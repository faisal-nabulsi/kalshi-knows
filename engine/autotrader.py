"""Auto-bettor for Kalshi Knows. DEMO exchange (play money) or dry-run only. Never production.

Rules = {id, name, enabled, trigger, action, limits}.  Triggers: alert | mover | dutchbook.
Actions: buy yes/no on a target ticker (limit = ask + max_slippage), or alert_only.
Modes: dry_run (default; builds the signed request it WOULD send, simulates the fill on the live
public order book + Kalshi taker fee) and demo (sends to external-api.demo.kalshi.co, then polls status/fills).
Hooks into engine/live.py: autotrader.on_alert(alert, game), autotrader.router, autotrader.start(get_engine).
"""
from __future__ import annotations

import hashlib
import json
import os
import logging
import math
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from engine import kalshi, kalshi_auth

log = logging.getLogger("auto")
ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "engine" / "logs" / "auto"
DIR.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="auto")

DEFAULT_SETTINGS = {"mode": "dry_run", "kill": False, "daily_loss_cap_usd": 25.0, "max_open_exposure_usd": 100.0}
HARD_MAX_CONTRACTS = 100          # absolute ceiling regardless of rule limits

STARTER_RULES = [
    {"id": "r_sf_td", "name": "49ers TD alert >=85% -> buy YES on SF game market", "enabled": True,
     "trigger": {"type": "alert", "team": "SF", "play_type": "TD", "min_confidence": 0.85, "named_only": True},
     "action": {"type": "buy", "side": "yes", "target": "same_game", "count": 5, "max_slippage": 0.02},
     "limits": {"max_contracts_per_order": 10, "max_usd_per_day": 10.0, "cooldown_s": 120}},
    {"id": "r_any_mover", "name": "Any Kalshi market moves >=15 pts in 60 s -> alert only", "enabled": True,
     "trigger": {"type": "mover", "scope": "any", "min_move": 0.15, "window_s": 60},
     "action": {"type": "alert_only"},
     "limits": {"max_contracts_per_order": 0, "max_usd_per_day": 0, "cooldown_s": 30}},
    {"id": "r_dutch", "name": "Dutch Book profit after fees > 0 -> buy all legs (1 set)", "enabled": True,
     "trigger": {"type": "dutchbook", "min_profit_after_fees": 0.0},
     "action": {"type": "buy_set", "sets": 1, "max_slippage": 0.02},
     "limits": {"max_contracts_per_order": 5, "max_usd_per_day": 20.0, "cooldown_s": 300}},
]

# ---------------------------------------------------------------- persistence

def _load(name, default):
    try:
        return json.loads((DIR / name).read_text())
    except (OSError, ValueError):
        return default


def _save(name, obj):
    tmp = DIR / (name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    tmp.replace(DIR / name)


SETTINGS = dict(DEFAULT_SETTINGS, **_load("settings.json", {}))
RULES: list[dict] = _load("rules.json", None) or [json.loads(json.dumps(r)) for r in STARTER_RULES]
ORDERS: list[dict] = _load("orders.json", [])
_cid_seen: set[str] = {o["client_order_id"] for o in ORDERS if o.get("client_order_id")}
_last_fire: dict[str, float] = {}
CACHE: dict = {"pnl": None, "pnl_ts": 0.0}
GET_ENGINE = lambda: None   # noqa: E731


def persist():
    with LOCK:
        _save("rules.json", RULES)
        _save("orders.json", ORDERS[-1500:])
        _save("settings.json", SETTINGS)


def day_key(ts_ms: int | None = None) -> str:
    return time.strftime("%Y-%m-%d", time.localtime((ts_ms or time.time() * 1000) / 1000))

# ---------------------------------------------------------------- pricing helpers

def kalshi_fee(count: int, price: float) -> float:
    """Taker fee: ceil(0.07 * C * P * (1-P)) to the cent."""
    return math.ceil(round(0.07 * count * price * (1 - price) * 100, 6)) / 100


def _lv(rows):
    out = []
    for p, q in rows or []:
        try:
            out.append((float(p), float(q)))
        except (TypeError, ValueError):
            pass
    return out


def parse_book(d: dict) -> dict:
    ob = d.get("orderbook_fp")
    if ob is not None:
        yes, no = _lv(ob.get("yes_dollars")), _lv(ob.get("no_dollars"))
    else:
        ob = d.get("orderbook") or {}
        yes = [(p / 100, q) for p, q in _lv(ob.get("yes"))]
        no = [(p / 100, q) for p, q in _lv(ob.get("no"))]
    return {"yes": sorted(yes, reverse=True), "no": sorted(no, reverse=True)}   # best bid first


_demo_lim = kalshi.RateLimiter(1.0)
_demo_http: httpx.Client | None = None


def demo_client() -> httpx.Client:
    global _demo_http
    if _demo_http is None:
        _demo_http = httpx.Client(base_url=kalshi_auth.DEMO_BASE, timeout=httpx.Timeout(8.0, connect=4.0),
                                  headers={"User-Agent": "kalshi-knows-hackathon/0.1"})
    return _demo_http


def demo_get_public(path: str, params=None) -> dict:
    kalshi_auth.assert_demo_url(kalshi_auth.DEMO_BASE + path)
    _demo_lim.wait()
    r = demo_client().get(path, params=params)
    r.raise_for_status()
    return r.json()


def fetch_book(ticker: str, demo: bool = False) -> dict:
    if demo:
        return parse_book(demo_get_public(f"/markets/{ticker}/orderbook", {"depth": 10}))
    return parse_book(kalshi.orderbook(ticker, depth=10))


def asks_for(book: dict, side: str) -> list[tuple[float, float]]:
    """Ask ladder for buying `side`: opposite-side bids flipped, cheapest first."""
    opp = book["no" if side == "yes" else "yes"]
    return sorted(((round(1 - p, 4), q) for p, q in opp if p > 0), key=lambda x: x[0])


def simulate_fill(book: dict, side: str, count: int, limit: float) -> dict:
    """Walk the real ask ladder up to the limit. Unfilled remainder would rest (not filled)."""
    left, fills = count, []
    for px, q in asks_for(book, side):
        if px > limit + 1e-9 or left <= 0:
            break
        n = int(min(left, q))
        if n > 0:
            fills.append({"price": px, "count": n})
            left -= n
    filled = count - left
    avg = sum(f["price"] * f["count"] for f in fills) / filled if filled else None
    fee = kalshi_fee(filled, avg) if filled else 0.0
    return {"fills": fills, "filled": filled, "avg_price": round(avg, 4) if avg else None, "fees": fee,
            "status": "filled" if left == 0 else ("partial" if filled else "resting")}

# ---------------------------------------------------------------- demo exchange

_demo_mk: dict = {"ts": 0.0, "set": set()}


def demo_listed(ticker: str) -> bool:
    now = time.time()
    if now - _demo_mk["ts"] > 600:
        try:
            s, cur = set(), None
            for _ in range(15):
                p = {"limit": 1000, "status": "open"}
                if cur:
                    p["cursor"] = cur
                d = demo_get_public("/markets", p)
                s |= {m["ticker"] for m in d.get("markets") or []}
                cur = d.get("cursor")
                if not cur:
                    break
            _demo_mk.update(ts=now, set=s)
        except Exception as e:
            log.warning("demo market list failed: %s", e)
            _demo_mk["ts"] = now - 540   # retry in a minute
    return ticker in _demo_mk["set"]


def demo_signed(method: str, endpoint: str, body: dict | None = None, params: dict | None = None) -> dict:
    req = kalshi_auth.build_request(method, endpoint, body)
    kalshi_auth.assert_demo_url(req["url"])
    _demo_lim.wait()
    r = demo_client().request(method, endpoint, params=params, json=body, headers=req["headers"])
    if r.status_code >= 400:
        raise RuntimeError(f"demo {method} {endpoint} -> {r.status_code} {r.text[:200]}")
    return r.json()


def _cents(p: float) -> int:
    return max(1, min(99, int(round(p * 100))))


def order_body(o: dict) -> dict:
    return {"ticker": o["ticker"], "action": "buy", "side": o["side"], "type": "limit", "count": o["count"],
            f"{o['side']}_price": _cents(o["limit_price"]), "client_order_id": o["client_order_id"],
            "time_in_force": "immediate_or_cancel"}


def order_body_v2(o: dict) -> dict:
    """Kalshi V2 create-order (POST /portfolio/events/orders; the v1 endpoint now returns 410).
    side 'bid' = buy YES at `price`; buying NO at p is the same as selling YES ('ask') at 1 - p."""
    if o["side"] == "yes":
        side, price = "bid", o["limit_price"]
    else:
        side, price = "ask", 1 - o["limit_price"]
    return {"ticker": o["ticker"], "client_order_id": o["client_order_id"], "side": side,
            "count": f"{float(o['count']):.2f}", "price": f"{min(max(price, 0.01), 0.99):.4f}",
            "time_in_force": "immediate_or_cancel", "self_trade_prevention_type": "taker_at_cross"}


def demo_place(o: dict):
    body = order_body_v2(o)
    d = demo_signed("POST", "/portfolio/events/orders", body)
    n = float(d.get("fill_count") or 0)
    avg = float(d["average_fill_price"]) if d.get("average_fill_price") else None
    if avg is not None and o["side"] == "no":
        avg = 1 - avg                                  # we sold YES; report the NO price we effectively paid
    o["demo"] = {"order_id": d.get("order_id"), "status": "filled" if n >= float(o["count"]) else ("partial" if n else "unfilled"),
                 "fill_count": n, "remaining": d.get("remaining_count"), "ts_ms": d.get("ts_ms"),
                 "fee_paid": d.get("average_fee_paid"), "request": body, "fills": []}
    with LOCK:
        if n:
            o.update(avg_price=round(avg, 4), filled=int(n), fees=round(float(d.get("average_fee_paid") or 0) * n, 4),
                     fills=[{"price": avg, "count": int(n)}])
        o["status"] = o["demo"]["status"]


def demo_refresh(o: dict):
    oid = (o.get("demo") or {}).get("order_id")
    if not oid or (o.get("demo") or {}).get("status") in ("filled", "unfilled", "partial"):
        return                                         # V2 IOC orders are final when placed
    od = demo_signed("GET", f"/portfolio/orders/{oid}").get("order") or {}
    fl = demo_signed("GET", "/portfolio/fills", params={"order_id": oid}).get("fills") or []
    fills = []
    for f in fl:
        px = f.get("yes_price_dollars") if o["side"] == "yes" else f.get("no_price_dollars")
        if px is None:
            px = (f.get("yes_price") if o["side"] == "yes" else f.get("no_price"))
            px = float(px) / 100 if px is not None else None
        fills.append({"price": float(px) if px is not None else o["limit_price"], "count": int(float(f.get("count_fp", f.get("count", 0))))})
    n = sum(f["count"] for f in fills)
    with LOCK:
        o["demo"].update(status=od.get("status"), fills=fills)
        o["fills"] = fills
        if n:
            avg = sum(f["price"] * f["count"] for f in fills) / n
            o.update(avg_price=round(avg, 4), fees=kalshi_fee(n, avg), filled=n)
        o["status"] = ("filled" if n >= o["count"] else "partial" if n else
                       ("resting" if od.get("status") in ("resting", "pending") else "unfilled"))

# ---------------------------------------------------------------- order pipeline

def _record_skip(rule, trig, reason, kind="order", ticker=None):
    with LOCK:
        o = {"id": f"o_{int(time.time()*1000)}_{len(ORDERS)}", "ts_ms": int(time.time() * 1000), "rule_id": rule["id"],
             "rule_name": rule["name"], "mode": "dry_run", "kind": kind, "status": "skipped", "reason": reason,
             "ticker": ticker, "trigger": trig, "client_order_id": None}
        ORDERS.append(o)
        persist()
    return o


def _spent_today(rule_id: str) -> float:
    d = day_key()
    return sum(o.get("count", 0) * o.get("limit_price", 0) for o in ORDERS
               if o["rule_id"] == rule_id and o.get("kind") == "order" and o["status"] != "skipped"
               and day_key(o["ts_ms"]) == d)


def _cid(rule_id: str, key: str, idx: int = 0) -> str:
    return "kk-" + hashlib.sha1(f"{rule_id}|{key}|{idx}".encode()).hexdigest()[:24]


def submit_order(rule: dict, trig: dict, ticker: str, side: str, count: int, key: str, idx: int = 0,
                 max_slippage: float = 0.02, group: str | None = None, force_dry: bool = False) -> dict | None:
    """Apply limits + idempotency, price off the live book, then simulate (dry_run) or send (demo)."""
    lim = rule.get("limits") or {}
    cid = _cid(rule["id"], key, idx)
    with LOCK:
        if cid in _cid_seen:
            return None                                   # idempotent: this trigger was already handled
        _cid_seen.add(cid)
        if SETTINGS["kill"]:
            return _record_skip(rule, trig, "kill switch on", ticker=ticker)
        pnl = CACHE.get("pnl") or {}
        if pnl.get("today", 0) <= -abs(SETTINGS["daily_loss_cap_usd"]):
            return _record_skip(rule, trig, "global daily loss cap hit", ticker=ticker)
        if (pnl.get("exposure", 0) or 0) >= SETTINGS["max_open_exposure_usd"]:
            return _record_skip(rule, trig, "max open exposure reached", ticker=ticker)
    count = int(min(count, lim.get("max_contracts_per_order") or HARD_MAX_CONTRACTS, HARD_MAX_CONTRACTS))
    if count <= 0:
        return _record_skip(rule, trig, "count is 0 after limits", ticker=ticker)
    want_demo = SETTINGS["mode"] == "demo" and kalshi_auth.have_credentials() and not force_dry
    note = None
    use_demo = False
    if want_demo:
        try:
            use_demo = demo_listed(ticker)
        except Exception:
            use_demo = False
        if not use_demo:
            note = "not listed on demo: staying dry-run for this order"
    try:
        book = fetch_book(ticker, demo=use_demo)
    except Exception as e:
        return _record_skip(rule, trig, f"no order book: {str(e)[:80]}", ticker=ticker)
    ladder = asks_for(book, side)
    if not ladder:
        return _record_skip(rule, trig, "no ask liquidity", ticker=ticker)
    ask = ladder[0][0]
    limit = round(min(0.99, ask + max_slippage), 2)
    cap = lim.get("max_usd_per_day")
    if cap is not None and _spent_today(rule["id"]) + count * limit > cap + 1e-9:
        return _record_skip(rule, trig, f"rule daily $ cap ${cap:.2f} reached", ticker=ticker)
    o = {"id": f"o_{int(time.time()*1000)}_{len(ORDERS)}", "ts_ms": int(time.time() * 1000), "rule_id": rule["id"],
         "rule_name": rule["name"], "kind": "order", "mode": "demo" if use_demo else "dry_run", "ticker": ticker,
         "side": side, "action": "buy", "count": count, "limit_price": limit, "ask_at_signal": ask,
         "client_order_id": cid, "group": group, "trigger": trig, "note": note, "status": "new", "fills": [],
         "avg_price": None, "fees": 0.0, "filled": 0}
    o["request"] = kalshi_auth.build_request("POST", "/portfolio/orders", order_body(o), preview=True)
    try:
        if use_demo:
            demo_place(o)
            demo_refresh(o)
        else:
            sim = simulate_fill(book, side, count, limit)
            o.update(fills=sim["fills"], filled=sim["filled"], avg_price=sim["avg_price"], fees=sim["fees"],
                     status=sim["status"])
    except Exception as e:
        o.update(status="rejected", reason=str(e)[:200])
        log.warning("order failed: %s", e)
    with LOCK:
        ORDERS.append(o)
        persist()
    log.info("AUTO %s %s %s %s x%d @%.2f -> %s", o["mode"], rule["id"], side, ticker, count, limit, o["status"])
    return o

# ---------------------------------------------------------------- rule matching

def _cooldown_ok(rule: dict, key: str = "") -> bool:
    cd = (rule.get("limits") or {}).get("cooldown_s", 0) or 0
    k = rule["id"] + "|" + key
    now = time.time()
    if now - _last_fire.get(k, 0) < cd:
        return False
    _last_fire[k] = now
    return True


def _enabled(kind: str):
    return [r for r in RULES if r.get("enabled") and (r.get("trigger") or {}).get("type") == kind]


def on_alert(alert: dict, game: dict | None = None, force: bool = False) -> None:
    """Called by live.py after an alert is created. Never raises, never blocks the engine."""
    try:
        if str(alert.get("id", "")).startswith("r_"):
            return                      # replay-mode alerts never trade
        for rule in _enabled("alert"):
            POOL.submit(_run_alert_rule, rule, alert, game or {}, force)
    except Exception as e:      # noqa: BLE001
        log.warning("on_alert: %s", e)


def alert_matches(t: dict, a: dict) -> bool:
    if t.get("named_only", True) and not a.get("named", True):
        return False
    team = (t.get("team") or "").strip()
    if team and team.lower() not in ("any", "*") and team.lower() != str(a.get("team", "")).lower() \
            and team.lower() not in str(a.get("headline", "")).lower():
        return False
    inf = a.get("inferred") or []
    top = inf[0] if inf else {}
    ptype = (t.get("play_type") or "").upper()
    if ptype and ptype not in ("ANY", "*") and top.get("type") != ptype:
        return False
    return float(top.get("prob", 0)) >= float(t.get("min_confidence", 0))


def _run_alert_rule(rule, alert, game, force=False):
    try:
        t, act = rule["trigger"], rule.get("action") or {}
        if not alert_matches(t, alert):
            return
        if not force and not _cooldown_ok(rule, alert.get("game_id", "")):
            return
        trig = {"type": "alert", "alert_id": alert["id"], "headline": alert.get("headline"), "team": alert.get("team"),
                "short_name": alert.get("short_name")}
        if act.get("type") == "alert_only":
            return _alert_only(rule, trig, f"alert:{alert['id']}")
        ticker = act.get("ticker")
        if act.get("target", "same_game") == "same_game":
            ticker = game.get("kalshi_home") if alert.get("team") == game.get("home") else game.get("kalshi_away")
        if not ticker:
            return _record_skip(rule, trig, "no target market for this game")
        submit_order(rule, trig, ticker, act.get("side", "yes"), int(act.get("count", 1)), f"alert:{alert['id']}",
                     max_slippage=float(act.get("max_slippage", 0.02)))
    except Exception as e:      # noqa: BLE001
        log.exception("alert rule failed: %s", e)


def _alert_only(rule, trig, key):
    cid = _cid(rule["id"], key)
    with LOCK:
        if cid in _cid_seen:
            return None
        _cid_seen.add(cid)
        o = {"id": f"o_{int(time.time()*1000)}_{len(ORDERS)}", "ts_ms": int(time.time() * 1000), "rule_id": rule["id"],
             "rule_name": rule["name"], "mode": "dry_run", "kind": "alert_only", "status": "alerted",
             "ticker": trig.get("ticker"), "trigger": trig, "client_order_id": cid}
        ORDERS.append(o)
        persist()
        return o


def check_dutchbook(db: dict | None):
    if not db:
        return
    for rule in _enabled("dutchbook"):
        t = rule["trigger"]
        for opp in db.get("opportunities") or []:
            if float(opp.get("profit_after_fees", 0)) <= float(t.get("min_profit_after_fees", 0)):
                continue
            POOL.submit(_run_dutch, rule, opp)


def _run_dutch(rule, opp):
    try:
        key = f"db:{opp.get('id') or opp.get('event_ticker')}:{int(time.time() // 900)}"
        if _cid(rule["id"], key, 0) in _cid_seen or not _cooldown_ok(rule, str(opp.get("id"))):
            return
        trig = {"type": "dutchbook", "opp_id": opp.get("id"), "title": opp.get("title"),
                "profit_after_fees": opp.get("profit_after_fees")}
        sets = int((rule.get("action") or {}).get("sets", 1))
        legs = opp.get("legs") or []
        if SETTINGS["mode"] == "demo" and kalshi_auth.have_credentials() and not all(demo_listed(l["ticker"]) for l in legs):
            note = "some legs not listed on demo: whole set stays dry-run"
        else:
            note = None
        for i, l in enumerate(legs):
            o = submit_order(rule, trig, l["ticker"], l.get("side", "yes"), int(l.get("qty", 1)) * sets, key, idx=i,
                             max_slippage=float((rule.get("action") or {}).get("max_slippage", 0.02)),
                             group=f"set:{opp.get('id')}", force_dry=bool(note))
            if o and note:
                o["note"] = note
    except Exception as e:      # noqa: BLE001
        log.exception("dutch rule failed: %s", e)

# ---------------------------------------------------------------- movers scanner (any category)

POLITICS_SERIES = ("KXPRES", "KXSENATE", "KXHOUSE", "KXGOV", "KXELECT", "KXTRUMP", "KXBIDEN", "KXVANCE", "KXMAYOR",
                   "KXPOLL", "KXCONGRESS", "KXPARTY", "KXIMPEACH", "KXCABINET", "KXDEM", "KXGOP", "KXPOLITICS")
POLITICS_RE = re.compile(r"\b(election|elections|senate|senator|president|presidential|congress|congressional|"
                         r"governor|trump|biden|vance|democrat\w*|republican\w*|mayor|impeach\w*|nominee|"
                         r"primary|gop|speaker of the house)\b", re.I)
CATS = [("Sports", ("NFL", "NBA", "NCAA", "MLB", "NHL", "WNBA", "MLS", "UFC", "SOCCER", "EPL", "TENNIS", "GOLF", "PGA",
                    "F1", "NASCAR", "BOXING", "CRICKET", "ATP", "WTA", "UCL", "LALIGA", "BUNDES", "SERIEA", "MMA", "ESPORT")),
        ("Weather", ("HIGH", "LOW", "RAIN", "SNOW", "TEMP", "HURR", "WEATHER", "STORM")),
        ("Crypto", ("BTC", "ETH", "SOL", "DOGE", "XRP", "CRYPTO")),
        ("Economics", ("CPI", "FED", "GDP", "JOBS", "UNRATE", "PAYROLL", "INFL", "RATE", "FOMC", "PCE", "RECESS", "OIL", "GAS")),
        ("Financials", ("INX", "NASDAQ", "SPX", "TSLA", "NVDA", "AAPL", "STOCK", "GOLD", "USD", "EURUSD")),
        ("Culture", ("OSCAR", "EMMY", "GRAMMY", "MOVIE", "BOXOFFICE", "SONG", "BILLBOARD", "SPOTIFY", "NETFLIX", "TV", "TAYLOR", "ALBUM"))]


def series_of(ticker: str) -> str:
    return ticker.split("-")[0]


def category_of(ticker: str) -> str:
    s = series_of(ticker).upper().removeprefix("KX")
    for name, keys in CATS:
        if any(s.startswith(k) or k in s[:12] for k in keys):
            return name
    return "Other"


def is_politics(m: dict) -> bool:
    s = series_of(m["ticker"]).upper()
    return s.startswith(POLITICS_SERIES) or bool(POLITICS_RE.search(m.get("title") or ""))


def price_of(m: dict) -> float | None:
    # last trade price only: mixing mid and last prices fabricates "moves" on wide, illiquid books
    px = kalshi.market_prices(m)
    return px["last"] if px["last"] else None


HIST: dict[str, deque] = {}
META: dict[str, dict] = {}
MOVERS: deque = deque(maxlen=200)
SCAN = {"ts": 0, "markets_seen": 0, "tracked": 0, "pages": 0, "err": None}
SCAN_INTERVAL = 30
TOP_N = 600
MAX_PAGES = 6
_last_feed: dict[str, float] = {}


def move_over(ticker: str, window_s: float, now: float | None = None):
    h = HIST.get(ticker)
    if not h or len(h) < 2:
        return None
    now = now or h[-1][0]
    cur = h[-1][1]
    best = None
    for ts, p in h:                      # oldest sample that is within 2x window, at least 0.5x window old
        age = now - ts
        if 0.5 * window_s <= age <= 2 * window_s:
            best = (ts, p)
            break
    if not best:
        return None
    return {"p_then": best[1], "p_now": cur, "move": cur - best[1], "age_s": now - best[0]}


def scan_once():
    markets, cursor, pages = [], None, 0
    for _ in range(MAX_PAGES):
        kalshi.BG_LIMITER.wait()
        p = {"limit": 1000, "status": "open", "mve_filter": "exclude"}
        if cursor:
            p["cursor"] = cursor
        d = kalshi.get("/markets", p)
        markets += d.get("markets") or []
        pages += 1
        cursor = d.get("cursor")
        if not cursor:
            break
        time.sleep(1.1)                  # scanner stays <= 1 req/s
    now = time.time()
    act = []
    for m in markets:
        try:
            v = float(m.get("volume_24h_fp") or 0)
        except ValueError:
            v = 0
        if v >= 10 and not is_politics(m):
            act.append((v, m))
    act.sort(key=lambda x: -x[0])
    for v, m in act[:TOP_N]:
        pr = price_of(m)
        if pr is None:
            continue
        t = m["ticker"]
        h = HIST.setdefault(t, deque(maxlen=60))
        h.append((now, pr))
        px = kalshi.market_prices(m)
        META[t] = {"title": m.get("title"), "category": category_of(t), "series": series_of(t), "vol": v,
                   "bid": px["bid"], "ask": px["ask"], "yes_sub": m.get("yes_sub_title")}
    SCAN.update(ts=int(now * 1000), markets_seen=len(markets), tracked=len(HIST), pages=pages, err=None)
    # feed: biggest move over 60/180/300 s
    for t in list(HIST):
        if now - HIST[t][-1][0] > 120:
            HIST.pop(t, None)
            continue
        for w in (60, 180, 300):
            mv = move_over(t, w, HIST[t][-1][0])
            if mv and abs(mv["move"]) >= 0.05 and now - _last_feed.get(t, 0) > 120:
                _last_feed[t] = now
                MOVERS.appendleft({"ts_ms": int(now * 1000), "ticker": t, "window_s": w, **{k: round(v, 4) for k, v in mv.items()},
                                   **{k: META[t][k] for k in ("title", "category", "series", "vol", "bid", "ask")}})
                break
    evaluate_mover_rules(now)


def evaluate_mover_rules(now: float):
    for rule in _enabled("mover"):
        t, fired = rule["trigger"], 0
        w, thr = float(t.get("window_s", 60)), float(t.get("min_move", 0.15))
        for tk in list(HIST):
            if fired >= 3:
                break
            if not _mover_scope(t, tk):
                continue
            mv = move_over(tk, w, HIST[tk][-1][0])
            if not mv or abs(mv["move"]) < thr:
                continue
            key = f"mv:{tk}:{int(now // 600)}"
            if _cid(rule["id"], key) in _cid_seen:
                continue
            fired += 1
            trig = {"type": "mover", "ticker": tk, "title": META.get(tk, {}).get("title"), "category": META.get(tk, {}).get("category"),
                    "move": round(mv["move"], 4), "p_then": round(mv["p_then"], 4), "p_now": round(mv["p_now"], 4), "window_s": w}
            act = rule.get("action") or {}
            if act.get("type") == "alert_only":
                _alert_only(rule, trig, key)
            else:
                up = (mv["move"] > 0) == (act.get("direction", "follow") == "follow")
                side = act.get("side") or ("yes" if up else "no")
                POOL.submit(submit_order, rule, trig, tk, side, int(act.get("count", 1)), key,
                            0, float(act.get("max_slippage", 0.02)))


def _mover_scope(t: dict, tk: str) -> bool:
    sc = t.get("scope", "any")
    if sc == "any":
        return True
    if sc == "ticker":
        return tk == t.get("ticker")
    if sc == "series":
        return series_of(tk).upper() == str(t.get("series", "")).upper()
    if sc == "category":
        return META.get(tk, {}).get("category") == t.get("category")
    return False

# ---------------------------------------------------------------- P&L / exposure

def compute_portfolio() -> dict:
    with LOCK:
        filled = [o for o in ORDERS if o.get("kind") == "order" and o.get("filled")]
    prod = sorted({o["ticker"] for o in filled if o["mode"] == "dry_run"})
    dem = sorted({o["ticker"] for o in filled if o["mode"] == "demo"})
    qs: dict[str, dict] = {}
    try:
        qs.update({("p", k): v for k, v in kalshi.quotes(prod[:100]).items()})
    except Exception as e:      # noqa: BLE001
        log.debug("pnl quotes: %s", e)
    if dem:
        try:
            d = demo_get_public("/markets", {"tickers": ",".join(dem[:100]), "limit": 100})
            qs.update({("d", m["ticker"]): m for m in d.get("markets") or []})
        except Exception as e:      # noqa: BLE001
            log.debug("demo pnl quotes: %s", e)
    tot = today = exp = 0.0
    d0 = day_key()
    for o in filled:
        m = qs.get(("d" if o["mode"] == "demo" else "p", o["ticker"]))
        n, cost = o["filled"], o["filled"] * (o["avg_price"] or 0)
        mark, settled = None, False
        if m:
            res = (m.get("result") or "").lower()
            if res in ("yes", "no"):
                mark, settled = (1.0 if res == o["side"] else 0.0), True
            else:
                px = kalshi.market_prices(m)
                yb, ya = px["bid"], px["ask"]
                mark = yb if o["side"] == "yes" else (None if ya is None else 1 - ya)
        if mark is None:
            mark = o["avg_price"] or 0
        pnl = n * mark - cost - (o.get("fees") or 0)
        tot += pnl
        if day_key(o["ts_ms"]) == d0:
            today += pnl
        if not settled:
            exp += cost
    out = {"total": round(tot, 2), "today": round(today, 2), "exposure": round(exp, 2), "ts": time.time()}
    CACHE["pnl"], CACHE["pnl_ts"] = out, time.time()
    return out

# ---------------------------------------------------------------- background loops

_stop = threading.Event()


def _scanner_loop():
    while not _stop.is_set():
        try:
            scan_once()
        except Exception as e:      # noqa: BLE001
            SCAN["err"] = str(e)[:120]
            log.warning("mover scan failed: %s", e)
        _stop.wait(SCAN_INTERVAL)


def _poller_loop():
    n = 0
    while not _stop.is_set():
        n += 1
        try:
            if kalshi_auth.have_credentials():
                with LOCK:
                    live = [o for o in ORDERS if o.get("mode") == "demo" and o["status"] in ("submitted", "partial", "resting")]
                for o in live[-20:]:
                    demo_refresh(o)
                if live:
                    persist()
            if n % 6 == 1:
                compute_portfolio()
            eng = GET_ENGINE()
            if eng is not None and n % 6 == 2:
                check_dutchbook(getattr(eng, "dutchbook", None))
        except Exception as e:      # noqa: BLE001
            log.warning("poller: %s", e)
        _stop.wait(5)


_started = False


def start(get_engine=None):
    """Called once from live.py startup. Refuses to run if the environment points anywhere but demo."""
    global _started, GET_ENGINE
    kalshi_auth.guard_demo_only()
    if get_engine:
        GET_ENGINE = get_engine
    if SETTINGS["mode"] == "demo" and not kalshi_auth.have_credentials():
        SETTINGS["mode"] = "dry_run"
    if _started:
        return
    _started = True
    threading.Thread(target=_scanner_loop, daemon=True, name="auto-scan").start()
    threading.Thread(target=_poller_loop, daemon=True, name="auto-poll").start()
    log.info("autotrader started: mode=%s key=%s", SETTINGS["mode"], kalshi_auth.have_credentials())

# ---------------------------------------------------------------- API

router = APIRouter(prefix="/api/auto")


def validate_rule(r: dict) -> dict:
    t, a = r.get("trigger") or {}, r.get("action") or {}
    if t.get("type") not in ("alert", "mover", "dutchbook"):
        raise ValueError("trigger.type must be alert, mover or dutchbook")
    if a.get("type") not in ("buy", "buy_set", "alert_only"):
        raise ValueError("action.type must be buy, buy_set or alert_only")
    if a.get("type") == "buy" and a.get("side", "yes") not in ("yes", "no"):
        raise ValueError("side must be yes or no")
    if t["type"] == "mover" and not (0 < float(t.get("min_move", 0)) <= 1):
        raise ValueError("mover.min_move must be in (0,1]")
    rid = str(r.get("id") or "r_" + hashlib.sha1(json.dumps(r, sort_keys=True).encode()).hexdigest()[:8])
    return {"id": re.sub(r"[^A-Za-z0-9_\-]", "", rid)[:40], "name": str(r.get("name") or "Untitled rule")[:120],
            "enabled": bool(r.get("enabled", True)), "trigger": t, "action": a, "limits": r.get("limits") or {}}


@router.get("/rules")
def get_rules():
    return RULES


def _require_admin(request):
    """Control endpoints need the admin token (engine/.admin_token, or ADMIN_TOKEN env): the API URL is public."""
    from pathlib import Path as _P
    want = os.environ.get("ADMIN_TOKEN") or ((_P(__file__).parent / ".admin_token").read_text().strip()
                                              if (_P(__file__).parent / ".admin_token").exists() else "")
    got = request.headers.get("x-admin") or request.query_params.get("admin") or ""
    if not want or got != want:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="admin token required")


@router.post("/rules")
async def post_rule(request: Request):
    _require_admin(request)
    try:
        rule = validate_rule(await request.json())
    except (ValueError, TypeError) as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    with LOCK:
        for i, r in enumerate(RULES):
            if r["id"] == rule["id"]:
                RULES[i] = rule
                break
        else:
            RULES.append(rule)
        persist()
    return {"ok": True, "rule": rule}


@router.delete("/rules/{rule_id}")
def del_rule(rule_id: str, request: Request):
    _require_admin(request)
    with LOCK:
        RULES[:] = [r for r in RULES if r["id"] != rule_id]
        persist()
    return {"ok": True}


@router.get("/orders")
def get_orders(limit: int = 100, since_ms: int = 0):
    with LOCK:
        return [o for o in ORDERS if o["ts_ms"] > since_ms][-limit:][::-1]


@router.get("/status")
def get_status():
    pnl = CACHE.get("pnl") or compute_portfolio()
    cred = kalshi_auth.have_credentials()
    with LOCK:
        n = len(ORDERS)
    return {"mode": SETTINGS["mode"] if cred or SETTINGS["mode"] == "dry_run" else "dry_run", "key_present": cred,
            "demo_base": kalshi_auth.DEMO_BASE, "kill": SETTINGS["kill"], "pnl": pnl, "orders": n,
            "daily_loss_cap_usd": SETTINGS["daily_loss_cap_usd"], "max_open_exposure_usd": SETTINGS["max_open_exposure_usd"],
            "rules": len(RULES), "scanner": dict(SCAN), "play_money": True}


@router.post("/kill")
async def kill(request: Request):
    _require_admin(request)
    try:
        body = await request.json()
    except ValueError:
        body = {}
    SETTINGS["kill"] = bool(body.get("on", True))
    persist()
    return {"ok": True, "kill": SETTINGS["kill"]}


@router.post("/mode")
async def set_mode(request: Request):
    _require_admin(request)
    body = await request.json()
    m = body.get("mode")
    if m not in ("dry_run", "demo"):
        return JSONResponse({"ok": False, "error": "mode must be dry_run or demo"}, status_code=400)
    if m == "demo" and not kalshi_auth.have_credentials():
        return JSONResponse({"ok": False, "error": "no demo credentials (KALSHI_DEMO_KEY_ID + ~/.kalshi/demo_private_key.pem)"}, status_code=400)
    SETTINGS["mode"] = m
    persist()
    return {"ok": True, "mode": m}


@router.get("/movers")
def get_movers(limit: int = 60, category: str | None = None):
    items = [m for m in MOVERS if not category or m["category"] == category][:limit]
    return {"scanner": dict(SCAN), "movers": items}


@router.post("/replay_alert")
async def replay_alert(request: Request):
    _require_admin(request)
    """Run the alert rules against an existing alert (testing / demo). Bypasses cooldown, keeps idempotency."""
    body = await request.json()
    eng = GET_ENGINE()
    a = (getattr(eng, "alert_by_id", {}) or {}).get(body.get("alert_id"))
    if not a:
        return JSONResponse({"ok": False, "error": "unknown alert"}, status_code=404)
    g = (getattr(eng, "games", {}) or {}).get(a["game_id"], {})
    for rule in _enabled("alert"):
        _run_alert_rule(rule, a, g, force=True)
    return {"ok": True, "orders": get_orders(5)}

"""Live Picks: the cross-market XGBoost model (trained on 4.36M settled Kalshi markets, kaggle/xmarket/train_xmarket.py,
report train/xmarket/REPORT.md) scored on OPEN Kalshi markets, turned into bet recommendations.

Same rule as the backtest (Jan 2026, +12% after fees at 24 h, +6.7% at 6 h):
  - look at each market ONCE per horizon, when it is ~24 h or ~6 h from close (one look, like the backtest)
  - features from Kalshi's public trade tape up to now (last price, VWAP, momentum, volatility, counts, time, category)
  - recommend YES if model - price > threshold, NO if price - model > threshold (24 h: 8c, 6 h: 5c), only if the
    market had 5+ trades and 50+ contracts and trades between 3c and 97c
  - and only if the bet still has positive expected value after the taker fee at the price you'd actually pay (the ask)

Every recommendation goes into a forward-test ledger (engine/logs/picks/live_ledger.jsonl) priced at the real ask, then
graded when the market settles. That ledger is the honest scoreboard. New picks also push to subscribed phones and
fire the auto-bettor's "pick" rules (orders go to Kalshi's DEMO exchange only; engine/autotrader.py).
Public market data only. Politics markets are skipped.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter

from engine import kalshi

log = logging.getLogger("picks")
ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "engine" / "model" / "xmarket_xgb.json"
META = ROOT / "engine" / "model" / "xmarket_meta.json"
DIR = ROOT / "engine" / "logs" / "picks"
DIR.mkdir(parents=True, exist_ok=True)
LEDGER = DIR / "live_ledger.jsonl"
LOOKED = DIR / "looked.json"

# horizon -> (window of hours-to-close in which a market gets its one look, model h, edge threshold)
HORIZONS = {"24h": ((23.0, 25.0), 24.0, 0.08), "6h": ((5.5, 6.5), 6.0, 0.05)}
SCAN_EVERY_S = int(os.environ.get("PICKS_SCAN_S", "1200"))     # 20 min < each look window, so every market gets a look
MAX_CANDIDATES = int(os.environ.get("PICKS_MAX_CANDIDATES", "160"))
MIN_EV_CENTS = float(os.environ.get("PICKS_MIN_EV_CENTS", "1.0"))
PUSH_PER_SCAN = int(os.environ.get("PICKS_PUSH_PER_SCAN", "3"))
QUIET = os.environ.get("PICKS_QUIET", "0-8")                   # local hours with no pick pushes (picks still logged)
STAKE_USD = 10.0                                               # forward-test sizing, same as the backtest chart

POLITICS_RE = re.compile(r"\b(election|elections|senate|senator|president|presidential|congress|congressional|governor|"
                         r"trump|biden|vance|democrat\w*|republican\w*|mayor|impeach\w*|nominee|primary|gop)\b", re.I)
POLITICS_GROUPS = ("politics", "elections", "world")

_lock = threading.RLock()
STATE: dict = {"generated_ms": None, "scanning": False, "looked": 0, "candidates": 0, "picks": [], "near": [],
               "err": None, "scorer": None, "scan_s": None}
_model = {"bst": None, "meta": None, "dtypes": None}


# ---------------------------------------------------------------- model

def load_model():
    if _model["bst"] is not None:
        return _model
    import xgboost as xgb
    meta = json.loads(META.read_text())
    bst = xgb.Booster()
    bst.load_model(str(MODEL))
    _model.update(bst=bst, meta=meta, dtypes={
        "group_c": pd.CategoricalDtype(meta["group_cats"]), "cat_c": pd.CategoricalDtype(meta["cat_cats"]),
        "series_c": pd.CategoricalDtype(meta["series_cats"])})
    try:
        from engine.vendor import jb_categories as jb       # Jon-Becker's ticker -> category map, for unseen series
        _model["jb"] = jb
    except Exception:       # noqa: BLE001
        _model["jb"] = None
    STATE["scorer"] = f"XGBoost cross-market model ({meta.get('trained', 'kaggle/xmarket')})"
    return _model


def category(series: str) -> tuple[str, str]:
    m = load_model()
    hit = m["meta"]["series_map"].get(series)
    if hit:
        return hit[0], hit[1]
    if m.get("jb") is not None:
        try:
            g = m["jb"].get_hierarchy(series)
            return g[0], g[1]
        except Exception:       # noqa: BLE001
            pass
    return "Other", "Other"


def lg(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def score(rows: list[dict]) -> np.ndarray:
    """rows: dicts with every training feature (raw, before categorical encoding). Returns P(YES)."""
    import xgboost as xgb
    m = load_model()
    feats = m["meta"]["features"]
    df = pd.DataFrame(rows)
    top = set(m["meta"]["series_cats"])
    df["series_c"] = pd.Categorical(np.where(df["series"].isin(top), df["series"], "_rare"), dtype=m["dtypes"]["series_c"])
    df["group_c"] = pd.Categorical(df["group"], dtype=m["dtypes"]["group_c"])
    df["cat_c"] = pd.Categorical(df["cat"], dtype=m["dtypes"]["cat_c"])
    X = df[feats].copy()
    for c in feats:
        if c not in ("group_c", "cat_c", "series_c"):
            X[c] = X[c].astype("float32")
    d = xgb.DMatrix(X, base_margin=lg(df["price"].values), enable_categorical=True)
    return m["bst"].predict(d, iteration_range=(0, int(m["meta"]["best_iteration"]) + 1))


# ---------------------------------------------------------------- Kalshi public data

def bg_get(path: str, params: dict) -> dict:
    return big_get(path, params)        # background budget: never starves the live game polling


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def series_of(m: dict) -> str:
    et = m.get("event_ticker") or m["ticker"]
    hit = re.match(r"^([A-Z0-9]+)", et)
    return hit.group(1) if hit else "independent"


def eff_close(m: dict) -> float:
    """When the market will really close. Training used the ACTUAL close of settled markets; sports markets
    (can_close_early) close right after the game, but an open market's close_time is the latest possible
    expiration, days later. So use expected_expiration_time for those."""
    if m.get("can_close_early") and m.get("expected_expiration_time"):
        return _ts(m["expected_expiration_time"])
    return _ts(m["close_time"])


_cache: dict = {"ts": 0.0, "markets": []}
_http = {"c": None}
EARLY_CLOSE_SLACK_H = 72      # sports markets list close_time up to ~2-3 days after the game (BUF@LAR: +45 h)


def _client():
    import httpx
    if _http["c"] is None:
        _http["c"] = httpx.Client(base_url=kalshi.BASE, timeout=httpx.Timeout(25.0, connect=6.0),
                                  headers={"User-Agent": "kalshi-knows-picks/0.2 (public data only)"})
    return _http["c"]


def big_get(path: str, params: dict) -> dict:
    """Background GET for the big /markets pages (slow to serve): longer timeout, background rate budget."""
    for i in range(4):
        kalshi.BG_LIMITER.wait()
        try:
            r = _client().get(path, params=params)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"status {r.status_code}")
            r.raise_for_status()
            return r.json()
        except Exception as e:      # noqa: BLE001
            if i == 3:
                raise
            time.sleep(1.5 * (i + 1))
            log.debug("retry %s: %s", path, e)
    return {}


def open_markets(lo_h: float, hi_h: float, now: float) -> list[dict]:
    """Open single-leg markets whose effective close is lo_h..hi_h hours away. One paged pull per scan covers both
    horizons: close_time from the earliest window start to the latest window end + the early-close slack."""
    if now - _cache["ts"] > 300:
        lo = min(w[0] for w, _, _ in HORIZONS.values())
        hi = max(w[1] for w, _, _ in HORIZONS.values()) + EARLY_CLOSE_SLACK_H
        out, cur = [], None
        for _ in range(30):
            p = {"status": "open", "mve_filter": "exclude", "limit": 1000,
                 "min_close_ts": int(now + lo * 3600), "max_close_ts": int(now + hi * 3600)}
            if cur:
                p["cursor"] = cur
            try:
                d = big_get("/markets", p)
            except Exception as e:      # noqa: BLE001
                log.warning("market list stopped after %d markets: %s", len(out), e)
                break
            out += d.get("markets") or []
            cur = d.get("cursor")
            if not cur:
                break
        _cache.update(ts=now, markets=out)
    res = []
    for m in _cache["markets"]:
        try:
            hrs = (eff_close(m) - now) / 3600
        except Exception:       # noqa: BLE001
            continue
        if lo_h <= hrs <= hi_h:
            res.append(m)
    return res


def trade_tape(ticker: str, max_pages: int = 5) -> tuple[list[tuple], bool]:
    """(ts, price, contracts, taker_yes) oldest first; truncated=True if the tape is longer than we fetched."""
    tr, cur = [], None
    for _ in range(max_pages):
        p = {"ticker": ticker, "limit": 1000}
        if cur:
            p["cursor"] = cur
        d = bg_get("/markets/trades", p)
        for t in d.get("trades") or []:
            px = _f(t.get("yes_price_dollars"))
            if px is None and t.get("yes_price") is not None:
                px = float(t["yes_price"]) / 100
            if px is None:
                continue
            tr.append((_ts(t["created_time"]), px, float(t.get("count_fp") or t.get("count") or 0),
                       1.0 if t.get("taker_side") == "yes" else 0.0))
        cur = d.get("cursor")
        if not cur:
            tr.sort()
            return tr, False
    tr.sort()
    return tr, True


def features(m: dict, tr: list[tuple], now: float, h: float) -> dict | None:
    """The training features (train_xmarket.py long table) with the cutoff = now."""
    if not tr:
        return None
    close_ts = eff_close(m)
    last_ts, price = tr[-1][0], min(max(tr[-1][1], 0.01), 0.99)
    w24 = [t for t in tr if t[0] >= now - 86400]

    def before(s):
        b = [t for t in tr if t[0] < now - s]
        return b[-1][1] if b else None

    ct24 = sum(t[2] for t in w24)
    ct_all = sum(t[2] for t in tr)
    vol = _f(m.get("volume_fp")) or _f(m.get("volume"))
    if vol and vol > ct_all:                 # truncated tape: the market's own volume counter is exact
        ct_all = vol
    vwap24 = sum(t[1] * t[2] for t in w24) / ct24 if ct24 else price
    vw_n = sum(t[2] for t in tr)
    vwap_all = sum(t[1] * t[2] for t in tr) / vw_n if vw_n else price
    p6, p24 = before(21600), before(86400)
    ps = [t[1] for t in w24]
    std24 = float(np.std(ps)) if ps else 0.0
    try:
        open_ts = _ts(m["open_time"])
    except Exception:       # noqa: BLE001
        open_ts = tr[0][0]
    ser = series_of(m)
    grp, cat = category(ser)
    return {
        "price": price, "logit_p": float(lg(price)), "h": h, "vwap24": vwap24, "vwap_all": vwap_all,
        "mom6": price - p6 if p6 is not None else 0.0, "mom24": price - p24 if p24 is not None else 0.0,
        "price_vs_vwap": price - vwap24, "std24": std24,
        "n_tr": math.log1p(len(tr)), "n_tr24": math.log1p(len(w24)), "ct": math.log1p(ct_all), "ct24": math.log1p(ct24),
        "yes_share24": (sum(t[2] * t[3] for t in w24) / ct24) if ct24 else 0.5,
        "hrs_since_last": math.log1p(max(0.0, (now - last_ts) / 3600)),
        "lifetime_h": math.log1p(max(0.0, (now - open_ts) / 3600)),
        "close_hour": int(close_ts // 3600) % 24, "close_dow": int(close_ts // 86400 + 4) % 7,
        "mom6_missing": int(p6 is None), "group": grp, "cat": cat, "series": ser,
        # raw values for eligibility + display (not model inputs)
        "_raw_n_tr": len(tr), "_raw_ct": ct_all, "_close_ts": close_ts,
    }


# ---------------------------------------------------------------- pick logic

def fee_pc(P: float, C: int = 10) -> float:
    """Kalshi taker fee per contract (dollars) for an order of C contracts at price P: ceil(0.07*C*P*(1-P)) cents."""
    return math.ceil(round(0.07 * C * P * (1 - P) * 100, 6)) / 100 / C


def max_fair_price(q: float, min_ev: float) -> float:
    """Highest price (to the cent) at which buying a side the model gives probability q still clears min_ev after fees."""
    for c in range(99, 0, -1):
        P = c / 100
        if q - P - fee_pc(P) >= min_ev:
            return P
    return 0.0


def is_politics(m: dict, grp: str) -> bool:
    return grp.lower() in POLITICS_GROUPS or bool(POLITICS_RE.search((m.get("title") or "") + " " + (m.get("event_ticker") or "")))


def decide(m: dict, f: dict, p_yes: float, hz: str, thr: float) -> dict:
    """Backtest rule + an executable-price check. Returns the full record (qualifies True/False)."""
    price = f["price"]
    px = kalshi.market_prices(m)
    side = "yes" if p_yes - price > 0 else "no"
    edge = abs(p_yes - price)
    q = p_yes if side == "yes" else 1 - p_yes
    ask = px["ask"] if side == "yes" else (None if px["bid"] is None else round(1 - px["bid"], 4))
    elig = f["_raw_n_tr"] >= 5 and f["_raw_ct"] >= 50 and 0.03 <= price <= 0.97
    ev_ask = None if not ask or ask <= 0 or ask >= 1 else (q - ask - fee_pc(ask)) * 100
    ok = elig and edge > thr and ev_ask is not None and ev_ask >= MIN_EV_CENTS
    why = ("ok" if ok else "not eligible (thin or extreme price)" if not elig else f"edge {edge * 100:.1f}c under {thr * 100:.0f}c"
           if edge <= thr else "no ask to buy at" if ev_ask is None else f"at the ask ({ask * 100:.0f}c) EV is {ev_ask:+.1f}c after fees")
    return {
        "ticker": m["ticker"], "event_ticker": m.get("event_ticker"), "title": m.get("title") or "",
        "yes_label": m.get("yes_sub_title") or "", "series": f["series"], "group": f["group"], "category": f["cat"],
        "horizon": hz, "close_ms": int(f["_close_ts"] * 1000), "side": side.upper(),
        "model_prob": round(float(p_yes), 4), "market_price": round(price, 4), "edge_cents": round(edge * 100, 1),
        "ask": ask, "model_q": round(float(q), 4), "max_price": max_fair_price(q, MIN_EV_CENTS / 100),
        "fee_cents_per_contract": round(fee_pc(ask) * 100, 2) if ask else None,
        "ev_cents_per_contract": round(ev_ask, 2) if ev_ask is not None else None,
        "trades": f["_raw_n_tr"], "contracts": round(f["_raw_ct"]), "qualifies": bool(ok), "why": why,
        "url": f"https://kalshi.com/markets/{f['series'].lower()}",
    }


# ---------------------------------------------------------------- ledger (forward test)

def _ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def _write_ledger(rows: list[dict]):
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in rows))
    tmp.replace(LEDGER)


def settle_ledger() -> int:
    """Grade picks whose markets have settled. P&L per contract at the ask we'd have paid, after the taker fee."""
    with _lock:
        rows = _ledger()
        open_ = [r for r in rows if r.get("result") is None and r["close_ms"] < time.time() * 1000 + 3600_000]
        if not open_:
            return 0
        res: dict[str, dict] = {}
        tks = sorted({r["ticker"] for r in open_})
        for i in range(0, len(tks), 100):
            d = bg_get("/markets", {"tickers": ",".join(tks[i:i + 100]), "limit": 100})
            res.update({m["ticker"]: m for m in d.get("markets") or []})
        n = 0
        for r in rows:
            m = res.get(r["ticker"])
            if r.get("result") is not None or not m:
                continue
            out = (m.get("result") or "").lower()
            if out not in ("yes", "no"):
                continue
            win = 1.0 if out == r["side"].lower() else 0.0
            P = r["entry"]
            r.update(result=out, won=bool(win), settled_ms=int(time.time() * 1000),
                     pnl_cents=round((win - P - fee_pc(P)) * 100, 2),
                     pnl_stake=round(r["contracts_at_stake"] * (win - P - fee_pc(P)), 2))
            n += 1
        if n:
            _write_ledger(rows)
        return n


def summary() -> dict:
    rows = _ledger()
    done = [r for r in rows if r.get("result") is not None]
    staked = sum(r["contracts_at_stake"] * r["entry"] for r in done)
    pnl = sum(r["pnl_stake"] for r in done)
    return {"picks": len(rows), "settled": len(done), "open": len(rows) - len(done),
            "won": sum(1 for r in done if r["won"]), "win_rate": (sum(1 for r in done if r["won"]) / len(done)) if done else None,
            "pnl_cents_per_contract": (sum(r["pnl_cents"] for r in done) / len(done)) if done else None,
            "pnl_usd_at_10_per_bet": round(pnl, 2), "staked_usd": round(staked, 2), "roi": (pnl / staked) if staked else None,
            "since_ms": rows[0]["ts_ms"] if rows else None}


# ---------------------------------------------------------------- scan loop

def _quiet_now() -> bool:
    try:
        a, b = (int(x) for x in QUIET.split("-"))
    except ValueError:
        return False
    h = time.localtime().tm_hour
    return (a <= h < b) if a <= b else (h >= a or h < b)


def _push(new: list[dict]):
    if not new or _quiet_now() or os.environ.get("PICKS_PUSH", "1") == "0":
        return
    try:
        from engine import push
        top = sorted(new, key=lambda r: -(r["ev_cents_per_contract"] or 0))
        for r in top[:PUSH_PER_SCAN]:
            label = f"{r['title']}" + (f" ({r['yes_label']})" if r["yes_label"] and r["yes_label"] not in r["title"] else "")
            hrs = max(0.0, (r["close_ms"] / 1000 - time.time()) / 3600)
            push.send_all({"title": f"PICK · BUY {r['side']} at {round(r['ask'] * 100)}¢",
                           "body": f"{label}. Model: {round(r['model_q'] * 100)}% {r['side']}, edge +{r['ev_cents_per_contract']:.0f}¢ "
                                   f"after fees. Don't pay over {round(r['max_price'] * 100)}¢. Closes in {hrs:.0f}h.",
                           "url": "./#picks", "tag": f"pick-{r['ticker']}"})
        if len(top) > PUSH_PER_SCAN:
            push.send_all({"title": f"+{len(top) - PUSH_PER_SCAN} more picks", "body": "Open Kalshi Knows to see them all.",
                           "url": "./#picks", "tag": f"picks-more-{int(time.time())}"})
    except Exception as e:      # noqa: BLE001
        log.warning("pick push failed: %s", e)


def _fire_rules(new: list[dict]):
    try:
        from engine import autotrader
        autotrader.on_picks(new)
    except Exception as e:      # noqa: BLE001
        log.warning("pick rules failed: %s", e)


def scan_once(now: float | None = None) -> dict:
    now = now or time.time()
    t0 = time.time()
    load_model()
    looked = json.loads(LOOKED.read_text()) if LOOKED.exists() else {}
    looked = {k: v for k, v in looked.items() if v > (now - 3 * 86400) * 1000}
    already = {r["ticker"] for r in _ledger()}
    cands = []
    for hz, ((lo, hi), h, thr) in HORIZONS.items():
        for m in open_markets(lo, hi, now):
            if (m.get("market_type") or "binary") != "binary" or m.get("mve_collection_ticker"):
                continue
            if f"{m['ticker']}|{hz}" in looked or m["ticker"] in already:
                continue
            last = kalshi.market_prices(m)["last"]
            vol = _f(m.get("volume_fp")) or 0
            if last is None or not (0.03 <= last <= 0.97) or vol < 50:
                continue
            cands.append((hz, h, thr, m))
    cands.sort(key=lambda x: -(_f(x[3].get("volume_24h_fp")) or 0))
    dropped = max(0, len(cands) - MAX_CANDIDATES)
    rows, metas = [], []
    for hz, h, thr, m in cands[:MAX_CANDIDATES]:
        looked[f"{m['ticker']}|{hz}"] = int(now * 1000)
        try:
            tr, trunc = trade_tape(m["ticker"])
            f = features(m, tr, now, h)
        except Exception as e:      # noqa: BLE001
            log.debug("features %s: %s", m["ticker"], e)
            continue
        if not f or is_politics(m, f["group"]):
            continue
        rows.append(f)
        metas.append((hz, thr, m, trunc))
    recs = []
    if rows:
        p = score(rows)
        for (hz, thr, m, trunc), f, py in zip(metas, rows, p):
            r = decide(m, f, float(py), hz, thr)
            r["tape_truncated"] = trunc
            recs.append(r)
    picks = [r for r in recs if r["qualifies"]]
    new = []
    with _lock:
        rows_l = _ledger()
        have = {r["ticker"] for r in rows_l}
        for r in sorted(picks, key=lambda r: -r["ev_cents_per_contract"]):
            if r["ticker"] in have:
                continue
            e = {**r, "ts_ms": int(now * 1000), "entry": r["ask"],
                 "contracts_at_stake": max(1, math.floor(STAKE_USD / r["ask"])), "result": None}
            rows_l.append(e)
            new.append(e)
        if new:
            _write_ledger(rows_l)
    LOOKED.write_text(json.dumps(looked))
    near = sorted([r for r in recs if not r["qualifies"]], key=lambda r: -r["edge_cents"])[:8]
    with _lock:
        live = [r for r in _ledger() if r.get("result") is None and r["close_ms"] > time.time() * 1000]
        STATE.update(generated_ms=int(time.time() * 1000), looked=len(recs), candidates=len(cands), dropped=dropped,
                     picks=sorted(live, key=lambda r: r["close_ms"]), near=near, err=None, scan_s=round(time.time() - t0, 1))
    log.info("picks scan: %d candidates (%d dropped by cap), %d scored, %d qualify, %d new [%.0fs]",
             len(cands), dropped, len(recs), len(picks), len(new), time.time() - t0)
    if new:
        _push(new)
        _fire_rules(new)
    return {"new": new, "scored": len(recs)}


_stop = threading.Event()
_started = False


def _loop():
    _stop.wait(20)
    while not _stop.is_set():
        STATE["scanning"] = True
        try:
            scan_once()
        except Exception as e:      # noqa: BLE001
            STATE["err"] = str(e)[:160]
            log.warning("picks scan failed: %s", e)
        try:
            settle_ledger()
        except Exception as e:      # noqa: BLE001
            log.warning("picks settle failed: %s", e)
        STATE["scanning"] = False
        _stop.wait(SCAN_EVERY_S)


def start():
    global _started
    if _started or os.environ.get("PICKS", "1") == "0":
        return
    if not (MODEL.exists() and META.exists()):
        log.warning("picks: model artifacts missing (%s); run train/xmarket/export_live_artifacts.py", MODEL)
        return
    _started = True
    threading.Thread(target=_loop, daemon=True, name="picks").start()
    log.info("picks scanner started (every %ds)", SCAN_EVERY_S)


# ---------------------------------------------------------------- API

router = APIRouter(prefix="/api/picks")


@router.get("")
def get_picks():
    with _lock:
        recent = [r for r in _ledger() if r.get("result") is not None][-30:][::-1]
        return {**STATE, "record": summary(), "settled_recent": recent,
                "rules": {"horizons": {k: {"window_h": v[0], "threshold_cents": v[2] * 100} for k, v in HORIZONS.items()},
                          "min_ev_cents": MIN_EV_CENTS, "stake_usd": STAKE_USD, "quiet_hours": QUIET},
                "disclaimer": "Model recommendations from public data, not financial advice. 21+. Automated orders go to "
                              "Kalshi's demo exchange (play money)."}

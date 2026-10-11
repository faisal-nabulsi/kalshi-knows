"""Two venues, one game: Polymarket live price next to Kalshi, plus lead-lag on each engine alert.

Public data only (Polymarket Gamma + CLOB market WebSocket, no keys, no trading).
Clock note: every Polymarket timestamp here is OUR receive time (server clock), not Polymarket's trade/print time,
because their print times are blockchain record times that lag the real match by ~2 s. Kalshi history points are our
poll times too, so both sides share one clock. Kalshi is sampled every ~2 s, so lead times resolve to ~2 s.

Mount from live.py with:  from engine import venues as _venues; _venues.mount(app, ENGINE)
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

log = logging.getLogger("venues")

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
HIST_MS = 20 * 60 * 1000
STALE_MS = 15_000            # no update this long -> REST fallback polls the game
MAX_SPREAD = 0.12            # ignore quotes from a broken/empty book
NEG_TTL_S = 300

# ESPN abbreviation -> Polymarket slug abbreviations to try
ALT = {"WSH": ["wsh", "was"], "JAX": ["jax", "jac"], "LV": ["lv", "lvr", "las"], "LAR": ["lar", "la"], "LAC": ["lac"],
       "NO": ["no", "nor"], "NE": ["ne", "nwe"], "TB": ["tb", "tam"], "GB": ["gb", "gnb"], "KC": ["kc", "kan"],
       "SF": ["sf", "sfo"]}

_now_ms = lambda: int(time.time() * 1000)


def _abbrs(x: str) -> list[str]:
    return ALT.get(x, [x.lower()])


def _norm(s: str | None) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def _name_match(outcome: str, team_name: str | None) -> bool:
    o, t = _norm(outcome), _norm(team_name)
    return bool(o and t and (o == t or o in t or t in o))


class Venues:
    def __init__(self, engine):
        self.E = engine
        self.lock = threading.RLock()
        self.maps: dict[str, dict] = {}        # gid -> mapping dict (status ok / no_event / name_mismatch ...)
        self.neg_until: dict[str, float] = {}
        self.books: dict[str, dict] = {}       # token -> {bid, ask, ms}
        self.tok_game: dict[str, str] = {}     # token -> gid
        self.hist: dict[str, deque] = {}       # gid -> deque[(recv_ms, p_home)]
        self.last_p: dict[str, dict] = {}      # gid -> {p, ms, src}
        self.ws_ok = False
        self.ws_msg_ms = 0
        self.ws_err: str | None = None
        self.rest_n = 0
        self.session = requests.Session()
        self._gamma_last = 0.0
        self._clob_last = 0.0
        self._started = False
        self.stop = False
        self.t_start = _now_ms()

    # ------------------------------------------------------------ mapping (Gamma)
    def _gamma(self, path: str, params: dict | None = None):
        w = 1.05 - (time.time() - self._gamma_last)
        if w > 0:
            time.sleep(w)
        self._gamma_last = time.time()
        r = self.session.get(GAMMA + path, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def _find_event(self, g: dict):
        date_ms = g.get("date_ms") or _now_ms()
        et = datetime.fromtimestamp(date_ms / 1000, ZoneInfo("America/New_York")).date()
        for dd in (et, et - timedelta(days=1), et + timedelta(days=1)):
            for a in _abbrs(g.get("away") or ""):
                for h in _abbrs(g.get("home") or ""):
                    try:
                        j = self._gamma("/events", {"slug": f"nfl-{a}-{h}-{dd}"})
                    except Exception as e:
                        log.debug("gamma slug fail %s", e)
                        continue
                    if j:
                        return j[0]
        return None

    def _resolve(self, gid: str, g: dict) -> dict:
        m = {"game_id": gid, "status": "no_event", "checked_ms": _now_ms()}
        ev = self._find_event(g)
        if not ev:
            return m
        mls = [x for x in ev.get("markets", []) if x.get("sportsMarketType") == "moneyline"] or ev.get("markets", [])[:1]
        if not mls:
            return m
        mk = mls[0]
        try:
            outs = json.loads(mk["outcomes"]) if isinstance(mk["outcomes"], str) else mk["outcomes"]
            toks = json.loads(mk["clobTokenIds"]) if isinstance(mk["clobTokenIds"], str) else mk["clobTokenIds"]
        except Exception:
            m["status"] = "bad_market"
            return m
        hi = next((i for i, o in enumerate(outs) if _name_match(o, g.get("home_name"))), None)
        ai = next((i for i, o in enumerate(outs) if _name_match(o, g.get("away_name"))), None)
        m.update(slug=ev.get("slug"), title=ev.get("title"), outcomes=outs, cond=mk.get("conditionId"))
        if hi is None or ai is None or hi == ai or len(toks) < 2:
            m["status"] = "name_mismatch"
            return m
        m.update(status="ok", home_tok=toks[hi], away_tok=toks[ai], home_outcome=outs[hi], away_outcome=outs[ai])
        return m

    def _wanted(self) -> dict[str, dict]:
        """Games worth mapping/streaming now: in progress, or starting within 45 min."""
        out = {}
        with self.E.lock:
            for gid, g in self.E.games.items():
                st = g.get("status")
                t = g.get("date_ms") or 0
                if g.get("kalshi_home") and (st == "in" or (st == "pre" and t - _now_ms() < 45 * 60 * 1000)):
                    out[gid] = dict(g)
        return out

    def _discover_loop(self):
        while not self.stop:
            try:
                for gid, g in self._wanted().items():
                    cur = self.maps.get(gid)
                    if cur and cur["status"] == "ok":
                        continue
                    if time.time() < self.neg_until.get(gid, 0):
                        continue
                    m = self._resolve(gid, g)
                    with self.lock:
                        self.maps[gid] = m
                        if m["status"] == "ok":
                            self.tok_game[m["home_tok"]] = gid
                            self.tok_game[m["away_tok"]] = gid
                            self.hist.setdefault(gid, deque())
                            log.info("mapped %s -> %s", g.get("short_name"), m["slug"])
                    if m["status"] != "ok":
                        self.neg_until[gid] = time.time() + NEG_TTL_S
                        log.info("no polymarket match for %s: %s", g.get("short_name"), m["status"])
            except Exception as e:
                log.warning("discover loop: %s", e)
            time.sleep(10)

    # ------------------------------------------------------------ prices
    def _set_quote(self, tok: str, bid: float | None, ask: float | None, src: str):
        gid = self.tok_game.get(tok)
        if gid is None or bid is None or ask is None or ask < bid or ask - bid > MAX_SPREAD or not (0 < ask <= 1):
            return
        ms = _now_ms()
        m = self.maps.get(gid)
        mid = (bid + ask) / 2
        p_home = mid if tok == m["home_tok"] else 1 - mid
        with self.lock:
            self.books[tok] = {"bid": bid, "ask": ask, "ms": ms}
            h = self.hist.setdefault(gid, deque())
            lp = self.last_p.get(gid)
            if not h or round(p_home, 4) != h[-1][1] or ms - h[-1][0] > 5000:
                if not h or ms > h[-1][0]:
                    h.append((ms, round(p_home, 4)))
            while h and h[0][0] < ms - HIST_MS:
                h.popleft()
            self.last_p[gid] = {"p": round(p_home, 4), "ms": ms, "src": src,
                                "changed_ms": ms if not lp or lp["p"] != round(p_home, 4) else lp["changed_ms"]}

    @staticmethod
    def _f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    def _on_msg(self, d: dict):
        et = d.get("event_type")
        if et == "price_changes" or "price_changes" in d:
            for c in d.get("price_changes", []):
                self._set_quote(c.get("asset_id"), self._f(c.get("best_bid")), self._f(c.get("best_ask")), "ws")
        elif et == "best_bid_ask":
            self._set_quote(d.get("asset_id"), self._f(d.get("best_bid")), self._f(d.get("best_ask")), "ws")
        elif et == "book":
            bids = [self._f(x.get("price")) for x in d.get("bids", [])]
            asks = [self._f(x.get("price")) for x in d.get("asks", [])]
            bids, asks = [x for x in bids if x is not None], [x for x in asks if x is not None]
            if bids and asks:
                self._set_quote(d.get("asset_id"), max(bids), min(asks), "ws")

    def _tokens(self) -> list[str]:
        w = self._wanted()
        with self.lock:
            return sorted(t for gid, m in self.maps.items() if m.get("status") == "ok" and gid in w
                          for t in (m["home_tok"], m["away_tok"]))

    async def _ws_main(self):
        import websockets
        backoff = 1
        while not self.stop:
            toks = self._tokens()
            if not toks:
                await asyncio.sleep(3)
                continue
            try:
                async with websockets.connect(WS_URL, ping_interval=None, open_timeout=10, max_size=2**24) as ws:
                    await ws.send(json.dumps({"assets_ids": toks, "type": "market"}))
                    self.ws_ok, self.ws_err, backoff = True, None, 1
                    last_ping = time.time()
                    while not self.stop:
                        if self._tokens() != toks:
                            break                      # new game mapped / game ended: resubscribe
                        try:
                            raw = await asyncio.wait_for(ws.recv(), 2)
                        except asyncio.TimeoutError:
                            raw = None
                        if time.time() - last_ping > 9:
                            await ws.send("PING")
                            last_ping = time.time()
                        if not raw or raw == "PONG":
                            continue
                        self.ws_msg_ms = _now_ms()
                        try:
                            d = json.loads(raw)
                        except Exception:
                            continue
                        for x in (d if isinstance(d, list) else [d]):
                            if isinstance(x, dict):
                                self._on_msg(x)
            except Exception as e:
                self.ws_err = str(e)[:160]
                log.warning("polymarket ws: %s", self.ws_err)
            self.ws_ok = False
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 15)

    def _ws_thread(self):
        asyncio.run(self._ws_main())

    def _rest_loop(self):
        """Fallback: <=1 request/s, only for games whose price has not been refreshed recently (or all if WS is down)."""
        i = 0
        while not self.stop:
            time.sleep(max(0.0, 1.05 - (time.time() - self._clob_last)))
            try:
                w = self._wanted()
                with self.lock:
                    cands = []
                    for gid, m in self.maps.items():
                        if m.get("status") != "ok" or gid not in w:
                            continue
                        lp = self.last_p.get(gid)
                        if not lp or _now_ms() - lp["ms"] > STALE_MS:
                            cands.append((gid, m))
                if not cands:
                    time.sleep(1)
                    continue
                gid, m = cands[i % len(cands)]
                i += 1
                self._clob_last = time.time()
                r = self.session.get(f"{CLOB}/midpoint", params={"token_id": m["home_tok"]}, timeout=8)
                mid = self._f(r.json().get("mid")) if r.status_code == 200 else None
                if mid is not None and 0 < mid < 1:
                    self.rest_n += 1
                    self._set_quote(m["home_tok"], mid - 0.0025, mid + 0.0025, "rest")
            except Exception as e:
                log.debug("rest fallback: %s", e)
                time.sleep(2)

    # ------------------------------------------------------------ lead-lag
    @staticmethod
    def _at(seq, t):
        """Last value at or before t (None if no data yet)."""
        v = None
        for ts, p in seq:
            if ts > t:
                break
            v = p
        return v

    @staticmethod
    def _half_cross(seq, t0, t1, before, after):
        """First timestamp in [t0, t1] where the series has covered half the move before->after."""
        if before is None or after is None:
            return None
        half = (before + after) / 2
        up = after > before
        for ts, p in seq:
            if ts < t0:
                continue
            if ts > t1:
                break
            if (p >= half) if up else (p <= half):
                return ts
        return None

    def measure(self, a: dict) -> dict:
        gid = a["game_id"]
        t_b = a.get("jump_started_ms") or a["ts_ms"] - 20_000
        t_a = a["ts_ms"]
        with self.E.lock:
            k = list(self.E.hist.get(gid) or [])
        with self.lock:
            pm = list(self.hist.get(gid) or [])
            lp = self.last_p.get(gid)
        out = {"measured_ms": _now_ms(), "clock": "own receive time on both venues; Kalshi sampled ~2 s"}
        if not pm or pm[0][0] > t_b + 3000:
            out["status"] = "no_poly_data"        # feed started too late to see the baseline
            return out
        kb, ka = self._at(k, t_b), self._at(k, t_a)
        pb, pa = self._at(pm, t_b), self._at(pm, t_a)
        out["kalshi_move"] = round(ka - kb, 4) if kb is not None and ka is not None else None
        out["poly_move"] = round(pa - pb, 4) if pb is not None and pa is not None else None
        kt = self._half_cross(k, t_b, t_a, kb, ka) if out["kalshi_move"] and abs(out["kalshi_move"]) >= 0.01 else None
        pt = self._half_cross(pm, t_b, t_a, pb, pa) if out["poly_move"] and abs(out["poly_move"]) >= 0.01 else None
        out["kalshi_half_ms"], out["poly_half_ms"] = kt, pt
        out["kalshi_first_by_s"] = round((pt - kt) / 1000, 1) if kt and pt else None   # >0: Kalshi moved first
        if lp and lp.get("p") is not None and k:
            out["gap_now"] = round(k[-1][1] - lp["p"], 4)       # Kalshi minus Polymarket, home-win probability
        out["status"] = "ok" if out["kalshi_first_by_s"] is not None else ("poly_flat" if pt is None else "kalshi_flat")
        return out

    def _alert_loop(self):
        done: set[str] = set()
        while not self.stop:
            time.sleep(1)
            try:
                with self.E.lock:
                    pending = [a for a in self.E.alerts if a["id"] not in done and a.get("venues") is None
                               and _now_ms() - a["ts_ms"] >= 3000]
                    for a in self.E.alerts:
                        if a.get("venues") is not None:
                            done.add(a["id"])
                for a in pending:
                    if a["ts_ms"] < self.t_start:
                        done.add(a["id"])
                        continue                          # alert restored from before this feed started: no history to measure
                    v = self.measure(a)
                    with self.E.lock:
                        a["venues"] = v
                        self.E._emit(a)
                    done.add(a["id"])
                    log.info("venues %s %s", a["id"], {x: v.get(x) for x in ("status", "kalshi_first_by_s", "poly_move", "gap_now")})
            except Exception as e:
                log.warning("alert loop: %s", e)

    # ------------------------------------------------------------ API
    @staticmethod
    def _down(seq, n=300):
        if len(seq) <= n:
            return [[t, p] for t, p in seq]
        step = len(seq) / n
        out = [seq[int(i * step)] for i in range(n)]
        out.append(seq[-1])
        return [[t, p] for t, p in out]

    def snapshot(self) -> dict:
        now = _now_ms()
        games = []
        with self.E.lock:
            gl = {gid: dict(g) for gid, g in self.E.games.items() if g.get("kalshi_home")}
            kh = {gid: list(self.E.hist.get(gid) or []) for gid in gl}
            last_alert = {}
            for a in self.E.alerts:
                if a.get("venues") and a["venues"].get("status") == "ok":
                    last_alert[a["game_id"]] = {"id": a["id"], "ts_ms": a["ts_ms"], "team": a.get("team"),
                                                "headline": a.get("headline"), **{k: a["venues"].get(k) for k in (
                                                    "kalshi_first_by_s", "kalshi_move", "poly_move", "gap_now")}}
        for gid, g in gl.items():
            if g.get("status") not in ("in", "pre"):
                continue
            m = self.maps.get(gid)
            with self.lock:
                pm = list(self.hist.get(gid) or [])
                lp = dict(self.last_p.get(gid) or {})
            k = kh[gid]
            kp = k[-1][1] if k else None
            pp = lp.get("p")
            games.append({
                "game_id": gid, "short_name": g.get("short_name"), "home": g.get("home"), "away": g.get("away"),
                "status": g.get("status"), "period": g.get("period"), "clock": g.get("clock"),
                "mapping": (m or {}).get("status", "pending"), "poly_slug": (m or {}).get("slug"),
                "kalshi_p_home": kp, "poly_p_home": pp,
                "gap": round(kp - pp, 4) if kp is not None and pp is not None else None,
                "kalshi_updated_ms": k[-1][0] if k else None, "poly_updated_ms": lp.get("ms"),
                "poly_changed_ms": lp.get("changed_ms"), "poly_src": lp.get("src"),
                "kalshi_history": self._down([x for x in k if x[0] >= now - HIST_MS]),
                "poly_history": self._down(pm),
                "last_leadlag": last_alert.get(gid),
            })
        return {"now_ms": now, "ws_connected": self.ws_ok, "ws_last_msg_ms": self.ws_msg_ms, "ws_err": self.ws_err,
                "rest_polls": self.rest_n, "poly_clock_note": "Polymarket times are our receive times; their own trade "
                "times lag ~2 s (blockchain).", "games": games}

    def start(self):
        if self._started:
            return
        self._started = True
        for fn, name in ((self._discover_loop, "venues-discover"), (self._ws_thread, "venues-ws"),
                         (self._rest_loop, "venues-rest"), (self._alert_loop, "venues-alerts")):
            threading.Thread(target=fn, daemon=True, name=name).start()


_V: Venues | None = None


def mount(app, engine):
    """Attach GET /api/venues and start the background feeds."""
    global _V
    from fastapi import APIRouter
    _V = Venues(engine)
    router = APIRouter()

    @router.get("/api/venues")
    def api_venues():
        return _V.snapshot()

    app.include_router(router)
    _V.start()
    log.info("venues mounted")

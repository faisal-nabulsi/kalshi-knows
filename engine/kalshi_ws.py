"""Kalshi PRODUCTION WebSocket market-data feed (read-only) for the live engine.

Why: the REST order book is polled round-robin at <= 2.6 req/s, so a live game's price is ~1-2 s old
when the detector sees it. The WebSocket pushes every order-book change the moment it happens.

What it does (docs.kalshi.com, WebSocket API v2, Oct 2026):
  - connects to wss://external-api-ws.kalshi.com/trade-api/ws/v2 (falls back to the shared host
    wss://api.elections.kalshi.com/trade-api/ws/v2), authenticated with KALSHI-ACCESS-KEY /
    KALSHI-ACCESS-SIGNATURE / KALSHI-ACCESS-TIMESTAMP signed over  timestamp + "GET" + "/trade-api/ws/v2"
  - subscribes to the public channels orderbook_delta + ticker + trade for the KXNFLGAME markets of every
    game the engine tracks (adds markets with update_subscription when games change)
  - turns each update into a home-win mid (yes bid/ask from the book, then the ticker, then last trade)
    and feeds it into the engine's normal on_quote path tagged src="ws_*"
  - reconnects with exponential backoff + jitter; a sequence gap forces a reconnect (fresh snapshots)

Credentials: ONLY ~/.kalshi/prod_key_id and ~/.kalshi/prod_private_key.pem. If either is missing the
feed stays off and the engine keeps polling exactly as before. Keys are never printed or logged.

HARD READ-ONLY GUARD: guard_prod_request() lets the production key sign exactly one thing, the GET of
the WebSocket handshake path. Every REST path (/trade-api/v2/...), anything containing /portfolio or
/orders, and any non-GET method raises ProdKeyMisuse. Outgoing socket commands are limited to
subscribe/update_subscription/unsubscribe/list_subscriptions on public market-data channels.
The auto-bettor never touches this module: it uses the demo key + demo host only (engine/autotrader.py).
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import statistics
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from engine import kalshi_auth

log = logging.getLogger("kalshi_ws")

WS_PATH = "/trade-api/ws/v2"
WS_URLS = ("wss://external-api-ws.kalshi.com/trade-api/ws/v2",     # current production host (docs, Oct 2026)
           "wss://api.elections.kalshi.com/trade-api/ws/v2")       # shared host, still supported
WS_HOSTS = frozenset(urlsplit(u).hostname for u in WS_URLS)
PROD_KEY_ID_PATH = Path("~/.kalshi/prod_key_id").expanduser()
PROD_KEY_PATH = Path("~/.kalshi/prod_private_key.pem").expanduser()

CHANNELS = ("orderbook_delta", "ticker", "trade")                   # public market data only
ALLOWED_CHANNELS = frozenset(CHANNELS)
ALLOWED_CMDS = frozenset({"subscribe", "update_subscription", "unsubscribe", "list_subscriptions"})
STALE_S = 5.0            # a live game with no socket message for this long falls back to REST polling
MAX_SPREAD = 0.12        # same rule as the REST path: ignore absurdly wide books
EMIT_MIN_MS = 250        # at most 4 engine quotes / s / game (bounds history + client payloads)
HEARTBEAT_MS = 1000      # re-emit an unchanged price every 1 s so the call timer keeps ticking


class ProdKeyMisuse(RuntimeError):
    """Raised when anything tries to use the production key for something other than market data."""


# ---------------------------------------------------------------- read-only guard + signing

def guard_prod_request(method: str, target: str) -> str:
    """Allow the production key to sign ONLY  GET /trade-api/ws/v2  (the market-data socket handshake).
    Returns the path to sign. Refuses every REST request and anything touching /portfolio or /orders."""
    t = str(target or "")
    low = t.lower()
    if "/portfolio" in low or "/orders" in low or "/order" in low:
        raise ProdKeyMisuse("production key may never sign portfolio/order requests")
    if "://" in t:
        p = urlsplit(t)
        if p.scheme != "wss" or p.hostname not in WS_HOSTS:
            raise ProdKeyMisuse("production key may only sign the Kalshi market-data WebSocket handshake")
        path, query = p.path, p.query
    else:
        path, _, query = t.partition("?")
    if str(method or "").upper() != "GET" or path != WS_PATH or query:
        raise ProdKeyMisuse("production key only signs GET /trade-api/ws/v2; REST requests are refused")
    return path


def prod_key_id() -> str | None:
    try:
        v = PROD_KEY_ID_PATH.read_text().strip() if PROD_KEY_ID_PATH.is_file() else ""
    except OSError:
        v = ""
    return v or None


def have_prod_credentials() -> bool:
    return bool(prod_key_id()) and PROD_KEY_PATH.is_file()


def sign_prod(method: str, target: str, timestamp_ms: int | None = None, *, private_key=None,
              key_id: str | None = None) -> dict:
    """Auth headers for the production market-data socket. Guarded: see guard_prod_request()."""
    path = guard_prod_request(method, target)
    if private_key is None:
        private_key = kalshi_auth.load_private_key(PROD_KEY_PATH)
        key_id = prod_key_id()
    if not key_id:
        raise ProdKeyMisuse("no production key id")
    ts = str(timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
    return {"KALSHI-ACCESS-KEY": key_id,
            "KALSHI-ACCESS-SIGNATURE": kalshi_auth.signature(private_key, ts, "GET", path),
            "KALSHI-ACCESS-TIMESTAMP": ts}


def build_cmd(cmd_id: int, cmd: str, params: dict) -> str:
    """The only way this module talks to the socket: allowlisted commands on public channels."""
    if cmd not in ALLOWED_CMDS:
        raise ProdKeyMisuse(f"socket command {cmd!r} not allowed (market data only)")
    bad = [c for c in (params.get("channels") or []) if c not in ALLOWED_CHANNELS]
    if bad:
        raise ProdKeyMisuse(f"channels {bad} not allowed (market data only)")
    return json.dumps({"id": int(cmd_id), "cmd": cmd, "params": params})


# ---------------------------------------------------------------- order book

def _f(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _px(dollars, cents=None) -> float | None:
    v = _f(dollars)
    if v is None and cents is not None:
        c = _f(cents)
        v = c / 100 if c is not None else None
    return round(v, 4) if v is not None else None


class Book:
    """Top-of-book for one market from orderbook_snapshot + orderbook_delta (YES bids and NO bids)."""

    def __init__(self):
        self.yes: dict[float, float] = {}
        self.no: dict[float, float] = {}
        self.ok = False

    @staticmethod
    def _levels(msg: dict, side: str) -> dict[float, float]:
        lv = msg.get(f"{side}_dollars_fp") or msg.get(f"{side}_dollars")
        out: dict[float, float] = {}
        if lv is not None:
            for p, q in lv:
                p, q = _px(p), _f(q)
                if p is not None and q and q > 0:
                    out[p] = q
            return out
        for p, q in msg.get(side) or []:          # legacy cents format
            p, q = _px(None, p), _f(q)
            if p is not None and q and q > 0:
                out[p] = q
        return out

    def snapshot(self, msg: dict):
        self.yes, self.no, self.ok = self._levels(msg, "yes"), self._levels(msg, "no"), True

    def delta(self, msg: dict):
        p = _px(msg.get("price_dollars"), msg.get("price"))
        d = _f(msg.get("delta_fp"))
        if d is None:
            d = _f(msg.get("delta"))
        if p is None or d is None:
            return
        side = self.yes if msg.get("side") == "yes" else self.no
        q = side.get(p, 0.0) + d
        if q <= 1e-9:
            side.pop(p, None)
        else:
            side[p] = q

    def top(self) -> tuple[float | None, float | None]:
        bid = max(self.yes) if self.yes else None
        nb = max(self.no) if self.no else None
        return bid, (round(1 - nb, 4) if nb is not None else None)


def _mid(b, a) -> float | None:
    if b is None or a is None or not (0 < b <= a <= 1.0001) or a - b > MAX_SPREAD:
        return None
    return (a + b) / 2


class SeqGap(RuntimeError):
    pass


# ---------------------------------------------------------------- feed

def now_ms() -> int:
    return int(time.time() * 1000)


class Feed:
    """targets() -> {ticker: (game_id, "home"|"away")};  on_quote(game_id, ts_ms, p_home, detail)."""

    def __init__(self, targets: Callable[[], dict], on_quote: Callable, *, enabled: bool = True):
        self.targets_fn = targets
        self.on_quote = on_quote
        self.allow = enabled
        self._stop = threading.Event()
        self.thread: threading.Thread | None = None
        self.enabled = False
        self.connected = False
        self.reason = "not started"
        self.error: str | None = None
        self.host: str | None = None
        self.connected_since_ms: int | None = None
        self.last_msg_ms: int | None = None
        self.n_msgs = 0
        self.n_quotes = 0
        self.n_reconnects = 0
        self.msg_times: deque = deque()
        self.ticker_map: dict[str, tuple[str, str]] = {}
        self.subscribed: set[str] = set()
        self.sids: dict[str, int] = {}
        self.seq: dict[int, int] = {}
        self.books: dict[str, Book] = {}
        self.tick: dict[str, dict] = {}
        self.last_by_ticker: dict[str, int] = {}
        self.dirty: set[str] = set()
        self.emitted: dict[str, tuple[int, float]] = {}
        self.trans: dict[str, deque] = {}
        self.poll_last: dict[str, float] = {}
        self.leads: deque = deque(maxlen=300)
        self.diffs: deque = deque(maxlen=300)
        self._cmd_id = 0
        self._last_stats = time.time()
        self._stats_n = 0

    # ---- lifecycle
    def start(self):
        if not self.allow:
            self.reason = "off: disabled by MARKET_WS=0"
            return
        if self.thread is None:
            self.thread = threading.Thread(target=lambda: asyncio.run(self._main()), daemon=True, name="kalshi_ws")
            self.thread.start()

    def stop(self):
        self._stop.set()

    # ---- freshness (used by the REST poller to decide whether to fall back)
    def fresh(self, gid: str, stale_s: float = STALE_S) -> bool:
        if not self.connected or gid not in self.emitted:
            return False
        cut = now_ms() - stale_s * 1000
        return any(self.last_by_ticker.get(t, 0) >= cut for t, (g, _) in list(self.ticker_map.items()) if g == gid)

    def note_poll(self, gid: str, ts: int, p: float):
        """REST order-book sample for a game the socket already covers: measure how far behind it is."""
        cur = self.emitted.get(gid)
        if cur:
            self.diffs.append(abs(p - cur[1]))
        prev = self.poll_last.get(gid)
        self.poll_last[gid] = p
        if prev is None or abs(prev - p) < 1e-6:
            return
        for t, v in reversed(self.trans.get(gid) or ()):
            if t <= ts and abs(v - p) < 0.003:
                if ts - t <= 60_000:
                    self.leads.append(ts - t)
                return

    # ---- status for /api/health
    def status(self) -> dict:
        now = now_ms()
        while self.msg_times and self.msg_times[0] < now - 10_000:
            self.msg_times.popleft()
        leads = sorted(self.leads)
        out = {"enabled": self.enabled, "connected": self.connected, "last_msg_ms": self.last_msg_ms,
               "msgs_per_s": round(len(self.msg_times) / 10.0, 1), "subscribed": len(self.subscribed),
               "host": self.host, "reason": self.reason, "error": self.error, "msgs": self.n_msgs,
               "quotes": self.n_quotes, "reconnects": self.n_reconnects,
               "fresh_games": sorted({g for g, _ in self.ticker_map.values() if self.fresh(g)})}
        if leads:
            out["lead_vs_poll_ms"] = {"n": len(leads), "median": int(statistics.median(leads)),
                                      "p90": int(leads[min(len(leads) - 1, int(0.9 * len(leads)))])}
        if self.diffs:
            out["poll_abs_diff_median"] = round(statistics.median(self.diffs), 4)
        return out

    # ---- pricing
    def _ticker_mid(self, t: str):
        b = self.books.get(t)
        if b is not None and b.ok:
            bid, ask = b.top()
            m = _mid(bid, ask)
            if m is not None:
                return m, bid, ask, "ws_book"
        tk = self.tick.get(t) or {}
        m = _mid(tk.get("bid"), tk.get("ask"))
        if m is not None:
            return m, tk.get("bid"), tk.get("ask"), "ws_ticker"
        return None

    def price(self, gid: str) -> tuple[float | None, dict]:
        home = next((t for t, (g, s) in self.ticker_map.items() if g == gid and s == "home"), None)
        away = next((t for t, (g, s) in self.ticker_map.items() if g == gid and s == "away"), None)
        if home:
            r = self._ticker_mid(home)
            if r:
                return r[0], {"hb": r[1], "ha": r[2], "src": r[3]}
        if away:
            r = self._ticker_mid(away)
            if r:
                return 1 - r[0], {"ab": r[1], "aa": r[2], "src": r[3] + "_away"}
        for t, flip in ((home, False), (away, True)):
            last = (self.tick.get(t) or {}).get("last") if t else None
            if last is not None and 0 < last < 1:
                return (1 - last if flip else last), {"src": "ws_trade" + ("_away" if flip else "")}
        return None, {}

    def _flush(self):
        now = now_ms()
        gids = set(self.dirty) | {g for g, (ts, _) in self.emitted.items() if now - ts >= HEARTBEAT_MS}
        for gid in gids:
            prev = self.emitted.get(gid)
            if prev and now - prev[0] < EMIT_MIN_MS:
                continue                              # stays dirty; emitted on a later flush
            was_dirty = gid in self.dirty
            self.dirty.discard(gid)
            if not was_dirty:                         # heartbeat: only while the socket is alive for this game
                last = max((self.last_by_ticker.get(t, 0) for t, (g, _) in list(self.ticker_map.items()) if g == gid),
                           default=0)
                if not self.connected or now - last > STALE_S * 1000:
                    continue                          # silent: REST polling owns this game until a message arrives
            p, detail = self.price(gid)
            if p is None:
                continue
            p = round(min(1.0, max(0.0, p)), 4)
            if prev and abs(prev[1] - p) < 1e-9 and now - prev[0] < HEARTBEAT_MS:
                continue
            if not prev or abs(prev[1] - p) >= 1e-9:
                self.trans.setdefault(gid, deque(maxlen=600)).append((now, p))
            self.emitted[gid] = (now, p)
            self.n_quotes += 1
            try:
                self.on_quote(gid, now, p, detail)
            except Exception as e:           # never let an engine error kill the socket
                log.warning("on_quote from ws failed: %s", e)

    # ---- messages
    def handle(self, raw) -> None:
        now = now_ms()
        self.n_msgs += 1
        self._stats_n += 1
        self.msg_times.append(now)
        self.last_msg_ms = now
        try:
            m = json.loads(raw)
        except ValueError:
            return
        typ = m.get("type")
        msg = m.get("msg") or {}
        if typ == "subscribed":
            if msg.get("channel"):
                self.sids[msg["channel"]] = msg.get("sid")
            return
        if typ == "error":
            self.error = f"kalshi ws error {msg.get('code')}: {str(msg.get('msg'))[:120]}"
            log.warning("%s", self.error)
            return
        tk = msg.get("market_ticker") or m.get("market_ticker")
        if not tk:
            return
        sid, seq = m.get("sid"), m.get("seq")
        if typ in ("orderbook_snapshot", "orderbook_delta") and seq is not None and sid is not None:
            last = self.seq.get(sid)
            if typ == "orderbook_delta" and last is not None and seq != last + 1:
                raise SeqGap(f"orderbook seq gap on sid {sid}: {last} -> {seq}")
            self.seq[sid] = seq
        if typ == "orderbook_snapshot":
            self.books.setdefault(tk, Book()).snapshot(msg)
        elif typ == "orderbook_delta":
            b = self.books.get(tk)
            if b is not None and b.ok:
                b.delta(dict(m, **msg))
        elif typ == "ticker":
            cur = self.tick.setdefault(tk, {})
            for k, v in (("bid", _px(msg.get("yes_bid_dollars"), msg.get("yes_bid"))),
                         ("ask", _px(msg.get("yes_ask_dollars"), msg.get("yes_ask"))),
                         ("last", _px(msg.get("price_dollars"), msg.get("price")))):
                if v is not None:
                    cur[k] = v
        elif typ == "trade":
            v = _px(msg.get("yes_price_dollars"), msg.get("yes_price"))
            if v is not None:
                self.tick.setdefault(tk, {})["last"] = v
        else:
            return
        self.last_by_ticker[tk] = now
        g = self.ticker_map.get(tk)
        if g:
            self.dirty.add(g[0])

    # ---- socket
    def _next_id(self) -> int:
        self._cmd_id += 1
        return self._cmd_id

    async def _sync_subs(self, ws):
        try:
            tm = dict(self.targets_fn() or {})
        except Exception as e:
            log.warning("ws targets failed: %s", e)
            return
        self.ticker_map.update(tm)
        new = sorted(set(tm) - self.subscribed)
        if not new:
            return
        if not self.subscribed:
            await ws.send(build_cmd(self._next_id(), "subscribe", {"channels": list(CHANNELS), "market_tickers": new}))
        else:
            if any(c not in self.sids for c in CHANNELS):
                return                                # acks not in yet; retry on the next sync
            for c in CHANNELS:
                await ws.send(build_cmd(self._next_id(), "update_subscription",
                                        {"sids": [self.sids[c]], "market_tickers": new, "action": "add_markets"}))
        self.subscribed.update(new)
        log.info("kalshi ws subscribed %d markets (+%d)", len(self.subscribed), len(new))

    async def _session(self, url: str):
        from websockets.asyncio.client import connect
        headers = sign_prod("GET", url)
        async with connect(url, additional_headers=headers, open_timeout=8, ping_interval=15, ping_timeout=15,
                           close_timeout=2, max_size=2 ** 23) as ws:
            self.connected, self.host, self.error = True, urlsplit(url).hostname, None
            self.connected_since_ms = now_ms()
            self.reason = "connected"
            self.subscribed, self.sids, self.seq, self.books, self.tick = set(), {}, {}, {}, {}
            log.info("kalshi ws connected to %s", self.host)
            await self._sync_subs(ws)

            async def reader():
                async for raw in ws:
                    self.handle(raw)

            async def ticker():
                last_sync = time.time()
                while not self._stop.is_set():
                    await asyncio.sleep(0.1)
                    self._flush()
                    if time.time() - last_sync > 2:
                        last_sync = time.time()
                        await self._sync_subs(ws)
                        if not self.ticker_map:
                            return
                    if time.time() - self._last_stats > 60:
                        dt = time.time() - self._last_stats
                        log.info("kalshi ws: %.1f msgs/s over %ds, %d markets, %d quotes, lead vs poll %s",
                                 self._stats_n / dt, dt, len(self.subscribed), self.n_quotes,
                                 self.status().get("lead_vs_poll_ms"))
                        self._last_stats, self._stats_n = time.time(), 0

            tasks = {asyncio.create_task(reader()), asyncio.create_task(ticker())}
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            for t in done:
                t.result()

    async def _main(self):
        backoff, url_i = 1.0, 0
        while not self._stop.is_set():
            if not have_prod_credentials():
                self.enabled, self.reason = False, "off: no production key (~/.kalshi/prod_key_id + prod_private_key.pem)"
                await asyncio.sleep(15)
                continue
            self.enabled = True
            try:
                self.ticker_map = dict(self.targets_fn() or {})
            except Exception as e:
                log.warning("ws targets failed: %s", e)
                self.ticker_map = {}
            if not self.ticker_map:
                self.reason = "idle: no tracked games"
                await asyncio.sleep(3)
                continue
            url = WS_URLS[url_i % len(WS_URLS)]
            t0 = time.time()
            try:
                await self._session(url)
                self.reason = "session ended"
            except ProdKeyMisuse as e:
                self.error = str(e)[:160]
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                self.error = (f"handshake rejected ({status})" if status else f"{type(e).__name__}: {str(e)[:120]}")
                log.warning("kalshi ws %s: %s", urlsplit(url).hostname, self.error)
                if not self.connected:
                    url_i += 1                          # couldn't connect: try the other production host next
            finally:
                was = self.connected
                self.connected = False
                if was:
                    self.n_reconnects += 1
            if time.time() - t0 > 60:
                backoff = 1.0
            sleep = min(60.0, backoff) * (0.5 + random.random())
            backoff = min(60.0, backoff * 2)
            self.reason = f"reconnecting in {sleep:.1f}s"
            await asyncio.sleep(sleep)

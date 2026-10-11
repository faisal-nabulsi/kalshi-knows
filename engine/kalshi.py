"""Public-only Kalshi client (no auth, no trading endpoints, ever).

Global rate limiter (<= 4 req/s per process), retries with exponential backoff
and jitter on 429/5xx/network errors. Helpers for NFL game markets and quotes,
plus ESPN <-> Kalshi game matching.
"""
from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx

BASE = "https://api.elections.kalshi.com/trade-api/v2"
log = logging.getLogger("kalshi")

MAX_RPS = 3.5  # stay safely under the 4 req/s hard rule


class RateLimiter:
    """Thread-safe minimum-interval limiter shared by the whole process."""

    def __init__(self, rps: float):
        self.interval = 1.0 / rps
        self.lock = threading.Lock()
        self.next_t = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next_t)
            self.next_t = t + self.interval
        delay = t - time.monotonic()
        if delay > 0:
            time.sleep(delay)


LIMITER = RateLimiter(MAX_RPS)
_client_lock = threading.Lock()
_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(
                base_url=BASE,
                timeout=httpx.Timeout(6.0, connect=4.0),
                headers={"User-Agent": "kalshi-knows-hackathon/0.1 (public data only)"},
            )
        return _client


def get(path: str, params: dict | None = None, retries: int = 4) -> dict:
    """GET a public endpoint with rate limiting + backoff. Raises on final failure."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        LIMITER.wait()
        try:
            r = client().get(path, params=params)
            if r.status_code == 429 or r.status_code >= 500:
                raise httpx.HTTPStatusError(f"status {r.status_code}", request=r.request, response=r)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPStatusError, httpx.TransportError, ValueError) as e:
            last_exc = e
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                raise
            if attempt < retries:
                sleep = min(8.0, 0.5 * (2 ** attempt)) * (0.5 + random.random())
                log.warning("kalshi %s failed (%s), retry in %.1fs", path, e, sleep)
                time.sleep(sleep)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------- endpoints

def list_markets(**params) -> list[dict]:
    """All markets matching params, following the cursor."""
    out: list[dict] = []
    cursor = None
    for _ in range(50):
        p = dict(params)
        p.setdefault("limit", 1000)
        if cursor:
            p["cursor"] = cursor
        d = get("/markets", p)
        out.extend(d.get("markets") or [])
        cursor = d.get("cursor")
        if not cursor:
            break
    return out


def list_nfl_game_markets() -> list[dict]:
    return list_markets(series_ticker="KXNFLGAME", status="open")


def quotes(tickers: list[str]) -> dict[str, dict]:
    """Batch quotes: ticker -> market dict. One call per <=100 tickers."""
    out: dict[str, dict] = {}
    tickers = [t for t in tickers if t]
    for i in range(0, len(tickers), 100):
        chunk = tickers[i:i + 100]
        d = get("/markets", {"tickers": ",".join(chunk), "limit": len(chunk)})
        for m in d.get("markets") or []:
            out[m["ticker"]] = m
    return out


def orderbook(ticker: str, depth: int = 5) -> dict:
    return get(f"/markets/{ticker}/orderbook", {"depth": depth})


def trades(ticker: str, min_ts: int | None = None, max_ts: int | None = None, limit: int = 1000) -> list[dict]:
    """Trades for a ticker; min_ts/max_ts are epoch SECONDS (Kalshi convention)."""
    out: list[dict] = []
    cursor = None
    for _ in range(20):
        p: dict = {"ticker": ticker, "limit": limit}
        if min_ts is not None:
            p["min_ts"] = int(min_ts)
        if max_ts is not None:
            p["max_ts"] = int(max_ts)
        if cursor:
            p["cursor"] = cursor
        d = get("/markets/trades", p)
        out.extend(d.get("trades") or [])
        cursor = d.get("cursor")
        if not cursor:
            break
    return out


# ---------------------------------------------------------------- pricing

def _f(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v


def market_prices(m: dict | None) -> dict:
    """yes_bid / yes_ask / last as floats in [0,1] (None when missing)."""
    if not m:
        return {"bid": None, "ask": None, "last": None}
    bid = _f(m.get("yes_bid_dollars"))
    ask = _f(m.get("yes_ask_dollars"))
    last = _f(m.get("last_price_dollars"))
    # legacy cent fields, just in case
    if bid is None and m.get("yes_bid") is not None:
        bid = _f(m["yes_bid"]) / 100
    if ask is None and m.get("yes_ask") is not None:
        ask = _f(m["yes_ask"]) / 100
    if last is None and m.get("last_price") is not None:
        last = _f(m["last_price"]) / 100
    return {"bid": bid, "ask": ask, "last": last}


def _mid(px: dict, max_spread: float = 0.12) -> tuple[float | None, float | None]:
    """(mid, spread) when the book is two-sided, uncrossed and not absurdly wide."""
    b, a = px["bid"], px["ask"]
    if b is None or a is None or b <= 0 or a <= 0 or a > 1.0001 or a < b:
        return None, None
    spread = a - b
    if spread > max_spread:
        return None, spread
    return (a + b) / 2, spread


def home_prob(home_m: dict | None, away_m: dict | None) -> tuple[float | None, dict]:
    """Home-win probability from both markets. Returns (p_home, detail)."""
    hp, ap = market_prices(home_m), market_prices(away_m)
    hmid, hs = _mid(hp)
    amid, as_ = _mid(ap)
    cands = []
    if hmid is not None:
        cands.append((hs, hmid))
    if amid is not None:
        cands.append((as_, 1 - amid))
    p = None
    src = None
    if len(cands) == 2:
        if abs(cands[0][1] - cands[1][1]) <= 0.08:
            p = (cands[0][1] + cands[1][1]) / 2
            src = "mid2"
        else:  # disagree: trust the tighter book
            p = min(cands)[1]
            src = "mid_tight"
    elif cands:
        p = cands[0][1]
        src = "mid1"
    else:
        if hp["last"] is not None and 0 < hp["last"] < 1:
            p, src = hp["last"], "last_home"
        elif ap["last"] is not None and 0 < ap["last"] < 1:
            p, src = 1 - ap["last"], "last_away"
    if p is not None:
        p = min(1.0, max(0.0, p))
    detail = {"hb": hp["bid"], "ha": hp["ask"], "hl": hp["last"],
              "ab": ap["bid"], "aa": ap["ask"], "al": ap["last"], "src": src}
    return p, detail


# ---------------------------------------------------------------- matching

# ESPN abbreviation -> Kalshi abbreviation (only where they differ)
ESPN_TO_KALSHI = {"JAX": "JAC", "WSH": "WAS", "LA": "LAR", "LARM": "LAR", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
KALSHI_TO_ESPN = {"JAC": "JAX", "WAS": "WSH"}

# Kalshi yes_sub_title (city names) -> Kalshi abbreviation, as a fallback matcher
CITY_TO_ABBR = {
    "arizona": "ARI", "atlanta": "ATL", "baltimore": "BAL", "buffalo": "BUF", "carolina": "CAR",
    "chicago": "CHI", "cincinnati": "CIN", "cleveland": "CLE", "dallas": "DAL", "denver": "DEN",
    "detroit": "DET", "green bay": "GB", "houston": "HOU", "indianapolis": "IND",
    "jacksonville": "JAC", "kansas city": "KC", "las vegas": "LV", "los angeles c": "LAC",
    "los angeles r": "LAR", "miami": "MIA", "minnesota": "MIN", "new england": "NE",
    "new orleans": "NO", "new york g": "NYG", "new york j": "NYJ", "philadelphia": "PHI",
    "pittsburgh": "PIT", "san francisco": "SF", "seattle": "SEA", "tampa bay": "TB",
    "tennessee": "TEN", "washington": "WAS",
}

_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def to_kalshi(espn_abbr: str) -> str:
    a = (espn_abbr or "").upper()
    return ESPN_TO_KALSHI.get(a, a)


def _event_date(event_ticker: str):
    """'KXNFLGAME-26OCT11SFSEA' -> date(2026,10,11) (US Eastern game date)."""
    try:
        code = event_ticker.split("-")[1]
        yy, mon, dd = int(code[0:2]), code[2:5], int(code[5:7])
        return datetime(2000 + yy, _MONTHS[mon], dd).date()
    except Exception:
        return None


def group_events(markets: list[dict]) -> dict[str, dict]:
    """event_ticker -> {"date": date, "teams": {KALSHI_ABBR: ticker}}"""
    ev: dict[str, dict] = {}
    for m in markets:
        et = m.get("event_ticker") or ""
        t = m.get("ticker") or ""
        side = t.rsplit("-", 1)[-1].upper() if "-" in t else ""
        city = (m.get("yes_sub_title") or "").strip().lower()
        if city in CITY_TO_ABBR and CITY_TO_ABBR[city] != side:
            log.info("ticker suffix %s differs from city %s (%s)", side, city, t)
        e = ev.setdefault(et, {"date": _event_date(et), "teams": {}})
        e["teams"][side] = t
        if city in CITY_TO_ABBR:
            e["teams"].setdefault(CITY_TO_ABBR[city], t)
    return ev


def match_game(game: dict, events: dict[str, dict]) -> tuple[str | None, str | None]:
    """Match one ESPN game (needs home/away ESPN abbrs + date_ms) to (home_ticker, away_ticker)."""
    h, a = to_kalshi(game["home"]), to_kalshi(game["away"])
    # ESPN kickoff (UTC) -> US Eastern calendar date (EDT, UTC-4, in October)
    gdate = None
    if game.get("date_ms"):
        gdate = (datetime.fromtimestamp(game["date_ms"] / 1000, tz=timezone.utc) - timedelta(hours=4)).date()
    best = None
    for et, e in events.items():
        teams = e["teams"]
        if h in teams and a in teams:
            dd = abs((e["date"] - gdate).days) if (gdate and e["date"]) else 0
            if dd <= 1 and (best is None or dd < best[0]):
                best = (dd, teams[h], teams[a])
    if best:
        return best[1], best[2]
    return None, None

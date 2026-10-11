"""Live bet recommendations ("Picks") from the cross-market study.

Fetches OPEN Kalshi markets closing in the next 1-30 h from the public API (no key, <=2 req/s), builds the
cross-market price features from public trades (last price, VWAP, momentum, volatility, trade counts, time to
close, category), scores them, and recommends a bet when |model - price| >= 0.08.

Model: if kaggle/xmarket/out_local/xmarket_xgb.json exists it is used (XGBoost residual on logit(price), same
feature list as train_xmarket.py). The XGBoost weights were trained on Kaggle and are NOT on this machine, so the
default scorer is the per-category logit recalibration (slope/intercept) fitted in the same study and saved in
kaggle/xmarket/out_local/favorite_longshot_by_category.csv. picks.json says which scorer produced the numbers.

Writes docs/data/picks.json and appends new picks to engine/logs/picks/ledger.jsonl.
Usage: .venv/bin/python engine/picks.py [--max-markets 300]
"""
import argparse, csv, json, math, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://api.elections.kalshi.com/trade-api/v2"
OUT = os.path.join(ROOT, "docs", "data", "picks.json")
LEDGER = os.path.join(ROOT, "engine", "logs", "picks", "ledger.jsonl")
ART = os.path.join(ROOT, "kaggle", "xmarket", "out_local")
THR = 0.08
SKIP_CATS = ("polit", "elect", "world", "war", "geopolit")
BACKTEST = {
    "label": "paper backtest, Jan 2026, one month, last-trade fills, not yet adversarially reviewed",
    "rule": "bet when model - price >= 0.08 at 24 h before close",
    "training_markets": 4363922, "test_month": "2026-01",
    "h24": {"bets": 1603, "win_rate": 0.582, "pnl_cents_per_contract": 6.1, "roi_after_fees": 0.120, "roi_ci95": [0.065, 0.178]},
    "h6": {"bets": 5371, "roi_after_fees": 0.067},
}
_last = [0.0]


def get(path, **q):
    q = {k: v for k, v in q.items() if v is not None}
    url = f"{BASE}{path}?{urllib.parse.urlencode(q)}"
    for i in range(4):
        wait = 0.5 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kalshi-knows-picks/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 + 2 * i); continue
            raise
        except Exception:
            time.sleep(1 + i)
    raise RuntimeError(f"failed {url}")


def cents(d, k):
    """Price field in cents, accepting both legacy integer cents and *_dollars strings."""
    v = d.get(k)
    if v is None and d.get(k + "_dollars") is not None:
        v = float(d[k + "_dollars"]) * 100
    return None if v is None else float(v)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def load_calib():
    rows = {}
    with open(os.path.join(ART, "favorite_longshot_by_category.csv")) as f:
        for r in csv.DictReader(f):
            if r["name"] == "name":
                continue
            k = r["name"]
            # prefer the unseen test-period fit, else the training-period fit
            if k not in rows or r["period"] == "test":
                rows[k] = (float(r["logit_slope"]), float(r["logit_intercept"]), r["period"], int(float(r["n"])))
    return rows


def calib_key(cat, series):
    s = (series or "").upper(); c = (cat or "").lower()
    if s.startswith("KXNFL"): return "NFL"
    if s.startswith("KXNCAAMB") or s.startswith("KXNCAAB"): return "NCAA Basketball"
    if "sport" in c: return "Sports"
    if "climate" in c or "weather" in c: return "Weather"
    if "crypto" in c: return "Crypto"
    if "financ" in c or "econom" in c: return "Finance"
    if "entertain" in c: return "Entertainment"
    if "media" in c or "mention" in c: return "Media"
    return "Other"


def lg(p):
    p = min(max(p, 1e-4), 1 - 1e-4); return math.log(p / (1 - p))


def sig(x):
    return 1 / (1 + math.exp(-x))


def fee_cents(P, C=10):
    """Kalshi taker fee for C contracts at price P (dollars), rounded up to the cent; returned per contract in cents."""
    return math.ceil(round(0.07 * C * P * (1 - P) * 100, 6)) / C


def fetch_markets(now, max_pages, cap):
    """Open single-leg markets closing in 1-30 h (mve_filter=exclude drops multivariate combos), then category per event."""
    out, cur = [], None
    lo, hi = int(now + 3600), int(now + 30 * 3600)
    for _ in range(max_pages):
        j = get("/markets", status="open", min_close_ts=lo, max_close_ts=hi, mve_filter="exclude", limit=1000, cursor=cur)
        for m in j.get("markets", []):
            if m.get("mve_collection_ticker") or m.get("mve_selected_legs") or (m.get("market_type") not in (None, "binary")):
                continue
            if (m.get("status") or "") not in ("active", "open"):
                continue
            try:
                ct = ts(m.get("close_time"))
            except Exception:
                continue
            if not (lo <= ct <= hi) or float(m.get("volume_24h_fp") or m.get("volume_24h") or 0) <= 0:
                continue
            m["_close_ts"] = ct
            out.append(m)
        cur = j.get("cursor")
        if not cur:
            break
    out.sort(key=lambda m: -(float(m.get("volume_24h_fp") or m.get("volume_24h") or 0)))
    keep, evs = [], {}
    for m in out:
        if len(keep) >= cap:
            break
        et = m.get("event_ticker")
        if et not in evs:
            try:
                evs[et] = get(f"/events/{et}").get("event", {})
            except Exception:
                evs[et] = {}
        ev = evs[et]
        cat = ev.get("category") or ""
        if any(k in cat.lower() for k in SKIP_CATS):
            continue
        m["_cat"], m["_series"], m["_event_title"] = cat, ev.get("series_ticker") or et.split("-")[0], ev.get("title") or ""
        keep.append(m)
    return keep


def trade_feats(m, now):
    j = get("/markets/trades", ticker=m["ticker"], limit=1000)
    tr = []
    for t in j.get("trades", []):
        p = cents(t, "yes_price")
        c = float(t.get("count_fp") or t.get("count") or 0)
        if p is None:
            continue
        tr.append((ts(t["created_time"]), p / 100, c, 1.0 if t.get("taker_side") == "yes" else 0.0))
    if not tr:
        return None
    tr.sort()
    last_ts, price = tr[-1][0], min(max(tr[-1][1], 0.01), 0.99)
    w24 = [t for t in tr if t[0] >= now - 86400]
    def before(s):
        b = [t for t in tr if t[0] < now - s]
        return b[-1][1] if b else None
    vol24 = sum(t[2] for t in w24)
    vwap24 = sum(t[1] * t[2] for t in w24) / vol24 if vol24 else price
    volall = sum(t[2] for t in tr)
    vwap_all = sum(t[1] * t[2] for t in tr) / volall if volall else price
    p6, p24 = before(21600), before(86400)
    ps = [t[1] for t in w24]
    std24 = (sum((x - sum(ps) / len(ps)) ** 2 for x in ps) / len(ps)) ** 0.5 if ps else 0.0
    return {
        "price": price, "vwap24": vwap24, "vwap_all": vwap_all, "price_vs_vwap": price - vwap24,
        "mom6": price - p6 if p6 is not None else 0.0, "mom6_missing": int(p6 is None),
        "mom24": price - p24 if p24 is not None else 0.0, "std24": std24,
        "n_tr": math.log1p(len(tr)), "n_tr24": math.log1p(len(w24)), "ct": math.log1p(volall), "ct24": math.log1p(vol24),
        "yes_share24": (sum(t[2] * t[3] for t in w24) / vol24) if vol24 else 0.5,
        "hrs_since_last": math.log1p(max(0.0, (now - last_ts) / 3600)),
        "raw_trades": len(tr), "raw_trades24": len(w24), "raw_ct24": vol24, "last_trade_ts": last_ts,
        "truncated": len(j.get("trades", [])) >= 1000,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-markets", type=int, default=300)
    ap.add_argument("--event-pages", type=int, default=10)
    a = ap.parse_args()
    t0 = time.time(); now = time.time()
    calib = load_calib()
    xgb_path = os.path.join(ART, "xmarket_xgb.json")
    scorer = "xgboost" if os.path.exists(xgb_path) else "per_category_logit_recalibration"
    mk = fetch_markets(now, a.event_pages, a.max_markets)
    print(f"open markets closing in 1-30 h (non-combo, non-politics, most traded): {len(mk)}  [{time.time() - t0:.0f}s]", flush=True)
    mk.sort(key=lambda m: m["_close_ts"])
    scored = []
    for i, m in enumerate(mk):
        if time.time() - t0 > 270:
            print("time cap hit, stopping at", i, flush=True); break
        try:
            f = trade_feats(m, now)
        except Exception as e:
            print("trades fail", m["ticker"], e, flush=True); continue
        if not f:
            continue
        h = (m["_close_ts"] - now) / 3600
        key = calib_key(m["_cat"], m["_series"])
        slope, icpt, period, ncal = calib.get(key, calib["Other"])
        prob = sig(slope * lg(f["price"]) + icpt)
        P = f["price"]
        side = "YES" if prob > P else "NO"
        q, Ps = (prob, P) if side == "YES" else (1 - prob, 1 - P)
        fee = fee_cents(Ps)
        ev = (q - Ps) * 100 - fee
        edge = abs(prob - P)
        tier = "A" if edge >= 0.15 and f["raw_trades24"] >= 50 else "B" if edge >= 0.10 and f["raw_trades24"] >= 10 else "C"
        title = m.get("title") or m["_event_title"]
        sub = m.get("yes_sub_title") or ""
        scored.append({
            "ticker": m["ticker"], "event_ticker": m.get("event_ticker"), "title": title, "yes_label": sub,
            "event_title": m["_event_title"], "category": m["_cat"], "calib_group": key, "series": m["_series"],
            "close_ms": int(m["_close_ts"] * 1000), "hours_to_close": round(h, 2), "horizon": "6h" if h <= 12 else "24h",
            "side": side, "model_prob": round(prob, 4), "market_price": round(P, 4),
            "yes_bid": cents(m, "yes_bid"), "yes_ask": cents(m, "yes_ask"),
            "edge_cents": round(edge * 100, 1), "fee_cents_per_contract": round(fee, 2), "ev_cents_per_contract": round(ev, 2),
            "tier": tier, "trades": f["raw_trades"], "trades_24h": f["raw_trades24"], "contracts_24h": round(f["raw_ct24"]),
            "vwap24": round(f["vwap24"], 4), "mom24": round(f["mom24"], 4), "std24": round(f["std24"], 4),
            "qualifies": edge >= THR and ev > 0,
            "url": f"https://kalshi.com/markets/{(m['_series'] or '').lower()}",
        })
        if (i + 1) % 25 == 0:
            print(f"scored {i + 1}/{len(mk)}  [{time.time() - t0:.0f}s]", flush=True)
    picks = sorted([s for s in scored if s["qualifies"]], key=lambda s: -s["ev_cents_per_contract"])
    closest = sorted([s for s in scored if not s["qualifies"]], key=lambda s: -s["edge_cents"])[:8]
    doc = {
        "generated_ms": int(time.time() * 1000), "markets_scored": len(scored), "threshold": THR,
        "window_hours": [1, 30], "scorer": scorer,
        "scorer_note": ("XGBoost cross-market model" if scorer == "xgboost" else
                        "Per-category calibration of the market price fitted in the 4.36M-market study (slope/intercept on logit price). "
                        "The full XGBoost weights live on Kaggle and were not on this machine at run time."),
        "picks": picks, "closest": closest, "backtest": BACKTEST,
        "disclaimer": "Paper recommendations, not financial advice. 21+. Kalshi demo exchange for automated orders.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fo:
        json.dump(doc, fo, indent=1)
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    seen = set()
    if os.path.exists(LEDGER):
        for line in open(LEDGER):
            try:
                r = json.loads(line); seen.add((r["ticker"], r["side"]))
            except Exception:
                pass
    with open(LEDGER, "a") as lf:
        for p in picks:
            if (p["ticker"], p["side"]) in seen:
                continue
            lf.write(json.dumps({**p, "logged_ms": doc["generated_ms"], "scorer": scorer, "settled": None}) + "\n")
    print(f"done: {len(scored)} scored, {len(picks)} picks, {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()

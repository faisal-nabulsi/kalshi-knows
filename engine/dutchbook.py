"""Dutch Book scanner for Kalshi public markets. Paper analysis only; no trading endpoints."""
import math, time, json, re, random, sys, os
from collections import defaultdict
import httpx
import numpy as np
from scipy.optimize import linprog

BASE = "https://api.elections.kalshi.com/trade-api/v2"
EXCLUDED_CATS = {"politics", "elections", "world"}
GEO_WORDS = re.compile(r"\b(war|invade|invasion|ceasefire|missile|nuclear strike|military|russia|ukraine|israel|gaza|iran|hamas|nato|taiwan|china attack|troops)\b", re.I)
GENERAL_RATE = 0.07
# series-prefix overrides (index products charge about half the general rate)
RATE_OVERRIDES = {"INX": 0.035, "NASDAQ100": 0.035, "KXINX": 0.035, "KXNASDAQ100": 0.035}
MIN_PROFIT = 0.005  # ignore sub-half-cent "profits" (rounding noise)
_last = [0.0]


def rate_for(series: str) -> float:
    for k, v in RATE_OVERRIDES.items():
        if (series or "").upper().startswith(k):
            return v
    return GENERAL_RATE


def fee(price: float, qty: float, rate: float = GENERAL_RATE) -> float:
    """Kalshi taker fee for one order: ceil to the cent of rate*C*P*(1-P)."""
    if qty <= 0:
        return 0.0
    raw = rate * qty * price * (1 - price)
    return math.ceil(round(raw * 100, 6)) / 100


def _get(client, path, params=None):
    for i in range(6):
        dt = time.time() - _last[0]
        if dt < 0.34:
            time.sleep(0.34 - dt)
        _last[0] = time.time()
        try:
            r = client.get(BASE + path, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
        except httpx.HTTPError:
            pass
        time.sleep(min(30, 2 ** i) + random.random())
    raise RuntimeError("kalshi fetch failed " + path)


def fetch_events():
    out, cur = [], None
    with httpx.Client() as c:
        while True:
            p = {"status": "open", "with_nested_markets": "true", "limit": 200}
            if cur:
                p["cursor"] = cur
            r = _get(c, "/events", p)
            out += r.get("events", [])
            cur = r.get("cursor")
            if not cur:
                break
    return out


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


class Mk:
    def __init__(self, m):
        self.t = m["ticker"]
        self.label = m.get("yes_sub_title") or m.get("title") or self.t
        self.ya, self.na = _f(m.get("yes_ask_dollars")), _f(m.get("no_ask_dollars"))
        self.yq = _f(m.get("yes_ask_size_fp")) or 0.0
        # NO ask size equals the YES bid size
        self.nq = _f(m.get("yes_bid_size_fp")) or 0.0
        self.st = m.get("strike_type") or ""
        self.fl, self.cap = _f(m.get("floor_strike")), _f(m.get("cap_strike"))
        self.m = m

    def ok_yes(self):
        return self.ya is not None and 0 < self.ya < 1 and self.yq > 0

    def ok_no(self):
        return self.na is not None and 0 < self.na < 1 and self.nq > 0


def _leg(mk, side, qty):
    return {"ticker": mk.t, "label": mk.label, "side": side,
            "price": mk.ya if side == "yes" else mk.na, "qty": round(qty, 2)}


def _build(ev, kind, legs, payout, rate, explanation, oid):
    """legs: list of (Mk, side, qty). Quote fees per leg order at that qty."""
    cost = sum((mk.ya if s == "yes" else mk.na) * q for mk, s, q in legs)
    fees = sum(fee(mk.ya if s == "yes" else mk.na, q, rate) for mk, s, q in legs)
    pb = payout - cost
    return {"id": oid, "event_ticker": ev["event_ticker"], "title": ev.get("title", ""),
            "category": ev.get("category", ""), "kind": kind,
            "legs": [_leg(mk, s, q) for mk, s, q in legs],
            "cost": round(cost, 4), "worst_case_payout": round(payout, 4),
            "profit_before_fees": round(pb, 4), "fees": round(fees, 4),
            "profit_after_fees": round(pb - fees, 4), "explanation": explanation}


def _covers_line(mks):
    """True if strikes tile the whole real line with open-ended tails (so exactly one wins)."""
    ivs = []
    for m in mks:
        if not _clean_strike(m):
            return False
        st = m.st
        if st in ("less", "less_or_equal") and m.cap is not None:
            ivs.append((-math.inf, m.cap, st))
        elif st in ("greater", "greater_or_equal") and m.fl is not None:
            ivs.append((m.fl, math.inf, st))
        elif st == "between" and m.fl is not None and m.cap is not None:
            ivs.append((m.fl, m.cap, st))
        else:
            return False
    ivs.sort(key=lambda x: (x[0], x[1]))
    if not ivs or ivs[0][0] != -math.inf or ivs[-1][1] != math.inf:
        return False
    for a, b in zip(ivs, ivs[1:]):
        if abs(a[1] - b[0]) > 1e-9:  # contiguous (integer gaps like 70-71 / 72-73 are not tiled here)
            # allow integer-step tiling: cap + 1 == next floor
            if not (a[1] == int(a[1]) and b[0] == int(b[0]) and abs(a[1] + 1 - b[0]) < 1e-9):
                return False
    return True


def _is_ladder(mks):
    return len(mks) >= 2 and all(m.st in ("greater", "greater_or_equal") and m.fl is not None for m in mks)


def _is_below_ladder(mks):
    return len(mks) >= 2 and all(m.st in ("less", "less_or_equal") and m.cap is not None for m in mks)


def _none_market(mks):
    """Only an explicit 'none/no one' outcome proves exhaustiveness ('Other' does not: nobody might win)."""
    return any(re.search(r"\b(none|no one|nobody|no winner)\b", (m.label or ""), re.I) for m in mks)


def _other_market(mks):
    return any(re.search(r"\b(other|none|no one|nobody|field)\b", (m.label or "") + " " + m.m.get("title", ""), re.I) for m in mks)


def check_mutex_no(ev, mks, rate):
    """Buy NO on every outcome: pays >= N-1 if at most one wins."""
    ms = [m for m in mks if m.ok_no()]
    n = len(mks)
    if len(ms) != n or n < 2:
        return None
    q = min(m.nq for m in ms)
    q = math.floor(q)
    if q < 1:
        return None
    legs = [(m, "no", q) for m in ms]
    tot = sum(m.na for m in ms)
    pay = (n - 1) * q
    if (n - 1) - tot <= 0:
        return None
    ex = (f"At most one of these {n} outcomes can happen, so NO wins on at least {n-1} of them. "
          f"Buying NO on all {n} costs ${tot:.2f} per set but pays at least ${n-1:.2f}.")
    return _build(ev, "bracket_sum", legs, pay, rate, ex, f"{ev['event_ticker']}:mutex_no")


def check_exhaustive_yes(ev, mks, rate, exhaustive):
    ms = [m for m in mks if m.ok_yes()]
    n = len(mks)
    if len(ms) != n or n < 2:
        return None
    tot = sum(m.ya for m in ms)
    if tot >= 1:
        return None
    q = math.floor(min(m.yq for m in ms))
    if q < 1:
        return None
    legs = [(m, "yes", q) for m in ms]
    if exhaustive:
        ex = (f"These {n} outcomes cover every possibility, so exactly one pays $1. "
              f"Buying YES on all of them costs ${tot:.2f} and always returns $1.00.")
        return _build(ev, "exhaustive_set", legs, q, rate, ex, f"{ev['event_ticker']}:exh_yes")
    r = _build(ev, "exhaustive_set", legs, q, rate,
               f"Looks like free money: all {n} YES prices add up to ${tot:.2f}, under $1. But the list is not "
               f"exhaustive, so an unlisted outcome can win and every ticket would lose.", f"{ev['event_ticker']}:fake_exh")
    r["false_positive"] = True
    return r


def check_ladders(ev, mks, rate, below=False):
    out = []
    if not below:
        s = sorted(mks, key=lambda m: m.fl)
        pairs = [(a, b) for i, a in enumerate(s) for b in s[i + 1:] if a.fl < b.fl]  # a=low, b=high
        for lo, hi in pairs:
            # P(>hi) <= P(>lo): buy YES(lo)+NO(hi); payout >=1
            if lo.ok_yes() and hi.ok_no() and lo.ya + hi.na < 1:
                q = math.floor(min(lo.yq, hi.nq))
                if q < 1:
                    continue
                tot = lo.ya + hi.na
                ex = (f"Kalshi prices '{hi.label}' above '{lo.label}' (it should never be higher, since beating the "
                      f"bigger number means beating the smaller one). Buy YES on {lo.label} and NO on {hi.label} for "
                      f"${tot:.2f} total; you get at least $1.00 whatever happens.")
                out.append(_build(ev, "ladder", [(lo, "yes", q), (hi, "no", q)], q, rate, ex,
                                  f"{ev['event_ticker']}:lad:{lo.t}:{hi.t}"))
    else:
        s = sorted(mks, key=lambda m: m.cap)
        for i, lo in enumerate(s):
            for hi in s[i + 1:]:
                if lo.cap >= hi.cap:
                    continue
                # P(<lo) <= P(<hi): buy YES(hi)+NO(lo)
                if hi.ok_yes() and lo.ok_no() and hi.ya + lo.na < 1:
                    q = math.floor(min(hi.yq, lo.nq))
                    if q < 1:
                        continue
                    tot = hi.ya + lo.na
                    ex = (f"Kalshi prices '{lo.label}' above '{hi.label}', though being below the smaller number "
                          f"means being below the bigger one. Buy YES on {hi.label} and NO on {lo.label} for "
                          f"${tot:.2f}; you get at least $1.00 whatever happens.")
                    out.append(_build(ev, "ladder", [(hi, "yes", q), (lo, "no", q)], q, rate, ex,
                                      f"{ev['event_ticker']}:lad:{hi.t}:{lo.t}"))
    return out


def _outcome_states(mks):
    """Discretize the line into states from strikes; return (states, indicator(m, state)) or None."""
    pts = set()
    for m in mks:
        for v in (m.fl, m.cap):
            if v is not None:
                pts.add(v)
    if not pts or any(m.st not in ("greater", "greater_or_equal", "less", "less_or_equal", "between") for m in mks):
        return None
    pts = sorted(pts)
    # states: points themselves, and midpoints/tails between them
    st = [pts[0] - 1]
    for a, b in zip(pts, pts[1:]):
        st += [a, (a + b) / 2]
    st += [pts[-1], pts[-1] + 1]

    def ind(m, x):
        t = m.st
        if t == "greater": return x > m.fl
        if t == "greater_or_equal": return x >= m.fl
        if t == "less": return x < m.cap
        if t == "less_or_equal": return x <= m.cap
        return m.fl <= x <= m.cap
    return st, ind


def check_lp(ev, mks, rate, exhaustive_known=True):
    """Min-cost portfolio of YES/NO buys paying >=1 in every state; includes linearized fee."""
    ms = [m for m in mks if m.st and (m.ok_yes() or m.ok_no())]
    if len(ms) < 2 or len(ms) > 60:
        return None
    r = _outcome_states(ms)
    if not r:
        return None
    states, ind = r
    cols, meta = [], []
    for m in ms:
        if m.ok_yes():
            cols.append((m, "yes", m.ya, m.yq))
        if m.ok_no():
            cols.append((m, "no", m.na, m.nq))
    # linearized fee per contract (exact at the ceil-free level): rate*P*(1-P)
    c = np.array([p + rate * p * (1 - p) for _, _, p, _ in cols])
    A = np.zeros((len(states), len(cols)))
    for j, (m, s, p, q) in enumerate(cols):
        for i, x in enumerate(states):
            y = ind(m, x)
            A[i, j] = 1.0 if (y if s == "yes" else not y) else 0.0
    # maximize profit: pay_min - cost. Use t = guaranteed payout (variable), maximize t - c.x
    nvar = len(cols) + 1
    obj = np.concatenate([c, [-1.0]])
    Aub = np.hstack([-A, np.ones((len(states), 1))])  # t - A x <= 0
    bub = np.zeros(len(states))
    bounds = [(0, math.floor(q)) for _, _, _, q in cols] + [(0, None)]
    res = linprog(obj, A_ub=Aub, b_ub=bub, bounds=bounds, method="highs")
    if not res.success or -res.fun <= 1e-6:
        return None
    x = res.x[:-1]
    legs = [(cols[j][0], cols[j][1], round(x[j])) for j in range(len(cols)) if round(x[j]) >= 1]
    if not legs:
        return None
    # recompute exact payout with rounded integer qtys
    pay = min(sum(q * (1.0 if (ind(m, st) if s == "yes" else not ind(m, st)) else 0.0) for m, s, q in legs) for st in states)
    o = _build(ev, "bracket_sum" if all(m.st == "between" or True for m in ms) else "ladder", legs, pay, rate,
               "The LP found a basket of YES/NO trades whose payout is at least "
               f"${pay:.0f} in every possible outcome for less than that cost, net of fees: "
               + "; ".join(f"{s.upper()} {m.label}" for m, s, q in legs[:6]) + ("..." if len(legs) > 6 else "") + ".",
               f"{ev['event_ticker']}:lp")
    o["kind"] = "ladder" if (_is_ladder(ms) or _is_below_ladder(ms)) else "bracket_sum"
    return o


def classify(ev):
    cat = (ev.get("category") or "").strip()
    if cat.lower() in EXCLUDED_CATS:
        return False
    if GEO_WORDS.search(ev.get("title", "") + " " + ev.get("sub_title", "")):
        return False
    return True


def _clean_strike(m):
    t = m.st
    if t in ("greater", "greater_or_equal"):
        return m.fl is not None and m.cap is None
    if t in ("less", "less_or_equal"):
        return m.cap is not None and m.fl is None
    if t == "between":
        return m.fl is not None and m.cap is not None and m.fl < m.cap
    return False


def check_time_ladder(ev, mks, rate):
    """Same question with different deadlines ('by 2027' vs 'by 2028'): the later one can't be cheaper."""
    out = []
    by = defaultdict(list)
    for m in mks:
        if m.st and m.m.get("close_time") and (m.fl is not None or m.cap is not None):
            by[(m.st, m.fl, m.cap, re.sub(r'[-+\d.,]+', '#', (m.label or '')).strip().lower())].append(m)
    for grp in by.values():
        if len(grp) < 2:
            continue
        grp.sort(key=lambda m: m.m["close_time"])
        for i, early in enumerate(grp):
            for late in grp[i + 1:]:
                if early.m["close_time"] == late.m["close_time"]:
                    continue
                if late.ok_yes() and early.ok_no() and late.ya + early.na < 1:
                    q = math.floor(min(late.yq, early.nq))
                    if q < 1:
                        continue
                    tot = late.ya + early.na
                    ex = (f"'{early.label}' is priced above '{late.label}', but if it happens by the earlier deadline it "
                          f"has also happened by the later one. Buy YES on {late.label} and NO on {early.label} for "
                          f"${tot:.2f} total; you get at least $1.00 whatever happens.")
                    out.append(_build(ev, "ladder", [(late, "yes", q), (early, "no", q)], q, rate, ex,
                                      f"{ev['event_ticker']}:time:{early.t}:{late.t}"))
    return out


def _groups(mks):
    """Split strike-bearing markets into same-subject groups (e.g. one per team in a spread event)."""
    g = defaultdict(list)
    for m in mks:
        if not m.st or not _clean_strike(m):
            continue
        fam = "above" if m.st.startswith("greater") else "below" if m.st.startswith("less") else m.st
        subj = re.sub(r"[-+\d.,]+", "#", (m.label or "")).strip().lower()
        g[(fam if fam != "between" else "x", subj if fam != "between" else "")].append(m)
    out = []
    for v in g.values():
        keys = [(m.st, m.fl, m.cap) for m in v]
        if len(v) >= 2 and len(set(keys)) == len(keys):  # duplicates = deadline ladders, handled separately
            out.append(v)
    return out


def analyze_event(ev):
    """Return (opportunities, near_misses) for one event dict with nested markets."""
    mks = [Mk(m) for m in ev.get("markets", []) if m.get("status") in ("active", "open", None) and m.get("market_type", "binary") == "binary"]
    rate = rate_for(ev.get("series_ticker") or ev["event_ticker"])
    cands = []
    mutex = bool(ev.get("mutually_exclusive"))
    if mutex:
        r = check_mutex_no(ev, mks, rate)
        if r: cands.append(r)
        exhaustive = _covers_line(mks) or _none_market(mks)
        r = check_exhaustive_yes(ev, mks, rate, exhaustive)
        if r: cands.append(r)
    cands += check_time_ladder(ev, mks, rate)
    seen = {frozenset(l["ticker"] for l in c["legs"]) for c in cands}
    for grp in _groups(mks):
        if not mutex and _covers_line(grp):
            r = check_exhaustive_yes(ev, grp, rate, True)
            if r: cands.append(r)
        if _is_ladder(grp):
            cands += check_ladders(ev, grp, rate)
        if _is_below_ladder(grp):
            cands += check_ladders(ev, grp, rate, below=True)
        r = check_lp(ev, grp, rate)
        if r and frozenset(l["ticker"] for l in r["legs"]) not in seen:
            r["id"] += ":" + grp[0].t
            cands.append(r)
    opps, near = [], []
    for c in cands:
        if c.pop("false_positive", False):
            near.append(c)
        elif c["profit_after_fees"] > MIN_PROFIT:
            opps.append(c)
        elif c["profit_before_fees"] > 0:
            near.append(c)
    return opps, near


TIERS = {1: ("Dugar", "Still on the waitlist for his own pre-seed round."),
         2: ("House Cat", "Pre-revenue, pre-product, pre-awake. 'Building in stealth' since 2023."),
         3: ("Gazelle", "Fast, pretty, and somebody's lunch. Series A tourist."),
         4: ("Everyone Else", "A 40-slide consulting deck with no recommendation."),
         5: ("Lion", "Tier-1 partner. Eats the gazelle, takes the board seat."),
         6: ("Kevin & Faisal", "Returned the fund. Twice.")}


def tier_of(o) -> int:
    r = o["profit_after_fees"] / o["cost"] if o["cost"] else 0
    if r <= 0: return 1
    for t, lim in ((2, .005), (3, .01), (4, .02), (5, .05)):
        if r < lim: return t
    return 6


def add_tier(o):
    t = tier_of(o)
    o["tier"], o["tier_name"], o["tier_blurb"] = t, TIERS[t][0], TIERS[t][1]
    return o


def scan(events=None) -> dict:
    events = events if events is not None else fetch_events()
    opps, near = [], []
    cats = defaultdict(lambda: {"events": 0, "violations": 0})
    se = sm = 0
    for ev in events:
        if ev.get("mve_collection_ticker") or "KXMVE" in (ev.get("event_ticker") or "") or "KXMVE" in (ev.get("series_ticker") or ""):
            continue
        if not classify(ev):
            continue
        mk = ev.get("markets") or []
        if not mk:
            continue
        se += 1
        sm += len(mk)
        cat = ev.get("category") or "Other"
        cats[cat]["events"] += 1
        try:
            o, n = analyze_event(ev)
        except Exception as e:  # never let one weird event kill the scan
            print("skip", ev.get("event_ticker"), e, file=sys.stderr)
            continue
        if o:
            cats[cat]["violations"] += 1
        opps += o
        near += n
    for o in opps + near:
        add_tier(o)
    opps.sort(key=lambda o: -o["profit_after_fees"])
    total = sum(max(o["profit_after_fees"], 0) for o in opps)  # profit already scaled to qty fillable at top of book
    near.sort(key=lambda o: -o["profit_before_fees"])
    return {"updated_ms": int(time.time() * 1000), "scanned_events": se, "scanned_markets": sm,
            "total_mispricing_usd": round(total, 2),
            "note": "Top-of-book only: profit is for the quantity fillable at the quoted asks. Paper analysis, not advice.",
            "opportunities": opps, "near_misses": near[:100], "by_category": dict(cats)}


def main():
    d = scan()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "data", "dutchbook.json")
    json.dump(d, open(path, "w"), indent=1)
    print(f"events={d['scanned_events']} markets={d['scanned_markets']} opps={len(d['opportunities'])} "
          f"near={len(d['near_misses'])} total=${d['total_mispricing_usd']}")


if __name__ == "__main__":
    main()

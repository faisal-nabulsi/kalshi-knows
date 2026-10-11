"""B) Pre-registered market-edge finder (see train/context/HYPOTHESES.md, committed before this ran).

After a big in-game jump, is Kalshi's home-win price mis-calibrated against the final result in identifiable
contexts?  Discover on 2025, test survivors once on 2026, paper P&L per $1 contract after Kalshi taker fees,
game-clustered bootstrap, Bonferroni over 8 hypotheses.  Output: train/context/out/market_edge.json
"""
import json, math, sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "train"))
import finetune_real as fr  # noqa: E402

THR, COOLDOWN_MS, B = 0.08, 60_000, 5000
M_TESTS, ALPHA = 8, 0.05


def detect_bin(t, p):
    """Live detector (same rule as finetune_real.detect): returns the confirm bin i and the signed jump."""
    w = int(fr.WINDOW_S / fr.STEP)
    for i in range(w, len(p) - fr.HOLD_BINS):
        if t[i] < -10 or np.isnan(p[i]) or np.isnan(p[i - w]):
            continue
        d = p[i] - np.nanmin(p[i - w:i + 1]) if p[i] >= p[i - w] else p[i] - np.nanmax(p[i - w:i + 1])
        if abs(d) >= THR and all(abs(p[i + k] - (p[i] - d)) >= THR * 0.8 for k in range(1, fr.HOLD_BINS + 1)):
            return i + fr.HOLD_BINS, d   # confirmed after the 3 s hold
    return None


df = fr.load_windows()
fires, series = [], {}
for r in df.itertuples(index=False):
    t = np.asarray(r.path_t, float); p = pd.Series(np.asarray(r.path_p, float)).ffill().to_numpy()
    if np.isnan(p).all():
        continue
    series.setdefault(r.game_id, []).append(np.column_stack([r.wallclock_ms + t * 1000, p]))
    hit = detect_bin(t, p)
    if hit is None:
        continue
    i, d = hit
    pih = int(bool(r.posteam_is_home)) if pd.notna(r.posteam_is_home) else int(r.posteam == r.home)
    fires.append({"game_id": r.game_id, "season": int(getattr(r, "season", 2026)), "abs_ms": r.wallclock_ms + t[i] * 1000,
                  "jump": d, "p_confirm": p[i], "qtr": int(min(max(r.qtr, 1), 5)), "gsr": r.game_seconds_remaining,
                  "posteam_is_home": pih, "category": r.category})
F = pd.DataFrame(fires).sort_values(["game_id", "abs_ms"])
keep, last = [], {}
for k, r in F.iterrows():               # 60 s cooldown on absolute time (windows overlap -> same jump seen twice)
    if r.game_id in last and r.abs_ms - last[r.game_id] < COOLDOWN_MS:
        continue
    last[r.game_id] = r.abs_ms; keep.append(k)
F = F.loc[keep].reset_index(drop=True)

# merged per-game price series (all windows), last trade at or before a wallclock time
S = {gid: (lambda a: a[np.argsort(a[:, 0], kind="stable")])(np.vstack(v)) for gid, v in series.items()}


def price_at(gid, ms, max_gap_ms=6000):
    a = S[gid]; j = np.searchsorted(a[:, 0], ms, side="right") - 1
    while j >= 0 and np.isnan(a[j, 1]):
        j -= 1
    return a[j, 1] if j >= 0 and ms - a[j, 0] <= max_gap_ms else np.nan


for lag in (20, 60):
    F[f"p{lag}"] = [price_at(r.game_id, r.abs_ms + lag * 1000) for r in F.itertuples()]

ctx = pd.read_parquet(ROOT / "train/context/out/game_context.parquet").set_index("game_id")
F = F.join(ctx[["home_win", "tie", "spread_home", "roof", "temp", "wind", "primetime", "home_dome_team", "away_dome_team",
                "home_backup_qb", "away_backup_qb"]], on="game_id")
n_tie = int(F.tie.sum()); F = F[F.home_win.notna()].reset_index(drop=True)
up = F.jump > 0                                    # jump moved toward the home team
fav_team_home = up.to_numpy()                      # "favored by the jump" = team the price moved toward
print(f"fires after cooldown: {len(F)} ({F.season.value_counts().to_dict()}), ties dropped: {n_tie}")


def fee(ask, C):
    return np.ceil(np.round(0.07 * C * ask * (1 - ask) * 100, 9)) / 100 / C


def trades(mask, buy_home, lag=20, C=100):
    """buy_home: bool array (True = buy home YES, False = buy away YES). Returns per-trade frame."""
    p = F[f"p{lag}"].to_numpy()
    ask = np.where(buy_home, p + 0.01, 1 - p + 0.01)
    ok = mask & ~np.isnan(p) & (ask < 1.0)
    win = np.where(buy_home, F.home_win.to_numpy(), 1 - F.home_win.to_numpy())
    f = fee(ask, C)
    return pd.DataFrame({"game_id": F.game_id[ok].to_numpy(), "season": F.season[ok].to_numpy(), "ask": ask[ok],
                         "win": win[ok], "fee": f[ok], "pnl": (win - ask - f)[ok]})


def boot_roi(T, seed=0):
    if len(T) == 0:
        return np.array([np.nan])
    agg = T.assign(cost=T.ask + T.fee).groupby("game_id")[["pnl", "cost"]].sum().to_numpy()
    draws = np.random.default_rng(seed).integers(0, len(agg), (B, len(agg)))
    return agg[draws, 0].sum(1) / agg[draws, 1].sum(1)


def stats(T, seed=0):
    if len(T) == 0:
        return {"n": 0}
    bs = boot_roi(T, seed); roi = T.pnl.sum() / (T.ask + T.fee).sum()
    return {"n": int(len(T)), "games": int(T.game_id.nunique()), "hit_rate": round(float(T.win.mean()), 3),
            "avg_ask": round(float(T.ask.mean()), 3), "avg_fee": round(float(T.fee.mean()), 4),
            "pnl_per_contract": round(float(T.pnl.mean()), 4), "roi": round(float(roi), 4),
            "roi_gross_at_last_trade_no_fee": round(float((T.win - T.ask + 0.01).sum() / (T.ask - 0.01).sum()), 4),
            "roi_ci95": [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)],
            "p_one_sided": round(float((bs <= 0).mean()), 4)}


q = F.qtr.to_numpy(); gsr = F.gsr.to_numpy(); s20 = F.p20.to_numpy()
outdoor_bad = F.roof.isin(["outdoors", "open"]).to_numpy() & ((F.temp <= 40) | (F.wind >= 15)).to_numpy()
fav_is_dome = np.where(fav_team_home, F.home_dome_team, F.away_dome_team) == 1
fav_backup = np.where(fav_team_home, F.home_backup_qb, F.away_backup_qb) == 1
spread = F.spread_home.to_numpy()
favorite_home = spread > 0
against_fav = np.where(favorite_home, ~up, up)
fade = ~fav_team_home          # buy the side the jump moved against
follow = fav_team_home
H = {
    "H1 Q1-Q2 jump -> fade": (np.isin(q, [1, 2]), fade),
    "H2 Q4 <=5:00 or OT -> follow": (((q == 4) & (gsr <= 300)) | (q >= 5), follow),
    "H3 dome team favored, outdoors cold/windy -> fade": (outdoor_bad & fav_is_dome, fade),
    "H4 favorite (>=6.5) hit early -> buy favorite": ((np.abs(spread) >= 6.5) & np.isin(q, [1, 2]) & against_fav, favorite_home),
    "H5 primetime -> fade": (F.primetime.to_numpy() == 1, fade),
    "H6 jump favored backup-QB team -> fade": (fav_backup, fade),
    "H7 price >=0.85 one side -> buy favorite": ((s20 >= 0.85) | (s20 <= 0.15), s20 >= 0.85),
}
# H8 grid: quarter x jump size x toward/against offense x action; chosen on 2025 only
toward_off = (F.posteam_is_home.to_numpy() == 1) == fav_team_home
aj = F.jump.abs().to_numpy()
grid = {}
for qn, qm in {"Q1-2": np.isin(q, [1, 2]), "Q3": q == 3, "Q4/OT": q >= 4}.items():
    for sn, sm in {"0.08-0.15": aj < 0.15, ">=0.15": aj >= 0.15}.items():
        for on, om in {"toward offense": toward_off, "against offense": ~toward_off}.items():
            for an, side in {"fade": fade, "follow": follow}.items():
                grid[f"{qn} | {sn} | {on} | {an}"] = (qm & sm & om, side)
s25, s26 = F.season.to_numpy() == 2025, F.season.to_numpy() == 2026
gres = {k: stats(trades(m & s25, b), 1) for k, (m, b) in grid.items()}
elig = {k: v for k, v in gres.items() if v["n"] >= 40}
best = max(elig, key=lambda k: elig[k]["roi"])
H[f"H8 grid best on 2025: {best}"] = grid[best]

res = {"n_fires": int(len(F)), "by_season": {int(k): int(v) for k, v in F.season.value_counts().items()}, "ties_dropped": n_tie,
       "fee_model": "ceil(0.07*C*P*(1-P)) per order, C=100 primary; ask = last trade + 1c",
       "bonferroni_alpha_one_sided": ALPHA / M_TESTS, "hypotheses": {}, "h8_grid_2025": gres}
for name, (m, b) in H.items():
    d25 = stats(trades(m & s25, b, 20), 2); t26 = stats(trades(m & s26, b, 20), 3)
    passed = d25.get("n", 0) >= 30 and d25.get("roi", -1) > 0 and d25.get("p_one_sided", 1) < ALPHA
    survived = passed and t26.get("n", 0) > 0 and t26["roi"] > 0 and t26["p_one_sided"] < ALPHA / M_TESTS
    res["hypotheses"][name] = {
        "discovery_2025_+20s": d25, "passed_discovery": bool(passed), "test_2026_+20s": t26, "survived_oos": bool(survived),
        "robustness_+60s": {"2025": stats(trades(m & s25, b, 60), 4), "2026": stats(trades(m & s26, b, 60), 5)},
        "fee_C1_+20s": {"2025": stats(trades(m & s25, b, 20, C=1), 6), "2026": stats(trades(m & s26, b, 20, C=1), 7)}}
for nm, side in {"ALL fade": fade, "ALL follow": follow}.items():
    res[nm] = {str(s): {f"+{lag}s": stats(trades((F.season.to_numpy() == s), side, lag), 8) for lag in (20, 60)}
               for s in (2025, 2026)}

# ---- calibration of the post-jump price vs the final result
cal = {}
for lag in (20, 60):
    for sname, sm in {"2025": s25, "2026": s26, "all": np.ones(len(F), bool)}.items():
        p = F[f"p{lag}"].to_numpy(); m = sm & ~np.isnan(p); pv, yv, gv = p[m], F.home_win.to_numpy()[m], F.game_id.to_numpy()[m]
        bins = np.clip((pv * 10).astype(int), 0, 9)
        rel = [{"bin": f"{b/10:.1f}-{(b+1)/10:.1f}", "n": int((bins == b).sum()), "mean_price": round(float(pv[bins == b].mean()), 3),
                "home_win_rate": round(float(yv[bins == b].mean()), 3)} for b in range(10) if (bins == b).any()]
        lp = np.log(np.clip(pv, .01, .99) / (1 - np.clip(pv, .01, .99)))

        def slope(ix):
            from sklearn.linear_model import LogisticRegression
            return LogisticRegression(C=1e6, max_iter=1000).fit(lp[ix, None], yv[ix]).coef_[0, 0]
        games = np.unique(gv); gi = {k: np.where(gv == k)[0] for k in games}; rng = np.random.default_rng(9)
        sl = [slope(np.concatenate([gi[k] for k in rng.choice(games, len(games))])) for _ in range(300)]
        cal[f"+{lag}s_{sname}"] = {"n": int(m.sum()), "games": int(len(games)),
                                   "ece": round(float(sum(r["n"] * abs(r["mean_price"] - r["home_win_rate"]) for r in rel) / m.sum()), 4),
                                   "brier": round(float(((pv - yv) ** 2).mean()), 4),
                                   "calib_slope": round(float(slope(np.arange(len(pv)))), 3),
                                   "calib_slope_ci95": [round(float(np.percentile(sl, 2.5)), 3), round(float(np.percentile(sl, 97.5)), 3)],
                                   "reliability": rel}
res["calibration"] = cal
# does the price keep moving after +20 s? (continuation > 0 = underreaction at +20 s, < 0 = overshoot)
cont = (F.p60 - F.p20) * np.sign(F.jump)
res["drift_+20s_to_+60s_in_jump_direction"] = {"mean": round(float(cont.mean()), 4), "median": round(float(cont.median()), 4),
                                               "n": int(cont.notna().sum())}
(ROOT / "train/context/out/market_edge.json").write_text(json.dumps(res, indent=1, default=float))

print("\nH | 2025 n hit ROI CI p | pass | 2026 n hit ROI CI p | survived")
for k, v in res["hypotheses"].items():
    a, b = v["discovery_2025_+20s"], v["test_2026_+20s"]
    fmt = lambda s: f"n={s.get('n')} hit={s.get('hit_rate')} roi={s.get('roi')} {s.get('roi_ci95')} p={s.get('p_one_sided')}"
    print(f"{k}\n   2025 {fmt(a)} pass={v['passed_discovery']}\n   2026 {fmt(b)} survived={v['survived_oos']}")
for nm in ("ALL fade", "ALL follow"):
    print(nm, {s: {l: (x.get("n"), x.get("roi"), x.get("roi_ci95"), x.get("roi_gross_at_last_trade_no_fee")) for l, x in v.items()} for s, v in res[nm].items()})
for k, v in cal.items():
    print(k, "n", v["n"], "ece", v["ece"], "brier", v["brier"], "slope", v["calib_slope"], v["calib_slope_ci95"])
print("drift", res["drift_+20s_to_+60s_in_jump_direction"])

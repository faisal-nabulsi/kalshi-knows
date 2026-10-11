"""A) Does pre-game context (venue, weather, betting lines, rest, QB/injuries) help the play-type model?

Same rows and protocol as train/eval_same_rows.py: the stage-2 matrix rebuilt with build_rows() + sim_logprobs()
from train/finetune_real.py (checked identical to train/out/stage2_matrix.npz), production features = stage-1
log-probs + game state, same XGBoost params, GroupKFold(5) by game + the 2025 -> 2026 temporal split, live regime
(|jump| >= 0.08), named-call precision at >= 0.75, game-clustered bootstrap CIs.
Adds: paired bootstrap of the difference vs production, and a placebo (context shuffled across games) to show
what "a gain from noise" looks like.  Output: train/context/out/context_play_model.json
"""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "train"))
import finetune_real as fr  # noqa: E402

K, OTHER = len(fr.CLASSES), fr.CLASSES.index("OTHER")
XP = dict(objective="multi:softprob", num_class=K, max_depth=3, learning_rate=0.05, subsample=0.8,
          colsample_bytree=0.8, min_child_weight=3, reg_lambda=3.0, tree_method="hist")

rows = fr.build_rows(fr.load_windows(), fr.FIRE_TRAIN)
rows = rows[rows["category"].isin(fr.CLASSES)].reset_index(drop=True)
y = rows["category"].map({c: i for i, c in enumerate(fr.CLASSES)}).to_numpy()
g = rows["game_id"].astype(str).to_numpy()
live = rows["delta_home"].abs().to_numpy() >= 0.08
season = rows["season"].to_numpy()
_, Z, _ = fr.sim_logprobs(rows)
simcols = [f"sim_{c}" for c in fr.CLASSES]
base = pd.concat([pd.DataFrame(Z, columns=simcols), rows[fr.STATE].reset_index(drop=True)], axis=1).astype(float)

ref = np.load(ROOT / "train/out/stage2_matrix.npz", allow_pickle=True)
same = len(ref["y"]) == len(y) and (ref["y"] == y).all() and np.allclose(ref["X"][:, :len(base.columns)], base.to_numpy(), equal_nan=True)
print("rows identical to train/out/stage2_matrix.npz:", same, len(y))

# ---- join per-game context; express it relative to the team with the ball (pos) vs the defense (def)
ctx = pd.read_parquet(ROOT / "train/context/out/game_context.parquet").set_index("game_id")
C = ctx.reindex(g).reset_index(drop=True)
pih = rows["posteam_is_home"].to_numpy() == 1
sgn = np.where(pih, 1.0, -1.0)
F = pd.DataFrame({
    "indoor": C.indoor, "grass": C.grass, "temp": C.temp, "wind": C.wind,                    # venue / weather
    "spread_pos": C.spread_home * sgn, "total_line": C.total_line,                          # betting lines
    "rest_diff_pos": (C.home_rest - C.away_rest) * sgn, "div_game": C.div_game, "primetime": C.primetime,
    "backup_qb_pos": np.where(pih, C.home_backup_qb, C.away_backup_qb),                     # QB / injuries
    "backup_qb_def": np.where(pih, C.away_backup_qb, C.home_backup_qb),
    "qb_out_pos": np.where(pih, C.home_qb_out, C.away_qb_out), "qb_out_def": np.where(pih, C.away_qb_out, C.home_qb_out),
    "inj_out_pos": np.where(pih, C.home_inj_out, C.away_inj_out), "inj_out_def": np.where(pih, C.away_inj_out, C.home_inj_out),
}).astype(float)
print("context join coverage:", round(float(C.spread_home.notna().mean()), 3))
GROUPS = {
    "venue_weather": ["indoor", "grass", "temp", "wind"],
    "lines": ["spread_pos", "total_line"],
    "rest_div_primetime": ["rest_diff_pos", "div_game", "primetime"],
    "qb_injuries": ["backup_qb_pos", "backup_qb_def", "qb_out_pos", "qb_out_def", "inj_out_pos", "inj_out_def"],
}
GROUPS["ALL_context"] = sum(GROUPS.values(), [])


def predict(M, split):
    P = np.zeros((len(y), K))
    for tr, te in split:
        P[te] = xgb.train(XP, xgb.DMatrix(M[tr], y[tr]), 300).predict(xgb.DMatrix(M[te]))
    return P


def summ(P, mask):
    pred, conf = P.argmax(1), P.max(1)
    named = (pred != OTHER) & (conf >= 0.75)
    pp = np.clip(P[np.arange(len(y)), y], 1e-6, 1)
    return pred == y, named, -np.log(pp)


def report(P, P0, mask, B=2000):
    ok, nm, ll = summ(P, mask); ok0, nm0, ll0 = summ(P0, mask)
    idx = np.where(mask)[0]; gg = g[idx]; games = np.unique(gg)
    gi = {k: idx[gg == k] for k in games}; rng = np.random.default_rng(11)
    d_acc, d_ll, d_np, npv = [], [], [], []
    for _ in range(B):
        s = np.concatenate([gi[k] for k in rng.choice(games, len(games))])
        d_acc.append(ok[s].mean() - ok0[s].mean()); d_ll.append(ll[s].mean() - ll0[s].mean())
        a = ok[s][nm[s]].mean() if nm[s].any() else np.nan; b = ok0[s][nm0[s]].mean() if nm0[s].any() else np.nan
        npv.append(a); d_np.append(a - b)
    q = lambda v: [round(float(np.nanpercentile(v, 2.5)), 3), round(float(np.nanpercentile(v, 97.5)), 3)]
    m = idx
    return {"acc": round(float(ok[m].mean()), 4), "always_other": round(float((y[m] == OTHER).mean()), 4),
            "log_loss": round(float(ll[m].mean()), 4),
            "named_precision": round(float(ok[m][nm[m]].mean()), 4) if nm[m].any() else None, "named_calls": int(nm[m].sum()),
            "named_precision_ci95": q(npv),
            "d_acc_vs_prod": round(float(ok[m].mean() - ok0[m].mean()), 4), "d_acc_ci95": q(d_acc),
            "d_logloss_vs_prod": round(float(ll[m].mean() - ll0[m].mean()), 4), "d_logloss_ci95": q(d_ll),
            "d_named_precision_ci95": q(d_np), "n": int(m.size), "games": int(games.size)}


splits = {"cv_by_game": list(GroupKFold(5).split(base, y, g)),
          "temporal_2025_to_2026": [(np.where(season == 2025)[0], np.where(season == 2026)[0])]}
masks = {"cv_by_game": live, "temporal_2025_to_2026": live & (season == 2026)}
res = {"rows_identical_to_stage2_matrix": bool(same), "n_rows": int(len(y)), "features": GROUPS}
for sname, split in splits.items():
    P0 = predict(base.to_numpy(), split)
    out = {"PRODUCTION (stage1 + state)": report(P0, P0, masks[sname])}
    for gname, cols in GROUPS.items():
        out[f"+ {gname}"] = report(predict(pd.concat([base, F[cols]], axis=1).to_numpy(), split), P0, masks[sname])
    # placebo: the same context columns, shuffled across games (keeps each game internally consistent)
    pl = []
    for seed in range(5):
        games = np.unique(g); perm = dict(zip(games, np.random.default_rng(seed).permutation(games)))
        Fp = F.groupby(g).first().reindex([perm[k] for k in g]).reset_index(drop=True)
        r = report(predict(pd.concat([base, Fp[GROUPS["ALL_context"]]], axis=1).to_numpy(), split), P0, masks[sname], B=200)
        pl.append({k: r[k] for k in ("acc", "d_acc_vs_prod", "d_logloss_vs_prod", "named_precision", "named_calls")})
    out["placebo: ALL_context shuffled across games (5 seeds)"] = pl
    res[sname] = out
    print(f"\n== {sname} (live regime)")
    for k, v in out.items():
        if isinstance(v, list):
            print(f"  {k}: d_acc {[p['d_acc_vs_prod'] for p in v]} d_ll {[p['d_logloss_vs_prod'] for p in v]}")
        else:
            print(f"  {k:30s} acc={v['acc']:.3f} ll={v['log_loss']:.3f} named={v['named_precision']}/{v['named_calls']} "
                  f"d_acc={v['d_acc_vs_prod']:+.3f} {v['d_acc_ci95']} d_ll={v['d_logloss_vs_prod']:+.4f} {v['d_logloss_ci95']} n={v['n']}")

# feature importance (gain) of the full-context model on all rows, for the report
b = xgb.train(XP, xgb.DMatrix(pd.concat([base, F], axis=1), y), 300)
imp = b.get_score(importance_type="gain"); tot = sum(imp.values())
res["gain_share_full_model"] = {k: round(v / tot, 4) for k, v in sorted(imp.items(), key=lambda kv: -kv[1])}
print("\ncontext gain share:", round(sum(v for k, v in res["gain_share_full_model"].items() if k in F.columns), 3))
(ROOT / "train/context/out/context_play_model.json").write_text(json.dumps(res, indent=1))

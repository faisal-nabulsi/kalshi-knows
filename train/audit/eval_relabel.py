"""Same-row evaluation, OLD vs NEW labels (adapted from train/eval_same_rows.py; never touches engine/).
Rows/features = train/out/stage2_matrix.npz (== pipeline/out/fires_relabeled.parquet, verified). Splits: GroupKFold(5) by
game and 2025->2026 temporal. Metrics on the live regime (|delta| >= 0.08): accuracy vs the SAME label set, always-OTHER,
lift with game-clustered bootstrap CI, named-call precision at >= 0.75.  Truth checks: every model's out-of-fold
predictions are also scored against (a) the NEW labels for all rows and (b) the 150 manual labels."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, xgboost as xgb
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[2]; A = Path(__file__).parent
d = np.load(ROOT / "train/out/stage2_matrix.npz", allow_pickle=True)
X, g, live, season = d["X"], d["g"].astype(str), d["live"].astype(bool), d["season"]
cols = list(d["cols"]); ci = {c: i for i, c in enumerate(cols)}
R = pd.read_parquet(ROOT / "pipeline/out/fires_relabeled.parquet")
CL6 = ["TD", "FG", "TURNOVER", "SAFETY", "BIG_PLAY", "OTHER"]; CL7 = CL6 + ["STOP"]; OTHER = 5
assert (R.category_old.map({c: i for i, c in enumerate(CL6)}).to_numpy() == d["y"]).all()
Y = {"OLD": d["y"], "NEW": R.category_new.map({c: i for i, c in enumerate(CL6)}).to_numpy(),
     "NEW7": R.category7.map({c: i for i, c in enumerate(CL7)}).to_numpy()}
sim = [ci[c] for c in cols if c.startswith("sim_")]
state = [ci[c] for c in ["qtr", "game_seconds_remaining", "score_diff_home", "posteam_is_home", "down", "ydstogo", "yardline_100"]]
micro = [ci[c] for c in cols if c.startswith("micro_")]
MODELS = {"PRODUCTION (stage1+state)": sim + state, "stage2 +shape (stage1+state+micro)": sim + state + micro}
M = pd.read_csv(A / "labels_manual.csv", dtype=str)
pos = {f: i for i, f in enumerate(R.fire_id)}; man_idx = np.array([pos[f] for f in M.fire_id])
man6 = M.manual_category.map({c: i for i, c in enumerate(CL6)}).to_numpy()
man7 = M.manual7.map({c: i for i, c in enumerate(CL7)}).to_numpy()


def fit_predict(F, y, K, split):
    P = np.zeros((len(y), K)); P[:, OTHER] = 0
    xp = dict(objective="multi:softprob", num_class=K, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
              min_child_weight=3, reg_lambda=3.0, tree_method="hist", seed=0)
    for tr, te in split:
        P[te] = xgb.train(xp, xgb.DMatrix(F[tr], y[tr]), 300).predict(xgb.DMatrix(F[te]))
    return P


def to6(pred):  # 7-class predictions scored on 6-class truth: STOP -> TURNOVER if it was a failed 4th down else OTHER
    return np.where(pred == 6, OTHER, pred)


def stats(pred, conf, y, gg, B=400):
    named = (pred != OTHER) & (conf >= 0.75)
    games = np.unique(gg); rng = np.random.default_rng(7); idx = {k: np.where(gg == k)[0] for k in games}
    lifts, precs = [], []
    for _ in range(B):
        s = np.concatenate([idx[k] for k in rng.choice(games, len(games))])
        lifts.append((pred[s] == y[s]).mean() - (y[s] == OTHER).mean())
        ns = s[named[s]]
        if len(ns): precs.append((pred[ns] == y[ns]).mean())
    acc = (pred == y).mean(); base = (y == OTHER).mean()
    return {"acc": round(float(acc), 3), "always_other": round(float(base), 3), "lift": round(float(acc - base), 3),
            "lift_ci95": [round(float(np.percentile(lifts, q)), 3) for q in (2.5, 97.5)],
            "named_prec": round(float((pred[named] == y[named]).mean()), 3) if named.any() else None,
            "named_prec_ci95": [round(float(np.percentile(precs, q)), 3) for q in (2.5, 97.5)] if precs else None,
            "named_calls": int(named.sum()), "n": int(len(y)), "games": int(len(games))}


def run(mask_rows, tag):
    rows = np.where(mask_rows)[0]; out = {}
    splits = {"cv_by_game": list(GroupKFold(5).split(rows, groups=g[rows])),
              "temporal_2025_to_2026": [(np.where(season[rows] == 2025)[0], np.where(season[rows] == 2026)[0])]}
    for sp, split in splits.items():
        test = np.zeros(len(rows), bool)
        for _, te in split: test[te] = True
        lv = live[rows] & test
        for lab, y in Y.items():
            K = 7 if lab == "NEW7" else 6
            yy = y[rows]
            out[(sp, lab, "always_other")] = {"self": stats(np.full(lv.sum(), OTHER), np.ones(lv.sum()), yy[lv], g[rows][lv])}
            for mn, fc in MODELS.items():
                P = fit_predict(X[rows][:, fc], yy, K, split)
                pred, conf = P.argmax(1), P.max(1)
                rec = {"self": stats(pred[lv], conf[lv], yy[lv], g[rows][lv])}
                p6 = to6(pred) if K == 7 else pred
                rec["vs_NEW_truth"] = stats(p6[lv], conf[lv], Y["NEW"][rows][lv], g[rows][lv])
                if tag == "all" and sp == "cv_by_game":
                    mi = man_idx; ok = test[mi]
                    yt = man7 if K == 7 else man6
                    rec["vs_manual150"] = {"acc": round(float((pred[mi] == yt)[ok].mean()), 3),
                                           "acc_live": round(float((pred[mi] == yt)[ok & live[mi]].mean()), 3),
                                           "named_prec": round(float((pred[mi] == yt)[ok & (pred[mi] != OTHER) & (conf[mi] >= .75)].mean()), 3),
                                           "named_calls": int((ok & (pred[mi] != OTHER) & (conf[mi] >= .75)).sum()), "n": int(ok.sum())}
                out[(sp, lab, mn)] = rec
    return out


res = {"all_8808_rows": run(np.ones(len(X), bool), "all"), "dedup_one_per_jump": run(R.rep.to_numpy(), "dedup")}
flat = {k: {"|".join(kk): vv for kk, vv in v.items()} for k, v in res.items()}
json.dump(flat, open(A / "eval_relabel.json", "w"), indent=1)
for k, v in res.items():
    print(f"\n######## {k}  (live regime |delta|>=0.08)")
    for (sp, lab, mn), rec in v.items():
        s = rec["self"]
        line = (f"{sp[:8]:8s} {lab:4s} {mn[:34]:34s} acc={s['acc']:.3f} othr={s['always_other']:.3f} lift={s['lift']:+.3f} "
                f"CI{s['lift_ci95']} prec@.75={s['named_prec']} CI{s['named_prec_ci95']} n_calls={s['named_calls']} n={s['n']}")
        if "vs_NEW_truth" in rec:
            t = rec["vs_NEW_truth"]; line += f" || vsNEW acc={t['acc']:.3f} prec={t['named_prec']} CI{t['named_prec_ci95']}"
        if "vs_manual150" in rec:
            m = rec["vs_manual150"]; line += f" || vsMANUAL acc={m['acc']} live={m['acc_live']} prec={m['named_prec']}({m['named_calls']})"
        print(line)

"""Post-test production model: same features as the pre-registered model (stage-1 log-probs + game state),
trained on the AUDITED labels (train/audit/relabel.py: turnovers on downs restored, each jump re-anchored to the
play that caused it, penalty-nullified plays dropped) and with duplicate fires of the same jump removed.
Evaluates with GroupKFold by game + the 2025->2026 temporal split; --deploy writes engine/model/stage2_*."""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "train"))
import finetune_real as F  # noqa: E402

df = pd.read_parquet(ROOT / "pipeline/out/fires_relabeled.parquet")
n0 = len(df)
df = df.drop_duplicates(subset=["game_id", "jump_start_ms"]).reset_index(drop=True)   # one row per real jump
df = df[df["category_new"].isin(F.CLASSES)].reset_index(drop=True)
y = df["category_new"].map({c: i for i, c in enumerate(F.CLASSES)}).to_numpy()
g = df["game_id"].astype(str).to_numpy()
live = df["delta_home"].abs().to_numpy() >= 0.08
season = df["season"].to_numpy()
_, Z, _ = F.sim_logprobs(df)
cols = [f"sim_{c}" for c in F.CLASSES] + F.STATE
X = np.hstack([Z, df[F.STATE].to_numpy(float)])
P_X = dict(objective="multi:softprob", num_class=6, max_depth=3, learning_rate=0.05, subsample=0.8,
           colsample_bytree=0.8, min_child_weight=3, reg_lambda=3.0, tree_method="hist")
print(f"fires {n0} -> unique jumps {len(df)} (live-size {int(live.sum())}); labels {pd.Series(df['category_new']).value_counts().to_dict()}")


def fit(tr):
    return xgb.train(P_X, xgb.DMatrix(X[tr], y[tr]), 300)


def stats(P, mask, name):
    yy, PP, gg = y[mask], P[mask], g[mask]
    pred, conf = PP.argmax(1), PP.max(1); named = (pred != 5) & (conf >= 0.75)
    acc, base = (pred == yy).mean(), (yy == 5).mean()
    games = np.unique(gg); idx = {k: np.where(gg == k)[0] for k in games}; rng = np.random.default_rng(7); L = []
    for _ in range(400):
        s = np.concatenate([idx[k] for k in rng.choice(games, len(games))]); L.append((pred[s] == yy[s]).mean() - (yy[s] == 5).mean())
    r = {"set": name, "n": int(mask.sum()), "games": int(len(games)), "accuracy": round(float(acc), 3), "always_other": round(float(base), 3),
         "lift": round(float(acc - base), 3), "lift_ci95": [round(float(np.percentile(L, q)), 3) for q in (2.5, 97.5)],
         "named_calls": int(named.sum()), "named_precision": round(float((pred[named] == yy[named]).mean()), 3) if named.any() else None}
    print(r); return r


P = np.zeros((len(y), 6))
for tr, te in GroupKFold(5).split(X, y, g):
    P[te] = fit(tr).predict(xgb.DMatrix(X[te]))
res = {"cv_live": stats(P, live, "CV by game, live regime")}
tr, te = np.where(season == 2025)[0], np.where(season == 2026)[0]
Pt = np.zeros((len(y), 6)); Pt[te] = fit(tr).predict(xgb.DMatrix(X[te]))
m = np.zeros(len(y), bool); m[te] = True
res["temporal_live"] = stats(Pt, m & live, "train 2025 -> test 2026, live regime")
(ROOT / "train/out/relabeled_metrics.json").write_text(json.dumps(res, indent=1))

if "--deploy" in sys.argv:
    b = fit(np.arange(len(y)))
    dst = ROOT / "engine/model"
    b.save_model(str(dst / "stage2_xgb.json"))
    meta = json.loads((dst / "stage2_meta.json").read_text())
    meta.update({"features": cols, "best": "stack_xgb", "production": "stage1_plus_state, AUDITED labels (train/audit), deduped jumps",
                 "labels": pd.Series(df["category_new"]).value_counts().to_dict(), "relabeled_metrics": res})
    (dst / "stage2_meta.json").write_text(json.dumps(meta, indent=1, default=float))
    print("deployed relabeled model to engine/model/stage2_xgb.json")

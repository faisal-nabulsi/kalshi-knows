"""Precision-targeted calling: per-play-type confidence thresholds so that NAMED calls are right >=90% of the time.
Thresholds are chosen on 2025 (out-of-fold, lag-robust model, one-play-late state = live conditions), then
verified once on 2026 games never used for choosing. Writes engine/model/precision_gate.json."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, xgboost as xgb
from sklearn.model_selection import GroupKFold
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "train"))
import finetune_real as F, train_lagged as L  # noqa: E402
df = pd.read_parquet(ROOT / "pipeline/out/fires_relabeled.parquet").drop_duplicates(subset=["game_id", "jump_start_ms"])
df = df[df["category_new"].isin(F.CLASSES)].reset_index(drop=True)
y = df["category_new"].map({c: i for i, c in enumerate(F.CLASSES)}).to_numpy(); g = df["game_id"].astype(str).to_numpy()
season = df["season"].to_numpy(); live = df["delta_home"].abs().to_numpy() >= 0.08
lm = L.lag_map(); X0 = L.features(df, df[F.STATE]); X1 = L.features(df, L.lagged_state_frame(df, lm))
def fit(idx): return xgb.train(L.PX, xgb.DMatrix(np.vstack([X0[idx], X1[idx]]), np.concatenate([y[idx], y[idx]])), 300)
# out-of-fold predictions on 2025 (for choosing thresholds) under live-like (late) state; plus exact for reference
i25, i26 = np.where(season == 2025)[0], np.where(season == 2026)[0]
P25 = np.zeros((len(y), 6))
for tr, te in GroupKFold(5).split(i25, y[i25], g[i25]):
    b = fit(i25[tr]); P25[i25[te]] = b.predict(xgb.DMatrix(X1[i25[te]]))
b = fit(i25); P26_late = b.predict(xgb.DMatrix(X1[i26])); P26_exact = b.predict(xgb.DMatrix(X0[i26]))
TARGET = 0.90; gate = {}
for k, c in enumerate(F.CLASSES):
    if c == "OTHER": continue
    m = live[i25] & (P25[i25].argmax(1) == k)
    conf, ok = P25[i25][m, k], (y[i25][m] == k)
    best = None
    for t in np.arange(0.50, 0.99, 0.01):
        sel = conf >= t
        if sel.sum() >= 15 and ok[sel].mean() >= TARGET + 0.01:   # 1-pt safety margin
            best = round(float(t), 2); break
    gate[c] = best   # None = never name this play type
print("thresholds (chosen on 2025, live-like state):", gate)
def evaluate(P, idx, name):
    pred, conf = P.argmax(1), P.max(1); yy = y[idx]; lv = live[idx]
    named = np.array([lv[i] and F.CLASSES[pred[i]] != "OTHER" and gate.get(F.CLASSES[pred[i]]) is not None and conf[i] >= gate[F.CLASSES[pred[i]]] for i in range(len(idx))])
    right = (pred[named] == yy[named]); n = int(named.sum())
    # game-clustered bootstrap CI
    gg = g[idx][named]; games = np.unique(gg); rng = np.random.default_rng(1); bs = []
    for _ in range(500):
        s = np.concatenate([np.where(gg == x)[0] for x in rng.choice(games, len(games))]) if len(games) else np.array([], int)
        if len(s): bs.append(right[s].mean())
    by = {F.CLASSES[k]: f"{int((pred[named]==k).sum())} calls, {np.mean(yy[named][pred[named]==k]==k):.0%}" for k in range(5) if (pred[named]==k).any()}
    print(f"{name}: named {n} of {int(lv.sum())} live-size jumps ({n/lv.sum():.0%} coverage) | right {right.mean():.1%} (95% CI {np.percentile(bs,2.5):.0%}-{np.percentile(bs,97.5):.0%}) | {by}")
    return {"named": n, "coverage": round(n / lv.sum(), 3), "precision": round(float(right.mean()), 3), "ci95": [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)], "by_type": by}
res = {"target": TARGET, "gate": gate, "test_2026_late": evaluate(P26_late, i26, "TEST 2026, one-play-late state (live conditions)"),
       "test_2026_exact": evaluate(P26_exact, i26, "TEST 2026, exact state")}
(ROOT / "engine/model/precision_gate.json").write_text(json.dumps(res, indent=1)); print("saved engine/model/precision_gate.json")

"""Pre-registered untouched test (research/PREREG.md): the FROZEN production model on today's finished games.
Refuses to run if the model hashes don't match PREREG. Reports exactly the pre-registered metrics, once."""
import hashlib, json, re, sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "train"))
import finetune_real as F  # noqa: E402  (same detector + feature builders as training)

prereg = (ROOT / "research/PREREG.md").read_text()
want = re.findall(r"sha256 `([0-9a-f]{64})`", prereg)
have = [hashlib.sha256((ROOT / f"engine/model/{f}").read_bytes()).hexdigest() for f in ("playinfer_xgb.json", "stage2_xgb.json")]
assert set(have) == set(want), f"model files changed since PREREG: {have} vs {want}"

src = ROOT / "pipeline/out/real_windows_today.parquet"
df = pd.read_parquet(src)
train_games = set(map(str, json.loads((ROOT / "pipeline/out/train_games.json").read_text())))
df = df[~df["game_id"].astype(str).isin(train_games)]
rows = F.build_rows(df, F.FIRE_TRAIN)
rows = rows[rows["category"].isin(F.CLASSES)].reset_index(drop=True)
y = rows["category"].map({c: i for i, c in enumerate(F.CLASSES)}).to_numpy()
g = rows["game_id"].astype(str).to_numpy()
live = rows["delta_home"].abs().to_numpy() >= 0.08
_, Z, _ = F.sim_logprobs(rows)
meta = json.loads((ROOT / "engine/model/stage2_meta.json").read_text())
feat = pd.concat([pd.DataFrame(Z, columns=[f"sim_{c}" for c in F.CLASSES]), rows[F.STATE].reset_index(drop=True)], axis=1)
b = xgb.Booster(); b.load_model(str(ROOT / "engine/model/stage2_xgb.json"))
P = b.predict(xgb.DMatrix(feat[meta["features"]].to_numpy(float)))


def report(mask, name):
    yy, PP, gg = y[mask], P[mask], g[mask]
    pred, conf = PP.argmax(1), PP.max(1)
    named = (pred != 5) & (conf >= 0.75)
    acc, base = (pred == yy).mean(), (yy == 5).mean()
    games = np.unique(gg); idx = {k: np.where(gg == k)[0] for k in games}; rng = np.random.default_rng(7); L = []
    for _ in range(1000):
        s = np.concatenate([idx[k] for k in rng.choice(games, len(games))])
        L.append((pred[s] == yy[s]).mean() - (yy[s] == 5).mean())
    r = {"set": name, "n_fires": int(mask.sum()), "games": int(len(games)), "accuracy": round(float(acc), 3),
         "always_other": round(float(base), 3), "lift": round(float(acc - base), 3),
         "lift_ci95": [round(float(np.percentile(L, 2.5)), 3), round(float(np.percentile(L, 97.5)), 3)],
         "named_calls": int(named.sum()),
         "named_precision": round(float((pred[named] == yy[named]).mean()), 3) if named.any() else None}
    print(r)
    return r


out = {"prereg_hashes_ok": True, "games": sorted(set(g)),
       "live_regime": report(live, "PRIMARY: live regime |Δ|>=0.08"),
       "all_fires": report(np.ones(len(y), bool), "secondary: all fires |Δ|>=0.05")}
(ROOT / "results/today_test.json").write_text(json.dumps(out, indent=1))
print("written results/today_test.json")

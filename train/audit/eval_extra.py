"""Extras: (1) where label changes come from, (2) paired game-clustered CI for OLD-trained vs NEW-trained production model
scored on the same truth, (3) STOP-class behaviour of the 7-class model. Live regime, GroupKFold(5) by game."""
import sys
from pathlib import Path
import numpy as np, pandas as pd, xgboost as xgb
from sklearn.model_selection import GroupKFold
sys.path.insert(0, str(Path(__file__).parent))
import relabel as rl
ROOT = Path(__file__).resolve().parents[2]
d = np.load(ROOT / "train/out/stage2_matrix.npz", allow_pickle=True)
X, g, live = d["X"], d["g"].astype(str), d["live"].astype(bool)
R = pd.read_parquet(ROOT / "pipeline/out/fires_relabeled.parquet")
P = rl.fixed_plays().drop_duplicates("play_id").set_index("play_id")
ch = R.category_old != R.category_new
np_ = R.new_play_id.map(P.downs).fillna(False).astype(bool)
print("label changes: %d of %d (%.1f%%); live %d of %d" % (ch.sum(), len(R), 100 * ch.mean(), (ch & live).sum(), live.sum()))
print("  -> TURNOVER via turnover-on-downs fix (F1): %d" % (ch & np_ & (R.category_new == "TURNOVER")).sum())
print("  -> re-anchored to a different play (F3): %d ; of which OTHER->named %d, named->OTHER %d, named->other named %d" % (
    (ch & R.anchor_changed).sum(), (ch & (R.category_old == "OTHER")).sum(), (ch & (R.category_new == "OTHER")).sum(),
    (ch & (R.category_old != "OTHER") & (R.category_new != "OTHER")).sum()))
print("  named->OTHER because the anchor play's beneficiary contradicts the move direction:",
      int((ch & (R.category_new == "OTHER") & ~R.anchor_changed).sum()), "(same play, direction/No-Play fix)")
print("  carry-in walk-back used:", int(R.carry_in.sum()), "| no ESPN play within [-30s,+40s] of jump:", int(R.no_play_nearby.sum()))
print("  live fires that are duplicates of the same physical jump:", int((live & ~R.rep).sum()), "of", int(live.sum()))

CL6 = ["TD", "FG", "TURNOVER", "SAFETY", "BIG_PLAY", "OTHER"]; CL7 = CL6 + ["STOP"]
ci = {c: i for i, c in enumerate(d["cols"])}
F = X[:, [ci[c] for c in d["cols"] if c.startswith("sim_")] + [ci[c] for c in ["qtr", "game_seconds_remaining", "score_diff_home", "posteam_is_home", "down", "ydstogo", "yardline_100"]]]
yo, yn = d["y"], R.category_new.map({c: i for i, c in enumerate(CL6)}).to_numpy()
y7 = R.category7.map({c: i for i, c in enumerate(CL7)}).to_numpy()
def oof(y, K):
    out = np.zeros((len(y), K))
    xp = dict(objective="multi:softprob", num_class=K, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
              min_child_weight=3, reg_lambda=3.0, tree_method="hist", seed=0)
    for tr, te in GroupKFold(5).split(F, groups=g):
        out[te] = xgb.train(xp, xgb.DMatrix(F[tr], y[tr]), 300).predict(xgb.DMatrix(F[te]))
    return out
Po, Pn, P7 = oof(yo, 6), oof(yn, 6), oof(y7, 7)
m = live; games = np.unique(g[m]); idx = {k: np.where(g[m] == k)[0] for k in games}; rng = np.random.default_rng(7)
for truth_name, yt in [("NEW labels", yn), ("OLD labels", yo)]:
    a, b = (Po.argmax(1) == yt)[m], (Pn.argmax(1) == yt)[m]
    diffs = [b[s].mean() - a[s].mean() for s in (np.concatenate([idx[k] for k in rng.choice(games, len(games))]) for _ in range(1000))]
    print(f"truth={truth_name}: acc OLD-trained {a.mean():.3f} NEW-trained {b.mean():.3f} diff {b.mean()-a.mean():+.3f} "
          f"CI [{np.percentile(diffs,2.5):+.3f}, {np.percentile(diffs,97.5):+.3f}]")
# named-call precision for each model judged against NEW labels, by named class
for nm, PP in [("OLD-trained", Po), ("NEW-trained", Pn)]:
    pr, cf = PP.argmax(1), PP.max(1); nmask = m & (pr != 5) & (cf >= .75)
    print(nm, "named calls (live, >=.75):", int(nmask.sum()), "by class", {CL6[k]: int(((pr == k) & nmask).sum()) for k in range(5)},
          "precision vs NEW %.3f" % (pr[nmask] == yn[nmask]).mean())
pr7, cf7 = P7.argmax(1), P7.max(1)
st = m & (y7 == 6)
print("7-class STOP: live n=%d ; argmax STOP %d (precision %.2f, recall %.2f); STOP calls at >=0.75: %d" % (
    st.sum(), (m & (pr7 == 6)).sum(), ((pr7 == 6) & st).sum() / max(1, (m & (pr7 == 6)).sum()), ((pr7 == 6) & st).sum() / max(1, st.sum()),
    (m & (pr7 == 6) & (cf7 >= .75)).sum()))
print("  mean predicted P(STOP) on true STOP rows %.2f vs others %.2f" % (P7[st, 6].mean(), P7[m & ~st, 6].mean()))

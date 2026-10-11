"""Same-row comparison on the frozen stage-2 matrix (REVIEW.md M2): every model and baseline scored on the
identical detector fires, GroupKFold(5) by game + the 2025->2026 temporal split, with game-clustered bootstrap CIs.
Named-call precision = when the model names a play (not OTHER) at >= 75% confidence, how often it's right."""
import json, sys
import numpy as np
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

d = np.load("train/out/stage2_matrix.npz", allow_pickle=True)
X, y, g, live, season = d["X"], d["y"], d["g"].astype(str), d["live"].astype(bool), d["season"]
cols = list(d["cols"]); K = 6; OTHER = 5
ci = {c: i for i, c in enumerate(cols)}
sim = [ci[c] for c in cols if c.startswith("sim_")]
state = [ci[c] for c in ["qtr", "game_seconds_remaining", "score_diff_home", "posteam_is_home", "down", "ydstogo", "yardline_100"]]
micro = [ci[c] for c in cols if c.startswith("micro_")]
# smart fan: sees the jump (size, direction relative to the offense) + game state, nothing learned from 28 seasons
d20 = X[:, ci["micro_d20"]]; pih = X[:, ci["posteam_is_home"]]
fan = np.column_stack([X[:, state], d20, np.abs(d20), np.where(pih == 1, d20, -d20)])
XP = {"xgb": dict(objective="multi:softprob", num_class=K, max_depth=3, learning_rate=0.05, subsample=0.8,
                  colsample_bytree=0.8, min_child_weight=3, reg_lambda=3.0, tree_method="hist")}


def full(cl, P, n):
    o = np.full((n, K), 1e-6); o[:, cl] = P; return o / o.sum(1, keepdims=True)


def model(kind, F):
    def fp(tr, te):
        if kind == "xgb":
            return xgb.train(XP["xgb"], xgb.DMatrix(F[tr], y[tr]), 300).predict(xgb.DMatrix(F[te]))
        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000)).fit(F[tr], y[tr])
        return full(m.classes_, m.predict_proba(F[te]), len(te))
    return fp


CANDS = {
    "always_other": None,
    "smart_fan_logistic (state + jump)": ("lr", fan),
    "xgb_no_pretraining (state + shape)": ("xgb", X[:, state + micro]),
    "stage1_plus_state (no price shape)": ("xgb", X[:, sim + state]),
    "PRODUCTION stage2 (stage1 + state + shape)": ("xgb", X),
}


def evaluate(split):
    out = {}
    for name, spec in CANDS.items():
        if spec is None:
            P = np.zeros((len(y), K)); P[:, OTHER] = 1
        else:
            P = np.zeros((len(y), K))
            for tr, te in split:
                P[te] = model(*spec)(tr, te)
        out[name] = P
    return out


def stats(P, mask):
    yy, PP, gg = y[mask], P[mask], g[mask]
    pred, conf = PP.argmax(1), PP.max(1)
    named = (pred != OTHER) & (conf >= 0.75)
    acc = (pred == yy).mean()
    base = (yy == OTHER).mean()
    # game-clustered bootstrap of the lift over always-OTHER
    games = np.unique(gg); rng = np.random.default_rng(7); lifts = []
    idx = {k: np.where(gg == k)[0] for k in games}
    for _ in range(400):
        s = np.concatenate([idx[k] for k in rng.choice(games, len(games))])
        lifts.append((pred[s] == yy[s]).mean() - (yy[s] == OTHER).mean())
    return {"acc": round(float(acc), 3), "always_other": round(float(base), 3), "lift": round(float(acc - base), 3),
            "lift_ci95": [round(float(np.percentile(lifts, 2.5)), 3), round(float(np.percentile(lifts, 97.5)), 3)],
            "named_precision": round(float((pred[named] == yy[named]).mean()), 3) if named.any() else None,
            "named_calls": int(named.sum()), "n": int(mask.sum()), "games": int(len(games))}


res = {}
cv = list(GroupKFold(5).split(X, y, g))
P_cv = evaluate(cv)
res["cv_by_game"] = {k: {"all": stats(P, np.ones(len(y), bool)), "live": stats(P, live)} for k, P in P_cv.items()}
tr, te = np.where(season == 2025)[0], np.where(season == 2026)[0]
P_t = evaluate([(tr, te)])
m26 = np.zeros(len(y), bool); m26[te] = True
res["temporal_2025_to_2026"] = {k: {"all": stats(P, m26), "live": stats(P, m26 & live)} for k, P in P_t.items()}
json.dump(res, open("train/out/same_rows.json", "w"), indent=1)
for split in res:
    print(f"\n== {split} (live regime, jumps >= 0.08)")
    for k, v in res[split].items():
        L = v["live"]
        print(f"  {k:44s} acc={L['acc']:.3f} (always-OTHER {L['always_other']:.3f}, lift {L['lift']:+.3f} CI {L['lift_ci95']}) "
              f"named-call precision={L['named_precision']} on {L['named_calls']} calls | n={L['n']} games={L['games']}")

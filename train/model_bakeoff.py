"""Model bake-off on the identical stage-2 matrix (real Kalshi detector fires), GroupKFold(5) by game.
Candidates: XGBoost (current), LightGBM, CatBoost, TabPFN v2 (GPU), and a probability-average ensemble."""
import sys, json
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score, log_loss

d = np.load(sys.argv[1] if len(sys.argv) > 1 else "train/out/stage2_matrix.npz", allow_pickle=True)
X, y, g, live = d["X"], d["y"], d["g"], d["live"]
K = 6
which = sys.argv[2].split(",") if len(sys.argv) > 2 else ["xgb", "lgbm", "cat"]


def full(classes, P, n):
    out = np.full((n, K), 1e-6); out[:, classes] = P; return out / out.sum(1, keepdims=True)


def fit_predict(name, Xtr, ytr, Xte):
    if name == "xgb":
        import xgboost as xgb
        p = {"objective": "multi:softprob", "num_class": K, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8,
             "colsample_bytree": 0.8, "min_child_weight": 3, "lambda": 3.0, "tree_method": "hist"}
        return xgb.train(p, xgb.DMatrix(Xtr, ytr), 300).predict(xgb.DMatrix(Xte))
    if name == "lgbm":
        import lightgbm as lgb
        m = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=15,
                               subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=3.0, verbose=-1)
        m.fit(Xtr, ytr); return full(m.classes_, m.predict_proba(Xte), len(Xte))
    if name == "cat":
        from catboost import CatBoostClassifier
        m = CatBoostClassifier(iterations=800, learning_rate=0.05, depth=5, l2_leaf_reg=5, loss_function="MultiClass",
                               verbose=False, random_seed=7)
        m.fit(Xtr, ytr); return full(np.array(m.classes_).astype(int), m.predict_proba(Xte), len(Xte))
    if name == "tabpfn":
        from tabpfn import TabPFNClassifier
        m = TabPFNClassifier(device="cuda", n_estimators=8, random_state=7)
        m.fit(Xtr, ytr); return full(m.classes_.astype(int), m.predict_proba(Xte), len(Xte))


res, P_all = {}, {}
for name in which:
    P = np.zeros((len(y), K))
    for tr, te in GroupKFold(n_splits=5).split(X, y, g):
        P[te] = fit_predict(name, X[tr], y[tr], X[te])
    P_all[name] = P
if len(P_all) > 1:
    P_all["ensemble"] = np.mean(list(P_all.values()), axis=0)
for name, P in P_all.items():
    Pc = np.clip(P, 1e-6, 1); Pc /= Pc.sum(1, keepdims=True)
    conf = Pc.max(1); ok = Pc.argmax(1) == y; m = live & (conf >= 0.75)
    res[name] = {"acc": accuracy_score(y, Pc.argmax(1)), "ll": log_loss(y, Pc, labels=list(range(K))),
                 "live_acc": float(ok[live].mean()), "live_ll": log_loss(y[live], Pc[live], labels=list(range(K))),
                 "live_conf75_acc": float(ok[m].mean()), "live_conf75_n": int(m.sum())}
    r = res[name]
    print(f"{name:9s} acc={r['acc']:.3f} ll={r['ll']:.3f} | live acc={r['live_acc']:.3f} ll={r['live_ll']:.3f} | live conf>=.75: {r['live_conf75_acc']:.3f} (n={r['live_conf75_n']})")
try:  # every training/eval run goes to W&B (offline if no key; sync with `wandb sync`)
    import wandb, os
    run = wandb.init(project="kalshi-knows", group="bakeoff", job_type="eval", name="bakeoff-" + "-".join(which),
                     mode=os.environ.get("WANDB_MODE", "online"),
                     config={"rows": int(len(y)), "cv": "GroupKFold(5) by game", "models": which})
    t = wandb.Table(columns=["model", "acc", "log_loss", "live_acc", "live_log_loss", "live_conf75_acc", "live_conf75_n"],
                    data=[[k, v["acc"], v["ll"], v["live_acc"], v["live_ll"], v["live_conf75_acc"], v["live_conf75_n"]] for k, v in res.items()])
    run.log({"bakeoff": t, "bakeoff_live_acc": wandb.plot.bar(t, "model", "live_acc", title="Live-regime accuracy by model")})
    run.finish()
except Exception as e:  # noqa: BLE001
    print("wandb logging skipped:", e)
np.savez(sys.argv[1].replace(".npz", f"_preds_{'_'.join(which)}.npz") if len(sys.argv) > 1 else "train/out/bakeoff_preds.npz", **P_all)
json.dump(res, open((sys.argv[1] if len(sys.argv) > 1 else "train/out/stage2_matrix.npz").replace(".npz", f"_bakeoff_{'_'.join(which)}.json"), "w"), indent=1)

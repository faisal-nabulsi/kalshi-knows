"""Play inverter: given the game state before a play and the observed jump in the home team's
win probability, predict what kind of play just happened (TD / FG / TURNOVER / SAFETY / BIG_PLAY / OTHER).

Trained on nflverse play-by-play (2016-2023), validated on 2024, tested on 2025-2026 (simulated
market jumps), and finally on REAL Kalshi jumps aligned to ESPN plays (pipeline/out/aligned_jumps.parquet).

Run on the GPU box:  ./venv/bin/python train_playinfer.py [--real aligned_jumps.parquet]
"""
import argparse, json, time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
try:
    import wandb  # runs are logged OFFLINE on the GPU box, then synced from the Mac (no API key on the box)
except ImportError:
    wandb = None
WANDB = dict(project="kalshi-knows", mode="offline")
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.preprocessing import StandardScaler

CLASSES = ["TD", "FG", "TURNOVER", "SAFETY", "BIG_PLAY", "OTHER"]
FEATURES = ["qtr", "game_seconds_remaining", "score_diff_home", "posteam_is_home", "down", "ydstogo",
            "yardline_100", "p_home_before", "delta_home", "abs_delta", "delta_pos"]
MIN_DELTA = 0.03
DATA = Path("data")
OUT = Path("out")
rng = np.random.default_rng(7)


def categorize(df: pd.DataFrame) -> pd.Series:
    td = df["touchdown"].fillna(0).eq(1)
    fg = df["field_goal_result"].eq("made")
    to = (df["interception"].fillna(0).eq(1) | df["fumble_lost"].fillna(0).eq(1)
          | df["fourth_down_failed"].fillna(0).eq(1))
    sf = df["safety"].fillna(0).eq(1)
    big = df["yards_gained"].fillna(0).ge(20)
    cat = np.select([td, sf, to, fg, big], ["TD", "SAFETY", "TURNOVER", "FG", "BIG_PLAY"], "OTHER")
    return pd.Series(cat, index=df.index)


def load_nflverse(years) -> pd.DataFrame:
    cols = ["game_id", "season", "home_team", "away_team", "posteam", "qtr", "game_seconds_remaining", "down",
            "ydstogo", "yardline_100", "total_home_score", "total_away_score", "home_wp", "home_wp_post",
            "vegas_home_wp", "vegas_home_wpa", "touchdown", "field_goal_result", "interception", "fumble_lost",
            "fourth_down_failed", "safety", "yards_gained", "play_type", "posteam_score", "defteam_score"]
    frames = []
    for y in years:
        f = DATA / f"pbp_{y}.parquet"
        if not f.exists() or f.stat().st_size == 0:
            continue
        d = pd.read_parquet(f)
        frames.append(d[[c for c in cols if c in d.columns]])
    df = pd.concat(frames, ignore_index=True)
    df = df[df["play_type"].notna() & df["posteam"].notna()]
    # Home win-prob jump the market would see. Vegas-adjusted WP is closest to a market price.
    if "vegas_home_wpa" in df and "vegas_home_wp" in df:
        df["p_home_before"] = df["vegas_home_wp"]
        df["delta_home"] = df["vegas_home_wpa"]
    else:
        df["p_home_before"] = df["home_wp"]
        df["delta_home"] = df["home_wp_post"] - df["home_wp"]
    df = df[df["p_home_before"].notna() & df["delta_home"].notna()]
    df["posteam_is_home"] = (df["posteam"] == df["home_team"]).astype(int)
    pos_minus_def = df["posteam_score"].fillna(0) - df["defteam_score"].fillna(0)
    df["score_diff_home"] = np.where(df["posteam_is_home"] == 1, pos_minus_def, -pos_minus_def)
    df["category"] = categorize(df)
    return df


def make_features(df: pd.DataFrame, augment: bool) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    X["qtr"] = df["qtr"].fillna(1).clip(1, 5)
    X["game_seconds_remaining"] = df["game_seconds_remaining"].fillna(1800)
    X["score_diff_home"] = df["score_diff_home"].fillna(0)
    X["posteam_is_home"] = df["posteam_is_home"].fillna(0)
    X["down"] = df["down"].fillna(0)
    X["ydstogo"] = df["ydstogo"].fillna(10)
    X["yardline_100"] = df["yardline_100"].fillna(75)
    p = df["p_home_before"].astype(float).to_numpy()
    d = df["delta_home"].astype(float).to_numpy()
    if augment:  # make simulated jumps look like noisy market moves
        d = d * rng.uniform(0.8, 1.2, len(d)) + rng.normal(0, 0.015, len(d))
        p = np.clip(p + rng.normal(0, 0.02, len(p)), 0.01, 0.99)
    X["p_home_before"] = p
    X["delta_home"] = d
    X["abs_delta"] = np.abs(d)
    X["delta_pos"] = np.where(X["posteam_is_home"] == 1, d, -d)
    return X[FEATURES]


def metrics(y_true, proba, name):
    pred = proba.argmax(1)
    top2 = np.mean([yt in np.argsort(-pr)[:2] for yt, pr in zip(y_true, proba)])
    return {"model": name, "accuracy": float(accuracy_score(y_true, pred)), "top2": float(top2),
            "log_loss": float(log_loss(y_true, np.clip(proba, 1e-6, 1), labels=list(range(len(CLASSES))))),
            "n": int(len(y_true))}


def rule_of_thumb(X: pd.DataFrame) -> np.ndarray:
    """What a sports fan would guess: offense gained a lot -> TD, a little -> big play; defense gained -> turnover."""
    P = np.full((len(X), len(CLASSES)), 0.02)
    off = X["delta_pos"].to_numpy() > 0
    big = X["abs_delta"].to_numpy() >= 0.10
    for i, (o, b) in enumerate(zip(off, big)):
        P[i, CLASSES.index("TD" if (o and b) else "BIG_PLAY" if o else "TURNOVER")] = 0.9
    return P / P.sum(1, keepdims=True)


def train_mlp(Xtr, ytr, Xva, yva, scaler):
    import torch, torch.nn as nn
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    xt = torch.tensor(scaler.transform(Xtr), dtype=torch.float32, device=dev)
    yt = torch.tensor(ytr, dtype=torch.long, device=dev)
    xv = torch.tensor(scaler.transform(Xva), dtype=torch.float32, device=dev)
    net = nn.Sequential(nn.Linear(xt.shape[1], 256), nn.ReLU(), nn.Linear(256, 256), nn.ReLU(),
                        nn.Linear(256, 128), nn.ReLU(), nn.Linear(128, len(CLASSES))).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
    best, best_state = 1e9, None
    run = wandb.init(**WANDB, group="mlp", job_type="train", name="mlp-256x256x128",
                     config={"layers": [256, 256, 128], "lr": 2e-3, "epochs": 40, "batch": 2048}, reinit=True) if wandb else None
    for epoch in range(40):
        net.train()
        perm = torch.randperm(len(xt), device=dev)
        for i in range(0, len(xt), 2048):
            idx = perm[i:i + 2048]
            loss = nn.functional.cross_entropy(net(xt[idx]), yt[idx])
            opt.zero_grad(); loss.backward(); opt.step()
        net.eval()
        with torch.no_grad():
            pv = torch.softmax(net(xv), 1).cpu().numpy()
        ll = log_loss(yva, np.clip(pv, 1e-6, 1), labels=list(range(len(CLASSES))))
        if run:
            run.log({"epoch": epoch, "val/logloss": ll, "train/last_batch_loss": float(loss)})
        if ll < best:
            best, best_state = ll, {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
    net.load_state_dict(best_state)
    net.eval()
    if run:
        run.summary["best_val_logloss"] = best
        run.finish()

    def predict(X):
        with torch.no_grad():
            return torch.softmax(net(torch.tensor(scaler.transform(X), dtype=torch.float32, device=dev)), 1).cpu().numpy()
    return predict, net, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", default=None, help="aligned_jumps.parquet from the nfl-data pipeline")
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--start", type=int, default=1999)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    t0 = time.time()
    df = load_nflverse(range(args.start, 2027))
    df = df[df["delta_home"].abs() >= MIN_DELTA]
    df["y"] = df["category"].map({c: i for i, c in enumerate(CLASSES)})
    tr, va, te = df[df.season <= 2023], df[df.season == 2024], df[df.season >= 2025]
    print("rows train/val/test", len(tr), len(va), len(te), "label dist", tr.category.value_counts(normalize=True).round(3).to_dict())
    # 3 noisy copies of the training set: data augmentation toward market-like jumps
    Xtr = pd.concat([make_features(tr, True) for _ in range(3)]); ytr = np.tile(tr.y.to_numpy(), 3)
    Xva, yva = make_features(va, True), va.y.to_numpy()
    Xte, yte = make_features(te, True), te.y.to_numpy()

    results = []
    prior = np.bincount(ytr, minlength=len(CLASSES)) / len(ytr)
    results.append(metrics(yte, np.tile(prior, (len(yte), 1)), "majority_prior"))
    results.append(metrics(yte, rule_of_thumb(Xte), "rule_of_thumb"))
    scaler = StandardScaler().fit(Xtr)
    sub = rng.choice(len(Xtr), min(len(Xtr), 200_000), replace=False)  # LR on a subsample: CPU-bound
    lr = LogisticRegression(max_iter=1000).fit(scaler.transform(Xtr.iloc[sub]), ytr[sub])
    results.append(metrics(yte, lr.predict_proba(scaler.transform(Xte)), "logistic_regression"))

    # XGBoost random search on GPU
    best = (1e9, None, None)
    for t in range(args.trials):
        params = {"objective": "multi:softprob", "num_class": len(CLASSES), "device": "cuda", "tree_method": "hist",
                  "max_depth": int(rng.integers(3, 11)), "learning_rate": float(10 ** rng.uniform(-1.5, -0.7)),
                  "subsample": float(rng.uniform(0.6, 1.0)), "colsample_bytree": float(rng.uniform(0.6, 1.0)),
                  "min_child_weight": float(10 ** rng.uniform(0, 1.5)), "lambda": float(10 ** rng.uniform(-1, 1)),
                  "eval_metric": "mlogloss"}
        dtr, dva = xgb.DMatrix(Xtr, ytr), xgb.DMatrix(Xva, yva)
        er = {}
        bst = xgb.train(params, dtr, 2000, evals=[(dva, "val")], early_stopping_rounds=50, verbose_eval=False,
                        evals_result=er)
        ll = bst.best_score
        if wandb:
            run = wandb.init(**WANDB, group="xgb-sweep", job_type="sweep", name=f"xgb-trial-{t:02d}",
                             config={**params, "train_rows": len(Xtr), "seasons": f"{args.start}-2023"}, reinit=True)
            for i, v in enumerate(er["val"]["mlogloss"]):
                run.log({"val/mlogloss": v, "boosting_round": i})
            run.summary.update({"best_val_mlogloss": ll, "best_iteration": bst.best_iteration})
            run.finish()
        print(f"trial {t} depth={params['max_depth']} lr={params['learning_rate']:.3f} val_logloss={ll:.4f} iters={bst.best_iteration}")
        if ll < best[0]:
            best = (ll, params, bst)
    bst = best[2]
    pte_xgb = bst.predict(xgb.DMatrix(Xte), iteration_range=(0, bst.best_iteration + 1))
    results.append(metrics(yte, pte_xgb, "xgboost_gpu"))

    mlp_predict, net, mlp_val = train_mlp(Xtr, ytr, Xva, yva, scaler)
    results.append(metrics(yte, mlp_predict(Xte), "mlp_gpu"))
    print(json.dumps(results, indent=1))

    winner = "xgboost_gpu" if best[0] <= mlp_val else "mlp_gpu"
    if wandb:
        run = wandb.init(**WANDB, group="comparison", job_type="eval", name="sim-test-2025-26", reinit=True,
                         config={"test_seasons": "2025-2026", "train_rows": int(len(tr)), "min_delta": MIN_DELTA})
        tbl = wandb.Table(columns=["model", "accuracy", "top2", "log_loss", "n"],
                          data=[[r["model"], r["accuracy"], r["top2"], r["log_loss"], r["n"]] for r in results])
        run.log({"sim_test": tbl,
                 "sim_test_accuracy": wandb.plot.bar(tbl, "model", "accuracy", title="Held-out 2025-26 seasons: accuracy"),
                 "label_distribution": wandb.Table(columns=["category", "share"],
                                                   data=[[k, float(v)] for k, v in tr.category.value_counts(normalize=True).items()])})
        pred = pte_xgb.argmax(1)
        run.log({"confusion_xgb": wandb.plot.confusion_matrix(y_true=yte.tolist(), preds=pred.tolist(), class_names=CLASSES)})
        run.finish()
    out = {"classes": CLASSES, "features": FEATURES, "min_delta": MIN_DELTA, "winner": winner,
           "xgb_params": best[1], "xgb_val_logloss": best[0], "mlp_val_logloss": mlp_val,
           "sim_test": results, "train_rows": int(len(tr)), "seconds": time.time() - t0}

    bst.save_model(OUT / "playinfer_xgb.json")
    json.dump({"classes": CLASSES, "features": FEATURES, "best_iteration": int(bst.best_iteration)}, open(OUT / "spec.json", "w"))
    # MLP weights as plain JSON so the Mac can run it with numpy only
    sd = {k: v.cpu().numpy().tolist() for k, v in net.state_dict().items()}
    json.dump({"state_dict": sd, "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()}, open(OUT / "playinfer_mlp.json", "w"))

    if False and args.real and Path(args.real).exists():  # real-Kalshi stage now lives in eval_real.py (Mac)
        real = pd.read_parquet(args.real)
        real = real[real["delta_home"].abs() >= 0.05].copy()
        if "is_quiet" in real:
            real = real[~real["is_quiet"].fillna(False).astype(bool)]
        if "score_diff_home" not in real:
            real["score_diff_home"] = real["home_score_pre"] - real["away_score_pre"]
        real = real[real["category"].isin(CLASSES)]
        if len(real):
            yr = real["category"].map({c: i for i, c in enumerate(CLASSES)}).to_numpy()
            Xr = make_features(real, False)
            pr_xgb = bst.predict(xgb.DMatrix(Xr), iteration_range=(0, bst.best_iteration + 1))
            out["real_kalshi_test"] = [
                metrics(yr, np.tile(prior, (len(yr), 1)), "majority_prior"),
                metrics(yr, rule_of_thumb(Xr), "rule_of_thumb"),
                metrics(yr, lr.predict_proba(scaler.transform(Xr)), "logistic_regression"),
                metrics(yr, pr_xgb, "xgboost_gpu"),
                metrics(yr, mlp_predict(Xr), "mlp_gpu"),
            ]
            # Stage 2: calibrate on REAL Kalshi jumps (multinomial logistic on log-probs), cross-validated by game
            if len(real) >= 60 and "game_id" in real:
                from sklearn.model_selection import GroupKFold
                Z = np.log(np.clip(pr_xgb, 1e-6, 1))
                cv = np.zeros_like(pr_xgb)
                for tr_i, te_i in GroupKFold(n_splits=5).split(Z, yr, real["game_id"]):
                    cal = LogisticRegression(max_iter=2000, C=1.0).fit(Z[tr_i], yr[tr_i])
                    full = np.full((len(te_i), len(CLASSES)), 1e-6)
                    full[:, cal.classes_] = cal.predict_proba(Z[te_i])
                    cv[te_i] = full / full.sum(1, keepdims=True)
                out["real_kalshi_test"].append(metrics(yr, cv, "xgboost_calibrated_on_kalshi"))
                cal = LogisticRegression(max_iter=2000, C=1.0).fit(Z, yr)
                coef = np.zeros((len(CLASSES), len(CLASSES))); icpt = np.full(len(CLASSES), -20.0)
                coef[cal.classes_] = cal.coef_; icpt[cal.classes_] = cal.intercept_
                json.dump({"coef": coef.tolist(), "intercept": icpt.tolist(), "n": int(len(real))}, open(OUT / "calib.json", "w"))
            out["real_label_dist"] = real["category"].value_counts().to_dict()
            print("REAL KALSHI:", json.dumps(out["real_kalshi_test"], indent=1))
    board = sorted(out.get("real_kalshi_test", results), key=lambda r: -r["log_loss"])  # worst first
    names = ["Dugar", "House Cat", "Gazelle", "Everyone Else", "Lion", "Kevin & Faisal"]
    offset = len(names) - len(board)
    out["model_leaderboard"] = [{**r, "tier": i + 1 + max(offset, 0), "tier_name": names[min(i + max(offset, 0), 5)]}
                                for i, r in enumerate(board)][::-1]
    json.dump(out, open(OUT / "metrics.json", "w"), indent=1)
    print("done in", round(time.time() - t0), "s; winner", winner)


if __name__ == "__main__":
    main()

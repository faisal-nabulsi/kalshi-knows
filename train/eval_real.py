"""Stage 2 (runs on the Mac): test the GPU-trained play inverter on REAL Kalshi jumps aligned to ESPN plays,
fit the real-market calibration layer (cross-validated by game), and write the model leaderboard.

Inputs:  train/out/{playinfer_xgb.json,spec.json,playinfer_mlp.json}, pipeline/out/aligned_jumps.parquet
Outputs: train/out/metrics.json, engine/model/{playinfer_xgb.json,spec.json,calib.json}
"""
import json, shutil, sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "train/out"
spec = json.loads((OUT / "spec.json").read_text())
CLASSES, FEATURES = spec["classes"], spec["features"]
K = len(CLASSES)
# Training label distribution (nflverse 1999-2023, |delta| >= 0.03), printed by the GPU run
PRIOR = {"OTHER": 0.712, "BIG_PLAY": 0.104, "TD": 0.084, "TURNOVER": 0.07, "FG": 0.029, "SAFETY": 0.001}
SIM_TEST = [  # held-out 2025-26 seasons, simulated market jumps (from train/out/train_v2.log)
    {"model": "majority_prior", "accuracy": 0.7072, "top2": 0.8123, "log_loss": 0.9927},
    {"model": "rule_of_thumb", "accuracy": 0.1699, "top2": 0.2368, "log_loss": 3.2652},
    {"model": "logistic_regression", "accuracy": 0.7493, "top2": 0.9546, "log_loss": 0.6551},
    {"model": "xgboost_gpu", "accuracy": 0.8591, "top2": 0.9862, "log_loss": 0.3388},
    {"model": "mlp_gpu", "accuracy": 0.8506, "top2": 0.9850, "log_loss": 0.3609},
]


def metrics(y, P, name):
    P = np.clip(P, 1e-6, 1); P = P / P.sum(1, keepdims=True)
    top2 = np.mean([yt in np.argsort(-p)[:2] for yt, p in zip(y, P)])
    return {"model": name, "accuracy": float(accuracy_score(y, P.argmax(1))), "top2": float(top2),
            "log_loss": float(log_loss(y, P, labels=list(range(K)))), "n": int(len(y))}


def espn_start_states():
    """True pre-play state for every play from the cached raw ESPN summaries (start.down/distance/yardsToEndzone/team)."""
    rows = []
    for f in (ROOT / "pipeline/out/espn").glob("*.json"):
        d = json.loads(f.read_text())
        if not isinstance(d, dict):
            continue
        try:
            abbr = {c["team"]["id"]: c["team"]["abbreviation"] for c in d["header"]["competitions"][0]["competitors"]}
        except (KeyError, IndexError):
            continue
        for dr in d.get("drives", {}).get("previous", []):
            for p in dr.get("plays", []):
                st = p.get("start") or {}
                tid = (st.get("team") or {}).get("id")
                rows.append({"play_id": str(p.get("id")), "s_posteam": abbr.get(tid), "s_down": st.get("down"),
                             "s_ydstogo": st.get("distance"), "s_yardline_100": st.get("yardsToEndzone")})
    return pd.DataFrame(rows)


def load_real():
    a = pd.read_parquet(ROOT / "pipeline/out/aligned_jumps.parquet")
    a["play_id"] = a["play_id"].astype(str)
    a = a.merge(espn_start_states(), on="play_id", how="left")
    for c in ["posteam", "down", "ydstogo", "yardline_100"]:
        a[c] = a[c].where(a[c].notna(), a["s_" + c])
    a.loc[a["down"].isin([0, -1]), "down"] = np.nan
    a = a[(a["delta_home"].abs() >= 0.05) & ~a["is_quiet"].fillna(False).astype(bool) & a["category"].isin(CLASSES)]
    a = a.copy()
    # Turnovers/FGs lack possession in the ESPN pull: the offense is the team that LOST the ball (turnover)
    # or the kicking team (FG). Down/distance unknown there -> typical values.
    miss = a["posteam"].isna()
    other = np.where(a["team"] == a["home"], a["away"], a["home"])
    a.loc[miss, "posteam"] = np.where(a.loc[miss, "category"] == "TURNOVER", other[miss.to_numpy()], a.loc[miss, "team"])
    a["posteam_is_home"] = (a["posteam"] == a["home"]).astype(int)
    a.loc[a["down"].isna(), ["down", "ydstogo"]] = [2, 8]
    a["yardline_100"] = a["yardline_100"].fillna(50)
    X = pd.DataFrame({
        "qtr": a["qtr"].clip(1, 5), "game_seconds_remaining": a["game_seconds_remaining"],
        "score_diff_home": a["home_score_pre"] - a["away_score_pre"], "posteam_is_home": a["posteam_is_home"],
        "down": a["down"].fillna(0), "ydstogo": a["ydstogo"].fillna(10), "yardline_100": a["yardline_100"].fillna(75),
        "p_home_before": a["p_home_before"], "delta_home": a["delta_home"],
    })
    X["abs_delta"] = X["delta_home"].abs()
    X["delta_pos"] = np.where(X["posteam_is_home"] == 1, X["delta_home"], -X["delta_home"])
    y = a["category"].map({c: i for i, c in enumerate(CLASSES)}).to_numpy()
    return X[FEATURES].astype(float), y, a["game_id"].to_numpy(), a


def mlp_predict(X):
    w = json.loads((OUT / "playinfer_mlp.json").read_text())
    h = (X.to_numpy() - np.array(w["mean"])) / np.array(w["scale"])
    sd = w["state_dict"]
    layers = sorted({k.split(".")[0] for k in sd}, key=int)
    for i, L in enumerate(layers):
        h = h @ np.array(sd[f"{L}.weight"]).T + np.array(sd[f"{L}.bias"])
        if i < len(layers) - 1:
            h = np.maximum(h, 0)
    h = h - h.max(1, keepdims=True)
    return np.exp(h) / np.exp(h).sum(1, keepdims=True)


def rule_of_thumb(X):
    P = np.full((len(X), K), 0.02)
    for i, (o, b) in enumerate(zip(X["delta_pos"].to_numpy() > 0, X["abs_delta"].to_numpy() >= 0.10)):
        P[i, CLASSES.index("TD" if (o and b) else "BIG_PLAY" if o else "TURNOVER")] = 0.9
    return P


def cv_logreg(Z, y, groups, C=1.0):
    P = np.zeros((len(y), K))
    for tr, te in GroupKFold(n_splits=5).split(Z, y, groups):
        m = LogisticRegression(max_iter=3000, C=C).fit(Z[tr], y[tr])
        full = np.full((len(te), K), 1e-6); full[:, m.classes_] = m.predict_proba(Z[te]); P[te] = full
    return P / P.sum(1, keepdims=True)


def main():
    X, y, groups, a = load_real()
    print("real test rows", len(y), "games", len(set(groups)), pd.Series(y).map(dict(enumerate(CLASSES))).value_counts().to_dict())
    bst = xgb.Booster(); bst.load_model(str(OUT / "playinfer_xgb.json"))
    P_xgb = bst.predict(xgb.DMatrix(X, feature_names=FEATURES), iteration_range=(0, spec["best_iteration"] + 1))
    prior = np.array([PRIOR[c] for c in CLASSES])
    Z = np.log(np.clip(P_xgb, 1e-6, 1))
    P_cal = cv_logreg(Z, y, groups)
    real = [
        metrics(y, np.tile(prior, (len(y), 1)), "majority_prior"),
        metrics(y, rule_of_thumb(X), "rule_of_thumb"),
        metrics(y, cv_logreg(X.to_numpy(), y, groups), "kalshi_only_logistic"),  # trained only on real Kalshi data
        metrics(y, mlp_predict(X), "mlp_gpu"),
        metrics(y, P_xgb, "xgboost_gpu"),
        metrics(y, P_cal, "xgboost_calibrated_on_kalshi"),
    ]
    for r in real:
        print(f"{r['model']:30s} acc={r['accuracy']:.3f} top2={r['top2']:.3f} logloss={r['log_loss']:.3f}")
    cal = LogisticRegression(max_iter=3000, C=1.0).fit(Z, y)
    coef = np.zeros((K, K)); icpt = np.full(K, -20.0)
    coef[cal.classes_] = cal.coef_; icpt[cal.classes_] = cal.intercept_
    names = ["Dugar", "House Cat", "Gazelle", "Everyone Else", "Lion", "Kevin & Faisal"]
    board = sorted(real, key=lambda r: -r["log_loss"])
    leaderboard = [{**r, "tier": i + 1, "tier_name": names[i]} for i, r in enumerate(board)][::-1]
    out = {"classes": CLASSES, "features": FEATURES, "sim_test": SIM_TEST, "real_kalshi_test": real,
           "model_leaderboard": leaderboard, "train_rows": 244434, "train_seasons": "1999-2023",
           "real_label_dist": a["category"].value_counts().to_dict(), "real_games": int(len(set(groups)))}
    (OUT / "metrics.json").write_text(json.dumps(out, indent=1))
    dst = ROOT / "engine/model"; dst.mkdir(exist_ok=True)
    shutil.copy(OUT / "playinfer_xgb.json", dst); shutil.copy(OUT / "spec.json", dst)
    use_calib = real[-1]["log_loss"] < real[-2]["log_loss"]
    if use_calib:
        (dst / "calib.json").write_text(json.dumps({"coef": coef.tolist(), "intercept": icpt.tolist(), "n": int(len(y))}))
    elif (dst / "calib.json").exists():
        (dst / "calib.json").unlink()
    print("deployed to engine/model; calibration", "ON" if use_calib else "OFF")
    if "--wandb" in sys.argv:
        log_wandb(real, leaderboard, y, P_cal, a)


def log_wandb(real, leaderboard, y, P_cal, a):
    import wandb
    lag = json.loads((ROOT / "results/market_lag.json").read_text()) if (ROOT / "results/market_lag.json").exists() else {}
    run = wandb.init(project="kalshi-knows", group="comparison", job_type="eval", name="real-kalshi-test-2026",
                     config={"test": "real Kalshi jumps aligned to ESPN plays, 2026 season", "rows": int(len(y)),
                             "games": int(a["game_id"].nunique()), "cv": "GroupKFold(5) by game", "min_abs_delta": 0.05})
    tbl = wandb.Table(columns=["tier", "predator_scale", "model", "accuracy", "top2", "log_loss", "n"],
                      data=[[r["tier"], r["tier_name"], r["model"], r["accuracy"], r["top2"], r["log_loss"], r["n"]] for r in leaderboard])
    run.log({"predator_scale_leaderboard": tbl,
             "real_accuracy": wandb.plot.bar(tbl, "model", "accuracy", title="Play-type accuracy on REAL Kalshi jumps"),
             "confusion_calibrated": wandb.plot.confusion_matrix(y_true=y.tolist(), preds=P_cal.argmax(1).tolist(), class_names=CLASSES)})
    png = ROOT / "results/market_lag.png"
    if png.exists():
        run.log({"market_lag_vs_stream_delay": wandb.Image(str(png))})
    best = max(real, key=lambda r: r["accuracy"])
    run.summary.update({"best_model": best["model"], "best_accuracy": best["accuracy"], "best_top2": best["top2"],
                        "market_lag_median_s": (lag.get("overall") or lag).get("median_s")})
    run.finish()
    print("logged to W&B:", run.url if hasattr(run, "url") else "")


if __name__ == "__main__":
    main()

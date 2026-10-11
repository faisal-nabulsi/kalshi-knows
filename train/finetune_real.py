"""Stage 3: fine-tune the play inverter on REAL Kalshi price paths.

Training distribution = exactly what the live engine sees: run the same jump detector over every real
price window (2 s grid); wherever it fires, build features from data available AT FIRE TIME only, and
label with the ESPN play (OTHER when the jump wasn't a TD/FG/turnover/safety/big play).

Features
  sim_*    log-probs from the 28-season nflverse model (stage 1), from state + jump
  state    down/distance/field position/clock/score
  micro_*  shape of the move: change over the last 4/10/20/40 s, pre-move volatility, fastest 2 s step,
           trade burst, distance from 0/1
Candidates (all evaluated with GroupKFold(5) by game, so a game is never in train and test at once):
  calib        stage-1 + multinomial calibration (the current production model)
  warmstart    stage-1 booster, boosting continued on real rows (GBDT fine-tuning, same 11 features)
  stack_xgb    small XGBoost on [sim log-probs + state + micro] trained on real rows
  stack_xgb+cl stack_xgb plus contrastive-encoder embeddings (train/contrastive.py), if present
Best by CV log loss is exported to engine/model/stage2*.json.  Logs everything to W&B with --wandb.
"""
import json, sys
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
CLASSES, SIM_FEATURES = spec["classes"], spec["features"]
K = len(CLASSES)
STEP = 2.0            # seconds per grid bin
WINDOW_S = 20.0       # detector window (matches engine/live.py)
HOLD_BINS = 2         # ~3 s persistence
FIRE_TRAIN = 0.05     # train on more jumps than the live 0.08 threshold; report both
CALL_DELAY_BINS = 4   # call the play 8 s after the detector fires (+2.7 pts live accuracy vs 0 s; see W&B)
CROP = 32             # bins (64 s) of price path ending at call time, for the contrastive encoder
MICRO = ["micro_d4", "micro_d10", "micro_d20", "micro_d40", "micro_vol_pre", "micro_max_step",
         "micro_burst", "micro_edge"]
STATE = ["qtr", "game_seconds_remaining", "score_diff_home", "posteam_is_home", "down", "ydstogo", "yardline_100"]


def micro_features(t, p, n, i_fire):
    """Shape of the move using bins <= i_fire only. p = home prob on a 2 s grid."""
    def back(sec):
        j = max(0, i_fire - int(round(sec / STEP)))
        return p[i_fire] - p[j]
    pre = p[max(0, i_fire - 30):max(1, i_fire - 10)]
    steps = np.abs(np.diff(p[max(0, i_fire - 10):i_fire + 1])) if i_fire > 0 else np.array([0.0])
    nn = np.nan_to_num(n)
    burst = nn[max(0, i_fire - 5):i_fire + 1].sum() / (nn[max(0, i_fire - 30):max(1, i_fire - 5)].mean() * 6 + 1)
    return {"micro_d4": back(4), "micro_d10": back(10), "micro_d20": back(20), "micro_d40": back(40),
            "micro_vol_pre": float(np.nanstd(np.diff(pre))) if len(pre) > 2 else 0.0,
            "micro_max_step": float(np.nanmax(steps)) if len(steps) else 0.0,
            "micro_burst": float(burst), "micro_edge": float(min(p[i_fire], 1 - p[i_fire]))}


def detect(t, p, thresh):
    """Same rule as the live engine: |change over trailing 20 s| >= thresh, persisting HOLD_BINS; first fire at t >= -10 s."""
    w = int(WINDOW_S / STEP)
    for i in range(w, len(p) - HOLD_BINS):
        if t[i] < -10 or np.isnan(p[i]) or np.isnan(p[i - w]):
            continue
        d = p[i] - np.nanmin(p[i - w:i + 1]) if p[i] >= p[i - w] else p[i] - np.nanmax(p[i - w:i + 1])
        if abs(d) >= thresh and all(abs(p[i + k] - (p[i] - d)) >= thresh * 0.8 for k in range(1, HOLD_BINS + 1)):
            i_f = min(i + HOLD_BINS + CALL_DELAY_BINS, len(p) - 1)
            return i_f, float(p[i] - d), float(p[i_f])
    return None


def build_rows(df, thresh):
    rows = []
    for r in df.itertuples(index=False):
        t = np.asarray(r.path_t, float); p = pd.Series(np.asarray(r.path_p, float)).ffill().to_numpy()
        n = np.asarray(r.path_n, float) if hasattr(r, "path_n") else np.zeros_like(p)
        if np.isnan(p).all():
            continue
        hit = detect(t, p, thresh)
        if hit is None:
            continue
        i_f, pb, pa = hit
        pih = int(bool(r.posteam_is_home)) if pd.notna(r.posteam_is_home) else int(r.posteam == r.home)
        row = {"game_id": r.game_id, "category": r.category, "fire_t": float(t[i_f]), "p_home_before": pb,
               "p_home_after": pa, "delta_home": pa - pb, "qtr": min(max(r.qtr, 1), 5),
               "game_seconds_remaining": r.game_seconds_remaining,
               "score_diff_home": (r.home_score_pre or 0) - (r.away_score_pre or 0), "posteam_is_home": pih,
               "down": r.down if pd.notna(r.down) else 0, "ydstogo": r.ydstogo if pd.notna(r.ydstogo) else 10,
               "yardline_100": r.yardline_100 if pd.notna(r.yardline_100) else 75}
        row.update(micro_features(t, p, n, i_f))
        lo = i_f - CROP + 1
        seg_p = p[max(lo, 0):i_f + 1]; seg_n = np.nan_to_num(n[max(lo, 0):i_f + 1])
        if lo < 0:
            seg_p = np.concatenate([np.full(-lo, seg_p[0]), seg_p]); seg_n = np.concatenate([np.zeros(-lo), seg_n])
        row["crop"] = np.stack([seg_p - seg_p[0], np.log1p(seg_n)]).astype(np.float32)
        rows.append(row)
    return pd.DataFrame(rows)


def sim_logprobs(df):
    X = pd.DataFrame({f: df[f] for f in ["qtr", "game_seconds_remaining", "score_diff_home", "posteam_is_home",
                                         "down", "ydstogo", "yardline_100", "p_home_before", "delta_home"]})
    X["abs_delta"] = X["delta_home"].abs()
    X["delta_pos"] = np.where(X["posteam_is_home"] == 1, X["delta_home"], -X["delta_home"])
    X = X[SIM_FEATURES].astype(float)
    bst = xgb.Booster(); bst.load_model(str(OUT / "playinfer_xgb.json"))
    P = bst.predict(xgb.DMatrix(X, feature_names=SIM_FEATURES), iteration_range=(0, spec["best_iteration"] + 1))
    return X, np.log(np.clip(P, 1e-6, 1)), bst


def metrics(y, P, name, mask=None):
    if mask is not None:
        y, P = y[mask], P[mask]
    P = np.clip(P, 1e-6, 1); P = P / P.sum(1, keepdims=True)
    return {"model": name, "accuracy": float(accuracy_score(y, P.argmax(1))),
            "top2": float(np.mean([a in np.argsort(-b)[:2] for a, b in zip(y, P)])),
            "log_loss": float(log_loss(y, P, labels=list(range(K)))), "n": int(len(y))}


def full_proba(model_classes, P_part, n):
    out = np.full((n, K), 1e-6); out[:, model_classes] = P_part
    return out / out.sum(1, keepdims=True)


def cv(y, groups, fit_predict):
    P = np.zeros((len(y), K))
    for tr, te in GroupKFold(n_splits=5).split(np.zeros(len(y)), y, groups):
        P[te] = fit_predict(tr, te)
    return P


def main():
    use_wandb = "--wandb" in sys.argv
    src = ROOT / "pipeline/out/real_windows.parquet"
    df = pd.read_parquet(src)
    rows = build_rows(df, FIRE_TRAIN)
    rows = rows[rows["category"].isin(CLASSES)].reset_index(drop=True)
    y = rows["category"].map({c: i for i, c in enumerate(CLASSES)}).to_numpy()
    groups = rows["game_id"].to_numpy()
    live_mask = rows["delta_home"].abs().to_numpy() >= 0.08
    print("windows", len(df), "-> detector fires", len(rows), "| live-threshold subset", int(live_mask.sum()))
    print("labels", rows["category"].value_counts().to_dict())
    np.save(OUT / "crops_labeled.npy", np.stack(rows["crop"].to_list()))

    Xsim, Z, bst = sim_logprobs(rows)
    simcols = [f"sim_{c}" for c in CLASSES]
    F = pd.concat([pd.DataFrame(Z, columns=simcols), rows[STATE + MICRO].reset_index(drop=True)], axis=1).astype(float)
    emb_path = OUT / "contrastive_emb.parquet"
    E = None
    if emb_path.exists():
        emb = pd.read_parquet(emb_path)
        if len(emb) == len(rows):
            E = emb.to_numpy()

    res = {}
    res["stage1_raw"] = np.exp(Z) / np.exp(Z).sum(1, keepdims=True)

    def fp_calib(tr, te):
        m = LogisticRegression(max_iter=3000).fit(Z[tr], y[tr]); return full_proba(m.classes_, m.predict_proba(Z[te]), len(te))
    res["calib"] = cv(y, groups, fp_calib)

    def fp_warm(tr, te):
        params = {"objective": "multi:softprob", "num_class": K, "max_depth": 3, "learning_rate": 0.05,
                  "subsample": 0.8, "lambda": 5.0, "tree_method": "hist"}
        b = xgb.train(params, xgb.DMatrix(Xsim.iloc[tr], y[tr]), 150, xgb_model=bst)
        return b.predict(xgb.DMatrix(Xsim.iloc[te]))
    res["warmstart"] = cv(y, groups, fp_warm)

    xparams = {"objective": "multi:softprob", "num_class": K, "max_depth": 3, "learning_rate": 0.05,
               "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 3, "lambda": 3.0, "tree_method": "hist"}

    def make_stack(Fm):
        def fp(tr, te):
            b = xgb.train(xparams, xgb.DMatrix(Fm[tr], y[tr]), 300)
            return b.predict(xgb.DMatrix(Fm[te]))
        return fp
    res["stack_xgb"] = cv(y, groups, make_stack(F.to_numpy()))
    if E is not None:
        res["stack_xgb+contrastive"] = cv(y, groups, make_stack(np.hstack([F.to_numpy(), E])))

    table = []
    for name, P in res.items():
        table.append({**metrics(y, P, name), "live_subset": metrics(y, P, name, live_mask)})
    # select on the regime the live engine actually runs in (jumps >= 0.08), not the training mix
    table.sort(key=lambda r: r["live_subset"]["log_loss"])
    for r in table:
        ls = r["live_subset"]
        print(f"{r['model']:24s} acc={r['accuracy']:.3f} top2={r['top2']:.3f} ll={r['log_loss']:.3f} | "
              f"live(>=0.08) acc={ls['accuracy']:.3f} ll={ls['log_loss']:.3f} n={ls['n']}")

    best = table[0]["model"]
    dst = ROOT / "engine/model"
    meta = {"best": best, "classes": CLASSES, "state": STATE, "micro": MICRO, "simcols": simcols,
            "fire_train": FIRE_TRAIN, "table": table, "labels": rows["category"].value_counts().to_dict(),
            "n_windows": int(len(df)), "n_fires": int(len(rows))}
    if best == "stack_xgb":
        b = xgb.train(xparams, xgb.DMatrix(F.to_numpy(), y), 300)
        b.save_model(str(dst / "stage2_xgb.json"))
        meta["features"] = list(F.columns)
    (OUT / "finetune_metrics.json").write_text(json.dumps(meta, indent=1, default=float))
    (dst / "stage2_meta.json").write_text(json.dumps(meta, indent=1, default=float))
    print("best:", best, "| exported" if best == "stack_xgb" else "| production model unchanged")

    if use_wandb:
        import wandb
        run = wandb.init(project="kalshi-knows", group="finetune", job_type="eval", name="stage3-finetune-real-paths",
                         config={"fire_train": FIRE_TRAIN, "n_fires": len(rows), "cv": "GroupKFold(5) by game",
                                 "labels": meta["labels"]})
        t = wandb.Table(columns=["model", "accuracy", "top2", "log_loss", "live_acc", "live_log_loss", "n"],
                        data=[[r["model"], r["accuracy"], r["top2"], r["log_loss"], r["live_subset"]["accuracy"],
                               r["live_subset"]["log_loss"], r["n"]] for r in table])
        run.log({"finetune_comparison": t,
                 "finetune_accuracy": wandb.plot.bar(t, "model", "accuracy", title="Real Kalshi detector fires: accuracy (CV by game)"),
                 "confusion_best": wandb.plot.confusion_matrix(y_true=y.tolist(), preds=res[best].argmax(1).tolist(),
                                                               class_names=CLASSES)})
        run.summary.update({"best": best, "best_accuracy": table[0]["accuracy"]})
        run.finish()


if __name__ == "__main__":
    main()

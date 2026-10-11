"""Trained play inverter for the live engine (lead-owned).

infer_play(state, p_before, p_after, team) -> [{"type","team","prob"}, ...] sorted by prob.
Loads engine/model/playinfer_xgb.json + spec.json (trained on the GPU box from nflverse 1999-2026),
and an optional real-Kalshi calibration layer engine/model/calib.json (multinomial logistic on
log-probabilities, fit on real 2026 Kalshi jumps aligned to ESPN plays).
"""
import json
from pathlib import Path

import numpy as np
import xgboost as xgb

_DIR = Path(__file__).parent / "model"
if not (_DIR / "spec.json").exists() or not (_DIR / "playinfer_xgb.json").exists():
    raise ImportError("trained model not deployed yet (engine/model/)")  # live.py falls back to the heuristic
_SPEC = json.loads((_DIR / "spec.json").read_text())
CLASSES = _SPEC["classes"]
FEATURES = _SPEC["features"]
_BST = xgb.Booster()
_BST.load_model(str(_DIR / "playinfer_xgb.json"))
_BEST_ITER = _SPEC.get("best_iteration")
_CALIB = json.loads((_DIR / "calib.json").read_text()) if (_DIR / "calib.json").exists() else None


def _num(x, default):
    try:
        v = float(x)
        return default if np.isnan(v) else v
    except (TypeError, ValueError):
        return default


def features(state: dict, p_before: float, p_after: float) -> np.ndarray:
    posteam_is_home = int(_num(state.get("posteam_is_home"), 0))
    score_diff_pos = _num(state.get("score_differential"), 0)
    d = float(p_after) - float(p_before)
    row = {
        "qtr": min(max(_num(state.get("qtr"), 1), 1), 5),
        "game_seconds_remaining": _num(state.get("game_seconds_remaining"), 1800),
        "score_diff_home": score_diff_pos if posteam_is_home else -score_diff_pos,
        "posteam_is_home": posteam_is_home,
        "down": _num(state.get("down"), 0),
        "ydstogo": _num(state.get("ydstogo"), 10),
        "yardline_100": _num(state.get("yardline_100"), 75),
        "p_home_before": float(p_before),
        "delta_home": d,
        "abs_delta": abs(d),
        "delta_pos": d if posteam_is_home else -d,
    }
    return np.array([[row[f] for f in FEATURES]], dtype=np.float32)


def predict_proba(state: dict, p_before: float, p_after: float) -> np.ndarray:
    X = features(state, p_before, p_after)
    dm = xgb.DMatrix(X, feature_names=FEATURES)
    kw = {"iteration_range": (0, _BEST_ITER + 1)} if _BEST_ITER is not None else {}
    p = _BST.predict(dm, **kw)[0]
    if _CALIB:
        z = np.log(np.clip(p, 1e-6, 1)) @ np.array(_CALIB["coef"]).T + np.array(_CALIB["intercept"])
        z = z - z.max()
        p = np.exp(z) / np.exp(z).sum()
    return p


def infer_play(state: dict, p_before: float, p_after: float, team: str):
    p = predict_proba(state, p_before, p_after)
    out = [{"type": c, "team": team, "prob": round(float(pr), 3)} for c, pr in zip(CLASSES, p)]
    return sorted(out, key=lambda r: -r["prob"])

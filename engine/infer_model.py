"""Trained play inverter for the live engine (lead-owned). See TRAINING.md.

infer_play(state, p_before, p_after, team) -> [{"type","team","prob"}, ...] sorted by prob.
  p_before/p_after: win prob of `team` (the side the move favours), as live.py passes them.
  state: pre-play game state (qtr, game_seconds_remaining, score_differential [posteam view],
         posteam_is_home, down, ydstogo, yardline_100, home, away) and, when available,
         state["path"] = [[ts_ms, p_home], ...] (recent price history) + state["call_ts"].

Stage 1: XGBoost pretrained on 28 seasons of nflverse plays (engine/model/playinfer_xgb.json).
Stage 2: stacked XGBoost fine-tuned on 1,596 real Kalshi detector fires (stage2_xgb.json), using
         stage-1 log-probs + state + the shape of the price move at call time.
Optional: TabPFN v2 on Apple MPS with the stage-2 training set as context, averaged with stage 2
         when it answers within TABPFN_TIMEOUT_S (best model in the bake-off; never delays an alert).
Falls back to stage 1 + calibration if stage 2 files or the price path are missing.
"""
import json, os, threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
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

_S2 = None
if (_DIR / "stage2_xgb.json").exists() and (_DIR / "stage2_meta.json").exists():
    _S2_META = json.loads((_DIR / "stage2_meta.json").read_text())
    if _S2_META.get("best") == "stack_xgb" and _S2_META.get("features"):
        _S2 = xgb.Booster(); _S2.load_model(str(_DIR / "stage2_xgb.json"))
STEP_MS = 2000
BURST_MEDIAN = 1.07           # trade-burst feature: the live engine polls order books, not trades
TABPFN_TIMEOUT_S = float(os.environ.get("TABPFN_TIMEOUT_S", "4"))
LAST = {"source": "stage1"}   # what produced the last prediction (shown in /api/health via infer.source)


def _num(x, default):
    try:
        v = float(x)
        return default if np.isnan(v) else v
    except (TypeError, ValueError):
        return default


def _home_view(state, p_before, p_after, team):
    if state.get("home") and team != state.get("home"):
        return 1 - p_before, 1 - p_after
    return p_before, p_after


def _state_cols(state):
    pih = int(_num(state.get("posteam_is_home"), 0))
    sd = _num(state.get("score_differential"), 0)
    return {"qtr": min(max(_num(state.get("qtr"), 1), 1), 5),
            "game_seconds_remaining": _num(state.get("game_seconds_remaining"), 1800),
            "score_diff_home": sd if pih else -sd, "posteam_is_home": pih,
            "down": _num(state.get("down"), 0), "ydstogo": _num(state.get("ydstogo"), 10),
            "yardline_100": _num(state.get("yardline_100"), 75)}


def stage1_logprobs(state, ph_before, ph_after):
    s = _state_cols(state)
    d = ph_after - ph_before
    row = {**s, "p_home_before": ph_before, "delta_home": d, "abs_delta": abs(d),
           "delta_pos": d if s["posteam_is_home"] else -d}
    X = np.array([[row[f] for f in FEATURES]], dtype=np.float32)
    kw = {"iteration_range": (0, _BEST_ITER + 1)} if _BEST_ITER is not None else {}
    p = _BST.predict(xgb.DMatrix(X, feature_names=FEATURES), **kw)[0]
    return np.log(np.clip(p, 1e-6, 1)), s


def _grid(path, call_ts):
    """Resample [[ts_ms, p_home], ...] onto a 2 s grid ending at call_ts (last value carried forward)."""
    path = sorted((int(t), float(p)) for t, p in path if p is not None)
    ts = [call_ts - STEP_MS * k for k in range(45, -1, -1)]
    out, j, last = [], 0, path[0][1] if path else np.nan
    for t in ts:
        while j < len(path) and path[j][0] <= t:
            last = path[j][1]; j += 1
        out.append(last)
    return np.array(out, float)


def micro(path, call_ts):
    p = _grid(path, call_ts)
    i = len(p) - 1
    back = lambda sec: p[i] - p[max(0, i - int(round(sec / 2)))]
    pre = p[max(0, i - 30):max(1, i - 10)]
    steps = np.abs(np.diff(p[max(0, i - 10):i + 1]))
    return {"micro_d4": back(4), "micro_d10": back(10), "micro_d20": back(20), "micro_d40": back(40),
            "micro_vol_pre": float(np.nanstd(np.diff(pre))) if len(pre) > 2 else 0.0,
            "micro_max_step": float(np.nanmax(steps)) if len(steps) else 0.0,
            "micro_burst": BURST_MEDIAN, "micro_edge": float(min(p[i], 1 - p[i]))}


# ---- optional TabPFN (lazy, background-initialised so engine start-up is never blocked)
_TAB = {"model": None, "err": None}
_POOL = ThreadPoolExecutor(max_workers=1)


def _init_tabpfn():
    try:
        if os.environ.get("TABPFN", "1") == "0" or _S2 is None:
            return
        os.environ.setdefault("TABPFN_ALLOW_CPU_LARGE_DATASET", "1")
        import torch
        from tabpfn import TabPFNClassifier
        ctx = np.load(_DIR / "stage2_ctx.npz", allow_pickle=True)
        dev = "mps" if torch.backends.mps.is_available() else "cpu"
        m = TabPFNClassifier(device=dev, n_estimators=int(os.environ.get("TABPFN_N", "3")), random_state=7,
                             ignore_pretraining_limits=True)
        m.fit(ctx["X"], ctx["y"])
        m.predict_proba(ctx["X"][:1])          # warm-up compile
        _TAB["model"] = m
    except Exception as e:                     # noqa: BLE001 - optional component
        _TAB["err"] = repr(e)


threading.Thread(target=_init_tabpfn, daemon=True).start()


def _tabpfn_proba(F):
    m = _TAB["model"]
    out = np.full(len(CLASSES), 1e-6)
    out[m.classes_.astype(int)] = m.predict_proba(F)[0]
    return out / out.sum()


def predict_proba(state, p_before, p_after, team):
    ph_b, ph_a = _home_view(state, p_before, p_after, team)
    z, s = stage1_logprobs(state, ph_b, ph_a)
    path, call_ts = state.get("path"), state.get("call_ts")
    if _S2 is not None and path and call_ts and len(path) >= 3:
        row = {**{f"sim_{c}": v for c, v in zip(CLASSES, z)}, **s, **micro(path, call_ts)}
        F = np.array([[row.get(c, np.nan) for c in _S2_META["features"]]], dtype=np.float32)  # mm_* absent live -> NaN
        p = _S2.predict(xgb.DMatrix(F))[0]
        source = "stage2"
        if _TAB["model"] is not None:
            try:
                pt = _POOL.submit(_tabpfn_proba, F).result(timeout=TABPFN_TIMEOUT_S)
                p = (p + pt) / 2; source = "stage2+tabpfn"
            except (FutTimeout, Exception):    # noqa: BLE001 - never block an alert on the optional model
                pass
        LAST["source"] = source
        return p
    p = np.exp(z)
    if _CALIB:
        zz = z @ np.array(_CALIB["coef"]).T + np.array(_CALIB["intercept"])
        zz -= zz.max(); p = np.exp(zz)
    LAST["source"] = "stage1+calib" if _CALIB else "stage1"
    return p / p.sum()


def infer_play(state: dict, p_before: float, p_after: float, team: str):
    p = predict_proba(state, p_before, p_after, team)
    out = [{"type": c, "team": team, "prob": round(float(pr), 3)} for c, pr in zip(CLASSES, p)]
    return sorted(out, key=lambda r: -r["prob"])

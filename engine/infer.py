"""Play inference: given the game state just before a market jump, guess the play.

If engine/infer_model.py exists (the trained model, written by the lead) and exposes
`infer_play(state, p_before, p_after, team)`, it is used. Otherwise a heuristic.
Both return a list of {"type","team","prob"} sorted by prob, summing to 1.
"""
from __future__ import annotations

import importlib
import logging
import math
import time

log = logging.getLogger("infer")
TYPES = ["TD", "FG", "TURNOVER", "BIG_PLAY", "SAFETY", "OTHER"]

_model = None
_model_checked = 0.0
_model_source = "heuristic"


def _load_model():
    global _model, _model_checked, _model_source
    if _model is not None or time.time() - _model_checked < 60:
        return _model
    _model_checked = time.time()
    try:
        mod = importlib.import_module("engine.infer_model")
        if hasattr(mod, "infer_play"):
            _model = mod.infer_play
            _model_source = "model"
            log.info("using engine.infer_model.infer_play")
    except Exception as e:  # missing or broken: keep the heuristic
        if not isinstance(e, ModuleNotFoundError):
            log.warning("infer_model import failed: %s", e)
    return _model


def source() -> str:
    _load_model()
    return _model_source


def _num(x, default):
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def heuristic(state: dict, p_before: float, p_after: float, team: str) -> list[dict]:
    """p_before/p_after are the win prob of `team` (so the move is positive)."""
    delta = abs(p_after - p_before)
    posteam = state.get("posteam")
    yl = _num(state.get("yardline_100"), 60)
    down = _num(state.get("down"), 1)
    togo = _num(state.get("ydstogo"), 10)
    qtr = _num(state.get("qtr"), 2)
    secs = _num(state.get("game_seconds_remaining"), 1800)
    # moves get bigger late in close games; normalise the jump by a "leverage" factor
    leverage = 1.0 + 1.6 * max(0.0, (1800 - secs) / 1800) if secs < 1800 else 1.0
    d = delta / leverage
    s = {k: -4.0 for k in TYPES}
    offense_benefits = (posteam is None) or (posteam == team)
    if offense_benefits:
        near = max(0.0, (40 - yl) / 40)          # 1 at the goal line, 0 beyond the 40
        s["TD"] = -1.0 + 3.0 * near + 18 * (d - 0.06) + (0.8 if yl <= 10 else 0)
        fg_zone = 1.0 if yl <= 38 else 0.0
        s["FG"] = -1.5 + 2.2 * fg_zone + (1.8 if down >= 4 else 0) + (0.6 if togo >= 6 and down >= 3 else 0) \
            - 14 * max(0.0, d - 0.10)
        s["BIG_PLAY"] = 0.2 + 1.2 * (1 - near) - 10 * max(0.0, d - 0.12)
        s["TURNOVER"] = -2.5
        s["OTHER"] = -0.8 - 8 * max(0.0, d - 0.08)
        if posteam is None:  # unknown possession: hedge toward turnovers too
            s["TURNOVER"] = -0.5 + 6 * d
    else:
        s["TURNOVER"] = 1.6 + 8 * (d - 0.06) + (0.6 if down >= 3 else 0)
        s["TD"] = -1.2 + 10 * max(0.0, d - 0.12)          # pick-six / return TD
        s["SAFETY"] = -4.0 + (4.5 if yl >= 95 else 0)
        s["OTHER"] = -0.2 + (1.2 if down >= 4 else 0) + (0.8 if yl <= 38 and down >= 4 else 0)  # failed 4th / missed FG
        s["BIG_PLAY"] = -2.5
        s["FG"] = -3.5
    if qtr >= 4 and secs < 300 and offense_benefits and yl <= 38:
        s["FG"] += 0.6
    m = max(s.values())
    ex = {k: math.exp(v - m) for k, v in s.items()}
    z = sum(ex.values())
    out = [{"type": k, "team": team, "prob": round(v / z, 3)} for k, v in ex.items()]
    out.sort(key=lambda r: -r["prob"])
    return out


def infer_play(state: dict, p_before: float, p_after: float, team: str) -> list[dict]:
    model = _load_model()
    if model is not None:
        try:
            res = model(state, p_before, p_after, team)
            if res:
                return sorted(res, key=lambda r: -r.get("prob", 0))
        except Exception as e:
            log.warning("infer_model failed, falling back to heuristic: %s", e)
    return heuristic(state, p_before, p_after, team)


NICK = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills", "CAR": "Panthers",
    "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns", "DAL": "Cowboys", "DEN": "Broncos",
    "DET": "Lions", "GB": "Packers", "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "JAC": "Jaguars",
    "KC": "Chiefs", "LV": "Raiders", "LAC": "Chargers", "LAR": "Rams", "LA": "Rams", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants", "NYJ": "Jets",
    "PHI": "Eagles", "PIT": "Steelers", "SF": "49ers", "SEA": "Seahawks", "TB": "Buccaneers",
    "TEN": "Titans", "WSH": "Commanders", "WAS": "Commanders",
}
PHRASE = {"TD": "touchdown", "FG": "field goal", "TURNOVER": "takeaway", "BIG_PLAY": "big play",
          "SAFETY": "safety", "OTHER": "big moment"}


def headline(inferred: list[dict], team: str) -> str:
    top = inferred[0] if inferred else {"type": "OTHER", "prob": 0.5}
    nick = NICK.get(team, team)
    return f"{nick} {PHRASE.get(top['type'], 'big moment')} ({round(100 * top['prob'])}% sure)"

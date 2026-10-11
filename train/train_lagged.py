"""Fix the train/serve skew: live, ESPN's game state arrives ~one play late, but the model was trained on the
exact pre-play state. Build the state the live engine would actually see (the PREVIOUS scrimmage play's pre-play
state: down, distance, field position, clock, score, possession) for every real Kalshi jump, train on a mix of
exact + one-play-late states, and compare against the current production model under both conditions.
Usage: .venv/bin/python train/train_lagged.py [--deploy]"""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "train"))
import finetune_real as F  # noqa: E402

STATE = F.STATE  # qtr, game_seconds_remaining, score_diff_home, posteam_is_home, down, ydstogo, yardline_100


def clock_secs(period, disp):
    try:
        m, s = str(disp).split(":"); left = int(m) * 60 + int(float(s))
    except Exception:  # noqa: BLE001
        left = 450
    p = int(period or 1)
    return max(0, (4 - min(p, 4)) * 900 + left) if p <= 4 else left


def game_states(path):
    """Ordered pre-play states for every scrimmage play in one cached ESPN summary."""
    d = json.loads(Path(path).read_text())
    if not isinstance(d, dict):
        return None
    try:
        comps = d["header"]["competitions"][0]["competitors"]
        abbr = {c["team"]["id"]: c["team"]["abbreviation"] for c in comps}
        home = next(c["team"]["abbreviation"] for c in comps if c["homeAway"] == "home")
    except (KeyError, IndexError, StopIteration):
        return None
    plays = [p for dr in d.get("drives", {}).get("previous", []) for p in dr.get("plays", [])]
    out, hs, as_, last_clock, last_period = [], 0, 0, "15:00", 1
    for p in plays:
        st = p.get("start") or {}
        pos = abbr.get(str((st.get("team") or {}).get("id")))
        per = (p.get("period") or {}).get("number") or last_period
        rec = {"play_id": str(p.get("id")), "posteam": pos, "down": st.get("down"), "ydstogo": st.get("distance"),
               "yardline_100": st.get("yardsToEndzone"), "qtr": per,
               "game_seconds_remaining": clock_secs(last_period, last_clock),   # clock at the end of the previous play
               "home_pre": hs, "away_pre": as_, "home": home, "scrim": bool(st.get("down")) and (st.get("down") or 0) > 0}
        out.append(rec)
        hs, as_ = p.get("homeScore", hs) or hs, p.get("awayScore", as_) or as_
        last_clock = (p.get("clock") or {}).get("displayValue") or last_clock
        last_period = per
    return out


def lag_map():
    """play_id -> pre-play state of the previous SCRIMMAGE play (what ESPN's scoreboard still shows live)."""
    m = {}
    for folder in ("pipeline/out/espn", "pipeline/out/espn2025"):
        for f in (ROOT / folder).glob("*.json"):
            states = game_states(f)
            if not states:
                continue
            prev = None
            for s in states:
                if prev is not None:
                    m[s["play_id"]] = prev
                if s["scrim"]:
                    prev = s
    return m


def lagged_state_frame(df, lm):
    rows, hit = [], 0
    for r in df.itertuples(index=False):
        pid = str(r.new_play_id if isinstance(r.new_play_id, str) and r.new_play_id not in ("", "None") else r.play_id)
        s = lm.get(pid)
        if s is None or s["posteam"] is None:
            rows.append({c: getattr(r, c) for c in STATE}); continue
        hit += 1
        pih = int(s["posteam"] == s["home"])
        rows.append({"qtr": min(max(s["qtr"], 1), 5), "game_seconds_remaining": s["game_seconds_remaining"],
                     "score_diff_home": s["home_pre"] - s["away_pre"], "posteam_is_home": pih,
                     "down": s["down"] or 0, "ydstogo": s["ydstogo"] or 10, "yardline_100": s["yardline_100"] or 75})
    print(f"lagged state found for {hit}/{len(df)} jumps")
    return pd.DataFrame(rows, index=df.index)


def features(df, state):
    d = df.copy()
    for c in STATE:
        d[c] = state[c].values
    _, Z, _ = F.sim_logprobs(d)
    return np.hstack([Z, d[STATE].to_numpy(float)])


PX = dict(objective="multi:softprob", num_class=6, max_depth=3, learning_rate=0.05, subsample=0.8,
          colsample_bytree=0.8, min_child_weight=3, reg_lambda=3.0, tree_method="hist")


def main():
    df = pd.read_parquet(ROOT / "pipeline/out/fires_relabeled.parquet").drop_duplicates(subset=["game_id", "jump_start_ms"])
    df = df[df["category_new"].isin(F.CLASSES)].reset_index(drop=True)
    y = df["category_new"].map({c: i for i, c in enumerate(F.CLASSES)}).to_numpy()
    g = df["game_id"].astype(str).to_numpy(); season = df["season"].to_numpy()
    live = df["delta_home"].abs().to_numpy() >= 0.08
    lm = lag_map()
    X0 = features(df, df[STATE])                       # exact pre-play state (what we trained on)
    X1 = features(df, lagged_state_frame(df, lm))      # one play late (what live usually sees)

    def run(train_aug, split):
        P0 = np.zeros((len(y), 6)); P1 = np.zeros((len(y), 6))
        for tr, te in split:
            if train_aug:   # exact + one-play-late copies of every training jump
                Xtr, ytr = np.vstack([X0[tr], X1[tr]]), np.concatenate([y[tr], y[tr]])
            else:
                Xtr, ytr = X0[tr], y[tr]
            b = xgb.train(PX, xgb.DMatrix(Xtr, ytr), 300)
            P0[te] = b.predict(xgb.DMatrix(X0[te])); P1[te] = b.predict(xgb.DMatrix(X1[te]))
        return P0, P1

    def stat(P, mask):
        pred, conf = P.argmax(1), P.max(1); nm = mask & (pred != 5) & (conf >= 0.75); t56 = mask & (pred != 5) & (conf >= 0.80)
        return (f"acc {np.mean(pred[mask] == y[mask]):.3f} | named@75 {int(nm.sum()):4d} right {np.mean(pred[nm] == y[nm]) if nm.any() else float('nan'):.3f}"
                f" | tier5+6 {int(t56.sum()):4d} right {np.mean(pred[t56] == y[t56]) if t56.any() else float('nan'):.3f}")

    res = {}
    for name, split, mask in [("CV by game", list(GroupKFold(5).split(X0, y, g)), live),
                              ("2025 -> 2026", [(np.where(season == 2025)[0], np.where(season == 2026)[0])], live & (season == 2026))]:
        for aug in (False, True):
            P0, P1 = run(aug, split)
            tag = "NEW (exact + one-play-late)" if aug else "CURRENT (exact only)"
            print(f"[{name}] {tag:28s} | tested on EXACT state: {stat(P0, mask)}")
            print(f"[{name}] {tag:28s} | tested on ONE-PLAY-LATE: {stat(P1, mask)}")
            res[f"{name}|{tag}"] = {"exact": stat(P0, mask), "late": stat(P1, mask)}
    (ROOT / "train/out/lagged_metrics.json").write_text(json.dumps(res, indent=1))

    if "--deploy" in sys.argv:
        b = xgb.train(PX, xgb.DMatrix(np.vstack([X0, X1]), np.concatenate([y, y])), 300)
        dst = ROOT / "engine/model"
        b.save_model(str(dst / "stage2_xgb.json"))
        meta = json.loads((dst / "stage2_meta.json").read_text())
        meta.update({"production": "stage1+state, audited labels, trained on exact + one-play-late ESPN state (train/train_lagged.py)",
                     "lagged_metrics": res})
        (dst / "stage2_meta.json").write_text(json.dumps(meta, indent=1, default=float))
        print("deployed lag-robust model")


if __name__ == "__main__":
    main()

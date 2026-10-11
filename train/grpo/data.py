"""Build 'Should I bet on this?' prompts from real Kalshi NFL windows.
Decision time = +20 s after the play; p = path_p at +20 s. Reward = 1-contract profit after Kalshi fee."""
import json, math, glob, os
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "pipeline", "out")


def winners():
    w = {}
    for d in ("espn2025", "espn"):
        for f in glob.glob(os.path.join(OUT, d, "*.json")):
            try:
                c = json.load(open(f))["header"]["competitions"][0]["competitors"]
                h = [x for x in c if x.get("homeAway") == "home"][0]
                a = [x for x in c if x.get("homeAway") == "away"][0]
                if h.get("winner") is None and a.get("winner") is None:
                    continue
                hs, as_ = int(h.get("score", 0)), int(a.get("score", 0))
                if hs == as_:
                    continue  # tie: skip
                w[str(os.path.basename(f)[:-5])] = 1 if hs > as_ else 0
            except Exception:
                pass
    return w


def fee(P):
    return math.ceil(round(0.07 * P * (1 - P) * 100, 6)) / 100


def reward(action, home_won, p):
    if action == "BUY_HOME":
        P = min(p + 0.01, 0.99)
        return (home_won - P) - fee(P)
    if action == "BUY_AWAY":
        P = min(1 - p + 0.01, 0.99)
        return ((1 - home_won) - P) - fee(P)
    if action == "PASS":
        return 0.0
    return -0.05


def parse(text):
    t = (text or "").strip().upper().replace("-", "_").replace(" ", "_")
    for a in ("BUY_HOME", "BUY_AWAY", "PASS"):
        if t.startswith(a):
            return a
    return None


def at(path_t, path_p, s):
    t = np.asarray(path_t); p = np.asarray(path_p, dtype=float)
    i = int(np.argmin(np.abs(t - s)))
    return float(p[i])


def mmss(sec_in_q):
    sec_in_q = max(0, int(sec_in_q)); return f"{sec_in_q // 60}:{sec_in_q % 60:02d}"


def prompt_for(r, p):
    q = int(r.qtr) if not pd.isna(r.qtr) else 1
    gsr = float(r.game_seconds_remaining) if not pd.isna(r.game_seconds_remaining) else 0
    qname = f"Q{q}" if q <= 4 else "OT"
    clock = mmss(gsr - (4 - q) * 900) if q <= 4 else str(r.clock)
    hs, as_ = int(r.home_score_pre), int(r.away_score_pre)
    s = f"NFL game: {r.away} (away) at {r.home} (home). {qname}, {clock} left in the quarter. Score: {r.home} {hs}, {r.away} {as_}."
    if isinstance(r.posteam, str) and r.posteam and not pd.isna(r.down):
        yl = int(r.yardline_100) if not pd.isna(r.yardline_100) else 50
        side = "own" if yl > 50 else "opponent's"
        ydl = 100 - yl if yl > 50 else yl
        s += f" {r.posteam} has the ball, {int(r.down)} and {int(r.ydstogo)} at the {side} {ydl}."
    if isinstance(r.text, str) and r.text:
        s += f" Last play: {r.text[:160]}"
    pc = int(round(p * 100))
    s += (f"\nKalshi price for {r.home} (HOME) to win: {pc} cents. Options: BUY_HOME (pay {pc + 1}c), "
          f"BUY_AWAY (pay {100 - pc + 1}c), PASS. Answer with one word.")
    return s


def build(path):
    W = winners()
    d = pd.read_parquet(path)
    rows = []
    for r in d.itertuples(index=False):
        g = str(r.game_id)
        if g not in W:
            continue
        p = at(r.path_t, r.path_p, 20)
        pre = at(r.path_t, r.path_p, -10)
        if not (0.01 <= p <= 0.99):
            continue
        rows.append(dict(game_id=g, play_id=str(r.play_id), p=p, p_pre=pre, home_won=W[g],
                         prompt=prompt_for(r, p)))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    tr = build(os.path.join(OUT, "real_windows_2025.parquet"))
    te = build(os.path.join(OUT, "real_windows.parquet"))
    here = os.path.dirname(os.path.abspath(__file__))
    tr.to_parquet(os.path.join(here, "train_prompts.parquet")); te.to_parquet(os.path.join(here, "test_prompts.parquet"))
    print("train", tr.shape, tr.game_id.nunique(), "test", te.shape, te.game_id.nunique())
    # blind 150
    sub = te.sample(150, random_state=0).reset_index(drop=True)
    sub["id"] = [f"q{i:03d}" for i in range(len(sub))]
    os.makedirs("/tmp/betbench", exist_ok=True)
    sub[["id", "prompt"]].to_csv("/tmp/betbench/prompts.csv", index=False)
    json.dump({r.id: dict(home_won=int(r.home_won), p=float(r.p), game_id=r.game_id) for r in sub.itertuples()},
              open(os.path.join(here, "betbench_key.json"), "w"), indent=0)
    sub.to_parquet(os.path.join(here, "betbench_subset.parquet"))
    print(sub.prompt.iloc[0])

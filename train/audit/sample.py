"""Stratified audit sample of detector fires + blind dossiers (auto label hidden) for manual labelling.
Writes train/audit/sample_key.csv (with auto labels; do not show labellers) and train/audit/dossiers/part{1,2,3}.txt."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent)); from common import *

A = Path(__file__).parent
F = fires(); P = plays_table()
F = F.sort_values(["game_id", "detect_ms"]).reset_index(drop=True)
F["jump_id"] = (F.game_id.ne(F.game_id.shift()) | (F.detect_ms.diff() > 8000)).cumsum()
F["fire_id"] = F.season.astype(str) + "_" + F.game_id + "_" + F.win_idx.astype(str)
F["absd"] = F.delta_home.abs(); F["live"] = F.absd >= 0.08
rng = np.random.default_rng(11)
# (class, live?, n)
plan = [("OTHER", True, 40), ("OTHER", False, 22), ("TD", True, 13), ("TD", False, 12), ("BIG_PLAY", True, 10),
        ("BIG_PLAY", False, 10), ("TURNOVER", True, 10), ("TURNOVER", False, 10), ("FG", True, 7), ("FG", False, 9),
        ("SAFETY", True, 4), ("SAFETY", False, 3)]
picked, used = [], set()
for c, lv, n in plan:
    pool = F[(F.category == c) & (F.live == lv) & ~F.jump_id.isin(used)]
    s = pool.sample(min(n, len(pool)), random_state=int(rng.integers(1e9)))
    used |= set(s.jump_id); picked.append(s)
S = pd.concat(picked).sample(frac=1, random_state=3).reset_index(drop=True)
S["sid"] = [f"S{i:03d}" for i in range(len(S))]
S[["sid", "fire_id", "jump_id", "game_id", "season", "play_id", "category", "window_kind", "delta_home", "absd", "live",
   "t_start", "jump_start_ms", "detect_ms", "win_idx"]].to_csv(A / "sample_key.csv", index=False)

import finetune_real as fr
W = fr.load_windows()
Pg = {g: d.sort_values("wallclock_ms") for g, d in P.groupby("game_id")}
blocks = []
for r in S.itertuples():
    w = W.iloc[r.win_idx]; t = np.asarray(w.path_t, float); p = pd.Series(np.asarray(w.path_p, float)).ffill().to_numpy()
    js = r.jump_start_ms; g = Pg[r.game_id]
    home, away = g.home.iloc[0], g.away.iloc[0]
    rel = (w.wallclock_ms + t * 1000 - js) / 1000
    pts = [f"{int(a):+d}:{b:.2f}" for a, b in zip(rel, p) if -40 <= a <= 70 and int(a) % 4 == 0 and not np.isnan(b)]
    lines = [f"### {r.sid} | {away} @ {home} | home-win-prob moved {r.delta_home:+.3f} (toward {'HOME '+home if r.delta_home>0 else 'AWAY '+away}) | time 0 = jump start",
             "price (s rel. jump start : p_home): " + " ".join(pts)]
    near = g[(g.wallclock_ms >= js - 120000) & (g.wallclock_ms <= js + 120000)]
    for q in near.itertuples():
        dd = f"{int(q.down)}&{int(q.ydstogo)}@{int(q.yardline_100)}" if pd.notna(q.down) and pd.notna(q.ydstogo) and pd.notna(q.yardline_100) else "-"
        lines.append(f"  {(q.wallclock_ms-js)/1000:+6.0f}s id={q.play_id} Q{q.period} {q.clock} [{q.type_text}] pos={q.posteam or '-'} {dd} "
                     f"score {away} {q.away_score}-{q.home_score} {home} | {str(q.text)[:230]}")
    blocks.append("\n".join(lines))
(A / "dossiers").mkdir(exist_ok=True)
k = int(np.ceil(len(blocks) / 3))
for i in range(3):
    (A / "dossiers" / f"part{i+1}.txt").write_text("\n\n".join(blocks[i * k:(i + 1) * k]) + "\n")
print(len(S), S.groupby(["category", "live"]).size().to_dict())

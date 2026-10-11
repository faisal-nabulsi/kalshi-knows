"""Per-game context for every game in our real Kalshi windows, keyed by ESPN game id.

Sources (downloaded to train/context/raw/, not committed):
  nflverse schedules games.csv  - roof, surface, temp, wind, spread_line, total_line, rest, div_game, kickoff, QBs, final score
  nflverse injuries_{2025,2026} - weekly injury report (Out / Doubtful counts, QB out)
ESPN id <-> nflverse game_id via the `espn` column in games.csv (348/348 of our games match).
Output: train/context/out/game_context.parquet
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW, OUT = ROOT / "train/context/raw", ROOT / "train/context/out"
OUT.mkdir(exist_ok=True)

g = pd.read_csv(RAW / "games.csv", low_memory=False)
g = g[g.season.isin([2025, 2026])].copy()
g["espn"] = g["espn"].astype("Int64").astype(str)

# home stadium type per team-season (mode of roof over its home games); dome team = dome or closed retractable
roof_mode = g.groupby(["season", "home_team"])["roof"].agg(lambda s: s.mode().iat[0]).rename("home_roof_type")
dome_team = roof_mode.isin(["dome", "closed"])

# opening-day starting QB per team-season (live-safe: known before any later game)
long = pd.concat([g[["season", "week", "home_team", "home_qb_id"]].set_axis(["season", "week", "team", "qb"], axis=1),
                  g[["season", "week", "away_team", "away_qb_id"]].set_axis(["season", "week", "team", "qb"], axis=1)])
first_qb = long.sort_values("week").groupby(["season", "team"])["qb"].first()

inj = pd.concat([pd.read_parquet(RAW / f"injuries_{y}.parquet") for y in (2025, 2026)])
inj = inj[inj.report_status.isin(["Out", "Doubtful"])]
inj_n = inj.groupby(["season", "week", "team"]).size()
inj_skill = inj[inj.position.isin(["QB", "RB", "WR", "TE"])].groupby(["season", "week", "team"]).size()
inj_qb = inj[inj.position == "QB"].groupby(["season", "week", "team"]).size()


def look(s, key):
    return float(s.get(key, 0))


rows = []
for r in g.itertuples(index=False):
    d = {"game_id": r.espn, "nfl_game_id": r.game_id, "season": r.season, "week": r.week, "game_type": r.game_type,
         "home": r.home_team, "away": r.away_team, "home_score": r.home_score, "away_score": r.away_score,
         "home_win": np.nan if pd.isna(r.result) or r.result == 0 else float(r.result > 0), "tie": r.result == 0,
         "roof": r.roof, "indoor": float(r.roof in ("dome", "closed")), "grass": float(str(r.surface).strip() == "grass"),
         "temp": r.temp if r.roof not in ("dome", "closed") else 70.0, "wind": r.wind if r.roof not in ("dome", "closed") else 0.0,
         "spread_home": r.spread_line, "total_line": r.total_line, "home_rest": r.home_rest, "away_rest": r.away_rest,
         "div_game": float(r.div_game), "gametime": r.gametime, "weekday": r.weekday,
         "primetime": float((str(r.gametime) >= "19:00") or r.weekday in ("Thursday", "Monday")),
         "home_dome_team": float(dome_team.get((r.season, r.home_team), False)),
         "away_dome_team": float(dome_team.get((r.season, r.away_team), False)),
         "home_backup_qb": float(r.home_qb_id != first_qb.get((r.season, r.home_team))),
         "away_backup_qb": float(r.away_qb_id != first_qb.get((r.season, r.away_team)))}
    for side, team in (("home", r.home_team), ("away", r.away_team)):
        k = (r.season, r.week, team)
        d[f"{side}_inj_out"], d[f"{side}_inj_skill"], d[f"{side}_qb_out"] = look(inj_n, k), look(inj_skill, k), look(inj_qb, k)
    rows.append(d)

ctx = pd.DataFrame(rows)
ctx.to_parquet(OUT / "game_context.parquet", index=False)
print(ctx.shape, ctx[["indoor", "grass", "primetime", "home_backup_qb", "away_backup_qb", "home_dome_team"]].mean().round(3).to_dict())

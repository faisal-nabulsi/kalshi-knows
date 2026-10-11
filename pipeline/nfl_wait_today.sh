#!/bin/bash
# Wait for today's early (<=17:30Z) games to go final, then refresh everything + real_windows_today + commit.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
while true; do
  left=$(curl -s "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=5" | $PY -c "
import json,sys
d=json.load(sys.stdin)
print(sum(1 for e in d['events'] if e['date']<='2026-10-11T17:30Z' and e['status']['type']['state']!='post'))")
  [ "$left" = "0" ] && break
  sleep 120
done
sleep 240
pipeline/nfl_refresh.sh && $PY pipeline/nfl_windows.py --today && \
git add pipeline/nfl_*.py pipeline/nfl_*.sh results/market_lag.json results/market_lag.png results/detector_sweep.json docs/data/replay.json pipeline/out/nfl_plays.parquet pipeline/out/aligned_jumps.parquet pipeline/out/game_map.json pipeline/out/real_windows_today.parquet && \
git commit -qm "nfl-data: refresh with today's early games + real_windows_today

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" && git push -q origin main
echo done

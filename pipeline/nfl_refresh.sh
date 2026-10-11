#!/bin/bash
# Full refresh: ESPN -> trades (only missing games) -> plays -> alignment/lag/detector -> replay
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
$PY pipeline/nfl_fetch_espn.py && $PY pipeline/nfl_pull_trades.py && $PY pipeline/nfl_build_plays.py && $PY pipeline/nfl_align.py && $PY pipeline/nfl_replay.py

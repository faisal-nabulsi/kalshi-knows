#!/bin/zsh
# One-command re-render. Reads every number from the repo at run time. ~3 min.
# Optional: HERO_ID=a_12 (pick a different logged alert), SITE=... , STEVE_VOICE="Rocko (English (US))", STEVE_RATE=228
set -e
cd "$(dirname "$0")"; PY=../.venv/bin/python
$PY build_data.py >/dev/null
$PY script.py >/dev/null
$PY audio.py          # TTS + stingers -> build/audio.wav, build/timeline.json
$PY frames.py         # cold open, money shot, how it works, close (deterministic frames)
$PY tour.py           # records the real site
$PY compose.py        # captions + mux
ffprobe -v error -show_entries format=duration,size -of default=nw=1 kalshi-knows-demo.mp4

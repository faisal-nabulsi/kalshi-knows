#!/bin/zsh
# One-command re-render of the ~69 s pitch ad -> video/kalshi-knows-ad.mp4
# Env: VOICE=am_michael (am_adam, am_puck, ...)  SPEED=1.0  AD_HERO=a_12  SITE=...
# Human voice: drop video/voice_override/NN.wav (NN = line id printed below) and re-run.
set -e
cd "$(dirname "$0")"; PY=../.venv/bin/python
$PY ad_data.py
$PY ad_audio.py
$PY ad_frames.py
$PY ad_tour.py
$PY ad_compose.py
ffprobe -v error -show_entries format=duration,size -of default=nw=1 kalshi-knows-ad.mp4

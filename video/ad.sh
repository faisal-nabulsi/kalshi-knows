#!/bin/zsh
# One-command re-render of the ~45 s story ad -> video/kalshi-knows-ad.mp4
# Voice: ElevenLabs premade (ELEVEN_VOICE=Liam) if ~/.config/elevenlabs/key exists, else edge-tts (EDGE_VOICE=en-US-AndrewMultilingualNeural). ENGINE=edge|elevenlabs to force.
# Human voice: drop video/voice_override/{hook,story,proof,more,close}.wav and re-run.
set -e
cd "$(dirname "$0")"; PY=../.venv/bin/python
$PY ad2_script.py >/dev/null
$PY ad2_audio.py
$PY ad2_frames.py
$PY ad2_tour.py
$PY ad2_compose.py
ffprobe -v error -show_entries format=duration,size -of default=nw=1 kalshi-knows-ad.mp4

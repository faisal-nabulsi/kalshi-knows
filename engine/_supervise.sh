#!/usr/bin/env bash
# Keep the engine running: restart it if it ever exits. Args go to engine.live.
cd "$(dirname "$0")/.."
while true; do
  .venv/bin/python -m engine.live "$@"
  echo "$(date) engine exited ($?); restarting in 2s" >&2
  sleep 2
done

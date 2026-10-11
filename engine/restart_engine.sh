#!/usr/bin/env bash
# Restart only the engine (uvicorn :8000); the Cloudflare tunnel and its URL stay up.
# Extra args go to the engine, e.g. engine/restart_engine.sh --replay docs/data/replay.json --speed 1 --loop
cd "$(dirname "$0")/.."
RUN=engine/logs/run; mkdir -p "$RUN"
[ -f "$RUN/engine.pid" ] && kill "$(cat "$RUN/engine.pid")" 2>/dev/null
pkill -f "python -m engine.live" 2>/dev/null
sleep 1
nohup .venv/bin/python -m engine.live "$@" > "$RUN/engine.log" 2>&1 &
echo $! > "$RUN/engine.pid"
for i in $(seq 1 30); do curl -sf localhost:8000/api/health >/dev/null && break; sleep 1; done
curl -s localhost:8000/api/health | head -c 300; echo

#!/usr/bin/env bash
# Stop the live engine and the Cloudflare tunnel started by run_live.sh.
cd "$(dirname "$0")/.."
RUN=engine/logs/run
for f in engine tunnel; do
  if [ -f "$RUN/$f.pid" ]; then kill "$(cat "$RUN/$f.pid")" 2>/dev/null; rm -f "$RUN/$f.pid"; fi
done
pkill -f "engine/_supervise.sh" 2>/dev/null
pkill -f "python -m engine.live" 2>/dev/null
pkill -f "cloudflared tunnel --no-autoupdate --url http://localhost:8000" 2>/dev/null
# free the port if something else still holds it
PIDS=$(lsof -ti tcp:8000 2>/dev/null); [ -n "$PIDS" ] && kill $PIDS 2>/dev/null
echo "stopped"

#!/usr/bin/env bash
# Start the live engine (uvicorn :8000) + a Cloudflare quick tunnel, publish the URL to docs/config.json.
# Re-runnable: kills old engine/tunnel first.  Extra args go to the engine, e.g.
#   engine/run_live.sh --replay docs/data/replay.json --speed 1 --loop
# Env: NO_PUSH_GIT=1 skips the git commit/push of docs/config.json.
set -u
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
RUN="$ROOT/engine/logs/run"
mkdir -p "$RUN"
PY="$ROOT/.venv/bin/python"
CF=/opt/homebrew/bin/cloudflared

"$ROOT/engine/stop_live.sh" >/dev/null 2>&1 || true
sleep 1

echo "starting engine on :8000 $*"
nohup "$ROOT/engine/_supervise.sh" "$@" > "$RUN/engine.log" 2>&1 &
echo $! > "$RUN/engine.pid"
# keep the Mac awake while the engine runs (display may sleep; system, disk and network stay up)
nohup caffeinate -imsu -w "$(cat "$RUN/engine.pid")" >/dev/null 2>&1 &
for i in $(seq 1 30); do
  curl -sf localhost:8000/api/health >/dev/null && break
  sleep 1
done
curl -sf localhost:8000/api/health >/dev/null || { echo "engine failed to start; see $RUN/engine.log"; tail -20 "$RUN/engine.log"; exit 1; }

echo "starting cloudflared tunnel"
: > "$RUN/tunnel.log"
nohup "$CF" tunnel --no-autoupdate --url http://localhost:8000 > "$RUN/tunnel.log" 2>&1 &
echo $! > "$RUN/tunnel.pid"
URL=""
for i in $(seq 1 45); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$RUN/tunnel.log" | head -1)
  [ -n "$URL" ] && break
  sleep 1
done
[ -n "$URL" ] || { echo "no tunnel URL; see $RUN/tunnel.log"; tail -20 "$RUN/tunnel.log"; exit 1; }
echo "$URL" > "$RUN/url.txt"

# wait until the tunnel actually serves the API (DNS for new quick tunnels can take a few seconds)
for i in $(seq 1 40); do
  curl -sf "$URL/api/health" >/dev/null && break
  sleep 2
done

printf '{"api":"%s"}\n' "$URL" > docs/config.json
if [ "${NO_PUSH_GIT:-0}" != "1" ]; then
  while [ -f .git/index.lock ]; do sleep 2; done
  git add docs/config.json
  git commit -q -m "live api url" -- docs/config.json 2>/dev/null || echo "(config.json unchanged)"
  git push -q origin main 2>&1 || echo "WARNING: git push failed; push docs/config.json manually"
fi
echo "health via tunnel: $(curl -s "$URL/api/health" | head -c 200)"
echo "LIVE API URL: $URL"
# Also publish the site (incl. the new config.json) to Cloudflare Pages: https://kalshi-knows.pages.dev
command -v wrangler >/dev/null && wrangler pages deploy docs --project-name kalshi-knows --branch main --commit-dirty=true >/dev/null 2>&1 && echo "deployed to https://kalshi-knows.pages.dev"

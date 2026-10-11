#!/usr/bin/env bash
# DEMO SAFETY NET: a SECOND engine on :8001 that replays today's real IND @ PIT "Steelers touchdown" alert
# (12:37pm, alert a_12) from the engine's own logs, at real speed, starting ~40 s before the price jump is
# detected (first buzz ~43 s after start, the named call ~8 s later, ESPN's confirmation ~70 s after that).
# The live engine on :8000 is never touched. Replay alerts get "r_" ids (the auto-bettor ignores them),
# the site shows REPLAY, and pushes are titled "REPLAY · SPOILER ...".
#
#   engine/demo_replay.sh              start (WITH push to the existing subscribers: phones buzz)
#   engine/demo_replay.sh --no-push    start without push (rehearsal)
#   engine/demo_replay.sh --lead 25    start 25 s before the jump instead of 40
#   engine/demo_replay.sh --no-serve   don't serve docs/ on http://localhost:8002 (served by default: the https
#                                      Pages site can't call http://localhost in Chrome without a permission prompt)
#   engine/demo_replay.sh --stop       stop the replay (and the docs server)
# Env: DAY=20261011 ALERT=a_12 PORT=8001 SITE_PORT=8002
# NOTE: engine/restart_engine.sh kills every "python -m engine.live" process, including this one; re-run after it.
cd "$(dirname "$0")/.."
RUN=engine/logs/run; mkdir -p "$RUN"
PORT="${PORT:-8001}"; SITE_PORT="${SITE_PORT:-8002}"; DAY="${DAY:-20261011}"; ALERT="${ALERT:-a_12}"
LEAD=40; PUSH=""; SERVE=1; STOP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --no-push) PUSH="--no-push" ;;
    --lead) LEAD="$2"; shift ;;
    --serve) SERVE=1 ;;
    --no-serve) SERVE=0 ;;
    --stop) STOP=1 ;;
    *) echo "unknown arg $1"; exit 2 ;;
  esac
  shift
done

stop_replay() {
  [ -f "$RUN/replay.pid" ] && kill "$(cat "$RUN/replay.pid")" 2>/dev/null
  pkill -f "engine.live --replay .* --port $PORT" 2>/dev/null
  rm -f "$RUN/replay.pid"
}
stop_site() {
  [ -f "$RUN/site.pid" ] && kill "$(cat "$RUN/site.pid")" 2>/dev/null
  rm -f "$RUN/site.pid"
}
if [ "$STOP" = 1 ]; then stop_replay; stop_site; echo "replay stopped (live engine on :8000 untouched)"; exit 0; fi

# start point = the alert's jump start minus LEAD seconds (original game time, from today's alert log)
read -r GID START JUMP < <(.venv/bin/python - "$DAY" "$ALERT" "$LEAD" <<'EOF'
import json, sys
day, aid, lead = sys.argv[1], sys.argv[2], float(sys.argv[3])
a = None
for ln in open(f"engine/logs/{day}/alerts.jsonl"):
    r = json.loads(ln)
    if r["id"] == aid:
        a = r
if a is None:
    sys.exit(f"alert {aid} not in engine/logs/{day}/alerts.jsonl")
j = a.get("detected_ms") or a.get("jump_started_ms") or a["ts_ms"]   # the moment the jump was confirmed
print(a["game_id"], int(j - lead * 1000), j)
EOF
)
[ -n "$START" ] || { echo "could not find $ALERT in engine/logs/$DAY"; exit 1; }

stop_replay
sleep 1
echo "replay: game $GID from $(date -r $((START / 1000)) +%H:%M:%S) (jump at $(date -r $((JUMP / 1000)) +%H:%M:%S)), speed 1, port $PORT ${PUSH:-WITH PUSH}"
REPLAY_SIDECAR=1 TABPFN=0 nohup .venv/bin/python -m engine.live --replay "engine/logs/$DAY" --game "$GID" --speed 1 \
  --start-ms "$START" --port "$PORT" $PUSH > "$RUN/replay.log" 2>&1 < /dev/null &
echo $! > "$RUN/replay.pid"
for i in $(seq 1 40); do curl -sf "localhost:$PORT/api/health" >/dev/null && break; sleep 0.5; done
curl -sf "localhost:$PORT/api/health" >/dev/null || { echo "replay engine failed; see $RUN/replay.log"; tail -20 "$RUN/replay.log"; exit 1; }
echo "health :$PORT -> $(curl -s "localhost:$PORT/api/health" | head -c 160)"

if [ "$SERVE" = 1 ]; then
  stop_site
  nohup python3 -m http.server "$SITE_PORT" --bind 127.0.0.1 --directory docs > "$RUN/site.log" 2>&1 < /dev/null &
  echo $! > "$RUN/site.pid"
  sleep 1
  curl -sf "localhost:$SITE_PORT/" >/dev/null || echo "WARNING: docs server on :$SITE_PORT not answering (port busy?); see $RUN/site.log"
  echo "PRESENTER: open http://localhost:$SITE_PORT/?present=1&api=http://localhost:$PORT"
fi
[ "$SERVE" = 1 ] || echo "presenter: serve docs/ locally (python3 -m http.server $SITE_PORT --directory docs) and open http://localhost:$SITE_PORT/?present=1&api=http://localhost:$PORT"
echo "first buzz in ~$((LEAD + 3)) s (provisional), the named call ~8 s later, ESPN confirms ~70 s after that."
echo "stop: engine/demo_replay.sh --stop"

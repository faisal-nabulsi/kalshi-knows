#!/usr/bin/env bash
# Keep the engine running: restart it if it exits OR hangs (health check fails twice in a row).
# Args go to engine.live. TabPFN is off in the live path: which model answered must not depend on timing.
cd "$(dirname "$0")/.."
export TABPFN="${TABPFN:-0}"
# Detector tuned for the real-time Kalshi stream (results/latency_study.md config B)
[ -f engine/live_config_B.sh ] && . engine/live_config_B.sh
PORT="${PORT:-8000}"
while true; do
  .venv/bin/python -m engine.live "$@" &
  PID=$!
  sleep 20                                    # start-up (restores history, loads the model)
  FAILS=0
  while kill -0 $PID 2>/dev/null; do
    if curl -sf -m 5 "localhost:$PORT/api/health" >/dev/null; then FAILS=0; else FAILS=$((FAILS+1)); fi
    if [ $FAILS -ge 2 ]; then
      echo "$(date) health failed twice; dumping stack and restarting engine" >&2
      .venv/bin/py-spy dump --pid $PID >&2 2>/dev/null || true
      kill $PID; sleep 2; kill -9 $PID 2>/dev/null
      break
    fi
    sleep 10
  done
  wait $PID 2>/dev/null
  echo "$(date) engine exited; restarting in 2s" >&2
  sleep 2
done

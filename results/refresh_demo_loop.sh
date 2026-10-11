#!/usr/bin/env bash
# Every 10 min until 16:30 PT: re-export the Kalshi demo ledger and push it if it changed.
cd "$(dirname "$0")/.."
while [ "$(date +%H%M)" -lt 1630 ]; do
  .venv/bin/python results/export_demo.py >/dev/null 2>&1
  if ! git diff --quiet -- results/demo_ledger.json results/charts/i_demo_ledger.png; then
    while [ -f .git/index.lock ]; do sleep 2; done
    git add results/demo_ledger.json results/charts/i_demo_ledger.png && \
      git commit -qm "Demo ledger refresh $(date +%H:%M)" -- results/demo_ledger.json results/charts/i_demo_ledger.png && git push -q origin main
  fi
  sleep 600
done

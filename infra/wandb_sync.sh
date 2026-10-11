#!/usr/bin/env bash
# Pull finished offline W&B runs from the GPU box and upload them from the Mac (where `wandb login` lives).
# Loops until the box's training process is gone. Usage: infra/wandb_sync.sh
cd "$(dirname "$0")/.."
IP=$(cat infra/instance_ip.txt); KEY=~/.ssh/hackathon-degen.pem; DST=train/wandb_runs
mkdir -p $DST
while true; do
  rsync -az -e "ssh -i $KEY -o ConnectTimeout=10" ubuntu@$IP:kk/out_v3/wandb/ $DST/ 2>/dev/null
  RUNNING=$(ssh -i $KEY -o ConnectTimeout=10 ubuntu@$IP 'pgrep -f "trials 20" >/dev/null && echo 1 || echo 0')
  NEWEST=$(ls -d $DST/offline-run-* 2>/dev/null | sort | tail -1)
  for d in $DST/offline-run-*; do
    [ "$RUNNING" = 1 ] && [ "$d" = "$NEWEST" ] && continue   # still being written
    [ -d "$d" ] || continue; [ -f "$d/.kk_synced" ] && continue
    ls "$d"/*.wandb >/dev/null 2>&1 || continue
    # only sync runs that have finished (the box writes the exit record on run.finish)
    if .venv/bin/wandb sync "$d" >/tmp/wandb_sync.log 2>&1; then touch "$d/.kk_synced"; echo "synced $(basename $d)"; fi
  done
  [ "$RUNNING" = 1 ] || { echo "training finished; all runs synced"; break; }
  sleep 30
done

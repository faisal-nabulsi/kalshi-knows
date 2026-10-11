#!/usr/bin/env bash
# Re-runnable setup for the disposable GPU box (Ubuntu 22.04 DLAMI base, NVIDIA L40S).
# Usage from the Mac: ssh -i ~/.ssh/hackathon-degen.pem ubuntu@$(cat infra/instance_ip.txt) 'bash -s' < train/setup_box.sh
set -euo pipefail
sudo shutdown -h +450 >/dev/null 2>&1 || true   # safety net: box dies by itself
mkdir -p ~/kk/data ~/kk/out
cd ~/kk
# DLAMI base lacks python3-venv; use uv (pinned) instead
[ -x ~/.local/bin/uv ] || curl -LsSf https://astral.sh/uv/0.5.11/install.sh | sh >/dev/null
export PATH=$HOME/.local/bin:$PATH
[ -d venv ] && [ -x venv/bin/python ] || { rm -rf venv; uv venv -q --python 3.11 venv; }
uv pip install -q --python venv/bin/python "xgboost==2.1.4" "pandas==2.2.3" "pyarrow==18.1.0" "scikit-learn==1.5.2" "numpy==1.26.4"
uv pip install -q --python venv/bin/python "torch==2.5.1" --index-url https://download.pytorch.org/whl/cu124
for y in $(seq 1999 2026); do
  f=data/pbp_$y.parquet
  [ -s "$f" ] || curl -sL -o "$f" "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_$y.parquet"
done
ls -la data | tail -3
./venv/bin/python -c "import torch,xgboost;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),'xgb',xgboost.__version__)"

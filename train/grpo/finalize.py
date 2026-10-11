"""Plot the GRPO reward curve and push the per-step log to W&B (project kalshi-knows, group grpo)."""
import os, json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(os.path.join(HERE, "reward_log.json")))
L = [x for x in L if "reward" in x]
st = np.array([x["step"] for x in L]); r = np.array([x["reward"] for x in L])
k = min(10, len(r)); roll = np.convolve(r, np.ones(k) / k, mode="valid")
fig, ax = plt.subplots(figsize=(7, 3.5))
ax.plot(st, r, color="#9aa5b1", lw=1, label="mean reward per step (8 completions)")
ax.plot(st[k - 1:], roll, color="#1f5fbf", lw=2, label=f"{k}-step rolling mean")
ax.axhline(0, color="black", lw=0.8, ls="--"); ax.set_xlabel("GRPO step"); ax.set_ylabel("$ P&L per contract")
ax.set_title("GRPO reward (1-contract Kalshi P&L after fee)"); ax.legend(fontsize=8, frameon=False)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "reward_curve.png"), dpi=130)
print("steps", len(r), "first10", round(float(r[:10].mean()), 4), "last10", round(float(r[-10:].mean()), 4))
try:
    import wandb
    run = wandb.init(project="kalshi-knows", group="grpo", name="grpo-qwen0.5b-lora-pnl", reinit=True)
    for x in L:
        wandb.log({k2: v for k2, v in x.items() if k2 != "step"}, step=int(x["step"]))
    for f in ("results_baselines.json", "results_base.json", "results_grpo.json"):
        p = os.path.join(HERE, f)
        if os.path.exists(p):
            run.summary[f[:-5]] = json.load(open(p))
    wandb.log({"reward_curve": wandb.Image(os.path.join(HERE, "reward_curve.png"))})
    print("wandb", run.url); run.finish()
except Exception as e:
    print("wandb failed", e)

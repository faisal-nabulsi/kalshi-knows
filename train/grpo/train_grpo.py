"""GRPO (TRL) on Qwen2.5-0.5B-Instruct + LoRA, reward = 1-contract Kalshi P&L. Wall-clock time-boxed."""
import os, sys, time, json, datetime
import pandas as pd
from datasets import Dataset
from transformers import TrainerCallback
from trl import GRPOConfig, GRPOTrainer
from peft import LoraConfig
import torch
import trl.trainer.utils as _U


class _TorchChunkedLogProb:  # pure-torch fallback: TRL's Triton kernel is Linux-only (None on macOS/MPS)
    @staticmethod
    def apply(hidden, weight, bias, targets, temperature, chunk_size, softcap=None, logit_scale=1.0, outputs=()):
        z = hidden @ weight.T
        if bias is not None:
            z = z + bias
        z = z.float() * logit_scale
        if softcap is not None:
            z = torch.tanh(z / softcap) * softcap
        z = z / temperature
        lp = torch.log_softmax(z, -1)
        logprobs = lp.gather(-1, targets.unsqueeze(-1)).squeeze(-1)
        pr = lp.exp()
        ent = -(pr * lp).sum(-1) if "entropy" in outputs else None
        lss = torch.log((pr * pr).sum(-1)) if "log_sum_sq_probs" in outputs else None
        ml = z.mean(-1) if "mean_logits" in outputs else None
        top = (z.argmax(-1) == targets) if "is_top1" in outputs else None
        return logprobs, ent, lss, ml, top


if _U._ChunkedLogProbFunction is None:
    _U._ChunkedLogProbFunction = _TorchChunkedLogProb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data import reward, parse

HERE = os.path.dirname(os.path.abspath(__file__))
DEADLINE = os.environ.get("DEADLINE", "15:43")  # local time HH:MM to stop training
hh, mm = map(int, DEADLINE.split(":"))
now = datetime.datetime.now()
stop_at = now.replace(hour=hh, minute=mm, second=0).timestamp()

SYS = "You are a sports-betting advisor. Reply with exactly one word: BUY_HOME, BUY_AWAY, or PASS."
tr = pd.read_parquet(os.path.join(HERE, "train_prompts.parquet")).sample(frac=1, random_state=1).reset_index(drop=True)
ds = Dataset.from_dict({
    "prompt": [[{"role": "system", "content": SYS}, {"role": "user", "content": p}] for p in tr.prompt],
    "home_won": tr.home_won.tolist(), "p": tr.p.tolist()})

LOG = []


def pnl_reward(prompts, completions, home_won, p, **kw):
    out = []
    for c, h, pp in zip(completions, home_won, p):
        txt = c[0]["content"] if isinstance(c, list) else c
        out.append(float(reward(parse(txt), int(h), float(pp))))
    return out


class TimeBox(TrainerCallback):
    def on_step_end(self, args, state, control, **kw):
        if time.time() > stop_at:
            control.should_training_stop = True
        return control

    def on_log(self, args, state, control, logs=None, **kw):
        if logs:
            LOG.append(dict(step=state.global_step, **{k: v for k, v in logs.items() if isinstance(v, (int, float))}))
            json.dump(LOG, open(os.path.join(HERE, "reward_log.json"), "w"))


cfg = GRPOConfig(
    output_dir="/tmp/betbench/grpo_out", learning_rate=1e-5, num_generations=8,
    per_device_train_batch_size=8, gradient_accumulation_steps=1,
    max_completion_length=6, temperature=1.0, beta=0.0,
    max_steps=2000, logging_steps=1, save_strategy="no", report_to="none",
    run_name="grpo-qwen0.5b-lora-pnl", bf16=False, fp16=False, seed=0,
    remove_unused_columns=False, model_init_kwargs={"dtype": "bfloat16"},
)
os.environ.setdefault("WANDB_PROJECT", "kalshi-knows")
os.environ.setdefault("WANDB_RUN_GROUP", "grpo")
trainer = GRPOTrainer(
    model="Qwen/Qwen2.5-0.5B-Instruct", reward_funcs=pnl_reward, args=cfg, train_dataset=ds,
    peft_config=LoraConfig(r=16, lora_alpha=32, lora_dropout=0.0, target_modules="all-linear", task_type="CAUSAL_LM"),
    callbacks=[TimeBox()],
)
trainer.train()
trainer.model.save_pretrained(os.path.join("/tmp/betbench", "grpo_lora"))
print("SAVED steps", trainer.state.global_step)

"""Kaggle T4 GRPO run: Qwen2.5-0.5B-Instruct + LoRA, reward = 1-contract Kalshi P&L after spread+fee.
Trains ~TRAIN_MIN minutes (wall clock), then evaluates base vs GRPO on the 2026 test prompts. W&B offline."""
import subprocess, sys, os, time, glob, json
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "trl>=0.12", "peft", "accelerate", "datasets"], check=False)
os.environ["WANDB_MODE"] = "offline"; os.environ["WANDB_PROJECT"] = "kalshi-knows"; os.environ["WANDB_RUN_GROUP"] = "grpo"
os.environ["WANDB_DIR"] = "/kaggle/working"
T0 = time.time()
TRAIN_MIN = float(os.environ.get("TRAIN_MIN", "10"))

import numpy as np, pandas as pd, torch
f = glob.glob("/kaggle/input/**/data.py", recursive=True)[0]
D = os.path.dirname(f); sys.path.insert(0, D)
from data import reward, parse
print("data dir", D, "torch", torch.__version__, "cuda", torch.cuda.is_available(), flush=True)

tr = pd.read_parquet(os.path.join(D, "train_prompts.parquet")).sample(frac=1, random_state=1).reset_index(drop=True)
te = pd.read_parquet(os.path.join(D, "test_prompts.parquet"))
sub = pd.read_parquet(os.path.join(D, "betbench_subset.parquet"))
SYS = "You are a sports-betting advisor. Reply with exactly one word: BUY_HOME, BUY_AWAY, or PASS."
NAME = "Qwen/Qwen2.5-0.5B-Instruct"


def metrics(df, actions, B=2000, seed=0):
    df = df.copy(); df["a"] = actions
    df["r"] = [reward(a, h, p) for a, h, p in zip(df.a, df.home_won, df.p)]
    bet = df.a.isin(["BUY_HOME", "BUY_AWAY"]); nb = int(bet.sum())
    out = dict(n=len(df), bets=nb, invalid=int(df.a.isna().sum()), pnl_total=round(float(df.r.sum()), 3),
               pnl_per_bet=round(float(df.r[bet].mean()), 4) if nb else 0.0,
               win_rate=round(float((df.r[bet] > 0).mean()), 4) if nb else None,
               mix={k: int(v) for k, v in df.a.fillna("INVALID").value_counts().items()})
    if nb:
        rng = np.random.default_rng(seed); games = df.game_id.unique(); g = {k: v for k, v in df.groupby("game_id")}
        per = []
        for _ in range(B):
            s = pd.concat([g[x] for x in rng.choice(games, len(games))]); sb = s.a.isin(["BUY_HOME", "BUY_AWAY"])
            per.append(s.r[sb].mean() if sb.any() else 0.0)
        out["pnl_per_bet_ci95"] = [round(float(np.percentile(per, 2.5)), 4), round(float(np.percentile(per, 97.5)), 4)]
    return out


def gen_actions(model, tok, df, bs=128):
    tok.padding_side = "left"
    texts = [tok.apply_chat_template([{"role": "system", "content": SYS}, {"role": "user", "content": p}],
                                     tokenize=False, add_generation_prompt=True) for p in df.prompt]
    outs = []
    model.eval()
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i + bs], return_tensors="pt", padding=True).to(model.device)
        with torch.no_grad():
            g = model.generate(**enc, max_new_tokens=6, do_sample=False, pad_token_id=tok.eos_token_id)
        outs += tok.batch_decode(g[:, enc.input_ids.shape[1]:], skip_special_tokens=True)
    return [parse(o) for o in outs], outs


def evaluate(model, tok, tag):
    a, raw = gen_actions(model, tok, te)
    key = dict(zip(te.play_id, a))
    pd.DataFrame(dict(play_id=te.play_id, game_id=te.game_id, p=te.p, home_won=te.home_won, action=a, raw=raw)).to_csv(
        f"/kaggle/working/preds_{tag}.csv", index=False)
    return {"full_2026": metrics(te, a), "betbench150": metrics(sub, [key[x] for x in sub.play_id])}


from transformers import AutoTokenizer, AutoModelForCausalLM, TrainerCallback
tok = AutoTokenizer.from_pretrained(NAME)
RES = {}
base = AutoModelForCausalLM.from_pretrained(NAME, torch_dtype=torch.float16).cuda()
RES["base"] = evaluate(base, tok, "base"); print("BASE", json.dumps(RES["base"]), flush=True)
del base; torch.cuda.empty_cache()

from datasets import Dataset
from trl import GRPOConfig, GRPOTrainer
from peft import LoraConfig
try:
    import trl.trainer.utils as _U
    if getattr(_U, "_ChunkedLogProbFunction", 1) is None:
        class _TorchChunked:
            @staticmethod
            def apply(hidden, weight, bias, targets, temperature, chunk_size, softcap=None, logit_scale=1.0, outputs=()):
                z = hidden @ weight.T
                if bias is not None: z = z + bias
                z = z.float() * logit_scale
                if softcap is not None: z = torch.tanh(z / softcap) * softcap
                z = z / temperature; lp = torch.log_softmax(z, -1); pr = lp.exp()
                return (lp.gather(-1, targets.unsqueeze(-1)).squeeze(-1),
                        -(pr * lp).sum(-1) if "entropy" in outputs else None,
                        torch.log((pr * pr).sum(-1)) if "log_sum_sq_probs" in outputs else None,
                        z.mean(-1) if "mean_logits" in outputs else None,
                        (z.argmax(-1) == targets) if "is_top1" in outputs else None)
        _U._ChunkedLogProbFunction = _TorchChunked
except Exception as e:
    print("patch skipped", e)

ds = Dataset.from_dict({"prompt": [[{"role": "system", "content": SYS}, {"role": "user", "content": p}] for p in tr.prompt],
                        "home_won": tr.home_won.tolist(), "p": tr.p.tolist()})
LOG = []


def pnl_reward(prompts, completions, home_won, p, **kw):
    return [float(reward(parse(c[0]["content"] if isinstance(c, list) else c), int(h), float(pp)))
            for c, h, pp in zip(completions, home_won, p)]


stop_at = time.time() + TRAIN_MIN * 60


class TimeBox(TrainerCallback):
    def on_step_end(self, args, state, control, **kw):
        if time.time() > stop_at: control.should_training_stop = True
        return control

    def on_log(self, args, state, control, logs=None, **kw):
        if logs:
            LOG.append(dict(step=state.global_step, **{k: v for k, v in logs.items() if isinstance(v, (int, float))}))
            if "reward" in logs: print("STEP", state.global_step, "reward", round(logs["reward"], 4), flush=True)


cfg = GRPOConfig(output_dir="/kaggle/working/grpo_out", learning_rate=1e-5, num_generations=8,
                 per_device_train_batch_size=64, gradient_accumulation_steps=1, max_completion_length=6,
                 temperature=1.0, beta=0.0, max_steps=5000, logging_steps=1, save_strategy="no",
                 report_to=["wandb"], run_name="grpo-qwen0.5b-lora-pnl-kaggle-t4", fp16=True, seed=0,
                 remove_unused_columns=False)
trainer = GRPOTrainer(model=NAME, reward_funcs=pnl_reward, args=cfg, train_dataset=ds,
                      peft_config=LoraConfig(r=16, lora_alpha=32, lora_dropout=0.0, target_modules="all-linear",
                                             task_type="CAUSAL_LM"), callbacks=[TimeBox()])
trainer.train()
trainer.model.save_pretrained("/kaggle/working/grpo_lora")
json.dump(LOG, open("/kaggle/working/reward_log.json", "w"))
steps = trainer.state.global_step
m = trainer.model.merge_and_unload().half().cuda()
RES["grpo"] = evaluate(m, tok, "grpo")
r = [x["reward"] for x in LOG if "reward" in x]
RES["train"] = dict(steps=steps, prompts_seen=steps * 8, completions=steps * 64,
                    reward_first10=float(np.mean(r[:10])) if r else None, reward_last10=float(np.mean(r[-10:])) if r else None,
                    minutes=round((time.time() - T0) / 60, 1))
json.dump(RES, open("/kaggle/working/final.json", "w"), indent=1)
print("FINAL_JSON", json.dumps(RES), flush=True)

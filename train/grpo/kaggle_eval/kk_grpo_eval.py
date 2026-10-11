"""Kaggle T4 GRPO run: Qwen2.5-0.5B-Instruct + LoRA, reward = 1-contract Kalshi P&L after spread+fee.
Trains ~TRAIN_MIN minutes (wall clock), then evaluates base vs GRPO on the 2026 test prompts. W&B offline."""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # v2 crashed: model split across 2 T4s
import subprocess, sys, time, glob, json
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "peft", "accelerate", "datasets"], check=False)
# Kaggle image ships torchao 0.10, which peft/transformers reject on import (needs >0.16): remove it
subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "-q", "torchao"], check=False)
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


from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
tok = AutoTokenizer.from_pretrained(NAME)
ad = os.path.dirname(glob.glob("/kaggle/input/**/adapter_config.json", recursive=True)[0])
m = AutoModelForCausalLM.from_pretrained(NAME, torch_dtype=torch.float16).to("cuda:0")
m = PeftModel.from_pretrained(m, ad).merge_and_unload().to("cuda:0")
RES = {"grpo": evaluate(m, tok, "grpo")}
json.dump(RES, open("/kaggle/working/final_eval.json", "w"), indent=1)
print("FINAL_JSON", json.dumps(RES), flush=True)

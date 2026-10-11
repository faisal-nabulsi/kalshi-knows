"""Baselines + base-vs-GRPO model eval on the 2026 test prompts. Metrics: P&L/bet, win rate of bets, #bets,
total P&L, and a game-clustered bootstrap 95% CI on total P&L per prompt and P&L per bet."""
import os, sys, json
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data import reward, parse

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = "You are a sports-betting advisor. Reply with exactly one word: BUY_HOME, BUY_AWAY, or PASS."


def metrics(df, actions, B=2000, seed=0):
    df = df.copy(); df["a"] = actions
    df["r"] = [reward(a, h, p) for a, h, p in zip(df.a, df.home_won, df.p)]
    bet = df.a.isin(["BUY_HOME", "BUY_AWAY"])
    nb = int(bet.sum())
    out = dict(n=len(df), bets=nb, invalid=int(df.a.isna().sum()),
               pnl_total=round(float(df.r.sum()), 3),
               pnl_per_bet=round(float(df.r[bet].mean()), 4) if nb else 0.0,
               win_rate=round(float((df.r[bet] > 0).mean()), 4) if nb else None,
               mix={k: int(v) for k, v in df.a.fillna("INVALID").value_counts().items()})
    if nb:
        rng = np.random.default_rng(seed); games = df.game_id.unique()
        g = {k: v for k, v in df.groupby("game_id")}
        per = []
        for _ in range(B):
            s = pd.concat([g[x] for x in rng.choice(games, len(games))])
            sb = s.a.isin(["BUY_HOME", "BUY_AWAY"])
            per.append(s.r[sb].mean() if sb.any() else 0.0)
        out["pnl_per_bet_ci95"] = [round(float(np.percentile(per, 2.5)), 4), round(float(np.percentile(per, 97.5)), 4)]
    return out


def baselines(df):
    fav = np.where(df.p >= 0.5, "BUY_HOME", "BUY_AWAY")
    jump = df.p - df.p_pre
    last = np.where(jump > 0, "BUY_HOME", np.where(jump < 0, "BUY_AWAY", "PASS"))
    # supervised view: our calibration work says the market is calibrated -> expected edge < fee+spread -> PASS
    return {"always_pass": metrics(df, ["PASS"] * len(df)),
            "always_favorite": metrics(df, list(fav)),
            "follow_last_jump": metrics(df, list(last)),
            "supervised_calibrated_market(PASS)": metrics(df, ["PASS"] * len(df))}


def model_actions(df, adapter=None, bs=64):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    name = "Qwen/Qwen2.5-0.5B-Instruct"
    tok = AutoTokenizer.from_pretrained(name, padding_side="left")
    m = AutoModelForCausalLM.from_pretrained(name, dtype=torch.bfloat16)
    if adapter:
        from peft import PeftModel
        m = PeftModel.from_pretrained(m, adapter); m = m.merge_and_unload()
    m.to(dev).eval()
    texts = [tok.apply_chat_template([{"role": "system", "content": SYS}, {"role": "user", "content": p}],
                                     tokenize=False, add_generation_prompt=True) for p in df.prompt]
    outs = []
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i + bs], return_tensors="pt", padding=True).to(dev)
        with torch.no_grad():
            g = m.generate(**enc, max_new_tokens=6, do_sample=False, pad_token_id=tok.eos_token_id)
        outs += tok.batch_decode(g[:, enc.input_ids.shape[1]:], skip_special_tokens=True)
    return [parse(o) for o in outs], outs


if __name__ == "__main__":
    which = sys.argv[1]  # baselines | base | grpo
    te = pd.read_parquet(os.path.join(HERE, "test_prompts.parquet"))
    sub = pd.read_parquet(os.path.join(HERE, "betbench_subset.parquet"))
    res = {}
    if which == "baselines":
        res = {"full_2026": baselines(te), "betbench150": baselines(sub)}
    else:
        adapter = "/tmp/betbench/grpo_lora" if which == "grpo" else None
        if os.environ.get("SUBSET_ONLY"):
            te = sub.copy()
        a, raw = model_actions(te, adapter, bs=int(os.environ.get("BS", "32")))
        te["action"] = a; te["raw"] = raw
        te[["game_id", "play_id", "p", "home_won", "action", "raw"]].to_csv(os.path.join(HERE, f"preds_{which}.csv"), index=False)
        key = dict(zip(te.play_id, a))
        res = {("betbench150_only" if os.environ.get("SUBSET_ONLY") else "full_2026"): metrics(te, a),
               "betbench150": metrics(sub, [key[x] for x in sub.play_id])}
    json.dump(res, open(os.path.join(HERE, f"results_{which}.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))

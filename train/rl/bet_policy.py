"""Learn a betting policy from the live decision log (engine/logs/picks/scored.jsonl).

Every row is one market the Picks model looked at, with the features, both asks, the decision, and (once settled) the
reward in cents per contract of each action: pass (0), buy YES at its ask, buy NO at its ask, after the taker fee.
Because the outcome reveals the reward of EVERY action, this is a full-feedback bandit: we can train and evaluate any
policy on all rows without exploration noise or importance weights.

Two learners, both evaluated on the newest 30% of rows (time split, never shuffled):
  1. recal: logistic recalibration on top of the model's p_yes (+ horizon, price, spread) -> expected reward -> argmax
  2. policy: softmax policy over {pass, yes, no} trained to maximize realized reward directly (policy gradient with
     known rewards for all actions, L2-regularized), the RL step
Baseline: the live rule (edge > threshold and EV at the ask >= 1c).
Usage: .venv/bin/python train/rl/bet_policy.py [--min-rows 300]
"""
import argparse, json, math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "engine/logs/picks/scored.jsonl"
OUT = ROOT / "train/rl/out"
NUM = ["price", "logit_p", "h", "vwap24", "mom6", "mom24", "price_vs_vwap", "std24", "n_tr", "n_tr24", "ct", "ct24",
       "yes_share24", "hrs_since_last", "lifetime_h"]


def fee_pc(P, C=10):
    return math.ceil(round(0.07 * C * P * (1 - P) * 100, 6)) / 100 / C


def load():
    rows = []
    for ln in LOG.read_text().splitlines() if LOG.exists() else []:
        r = json.loads(ln)
        rc = r.get("reward_cents") or {}
        if r.get("result") is None or rc.get("yes") is None or rc.get("no") is None:
            continue
        rows.append(r)
    rows.sort(key=lambda r: r["ts_ms"])
    return rows


def matrix(rows):
    p = np.array([r["p_yes"] for r in rows])
    lp = np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
    ya = np.array([r["yes_ask"] for r in rows]); na = np.array([r["no_ask"] for r in rows])
    f = np.array([[float(r["features"].get(k) or 0) for k in NUM] for r in rows])
    X = np.column_stack([lp, ya, na, ya + na - 1, f])
    R = np.array([[0.0, r["reward_cents"]["yes"], r["reward_cents"]["no"]] for r in rows])   # pass, yes, no
    base = np.array([{"pass": 0, "YES": 1, "NO": 2}[r["side"]] if r["decision"] == "pick" else 0 for r in rows])
    return X, R, base, p, ya, na, np.array([r.get("y", 0) for r in rows])


def softmax(z):
    z = z - z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)


def train_policy(X, R, l2=1e-2, lr=0.05, epochs=400):
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = np.column_stack([(X - mu) / sd, np.ones(len(X))])
    W = np.zeros((Z.shape[1], 3))
    for _ in range(epochs):                       # maximize mean expected reward under the stochastic policy
        P = softmax(Z @ W)
        adv = R - (P * R).sum(1, keepdims=True)   # exact gradient: rewards of all actions are known
        W += lr * (Z.T @ (P * adv) / len(Z) - l2 * W)
    return lambda Xn: softmax(np.column_stack([(Xn - mu) / sd, np.ones(len(Xn))]) @ W).argmax(1)


def train_recal(X, y):
    from sklearn.linear_model import LogisticRegression
    m = LogisticRegression(C=0.5, max_iter=500).fit(X, y)
    def act(Xn, ya, na):
        q = m.predict_proba(Xn)[:, 1]
        ev = np.column_stack([np.zeros(len(q)), q - ya - np.vectorize(fee_pc)(ya), (1 - q) - na - np.vectorize(fee_pc)(na)])
        ev[:, 1:][ev[:, 1:] < 0.01] = -1          # same 1c minimum EV as live
        return ev.argmax(1)
    return act


def report(name, a, R):
    bets = a != 0
    tot = R[np.arange(len(R)), a].sum()
    return {"policy": name, "bets": int(bets.sum()), "pnl_cents_total": round(float(tot), 1),
            "pnl_cents_per_bet": round(float(tot / bets.sum()), 2) if bets.any() else None,
            "win_rate": round(float((R[np.arange(len(R)), a][bets] > 0).mean()), 3) if bets.any() else None}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--min-rows", type=int, default=300); a = ap.parse_args()
    rows = load()
    print(f"settled rows with both asks: {len(rows)}")
    if len(rows) < a.min_rows:
        print(f"not enough data yet (need {a.min_rows}); keep the engine running so the log grows"); return
    X, R, base, p, ya, na, y = matrix(rows)
    cut = int(len(rows) * 0.7)
    pol = train_policy(X[:cut], R[:cut]); rec = train_recal(X[:cut], y[:cut])
    res = [report("live rule (baseline)", base[cut:], R[cut:]), report("recalibrated + EV", rec(X[cut:], ya[cut:], na[cut:]), R[cut:]),
           report("policy gradient (RL)", pol(X[cut:]), R[cut:])]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "eval.json").write_text(json.dumps({"n_train": cut, "n_test": len(rows) - cut, "results": res}, indent=1))
    for r in res:
        print(r)


if __name__ == "__main__":
    main()

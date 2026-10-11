"""Merge pipeline + training outputs into docs/data/results.json (schema in CONTRACT.md)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(p):
    p = ROOT / p
    return json.loads(p.read_text()) if p.exists() else {}


lag = load("results/market_lag.json")
sweep = load("results/detector_sweep.json")
metrics = load("train/out/metrics.json")

overall = lag.get("overall", lag)
out = {
    "market_lag": {
        "median_s": overall.get("median_s", overall.get("median")),
        "p25_s": overall.get("p25_s", overall.get("p25")),
        "p75_s": overall.get("p75_s", overall.get("p75")),
        "n_plays": overall.get("n_plays", overall.get("n")),
        "by_type": lag.get("by_category", lag.get("by_type", {})),
    },
    "stream_delay_reference_s": {"broadcast": 19, "best_stream": 48, "worst_stream": 62},
    "games_analyzed": lag.get("games_analyzed", lag.get("n_games")),
}

rec = sweep.get("recommended_threshold")
row = next((r for r in sweep.get("sweep", []) if abs(r.get("threshold", -1) - (rec or -2)) < 1e-9), {})
out["detector"] = {"threshold": rec, "precision": row.get("precision"), "recall": row.get("recall"),
                   "n_alerts": row.get("n_alerts"), "median_delay_s": row.get("median_delay_s")}

real = {r["model"]: r for r in metrics.get("real_kalshi_test", [])}
sim = {r["model"]: r for r in metrics.get("sim_test", [])}
best_name = "xgboost_calibrated_on_kalshi" if "xgboost_calibrated_on_kalshi" in real else "xgboost_gpu"
best = real.get(best_name) or sim.get("xgboost_gpu", {})
base = real.get("rule_of_thumb") or sim.get("rule_of_thumb", {})
out["model"] = {
    "name": best_name, "accuracy": best.get("accuracy"), "top2": best.get("top2"), "log_loss": best.get("log_loss"),
    "baseline_name": "rule_of_thumb", "baseline_accuracy": base.get("accuracy"), "n_test": best.get("n"),
    "train_rows": metrics.get("train_rows"), "sim_test": metrics.get("sim_test"),
    "tested_on": "real Kalshi jumps (2026 season)" if real else "simulated jumps (2025-26 seasons)",
}
out["model_leaderboard"] = metrics.get("model_leaderboard", [])

(ROOT / "docs/data/results.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("market_lag", "detector", "model")}, indent=1)[:1500])

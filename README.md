# Kalshi Knows: the intelligence layer on top of prediction markets

**Team 4 · VSS New Member Hackathon · Sun Oct 11 2026** · Faisal Nabulsi, Kevin Huang, Dugar

Prediction markets know things before you do. Kalshi's price moves **~7 seconds** after a real NFL play; streams show it **48–62 seconds** after. Kalshi Knows reads Kalshi's public order book live, works out *what just happened*, and pushes it to your phone before your stream shows it. The same engine looks at two more time scales: prices that contradict each other right now (**Dutch Book**) and markets that moved before the news (**The market beat the headlines**), and an **auto-bettor** agent turns the signals into orders on Kalshi's demo exchange (play money). NFL is tonight's demo; the movers feed, Dutch Book, headlines scan and auto-bettor already work across all Kalshi categories.

## Links
| What | Where |
|---|---|
| **Live site (installable iPhone app)** | https://kalshi-knows.pages.dev (mirror: https://faisal-nabulsi.github.io/kalshi-knows/) · presenter view: add `?present=1` |
| **Demo video (2:26)** | GitHub release **[demo-video](https://github.com/faisal-nabulsi/kalshi-knows/releases/tag/demo-video)** → `kalshi-knows-demo.mp4` |
| **Training runs (W&B)** | https://wandb.ai/faisal_nabulsi-berkeley2025/kalshi-knows · consolidated results run: https://wandb.ai/faisal_nabulsi-berkeley2025/kalshi-knows/runs/g7xxxcch |
| **Every number, with definitions + sources** | [STATS.md](STATS.md) (use section 0 for slides) |
| **Slide plan (9 slides, 5 min) + Q&A** | [SLIDES.md](SLIDES.md) |
| **Demo script, what's proven on Kalshi's demo exchange, pre-flight checklist** | [DEMO.md](DEMO.md) · ledger: [results/demo_ledger.json](results/demo_ledger.json) |
| **What judges score → our evidence** | [JUDGING.md](JUDGING.md) |
| **Training plan + model choices** | [TRAINING.md](TRAINING.md) |
| **Market + competitor research (2 rounds, fact-checked)** | [research/BRIEF.md](research/BRIEF.md), [research/market.md](research/market.md), [research/features.md](research/features.md), [research/touts.md](research/touts.md), [research/ai-algos.md](research/ai-algos.md) |
| **5-reviewer critique (judge, bettor, fan, analyst, data)** | [research/REVIEW.md](research/REVIEW.md) |
| **Slide-ready charts (1600×900, dark)** | [results/charts/](results/charts/) |

## Headline results (all on games the model never trained on)
- **Speed:** Kalshi moves a median **7.0 s** after the real play (417 big plays, 66 games). Our live alerts land ~30 s after the play, i.e. **15–40 s before a streaming viewer sees it** (and 18–65 s before the same play appears in ESPN's public play-by-play feed). This is a spoiler / second-screen speed, not a trading edge: Kalshi itself has already moved.
- **Model:** pretrained on **28 seasons of NFL plays** (GPU), fine-tuned on **~8,800 real Kalshi price jumps** (2025 + 2026) with **audited labels** (we hand-checked 150, found 15% wrong, fixed the two bugs).
  - Live-size jumps, trained on 2025 → tested on 2026: **75.0% accuracy**; **~80% right when it names a play at ≥75% confidence** (audited labels; on the old labels the same model was 73.7% vs a 60.0% always-"nothing big" baseline — the audit mainly made the labels truthful, not the accuracy higher).
  - A smart sports fan (same inputs): **63%**, and 38% right when naming a play. Pretraining on 28 seasons is worth **+11 pts**.
  - **Head-to-head vs Claude Opus 5.5** (150 unseen jumps, same inputs): ties on accuracy (77.3% vs 76.0%), **better calibrated** (Brier 0.301 vs 0.354), 7 ms per call.
  - **Pre-registered test on today's games** (frozen pre-audit model, run once): primary (live-size jumps, n=32) +18.8 pts over baseline but the 95% CI (−13 to +33) includes zero, too small to conclude; across all jumps (n=113) named calls were **8 of 9** right.
  - **Live today:** named calls **4 of 4 right, 0 wrong**; every alert graded publicly on the site's Receipts (misses included).
- **Market efficiency:** we tested **1,255 pre-registered trading rules** (in-game, pre-game, cross-market lead-lag, Kalshi vs Polymarket, weather/injuries/spread): 11 passed the statistics, **0 survived adversarial review**. Post-jump prices are calibrated. Conclusion: the market digests plays in seconds; **the edge is speed**.
- **Dutch Book:** ~100k open markets scanned every minute: 16 arbitrages before fees, **0 after** (fees are Kalshi's moat).
- **The market beat the headlines:** 3 of 6 hand-checked cases moved ≥15 min before the earliest official source (best: Princeton's U.S. News ranking, ~6.8 h early).

## What's built
- `engine/`: live backend (FastAPI): Kalshi public order-book poller, jump detector, 2-stage play model, ESPN confirmation + graded receipts, iPhone Web Push (+ "confirmed" receipts), Spoiler Shield support, auto-bettor (rules engine, risk limits, kill switch, Ed25519-signed orders to Kalshi's **demo** exchange only), cross-market movers scanner, Dutch Book LP scanner, hang watchdog.
- `docs/`: the site/PWA (Live + Receipts, Headlines, Dutch Book, Proof, Predator Scale, Auto, Get alerts).
- `train/`, `pipeline/`: data pulls (ESPN + Kalshi trade tapes, 2025–26), training, audits, pattern hunt, context study.
- `video/`: the demo video pipeline (`video/render.sh` re-renders with current numbers).

**Rules we kept:** public data only; no real money; demo-exchange orders only; no politics in the UI; we show *when* a price moved, never *who*.

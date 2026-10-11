# Slide plan: Kalshi Knows (5-minute talk + 3-minute Q&A)

Built 1:50pm from STATS.md section 0, JUDGING.md, research/REVIEW.md and research/BRIEF.md. **Every number below is final unless STATS.md changes; don't use older numbers from elsewhere.**
Style: black background, bone/off-white text, ONE orange accent (#FF4D1A), big numbers, few words. Use the charts in `results/charts/`. QR to **https://kalshi-knows.pages.dev**.
Speaker: Faisal (talk + demo), Kevin (business slide), Dugar (clicker + backup video).

| # | Slide | On screen | Say (≈) | Judging criterion |
|---|---|---|---|---|
| 1 | **Title** (0:00–0:15) | KALSHI KNOWS · "the intelligence layer on top of prediction markets" · Faisal Nabulsi, Kevin, Dugar · QR | "Prediction markets know things before you do. We built the layer that reads them." | 5 |
| 2 | **The problem** (0:15–0:45) | Chart `a_kalshi_beats_your_stream.png`: Kalshi 7 s vs antenna 19 / cable 38 / Peacock 48 / YouTube TV 53 / NFL+ 62 (Super Bowl LX latency study) | "Kalshi's price moves about 7 seconds after a play. Your stream shows it 48 to 62 seconds after. Anyone live-betting off a stream is trading against people who already know, and every streaming fan gets spoiled by group chats." | 1 |
| 3 | **Who it's for** (0:45–1:05) | Three columns: Retail (streaming fans + prediction-market traders), Quants (latency + info-flow data), Exchanges/regulators (market-integrity monitoring) | "We don't compete with Kalshi. We're the analytics layer on top, starting with retail traders and fans." | 1, 4 |
| 4 | **LIVE DEMO** (1:05–2:35) | Switch to the site `?present=1`: Live board + Receipts → (wait ≤45 s for a buzz) → Auto page (auto-bettor on Kalshi's demo exchange + movers across every category) → if no live buzz, play the 38-second money-shot clip from the video | "Here's today. Every call is timestamped and graded against ESPN, misses included. When we named the play, we were right N of N." Then the Auto page: "The same signals drive an agent that places orders on Kalshi's demo exchange, play money, and it works on any market." Also point at the **Kalshi vs Polymarket panel** under the game tiles: "we watch both venues; Kalshi moves first". Backup slide: `results/charts/i_demo_ledger.png` (real demo orders + balance; refresh with `.venv/bin/python results/export_demo.py` at 3:45). | 2, 5 |
| 5 | **How it works** (2:35–3:15) | Diagram: Kalshi public order book → jump detector → play model (pretrained on 28 seasons of NFL plays, fine-tuned on ~8,800 real Kalshi jumps with audited labels) → push + live site + auto-bettor | "Two-stage model. The 28-season pretraining is the secret sauce: worth 11 points over a smart fan. We audited our own labels, found 15% were wrong, fixed them." | 2, 3 |
| 6 | **Results** (3:15–3:50) | Chart `h_model_vs_smart_fan.png` + a 3-row table: Smart fan 63% · Kalshi Knows 74–75% · always-"nothing" 50–60%; "When it names a play at 75%+: right ~80%"; "vs Claude Opus 5.5: ties on accuracy (77 vs 76%), better calibrated, 7 ms" ; "Pre-registered test on today's games: named calls 8 of 9" | "Tested on games it never saw, against a smart fan and against Claude." | 2 |
| 7 | **What the market taught us** (3:50–4:15) | "1,255 trading rules tested · 11 passed the stats · 0 survived our skeptics" · "Weather, injuries, spreads: already priced in" · "Dutch Book: 100k markets, 16 arbs before fees, 0 after" | "We tried hard to find a flaw. The market digests plays in seconds; the only edge is speed, and that's what we sell." | 3 |
| 8 | **Business** (4:15–4:45) | Free: spoiler alerts + Spoiler Shield + Receipts → **Pro ~$15/mo**: auto-bet rules + "market already moved" warnings + all markets → **B2B**: info-flow API, integrity monitoring ("the market beat the headlines": Princeton rankings moved ~6.8 h before the official release). Comps: Action Network PRO $24.99/mo, OddsJam $199+/mo | "Retail is the wedge, B2B data is the business." Proof it scales past NFL: the cross-market model trained on 4.36M settled Kalshi markets beats the raw market price on an unseen month (2.7% better Brier). | 4 |
| 9 | **Close** (4:45–5:00) | QR + "Public data only. No real money." | "Kalshi knows. Now you do too." | 5 |

## Demo rules (from research/REVIEW.md)
- Never depend on a live play: show alerts that already fired today first; wait at most 45 s for a fresh buzz; else play the money-shot clip without apologizing.
- At 3:45: presenter laptop shows LIVE (not REPLAY), Faisal's phone subscribed (`/api/health` subscribers ≥ 1), test push received.
- Backup: `video/kalshi-knows-demo.mp4` (2:26) if Wi-Fi dies.

## Q&A (crisp answers; details in research/REVIEW.md §3)
1. **"What's the real head start?"** Market ~7 s after the play; our first buzz ~15–25 s after (named call ~8 s later); streams 48–62 s → 25–45 s ahead of streams. An antenna (19 s) still beats us.
2. **"Beats ESPN how?"** Our alerts arrived 18–65 s before the same play showed up in ESPN's public play-by-play feed (conservative; we poll it every 4 s).
3. **"Which accuracy is real?"** Trained on 2025, tested on unseen 2026 games: 75% vs 47% always-"nothing" (audited labels, 511 jumps); named calls ~80% right. Pre-registered test on today's games: +19 pts over the baseline at live thresholds, named calls 8 of 9 (small sample, wide interval).
4. **"Half your buzzes aren't big plays?"** We only see what the market reacts to: stops and penalties swing it too. When unsure we say "big swing", and phones only buzz on confident calls.
5. **"Insider trading?"** We show *when* a price moved, never *who*. 3 of 6 hand-checked cases moved ≥15 min before the earliest official source.
6. **"Isn't this courtsiding?"** We warn bettors ("this market already moved"); the auto-bettor runs on Kalshi's demo exchange; public data only.
7. **"Who pays?"** Pro subscription for traders; B2B info-flow data and integrity monitoring for exchanges, quants and streamers.
8. **"What if the laptop dies?"** Watchdog restarts the engine in 20 s; the site falls back to a labelled replay; push fans out from one poller.

# Kalshi Knows: stats ledger (single source of truth)

Built Sun Oct 11 2026. Every number has a plain-English definition, n, and its source file. Charts are in `results/charts/` (script: `results/charts/make_charts.py`; cached inputs in `results/charts/data/`). Charts are also in W&B run `slide-charts` (https://wandb.ai/faisal_nabulsi-berkeley2025/kalshi-knows/runs/kgoeuzc4).

## 0. UPDATED 1:30pm: the numbers to use on slides (supersede older rows below where they conflict)

**Model accuracy, same plays for every model** (live-size jumps ≥0.08; CV = 5 folds grouped by game; "temporal" = trained on 2025, tested on 2026 games it never saw). Source: train/out/same_rows.json, train/out/relabeled_metrics.json.

| Model | Accuracy | Always-"nothing big" | Lift (95% CI, game-clustered) | Named calls at ≥75% confidence |
|---|---|---|---|---|
| Smart fan (state + price jump, logistic) | 62.8% | 60.0% | +2.8 (1.4–4.3) | 38% right (97 calls) |
| XGBoost without the 28-season pretraining | 70.0% | 60.0% | +9.9 (8.0–11.7) | 54% (69) |
| Pre-registered production model (old labels) | 73.7% | 60.0% | +13.7 (11.7–15.7) | 79.5% (200) |
| **Audited-label model, CV** (deduped jumps, n=2,641, 296 games) | **73.8%** | **49.8%** | **+24.0 (21.6–26.7)** (most of the lift change vs the old row comes from the baseline moving 60.0→49.8% once labels were fixed; lead with accuracy + named-call precision) | **80.5% (466)** |
| **Audited-label model, temporal 2025→2026** (n=511, 58 games) | **75.0%** | **47.0%** | **+28.0 (21.7–35.1)** | **76.6% (94)** |

**Head-to-head vs Claude Opus 5.5** (150 unseen 2026 live-size jumps, identical inputs, Claude zero-shot): Kalshi Knows 77.3% acc / log loss 0.513 / Brier 0.301 vs Claude 76.0% / 0.615 / 0.354 vs always-other 64.7%. Accuracy gap +1.3 pts (95% CI −7 to +11 → a tie); calibration directionally better (not significant at n=150); 7 ms per call. Source: train/out/claude_bench.json.

**Data audit** (150 jumps hand-labeled): 15.3% of automatic labels were wrong → 3.3% after fixes (turnovers on downs restored; each jump re-anchored to the play that caused it; penalty-nullified plays dropped). Source: train/audit/.

**What did NOT help (tested and dropped):** price-shape features (+0.1), contrastive-pretrained CNN (−1.6 live), multi-market features (totals ladder reacts slowly; TD ladder barely trades), game context (weather/field/spread/rest/injuries: −0.3 to −0.7, no better than placebo), LightGBM/CatBoost/TabPFN (±1–2). Sources: TRAINING.md, train/context/REPORT.md.

**Market efficiency (the "find a flaw" hunt):** 1,255 pre-registered trading rules tested (in-game, pre-game, lead-lag across Kalshi markets, Kalshi vs Polymarket, context): 17 passed discovery, 11 passed the out-of-sample test + false-discovery control, **0 survived adversarial review** (each died on look-ahead timing or stale-price fills). Post-jump prices are calibrated (slope 0.97). Kalshi moves before Polymarket by ~0–4 s after big plays. **Conclusion: the market digests plays in seconds; the edge is speed.** Source: train/patterns/REPORT.md.

**Live today (engine/logs/20261011, /api/health tally at 1:25pm):** 30 alerts; named plays 4 of 4 correct at 1:25pm — LATER: 4 of 7 by 2:59pm under swing-play grading (3 morning-model misses); 10 "big swing" alerts on a real play; 15 with no matching TD/FG/turnover/20+ yd play (stops, penalties, kickoffs); 1 pending. Best: "Steelers touchdown (80%)", 32 s before ESPN's feed; takeaways 38.6–64.8 s before.

**Pre-registered untouched test on today's early games (run once at 1:36pm; research/PREREG.md, results/today_test.json):** frozen model, 7 unseen games. PRIMARY live-size jumps: 65.6% vs 46.9% always-other (+18.8 pts, 95% CI −13 to +33; n=32, 6 games), named calls 2/2 correct. All jumps: 72.6% vs 61.1% (+11.5, CI −1 to +19; n=113), named calls 8/9 (89%). Same direction as offline; one morning is too small for a tight interval (primary CI includes zero). NOTE: this tested the frozen pre-audit model; production switched to the audited-label model afterwards.

**Works beyond NFL (cross-market model, train/xmarket/REPORT.md):** trained on 4.36M settled Kalshi markets (2021–Dec 2025, all categories), tested on an unseen month (Jan 2026, 70,249 markets): Brier 0.1236 vs 0.1270 for the raw market price (2.7% better, 95% CI 2.2–3.1%); gains largest 1 h before close and in Sports, Finance, Crypto, Entertainment. Paper strategy (model vs price gap ≥ 8 pts, 24 h out, after fees): +12.0% ROI (CI 6.5–17.8%, 1,603 bets) — ONE test month, last-trade fills, NOT adversarially reviewed (unlike the 1,255-rule hunt): suggestive only, do not pitch as an edge.

**Auto-bettor on Kalshi's demo exchange (play money):** real signed order placed and filled at 2:05pm — buy 1 YES "49ers win" at $0.39, fee $0.0167, order 01a12cc9-43b0-7d31-af6a-b259485bac52; mode = demo; rules: SF/SEA named call ≥80% → buy 5 YES on that team to win ($25/day cap, kill switch).

**Confidence tiers (Predator Scale) — how often the model names the play right when it's sure** (live-size jumps, games it never trained on; train/out/lagged_metrics.json + session log 3:20pm):

| Model / test condition | Tier 5+6 (≥80% sure): calls → right | Tier 6 (≥90%) | Tier 5 (80–90%) | Tier 4 (65–80%) |
|---|---|---|---|---|
| Audited model, exact game state, CV by game | 317 → **81.7%** | 24 → 83.3% | 293 → 81.6% | 445 → 72.6% |
| Audited model, exact state, trained 2025 → tested 2026 | 63 → **81.0%** | 5 → 5 of 5 | 58 → 79.3% | 80 → 72.5% |
| **Production (lag-robust) model, ONE-PLAY-LATE state (what live sees), CV by game** | 240 → **78.7%** | | | |
| **Production (lag-robust), one-play-late, trained 2025 → tested 2026** | 43 → **79.1%** | | | |

Slide line: **"When it's at least 80% sure, it names the play right about 4 times in 5 (79–82% across four tests on unseen games)."** This is calling what happened, not a betting win rate (post-jump prices are already fair; train/patterns/REPORT.md).

**Train/serve fix (3:20pm):** live ESPN state arrives ~one play late. Retrained on exact + one-play-late state (train/train_lagged.py). Under one-play-late conditions: accuracy 65.6% → **68.2%**, named-call precision 74.1% → **77.7%** (CV); temporal 65.2% → **68.7%**, 75.5% → **79.7%**. Stale-state naming gate relaxed 60 s → 180 s accordingly. Real-time Kalshi stream connected (production key, read-only guard) + detector config B: first buzz ~5 s after Kalshi moves (results/latency_study.md).

**Precision gate (3:30pm, live):** the app names a play only when it clears a per-type threshold chosen on 2025 for ≥80% precision (TD ≥74% confidence, turnover ≥86%; field goals / big plays never clear it → "big swing"). Verified once on unseen 2026 games under live (one-play-late) conditions: **26 of 30 named calls right (86.7%, game-clustered 95% CI 68–100%)**; turnovers **7 of 7**, touchdowns 83%; it names ~6% of live-size jumps. A 90% target is reachable only on ~1% of jumps (3 of 3 TDs), too rare to use. (train/precision_gate.py, engine/model/precision_gate.json)

**Platform scale:** Dutch Book scans ~100k open Kalshi markets every minute (16 arbs before fees, 0 after); movers feed tracks ~600 markets across categories; auto-bettor signs real orders for Kalshi's demo exchange (Ed25519, demo-only guard).

## 1. Speed: the market vs the play, the stream, and ESPN

| Number | Plain English | n / date | Source |
|---|---|---|---|
| **7.0 s** (6.97) | Median time from the real play (ESPN's play timestamp) to Kalshi's price moving halfway to its new level. Middle half of plays: 5.6 to 9.0 s. | 417 big plays (TD, FG, turnover, big play), 62 of 66 games, 2026 wk1-5 | results/market_lag.json |
| 6.2 / 6.6 / 7.1 / 7.4 s | Same median by play type: TD / FG / turnover / big play | n = 132 / 12 / 105 / 168 | results/market_lag.json |
| 6.84 s | Same, "clean" plays only (no other event nearby) | n = 354 | results/market_lag.json |
| 0% | Share of plays where the price moved BEFORE the ESPN timestamp (so no leak before the play) | 417 | results/market_lag.json |
| 98.3% | Share where the price moved in the direction of the right team | 417 | results/market_lag.json |
| 19 s / 48 s / 62 s | Reference delays: TV broadcast / best stream / worst stream behind live | reference values, not measured by us | market_lag.json `stream_delay_reference_s` |
| **38.6 / 50.4 / 64.8 s** | Today's live alerts: how many seconds before ESPN's own play-by-play feed showed the same play (our alert time vs the time our poller first saw the play in ESPN's feed) | 3 confirmed alerts of 5 so far, Oct 11 (MIN@NO, CIN@MIA, NYG@WSH; all turnovers) | engine/logs/20261011/alerts.jsonl (`confirmed.lead_s`) |
| 23.2 / 27.9 / 32.7 s | Today's live alerts: seconds after the real play (ESPN wallclock) that OUR ALERT fired | same 3 | alerts.jsonl (`confirmed.market_lag_s`) |
| 3 of 3 | Confirmed live calls with the right play type | 3 (2 more pending, no ESPN match yet) | alerts.jsonl (`inferred_correct`) |
| 15.5 / 19.2 / 13.7 s | Detector delay today: price starts moving to alert detected (confirmed alerts a_1, a_3, a_5) | 3 | alerts.jsonl (`detected_ms - jump_started_ms`) |

## 2. Detector (the thing that watches the price and fires)

Rule: price change of at least `thr` over 20 s, holding for 3 s, 60 s cooldown. Source: results/detector_sweep.json (66 games; match window -20 to +90 s around the ESPN play).

| Threshold | Alerts | Precision (strict) | Precision incl. high-leverage plays | Recall (TD/FG/TO) | Median delay |
|---|---|---|---|---|---|
| 0.05 | 1,133 | 41.4% | 73.9% | 38.6% | 11 s |
| **0.08 (live setting)** | **509** | **52.1%** | **85.9%** | **24.4%** | **12 s** |
| 0.10 | 297 | 58.6% | 88.6% | 16.3% | 12.5 s |
| 0.15 | 108 | 66.7% | 95.4% | 7.7% | 13 s |

Definitions: strict precision = share of alerts within 90 s of a real TD/FG/turnover/safety/big play. "Incl. high-leverage" also counts plays where ESPN win probability moved 5+ points (missed FG, 4th-down stop). Recall = share of TD/FG/turnovers that got an alert. 0.08 was chosen as the lowest threshold with 85%+ precision incl. high-leverage.

## 3. Play-type model accuracy (what happened, given a price jump)

Classes: TD, FG, turnover, safety, big play, OTHER ("nothing special"). Training: 244,434 simulated jump rows from nflverse play-by-play, seasons 1999-2023 (train/out/metrics.json), tuned in a 20-trial XGBoost sweep on an AWS L40S, then adapted to real Kalshi price paths.

### 3a. Held-out simulated test (2025-26 seasons, simulated jumps) - train/out/metrics.json `sim_test`
| Model | Accuracy | Top-2 | Log loss |
|---|---|---|---|
| **XGBoost (GPU)** | **85.9%** | 98.6% | 0.339 |
| Neural net (GPU) | 85.1% | 98.5% | 0.361 |
| Logistic regression | 74.9% | 95.5% | 0.655 |
| Always "OTHER" | 70.7% | 81.2% | 0.993 |
| Rule of thumb ("sports fan") | 17.0% | 23.7% | 3.265 |

### 3b. Real Kalshi big-play jumps (n=417, 62 games, no OTHER class in this set; 5-fold CV by game) - train/out/metrics.json `real_kalshi_test`
| Predator Scale tier | Model | Accuracy | Top-2 | Log loss |
|---|---|---|---|---|
| Kevin & Faisal | **XGBoost + calibrated on Kalshi** | **89.7%** | 97.6% | 0.301 |
| Lion | Logistic on Kalshi data only | 72.2% | 90.9% | 0.761 |
| Everyone Else | Neural net (sim only) | 62.8% | 94.2% | 0.920 |
| Gazelle | XGBoost (sim only) | 58.8% | 93.3% | 0.937 |
| House Cat | **Smart sports fan rule of thumb** | 60.0% | 83.5% | 1.630 |
| Dugar | Always guess OTHER | 0.0% | 40.3% | 2.467 |

Tiers are ranked by log loss, which is why Gazelle (58.8%) sits above House Cat (60.0%) by name but below it by accuracy.
Sports-fan rule of thumb (`train/eval_real.py`): price rises for the team with the ball = TD if the jump is 10+ points, else big play; price falls = turnover.

### 3c. Realistic mix: everything the detector fires on, including OTHER (n=1,596 fires, 64 games, 5-fold CV by game) - train/out/finetune_metrics.json
Labels: OTHER 1,032 (64.7%), big play 229, TD 182, turnover 119, FG 34.
| Model | Accuracy (all fires) | Accuracy (live 0.08 subset, n=569) | Log loss |
|---|---|---|---|
| **Stack XGBoost (production)** | **76.3%** | **71.5%** | 0.580 |
| Calibrated stage 1 | 74.8% | 68.7% | 0.604 |
| Warm-started XGBoost | 74.6% | 69.9% | 0.611 |
| Stage 1 raw (sim only) | 72.9% | 66.6% | 0.724 |
| Always say OTHER (our recompute) | 64.7% | 57.1% | n/a |
| Sports-fan rule (our recompute; it never says OTHER) | 19.8% | 24.3% | n/a |

Top-2 accuracy of the production model: 96.4%. Baseline rows marked "our recompute" were computed on Oct 11 with the same fires and are not in the JSON file (script: results/charts/data/compute_preds.py). The 76.3% was reproduced exactly.

### 3d. Confidence (production model, CV, results/charts/data/preds.json)
| Model says | Right (all 1,596 fires) | Right (417 big plays) |
|---|---|---|
| under 50% | 41% (n=75) | 25% (n=4) |
| 50-70% | 62% (n=398) | 60% (n=42) |
| 70-90% | 72% (n=496) | 83% (n=78) |
| **90%+** | **93% (n=627)** | **97% (n=293)** |

Per-class recall on the 1,596 fires: TD 70%, FG 65%, turnover 66%, big play 48% (45% of big plays get called "nothing special"), OTHER 85%. On the 417: TD 83%, FG 83%, turnover 95%, big play 92%.

### 3e. Training and sweep (W&B project faisal_nabulsi-berkeley2025/kalshi-knows)
- 20 XGBoost trials (group xgb-sweep) on an L40S: best validation log loss **0.3432** (trial-01, 617 rounds, depth 9, lr 0.048); worst 0.3469. Spread 0.0037.
- MLP 256x256x128: best validation log loss 0.3632 (40 epochs).
- Comparison run `real-kalshi-test-2026` holds the tables behind 3b. The stage-3 fine-tune (3c) was NOT logged to W&B (no run found).

## 4. SOMEONE KNEW (docs/data/someone_knew.json, generated Oct 11)
5 settled non-political markets screened (from 763 scanned); the price moved before the first news article in 80% (4 of 5); median lead 398.5 min (6.6 h). Top case: Adam Driver X-Men cast, price 0.65 to 0.97, 564 min (9.4 h) before the first article.

## 5. DUTCH BOOK (docs/data/dutchbook.json, updated Oct 11)
| Number | Meaning |
|---|---|
| 9,050 events / 103,807 markets | Scanned (all 16 categories) |
| 65 | "Near misses" listed (positive before fees on paper) |
| 49 | Of those, "fake": the outcome list is not exhaustive, so not an arbitrage |
| **16** | Real candidates (7 bracket-sum, 6 ladder, 3 exhaustive-set) with profit before fees; all 16 positive before fees |
| **0** (strictly) | Survive fees at $0.01 or more. Two ladders show +$0.003 after fees (rounding noise). `opportunities` list is empty, `total_mispricing_usd` = 0 |

## 6. INCONSISTENCIES AND CAVEATS (read before presenting)

1. **Alerts do NOT beat the TV broadcast.** Today's alerts fire 23-33 s after the real play; the broadcast is 19 s behind. They beat ESPN's feed (by 39-65 s) and the 48-62 s streams (by roughly 15-39 s), but not cable. The market itself (7 s) does beat the broadcast by 12 s. The gap between 7 s market lag and 23-33 s alert lag is detector delay (about 12-19 s, today's alerts 13.7-19.2 s) plus the 8 s call delay in finetune_real.py. Say "beat streams and ESPN", not "beat TV".
2. **The 38.6/50.4/64.8 s lead is vs ESPN's feed as seen by our poller** (`espn_seen_ms`), so it depends on our poll timing. It is not a lead over a TV stream. Only 3 of 5 alerts confirmed; a_2 (LV@NE TD) and a_4 (CLE@NYJ big play) are still `confirmed: null`.
3. **Games: 66 vs 62 vs 64.** market_lag.json says 66 games, but the 417 plays come from 62 games (metrics.json `real_games`, and our recompute); the 1,596 fires come from 64 games. Use "66 games analyzed, 417 plays from 62".
4. **Two different accuracy headlines.** 89.7% (417 big plays, no OTHER) vs 76.3% (1,596 fires with OTHER; 71.5% at the live 0.08 threshold). The honest live number is 71-76%. Always say which.
5. **"Always say OTHER" scores 64.7% on the realistic mix**, so 76.3% is +11.6 points over lazy, and the sports-fan rule (19.8%) looks bad partly because it never says OTHER. On the 417-play set (no OTHER) the fan rule gets 60.0%.
6. **Training size: 244,434 (metrics.json `train_rows`) vs 733,302 (W&B sweep config).** The ratio is exactly 3.0, so the sweep likely used 3 simulated jumps per play. SLIDES.md says "[~1.2M plays]" and "28 seasons": the train seasons are 1999-2023 (25 seasons); 28 only counts if you include the 2024 validation and 2025-26 test seasons. train_playinfer.py docstring says 2016-2023 (default, overridden by `--start`). Use "25 seasons for training, 28 in total" and 244k rows.
7. **docs/data/results.json has `games_analyzed: null` and detector `median_delay_s: null`** although detector_sweep.json has 66 games and 12.0 s. build_results.py reads keys that do not exist (`games_analyzed`, `n_games`); fix to `lag["games"]` and the sweep row.
8. **SLIDES.md says "2 case files" for Someone Knew; the JSON has 5 cases.**
9. **SLIDES.md "16 arbitrages before fees, 0 after"** matches the data only with the $0.01 cutoff (two ladders at +$0.003). The count of 49 fake lists matches.
10. **Sim-test rule-of-thumb is 17.0% but real-test is 60.0%** because the sim test includes the OTHER class (70.7% of rows) which the rule never predicts. Do not compare them side by side.
11. W&B has no stage-3 fine-tune run, and the engine log `infer_source` is "heuristic" for a_1 and a_2 (model for a_3-a_5): the first two live alerts used the fallback, not the model.

## Ten headline numbers
1. Kalshi's price moves a median **7.0 s** after the real play (417 plays, 62 games).
2. Today's alerts beat ESPN's play feed by **38.6 / 50.4 / 64.8 s** (3 confirmed, all right).
3. Streams are **19 s (TV) to 48-62 s (streams)** behind live; alerts arrive 23-33 s after the play.
4. Play-type accuracy on 417 real big plays: **89.7%** vs **60.0%** for the sports-fan rule.
5. Realistic mix incl. "nothing special" (1,596 fires): **76.3%** (71.5% at the live threshold) vs 64.7% always-OTHER.
6. When the model says 90%+, it is right **93%** (all fires; 97% on big plays).
7. Held-out simulated seasons 2025-26: XGBoost **85.9%**, log loss 0.339.
8. Detector at 0.08: **509 alerts, 52.1% strict precision (85.9% incl. high-leverage), 24.4% recall, 12 s delay.**
9. 20-trial GPU sweep: best validation log loss **0.3432**, all 20 within 0.0037.
10. Dutch Book: **103,807 markets, 16 contradictions before fees, 0 after**; 49 fake "free money" lists.

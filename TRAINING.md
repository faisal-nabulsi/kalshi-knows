# Training plan: the play inverter

**Task.** When Kalshi's win-probability price for an NFL game jumps, say *what just happened* (TD / FG / turnover / big play / other) before your stream shows it. Inputs are only what we know at call time: the game state before the play, the price path, and other same-game markets. Labels come from ESPN's play-by-play.

**Why this model family.** The data is a small table (thousands of rows, ~20–30 features), not text or images, so an LLM has nothing to read at call time.
- **Gradient-boosted trees** are the standard winner on tables like this (Grinsztajn et al., NeurIPS 2022: "Why do tree-based models still outperform deep learning on tabular data?").
- **TabPFN v2** is a transformer pretrained on millions of synthetic tables that predicts in a single pass. It's state of the art for tables under ~10k rows (Hollmann et al., *Nature* 2025).
- **We tested instead of assuming:** XGBoost, LightGBM, CatBoost, TabPFN, a self-supervised 1D-CNN (contrastive), and ensembles, all on the identical split.

## Data at each step
| # | Data | Size | Used for |
|---|---|---|---|
| D1 | **nflverse play-by-play 1999–2026**: every NFL play, with game state and a market-style (Vegas-adjusted) win probability before and after | ~1.2M plays; 244k with a ≥3-pt win-prob swing | Stage 1 pretraining: learns what each play type does to win probability in each situation |
| D2 | **Kalshi 2026 trade tapes** (weeks 1–5), millisecond trades aligned to ESPN play timestamps | 66 games → 2,800 windows → 1,596 detector fires | Stage 2 fine-tuning on real market behavior |
| D3 | **Kalshi 2025 season** (regular season + playoffs), same format | pulling now (latest games first) | More stage-2 data (the biggest lever: the model bake-off showed data, not model, is the bottleneck) |
| D4 | **Same-game Kalshi markets**: total-points ladder (`KXNFLTOTAL`), total-TDs ladder (`KXNFLTOTALTD`), anytime TD scorer (`KXNFLANYTD`) | pulling now | New features: market-implied points added (~7 TD, ~3 FG, ~0 turnover) and TDs added (~1 TD); scorer name |
| D5 | **Today's 8 live games**, logged by our own engine from the live order book | ~8 games | Final untouched test set (never used to pick anything) |

## Pipeline
1. **Stage 1, pretrain (AWS L40S, ~5 min).**
   - Model: XGBoost on D1 with simulated market jumps (win-prob change × U(0.8, 1.2) + noise). Seasons ≤2023 train, 2024 validation, 2025–26 test. 20-config random sweep, early stopping. Logged to W&B (`xgb-sweep`).
   - Result: 85.9% accuracy (top-2: 98.6%) on held-out seasons, vs 70.7% for always guessing the most common class.
2. **Stage 2, fine-tune on real market data (Mac, minutes).**
   - We run the **same jump detector as the live engine** over every real window, so the training rows match what happens live. Features come only from data available at call time:
     - stage-1 log-probabilities
     - game state
     - move-shape features (change over the last 4/10/20/40 s, pre-move volatility, fastest step, trade burst)
     - + D4 multi-market features
   - Candidates: calibration only, warm-start boosting, a stacked XGBoost, + contrastive embeddings, LightGBM, CatBoost, TabPFN, ensembles.
   - Evaluation: **GroupKFold(5) by game**, so no game is ever in both train and test. Selection is on the **live regime** (jumps ≥0.08), not the training mix.
3. **Call timing.** Call the play **8 s after the jump**: +2.7 points of live accuracy for 8 s of a 30–55 s lead (0 / 4 / 8 / 14 s were tested).
4. **Confidence gate.** Name the play type only when the model is ≥75% sure (83–87% accurate there). Otherwise push "Big swing to the 49ers".
5. **Final test.** D5 (today's games), run once, reported as is.

## Results so far (all real Kalshi data, CV by game; details in STATS.md and W&B)
| Model | All fires | Live regime (≥0.08) | Live, when ≥75% sure |
|---|---|---|---|
| Always "OTHER" | 64.7% | 57.1% | – |
| Stage 1 only (sim-trained) | 72.9% | 66.6% | – |
| Calibrated stage 1 | 74.8% | 68.7% | – |
| Stacked XGBoost (+ move shape) | 76.3% | 71.5% | 83.4% |
| + contrastive CNN embeddings | 76.2% | 69.9% | – (no gain: dropped) |
| CatBoost | 76.4% | 72.6% | 81.7% |
| TabPFN v2 (GPU run) | 78.3% | 74.0% | 87.5% |
| **TabPFN + XGBoost ensemble (GPU run)** | **78.4%** | **75.0%** | **87.2%** |

GPU-run XGBoost scores slightly differently from the Mac run (73.1% live) because of library versions.

Conditional on the play being a TD/FG/turnover/big play (no "other"), the calibrated model is 89.7% (n=417; the "given it was a scoring/turnover/big play" view).

## Not used, and why
- **LLM fine-tuning (SFT) / RL:** there is no text at call time, and the labels are exact. RL fits sequential decisions with delayed rewards; the only decision here (when to alert) has 2 settings, so a grid search covers it exactly.
- **Contrastive pretraining:** tried (SimCLR 1D-CNN on 53k unlabeled windows). No gain over the move-shape features in the live regime; kept as a logged experiment.

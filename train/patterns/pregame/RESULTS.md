# Pre-game and schedule patterns (KXNFLGAME, 2025 discover / 2026 wk1-5 test)

**Bottom line: 0 survivors out of 19 cells tested.** No pre-game or schedule rule passed discovery on 2025 with n >= 30, ROI > 0 and one-sided p < 0.05, so nothing was promoted to a real 2026 test. Kickoff prices are well calibrated and the hourly price path adds no information after the price three days out. Pre-registration: PREREG.md (written before outcomes were joined; three small deviations are logged at its bottom).

## Data
- 281 2025 games (discovery) and 66 2026 weeks 1-5 games (test) with a Kalshi hourly candlestick path from market open to kickoff (home-team YES market). 2025 via /historical/markets/{t}/candlesticks, 2026 via /series/KXNFLGAME/markets/{t}/candlesticks. One 2025 game had no outcome and ties are dropped.
- "Kickoff price" P_k = last candle ending at or before kickoff minus 1 hour. Median hourly volume in that candle: 82k contracts (2025), 70k (2026); minimum 2.7k. Median bid-ask spread: 1 cent. So size is not a constraint at 100 contracts (all trades passed the >=500 volume check).
- Trades: buy at the real ask at kickoff-1h (home YES at yes_ask, away YES at 1 - yes_bid), 100 contracts, hold to settlement, fee ceil(0.07*C*P*(1-P)) per order. Game-clustered bootstrap, 5,000 draws.
- Polymarket (added at the user's suggestion): Gamma slug nfl-{away}-{home}-{date} plus CLOB hourly price history; 344 of 347 games matched (token 0 = away team, corr with Kalshi home price -0.999). PrizePicks has no public API and is a player-prop product, so it was not used.
- Files: games_table.csv, cells.csv, reliability.csv, desc.txt, analyze.py, pull_candles.py, pull_pm.py.

## Kickoff calibration (descriptive)
| Season | n | logit slope [95% CI] | Brier P_k | Brier P_open (first traded hour) |
|---|---|---|---|---|
| 2025 | 281 | 0.957 +- 0.310 | 0.2130 | 0.2316 |
| 2026 wk1-5 | 66 | 0.693 +- 0.676 | 0.2324 | 0.2591 |
| pooled | 347 | 0.914 +- 0.280 | 0.2167 | 0.2368 |

Slope 1 and intercept 0 are inside every CI, so kickoff prices are calibrated. Favorite-side reliability, 2025: price 0.5-0.6 -> won 55.7% (n=88, priced 55.6%); 0.6-0.7 -> 58.1% (n=86, priced 65.2%); 0.7-0.8 -> 70.6% (n=68, priced 75.5%); 0.8-0.9 -> 94.3% (n=35, priced 85.7%). 2026: 56.5% / 65.0% / 68.8% / 66.7% (n=23/20/16/6). The 0.6-0.8 favorites underperformed in 2025 (-3.5 to -9 points, ROI -12% for 0.65-0.80, CI [-24%, -0.3%]), and in 2026 the 0.65-0.80 cell was also negative (ROI -9.5%, hit 66.7% vs priced 72.3%, n=27, CI includes 0), so the sign persists but is not significant, and 0.8+ favorites did the opposite. No stable longshot bias.

**Slow incorporation?** No. Brier of the price 72 h before kickoff (0.2124) and 24 h before (0.2126) is the same as at kickoff (0.2130). Only the very first traded hour is worse (0.2316), i.e. information is absorbed within the first days after the opening quotes, not drip-fed toward kickoff. Logistic regression of the result on logit(P_k) and the drift logit(P_k) - logit(P_open): drift coefficient -0.006 +- 0.381 (2025), 1.47 +- 1.49 (2026), pooled 0.10 +- 0.37. The drift carries no extra information once P_k is known. Of 261 games with |drift| >= 0.03, the drift side won 59.4%, about the average price paid (58%).

## All 19 cells (net of fee, paid at the ask, ROI = P&L / cost)
Survive = passes 2025 gate, 2026 ROI > 0, and BH q=0.10 over all 19 cells (cells that failed discovery get p=1 in 2026, which is conservative).
| cell | rule | n25 | ROI25 [95% CI] | p25 (1-sided) | n26 | ROI26 [95% CI] | passed 2025 gate | survive |
|---|---|---|---|---|---|---|---|---|
| C1 | follow open->kickoff drift (>=3c) | 213 | -4.4% [-14.9, 6.0] | 0.79 | 48 | +15.1% [-6.1, 35.5] | no | no |
| C2 | fade that drift | 213 | -3.0% [-16.9, 11.2] | 0.67 | 48 | -29.4% [-56.8, -0.8] | no | no |
| C3 | fade midweek move (T-72h to T-24h, >=4c) | 16 | -17.1% | 0.72 | 1 | n/a | no (n<30) | no |
| C4 | follow gameday move (T-24h to T-1h, >=2c) | 88 | -6.2% [-24.9, 12.9] | 0.73 | 6 | +8.3% | no | no |
| C5 | fade gameday move | 88 | -1.2% [-22.6, 20.8] | 0.55 | 6 | -14.0% | no | no |
| C6a | buy favorite priced 0.50-0.65 | 131 | -3.5% [-17.7, 10.6] | 0.68 | 33 | +0.7% | no | no |
| C6b | buy favorite 0.65-0.80 | 105 | -12.1% [-24.2, -0.3] | 0.98 | 27 | -9.5% | no | no |
| C6c | buy favorite >=0.80 | 45 | +3.1% [-7.5, 12.7] | 0.25 | 6 | -21.8% | no | no |
| C7 | buy home | 281 | -5.3% [-14.7, 4.2] | 0.87 | 66 | -5.4% | no | no |
| C8 | buy away | 281 | -2.1% [-13.4, 9.4] | 0.63 | 66 | -1.9% | no | no |
| C9 | divisional: buy underdog | 98 | +14.8% [-14.3, 44.3] | 0.154 | 17 | +35.9% | no | no |
| C10 | primetime: buy underdog | 67 | +17.4% [-16.4, 51.8] | 0.150 | 14 | +48.6% | no | no |
| C11 | short rest (<=6 d, opp >= +3 d): buy opponent | 4 | +60% | - | 0 | n/a | no (n<30) | no |
| C12 | Pac/Mtn away at 13:00 ET Eastern/Central home: buy home | 31 | -19.1% [-49.1, 10.0] | 0.90 | 4 | +62.3% | no | no |
| C13 | outdoor, away dome team: buy home | 69 | +7.1% [-11.7, 26.2] | 0.23 | 17 | +7.8% | no | no |
| C14 | buy road favorite | 115 | -4.7% [-17.9, 7.8] | 0.78 | 23 | -5.8% | no | no |
| C15 | buy home underdog (P_k < 0.5) | 115 | -2.6% [-25.6, 22.1] | 0.59 | 23 | -1.1% | no | no |
| C16 | buy on Kalshi the side Polymarket rates higher (diff >= 3c) | 0 | - | - | 0 | - | no | no |
| C17 | buy the side Polymarket rates lower | 0 | - | - | 0 | - | no | no |

Notes
- Tested count: 19 cells x 2 seasons evaluated (38 cell-seasons); 0 cells passed discovery; 0 survivors. BH on 2025 p-values alone also leaves nothing valid (C11 flagged only because n=4 with p=0, which fails the n >= 30 rule). PREREG.md says m=17 because it lists C6 as one row; C6 has three cells, so m=19.
- Underdog cells C9/C10 are the only mildly interesting ones (+15% / +17% in 2025, both with CIs spanning zero, p about 0.15; 2026 on 17 and 14 trades is +36% / +49%, also noisy). Those are the cells to extend with more seasons (2024, 2023 via the same historical candlestick endpoint) before anyone believes them: the sign agrees across seasons but neither is significant, and 2 of 19 cells looking positive is what chance gives.
- Polymarket and Kalshi kickoff prices agree to within 0.8 cents on average (max 2.5c, 77 of 346 games differ by >= 1.5c, 7 by >= 2c, 0 by >= 3c), so the cross-market convergence trade has no qualifying trades at the pre-registered 3c threshold, and at 2c fees plus the 1c spread would consume it.
- 2026 has only 66 games, so a real edge below about 20% ROI could not be detected in 2026 alone. That is a power limit, not evidence of no edge, but nothing reached the 2026 stage anyway.
- Caveats: P_open (first traded hour) can be a thin, early quote; C3/C11 had too few qualifying games (16 and 4); C12 had 31; liquidity is inferred from candle volume, not book depth; ESPN kickoff time is the schedule time.

## Deviations from PREREG (all logged there before outcomes were joined or were pure code fixes)
C15 defined by P_k < 0.5 instead of spread sign; snapshot price falls back to bid/ask mid; candle window 120 days before kickoff; C9 code bug (silent 0 trades) fixed after first run, no definition changed.

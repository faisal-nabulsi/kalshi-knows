# Lead-lag across related Kalshi markets (in-game): results

Written 2026-10-11 after running the protocol in PREREG.md (committed first, e93a2cc). Code: desc.py, backtest.py, analyze.py, explore.py. Per-cell table: cells.csv. Every trade: trades.parquet.

## Bottom line
- Tested **25 cells** (pre-registered). Discovery wk1-3 (48 games), single test wk4-5 (18 games), Benjamini-Hochberg q=0.10 over all 25, net of the Kalshi taker fee, buy at last trade +1c.
- **4 cells survive**, all the same idea: **right after an ESPN-labelled TD, buy "Over" on the total-points ladder at the strike nearest 50% and sell 60 or 120 s later.** Test ROI after fees: median strike +15.4% (60 s) / +16.6% (120 s); one strike lower +9.6% / +10.6%. CIs exclude zero.
- **Big caveat: the edge exists only if you know it is a TD within ~6-10 s of the play.** The label comes from ESPN's play-by-play (available after the fact), so these are "oracle-label" cells. The label-free version (any win-price jump) loses money. The edge is gone by 15-20 s of delay (table below). Do not call this a deployable edge until a classifier shows it can name TDs at +6-10 s.
- Hold-to-settlement versions look better on point estimates (+26%) but do not survive (p=0.067 / 0.034 not BH-significant at m=25, and the bootstrap CI includes 0). Over-settlement is also confounded with the total ladder simply being low in these weeks (the label-free S1 and S2 Over settle cells are also positive, +1% to +21%).

## Descriptive lead-lag (not tests; desc.py, 2026 wk1-5, 66 games)
Median move after the play, scoring-team sign. wp = win-price change, pts = change in market-implied points (6 strikes nearest the median).
| Play | n | wp +10s | wp +30s | pts +10s | pts +30s | pts +120s | half-adjust wp / pts (median per window) |
|---|---|---|---|---|---|---|---|
| TD | 339 | +0.03 | +0.04 | +0.29 | +0.77 | +1.11 | 8 s / 14 s |
| FG | 226 | +0.01 | +0.01 | +0.03 | +0.09 | +0.05 | 6 s / 10 s |
| Turnover | 145 | -0.05 | -0.07 | -0.01 | -0.03 | -0.08 | 10 s / 24 s |
| Big play | 381 | +0.03 | +0.05 | +0.04 | +0.37 | +0.51 | 10 s / 18 s |
Cross-correlation of 2 s changes (win price vs implied points): peak at lag 0-2 s (0.14), 0.10 at 4 s, 0.05 at 6 s, ~0 after 10 s. So the total ladder trails the winner market by roughly **2-6 s**, and finishes adjusting about 6-8 s later than it. The 120 s drift (+1.1 pts after TD) is partly later plays in the same window, so the cross-correlation is the cleaner lag estimate: the lag is seconds, not minutes. The earlier "+1.4/+1.8/+2.2 pts" hint is not reproduced as a pure lag (our median is +0.77/+0.98/+1.11).

## Tradable cells (25), discovery -> test (ROI net of fees; fill = share of signals with a quoted strike and >=5 contracts)
Signals: S1 = win-price detector 0.05, S2 = detector 0.08, S3 = ESPN TD label (oracle) at play+6 s, S4 = FG label, S5 = turnover label (buy Under). Ladder TOT = total points (median size 100 contracts, fill 93-100%); TD = total-TD ladder (fill only 9-13%, median 35-44 contracts).
| Cell | disc n | disc ROI | test n (games) | test ROI [95% CI] | BH |
|---|---|---|---|---|---|
| **TOT S3 M0 +120 s** | 242 | +15.4% | 92 (18) | +16.6% [+11.3, +22.8] | survives |
| **TOT S3 M0 +60 s** | 242 | +12.6% | 92 | +15.4% [+10.3, +21.5] | survives |
| **TOT S3 M-1 +120 s** | 229 | +9.2% | 88 | +10.6% [+7.6, +14.4] | survives |
| **TOT S3 M-1 +60 s** | 229 | +7.1% | 88 | +9.6% [+6.5, +13.4] | survives |
| TOT S3 M0 settle | 242 | +31.7% | 92 | +26.2% [-9.4, +54.7] | p=.067, no |
| TOT S3 M-1 settle | 229 | +20.8% | 88 | +19.6% [-1.7, +36.6] | p=.034, no (BH threshold) |
| TD ladder S3 +120 s | 43 | +14.0% | 0 (no test fills) | n/a | no |
| TD ladder S3 settle, S1 both exits | <=74 | <=+9% / negative | - | - | failed discovery |
| TOT S1 (any jump) all exits/strikes | 496-587 | -2.8% to -6.2% (60/120 s), +4.5 / +9.2% (settle) | 245-275 | -4.8% to -6.1% (60/120 s) | fail discovery on 60/120 s; settle fails p<.10 |
| TOT S2 (jump>=0.08) all exits | 258 | -7.3% / -6.0% / +1.0% | 109 | - | failed |
| TOT S4 (FG) all exits | 159 | -8.2% / -7.7% / -1.7% | 65 | - | failed |
| TOT S5 (turnover, Under) all exits | 105 | -1.6% / -1.9% / +7.1% | 40 | - | failed (p>.27) |
Full numbers for all 25 in cells.csv (test columns for failed-discovery cells are shown for transparency only and were not used).

## Execution realism
- Entry = last trade at that strike (must be within 120 s) +1c; size = contracts traded at that strike in [-60 s, +30 s] around entry, capped at 100, min 5. The central strikes are deep (hundreds of thousands of contracts per game) so 100 contracts fills at 93-100% of signals. Tails (strikes >=11.5 away from median) are thin.
- Exit price = last trade -1c at the strike at +60/+120 s, fee on both legs. Last-trade prices are not the book; a real ask could be wider than +1c at the instant after a TD when quotes are being pulled. Sensitivity to wider spreads was not run.
- The total-TD ladder is thin (a few trades per game): 9-13% fill, so the cell has too few test fills.
- Overlapping windows deduped (60 s). 18 test games, 92 TD events: low power and one season-slice (wk4-5).

## Post-hoc delay sensitivity (exploratory, NOT in the 25-cell family; explore.py)
Same TD-Over M0 rule, entry delayed after the play; ROI net of fees, test wk4-5 / discovery wk1-3, exit +120 s:
| Delay after play | wk1-3 | wk4-5 |
|---|---|---|
| 6 s | +15.4% | +16.6% |
| 10 s | +9.1% | +9.7% |
| 15 s | +2.7% | +2.7% (CI includes 0) |
| 20 s | +1.8% | -2.7% |
| 30 s | -3.7% | -4.9% |
The edge is a ~10 s window. Any real implementation needs TD recognition, then order submission, inside about 10 s of the play. The earlier call-timing work chose 8 s for accuracy; the two goals conflict.

## Not covered
- Spread ladder KXNFLSPREAD: exists on the public API for 2026 games (27 markets per game, trades endpoint works), but it is the same information as the moneyline; at 1.5 req/s a full pull of 66 games x 27 markets is about an hour, so it was not pulled. Expected: it adjusts with the winner market (seconds).
- Anytime-TD scorer (KXNFLTD): a scorer's price jump is a label-free TD detector that might fire within seconds. Not preregistered so not tested; this is the natural next step (use "a scorer contract jumps >=0.5" as the real-time TD signal in place of the oracle label).
- Polymarket (CLOB public price history is 1-minute resolution at best, too coarse for a 10 s lag) and PrizePicks (no public historical API, and lines are static-ish pregame props): not tested. 
- Today's games file (real_windows_today_mm.parquet) did not exist at run time, so no untouched live test.
- The 2025 season has no total-points ladder on disk, so no 2025 confirmation.

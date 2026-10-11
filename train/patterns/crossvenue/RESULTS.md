# Cross-venue (Kalshi vs Polymarket) results

Pre-registered in PREREG.md (written before any cross-venue comparison). Code: pull_poly.py (data pull), analyze.py (everything else). Raw numbers: results.json, cells.csv, analysis_output.txt.
Discovery on 2025 (281 games), one test on 2026 (66 games, weeks 1-5). **15 cells tested.** BH q=0.10 on the 2026 p-values over all 15. Game-clustered bootstrap (5,000 draws).

## Bottom line
- **No tradable edge survives.** Kalshi moves first, but only by a few seconds, and following it onto Polymarket (F1/F2) loses money in 2026 after fees. Buying the cheaper venue (C1-C3) is noise. The "locked arbitrage" cells (A1-A3) pass the pre-registered gates but are a stale-price artifact: they flip to a loss as soon as the second leg is delayed 10 s.
- **Lead-lag is real and robust in direction:** Kalshi moves before Polymarket in 87% (2026) to 92% (2025) of big-play jumps. Size: median 2 s in 2026 (CI 2-3 s), median 9 s in 2025 (CI 8-10 s). The 2026 figure sits at the resolution limit of both series (Polymarket median gap between trades is 2 s; Kalshi bins are 2 s), so read it as "Kalshi leads by roughly 0-5 s". The 2025-vs-2026 difference is not explained (could be Polymarket data-api timestamps or liquidity changes in 2025); do not pool.
- Polymarket and Kalshi agree on level: Polymarket-home vs Kalshi-home correlated (all 347 games had correlation > 0.5, no orientation flips). Gaps between last trades of >= 3c exist but close within 60 s (82% of 5c gaps halve within 60 s in 2025, 93% in 2026).

## Coverage and resolution (be explicit)
- Polymarket: 348/348 target games (all 282 in 2025 + 66 in 2026) had a moneyline event found by slug `nfl-<away>-<home>-<ET date>`; 347 have both venues (1 lacked Kalshi windows). 2025: 281 games, 2026: 66 games. Not covered: today's (Oct 11, week 6) games, because we have no Kalshi tape for them yet.
- Polymarket data-api `/trades` gives every fill with **1-second timestamps**; median gap between trades in-game is 2 s (p90 18 s), ~1,450 (2025) / ~1,680 (2026) trades per game. Page cap: 6,000 trades; 7 games (mostly playoffs) lost the earliest trades (pre-game only, in-game intact in the games checked by first-trade time).
- Polymarket CLOB `/prices-history` returns **1-minute points** (fidelity=1, ~348 points per game), but only when called with explicit startTs/endTs; `interval=max/all` returns an empty list for closed markets. 1-minute points cannot resolve a lead under 60 s, so lead-lag was measured on the trade tape; the CLOB series was pulled (data/pclob_*.json) but not used for any cell.
- Kalshi: the data on disk is the per-play window series (-90..+120 s, **2 s bins**, trade events = bins with path_n>0), not a continuous tape, for BOTH seasons (the ms tapes exist only for 2026 and were not used, for consistency). Kalshi's native candlesticks are 1-minute and were not used. So Kalshi coverage is the union of play windows and 2 s is its time resolution.
- Fees: Kalshi ceil(0.07*C*P*(1-P)) (C=100 per-contract form); Polymarket taker 0.05*P*(1-P) per share per the fee docs, applied to both seasons (2025 markets show feesEnabled=false, so this is conservative there; current NFL markets show rate 0.03). Ask proxy = last trade + 1c. Prices are last trades, not books, so spread/depth is not modeled.

## All 15 cells
| Cell | Rule | 2025 discovery | passes discovery | 2026 test | BH q=0.10 | survives |
|---|---|---|---|---|---|---|
| L1 TD | median lead (PM - Kalshi t50) | +10 s [8,12], n=208 | yes | +2 s [2,3], n=59, p<0.001 | yes | yes (finding, not a trade) |
| L2 FG | same | +8 s, n=11 | yes | n=4, no estimate | no | no (too few) |
| L3 turnover | same | +10 s [8,11], n=219 | yes | +2 s [2,2], n=61, p<0.001 | yes | yes (finding) |
| L4 big play | same | +8 s [7,9], n=210 | yes | +2.5 s [2,3], n=64, p<0.001 | yes | yes (finding) |
| L5 all jumps | same | +9 s [8,10], n=1,617 | yes | +2 s [2,3], n=432, p<0.001 | yes | yes (finding) |
| A1 | locked arb, gap >= 4c | +1.65% [1.5,1.8], n=2,918 | yes | +1.52% [1.2,1.8], n=361 | yes | passes gates, NOT executable (below) |
| A2 | gap >= 6c | +4.5% [4.3,4.8], n=1,486 | yes | +4.7% [4.1,5.4], n=149 | yes | same |
| A3 | gap >= 8c | +7.6% [7.2,8.0], n=830 | yes | +7.8% [6.9,8.7], n=79 | yes | same |
| C1 | buy cheaper venue's home, hold, gap >= 3c | +0.3% (p=0.47), n=4,200 | no | -7.1% [-31,+16], n=555 | no | no |
| C2 | gap >= 5c | +4.9% (p=0.24) | no | -7.4% [-36,+20], n=232 | no | no |
| C3 | gap >= 8c | +8.6% (p=0.16) | no | +1.1% [-38,+40], n=79 | no | no |
| F1 | Kalshi jump, buy PM at +10 s, exit +60 s | +2.7% [1.0,4.4], n=400 | yes | -2.8% [-6.2,-0.3], n=33 | no | no |
| F2 | same, exit +120 s | +4.6% [2.5,6.7], n=400 | yes | -1.1% [-7.2,+5.7], n=33 | no | no |
| F3 | PM jump, buy Kalshi at +10 s, exit +60 s | -7.5%, n=375 | no | -5.5%, n=29 | no | no |
| F4 | same, exit +120 s | -7.3%, n=375 | no | -4.4%, n=29 | no | no |

Survivors by the pre-registered gates: L1, L3, L4, L5, A1, A2, A3 (7 of 15). **None is a tradable edge**; see below. (ROI figures are P&L / cost including fees.)

## Why A1-A3 are not real (post-hoc robustness, descriptive; not part of the 15 cells)
A cell "buys home on one venue and away on the other" using each venue's last trade, accepted if both are <= 20 s old. A venue's last trade can be 20 s stale right after a play, so the "gap" is mostly one venue that has not updated yet. Re-running the same triggers:
| Variant | A1 2025 | A1 2026 | A2 2026 | A3 2026 |
|---|---|---|---|---|
| as pre-registered | +1.7% | +1.5% | +4.7% | +7.8% |
| both prices <= 2 s old | +2.0% | +2.1% | +5.5% | +8.8% |
| execute 10 s after the gap is seen | -1.0% [-1.2,-0.9] | -2.8% [-3.0,-2.6] | -2.6% [-2.9,-2.3] | -2.1% [-2.8,-1.3] |
Requiring fresh prices does not remove the profit (last-trade-plus-1c understates real spreads and bid-ask bounce), but a 10 s execution delay turns every cell negative in 2026. Treat A1-A3 as an artifact of last-trade pricing, not an arbitrage.

## Lead-lag details
- Method: for each Kalshi jump (|move| >= 0.08 in 20 s), each venue's t50 = first trade at which the price has covered half of its own move from t0-30 s to t0+120 s; both venues must move >= 4c in the same direction. Lead = Polymarket t50 - Kalshi t50.
- Cross-correlation of 5 s returns (descriptive): 2026 concentrated in the lag-0 bin (corr 0.52 vs ~0 elsewhere) so the lead is under 5 s; 2025 peaks at +10 to +20 s (Kalshi first).
- Restricting to jumps where Polymarket was liquid (>= 8 or >= 15 trades within t0-10..t0+30 s) leaves the medians unchanged (2025: 8 s; 2026: 2 s), so Polymarket sparseness is not the explanation. Bias that remains: t50 needs an actual trade, which biases the lead toward "Kalshi first" by up to one inter-trade gap (~2 s median), so the 2026 lead of 2 s is consistent with zero.
- Tradable lead-lag (F1/F2): 2025 looked profitable after fees (+2.7% / +4.6%, 400 trades) but 2026 is negative (-2.8% / -1.1%, 33 trades; n is small). Polymarket-to-Kalshi (F3/F4) loses in both seasons. Fee drag is ~4c per round trip at mid prices, bigger than the move captured.
- Gap -> convergence direction: gaps shrink (82-93% halve within 60 s) but holding the cheaper side to settlement has no edge (C cells).

## Not covered
PrizePicks has no public API (and offers player props, not game moneylines), so it was not tested. Today's week-6 games were not covered (no Kalshi tape yet; Polymarket events exist and could be pulled with pull_poly.py once tapes exist). Polymarket spreads/totals markets for the same games were not analyzed.

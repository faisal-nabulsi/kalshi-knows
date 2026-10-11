# CROSS-VENUE (Kalshi vs Polymarket) pre-registration
Written 2026-10-11 ~12:45 PDT, BEFORE any Polymarket-vs-Kalshi comparison was computed. Only data availability was probed
(Polymarket event slugs `nfl-<away>-<home>-<ET date>`; data-api `/trades` gives per-trade second timestamps; CLOB `/prices-history` gives 1-minute points
only when called with startTs/endTs). Not edited after analysis; later changes go under "Deviations".

## Data
- Kalshi: home-win trade tape (ms) from pipeline/out/trades (2026, 66 games) and pipeline/out/w2025 (2025, 282 games). Plays/categories/wallclock from real_windows*.parquet.
- Polymarket: moneyline market of the same game; trades (second timestamps, price, side, outcome) from data-api; oriented to HOME-win price
  (trade in the away outcome => home price = 1 - price). CLOB 1-minute history is pulled too and used only to state/measure the 1-minute resolution limit.
- Settlement: final ESPN score. Ties dropped. Resolution limit: Polymarket series are trade-by-trade (seconds) but sparse (median gap reported); CLOB history is 1-minute.
- Fresh price = last trade on that venue within the previous 20 s. "Ask" proxy = last trade + 1c on the side bought (cap: skip if >=0.99).
- Fees: Kalshi taker ceil(0.07*C*P*(1-P)) per order, C=100 (per contract = 0.07P(1-P)). Polymarket taker 0.05*P*(1-P) per share (docs; applied conservatively to both seasons even though 2025 markets show feesEnabled=false).
- Only games with both a Kalshi tape and a Polymarket moneyline market are used; the count is reported.
- Uncertainty: game-clustered bootstrap (5,000 draws). Discover on 2025 (rule passes if effect>0 and one-sided p<0.05), test ONCE on 2026,
  Benjamini-Hochberg q=0.10 over ALL 15 cells below using the 2026 p-values (cells that fail discovery are included in the BH denominator with their 2026 p). A survivor must pass discovery AND BH.

## The 15 cells (fixed)
Jump definition (Kalshi): the live detector (|change| >= 0.08 over trailing 20 s, held 3 s) on Kalshi's 2 s window path; t0 = confirmation; fires within 60 s of a kept fire are dropped (as in HYPOTHESES.md).

**Lead-lag (5 cells, L1-L5).** For each Kalshi jump: pre = last price of each venue at t0-30 s (must exist), post = venue price 120 s after t0 (last trade).
Venue t50 = first time after t0-30 s at which that venue's last-trade price has covered half of its own pre->post move (needs |pre->post| >= 0.04 on BOTH venues).
Lead = t50_PM - t50_K (positive = Kalshi first). Cells = category of the play: L1 TD, L2 FG, L3 turnover, L4 big play, L5 all jumps pooled.
Statistic: median lead; two-sided game-clustered bootstrap p of median = 0. "Pass" = p<0.05 in the same sign discovered in 2025.
Also reported (descriptive): cross-correlation of 5 s returns, lags -120..+120 s.

**Locked arbitrage (3 cells, A1-A3).** On a 10 s grid in-game (first to last play), when both venues are fresh and home price gap |pPM - pK| >= thr,
buy home on the cheaper venue and away on the other (each at ask proxy = last + 1c on the side bought), 1 contract each, net of both fees.
Payoff is exactly 1 at settlement, so profit = 1 - cost - fees. thr = A1 0.04, A2 0.06, A3 0.08. One entry per game per 5 min.
Statistic: mean net profit per $ of cost, >0; game-clustered bootstrap. (Expectation: negative after 2c of spread + fees, we test it rather than assume.)

**Gap convergence direction (3 cells, C1-C3).** Same trigger as A (thr 0.03 / 0.05 / 0.08, one entry per game per 5 min, both fresh): buy HOME on the venue where home is cheaper
(at ask proxy, own fee) and hold to settlement. ROI = (payout - ask - fee)/(ask+fee). Statistic: ROI>0, game-clustered bootstrap.
Companion descriptive: share of gaps that shrink by >=50% within 60 s.

**Follow-the-leader trades (4 cells, F1-F4).**
F1/F2: Kalshi jump detected (as above); at t0+10 s buy the jump-direction side on POLYMARKET at ask proxy if Polymarket's last trade is still within 0.03 of its t0-30 s price
(has not yet moved); exit at the last Polymarket trade at/before t0+60 s (F1) or t0+120 s (F2) minus 1c (bid proxy); both taker fees paid (round trip).
F3/F4: Polymarket jump detected from PM trades (|change| >= 0.08 over trailing 20 s, same cooldown); at t0+10 s buy the jump-direction side on KALSHI if Kalshi has not yet moved (within 0.03 of its t0-30 s price);
exit at the last Kalshi trade at/before t0+60 s (F3) / t0+120 s (F4) minus 1c; Kalshi fee both legs.
Statistic: ROI = total P&L / total cost incl. fees, > 0; game-clustered bootstrap. Size: 1 contract per trade (so fee rounding is per order, ceil to cent, reported separately from per-contract).

## Deviations
(none at time of writing)

- 2026-10-11 ~12:50 PDT (before any cross-venue comparison): the 2025 Kalshi data on disk is NOT a continuous tape, only the per-play windows (-90..+120 s, 2 s bins, path_n = trades per bin).
  For BOTH seasons the Kalshi series used is therefore the merged window series, trade events = bins with path_n>0 at (wallclock + t) with the bin price (2 s resolution, Kalshi coverage = union of play windows).
  The A/C cells' "in-game 10 s grid" is restricted to times where Kalshi has a trade event in the previous 20 s. No cell definition, threshold or test changed.

# PREREG: large in-game scan on game-winner price paths

Written 2026-10-11 ~12:40 PDT BEFORE any outcome (win/loss, P&L) was computed in this family. Only the distribution of one covariate
(pre-jump trade activity, to set terciles) was inspected. Previous failed hypotheses (H1-H8 in train/context/HYPOTHESES.md) are not repeated
as such; this is a wider grid, so BH over all cells controls for the breadth.

## Data / events
- Windows: pipeline/out/real_windows_2025.parquet (discovery, 282 games), real_windows_mm.parquet (2026 wk1-5, test, 66 games). Outcome = game_context.home_win (ties dropped).
- Event = live detector fire (|change over 20 s| >= 0.08, held 3 s, same code as train/context/market_edge.py), t_c = confirm time (play-relative grid, 2 s).
  60 s wallclock cooldown per game. One fire per window.
- Signed jump d (home-price units); "toward" side = side the jump moved toward.
- Covariates (all known at t_c): |d| bucket {0.08-0.12, 0.12-0.20, >=0.20}; direction {toward offense, toward defense} (posteam_is_home);
  time {Q1, Q2, Q3, Q4 with >300 s left, Q4 <=300 s or OT}; pre-jump favorite price max(pb,1-pb), pb = price at t_c-20 s:
  {<0.60, 0.60-0.80, 0.80-0.90, >=0.90 (extreme)}; pre-jump activity = sum(path_n over t in [-90,-10]) split at 2025 terciles {low, mid, high};
  ESPN category {OTHER, TD, FG, TURNOVER, BIG_PLAY} (SAFETY dropped).
## Cell grid (in-game scan)
Slices: ALL; each single covariate level above (3+2+5+4+3+5 = 22) ; crosses direction x {|d| bucket (6), time (10), category (10)} = 26. Total 49 slices.
x action {fade (buy side jump moved against), follow (buy toward side)} x entry horizon {t_c+6 s (the +5 s grid bin), +10, +20, +40}
x exit {settlement, mark-to-market sell at play-relative t=+60, at t=+120}  => 49*2*4*3 = 1176 cells.
## Late-game extremes (12 cells, settlement only)
All windows (not only jump fires), play at gsr <= 300 s; entry price at play-time +10 s (path grid), side price s in the band; dedupe: at most one entry per game per
cell (the first window by wallclock). Cells = side-price band {[0.90,0.93), [0.93,0.96), [0.96,0.99]} x time {120 < gsr <= 300, gsr <= 120} x buy {favorite (the >=0.90 side), longshot (the <=0.10 side)}.
Total family m = 1176 + 12 = 1188 cells.
## Trade mechanics
Ask = last trade price of the side bought + 1c (home: p+0.01; away: (1-p)+0.01); skip if ask >= 1. Fee per order = ceil(0.07*C*P*(1-P)) with C=100 per order (per-contract fee = that/100), also on the sell leg for MTM exits (sell at last-1c).
Size: 1 contract per event (last-trade data only: displayed liquidity unknown, so no size scaling; stated caveat). P&L settle = win - ask - fee; MTM = bid_exit - ask - fee_buy - fee_sell.
ROI = sum pnl / sum (ask+fee). MTM exit needs exit time >= entry+10 s and a price (ffilled; skipped otherwise).
## Test
1. Discovery on 2025 per cell: n>=40, ROI>0, game-clustered bootstrap (5000 draws, resampling games) one-sided p<0.05.
2. Every cell that passes is run ONCE on 2026 (no tuning). One-sided clustered bootstrap p (5000 draws). 2026 cells with n<15 get p=1 (untestable).
3. Benjamini-Hochberg q=0.10 over ALL 1188 cells (cells that failed discovery or lacked 2026 data enter with p=1). Survivor = passes BH AND 2026 ROI>0.
   Also reported: unadjusted 2026 p<0.05 list, BH-on-2025-alone count (descriptive), and a null check (count of discovery passes expected by chance ~5%).
## Deviations
(none yet)

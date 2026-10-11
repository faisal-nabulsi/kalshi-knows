# PREREG: lead-lag across related same-game Kalshi markets (written 2026-10-11 ~12:55 PT, before any P&L/outcome looked at)

Only data-availability checks were done (columns, tape formats, week counts: 2026 wk1-3 = 48 games discovery, wk4-5 = 18 games test).
Descriptive lead-lag stats (cross-correlation, time-to-half-adjustment) are reported but are NOT tests and are not in the BH family.

## Mechanics (fixed)
- Windows: real_windows_mm.parquet. t=0 is the ESPN play wallclock. Dedupe: within a game, drop any signal <60 s (wallclock) after a kept one.
- Detector signals (S1,S2): |p_home(t)-p_home(t-20s)| >= thr held for 3 consecutive grid points; detection time D = first confirming grid time. Entry time E = D (already includes the hold; the "+3 s" of the brief).
- Label signals (S3 TD, S4 FG, S5 TURNOVER): ESPN category of the play, E = play time + 6 s (3 s detect + 3 s hold). This ASSUMES a correct call by the play classifier, so these are upper-bound ("oracle-label") cells; they are in the BH family anyway.
- Instrument: KXNFLTOTAL (total points ladder) raw tape. Strike = strike whose last trade price at E is closest to 0.50 ("median strike", M0) or the next strike below it (M-1, more in-the-money). Must have a trade at that strike within the 120 s before E, else skip (stale).
- Direction: S1,S2,S3,S4 buy OVER (yes). S5 buys UNDER (the no side, ask = (1-p_last)+1c).
- Entry price = last trade price at the strike at E, +1 c (buy-at-ask proxy); skip if >=0.99.
- Size C = min(100, contracts traded at that strike in [E-60 s, E+30 s]); skip if < 5. (Thin-ladder realism.)
- Exits: X60 / X120: sell at last trade at that strike at E+60 / E+120 s minus 1 c (floor 0.01), fee charged on both entry and exit. XS: hold to settlement (final total from game_context home_score+away_score; Over wins iff total > strike), fee on entry only.
- Fee per order = ceil(0.07*C*P*(1-P)) in cents (per leg). P&L and ROI = sum P&L / sum cost, cost = C*ask + entry fee (cost-weighted by contracts).
- Uncertainty: game-clustered bootstrap, 10,000 draws, one-sided p = share of draws with ROI <= 0.

## Candidate cells (25 in the family)
Total-points ladder:
 1-3   S1 (detector thr 0.05) M0   x {X60, X120, XS}
 4-6   S2 (detector thr 0.08) M0   x {X60, X120, XS}
 7-9   S3 (TD label) M0            x {X60, X120, XS}
 10-12 S4 (FG label) M0            x {X60, X120, XS}
 13-15 S5 (TURNOVER label, buy Under) M0 x {X60, X120, XS}
 16-18 S1 M-1 x {X60,X120,XS}
 19-21 S3 M-1 x {X60,X120,XS}
Total-TD ladder (KXNFLTOTALTD, same mechanics, strike nearest 0.50, buy "N+ touchdowns" yes):
 22-23 S3 x {X120, XS}
 24-25 S1 x {X120, XS}
(Cells are discovery-tested on wk1-3; spread ladder KXNFLSPREAD, anytime-TD-scorer, Polymarket and PrizePicks are NOT in the family; see RESULTS.md for what was/wasn't checkable.)

## Protocol
1. Discovery (wk1-3): a cell passes if n>=30 filled trades, ROI>0 and one-sided bootstrap p<0.10.
2. Test (wk4-5) exactly once per passing cell, unchanged.
3. BH at q=0.10 over ALL 25 cells: test p-value of a cell that failed discovery (or has no test trades) is set to 1. A cell SURVIVES if BH-rejected AND test ROI>0 AND test n>=15.
4. Expected: wk4-5 has 18 games, so power is low; this will be stated.

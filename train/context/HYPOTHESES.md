# Pre-registered hypotheses: is Kalshi's post-jump price mispriced in identifiable contexts?

Written 2026-10-11 ~12:35 PDT, BEFORE computing any outcome broken down by context.
At this point only data availability had been checked (which games join to nflverse, how often temp/wind exist).
This file is not edited after the analysis runs; anything added later goes under "Deviations" with a timestamp.

## Data and trade mechanics (fixed for every hypothesis)

- **Fires.** The live detector (|change| >= 0.08 over a trailing 20 s window, held 3 s) run over every real price window:
  2025 season (`pipeline/out/real_windows_2025.parquet`) and 2026 weeks 1-5 (`pipeline/out/real_windows_mm.parquet`).
  Jump time t0 = the bin where the detector confirms. Windows overlap, so within a game any fire within 60 s
  (absolute wallclock) of an earlier kept fire is dropped, matching the live 60 s cooldown.
- **Entry.** Price at t0 + 20 s (PRIMARY: what a human could still trade). t0 + 60 s is reported as a robustness
  check only and is never used to declare a rule "survived". The price is the last trade (home-win contract), so the
  ask is approximated as last trade + 1 cent on the side bought: home YES costs p + 0.01, away YES costs (1 - p) + 0.01.
  Trades whose ask would be >= 1.00 are skipped.
- **Outcome.** Final game result from nflverse schedules (`home_score`, `away_score`). Tied games are dropped.
- **Fees.** Kalshi taker fee per order = ceil(0.07 x C x P x (1 - P)) in cents-rounded dollars, P = ask.
  Primary: C = 100 contracts per order (fee per contract ~ 0.07 P(1-P)). Also reported: C = 1 (rounding to 1 cent).
- **P&L per $1 contract** = payout (1 or 0) - ask - fee. **ROI** = total P&L / total cost (ask + fee).
  **Hit rate** = share of trades where the side bought won.
- **Directions.** "Fade" = buy the side the jump moved AGAINST. "Follow" = buy the side the jump moved TOWARD.
- **Uncertainty.** Game-clustered bootstrap (resample games with replacement, 5,000 draws) for ROI.

## Protocol

1. **Discover on 2025 only.** A rule passes discovery if it has >= 30 trades, ROI after fees > 0, and the
   game-clustered bootstrap one-sided p < 0.05 (5th percentile of bootstrap ROI > 0).
2. **Test once on 2026 (held out, weeks 1-5).** Each rule that passed discovery is run once on 2026, unchanged.
   It "survives" only if 2026 ROI > 0 AND its one-sided bootstrap p < 0.05 / 8 = 0.00625 (Bonferroni over the
   8 hypotheses). Unadjusted numbers are reported too. Rules that failed discovery are still shown on 2026 for
   transparency, but can't "survive".
3. 2026 has only ~66 games, so a real but small edge may be undetectable there; that will be stated, not hidden.

## The 8 hypotheses (direction fixed in advance)

| # | Context (known at trade time) | Action at +20 s | Why it might work |
|---|---|---|---|
| H1 | Jump in Q1 or Q2 | Fade | Early swings are far from decisive; crowds overreact to vivid plays (TDs) |
| H2 | Q4 with <= 5:00 left in regulation, or overtime | Follow | Late plays matter more than they look; the price may move too little or too slowly |
| H3 | Outdoor game (roof outdoors/open) with temp <= 40 F or wind >= 15 mph, and the jump favored the "dome team" (a team whose home stadium is dome/closed) | Fade | Dome teams may be overrated in bad weather |
| H4 | Pregame spread >= 6.5 points, jump in Q1 or Q2 that moved AGAINST the favorite | Fade (buy the favorite) | Markets may overreact to an early setback for the better team |
| H5 | Primetime: kickoff 19:00 ET or later, or a Thursday/Monday game | Fade | Bigger casual audience, more emotional order flow |
| H6 | Jump favored a team whose starting QB is not the QB who started its first game of the season | Fade | Good plays by a backup-QB team may be over-trusted |
| H7 | Price at +20 s puts one side at >= 0.85 (the favorite) | Buy the favorite side | Favorite-longshot bias: longshots tend to be overpriced in betting markets |
| H8 | Data-driven cell: the single best cell (highest 2025 ROI after fees, >= 40 trades) from a fixed grid of quarter {Q1-2, Q3, Q4/OT} x jump size {0.08-0.15, >= 0.15} x jump toward / against the team with the ball x action {fade, follow} = 24 cells | As selected | Lets the data find a "small pattern"; selection happens on 2025 only, so the 2026 test is clean |

## Also reported (descriptive, not hypotheses)

- Reliability of the post-jump price (+20 s and +60 s) by decile against the actual home win, per season, plus a
  logistic calibration slope (slope < 1 = prices too extreme / overreaction, > 1 = too timid / underreaction).
- Unconditional "fade every jump" and "follow every jump" P&L after fees.

## Deviations

(none at time of writing)

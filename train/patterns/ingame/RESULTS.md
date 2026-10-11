# In-game scan on game-winner price paths: RESULTS

Code: train/patterns/ingame/scan.py. Pre-registration: PREREG.md (written before any outcome was computed). Per-cell numbers: cells.json.

**Bottom line: 0 survivors out of 1,188 cells tested. Zero cells even passed 2025 discovery.**

## What was tested
- 1,176 in-game cells = 49 slices (all; jump size x3; direction toward offense/defense; quarter/time left x5; pre-jump favorite price x4 incl. >=0.90 extreme; pre-jump activity x3; ESPN category x5; crosses of direction with jump/time/category) x fade/follow x entry +6/+10/+20/+40 s x exit settlement / sell at +60 s / sell at +120 s.
- 12 late-game extreme cells (last 5 min, side priced 0.90-0.99; buy favorite or longshot; settlement).
- Events: 2,210 detector fires in 2025 (282 games, discovery), 565 in 2026 (66 games, test). Ask = last trade + 1c, taker fee ceil(0.07*C*P*(1-P)) per order (C=100), also charged on the sell leg for early exits; 1 contract per event (last-trade data, no displayed-liquidity info, so no size scaling).
- Discovery rule: n>=40, ROI>0, game-clustered bootstrap one-sided p<0.05. Survivors would be tested once on 2026 and BH q=0.10 applied over all 1,188 cells.

## Results
- 923 of 1,176 in-game cells had n>=40 in 2025; only 62 had ROI>0; the smallest bootstrap p anywhere was 0.081. Discovery passes: 0 (about 45 would be expected from noise alone at p<0.05, so the market is, if anything, tighter than random).
- Unconditional: fade every jump -4.4% to -5.1% ROI net (about 0 to +0.6% gross of fees at last trade), follow every jump -4.4% to -4.9% net, at every entry horizon. This is the spread (1c) plus the fee, with no directional edge in either direction.
- Best 2025 cells (not significant, listed for transparency; 2026 numbers are descriptive only, not a test): jump >=0.20 fade +28% (n=42, p=0.08; 2026 n=15, -4%); jump 0.12-0.20 toward-offense fade +7.0% (n=162, p=0.23; 2026 n=50, +21%); Q4<=5min/OT toward-offense fade +6.5% (n=369, p=0.12; 2026 n=105, +18%).
- Across cells with n>=30 in 2026 (798 cells), only 11% had ROI>0.

## Late-game extremes (90-99c, last 5 min), 2025 discovery
| Band (favorite price) | Time left | Buy favorite: n, hit rate, ROI net [95% CI] | Buy longshot: n, ROI net |
|---|---|---|---|
| 0.90-0.93 | 120-300 s | 37, 97.3%, +4.3% [-1.6, +7.4], p=0.08 | 37, -72% |
| 0.90-0.93 | <=120 s | 37, 97.3%, +4.3% [-1.5, +7.4], p=0.08 | 37, -72% |
| 0.93-0.96 | 120-300 s | 46, 93.5%, -2.6% | 46, -4% |
| 0.93-0.96 | <=120 s | 36, 97.2%, +1.1% | 36, -58% |
| 0.96-0.99 | 120-300 s | 60, 96.7%, -1.9% | 154, -52% |
| 0.96-0.99 | <=120 s | 57, 98.2%, -0.1% | 164, -78% |
Answer to the favorite-longshot question: no. Heavy favorites win about as often as their price says (a slight +4% lean for buying 0.90-0.93 favorites is not significant, and the same games appear in both time rows, so it is one observation, not two). Longshots at <=10c lose most of their stake. These cells are small because our windows only exist around notable plays; they were not tested on 2026 because none passed discovery.

## Caveats
- Last-trade prices, not the order book; real fills at the ask could be worse in thin markets, so any paper edge would be an upper bound.
- 2026 is weeks 1-5 only (66 games): small effects are not detectable there. The "toward-offense fade in the last 5 min" lead (2025 p=0.12, 2026 descriptive +18%) is a hypothesis to pre-register for future weeks, not a finding.
- Windows only exist near ESPN plays, so extreme-price coverage is thin.

## Other data sources (user suggestion)
Not covered by this family. Polymarket's public price history is minute-resolution at best, too coarse for the +5 to +40 s horizons here, and PrizePicks has no public API; neither was tested.

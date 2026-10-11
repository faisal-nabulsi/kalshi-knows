# PREREG: pre-game and schedule patterns, KXNFLGAME (written before any outcome was joined to any price feature)

Written 2026-10-11 ~12:38 PDT. Only data availability (candlestick endpoints respond) was checked before this.
Not edited after outcomes are joined. Later changes go under "Deviations" with a timestamp.

## Data
- Games: 2025 season (282 games, discovery) and 2026 weeks 1-5 (66 games, test). Home-team YES market of each KXNFLGAME event.
- Prices: Kalshi hourly candlesticks (public; 2025 via /historical/markets/{t}/candlesticks, 2026 via /series/KXNFLGAME/markets/{t}/candlesticks)
  from market open to scheduled kickoff (ESPN date). Fields used: price close, yes_bid close, yes_ask close, volume.
- Outcome: final score from game_context.parquet (home_win). Ties dropped.
- Price snapshots (all taken from the last candle ending at or before the stated time; a snapshot is missing if no candle
  with a quote exists within 6 h before it):
  P_open = first candle with volume > 0 (price close). P_72 = kickoff-72h, P_24 = kickoff-24h, P_k = kickoff-1h (last pre-kickoff hour; used as the "kickoff price").
  Entry quotes at kickoff-1h: home YES costs yes_ask; away YES costs 1 - yes_bid (real quotes, so we buy at the ask). If a quote is missing use last price + 1c.
  Games with P_k missing are dropped (count reported).
- Trade: 100 contracts per order held to settlement. Fee per order = ceil(0.07*C*P*(1-P) in cents)/100 dollars, P = ask paid. P&L per contract = payout - ask - fee/C.
  ROI = total P&L / total cost. Liquidity: candlestick has no depth; hourly volume is reported and trades are flagged if hour volume < 500 contracts (such trades dropped from "liquid" robustness check only).
- Uncertainty: game-clustered bootstrap (games resampled, 5000 draws), one-sided p = share of bootstrap ROI <= 0.

## Protocol
1. Discovery on 2025: a cell passes if n >= 30 trades, ROI after fees > 0 and one-sided p < 0.05.
2. Each passing cell is run ONCE on 2026 unchanged. A cell "survives" if 2026 ROI > 0 and it is rejected by Benjamini-Hochberg at q = 0.10.
3. BH is applied to 2026 one-sided p-values over ALL cells in the family (m = every cell below); cells that failed discovery are given p = 1 (conservative). BH on the 2025 p-values is also shown for information.
4. Cells are never added, re-signed or re-thresholded after seeing outcomes.

## Cells (direction fixed). d_total = P_k - P_open (home prob). "toward" = buy side the move favored; "against" = fade.
| id | filter | action |
|---|---|---|
| C1 | |d_total| >= 0.03 | follow total drift open->kickoff |
| C2 | |d_total| >= 0.03 | fade total drift |
| C3 | midweek move P_24 - P_open_for_midweek (= P_24 - P_72 >= or <= 0.04 abs) | fade (reversal of midweek move) |
| C4 | gameday move P_k - P_24, abs >= 0.02 | follow (late info: injuries, inactives) |
| C5 | gameday move P_k - P_24, abs >= 0.02 | fade |
| C6a | favorite (side with P_k >= 0.5) price in [0.50,0.65) | buy favorite |
| C6b | favorite price in [0.65,0.80) | buy favorite |
| C6c | favorite price >= 0.80 (longshot bias) | buy favorite |
| C7 | all games | buy home team (home bias) |
| C8 | all games | buy away team |
| C9 | divisional game | buy underdog |
| C10 | primetime (game_context.primetime=1) | buy underdog |
| C11 | one team has rest <= 6 days and opponent rest >= short+3 | fade the short-rest team (buy opponent) |
| C12 | away team from Pacific/Mountain time zone, kickoff 13:00 ET or earlier, home team Eastern/Central | buy home |
| C13 | outdoor stadium (roof outdoors/open), away team is a dome team (away_dome_team=1) | buy home |
| C14 | away team is the favorite (P_k home < 0.5) | buy road favorite |
| C15 | home team is the underdog, spread_home > 0 | buy home dog |
| C16 | Polymarket vs Kalshi at kickoff-1h: |PM home - Kalshi mid| >= 0.03 (only games with PM history) | buy on Kalshi the side Polymarket rates higher |
| C17 | same as C16 | buy on Kalshi the side Polymarket rates lower |

Notes: C3 uses P_24 - P_72 with |move| >= 0.04 (fixed). C16/C17 are attempted only if Polymarket history is retrievable by slug within the time budget; if not they are reported as "not tested" and excluded from m.
Total cells m = 17 (or 15 if C16/C17 not run).

## Descriptive (not hypotheses)
Kickoff-price reliability by decile, calibration slope (logit), Brier of P_open vs P_72 vs P_24 vs P_k; logistic regression of result on logit(P_k) and drift logit(P_k)-logit(P_open) (does drift carry extra information?).
Data availability of PrizePicks: no public API, not used.

## Deviations
- 12:58 PDT (before any outcome was joined): C15 "home dog" is defined by Kalshi kickoff price (home P_k < 0.5), not by spread_home (sign convention ambiguous). Snapshot price P(t) = price close, falling back to bid/ask mid when no trade in the candle. Candle fetch window = 120 days before kickoff (single request; start of the market is not needed). Polymarket YES token 0 is assumed to be the away team (slug order); orientation is checked by the sign of its correlation with Kalshi home price. P_k kickoff-1h candle must end at or before kickoff-1h. Rate limit: Kalshi 0.7 s/request, Polymarket 1.05 s/request.
- 12:50 PDT: code bug fix only (C9 filter used r['div'] on a namedtuple and silently produced 0 trades; changed to r.div). No definitions changed. The C1-C15 first run happened before this fix; its results for other cells are unaffected.
- 12:50 PDT: code bug fix only (C9 filter used r['div'] on a namedtuple and silently produced 0 trades; changed to r.div). No definitions changed. The first run (C1-C15) happened before this fix; other cells unaffected.

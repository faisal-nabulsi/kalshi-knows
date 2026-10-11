# Pattern search: final report (Kalshi Knows, 2026-10-11)

## Bottom line
- We tested **1,247 trading rules** across four families of patterns. All of them used public Kalshi data, and two families also used public Polymarket data.
- **17 rules** passed the first screen on the earlier data.
- **11 rules** also passed the one-shot test on the later data and the false-discovery correction.
- **0 rules** survived review by two independent skeptics. Every one of the 11 was knocked out by at least one skeptic.
- **So no rule survives, and we have no betting rule to deploy.** Kalshi's NFL prices take in a play within seconds and stay fair after that. The money in our best-looking rules came from knowing something before the market did, which no public data feed allows.
- Earlier, 8 context hypotheses (weather, rest, primetime, backup QB and so on) were tested the same way and also failed (train/context/REPORT.md). Counting those, the total is 1,255 rules tested and 0 survivors.

## Terms used below
- **Cell:** one exact rule tested as one hypothesis. A rule is a trigger, an entry time, an exit time and an optional filter.
- **Discovery period:** the earlier data, where rules are allowed to look good. This was the 2025 season, or 2026 weeks 1-3 for the total-points ladder, which only exists for 2026.
- **Test period:** the later data. Each rule that passed discovery was run on it once, unchanged. This was 2026 weeks 1-5 (66 games), or weeks 4-5 (18 games) for the ladder.
- **BH (Benjamini-Hochberg) at q=0.10:** a correction for testing many rules at once. It keeps the expected share of flukes among the rules we call winners at or below 10%. It was applied across every cell in a family.
- **ROI after fees:** profit divided by money spent. Every trade buys at the ask and pays Kalshi's taker fee, ceil(0.07 x contracts x P x (1-P)), on each order. The ask is taken as the last trade + 1 cent, because the data has trades, not order books.
- **95% CI (confidence interval):** a range that likely contains the true ROI. It comes from a game-clustered bootstrap, which resamples whole games. Whole games are used because plays within one game are not independent.
- **Skeptics:** two separate reviewers re-ran each surviving rule and tried to break it. One looked for data errors and look-ahead, meaning use of information that was not available at trade time. The other looked at whether the trade could really be placed. A rule had to survive both.
- **Oracle label:** information we only have after the fact, such as ESPN's final play-by-play saying a play was a touchdown (TD).

## The funnel
| Family | What it tested | Cells tested | Passed discovery | Passed test + BH | Survived both skeptics |
|---|---|---|---|---|---|
| ingame | Fading or following swings in the game-winner price, split by quarter, jump size, who has the ball, price level and play type; heavy late-game favorites | 1,188 | 0 | 0 | 0 |
| pregame | Kickoff prices, price drift before kickoff, schedule spots (divisional, primetime, short rest, travel, dome), Polymarket vs Kalshi before kickoff | 19 | 0 | 0 | 0 |
| leadlag | Whether the same-game total-points and total-TD markets trail the winner market after a play | 25 | 7 | 4 | 0 |
| crossvenue | Kalshi vs Polymarket during games: who moves first, following one venue onto the other, two-venue arbitrage | 15 | 10 | 7 | 0 |
| **Total** | | **1,247** | **17** | **11** | **0** |

Details for each family, including every cell, are in train/patterns/<family>/RESULTS.md and PREREG.md. PREREG.md is the list of rules and tests written down before outcomes were checked.

## Final survivors
**None.** There is therefore no alert rule or auto-bet rule to ship from this work. The table below covers the 11 rules that passed every statistical gate and then failed review. They are grouped into 7 reviewed claims.

| Rule (family) | Test result as claimed | Why it died | Result with realistic timing and fills |
|---|---|---|---|
| **TD -> buy Over, total-points ladder, strike nearest 50%, sell at +120 s** (leadlag) | +16.6% [+11.3, +22.8], n=92 trades, 18 games | Entry is 6 s after ESPN's play timestamp, and it assumes we already know the play was a TD. That timestamp is close to the snap. On long TDs, the trade is placed before the touchdown has even been scored. TDs of 20+ yards make up 23% of trades but 66% of the profit. TDs of 2 yards or less earn about 0. | +3.1% [-4.8, +10.1] when entry waits for the winner price to start moving, plus 8 s. -4.5% to -5.9% at play +22-30 s (TV delay or our live engine), with CIs below 0. Both skeptics refuted it. |
| Same rule, sell at +60 s (leadlag) | +15.4% [+10.3, +21.5], n=92 | Same look-ahead. Entries at or before the actual score earn +18%. Entries more than 2.5 s after the score earn about 0. | +0.7% to +2.6% (CI includes 0) when entry comes after the score and uses real fill prices. -1.7% at our engine's call time. Both refuted. |
| TD -> buy Over, one strike below the median, sell at +120 s (leadlag) | +10.6% [+7.6, +14.4], n=88 | Same look-ahead. The entry price is also often stale: the median last trade is 5.6 s old, and the next real trade is about 2c higher. | +1.4% [-1.9, +4.7], n=54, entering 1 s after the first public TD-scorer print at 0.90 or higher, at real ask/bid prices. Both refuted. |
| Same, sell at +60 s (leadlag) | +9.6% [+6.5, +13.4], n=88 | Same look-ahead. | +1.5% [-1.4, +5.2], n=71, entering 4 s after the winner price first moves 2c. -0.2% to -3.2% at our engine's call time (about +20 s). Both refuted. |
| Kalshi moves before Polymarket, all big jumps (crossvenue, L5) | Median lead +2 s [2, 3], n=432 jumps, 60 games (2025: +9 s) | This is a timing fact, not a trade. Polymarket's trade times are blockchain record times. A skeptic measured them live today at a median 2.2 s after the actual match. Correcting for that shrinks the lead to about 0-2 s. | Not a trade, so no ROI. When our detector fires, Polymarket has already made 70% of its move. Split verdict: one skeptic upheld the direction (with a corrected lead of +3.8 s on the exact Kalshi tape), the other refuted it. It needed both, so it fails. |
| Same lead, split into TD / turnover / big play (crossvenue, L1/L3/L4) | +2 s (n=59) / +2 s (n=61) / +2.5 s (n=64) | Same clock problem. With Polymarket's 2 s recording delay removed, the leads become 0 / 0 / 0.5 s (p=1.0 / 1.0 / 0.94). | Not a trade. Both refuted. |
| Two-venue "locked arbitrage": buy home on the cheaper venue and away on the other when the gap is at least 4c / 6c / 8c (crossvenue, A1-A3) | +1.5% [1.2, 1.8] n=361 / +4.7% [4.1, 5.4] n=149 / +7.8% [6.9, 8.7] n=79 | The "gap" is one venue's last trade that has not updated yet. Those prices had already been traded away. The next real fill on the side you would buy had closed the gap. | A2: -0.4% [-1.3, +0.6] at zero delay, -2.0% at 2 s. Full two-leg fill simulation: -1.3% to -3.3%. Both refuted. |

**How we would use a survivor, and why we won't now.** The plan was for a surviving rule to become an auto-bet rule on the Auto page, plus an alert ("TD just happened: total ladder still lagging"). No rule earned that, so the Auto page should stay in demo/dry-run mode, because every candidate loses money or breaks even once timing is realistic. Even the best case for the closest candidate falls short. A perfect TD classifier that fires the moment the market starts moving earns about +1.5%, with a CI that includes 0. The fee and spread alone cost about 4-5% per round trip.

## Polymarket and PrizePicks (the question you asked)
- **Polymarket: yes, used in two families.**
  - **pregame:** hourly prices for 344 games. Before kickoff, Polymarket and Kalshi agree to within 0.8c on average, and never differ by more than 2.5c. So the "buy where the other venue disagrees" cells had zero qualifying trades.
  - **crossvenue:** the full trade record for 347 of 348 games (281 in 2025 and 66 in 2026), with 1-second timestamps, across 15 cells. Kalshi moves first after big plays, but only by about 0-4 s once clocks are corrected. Gaps between the venues close within 60 s, and the arbitrage disappears once fills are realistic.
  - The ingame and leadlag families skipped Polymarket as "too coarse". That only applies to Polymarket's price-history endpoint, which has 1-minute points. The trade record crossvenue used is fine-grained.
  - **Not covered:** Polymarket's spread, totals and player-prop markets.
  - **Caveats from a skeptic, not checked by us:** Polymarket holds in-game sports orders in a short delay window. That lets its market makers pull stale quotes before you can fill. The venue may also be closed to US users.
- **PrizePicks: not used by any family.** There are three reasons:
  1. It has no official public API. Its unofficial projections endpoint returned 403 (bot protection) when we tried it today.
  2. It publishes no history of its lines, so there is nothing to backtest.
  3. It is pick'em against the house at fixed payouts, not a traded price. There is no price path that could lead or lag Kalshi.
- **The only way to use PrizePicks** would be to record its player-prop lines ourselves from now on and compare them with Kalshi's anytime-TD scorer prices. That would take weeks of logging, and their terms of service would need checking first.

## Facts about the market we can stand behind (not trades)
- **Prices are fair at kickoff.** The calibration slope is 0.91 +- 0.28 over 347 games. A slope of 1 means prices match how often teams actually win.
- **Prices are fair 20 s after a swing.** The slope is 0.97 there.
- **Fees and spread are the whole story for simple rules.** Fading or following every swing loses 4-5% after fees, which is about the 1c spread plus the fee.
- **The total-points ladder trails the winner market by about 2-6 s.** It takes 14 s to make half of its move after a TD, versus 8 s for the winner market.
- **The touchdown edge depends on the moment of entry.** It is +16.6% at play +6 s, +9.7% at +10 s, +2.7% at +15 s and -2.7% at +20 s. Our engine calls a play about 20 s after it happens, and a TV viewer is tens of seconds behind the market.

## Leads for a future pre-registered test (not findings)
- **Fade swings toward the team with the ball in the last 5 minutes or overtime.** 2025: +6.5% (p=0.12). 2026, descriptive only: +18% (n=105).
- **Buy the underdog in divisional and primetime games.** 2025: +15% and +17% (p about 0.15). 2026: +36% and +49%, on only 17 and 14 trades.
- **Use the anytime-TD scorer market as a real-time TD trigger.** Low priority, because the skeptics' informal checks already put it at about -0.5% to +3% after realistic fills.

## Caveats
- **Pre-registration timing:** in leadlag and crossvenue, the times written inside PREREG.md do not match the file times. The leadlag PREREG was committed only about 2 minutes before its results, so we cannot prove its outcomes were never looked at early. This does not change the conclusion, because nothing survived.
- **Small test periods:** the leadlag test is effectively one week, since week 5 has only 2 games. 2026 as a whole has 66 games, so an edge smaller than about 20% ROI cannot be detected in 2026 alone.
- **Trades, not quotes:** prices are last trades, not the order book. That makes paper results optimistic, not pessimistic.

## Conclusion
We set out to find a repeatable money-making pattern in public NFL prediction-market data, and we did not find one. The rules came from four families: in-game swings, pre-game and schedule spots, related same-game markets, and Kalshi vs Polymarket. The process was built to stop us fooling ourselves:
- rules written down before we looked at outcomes
- discovery on early data and a single test on later data
- a correction for testing many rules at once
- fees charged and buying at the ask
- two hostile reviewers per survivor

Of 1,247 rules, 11 cleared every statistical gate. All 11 fell apart under review, because:
- they bought before the touchdown was public,
- they used a trade price that had already gone,
- or they relied on a timestamp gap that is really Polymarket's blockchain recording delay.

The consistent finding is that Kalshi digests a play within about 6-14 seconds and is fair afterwards. So the product's value is information, not a betting edge: telling a viewer what just happened before their stream shows it. Until a rule survives a fresh pre-registered test on new weeks, no real-money auto-bet rule should be turned on.

## Slide-ready
1. We pre-registered and tested 1,247 NFL trading rules on public Kalshi and Polymarket data; 11 passed every statistical check, and all 11 were knocked out by independent skeptics, so zero survive.
2. Kalshi prices a play within seconds and stays fair, so our edge is not a bet: it is telling you what just happened before your stream shows it.
# Kalshi Knows: research brief (synthesis of rounds 1 and 2)

Written Sun Oct 11 2026 for whoever has to defend this on stage. It condenses four verified reports in this folder (touts.md, ai-algos.md, market.md, features.md) and the stats ledger (../STATS.md). Outside facts carry a link. Our own numbers cite the STATS.md section or the repo file they come from. Anything not backed by a source is marked **(our inference)**, **(assumption)** or **(unverified)**.

Quick definitions used below:
- **Order book**: the live list of buy and sell offers on a Kalshi market. Its price is the crowd's probability.
- **Tout**: a person or site that sells sports picks.
- **ATS (against the spread)**: a pick on the point margin the sportsbook sets. At standard -110 odds you must win **52.38%** of picks just to break even, because the book keeps a fee called the **vig** (110/210; [Murray](https://johnfmurray.com/?p=10059)).
- **Accuracy**: share of guesses that were right. **Top-2**: right answer was one of our two best guesses.
- **Log loss**: a score for probability guesses that punishes confident wrong answers. Lower is better.
- **Calibration**: when the model says 90%, is it right about 90% of the time?
- **Precision**: share of alerts that were real plays. **Recall**: share of real plays that got an alert.
- **TAM**: total addressable market, the most revenue a product could earn if everyone who could buy it did.

> **Data freshness warning.** STATS.md was written at 11:28. At 11:53 a newer model was committed (commit 7615b68, train/out/finetune_metrics.json). It was trained on **3,704** real Kalshi fires from the 2025 and 2026 seasons, not the 1,596 from 2026 that STATS.md describes. The new numbers appear below as "new model". STATS.md should be updated before the slides are locked.

## 1. Positioning (what is new, and what is not)

Kalshi Knows treats the prediction market as a sensor, not a crystal ball. Touts and AI pick sites try to **predict** who will win, which is a game almost nobody wins after fees. Independent studies find most tipsters lose ([Tips.GG](https://tips.gg/article/football-prediction-services-profitability/), [arXiv 2604.08251](https://arxiv.org/abs/2604.08251)). The best AI claim we found is Dimers' self-reported 52.7% against closing lines, about 0.3 points above break-even ([Dimers](https://www.dimers.com/news/why-dimers-proven-ai-sports-predictions-engine-is-primed-to-dominate-nfl-and-college-football-betting-in-2026)). We **infer what just happened** from how Kalshi's public order book jumps, then tell fans before their stream shows it. Then we publish what no tout publishes: a timestamped, held-out, calibrated record that includes our misses. As far as two rounds of searching could find, nobody else turns prediction-market price jumps into play-type spoilers timed against streams (ai-algos.md section 7, features.md section 3). Say "we found no one", not "no one exists".

What is **not** new, said honestly:
- **Our model family.** Gradient-boosted trees (XGBoost) on nflverse play-by-play are what the open-source nflfastR win-probability model already uses ([fastrmodels](https://nflverse.r-universe.dev/api/packages/fastrmodels)).
- **Trading on broadcast delay.** Kalshi traders already use antennas and stopwatches to exploit the delay ([Operative](https://www.operative.com/resources/why-the-gap-between-the-game-and-your-screen-is-a-business-problem/)), and an academic paper adds a latency-arbitrage module for Polymarket ([PolySwarm](https://arxiv.org/abs/2604.03888)).
- **Price alerts.** Kalshi alerts already exist. Bot for Kalshi sends email threshold alerts for $99/mo ([Bot for Kalshi](https://www.botforkalshi.com/kalshi-alerts)), and Kalshi's own app offers price-movement notifications ([Kalshi help](https://help.kalshi.com/en/articles/17297679-manage-your-kalshi-email-notifications)).
- **Delayed notifications.** The MLB app already holds alerts for a fixed 30 s ([Six Colors](https://sixcolors.com/post/2024/03/mlb-app-will-slow-itself-down-let-your-media-stream-catch-up/)).
- **Arbitrage scanners.** Fee-aware scanners already exist ([Oddpool](https://www.oddpool.com)).
- **Stream-latency studies.** Stats Perform and Phenix already publish stream latency studies ([SVG](https://www.sportsvideo.org/2026/02/11/stats-perform-2026-super-bowl-latency-report/), [Awful Announcing](https://awfulannouncing.com/tv/antenna-cable-win-super-bowl-latency-battle-streamers-lag-behind.html)).
- **Speed.** Paid official data feeds are faster than our method (Stats Perform claims under 1 s for some sports; [Stats Perform](https://developers.statsperform.com/low-latency-sports-data-for-in-play-markets)).

The new part is the combination: free public market data, play-type inference, a per-viewer delay, and a public, honest ledger.

## 2. "Better than a smart sports fan": how competitors prove accuracy, and how we do

### How competitors prove (or fail to prove) accuracy
- **Touts show records that nobody audits.** Doc's Sports shows win-loss records in "units" it never defines, quotes hand-picked slices such as "22-14 on 6- and 7-Unit plays", and its "guarantee" only extends your subscription; it is not a refund ([Doc's Sports](https://www.docsports.com/expert-picks/college-football/)). Pickswise claims +82.1 units, but its own pages give conflicting supporting counts ([Pickswise](https://www.pickswise.com/nfl/picks/)). The Handle says no tout's record is independently verified ([The Handle](https://thehandle.substack.com/p/tout)).
- **"Verified" tools only lock the bets you choose to log.** Action Network's verified bets lock the bet at the consensus line and block edits, but users still pick which bets to log ([Action Network](https://www.actionnetwork.com/press/new-in-the-action-network-app-verified-bets-leaderboard-year-in-review-props)). We found no independent audit of Betstamp or Juice Reel records (touts.md section 3).
- **AI pick sites report their own season hit rates, which sit near break-even.** Dimers reports 52.7% (self-reported, no audit). BetQL's 1-to-5 star formula is unpublished ([App Store](https://apps.apple.com/us/app/betql-sports-betting/id1334825645)). SportsLine quotes its own "top-rated picks" tally ([CBS](https://www.cbssports.com/nfl/news/2024-week-11-nfl-score-predictions-game-picks-odds-model-gives-exact-scores-from-10000-simulations/)). PFF's 53.5% is from 2019 and mixes all bet types ([PFF](https://www.pff.com/news/pro-bet-pff-greenline-an-introduction-for-2019)). The open model nfelo roughly ties the closing line (the final pre-game price) but does not beat it (self-reported; [nfelo](https://nfeloapp.com/games/nfl-model-performance/)).
- **Independent evidence says the field loses.**
  - Only 38 of 165 football prediction services (23.0%) were profitable from January to August 2026. This is a self-study by a firm that ranks tipsters, and it covers soccer ([Tips.GG](https://tips.gg/article/football-prediction-services-profitability/)).
  - 37 NFL handicappers combined went 52.14% ATS since 2003, below the 52.38% break-even. The study was published by someone who sells picks ([Murray](https://johnfmurray.com/?p=10059)).
  - Three social-media tipsters lost 25.24% collectively in a 2026 preprint ([arXiv 2604.08251](https://arxiv.org/abs/2604.08251)).
- **Almost none of them publish a calibration chart, a timestamp, or their misses** (touts.md section 6, features.md section 5). That is the gap we fill.

### Which of our numbers beat which baseline
The "smart sports fan" baseline is a written rule that sees only the price jump. If the price rises for the team with the ball, the rule says touchdown when the jump is 10+ points and big play otherwise. If the price falls, it says turnover (STATS.md 3b, `train/eval_real.py`). It stands for a fan who sees the price move but not the TV.

| Our metric | Baseline it beats | Gap | Test set | Source |
|---|---|---|---|---|
| 89.7% play-type accuracy; top-2 97.6%; log loss 0.301 | Smart-fan rule: 60.0%; top-2 83.5%; log loss 1.630 | +29.7 pts | 417 real Kalshi big plays, 62 games, 5-fold CV by game, no "nothing happened" class | STATS.md 3b |
| 76.3% accuracy on every detector fire (71.5% at the live 0.08 threshold) | Always guess "nothing special": 64.7% (57.1% live) | +11.6 pts (+14.4 live) | 1,596 fires, 64 games, 2026 | STATS.md 3c |
| New model, strict out-of-season test (trained on 2025, tested on 2026): 74.7% (69.4% live) | Same "nothing special" baseline on the same fires: 64.7% (57.1% live) | +10.0 pts (+12.3 live) | 1,596 fires 2026; live subset n=569 | finetune_metrics.json `temporal` (our arithmetic for the gap) |
| New model, 5-fold CV: 77.3% (73.0% live) | Always "nothing special": 67.2% (2,488 of 3,704; our arithmetic) | +10.1 pts | 3,704 fires, 2025+2026 | finetune_metrics.json `table` |
| When the model says 90%+, it is right 93% (n=627); 97% on big plays (n=293) | Touts' star ratings, which have no published hit rate | n/a | 1,596 fires | STATS.md 3d |
| Kalshi's price moves a median 7.0 s after the play (middle half of plays: 5.6 to 9.0 s); 0% moved before the play | Broadcast TV about 19 s behind; streams 48 to 62 s behind | Market beats TV by about 12 s and streams by 41 to 55 s | 417 plays | STATS.md 1; [SVG/Stats Perform](https://www.sportsvideo.org/2026/02/11/stats-perform-2026-super-bowl-latency-report/) |
| Today's alerts landed 38.6 / 50.4 / 64.8 s before ESPN's own play-by-play feed | ESPN's feed as our poller saw it | 39 to 65 s | 3 confirmed alerts, Oct 11, all turnovers | STATS.md 1 |
| Today's alerts fired 23.2 to 32.7 s after the play | Streams at 48 to 62 s | About 15 to 39 s ahead of streams | 3 alerts | STATS.md 1, 6.1 |

### The 3 most convincing comparisons for the slides
1. **"We know before your stream does."** Use chart `results/charts/a_kalshi_beats_your_stream.png` plus `f_live_alerts_timeline.png`. The market moves 7.0 s after the play (417 plays), streams show it 48 to 62 s after, and today's alerts reached phones 38.6 / 50.4 / 64.8 s before ESPN's play-by-play. **Because:** this is a timestamped measurement, and no tout or AI pick site publishes anything like it.
2. **"Kevin & Faisal vs the House Cat."** Use chart `h_model_vs_smart_fan.png`. On 417 real Kalshi big plays, the model names the play right 89.7% of the time; a smart fan's rule gets 60.0%. **Because:** it answers the user's question directly with a held-out, game-split test, and the Predator Scale makes it memorable.
3. **"We say how sure we are, and we're right that often."** Use chart `e_accuracy_vs_confidence.png`. At 90%+ confidence the model is right 93% (n=627). On everything the detector fires on, it beats "always say nothing happened" by 10 to 12 points, even when trained on last season and tested on this one (74.7% vs 64.7%). **Because:** calibration plus an honest baseline is exactly what touts' stars and win-loss records lack, and it is the hardest claim for a skeptical judge to poke holes in.

### Claims we should NOT make
- **"We beat TV."** Our alerts fire 23 to 33 s after the play, and broadcast TV is about 19 s behind. Only the market itself (7.0 s) beats TV. Say "faster than streams and ESPN's feed" (STATS.md 6.1).
- **"We beat ESPN by 38 to 50 seconds"** with no qualifier. It is ESPN's play-by-play feed as our poller saw it, on 3 alerts, all turnovers, and the honest range is 38.6 to 64.8 s (STATS.md 6.2).
- **"76% vs 20% for a sports fan."** The fan rule never says "nothing happened", so the realistic-mix comparison is rigged against it. Use 89.7% vs 60.0% on big plays, or 76.3% vs 64.7% against "always nothing" (STATS.md 6.5, 6.10).
- **"89.7% accurate" or "85.9% accurate" as the live number.** 89.7% covers big plays only, and 85.9% is a simulated test. The live, realistic number is 69 to 77% depending on the test. Always say which.
- **"Our model went 3 for 3 live."** One of the three confirmed alerts (a_1) used the fallback rule, not the model (STATS.md 6.11). Say "3 of 3 live calls right".
- **"Trained on 28 seasons / 1.2M plays."** It was 25 training seasons (1999-2023), 28 including validation and test, and 244,434 rows (STATS.md 6.6).
- **"66 games" for the 417 plays.** They came from 62 games (STATS.md 6.3).
- **"Nobody else does this."** Say "we found no one".
- **"Kalshi is sharper than sportsbooks."** 2026 evidence is mixed ([CDC Gaming](https://cdcgaming.com/brief/kalshi-pricing-remains-worse-than-sportsbooks-says-citizens/), [Claremont](https://scholarship.claremont.edu/cmc_theses/4214)).
- **"Faster than official data."** Paid feeds such as Genius and Stats Perform are faster. Our edge is free, public and independent.
- **Any betting-profit or ATS claim.** We predict play type, not bet outcomes.
- **"Someone knew" as an accusation, or "80% of markets leak".** The sample is 5 cases (4 of 5). Keep the wording "the market moved before the first article" (STATS.md 4, CONTRACT.md).
- **"16 arbitrages"** without "before fees; 0 after" (STATS.md 5).

## 3. Top 8 feature/design additions (ranked by demo impact x buildability, each under 45 min)

Already built (show these off, don't rebuild them):
- the "Watching on" stream-delay picker, saved per viewer. It is the adjustable version of MLB's fixed 30 s toggle, and we found no adjustable one for the NFL.
- the takeover countdown and crowd vote.
- the Predator Scale leaderboard.
- per-alert lines like "Beat ESPN's own play-by-play by N s" (docs/js/app.js).

| Rank | Feature | What it shows | Competitor inspiration | Data we already have | Est. time |
|---|---|---|---|---|---|
| 1 | **Receipts ledger** | Every alert today, misses and pending ones included. Each row has 3 timestamps: the play per ESPN, our alert, and ESPN's feed. It also shows the lead and whether we were right, and losses are visible by default | The opposite of Doc's Sports' cherry-picked "last 53 days" slices; Action Network's locked, timestamped verified bets | engine/logs/20261011/alerts.jsonl (`confirmed.lead_s`, `market_lag_s`, `inferred_correct`) | 35 min |
| 2 | **Model vs smart-fan duel on each alert** | Each card says "Fan rule would say: turnover / Model says: TD 91%". A running tally covers today, with the 89.7 vs 60.0 headline under it | SportsLine and Bleacher Report expert-panel standings tables; the Apify Whale/Shark tiers that our Predator Scale echoes | Fan rule is 3 lines (`train/eval_real.py`); alert `team`, `delta`, game `possession` | 30 min |
| 3 | **Calibration strip** | "When we say 90%+, we're right 93% (n=627)" with 4 confidence buckets. Alert cards show a calibrated % instead of stars | FlukeWatch ranks traders by calibration, not profit; the BetQL and Pickswise stars are the anti-pattern | STATS.md 3d; results/charts/data/preds.json | 25 min |
| 4 | **"How to read this / What we don't claim" panel** on each section | What a price means, why we trade on paper only, why we are not faster than cable TV, and why 52.38% is break-even for touts | Prediction Hunt's plain-English FAQ and rules panels | Text only | 20 min |
| 5 | **Free-delayed vs live toggle** | The same alert shown "+30 s (free tier)" and "live (pro)". It makes the business model visible during the demo | Action PRO gives paying users real-time expert alerts and everyone else a 30-minute delay; whale trackers offer a 1-hour-delayed free tier | Existing alert feed | 25 min |
| 6 | **"What moved" explainer with a swing label** | Price before and after, jump size, the inferred play, confidence, and a small/medium/huge swing label. It answers the point that a bare number is redundant | FanGraphs' Leverage Index (how much one moment can swing a game); critiques of ESPN's win-probability graphic ([Defector](https://defector.com/espns-win-probability-graphic-wants-to-give-you-gambling-brain)) | Alert `p_before`, `p_after`, `inferred` | 30 min |
| 7 | **Fee chip on every Dutch Book row** | Edge before fees, Kalshi's fee (0.07 x price x (1 - price) per contract), and edge after fees as a bar. It explains "16 before fees, 0 after" at a glance | Oddpool shows "fee and spread context" next to every divergence and a net-of-fee arbitrage scanner | docs/data/dutchbook.json; fee formula from [ATS.io](https://ats.io/prediction-markets/kalshi/fees/) | 25 min |
| 8 | **Share card** | Turns an alert into a PNG ("Turnover, CIN @ MIA, 50 s before ESPN") that shares through the phone's share sheet, so judges can share it during the demo | Pikkit's QuickPickBot share links; Prediction Hunt's share row | Alert fields; canvas | 40 min |

**Why this order:** 1 to 3 directly answer "prove you're better than a smart fan," which the user ranked as the top priority. Item 4 protects the presenter from the riskiest judge questions. Items 5 to 8 add polish and business-model storytelling **(our inference)**. Honorable mention: user-set alert thresholds by play type and minimum jump, saved on the device (Pikkit market alerts, OddsJam filters), which help daily use more than they help the demo.

## 4. Six slide-ready facts (with sources)

1. **US sports betting is a $17B-a-year business.** In 2025 Americans bet $166.9B, and sportsbooks kept about $17.0B, a record ([AGA via Sports Betting Dime](https://www.sportsbettingdime.com/news/betting/u-s-sports-betting-revenues-rise-to-nearly-17-billion-in-2025/), [Legal Sports Report](https://www.legalsportsreport.com/263300/sportsbooks-make-more-money-from-slower-sports-betting-growth-in-2025/)).
2. **Kalshi is a $22B company, and sports is its main business.**
   - It was valued at $22B in May 2026 ([The Block](https://www.theblock.co/post/400413/kalshi-hits-22-billion-valuation-after-1-billion-raise-led-by-coatue)).
   - Sports made up 80% of its volume from July 2024 to April 2026 ([Pew](https://www.pewresearch.org/short-reads/2026/05/27/trading-volume-on-prediction-markets-has-soared-in-recent-months/)).
   - 89% of its $263.5M 2025 fee revenue came from sports ([CDC Gaming](https://cdcgaming.com/brief/kalshis-2025-fee-revenue-was-263-5m-with-89-coming-from-sports/)).
3. **About $983M traded on Kalshi NFL markets in Week 1 of 2026 alone** ([iGaming Business](https://igamingbusiness.com/sports-betting/kalshi-polymarket-beat-rivals-nfl-week-1/)). That depth is why the price is a reliable live signal **(our inference)**.
4. **Only 23% of prediction services made money.** 38 of 165 football (soccer) services were profitable from January to August 2026. The most accurate one, with a 76% win rate, still lost money. This is a self-study by a tipster-ranking firm ([Tips.GG](https://tips.gg/article/football-prediction-services-profitability/)).
5. **Expert NFL handicappers do not beat the house fee.** A panel of 37 went 52.14% against the spread since 2003, below the 52.38% needed to break even. The author sells picks ([Murray](https://johnfmurray.com/?p=10059)).
6. **Your stream is up to a minute behind the field.** At the Super Bowl, broadcast TV ran about 19 s behind, cable 38 s, Peacock 48 s, YouTube TV 53 s and NFL+ 62 s ([Stats Perform via SVG](https://www.sportsvideo.org/2026/02/11/stats-perform-2026-super-bowl-latency-report/), [CSI](https://csimagazine.com/csi/Peacock-leads-SuperBowlLX-streaming-latency.php)). Kalshi's price moves a median 7.0 s after the play (ours, STATS.md 1). The SVG article mislabels the game year in one spot, so say "Stats Perform's Super Bowl latency study."

## 5. Business models and likely VC-judge questions

Lead with the B2B models; use the consumer app as the hook. **Because:** businesses that face legal or revenue pressure already pay for evidence, while consumer pick apps crowd around $25 a month (market.md section 6).

| Model | Who pays | One-line TAM logic |
|---|---|---|
| **1. Market-integrity monitoring ("Someone Knew" for compliance teams)** | Exchanges (Kalshi, Polymarket, Robinhood, FanDuel Predicts, DraftKings Predictions), leagues, regulators | Kalshi alone earned $263.5M in fees in 2025 ([CDC Gaming](https://cdcgaming.com/brief/kalshis-2025-fee-revenue-was-263-5m-with-89-coming-from-sports/)). Robinhood earned $156M from event contracts in Q2 2026 ([The Block](https://www.theblock.co/post/410102/robinhood-prediction-markets-top-crypto-and-equities-revenue-in-q2)). Insider-trading rules are tightening ([CFTC advisory](https://www.cftc.gov/PressRoom/PressReleases/9185-26)). If integrity spend is about 1% of revenue **(assumption)**, the 2025 Kalshi figure alone is about $2.6M a year (our arithmetic). |
| **2. Independent latency audit** | Streamers, sportsbooks, leagues, data vendors | Genius ($669.5M 2025 revenue; [SEC 6-K](https://www.sec.gov/Archives/edgar/data/1834489/000119312526089847/geni-ex99_1.htm)) and Sportradar (EUR 1.29B; [Sportradar](https://sportradar.com/content-hub/blog/sportradar-closes-2025-with-significant-growth-and-expanded-share-repurchase-plan/)) sell speed with no published latency numbers (market.md section 3). An independent, per-game market-vs-play audit is a quality-control line item. Example: about 30 buyers x $50-150K a year is about $1.5-4.5M **(assumption)**. |
| **3. Consumer "Spoiler Shield" subscription** | Fans who stream games | The price anchor is $10-30 a month: Action PRO costs $24.99/mo or $119.99/yr ([Action Network](https://www.actionnetwork.com/pro)) and Pikkit $29.99/mo (features.md). The tier ladder is free and delayed vs paid and live. Every 100,000 subscribers at $10/mo is $12M a year (arithmetic, not a market estimate). |

### Likely judge questions, with crisp answers
- **"Doesn't cable TV beat you?"** Yes. Our alerts arrive 23 to 33 s after the play, and broadcast TV is about 19 s behind. We beat streams (48 to 62 s) and ESPN's feed. The market itself moves at 7 s, so the 12 to 19 s our detector takes to fire is the engineering roadmap. Cutting it is how we would beat TV (STATS.md 6.1).
- **"Isn't 76% just because most jumps are 'nothing'?"** Always guessing "nothing" gets 64.7%; we get 76.3%. Trained on last season and tested on this one, we get 74.7%. On real big plays we get 89.7%, against 60.0% for a smart fan's rule. When we say 90%+, we are right 93%.
- **"What's the moat? XGBoost is standard."** Agreed, the algorithm is not the moat. The moat is the labeled dataset of 3,704 Kalshi fires matched to ESPN plays across two seasons, plus the timing measurement and an honest, public ledger. Competitors would have to rebuild all of it.
- **"Why not just buy the official feed?"** The NFL's official feed goes exclusively through Genius to sportsbooks, through the 2029 season ([Sportcal](https://www.sportcal.com/news/nfl-renews-expands-genius-sports-partnership-through-2029/)). Paid feeds are faster. We are free, public and independent, which is what an auditor needs to be.
- **"Will Kalshi or the NFL shut you down?"** We use only Kalshi's public endpoints, place no bets and trade on paper only. The NFL is hostile to manipulable contracts and insider trading ([Front Office Sports](https://frontofficesports.com/article/nfl-warns-prediction-markets-operators-over-vulnerable-bets/)), which makes an integrity monitor something they say they want. Risk: Kalshi's terms for commercial use of public data are an open question (section 6).
- **"Regulation could kill prediction markets."** The appeals courts are split: the Third Circuit sided with Kalshi, while the Ninth and Sixth sided with the states ([CNBC](https://www.cnbc.com/2026/09/25/appeals-court-rules-states-can-regulate-sports-prediction-markets.html)). Tighter rules raise demand for monitoring, and the latency audit works for sportsbooks too.
- **"Is Dutch Book a money machine?"** No. We scanned 103,807 markets and found 16 contradictions before fees and 0 after. That is evidence the market is efficient and that our accounting is honest. A fee-aware Kalshi backtest found the same: naive agents lose to fees ([PredictionMarketBench](https://arxiv.org/abs/2602.00133)).
- **"How is this different from Oddpool, Bot for Kalshi or whale trackers?"** Oddpool is a cross-market dashboard. Bot for Kalshi sends email threshold alerts. Whale trackers follow big Polymarket wallets. None of them infers the play type and times it against your stream (features.md).
- **"Who pays first?"** A prediction exchange or sportsbook compliance team for integrity screening. **Because:** they face CFTC insider-trading guidance now. Comparable data tools charge $100/mo (Oddpool Premium) up to a reported $3,000/mo for APIs (Unabated, low confidence).

## 6. Open questions that still need a source (or a measurement)

1. **Update STATS.md to the 11:53 model.** We have 3,704 fires, 77.3% (73.0% live) and an out-of-season test at 74.7% (69.4% live). We still lack the "always nothing" baseline on the new 1,267-fire live subset, and W&B still has no stage-3 run.
2. **More live confirmations.** Only 3 alerts are confirmed so far, all turnovers, and 2 are still pending. Every confirmed alert during today's games before 4pm makes the speed claim stronger.
3. **Is ESPN's play timestamp the real on-field time?** Our 7.0 s depends on ESPN's `wallclock`. We found no source that validates its accuracy.
4. **The stream delays (19/38/48/53/60/62 s) are Super Bowl reference values, not our measurement.** Regular-season delays for each service are unsourced, and the SVG article has a year typo.
5. **Kalshi's terms for commercial use of public market data and rate limits.** We found no source. This matters for every business model.
6. **Does anyone else detect plays from prediction-market flow?** Two rounds found nobody. Keep saying "we found none."
7. **Official-feed latency (Genius to sportsbooks).** No published number exists. Genius's "98% of US NFL betting data" claim is also unverified.
8. **Market sizing for the business models.** The buyer count and willingness to pay for latency audits are unsourced, and so is the number of US fans who stream NFL and also bet or trade live. The 1%-of-revenue integrity spend is an assumption.
9. **Kalshi 2026 year-to-date volume.** The $256.8B figure is unverified. Use only the verified pieces: a record week of $15.27B and a $22B valuation.
10. **Competitor prices still missing or conflicting:** OddsJam ($199.99-$399.99 on iOS vs $299 from Preqin), BetQL, Unabated, Covers/VSiN/WagerTalk, Dimers (one secondary source).
11. **Independent audits.** We found none of any AI pick site (Dimers 52.7%) or tout, and no published share of touts who beat the closing line.
12. **Someone Knew sample size.** It rests on 5 cases from 763 scanned, so a larger screen is needed before anyone quotes a rate.
13. **Unverified folklore that must stay off slides:** "only 3-5% of bettors profit long-run" (no primary study), and Mazi VS's sentence (the Gambling911 report contradicts itself, and there is no court record).

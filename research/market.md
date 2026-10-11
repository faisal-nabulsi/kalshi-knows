# Kalshi Knows: Market and Business Research (Rounds 1 and 2)

Written Sun Oct 11 2026. Plain language: jargon is defined at first use. Figures come from the linked sources; where sources disagree or I could not confirm a number, it says so.

## Executive summary

- **The pond is big and growing.** US sportsbooks took in about $166.9B of bets ("handle") and kept about $17.0B ("revenue") in 2025, a record ([Sports Betting Dime](https://www.sportsbettingdime.com/news/betting/u-s-sports-betting-revenues-rise-to-nearly-17-billion-in-2025/), [Legal Sports Report](https://www.legalsportsreport.com/263300/sportsbooks-make-more-money-from-slower-sports-betting-growth-in-2025/)).
- **Prediction markets are now a sports business.** Kalshi was valued at $22B in May 2026 ([The Block](https://www.theblock.co/post/400413/kalshi-hits-22-billion-valuation-after-1-billion-raise-led-by-coatue)). The 2026 year-to-date volume figure of $256.8B from round 1 is **(unverified)**: the cited DeFi Rate page does not contain it. Verified instead: DeFi Rate's tracker shows $133.97B year-to-date through July (contract-volume basis), and Kalshi's record week was $15.27B (Sept 14-20). Sports was 80% of Kalshi volume from July 2024 through April 2026 ([Pew, May 2026](https://www.pewresearch.org/short-reads/2026/05/27/trading-volume-on-prediction-markets-has-soared-in-recent-months/)); in June-July 2026 it was about 79% by our arithmetic from Pew's September table.
- **Speed is what the incumbents sell.** Genius Sports ($669.5M 2025 revenue) holds the exclusive NFL official data deal through the 2029 season (verified by Sportcal and SBC News; the earlier deal ended 2027-28), and Sportradar had EUR 1.29B revenue ([Genius 6-K](https://www.sec.gov/Archives/edgar/data/1834489/000119312526089847/geni-ex99_1.htm), [Sportradar](https://sportradar.com/content-hub/blog/sportradar-closes-2025-with-significant-growth-and-expanded-share-repurchase-plan/), [Business Wire](https://www.businesswire.com/news/home/20250611456305/en/The-National-Football-League-Expands-and-Extends-Strategic-Partnership-with-Genius-Sports-in-Multi-Year-Deal)). Our measured result (Kalshi prices move a median 7.0 s after ESPN's play timestamp; alerts beat ESPN's feed by 38.6 to 64.8 s) is our own data, not from these sources.
- **Consumer pick tools sell for about $25 to $100 per month**, so a paid alert product has clear price anchors.
- **Regulation is the main risk.** Appeals courts are split on whether states can block Kalshi sports contracts, the age minimum (18) is under attack, and insider-trading rules are tightening. This is a risk for Kalshi, and it is also demand for a monitoring product.
- **Recommended pitch:** lead with B2B latency auditing and market-integrity monitoring (the buyers have budgets and a legal need), with B2C Spoiler Shield as the consumer hook.

## 1. US sports betting size

- 2025 handle was about $166.94B, up roughly 11%; revenue was about $16.96B, up 22.8% (AGA headline) ([Sports Betting Dime](https://www.sportsbettingdime.com/news/betting/u-s-sports-betting-revenues-rise-to-nearly-17-billion-in-2025/)). Legal Sports Report cites a narrower AGA number of $16.89B that excludes tribal sportsbooks ([Legal Sports Report](https://www.legalsportsreport.com/263300/sportsbooks-make-more-money-from-slower-sports-betting-growth-in-2025/)). Treat about $17B as the right size.
- States collected $3.71B in sports betting taxes, up 32.4% ([Legal Sports Report](https://www.legalsportsreport.com/263300/sportsbooks-make-more-money-from-slower-sports-betting-growth-in-2025/)).
- Revenue grew about twice as fast as handle, because sportsbooks kept a bigger share ("hold") of each dollar bet ([Legal Sports Report](https://www.legalsportsreport.com/263300/sportsbooks-make-more-money-from-slower-sports-betting-growth-in-2025/)).
- All US commercial gaming revenue was a record $78.72B in 2025 ([InterGame](https://www.intergameonline.com/casino/news/aga-reports-record-us-commercial-gaming-revenue-in-2025)).

## 2. Prediction markets

A **prediction market** lets people trade yes/no contracts that pay $1 if an event happens. A **contract** is one such share; **volume** is dollars traded.

| Platform | Fact | Source |
|---|---|---|
| Kalshi | **(unverified)** Round 1 said $256.8B traded in 2026 through Oct 6 and $60.7B in September; the cited page does not show either. Verified pieces: $133.97B year-to-date through July (DeFi Rate, contract basis); $37.17B in August (The Block, down 7.3% from July's $40.1B, the first monthly decline in a year); $23.45B month-to-date Sept 13 (SCCG); record week $15.27B, Sept 14-20, with the first $3B day on Sept 20; $18.37B for Sept 28-Oct 4. Trackers use different bases (notional vs contract vs execution price), so never mix them | [DeFi Rate](https://defirate.com/news/kalshi-2026-volume-record-15b-week/), [The Block](https://www.theblock.co/news/business/2026-09-02-kalshi-polymarkets-volume-falls-august-413309), [DeFi Rate weekly](https://defirate.com/news/sept-28-oct-4-2026-volume-report/) |
| Kalshi | $1B Series F at $22B valuation, announced May 7, 2026 (Coatue led; Sequoia, a16z, IVP, Paradigm, Morgan Stanley, ARK); a $200M extension at the same valuation followed; late-June reports said Kalshi was seeking about $40B (unconfirmed) | [The Block](https://www.theblock.co/post/400413/kalshi-hits-22-billion-valuation-after-1-billion-raise-led-by-coatue), [Cooley](https://www.cooley.com/news/coverage/2026/2026-05-07-kalshi-raises-$1-billion-series-f) |
| Kalshi | Revenue run-rate estimates conflict: The Information said above $2B annualized in mid-June 2026; Sacra says $3.5B for June; a Dealroom report says above $4B in July. All are estimates, not filings. Audited anchor: 2025 fee revenue was $263.5M, about 89% from sports | [Sacra](https://sacra.com/research/kalshi-at-3b-year/), [Crowdfund Insider](https://crowdfundinsider.com/2026/06/286520-kalshi-reportedly-explores-early-ipo-path-as-annualized-revenue-tops-2-billion), [Dealroom](https://dealroom.co/news/144595-kalshi-eyes-40b-valuation-as-revenue-doubles-to-4b-annualized/), [CDC Gaming](https://cdcgaming.com/brief/kalshis-2025-fee-revenue-was-263-5m-with-89-coming-from-sports/) |
| Kalshi | Monthly volume: $226M (Dec 2024), $6.6B (Dec 2025), $29.2B (Jun 2026) | [Sacra](https://sacra.com/c/kalshi/) |
| Sports share | 80% of Kalshi volume and 39% of Polymarket, cumulative July 2024 through April 2026 (Pew May 2026 piece). Pew's Sept 2026 piece adds: June-July 2026 sports volume topped $58B on Kalshi and neared $22B on Polymarket, about 79% of Kalshi's June-July volume by our arithmetic. Pew measures notional value (each contract counted at its $1 payout) | [Pew May](https://www.pewresearch.org/short-reads/2026/05/27/trading-volume-on-prediction-markets-has-soared-in-recent-months/), [Pew Sept](https://www.pewresearch.org/short-reads/2026/09/23/prediction-markets-trading-volume-doubled-between-may-and-july-largely-driven-by-sports/) |
| Sports share (dispute) | 85% lifetime if "Exotics" is counted with Sports; Kalshi's CEO said the share is falling, and the gap is mostly category definitions | [SGI Europe](https://www.sgieurope.com/technology/kalshi-booms-on-sports/121847.article) |
| Robinhood | 13.6B event contracts in Q2 2026; event-contract revenue $156M (about $10M a year earlier), ahead of equities ($129M) and crypto ($100M). Verified in round 2 against two outlets; the Q1 baseline differs by source ($104M vs $147M) | [The Block](https://www.theblock.co/post/410102/robinhood-prediction-markets-top-crypto-and-equities-revenue-in-q2), [BrokerChooser](https://brokerchooser.com/news/prediction-markets-become-robinhoods-second-largest-revenue-driver--0c37bdeb) |
| Kalshi + Polymarket | Combined 2026 volume above $130B (a May report, so now out of date versus Kalshi alone at $256.8B; definitions differ) | [Pew](https://www.pewresearch.org/short-reads/2026/05/27/trading-volume-on-prediction-markets-has-soared-in-recent-months/) |

Why this matters for us: Kalshi's public order book is a live, price-based sensor for NFL games, and sports is where the volume is, so the signal is liquid.

## 3. Sports data market

- **Sportradar** (reports in euros): 2025 revenue EUR 1,290M, up 17%; adjusted EBITDA (profit before interest, tax, depreciation) EUR 297M, margin 23.0% ([Sportradar](https://sportradar.com/content-hub/blog/sportradar-closes-2025-with-significant-growth-and-expanded-share-repurchase-plan/), [Sportcal](https://www.sportcal.com/financial/sportradar-hits-record-revenue-in-2025-financial-results/)). About $1.5B in dollars ([SportBusiness](https://tech.sportbusiness.com/news/sportradar-revenues-hit-e1-3bn-forex-aids-profits/)).
- **Genius Sports** (dollars): 2025 revenue $669.5M, up 31%; adjusted EBITDA $136.2M ([SEC 6-K](https://www.sec.gov/Archives/edgar/data/1834489/000119312526089847/geni-ex99_1.htm)). Announced a $1.2B Legend acquisition ([Barchart](https://www.barchart.com/story/news/555609/genius-sports-reports-fourth-quarter-and-full-year-2025-results)).
- **Official league data:** Genius is the NFL's exclusive distributor of official real-time play-by-play, Next Gen Stats, and the betting data feed through the 2029 season, plus low-latency "Watch & Bet" video to sportsbooks ([Business Wire](https://www.businesswire.com/news/home/20250611456305/en/The-National-Football-League-Expands-and-Extends-Strategic-Partnership-with-Genius-Sports-in-Multi-Year-Deal)). The original 2021 deal was reported at roughly $100M to $120M per year; terms were not disclosed ([Legal Sports Report](https://www.legalsportsreport.com/50077/genius-sports-wins-nfl-data-rights/), [Ministry of Sport](https://ministryofsport.com/nfl-brings-in-genius-sports-as-data-partner/)).
- **Latency:** I found no published latency figures for the official feed. Genius's own docs call its GeniusPremium feed "low latency" ([Genius docs](https://geniussports.atlassian.net/wiki/x/VwIE9)). This gap is the opening for an independent auditor.

## 4. Subscription pick and analytics businesses

| Product | Price found | Confidence / source |
|---|---|---|
| Action Network PRO | $24.99/mo, $119.99/yr, $14.99/wk | Official page, fetched Oct 11 ([Action Network](https://www.actionnetwork.com/pro)) |
| Dimers Pro | $24.99/mo, $199.99/yr; $9.99/wk | One review blog, not the vendor ([Skillnation](https://skillnation.in/posts/dimers-college-football/)) |
| Rithmm | Core $29.99/mo or $239.99/yr; Premium $99.99/mo or $999.99/yr | App Store listing ([Apple](https://apps.apple.com/us/app/-/id1641010681)) |
| Unabated | Conflicting: $99 to $199/mo consumer tiers; API reported from $3,000/mo | Third-party comparisons ([Parse](https://www.parse.gl/rankings/prediction-markets/sports-betting-picks-analytics-services), [SportsGameOdds](https://sportsgameodds.com/compare/unabated)); low confidence |
| OddsJam | Not found (vendor page blocked, 403) | Parse says custom/premium ([Parse](https://www.parse.gl/rankings/prediction-markets/sports-betting-picks-analytics-services)) |
| BetQL | Not found; app is free with in-app purchases | [App Store](https://apps.apple.com/us/app/betql-sports-betting/id1334825645) |

Takeaway: mass-market tools cluster at $10 to $30 per month; pro tools (Unabated, Rithmm Premium) reach $100 to $200. Verify OddsJam and BetQL on their own pricing pages before quoting them to judges.

## 5. Regulation

- **Who regulates:** The CFTC (Commodity Futures Trading Commission, the federal futures regulator) oversees Kalshi as a registered exchange. States say sports contracts are gambling.
- **Courts are split.** The Third Circuit (April 6, 2026) sided with Kalshi on a preliminary basis ([Holland & Knight](https://www.hklaw.com/en/insights/publications/2026/04/federal-appeals-court-cftc-jurisdiction-over-sports-event-contracts), [Paul Weiss](https://www.paulweiss.com/insights/client-memos/a-divided-third-circuit-holds-that-the-cftc-has-exclusive-jurisdiction-over-sports-related-event-contracts)). The Third Circuit panel was 2-1 (Judge Roth dissenting) and only found Kalshi likely to win; the case returns to the district court. The Ninth Circuit ruled for Nevada in August ([PYMNTS](https://www.pymnts.com/legal/2026/a-second-federal-appeals-court-rules-sports-event-contracts-are-not-swaps/)). The Sixth Circuit (Sept 25-26, 2026) held states can regulate in Ohio and Tennessee ([CNBC](https://www.cnbc.com/2026/09/25/appeals-court-rules-states-can-regulate-sports-prediction-markets.html), [Prediction News](https://predictionnews.com/story/kalshi-split-widens-with-6th-circuit-ruling-on-sports-event-contracts)). Maryland (Fourth Circuit) is pending, and a Supreme Court request is expected. About 20 states are challenging these contracts ([Prediction News](https://predictionnews.com/story/about-20-states-still-challenging-sports-event-contracts-from-kalshi-polymarket)).
- **CFTC backs the exchanges** and sued states including Arizona, Connecticut and Illinois on April 2, 2026 ([Paul Weiss](https://www.paulweiss.com/insights/client-memos/a-divided-third-circuit-holds-that-the-cftc-has-exclusive-jurisdiction-over-sports-related-event-contracts)).
- **Age:** Kalshi keeps 18+, while most sportsbooks require 21+. New York's Attorney General sued on July 31, 2026, seeking at least $36B in penalties and disgorgement, partly over this (the CFTC filed its own suit against New York the same day); Kalshi says 18-to-21-year-olds are 3.14% of its volume; a CNN analysis (estimate, disputed by Kalshi) found 18-to-21-year-olds traded about $5.4B on Kalshi in 2026 ([Business Today](https://www.businesstoday.in/world/story/young-americans-aged-18-21-traded-5-4-billion-on-kalshi-this-year-report-551992-2026-08-28), [Crypto Briefing](https://cryptobriefing.com/cftc-kalshi-new-york-gambling-lawsuit/)). Relevance: many VSS judges and our own peers are 18 to 20, so keep our app free of real-money features (paper trading only) and say so.
- **Insider trading:** CFTC Enforcement issued an advisory Feb 25, 2026 ([CFTC](https://www.cftc.gov/PressRoom/PressReleases/9185-26)); staff advisory 26-08 (March 12) covers sports contracts ([CFTC](https://www.cftc.gov/csl/26-08/download)); an advance notice of proposed rulemaking followed in March ([Sidley](https://www.sidley.com/en/insights/newsupdates/2026/03/us-cftc-issues-guidance-advance-notice-of-proposed-rulemaking)). The first event-contract insider case was filed April 23, 2026, against an active-duty Army service member for trading on Polymarket (not Kalshi, not an athlete); it alleges about $404,000 in profit ([Foley](https://www.foley.com/insights/publications/2026/05/insider-predicting-cftcs-first-action-and-how-we-got-here/)). The CFTC is talking with all major leagues and has an MOU with MLB ([CoinDesk](https://www.coindesk.com/policy/2026/05/12/the-cftc-is-in-talks-with-every-major-pro-sports-league-to-crack-down-on-insider-trading)). Kalshi bans athletes, coaches and officials from trading their own sport ([CoinDesk](https://www.coindesk.com/policy/2026/05/12/the-cftc-is-in-talks-with-every-major-pro-sports-league-to-crack-down-on-insider-trading)). I found no final rule yet.

## 6. Three business models for Kalshi Knows

1. **B2C "Spoiler Shield" and spoiler alerts.** Subscription priced at the $10 to $25 per month anchor set by Action PRO. Because streams run 19 to 62 s behind live (our measurement), fans watching with delay get alerts first, or can have spoilers hidden. TAM logic: Robinhood alone saw 13.6B contracts in a quarter, so millions of sports-engaged users already sit in this behavior; even 0.1% of 1M Robinhood-type users at $15/mo is about $180K per year ([Gambling Insider](https://www.gamblinginsider.com/news/157029/robinhood-q1-prediction-markets-record-volume)). The user count is an assumption, not a sourced figure.
2. **B2B latency auditing** for streamers, sportsbooks and leagues. We independently measure how far each feed lags real play. TAM logic: Genius ($669.5M) and Sportradar (EUR 1.29B) sell speed, and no published latency numbers exist, so an auditor serves buyers of a multi-billion-dollar data market ([SEC 6-K](https://www.sec.gov/Archives/edgar/data/1834489/000119312526089847/geni-ex99_1.htm), [Sportradar](https://sportradar.com/content-hub/blog/sportradar-closes-2025-with-significant-growth-and-expanded-share-repurchase-plan/)). Budget logic: compliance spend, not a share of data revenue.
3. **Market-integrity monitoring ("Someone Knew")** for exchanges, leagues and regulators. We flag price moves before public news. TAM logic: the CFTC is in talks with every major league, has launched rulemaking, and Kalshi already contracts a monitor, so there are named buyers with a legal need ([CoinDesk](https://www.coindesk.com/policy/2026/05/12/the-cftc-is-in-talks-with-every-major-pro-sports-league-to-crack-down-on-insider-trading), [PaymentExpert](https://paymentexpert.com/2025/03/25/kalshi-railguards-judgments-mlb-us/)).
4. **(Bonus) Data licensing** of the labeled Kalshi-fire dataset (1,596 fires, 66 games) to quant and research buyers. TAM logic: Unabated-style data products reportedly start near $3,000 per month, though that figure is low confidence ([SportsGameOdds](https://sportsgameodds.com/compare/unabated)).

Recommendation and the "because": lead with 2 and 3. Their buyers face legal and revenue pressure and pay for evidence, while consumer subscriptions (1) face a crowded $25-per-month field and depend on an unproven user base.

## 7. Round 2 additions: facts round 1 missed

- **The NFL is hostile to prediction markets, which shapes the pitch.** The NFL has no prediction-market partnership, banned prediction-market advertising (extended to sportsbook partners that also offer event contracts), renewed DraftKings, FanDuel and Fanatics without letting them promote event contracts, and sent letters objecting to manipulable contracts such as kicker misses and injuries; Kalshi agreed to stop injury contracts at the CFTC's request. The NFL also told a court that prediction markets are sports gambling. Commissioner Goodell says talks continue. Because the league fears manipulable and insider-driven contracts, an independent integrity monitor ("Someone Knew") fits their stated concern. Genius is also the NFL's official integrity-services provider, so it is an incumbent in that role ([FOS](https://frontofficesports.com/article/nfl-warns-prediction-markets-operators-over-vulnerable-bets/), [Casino.org](https://casino.org/news/nfl-wants-stronger-prediction-market-oversight-before-considering-partnerships), [Gambling Insider](https://www.gamblinginsider.com/news/151450/nfl-urges-prediction-markets-avoid-manipulable-contracts), [SBC News on the Genius deal](https://sbcnews.co.uk/technology/2025/06/11/genius-sports-nfl-2029/)).
- **NFL volume on Kalshi is large:** about $983M in Week 1 of 2026 alone (iGamingBusiness), and a forecast of up to $57B of NFL prediction-market volume this season (DeFi Rate, a forecast, not a measurement) ([iGB](https://igamingbusiness.com/sports-betting/kalshi-polymarket-beat-rivals-nfl-week-1/), [DeFi Rate](https://defirate.com/?p=19424)).
- **How Kalshi makes money:** a taker fee of 0.07 x contracts x price x (1 - price), rounded up to the cent, so about 1.75 cents on a 50-cent contract; maker fees use a lower multiplier. 2025 fees were about 1.2% of the volume they applied to. This is from third-party analyses of the February 2026 schedule, not Kalshi's page ([ATS.io](https://ats.io/prediction-markets/kalshi/fees/), [CDC Gaming](https://cdcgaming.com/brief/kalshis-2025-fee-revenue-was-263-5m-with-89-coming-from-sports/)).
- **Competitors from sportsbooks:** FanDuel Predicts (a joint venture with CME Group) and DraftKings Predictions are live, reportedly with about $600M of 2026 marketing between them (single secondary source, low confidence) ([BlockEden](https://blockeden.xyz/blog/2026/04/27/fanduel-prediction-markets-kalshi-polymarket-sportsbook-pivot/)). Polymarket's implied valuation near $20B is an analyst figure, not a confirmed round ([H2GC](https://h2gc.com/news/general/prediction-markets-overhyped-and-underperforming)).
- **Prediction markets divert tax revenue:** the AGA estimates over $500M of potential sports-betting tax revenue has gone to prediction markets so far, which is why states and the AGA are litigation allies ([AGA](https://www.americangaming.org/new/commercial-gaming-revenue-hits-78-7-billion-in-2025-driving-record-18-1-billion-in-gaming-taxes-nationwide/)).
- **Genius 2026 outlook:** standalone revenue guidance of $810-820M, about $1.1B pro forma with Legend ([Barchart](https://www.barchart.com/story/news/555609/genius-sports-reports-fourth-quarter-and-full-year-2025-results)).

## Caveats

- Several prediction-market numbers come from aggregators (DeFi Rate, Sacra, Dune-based sites) and conflict on definitions.
- Robinhood Q2 2026 figures come from two press reports of the earnings release, not from the 10-Q itself.
- The Kalshi 2026 year-to-date and September volume numbers from round 1 could not be reproduced (see the verification log).
- OddsJam and BetQL prices were not found; Dimers and Unabated prices are secondary.
- Court dates for the Sixth Circuit differ by one day across outlets.

## Verification log (round 2, Oct 11 2026)

| # | Claim | Verdict | Independent source |
|---|---|---|---|
| 1 | 2025 US sports betting handle $166.94B (+11.0%), revenue $16.96B (+22.8%), taxes $3.71B (+32.4%) | Verified (AGA tracker; $16.89B excludes tribal in the State of the States report) | [AGA](https://www.americangaming.org/new/commercial-gaming-revenue-hits-78-7-billion-in-2025-driving-record-18-1-billion-in-gaming-taxes-nationwide/) |
| 2 | Kalshi $256.8B in 2026 through Oct 6; $60.7B in Sept | **Unverified.** Cited page lacks both; verified partial figures added in section 2 | [DeFi Rate](https://defirate.com/news/kalshi-2026-volume-record-15b-week/), [The Block](https://www.theblock.co/news/business/2026-09-02-kalshi-polymarkets-volume-falls-august-413309) |
| 3 | Kalshi $22B valuation, May 2026 | Verified ($1B Series F, May 7; $200M extension; about $40B talks reported) | [The Block](https://www.theblock.co/post/400413/kalshi-hits-22-billion-valuation-after-1-billion-raise-led-by-coatue), [Cooley](https://www.cooley.com/news/coverage/2026/2026-05-07-kalshi-raises-$1-billion-series-f) |
| 4 | Sports 80% of Kalshi, 39% of Polymarket since July 2024 (Pew Sept) | Corrected: figure is from Pew's May 2026 piece (through April 2026), not the Sept piece | [Pew May](https://www.pewresearch.org/short-reads/2026/05/27/trading-volume-on-prediction-markets-has-soared-in-recent-months/) |
| 5 | Genius 2025 revenue $669.5M (+31%), adj. EBITDA $136.2M | Verified | [Insider Sport](https://insidersport.com/2026/03/05/genius-sports-fy2025-results/) |
| 6 | Sportradar 2025 revenue EUR 1,290M (+17%), adj. EBITDA EUR 297M | Verified (released Mar 3, 2026) | [SEC 6-K via search](https://investors.sportradar.com/node/9431/pdf) |
| 7 | Genius exclusive NFL data through 2029 | Verified (end of the 2029 season; prior deal ran to 2027-28). Business Wire page returned 403 to us, so confirmed via trade press | [Sportcal](https://www.sportcal.com/news/nfl-renews-expands-genius-sports-partnership-through-2029/), [SBC News](https://sbcnews.co.uk/technology/2025/06/11/genius-sports-nfl-2029/) |
| 8 | Action Network PRO $24.99/mo, $119.99/yr | Verified on the official page; app-store trackers also show a $19.99 monthly and older $29.99, so promos vary | [Action Network](https://www.actionnetwork.com/pro), [AppPricingLab](https://apppricinglab.com/iap/apple/1083677479) |
| 9 | Third Circuit for Kalshi Apr 6; Ninth for Nevada; Sixth for Ohio/Tennessee Sept 25 | Verified (Third 2-1, preliminary injunction only; Ninth in August; Sixth unanimous, Sept 25; one outlet, Phemex, wrongly reported a Kalshi win) | [Lowenstein](https://www.lowenstein.com/news-insights/publications/client-alerts/third-circuit-affirms-preliminary-injunction-in-favor-of-kalshi-fctm), [SBC Americas](https://sbcamericas.com/2026/09/25/kalshi-sixth-circuit-sides-oh-tn/) |
| 10 | CFTC first event-contract insider action Apr 23 2026 | Verified; detail added: defendant traded on Polymarket, not Kalshi | [Lowenstein](https://lowenstein.com/news-insights/publications/client-alerts/cftc-and-kalshi-announce-enforcement-actions-targeting-prediction-markets-fctm) |
| 11 | NY AG sued Kalshi July 2026 over age; 18-21 traded $5.4B | Verified (filed July 31, seeks at least $36B; $5.4B is a CNN estimate, $3.9B of it sports; Kalshi says 3.14% of volume) | [NY1](https://ny1.com/nyc/all-boroughs/news/2026/07/31/new-york-sues-kalshi--alleging-illegal-gambling-operation-), [KEYT/CNN](https://keyt.com/news/money-and-business/cnn-business-consumer/2026/08/28/young-adults-under-21-traded-5-billion-on-kalshi-this-year-amid-prediction-market-frenzy/) |
| 12 | Kalshi about $4B annualized revenue (attributed to Sacra) | Corrected: Sacra says $3.5B (June); $2B+ (The Information, mid-June); $4B+ (Dealroom, July). Run-rates are estimates | [Sacra](https://sacra.com/research/kalshi-at-3b-year/), [Dealroom](https://dealroom.co/news/144595-kalshi-eyes-40b-valuation-as-revenue-doubles-to-4b-annualized/) |
| 13 | Robinhood Q2 2026: 13.6B contracts, $156M revenue | Verified; no longer unconfirmed | [The Block](https://www.theblock.co/post/410102/robinhood-prediction-markets-top-crypto-and-equities-revenue-in-q2) |

Not re-checked in round 2: Rithmm and Dimers prices, Unabated pricing, the CFTC MOU with MLB, and the ANPRM details.

## Sources

- [Sports Betting Dime, 2025 revenue](https://www.sportsbettingdime.com/news/betting/u-s-sports-betting-revenues-rise-to-nearly-17-billion-in-2025/)
- [Legal Sports Report, 2025](https://www.legalsportsreport.com/263300/sportsbooks-make-more-money-from-slower-sports-betting-growth-in-2025/)
- [InterGame, AGA 2025](https://www.intergameonline.com/casino/news/aga-reports-record-us-commercial-gaming-revenue-in-2025)
- [DeFi Rate, Kalshi volume](https://defirate.com/news/kalshi-2026-volume-record-15b-week/)
- [Sacra, Kalshi](https://sacra.com/c/kalshi/)
- [Pew, Sept 2026](https://www.pewresearch.org/short-reads/2026/09/23/prediction-markets-trading-volume-doubled-between-may-and-july-largely-driven-by-sports/)
- [Pew, May 2026](https://www.pewresearch.org/short-reads/2026/05/27/trading-volume-on-prediction-markets-has-soared-in-recent-months/)
- [SGI Europe](https://www.sgieurope.com/technology/kalshi-booms-on-sports/121847.article)
- [Gambling Insider, Robinhood](https://www.gamblinginsider.com/news/157029/robinhood-q1-prediction-markets-record-volume)
- [Sportradar FY2025](https://sportradar.com/content-hub/blog/sportradar-closes-2025-with-significant-growth-and-expanded-share-repurchase-plan/)
- [Sportcal](https://www.sportcal.com/financial/sportradar-hits-record-revenue-in-2025-financial-results/)
- [SportBusiness](https://tech.sportbusiness.com/news/sportradar-revenues-hit-e1-3bn-forex-aids-profits/)
- [Genius 6-K FY2025](https://www.sec.gov/Archives/edgar/data/1834489/000119312526089847/geni-ex99_1.htm)
- [Barchart, Genius](https://www.barchart.com/story/news/555609/genius-sports-reports-fourth-quarter-and-full-year-2025-results)
- [Business Wire, NFL-Genius 2025](https://www.businesswire.com/news/home/20250611456305/en/The-National-Football-League-Expands-and-Extends-Strategic-Partnership-with-Genius-Sports-in-Multi-Year-Deal)
- [Legal Sports Report, NFL data rights](https://www.legalsportsreport.com/50077/genius-sports-wins-nfl-data-rights/)
- [Ministry of Sport](https://ministryofsport.com/nfl-brings-in-genius-sports-as-data-partner/)
- [Genius docs](https://geniussports.atlassian.net/wiki/x/VwIE9)
- [Action Network PRO](https://www.actionnetwork.com/pro)
- [Skillnation, Dimers](https://skillnation.in/posts/dimers-college-football/)
- [Rithmm, App Store](https://apps.apple.com/us/app/-/id1641010681)
- [BetQL, App Store](https://apps.apple.com/us/app/betql-sports-betting/id1334825645)
- [Parse rankings](https://www.parse.gl/rankings/prediction-markets/sports-betting-picks-analytics-services)
- [SportsGameOdds vs Unabated](https://sportsgameodds.com/compare/unabated)
- [Holland & Knight](https://www.hklaw.com/en/insights/publications/2026/04/federal-appeals-court-cftc-jurisdiction-over-sports-event-contracts)
- [Paul Weiss](https://www.paulweiss.com/insights/client-memos/a-divided-third-circuit-holds-that-the-cftc-has-exclusive-jurisdiction-over-sports-related-event-contracts)
- [PYMNTS](https://www.pymnts.com/legal/2026/a-second-federal-appeals-court-rules-sports-event-contracts-are-not-swaps/)
- [CNBC, Sixth Circuit](https://www.cnbc.com/2026/09/25/appeals-court-rules-states-can-regulate-sports-prediction-markets.html)
- [Prediction News, Sixth Circuit](https://predictionnews.com/story/kalshi-split-widens-with-6th-circuit-ruling-on-sports-event-contracts)
- [Prediction News, 20 states](https://predictionnews.com/story/about-20-states-still-challenging-sports-event-contracts-from-kalshi-polymarket)
- [Business Today, age 18-21](https://www.businesstoday.in/world/story/young-americans-aged-18-21-traded-5-4-billion-on-kalshi-this-year-report-551992-2026-08-28)
- [Crypto Briefing, NY suit](https://cryptobriefing.com/cftc-kalshi-new-york-gambling-lawsuit/)
- [CFTC enforcement advisory](https://www.cftc.gov/PressRoom/PressReleases/9185-26)
- [CFTC Letter 26-08](https://www.cftc.gov/csl/26-08/download)
- [Sidley, ANPRM](https://www.sidley.com/en/insights/newsupdates/2026/03/us-cftc-issues-guidance-advance-notice-of-proposed-rulemaking)
- [Foley, first insider action](https://www.foley.com/insights/publications/2026/05/insider-predicting-cftcs-first-action-and-how-we-got-here/)
- [CoinDesk, CFTC and leagues](https://www.coindesk.com/policy/2026/05/12/the-cftc-is-in-talks-with-every-major-pro-sports-league-to-crack-down-on-insider-trading)
- [PaymentExpert, Kalshi integrity monitor](https://paymentexpert.com/2025/03/25/kalshi-railguards-judgments-mlb-us/)
- [Cooley, Kalshi Series F](https://www.cooley.com/news/coverage/2026/2026-05-07-kalshi-raises-$1-billion-series-f)
- [The Block, Kalshi $22B](https://www.theblock.co/post/400413/kalshi-hits-22-billion-valuation-after-1-billion-raise-led-by-coatue)
- [The Block, August volume](https://www.theblock.co/news/business/2026-09-02-kalshi-polymarkets-volume-falls-august-413309)
- [DeFi Rate, Sept 28-Oct 4](https://defirate.com/news/sept-28-oct-4-2026-volume-report/)
- [Sacra, Kalshi $3.5B](https://sacra.com/research/kalshi-at-3b-year/)
- [Dealroom, Kalshi $4B](https://dealroom.co/news/144595-kalshi-eyes-40b-valuation-as-revenue-doubles-to-4b-annualized/)
- [CDC Gaming, Kalshi 2025 fees](https://cdcgaming.com/brief/kalshis-2025-fee-revenue-was-263-5m-with-89-coming-from-sports/)
- [Front Office Sports, NFL and prediction markets](https://frontofficesports.com/article/nfl-warns-prediction-markets-operators-over-vulnerable-bets/)
- [Casino.org, NFL oversight](https://casino.org/news/nfl-wants-stronger-prediction-market-oversight-before-considering-partnerships)
- [Sportcal, NFL-Genius through 2029](https://www.sportcal.com/news/nfl-renews-expands-genius-sports-partnership-through-2029/)
- [The Block, Robinhood Q2](https://www.theblock.co/post/410102/robinhood-prediction-markets-top-crypto-and-equities-revenue-in-q2)
- [NY1, NY sues Kalshi](https://ny1.com/nyc/all-boroughs/news/2026/07/31/new-york-sues-kalshi--alleging-illegal-gambling-operation-)
- [Lowenstein, CFTC and Kalshi enforcement](https://lowenstein.com/news-insights/publications/client-alerts/cftc-and-kalshi-announce-enforcement-actions-targeting-prediction-markets-fctm)

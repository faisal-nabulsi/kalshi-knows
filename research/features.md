# Round 1 Research: Competitor Feature Teardown and Design Patterns

Date: Sun Oct 11 2026. Scope: products close to "Kalshi Knows" (prediction-market analytics, live win-probability, bettor alert apps, spoiler tools).

## Executive summary

- No competitor does what we do. Kalshi order-book jump detection that infers the play type and warns you before your TV stream shows it is not offered by any product I found. The nearest ideas are whale alerts on Polymarket ([FlukeWatch](https://hunted.space/product/flukewatch)) and cross-venue dashboards ([Oddpool](https://www.oddpool.com)). Absence of evidence in search results is not proof, so say "we found no one else" on stage, not "no one else exists."
- No spoiler-delay tool exists for NFL either. A search found only a YouTube TV "Broadcast Delay" setting that trims 10-30 s of lag, and a note that score-app alerts often arrive before the stream ([Cord Cutters News](https://cordcuttersnews.com/3-pro-tips-youtube-tv-subscribers-need-to-know-to-make-watching-sports-even-better/)). This frames our product as the fix for a known annoyance.
- The paid products win on three habits: (1) a trust score ranking people by calibration, not profit ([FlukeWatch](https://hunted.space/product/flukewatch)); (2) user-set alert thresholds ([Pikkit](https://apps.apple.com/app/id1586567110), [OddsJam](https://ideausher.com/blog/betting-arbitrage-platform-development/)); (3) one-tap sharing and a social feed ([Pikkit](https://apps.apple.com/app/id1586567110), [Prediction Hunt](https://prediction.com/odds/nfl/green-bay-packers-vs-denver-broncos-2026-08-21/34195)).
- "Premium" feel in this category comes from naming things as a score or tier (Influence Score, Copyability Score, Shark/Dolphin tiers), showing fee and spread context next to every number, and having one-line "what this means" explainers. Our Predator Scale already fits this pattern.
- Source quality caveat: much of the competitor detail comes from directory pages and auto-generated summaries, not the companies' own sites. I mark claims as "third-party" where that applies. Several products (Polymarket Analytics, Juice Reel, inpredictable, ESPN Gamecast, Kalshi's own live UI) could not be verified; see "Gaps."

## 1. Prediction-market analytics dashboards

**Oddpool** (cross-venue analytics; Y Combinator-listed per a third-party profile).
- Features on its own page: search across 700K+ Kalshi and Polymarket markets, live probability streaming, historical full-depth order-book snapshots (an "order book" is the list of open buy and sell offers), trade tape, cross-venue hedge ratios and price divergence "with fee and spread context," an Arbitrage Dashboard, Volume Dashboard, Whale Tracking, Paper Trading, and an AI chat called Oddbot ([Oddpool](https://www.oddpool.com)).
- Stats shown: aggregated probabilities, depth, spread and skew, trade price/size/taker side ([Oddpool](https://www.oddpool.com)).
- Tiers: Free (1,000 API requests/month), Pro $30/mo ($200/yr per third party), Premium $100/mo, plus an Institutional tier priced by sales call ([Oddpool](https://www.oddpool.com)). Round 2: Oddpool's changelog says Premium launched March 2026 and adds API access/custom alerting, and that a third venue (Opinion) was added to the arbitrage scanner in Feb 2026, so "Kalshi/Polymarket only" is stale. The page lists Arbitrage, Whales and Paper Trading by name only; feature depth is unverified.
- Third-party profiles add 40+ curated free dashboards (corroborated by a second search summary) and whale alerts for trades over $500 ([Extruct](https://www.extruct.ai/hub/oddpool-com/), [Dealroom](https://app.dealroom.co/companies/oddpool)); the $500 threshold is (unverified).
- Its arbitrage scanner reports net profit after fees, which matches our fee-aware Dutch Book framing (16 before fees, 0 after) ([Oddpool NFL page via search](https://www.oddpool.com/nfl-weekly)).
- What looks premium: a developer-style curl example and Parquet archive, i.e. "serious data." Visual style and chart types are not described on the page.

**FlukeWatch** (Polymarket whale tracker).
- Shows every trade of $10k or more live; ranks traders by calibration (how often stated confidence matches outcomes) instead of raw profit; free tier has the feed and leaderboards; paid "Tracker" tier adds Telegram alerts and signals; watchlists by category ([FlukeWatch listing](https://hunted.space/product/flukewatch)).
- Launch traction was minimal (0 upvotes on Product Hunt per the listing), so it is a design reference, not proof of demand.

**Other Polymarket whale trackers** (third-party summaries).
- PolyTrends: live whale feed, an Influence Score blending capital, profitability, consistency, activity and longevity, refreshed every five minutes, plus wallet archetypes ([search summary](https://alternativeto.net/software/polytrends--polymarket-whale-tracker/about)).
- PolyTrack: wallet profiles with P&L history, win rate, volume, open positions, category specialty ([pm.wiki](https://pm.wiki/uk/projects/polytrack)).
- GodEye: "Copyability Score" for copy-trading ([pm.wiki](https://pm.wiki/uk/projects/godeye-fun)).
- Apify actor tiers wallets as Whale / Shark / Dolphin / Fish / Retail ([Apify](https://apify.com/jy-labs/polymarket-whale-tracker?fpr=data)). This is the closest analog to our Predator Scale.
- Free 1-hour-delayed alerts versus $29/mo real-time (unverified, single directory) is a common freemium split ([pm.wiki Polymaster](https://pm.wiki/uk/projects/polymaster)).

**PolyMaster** (open-source Rust command-line tool): watches both Polymarket and Kalshi, default $5,000 threshold, audio plus terminal alerts, flags wallets that double or flip positions, uses Kalshi WebSocket with HTTP polling fallback ([pm.wiki](https://pm.wiki/uk/projects/polymaster)).

**Betmoar** (Polymarket Discord terminal): "Smart Money," "Whale Alerts," and "Insider Funding" labels, market delta analysis, trading inside Discord; self-reported 50,000+ users across 30+ servers (unverified directory claim) ([QuickNode directory](https://www.quicknode.com/builders-guide/tools/betmoar-by-betmoar-pte-ltd), [pm.wiki](https://pm.wiki/hi/compare/betmoar-vs-predictfi-one)). Note: the "Insider Funding" label is exactly the accusation our contract forbids; we say "the market moved before the first article."

**Verso** (pitched as a "Bloomberg Terminal for prediction markets"): live Kalshi data, a news engine, real-time alerts; details thin ([pm.wiki](https://pm.wiki/fr/compare/tryodds-fun-vs-verso)).

**Prediction Hunt** (predictionhunt.com, also branded prediction.com; round 2: also compares Polymarket US): per-game page with a Kalshi vs Polymarket odds table, 30-day probability chart, spread stat (1.0% on that page; other games show 1.0-2.5%, with 2.5% labelled an "active arbitrage window"), resolution-rules panels, FAQ explaining what a price means, share buttons for X/Telegram/WhatsApp/Reddit, related-game links ([Prediction Hunt game page](https://prediction.com/odds/nfl/green-bay-packers-vs-denver-broncos-2026-08-21/34195)).

**Kalshi's own app/site**: NFL browse path (Sports, Football, NFL; Props, Futures, Win Totals, Awards), Combos builder, price and payout preview, sell-before-settlement, and derived views like market-implied standings, power rankings and a projected playoff bracket ([Sports Illustrated review](https://www.si.com/prediction-markets/reviews/kalshi-nfl)). Round 2: Kalshi's help center confirms email, push and in-app notification toggles with a price-movement option under Predictions and only "Major events" under Sports; no live-game price-jump alert is documented. I could not confirm in-game charts or dedicated live-game push alerts in Kalshi's app ([search results](https://sailgp.com/prediction-markets/trending/best-prediction-market-apps-for-nfl-week-1-weekend-09-10-2026)).

## 2. Live win-probability products

- ESPN added a win-probability graphic to MLB broadcast score bugs in 2024, a small percent bar that updates after each play, pitched partly at bettors ([NewscastStudio](https://www.newscaststudio.com/2024/03/14/espn-brings-win-probability-to-mlb-score-bug/)). Critics (Defector, Awful Announcing) called it redundant because the score already works as a win probability, and said it makes viewers less invested ([Defector](https://defector.com/espns-win-probability-graphic-wants-to-give-you-gambling-brain)). Correction (round 2): Defector's actual argument was "redundant," not "tells no story"; the per-alert explainer idea is our own inference, not a Defector finding. Lesson (ours): pair every number with the play that caused it.
- I could not verify Gamecast's or Bet Center's current NFL features from search ([search results](https://defector.com/espns-win-probability-graphic-wants-to-give-you-gambling-brain)).
- Academic and open models: logistic win-probability from score gap, time left, field position, down and timeouts; nflfastR adds expected points and the spread ([arXiv iWinRNFL](https://arxiv.org/abs/1704.00197v3), [MetricGate](https://metricgate.com/docs/in-game-win-probability-football/)). "Leverage Index" (how much one moment can swing the result) is a ready-made stat for a "biggest swing" label ([FanGraphs](https://library.fangraphs.com/misc/li), [Football Perspective](https://www.footballperspective.com/super-bowl-leverage-and-the-best-postseason-passers-since-1966/)).
- The Athletic's fourth-down calculator and the Twitter bot share the open nfl4th package ([nfl4th docs](https://cloud.r-project.org/web/packages/nfl4th/refman/nfl4th.html)); I found nothing on The Athletic's live-blog format. The "inpredictable" site could not be found.

## 3. Alert and notification apps for bettors

**Action Network**: free account gives live odds from 50+ books, bet tracking, following friends and experts ([FAQ via search](https://www.actionnetwork.com/general/faq)). Opt-in pushes for game start, scores, halftime, bet final, and when a followed expert posts a pick; confirmed round 2 on Action Network's own page. New: Action PRO gets expert-pick alerts in real time versus a 30-minute delay for everyone else, a live example of a paid "speed" ladder ([Action Network](https://www.actionnetwork.com/general/action-network-mobile-app-must-have-sports-fans), [Action PRO page](https://www.actionnetwork.com/general/action-pro-picks-tools-projections)). Best-price book is highlighted at the top; QuickSlip sends a bet to a sportsbook in one tap. Sharp-money and tickets-versus-dollars data sit behind the paid tier, though sources disagree on what is free ([RotoGrinders](https://rotogrinders.com/sports-betting/guides/best-odds-apps)).

**Pikkit**: auto-sync from 30+ books; analytics by sport and bet type; unit-based display with dollars private by default; follow and copy verified top performers; live leaderboards; invite-friends competition; QuickPickBot turns text or screenshots into shareable slip links for Discord and iMessage; Pro Market Alerts when a line hits your level; 4.9 stars from roughly 20K ratings (third-party tracker, May 2026, says 20.1K; round 1 said 22K, unconfirmed); $29.99/mo or $199.99/yr (third-party price tracker, May 2026); an automated review-sentiment tool puts only 32% of reviews positive, so "4.9" is not the whole story ([App Store](https://apps.apple.com/app/id1586567110)).

**OddsJam**: compares odds across books, flags arbitrage and +EV (a bet priced better than the "fair" price taken from a sharp book such as Pinnacle) ([RotoWire](https://www.rotowire.com/article/arbitrage-betting-finder-7-day-free-trial-with-oddsjam-98274)). Alerts reportedly filter by sport, minimum profit and book ([IdeaUsher, development-firm blog](https://ideausher.com/blog/betting-arbitrage-platform-development/)). Price (round 2): iOS listing shows Gold $199.99/mo and Global $399.99/mo, Preqin says $299/mo ($199 annual), IdeaUsher says Platinum ~$499; the old "$99" figure is not supported. 7-day free trial.

**Juice Reel**: only found as a bet tracker syncing sportsbooks; no alert or social detail verified ([search summary](https://parse.gl/brands/pikkit-com)).

**Bot for Kalshi** (round 2, new): Complete plan $99/mo; email-only alerts (no push/SMS) for Kalshi price thresholds, ESPN live score margin or "next team to score," weather, news; polling is "timely rather than tick-by-tick" ([Bot for Kalshi](https://www.botforkalshi.com/kalshi-alerts)). Closest thing to our spoiler feed, but threshold-based, email, no play-type inference, so we still differ.

**alerts.chat / Polylerts / WhaleWatch** (Telegram and push): custom price alerts for Polymarket and Kalshi, tracked wallets, filters by size/odds/category/source ([pm.wiki alerts.chat](https://pm.wiki/uk/projects/alerts-chat), [pm.wiki Polymaster](https://pm.wiki/uk/projects/polymaster)).

## 4. Spoiler-avoidance tools

- No NFL tool syncs scores to a viewer's stream delay. Options found: YouTube TV Broadcast Delay (smart TVs only), hiding scores, muting push alerts ([Cord Cutters News](https://cordcuttersnews.com/3-pro-tips-youtube-tv-subscribers-need-to-know-to-make-watching-sports-even-better/)). Axwave's audio-recognition sync targets NBA and FanDuel ([Loyalty360](https://loyalty360.org/Content-Gallery/Daily-News/Axwave-Increases-CX-with-Fanduel-and-NBA-Partnersh)). MLB's app notification delay was also covered by The Verge ([via Scour](https://scour.ing/p/https://www.theverge.com/tech/800279/mlb-app-baseball-notifications-delay)).
- Round 2 correction: a fixed-delay precedent exists. The MLB app has a "Delayed Gameday Notifications" setting that holds alerts 30 s, and The Verge called it the app's best feature ([Six Colors](https://sixcolors.com/post/2024/03/mlb-app-will-slow-itself-down-let-your-media-stream-catch-up/)). So say "no NFL tool offers an adjustable, per-viewer delay," not "nobody has a delay." Our stream delay slider is the adjustable version of that 30 s toggle.
- Insight: the market is a "spoiler" tool, and everyone else treats it as a problem. We should offer a "My stream delay" slider; we found no adjustable one for NFL.

## 5. What makes products look premium vs generic (synthesis)

1. Named scores and tiers instead of raw numbers (Influence Score, Copyability Score, Shark/Dolphin) ([PolyTrends](https://alternativeto.net/software/polytrends--polymarket-whale-tracker/about), [GodEye](https://pm.wiki/uk/projects/godeye-fun)).
2. Fee and spread shown beside every divergence ([Oddpool](https://www.oddpool.com)).
3. Calibration over profit as the credibility measure ([FlukeWatch](https://hunted.space/product/flukewatch)).
4. Plain-English FAQ blocks and rulebook panels on each page ([Prediction Hunt](https://prediction.com/odds/nfl/green-bay-packers-vs-denver-broncos-2026-08-21/34195)).
5. Shareable output (one-tap slip links, share buttons) ([Pikkit](https://apps.apple.com/app/id1586567110)).
6. Privacy by default (units not dollars) ([Pikkit](https://apps.apple.com/app/id1586567110)).
7. Free-delayed vs paid-real-time ladders create a visible "live" premium ([pm.wiki](https://pm.wiki/uk/projects/polymaster)).

## 6. Ranked list: 10 ideas buildable in under 45 minutes (static vanilla JS)

Ranked by (judge impact) x (ease). Each uses data we already have.

1. **"My stream delay" slider + "you are X s ahead" counter.** User picks their stream lag (19-62 s range we measured); the alert feed replays each spoiler at the matching time, or shows a countdown to "TV shows this in 23 s." Source gap: nobody syncs to stream delay ([Cord Cutters News](https://cordcuttersnews.com/3-pro-tips-youtube-tv-subscribers-need-to-know-to-make-watching-sports-even-better/)); inspired by YouTube TV Broadcast Delay. ~30 min.
2. **Calibration chart (reliability diagram) with a one-line verdict.** Plot predicted vs actual play-type hit rate on the 1,596 real fires; label "when we say 80%, it happens X%." From FlukeWatch's calibration-first ranking ([FlukeWatch](https://hunted.space/product/flukewatch)). ~40 min.
3. **Fee and spread chip on every Dutch Book row** ("16 arbs before fees, 0 after," with a fee-bar). From Oddpool's fee-and-spread context ([Oddpool](https://www.oddpool.com)). ~25 min.
4. **Predator Scale score card per user/alert source:** a named numeric score (e.g., "Lion 87") with a tooltip on how it is computed, like PolyTrends' Influence Score ([PolyTrends](https://alternativeto.net/software/polytrends--polymarket-whale-tracker/about)) and Apify's Whale/Shark tiers ([Apify](https://apify.com/jy-labs/polymarket-whale-tracker?fpr=data)). ~30 min.
5. **Alert threshold controls (play types, min jump size) saved in localStorage.** Pikkit Market Alerts and OddsJam filters by profit and sport ([Pikkit](https://apps.apple.com/app/id1586567110), [IdeaUsher](https://ideausher.com/blog/betting-arbitrage-platform-development/)). ~30 min.
6. **Share card button:** render a spoiler ("TD, SF @ SEA, 41 s before ESPN") to a canvas PNG and use the Web Share API/copy-link. From Pikkit QuickPickBot and Prediction Hunt share row ([Pikkit](https://apps.apple.com/app/id1586567110), [Prediction Hunt](https://prediction.com/odds/nfl/green-bay-packers-vs-denver-broncos-2026-08-21/34195)). ~40 min.
7. **Per-alert "what moved" explainer:** each spoiler shows price before/after, jump size, inferred play, confidence, and a "swing" label (leverage-style: small/medium/huge). Answers the critique that a bare percentage tells no story ([Defector](https://defector.com/espns-win-probability-graphic-wants-to-give-you-gambling-brain), [FanGraphs](https://library.fangraphs.com/misc/li)). ~35 min.
8. **Plain-English FAQ + "how to read this" accordion per tab** (what a price is, why paper only, what an arbitrage is). From Prediction Hunt's FAQ and rulebook panels ([Prediction Hunt](https://prediction.com/odds/nfl/green-bay-packers-vs-denver-broncos-2026-08-21/34195)). ~20 min.
9. **Free-vs-instant "lead time" ladder:** a toggle showing alerts "delayed 60 s (everyone else)" vs "live (us)" with our measured 38.6/50.4/64.8 s lead over ESPN's feed. Mirrors free delayed / paid real-time ladders ([pm.wiki](https://pm.wiki/uk/projects/polymaster)). ~25 min.
10. **Unit-based, privacy-first leaderboard with invite link** ("units, not dollars," paper trades only), plus follow-a-friend via URL hash. From Pikkit's units-by-default and live leaderboards ([Pikkit](https://apps.apple.com/app/id1586567110)). Fits the paper-trading and PG rules. ~40 min.

Honorable mention: a "Super-sharp feed" of Someone Knew events with the safe wording "market moved before the first article" (note: Kalshi and Polymarket both tightened insider-trading controls in 2026, so "someone knew" framing is politically live; keep wording neutral; avoid Betmoar-style "Insider Funding" labels) ([QuickNode](https://www.quicknode.com/builders-guide/tools/betmoar-by-betmoar-pte-ltd)).

## Gaps and open questions

- Polymarket Analytics' own site returned HTTP 429 and search found no official product by that name; the whale-tracker evidence is third-party.
- Not verified: Juice Reel features, inpredictable, Gamecast/Bet Center NFL details, Kalshi in-app live charts and notifications, Verso pricing.
- Round 2 still unverified: Betmoar's 50,000 users, PolyTrends Influence Score method, GodEye Copyability Score, Verso, Polymaster open-source status (one directory page calls it both open and closed source; the "Rust CLI, $5,000 default" detail comes from that directory only), the exact per-service latency table in the Stats Perform report.
- Several pricing figures (OddsJam, Action Network tier names, Oddpool profile claims) conflict between sources.

## Sources

- [Oddpool](https://www.oddpool.com)
- [Oddpool NFL weekly](https://www.oddpool.com/nfl-weekly)
- [Extruct: Oddpool](https://www.extruct.ai/hub/oddpool-com/)
- [Dealroom: Oddpool](https://app.dealroom.co/companies/oddpool)
- [FlukeWatch listing](https://hunted.space/product/flukewatch)
- [PolyTrends (AlternativeTo)](https://alternativeto.net/software/polytrends--polymarket-whale-tracker/about)
- [PolyTrack (pm.wiki)](https://pm.wiki/uk/projects/polytrack)
- [GodEye (pm.wiki)](https://pm.wiki/uk/projects/godeye-fun)
- [Polymarket Whale Tracker (Apify)](https://apify.com/jy-labs/polymarket-whale-tracker?fpr=data)
- [PolyMaster (pm.wiki)](https://pm.wiki/uk/projects/polymaster)
- [alerts.chat (pm.wiki)](https://pm.wiki/uk/projects/alerts-chat)
- [Betmoar (QuickNode directory)](https://www.quicknode.com/builders-guide/tools/betmoar-by-betmoar-pte-ltd)
- [Betmoar comparison (pm.wiki)](https://pm.wiki/hi/compare/betmoar-vs-predictfi-one)
- [Verso comparison (pm.wiki)](https://pm.wiki/fr/compare/tryodds-fun-vs-verso)
- [Prediction Hunt game page](https://prediction.com/odds/nfl/green-bay-packers-vs-denver-broncos-2026-08-21/34195)
- [Sports Illustrated: Kalshi NFL review](https://www.si.com/prediction-markets/reviews/kalshi-nfl)
- [SailGP: NFL prediction apps Week 1](https://sailgp.com/prediction-markets/trending/best-prediction-market-apps-for-nfl-week-1-weekend-09-10-2026)
- [NewscastStudio: ESPN win probability](https://www.newscaststudio.com/2024/03/14/espn-brings-win-probability-to-mlb-score-bug/)
- [Defector: ESPN win probability](https://defector.com/espns-win-probability-graphic-wants-to-give-you-gambling-brain)
- [arXiv: iWinRNFL](https://arxiv.org/abs/1704.00197v3)
- [MetricGate: win probability](https://metricgate.com/docs/in-game-win-probability-football/)
- [FanGraphs: Leverage Index](https://library.fangraphs.com/misc/li)
- [Football Perspective: leverage](https://www.footballperspective.com/super-bowl-leverage-and-the-best-postseason-passers-since-1966/)
- [nfl4th docs](https://cloud.r-project.org/web/packages/nfl4th/refman/nfl4th.html)
- [Action Network app article](https://www.actionnetwork.com/general/action-network-mobile-app-must-have-sports-fans)
- [Action Network FAQ](https://www.actionnetwork.com/general/faq)
- [RotoGrinders: best odds apps](https://rotogrinders.com/sports-betting/guides/best-odds-apps)
- [Pikkit on the App Store](https://apps.apple.com/app/id1586567110)
- [Pikkit/Juice Reel summary (parse.gl)](https://parse.gl/brands/pikkit-com)
- [RotoWire: OddsJam review](https://www.rotowire.com/article/arbitrage-betting-finder-7-day-free-trial-with-oddsjam-98274)
- [IdeaUsher: OddsJam-style platform](https://ideausher.com/blog/betting-arbitrage-platform-development/)
- [Cord Cutters News: YouTube TV broadcast delay](https://cordcuttersnews.com/3-pro-tips-youtube-tv-subscribers-need-to-know-to-make-watching-sports-even-better/)
- [Loyalty360: Axwave/FanDuel/NBA](https://loyalty360.org/Content-Gallery/Daily-News/Axwave-Increases-CX-with-Fanduel-and-NBA-Partnersh)
- [The Verge via Scour: MLB notification delay](https://scour.ing/p/https://www.theverge.com/tech/800279/mlb-app-baseball-notifications-delay)

## Round 2 additions (new sources)

- Stats Perform 2026 Super Bowl latency report: streams lagged up to 62 s behind the field. Supports our "19-62 s" range, but the article body also says "Super Bowl LIX" (the Feb 2025 game) next to a 2026 date, so cite as "Stats Perform's Super Bowl latency study" and avoid naming the year on stage ([SVG](https://www.sportsvideo.org/2026/02/11/stats-perform-2026-super-bowl-latency-report/), [Stats Perform](https://www.statsperform.com/insights/super-bowl-live-streaming-experience/)).
- Six Colors / The Verge on MLB's 30 s delayed-notification toggle (see section 4).
- Bot for Kalshi competitor (see section 3).
- Action PRO real-time vs 30-minute delay ladder (see section 3).
- Kalshi integrity changes: June 2026 per-market risk scores, IC360 athlete/referee screening lists, 100+ potential insider cases blocked per its committee report; Polymarket hired Chainalysis (April 2026); House Oversight opened a probe (May 2026). No consumer-facing "insider alert" product found, which supports Someone Knew as a gap, but handle with care ([The Block](https://www.theblock.co/post/394807/kalshi-polymarket-insider-trading-curbs), [Gigazine](https://gigazine.net/gsc_news/en/20260612-kalshi-integrity-updates/), [Oversight Committee](https://oversight.house.gov/release/comer-launches-investigation-into-insider-trading-on-prediction-market-platforms/)).
- Kalshi help center notification settings ([Kalshi help](https://help.kalshi.com/en/articles/17297679-manage-your-kalshi-email-notifications)).
- Oddpool changelog ([Oddpool changelog](https://www.oddpool.com/changelog)); QuickNode Oddpool listing ([QuickNode](https://www.quicknode.com/builders-guide/tools/oddpool-by-oddpool-inc)).
- Pikkit price tracker ([App Pricing Lab](https://apppricinglab.com/iap/apple/1586567110)); OddsJam iOS listing ([App Store](https://apps.apple.com/app/id6448072108)).
- Awful Announcing on ESPN MLB win probability ([Awful Announcing](https://awfulannouncing.com/gambling/espn-mlb-win-probability-sports-betting.html)).

## Verification log (round 2, Oct 11 2026)

| # | Claim | Verdict | Source |
|---|-------|---------|--------|
| 1 | Oddpool 700K+ markets | Confirmed | oddpool.com |
| 2 | Oddpool Free/Pro $30/Premium $100 | Confirmed on own page; Pro $200/yr and Institutional tier added | oddpool.com, QuickNode, Dealroom |
| 3 | Oddpool arbitrage, whale, paper trading | Confirmed as named pages; depth unverified; scanner now has 3 venues (Opinion added) | oddpool.com, changelog |
| 4 | Oddpool whale alerts over $500 | (unverified), third-party only | Extruct/Dealroom |
| 5 | FlukeWatch calibration ranking, $10k+ trades, paid Telegram | Confirmed as the vendor's own claim; no methodology or validation published | hunted.space listing, search |
| 6 | Pikkit 4.9 stars, ~22K ratings | Corrected to ~20.1K (third party); stars confirmed | App Pricing Lab |
| 7 | Pikkit $29.99/mo | Confirmed (third-party tracker, May 2026; $199.99/yr also confirmed) | App Pricing Lab |
| 8 | No NFL spoiler-delay tool | Mostly confirmed; corrected: MLB app has a fixed 30 s delayed-notification toggle; YouTube TV Broadcast Delay 10-30 s smart TVs only confirmed | Six Colors, Cord Cutters |
| 9 | Streams 19-62 s behind | 62 s max confirmed (Stats Perform); report has a LIX/2026 inconsistency; 19 s low end from our own data | SVG |
| 10 | Prediction Hunt page contents | Confirmed in substance; domain is predictionhunt.com; spread varies 1.0-2.5%; includes Polymarket US | predictionhunt.com pages |
| 11 | Action Network push types | Confirmed; PRO real-time vs 30 min delay added | actionnetwork.com |
| 12 | Defector: bare win probability tells no story | Wrong as stated; Defector said redundant with the score | Defector, Awful Announcing |
| 13 | OddsJam $99-$199+/mo | Corrected: $199.99-$399.99 on iOS, $299 per Preqin | App Store, Preqin, IdeaUsher |
| 14 | Kalshi app has no confirmed live alerts | Confirmed as unproven; help center shows price-movement notifications, no live-game jump alert | Kalshi help, reviews |
| 15 | No one else warns before TV stream | Consistent with new search; closest is Bot for Kalshi (email, thresholds) | botforkalshi.com |

## Round 3 gap fill (Oct 11 2026)
- **Stream latency table:** It is Super Bowl LX (Feb 2026), not LIX; the SVG article's year is a typo. Over-the-air about 19 s, cable about 38 s, Peacock 48 s, YouTube TV 53 s (spread 126 s), Hulu + Live TV 53 s (spread 3 s), DirecTV Stream 60 s, NFL+ 62 s; 71 data points, 8 platforms ([SVG](https://www.sportsvideo.org/2026/02/11/stats-perform-2026-super-bowl-latency-report/), [Stats Perform PDF](https://www.statsperform.com/wp-content/uploads/2026/02/2026-Super-Bowl-%E2%80%93-Latency-Study.pdf), [Awful Announcing](https://awfulannouncing.com/tv/antenna-cable-win-super-bowl-latency-battle-streamers-lag-behind.html)). Note: outlets disagree on whether "broadcast" is 19 s (antenna) or cable 38 s; say "antenna about 19 s".
- **Kalshi dedicated live-game push alert:** Not found. Kalshi's help center lists Notification categories (General, Predictions, Perpetuals, Sports, Social, Promotional) with Push and In-app per channel, but the Sports item is only "Major events" ([Kalshi help](https://help.kalshi.com/en/articles/17297679-manage-your-kalshi-email-notifications)); default pushes are price alerts and resolutions ([Phandroid](https://phandroid.com/2026/08/19/using-kalshi-on-android-what-new-users-should-know/amp/)). Say "no live-game play alerts found" (absence, not proof).

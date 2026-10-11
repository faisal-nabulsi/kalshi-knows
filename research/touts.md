# Round 1 research: pick sellers, Twitter/X cappers and pick websites

Written Oct 11, 2026 for the Kalshi Knows team. Plain language; jargon is defined where it first appears. Every factual claim links to the page it came from. Where a number is the seller's own claim, it is labeled "claimed". Where I could not find a number, I say so instead of guessing.

## Executive summary

1. **The pick-selling world sells confidence, not audited results.** Almost every record we found is self-reported. Doc's Sports, for example, shows per-handicapper records in "units" (a unit is one standard bet size) but its own page does not define units or name an independent verifier ([Doc's Sports](https://www.docsports.com/expert-picks/college-football/)).
2. **The math is brutal.** At standard -110 odds (risk $110 to win $100) a bettor must win 52.38% of bets just to break even, because the sportsbook keeps a cut called the vig (short for vigorish, the built-in fee). The 52.38% figure comes from 110/210; one handicapper study states it directly ([John Murray](https://johnfmurray.com/?p=10059)).
3. **Independent evidence says most tipsters lose.** (a) A 2026 study of 165 football prediction services found only 38 (23.0%) profitable ([Tips.GG via Coincub](https://coincub.com/?p=14530)). (b) A 2026 academic paper on 5,467 verified tips from three social-media tipsters found collective losses of 25.24% ([arXiv 2604.08251](https://arxiv.org/abs/2604.08251)). (c) A panel of 37 NFL handicappers since 2003 combined to 52.14% against the spread, just under breakeven ([John Murray](https://johnfmurray.com/?p=10059), self-published by a pick seller, so treat as indicative).
4. **There is a counterpoint.** A 2020 study of 1.5 million tips on Blogabet found tipsters collectively won 3.29% more often than bookmaker odds implied, with average yield of 3.97% ([Grüttner, Univ. of St. Gallen](https://www.alexandria.unisg.ch/259455)). That is a small crowd effect, not proof any single seller is worth paying.
5. **"Verified" is a weak word.** Action Network's verified bets lock the bet at the consensus line and block edits ([Action Network](https://www.actionnetwork.com/press/new-in-the-action-network-app-verified-bets-leaderboard-year-in-review-props)); Betstamp and Juice Reel link or lock tracked bets. None of this proves a seller is profitable, and a capper can still choose what to log. We found no independent audit of Betstamp seller records.
6. **For Kalshi Knows the opening is clear.** Touts show win-loss records and star ratings without reporting a timestamp-proven edge. We can show something none of them show: a measured latency (alerts beat ESPN's feed by 38.6/50.4/64.8 s) and a published, held-out accuracy figure. Section 6 lists concrete design implications.

## 1. The market in four layers

| Layer | Examples | Typical price | What the buyer gets |
|---|---|---|---|
| Premium touts (phone-room style) | Doc's Sports; Mazi VS | $99 per weekend to $950 per season per handicapper (Doc's); $200 to $5,000 (Mazi) | Individual handicapper picks with unit sizes |
| Pick sites and media | Pickswise, Covers, VSiN, WagerTalk, SportsLine | Mostly free picks, monetized by sportsbook referral links ("Bet Now" buttons) | Staff expert picks, star ratings |
| Data/model subscriptions | Action Network PRO, BetQL, Sports Insights (Bet Labs) | $9.99 weekly to $119.99 per year (Action) | Model projections, sharp-money signals, odds screens |
| Social and Discord/Telegram cappers | Gumroad-style Discord VIPs; X accounts | $40 to $50 per month typical in listings | Daily plays in a chat |

## 2. Specific sellers, with prices and displays

### Doc's Sports (premium tout, claims a guarantee)
- Pricing for the 2026 season: $99 per weekend, $325 per 4 weekends, $950 per full season, each per handicapper; $30 for a single "Top Play"; preseason package $79 ([Doc's Sports](https://www.docsports.com/expert-picks/college-football/)). The page contradicts itself: its history section says $749 for a full season while the package lists $950.
- Claimed guarantee: "We guarantee you a profit with any of our handicapper packages or we will extend your service" ([Doc's Sports](https://www.docsports.com/expert-picks/college-football/)). Note this is an extension of service, not a refund.
- Pick-card style: win-loss records plus dollar-style "units" and a rating system where plays are tagged 5.0+, 6-Unit, 7-Unit, 8-Unit. Examples claimed: Scott Spreitzer 129-95 (58%), +12,050; Strike Point Sports 28-14 (67%), +6,200; Arun Shiva 2021 NFL 64-46 (58%), +5,305 ([Doc's Sports](https://www.docsports.com/expert-picks/college-football/)).
- Display pattern worth noting: the headline numbers are slices ("22-14 on 6- and 7-Unit plays", "last 53 days") rather than full-season records. This is the cherry-picked date range warning that integrity guides raise ([Birches Health on touts](https://bircheshealth.com/resources/sports-betting-touts)).

### Mazi VS (Instagram-era super-tout, now a cautionary tale)
- The New York Times profiled him in July 2025: about 2.5 million followers, claimed win rates up to 70%, claimed 28,000 paying subscribers, prices of $200 daily up to $1,500 for an "Exclusive Play of the Day" and $5,000 for a week, as summarized in [this secondary write-up](https://bircheshealth.com/resources/famous-gambling-tout-mazi-vs).
- He was charged with 14 felony counts of forgery and identity fraud, pleaded not guilty at arraignment, was denied bail because he was on probation from an earlier gun charge, and stopped posting; trial was set for August 25, 2025 ([Gambling911](https://gambling911.com/gambling/mazi-smith-sports-betting-king-trial-072025.html)). **Round 2 update:** a Sept 2, 2025 Gambling911 article says he pleaded guilty to fraud charges and was sentenced to prison, but its headline says 12-24 months and its body says 12-48 months, and I found no court record or mainstream report (so the plea and sentence are unverified) ([Gambling911](https://www.gambling911.com/gambling/mazi-smith-sports-betting-king-sentenced-090225.html)). The 28,000-subscriber figure is his own claim, relayed by the Times. Court records reportedly identify him as Darnell Smith (an allegation); he is not the Michigan football player of the same name.
- Lesson: the product being sold was lifestyle. The Times noted he was reluctant to talk about picks.

### Vegas Dave, Stu Feiner and other named X accounts
- The Handle names Vegas Dave and Stu Feiner as touts who obscure results; it says an account, @vegas_scum, is dedicated to exposing Vegas Dave. It gives no specific record figures ([The Handle](https://thehandle.substack.com/p/tout)).
- Independent coverage of Vegas Dave describes self-reported big wins (for example $220,000 on a UFC upset) but I found no audited record ([Midweek](https://www.midweek.com/?p=96228)).
- Older precedent: Adam Meyer, a US sports-betting tout, was arrested in 2014 over an alleged $25M scam (headline only; article body paywalled) ([Gaming Intelligence](https://www.gamingintelligence.com/news-and-archive/29463-us-sports-betting-tout-adam-meyer-arrested-over-25m-scam-2)).

### Jim Hurley and the old 1990s-2000s tout model
- Juice Reel's newsletter says Hurley's membership cost $99 and that his premium "Back to School Parlay" went 0-2, and it cites a "70% win rate" claim from touts of that era, unverified ([Juice Reel](https://juicereel.beehiiv.com/p/can-betting-advice-be-trusted)). The author sells his own picks, so this is a promoter's critique.

### Discord and Telegram services
- Listings found: PickzDaily at $40 per month with a 1-week free trial ([Gumroad](https://pickzdaily.gumroad.com/l/cjysqz)); Almighty Sportsbook at $49.99 per month ([Gumroad](https://almightyfleee1.gumroad.com/l/discord)); a Telegram "Sports VIP" at $39 per month ([Gumroad](https://coingrams.gumroad.com/l/Sports)).
- Claims are unaudited: one directory lists a community claiming a 90% win rate and another over $500,000 in member profits in 2023 ([Hive Index](https://thehiveindex.com/communities/goat-sports-bets/)).
- A mainstream media version also exists: SportsLine launched a Discord community with expert chats ([CBS Sports](https://www.cbssports.com/promotions/sports-betting-discord-sportsline-launches-new-sportsbetting-community-with-expert-chats/)).

### Pickswise (free picks, self-reported units)
- Pick cards show handicapper name, pick type (point spread, game total, best bet), the selection with odds (for example -131 or +102), a 2-to-5 star confidence rating, a "best odds" column and a "Bet Now" link per sportsbook. The cards I read did not show unit size or stake ([Pickswise NFL predictions](https://www.pickswise.com/nfl/predictions/)).
- Claimed record: "+82.1 units" for the 2025-26 season. My searches found conflicting supporting counts on different Pickswise pages (one says 158 ATS and 151 totals wins; another says "30 winning selections"), and units are not defined, so we cannot reproduce it ([Pickswise picks](https://www.pickswise.com/nfl/picks/), [predictions](https://www.pickswise.com/nfl/predictions/)). Pickswise also reports +23.7 units on parlays and +7.7 on a player-prop snapshot (same sources).
- Pickswise runs an AI "computer picks" page ([Pickswise computer picks](https://www.pickswise.com/nfl/computer-picks/)); I did not extract its methodology.

### SportsLine, Bleacher Report and other media panels
- SportsLine shows individual expert streaks (for example "18-8 over last 26 NFL ATS picks") that are self-reported and short-window ([CBS Sports Week 9 picks](https://www.cbssports.com/nfl/news/nfl-picks-odds-lines-best-bets-week-9-2025-expert-predictions-spread-parlays-player-props)). ATS means "against the spread" (beating the point margin the sportsbook sets).
- Bleacher Report publishes a panel standings table; mid-2025 the leader was 41-37 ([Bleacher Report](https://bleacherreport.com/articles/25258361-2025-nfl-week-6-expert-picks)). I found no third-party audit of any of these.

### Covers, VSiN, WagerTalk, OddsShark
- Covers: a 2019 announcement described its roster as including forum "legends," a data model and specialists ([SBC Americas](https://sbcamericas.com/2019/08/28/covers-com-strengthens-and-diversifies-with-four-new-brands-on-board/)). A Korean-language guide says Covers shows the share of users backing each side and a TOP100 user-picks view ([Outlook India](https://www.outlookindia.com/xhub/e-gaming/covers-pick-rankings-and-analysis-data)). I could not retrieve current unit records or prices.
- VSiN was acquired by Musburger Media in July 2024 ([CB Insights](https://www.cbinsights.com/compare/pickswise-vs-vegas-stats-information-network)). WagerTalk offers free and paid picks from handicappers ([Parse](https://parse.gl/brands/wagertalk-com)). I could not find reliable current paid-tier prices for VSiN, WagerTalk, Covers or OddsShark. Open gap.

### Action Network, BetQL, Sports Insights (data and model products)
- Action Network PRO: App Store price snapshot (April 24, 2026) lists $9.99 weekly (round 2: the verified-bets press page itself lists no prices; and RotoGrinders gives $19.99 weekly / $29.99 monthly / $119.88 annual, so weekly and monthly prices are disputed and the only firm number is about $119.99 per year) , $19.99 or $24.99 monthly, $59.99 for three months and $119.99 annually, plus an EDGE annual at $99.99 ([App Pricing Lab](https://apppricinglab.com/iap/apple/1083677479)). A 2024 listing had monthly at $29.99 ([Adapty](https://adapty.io/paywall-library/action-network-sports-betting/)). Marketing for PRO lists instant expert pick alerts, sharp-money tracking, game projections and prop edges ([Action Network](https://www.actionnetwork.com/nfl/action-pro-big-game-special-2025)).
- Verified-bets leaderboard (Action Network, updated Feb 2022): bet must be at the consensus line, cannot be edited, stake 0.5 to 3 units, no live bets, futures or very large favorites, and no betting the same side more than twice; the board sorts by 7 days, 30 days, all-time or sport ([Action Network](https://www.actionnetwork.com/press/new-in-the-action-network-app-verified-bets-leaderboard-year-in-review-props)). Rules may have changed since.
- BetQL: a proprietary 1-to-5 star system where five stars is the strongest model-backed play; one source says it simulates games 10,000 times ([BetQL App Store](https://apps.apple.com/us/app/betql-sports-betting/id1334825645), [Parse](https://www.parse.gl/brands/betql-co)). Consumer pricing not confirmed; affiliate payouts ($20 to $100 per subscriber) suggest a paid monthly and annual tier ([FlexOffers](https://www.flexoffers.com/affiliate-programs/betql-affiliate-program/)).
- Sports Insights is part of Action Network (acquired as one of three companies by The Chernin Group) and sells Bet Labs, a backtesting tool ([LSR](https://www.legalsportsreport.com/19628/betql-sports-betting/), [Parse](https://www.parse.gl/brands/sportsinsights-com-3)). Pricing not confirmed.

## 3. Verification tools: what "verified" actually means

| Tool | What it does | What it does not prove |
|---|---|---|
| [Juice Reel](https://juicereel.beehiiv.com/p/can-betting-advice-be-trusted) | Leaderboard from bets at linked sportsbooks; filter by sport and subscription price | That the seller wins long-run; the cited claims are small samples (the newsletter author reports +13.1 units at 24% ROI, implying roughly 55 units staked) |
| [Betstamp](https://www.betstamp.com/education/what-is-betstamp-guide-to-smarter-betting) | Tracks bets with closing line value (CLV); profiles public or private; reviewers say click-tracked bets cannot be edited | Independent audit; public profiles may be a favorable subset ([XCLSV](https://xclsvmedia.com/pikkit-vs-slipsync-vs-betstamp-bet-tracker-2026/)) |
| [Pikkit](https://igamingfuture.com/pikkit-unveils-2024-instant-replay-with-record-breaking-betting-insights/) | Syncs sportsbook accounts; tracked 323M bets ($10.6B) in 2024 | No published share of users who are profitable that I could find |
| [Action Network verified bets](https://www.actionnetwork.com/press/new-in-the-action-network-app-verified-bets-leaderboard-year-in-review-props) | Locked, capped-stake bets on a leaderboard | Selection (not every bet must be verified) |

The Handle's summary: no tout's record is independently verified, and touts may fudge record, CLV% or ROI% ([The Handle](https://thehandle.substack.com/p/tout)).

CLV (closing line value) means beating the final pre-game price. It is the usual skill proxy, but it is not sufficient. In a 3,670-game NBA sample (2022/23 to 2024/25 seasons), only the top CLV decile made meaningful money (11.4% average return); the ninth decile averaged 5% CLV yet earned just 0.2%, because the sportsbook margin (4.5% on NBA moneylines) must be overcome first ([Karl Whelan](https://www.karlwhelan.com/?p=2595)).

## 4. What fraction of touts beat the market?

| Evidence | Sample | Result |
|---|---|---|
| [Tips.GG study, Jan-Aug 2026](https://coincub.com/?p=14530) (Tips.GG sells tipster rankings, so it has a commercial interest; Coincub and Possible11 are reposts, not independent; only 4 of 73 services with 1,000+ predictions were profitable) | 165 football prediction services; 500,000+ predictions, flat $10 stakes, average bookmaker margin 8.19% not removed | 38 (23.0%) profitable; top ROI +17.40% on only 95 predictions; highest win rate (76.0% over 870) had -1.94% ROI |
| [Makinde et al., arXiv, Apr 2026](https://arxiv.org/abs/2604.08251) | 5,467 slips from 3 X/Telegram tipsters in Nigeria; about $4.8M tracked; verified vs Stake.com | Influencers lost 25.24% collectively; flat-stake followers lost 38.27% |
| [Murray, 2024](https://johnfmurray.com/?p=10059) | 37 NFL panel handicappers, picks since 2003 | 15,228-13,976 with 873 pushes = 52.14% ATS vs 52.38% breakeven; top 10 52.24%. Author sells picks |
| [Grüttner 2020](https://www.alexandria.unisg.ch/259455) | 1,534,041 tips, 3,484 Blogabet tipsters | Won 3.29% more than odds implied; average yield 3.97% (aggregate, not per seller) |
| [Levitt 2004, Economic Journal](https://www.nber.org/papers/w9422) | one NFL season of bet prices and quantities (NBER page does not name the season; "2001-02" in round 1 is unverified) | Bookmakers set prices to exploit bettor biases; little evidence bettors beat the book |
| [Journal of Forecasting study via IAORIFORS](https://iaorifors.com/paper/64997) | Bundesliga, 2009 | Prediction markets and betting odds match each other and strongly beat tipsters |

Round 2: the NerdWallet 40% figure is real but is a December 2024 survey of 2,000+ US adults, self-reported, one year ([NerdWallet](https://www.nerdwallet.com/article/investing/2025-sports-betting-and-gambling-survey)). The 3-5% long-run figure is widely repeated (BofA Institute coverage by [Casino.org](https://casino.org/news/bofa-bettors-taking-out-75-cents-for-each-1-they-put-in)) but has no primary study behind it (unverified). A better-sourced number: a 2025 Rady School study of 700,000+ online gamblers found about 96% lost money over five years (all online gambling, not sports only) ([Gambling Harm](https://gamblingharm.org/casino/most-online-gamblers-lose-study)).

Unverified folklore, do not put on a slide: search results repeated that only 3% to 5% of bettors are profitable long-run with no named study, and that a NerdWallet survey found 40% of bettors report net gains in the past 12 months (self-reported, one year). I did not open the underlying pages, so I could not confirm either figure; the [Casino.org bettor-income article](https://www.casino.org/news/sports-bettors-eye-income-but-some-take-on-debt-to-fund-habit/) surfaced alongside them but I did not verify it contains them.

Answer to "what fraction beat closing line or break even long-run": the best direct figure is 23.0% profitable over eight months in a football services sample, with the caveat that eight months can flatter lucky small-sample sellers. I did not find a published share-beating-closing-line number for touts specifically (open gap).

## 5. Regulatory and legal signals
- I found no FTC action specifically against a sports-betting tout. The closest analogue is the FTC's $2.4M settlement with the stock-tout service Raging Bull over earnings claims made without tracking customer results ([Bloomberg Law](https://news.bloomberglaw.com/antitrust/investment-site-to-pay-ftc-2-4-million-for-earnings-deception)).
- Round 2 note: I found no 2025-26 FTC, state AG or CFTC action against a sports-picks seller; the BBB has warned since 2022 about "scamdicappers" who promise guaranteed wins and never refund ([Bitdefender summary of BBB](https://bitdefender.com/blog/hotforsecurity/bbb-warns-of-phony-sports-handicappers-services-promising-guaranteed-winnings)). Raging Bull detail: FTC sued Dec 2020 (Operation Income Illusion), settled March 2022 for $2.4M (some reports $2.425M) ([FTC consumer alert](https://www.consumer.ftc.gov/consumer-alerts/2022/03/investment-trading-operation-will-pay-millions-empty-promises)).
- Hungary's competition authority opened a probe into advertising of sports-betting tips in 2021 ([GVH](https://gvh.hu/en/press_room/press_releases/press-releases-2021/the-gvh-is-investigating-the-advertisements-of-sports-betting-tips)).
- The Handle's informal survey: 65 of 100 bettors said they would consider paying $100 per year for picks; it assumed a $1B total market from 10M bettors at 50% willingness ([The Handle](https://thehandle.substack.com/p/tout)). Not randomized; treat as a thought experiment. It also shows the seller's own break-even: with a fee added, a "55 to win 50" bet effectively becomes 59 to win 50, so the seller must win about 54% for the buyer to break even.

## 6. Design implications for Kalshi Knows
1. **Lead with timestamps, not win rates.** No competitor reports a timestamped lead over a public feed. Our measured claims (Kalshi price moves a median 7.0 s after ESPN play time; alerts beat ESPN's feed by 38.6/50.4/64.8 s) are exactly what the verification tools cannot show.
2. **Show the full ledger, losses included.** Cherry-picked slices ("last 53 days", "7-Unit plays only") are the tell. Show every fire, hit-rate by play type, and a calibration chart.
3. **Define every unit.** Pickswise and Doc's Sports use units without definitions. Ours should say what one unit is, or avoid units because we are not selling bets.
4. **Report the breakeven benchmark.** Showing "52.38% needed at -110" teaches judges why a 55% claim is hard, and positions our play-type accuracy against a stated bar. Our model predicts play type, not a bet outcome, so say that clearly rather than imply a betting ROI.
5. **Borrow the card vocabulary, not the claims.** Confidence stars (Pickswise, BetQL), streaks, and "best odds" columns are familiar to sports fans. Map confidence to calibrated probability instead of a marketing star.
6. **Stay PG and paper-only.** Touts end in fraud cases (Mazi) and guarantees that are only service extensions (Doc's). We sell no picks and make no guarantee.

## Open gaps (not found in Round 1)
- Current paid-tier prices for Covers, VSiN, WagerTalk, OddsShark, BetQL and Sports Insights.
- Any published share of touts beating the closing line (as opposed to being profitable).
- Betstamp or Pikkit aggregate seller-profitability statistics, and any independent audit of Betstamp or Juice Reel records.
- Methodology of Pickswise "computer picks" and its +82.1-unit definition.
- Nigerian paper per-strategy figures and win rate (text I retrieved did not give them).

## Sources
- [Doc's Sports expert picks](https://www.docsports.com/expert-picks/college-football/)
- [The Handle, "tout"](https://thehandle.substack.com/p/tout)
- [Juice Reel, "Can betting advice be trusted?"](https://juicereel.beehiiv.com/p/can-betting-advice-be-trusted)
- [arXiv 2604.08251, Nigerian influencer study](https://arxiv.org/abs/2604.08251)
- [Tips.GG study via Coincub](https://coincub.com/?p=14530)
- [Action Network verified bets](https://www.actionnetwork.com/press/new-in-the-action-network-app-verified-bets-leaderboard-year-in-review-props)
- [Karl Whelan, The Truth about Closing Line Value](https://www.karlwhelan.com/?p=2595)
- [John Murray handicapper study](https://johnfmurray.com/?p=10059)
- [Grüttner, Wisdom of an Online Tipster Community](https://www.alexandria.unisg.ch/259455)
- [Levitt, NBER w9422](https://www.nber.org/papers/w9422)
- [Bundesliga tipsters vs markets](https://iaorifors.com/paper/64997)
- [Pickswise NFL predictions](https://www.pickswise.com/nfl/predictions/), [picks](https://www.pickswise.com/nfl/picks/), [computer picks](https://www.pickswise.com/nfl/computer-picks/)
- [Action Network pricing (App Pricing Lab)](https://apppricinglab.com/iap/apple/1083677479), [Adapty 2024](https://adapty.io/paywall-library/action-network-sports-betting/), [Action PRO promo](https://www.actionnetwork.com/nfl/action-pro-big-game-special-2025)
- [BetQL App Store](https://apps.apple.com/us/app/betql-sports-betting/id1334825645), [Parse BetQL](https://www.parse.gl/brands/betql-co), [FlexOffers BetQL](https://www.flexoffers.com/affiliate-programs/betql-affiliate-program/)
- [Legal Sports Report on BetQL/RotoQL](https://www.legalsportsreport.com/19628/betql-sports-betting/), [Parse Sports Insights](https://www.parse.gl/brands/sportsinsights-com-3)
- [Betstamp guide](https://www.betstamp.com/education/what-is-betstamp-guide-to-smarter-betting), [XCLSV tracker comparison](https://xclsvmedia.com/pikkit-vs-slipsync-vs-betstamp-bet-tracker-2026/)
- [Pikkit 2024 Instant Replay](https://igamingfuture.com/pikkit-unveils-2024-instant-replay-with-record-breaking-betting-insights/)
- [Mazi VS summary](https://bircheshealth.com/resources/famous-gambling-tout-mazi-vs), [Gambling911](https://gambling911.com/gambling/mazi-smith-sports-betting-king-trial-072025.html)
- [Vegas Dave coverage (Midweek)](https://www.midweek.com/?p=96228), [Adam Meyer arrest](https://www.gamingintelligence.com/news-and-archive/29463-us-sports-betting-tout-adam-meyer-arrested-over-25m-scam-2)
- [Birches Health, touts guide](https://bircheshealth.com/resources/sports-betting-touts)
- Discord/Telegram listings: [PickzDaily](https://pickzdaily.gumroad.com/l/cjysqz), [Almighty](https://almightyfleee1.gumroad.com/l/discord), [Coingrams](https://coingrams.gumroad.com/l/Sports), [Hive Index](https://thehiveindex.com/communities/goat-sports-bets/), [CBS SportsLine Discord](https://www.cbssports.com/promotions/sports-betting-discord-sportsline-launches-new-sportsbetting-community-with-expert-chats/)
- [CBS Sports Week 9 picks](https://www.cbssports.com/nfl/news/nfl-picks-odds-lines-best-bets-week-9-2025-expert-predictions-spread-parlays-player-props), [Bleacher Report Week 6](https://bleacherreport.com/articles/25258361-2025-nfl-week-6-expert-picks)
- [SBC Americas on Covers](https://sbcamericas.com/2019/08/28/covers-com-strengthens-and-diversifies-with-four-new-brands-on-board/), [Outlook India on Covers](https://www.outlookindia.com/xhub/e-gaming/covers-pick-rankings-and-analysis-data), [CB Insights VSiN](https://www.cbinsights.com/compare/pickswise-vs-vegas-stats-information-network), [Parse WagerTalk](https://parse.gl/brands/wagertalk-com)
- [Bloomberg Law, FTC Raging Bull](https://news.bloomberglaw.com/antitrust/investment-site-to-pay-ftc-2-4-million-for-earnings-deception), [GVH Hungary](https://gvh.hu/en/press_room/press_releases/press-releases-2021/the-gvh-is-investigating-the-advertisements-of-sports-betting-tips)
- [Casino.org, bettor income survey](https://www.casino.org/news/sports-bettors-eye-income-but-some-take-on-debt-to-fund-habit/)


## Round 2 additions (new sources)
- Mazi VS outcome: [Gambling911 sentencing report](https://www.gambling911.com/gambling/mazi-smith-sports-betting-king-sentenced-090225.html) (inconsistent 12-24 vs 12-48 months; unverified by court record) and [FlowingData summary of the NYT piece](https://flowingdata.com/2025/07/31/odds-against-a-sports-betting-king/): oddsmakers said sportsbooks would not accept his action if he really won at his claimed rate.
- [FTC consumer alert on Raging Bull](https://www.consumer.ftc.gov/consumer-alerts/2022/03/investment-trading-operation-will-pay-millions-empty-promises): 9,862 PayPal refunds sent; confirms no tracking of customer results.
- [BBB scamdicapper warning via Bitdefender](https://bitdefender.com/blog/hotforsecurity/bbb-warns-of-phony-sports-handicappers-services-promising-guaranteed-winnings): guaranteed-win and refund promises are the standard scam pattern.
- [Tips.GG original study page](https://tips.gg/article/football-prediction-services-profitability/): goal.pl won only 47.8% of picks yet had +2.01% ROI; accuracy does not predict profit because odds matter.
- [NerdWallet 2025 survey](https://www.nerdwallet.com/article/investing/2025-sports-betting-and-gambling-survey), [Rady School study via Gambling Harm](https://gamblingharm.org/casino/most-online-gamblers-lose-study), [Pikkit 2024 Instant Replay (Business Wire)](https://www.businesswire.com/news/home/20241209399992/en/Pikkit-Releases-2024-Instant-Replay) (activity stats only, no profitability share), [RotoGrinders picks-app guide](https://rotogrinders.com/sports-betting/guides/best-picks-apps) (alternate Action PRO prices).
- Sports Insights is now folded into Action Network; no standalone pricing found.

## Verification log (round 2, Oct 11 2026)
| # | Claim | Verdict | Source |
|---|---|---|---|
| 1 | 52.38% breakeven at -110; 37 handicappers 15,228-13,976-873 = 52.14% ATS | Confirmed; "since 2003" holds only for some; author is a sports psychologist who sells picks; host site unnamed | [Murray](https://johnfmurray.com/?p=10059) |
| 2 | 38 of 165 football services (23.0%) profitable Jan-Aug 2026; top win rate 76.0% on 870 at -1.94% ROI | Confirmed by Tips.GG's own study; commercial interest, reposts not independent | [Tips.GG](https://tips.gg/article/football-prediction-services-profitability/) |
| 3 | 5,467 tips, -25.24% collective, -38.27% flat followers | Confirmed (abstract; submitted 9 Apr 2026; period tracked not stated; preprint) | [arXiv](https://arxiv.org/abs/2604.08251) |
| 4 | Blogabet 1.53M tips, +3.29%, 3.97% yield | Confirmed (1,534,041 tips, 3,484 tipsters, 2020); wording is "won 3.29% more tips than implied probability" | [St. Gallen](https://www.alexandria.unisg.ch/259455) |
| 5 | Doc's $99/$325/$950, extension-only guarantee, units undefined | Confirmed; page also says $749 season in history; only defines a 1.0-8.0 unit rating | [Doc's](https://www.docsports.com/expert-picks/college-football/) |
| 6 | Whelan: only top CLV decile profits (11.4%) | Corrected: 9th decile also positive (0.2%); round-1 "three of five" sentence was garbled and was removed | [Whelan](https://www.karlwhelan.com/?p=2595) |
| 7 | Action verified bets rules | Confirmed (Feb 2, 2022 update); page lists NO prices, so the PRO price claim needs other sources | [Action Network](https://www.actionnetwork.com/press/new-in-the-action-network-app-verified-bets-leaderboard-year-in-review-props) |
| 8 | Action PRO $9.99 weekly to $119.99 annual | Disputed: annual ~$119.99 agrees; weekly/monthly conflict between App Pricing Lab and RotoGrinders | [App Pricing Lab](https://apppricinglab.com/iap/apple/1083677479), [RotoGrinders](https://rotogrinders.com/sports-betting/guides/best-picks-apps) |
| 9 | Mazi VS 28,000 subscribers, 14 felony counts | Subscribers = his own claim; counts confirmed as charges; outcome updated (guilty plea reported, sentence inconsistent, unverified) | [Birches](https://bircheshealth.com/resources/famous-gambling-tout-mazi-vs), [Gambling911](https://www.gambling911.com/gambling/mazi-smith-sports-betting-king-sentenced-090225.html) |
| 10 | FTC Raging Bull $2.4M | Confirmed (March 2022, $2.4M-$2.425M) | [FTC](https://www.consumer.ftc.gov/consumer-alerts/2022/03/investment-trading-operation-will-pay-millions-empty-promises) |
| 11 | Levitt: little evidence bettors beat the book | Confirmed; season "2001-02" not supported by the NBER page | [NBER](https://www.nber.org/papers/w9422) |
| 12 | NerdWallet 40% net gains; 3-5% profitable | 40% confirmed (Dec 2024 survey, self-reported); 3-5% has no primary study (unverified) | [NerdWallet](https://www.nerdwallet.com/article/investing/2025-sports-betting-and-gambling-survey) |
| - | Pickswise +82.1 units, Covers/VSiN prices, Hive Index claims, Vegas Dave, Pikkit profitable share | Not rechecked (unverified); prior open gaps stand | n/a |

# Kalshi Knows: lead review (merged from 5 reviewers)

Written 12:15 PT, Sun Oct 11. Reviewers and scores: hackathon judge 7.2, bettor 5.5, casual fan 5.5, sports analyst 6.0, data researcher 6.5 (average 6.1).

**Bottom line.** The core insight is real and new: Kalshi's price is a sensor that knows what just happened on the field before your stream does. The methods are better than most hackathon work. Four things could lose the prize:
1. The engine can hang and go dark with no warning.
2. The headline numbers are louder than the data.
3. The demo depends on a big play happening on cue.
4. There is no clear answer to "who pays?"

All four can be fixed by 2:30.

## What I checked myself at 12:07-12:12 (this overrides the reviewers where they disagree)

- **The engine is up again.** It restarted at 12:07:14 (PID 23991). `/api/health` returns `mode: live`, 8 games, both feeds OK, through the same tunnel URL. The judge's 12:00-12:05 hang was real, though, and its cause is unknown. The watchdog fix below still matters.
- **Zero phones are subscribed to push.** `engine/subscriptions.json` holds `[]` and has not changed since 10:43, and health reports `subscribers: 0`. The demo is "phones buzz", and right now no phone would buzz. This is the most urgent human task.
- **The model was retrained at 12:06.** The new training set has 6,122 detector fires ("fires" = moments where the price jump detector triggered). 2,084 of them are at the live threshold, across 207 games. The reviewers' numbers (3,704 / 1,267 fires) are out of date. STATS.md (1,596 fires, 76.3%, 71.5%) is older still.
- **`mm_features: []`.** The new model does not use the other-market features (anytime-TD scorer, total points). The data researcher's critical item ("trained on features the live engine never sends") and the analyst's NaN-total-points concern **no longer apply**. One mismatch remains: `micro_burst` (trade-burst size) is real in training but a fixed 1.07 live. The analyst measured this as costing about 1.7 points.
- **TabPFN is on by default** (`TABPFN` env defaults to "1"). TabPFN is a second model that gets averaged in only when it answers within 4 s, so which model produced an alert depends on timing.
- **Accuracy and baseline on the same rows** (computed from `train/out/stage2_matrix.npz` and `finetune_metrics.json`). The baseline is "always guess nothing big happened" (OTHER):

| Test | Fires (games) | Model | Always OTHER |
|---|---|---|---|
| Cross-validation, live threshold (the model never sees a test game in training) | 2,084 (207) | 74.5% | 60.4% |
| **Train on 2025, test on 2026, live threshold** | **569 (58)** | **72.4%** | **57.1%** |

  The second row is the honest headline. It tests on later games the model never saw, and the baseline is computed on the same rows.
- **Today's alerts land 28-33 s after ESPN's timestamp for the play** (`market_lag_s`: 32.7 and 27.9 on the confirmed ones). ESPN's public feed showed those plays 71-78 s after the same timestamp.

## Contradictions and which side I take

| Disagreement | My call | Why |
|---|---|---|
| Fan: "restart the tunnel". Judge: "restart only the engine". | **Judge.** | Restarting a quick tunnel gives it a new random URL. That forces a config.json redeploy, and Pages caching takes minutes. |
| Bettor and fan: "move to a named tunnel or an always-on server today". | **After the hackathon.** | A watchdog plus `caffeinate` (already running) covers 4pm. A migration at 2pm adds more risk than it removes. |
| Data researcher: "wire up the KXNFLTD scorer market now". | **After the hackathon.** | The current model has no training data for that feature, so a live-only input cannot help today. |
| Analyst: "retrain with stale-state simulation". Analyst: "pre-register a frozen-model test on today's games". | **Pre-register now; retrain later.** | Changing the model after noon would void today's out-of-sample test and move every headline number at 2:30. A cheap engine-side gate (E2 below) covers the stale-state failure for today. |
| Bettor: "show which sportsbooks haven't moved yet". Judge: "we warn bettors, we don't arm them". | **Judge.** | Using a fast alert to bet a slow book is past-posting or courtsiding (betting on information other bettors don't have yet). Books ban accounts for it, the room is under 21, and Genius Sports holds the NFL data rights. The bettor's need becomes a "this market already moved" warning instead. |
| Fan: "only push at 75%+ confidence". Demo: needs buzzes. | **Always push; name the play only when the model is 75%+ sure and the game state is fresh.** Otherwise the push says "Big swing to Seattle". | This keeps the demo buzzing and removes the wrong "TOUCHDOWN" pushes. |
| Accuracy headline: 73/57, 76/60, 72.6, 89.7? | **72% vs 57%** (row 2 of the table above). | It is forward in time, uses the same rows for both numbers, and the model was not selected on it. |
| "Beats ESPN by 38.6-64.8 s" vs the 15-31 s figures on the site cards. | **Use the stream-based lead in the headline.** Mention the ESPN-feed lead only with its basis named. | These are different comparisons. Mixing them makes both look made up. |

## 1. Do before the 2:30 freeze

Ranked by (impact on winning + product quality) / effort. Core Claude work totals 150 min across 4 parallel streams. Every stream finishes by about 1:55, which leaves 35 min of buffer.

| # | Fix | Owner | Min |
|---|---|---|---|
| H1 | **Subscribe every team phone now and send a test push.** On iPhone: Share, then Add to Home Screen, open from the home-screen icon, then Allow. Confirm `subscribers >= 3` in /api/health. Repeat the test at 3:45. | Faisal, Kevin, Dugar | 5 |
| E1 | **Engine watchdog.** In `_supervise.sh`, every 10 s run `curl -m 5 localhost:8000/api/health`; after 2 failures, kill the PID so the loop restarts the engine (never cloudflared). Wrap `ENGINE.games_list()` in `/api/ws` with `await asyncio.to_thread(...)`. `pip install py-spy` so a hang can be dumped (`py-spy dump --pid`) before it is killed. Log every restart. | Claude-engine | 15 |
| M1 | **Freeze and pre-register.** Write `research/PREREG.md` with: the sha256 of `engine/model/stage2_xgb.json`; threshold 0.08; confidence gate 0.75; 8 s call delay; labeler = `pipeline/nfl_build_plays.py`; match window -20 s to +90 s. No retrains before 4pm. | Claude-model | 5 |
| E2 | **Don't name a play on bad inputs.** If posteam, yardline_100 or down is missing, the ESPN snapshot is more than 60 s old, or top-class confidence is under 0.75, then push "Big swing to {team} in {game}" and do not name the play. Set `TABPFN=0` in `run_live.sh`. Restart the engine once and verify health. | Claude-engine | 15 |
| W1 | **Claims copy pass** (exact wording in section 2): hero, closing line, Receipts section, ESPN wording, the Someone Knew caption and rename, "25 seasons", footer disclaimer. Then redeploy Pages. | Claude-web | 20 |
| M2 | **Same-row numbers on the 12:06 model.** Compute out-of-fold "named-call precision": when the model names a play (not OTHER) at 75%+ confidence, how often it is right, and how many such calls there are. Add 3 comparison rows on the same 2,084 fires: a smart-fan logistic regression, XGBoost without stage 1, and stage 1 + game state with no price shape. Delete the "sports-fan rule" row (it never predicts OTHER, so it is a strawman). Update STATS.md, TRAINING.md, the `infer_model.py` docstring and `results.json` (also fill `games_analyzed`). Reuse `/tmp/kkaudit/audit.py`. | Claude-model | 15 |
| E3 | **Honest live tally.** 90 s after an alert, score it with the *training* labeler: turnover on downs counts as a turnover, blocked kicks follow the training rules, BIG_PLAY means 20+ yards on a run or catch. Mark each alert `correct`, `wrong` or `no_match` instead of leaving it `pending` forever. The site card shows "missed" in grey, and the header shows "Today: N alerts · X right · Y missed". | Claude-engine (+5 Claude-web) | 15 |
| M3 | **Out-of-sample test on today's finished early games** (start about 1:20, once they end). Pull their trade tapes, run `nfl_windows.py --today` plus the detector with the frozen model, and expect 100+ fires. Report accuracy, named-call precision, and always-OTHER on the same rows, with confidence intervals that account for plays in the same game being related. This becomes the "pre-registered, today's games" slide number. | Claude-model | 30 |
| R1 | **Someone Knew primary-source check.** GPT-6: look for an OpenAI post, X post or teaser on Sep 2 before 9:32am PT. Adam Driver: find the D23 panel start time on Aug 14. Re-measure each lead against the primary source. Lead the slide with whichever case survives. | Claude-research | 15 |
| W2 | **Dutch Book panel.** On incomplete-list cards, show worst-case payout $0, worst-case loss -$21.15, and the paper profit greyed out as "only if the list were complete". Labels: "TRAP: list not complete" and "EATEN BY FEES". Show the "waitlist" tier badge once per section, and take the Predator-scale badges off alert cards (they confuse fans). | Claude-web | 10 |
| W3 | **iPhone hero overlap.** Below 480 px wide, move the 3D football behind the text at low opacity, or below the headline. Respect `prefers-reduced-motion`. Check on iPhone 13 and SE sizes with Playwright. | Claude-web | 10 |
| K1 | **Business slide plus a 5-row competitor table** (ESPN/theScore push, Apple Sports, the Kalshi app, Action Network/OddsJam, Genius/Sportradar official feeds). Columns: speed, what it tells you, price, what we add. Fill every [bracket] on the slides from M2/M3 at 2:30, not from the old STATS.md. | Kevin | 25 |
| D1 | **SF@SEA head-to-head, 1:25-2:30.** Put a phone with ESPN and theScore push alerts next to a Kalshi Knows phone and the stream. Record any alert, and log for each one: our push time, the ESPN/theScore push time, and when the stream shows it. Two data points beat a guess. | Dugar (video), Kevin (log) | 65 (live) |
| F1 | **Reorder the demo** (see below) and rehearse the Q&A twice. | Faisal | 20 |

**Optional, in order, only if a stream finishes early:**
- O1 Spoiler Shield toggle (Claude-web, 25 min). `sw.js` reads a stored preference and shows "Something big just happened in SF@SEA" with no team, play or score. Feed cards are blurred until tapped. The existing stream-delay picker can say "we'll hold it until your stream catches up" as a roadmap note. This answers the fan's #1 question on stage.
- O2 Leverage-aware detector recall (Claude-model, 20 min). Recall = the share of real big plays the detector catches, here limited to plays that moved ESPN's win probability by 8+ points. It answers "you miss 3 of 4 TDs".
- O3 What ESPN's wallclock marks (Claude-model, 15 min): snap, whistle or data entry. Check about 20 plays against nflverse `time_of_day`.
- O4 iPhone onboarding sheet with an Add to Home Screen arrow and a test-push button (Claude-web, 20 min).

**Demo reorder.** This replaces "LIVE 0:30-2:30".
1. Open the live board and show alerts that already fired today, with their timings, ideally one from SF@SEA (15 s).
2. Wait up to 45 s for a fresh buzz.
3. If nothing comes, play Dugar's SF@SEA recording without apologizing.
4. Phones that buzz during Q&A are a bonus.
5. Cut Dutch Book to one 15-second sentence. Show one Someone Knew case, not two.

At 3:45: the header pill says LIVE on the presenter machine, health shows `subscribers >= 3`, and the test push has arrived.

## 2. Claims to change (exact wording)

| Where | Now | Change to |
|---|---|---|
| Hero subtext (`index.html` L71) | "...We read the market and buzz your phone with the play before your TV gets there." | "Kalshi's traders react to a big play in about 7 seconds. Our alert lands about 30 seconds after the play. Streams show it 48 to 62 seconds after. That's a 15 to 40 second head start on streaming. (Cable, at 19 seconds, still beats us.)" Keep the big "About 40 seconds of lying" line: it describes the market vs the stream, and the subtext now explains it. |
| `index.html` L261 and SLIDES | "Call it before your TV does." / "before your TV" | "Call it before your stream does." |
| `index.html` L87 | "Some of them trade on it." | "Their trades move the price before your stream shows the play." |
| `index.html` L193 | "nflverse play-by-play 2016–2025" | "nflverse play-by-play: 25 seasons to train (1999-2023), 28 in total, 244k plays" |
| SLIDES 5 | "28 seasons ... [~1.2M plays]" | "25 seasons to train, 28 total, 244k plays" |
| Anywhere "beats ESPN" appears | "beat ESPN by 38.6-64.8 s" | "Our alerts arrived 39-65 s before the same play showed up in ESPN's public play-by-play feed, which we poll every [N] s (3 matched plays)." Never say "faster than ESPN". |
| Live tally (STATS, slides) | "3 of 5 settled alerts correct" / "3 confirmed, all right" | "7 alerts so far today: 3 matched a real turnover and named it right. 4 matched no score, turnover or 20+ yard gain." Update from E3 at 2:30. If asked, the model alone is 2 of 5. |
| Accuracy (everywhere) | 73%, 76.3%, 71.5%, 85.9%, 89.7%, 93% | "Trained on 2025 games, tested on 2026 games it never saw: it names the play right **72%** of the time, vs **57%** for always guessing 'nothing big' (same 569 fires, 58 games)." Second line from M2: "When it names a play at 75%+ confidence, it's right [X]% of the time ([N] calls)." Say 89.7% only if asked, as "an upper bound if you already know a big play happened." |
| "83-87% when 75%+ sure" | | Delete. Most of those are confident "nothing happened" calls, which never become alerts. Replace with the named-call precision from M2. |
| Detector | (unstated) | "About half our buzzes are a TD, field goal, turnover or 20+ yard play. 86% are one of those or another play that swung the game. We catch about 1 in 4 of those plays overall. If the market barely moves, we can't see the play." Use the O2 number if it is ready. |
| Someone Knew name | "Someone Knew" | "The market beat the headlines" |
| `app.js` L347 caption | "83% of big moves happened before any news we could find" | "5 of the 6 cases we checked by hand moved before the first article we could find (picked from 763 markets with big moves)." |
| GPT-6 case | "97% about 28 h before the first article" | Re-measure against the primary source (R1). If a Sep 2 public teaser explains the move, drop or relabel the case. Never imply that a named person traded on inside information. |
| Dutch Book | feature framing, profit numbers on traps | "We scanned 103,807 markets: 16 arbitrages before fees, 0 after. Fees are Kalshi's moat." |
| SLIDES Q&A | "ESPN's API posts plays [~30+] s late" | "Today ESPN's public feed showed plays 71-78 s after ESPN's own play timestamp. Our alerts came 28-33 s after it." |
| Market research doc | stream delays called "our measurement" | "published reference values (Super Bowl LX)" |
| Footer | "Paper trading only" | "Free. Public Kalshi and ESPN data only. We never trade or take bets. Not affiliated with Kalshi. Not betting advice. 21+ where required." |

## 3. Q&A prep: the 8 hardest questions

1. **"Your hero says 40 seconds. What is the real head start, and for whom?"**
   The market moves about 7 s after the play. Our push lands about 30 s after (28-33 s today), because we wait 8 s to read the shape of the move. On a 48-62 s stream, that is a 15-40 s head start. On cable at 19 s, we lose. The product is for streamers, and that is most young viewers.

2. **"'Beats ESPN': is that ESPN's free JSON? And what about the ESPN push I already get?"**
   Yes. It is ESPN's public play-by-play feed, which we poll, and today it showed plays 71-78 s after the play's own timestamp. Against ESPN and theScore push alerts we measured [D1 result] during SF@SEA. If D1 got nothing, say: "Not yet measured, and that's next. Score apps push scores. We also catch turnovers and big swings, and we can hold the alert until your stream catches up."

3. **"Which accuracy is real: 89.7, 76, 73 or 72?"**
   72%. We trained only on 2025 games and tested on 569 detector fires from 2026 games the model never saw. Always guessing "nothing big" scores 57% on those same fires. When we name a play at 75%+ confidence, we're right [X]% of the time. The 89.7% assumes you already know a big play happened, so it is an upper bound, not a product number.

4. **"You miss most touchdowns, and half your buzzes aren't big plays. Why would a fan leave this on?"**
   We only see plays the market reacts to. A garbage-time field goal doesn't move the price, so it isn't there to read. Of plays that swung the game, we catch [O2]%. 86% of our buzzes are a score, a turnover or a swing play. When the model isn't sure, the push says "big swing to Seattle" instead of guessing "touchdown".

5. **"Today you sent 7 alerts. How many were wrong? And what did the model see on a_6?"**
   3 right and 4 that matched no big play. The ledger on the site counts misses as misses. On a_6, the model saw halftime defaults, because ESPN's scoreboard runs about 50 s behind. Since [E2 time], we no longer name a play when the game state is stale. Retraining on realistically stale state is the next model fix. We also pre-registered a frozen-model test at noon, which scored [M3]% on [N] fires from today's early games.

6. **"Someone Knew: aren't 6 hand-picked cases out of 763 just selection? Are you accusing people of insider trading?"**
   They are hand-picked, and we say so. They are case files, not a rate. We renamed the section "The market beat the headlines" because we can show *when* the price moved, not *who* moved it. [R1: "We re-timed GPT-6 against OpenAI's own post: still N h early" or "we dropped it because a public teaser explained the move."]

7. **"Who pays? Isn't betting a slower sportsbook off your alert just courtsiding? And who owns the data?"**
   We warn bettors; we don't arm them. The consumer product is free: Spoiler Shield, plus a "this market already moved" warning before you live-bet. Revenue is B2B (business to business):
   - latency audits for streamers and sportsbooks;
   - a millisecond-aligned feed of "the price moved before the news" for exchanges and integrity teams.

   We use only Kalshi's public data, within its rate limits. Genius Sports holds the official NFL data rights through 2029, so we don't resell play data. We sell timing measurements.

8. **"What happens if your laptop or the tunnel dies right now? How does this serve 1,000 users?"**
   A watchdog restarts the engine within 20 s. The site switches to a clearly labeled replay and never fakes "live". Web Push fans out from a single poller, so polling Kalshi costs the same whether 10 people subscribe or 10,000. The next step is a small always-on server with a named tunnel.

Bonus, if asked "isn't this known?": Croxson and Reade (2014) showed that betting-exchange prices absorb goal news within about a minute. Fast reaction is known. What is new is reading the move backwards to say which play happened, before the broadcast shows it. (Verify the citation before saying it on stage.)

## 4. Post-hackathon product roadmap (top 5)

1. **Reliability first.** Move the engine off the laptop to a small always-on server with a named Cloudflare tunnel, health alerts, and a public uptime page. Because: nobody keeps notifications on for an app that goes dark mid-game.
2. **Retrain on what the live engine actually sees.** Simulate ESPN's 40-75 s state lag in training. Add state-age and state-missing features. Drop `micro_burst`. Train on order-book mid-prices instead of last trades. Remove duplicate overlapping fires. Switch to 4 user-facing classes (Score / Turnover / Big gain / Nothing). Each week, train on all earlier weeks and test on the next one, and publish the live ledger. Because: today's 3 wrong high-confidence calls came from stale inputs, not from a weak model.
3. **A fan product that respects spoilers.** Spoiler Shield, plus "sync to my stream": each subscriber picks a delay and the server holds the push that long. Add team follow, a per-game cooldown, guided iPhone setup, and "share this call" image cards. Because: the casual fan is the largest audience, and today the product is built against them.
4. **Read more than one market.** Use the KXNFLTD scorer market (about 13.5M open interest, all 12 games), total points and team totals to tell a TD from a FG from a turnover and to name the scorer. Pull historical tapes first so the model can learn these features. Because: this is the biggest accuracy gain available, and a named scorer makes a better push.
5. **B2B data product.** Sell Kalshi price paths aligned to plays at the millisecond, with market vs ESPN vs stream latency, as an API, latency audits and an integrity feed. Clear Kalshi's data terms and the NFL data rights first. Because: the analyst and the judge both named this as the part someone would pay for. The bettor would pay $10-15 a month only for a cross-sportsbook signal, which we are deliberately not building.

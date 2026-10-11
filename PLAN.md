# Kalshi Knows: plan (VSS New Member Hackathon, Sun Oct 11 2026, Haas N158)

Team 4: Faisal, Kevin, Dugar. **Hacking ends 4:00pm sharp.** Track 2: take something that exists (a market) and use it to find insights or make money.

## One-line pitch
Your TV is 20–60 seconds behind reality. Kalshi isn't. We read Kalshi's public order book live, work out *what just happened* from how the price jumped, and buzz your phone before your stream shows the play. The same engine looks at two more time scales: prices that contradict each other right now (Dutch Book) and markets that moved hours before the news (Someone Knew).

## Why it's novel (prior-art check, 10:00am)
- Stream delays are measured (Super Bowl LX: broadcast 19 s, best stream 48 s, worst 62 s), and there are anecdotes of traders exploiting them. **No published measurement of Kalshi's lead over streams, and no product that turns market moves into play-by-play spoilers.**
- Dutch-book arbitrage via LLM dependency detection has been done on **Polymarket** (arXiv 2508.03474, about $40M). Ours is on Kalshi and net of Kalshi's fee formula. That's a supporting act, not the headline.
- No systematic "market moved before the news" scan for Kalshi that we could find.

## The technical core
1. **Live jump detector**: polls the public order book for every live NFL game (batched, about 1 request/s total); a jump is a mid-price change of at least X within 20 s.
2. **Play inverter (trained on AWS)**:
   - A win-probability model trained on nflverse play-by-play data (every play, 2016–2025).
   - A model that answers: given the game state before the play and the observed jump, what play happened (TD / FG / turnover / big play)?
   - Trained on simulated jumps (the change in win probability, plus noise), then **tested on real Kalshi jumps aligned to ESPN plays** from the 2026 season. It's tabular data, so gradient-boosted trees (XGBoost on GPU, with a hyperparameter sweep) vs an MLP. Pick the best on held-out data.
3. **Lag measurement**: for every scoring play this season, the time from ESPN's real-world play clock to Kalshi's first big trade. This is the headline number.
4. **Dutch Book LP**: every open bracket/ladder event, fee-aware, using a linear program over outcomes.
5. **Someone Knew**: settled non-political markets with big moves; earliest news article from GDELT (a free news index); the lead time in minutes.
6. **Product**: an installable iPhone web app (PWA) on GitHub Pages, real Web Push notifications, a 3D hero, live SSE (server-sent events, a one-way live stream from the backend). The backend runs on the Mac and is exposed through a Cloudflare tunnel.

## Timeline (padded; if a step runs over, cut scope, never the deadline)
| Time | Milestone | Owner |
|---|---|---|
| 10:10–10:30 | Plan, contract, GPU box up, agents dispatched | Claude (lead) |
| 10:30–12:00 | NFL alignment data + lag numbers; live engine skeleton + push; Dutch Book scanner; Someone Knew candidates; website v1 deployed | agents |
| 11:00–12:30 | Train win-prob model + play inverter on AWS | lead |
| **12:30** | **Checkpoint: site live on GitHub Pages, push reaches Faisal's iPhone, early-game alerts firing, Dutch Book list renders.** Else cut. | all |
| 12:30–1:45 | Model into live alerts; Someone Knew case files; site polish + 3D; results.json | agents + lead |
| 1:05/1:25 | Late games kick off (DEN@LAC, DET@ARI, **SF@SEA**). Live testing on real plays | Faisal + Kevin |
| 1:45–2:30 | Record a live spoiler moment (screen + phone) as backup; fix bugs | Dugar + lead |
| **2:30** | **Feature freeze** | |
| 2:30–3:30 | Slides, 2–3 min video, rehearse twice | Kevin (slides), Dugar (video), Faisal (talk) |
| 3:30–4:00 | Buffer, submit, **terminate AWS** | lead |

## Demo script (5 min)
- **0:00–0:30.** "Who here watches games on a stream? You're watching the past." A slide shows "Super Bowl LX: streams ran up to 62 s behind." QR code: "Install Kalshi Knows."
- **0:30–2:30, LIVE.** The 49ers game streams on the projector, with Kalshi Knows on the second screen. When the market jumps, phones buzz: "SPOILER · SF @ SEA: 49ers touchdown (81% sure)." The room votes on what happened; then it shows up on the stream. If nothing happens in time, we play the recorded moment from 2pm.
- **2:30–3:15.** Someone Knew: two case files where the price moved before the first article.
- **3:15–3:45.** Dutch Book: the live "$ of contradictory pricing on Kalshi right now" counter; click one to see the paper trades and the guaranteed payoff, net of fees.
- **3:45–4:30.** How we built it, plus the numbers: Kalshi lags the real play by a median of X s; streams lag 20–60 s; play-type accuracy Y% vs a Z% baseline.
- **4:30–5:00.** What's next: a "spoiler shield" for people who *don't* want spoilers, and latency-aware sanity checks before you live-bet off a stream.

## Cut-list (drop in this order if behind)
1. Audience guessing game (keep alerts + push only)
2. MLP challenger (XGBoost only)
3. Someone Knew: cut to 5 hand-verified cases
4. 3D: hero only, no scroll scenes
5. Dutch Book: the bracket-sum check only, no ladder LP
6. Push to audience phones (team phones only; the audience watches the big screen)

## Backup
- `docs/data/replay.json` plays a real recorded game, so the site works with no backend.
- A 2–3 min video of a real spoiler moment, recorded during the 1:25pm games.

## Safety
GPU box `i-091573ad3d2fadc6c` (g6e.xlarge) auto-shuts down at 5:40pm PT; terminate by 4pm. Public data only, no trades, no Kalshi account.

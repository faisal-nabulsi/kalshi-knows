# The demo: what to show, what to click, what's proven

**Video:** https://github.com/faisal-nabulsi/kalshi-knows/releases/tag/demo-video (2:26 long cut; the 60–75 s pitch-ad cut gets added to the same release when it's rendered).
**Site:** https://kalshi-knows.pages.dev · presenter view: https://kalshi-knows.pages.dev/?present=1 (keys 1–7 switch pages, Q pins the QR).

## Live demo flow (90 seconds, slide 4 in SLIDES.md)
1. **Live page** (`#/live`): game tiles with Kalshi's live win probability, the **Kalshi vs Polymarket** panel under them ("Kalshi moved first by X s"), and **Receipts**: every alert today, timestamped and graded against ESPN, misses included ("When we named the play: N of N right").
2. **Wait up to 45 s** for a fresh alert on SF @ SEA / DET @ ARI / DEN @ LAC: full-screen spoiler takeover on the projector + Faisal's phone buzzes (push). If nothing fires, play the money-shot clip from the video.
3. **Auto page** (`#/auto`): the auto-bettor in **KALSHI DEMO EXCHANGE (play money)** mode. Rules: "49ers or Seahawks named call ≥80% → buy 5 YES on that team to win", $25/day cap, kill switch. Below: the **movers feed** across every Kalshi category (proof it works beyond NFL).
4. Optional: **Proof** (model leaderboard, head-to-head vs Claude), **Dutch Book** (100k markets, 0 arbitrages after fees), **Beat the headlines** (Princeton rankings moved ~6.8 h before the official release).

## Fallback: real replay of the Steelers TD
Use this if no live alert fires in step 2. It replays today's real **IND @ PIT "Steelers touchdown (80% sure)"** alert (12:37pm) from the engine's own logs, at real speed, on a second engine (port 8001). The live engine on :8000 and the tunnel are not touched.

1. **Before you present** (presenter laptop = the Mac running the engine): rehearse once with `engine/demo_replay.sh --no-push`. It prints the presenter URL. Then run `engine/demo_replay.sh --stop`.
2. **On stage:** run `engine/demo_replay.sh`. This one **pushes to every subscribed phone**, so Faisal's phone really buzzes.
3. Open **http://localhost:8002/?present=1&api=http://localhost:8001** (the script serves `docs/` on :8002). Don't use the https Pages URL with `api=http://localhost:8001`: Chrome blocks an https page from calling localhost unless you click a permission prompt. We tested this, and the site fell back to the old canned replay.
4. What happens: about **43 s** after you start, the takeover opens ("Big swing to the Steelers", phone buzz #1). About **8 s** later it changes to **"Steelers touchdown, 85% sure"** (phone buzz #2). About **35 s** after that, ESPN's play-by-play confirms the 17-yard Freiermuth TD. The Receipts row then shows **RIGHT**, 32 s before ESPN's public feed.
5. Honesty labels: the header badge says **REPLAY · live server**, the takeover says **REPLAY · MARKET MOVED …** and "REPLAY of a real alert from earlier today", and phone pushes are titled **"REPLAY · SPOILER · IND @ PIT"**. Replay alert ids start with `r_`, so the auto-bettor never trades on them, and they never count in today's tally. The replay engine also runs without the auto-bettor loop and the Dutch Book scanner.
6. Afterwards: `engine/demo_replay.sh --stop`. Note: `engine/restart_engine.sh` also kills the replay, because it stops every engine process. Re-run step 2 if you restart the live engine.

Options: `--lead 25` starts 25 s before the jump (shorter wait). `--no-serve` skips the :8002 site. Logs are in `engine/logs/run/replay.log`. Tested end to end with `--no-push` at 2:35pm (provisional, then named, then confirmed RIGHT).

## How alerts are graded (Receipts)
About 3 minutes after an alert fires, we check it against ESPN's play-by-play, in this order:
1. **Was there a TD, field goal, turnover, safety or 20+ yard play by that team?** If yes, a named call is **RIGHT** or **WRONG**. An unnamed "big swing" alert counts as **REAL PLAY, NOT NAMED**.
2. **If not, was there another play that moved ESPN's own win probability 5+ points toward that team?** The window runs from 20 s before the price jump to 90 s after it, and each play can only grade one alert. A "big swing" alert then counts as **REAL SWING PLAY**, with a plain-English label such as "Defensive stop — 3rd-down sack", "Big conversion", "Missed field goal", "Penalty swing" or "Return / special teams". A *named* call (TD, FG, turnover, big play) that only had a swing play behind it counts as **WRONG**.
3. **If neither:** **NO MATCHING PLAY**, which counts as a miss. These rows are collapsed behind "Show all (N)", but the count always stays in the header.

Today at 2:41pm: 48 alerts. 18 were tied to a TD, FG, turnover or 20+ yard play (the 4 named calls were all right). 17 were on another play that swung ESPN's win odds 5+ pts (3 of those were named calls we got wrong). 13 had no matching play. When we named the play, we were right **4 of 7 times**. Before swing grading, 26 of 44 alerts showed as "no matching play".

## What's proven on Kalshi's demo exchange (play money, real Kalshi API)
- First real order (2:05pm): **bought 1 YES "49ers win" at $0.39**, fee $0.0167, filled; order id `01a12cc9-43b0-7d31-af6a-b259485bac52`.
- Live ledger: [results/demo_ledger.json](results/demo_ledger.json) (balance, positions, fills, which alert triggered each order) and slide image [results/charts/i_demo_ledger.png](results/charts/i_demo_ledger.png). Refreshed at 3:45 to include any orders from the late games.
- Why demo for orders but the REAL market for data: demo prices are up to 14 pts off the real market and trade ~$1k/day vs ~$2.5M on the real game markets, so signals come from Kalshi's real public data and orders go to the demo exchange (no real money).

## Safety rails (say these if asked)
- Signed orders can only go to Kalshi's **demo** host (hard-coded; production order paths refused in code + tests).
- Public market data only; no real money; no politics in the UI; we show when a price moved, never who moved it.
- Watchdog restarts the engine within ~20 s; the site falls back to a clearly labelled replay if the backend drops.

## Pre-flight checklist (3:45pm)
- [ ] Presenter laptop: site shows **LIVE** (not REPLAY) in the header
- [ ] Faisal's phone: Kalshi Knows installed, alerts enabled, test push received (`/api/health` subscribers ≥ 1)
- [ ] Auto page shows mode **KALSHI DEMO**
- [ ] `.venv/bin/python results/export_demo.py` re-run (fresh ledger + chart)
- [ ] Video file downloaded locally as backup (Wi-Fi can die)

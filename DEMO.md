# The demo: what to show, what to click, what's proven

**Video:** https://github.com/faisal-nabulsi/kalshi-knows/releases/tag/demo-video (2:26 long cut; the 60–75 s pitch-ad cut gets added to the same release when it's rendered).
**Site:** https://kalshi-knows.pages.dev · presenter view: https://kalshi-knows.pages.dev/?present=1 (keys 1–7 switch pages, Q pins the QR).

## Live demo flow (90 seconds, slide 4 in SLIDES.md)
1. **Live page** (`#/live`): game tiles with Kalshi's live win probability, the **Kalshi vs Polymarket** panel under them ("Kalshi moved first by X s"), and **Receipts**: every alert today, timestamped and graded against ESPN, misses included ("When we named the play: N of N right").
2. **Wait up to 45 s** for a fresh alert on SF @ SEA / DET @ ARI / DEN @ LAC: full-screen spoiler takeover on the projector + Faisal's phone buzzes (push). If nothing fires, play the money-shot clip from the video.
3. **Auto page** (`#/auto`): the auto-bettor in **KALSHI DEMO EXCHANGE (play money)** mode. Rules: "49ers or Seahawks named call ≥80% → buy 5 YES on that team to win", $25/day cap, kill switch. Below: the **movers feed** across every Kalshi category (proof it works beyond NFL).
4. Optional: **Proof** (model leaderboard, head-to-head vs Claude), **Dutch Book** (100k markets, 0 arbitrages after fees), **Beat the headlines** (Princeton rankings moved ~6.8 h before the official release).

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

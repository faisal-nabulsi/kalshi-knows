# Slides: Kalshi Knows (Kevin owns; 5 min talk + 3 min Q&A)

Style: black background, off-white text, ONE orange accent (#FF4D1A) for "the market knows" moments. Huge numbers, few words. Use the website itself for the demo; slides are only the frame. Fill in the [brackets] from docs/data/results.json at ~2:30.

1. **Title.** "KALSHI KNOWS: the prediction market is a time machine." Team 4: Faisal Nabulsi, Kevin, Dugar. QR code → https://faisal-nabulsi.github.io/kalshi-knows/
2. **The problem (10 s).** "You're watching the past." Super Bowl LX: cable 19 s behind, best stream 48 s, worst 62 s. Meanwhile Kalshi traded $1B+ that day.
3. **The insight.** Kalshi's price moves [~7] seconds after a real play. Your stream shows it [20–60] seconds later. So the market can spoil your game, and anyone live-betting off a stream is trading against people who already know.
4. **LIVE DEMO (2 min).** Switch to the site in presenter mode (`?present=1`) next to the 49ers stream. Phones buzz → room votes → the play airs.
5. **How it works (one diagram).** Kalshi public order book (polled every ~2 s) → jump detector → **play inverter** (an XGBoost model trained on an L40S GPU on AWS with 28 seasons of NFL plays, [~1.2M plays], then calibrated on real Kalshi jumps) → Web Push to your phone.
6. **Results.**
   - Market lag after the real play: median [X] s (n = [N] plays, [G] games, 2026 season)
   - Detector: [P]% of alerts were real big plays; caught [R]% of TDs/turnovers
   - Play-type accuracy on REAL Kalshi jumps: [A]% vs [B]% for a sports-fan rule of thumb
   - The Predator Scale model leaderboard (Dugar → Kevin & Faisal)
7. **Someone Knew (hours, not seconds).** 2 case files: the price moved [N] minutes before the first article. "We don't say who. We say when."
8. **Dutch Book (right now).** We scanned 9,050 events / 103,807 markets for prices that contradict each other. 16 arbitrages before fees, **0 after** fees. 49 "free money" lists that aren't (the outcomes weren't exhaustive). Insight: fees are Kalshi's moat.
9. **What's next.** (1) Spoiler Shield: mute your feed until your stream catches up. (2) A stream-latency warning before you live-bet. (3) Every sport + Polymarket.
10. **Thanks + QR.**

Q&A prep (Faisal):
- "Is this legal / insider trading?" Public data only, no trading, no account. We measure information flow; we never name anyone.
- "Why not just use ESPN?" ESPN's API posts plays [~30+] s late; the market is faster than the official feed.
- "Does the model beat the market?" It isn't trying to predict winners; it infers WHAT happened from how the market moved.
- "How do you know the lag?" ESPN play wallclock timestamps aligned to Kalshi's millisecond trade timestamps, for every big play this season.

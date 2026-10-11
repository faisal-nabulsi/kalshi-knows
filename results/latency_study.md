# Alert latency study: how fast can the first buzz land after Kalshi moves?

Generated 2026-10-11 by `pipeline/latency_study.py` (numbers in `results/latency_study.json`). Nothing was deployed and no live default was changed.

## Headline

**First buzz = 8.2 s after Kalshi's price starts moving (today) -> 6.5 s with `JUMP_HOLD_S=1` (no websocket needed) -> 5.1 s (fastest quarter of plays: 3.1 s) with the websocket plus `JUMP_THRESHOLD=0.10 JUMP_HOLD_S=0 JUMP_WINDOW_S=10 PROVISIONAL_PUSH_MIN=0.11`.**

- Both configs keep phone-push precision within 2 points of today, or better.
- Relative to the ESPN play timestamp, the first buzz goes from 15.3 s to 13.5 s (poll) and then to 12.0 s (websocket).
- A 3 s median is not reachable with a threshold detector. The reason is that after the first trade of a jump, the price needs about 2.4-3.1 s (median) to travel a full 0.08-0.10. Push delivery then adds about 1 s.

## Terms

- **Move start**: the first trade of the price jump. Precisely, it is the first trade after the last trade (from ESPN time -20 s up to the halfway point) that is still within max(2 cents, 20% of the jump) of the pre-play price.
- **Halfway**: the first trade that crosses halfway between the pre-play price and the post-play price. Pre-play price = last trade in [-60, -5] s. Post-play price = volume-weighted average price in [+30, +90] s. These are the same definitions as `nfl_align.align_play`.
- **Big play**: a TD, FG, turnover, safety or 20+ yard play whose home-win price moved at least 0.08. Its halfway point must fall within [-10, +90] s of the ESPN timestamp. There are 243 such plays in 73 games.
- **Hold**: how long a detected jump must persist before the alert fires (`JUMP_HOLD_S`).
- **Window**: the look-back window for the jump (`JUMP_WINDOW_S`). The detector compares the price now to the window's min/max.
- **Precision strict**: the share of alerts within [-20, +90] s of a TD/FG/turnover/safety/20+ yd play.
- **Precision incl. swing**: precision strict, plus alerts within that window of plays that moved ESPN win probability by at least 5 points.
- **Recall**: the share of TD/FG/turnover plays with an alert in the window.
- **WS**: the Kalshi websocket feed (`engine/kalshi_ws.py`). It emits a quote at most every 250 ms per game, with a 1 s heartbeat, and is modelled with 0.2 s network latency. The websocket is currently off because there is no production key (`/api/health`, 14:55).
- **Poll**: the REST order-book poller. It reaches each game every ~1.2-3 s, depending on how many games are live. The study models it with ±15% jitter.

## Method

1. The study replays the millisecond Kalshi trade tapes (`pipeline/out/trades`, 73 games) through a port of `engine/live.py Engine._detect`. The port covers window min/max, the pending state, the hold, the revert at 0.75x threshold, confirmation at 0.9x threshold and the 60 s cooldown.
2. **Fidelity check**: on 12 games, the real `_detect` (imported from `engine.live`) and the port fired 135/135 alerts at identical timestamps.
3. Each feed (poll at 1.2/1.75/3 s, WS, 1 s grid) samples the last trade price at its quote times. The study then runs each detector configuration on the resulting quotes.
4. Phone pushes follow the live rules. A stage-1 ("provisional") push goes out at detection only if the move is at least `PROVISIONAL_PUSH_MIN` (today 0.10). Otherwise, the earliest possible buzz is the stage-2 ("called") push `CALL_DELAY_S`=8 s later. This is a best case, because live sends that push only if the play is named or the move is at least 0.12. Push delivery is assumed to take 1 s.
5. "Paired gain" is the median per-play speed-up versus today's configuration, measured only on plays both detectors caught. Low-recall detectors catch only the sharpest moves, which flatters their raw medians, so the paired gain is the fairer speed comparison.

## 1. Latency budget today (median seconds, big plays)

| step | seconds | how measured |
|---|---|---|
| ESPN play timestamp -> Kalshi move start | 6.3 (p25 5.1, p75 8.0) | trade tape vs ESPN wallclock |
| move start -> halfway | 0.55 | trade tape: jumps are nearly instant |
| price travels the 0.08 threshold + next quote | 2.4 | WS, hold 0 (2.59) minus 0.2 s network |
| hold 3 s | 2.9 | WS hold 3 (5.53) minus WS hold 0 (2.59) |
| REST poll sampling (1.75 s) vs WS | 1.4 | poll (6.89) minus WS (5.53), both with today's detector |
| **= detection after move start** | **6.9** (p25 5.0, p75 9.0) | today's config, replayed |
| push delivery | 1.0 | assumed |
| provisional gate (`PROVISIONAL_PUSH_MIN`=0.10) | +0.3 median, +8 s on about half of alerts | if the move at detection is < 0.10, the first buzz waits for stage 2 |
| **= first buzz after move start** | **8.2** (p75 14.4) | 15.3 s after the ESPN play |

The two biggest costs we control are the 3 s hold (2.9 s) and REST polling (1.4 s). The provisional gate also matters: it is why any faster detector must be paired with the right `PROVISIONAL_PUSH_MIN`. Without that pairing, a faster detection fires while the move is still below 0.10, the stage-1 push is skipped, and the buzz waits 8 s for stage 2. For example, WS + threshold 0.09 + hold 0 with the push minimum left at 0.10 has a p75 first buzz of 12.5 s.

## 2. Detectors compared (alert level, i.e. the site feed)

Today's replayed precision (47.2% strict / 82.1% incl. swing) is lower than the 52.8% / 85.8% in `detector_sweep.json`. The reason is that the sweep used a simpler `p(t)-p(t-20s)` rule on a 1 s grid. The live engine compares against the window min/max, which catches more swings. All rows below use the same live logic, so they are comparable with each other.

| detector | s after move start, median (p25-p75) | s after ESPN play | paired gain vs today (s) | precision strict | precision incl. swing | recall | alerts/game |
|---|---|---|---|---|---|---|---|
| **today**: REST poll 1.75 s, thr 0.08, window 20 s, hold 3 s | 6.9 (5.0-9.0) | 13.5 | +0.0 | 47.2% | 82.1% | 26.6% | 9.1 |
| today, poll 1.2 s (few live games) | 6.1 (5.0-8.6) | 13.0 | +0.2 | 46.9% | 81.2% | 26.8% | 9.5 |
| today, poll 3 s (many live games) | 8.8 (6.7-11.1) | 15.2 | -1.8 | 49.6% | 85.3% | 24.6% | 8.0 |
| pipeline 1 s grid (reference) | 5.8 (4.4-8.1) | 12.0 | +0.9 | 46.1% | 79.6% | 28.8% | 10.2 |
| (a) poll 1.75 s, hold 1 s | 5.0 (3.2-7.2) | 11.7 | +1.8 | 46.9% | 81.3% | 27.0% | 9.4 |
| (a) poll 1.75 s, hold 0 s (= next poll) | 5.0 (3.2-7.2) | 11.7 | +1.8 | 46.9% | 81.3% | 27.0% | 9.4 |
| (d) poll, thr 0.09, hold 1 s | 5.3 (3.7-8.0) | 12.0 | +1.6 | 50.0% | 84.4% | 21.9% | 7.3 |
| (d) poll, thr 0.10, hold 1 s | 5.8 (3.9-8.0) | 12.1 | +1.6 | 54.4% | 87.6% | 18.8% | 5.9 |
| WS, today's detector | 5.5 (4.1-8.1) | 12.5 | +1.1 | 44.5% | 78.9% | 29.5% | 11.2 |
| (a) WS, hold 1 s | 3.6 (2.1-5.9) | 10.5 | +3.2 | 43.2% | 78.4% | 29.9% | 11.8 |
| (a) WS, hold 0 s | 2.6 (1.4-5.2) | 9.8 | +3.9 | 43.2% | 78.2% | 30.4% | 12.0 |
| (d) WS, thr 0.09, hold 0, window 20 s | 3.4 (1.6-6.3) | 10.2 | +3.5 | 45.4% | 80.8% | 25.8% | 9.6 |
| (d) WS, thr 0.09, hold 1 s | 3.9 (2.3-7.3) | 10.9 | +2.7 | 45.5% | 81.2% | 25.3% | 9.4 |
| (c) WS, thr 0.09, hold 0, window 10 s | 3.1 (1.5-4.9) | 9.5 | +3.4 | 45.9% | 83.1% | 21.5% | 8.1 |
| (c) WS, thr 0.09, hold 0, window 5 s (velocity) | 2.4 (1.2-3.7) | 8.8 | +3.5 | 46.0% | 85.4% | 16.5% | 6.2 |
| (c) WS, thr 0.10, hold 0, window 10 s | 3.3 (1.5-5.4) | 9.8 | +3.0 | 49.1% | 85.4% | 17.6% | 6.4 |
| (c) WS, thr 0.10, hold 0, window 5 s | 2.4 (1.1-3.9) | 8.5 | +3.2 | 47.5% | 87.1% | 12.5% | 4.7 |
| (e) WS, thr 0.09, survive 2 trades | 3.5 (1.8-6.3) | 10.4 | +3.3 | 45.7% | 81.4% | 25.7% | 9.4 |
| (e) WS, thr 0.09, survive 5 trades | 4.0 (2.2-7.6) | 11.2 | +3.0 | 45.9% | 81.5% | 25.7% | 9.4 |
| (b) burst >=0.05 in 2 s, 3+ trades, no confirm | 0.4 (0.2-1.2) | 6.7 | +5.4 | 36.1% | 64.8% | 30.7% | 15.0 |
| (b) burst >=0.08 in 2 s, 3+ trades, holds 1 s | 1.9 (1.2-2.8) | 8.2 | +3.2 | 45.3% | 82.6% | 13.4% | 4.7 |
| (b) burst >=0.10 in 5 s, 3+ trades, holds 1 s | 3.1 (1.6-4.5) | 9.4 | +2.5 | 53.5% | 88.5% | 12.1% | 3.6 |

What the table says:
- **(a) Hold.** On REST polling, hold 0 s and 1 s are identical, because the next poll is already more than 1 s away. Either setting is 1.8 s faster (paired) and costs 0.3 / 0.8 points of precision. On WS, cutting the hold is fast (2.6-3.6 s) but costs 3-4 points of precision at threshold 0.08.
- **WS alone hurts precision** at today's settings (-2.7 / -3.2 points). The reason is that tick-level sampling catches brief one-trade spikes that a 1.75 s poll usually misses. So switching on WS should come with a higher threshold.
- **(d) Threshold.** On WS, 0.06-0.08 loses 3-10 points of precision with any hold or window. 0.09-0.10 restores it.
- **(c) Shorter window (velocity).** A 5-10 s window is the most precise fast option (83-87% incl. swing). The cost is recall: it misses slower, multi-step swings.
- **(e) Survive k trades instead of k seconds.** This matches a time hold. With k=2 the result is about the same as hold 0 (3.5 s vs 3.4 s at the same precision), so there is no gain.
- **(b) Burst/sweep detector** (raw trades with taker side). It is the fastest by far: 0.4-1.9 s after move start, with precision comparable to today's at X >= 0.08 plus a 1 s confirm. Recall is only 12-13%, and it needs new code (trade-channel parsing), so it is not a config flip. It would make a good fast first trigger next to the threshold detector after the demo.

## 3. Phone pushes (first buzz)

| config | first buzz, s after move start, median (p25-p75) | s after ESPN play | pushes/game | push precision strict | push precision incl. swing |
|---|---|---|---|---|---|
| **today** (poll, hold 3 s, PROVISIONAL_PUSH_MIN 0.10) | 8.2 (6.2-14.4) | 15.3 | 5.2 | 54.1% | 87.5% |
| today + PROVISIONAL_PUSH_MIN 0.08 (push every alert) | 7.9 (6.0-10.0) | 14.5 | 9.1 | 47.2% | 82.1% |
| **poll + JUMP_HOLD_S=1** | 6.5 (4.3-13.7) | 13.5 | 5.2 | 52.9% | 86.3% |
| poll + hold 1 s + PROVISIONAL_PUSH_MIN 0.08 | 6.0 (4.2-8.2) | 12.7 | 9.4 | 46.9% | 81.3% |
| poll + hold 1 s + late-push patch at 0.10 | 6.2 (4.3-10.5) | 13.1 | 6.5 | 50.6% | 85.5% |
| poll 1.2 s + hold 1 s | 6.3 (3.9-13.3) | 14.9 | 4.9 | 50.0% | 84.6% |
| WS, today's detector | 7.1 (5.2-14.6) | 15.2 | 5.8 | 51.8% | 86.2% |
| WS thr 0.09 hold 0 win 20, push min 0.10 | 5.4 (3.2-12.5) | 13.8 | 5.9 | 49.1% | 83.9% |
| WS thr 0.09 hold 0 win 20, push min 0.09 (every alert) | 4.4 (2.6-7.3) | 11.2 | 9.6 | 45.4% | 80.8% |
| WS thr 0.09 hold 0 win 10, late-push patch at 0.12 | 5.8 (3.2-11.8) | 13.2 | 4.6 | 54.4% | 87.3% |
| WS thr 0.10 hold 0 win 10, push min 0.10 | 4.4 (2.9-7.2) | 11.0 | 5.9 | 50.6% | 86.2% |
| **WS thr 0.10 hold 0 win 10, push min 0.11** | 5.1 (3.1-10.2) | 12.0 | 4.2 | 56.5% | 87.1% |
| WS thr 0.10 hold 0 win 10, late-push patch at 0.12 | 5.1 (3.2-9.6) | 12.5 | 4.7 | 53.7% | 88.6% |

Today, phones buzz on about 5.2 alerts per game, with push precision of 54.1% strict / 87.5% incl. swing. Pushing every alert (`PROVISIONAL_PUSH_MIN` = threshold) is faster but nearly doubles the buzzes, and the extra buzzes are mostly false alarms. So it does not meet the "no more false alarms" bar. A "late provisional push" patch was also simulated. It would push the moment the move reaches the minimum within the 8 s call window. It gives only 0.1-0.8 s extra and costs push precision, so it is not recommended. No code patch is needed: every recommended change is an existing env var.

## 4. Ready-to-flip configs (not applied)

All four variables are read at engine start (`engine/live.py` lines 47-81), so a flip means a restart. The `JUMP_THRESHOLD` env var overrides `results/detector_sweep.json`, which this study did not touch.

**A. Now, REST polling (no prod key):**
```
JUMP_HOLD_S=1
```
- Detection: 6.9 -> 5.0 s after move start (paired -1.8 s).
- First buzz: 8.2 -> 6.5 s after move start, and 15.3 -> 13.5 s after the ESPN play.
- Alert precision: 47.2/82.1 -> 46.9/81.3. Push precision: 54.1/87.5 -> 52.9/86.3. Recall: 26.6 -> 27.0%. Alerts per game: 9.1 -> 9.4.
- Why 1 s and not 0: on polling they behave the same. If the websocket comes on later, 1 s still guarantees a real hold, whereas 0 would fire on the next 250 ms quote.
- Caveat: with only 1-2 live games, polls come every ~1.2 s. In that case push precision drops 2.2 / 1.8 points versus the same-rate baseline, which is right at the 2-point limit.

**B. Once the websocket (prod key) is live:**
```
JUMP_THRESHOLD=0.10 JUMP_HOLD_S=0 JUMP_WINDOW_S=10 PROVISIONAL_PUSH_MIN=0.11
```
- Detection: 3.3 s after move start (paired -3.0 s vs today).
- First buzz: 5.1 s median, 3.1 s at p25 and 10.2 s at p75. That is 12.0 s after the ESPN play.
- Push precision: 56.5/87.1 at 4.2 pushes per game. That is better than today, so phones get fewer false alarms.
- Site-feed alerts: precision 49.1/85.4 (better than today), but recall drops 26.6 -> 17.6%, with 6.4 alerts per game.
- Why: on WS the hold is no longer needed for de-noising, because the higher threshold and the 10 s window do that job and are faster. Raising the push minimum to 0.11 then keeps phone precision at or above today's.
- If recall matters more than buzz speed, use `JUMP_THRESHOLD=0.09 JUMP_HOLD_S=0 JUMP_WINDOW_S=20` and keep `PROVISIONAL_PUSH_MIN=0.10`. That gives detection 3.4 s (paired -3.5 s), recall 25.8%, alert precision 45.4/80.8 (-1.8/-1.3), and a first buzz of 5.4 s. The catch is that push precision falls to 49.1/83.9.

## Caveats

- **Trade prints, not order-book mids.** The tapes record trades, while the engine prices off the order-book mid. Trade prints bounce between bid and ask and show one-trade spikes, so the WS rows probably understate WS precision. The order book can also move before a trade prints, so real WS detection may be slightly earlier than shown.
- **Poll timing is modelled, not logged.** The poll is a jittered fixed interval. The real round-robin also weights focus games and games with a pending alert 2x, which shortens the effective interval right when it matters.
- **ESPN timestamp meaning.** ESPN wallclock timing is not exact, so "seconds after the ESPN play" is a relative comparison, not an absolute one.
- **Push timing assumptions.** Push delivery is fixed at 1 s. Stage-2 pushes are assumed to always fire, which is a best case for any row that relies on them.

Reproduce: `cd pipeline && ../.venv/bin/python latency_study.py` (about 4 min on 5 cores). Push-rule rows come from `latency_study.run_push(cfg, rules)`. Per-play move start, halfway and fire times for 7 key detectors are in `latency_study.json` under `per_play`.

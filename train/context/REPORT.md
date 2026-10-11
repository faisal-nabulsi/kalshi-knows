# Context features + pre-registered edge finder: results

**Bottom line:** twenty seconds after a big swing, Kalshi's price is already fair (calibration slope 0.97 [0.80, 1.15]). None of 8 pre-registered context edges survived the 2026 holdout after fees, and adding weather, spread, rest or injuries to the play model changed nothing (all within noise, no better than a shuffled placebo). The market digests plays in seconds, so the only edge is speed.

## 1. Context for the play model (same protocol as train/eval_same_rows.py; live regime |Δ| ≥ 0.08)
| Features | Accuracy | Δ vs production [95% CI] | Named-call precision (calls) |
|---|---|---|---|
| Production (stage-1 + state), CV by game (2,940 fires, 296 games) | 73.7% | – | 79.5% (200) |
| + venue/weather | 73.4% | −0.3 [−0.9, +0.3] | 80.9% (204) |
| + spread/total | 73.4% | −0.3 [−0.9, +0.3] | 76.4% (203) |
| + rest/division/primetime | 73.2% | −0.5 [−1.0, −0.0] | 81.2% (197) |
| + QB status/injuries | 73.3% | −0.4 [−1.0, +0.2] | 79.1% (210) |
| + all context | 73.3% | −0.4 [−1.0, +0.3] | 79.1% (210) |
| Train 2025 → test 2026, production / + all context | 74.0% / 73.3% | −0.7 [−2.1, +0.6] | 81.1% (37) / 74.4% (43) |
Why: the pre-jump Kalshi price already contains the context; context changes who will win, not what just happened.

## 2. Edge finder (HYPOTHESES.md committed before outcomes were split by context)
Discovery on 2025 (2,210 jumps), one test on 2026 (565 jumps), trade at +20 s at last trade + 1¢, net of the taker fee, Bonferroni over 8.
| # | Rule | 2025 ROI | 2026 ROI | Result |
|---|---|---|---|---|
| H1 | Fade Q1–Q2 jumps | −8.4% | −12.8% | failed |
| H2 | Follow last-5-min Q4/OT jumps | −5.3% | −8.2% | failed |
| H3 | Fade dome team outdoors in cold/wind | −14.8% | no 2026 games | untestable |
| H4 | Buy 6.5+ favorite after early setback | +0.9% (CI ±24) | −19.7% | failed |
| H5 | Fade primetime jumps | −1.4% | −19.5% | failed |
| H6 | Fade jumps toward backup-QB team | −2.0% | −39.1% | failed |
| H7 | Buy ≥85% side (favorite-longshot) | −2.8% | −0.7% | failed |
| H8 | Best of 24-cell grid (Q4/OT, jump ≥0.15, fade) | +30.4% (p=0.044) | −24.0% | passed 2025 by chance, failed 2026 |
Post-jump calibration: slope 0.97 at +20 s, 0.99 at +60 s; median price move +20→+60 s is 0. Fading/following every jump: ~0% before costs, −4 to −5% after (1¢ spread + ~1.4¢ fee).

Caveats: last-trade prices (not the book); "backup QB" is a proxy; 2026 = weeks 1–5 (~60 games).

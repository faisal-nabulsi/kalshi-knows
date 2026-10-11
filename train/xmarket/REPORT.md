# Cross-market study: does a model beat the Kalshi price? (Kalshi Knows)

Plain-language summary. Code: `kaggle/xmarket/train_xmarket.py`. Raw numbers: `kaggle/xmarket/out_local/` (metrics.json and CSVs).

## What was run, and where (read this first)
- Data: the public Kalshi dump from Jon-Becker/prediction-market-analysis. Kaggle kernels could not reach `s3.jbecker.dev` (DNS and direct-IP probes both timed out). Hugging Face was also blocked from the kernel. The data was therefore taken from the Hugging Face mirror `TrevorJS/kalshi-trades` (CC-BY-4.0, built on Andrew Becker's Kalshi dump, 154.5M trades, 17.5M markets, Jun 2021 - Jan 2026). I downloaded it on the Mac in streaming fashion (about 6 GB, files deleted after reduction), not Kaggle.
- The same script (`XM_LOCAL=1`) ran on the Mac CPU in 3 minutes. The Kaggle kernel `faisalnabulsi/kalshi-knows-xmarket` failed 3 times on network egress, and no Kaggle GPU was ever used (the kernel reported no GPU). XGBoost therefore ran on CPU. The Kaggle GPU request in the brief was NOT met.
- Everything is logged to W&B project `kalshi-knows` (offline run, synced from the Mac). The filtered table is saved as private Kaggle dataset `faisalnabulsi/kalshi-settled-markets` (34 MB).

## Markets used
- 4,363,922 settled yes/no markets in the mirror. Only 22 were multivariate (combo) markets by the `KXMVE` ticker prefix, so the combo filter removed almost nothing. Combo markets in this mirror may be named differently.
- Only 351,244 settled markets traded before at least one cutoff. The other roughly 4 million never traded or traded only inside the last hour. Features use ONLY trades before close time minus 24h / 6h / 1h, giving 783,444 market-horizon rows.
- Categories come from the dataset repo's own ticker mapping. Sports is by far the biggest in the test set (101k of 142k rows).

## Split (no leakage)
- Fit: markets closing 2021-07 to 2025-12-11 (225,295 markets). Validation (early stopping, threshold choice): 2025-12-13 to 2026-01-03. Test (newest 20%): **2026-01-05 to 2026-01-30, 70,249 markets, 142,446 rows**.
- 2-day gaps between splits, and any event with a market on the newer side was removed from the older side.

## Brier score vs the raw market price (lower is better)
| model | Brier (all) | Brier (price 5-95c only) | log loss (all) |
|---|---|---|---|
| raw market price | 0.1270 | 0.1742 | 0.3934 |
| global Platt calibration | 0.1262 | 0.1732 | 0.3915 |
| per-category Platt | 0.1258 | 0.1727 | 0.3877 |
| per-category isotonic | 0.1259 | 0.1731 | 0.3874 |
| multi-feature logistic | 0.1251 | 0.1718 | 0.3847 |
| XGBoost | **0.1236** | **0.1717** | **0.3768** |

- XGBoost gain over the market: 0.0034 Brier (about 2.7%), 95% CI [0.0028, 0.0040] (bootstrap over events). On contested prices only: 0.0026 [0.0018, 0.0033]. The gain is real but small.
- By horizon (XGBoost vs market): 24h 0.1484 vs 0.1492, 6h 0.1514 vs 0.1516 (both nearly no gain); 1h 0.0960 vs 0.1024 (the gain is concentrated near close).
- By group (Brier, market -> XGBoost): Sports 0.1464 -> 0.1426 (101k rows); Finance 0.0920 -> 0.0723 (only 3.5k rows); Crypto 0.0556 -> 0.0547; Entertainment 0.0335 -> 0.0318; Weather 0.0430 -> 0.0428; Media 0.0620 -> 0.0635 and Other 0.1219 -> 0.1232 (XGBoost is slightly worse). Full table: `metrics_by_category.csv`.

## Calibration and favorite-longshot bias
- 24h-before-close reliability in the test month (`reliability_deciles_h24.csv`): the market price was too HIGH in every price decile. Realized win rate minus price runs from -0.8 points (prices under 10c) to -6.0 points (70-80c). Prices 90c+ won 90.4% against a 95.3% price.
- So the main error in January 2026 is a broad "YES is overpriced" shift (strongest for favorites), not a classic longshot effect. XGBoost mostly learns this shift (its mean prediction sits 1-5 points under the price). Part of the Brier gain is therefore one month's regime, not a stable structural edge.
- Classic favorite-longshot bias is weak in the fit period. The slope of logit(outcome) on logit(price) is 0.94 to 1.12 for every category (1.0 means calibrated). Longshots (15c or less) win about 1-2 points less than their price in Sports, Weather, Entertainment, Other and Politics. Crypto is the exception (+2.1 points). Test-period Sports favorites (85c or more) won 7.2 points less than their price. Per-category numbers: `favorite_longshot_by_category.csv`.

## Paper strategy, net of Kalshi taker fee ceil(0.07 * C * P * (1-P))
Rules: one bet per market at 24h or 6h before close; buy YES if model - price > threshold, buy NO if price - model > threshold; needs 5+ trades and 50+ contracts before the cutoff and a price between 3c and 97c. Fee uses C=10 contracts and rounds up to the cent. The threshold is picked on the validation month only. Fills are assumed at the last traded price, which is optimistic. The +1c slippage column is the stress test.

| model, horizon | threshold | bets | hit rate | avg P&L per contract (95% CI) | ROI | with +1c slippage |
|---|---|---|---|---|---|---|
| XGBoost, 24h | 0.08 | 1,603 | 58.2% [54.9, 61.7] | +6.1c [+3.3, +9.1] | +12.0% [6.5, 17.8] | +5.1c |
| XGBoost, 6h | 0.05 | 5,371 | 58.8% [57.0, 60.5] | +3.6c [+2.1, +5.0] | +6.7% [3.9, 9.4] | +2.6c |
| multi-feature logistic, 24h | 0.02 | 4,997 | 68.5% | +2.0c [+0.7, +3.3] | +3.0% | +1.0c |
| per-category isotonic, 24h | 0.02 | 7,274 | 63.6% | +1.4c [+0.3, +2.5] | +2.2% | +0.4c |

Confidence intervals come from resampling whole events (500-1000 draws). Fees are already inside the P&L. Gross (pre-fee) P&L for XGBoost 24h is +7.6c.

## Honest verdict
- The model does beat the raw price out of sample on Brier and log loss, with confidence intervals that exclude zero. The size is small (about 2.7% Brier) and concentrated near close and in Sports volume.
- The paper strategy is positive after fees in this one test month, including with 1c slippage. But it is a single 26-day window, and much of the edge is one correction (YES overpriced). Edges in a different regime could vanish or flip. A rolling retrain across several months would be needed before trusting it.
- Higher-threshold results rest on fewer bets and wider intervals. Some groups lose (for example Finance in the logistic per-group table).

## Caveats
- The last trade price is not an executable price. Real fills pay the spread, which this dataset has no quotes for.
- Only markets that traded are covered (8% of settled markets). Many untraded markets are mechanical strike ladders.
- `close_time` can be later than when the outcome became known. Many "24h before close" prices are already near 0 or 100. The 5-95c columns report the harder subset.
- Categories are inferred from ticker prefixes. "Other" is a large catch-all.
- Test-period Finance and Crypto samples are small (3.5k and 7k rows). Treat their per-category numbers as noisy.
- No API keys were used, and nothing secret went to Kaggle.

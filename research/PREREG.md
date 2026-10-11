# Pre-registration: frozen model for today's untouched test

Frozen at 2026-10-11 12:25 PDT, BEFORE any of today's games (Sun Oct 11 2026) were used for training or evaluation.
No retraining or threshold changes until after the test is reported.

| Item | Value |
|---|---|
| Stage 1 model | engine/model/playinfer_xgb.json, sha256 `97613fe8cec0e5e89103cba655dac952ec15033a0d7dea17f1e185dbefd71853` (XGBoost, nflverse 1999-2023 train) |
| Stage 2 model | engine/model/stage2_xgb.json, sha256 `5c94d6b7c2aac4e15e2124061f7bb11be5ca65091fbf986dceb8cd932610605c` (stage-1 log-probs + game state; 8,808 real fires, 2025 + 2026 wk1-5) |
| Detector | |Δp| ≥ 0.08 over a trailing 20 s window, held 3 s, 60 s cooldown |
| Call delay | 8 s after the jump is confirmed |
| Confidence gate | name the play only if top class ≠ OTHER and prob ≥ 0.75; otherwise "big swing" |
| Labels | ESPN play-by-play categories as in pipeline/nfl_build_plays.py (TD > safety > turnover incl. on downs > FG > 20+ yd gain > OTHER) |
| Match window | ESPN play wallclock in [jump −20 s, +90 s] |
| Test set | today's games that are final by ~1:20pm PT and were never in training (pipeline/out/train_games.json excludes them) |
| Metrics (reported as-is) | accuracy and always-OTHER on the same fires (live regime ≥0.08), named-call precision at ≥0.75 + count, game-clustered bootstrap 95% CI |

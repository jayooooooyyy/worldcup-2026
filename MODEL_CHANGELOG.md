# Model Changelog

This file records model changes and backtest metrics so future iterations do not mix model purposes or regress silently.

## Frozen Dashboard Stack

Date: 2026-06-11

| Use | Model |
|---|---|
| Winner / favorite | `v4_elo_ensemble_calibrated_v1` |
| Probability / fair odds | `calibrated_v3_floor_010_T1.2` |

Draw is treated as a risk signal, not as the final pick.

## v1: Elo Only

- Purpose: baseline benchmark.
- Features: team Elo ratings and Elo difference.
- Role: compare later models against the simplest Elo-driven model.

## v4: Elo + Recent Form + Goal Stats

- Purpose: stronger match-result feature model.
- Features: Elo, recent match form, recent goals for/against.
- Added sample weighting:
  - recency weighting
  - tournament weighting
- Role: main feature model inside the ensemble.

## calibrated_v1: Winner Picker

- Version: `v4_elo_ensemble_calibrated_v1`
- Purpose: winner / favorite pick.
- Structure: V4 model + Elo-only model ensemble, followed by probability calibration.
- Dashboard role: choose `winner_model_pick`.
- World Cup walk-forward backtest:
  - accuracy: 67.97%
  - log loss: 2.116
  - brier: 0.422
  - avg draw probability: 25.46%
- Known issue: probability tails are too aggressive, so log loss is poor on upsets and draws.

## calibrated_v3_floor_010_T1.2: Probability Model

- Version: `calibrated_v3_floor_010_T1.2`
- Purpose: probability display and fair odds.
- Base: `v2_50_50 = 50% calibrated_v1 + 50% raw_ensemble`
- Probability floor: 0.10
- Temperature scaling: T = 1.2
- Dashboard role: `home_win_prob`, `draw_prob`, `away_win_prob`, fair odds, draw risk, upset risk.
- World Cup walk-forward backtest:
  - accuracy: 66.41%
  - log loss: 1.520
  - brier: 0.499
  - avg draw probability: 27.36%
  - min true class probability: 12.40%
- Selection reason: best fit to current probability-display target while keeping high winner accuracy.

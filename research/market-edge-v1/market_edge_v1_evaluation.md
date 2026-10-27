# Market Edge V1 — Prospective Evaluation

**Decision:** `HOLD_MARKET_EDGE_V1_NO_VALIDATED_EDGE`

- Baseline players: **503**
- Baseline: **2026-09-17T03:39:09.844866Z**

## Market-movement horizons

| Horizon | Status | N | Gap→change ρ | Mean-reversion ρ | Incremental Δ | Directional | Buy−sell spread |
|---|---|---:|---:|---:|---:|---:|---:|
| 1w_diagnostic | evaluated | 503 | 0.040 | 0.141 | -0.102 | 0.505 | 0.003 |
| 2w_supportive | evaluated | 503 | 0.040 | 0.141 | -0.102 | 0.505 | 0.003 |
| 4w_primary | evaluated | 503 | 0.044 | 0.143 | -0.099 | 0.528 | 0.003 |

## Frozen 4-week hard gates

- `minimum_common_players`: **PASS**
- `minimum_gap_change_spearman`: **FAIL**
- `minimum_incremental_spearman_vs_mean_reversion`: **FAIL**
- `minimum_directional_accuracy`: **FAIL**
- `minimum_directional_comparable_players`: **PASS**
- `minimum_buy_minus_sell_mean_change`: **FAIL**
- `minimum_positions_with_positive_spearman`: **PASS**

## Secondary realized-production test

This is descriptive only and cannot rescue a failed market-movement result.

- 2w: n=503, position-gap→production-surprise Spearman **0.657**
- 4w: n=503, position-gap→production-surprise Spearman **0.681**

## Governance

- No thresholds or gates are re-fit from these results.
- No player recommendation is deployed from this study.
- FV, Market Value V2, Team Utility, and verdict math are unchanged.

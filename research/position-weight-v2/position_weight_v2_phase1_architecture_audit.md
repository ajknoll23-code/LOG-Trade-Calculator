# Position Weight / Cross-Position Economics V2 — Phase 1 Architecture Audit

**Research only. No POSITION_WEIGHT change is authorized.**

Method: `position-weight-v2-phase1-architecture-audit-v1`

## Architecture

- **Replacement rank:** within-position production normalization. This is already isolated and frozen prospectively.
- **POSITION_WEIGHT:** cross-position translation of the same normalized production unit into league-specific economic value.
- **Global scale:** absolute display/value-unit scale; not calibrated here.

Phase 1 deliberately does **not** turn start demand or replacement PPG directly into a new weight. Each is only one axis of cross-position economics.

## Current weights versus independent league signals

| Pos | Current PW | PW vs WR | Effective demand | Demand vs WR | 80/90/95% start coverage | Bootstrap 50% crossing | Median replacement-PPG scale vs WR | Rank-family scale CV |
|---|---:|---:|---:|---:|---|---|---:|---:|
| QB | 1.30 | 1.300 | 27.65 | 0.835 | 24/29/34 | 22 [22, 34] | 1.565 | 0.110 |
| RB | 0.89 | 0.890 | 27.03 | 0.816 | 26/33/39 | 25 [25, 28] | 1.225 | 0.037 |
| WR | 1.00 | 1.000 | 33.13 | 1.000 | 36/43/49 | 34 [28, 37] | 1.000 | 0.000 |
| TE | 0.82 | 0.820 | 19.83 | 0.599 | 21/27/33 | 13 [10, 13] | 0.781 | 0.040 |
| DL | 0.93 | 0.930 | 34.37 | 1.037 | 29/39/47 | 34 [16, 37] | 0.967 | 0.050 |
| LB | 1.12 | 1.120 | 40.52 | 1.223 | 41/50/55 | 43 [40, 52] | 1.169 | 0.040 |
| DB | 0.87 | 0.870 | 36.43 | 1.100 | 38/47/53 | 28 [22, 40] | 1.005 | 0.028 |

## Historical replacement scoring scale by frozen rank family

Each cell is the median 2024–2025 replacement PPG ratio versus WR under that already-frozen replacement-rank family.

| Pos | Legacy | Prior evidence | Stable-only | Full leaders |
|---|---:|---:|---:|---:|
| QB | 1.667 | 1.634 | 1.496 | 1.246 |
| RB | 1.182 | 1.308 | 1.225 | 1.225 |
| WR | 1.000 | 1.000 | 1.000 | 1.000 |
| TE | 0.801 | 0.785 | 0.719 | 0.777 |
| DL | 0.869 | 0.951 | 0.984 | 0.984 |
| LB | 1.234 | 1.209 | 1.130 | 1.130 |
| DB | 1.045 | 1.028 | 0.982 | 0.982 |

## Diagnostic mismatches

These are **not candidate weights**. They only show where the current multiplier is far from either raw-demand scale or absolute replacement-scoring scale.

| Pos | Current PW / demand index | Current PW / scoring-scale index | Demand × scoring index vs WR |
|---|---:|---:|---:|
| QB | 1.558 | 0.831 | 1.306 |
| RB | 1.091 | 0.726 | 1.000 |
| WR | 1.000 | 1.000 | 1.000 |
| TE | 1.370 | 1.049 | 0.468 |
| DL | 0.896 | 0.961 | 1.004 |
| LB | 0.916 | 0.958 | 1.430 |
| DB | 0.791 | 0.866 | 1.105 |

## Interpretation

A direct `effective demand → POSITION_WEIGHT` mapping is rejected because it ignores absolute scoring leverage and available supply.

A direct `replacement PPG ratio → POSITION_WEIGHT` mapping is also rejected because it ignores how often the position occupies scarce lineup slots.

Market Value is intentionally **not** used as ground truth. Fundamental Value should remain independently grounded in league scoring/economics rather than being trained to imitate the market layer.

## Phase 2

Build a historical out-of-sample **marginal lineup utility** target. The target should combine:

1. future realized scoring surplus above a future-only replacement structure, and
2. observed lineup demand/exposure for the position.

Then test cross-position weight families while holding replacement rank, PM transform, age, role, no-history semantics, and global scale fixed. POSITION_WEIGHT must be the only cross-position scaler allowed to move.

## Guardrails

- deployment_authorized: **false**
- position_weight_change_authorized: **false**
- replacement_rank_change_authorized: **false**
- production_v2_change_authorized: **false**
- transform_change_authorized: **false**
- scale_change_authorized: **false**
- frozen prospective experiments touched: **false**

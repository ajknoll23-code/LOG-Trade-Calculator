# Position Weight / Cross-Position Economics V2 — Phase 3 Historical Calibration

**Research only. No POSITION_WEIGHT change is authorized.**

Method: `position-weight-v2-phase3-historical-calibration-v1`

## Target

Future target = **active-game structural lineup utility under the 2026 roster slots**. A structurally started player gets his league-scored points; an active nonstarter gets 0. Missing-score weeks are omitted so durability is not re-tested.

Every candidate receives its own training-only global rescale, so only relative POSITION_WEIGHT differences can win.

## Alpha selection across all frozen replacement families

| Alpha | Mean primary MAE | Rank families beating control | Window×family non-worse |
|---:|---:|---:|---:|
| 0.00 | 3.6181 | 0/4 | 12/12 (+100.0%) |
| 0.25 | 3.5399 | 4/4 | 12/12 (+100.0%) |
| 0.50 | 3.4663 | 4/4 | 12/12 (+100.0%) |
| 0.75 | 3.4293 | 4/4 | 12/12 (+100.0%) |
| 1.00 | 3.4212 | 4/4 | 12/12 (+100.0%) |

Selected historical alpha: **1.00**
Historical screen: **PASS**

## Primary 4-week results by replacement-rank family

| Rank family | Deployed MAE | Selected MAE | Δ vs deployed | Selected pairwise |
|---|---:|---:|---:|---:|
| `legacy_control` | 3.6372 | 3.3988 | -6.6% | 0.8016 |
| `prior_limited_evidence` | 3.6444 | 3.4140 | -6.3% | 0.7996 |
| `stable_positions_only` | 3.6344 | 3.4354 | -5.5% | 0.7989 |
| `full_phase2_leaders` | 3.5564 | 3.4364 | -3.4% | 0.7967 |

## Full-history candidate weights

These are **shadow candidates only**.

| Pos | Deployed | Robust median candidate | Family min | Family max |
|---|---:|---:|---:|---:|
| QB | 1.300 | 2.213 | 1.694 | 2.335 |
| RB | 0.890 | 1.554 | 1.526 | 1.601 |
| WR | 1.000 | 1.000 | 1.000 | 1.000 |
| TE | 0.820 | 0.687 | 0.650 | 0.707 |
| DL | 0.930 | 0.695 | 0.645 | 0.719 |
| LB | 1.120 | 1.070 | 1.046 | 1.123 |
| DB | 0.870 | 0.660 | 0.656 | 0.676 |

## Interpretation

If the historical screen passes, Phase 4 may shadow the robust median candidate on the current board. Large rank-family spread is a warning that weight and replacement normalization are not cleanly separable for that position.

## Guardrails

- deployment_authorized: **false**
- position_weight_change_authorized: **false**
- replacement_rank_change_authorized: **false**
- production_v2_change_authorized: **false**
- transform_change_authorized: **false**
- scale_change_authorized: **false**
- frozen prospective experiments touched: **false**

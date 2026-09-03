# Continuous Opportunity / Role Signal V2 — Phase 2 Candidate Evaluation

Method: `opportunity-v2-phase2-candidate-evaluation-v1`  
Status: **`RESEARCH_ONLY_OPPORTUNITY_INCREMENTAL_PREDICTION_AUDIT`**

## Guardrail

**Research only. No deployed ROLE_MULT or player value is changed.**

## Historical protocol

- Base seasons: **2015–2024**
- Evaluation rows: **16506**
- Future-zero rows: **4410**
- Target: **next-season custom-scored points per scheduled team game**
- Cross-validation: **leave one base season out**
- Model: **position-specific OLS**
- Missing future production: **zero**

## Overall out-of-fold results

| Variant | MAE | RMSE | Spearman | Pearson | Δ MAE vs production | Δ Spearman | Pos MAE improved | Folds MAE improved |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `production_only` | 2.1913 | 3.1779 | 0.6740 | 0.7216 | — | — | — | — |
| `production_plus_season_opportunity` | 2.1910 | 3.1786 | 0.6739 | 0.7214 | -0.0003 | -0.0001 | 2/7 | 7/10 |
| `production_plus_active_snap` | 2.1814 | 3.1696 | 0.6700 | 0.7233 | -0.0100 | -0.0040 | 6/7 | 9/10 |
| `production_plus_active_and_availability` | 2.1842 | 3.1689 | 0.6671 | 0.7234 | -0.0071 | -0.0069 | 4/7 | 8/10 |
| `production_plus_season_opportunity_change` | 2.1752 | 3.1539 | 0.6729 | 0.7266 | -0.0161 | -0.0011 | 7/7 | 9/10 |

## By-position Spearman

| Variant | QB | RB | WR | TE | DL | LB | DB |
|---|---:|---:|---:|---:|---:|---:|---:|
| `production_only` | 0.6915 | 0.6742 | 0.7086 | 0.6803 | 0.6529 | 0.6785 | 0.6517 |
| `production_plus_season_opportunity` | 0.6967 | 0.6734 | 0.7082 | 0.6772 | 0.6545 | 0.6787 | 0.6512 |
| `production_plus_active_snap` | 0.6908 | 0.6628 | 0.7068 | 0.6778 | 0.6524 | 0.6750 | 0.6478 |
| `production_plus_active_and_availability` | 0.6771 | 0.6490 | 0.6984 | 0.6741 | 0.6490 | 0.6753 | 0.6481 |
| `production_plus_season_opportunity_change` | 0.7035 | 0.6673 | 0.7082 | 0.6738 | 0.6522 | 0.6751 | 0.6509 |

## By-position MAE delta vs production-only

| Variant | QB | RB | WR | TE | DL | LB | DB |
|---|---:|---:|---:|---:|---:|---:|---:|
| `production_plus_season_opportunity` | +0.0160 | +0.0017 | +0.0058 | +0.0041 | -0.0121 | +0.0036 | -0.0034 |
| `production_plus_active_snap` | +0.0035 | -0.0089 | -0.0065 | -0.0011 | -0.0229 | -0.0082 | -0.0094 |
| `production_plus_active_and_availability` | +0.0212 | -0.0000 | +0.0043 | +0.0026 | -0.0169 | -0.0155 | -0.0117 |
| `production_plus_season_opportunity_change` | -0.1015 | -0.0081 | -0.0067 | -0.0013 | -0.0260 | -0.0064 | -0.0136 |

## Monitoring result

Monitoring leader: **`production_plus_season_opportunity_change`**

**This is not a deployment choice.**

## Phase 3

If an opportunity candidate improves future production beyond the production-only control across the overall sample and most positions, apply the surviving candidate(s) to current real-history players as a research-only shadow. Keep Production V2 frozen and do not rewrite its forward blend. The opportunity layer should be evaluated as a role/durability signal, not as a replacement forward-projection engine.

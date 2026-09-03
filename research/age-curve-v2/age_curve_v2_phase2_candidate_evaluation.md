# Age Curve V2 — Phase 2 Out-of-Sample Candidate Evaluation

Method: `age-curve-v2-phase2-candidate-evaluation-v1`  
Status: **`RESEARCH_ONLY_OUT_OF_SAMPLE_AGE_CURVE_CANDIDATES`**

## Guardrail

**Research only. No deployed AGE_CURVE or player value is changed.**

- Historical player-season rows: **14102**
- Cross-validation: **leave_one_base_season_out**
- Primary target: **mean of Year+1 and Year+2 custom-scored points per scheduled team game**

## Overall out-of-sample results

| Model | N | MAE ↓ | RMSE ↓ | Spearman ↑ | Pearson ↑ | Pairwise ↑ |
|---|---:|---:|---:|---:|---:|---:|
| `current_production_only` | 14102 | 2.3507 | 3.4612 | 0.6677 | 0.7150 | 0.7519 |
| `deployed_age_policy_proxy` | 14102 | 2.2576 | 3.3908 | 0.6752 | 0.7163 | 0.7546 |
| `empirical_position_age_k25` | 14102 | 1.9903 | 2.9688 | 0.6919 | 0.7308 | 0.7620 |
| `empirical_tier_age_k25` | 14102 | 1.9700 | 2.9125 | 0.6958 | 0.7330 | 0.7638 |
| `empirical_position_age_k50` | 14102 | 1.9920 | 2.9646 | 0.6897 | 0.7309 | 0.7612 |
| `empirical_tier_age_k50` | 14102 | 1.9696 | 2.9136 | 0.6940 | 0.7336 | 0.7631 |

## Empirical candidate improvement vs controls

| Candidate | Δ MAE vs current-only | Δ MAE vs deployed proxy | Δ Spearman vs current-only | Δ Spearman vs deployed proxy |
|---|---:|---:|---:|---:|
| `empirical_tier_age_k50` | -0.3811 | -0.2880 | +0.0263 | +0.0189 |
| `empirical_tier_age_k25` | -0.3806 | -0.2875 | +0.0281 | +0.0206 |
| `empirical_position_age_k25` | -0.3604 | -0.2672 | +0.0242 | +0.0168 |
| `empirical_position_age_k50` | -0.3587 | -0.2655 | +0.0220 | +0.0145 |

## By-position primary-target Spearman

| Model | QB | RB | WR | TE | DL | LB | DB |
|---|---:|---:|---:|---:|---:|---:|---:|
| `current_production_only` | 0.7336 | 0.6759 | 0.7052 | 0.6603 | 0.6584 | 0.6601 | 0.6280 |
| `deployed_age_policy_proxy` | 0.7313 | 0.6879 | 0.7080 | 0.6593 | 0.6637 | 0.6650 | 0.6413 |
| `empirical_position_age_k25` | 0.7340 | 0.6934 | 0.7253 | 0.6792 | 0.6862 | 0.6879 | 0.6590 |
| `empirical_tier_age_k25` | 0.7327 | 0.6939 | 0.7278 | 0.6839 | 0.6893 | 0.6936 | 0.6620 |
| `empirical_position_age_k50` | 0.7347 | 0.6915 | 0.7234 | 0.6769 | 0.6831 | 0.6858 | 0.6567 |
| `empirical_tier_age_k50` | 0.7339 | 0.6932 | 0.7258 | 0.6828 | 0.6872 | 0.6916 | 0.6607 |

## Monitoring result

- Best empirical candidate by primary MAE: **`empirical_tier_age_k50`**
- This is **not a deployment choice**.

The monitoring leader is descriptive only. No AGE_CURVE constant should change until current-player shadow impacts are audited and the chosen candidate is checked for position/tier stability.

## Phase 3

Apply the strongest historical candidate(s) to the current player database as shadow age multipliers, compare rank/value movement, and freeze a small candidate family for prospective 2026 review.

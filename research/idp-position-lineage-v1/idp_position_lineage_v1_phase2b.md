# IDP Position Lineage V1 — Phase 2B Age-Feedback Shadow

**Decision:** `PASS_IDP_POSITION_LINEAGE_V1_PHASE2B_AGE_FEEDBACK_SHADOW`

Production remains unchanged.

## Cohort

- Frozen current-core cohort: **27**
- Candidates: **24**
- Holds: **3**
- Production-sensitive-age candidates: **21**
- Candidates with nonzero FV age feedback: **3**

## Hard gates

| Gate | Result |
|---|---|
| `phase1b_pass_and_hashes_intact` | PASS |
| `phase2_stop_and_hashes_intact` | PASS |
| `phase2_failure_was_age_output_only` | PASS |
| `frozen_cohort_counts_intact` | PASS |
| `current_core_identity_position_intact` | PASS |
| `deployed_raw_still_matches_phase1b` | PASS |
| `transport_reconstruction_exact` | PASS |
| `unclamped_model_offset_preserved` | PASS |
| `static_metadata_and_age_formula_inputs_unchanged` | PASS |
| `age_multiplier_recomputes_exactly` | PASS |
| `post_peak_age_multiplier_unchanged` | PASS |
| `age_feedback_direction_consistent` | PASS |
| `fv_effect_decomposition_exact` | PASS |
| `held_rows_unchanged` | PASS |
| `candidate_values_valid` | PASS |
| `raw_prod_direction_total_fv_monotonic` | PASS |
| `zero_noncohort_fv_changes` | PASS |
| `zero_offense_fv_changes` | PASS |

## FV decomposition diagnostics

- Median total FV delta: **+1127.0**
- Median direct-production effect: **+1104.0**
- Median age-feedback effect: **+0.0**
- P90 age-feedback effect: **+55.3**
- Median age-feedback share of absolute total: **0.0%**

### Largest age-feedback effects

| Player | Pos | Age | Total ΔFV | Direct Prod | Age Feedback | Age Mult Δ |
|---|---|---:|---:|---:|---:|---:|
| abdul carter | DL | 22 | +1249 | +1008 | +241 | +0.049511 |
| dallas turner | DL | 23 | +1374 | +1229 | +145 | +0.026865 |
| david bailey | DL | 23 | +969 | +890 | +79 | +0.019903 |
| akheem mesidor | DL | 25 | +870 | +870 | +0 | +0.000000 |
| alex highsmith | DL | 29 | +1235 | +1235 | +0 | +0.000000 |
| bradley chubb | DL | 30 | +1080 | +1080 | +0 | +0.000000 |
| brian burns | DL | 28 | +1768 | +1768 | +0 | +0.000000 |
| byron young | DL | 28 | +1500 | +1500 | +0 | +0.000000 |
| derrick barnes | DL | 27 | +1152 | +1152 | +0 | +0.000000 |
| harold landry | DL | 30 | +1103 | +1103 | +0 | +0.000000 |
| jaelan phillips | DL | 27 | +1149 | +1149 | +0 | +0.000000 |
| jermaine johnson | DL | 27 | +785 | +785 | +0 | +0.000000 |
| joseph ossai | DL | 26 | +925 | +925 | +0 | +0.000000 |
| joshua metellus | LB | 28 | -650 | -650 | +0 | +0.000000 |
| micah parsons | DL | 27 | +1200 | +1200 | +0 | +0.000000 |
| nick herbig | DL | 24 | +1179 | +1179 | +0 | +0.000000 |
| nik bonitto | DL | 26 | +1449 | +1449 | +0 | +0.000000 |
| nolan smith | DL | 25 | +774 | +774 | +0 | +0.000000 |
| odafe oweh | DL | 27 | +1105 | +1105 | +0 | +0.000000 |
| rashan gary | DL | 28 | +1097 | +1097 | +0 | +0.000000 |

## Decision semantics

A PASS proves the prior Phase 2 STOP came from an invalid age-output invariant, while the unchanged production age formula deterministically explains the feedback. It still does not authorize deployment.


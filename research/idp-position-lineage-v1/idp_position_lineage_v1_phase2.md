# IDP Position Lineage V1 — Phase 2 Shadow Sanity

**Decision:** `STOP_IDP_POSITION_LINEAGE_V1_PHASE2_SHADOW_SANITY`

Production remains unchanged.

## Frozen candidate

- Current-core cohort: **27**
- Candidate rows: **24**
- Held rows: **3**
- Candidate rows with changed FV: **24**
- Clamp-saturated candidates: **0**

## Hard gates

| Gate | Result |
|---|---|
| `phase1b_pass_and_hashes_intact` | PASS |
| `frozen_cohort_identity_position_intact` | PASS |
| `deployed_raw_still_matches_phase1b` | PASS |
| `transport_reconstruction_exact` | PASS |
| `unclamped_model_offset_preserved` | PASS |
| `candidate_metadata_and_age_multiplier_unchanged` | FAIL |
| `held_rows_unchanged` | PASS |
| `candidate_values_valid` | PASS |
| `prod_direction_fv_monotonic` | PASS |
| `zero_noncohort_fv_changes` | PASS |
| `zero_offense_fv_changes` | PASS |

## Candidate movement diagnostics

- Median raw PROD_MULT delta: **+0.2269**
- Median FV delta: **+1127.0**
- P90 FV delta: **+1446.0**
- Median FV % change: **+34.3%**
- Median absolute position-rank move: **15.0**
- P90 absolute position-rank move: **22.0**

## Position distribution diagnostics

| Pos | Pop N | Targets | Candidates | Current median FV | Shadow median FV | Top-12 in/out | Top-24 in/out | Top-36 in/out | Max abs move |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DB | 69 | 0 | 0 | 2818.0 | 2818.0 | 0/0 | 0/0 | 0/0 | 0 |
| DL | 88 | 26 | 23 | 2918.5 | 3200.5 | 4/0 | 7/0 | 7/0 | 25 |
| LB | 82 | 1 | 1 | 3270.0 | 3214.5 | 0/0 | 0/0 | 0/1 | 15 |

## Largest candidate FV movers

| Player | Pos | Old FV | Shadow FV | Delta | Old Prod | New Prod | Rank Delta |
|---|---|---:|---:|---:|---:|---:|---:|
| brian burns | DL | 5623 | 7391 | +1768 | 1.0993 | 1.4449 | -1 |
| byron young | DL | 4623 | 6123 | +1500 | 0.9039 | 1.1970 | -5 |
| nik bonitto | DL | 4415 | 5864 | +1449 | 0.8631 | 1.1465 | -5 |
| will anderson | DL | 4522 | 5961 | +1439 | 0.8840 | 1.1653 | -5 |
| dallas turner | DL | 3695 | 5069 | +1374 | 0.7892 | 1.0516 | -10 |
| tj watt | DL | 4075 | 5344 | +1269 | 0.9395 | 1.2321 | -5 |
| abdul carter | DL | 2956 | 4205 | +1249 | 0.7095 | 0.9513 | -22 |
| alex highsmith | DL | 3984 | 5219 | +1235 | 0.7788 | 1.0203 | -5 |
| micah parsons | DL | 3742 | 4942 | +1200 | 0.7316 | 0.9662 | -8 |
| nick herbig | DL | 3525 | 4704 | +1179 | 0.6892 | 0.9197 | -13 |
| derrick barnes | DL | 2247 | 3399 | +1152 | 0.4392 | 0.6645 | -24 |
| jaelan phillips | DL | 3391 | 4540 | +1149 | 0.6630 | 0.8876 | -15 |
| odafe oweh | DL | 3153 | 4258 | +1105 | 0.6165 | 0.8324 | -18 |
| harold landry | DL | 3404 | 4507 | +1103 | 0.7202 | 0.9536 | -13 |
| rashan gary | DL | 3197 | 4294 | +1097 | 0.6250 | 0.8394 | -18 |
| bradley chubb | DL | 2637 | 3717 | +1080 | 0.5580 | 0.7865 | -25 |
| travon walker | DL | 3135 | 4208 | +1073 | 0.6129 | 0.8226 | -18 |
| uchenna nwosu | DL | 2854 | 3863 | +1009 | 0.5580 | 0.7553 | -19 |
| david bailey | DL | 2690 | 3659 | +969 | 0.5877 | 0.7821 | -22 |
| joseph ossai | DL | 2657 | 3582 | +925 | 0.5194 | 0.7002 | -18 |

## Decision semantics

A PASS establishes that the large movement is structurally isolated and consistent with the original IDP V1 transport methodology. It does not by itself authorize deployment.


# IDP Position Lineage V1 — Phase 1B Current-Core Rebase

**Decision:** `PASS_IDP_POSITION_LINEAGE_V1_PHASE1B_CURRENT_CORE_FREEZE`

Production remains unchanged.

## Cohort

- Frozen current-core mismatches: **27**
- Candidate rows: **24**
- Held rows: **3**
- Rows with changed FV: **24**

## Hard gates

| Gate | Result |
|---|---|
| `immutable_release_hashes_match` | PASS |
| `failed_phase1_artifacts_intact` | PASS |
| `current_core_cohort_nonempty_unique` | PASS |
| `current_positions_exact` | PASS |
| `deployed_raw_matches_frozen_v1` | PASS |
| `classification_complete` | PASS |
| `no_unguarded_floor_rescue_discontinuity` | PASS |
| `candidate_values_valid` | PASS |
| `prod_direction_fv_monotonic` | PASS |
| `zero_noncohort_fv_changes` | PASS |
| `zero_offense_fv_changes` | PASS |

## Movement diagnostics

- Median raw PROD_MULT delta: **+0.2246**
- Median FV delta: **+1103.0**
- P90 FV delta: **+1443.0**
- Minimum FV delta: **-650.0**
- Maximum FV delta: **+1768.0**

### Rank stability

| Pos | Target N | Max abs move | Top-24 >=5 | Top-36 >=5 |
|---|---:|---:|---:|---:|
| DB | 0 | 0 | 0 | 0 |
| DL | 26 | 25 | 7 | 11 |
| LB | 1 | 15 | 0 | 1 |

### Largest FV movers

| Player | Legacy | Current | Old FV | Candidate FV | Delta | Status |
|---|---|---|---:|---:|---:|---|
| brian burns | LB | DL | 5623 | 7391 | +1768 | candidate |
| byron young | LB | DL | 4623 | 6123 | +1500 | candidate |
| nik bonitto | LB | DL | 4415 | 5864 | +1449 | candidate |
| will anderson | LB | DL | 4522 | 5961 | +1439 | candidate |
| dallas turner | LB | DL | 3695 | 5069 | +1374 | candidate |
| tj watt | LB | DL | 4075 | 5344 | +1269 | candidate |
| abdul carter | LB | DL | 2956 | 4205 | +1249 | candidate |
| alex highsmith | LB | DL | 3984 | 5219 | +1235 | candidate |
| micah parsons | LB | DL | 3742 | 4942 | +1200 | candidate |
| nick herbig | LB | DL | 3525 | 4704 | +1179 | candidate |
| derrick barnes | LB | DL | 2247 | 3399 | +1152 | candidate |
| jaelan phillips | LB | DL | 3391 | 4540 | +1149 | candidate |
| odafe oweh | LB | DL | 3153 | 4258 | +1105 | candidate |
| harold landry | LB | DL | 3404 | 4507 | +1103 | candidate |
| rashan gary | LB | DL | 3197 | 4294 | +1097 | candidate |
| bradley chubb | LB | DL | 2637 | 3717 | +1080 | candidate |
| travon walker | LB | DL | 3135 | 4208 | +1073 | candidate |
| uchenna nwosu | LB | DL | 2854 | 3863 | +1009 | candidate |
| david bailey | LB | DL | 2690 | 3659 | +969 | candidate |
| joseph ossai | LB | DL | 2657 | 3582 | +925 | candidate |

A PASS freezes the current-core candidate for a separate shadow/sanity review. It does not authorize deployment.


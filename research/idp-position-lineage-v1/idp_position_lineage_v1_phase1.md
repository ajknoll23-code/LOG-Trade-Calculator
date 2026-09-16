# IDP Position Lineage V1 — Phase 1 Audit

**Decision:** `STOP_IDP_POSITION_LINEAGE_V1_PHASE1_INTEGRITY_FAILURE`

Research-only. Production is unchanged.

## Frozen cohort

- Position-lineage mismatches: **46**
- Current-core targets: **27**
- Free-agent-only targets held: **18**
- Not-currently-rendered targets held: **1**
- Recomputed candidates: **24**
- Explicit holds: **22**
- Floor-rescue guarded holds: **0**
- Target rows with stable Sleeper ID: **45**
- Target rows with changed FV: **24**

## Hard gates

| Gate | Result |
|---|---|
| `immutable_release_hashes_match` | PASS |
| `target_count_exact_46` | PASS |
| `current_positions_match_frozen_target` | FAIL |
| `live_core_positions_match_frozen_target` | PASS |
| `free_agent_positions_match_frozen_target` | FAIL |
| `live_roster_merge_resolved` | PASS |
| `deployed_raw_matches_frozen_v1` | PASS |
| `target_identity_unique` | PASS |
| `classification_complete` | PASS |
| `no_unguarded_floor_rescue_discontinuity` | PASS |
| `candidate_values_valid` | PASS |
| `prod_direction_fv_monotonic` | PASS |
| `zero_non_target_fv_changes` | PASS |
| `zero_offense_fv_changes` | PASS |

## Movement

- Median raw PROD_MULT delta: **+0.2246**
- P90 absolute-style raw delta endpoint: **+0.2871**
- Median FV delta: **+1103.0**
- P90 FV delta: **+1443.0**
- Minimum FV delta: **-650.0**
- Maximum FV delta: **+1768.0**

### Rank stability by current position

| Pos | Target N | Max abs rank move | Top-24 movers >=5 | Top-36 movers >=5 |
|---|---:|---:|---:|---:|
| DB | 0 | 0 | 0 | 0 |
| DL | 26 | 25 | 7 | 11 |
| LB | 1 | 15 | 0 | 1 |

### Largest FV movers

| Player | Legacy pos | Current pos | Old FV | Candidate FV | Delta | Status |
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

## Decision semantics

A PASS freezes an isolated position-lineage candidate for shadow validation. It does not authorize deployment.


# Offense Position Lineage V1 — Phase 1 Audit

**Decision:** `STOP_OFFENSE_POSITION_LINEAGE_V1_NO_MATERIAL_CANDIDATE`

Research-only. Production is unchanged.

- Offense position-lineage mismatches: **1**
- Current-core targets: **0**
- Recomputed candidates: **0**
- Explicit holds: **1**
- Target rows with changed FV: **0**

## Hard gates

| Gate | Result |
|---|---|
| `offense_replacement_baseline_rank32_available` | PASS |
| `live_core_positions_match_generated_current_position` | PASS |
| `classification_complete` | PASS |
| `no_unguarded_floor_rescue_discontinuity` | PASS |
| `candidate_values_valid` | PASS |
| `prod_direction_fv_monotonic` | PASS |
| `zero_non_target_fv_changes` | PASS |
| `zero_idp_fv_changes` | PASS |
| `apex_diagnostic_complete` | PASS |

## Brian Burns vs Josh Allen apex diagnostic

- Diagnostic status: **`HIGH_PRIORITY_CROSS_POSITION_CALIBRATION_REVIEW`**
- Brian Burns: **7391 FV**, DL rank **#1**, overall **#5**
- Josh Allen: **6564 FV**, QB rank **#1**, overall **#10**
- Burns minus Allen: **+827 FV**
- Burns / Allen FV ratio: **1.1260x**
- Burns raw/effective PROD_MULT: **1.4449 / 1.4449**
- Allen raw/effective PROD_MULT: **0.918 / 0.918**
- Burns position weight / age multiplier: **0.93 / 1.0**
- Allen position weight / age multiplier: **1.3 / 1.0**
- High-priority >=1.10x flag: **YES**

This apex diagnostic is separate from the lineage candidate. A flag supports a later cross-position calibration study; it does not justify reversing a lineage fix.

# Player Role V2 — B44W4 V1 Week-4 DOB_POSITION Remediation Re-Audit

- Decision: **SCIENTIFIC_STOP_B44W4_V1_OWNER_BLIND_ROLE_PARITY_FAILED**
- Classification: **Same-week Week-4 engineering remediation validation; not independent confirmation**
- V1R1 scientific STOP preserved: **Yes**
- Team count: **12**
- Minimum team role coverage: **0.9737**
- Maximum team role coverage: **1.0000**
- Coverage range: **0.0263**
- Required per-team coverage: **0.98**
- Maximum allowed coverage range: **0.02**
- Rostered DOB_POSITION overlay players: **14**
- Overlay precision verified: **14**
- Overlay precision unverifiable: **0**
- Overlay precision contradictions: **0**
- Production authorized: **No**

## Opaque team parity

| Team | Role-eligible | Covered | Pending | Identity-gap unknown-pos | Source disagreement | No current evidence | Pos-label mismatch | Coverage | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| Team01 | 44 | 44 | 0 | 0 | 0 | 3 | 2 | 1.0000 | PASS |
| Team02 | 38 | 37 | 1 | 0 | 0 | 4 | 0 | 0.9737 | FAIL |
| Team03 | 41 | 41 | 0 | 0 | 0 | 2 | 2 | 1.0000 | PASS |
| Team04 | 34 | 34 | 0 | 0 | 0 | 9 | 3 | 1.0000 | PASS |
| Team05 | 43 | 43 | 0 | 0 | 0 | 5 | 2 | 1.0000 | PASS |
| Team06 | 40 | 40 | 0 | 0 | 1 | 3 | 1 | 1.0000 | PASS |
| Team07 | 39 | 39 | 0 | 0 | 0 | 7 | 3 | 1.0000 | PASS |
| Team08 | 41 | 41 | 0 | 0 | 0 | 4 | 2 | 1.0000 | PASS |
| Team09 | 42 | 42 | 0 | 0 | 0 | 5 | 3 | 1.0000 | PASS |
| Team10 | 41 | 41 | 0 | 0 | 0 | 2 | 2 | 1.0000 | PASS |
| Team11 | 40 | 39 | 1 | 0 | 0 | 7 | 1 | 0.9750 | FAIL |
| Team12 | 41 | 40 | 1 | 0 | 0 | 5 | 1 | 0.9756 | FAIL |

## Gate results

- exactly_12_teams: **PASS**
- every_team_has_supported_position_denominator: **PASS**
- minimum_98pct_role_coverage_every_team: **FAIL**
- maximum_2_percentage_point_coverage_range: **FAIL**
- structural_owner_slot_role_invariance: **PASS**
- shadow_refresh_frozen_before_roster_semantic_parse: **PASS**
- shadow_role_inference_source_firewall: **PASS**
- all_eight_positions_in_declared_scope: **PASS**
- no_owner_blind_fallback_invented_post_holdout: **PASS**
- continuation_class_preserved: **PASS**
- model_or_tier_retuning_absent: **PASS**
- B41J_implementation_parity_oracle: **PASS**
- DOB_POSITION_fresh_reference_precision: **PASS**
- rostered_overlay_identity_precision: **PASS**
- owner_identity_privacy: **PASS**

## Identity precision

- Fresh known-pair DOB_POSITION comparisons: **1243**
- Fresh known-pair conflicts: **0**
- Accepted overlay pairs: **76**
- Quarantined overlay proposals: **2**

A mid-week NFL trade can create a conservative team-field false STOP in the rostered overlay precision check; that risk was frozen in the protocol before roster parsing.

## Next stage

STOP is final for this adopted bridge on this B44 data. Do not add identity rules or alter gates after observing this result.

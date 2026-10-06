# Player Role V2 — B42 V4 12-Team Owner-Blind Parity Audit

- Continuation class: **OUTCOME_BLIND_IDENTITY_SOURCE_AMENDMENT**
- Decision: **SCIENTIFIC_STOP_B42_V4_OWNER_BLIND_ROLE_PARITY_FAILED**
- Team count: **12**
- Minimum team role coverage: **0.9250**
- Maximum team role coverage: **1.0000**
- Coverage range: **0.0750**
- Required per-team coverage: **0.98**
- Maximum allowed coverage range: **0.02**
- Counterfactual assignment comparisons: **22416**
- Counterfactual role changes: **0**
- Fallback roles used: **0**
- Model/tier retuning: **No**
- Production deployed: **No**
- Production change authorized: **No**
- Data-integrity checks: **PASS**
- Supported-position roster name availability: **1.0000**
- Sleeper participant confirmation of stable-mapped eligible players: **1.0000**

## Opaque team parity

| Team | Role-eligible | Data-driven | Eligible pending | Identity-gap unknown-pos | Source disagreement | No current evidence | Pos-label mismatch | Coverage | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| Team01 | 41 | 38 | 3 | 0 | 0 | 5 | 1 | 0.9268 | FAIL |
| Team02 | 40 | 40 | 0 | 0 | 1 | 3 | 1 | 1.0000 | PASS |
| Team03 | 41 | 39 | 2 | 0 | 0 | 2 | 1 | 0.9512 | FAIL |
| Team04 | 41 | 39 | 2 | 1 | 0 | 4 | 2 | 0.9512 | FAIL |
| Team05 | 42 | 40 | 2 | 0 | 0 | 5 | 2 | 0.9524 | FAIL |
| Team06 | 39 | 38 | 1 | 0 | 0 | 7 | 3 | 0.9744 | FAIL |
| Team07 | 40 | 37 | 3 | 0 | 0 | 7 | 1 | 0.9250 | FAIL |
| Team08 | 41 | 41 | 0 | 0 | 0 | 2 | 2 | 1.0000 | PASS |
| Team09 | 43 | 42 | 1 | 1 | 0 | 5 | 2 | 0.9767 | FAIL |
| Team10 | 34 | 33 | 1 | 0 | 0 | 9 | 2 | 0.9706 | FAIL |
| Team11 | 38 | 36 | 2 | 0 | 0 | 4 | 0 | 0.9474 | FAIL |
| Team12 | 44 | 44 | 0 | 0 | 0 | 3 | 2 | 1.0000 | PASS |

## Eligibility and pending diagnostics

- Team01: match_methods={"stable_sleeper_id": 38, "unique_exact_name_denominator_only": 3}; pending_reasons={"stable_id_crosswalk_absent_name_bridge": 3}; source_disagreement=0
- Team02: match_methods={"stable_sleeper_id": 40}; pending_reasons={}; source_disagreement=1
- Team03: match_methods={"stable_sleeper_id": 39, "unique_exact_name_denominator_only": 2}; pending_reasons={"stable_id_crosswalk_absent_name_bridge": 2}; source_disagreement=0
- Team04: match_methods={"sleeper_participation_identity_gap": 1, "stable_sleeper_id": 39, "unique_exact_name_denominator_only": 1}; pending_reasons={"stable_id_crosswalk_absent_name_bridge": 1, "stable_id_crosswalk_missing_gsis_bridge": 1}; source_disagreement=0
- Team05: match_methods={"stable_sleeper_id": 40, "unique_exact_name_denominator_only": 2}; pending_reasons={"stable_id_crosswalk_absent_name_bridge": 2}; source_disagreement=0
- Team06: match_methods={"stable_sleeper_id": 38, "unique_exact_name_denominator_only": 1}; pending_reasons={"stable_id_crosswalk_absent_name_bridge": 1}; source_disagreement=0
- Team07: match_methods={"stable_sleeper_id": 37, "unique_exact_name_denominator_only": 3}; pending_reasons={"stable_id_crosswalk_absent_name_bridge": 3}; source_disagreement=0
- Team08: match_methods={"stable_sleeper_id": 41}; pending_reasons={}; source_disagreement=0
- Team09: match_methods={"sleeper_participation_identity_gap": 1, "stable_sleeper_id": 42}; pending_reasons={"stable_id_crosswalk_missing_gsis_bridge": 1}; source_disagreement=0
- Team10: match_methods={"stable_sleeper_id": 33, "unique_exact_name_denominator_only": 1}; pending_reasons={"stable_id_crosswalk_absent_name_bridge": 1}; source_disagreement=0
- Team11: match_methods={"stable_sleeper_id": 36, "unique_exact_name_denominator_only": 2}; pending_reasons={"stable_id_crosswalk_absent_name_bridge": 2}; source_disagreement=0
- Team12: match_methods={"stable_sleeper_id": 44}; pending_reasons={}; source_disagreement=0

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
- owner_identity_privacy: **PASS**

## Interpretation

Coverage parity is evaluated only among role-eligible players with current-season active evidence. Sleeper participants without a valid GSIS bridge into the 2026 nflverse source are conservatively counted as eligible and uncovered so identity failures cannot improve coverage. These identity-gap players have unknown model position and therefore are tracked separately from per-position eligible counts. Players with no 2026 active evidence are descriptive only. The counterfactual owner/slot check is structural and true by construction; the substantive owner-blind guarantee is the pre-roster shadow freeze and source firewall. Parity otherwise means equal evidence completeness and identical owner-blind rules. It does **not** require teams to have similar role-tier distributions.

B42 V4 intentionally uses no fallback role mapping. No owner-blind fallback rule was frozen in B41A–B41J, and the earlier fantasy starter/bench/taxi/IR fallback concept is incompatible with the owner-blind design. Uncovered players remain pending rather than being rescued post hoc.

The shadow role refresh was frozen before the roster assignment snapshot was semantically parsed. Team labels are opaque; owner identity, real team names, and roster IDs are not emitted.

## Next stage

Scientific stop. Preserve B42 evidence. Any remediation must be newly versioned and frozen before another parity audit; do not post-hoc invent a fallback to rescue this result.

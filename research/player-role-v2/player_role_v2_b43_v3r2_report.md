# Player Role V2 — B43 V3R2 Exact ESPN-ID Source Extension and Stale-Alias Adjudication

- Decision: **SCIENTIFIC_STOP_B43_V3R2_EXACT_ESPN_ID_BRIDGE_FAILED**
- Current owner-blind active eligible GSIS rows: **1398**
- Base stable mappings: **1311 (0.9378)**
- Exact ESPN known-pair comparisons: **382**
- Exact ESPN known-pair conflicts: **0**
- Known-pair DOB agreement (descriptive): **1266/1311**; disagreements **45**
- Sleeper ESPN IDs duplicated across raw supported records: **9** (all fail closed)
- Exact ESPN proposals for previously unmapped current GSIS IDs: **0**
- Accepted supplements: **0**
- Adjudicated stale-alias supersessions: **0**
- Unadjudicated identity conflicts: **0**
- Combined mapping coverage: **0.9378**
- Minimum required combined coverage: **0.9950**
- League roster source used: **No**
- Owner/fantasy-team context used: **No**
- Player-specific exceptions: **0**
- Model/tier retuning: **No**
- Production authorized: **No**

## Gate results

- no_roster_or_owner_context: **PASS**
- minimum_exact_espn_reference_comparisons: **FAIL**
- zero_exact_espn_reference_conflicts: **PASS**
- exact_espn_rule_independently_validated: **FAIL**
- zero_unadjudicated_identity_conflicts: **PASS**
- minimum_base_plus_supplemental_current_eligible_coverage: **FAIL**
- minimum_supplemental_mapping_count: **FAIL**

## Interpretation

B43 V3R2 is a disclosed post-stop identity-source extension. The sole mapping rule requires an exact ESPN ID exposed by both the frozen nflverse identity snapshot and the newly frozen Sleeper map, plus canonical-name and position-family agreement. Any duplicated Sleeper ESPN ID fails closed before filtering, and the frozen birth-date contradiction veto remains a hard safeguard.

A historical stable inverse claim may be superseded only for the current bridge overlay when the old stable GSIS claimant is outside the frozen current-eligible population and the frozen nflverse snapshot shows the old and current GSIS IDs share the same exact nonmissing ESPN ID, canonical name, and position family, with no conflicting nonmissing birth date. The historical crosswalk itself is never rewritten.

No B42/B43 missed-player names, GSIS IDs, Sleeper IDs, or per-player exceptions are encoded in the evaluator. B44 remains the actual post-remediation owner-blind acceptance re-audit under the unchanged 98% minimum-team-coverage and 2-percentage-point range gates.

# Player Role V2 — B43 V4R2 Direct Sleeper GSIS-ID Current-Source Extension

- Decision: **SCIENTIFIC_STOP_B43_V4R2_DIRECT_SLEEPER_GSIS_BRIDGE_FAILED**
- Current owner-blind active eligible GSIS rows: **1398**
- Base stable mappings: **1311 (0.9378)**
- Exact direct-GSIS known-pair comparisons: **297**
- Exact direct-GSIS known-pair conflicts: **0**
- Known-pair DOB agreement (descriptive): **1266/1311**; disagreements **45**
- Sleeper GSIS IDs duplicated across raw player records: **7** (all fail closed)
- Exact direct-GSIS proposals for previously unmapped current GSIS IDs: **0**
- Accepted supplements: **0**
- Historical inverse supersessions: **0**
- Unadjudicated identity conflicts: **0**
- Combined mapping coverage: **0.9378**
- Former population-wide coverage gate (descriptive only): **0.9950**
- Population-wide coverage used as primary gate: **No**
- League roster source used: **No**
- Owner/fantasy-team context used: **No**
- Player-specific exceptions: **0**
- Model/tier retuning: **No**
- Production authorized: **No**

## Gate results

- no_roster_or_owner_context: **PASS**
- minimum_exact_gsis_reference_comparisons: **FAIL**
- zero_exact_gsis_reference_conflicts: **PASS**
- exact_gsis_rule_independently_validated: **FAIL**
- zero_unadjudicated_identity_conflicts: **PASS**
- minimum_supplemental_mapping_count: **FAIL**

## Interpretation

B43 V4R2 is a disclosed prospective objective re-specification made before any V4R1/V4R2 identity result. The sole mapping rule remains unchanged: Sleeper itself must expose the exact frozen current GSIS ID on exactly one raw player record, plus canonical-name and compatible-position agreement. A conflicting nonmissing birth date remains a hard veto, and duplicate direct GSIS claims fail closed before filtering.

A historical stable inverse claim may be superseded only in the current bridge overlay after the direct-GSIS rule independently validates, when the old claimant is outside the frozen current-eligible population and the unique current Sleeper record directly exposes the current GSIS ID with matching name/position plus a positive, nonmissing, exact DOB match to frozen B41I. Missing DOB is not sufficient for supersession. The historical crosswalk is never rewritten, and a claim by another current player is never superseded.

Population-wide B43 coverage is descriptive only and a PASS does not claim 99.5% population coverage. No substitute population threshold is introduced. No B42/B43 missed-player names, GSIS IDs, Sleeper IDs, or per-player exceptions are encoded. B44 remains the actual post-remediation owner-blind acceptance re-audit under the unchanged >=98% per-team and <=2-percentage-point range gates on rostered, role-eligible players.

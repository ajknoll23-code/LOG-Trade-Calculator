# Player Role V2 — B43 V2R1 Owner-Blind Identity Bridge Remediation Feasibility

- Decision: **SCIENTIFIC_STOP_B43_V2R1_OWNER_BLIND_IDENTITY_BRIDGE_FEASIBILITY_FAILED**
- Current owner-blind active eligible GSIS rows: **1398**
- Base stable mappings: **1311 (0.9378)**
- Supplemental accepted mappings: **1**
- Combined mapping coverage: **0.9385**
- Minimum required combined coverage: **0.9950**
- Gating reference comparisons across final eligible rules: **2516**
- Gating reference conflicts across final eligible rules: **0**
- Collision-evidence conflicts across final eligible rules: **0**
- Provisional collision evidence rows: **2**
- Final duplicate-identity collision rows quarantined: **0**
- Accepted-bridge structural conflicts: **0 (asserted invariant)**
- League roster source used: **No**
- Owner/fantasy-team context used: **No**
- Player-specific exceptions: **0**
- Model/tier retuning: **No**
- Production authorized: **No**

## Rule validation

Lower-priority gate trials mask nflverse birth date. DOB-informed lower-rule trials are descriptive only. Reference-comparison totals are rule-level trials and may overlap the same known rows across rules.

| Rule | Gating comparisons | Gating conflicts | Gating precision | Collision conflicts | DOB-informed comparisons (descriptive) | DOB-informed conflicts | Final eligible | Accepted supplements |
|---|---:|---:|---:|---:|---:|---:|:---:|---:|
| DOB_POSITION | 1243 | 0 | 1.000000 | 2 | 1243 | 0 | NO | 0 |
| NFL_TEAM_POSITION | 1239 | 0 | 1.000000 | 0 | 1197 | 0 | YES | 1 |
| UNIQUE_NAME_POSITION | 1277 | 0 | 1.000000 | 0 | 1241 | 0 | YES | 0 |

## Gate results

- no_roster_or_owner_context: **PASS**
- minimum_total_reference_comparisons_across_eligible_rules: **PASS**
- zero_reference_and_collision_conflicts_among_applied_rules: **PASS**
- every_applied_rule_independently_validated: **PASS**
- minimum_base_plus_supplemental_current_eligible_coverage: **FAIL**
- minimum_supplemental_mapping_count: **PASS**

## Interpretation

B43 V2R1 is a disclosed post-V1 re-analysis on frozen data. It preserves the V1 application matcher and DOB contradiction veto. For gate validation, NFL_TEAM_POSITION and UNIQUE_NAME_POSITION are evaluated with birth date masked so they must stand on name/position/team information without hidden DOB disambiguation. The corresponding DOB-informed results are reported only descriptively.

Collision evidence is not discarded. A stable-map or supplemental Sleeper-ID collision is classified as duplicate identity only when every other claimant is present in frozen B41I with the same canonical name, same nonmissing birth date, and same position family. Otherwise the collision counts as a conflict against the rule that produced the proposal and makes that rule ineligible. All collision proposals remain quarantined from the bridge.

The accepted bridge's one-to-one/stable-map safety is enforced as a structural assertion rather than presented as a primary scientific gate. No individual B42- or B43-V1-missed player, Sleeper ID, or exception is hard-coded.

If B43 V2R1 passes, the exact frozen bridge is eligible only for a separately preregistered B44 owner-blind post-remediation acceptance re-audit under the original B42 98% minimum-team-coverage and 2-percentage-point range gates.

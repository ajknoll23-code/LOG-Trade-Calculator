# Identity V2 Phase 4 — Position-Conflict Policy Audit

**Decision:** `PASS_EXPLICIT_EVIDENCE_BACKED_POSITION_OVERRIDE_CANDIDATE`

**RESEARCH ONLY. No production mapping or resolver policy is changed.**

## Why this phase exists

The production resolver already preserves an existing authoritative FPID↔Sleeper-ID pair across later position changes. The unresolved question is how to handle a **brand-new** match when the two providers disagree on position.

## Current strict-policy population

- Fresh rows failing only at position compatibility: **5**

## P1 — Generic exact-name + exact-team override

**Diagnostic only; cannot be promoted by this phase.**

- Would create new candidates: **5**
- Extra FPIDs beyond the evidence-backed explicit set: **2**

- Extra FPIDs: `24562`, `26157`

## P2 — Evidence-backed explicit override

- Frozen targets: **3**
- Qualified targets: **3**
- All hard gates pass: **True**

| Player | FPID | FP pos | Team | Phase 3 evidence | Candidate SID | Sleeper positions |
|---|---|---|---|---|---|---|
| Austin Booker | `26313` | LB | CHI | `OFFICIAL_POSITION_SUPPORTS_SLEEPER_TAXONOMY` | 11760 | DL |
| Gabe Jacas | `27959` | LB | NE | `OFFICIAL_POSITION_SUPPORTS_FANTASYPROS_TAXONOMY` | 13457 | DL |
| Kendal Daniels | `28290` | DB | ATL | `OFFICIAL_POSITION_SUPPORTS_SLEEPER_TAXONOMY` | 13482 | LB |

### Hard gates

- `three_targets_have_exact_unique_name_team_candidate`: **PASS**
- `explicit_target_sids_unique`: **PASS**
- `no_existing_authoritative_sid_collision`: **PASS**
- `explicit_arm_exactly_three_fpids`: **PASS**
- `jonah_elliss_remains_outside_explicit_arm`: **PASS**
- `zero_unrelated_explicit_changes`: **PASS**

## Ambiguous taxonomy hold

- **Jonah Elliss** (`26157`): LB vs Sleeper candidate positions ['DL']; Phase 3 = `OFFICIAL_POSITION_TAXONOMY_REMAINS_AMBIGUOUS`. Remains held.

## Governance

- The generic rule is diagnostic only.
- The explicit candidate is limited to the three frozen evidence-backed FPIDs.
- Jonah Elliss remains held because the official OLB label is hybrid/ambiguous under the frozen policy.
- No resolver source file or production crosswalk is changed.
- Even a PASS only permits a separate production-candidate shadow.

## Next-step rule

A PASS authorizes only a separate production-candidate shadow that applies the three explicit mappings, re-runs the unified resolver/regression suite, and proves zero unrelated changes. It does not authorize deployment.

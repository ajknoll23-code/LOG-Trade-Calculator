# Identity V2 Phase 2 — Manual Adjudication Preregistration

**Status:** `FROZEN_MANUAL_ADJUDICATION_POLICY`

Scope is the exact **17** manual-review rows frozen by Identity V2 Phase 1.

A row can become research-authoritative here only from deterministic
corroboration already present in the repository:

1. exactly one current position-compatible Sleeper candidate **and**
   exact current team corroboration; or
2. the exact same FPID↔SID pair is already authoritative in the deployed
   production crosswalk and current positions remain compatible.

Name alone never qualifies. Missing/free-agent team state does not count
as corroboration. Position conflicts remain holds. If a frozen Phase 1
FantasyPros row has disappeared from the current normalized source, it is
frozen as `HOLD_SOURCE_ROW_DISAPPEARED`; disappearance is never treated as
evidence for an identity match.

This phase writes research artifacts only. It cannot change or promote
`scripts/identity_crosswalk.json`.

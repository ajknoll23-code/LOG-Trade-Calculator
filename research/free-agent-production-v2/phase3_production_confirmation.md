# Free-Agent Production V2 — Phase 3 Production Confirmation

**Decision:** `PASS_FA_PROD_V2_PHASE3_CONFIRMED_AND_DEPLOYED`

Free-Agent Production V2 is now deployed.

- Approved candidate overrides deployed: **333**
- Unresolved active FA-specific rows held at legacy values: **31**
- Kickers changed: **0**
- Canonical `PROD_MULT_DATA` changed: **No**
- Role/age/team/identity logic changed: **No**
- Current-snapshot transported shadow reproduced exactly for every rendered FA: **Yes**
- Full free-agent parity validation: **PASS**
- Full repository regression suite after deployment: **PASS**

## Carried-forward Phase 2 movement

- Candidate rows with changed FV: **298**
- Increased FV: **275**
- Decreased FV: **23**
- Active-cohort rank Spearman: **0.8633**
- Top-25 overlap: **68.0%**
- Top-50 overlap: **66.0%**
- Top-100 overlap: **76.0%**

## Deployment architecture

The historical `FA_PROD_MULT_DATA` object remains intact as the legacy baseline.
A generated `FA_PROD_MULT_V2_RELEASE` block overrides production multipliers for
exactly the 333 Phase 1 candidates validated in Phase 2. The 31 unresolved active
rows remain on their historical values. This makes the deployment deterministic,
auditable, reversible, and checkable with
`scripts/model/apply_free_agent_production_v2_release.py --check`.

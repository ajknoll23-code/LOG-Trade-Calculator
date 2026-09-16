# Draft Pick FV V3 — Formal Closure

**Status:** `CLOSED_PRE_OUTCOME`
**Decision:** `STOP_V3_SOURCE_SCOPE_CONTAMINATION_CLEAN_SUBSET_INSUFFICIENT`

V3 is closed before historical player-outcome ingestion, candidate fitting, validation scoring,
or any production change.

## Why V3 stopped

The frozen source catalog contained **41** leagues with positive
evidence of rookie-scope contamination. Removing those leagues left **172**
clean leagues from the original **213**.

The clean subset failed the original frozen pooled gates:

| Gate | Clean value | Frozen requirement | Result |
|---|---:|---:|---|
| R1–R4 nonmock total | 172 | ≥ 180 | FAIL |
| R5 non-IDP total | 52 | ≥ 60 | FAIL |
| R6 non-IDP total | 21 | ≥ 36 | FAIL |
| R6 minimum per year | 2 | ≥ 3 | FAIL |
| R6 effective years | 5.3133 | ≥ 4.5 | PASS |
| R6 max year share | 0.2381 | ≤ 0.30 | PASS |
| IDP R6 total | 16 | ≥ 20 | FAIL |
| IDP R6 years represented | 6 | ≥ 5 | PASS |

## Scientific meaning

This is a **source-feasibility stop**, not evidence that a new draft-pick valuation curve would
succeed or fail. V3 never read historical player outcomes and never scored the candidate models.

No V3 threshold is lowered, no contaminated league is retained to rescue a gate, and the frozen V3
catalog is not rewritten after the result.

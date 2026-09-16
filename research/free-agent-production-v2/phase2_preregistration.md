# Free-Agent Production V2 — Phase 2 Shadow Validation Preregistration

**Status:** `FROZEN_PRE_SHADOW_EVALUATION`

Phase 2 is research-only. It cannot mutate `FA_PROD_MULT_DATA`, `PROD_MULT_DATA`,
`index.html`, `free-agent-board.html`, roles, age curves, position weights, or any
other production valuation logic.

The shadow candidate is exactly the frozen Phase 1 `candidate_prod` population.
Any active Phase 1 row without a candidate remains on its deployed FA production
multiplier. Kickers remain out of scope.

The real free-agent-board JavaScript valuation engine is executed twice: once
unchanged and once with in-memory production-multiplier overrides for the frozen
candidate cohort. Only `prod` may change.

Phase 2 PASS is based on structural safety and isolation: exact frozen lineage,
exact active identity, exact override application, no spillover to unresolved or
non-candidate rows, unchanged metadata/source precedence, finite values, monotonic
FV response, parity/roster safety, repository regressions, and a zero-production-
mutation firewall.

Value magnitude, rank movement, top-N overlap, and positional movement are reported
as diagnostics. They are intentionally not retrofitted into pass/fail thresholds
after Phase 1 already revealed that the candidate is materially different.

A PASS does **not** authorize deployment. It permits only a separate guarded
production-confirmation step.

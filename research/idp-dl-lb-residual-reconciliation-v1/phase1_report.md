# IDP DL/LB Residual Reconciliation V1 — Phase 1

**Decision:** `FREEZE_DL_LINEAGE_RESIDUAL_RESET_C0_FOR_PROSPECTIVE_VALIDATION`

## Residual distributions

- Migrated LB→DL median residual: **+0.1922** (n=21)
- Native DL median residual: **-0.0363** (n=99)
- Native LB median residual: **+0.0061** (n=94)
- Cliff's delta vs native DL: **+0.927**; permutation p = **0.000020**
- Cliff's delta vs native LB: **+0.992**; permutation p = **0.000020**
- Migrated residuals above native DL p95: **20/21**
- Migrated residuals above native LB p95: **20/21**

## Structural reset candidate

- Brian Burns: **7441 → 6007**
- Cohort median FV delta: **-983**
- Cohort mean FV delta: **-945.6**

The reset candidate removes only the legacy-LB residual. It does not change the current-DL clean model, age logic, position weight, replacement rank, or later successor overlay.

No production change is authorized in this phase.


# IDP Position Lineage V1 — Phase 3 Production Confirmation

**Decision:** `PASS_IDP_POSITION_LINEAGE_V1_PHASE3_CONFIRMED_AND_DEPLOYED`

IDP Position Lineage V1 is deployed.

- Approved raw `PROD_MULT_DATA` changes: **24**
- Explicit holds: **3**
- Non-cohort production changes: **0**
- Offense production changes: **0**
- Current-snapshot shadow reproduced exactly: **Yes**
- Free-agent canonical mirror synchronized: **Yes**
- Free-agent full parity/source-precedence validation: **PASS**
- Free-Agent Production V2 board-specific mechanism preserved: **Yes**
- Post-deployment repository regression suite: **PASS**

## Carried-forward Phase 2B evidence

- Phase 2B decision: `PASS_IDP_POSITION_LINEAGE_V1_PHASE2B_AGE_FEEDBACK_SHADOW`
- Median total FV delta: **+1127.0**
- Median direct production effect: **+1104.0**
- Median age-feedback effect: **+0.0**
- Median age-feedback share: **0.0%**

## Deployment architecture

The scientific deployment modifies only the 24 approved existing keys
inside `PROD_MULT_DATA` in `index.html`. The repository-owned canonical
synchronizer then mirrors that updated valuation engine into
`free-agent-board.html` while preserving all board-specific/free-agent
production regions. It does not alter positions, ages, roles, position
weights, age curves, no-history lineage, Team Utility, offense values,
or Free-Agent Production V2 logic.

The deterministic applicator/checker is:
`scripts/model/apply_idp_position_lineage_v1_release.py`.

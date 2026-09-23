# Draft Pick FV V6.1 — Phase 3.1 DOB Repair Protocol

**Decision:** `FREEZE_V6_1_PHASE3_1_DOB_REPAIR_PROTOCOL_EXECUTION_AUTHORIZED`

This is a post-harvest, pre-fit metadata repair. The rule is frozen before the new Sleeper DOB source is queried.

- Apply to every missing-DOB target in the complete 2018–2023 development corpus.
- Join only by the already-frozen Sleeper ID.
- Never overwrite an existing DOB.
- No manual, name, or position matching.
- No alternate-source chasing.
- Keep the original 95% readiness threshold.
- Recompute only age-dependent O2 fields; preserve O1 and football-production data.
- If the same gate still fails, stop before fitting.

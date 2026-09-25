# Draft Pick FV V7 — Phase 2 Targeted R25 Recovery

**Decision:** `FREEZE_V7_PHASE2_TARGETED_R25_RECOVERY_AUTHORIZED`

Execution-only recovery after harvesting every completed shard checkpoint.

- 6,203 frozen candidates / 251 frozen R25 batches.
- 199 batches already validated and will not be rerun.
- Exactly 52 missing batches are authorized for recovery.
- One R25 batch per matrix job; maximum three concurrent jobs.
- No source search, substitution, outcome access, fit/scoring, market/vote read, or production change.

Missing by year:
- 2018: 0, 3, 5, 6, 7, 13, 14, 15, 16, 17, 24, 25, 26, 27, 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42
- 2019: 0, 1, 2, 3, 4, 15, 16, 17, 18, 19, 24, 25, 26, 27, 28, 29, 37, 38, 39
- 2020: 12, 13, 14, 34, 39
- 2021: 28, 29, 34
- 2022: none
- 2023: none


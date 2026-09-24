# Draft Pick FV V7 - Phase 2 R25 Probe Repartition Recovery

**Decision:** `FREEZE_V7_PHASE2_PROBE_REPARTITION_RECOVERY_RERUN_AUTHORIZED`

Execution-only recovery after the checkpointed run completed all six discovery checkpoints but was cancelled during probing.

- Reuse the six discovery JSON files from run `36036888017` byte-for-byte; do not call `leagueSearch` again.
- Candidate membership and deterministic order remain unchanged: 6,203 total candidates.
- Repartition only the probe execution from 40 candidates per batch to 25.
- Run at most two probe jobs concurrently.
- Preserve the existing 5-second MFL throttle, redirect handling, retry schedule, and 429 cooldowns unchanged.
- Prove exact-once coverage against each frozen discovery order before any year aggregation.
- Preserve the exact prior identity snapshot and all pre-outcome firewalls.
- No 2024 search, outcome ingestion, candidate fitting, market/vote data, or production change is authorized.

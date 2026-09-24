# Draft Pick FV V7 - Phase 2 Checkpoint Recovery

**Decision:** `FREEZE_V7_PHASE2_CHECKPOINT_RECOVERY_RERUN_AUTHORIZED`

This is an execution-partition recovery only. It changes no scientific, source-selection, identity, gate, holdout, or candidate rule.

- Freeze each year candidate union before probing.
- Probe the exact deterministic order in non-overlapping batches of 40.
- A candidate appears in exactly one batch.
- Year aggregation proves the batch concatenation exactly equals the frozen discovery order.
- No early stopping, substitution, or membership change is permitted.
- The existing transport recovery and exact run-1 identity snapshot remain unchanged.

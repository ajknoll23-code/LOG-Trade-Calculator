# Draft Pick FV V7 - Phase 2 Transport Recovery

**Decision:** `FREEZE_V7_PHASE2_TRANSPORT_RECOVERY_RERUN_AUTHORIZED`

This is a transport-only recovery after run #1 hit MFL redirect/rate-limit and shard timeout failures. It changes no search union, source qualification rule, identity priority, gate, candidate family, outcome firewall, or holdout policy.

- Rehydrate the exact run-1 pre-search identity assets by SHA-256.
- Pace MFL requests at least 5 seconds apart.
- Disable automatic redirect chains and follow at most four redirects manually.
- Cool down 5-15 minutes on HTTP 429.
- Probe draftResults before league metadata to discard incomplete <72-pick candidates with fewer requests.
- Exhausted transport retries remain fatal; no candidate is silently skipped.

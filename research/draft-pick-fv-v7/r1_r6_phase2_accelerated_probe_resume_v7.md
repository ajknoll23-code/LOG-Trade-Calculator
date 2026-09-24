# Draft Pick FV V7 - Phase 2 Accelerated Probe Resume

**Decision:** `FREEZE_V7_PHASE2_ACCELERATED_PROBE_RESUME_AUTHORIZED`

Execution-only acceleration after live R25 batches proved correct but too slow.

- Reuse every already-green R25 probe checkpoint only after exact revalidation against the frozen discovery slice.
- Keep the exact 6,203-candidate universe, deterministic order, and 25-candidate R25 partition.
- Group up to five missing R25 batches into one runner job to remove repeated checkout/setup overhead.
- Run at most three probe jobs concurrently.
- Preserve the five-second minimum between request starts; retries, redirect handling, 429 cooldowns, and request timeouts remain unchanged.
- No leagueSearch, source substitution, identity change, 2024 search, outcome ingestion, fit/scoring, market/vote read, or production promotion is authorized.

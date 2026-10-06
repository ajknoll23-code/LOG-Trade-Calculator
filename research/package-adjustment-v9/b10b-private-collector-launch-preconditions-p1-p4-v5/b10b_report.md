# Package Adjustment V9 — B10B Private Collector Launch Preconditions P1–P4

**Decision:** `PASS_B10B_P1_TO_P4_PRIVATE_COLLECTOR_VERIFIED`

- P1 live browser parity/hash verification: `True`
- P2 private collector persistence confirmed by sentinel-only endpoint: `True`
- P3 KTC isolation guard: `True`
- P4 sentinel absent through >=96 successful public KTC CSV observations spanning >=24 minutes; private destination blocked through both export and gviz anonymous-read paths: `True`

**No real voter slot was used. Only invalid slot 0 / `pkgv9val_LAUNCHTEST` was submitted.**

Real voter URLs remain unauthorized until P5 and P6 are completed and committed.

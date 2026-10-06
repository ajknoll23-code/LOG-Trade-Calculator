# Package Adjustment V9 — B10F UX Latency Preview Amendment V1

## Decision

**PASS_B10F_PROSPECTIVE_PRESENTATION_ONLY_LATENCY_AMENDMENT**

The only feedback used was operational UX feedback after slot 1: post-click waiting was reported at roughly 5–20 seconds. No human A/B choices were inspected.

Beginning prospectively after this commit, the browser shows the next already-frozen assigned trade while the unchanged B9 POST is still in flight. Both next-trade buttons remain disabled until the original submission resolves.

The exact B9 transport block remains byte-for-byte frozen at `9750dc02cdc3b65874a48211d3e7c86c5f6bd9b401855775254ef0c3cc0d5dca`. Assignments, left/right randomization, payloads, timestamps, pending-state logic, failure policy, and the primary analysis are unchanged.

Slot 1 is the sole pre-amendment completed slot. Before outcomes are opened, this amendment preregisters one final robustness check: repeat the frozen analysis excluding slot 1 and report whether any inferential conclusion changes.

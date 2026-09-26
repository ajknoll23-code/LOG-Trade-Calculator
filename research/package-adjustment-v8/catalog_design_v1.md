# Package Adjustment V8 — Phase 1B Catalog Design Freeze

**Decision:** `PASS`

## Why raw top share was rejected for unequal-size catalog stratification

- 2-player minimum top share: **0.5000**
- Maximum 4-player top share under the FV>=2500 floor: **0.5364**
- Maximum reverse raw-top-share gap: **0.0364**
- Moderate band begins at **0.0500**, so reverse 2v4 moderate/high cells are structurally impossible without low-value filler.

## Frozen replacement metric

`apex_excess_share = top_asset_share - 1 / asset_count`

This leaves 2v2, 3v3, and 4v4 contrast exactly unchanged while making 2v3, 2v4, and 3v4 concentration comparable across side sizes.

## Feasibility

- 2-player side pool: **1545**
- 3-player side pool: **2422**
- 4-player side pool: **2470**
- Weakest required design cell: **>=500 candidate pairs** (count capped at 500).
- Every required cell passes the high-value realism rules.

Power plan remains 44 voters / 44 per challenge, hard cap 50.
No catalog or V8 vote was read/generated.

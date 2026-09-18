# Package Adjustment V3 — Phase 2 Candidate Family

**Decision:** `PASS_V3_PHASE2_FAMILY_FROZEN_FOR_FRESH_CONFIRMATION`

**Research only. Production V1.6 is unchanged.**

## Frozen family for fresh confirmation

| Candidate | Gamma | KTC side direction | KTC dev MAE | Hard invariants | Fresh confirmation? |
|---|---:|---:|---:|---:|---:|
| `power-g1.85-control` | 1.85 | 4/5 | 566.9 | PASS | NO |
| `power-g2.01` | 2.01 | 5/5 | 565.3 | PASS | YES |
| `power-g2.15` | 2.15 | 5/5 | 1245.5 | PASS | YES |
| `power-g2.30` | 2.30 | 5/5 | 1761.0 | PASS | YES |

Development reference: **`power-g2.01`**.

That label does **not** authorize deployment. It only identifies the closest KTC-development anchor among the mathematically valid candidates.

## Stress coverage

- Player assets: **565**
- Pick variants: **72**
- Deterministic cases per eligible candidate: **2000**
- Shapes: 1v2, 1v3, 2v2, 2v3, 3v3, 3v4, 4v6, 5v6, 6v6, 1v10
- Picks are first-class positive-value assets; no player-only gate.
- Multi-vs-multi is supported by construction.
- 1v1 remains quiet with zero package adjustment.

## Hard invariants

Every eligible candidate passed:

- side-swap symmetry;
- asset-order invariance;
- positive-value monotonicity;
- scale equivariance;
- equal-total fragmentation penalty;
- tiny-piece continuity;
- finite/nonnegative display adjustment;
- player/pick mixed-package support;
- all frozen package topologies.

## Historical-trade diagnostic

- Current-state values resolvable for **6/8** real trade anchors.
- These outputs are diagnostic only; accepted historical trades are not assumed fair.

## Next

Phase 3 should freeze a fresh human-vote catalog specifically designed to distinguish the three eligible gamma curves. No old votes may be reused.

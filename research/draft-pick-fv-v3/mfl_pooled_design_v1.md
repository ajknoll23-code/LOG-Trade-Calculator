# Draft Pick FV V3 — MFL Pooled Design Freeze

**Decision:** `ACCEPT_MFL_YEAR_BALANCED_POOLED_R1_R6_DESIGN`

## Scientific status

- The earlier MFL per-year feasibility result remains `DISCOVERY_INCONCLUSIVE_OR_INSUFFICIENT`.
- The 2018 R1-R4 boundary remains a formal 24/25 transport-limited near-pass, not a retroactive pass.
- This document defines a new pooled estimator design before any player-outcome ingestion.
- No historical player outcomes, KTC/market values, package votes, candidate scores, or model fits were read.

## Frozen pooled evidence after excluding obvious mocks

- R1-R4 non-mock complete drafts: **213**
- R5 non-IDP non-mock complete drafts: **81**
- R6 non-IDP non-mock complete drafts: **44**
- R6 non-IDP minimum in any year: **3**
- R6 non-IDP maximum year share: **0.250**
- R6 non-IDP effective years (HHI): **5.042**
- R6 IDP non-mock complete drafts: **25**

## Frozen estimator rule

If accepted, R5-R6 are not estimated as six independent yearly curves. They use year-balanced pooled evidence with smoothing/shrinkage across adjacent slots and years.

Obvious mocks are excluded using the already-frozen diagnostic flag. IDP drafts are not mixed into the primary non-IDP curve.

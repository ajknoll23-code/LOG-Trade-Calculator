# Package Adjustment V4 — Phase 1 Structural Preregistration

**Status:** `FROZEN_BEFORE_SPENT_EVIDENCE_DEVELOPMENT`

V4 is a new research cycle. Production remains
`v1.6-v5-size2-composition-overlay`.

## New structural hypothesis

V4 does **not** continue the V3 gamma search.

Each side is sorted by FV. The best asset receives an explicit
elite-anchor premium that grows with `v1 / 10000`; the second piece is
discounted; third-and-later pieces receive a stronger fragmentation
discount.

The frozen candidate grid has **24 discrete configurations** covering
three stud strengths, three second-piece discounts, and three third-plus
discounts under `third_plus_discount >= second_piece_discount`.

## Asset eligibility

V4 generated trades use currently rostered, positive-FV
QB/RB/WR/TE/DL/LB/DB assets. **Joe Mixon is explicitly excluded** and
retired players are not eligible for V4 challenge generation.

Draft picks are limited to **2027 and 2028, rounds 1-4,
early/mid/late**. **2029 and later picks are prohibited** from V4
development and fresh-confirmation catalogs.

## Development

Only after this preregistration is committed may the spent V3 exact-600
ballots be read for V4 development. They are development evidence only.

Phase 2 compares raw addition, the frozen V3 `g2.15` reference, and all
invariant-passing V4 candidates with five-fold voter-grouped held-out
log loss. No continuous optimization and no gamma parameter are allowed.

A candidate must beat both raw addition and the V3 reference, improve in
at least 3/5 folds versus raw, and avoid >0.02 topology×asset-mix
regression. At most two near-tied candidates may be frozen.

## Fresh confirmation

Any nominated V4 candidate still requires completely fresh human votes.
The fresh catalog will contain 24 cells spanning six topologies, two
asset mixes, and both targeted-disagreement and broad-balanced strata.

The V3 600 votes and the older 900-vote study cannot count toward V4
confirmation.

Final deployment gates remain strict: >=0.005 held-out log-loss
improvement versus raw, >=0.90 challenge-cluster bootstrap favorable
fraction, <=0.03 maximum topology×asset-mix regression, and full 24-cell
coverage.

This phase does not read human outcomes, fit a model, select a candidate,
or alter production.

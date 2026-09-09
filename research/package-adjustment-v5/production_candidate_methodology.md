# Package Adjustment V5 — Production Candidate Methodology

**Status: SHADOW DESIGN ONLY. No live consumer is changed.**

## Design choice

The candidate preserves the exact controlled-live V1.5 target-sensitive two-player curve and treats V5 as a composition overlay rather than a replacement model.

The frozen V3 composition core remains untouched. Hardened V5 evidence supports expansion review through the 55/45 and 60/40 bands, while 65/35 fails the hardening rule. Therefore the candidate supports no composition more imbalanced than 60/40.

## Composition factor

The hardened V5 normalized 50% crossing is interpreted as a multiplicative factor on the existing V1.5 size-2 threshold:

`candidate multiplier = live V1.5 size-2 multiplier(target FV) × composition factor`

The factor is anchored at:
- frozen V3 upper composition boundary: 1.000x;
- 55/45 hardened normalized point;
- 60/40 hardened normalized point, floored at 1.000x.

Piecewise-linear interpolation is used between these anchors to avoid discontinuous trade verdicts. This interpolation is candidate engineering, not a new research finding. It bridges only the small interior spacing between evidence-supported bands and does not extend beyond the nominal 60/40 boundary.

## Conservative floor

The 60/40 hardened normalized point is slightly below 1.0. This study was designed to determine whether composition justifies expansion of the existing Package Adjustment, not to reduce the already-controlled-live V1.5 consolidation premium. The candidate therefore floors every V5 composition factor at 1.0.

## Production invariants

The candidate design does not alter Fundamental Value, Market Value, draft-pick values, Team Utility, or size-3 V4 Package Adjustment. Picks, multi-v-multi trades, 4+ meaningful package players, unsupported positions, and package pieces at or above target FV remain fail-closed exactly as before.

## Promotion policy

Candidate definition is not production approval. A separate shadow implementation must reproduce exact V1.5 behavior inside the existing V3 core, apply the new overlay only in the V5 review-supported region, and pass adversarial boundary/regression tests before a human-reviewed promotion decision.

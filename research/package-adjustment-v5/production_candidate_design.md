# Package Adjustment V5 — Production Candidate Design

**SHADOW CANDIDATE ONLY — controlled-live V1.5 is unchanged.**

- Candidate: `package-adjustment-v5-size2-composition-overlay-candidate-v1`
- Frozen evidence: `600` votes / `30` voters
- Evidence fingerprint: `1ca34ccc57c42b77350905f711d79b63a40e63530691c985a1fbade8108daecc`
- Expansion review ceiling: **60/40**
- 65/35 and more imbalanced packages: **unsupported / fail closed**

## Candidate formula

The exact V1.5 target-sensitive size-2 multiplier remains the baseline.
A composition factor is layered on top only outside the existing frozen V3 core:

- Existing V3 core through largest-share `0.523028`: factor **1.000x**
- 55/45 anchor: factor **1.133281x**
- 60/40 anchor: factor **1.000000x**
- Between anchors: piecewise-linear interpolation.
- The factor is floored at 1.000x, so V5 cannot reduce the existing V1.5 premium.
- Above 60/40: fail closed.

## Why this candidate

- 55/45 and 60/40 both survived voter-cluster and target-cluster hardening.
- 65/35 failed hardened expansion review, so the candidate stops before it.
- The frozen V3 core is not recalibrated from the V5 50/50 validation band.
- Narrow interior coverage gaps are bridged only by interpolation; no extrapolation is allowed beyond 60/40.

## 56/44 reference case

- Largest share: `56.0383%`
- Raw package/target ratio: `1.257x`
- Live V1.5 target multiplier: `1.569x`
- V5 composition factor: `1.106x`
- Shadow candidate multiplier: `1.735x`
- Shadow trade-equivalent target FV: `10,229`

## Next gate

This file does **not** implement the formula. The next step is a separate shadow regression/adversarial hardening pass against exact production semantics and boundary cases before any human-reviewed live promotion.

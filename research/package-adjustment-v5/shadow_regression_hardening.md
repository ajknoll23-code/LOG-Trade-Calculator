# Package Adjustment V5 — Shadow Regression Hardening

**SHADOW ONLY — controlled-live V1.5 is unchanged.**

- Candidate: `package-adjustment-v5-size2-composition-overlay-candidate-v1`
- Frozen evidence: `600` votes
- Candidate spec SHA-256: `f09ff5c777960c3a805dfaa83b10606f0cc325b7d8f518d3bafcdb7db9be928e`
- Adversarial cases passed: `25`
- Dense numeric sweep cases: `48048`
- Existing V1.5 applied cases changed: `0`
- Illegal new support cases: `0`
- New support above 60/40: `0`
- Candidate factors below 1.0: `0`

## Candidate shape

- Factor floor: `1.000000x`
- Factor peak: `1.133276x` at largest share `0.5500`
- Factor at 60/40: `1.000000x`
- Threshold largest-piece maximum: `0.988517x` target FV
- Shape is intentionally single-peaked at 55/45 and returns to the existing live baseline at 60/40.

## Scope regression

- Frozen V3 core behavior is byte/semantics protected.
- Frozen V4 3-player behavior is unchanged.
- Tiny sub-6% throw-ins stay excluded from composition classification but retain full raw FV.
- Package pieces at or above target FV remain unsupported.
- Picks, K, multi-v-multi, and 4+ meaningful-player packages remain fail closed.
- No candidate support exists above 60/40.

## 56/44 motivating case

- Candidate factor: `1.106x`
- Candidate multiplier: `1.735x`
- Trade-equivalent target FV: `10,229`
- Raw verdict: `package` side
- Shadow candidate verdict: `target` side

## Result

**Shadow regression passed. Candidate is ready for human promotion review, not automatic production promotion.**

No production formula or consumer was modified by this hardening pass.

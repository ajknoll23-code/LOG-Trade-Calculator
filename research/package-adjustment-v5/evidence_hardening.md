# Package Adjustment V5 — Evidence Hardening

**RESEARCH ONLY — production V1.5 remains unchanged.**

- Generated: `2026-09-09T23:17:39.802899+00:00`
- Frozen counted votes: `600`
- Unique voters: `30`
- Evidence fingerprint: `1ca34ccc57c42b77350905f711d79b63a40e63530691c985a1fbade8108daecc`
- Expansion ceiling supported for review: `60/40`

## Why this hardening exists

The mature V5 raw-ratio fit is necessary but not sufficient for a production candidate. This pass re-expresses each ballot relative to the exact controlled-live V1.5 target-sensitive two-player curve, then checks sensitivity to both voters and target selection.

## Composition robustness

| Band | Raw fit stable | Live-V3 normalized factor | Voter bootstrap bracketed | Target bootstrap bracketed | Expansion review support |
|---:|---:|---:|---:|---:|---:|
| 50/50 | False | 1.043x | 89.6% | 88.6% | False |
| 55/45 | True | 1.133x | 100.0% | 100.0% | True |
| 60/40 | True | 0.999x | 99.6% | 99.4% | True |
| 65/35 | False | unbracketed | 67.2% | 61.0% | False |
| 70/30 | False | 0.894x | 91.6% | 81.4% | False |
| 75/25 | False | 0.928x | 98.6% | 91.4% | False |

## Catalog composition coverage

| Band | Actual largest-share min | Actual largest-share max | Gap from prior max |
|---:|---:|---:|---:|
| 50/50 | 0.500 | 0.523 | 0.000 |
| 55/45 | 0.525 | 0.568 | 0.002 |
| 60/40 | 0.577 | 0.622 | 0.008 |
| 65/35 | 0.629 | 0.674 | 0.007 |
| 70/30 | 0.675 | 0.725 | 0.001 |
| 75/25 | 0.727 | 0.772 | 0.002 |

## Guardrails

- No production formula is changed by this hardening pass.
- No Fundamental Value, Market Value, draft-pick value, or Team Utility consumer changes.
- No extrapolation beyond tested V5 evidence.
- 50/50 remains the frozen V3 production anchor; V5 50/50 is a validation view, not an automatic replacement.
- Expansion support must be contiguous from 55/45 outward; the analysis never jumps over a failed band.
- A separate production-candidate design and human review are required before any live change.

# Package Adjustment — Exact-Live Prospective/OOS Monitor (V1.5)

Generated: 2026-09-10T03:15:14.472598+00:00

## Release

- Release ID: **package-adjustment-exact-live-v1.5-step6-realignment**
- OOS cutoff: **2026-09-09T03:08:16.458000+00:00**
- Production revision at release: **v1.5-audit-step6-scope-ui-idp**
- Exact-live formula SHA256: `209bc5bcf75b67d0ae4feeb811bf3b763e13395005fb859d61439fc84004337b`

Only trades strictly after the release cutoff can enter the OOS sample.
The evaluator uses the exact live V3 size2 curve, V3 51/49 composition
envelope, V4 size3 multiplier, V4 45/33/22 composition envelope,
meaningful-piece threshold, tiny-padding behavior, and fail-closed scope.

## Current evidence

- Logged trades classified: **15**
- Supported exact-live OOS trades: **0**
- Distinct concentrated targets: **0**
- Size2 OOS trades: **0**
- Size3 OOS trades: **0**
- Evidence stream age: **7.86 hours**

## Evidence maturity gates

- Supported trades >= 10: **False**
- Distinct targets >= 6: **False**
- Size2 trades >= 3: **False**
- Size3 trades >= 3: **False**
- All maturity gates passed: **False**

These gates only indicate that enough prospective evidence exists for
another human review. They do **not** authorize an automatic formula change.

## Audit state

Exact-live monitoring is revision-aligned to production V1.5 and its release manifest is frozen.
Step 6 is complete. The next audit gate is **Step 7 — Permanent Package Adjustment repo regression suite**.

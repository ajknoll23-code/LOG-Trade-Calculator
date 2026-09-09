# Package Adjustment Step 4 — Exact-Live Prospective/OOS Monitor

Generated: 2026-09-09T00:32:10.133746+00:00

## Release

- Release ID: **package-adjustment-exact-live-v1.4-step4**
- OOS cutoff: **2026-09-09T00:32:10.136000+00:00**
- Production revision at release: **v1.4-audit-step4-exact-live-oos-monitoring**
- Exact-live formula SHA256: `e752b522a36eb515dcc8523bce54173cf9a22f5b4ad9d3e6f8021475dd54ce9c`

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
- Evidence stream age: **3.78 hours**

## Evidence maturity gates

- Supported trades >= 10: **False**
- Distinct targets >= 6: **False**
- Size2 trades >= 3: **False**
- Size3 trades >= 3: **False**
- All maturity gates passed: **False**

These gates only indicate that enough prospective evidence exists for
another human review. They do **not** authorize an automatic formula change.

## Audit state

Step 4 monitoring is installed and the release manifest is frozen.
The next audit gate is **Step 5 — Freeze pre-launch V3/V4 evidence / separate post-launch votes**.

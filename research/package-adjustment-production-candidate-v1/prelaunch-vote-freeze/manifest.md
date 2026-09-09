# Package Adjustment Step 5 — Pre-Launch Vote Evidence Freeze

Created: 2026-09-09T00:43:17.681827+00:00

## Production launch cutoff

**2026-09-08T21:33:18.390887+00:00**

Votes at or before this timestamp are calibration evidence. Votes strictly
after it are post-launch research evidence. The two phases must never be
merged into one calibration dataset.

## Frozen calibration evidence

- V3: **300 counted votes**, canonical result generated before production launch.
- V4: **300 counted votes**, canonical result generated before production launch.
- V3 and V4 challenge catalogs, results, fit diagnostics, and the derived
  Shadow V2 candidate were copied byte-for-byte and SHA256-pinned.
- Freeze manifest SHA256: `bd6212e19a81ca1f04dfd5823a6246450fe07e6e8d0d3a18b21645ca5f77a99f`

## Post-launch policy

- V3/V4 aggregators partition rows by the production launch cutoff **before**
  applying the daily voter cap.
- Canonical aggregation output after Step 5 is post-launch-only research.
- Frozen pre-launch snapshots are never rewritten by those aggregators.
- Shadow V2 is not rebuilt from post-launch vote results.
- Post-launch votes can trigger future human research review only; they never
  modify the live Package Adjustment automatically.

## Audit state

Step 5 is complete. The next gate is **Step 6 — Unsupported-shape UI + scope guards + IDP consistency**.

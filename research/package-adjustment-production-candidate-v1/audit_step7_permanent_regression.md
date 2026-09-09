# Package Adjustment Step 7 — Permanent Regression Suite

Generated: 2026-09-09T03:20:45.500284+00:00

## Installed

- `scripts/validation/check_package_adjustment_live.py` is the permanent Package Adjustment validator.
- It is wired directly into `scripts/validation/repo_regression_checks.py` as regression group #13.
- The existing `Repo Regression Checks` workflow therefore runs Package Adjustment checks automatically.

## Permanent coverage

- Exact V1.5 formula + position-scope fingerprint against the frozen V1.5 release manifest.
- V1.4 release preservation and V1.5 release lineage.
- Frozen pre-launch V3/V4 evidence snapshots and challenge catalogs.
- Exact-live OOS monitor hash/release alignment.
- QB/RB/WR/TE/DL/LB/DB scope and K exclusion.
- Offense/IDP parity.
- V3 51/49 size2 and V4 45/33/22 size3 support.
- Tiny-padding invariance for both size2 and size3.
- Unsupported 60/40 size2, 55/24/21 size3, fourth meaningful piece, picks, multi-v-multi, and target-equal package pieces.
- True/effective 1-for-1 remain not-applicable.
- Package Adjustment changes only the trade-verdict consumer.

## Production

No Package Adjustment formula value changed in Step 7.

Step 7 is complete. Next: **Step 8 — Obsolete/duplicate workflow cleanup**.

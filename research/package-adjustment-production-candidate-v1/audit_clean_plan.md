# Package Adjustment Audit-Clean Plan

Status: COMPLETE

The live Package Adjustment stays controlled-live while each audit gate is
hardened and independently verified.

## Gates

- [x] Step 1 — Tiny-padding invariance
  - Three meaningful package pieces plus sub-6%-of-target throw-ins retain the
    same premium tier and target-side adjustment.
  - A fourth meaningful piece remains unsupported.
- [x] Step 2 — Evidence-bounded 3-player composition policy
  - 3-player Package Adjustment is limited to the exact rectangular empirical
    composition hull observed across all 100 frozen V4 challenges.
  - Unsupported 3-meaningful-player compositions fail closed instead of
    inheriting the 2-player multiplier.
  - Step 1 tiny-padding invariance remains intact because composition is
    normalized over meaningful package FV only.
- [x] Step 3 — Evidence-bounded 2-player composition policy
  - 2-player Package Adjustment is limited to the exact empirical 51/49
    composition envelope observed across all 100 frozen V3 size2 challenges.
  - Unsupported 2-meaningful-player compositions fail closed.
  - The V3 target-sensitive size2 multiplier curve itself is unchanged.
- [x] Step 4 — Exact-live prospective/OOS monitoring + release manifest
  - The exact live V1.4 formula is frozen in an immutable release manifest.
  - Only trades strictly after the Step 4 release cutoff can enter OOS evidence.
  - OOS evaluation requires anti-hindsight pre-trade FV snapshots no older than 48h.
  - Evidence-maturity gates trigger review only and never auto-change production.
- [x] Step 5 — Freeze pre-launch V3/V4 evidence / separate post-launch votes
  - The 300-vote V3 and 300-vote V4 calibration datasets are frozen byte-for-byte.
  - Production launch time is the hard pre-launch/post-launch vote boundary.
  - V3/V4 aggregators partition before daily caps and report post-launch-only evidence.
  - Historical Shadow V2 cannot be rebuilt from post-launch vote results.
- [x] Step 6 — Unsupported-shape UI + scope guards + IDP consistency
  - Unsupported shapes explain why Package Adjustment was not applied while raw FV/verdict behavior remains available.
  - Package Adjustment is explicitly limited to QB/RB/WR/TE/DL/LB/DB; K fails closed.
  - DL/LB/DB use the same evidence-bounded Package Adjustment rules as offense.
  - Exact-live prospective/OOS monitoring is re-frozen and revision-aligned to production V1.5.
- [x] Step 7 — Permanent Package Adjustment repo regression suite
  - Dedicated live Package Adjustment validator is wired into repo_regression_checks.py.
  - Permanent coverage protects V1.5 formula/scope, frozen release lineage, and OOS monitor alignment.
  - Live-JS cases cover supported size2/size3, tiny padding, K exclusion, IDP parity, and unsupported shapes.
  - Repo Regression Checks now runs Package Adjustment automatically on PRs, manual runs, and after Scheduled Data Refresh.
- [x] Step 8 — Obsolete/duplicate workflow cleanup
  - Removed duplicate scheduled Shadow V1 aggregation and obsolete one-time activation/install/audit workflows.
  - Retained only the active V1.5 OOS monitor, prospective evidence capture, current V4/post-launch vote aggregation, and permanent repo regression workflow.
  - No Package Adjustment formula or consumer behavior changed during cleanup.
- [x] Step 9 — Final adversarial audit and production sign-off
  - Permanent 13-group repo regression suite and an independent 16-case live-JS boundary/adversarial suite passed.
  - Frozen V1.4/V1.5 release lineage, pre-launch evidence freeze, exact-live monitor hash, scope guards, and consumer isolation were re-verified.
  - Production remains controlled-live at revision v1.5; no formula value changed.
  - Prospective OOS maturity remains a monitoring gate and is not overstated as calibration validation until its evidence thresholds pass.

## Step 1 invariant

A package of three meaningful lesser players must not lose its 3-player
consolidation treatment merely because one or more additional assets are below
the existing 6%-of-target meaningful-piece threshold.

Tiny assets continue to count at their full raw Fundamental Value on the
package side. They are excluded only from the package-size/materiality
classification. A fourth meaningful player still makes the production shape
unsupported.

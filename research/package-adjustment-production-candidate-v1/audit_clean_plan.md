# Package Adjustment Audit-Clean Plan

Status: IN PROGRESS

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
- [ ] Step 6 — Unsupported-shape UI + scope guards + IDP consistency
  - Live scope/UI hardening installed: unsupported shapes now explain why Package Adjustment was not applied.
  - Package Adjustment is explicitly limited to QB/RB/WR/TE/DL/LB/DB, the frozen V3/V4 evidence-supported positions.
  - K is fail-closed; DL/LB/DB use the same evidence-bounded Package Adjustment rules as offense.
  - Pending before this gate closes: re-freeze/re-align the exact-live Step 4 OOS monitor to production revision V1.5.
- [ ] Step 7 — Permanent Package Adjustment repo regression suite
- [ ] Step 8 — Obsolete/duplicate workflow cleanup
- [ ] Step 9 — Final adversarial audit and production sign-off

## Step 1 invariant

A package of three meaningful lesser players must not lose its 3-player
consolidation treatment merely because one or more additional assets are below
the existing 6%-of-target meaningful-piece threshold.

Tiny assets continue to count at their full raw Fundamental Value on the
package side. They are excluded only from the package-size/materiality
classification. A fourth meaningful player still makes the production shape
unsupported.

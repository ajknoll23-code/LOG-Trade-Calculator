# Package Adjustment Audit-Clean Plan

Status: IN PROGRESS

The live Package Adjustment stays controlled-live while each audit gate is
hardened and independently verified.

## Gates

- [x] Step 1 — Tiny-padding invariance
  - Three meaningful package pieces plus sub-6%-of-target throw-ins retain the
    same premium tier and target-side adjustment.
  - A fourth meaningful piece remains unsupported.
- [ ] Step 2 — Evidence-bounded 3-player composition policy
- [ ] Step 3 — Evidence-bounded 2-player composition policy
- [ ] Step 4 — Exact-live prospective/OOS monitoring + release manifest
- [ ] Step 5 — Freeze pre-launch V3/V4 evidence / separate post-launch votes
- [ ] Step 6 — Unsupported-shape UI + scope guards + IDP consistency
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

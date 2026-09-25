# Package Adjustment V7 — Phase 1 Multi-v-Multi Preregistration

**Decision:** `FREEZE_V7_MULTI_V_MULTI_PHASE1_ARCHITECTURE_POWER_AND_CATALOG_NEXT`

**Research only. No V7 vote has been collected or read, no candidate has been fit, and production is unchanged.**

## Why this study exists

Production V1.7 deliberately fails closed on multi-v-multi and draft-pick trades. Those trades therefore fall back to raw FV addition even when one side is materially more concentrated.

The motivating real trade is retained only as a structural regression fixture:
- Side A raw FV: **14,346**
- Side B raw FV: **12,366**
- Raw gap: **1,980** toward Side A
- Highest-FV player: **Jamien Sherwood (4,801)** on Side B
- It is **not** labeled Side A or Side B for model fitting.
- Because it contains a pick, it remains outside the primary player-only voting study.

## Candidate architectures

- `C0_RAW_SUM`: current multi-v-multi fallback.
- `C1_V6_Q_TRANSFER`: symmetric V6 power score with fixed `q=2.9897594788655337`.
- `C2_GLOBAL_Q`: same power score with one globally fitted q.
- `C3_APEX_REMAINDER`: max asset + fitted fraction of remainder.

All candidates are symmetric between trade sides, scale-homogeneous, player-order invariant, and use no position-specific or named-player parameters.

## Mock-trade voting

**Yes — V7 will require new mock-trade votes.** Phase 1 itself does not collect them.

- 40 player-only multi-v-multi challenges per voter.
- Every voter can complete all 40 in one session.
- Topologies: 2v2, 2v3, 2v4, 3v3, 3v4, 4v4.
- FV/model scores hidden.
- Side and challenge order randomized.
- Candidate checkpoint must be frozen at 30, 40, or 50 distinct voters before activation.
- Stopping cannot depend on vote direction or model performance.

## Pick firewall

The Phase 0 audit found a material pick/player scale displacement. Draft picks therefore cannot enter the primary multi-v-multi voting experiment. Mixed-asset voting comes only after an independent pick→player FV bridge is frozen.

## Next stage

`package-adjustment-v7-phase1a-power-and-catalog-freeze`

# Trade Robustness V1 Phase 3 — Pick Slot Sensitivity Shadow

**Decision:** `HOLD_TRADE_ROBUSTNESS_V1_PHASE3_PICK_SLOT_SENSITIVITY_SHADOW`

**RESEARCH ONLY. No calculator behavior changed.**

## Method

- Player assets keep the deployed deterministic sensitivity envelope.
- Pick center values use the live production `pickValue()` function.
- Pick low/high values span late-to-early slot values for the same round/year.
- The deployed year discount is held fixed; no unsupported year-discount uncertainty is invented.
- Rounds 1-4 are promotion-eligible.
- Rounds 5-6 remain fail-closed because their production base values are extrapolated.
- Every adverse case reruns the actual live Package Adjustment and Trade Verdict.

## Universe

- Cases: **3636**
- Player sensitivity pool: **80**
- Pick center types: **24**
- Promotion-eligible pick types: **16**
- Research-only R5/R6 pick types: **8**

## Supported Round 1-4 directional outcomes

- Directional cases: **1717**
- Sensitivity Robust: **853** (49.7%)
- Fragile → Fair: **202** (11.8%)
- Fragile → opposite side: **662** (38.6%)

## Feasibility gates

- phase1b_anchor_passed: **PASS**
- live_thresholds_preserved: **PASS**
- all_production_pick_seasons_covered: **PASS**
- rounds_1_4_have_structural_envelopes: **PASS**
- rounds_5_6_explicitly_fail_closed: **PASS**
- mixed_live_package_adjustment_exercised: **PASS**
- year_discount_not_reestimated: **PASS**
- production_change_authorized: **FAIL**

## By trade structure

| Structure | Cases | Center fair | Robust | → Fair | Flipped |
|---|---:|---:|---:|---:|---:|
| pick_vs_pick | 276 | 7 | 228 | 20 | 21 |
| player_plus_pick_vs_player | 720 | 505 | 0 | 10 | 205 |
| player_vs_pick | 1920 | 83 | 1403 | 169 | 265 |
| player_vs_player_plus_pick | 720 | 505 | 0 | 10 | 205 |

## Promotion boundary

A future UI phase may support player + Round 1-4 pick trades using this structural slot envelope. Trades containing Round 5-6 picks must continue to show no robustness badge until those pick values have a stronger evidence base.

This remains a deterministic stress test, not a probability or confidence interval.

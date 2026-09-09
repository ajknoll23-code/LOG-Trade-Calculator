# Package Adjustment Audit Step 6 — Scope, UI, and IDP Analysis

Generated: 2026-09-09T02:03:17.315070+00:00

## Current live behavior

- Unsupported Package Adjustment shapes currently fail closed in the calculation.
- The trade verdict correctly falls back to raw side totals when Package Adjustment returns null.
- **The UI is silent when that happens**, so users cannot distinguish an unsupported
  package from a trade where Package Adjustment is simply not applicable.
- Explicit evidence-bounded position guard present in Package Adjustment: **False**

## Frozen evidence position coverage

- V3 targets: `DB=30, DL=30, LB=30, QB=30, RB=30, TE=30, WR=20`
- V3 package players: `DB=77, DL=95, LB=62, QB=30, RB=73, TE=54, WR=109`
- V4 targets: `DB=15, DL=15, LB=15, QB=15, RB=15, TE=15, WR=10`
- V4 package players: `DB=41, DL=51, LB=52, QB=20, RB=40, TE=32, WR=64`
- Positions represented on both target and package sides: **DB, DL, LB, QB, RB, TE, WR**

### IDP

- **DL, LB, and DB are all represented in frozen evidence.**
- The frozen experiments do not support a separate IDP-specific Package Adjustment multiplier.
- Recommended policy: apply the exact same shape/composition rules to offense and IDP.

### Kicker scope

- K appears in frozen V3/V4 evidence: **False**
- K is exposed by current UI/runtime position lists: **True**
- Current Package Adjustment explicitly blocks K by position: **False**
- Uncalibrated K scope leak detected: **True**

## Unsupported-shape UX

| Case | Current behavior | Recommended UI |
|---|---|---|
| pick_or_nonplayer_asset_present | Package Adjustment returns null; UI renders no explanation | unsupported |
| multi_vs_multi | Package Adjustment returns null; UI renders no explanation | unsupported |
| package_piece_at_or_above_target_fv | Package Adjustment returns null; UI renders no explanation | unsupported |
| more_than_3_meaningful_package_players | Package Adjustment returns null; UI renders no explanation | unsupported |
| size2_composition_outside_frozen_v3_envelope | Package Adjustment returns null; UI renders no explanation | unsupported |
| size3_composition_outside_frozen_v4_envelope | Package Adjustment returns null; UI renders no explanation | unsupported |
| one_for_one | Package Adjustment returns null; UI renders no explanation | not_applicable |
| effective_one_for_one_after_tiny_piece_filter | Package Adjustment returns null; UI renders no explanation | not_applicable |

## Recommended Step 6 hardening

1. Introduce one shared Package Adjustment assessment/classification path.
2. Use that same result for both the trade-verdict adjustment and the UI reason.
3. Fail closed for positions absent from frozen V3/V4 evidence.
4. Keep QB/RB/WR/TE/DL/LB/DB on the same evidence-bounded rules.
5. Show a compact unsupported-scope note for 1-v-package shapes that fail calibration scope.
6. Keep ordinary 1-for-1 trades as not-applicable rather than warning users.
7. Explicitly state that unsupported Package Adjustment does not alter raw FV.

No production file was modified by this analysis.

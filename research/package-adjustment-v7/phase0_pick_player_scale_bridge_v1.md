# Package Adjustment V7 Phase 0 — Pick/Player Scale Bridge Audit

**Decision:** `INVESTIGATE_DRAFT_PICK_TO_PLAYER_FV_BRIDGE_BEFORE_V7_PHASE1`

This is a diagnostic-only upstream scale audit. It does **not** change Fundamental Value, draft-pick values, Market Value, Team Utility, or Package Adjustment.

## Bridge cases

| Case | LOG pick FV | Same-market player FV median | Gap | LOG rank displacement | Classification |
|---|---:|---:|---:|---:|---|
| 2027_early_1st | 7500 | 5563 | +34.8% | +10.0 | MATERIAL_HIGH |
| 2027_mid_1st | 5854 | 4679 | +25.1% | +29.0 | MATERIAL_HIGH |
| 2027_late_1st | 5244 | 3648 | +43.8% | +59.0 | MATERIAL_HIGH |
| 2028_early_1st | 6375 | 4600 | +38.6% | +36.0 | MATERIAL_HIGH |
| 2027_early_2nd | 3906 | 3646 | +7.1% | +11.0 | ALIGNED |

## Interpretation

The current LOG pick/player bridge is materially displaced in a consistent direction across the primary first-round cases (PICKS_HIGH_RELATIVE_TO_SAME_MARKET_PLAYERS). Treat this as an upstream draft-pick FV calibration research problem before asking a downstream package modifier to absorb the discrepancy.

The KTC snapshots define only the external market neighborhood. Their numeric values are not imported into LOG FV. The comparison asks whether a pick and players valued similarly by the external market land in a similar region of LOG's Fundamental Value scale.

## Snapshot consistency

User screenshot vs public KTC snapshot max drift: 0.09% (gate ≤ 1%).

## Firewall

- KTC network access from repository code: **No**
- Scraping performed by repository code: **No**
- Package Adjustment changed: **No**
- Draft-pick values changed: **No**
- Fundamental Value changed: **No**
- Production change authorized: **No**

## Next step

Freeze V7 Package Adjustment Phase 1. Open a separate draft-pick-to-player FV bridge investigation first; keep V1.7/V6 Package Adjustment untouched.

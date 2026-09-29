# Draft Pick FV V10 — Phase 1 Market Bridge + Tail Evaluation

**Decision:** `FREEZE_V10_PHASE1_MARKET_TRANSLATED_PICK_CURVE_AUTHORIZE_PHASE2_AUDIT`

The frozen Phase-0 fundamental R1–R4 expected-value curve was not changed. A separate one-parameter market translation was estimated from the frozen 2027 KTC combined curve.

## Market bridge

- Global combined multiplier: **2.244174**
- Tradesourced-only multiplier: **2.082715**
- Crowdsourced-only multiplier: **2.404616**
- LOCO median absolute log error: **0.0352**
- LOCO maximum absolute log error: **0.1312**
- Cells inside trade↔crowd band: **11/12**

## Market tail

- Combined KTC R3→R4 geometric decay: **0.773408**
- Tradesourced decay: **0.804971**
- Crowdsourced decay: **0.746159**
- R5 and R6 remain explicit extrapolations; KTC does not provide those rounds.

## Candidate values

| Cell | Candidate |
|---|---:|
| r1_early | 6131.5 |
| r1_mid | 5076.2 |
| r1_late | 4657.7 |
| r2_early | 3817.3 |
| r2_mid | 3142.1 |
| r2_late | 3016.3 |
| r3_early | 2776.6 |
| r3_mid | 2363.5 |
| r3_late | 2075.7 |
| r4_early | 1891.4 |
| r4_mid | 1739.6 |
| r4_late | 1731.2 |
| r5_early | 1462.8 |
| r5_mid | 1345.4 |
| r5_late | 1338.9 |
| r6_early | 1131.4 |
| r6_mid | 1040.6 |
| r6_late | 1035.5 |

## Historical tail diagnostic

- Historical expected-player R3→R4 geometric ratio: **0.7350**
- Historical expected-player R4→R5 geometric ratio: **0.9825**
- Historical expected-player R5→R6 geometric ratio: **1.1189**

These late-round outcome ratios are preserved as diagnostics only and do not directly set market prices.

All Phase-1 gates pass: **True**

No production values changed. YEAR_DISCOUNT, player valuation, Package Adjustment, and Team Utility remain untouched.

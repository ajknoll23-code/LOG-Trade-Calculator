# Draft Pick FV V10 — Phase 0 Expected-Value Construct Audit

**Decision:** `ADVANCE_V10_TO_PHASE1_UNDER_FROZEN_EXPECTED_VALUE_CONTRACT`

Phase 0 successfully rebuilt the R1–R4 target as class-balanced arithmetic expected H3 O2, with KTC held out of fitting and used only as a construct check.

## Raw R1–R4 expected values

| Cell | EV | 95% bootstrap interval | KTC combined | EV/KTC | In trade↔crowd band |
|---|---:|---:|---:|---:|:---:|
| r1_early | 2732.2 | 2385.1–3070.7 | 6381 | 0.428 | no |
| r1_mid | 2262.0 | 2062.1–2467.6 | 5250 | 0.431 | no |
| r1_late | 2075.4 | 1844.8–2323.7 | 4586 | 0.453 | no |
| r2_early | 1701.0 | 1440.2–1973.3 | 3623 | 0.469 | no |
| r2_mid | 1400.1 | 1234.3–1572.8 | 3279 | 0.427 | no |
| r2_late | 1344.1 | 1230.2–1467.2 | 3051 | 0.441 | no |
| r3_early | 1237.3 | 1149.7–1337.1 | 2462 | 0.503 | no |
| r3_mid | 1053.2 | 1001.3–1089.8 | 2344 | 0.449 | no |
| r3_late | 924.9 | 874.3–967.7 | 2178 | 0.425 | no |
| r4_early | 842.8 | 759.5–942.2 | 1927 | 0.437 | no |
| r4_mid | 775.2 | 663.9–905.5 | 1794 | 0.432 | no |
| r4_late | 771.4 | 671.6–889.5 | 1682 | 0.459 | no |

## Construct diagnostics

- Spearman vs 2027 KTC combined: **1.0000**
- Median absolute log ratio: **0.8234**
- Cells inside tradesourced↔crowdsourced band: **0/12**
- Raw monotonic violations: **0**
- Raw C1 passes all preregistered production construct gates: **False**

## Historical multiplicative decay diagnostics

- R3→R4 geometric mean: **0.7350**
- R4→R5 geometric mean: **0.9825**
- R5→R6 geometric mean: **1.1189**

No production values changed. YEAR_DISCOUNT remains out of scope. Phase 1 must evaluate the frozen core/tail candidates without fitting to KTC.

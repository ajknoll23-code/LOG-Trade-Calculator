# Team Utility Bench-Weight Sensitivity V1

**Status: RESEARCH ONLY — no production consumer changed.**

This study does **not** choose a new bench weight. It measures how much the Team Utility conclusion moves when the unvalidated bench coefficient is varied while legal-roster enforcement stays fixed.

## Inputs and guardrails

- Deployed bench weight: `0.15` (unchanged)
- Legal active-roster limit: `41`
- Tested weights: `0.00`, `0.05`, `0.10`, `0.15`, `0.20`, `0.25`, `0.30`
- Current active-roster FV coverage: `95.86%`
- Teams: `12`
- Synthetic raw-balanced scenarios: `3100`
- 1-for-2 scenarios: `1562`
- 1-for-3 scenarios: `1538`
- Concentrated target minimum FV (league active FV p60): `3377`

Synthetic scenarios intentionally pair a current optimized starter with 2 or 3 individually weaker players from another real roster whose raw Fundamental Value sum is within ±10% of the starter. This isolates lineup concentration vs. legal-roster depth without using Package Adjustment.

## Fragmented receiver sensitivity

| Bench weight | Positive TU | Negative TU | Median TU |
|---:|---:|---:|---:|
| 0.00 | 5.8% | 94.2% | -1364 |
| 0.05 | 5.8% | 94.2% | -1227 |
| 0.10 | 5.8% | 94.2% | -1090 |
| 0.15 | 5.8% | 94.2% | -957 |
| 0.20 | 5.8% | 94.2% | -826 |
| 0.25 | 5.5% | 94.5% | -689 |
| 0.30 | 5.5% | 94.5% | -561 |

- Sign flips anywhere from 0.00–0.30: **0.5%**
- Sign flips inside the core 0.10–0.20 band: **0.0%**
- Current 0.15 disagrees with either 0.05 or 0.30: **0.5%**

## Consolidator sensitivity

| Bench weight | Positive TU | Negative TU | Median TU |
|---:|---:|---:|---:|
| 0.00 | 66.6% | 17.2% | 560 |
| 0.05 | 69.1% | 20.6% | 504 |
| 0.10 | 70.2% | 21.8% | 447 |
| 0.15 | 71.3% | 22.6% | 390 |
| 0.20 | 72.0% | 23.2% | 334 |
| 0.25 | 72.0% | 23.2% | 278 |
| 0.30 | 72.9% | 24.0% | 221 |

- Sign flips anywhere from 0.00–0.30: **0.2%**
- Sign flips inside the core 0.10–0.20 band: **0.0%**

## Interpretation rule

There is deliberately **no `recommended_weight` field**. Without package preference or prospective trade labels, choosing the weight that makes one side win more often would be circular. The correct use of this report is to determine whether `0.15` is a stable placeholder and how strongly future Package Adjustment research must control for Team Utility weight.

## Production impact

- `TU_BENCH_WEIGHT` changed: **NO**
- Fundamental Value changed: **NO**
- Market Value changed: **NO**
- Trade verdict changed by this research job: **NO**
- Package Adjustment deployed: **NO**

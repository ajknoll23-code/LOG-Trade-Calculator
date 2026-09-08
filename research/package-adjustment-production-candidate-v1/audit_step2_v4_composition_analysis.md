# Package Adjustment Audit Step 2 — Frozen V4 Composition Analysis

Generated: 2026-09-08T23:57:04.388782+00:00

## Scope

Read-only analysis of the 100 frozen V4 3-player challenges. No production formula, FV, MV, Team Utility, pick value, or UI code is changed by this workflow.

## Experimental interpretation

V4 varied the package/target ratio across 1.75, 1.85, 1.95, 2.05, and 2.15 while holding the intended package composition at approximately 45/33/22. Therefore, the observed composition spread is construction noise around a fixed design, not evidence that arbitrary 3-player compositions were tested.

## Overall empirical composition

- Largest piece / meaningful package FV: **41.991% – 46.962% (median 45.043%, p05–p95 44.570% – 45.477%)**
- Middle piece / meaningful package FV: **30.827% – 36.725% (median 32.966%, p05–p95 32.484% – 33.439%)**
- Smallest piece / meaningful package FV: **21.202% – 22.473% (median 21.978%, p05–p95 21.602% – 22.319%)**
- Largest piece / target FV: **78.427% – 97.761% (median 87.928%, p05–p95 78.659% – 97.187%)**
- Middle piece / target FV: **56.810% – 78.954% (median 64.256%, p05–p95 57.229% – 71.371%)**
- Smallest piece / target FV: **37.104% – 48.292% (median 42.834%, p05–p95 38.321% – 47.370%)**

## Current 16% production guardrail comparison

- Frozen V4 challenges below 16% smallest-piece package share: **0 / 100**
- Empirical minimum smallest-piece package share: **21.202%**
- Empirical median smallest-piece package share: **21.978%**
- Empirical maximum smallest-piece package share: **22.473%**
- Gap from live 16% cutoff to empirical minimum: **5.202%**

## Rectangular empirical hull

- Largest package share: **41.991% – 46.962%**
- Middle package share: **30.827% – 36.725%**
- Smallest package share: **21.202% – 22.473%**

## Grouped checks

### Ratio target

| Group | N | Largest package share | Middle package share | Smallest package share | Smallest / target FV |
|---|---:|---:|---:|---:|---:|
| 1.75 | 20 | 45.087% | 32.920% | 21.992% | 38.487% |
| 1.85 | 20 | 44.985% | 33.033% | 21.983% | 40.668% |
| 1.95 | 20 | 45.053% | 32.980% | 21.967% | 42.834% |
| 2.05 | 20 | 45.180% | 32.823% | 21.998% | 45.101% |
| 2.15 | 20 | 44.944% | 33.182% | 21.874% | 47.030% |

### Target tier

| Group | N | Largest package share | Middle package share | Smallest package share | Smallest / target FV |
|---|---:|---:|---:|---:|---:|
| elite | 30 | 45.088% | 32.937% | 21.976% | 42.841% |
| premium | 35 | 45.083% | 32.978% | 21.939% | 42.786% |
| starter | 35 | 44.984% | 33.041% | 21.975% | 42.847% |

### Target position

| Group | N | Largest package share | Middle package share | Smallest package share | Smallest / target FV |
|---|---:|---:|---:|---:|---:|
| DB | 15 | 44.948% | 32.990% | 22.062% | 43.030% |
| DL | 15 | 45.025% | 32.997% | 21.979% | 42.861% |
| LB | 15 | 45.082% | 32.981% | 21.937% | 42.759% |
| QB | 15 | 45.096% | 32.958% | 21.946% | 42.810% |
| RB | 15 | 45.161% | 32.944% | 21.896% | 42.674% |
| TE | 15 | 45.062% | 33.004% | 21.934% | 42.755% |
| WR | 10 | 44.938% | 33.065% | 21.997% | 42.906% |

## Audit conclusion from this gate

This report intentionally does **not** select or deploy a new production policy. Its purpose is to establish the exact frozen V4 composition support before choosing between a conservative smooth bridge and a fail-closed composition envelope.

The next audit action should inspect this artifact and choose the safest evidence-bounded policy. Production must not be patched until that review is complete.

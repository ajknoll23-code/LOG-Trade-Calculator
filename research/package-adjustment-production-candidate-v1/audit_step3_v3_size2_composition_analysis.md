# Package Adjustment Audit Step 3 — Frozen V3 Two-Player Composition Analysis

Generated: 2026-09-09T00:18:55.116052+00:00

## Scope

Read-only analysis of the 100 frozen V3 two-player challenges. No production formula, FV, MV, Team Utility, pick value, or UI code is changed by this workflow.

## Experimental interpretation

V3 varied package/target ratio and package size while holding intended two-player composition at approximately **51/49**. The observed composition spread is construction noise around a fixed design, not evidence that arbitrary two-player splits were tested.

## Overall empirical composition

- Largest piece / meaningful package FV: **50.441% – 52.303% (median 50.998%, p05–p95 50.835% – 51.127%)**
- Smallest piece / meaningful package FV: **47.697% – 49.559% (median 49.002%, p05–p95 48.873% – 49.165%)**
- Largest piece / target FV: **55.789% – 96.268%**
- Smallest piece / target FV: **53.781% – 90.983%**
- Two-player split gap (largest minus smallest): **0.882% – 4.606%**

## Current production comparison

Production currently has **no two-player composition guard**. Once exactly two meaningful lesser players qualify, the V3 target-sensitive multiplier can apply regardless of how unevenly those two players divide meaningful package FV.

## Rectangular empirical envelope

- Largest package share: **50.441% – 52.303%**
- Smallest package share: **47.697% – 49.559%**

## Grouped checks — ratio target

| Group | N | Largest package share | Smallest package share | Largest / target FV | Smallest / target FV |
|---|---:|---:|---:|---:|---:|
| 1.1 | 20 | 50.981% | 49.019% | 56.095% | 53.908% |
| 1.25 | 20 | 50.982% | 49.018% | 63.747% | 61.255% |
| 1.4 | 20 | 51.006% | 48.994% | 71.377% | 68.589% |
| 1.6 | 20 | 51.007% | 48.993% | 81.597% | 78.404% |
| 1.85 | 20 | 50.999% | 49.001% | 94.396% | 90.633% |

## Grouped checks — target tier

| Group | N | Largest package share | Smallest package share | Largest / target FV | Smallest / target FV |
|---|---:|---:|---:|---:|---:|
| elite | 30 | 51.012% | 48.988% | 71.514% | 68.662% |
| premium | 35 | 50.983% | 49.017% | 71.376% | 68.610% |
| starter | 35 | 50.988% | 49.012% | 71.354% | 68.547% |

## Grouped checks — target position

| Group | N | Largest package share | Smallest package share | Largest / target FV | Smallest / target FV |
|---|---:|---:|---:|---:|---:|
| DB | 15 | 51.014% | 48.986% | 71.411% | 68.654% |
| DL | 15 | 51.003% | 48.997% | 71.376% | 68.547% |
| LB | 15 | 50.974% | 49.026% | 71.370% | 68.749% |
| QB | 15 | 51.013% | 48.987% | 71.335% | 68.548% |
| RB | 15 | 50.971% | 49.029% | 71.433% | 68.426% |
| TE | 15 | 50.972% | 49.028% | 71.371% | 68.592% |
| WR | 10 | 50.991% | 49.009% | 71.298% | 68.590% |

## Grouped checks — target FV band

| Group | N | Largest package share | Smallest package share | Largest / target FV | Smallest / target FV |
|---|---:|---:|---:|---:|---:|
| high | 35 | 50.996% | 49.004% | 71.433% | 68.570% |
| low | 30 | 50.989% | 49.011% | 71.382% | 68.569% |
| mid | 35 | 51.003% | 48.997% | 71.376% | 68.694% |

## Audit conclusion from this gate

This report intentionally does **not** select or deploy a new two-player production policy. The next audit action should inspect the exact frozen V3 composition support and choose the safest evidence-bounded size2 rule before production is patched.

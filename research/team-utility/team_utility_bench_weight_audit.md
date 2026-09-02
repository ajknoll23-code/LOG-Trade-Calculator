# Team Utility Bench-Weight Audit — Stage 1

## Decision

**Research only — no production coefficient change is authorized by this audit.**

- Current production `TU_BENCH_WEIGHT`: **0.15**
- Primary empirical target (4-week future-start share): **15.25%**
- Nearest 0.05 candidate: **0.15**
- Current 0.15 inside clustered-bootstrap 80% band: **True**
- Current 0.15 inside clustered-bootstrap 95% band: **True**
- 2024 vs 2025 target spread: **1.35%**

Why no automatic deployment: Stage-1 uses 2024-2025 active-bench utilization under the old 1-RB/1-LB ruleset and does not observe taxi/IR utilization. Use this as an empirical anchor, then run a 2026-roster and trade-sensitivity audit before changing the global coefficient.

## Historical sample quality

| Season | Teams | Weeks | Records | Started | Benched | Starter slots | RB dedicated | LB dedicated |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024 | 12 | 18 | 8294 | 3240 | 5054 | 15 | 1 | 1 |
| 2025 | 12 | 18 | 8723 | 3224 | 5499 | 15 | 1 | 1 |

## Bench utilization by horizon

| Horizon | Bench player-weeks | Future start share | Any future start | Same-team retention | Start share if retained |
|---|---:|---:|---:|---:|---:|
| 1 week | 9959 | 11.52% | 11.52% | 95.33% | 12.08% |
| 2 weeks | 9367 | 13.24% | 18.55% | 93.45% | 14.17% |
| 4 weeks | 8196 | 15.25% | 28.26% | 90.20% | 16.90% |

## Four-week primary target by season

| Season | Bench player-weeks | Future start share | Any future start | Retention |
|---|---:|---:|---:|---:|
| 2024 | 3897 | 15.95% | 29.43% | 89.15% |
| 2025 | 4299 | 14.61% | 27.19% | 91.16% |

## Four-week target by position

| Position | Bench player-weeks | Future start share | Any future start | Retention |
|---|---:|---:|---:|---:|
| DB | 984 | 20.12% | 37.50% | 88.21% |
| DL | 759 | 16.77% | 29.25% | 89.59% |
| K | 125 | 15.40% | 24.00% | 79.00% |
| LB | 1154 | 21.53% | 36.92% | 89.41% |
| QB | 901 | 15.46% | 29.41% | 90.45% |
| RB | 1657 | 10.33% | 18.77% | 92.49% |
| TE | 665 | 14.62% | 29.32% | 89.32% |
| WR | 1951 | 12.76% | 25.53% | 90.88% |

## Clustered bootstrap

- Team-season clusters: **24**
- Replicates: **2000**
- 80% band for 4-week future-start share: **14.70% to 15.80%**
- 95% band: **14.42% to 16.14%**

## Candidate coefficient grid

| Candidate w | Distance to empirical target | Improvement vs current 0.15 |
|---:|---:|---:|
| 0.15 | 0.25% | -0.00% |
| 0.20 | 4.75% | -4.50% |
| 0.10 | 5.25% | -5.00% |
| 0.25 | 9.75% | -9.50% |
| 0.05 | 10.25% | -10.00% |
| 0.30 | 14.75% | -14.50% |
| 0.00 | 15.25% | -15.00% |
| 0.35 | 19.75% | -19.50% |
| 0.40 | 24.75% | -24.50% |
| 0.50 | 34.75% | -34.50% |

## Interpretation guardrails

- This is a **utilization calibration anchor**, not a proof that bench dynasty assets are worth only their short-horizon start probability.
- 2024–25 were played with **1 dedicated RB and 1 dedicated LB**; production 2026 uses **2 RB and 2 LB**.
- Historical `benched` observations exclude taxi/IR. Production currently keeps taxi/reserve-IR assets in bench economics while preventing them from starting.
- A single global `w` may therefore be too coarse. Stage 2 should test 2026 roster sensitivity and whether active bench vs taxi/IR need separate treatment.
- `TU_BENCH_WEIGHT` remains unchanged at **0.15** after this audit.

## Next test

Use this empirical range to run a **2026 roster + real-trade sensitivity audit** across `w = 0.00–0.50`. That second audit should determine whether changing 0.15 materially improves decision quality or merely changes score magnitude.

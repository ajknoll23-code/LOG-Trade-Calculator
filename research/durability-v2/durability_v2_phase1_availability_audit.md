# Durability / Availability V2 — Phase 1 Historical Audit

Method: `durability-v2-phase1-availability-audit-v1`  
Status: **`RESEARCH_ONLY_DURABILITY_AVAILABILITY_AUDIT`**

## Guardrail

**Research only. No deployed durability or player value is changed.**

## Why this audit matters

The live history component uses each position's year-over-year games-played **R² directly as the player-specific availability weight**. Phase 1 tests survivor-only persistence, an unconditional next-season view where missing future seasons are zero, and whether 2–3 years of history adds signal.

- Historical seasons: **2015–2025**
- Player-seasons with mapped tracked position: **18060**
- Unresolved GP-positive player-seasons: **5892**

## Year-over-year persistence

| Pos | Deployed R² | Survivor R² | Unconditional R² | Survivor ρ | Unconditional ρ | Survivor N | Unconditional N |
|---|---:|---:|---:|---:|---:|---:|---:|
| QB | 0.3762 | 0.4125 | 0.4434 | 0.6246 | 0.6245 | 597 | 776 |
| RB | 0.1309 | 0.1113 | 0.2274 | 0.2965 | 0.4581 | 1145 | 1548 |
| WR | 0.1545 | 0.1368 | 0.2490 | 0.3467 | 0.4895 | 1755 | 2383 |
| TE | 0.1624 | 0.1348 | 0.2339 | 0.3347 | 0.4694 | 1051 | 1397 |
| DL | 0.1956 | 0.1529 | 0.2472 | 0.3614 | 0.4780 | 2489 | 3173 |
| LB | 0.0850 | 0.0863 | 0.2300 | 0.2815 | 0.4567 | 2275 | 2959 |
| DB | 0.1081 | 0.1048 | 0.2283 | 0.2964 | 0.4494 | 3176 | 4110 |

## Multi-year history vs unconditional next-season availability

| Pos | Current ρ | 2Y mean ρ | 2Y recency ρ | 3Y mean ρ | 3Y recency ρ |
|---|---:|---:|---:|---:|---:|
| QB | 0.6245 | 0.6612 | 0.6665 | 0.6471 | 0.6612 |
| RB | 0.4581 | 0.4125 | 0.4328 | 0.3857 | 0.4255 |
| WR | 0.4895 | 0.4599 | 0.4731 | 0.4270 | 0.4587 |
| TE | 0.4694 | 0.3922 | 0.4178 | 0.3892 | 0.4298 |
| DL | 0.4780 | 0.4287 | 0.4450 | 0.3982 | 0.4383 |
| LB | 0.4567 | 0.4138 | 0.4343 | 0.3865 | 0.4300 |
| DB | 0.4494 | 0.4186 | 0.4369 | 0.3743 | 0.4177 |

## Low-availability pattern check

These are descriptive participation patterns, not injury diagnoses.

| Pattern | N | Mean next availability | Median next availability |
|---|---:|---:|---:|
| `one_year_low_after_near_full` | 1188 | 45.0% | 41.2% |
| `repeated_low_two_years` | 1812 | 25.9% | 5.9% |
| `current_near_full` | 6653 | 73.9% | 88.2% |

## Phase 2

Cross-validate next-season availability by held-out base season. Compare position median only, deployed R2 blend, prior-year availability, 2-year mean, 2-year recency, 3-year mean, 3-year recency, and simple position-specific OLS variants. Keep survivor-only and unconditional targets separate so role/league-exit risk is not silently conflated with within-career injury persistence.

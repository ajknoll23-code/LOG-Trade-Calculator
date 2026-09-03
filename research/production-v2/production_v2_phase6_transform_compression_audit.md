# Production V2 — Phase 6 Transform Compression Audit

## Decision

**KEEP_TRANSFORM_FLOOR_UNDEPLOYED_PENDING_PROSPECTIVE_CALIBRATION**

- Production files mutated: **0**
- New transform coefficients selected: **No**
- Current floor activation: ratio ≤ **0.333× replacement**
- Current ceiling activation: ratio ≥ **2.20× replacement**

The current `0.15` floor is not just a guardrail. It maps every player below one-third of replacement production to the same raw production multiplier.

## Current 0.15 compression

| Pos | Doc floor | Hybrid floor | Distinct PM estimates collapsed (doc / hybrid) | Ceiling doc / hybrid |
|---|---:|---:|---:|---:|
| QB | 21 (38.9%) | 21 (38.9%) | 20 / 20 | 0 / 0 |
| RB | 14 (15.1%) | 22 (23.7%) | 13 / 21 | 0 / 0 |
| WR | 4 (3.7%) | 4 (3.7%) | 3 / 3 | 0 / 0 |
| TE | 0 (0.0%) | 0 (0.0%) | 0 / 0 | 0 / 0 |
| DL | 0 (0.0%) | 0 (0.0%) | 0 / 0 | 0 / 0 |
| LB | 0 (0.0%) | 0 (0.0%) | 0 / 0 | 0 / 0 |
| DB | 0 (0.0%) | 0 (0.0%) | 0 / 0 | 0 / 0 |

## Floor sensitivity — hit rate by position

These are diagnostics only, not recommendations.

| Floor | Activation ratio | QB doc/hybrid | RB doc/hybrid | WR doc/hybrid | DL doc/hybrid |
|---:|---:|---:|---:|---:|---:|
| 0.05 | 0.200× | 9.3%/9.3% | 4.3%/5.4% | 0.9%/0.9% | 0.0%/0.0% |
| 0.10 | 0.267× | 18.5%/18.5% | 7.5%/15.1% | 1.9%/1.9% | 0.0%/0.0% |
| 0.15 | 0.333× | 38.9%/38.9% | 15.1%/23.7% | 3.7%/3.7% | 0.0%/0.0% |
| 0.20 | 0.400× | 38.9%/38.9% | 23.7%/35.5% | 6.5%/6.5% | 0.0%/0.0% |

## Value sensitivity versus the current 0.15 floor

| Floor | QB P95 abs FV Δ (doc/hybrid) | RB P95 | WR P95 | DL P95 |
|---:|---:|---:|---:|---:|
| 0.05 | 66.6%/66.6% | 46.3%/64.1% | 0.0%/0.0% | 0.0%/0.0% |
| 0.10 | 33.4%/33.4% | 33.2%/33.3% | 0.0%/0.0% | 0.0%/0.0% |
| 0.15 | 0.0%/0.0% | 0.0%/0.0% | 0.0%/0.0% | 0.0%/0.0% |
| 0.20 | 35.0%/35.0% | 33.4%/33.5% | 6.3%/7.8% | 0.0%/0.0% |

## Interpretation

The hard PM floor is a compression mechanism, not merely a safety bound: every candidate below its activation ratio is assigned the same raw PM and loses production ordering at that layer. Phase 6 quantifies the compression but does not select a replacement floor without out-of-sample 2026 evidence.

Positions with ≥10% floor compression under at least one normalization candidate: **QB, RB**.

Positions with ≥5% ceiling compression: **None**.

The correct response is **not** to pick a prettier floor by eye. Phase 2A already froze the preseason evidence needed to test these candidates prospectively against real 2026 outcomes.

## Next step

Do not choose a new affine floor from cross-sectional aesthetics. Carry the floor sensitivity candidates into the prospective 2026 outcome evaluator frozen in Phase 2A. Separately audit the 31 missing-candidate players because their fallback semantics are still undefined for V2.

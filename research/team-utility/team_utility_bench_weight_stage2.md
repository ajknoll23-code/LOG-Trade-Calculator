# Team Utility Bench-Weight Audit — Stage 2

## Decision

**Recommendation: `KEEP_0_15`**

- Production coefficient: **0.15**
- Stage-1 empirical 4-week target: **15.2%**
- Stage-1 clustered 95% band: **14.4% to 16.1%**
- Stage-1 anchor supports 0.15: **True**
- Local 0.10/0.20 minimum median acquisition top-10 overlap vs 0.15: **100.0%**
- Local 0.10/0.20 minimum median acquisition Spearman vs 0.15: **0.9920**
- Local 0.10/0.20 maximum balanced-swap sign-pattern flip rate: **1.46%**
- Local stability rule passed: **True**

Stage 1 empirically anchors the coefficient near 0.15 and Stage 2 shows 2026 Team Utility decisions are locally robust to +/-0.05 changes. There is no evidence-based reason to move the global coefficient.

**This audit does not authorize an automatic production change.**

## Data quality

- Current teams: **12**
- Current rostered players evaluated: **551**
- Projection artifact rows available: **1022**
- Current unresolved roster rows: **0**
- Marginal acquisition scenarios: **6061**
- FV-balanced one-for-one swap scenarios: **20100**

Every current team filled all 17 legal starter slots with zero taxi/reserve starters and zero missing non-K projections.

## Acquisition-ranking sensitivity

| w | Median Spearman vs .15 | Min Spearman | Median top-10 overlap | Min top-10 | Median top-25 overlap |
|---:|---:|---:|---:|---:|---:|
| 0.00 | 0.7365 | 0.4765 | 100.0% | 90.0% | 96.0% |
| 0.05 | 0.9718 | 0.9541 | 100.0% | 90.0% | 98.0% |
| 0.10 | 0.9937 | 0.9878 | 100.0% | 100.0% | 98.0% |
| 0.15 | 1.0000 | 1.0000 | 100.0% | 100.0% | 100.0% |
| 0.20 | 0.9920 | 0.9848 | 100.0% | 90.0% | 100.0% |
| 0.25 | 0.9794 | 0.9552 | 100.0% | 90.0% | 96.0% |
| 0.30 | 0.9610 | 0.9170 | 100.0% | 80.0% | 96.0% |
| 0.35 | 0.9444 | 0.8729 | 100.0% | 80.0% | 92.0% |
| 0.40 | 0.9263 | 0.8366 | 90.0% | 70.0% | 84.0% |
| 0.50 | 0.8939 | 0.7654 | 80.0% | 60.0% | 76.0% |

## Balanced one-for-one swap sensitivity

| w | Sign-pattern changes vs .15 | Side sign flips | Mutual positive | Mutual negative | Split-sign |
|---:|---:|---:|---:|---:|---:|
| 0.00 | 56.12% | 44.76% | 3.42% | 14.04% | 26.51% |
| 0.05 | 2.82% | 1.90% | 6.02% | 20.40% | 70.67% |
| 0.10 | 1.46% | 0.85% | 6.03% | 20.35% | 71.61% |
| 0.15 | 0.00% | 0.00% | 5.89% | 20.28% | 72.32% |
| 0.20 | 1.35% | 0.78% | 5.60% | 20.21% | 72.98% |
| 0.25 | 2.84% | 1.53% | 5.36% | 19.85% | 73.61% |
| 0.30 | 5.11% | 2.74% | 4.88% | 19.32% | 74.72% |
| 0.35 | 8.05% | 4.30% | 4.32% | 18.06% | 76.59% |
| 0.40 | 12.56% | 6.81% | 3.56% | 15.75% | 79.61% |
| 0.50 | 33.30% | 20.06% | 0.00% | 0.00% | 98.93% |

## Taxi / reserve contribution to current bench capital

- Median taxi+reserve share of nonstarter FV across teams: **13.4%**
- Maximum team taxi+reserve share of nonstarter FV: **24.4%**

This matters because Stage 1 empirically measured active-bench utilization only; historical Sleeper matchup rosters excluded taxi/IR.

## Interpretation

- Stage 1 answers **where the empirical bench coefficient is centered**.
- Stage 2 answers **whether moving that coefficient changes real 2026 roster-fit decisions**.
- The historical trade file is deliberately **not** used as a fake outcome backtest because it does not preserve exact pre-trade roster and slot state.
- Fundamental Value remains the accounting unit. Projections only choose who starts.
- Incoming players are treated exactly like production: active bench and immediately starter-eligible.
- `TU_BENCH_WEIGHT` remains **0.15** after this research run unless a later explicit production deployment changes it.

## Recommended close

Lock **`TU_BENCH_WEIGHT = 0.15`** as the validated V1 global bench coefficient.

Do not reopen the coefficient until one of these conditions occurs:
1. enough 2026 regular-season lineup history accumulates under the new 2-RB/2-LB ruleset;
2. a trustworthy exact pre/post trade-roster history is built;
3. evidence justifies separate active-bench vs taxi/reserve weighting.

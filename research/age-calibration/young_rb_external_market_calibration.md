# Young RB External Market Age Calibration

**Status:** research-only; no production values changed.

## External evidence

- Provider: **Stats Guy Fantasy**
- Format: **sf_dynasty**
- External snapshot: **2026-09-02T13:00:57.089Z**
- Signal: real-trade-derived broad SF dynasty market value.
- Use in this audit: independent calibration evidence only, not fundamental truth.

## Method

For RBs age 21-30, fit external log market value after controlling for Trade Desk production multiplier (linear + squared log term) and Trade Desk role. The remaining median residual by age is converted into a market-implied age factor relative to age 25.

Two cohorts are shown:

- meaningful production: PM >= 0.35
- high production: PM >= 0.65

## High-production cohort

- N: **32**

| Age | N | Implied factor vs age 25 | Bootstrap P10 | Bootstrap P90 | Current | Linear | Smoothstep | Quadratic |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 21 | 1 | 2.109 | 1.647 | 2.560 | 1.493 | 1.493 | 1.493 | 1.493 |
| 22 | 3 | 2.466 | 1.486 | 3.390 | 1.390 | 1.370 | 1.416 | 1.277 |
| 23 | 3 | 2.092 | 1.131 | 2.590 | 1.268 | 1.246 | 1.246 | 1.123 |
| 24 | 4 | 1.322 | 0.910 | 1.838 | 1.384 | 1.123 | 1.077 | 1.031 |
| 25 | 4 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

### Candidate fit

| Rank | Candidate | Ages used | Log-factor RMSE |
|---:|---|---|---:|
| 1 | current | 22, 23, 24, 25 | 0.3813 |
| 2 | smoothstep_to_25 | 22, 23, 24, 25 | 0.3931 |
| 3 | linear_to_25 | 22, 23, 24, 25 | 0.4001 |
| 4 | quadratic_to_25 | 22, 23, 24, 25 | 0.4694 |

## Meaningful-production cohort

- N: **48**

| Age | N | Implied factor vs age 25 | Bootstrap P10 | Bootstrap P90 | Current | Linear | Smoothstep | Quadratic |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 21 | 2 | 1.647 | n/a | n/a | 1.493 | 1.493 | 1.493 | 1.493 |
| 22 | 3 | 2.462 | n/a | n/a | 1.390 | 1.370 | 1.416 | 1.277 |
| 23 | 4 | 2.124 | n/a | n/a | 1.268 | 1.246 | 1.246 | 1.123 |
| 24 | 7 | 1.199 | n/a | n/a | 1.384 | 1.123 | 1.077 | 1.031 |
| 25 | 9 | 1.000 | n/a | n/a | 1.000 | 1.000 | 1.000 | 1.000 |

### Candidate fit

| Rank | Candidate | Ages used | Log-factor RMSE |
|---:|---|---|---:|
| 1 | smoothstep_to_25 | 21, 22, 23, 24, 25 | 0.3497 |
| 2 | current | 21, 22, 23, 24, 25 | 0.3531 |
| 3 | linear_to_25 | 21, 22, 23, 24, 25 | 0.3583 |
| 4 | quadratic_to_25 | 21, 22, 23, 24, 25 | 0.4169 |

## Interpretation boundary

This is cross-sectional market calibration, not causal proof of aging. Production and role controls reduce obvious confounding, but external managers may price draft capital, injury risk, draft pedigree, contract status, team context, and future upside not fully captured by Trade Desk PM/role.

A production change should only be considered if the high-production cohort has enough age coverage, the bootstrap intervals are informative, and one candidate has a materially better fit without reintroducing a discontinuity.

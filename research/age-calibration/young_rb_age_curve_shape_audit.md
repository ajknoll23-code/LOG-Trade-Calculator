# Young RB Age-Curve Shape Audit

**Status:** research-only; no production values changed.

## What changed from the first audit

The first audit established leverage. This follow-up tests whether the deployed elite-RB age curve has an avoidable shape/discontinuity problem.

All smooth candidates preserve the deployed age-21 multiplier and end at exactly 1.0 at age 25.
Market Value is used only as an external rank diagnostic.

## Synthetic elite-RB age profiles

| Candidate | Age 21 | Age 22 | Age 23 | Age 24 | Age 25 | Monotone? | Largest 1-year swing |
|---|---:|---:|---:|---:|---:|---|---:|
| current | 1.493 | 1.390 | 1.268 | 1.384 | 1.000 | NO | +27.7% |
| linear_to_25 | 1.493 | 1.370 | 1.246 | 1.123 | 1.000 | yes | +11.0% |
| smoothstep_to_25 | 1.493 | 1.416 | 1.246 | 1.077 | 1.000 | yes | +13.6% |
| quadratic_to_25 | 1.493 | 1.277 | 1.123 | 1.031 | 1.000 | yes | +14.4% |

## Market-rank diagnostic across current young RBs

This is **not** a truth score. Higher Spearman means the candidate's young-RB ordering is more consistent with current league Market Value ordering for players with coverage.

| Candidate | N with market | Spearman |
|---|---:|---:|
| current | 45 | 0.526 |
| linear_to_25 | 45 | 0.526 |
| smoothstep_to_25 | 45 | 0.526 |
| quadratic_to_25 | 45 | 0.526 |

## current

| Player | Age | Current AM | Candidate AM | Current value | Candidate value | Delta | Delta % | Current RB rank | Candidate RB rank | Market |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ashton jeanty | 22 | 1.390 | 1.390 | 7410 | 7410 | +0 | +0.0% | 4 | 4 | n/a |
| bijan robinson | 24 | 1.384 | 1.384 | 10501 | 10501 | +0 | +0.0% | 1 | 1 | n/a |
| devon achane | 24 | 1.384 | 1.384 | 8963 | 8963 | +0 | +0.0% | 3 | 3 | 3520 |
| jahmyr gibbs | 24 | 1.384 | 1.384 | 10501 | 10501 | +0 | +0.0% | 2 | 2 | 4604 |
| kyren williams | 25 | 1.000 | 1.000 | 5375 | 5375 | +0 | +0.0% | 7 | 7 | 5401 |

## linear_to_25

| Player | Age | Current AM | Candidate AM | Current value | Candidate value | Delta | Delta % | Current RB rank | Candidate RB rank | Market |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bijan robinson | 24 | 1.384 | 1.123 | 10501 | 8522 | -1979 | -18.8% | 1 | 1 | n/a |
| jahmyr gibbs | 24 | 1.384 | 1.123 | 10501 | 8522 | -1979 | -18.8% | 2 | 2 | 4604 |
| devon achane | 24 | 1.384 | 1.123 | 8963 | 7274 | -1689 | -18.8% | 3 | 4 | 3520 |
| ashton jeanty | 22 | 1.390 | 1.370 | 7410 | 7302 | -108 | -1.5% | 4 | 3 | n/a |
| kyren williams | 25 | 1.000 | 1.000 | 5375 | 5375 | +0 | +0.0% | 7 | 7 | 5401 |

## smoothstep_to_25

| Player | Age | Current AM | Candidate AM | Current value | Candidate value | Delta | Delta % | Current RB rank | Candidate RB rank | Market |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bijan robinson | 24 | 1.384 | 1.077 | 10501 | 8172 | -2329 | -22.2% | 1 | 1 | n/a |
| jahmyr gibbs | 24 | 1.384 | 1.077 | 10501 | 8172 | -2329 | -22.2% | 2 | 2 | 4604 |
| devon achane | 24 | 1.384 | 1.077 | 8963 | 6975 | -1988 | -22.2% | 3 | 4 | 3520 |
| ashton jeanty | 22 | 1.390 | 1.416 | 7410 | 7548 | +138 | +1.9% | 4 | 3 | n/a |
| kyren williams | 25 | 1.000 | 1.000 | 5375 | 5375 | +0 | +0.0% | 7 | 7 | 5401 |

## quadratic_to_25

| Player | Age | Current AM | Candidate AM | Current value | Candidate value | Delta | Delta % | Current RB rank | Candidate RB rank | Market |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bijan robinson | 24 | 1.384 | 1.031 | 10501 | 7821 | -2680 | -25.5% | 1 | 1 | n/a |
| jahmyr gibbs | 24 | 1.384 | 1.031 | 10501 | 7821 | -2680 | -25.5% | 2 | 2 | 4604 |
| devon achane | 24 | 1.384 | 1.031 | 8963 | 6676 | -2287 | -25.5% | 3 | 4 | 3520 |
| ashton jeanty | 22 | 1.390 | 1.277 | 7410 | 6809 | -601 | -8.1% | 4 | 3 | n/a |
| kyren williams | 25 | 1.000 | 1.000 | 5375 | 5375 | +0 | +0.0% | 7 | 7 | 5401 |

## Interpretation boundary

A candidate is not production-ready merely because it is smoother or tracks market rank better. The purpose here is to identify whether the current curve contains a structural artifact worth replacing, and which candidate families deserve real calibration next.

# Package Preference Voting V3 — Indifference Calibration

**Status: RESEARCH ONLY — no production consumer changed.**

V3 estimates how much raw FV a multi-player package must contain before voters are indifferent to the concentrated target asset.

- Counted V3 votes: `300`
- Unique V3 voters: `15`
- Distinct challenges: `162`
- Distinct targets: `20`
- Overall package choice rate: `32.0`
- Display-left choice rate: `51.33`

## By raw package / target FV ratio

| Ratio | Votes | Package chosen |
|---:|---:|---:|
| 1.10 | 54 | 9.3% |
| 1.25 | 66 | 13.6% |
| 1.40 | 66 | 43.9% |
| 1.60 | 63 | 47.6% |
| 1.85 | 51 | 45.1% |

## By package size

| Size | Votes | Package chosen |
|---:|---:|---:|
| 2 | 155 | 43.9% |
| 3 | 145 | 19.3% |

## Indifference bracketing

- Lowest tested ratio `1.1` package choice: `9.26`
- Highest tested ratio `1.85` package choice: `45.1`
- 50% empirically bracketed by tested endpoints: `False`

## Diagnostic gates

- All passed: `True`
- counted_votes: `True`
- unique_voters: `True`
- distinct_challenges: `True`
- distinct_targets: `True`
- choice_mix: `True`
- ratio_bucket_coverage: `True`
- package_size_coverage: `True`

## V2 reuse policy

- V2 remains frozen and is never relabeled as V3.
- V3-only data is the primary indifference calibration dataset.
- V2 may be pooled only in a separately labeled lower-ratio sensitivity analysis.

## Isolation

- V3 rows use reserved `__pkgv3__` transport markers.
- V3 does not alter KTC, Market Value, Fundamental Value, Team Utility, or the live trade verdict.

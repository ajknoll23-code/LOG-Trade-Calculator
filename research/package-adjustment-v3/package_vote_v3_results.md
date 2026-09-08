# Package Preference Voting V3 — Indifference Calibration

**Status: RESEARCH ONLY — no production consumer changed.**

V3 estimates how much raw FV a multi-player package must contain before voters are indifferent to the concentrated target asset.

- Counted V3 votes: `0`
- Unique V3 voters: `0`
- Distinct challenges: `0`
- Distinct targets: `0`
- Overall package choice rate: `None`
- Display-left choice rate: `None`

## By raw package / target FV ratio

| Ratio | Votes | Package chosen |
|---:|---:|---:|
| 1.10 | 0 | n/a |
| 1.25 | 0 | n/a |
| 1.40 | 0 | n/a |
| 1.60 | 0 | n/a |
| 1.85 | 0 | n/a |

## By package size

| Size | Votes | Package chosen |
|---:|---:|---:|
| 2 | 0 | n/a |
| 3 | 0 | n/a |

## Indifference bracketing

- Lowest tested ratio `1.1` package choice: `None`
- Highest tested ratio `1.85` package choice: `None`
- 50% empirically bracketed by tested endpoints: `False`

## Diagnostic gates

- All passed: `False`
- counted_votes: `False`
- unique_voters: `False`
- distinct_challenges: `False`
- distinct_targets: `False`
- choice_mix: `False`
- ratio_bucket_coverage: `False`
- package_size_coverage: `False`

## V2 reuse policy

- V2 remains frozen and is never relabeled as V3.
- V3-only data is the primary indifference calibration dataset.
- V2 may be pooled only in a separately labeled lower-ratio sensitivity analysis.

## Isolation

- V3 rows use reserved `__pkgv3__` transport markers.
- V3 does not alter KTC, Market Value, Fundamental Value, Team Utility, or the live trade verdict.

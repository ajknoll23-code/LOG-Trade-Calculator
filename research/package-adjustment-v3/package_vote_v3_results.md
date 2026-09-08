# Package Preference Voting V3 — Indifference Calibration

**Status: RESEARCH ONLY — no production consumer changed.**

V3 estimates how much raw FV a multi-player package must contain before voters are indifferent to the concentrated target asset.

- Counted V3 votes: `140`
- Unique V3 voters: `7`
- Distinct challenges: `106`
- Distinct targets: `20`
- Overall package choice rate: `35.71`
- Display-left choice rate: `54.29`

## By raw package / target FV ratio

| Ratio | Votes | Package chosen |
|---:|---:|---:|
| 1.10 | 25 | 12.0% |
| 1.25 | 32 | 15.6% |
| 1.40 | 33 | 57.6% |
| 1.60 | 27 | 48.1% |
| 1.85 | 23 | 43.5% |

## By package size

| Size | Votes | Package chosen |
|---:|---:|---:|
| 2 | 69 | 47.8% |
| 3 | 71 | 23.9% |

## Indifference bracketing

- Lowest tested ratio `1.1` package choice: `12.0`
- Highest tested ratio `1.85` package choice: `43.48`
- 50% empirically bracketed by tested endpoints: `False`

## Diagnostic gates

- All passed: `False`
- counted_votes: `False`
- unique_voters: `False`
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

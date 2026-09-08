# Package Preference Voting V3 — Indifference Calibration

**Status: RESEARCH ONLY — no production consumer changed.**

V3 estimates how much raw FV a multi-player package must contain before voters are indifferent to the concentrated target asset.

- Counted V3 votes: `240`
- Unique V3 voters: `12`
- Distinct challenges: `145`
- Distinct targets: `20`
- Overall package choice rate: `32.5`
- Display-left choice rate: `51.67`

## By raw package / target FV ratio

| Ratio | Votes | Package chosen |
|---:|---:|---:|
| 1.10 | 47 | 8.5% |
| 1.25 | 54 | 14.8% |
| 1.40 | 53 | 49.1% |
| 1.60 | 47 | 46.8% |
| 1.85 | 39 | 46.1% |

## By package size

| Size | Votes | Package chosen |
|---:|---:|---:|
| 2 | 121 | 43.8% |
| 3 | 119 | 21.0% |

## Indifference bracketing

- Lowest tested ratio `1.1` package choice: `8.51`
- Highest tested ratio `1.85` package choice: `46.15`
- 50% empirically bracketed by tested endpoints: `False`

## Diagnostic gates

- All passed: `False`
- counted_votes: `True`
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

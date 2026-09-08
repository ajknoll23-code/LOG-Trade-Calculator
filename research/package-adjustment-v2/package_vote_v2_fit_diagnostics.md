# Package Vote V2 Fit Diagnostics

**Status: RESEARCH ONLY — no production consumer changed.**

V2 uses matched secondary splits: `[A,B]` versus `[A,C,D]` around the same target and raw FV ratio.

- Counted votes: `120`
- Unique voters: `12`
- Distinct challenges: `96`
- Matched pairs with both sizes observed: `23`

## Diagnostic conclusion

- Status: `hold_research`
- Lowest-AIC candidate: `ratio_only`
- Production promotion allowed: `False`

Warnings:
- FG penalty sign is not yet stable across voter clusters

## Candidate model comparison

| Model | AIC | coefficients |
|---|---:|---|
| ratio_only | 121.02 | `{'intercept': -1.5544862614008657, 'log_ratio': 0.985742713698728}` |
| ratio_plus_size | 121.99 | `{'intercept': -1.3010233439736054, 'log_ratio': 0.831645779740615, 'size3': -0.475012131271778}` |
| ratio_plus_fg | 122.91 | `{'intercept': -1.9057988517890037, 'log_ratio': 1.3394351003170493, 'fg': 1.7397636909338645}` |
| ratio_plus_size_plus_fg | 123.57 | `{'intercept': -1.979275046037933, 'log_ratio': 1.534423485706743, 'size3': -0.5664664773467734, 'fg': 3.5986224983203328}` |

## Incremental tests

- Add size to ratio-only: LR `1.034`, p `0.30929946092839594`
- Add FG to ratio-only: LR `0.110`, p `0.7399046557074209`

## Voter-cluster bootstrap

- Reps: `400`
- size3 negative: `87.8%`
- FG negative: `27.0%`
- raw-ratio coefficient positive: `86.2%`
- size3 median: `-0.5650805665039286` (5–95% `-1.5381326851215822`–`0.23114264519803793`)
- FG median: `3.70840599576998` (5–95% `-4.291348505708452`–`13.331740380431638`)

## Matched-pair design check

- Pairs with both sizes observed: `23`
- 3-player package chosen less often: `3` pairs
- 3-player package chosen more often: `2` pairs
- ties: `18` pairs
- median 3-player minus 2-player package-choice difference: `0.0` pp

## Matched-pair fixed effects

- Eligible pairs: `23`
- Votes: `57`
- size3 coefficient: `-1.546375389794097`
- FG coefficient: `30.0`

## Guardrails

- V1 remains frozen and is never refit as V2.
- V2 challenge values and matched metadata remain hidden from voters.
- Bootstrap resamples whole voters.
- No model in this report changes the live calculator.

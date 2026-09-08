# Package Preference Voting V2

**Status: RESEARCH ONLY — no production consumer changed.**

V2 is a frozen matched-secondary-split design: each matched pair compares `[A, B]` against `[A, C, D]` around the same target and raw FV ratio.

- Counted package votes: `90`
- Unique voters: `9`
- Distinct challenges: `80`
- Package choice rate: `18.89`
- Display-left choice rate: `52.22`
- Matched pairs with both sizes observed: `14` / `84`

## By package size

| Size | Votes | Package chosen |
|---:|---:|---:|
| 2 | 43 | 23.3% |
| 3 | 47 | 14.9% |

## By raw package / target FV ratio

| Ratio | Votes | Package chosen |
|---:|---:|---:|
| 0.95 | 20 | 10.0% |
| 1.05 | 22 | 9.1% |
| 1.15 | 17 | 35.3% |
| 1.30 | 31 | 22.6% |

## Diagnostic gates

- All passed: `False`
- counted_votes: `False`
- unique_voters: `False`
- distinct_challenges: `True`
- matched_pairs_with_both_sizes: `False`
- choice_mix: `False`

## Isolation

- V2 rows use reserved `__pkgv2__` transport markers.
- V1 remains frozen and analytically separate.
- V2 package votes do not alter KTC, Market Value, Fundamental Value, Team Utility, or the live trade verdict.

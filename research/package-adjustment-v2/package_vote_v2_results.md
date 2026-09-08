# Package Preference Voting V2

**Status: RESEARCH ONLY — no production consumer changed.**

V2 is a frozen matched-secondary-split design: each matched pair compares `[A, B]` against `[A, C, D]` around the same target and raw FV ratio.

- Counted package votes: `20`
- Unique voters: `2`
- Distinct challenges: `20`
- Package choice rate: `15.0`
- Display-left choice rate: `50.0`
- Matched pairs with both sizes observed: `1` / `84`

## By package size

| Size | Votes | Package chosen |
|---:|---:|---:|
| 2 | 11 | 9.1% |
| 3 | 9 | 22.2% |

## By raw package / target FV ratio

| Ratio | Votes | Package chosen |
|---:|---:|---:|
| 0.95 | 5 | 0.0% |
| 1.05 | 7 | 14.3% |
| 1.15 | 4 | 50.0% |
| 1.30 | 4 | 0.0% |

## Diagnostic gates

- All passed: `False`
- counted_votes: `False`
- unique_voters: `False`
- distinct_challenges: `False`
- matched_pairs_with_both_sizes: `False`
- choice_mix: `False`

## Isolation

- V2 rows use reserved `__pkgv2__` transport markers.
- V1 remains frozen and analytically separate.
- V2 package votes do not alter KTC, Market Value, Fundamental Value, Team Utility, or the live trade verdict.

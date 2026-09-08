# Package Preference Voting V2

**Status: RESEARCH ONLY — no production consumer changed.**

V2 is a frozen matched-secondary-split design: each matched pair compares `[A, B]` against `[A, C, D]` around the same target and raw FV ratio.

- Counted package votes: `0`
- Unique voters: `0`
- Distinct challenges: `0`
- Package choice rate: `None`
- Display-left choice rate: `None`
- Matched pairs with both sizes observed: `0` / `84`

## By package size

| Size | Votes | Package chosen |
|---:|---:|---:|
| 2 | 0 | n/a |
| 3 | 0 | n/a |

## By raw package / target FV ratio

| Ratio | Votes | Package chosen |
|---:|---:|---:|
| 0.95 | 0 | n/a |
| 1.05 | 0 | n/a |
| 1.15 | 0 | n/a |
| 1.30 | 0 | n/a |

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

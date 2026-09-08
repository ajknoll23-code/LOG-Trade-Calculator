# Package Preference Voting V2

**Status: RESEARCH ONLY — no production consumer changed.**

V2 is a frozen matched-secondary-split design: each matched pair compares `[A, B]` against `[A, C, D]` around the same target and raw FV ratio.

- Counted package votes: `110`
- Unique voters: `11`
- Distinct challenges: `92`
- Package choice rate: `18.18`
- Display-left choice rate: `48.18`
- Matched pairs with both sizes observed: `21` / `84`

## By package size

| Size | Votes | Package chosen |
|---:|---:|---:|
| 2 | 52 | 21.1% |
| 3 | 58 | 15.5% |

## By raw package / target FV ratio

| Ratio | Votes | Package chosen |
|---:|---:|---:|
| 0.95 | 22 | 13.6% |
| 1.05 | 30 | 10.0% |
| 1.15 | 23 | 30.4% |
| 1.30 | 35 | 20.0% |

## Diagnostic gates

- All passed: `False`
- counted_votes: `False`
- unique_voters: `True`
- distinct_challenges: `True`
- matched_pairs_with_both_sizes: `True`
- choice_mix: `True`

## Isolation

- V2 rows use reserved `__pkgv2__` transport markers.
- V1 remains frozen and analytically separate.
- V2 package votes do not alter KTC, Market Value, Fundamental Value, Team Utility, or the live trade verdict.

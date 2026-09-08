# Package Preference Voting V2

**Status: RESEARCH ONLY — no production consumer changed.**

V2 is a frozen matched-secondary-split design: each matched pair compares `[A, B]` against `[A, C, D]` around the same target and raw FV ratio.

- Counted package votes: `50`
- Unique voters: `5`
- Distinct challenges: `48`
- Package choice rate: `18.0`
- Display-left choice rate: `52.0`
- Matched pairs with both sizes observed: `6` / `84`

## By package size

| Size | Votes | Package chosen |
|---:|---:|---:|
| 2 | 29 | 17.2% |
| 3 | 21 | 19.1% |

## By raw package / target FV ratio

| Ratio | Votes | Package chosen |
|---:|---:|---:|
| 0.95 | 14 | 7.1% |
| 1.05 | 12 | 8.3% |
| 1.15 | 9 | 44.4% |
| 1.30 | 15 | 20.0% |

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

# Package Preference Voting V2

**Status: RESEARCH ONLY — no production consumer changed.**

V2 is a frozen matched-secondary-split design: each matched pair compares `[A, B]` against `[A, C, D]` around the same target and raw FV ratio.

- Counted package votes: `120`
- Unique voters: `12`
- Distinct challenges: `96`
- Package choice rate: `19.17`
- Display-left choice rate: `50.0`
- Matched pairs with both sizes observed: `23` / `84`

## By package size

| Size | Votes | Package chosen |
|---:|---:|---:|
| 2 | 56 | 23.2% |
| 3 | 64 | 15.6% |

## By raw package / target FV ratio

| Ratio | Votes | Package chosen |
|---:|---:|---:|
| 0.95 | 25 | 20.0% |
| 1.05 | 33 | 9.1% |
| 1.15 | 25 | 32.0% |
| 1.30 | 37 | 18.9% |

## Diagnostic gates

- All passed: `True`
- counted_votes: `True`
- unique_voters: `True`
- distinct_challenges: `True`
- matched_pairs_with_both_sizes: `True`
- choice_mix: `True`

## Isolation

- V2 rows use reserved `__pkgv2__` transport markers.
- V1 remains frozen and analytically separate.
- V2 package votes do not alter KTC, Market Value, Fundamental Value, Team Utility, or the live trade verdict.

# Market Value V2 — Blended KTC Shadow

**Status: RESEARCH ONLY / SHADOW. Market Value V1 remains deployed.**

## Policy

- League voter multiplier: `1.00`
- Primary guest voter multiplier: `0.50`
- Per-voter lifetime cap before group weighting: `30` ballots
- KTC daily cap: `20` ballots per voter per UTC day
- Package Preference rows are excluded before KTC market processing.
- Guest browser identities are not verified unique people, so guest influence is both capped and discounted.
- Fundamental Value, Team Utility, live verdicts, and deployed Market Value V1 are unchanged.

## Current evidence mass at primary 0.50 guest weight

- League voters: `10`
- Guest voters: `11`
- Raw league ballots: `449`
- Raw guest ballots: `204`
- Effective league ballots: `192.0` (`66.4%`)
- Effective guest ballots: `97.0` (`33.6%`)
- Resolved V2 market players: `492`

## What guests change

This comparison holds the per-voter league balancing policy constant and changes only guest weight from 0.00 to 0.50.

- Common players: `469`
- Rank correlation: `0.893983`
- Median absolute value change: `224.0`
- 90th-percentile absolute change: `1104.6`
- Maximum absolute change: `2224.0`

| Player | V2 0.50 | Balanced league-only shadow | Guest effect | Rank change |
|---|---:|---:|---:|---:|
| jamien sherwood | 1034 | 3258 | -2224 | -286.0 |
| dorian williams | 8895 | 6679 | +2216 | +1.0 |
| budda baker | 3605 | 1438 | +2167 | +235.0 |
| deforest buckner | 950 | 3081 | -2131 | -269.0 |
| tyrel dodson | 1077 | 3153 | -2076 | -255.0 |
| terrel bernard | 4581 | 6564 | -1983 | -49.0 |
| cody simon | 3889 | 1966 | +1923 | +231.0 |
| aj barner | 842 | 2721 | -1879 | -232.0 |
| akheem mesidor | 3243 | 1388 | +1855 | +197.0 |
| malachi lawrence | 3286 | 1474 | +1812 | +192.0 |
| alex singleton | 1438 | 3141 | -1703 | -209.0 |
| dillon thieneman | 3936 | 5623 | -1687 | -84.0 |
| klavon chaisson | 1965 | 3618 | -1653 | -236.0 |
| jalen nailor | 3162 | 1543 | +1619 | +176.0 |
| colston loveland | 4770 | 3157 | +1613 | +125.0 |
| dallas goedert | 3421 | 1897 | +1524 | +187.0 |
| tucker kraft | 5155 | 3631 | +1524 | +85.0 |
| derick hall | 1210 | 2729 | -1519 | -172.0 |
| alvin kamara | 3526 | 2010 | +1516 | +183.0 |
| arvell reese | 5538 | 4050 | +1488 | +60.0 |

## V2 shadow vs deployed Market Value V1

- Common players: `469`
- Rank correlation: `0.801231`
- Median absolute value change: `529.0`
- 90th-percentile absolute change: `1399.2`
- Maximum absolute change: `3768.0`

| Player | V2 shadow | Deployed V1 | Difference | Rank change |
|---|---:|---:|---:|---:|
| xavier worthy | 8563 | 4795 | +3768 | +30.0 |
| tucker kraft | 5155 | 8895 | -3740 | -21.0 |
| dorian williams | 8895 | 5493 | +3402 | +9.0 |
| bhayshul tuten | 3348 | 6679 | -3331 | -156.0 |
| jamien sherwood | 1034 | 3702 | -2668 | -339.0 |
| jadeveon clowney | 3791 | 1189 | +2602 | +282.0 |
| cody simon | 3889 | 1412 | +2477 | +268.0 |
| devon witherspoon | 5655 | 3273 | +2382 | +144.0 |
| dallas goedert | 3421 | 1079 | +2342 | +254.0 |
| tyrel dodson | 1077 | 3348 | -2271 | -277.0 |
| eric wilson | 4426 | 2216 | +2210 | +237.0 |
| fernando mendoza | 7148 | 4952 | +2196 | +20.0 |
| aj brown | 5852 | 3739 | +2113 | +92.0 |
| christian mccaffrey | 5623 | 3585 | +2038 | +106.0 |
| alvin kamara | 3526 | 1501 | +2025 | +221.0 |
| brenton strange | 3431 | 1410 | +2021 | +220.0 |
| bobby okereke | 3079 | 1077 | +2002 | +203.0 |
| trey hendrickson | 2026 | 3990 | -1964 | -259.0 |
| jonathon cooper | 2002 | 3948 | -1946 | -259.0 |
| christian rozeboom | 643 | 2534 | -1891 | -232.0 |

## Guest-weight sensitivity

| Guest weight | League effective | Guest effective | Guest share | Resolved | Rank corr vs 0.50 | Median abs Δ | P90 abs Δ | Max abs Δ |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 192.0 | 0.0 | 0.0% | 469 | 0.893983 | 224.0 | 1104.6 | 2224.0 |
| 0.25 | 192.0 | 48.5 | 20.2% | 492 | 0.986147 | 86.0 | 426.5 | 836.0 |
| 0.50 | 192.0 | 97.0 | 33.6% | 492 | 1.0 | 0.0 | 0.0 | 0.0 |
| 0.75 | 192.0 | 145.5 | 43.1% | 492 | 0.993708 | 83.5 | 284.9 | 1999.0 |
| 1.00 | 192.0 | 194.0 | 50.3% | 492 | 0.980755 | 136.0 | 518.7 | 3118.0 |

## Guardrails

- This artifact cannot promote itself. `production_promotion_allowed` is hard-coded `false`.
- The primary 0.50 guest multiplier is a policy hypothesis, not a fitted truth.
- The sensitivity table is required specifically to show whether that policy choice materially changes rankings.
- Guest `ext_*` ids are browser-local identities; clearing browser storage can create a new identity. The cap and 0.50 discount limit this risk but do not eliminate it.
- V2 uses the same Bradley-Terry implementation and the same rank-to-FV quantile calibration concept as V1 so the experimental change is the voter weighting policy, not a new value scale.
- Largest effective voter at the primary setting: `4` (league), `10.38%` of effective ballot mass.

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
- Guest voters: `15`
- Raw league ballots: `449`
- Raw guest ballots: `284`
- Effective league ballots: `192.0` (`58.4%`)
- Effective guest ballots: `137.0` (`41.6%`)
- Resolved V2 market players: `496`

## What guests change

This comparison holds the per-voter league balancing policy constant and changes only guest weight from 0.00 to 0.50.

- Common players: `469`
- Rank correlation: `0.862593`
- Median absolute value change: `319.0`
- 90th-percentile absolute change: `1261.8`
- Maximum absolute change: `2711.0`

| Player | V2 0.50 | Balanced league-only shadow | Guest effect | Rank change |
|---|---:|---:|---:|---:|
| fernando mendoza | 8563 | 5852 | +2711 | +3.0 |
| trey hendrickson | 892 | 3455 | -2563 | -329.0 |
| alontae taylor | 2940 | 5351 | -2411 | -200.0 |
| tyrel dodson | 842 | 3153 | -2311 | -299.0 |
| terrel bernard | 4316 | 6564 | -2248 | -63.0 |
| dorian williams | 8895 | 6679 | +2216 | +1.0 |
| deforest buckner | 884 | 3081 | -2197 | -280.0 |
| budda baker | 3605 | 1438 | +2167 | +233.0 |
| leonard williams | 1273 | 3370 | -2097 | -259.0 |
| harold fannin | 6679 | 4662 | +2017 | +35.0 |
| alex singleton | 1210 | 3141 | -1931 | -237.0 |
| aj barner | 882 | 2721 | -1839 | -231.0 |
| dillon thieneman | 3794 | 5623 | -1829 | -95.0 |
| cody simon | 3775 | 1966 | +1809 | +219.0 |
| josh sweat | 4455 | 2657 | +1798 | +181.0 |
| akheem mesidor | 3136 | 1388 | +1748 | +177.0 |
| xavier worthy | 7148 | 8895 | -1747 | -2.0 |
| malachi lawrence | 3162 | 1474 | +1688 | +176.0 |
| drue tranquill | 3291 | 4962 | -1671 | -143.0 |
| ventrell miller | 2752 | 1082 | +1670 | +157.0 |

## V2 shadow vs deployed Market Value V1

- Common players: `469`
- Rank correlation: `0.799987`
- Median absolute value change: `572.0`
- 90th-percentile absolute change: `1350.2`
- Maximum absolute change: `3970.0`

| Player | V2 shadow | Deployed V1 | Difference | Rank change |
|---|---:|---:|---:|---:|
| tucker kraft | 4925 | 8895 | -3970 | -29.0 |
| fernando mendoza | 8563 | 4952 | +3611 | +21.0 |
| dorian williams | 8895 | 5493 | +3402 | +9.0 |
| trey hendrickson | 892 | 3990 | -3098 | -384.0 |
| bhayshul tuten | 3974 | 6679 | -2705 | -86.0 |
| tyrel dodson | 842 | 3348 | -2506 | -321.0 |
| cody simon | 3775 | 1412 | +2363 | +256.0 |
| leonard williams | 1273 | 3631 | -2358 | -294.0 |
| xavier worthy | 7148 | 4795 | +2353 | +29.0 |
| dallas goedert | 3419 | 1079 | +2340 | +250.0 |
| devon witherspoon | 5445 | 3273 | +2172 | +136.0 |
| jadeveon clowney | 3340 | 1189 | +2151 | +221.0 |
| christian mccaffrey | 5621 | 3585 | +2036 | +105.0 |
| kenyon sadiq | 4640 | 2675 | +1965 | +188.0 |
| alvin kamara | 3450 | 1501 | +1949 | +210.0 |
| brenton strange | 3348 | 1410 | +1938 | +204.0 |
| josh sweat | 4455 | 2558 | +1897 | +196.0 |
| henry tootoo | 1213 | 3074 | -1861 | -220.0 |
| brian branch | 3889 | 2030 | +1859 | +217.0 |
| devin white | 2789 | 4640 | -1851 | -195.0 |

## Guest-weight sensitivity

| Guest weight | League effective | Guest effective | Guest share | Resolved | Rank corr vs 0.50 | Median abs Δ | P90 abs Δ | Max abs Δ |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 192.0 | 0.0 | 0.0% | 469 | 0.862593 | 319.0 | 1261.8 | 2711.0 |
| 0.25 | 192.0 | 68.5 | 26.3% | 496 | 0.98253 | 134.0 | 476.5 | 1415.0 |
| 0.50 | 192.0 | 137.0 | 41.6% | 496 | 1.0 | 0.0 | 0.0 | 0.0 |
| 0.75 | 192.0 | 205.5 | 51.7% | 496 | 0.993038 | 85.0 | 301.5 | 1493.0 |
| 1.00 | 192.0 | 274.0 | 58.8% | 496 | 0.98103 | 137.0 | 472.5 | 1961.0 |

## Guardrails

- This artifact cannot promote itself. `production_promotion_allowed` is hard-coded `false`.
- The primary 0.50 guest multiplier is a policy hypothesis, not a fitted truth.
- The sensitivity table is required specifically to show whether that policy choice materially changes rankings.
- Guest `ext_*` ids are browser-local identities; clearing browser storage can create a new identity. The cap and 0.50 discount limit this risk but do not eliminate it.
- V2 uses the same Bradley-Terry implementation and the same rank-to-FV quantile calibration concept as V1 so the experimental change is the voter weighting policy, not a new value scale.
- Largest effective voter at the primary setting: `4` (league), `9.12%` of effective ballot mass.

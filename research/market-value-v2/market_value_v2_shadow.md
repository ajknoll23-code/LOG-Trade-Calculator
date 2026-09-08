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
- Guest voters: `18`
- Raw league ballots: `449`
- Raw guest ballots: `344`
- Effective league ballots: `192.0` (`53.5%`)
- Effective guest ballots: `167.0` (`46.5%`)
- Resolved V2 market players: `500`

## What guests change

This comparison holds the per-voter league balancing policy constant and changes only guest weight from 0.00 to 0.50.

- Common players: `469`
- Rank correlation: `0.845721`
- Median absolute value change: `373.0`
- 90th-percentile absolute change: `1341.2`
- Maximum absolute change: `3043.0`

| Player | V2 0.50 | Balanced league-only shadow | Guest effect | Rank change |
|---|---:|---:|---:|---:|
| fernando mendoza | 8895 | 5852 | +3043 | +4.0 |
| trey hendrickson | 825 | 3455 | -2630 | -345.0 |
| leonard williams | 1037 | 3370 | -2333 | -305.0 |
| dillon thieneman | 3292 | 5623 | -2331 | -161.0 |
| alontae taylor | 3030 | 5351 | -2321 | -195.0 |
| tyrel dodson | 884 | 3153 | -2269 | -297.0 |
| terrel bernard | 4316 | 6564 | -2248 | -66.0 |
| deforest buckner | 882 | 3081 | -2199 | -285.0 |
| drue tranquill | 2785 | 4962 | -2177 | -220.0 |
| budda baker | 3605 | 1438 | +2167 | +229.0 |
| malik willis | 7148 | 4985 | +2163 | +17.0 |
| chig okonkwo | 1573 | 3610 | -2037 | -263.0 |
| harold fannin | 6679 | 4662 | +2017 | +33.0 |
| xavier worthy | 6913 | 8895 | -1982 | -4.0 |
| sauce gardner | 1162 | 3058 | -1896 | -232.0 |
| dorian williams | 8563 | 6679 | +1884 | +0.0 |
| micah parsons | 7023 | 5155 | +1868 | +13.0 |
| alex singleton | 1303 | 3141 | -1838 | -231.0 |
| aj barner | 922 | 2721 | -1799 | -229.0 |
| cody simon | 3695 | 1966 | +1729 | +207.0 |

## V2 shadow vs deployed Market Value V1

- Common players: `469`
- Rank correlation: `0.805528`
- Median absolute value change: `523.0`
- 90th-percentile absolute change: `1382.4`
- Maximum absolute change: `3970.0`

| Player | V2 shadow | Deployed V1 | Difference | Rank change |
|---|---:|---:|---:|---:|
| tucker kraft | 4925 | 8895 | -3970 | -32.0 |
| fernando mendoza | 8895 | 4952 | +3943 | +22.0 |
| trey hendrickson | 825 | 3990 | -3165 | -400.0 |
| dorian williams | 8563 | 5493 | +3070 | +8.0 |
| bhayshul tuten | 3974 | 6679 | -2705 | -89.0 |
| leonard williams | 1037 | 3631 | -2594 | -340.0 |
| tyrel dodson | 884 | 3348 | -2464 | -319.0 |
| cody simon | 3695 | 1412 | +2283 | +244.0 |
| devon witherspoon | 5445 | 3273 | +2172 | +134.0 |
| dallas goedert | 3225 | 1079 | +2146 | +221.0 |
| sauce gardner | 1162 | 3306 | -2144 | -272.0 |
| xavier worthy | 6913 | 4795 | +2118 | +27.0 |
| kenyon sadiq | 4739 | 2675 | +2064 | +191.0 |
| christian mccaffrey | 5563 | 3585 | +1978 | +102.0 |
| jadeveon clowney | 3137 | 1189 | +1948 | +191.0 |
| brenton strange | 3348 | 1410 | +1938 | +200.0 |
| alvin kamara | 3431 | 1501 | +1930 | +205.0 |
| devin white | 2721 | 4640 | -1919 | -209.0 |
| henry tootoo | 1213 | 3074 | -1861 | -224.0 |
| kyle pitts | 3267 | 5087 | -1820 | -155.0 |

## Guest-weight sensitivity

| Guest weight | League effective | Guest effective | Guest share | Resolved | Rank corr vs 0.50 | Median abs Δ | P90 abs Δ | Max abs Δ |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 192.0 | 0.0 | 0.0% | 469 | 0.845721 | 373.0 | 1341.2 | 3043.0 |
| 0.25 | 192.0 | 83.5 | 30.3% | 500 | 0.981426 | 142.0 | 472.2 | 1747.0 |
| 0.50 | 192.0 | 167.0 | 46.5% | 500 | 1.0 | 0.0 | 0.0 | 0.0 |
| 0.75 | 192.0 | 250.5 | 56.6% | 500 | 0.99236 | 93.5 | 284.4 | 1350.0 |
| 1.00 | 192.0 | 334.0 | 63.5% | 500 | 0.980663 | 140.0 | 470.5 | 1827.0 |

## Guardrails

- This artifact cannot promote itself. `production_promotion_allowed` is hard-coded `false`.
- The primary 0.50 guest multiplier is a policy hypothesis, not a fitted truth.
- The sensitivity table is required specifically to show whether that policy choice materially changes rankings.
- Guest `ext_*` ids are browser-local identities; clearing browser storage can create a new identity. The cap and 0.50 discount limit this risk but do not eliminate it.
- V2 uses the same Bradley-Terry implementation and the same rank-to-FV quantile calibration concept as V1 so the experimental change is the voter weighting policy, not a new value scale.
- Largest effective voter at the primary setting: `4` (league), `8.36%` of effective ballot mass.

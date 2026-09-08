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
- Guest voters: `19`
- Raw league ballots: `449`
- Raw guest ballots: `364`
- Effective league ballots: `192.0` (`52.0%`)
- Effective guest ballots: `177.0` (`48.0%`)
- Resolved V2 market players: `500`

## What guests change

This comparison holds the per-voter league balancing policy constant and changes only guest weight from 0.00 to 0.50.

- Common players: `469`
- Rank correlation: `0.838093`
- Median absolute value change: `386.0`
- 90th-percentile absolute change: `1373.4`
- Maximum absolute change: `3043.0`

| Player | V2 0.50 | Balanced league-only shadow | Guest effect | Rank change |
|---|---:|---:|---:|---:|
| fernando mendoza | 8895 | 5852 | +3043 | +4.0 |
| arvell reese | 6913 | 4050 | +2863 | +67.0 |
| trey hendrickson | 734 | 3455 | -2721 | -359.0 |
| alontae taylor | 2990 | 5351 | -2361 | -198.0 |
| dillon thieneman | 3291 | 5623 | -2332 | -162.0 |
| leonard williams | 1046 | 3370 | -2324 | -303.0 |
| chig okonkwo | 1303 | 3610 | -2307 | -291.0 |
| tyrel dodson | 906 | 3153 | -2247 | -293.0 |
| terrel bernard | 4347 | 6564 | -2217 | -65.0 |
| xavier worthy | 6679 | 8895 | -2216 | -5.0 |
| deforest buckner | 896 | 3081 | -2185 | -281.0 |
| drue tranquill | 2785 | 4962 | -2177 | -220.0 |
| malik willis | 7148 | 4985 | +2163 | +17.0 |
| budda baker | 3559 | 1438 | +2121 | +223.0 |
| cooper dejean | 1555 | 3644 | -2089 | -272.0 |
| aj barner | 798 | 2721 | -1923 | -247.0 |
| sauce gardner | 1150 | 3058 | -1908 | -233.0 |
| harold fannin | 6564 | 4662 | +1902 | +32.0 |
| dorian williams | 8563 | 6679 | +1884 | +0.0 |
| micah parsons | 7023 | 5155 | +1868 | +13.0 |

## V2 shadow vs deployed Market Value V1

- Common players: `469`
- Rank correlation: `0.805332`
- Median absolute value change: `519.0`
- 90th-percentile absolute change: `1382.4`
- Maximum absolute change: `3943.0`

| Player | V2 shadow | Deployed V1 | Difference | Rank change |
|---|---:|---:|---:|---:|
| fernando mendoza | 8895 | 4952 | +3943 | +22.0 |
| tucker kraft | 4985 | 8895 | -3910 | -28.0 |
| trey hendrickson | 734 | 3990 | -3256 | -414.0 |
| dorian williams | 8563 | 5493 | +3070 | +8.0 |
| bhayshul tuten | 3980 | 6679 | -2699 | -88.0 |
| leonard williams | 1046 | 3631 | -2585 | -338.0 |
| tyrel dodson | 906 | 3348 | -2442 | -315.0 |
| arvell reese | 6913 | 4604 | +2309 | +38.0 |
| cody simon | 3625 | 1412 | +2213 | +239.0 |
| dallas goedert | 3241 | 1079 | +2162 | +223.0 |
| sauce gardner | 1150 | 3306 | -2156 | -273.0 |
| kenyon sadiq | 4739 | 2675 | +2064 | +191.0 |
| brenton strange | 3377 | 1410 | +1967 | +204.0 |
| christian mccaffrey | 5538 | 3585 | +1953 | +101.0 |
| jadeveon clowney | 3136 | 1189 | +1947 | +190.0 |
| alvin kamara | 3419 | 1501 | +1918 | +203.0 |
| devin white | 2735 | 4640 | -1905 | -206.0 |
| xavier worthy | 6679 | 4795 | +1884 | +26.0 |
| henry tootoo | 1210 | 3074 | -1864 | -226.0 |
| kyle pitts | 3273 | 5087 | -1814 | -153.0 |

## Guest-weight sensitivity

| Guest weight | League effective | Guest effective | Guest share | Resolved | Rank corr vs 0.50 | Median abs Δ | P90 abs Δ | Max abs Δ |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 192.0 | 0.0 | 0.0% | 469 | 0.838093 | 386.0 | 1373.4 | 3043.0 |
| 0.25 | 192.0 | 88.5 | 31.6% | 500 | 0.981595 | 149.0 | 485.2 | 1884.0 |
| 0.50 | 192.0 | 177.0 | 48.0% | 500 | 1.0 | 0.0 | 0.0 | 0.0 |
| 0.75 | 192.0 | 265.5 | 58.0% | 500 | 0.992793 | 85.0 | 286.1 | 1141.0 |
| 1.00 | 192.0 | 354.0 | 64.8% | 500 | 0.980918 | 142.5 | 454.1 | 1667.0 |

## Guardrails

- This artifact cannot promote itself. `production_promotion_allowed` is hard-coded `false`.
- The primary 0.50 guest multiplier is a policy hypothesis, not a fitted truth.
- The sensitivity table is required specifically to show whether that policy choice materially changes rankings.
- Guest `ext_*` ids are browser-local identities; clearing browser storage can create a new identity. The cap and 0.50 discount limit this risk but do not eliminate it.
- V2 uses the same Bradley-Terry implementation and the same rank-to-FV quantile calibration concept as V1 so the experimental change is the voter weighting policy, not a new value scale.
- Largest effective voter at the primary setting: `4` (league), `8.13%` of effective ballot mass.

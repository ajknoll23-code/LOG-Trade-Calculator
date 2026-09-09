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
- Guest voters: `20`
- Raw league ballots: `469`
- Raw guest ballots: `392`
- Effective league ballots: `192.0` (`50.1%`)
- Effective guest ballots: `191.0` (`49.9%`)
- Resolved V2 market players: `502`

## What guests change

This comparison holds the per-voter league balancing policy constant and changes only guest weight from 0.00 to 0.50.

- Common players: `476`
- Rank correlation: `0.832528`
- Median absolute value change: `400.0`
- 90th-percentile absolute change: `1372.0`
- Maximum absolute change: `3581.0`

| Player | V2 0.50 | Balanced league-only shadow | Guest effect | Rank change |
|---|---:|---:|---:|---:|
| sonny styles | 8556 | 4975 | +3581 | +21.0 |
| arvell reese | 6913 | 3777 | +3136 | +92.0 |
| fernando mendoza | 8888 | 5984 | +2904 | +3.0 |
| trey hendrickson | 734 | 3450 | -2716 | -354.0 |
| leonard williams | 905 | 3340 | -2435 | -310.0 |
| terrel bernard | 4295 | 6673 | -2378 | -69.0 |
| xavier worthy | 6564 | 8888 | -2324 | -6.0 |
| dillon thieneman | 3162 | 5445 | -2283 | -173.0 |
| alontae taylor | 2832 | 4984 | -2152 | -210.0 |
| deforest buckner | 864 | 3003 | -2139 | -274.0 |
| malik willis | 7023 | 4925 | +2098 | +22.0 |
| cooper dejean | 1555 | 3631 | -2076 | -268.0 |
| alex singleton | 1454 | 3526 | -2072 | -259.0 |
| tyrel dodson | 1073 | 3140 | -2067 | -262.0 |
| drue tranquill | 2794 | 4829 | -2035 | -209.0 |
| aj barner | 783 | 2779 | -1996 | -252.0 |
| chig okonkwo | 1077 | 2990 | -1913 | -236.0 |
| sauce gardner | 1169 | 3080 | -1911 | -231.0 |
| jameson williams | 3450 | 1573 | +1877 | +206.0 |
| demarvion overshown | 3136 | 1282 | +1854 | +188.0 |

## V2 shadow vs deployed Market Value V1

- Common players: `476`
- Rank correlation: `0.808612`
- Median absolute value change: `508.0`
- 90th-percentile absolute change: `1396.0`
- Maximum absolute change: `3976.0`

| Player | V2 shadow | Deployed V1 | Difference | Rank change |
|---|---:|---:|---:|---:|
| fernando mendoza | 8888 | 4912 | +3976 | +26.0 |
| sonny styles | 8556 | 4925 | +3631 | +24.0 |
| jeremiyah love | 5538 | 8888 | -3350 | -14.0 |
| trey hendrickson | 734 | 3991 | -3257 | -413.0 |
| leonard williams | 905 | 3671 | -2766 | -354.0 |
| arvell reese | 6913 | 4581 | +2332 | +42.0 |
| tyrel dodson | 1073 | 3286 | -2213 | -282.0 |
| cody simon | 3618 | 1412 | +2206 | +242.0 |
| sauce gardner | 1169 | 3340 | -2171 | -266.0 |
| dallas goedert | 3225 | 1102 | +2123 | +224.0 |
| brenton strange | 3350 | 1410 | +1940 | +206.0 |
| abdul carter | 5621 | 3713 | +1908 | +92.0 |
| kyle pitts | 3270 | 5155 | -1885 | -156.0 |
| christian mccaffrey | 5491 | 3610 | +1881 | +98.0 |
| alontae taylor | 2832 | 4704 | -1872 | -192.0 |
| kenyon sadiq | 4581 | 2710 | +1871 | +181.0 |
| devin white | 2776 | 4640 | -1864 | -203.0 |
| henry tootoo | 1210 | 3074 | -1864 | -223.0 |
| jadeveon clowney | 3058 | 1197 | +1861 | +179.0 |
| jaylen warren | 4229 | 2386 | +1843 | +208.0 |

## Guest-weight sensitivity

| Guest weight | League effective | Guest effective | Guest share | Resolved | Rank corr vs 0.50 | Median abs Δ | P90 abs Δ | Max abs Δ |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 192.0 | 0.0 | 0.0% | 476 | 0.832528 | 400.0 | 1372.0 | 3581.0 |
| 0.25 | 192.0 | 95.5 | 33.2% | 502 | 0.982543 | 160.0 | 465.2 | 1992.0 |
| 0.50 | 192.0 | 191.0 | 49.9% | 502 | 1.0 | 0.0 | 0.0 | 0.0 |
| 0.75 | 192.0 | 286.5 | 59.9% | 502 | 0.993066 | 89.5 | 267.9 | 1377.0 |
| 1.00 | 192.0 | 382.0 | 66.5% | 502 | 0.981349 | 145.5 | 439.0 | 1938.0 |

## Guardrails

- This artifact cannot promote itself. `production_promotion_allowed` is hard-coded `false`.
- The primary 0.50 guest multiplier is a policy hypothesis, not a fitted truth.
- The sensitivity table is required specifically to show whether that policy choice materially changes rankings.
- Guest `ext_*` ids are browser-local identities; clearing browser storage can create a new identity. The cap and 0.50 discount limit this risk but do not eliminate it.
- V2 uses the same Bradley-Terry implementation and the same rank-to-FV quantile calibration concept as V1 so the experimental change is the voter weighting policy, not a new value scale.
- Largest effective voter at the primary setting: `4` (league), `7.83%` of effective ballot mass.

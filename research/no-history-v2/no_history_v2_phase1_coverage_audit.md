# No-History / Rookie Value V2 — Phase 1 Coverage Audit

Method: `no-history-rookie-v2-phase1-coverage-v1`  
Status: **`RESEARCH_ONLY_COVERAGE_AUDIT_NO_VALUE_CHANGES`**

## Guardrail

**Research only. No player value, Production V2 coefficient, Market Value, or `index.html` production constant is changed by this audit.**

Production V2 already handles forward/history estimation for most players. This phase only identifies the young/no-history cohort that could justify a separate prospect prior later.

## Coverage summary

- Tracked players: **549**
- No-real-history players: **108**
- Prospect-prior eligible: **95**
- Eligible with normal Production V2 candidate: **86**
- Eligible missing Production V2 candidate: **9**
- Eligible with Sleeper ID: **95 (100.0%)**
- Eligible with years experience: **95 (100.0%)**
- Eligible with nflverse draft pick: **88 (92.6%)**
- Eligible with Sleeper depth-chart order: **89 (93.7%)**

### No-history experience classes

- `rookie`: **92**
- `second_year`: **3**
- `unknown`: **1**
- `veteran`: **12**

## By position

| Pos | Tracked | No history | Eligible | V2 candidate | Missing V2 | Sleeper ID | Draft pick | Depth order |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| QB | 64 | 15 | 11 | 7 | 4 | 11 | 10 | 10 |
| RB | 97 | 20 | 16 | 14 | 2 | 16 | 13 | 12 |
| WR | 114 | 29 | 27 | 27 | 0 | 27 | 27 | 27 |
| TE | 44 | 10 | 10 | 10 | 0 | 10 | 8 | 9 |
| DL | 86 | 12 | 11 | 11 | 0 | 11 | 11 | 11 |
| LB | 79 | 15 | 13 | 11 | 2 | 13 | 12 | 13 |
| DB | 65 | 7 | 7 | 6 | 1 | 7 | 7 | 7 |

## Prospect-prior eligible players

| Player | Pos | Age | Exp | Draft | Pick | Current FV | V2 candidate | Depth | Sleeper resolution |
|---|---|---:|---|---:|---:|---:|---|---:|---|
| mansoor delane | DB | 22 | rookie | 2026 | 6 | 2048 | yes | 1 | identity_crosswalk |
| dillon thieneman | DB | 22 | rookie | 2026 | 25 | 2346 | yes | 1 | identity_crosswalk |
| treydan stukes | DB | 24 | rookie | 2026 | 38 | 2101 | yes | 2 | identity_crosswalk |
| dangelo ponds | DB | 21 | rookie | 2026 | 50 | 670 | yes | 1 | identity_crosswalk |
| emmanuel mcneilwarren | DB | 22 | rookie | 2026 | 58 | 827 | yes | 2 | unique_name_position |
| aj haulcy | DB | 22 | rookie | 2026 | 78 | 1150 | yes | 1 | identity_crosswalk |
| david bailey | DL | 22 | rookie | 2026 | 2 | 2374 | yes | 1 | identity_crosswalk |
| rueben bain | DL | 21 | rookie | 2026 | 15 | 2026 | yes | 1 | unique_name_position |
| akheem mesidor | DL | 25 | rookie | 2026 | 22 | 2290 | yes | 2 | identity_crosswalk |
| malachi lawrence | DL | 23 | rookie | 2026 | 23 | 1855 | yes | 3 | identity_crosswalk |
| peter woods | DL | 21 | rookie | 2026 | 29 | 884 | yes | 2 | identity_crosswalk |
| keldric faulk | DL | 20 | rookie | 2026 | 31 | 892 | yes | 2 | identity_crosswalk |
| kayden mcdonald | DL | 21 | rookie | 2026 | 36 | 643 | yes | 2 | unique_name_position |
| r mason thomas | DL | 21 | rookie | 2026 | 40 | 1176 | yes | 2 | identity_crosswalk |
| cashius howell | DL | 23 | rookie | 2026 | 41 | 965 | yes | 2 | unique_name_position |
| derrick moore | DL | 23 | rookie | 2026 | 44 | 2239 | yes | 2 | unique_name_position |
| zion young | DL | 22 | rookie | 2026 | 45 | 1044 | yes | 2 | identity_crosswalk |
| arvell reese | LB | 20 | rookie | 2026 | 5 | 2465 | yes | 1 | identity_crosswalk |
| sonny styles | LB | 21 | rookie | 2026 | 7 | 3273 | yes | 1 | identity_crosswalk |
| jacob rodriguez | LB | 23 | rookie | 2026 | 43 | 1682 | yes | 1 | identity_crosswalk |
| josiah trotter | LB | 21 | rookie | 2026 | 46 | 924 | yes | 1 | identity_crosswalk |
| jake golday | LB | 23 | rookie | 2026 | 51 | 1162 | yes | 2 | identity_crosswalk |
| cj allen | LB | 21 | rookie | 2026 | 53 | 2021 | yes | 1 | identity_crosswalk |
| anthony hill | LB | 21 | rookie | 2026 | 60 | 889 | yes | 2 | unique_name_position |
| jaishawn barham | LB | 22 | rookie | 2026 | 92 | 968 | yes | 2 | identity_crosswalk |
| kaleb elarmsorr | LB | 22 | rookie | 2026 | 126 | 968 | yes | 2 | identity_crosswalk |
| bryce boettcher | LB | 24 | rookie | 2026 | 135 | 1355 | yes | 2 | identity_crosswalk |
| kyle louis | LB | 22 | rookie | 2026 | 138 | 968 | yes | 2 | identity_crosswalk |
| fernando mendoza | QB | 22 | rookie | 2026 | 1 | 2150 | yes | 2 | identity_crosswalk |
| ty simpson | QB | 23 | rookie | 2026 | 13 | 1169 | yes | 2 | identity_crosswalk |
| carson beck | QB | 24 | rookie | 2026 | 65 | 1303 | yes | 3 | identity_crosswalk |
| drew allar | QB | 22 | rookie | 2026 | 76 | 1034 | yes | 2 | identity_crosswalk |
| cade klubnik | QB | 22 | rookie | 2026 | 110 | 1034 | yes | 2 | identity_crosswalk |
| cole payton | QB | 23 | rookie | 2026 | 178 | 1169 | yes | 4 | identity_crosswalk |
| will howard | QB | 24 | second_year | 2025 | 185 | 1303 | yes | 4 | identity_crosswalk |
| jeremiyah love | RB | 21 | rookie | 2026 | 3 | 4436 | yes | 1 | identity_crosswalk |
| jadarian price | RB | 22 | rookie | 2026 | 32 | 3584 | yes | 1 | identity_crosswalk |
| kaelon black | RB | 24 | rookie | 2026 | 90 | 896 | yes | 2 | identity_crosswalk |
| jonah coleman | RB | 22 | rookie | 2026 | 108 | 1126 | yes | 3 | identity_crosswalk |
| mike washington | RB | 23 | rookie | 2026 | 122 | 842 | yes | 2 | unique_name_position |
| emmett johnson | RB | 22 | rookie | 2026 | 161 | 1054 | yes | 2 | identity_crosswalk |
| nicholas singleton | RB | 22 | rookie | 2026 | 165 | 998 | yes | 3 | identity_crosswalk |
| adam randall | RB | 22 | rookie | 2026 | 174 | 878 | yes | 5 | identity_crosswalk |
| kaytron allen | RB | 23 | rookie | 2026 | 187 | 1077 | yes | 3 | identity_crosswalk |
| demond claiborne | RB | 22 | rookie | 2026 | 198 | 1054 | yes | 3 | identity_crosswalk |
| eli heidenreich | RB | 23 | rookie | 2026 | 230 | 1077 | yes | 3 | identity_crosswalk |
| seth mcgowan | RB | 24 | rookie | 2026 | 237 | 1077 | yes | 2 | identity_crosswalk |
| jam miller | RB | 22 | rookie | 2026 | 245 | 846 | yes | — | unique_name_position |
| jmari taylor | RB | 24 | rookie | — | — | 1077 | yes | — | unique_name_position |
| kenyon sadiq | TE | 21 | rookie | 2026 | 16 | 1303 | yes | 2 | identity_crosswalk |
| eli stowers | TE | 23 | rookie | 2026 | 54 | 578 | yes | 2 | identity_crosswalk |
| max klare | TE | 23 | rookie | 2026 | 61 | 780 | yes | 4 | identity_crosswalk |
| sam roush | TE | 22 | rookie | 2026 | 69 | 673 | yes | 3 | identity_crosswalk |
| oscar delp | TE | 23 | rookie | 2026 | 73 | 780 | yes | 3 | identity_crosswalk |
| eli raridon | TE | 22 | rookie | 2026 | 95 | 673 | yes | 2 | identity_crosswalk |
| justin joly | TE | 22 | rookie | 2026 | 152 | 486 | yes | 7 | unique_name_position |
| jack endries | TE | 22 | rookie | 2026 | 221 | 673 | yes | 4 | identity_crosswalk |
| matt hibner | TE | 24 | rookie | — | — | 886 | yes | 2 | unique_name_position |
| michael trigg | TE | 24 | rookie | — | — | 886 | yes | — | unique_name_position |
| carnell tate | WR | 21 | rookie | 2026 | 4 | 3157 | yes | 1 | identity_crosswalk |
| jordyn tyson | WR | 22 | rookie | 2026 | 8 | 2449 | yes | 10 | identity_crosswalk |
| makai lemon | WR | 22 | rookie | 2026 | 20 | 2569 | yes | 3 | identity_crosswalk |
| kc concepcion | WR | 21 | rookie | 2026 | 24 | 2115 | yes | 1 | identity_crosswalk |
| omar cooper | WR | 22 | rookie | 2026 | 30 | 1965 | yes | 3 | unique_name_position |
| dezhaun stribling | WR | 23 | rookie | 2026 | 33 | 2134 | yes | 3 | identity_crosswalk |
| denzel boston | WR | 22 | rookie | 2026 | 39 | 1847 | yes | 2 | identity_crosswalk |
| germie bernard | WR | 22 | rookie | 2026 | 47 | 1382 | yes | 3 | identity_crosswalk |
| antonio williams | WR | 22 | rookie | 2026 | 71 | 1102 | yes | 3 | identity_crosswalk |
| malachi fields | WR | 22 | rookie | 2026 | 74 | 864 | yes | 2 | identity_crosswalk |
| caleb douglas | WR | 22 | rookie | 2026 | 75 | 687 | yes | 2 | identity_crosswalk |
| zachariah branch | WR | 22 | rookie | 2026 | 79 | 1197 | yes | 4 | identity_crosswalk |
| jakobi lane | WR | 22 | rookie | 2026 | 80 | 1055 | yes | 3 | identity_crosswalk |
| ted hurst | WR | 22 | rookie | 2026 | 84 | 864 | yes | 4 | unique_name_position |
| zavion thomas | WR | 22 | rookie | 2026 | 89 | 626 | yes | 4 | identity_crosswalk |
| chris bell | WR | 22 | rookie | 2026 | 94 | 1106 | yes | 5 | identity_crosswalk |
| brenen thompson | WR | 23 | rookie | 2026 | 105 | 1037 | yes | 4 | identity_crosswalk |
| elijah sarratt | WR | 23 | rookie | 2026 | 115 | 1037 | yes | 5 | identity_crosswalk |
| skyler bell | WR | 24 | rookie | 2026 | 125 | 1210 | yes | 5 | identity_crosswalk |
| bryce lance | WR | 23 | rookie | 2026 | 136 | 1037 | yes | 3 | identity_crosswalk |
| colbie young | WR | 24 | rookie | 2026 | 140 | 1210 | yes | 4 | identity_crosswalk |
| reggie virgil | WR | 22 | rookie | 2026 | 143 | 864 | yes | 4 | identity_crosswalk |
| cyrus allen | WR | 23 | rookie | 2026 | 176 | 1037 | yes | 4 | identity_crosswalk |
| kevin coleman | WR | 22 | rookie | 2026 | 177 | 1426 | yes | 3 | unique_name_position |
| barion brown | WR | 22 | rookie | 2026 | 190 | 1426 | yes | 4 | identity_crosswalk |
| cj daniels | WR | 24 | rookie | 2026 | 197 | 1210 | yes | 3 | unique_name_position |
| deion burks | WR | 23 | rookie | 2026 | 254 | 1676 | yes | 6 | unique_name_position |
| chris johnson | DB | 21 | rookie | 2026 | 27 | 1384 | NO | 1 | identity_crosswalk |
| harold perkins jr | LB | 21 | rookie | 2026 | 215 | 774 | NO | 2 | unique_name_position |
| erick hunter | LB | 23 | rookie | — | — | 1162 | NO | 3 | unique_name_position |
| taylen green | QB | 23 | rookie | 2026 | 182 | 1169 | NO | 4 | unique_name_position |
| cam miller | QB | 25 | second_year | 2025 | 215 | 1438 | NO | — | unique_name_position |
| garrett nussmeier | QB | 24 | rookie | 2026 | 249 | 1303 | NO | 4 | unique_name_position |
| haynes king | QB | 25 | rookie | — | — | 1438 | NO | 3 | unique_name_position |
| donovan edwards | RB | 23 | second_year | — | — | 1077 | NO | — | unique_name_position |
| leveon moss | RB | 23 | rookie | — | — | 1077 | NO | — | unique_name_position |

## Phase 1 decision rule

Do **not** design the prospect-value blend until this audit shows that the eligible cohort has enough reliable identity, experience, draft, and forward-candidate coverage to avoid replacing one coarse fallback with another.

If coverage is strong, Phase 2 should test **draft capital + age + Production V2 forward strength** as a research-only prospect prior. It should compare multiple blend strengths rather than selecting a hand-tuned coefficient.

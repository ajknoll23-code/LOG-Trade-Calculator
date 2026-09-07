# KTC Voter-Balance Research Analysis

Method: `ktc-voter-balance-analysis-v1`  
Source generated at: `2026-09-07T16:12:00.270728`  
Status: `research_only_no_market_value_change`

## Critical interpretation

**This report is research-only. Market Value V1 still uses `league_only.player_ratings`; this analysis does not change production values.**

The purpose is to quantify how much the raw league ranking changes when every league voter is limited to the configured effective lifetime contribution cap while retaining all counted ballots.

## Voter concentration

- Distinct league voters: **10**
- Voters currently down-weighted by the lifetime cap: **2**
- Largest raw voter share: **63.04%**
- Largest effective voter share: **16.95%**
- Raw HHI: **0.4182** (effective voter count ≈ **2.391**)
- Balanced HHI: **0.1297** (effective voter count ≈ **7.711**)
- Raw league ballots: **414**
- Effective league ballots after weighting: **177.0** (**42.75%** of raw mass)

## Rank agreement: raw vs voter-balanced

- Common rated players: **482**
- Spearman rank correlation: **0.848158**
- Median absolute rank shift: **42.0** spots
- 90th-percentile absolute rank shift: **111.8** spots
- Maximum absolute rank shift: **345.0** spots
- Top-10 overlap: **1/10 (10.0%)**
- Top-20 overlap: **10/20 (50.0%)**
- Top-50 overlap: **32/50 (64.0%)**

## Top 20 side-by-side

| Rank | Raw league | Voter-balanced |
|---:|---|---|
| 1 | trey mcbride | dorian williams |
| 2 | bhayshul tuten | xavier worthy |
| 3 | david bailey | terrel bernard |
| 4 | rome odunze | dillon thieneman |
| 5 | brock bowers | travis etienne |
| 6 | tyler shough | carnell tate |
| 7 | rashid shaheed | alontae taylor |
| 8 | tucker kraft | george karlaftis |
| 9 | harold fannin | tyler shough |
| 10 | micah parsons | devon witherspoon |
| 11 | malik willis | rashid shaheed |
| 12 | dorian williams | rome odunze |
| 13 | ty simpson | aidan hutchinson |
| 14 | carnell tate | micah parsons |
| 15 | terrel bernard | yaya diaby |
| 16 | kyren williams | malik willis |
| 17 | c schwesinger | lamar jackson |
| 18 | carson schwesinger | jaxson dart |
| 19 | nick emmanwori | trey mcbride |
| 20 | tj hockenson | tj hockenson |

## Largest gainers after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| bradley chubb | 397.0 | 52.0 | +345.0 | 345.0 |
| chig okonkwo | 448.0 | 110.0 | +338.0 | 338.0 |
| bobby okereke | 416.0 | 124.0 | +292.0 | 292.0 |
| jadeveon clowney | 332.0 | 72.0 | +260.0 | 260.0 |
| tank dell | 349.0 | 104.0 | +245.0 | 245.0 |
| kevin byard | 334.0 | 100.0 | +234.0 | 234.0 |
| klavon chaisson | 325.0 | 109.0 | +216.0 | 216.0 |
| brian branch | 307.0 | 107.0 | +200.0 | 200.0 |
| patrick queen | 276.5 | 81.0 | +195.5 | 195.5 |
| cooper dejean | 294.0 | 99.0 | +195.0 | 195.0 |
| uchenna nwosu | 254.0 | 69.5 | +184.5 | 184.5 |
| eric wilson | 233.0 | 56.0 | +177.0 | 177.0 |
| isaiah davis | 263.0 | 96.0 | +167.0 | 167.0 |
| drue tranquill | 174.0 | 21.0 | +153.0 | 153.0 |
| demarcus lawrence | 430.0 | 283.0 | +147.0 | 147.0 |

## Largest decliners after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| jonathon cooper | 61.0 | 378.0 | -317.0 | 317.0 |
| cade klubnik | 113.0 | 373.0 | -260.0 | 260.0 |
| chuba hubbard | 165.0 | 398.0 | -233.0 | 233.0 |
| malachi lawrence | 152.0 | 372.0 | -220.0 | 220.0 |
| demarvion overshown | 193.0 | 384.0 | -191.0 | 191.0 |
| tyler warren | 205.0 | 381.0 | -176.0 | 176.0 |
| budda baker | 211.0 | 375.0 | -164.0 | 164.0 |
| cashius howell | 247.0 | 407.0 | -160.0 | 160.0 |
| christian rozeboom | 315.0 | 475.0 | -160.0 | 160.0 |
| myles murphy | 305.0 | 464.0 | -159.0 | 159.0 |
| travon walker | 232.0 | 391.0 | -159.0 | 159.0 |
| tykee smith | 148.0 | 307.0 | -159.0 | 159.0 |
| pat bryant | 279.0 | 432.0 | -153.0 | 153.0 |
| juwan johnson | 255.0 | 401.0 | -146.0 | 146.0 |
| cedric gray | 140.0 | 282.0 | -142.0 | 142.0 |

## Decision guardrail

Do **not** promote the voter-balanced view into Market Value V1 from this report alone. The current evidence shows that voter concentration materially changes the ordering; the next question is whether the balanced ordering is more stable and more predictive of later league opinion across repeated snapshots.

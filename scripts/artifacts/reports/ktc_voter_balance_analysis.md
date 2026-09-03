# KTC Voter-Balance Research Analysis

Method: `ktc-voter-balance-analysis-v1`  
Source generated at: `2026-09-03T14:28:02.028650`  
Status: `research_only_no_market_value_change`

## Critical interpretation

**This report is research-only. Market Value V1 still uses `league_only.player_ratings`; this analysis does not change production values.**

The purpose is to quantify how much the raw league ranking changes when every league voter is limited to the configured effective lifetime contribution cap while retaining all counted ballots.

## Voter concentration

- Distinct league voters: **10**
- Voters currently down-weighted by the lifetime cap: **2**
- Largest raw voter share: **68.60%**
- Largest effective voter share: **20.98%**
- Raw HHI: **0.4904** (effective voter count ≈ **2.039**)
- Balanced HHI: **0.1635** (effective voter count ≈ **6.116**)
- Raw league ballots: **379**
- Effective league ballots after weighting: **143.0** (**37.73%** of raw mass)

## Rank agreement: raw vs voter-balanced

- Common rated players: **471**
- Spearman rank correlation: **0.854025**
- Median absolute rank shift: **39.0** spots
- 90th-percentile absolute rank shift: **102.0** spots
- Maximum absolute rank shift: **336.0** spots
- Top-10 overlap: **3/10 (30.0%)**
- Top-20 overlap: **10/20 (50.0%)**
- Top-50 overlap: **27/50 (54.0%)**

## Top 20 side-by-side

| Rank | Raw league | Voter-balanced |
|---:|---|---|
| 1 | trey mcbride | dorian williams |
| 2 | rome odunze | travis etienne |
| 3 | nick emmanwori | carnell tate |
| 4 | brock bowers | yaya diaby |
| 5 | tyler shough | george karlaftis |
| 6 | harold fannin | alontae taylor |
| 7 | ty simpson | rome odunze |
| 8 | micah parsons | tyler shough |
| 9 | tucker kraft | micah parsons |
| 10 | carson schwesinger | aidan hutchinson |
| 11 | rashid shaheed | ty simpson |
| 12 | c schwesinger | trey mcbride |
| 13 | carnell tate | emeka egbuka |
| 14 | kyren williams | fred warner |
| 15 | tj watt | drue tranquill |
| 16 | emeka egbuka | will anderson |
| 17 | jeremiyah love | lamar jackson |
| 18 | david bailey | tj watt |
| 19 | travis etienne | carson schwesinger |
| 20 | jack campbell | terry mclaurin |

## Largest gainers after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| bradley chubb | 362.0 | 26.0 | +336.0 | 336.0 |
| bobby okereke | 390.0 | 86.0 | +304.0 | 304.0 |
| tank dell | 369.0 | 90.0 | +279.0 | 279.0 |
| jadeveon clowney | 324.0 | 61.0 | +263.0 | 263.0 |
| kevin byard | 333.0 | 85.0 | +248.0 | 248.0 |
| klavon chaisson | 317.0 | 91.0 | +226.0 | 226.0 |
| mason graham | 310.0 | 89.0 | +221.0 | 221.0 |
| cooper dejean | 293.0 | 83.0 | +210.0 | 210.0 |
| patrick queen | 264.0 | 76.0 | +188.0 | 188.0 |
| eric wilson | 258.0 | 74.0 | +184.0 | 184.0 |
| deforest buckner | 251.0 | 71.0 | +180.0 | 180.0 |
| isaiah davis | 257.0 | 78.0 | +179.0 | 179.0 |
| drue tranquill | 173.0 | 15.0 | +158.0 | 158.0 |
| nick bosa | 204.0 | 48.0 | +156.0 | 156.0 |
| dandre swift | 236.0 | 84.0 | +152.0 | 152.0 |

## Largest decliners after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| jonathon cooper | 73.0 | 389.0 | -316.0 | 316.0 |
| cade klubnik | 107.0 | 381.0 | -274.0 | 274.0 |
| malachi lawrence | 152.0 | 380.0 | -228.0 | 228.0 |
| christian rozeboom | 188.0 | 397.0 | -209.0 | 209.0 |
| travon walker | 210.0 | 394.0 | -184.0 | 184.0 |
| budda baker | 203.0 | 385.0 | -182.0 | 182.0 |
| demarvion overshown | 205.0 | 386.0 | -181.0 | 181.0 |
| pat bryant | 256.0 | 428.0 | -172.0 | 172.0 |
| cashius howell | 244.0 | 408.0 | -164.0 | 164.0 |
| cedric gray | 120.0 | 280.0 | -160.0 | 160.0 |
| myles murphy | 299.0 | 459.0 | -160.0 | 160.0 |
| tyler warren | 233.0 | 390.5 | -157.5 | 157.5 |
| tykee smith | 127.0 | 277.0 | -150.0 | 150.0 |
| derwin james | 247.0 | 390.5 | -143.5 | 143.5 |
| eli raridon | 266.0 | 404.0 | -138.0 | 138.0 |

## Decision guardrail

Do **not** promote the voter-balanced view into Market Value V1 from this report alone. The current evidence shows that voter concentration materially changes the ordering; the next question is whether the balanced ordering is more stable and more predictive of later league opinion across repeated snapshots.

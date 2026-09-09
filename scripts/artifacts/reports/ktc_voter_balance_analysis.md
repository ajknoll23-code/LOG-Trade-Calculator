# KTC Voter-Balance Research Analysis

Method: `ktc-voter-balance-analysis-v1`  
Source generated at: `2026-09-09T04:34:46.083446`  
Status: `research_only_no_market_value_change`

## Critical interpretation

**This report is research-only. Market Value V1 still uses `league_only.player_ratings`; this analysis does not change production values.**

The purpose is to quantify how much the raw league ranking changes when every league voter is limited to the configured effective lifetime contribution cap while retaining all counted ballots.

## Voter concentration

- Distinct league voters: **10**
- Voters currently down-weighted by the lifetime cap: **2**
- Largest raw voter share: **62.31%**
- Largest effective voter share: **15.62%**
- Raw HHI: **0.4082** (effective voter count ≈ **2.45**)
- Balanced HHI: **0.1196** (effective voter count ≈ **8.364**)
- Raw league ballots: **451**
- Effective league ballots after weighting: **192.0** (**42.57%** of raw mass)

## Rank agreement: raw vs voter-balanced

- Common rated players: **490**
- Spearman rank correlation: **0.845248**
- Median absolute rank shift: **44.5** spots
- 90th-percentile absolute rank shift: **120.3** spots
- Maximum absolute rank shift: **342.0** spots
- Top-10 overlap: **2/10 (20.0%)**
- Top-20 overlap: **8/20 (40.0%)**
- Top-50 overlap: **35/50 (70.0%)**

## Top 20 side-by-side

| Rank | Raw league | Voter-balanced |
|---:|---|---|
| 1 | tucker kraft | xavier worthy |
| 2 | bhayshul tuten | terrel bernard |
| 3 | trey mcbride | travis etienne |
| 4 | makai lemon | will anderson |
| 5 | rome odunze | fernando mendoza |
| 6 | david bailey | carnell tate |
| 7 | josh allen | dillon thieneman |
| 8 | micah parsons | rome odunze |
| 9 | brock bowers | devon witherspoon |
| 10 | tyler shough | tyler shough |
| 11 | rashid shaheed | luther burden |
| 12 | carson schwesinger | rashid shaheed |
| 13 | malik willis | george karlaftis |
| 14 | harold fannin | alontae taylor |
| 15 | ty simpson | aidan hutchinson |
| 16 | will anderson | micah parsons |
| 17 | carnell tate | yaya diaby |
| 18 | terrel bernard | kc concepcion |
| 19 | kyle pitts | makai lemon |
| 20 | nick emmanwori | dorian williams |

## Largest gainers after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| chig okonkwo | 458.0 | 116.0 | +342.0 | 342.0 |
| bradley chubb | 396.5 | 59.0 | +337.5 | 337.5 |
| jadeveon clowney | 398.0 | 90.0 | +308.0 | 308.0 |
| bobby okereke | 413.0 | 122.0 | +291.0 | 291.0 |
| tank dell | 331.0 | 100.0 | +231.0 | 231.0 |
| eric wilson | 306.0 | 81.0 | +225.0 | 225.0 |
| brian branch | 321.0 | 113.0 | +208.0 | 208.0 |
| klavon chaisson | 312.5 | 115.0 | +197.5 | 197.5 |
| cooper dejean | 304.0 | 109.0 | +195.0 | 195.0 |
| uchenna nwosu | 265.0 | 73.0 | +192.0 | 192.0 |
| patrick queen | 271.0 | 84.0 | +187.0 | 187.0 |
| aaron rodgers | 235.0 | 66.0 | +169.0 | 169.0 |
| kenyon sadiq | 242.0 | 80.0 | +162.0 | 162.0 |
| isaiah davis | 263.0 | 102.0 | +161.0 | 161.0 |
| demarcus lawrence | 437.0 | 281.0 | +156.0 | 156.0 |

## Largest decliners after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| jonathon cooper | 82.0 | 379.0 | -297.0 | 297.0 |
| chuba hubbard | 163.0 | 407.0 | -244.0 | 244.0 |
| cade klubnik | 137.0 | 377.0 | -240.0 | 240.0 |
| christian rozeboom | 261.0 | 475.0 | -214.0 | 214.0 |
| malachi lawrence | 171.0 | 372.0 | -201.0 | 201.0 |
| demarvion overshown | 208.0 | 388.0 | -180.0 | 180.0 |
| derwin james | 288.0 | 467.0 | -179.0 | 179.0 |
| tyler warren | 202.0 | 380.0 | -178.0 | 178.0 |
| tykee smith | 77.0 | 253.0 | -176.0 | 176.0 |
| juwan johnson | 250.0 | 421.0 | -171.0 | 171.0 |
| travon walker | 232.0 | 399.0 | -167.0 | 167.0 |
| cashius howell | 249.0 | 413.0 | -164.0 | 164.0 |
| akheem mesidor | 222.0 | 384.0 | -162.0 | 162.0 |
| budda baker | 220.0 | 374.0 | -154.0 | 154.0 |
| myles murphy | 319.0 | 471.0 | -152.0 | 152.0 |

## Decision guardrail

Do **not** promote the voter-balanced view into Market Value V1 from this report alone. The current evidence shows that voter concentration materially changes the ordering; the next question is whether the balanced ordering is more stable and more predictive of later league opinion across repeated snapshots.

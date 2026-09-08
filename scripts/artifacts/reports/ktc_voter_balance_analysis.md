# KTC Voter-Balance Research Analysis

Method: `ktc-voter-balance-analysis-v1`  
Source generated at: `2026-09-08T00:00:10.137418`  
Status: `research_only_no_market_value_change`

## Critical interpretation

**This report is research-only. Market Value V1 still uses `league_only.player_ratings`; this analysis does not change production values.**

The purpose is to quantify how much the raw league ranking changes when every league voter is limited to the configured effective lifetime contribution cap while retaining all counted ballots.

## Voter concentration

- Distinct league voters: **10**
- Voters currently down-weighted by the lifetime cap: **2**
- Largest raw voter share: **62.58%**
- Largest effective voter share: **15.62%**
- Raw HHI: **0.4110** (effective voter count ≈ **2.433**)
- Balanced HHI: **0.1196** (effective voter count ≈ **8.364**)
- Raw league ballots: **449**
- Effective league ballots after weighting: **192.0** (**42.76%** of raw mass)

## Rank agreement: raw vs voter-balanced

- Common rated players: **489**
- Spearman rank correlation: **0.844551**
- Median absolute rank shift: **44.0** spots
- 90th-percentile absolute rank shift: **123.4** spots
- Maximum absolute rank shift: **342.0** spots
- Top-10 overlap: **3/10 (30.0%)**
- Top-20 overlap: **9/20 (45.0%)**
- Top-50 overlap: **33/50 (66.0%)**

## Top 20 side-by-side

| Rank | Raw league | Voter-balanced |
|---:|---|---|
| 1 | tucker kraft | xavier worthy |
| 2 | bhayshul tuten | dorian williams |
| 3 | trey mcbride | terrel bernard |
| 4 | rome odunze | travis etienne |
| 5 | david bailey | fernando mendoza |
| 6 | josh allen | carnell tate |
| 7 | brock bowers | dillon thieneman |
| 8 | micah parsons | rome odunze |
| 9 | tyler shough | devon witherspoon |
| 10 | dorian williams | tyler shough |
| 11 | rashid shaheed | luther burden |
| 12 | carson schwesinger | george karlaftis |
| 13 | malik willis | rashid shaheed |
| 14 | harold fannin | alontae taylor |
| 15 | ty simpson | aidan hutchinson |
| 16 | carnell tate | yaya diaby |
| 17 | terrel bernard | micah parsons |
| 18 | kyle pitts | kc concepcion |
| 19 | nick emmanwori | josh allen |
| 20 | kyren williams | malik willis |

## Largest gainers after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| chig okonkwo | 457.0 | 115.0 | +342.0 | 342.0 |
| bradley chubb | 395.0 | 56.0 | +339.0 | 339.0 |
| jadeveon clowney | 396.0 | 88.0 | +308.0 | 308.0 |
| bobby okereke | 413.0 | 122.0 | +291.0 | 291.0 |
| tank dell | 330.0 | 92.0 | +238.0 | 238.0 |
| eric wilson | 306.0 | 80.0 | +226.0 | 226.0 |
| brian branch | 322.0 | 112.0 | +210.0 | 210.0 |
| klavon chaisson | 313.0 | 113.0 | +200.0 | 200.0 |
| cooper dejean | 304.0 | 108.0 | +196.0 | 196.0 |
| uchenna nwosu | 265.0 | 72.0 | +193.0 | 193.0 |
| patrick queen | 271.0 | 84.0 | +187.0 | 187.0 |
| aaron rodgers | 235.0 | 55.0 | +180.0 | 180.0 |
| kenyon sadiq | 242.0 | 79.0 | +163.0 | 163.0 |
| isaiah davis | 263.0 | 101.0 | +162.0 | 162.0 |
| demarcus lawrence | 436.0 | 281.0 | +155.0 | 155.0 |

## Largest decliners after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| jonathon cooper | 82.0 | 379.0 | -297.0 | 297.0 |
| chuba hubbard | 163.0 | 406.0 | -243.0 | 243.0 |
| cade klubnik | 135.0 | 377.0 | -242.0 | 242.0 |
| christian rozeboom | 260.0 | 474.0 | -214.0 | 214.0 |
| malachi lawrence | 173.0 | 373.0 | -200.0 | 200.0 |
| demarvion overshown | 200.0 | 390.0 | -190.0 | 190.0 |
| tyler warren | 201.0 | 380.0 | -179.0 | 179.0 |
| derwin james | 288.0 | 466.0 | -178.0 | 178.0 |
| tykee smith | 77.0 | 253.0 | -176.0 | 176.0 |
| juwan johnson | 250.0 | 420.0 | -170.0 | 170.0 |
| travon walker | 231.0 | 398.0 | -167.0 | 167.0 |
| akheem mesidor | 220.0 | 383.0 | -163.0 | 163.0 |
| cashius howell | 249.0 | 411.0 | -162.0 | 162.0 |
| budda baker | 219.0 | 376.0 | -157.0 | 157.0 |
| myles murphy | 321.0 | 470.0 | -149.0 | 149.0 |

## Decision guardrail

Do **not** promote the voter-balanced view into Market Value V1 from this report alone. The current evidence shows that voter concentration materially changes the ordering; the next question is whether the balanced ordering is more stable and more predictive of later league opinion across repeated snapshots.

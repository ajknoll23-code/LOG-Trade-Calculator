# KTC Voter-Balance Research Analysis

Method: `ktc-voter-balance-analysis-v1`  
Source generated at: `2026-09-18T21:46:07.044312`  
Status: `research_only_no_market_value_change`

## Critical interpretation

**This report is research-only. Market Value V1 still uses `league_only.player_ratings`; this analysis does not change production values.**

The purpose is to quantify how much the raw league ranking changes when every league voter is limited to the configured effective lifetime contribution cap while retaining all counted ballots.

## Voter concentration

- Distinct league voters: **10**
- Voters currently down-weighted by the lifetime cap: **2**
- Largest raw voter share: **55.21%**
- Largest effective voter share: **15.62%**
- Raw HHI: **0.3505** (effective voter count ≈ **2.853**)
- Balanced HHI: **0.1196** (effective voter count ≈ **8.364**)
- Raw league ballots: **509**
- Effective league ballots after weighting: **192.0** (**37.72%** of raw mass)

## Rank agreement: raw vs voter-balanced

- Common rated players: **505**
- Spearman rank correlation: **0.850223**
- Median absolute rank shift: **48.0** spots
- 90th-percentile absolute rank shift: **121.2** spots
- Maximum absolute rank shift: **314.0** spots
- Top-10 overlap: **0/10 (0.0%)**
- Top-20 overlap: **7/20 (35.0%)**
- Top-50 overlap: **29/50 (58.0%)**

## Top 20 side-by-side

| Rank | Raw league | Voter-balanced |
|---:|---|---|
| 1 | jeremiyah love | xavier worthy |
| 2 | tucker kraft | dorian williams |
| 3 | myles garrett | terrel bernard |
| 4 | sonny styles | travis etienne |
| 5 | tyler shough | fernando mendoza |
| 6 | micah parsons | carnell tate |
| 7 | will anderson | dillon thieneman |
| 8 | carson schwesinger | rashid shaheed |
| 9 | bhayshul tuten | devon witherspoon |
| 10 | josh allen | alex anzalone |
| 11 | rome odunze | sonny styles |
| 12 | trey mcbride | aidan hutchinson |
| 13 | makai lemon | micah parsons |
| 14 | drake maye | tj hockenson |
| 15 | david bailey | jeremiyah love |
| 16 | nick emmanwori | tyler shough |
| 17 | rashid shaheed | kc concepcion |
| 18 | harold fannin | patrick mahomes |
| 19 | carnell tate | josh allen |
| 20 | brock bowers | lamar jackson |

## Largest gainers after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| bradley chubb | 399.0 | 85.0 | +314.0 | 314.0 |
| bobby okereke | 432.0 | 140.0 | +292.0 | 292.0 |
| jadeveon clowney | 406.0 | 124.0 | +282.0 | 282.0 |
| eric wilson | 316.0 | 73.0 | +243.0 | 243.0 |
| mansoor delane | 336.0 | 93.0 | +243.0 | 243.0 |
| chig okonkwo | 481.0 | 260.0 | +221.0 | 221.0 |
| xavier hutchinson | 307.0 | 94.0 | +213.0 | 213.0 |
| brian branch | 338.0 | 126.0 | +212.0 | 212.0 |
| uchenna nwosu | 268.0 | 67.0 | +201.0 | 201.0 |
| alex singleton | 309.0 | 109.0 | +200.0 | 200.0 |
| cooper dejean | 306.0 | 114.0 | +192.0 | 192.0 |
| tank dell | 340.0 | 160.0 | +180.0 | 180.0 |
| danny stutsman | 292.0 | 115.0 | +177.0 | 177.0 |
| patrick queen | 222.0 | 49.0 | +173.0 | 173.0 |
| drue tranquill | 194.0 | 25.0 | +169.0 | 169.0 |

## Largest decliners after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| jonathon cooper | 95.0 | 400.0 | -305.0 | 305.0 |
| chuba hubbard | 145.0 | 413.0 | -268.0 | 268.0 |
| demarvion overshown | 214.0 | 419.0 | -205.0 | 205.0 |
| christian rozeboom | 288.0 | 487.0 | -199.0 | 199.0 |
| tyler warren | 216.0 | 412.0 | -196.0 | 196.0 |
| tykee smith | 91.0 | 279.0 | -188.0 | 188.0 |
| derwin james | 302.0 | 484.0 | -182.0 | 182.0 |
| juwan johnson | 260.0 | 442.0 | -182.0 | 182.0 |
| cashius howell | 252.0 | 429.0 | -177.0 | 177.0 |
| travon walker | 246.0 | 420.0 | -174.0 | 174.0 |
| malik mustapha | 296.0 | 464.5 | -168.5 | 168.5 |
| brian burns | 183.0 | 350.0 | -167.0 | 167.0 |
| pat bryant | 304.0 | 462.0 | -158.0 | 158.0 |
| akheem mesidor | 192.0 | 348.0 | -156.0 | 156.0 |
| myles murphy | 332.0 | 488.0 | -156.0 | 156.0 |

## Decision guardrail

Do **not** promote the voter-balanced view into Market Value V1 from this report alone. The current evidence shows that voter concentration materially changes the ordering; the next question is whether the balanced ordering is more stable and more predictive of later league opinion across repeated snapshots.

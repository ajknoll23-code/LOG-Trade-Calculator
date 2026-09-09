# KTC Voter-Balance Research Analysis

Method: `ktc-voter-balance-analysis-v1`  
Source generated at: `2026-09-09T10:24:07.218472`  
Status: `research_only_no_market_value_change`

## Critical interpretation

**This report is research-only. Market Value V1 still uses `league_only.player_ratings`; this analysis does not change production values.**

The purpose is to quantify how much the raw league ranking changes when every league voter is limited to the configured effective lifetime contribution cap while retaining all counted ballots.

## Voter concentration

- Distinct league voters: **10**
- Voters currently down-weighted by the lifetime cap: **2**
- Largest raw voter share: **59.91%**
- Largest effective voter share: **15.62%**
- Raw HHI: **0.3850** (effective voter count ≈ **2.597**)
- Balanced HHI: **0.1196** (effective voter count ≈ **8.364**)
- Raw league ballots: **469**
- Effective league ballots after weighting: **192.0** (**40.94%** of raw mass)

## Rank agreement: raw vs voter-balanced

- Common rated players: **496**
- Spearman rank correlation: **0.845894**
- Median absolute rank shift: **46.5** spots
- 90th-percentile absolute rank shift: **122.25** spots
- Maximum absolute rank shift: **324.0** spots
- Top-10 overlap: **2/10 (20.0%)**
- Top-20 overlap: **8/20 (40.0%)**
- Top-50 overlap: **33/50 (66.0%)**

## Top 20 side-by-side

| Rank | Raw league | Voter-balanced |
|---:|---|---|
| 1 | jeremiyah love | xavier worthy |
| 2 | tyler shough | terrel bernard |
| 3 | tucker kraft | travis etienne |
| 4 | trey mcbride | fernando mendoza |
| 5 | makai lemon | carnell tate |
| 6 | josh allen | tyler shough |
| 7 | bhayshul tuten | jeremiyah love |
| 8 | micah parsons | dorian williams |
| 9 | rome odunze | alex anzalone |
| 10 | david bailey | patrick mahomes |
| 11 | brock bowers | rashid shaheed |
| 12 | carson schwesinger | dillon thieneman |
| 13 | rashid shaheed | devon witherspoon |
| 14 | carnell tate | micah parsons |
| 15 | harold fannin | rome odunze |
| 16 | malik willis | josh allen |
| 17 | terrel bernard | luther burden |
| 18 | kyle pitts | brock purdy |
| 19 | will anderson | aidan hutchinson |
| 20 | ty simpson | george karlaftis |

## Largest gainers after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| bradley chubb | 391.0 | 67.0 | +324.0 | 324.0 |
| jadeveon clowney | 402.0 | 104.0 | +298.0 | 298.0 |
| bobby okereke | 418.0 | 130.0 | +288.0 | 288.0 |
| chig okonkwo | 468.0 | 203.0 | +265.0 | 265.0 |
| eric wilson | 312.0 | 74.0 | +238.0 | 238.0 |
| tank dell | 333.0 | 118.0 | +215.0 | 215.0 |
| brian branch | 327.0 | 123.0 | +204.0 | 204.0 |
| uchenna nwosu | 269.0 | 68.0 | +201.0 | 201.0 |
| patrick queen | 279.0 | 79.0 | +200.0 | 200.0 |
| cooper dejean | 300.0 | 114.0 | +186.0 | 186.0 |
| mansoor delane | 245.0 | 65.0 | +180.0 | 180.0 |
| xavier hutchinson | 302.0 | 125.0 | +177.0 | 177.0 |
| alex singleton | 304.0 | 131.0 | +173.0 | 173.0 |
| kenyon sadiq | 243.0 | 73.0 | +170.0 | 170.0 |
| klavon chaisson | 316.0 | 150.0 | +166.0 | 166.0 |

## Largest decliners after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| jonathon cooper | 85.0 | 383.0 | -298.0 | 298.0 |
| chuba hubbard | 155.0 | 402.0 | -247.0 | 247.0 |
| christian rozeboom | 266.0 | 481.0 | -215.0 | 215.0 |
| cade klubnik | 131.0 | 336.0 | -205.0 | 205.0 |
| demarvion overshown | 210.5 | 400.5 | -190.0 | 190.0 |
| tykee smith | 83.0 | 271.0 | -188.0 | 188.0 |
| tyler warren | 205.0 | 392.0 | -187.0 | 187.0 |
| juwan johnson | 248.0 | 433.0 | -185.0 | 185.0 |
| derwin james | 291.0 | 474.0 | -183.0 | 183.0 |
| cashius howell | 247.0 | 423.0 | -176.0 | 176.0 |
| travon walker | 239.0 | 408.0 | -169.0 | 169.0 |
| akheem mesidor | 228.0 | 396.0 | -168.0 | 168.0 |
| malachi lawrence | 181.0 | 347.0 | -166.0 | 166.0 |
| quentin lake | 249.5 | 409.0 | -159.5 | 159.5 |
| myles murphy | 322.0 | 477.0 | -155.0 | 155.0 |

## Decision guardrail

Do **not** promote the voter-balanced view into Market Value V1 from this report alone. The current evidence shows that voter concentration materially changes the ordering; the next question is whether the balanced ordering is more stable and more predictive of later league opinion across repeated snapshots.

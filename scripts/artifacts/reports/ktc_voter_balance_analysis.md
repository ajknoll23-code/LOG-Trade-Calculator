# KTC Voter-Balance Research Analysis

Method: `ktc-voter-balance-analysis-v1`
Source generated at: `2026-09-17T12:28:11.697241`
Status: `research_only_no_market_value_change`

## Critical interpretation

**This report is research-only. Market Value V1 still uses `league_only.player_ratings`; this analysis does not change production values.**

The purpose is to quantify how much the raw league ranking changes when every league voter is limited to the configured effective lifetime contribution cap while retaining all counted ballots.

## Voter concentration

- Distinct league voters: **10**
- Voters currently down-weighted by the lifetime cap: **2**
- Largest raw voter share: **57.46%**
- Largest effective voter share: **15.62%**
- Raw HHI: **0.3652** (effective voter count ≈ **2.738**)
- Balanced HHI: **0.1196** (effective voter count ≈ **8.364**)
- Raw league ballots: **489**
- Effective league ballots after weighting: **192.0** (**39.26%** of raw mass)

## Rank agreement: raw vs voter-balanced

- Common rated players: **498**
- Spearman rank correlation: **0.843362**
- Median absolute rank shift: **46.0** spots
- 90th-percentile absolute rank shift: **124.6** spots
- Maximum absolute rank shift: **310.0** spots
- Top-10 overlap: **1/10 (10.0%)**
- Top-20 overlap: **8/20 (40.0%)**
- Top-50 overlap: **32/50 (64.0%)**

## Top 20 side-by-side

| Rank | Raw league | Voter-balanced |
|---:|---|---|
| 1 | jeremiyah love | xavier worthy |
| 2 | sonny styles | terrel bernard |
| 3 | myles garrett | travis etienne |
| 4 | tyler shough | dorian williams |
| 5 | tucker kraft | fernando mendoza |
| 6 | micah parsons | carnell tate |
| 7 | will anderson | alex anzalone |
| 8 | makai lemon | sonny styles |
| 9 | josh allen | dillon thieneman |
| 10 | bhayshul tuten | rashid shaheed |
| 11 | rome odunze | devon witherspoon |
| 12 | carson schwesinger | tyler shough |
| 13 | trey mcbride | jeremiyah love |
| 14 | david bailey | micah parsons |
| 15 | nick emmanwori | will anderson |
| 16 | rashid shaheed | patrick mahomes |
| 17 | harold fannin | aidan hutchinson |
| 18 | carnell tate | josh allen |
| 19 | brock bowers | brock purdy |
| 20 | maxx crosby | kc concepcion |

## Largest gainers after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| bradley chubb | 382.0 | 72.0 | +310.0 | 310.0 |
| chig okonkwo | 466.0 | 164.0 | +302.0 | 302.0 |
| bobby okereke | 421.0 | 136.0 | +285.0 | 285.0 |
| jadeveon clowney | 401.0 | 120.0 | +281.0 | 281.0 |
| eric wilson | 315.0 | 71.0 | +244.0 | 244.0 |
| mansoor delane | 331.0 | 105.0 | +226.0 | 226.0 |
| brian branch | 334.0 | 126.0 | +208.0 | 208.0 |
| patrick queen | 284.0 | 77.0 | +207.0 | 207.0 |
| uchenna nwosu | 267.0 | 64.0 | +203.0 | 203.0 |
| tank dell | 333.0 | 131.0 | +202.0 | 202.0 |
| xavier hutchinson | 304.0 | 103.0 | +201.0 | 201.0 |
| cooper dejean | 300.0 | 112.0 | +188.0 | 188.0 |
| alex singleton | 301.0 | 119.0 | +182.0 | 182.0 |
| kenyon sadiq | 241.0 | 70.0 | +171.0 | 171.0 |
| demarcus lawrence | 444.0 | 281.0 | +163.0 | 163.0 |

## Largest decliners after voter balancing

| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |
|---|---:|---:|---:|---:|
| jonathon cooper | 88.0 | 393.0 | -305.0 | 305.0 |
| chuba hubbard | 133.0 | 402.0 | -269.0 | 269.0 |
| demarvion overshown | 208.0 | 407.0 | -199.0 | 199.0 |
| christian rozeboom | 285.0 | 479.0 | -194.0 | 194.0 |
| tyler warren | 211.0 | 405.0 | -194.0 | 194.0 |
| tykee smith | 84.0 | 272.0 | -188.0 | 188.0 |
| juwan johnson | 249.0 | 435.0 | -186.0 | 186.0 |
| cashius howell | 244.0 | 428.0 | -184.0 | 184.0 |
| derwin james | 294.0 | 477.0 | -183.0 | 183.0 |
| travon walker | 233.0 | 414.0 | -181.0 | 181.0 |
| quentin lake | 245.0 | 417.0 | -172.0 | 172.0 |
| malik mustapha | 295.0 | 455.0 | -160.0 | 160.0 |
| myles murphy | 323.0 | 481.0 | -158.0 | 158.0 |
| pat bryant | 299.0 | 454.0 | -155.0 | 155.0 |
| brian burns | 170.0 | 323.0 | -153.0 | 153.0 |

## Decision guardrail

Do **not** promote the voter-balanced view into Market Value V1 from this report alone. The current evidence shows that voter concentration materially changes the ordering; the next question is whether the balanced ordering is more stable and more predictive of later league opinion across repeated snapshots.

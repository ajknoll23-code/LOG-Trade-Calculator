# Team Utility Starter-Objective Audit

Research-only audit. **No production values or Team Utility constants were changed.**

## What this tests

- Current production starter selection: **Fundamental Value**.
- Comparison starter selection: **Sleeper 2026 projected fantasy points**, scored under the league's own scoring rules.
- Both use the same legal 17-slot lineup structure.
- Current Team Utility roster scope is mirrored as **starters + bench + taxi**; IR is excluded.

## League-wide results

- Teams audited: **12**
- Teams where the selected starting lineup differs: **12 / 12**
- Complete projection comparisons: **7 / 12**
- Median starter overlap: **14.0 / 17**
- Median projected non-K points left on table by FV selection: **100.3** season points
- Mean projected non-K points left on table: **120.06** season points
- Worst team projected non-K points left on table: **256.8** season points
- Median FV-lineup projection efficiency: **97.03%**
- Taxi players selected as starters by FV objective: **1**
- Taxi players selected as starters by projection objective: **0**
- Teams where allowing taxi changes projection-optimal lineup: **0**
- Unresolved roster records: **25**

## Team detail

| Team | Coverage | Overlap | Swaps | FV projected pts | Optimal projected pts | Left on table | Efficiency | Taxi changes optimum? |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| Just Run Power | 92.5% | 13/17 | 4 | 3103.2 | 3360.0 | 256.8 | 92.36% | no |
| Narroway Farms M714 | 91.1% | 13/17 | 4 | 3386.4 | 3555.6 | 169.2 | 95.24% | no |
| Cock Mchorse 🐴 | 86.7% | 14/17 | 3 | 2887.5 | 3008.7 | 121.2 | 95.97% | no |
| Toddy2times | 90.7% | 14/17 | 3 | 3274.5 | 3374.8 | 100.3 | 97.03% | no |
| Moose Knuckles | 76.7% | 14/17 | 3 | 3004.6 | 3091.6 | 87.0 | 97.19% | no |
| Landry's Hat | 92.5% | 15/17 | 2 | 3677.6 | 3751.6 | 74.0 | 98.03% | no |
| Serious Gourmet Shit | 93.2% | 16/17 | 1 | 3300.2 | 3332.1 | 31.9 | 99.04% | no |
| Sunday Brunson  | 90.7% | 15/17 | 2 | 3228.6 | 3406.4 | n/a | n/a | no |
| Pullham Bluecocks  | 88.1% | 14/17 | 3 | 3018.3 | 3223.3 | n/a | n/a | no |
| Jersey Bagels | 71.4% | 15/17 | 2 | 2930.7 | 3071.6 | n/a | n/a | no |
| Apex Predators | 79.5% | 12/17 | 5 | 3375.0 | 3679.9 | n/a | n/a | no |
| <respectable team name> | 87.8% | 13/17 | 4 | 2566.6 | 2893.0 | n/a | n/a | no |

## Biggest lineup disagreements

### Just Run Power

- Projection objective starts instead: Alex Singleton (LB, FV 2578, Proj 166.8), George Kittle (TE, FV 2785, Proj 164.5), David Montgomery (RB, FV 2734, Proj 276.6), Andrew Van Ginkel (LB, FV 2528, Proj 192.8)
- Fundamental objective starts instead: Dalton Kincaid (TE, FV 2990, Proj 125.5), Henry To'oTo'o (LB, FV 3379, Proj 142.6), Brian Thomas (WR, FV 3216, Proj 154.7), Derrick Brown (DL, FV 3340, Proj 121.1)

### Narroway Farms M714

- Projection objective starts instead: Demetrius Knight (LB, FV 3852, Proj 181.9), Jessie Bates (DB, FV 2488, Proj 149.9), Cam Bynum (DB, FV 2779, Proj 139.6), Malik Willis (QB, FV 3711, Proj 299.7)
- Fundamental objective starts instead: Michael Wilson (WR, FV 4070, Proj 160.0), Mike Sainristil (DB, FV 2938, Proj 137.8), Danielle Hunter (DL, FV 3862, Proj 171.3), Marcus Jones (DB, FV 3104, Proj 132.8)

### Cock Mchorse 🐴

- Projection objective starts instead: Kyler Murray (QB, FV 3990, Proj 305.4), Rhamondre Stevenson (RB, FV 2409, Proj 210.6), George Karlaftis (DL, FV 3421, Proj 142.5)
- Fundamental objective starts instead: Tyrone Tracy (RB, FV 2604, Proj 106.8), Tyler Shough (QB, FV 4276, Proj 295.8), Jordyn Brooks (LB, FV 5155, Proj 134.7)

### Toddy2times

- Projection objective starts instead: TreVeyon Henderson (RB, FV 3784, Proj 215.7), Rueben Bain (DL, FV 2026, Proj 128.9), Drue Tranquill (LB, FV 2732, Proj 188.4)
- Fundamental objective starts instead: Rashan Gary (DL, FV 3197, Proj 125.9), Jameson Williams (WR, FV 4829, Proj 204.8), Jordan Davis (DL, FV 3082, Proj 102.0)

### Moose Knuckles

- Projection objective starts instead: Demario Davis (LB, FV 2558, Proj 148.6), Luther Burden (WR, FV 3562, Proj 191.0), Paulson Adebo (DB, FV 3137, Proj 127.2)
- Fundamental objective starts instead: Emeka Egbuka (WR, FV 3934, Proj 167.4), Ed Oliver (DL, FV 3539, Proj 106.2), Quentin Lake (DB, FV 3291, Proj 106.2)

### Landry's Hat

- Projection objective starts instead: Saquon Barkley (RB, FV 3566, Proj 287.3), Tre'von Moehrig (DB, FV 3636, Proj 167.6)
- Fundamental objective starts instead: Kamari Lassiter (DB, FV 3772, Proj 160.8), George Pickens (WR, FV 5896, Proj 220.1)

## Interpretation guardrails

- This audit tests the **starter-selection objective only**. It does not determine the correct bench weight.
- Sleeper projections are a forward-looking scoring proxy, not ground truth.
- The report does **not** change Fundamental Value. It asks only which players should count as starters inside Team Utility.
- Taxi findings are reported separately because taxi eligibility is an architecture question, not a scoring-model question.


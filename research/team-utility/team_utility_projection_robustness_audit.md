# Team Utility Projection Robustness Audit

Research-only. **No production values or Team Utility constants were changed.**

## Question

Does the conclusion that Fundamental Value is a poor starter-selection objective survive an independent projection provider?

## Aggregate results

| Objective used to select starters | Teams differing from FV | Complete comparisons | Median overlap with FV | Median points FV leaves on table | Median FV efficiency |
|---|---:|---:|---:|---:|---:|
| Sleeper | 12/12 | 7/12 | 14.0/17 | 112.4 | 96.68% |
| FantasyPros normalized | 12/12 | 0/12 | 15.0/17 | n/a | n/a |
| 50/50 blend | 12/12 | 10/12 | 14.0/17 | 136.9 | 95.91% |

## Projection-provider agreement

- Median Sleeper vs FantasyPros starter overlap: **13.0 / 17**
- Median Sleeper vs blend starter overlap: **15.0 / 17**
- Median FantasyPros vs blend starter overlap: **14.5 / 17**

## Team detail

| Team | Sleeper vs FV | FP vs FV | Blend vs FV | Sleeper/FP overlap | Sleeper cov. | FP cov. | Blend cov. |
|---|---:|---:|---:|---:|---:|---:|---:|
| Just Run Power | 12/17 | 15/17 | 12/17 | 11/17 | 91.1% | 40.0% | 91.1% |
| Sunday Brunson  | 15/17 | 14/17 | 15/17 | 16/17 | 95.3% | 34.9% | 95.3% |
| Narroway Farms M714 | 13/17 | 15/17 | 14/17 | 13/17 | 91.1% | 35.6% | 91.1% |
| Landry's Hat | 15/17 | 15/17 | 14/17 | 13/17 | 95.1% | 43.9% | 97.6% |
| Pullham Bluecocks  | 14/17 | 15/17 | 14/17 | 13/17 | 90.5% | 40.5% | 95.2% |
| Cock Mchorse 🐴 | 13/17 | 16/17 | 13/17 | 12/17 | 88.9% | 35.6% | 93.3% |
| Jersey Bagels | 15/17 | 16/17 | 16/17 | 15/17 | 71.4% | 26.2% | 73.8% |
| Apex Predators | 12/17 | 14/17 | 13/17 | 12/17 | 77.8% | 31.1% | 86.7% |
| Toddy2times | 14/17 | 14/17 | 13/17 | 13/17 | 88.9% | 26.7% | 93.3% |
| Moose Knuckles | 14/17 | 15/17 | 13/17 | 14/17 | 78.6% | 31.0% | 81.0% |
| <respectable team name> | 12/17 | 16/17 | 14/17 | 12/17 | 88.4% | 37.2% | 93.0% |
| Serious Gourmet Shit | 15/17 | 15/17 | 15/17 | 14/17 | 97.6% | 43.9% | 97.6% |

## Data-integrity notes

- FantasyPros normalized rows: **1033**
- Crosswalk rows mapped to Sleeper IDs with normalized points: **472**
- Manual-review crosswalk rows skipped: **0**

## Guardrails

- This tests starter selection only, not the bench-weight coefficient.
- FantasyPros normalized totals explicitly omit categories unavailable from its confirmed schema, including IDP QB hits.
- Provider agreement does not make projections ground truth; it tests whether the conclusion is source-specific.
- Current production roster scope (including taxi) is held fixed to isolate starter-objective choice.


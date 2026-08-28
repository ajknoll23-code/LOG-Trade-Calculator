# IDP V1 Live-Anchored Candidate Report

## Status

**Diagnostic candidate only. This does not edit `index.html`.**

The candidate anchors to the actual baked pre-V1 `prod_mult` values and applies only the V1-vs-legacy projection delta on the established 55% projection share. This avoids importing unrelated drift from the legacy history generator into the user-visible before/after comparison.

## Baselines

| Pos | Legacy point-scale baseline | Candidate baseline | Shift | Rank-32 player |
|---|---:|---:|---:|---|
| LB | 184.15 | 199.53 | +8.3% | quincy williams |
| DL | 132.00 | 135.98 | +3.0% | jonathon cooper |
| DB | 156.16 | 163.22 | +4.5% | mike jackson |

## True live old -> candidate prod_mult change

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 119 | -5.1% | +8.8% | +17.0% | -30.2% | +42.0% |
| DL | 93 | +5.5% | +12.2% | +13.7% | -11.0% | +19.3% |
| DB | 117 | -0.3% | +13.4% | +16.0% | -22.8% | +42.5% |

## Source cohorts

| Cohort | N | Median change | P90 | P95 |
|---|---:|---:|---:|---:|
| both | 272 | +0.5% | +13.7% | +17.1% |
| fp_only | 9 | -7.9% | +2.5% | +3.2% |
| sleeper_only | 44 | -5.1% | -1.0% | +0.0% |
| no_new_data | 4 | -1.9% | +0.0% | +0.0% |

## Holds / unresolved deltas

- None

## Clamp occupancy

- Old live floor: 10; ceiling: 0
- Candidate floor: 10; ceiling: 0

## Largest absolute movers

| Player | Pos | Old | Candidate | Change | Source | Projection delta | Status |
|---|---|---:|---:|---:|---|---:|---|
| aj haulcy | DB | 0.2120 | 0.3021 | +42.5% | both | +41.0 | projection_delta_applied |
| denzel perryman | LB | 0.1730 | 0.2457 | +42.0% | both | +45.3 | projection_delta_applied |
| isaiah mcduffie | LB | 0.3740 | 0.2610 | -30.2% | both | -37.0 | projection_delta_applied |
| dmarco jackson | LB | 0.2140 | 0.1500 | -29.9% | both | -20.8 | projection_delta_applied |
| eric murray | DB | 0.3080 | 0.3977 | +29.1% | both | +42.5 | projection_delta_applied |
| bradley chubb | LB | 0.4110 | 0.5237 | +27.4% | both | +73.6 | projection_delta_applied |
| mike hughes | DB | 0.2750 | 0.3425 | +24.5% | both | +33.1 | projection_delta_applied |
| nohl williams | DB | 0.3810 | 0.2940 | -22.8% | both | -26.2 | projection_delta_applied |
| jevon holland | DB | 0.3410 | 0.4174 | +22.4% | both | +37.8 | projection_delta_applied |
| craig woodson | DB | 0.4040 | 0.4907 | +21.5% | both | +43.0 | projection_delta_applied |
| khalil mack | LB | 0.2130 | 0.2555 | +20.0% | both | +32.2 | projection_delta_applied |
| jonathan greenard | DL | 0.3460 | 0.4129 | +19.3% | both | +26.4 | projection_delta_applied |
| omar speights | LB | 0.2820 | 0.3350 | +18.8% | both | +39.9 | projection_delta_applied |
| malcolm rodriguez | LB | 0.2680 | 0.2185 | -18.5% | both | -10.2 | projection_delta_applied |
| adam butler | DL | 0.3250 | 0.3846 | +18.3% | both | +23.7 | projection_delta_applied |
| christian elliss | LB | 0.3040 | 0.3584 | +17.9% | both | +41.4 | projection_delta_applied |
| troy dye | LB | 0.2840 | 0.2332 | -17.9% | both | -10.3 | projection_delta_applied |
| trevin wallace | LB | 0.3380 | 0.3983 | +17.8% | both | +45.5 | projection_delta_applied |
| andrew mukuba | DB | 0.3370 | 0.3951 | +17.2% | both | +30.5 | projection_delta_applied |
| cody barton | LB | 0.4080 | 0.4771 | +16.9% | both | +52.4 | projection_delta_applied |
| jacob rodriguez | LB | 0.2560 | 0.2986 | +16.6% | both | +33.9 | projection_delta_applied |
| trenton simpson | LB | 0.2780 | 0.2329 | -16.2% | both | -7.7 | projection_delta_applied |
| justin strnad | LB | 0.2820 | 0.3276 | +16.2% | both | +36.3 | projection_delta_applied |
| jake golday | LB | 0.1500 | 0.1742 | +16.1% | both | +21.0 | projection_delta_applied |
| jiayir brown | DB | 0.4340 | 0.5022 | +15.7% | both | +36.1 | projection_delta_applied |
| javon hargrave | DL | 0.3500 | 0.4048 | +15.7% | both | +22.4 | projection_delta_applied |
| javon bullard | DB | 0.3490 | 0.4036 | +15.6% | both | +29.3 | projection_delta_applied |
| jamel dean | DB | 0.4110 | 0.4740 | +15.3% | both | +33.7 | projection_delta_applied |
| ashawn robinson | DL | 0.4210 | 0.4850 | +15.2% | both | +26.1 | projection_delta_applied |
| christian harris | LB | 0.2830 | 0.3251 | +14.9% | both | +34.7 | projection_delta_applied |

## Point-scale robustness (+/-10%)

The live ratio itself is scale-free, but the projection delta is measured in fantasy points. To expose dependence on the legacy combined-point scale, the candidate was rerun at 90% and 110% of the current legacy position baselines.

- Median candidate prod_mult spread across the full +/-10% scale range: **0.0033**
- P95 spread: **0.0125**
- Maximum spread: **0.0243**

## Interpretation

This method is deliberately conservative: it preserves what production actually valued before V1 and applies the new projection architecture as a delta instead of re-running every historical modeling choice. Rows where a new V1 source exists but the legacy pipeline had no comparable projection are held unchanged and surfaced rather than guessed.

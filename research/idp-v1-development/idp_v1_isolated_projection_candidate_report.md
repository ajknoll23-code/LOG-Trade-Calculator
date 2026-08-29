# IDP V1 Isolated Projection Candidate Report

## Status

**Preferred V1 bake candidate for validation; still does not edit `index.html`.**

This path isolates the validated projection-source change from historical history/prod-mult drift. It does not read `prod_mult_pipeline_output.json`. The actual pre-V1 baked prod_mult supplies the starting player ratio; a freshly reproducible old-model baseline supplies only the point-unit conversion used for the 55%-weighted projection delta.

## Old point-scale -> candidate baseline

| Pos | Canonical old point baseline | Old rank-32 | Candidate baseline | New rank-32 | Shift |
|---|---:|---|---:|---|---:|
| LB | 182.11 | zaire franklin | 201.60 | abdul carter | +10.7% |
| DL | 131.27 | quinnen williams | 135.28 | jonathon cooper | +3.1% |
| DB | 155.26 | malik mustapha | 162.16 | malik mustapha | +4.4% |

## True pre-V1 live -> isolated V1 prod_mult change

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 164 | -8.1% | +0.0% | +13.1% | -32.5% | +38.4% |
| DL | 108 | +4.7% | +11.8% | +13.6% | -11.1% | +19.4% |
| DB | 132 | -0.6% | +12.7% | +15.9% | -22.9% | +42.9% |

## Source cohorts

| Cohort | N | Median | P90 | P95 |
|---|---:|---:|---:|---:|
| both | 273 | +0.4% | +13.3% | +15.8% |
| fp_only | 35 | -5.3% | +0.0% | +2.6% |
| sleeper_only | 44 | -5.1% | -1.0% | +0.0% |
| no_new_data | 52 | -5.1% | +0.0% | +0.0% |

## Holds

- `hold_new_source_without_legacy_projection`: **22**

## Anchor methods

- `exact_unclamped`: **379**
- `floor_boundary_fallback`: **15**
- `floor_canonical_old_bounded`: **10**

## Clamp occupancy

| Pos | Old floor | New floor | Old ceiling | New ceiling |
|---|---:|---:|---:|---:|
| LB | 20 | 26 | 0 | 0 |
| DL | 4 | 4 | 0 | 0 |
| DB | 1 | 1 | 0 | 0 |

## Known anchors

| Player | Pos | Old | Candidate | Change | Cohort | Status |
|---|---|---:|---:|---:|---|---|
| bradley chubb | LB | 0.4110 | 0.5121 | +24.6% | both | projection_delta_applied |
| aidan hutchinson | DL | 0.9940 | 1.0730 | +7.9% | both | projection_delta_applied |
| myles garrett | DL | 1.1310 | 1.2160 | +7.5% | both | projection_delta_applied |
| fred warner | LB | 0.7730 | 0.7123 | -7.9% | both | projection_delta_applied |
| roquan smith | LB | 0.7760 | 0.7087 | -8.7% | both | projection_delta_applied |
| ej speed | LB | 0.2070 | 0.1774 | -14.3% | sleeper_only | projection_delta_applied |
| isaiah mcduffie | LB | 0.3740 | 0.2524 | -32.5% | both | projection_delta_applied |

## Top 20 risers

| Player | Pos | Old | Candidate | Change | Cohort | Status |
|---|---|---:|---:|---:|---|---|
| aj haulcy | DB | 0.2120 | 0.3030 | +42.9% | both | projection_delta_applied |
| denzel perryman | LB | 0.1730 | 0.2394 | +38.4% | both | projection_delta_applied |
| eric murray | DB | 0.3080 | 0.3987 | +29.4% | both | projection_delta_applied |
| mike hughes | DB | 0.2750 | 0.3433 | +24.8% | both | projection_delta_applied |
| bradley chubb | LB | 0.4110 | 0.5121 | +24.6% | both | projection_delta_applied |
| jevon holland | DB | 0.3410 | 0.4184 | +22.7% | both | projection_delta_applied |
| craig woodson | DB | 0.4040 | 0.4918 | +21.7% | both | projection_delta_applied |
| jonathan greenard | DL | 0.3460 | 0.4131 | +19.4% | both | projection_delta_applied |
| adam butler | DL | 0.3250 | 0.3848 | +18.4% | both | projection_delta_applied |
| andrew mukuba | DB | 0.3370 | 0.3959 | +17.5% | both | projection_delta_applied |
| khalil mack | LB | 0.2130 | 0.2486 | +16.7% | both | projection_delta_applied |
| jiayir brown | DB | 0.4340 | 0.5032 | +15.9% | both | projection_delta_applied |
| javon bullard | DB | 0.3490 | 0.4045 | +15.9% | both | projection_delta_applied |
| omar speights | LB | 0.2820 | 0.3266 | +15.8% | both | projection_delta_applied |
| javon hargrave | DL | 0.3500 | 0.4050 | +15.7% | both | projection_delta_applied |
| jamel dean | DB | 0.4110 | 0.4749 | +15.5% | both | projection_delta_applied |
| ashawn robinson | DL | 0.4210 | 0.4852 | +15.2% | both | projection_delta_applied |
| trevin wallace | LB | 0.3380 | 0.3887 | +15.0% | both | projection_delta_applied |
| christian elliss | LB | 0.3040 | 0.3495 | +15.0% | both | projection_delta_applied |
| jaylen watson | DB | 0.5140 | 0.5891 | +14.6% | both | projection_delta_applied |

## Top 20 fallers

| Player | Pos | Old | Candidate | Change | Cohort | Status |
|---|---|---:|---:|---:|---|---|
| isaiah mcduffie | LB | 0.3740 | 0.2524 | -32.5% | both | projection_delta_applied |
| dmarco jackson | LB | 0.2140 | 0.1500 | -29.9% | both | projection_delta_applied |
| nohl williams | DB | 0.3810 | 0.2939 | -22.9% | both | projection_delta_applied |
| malcolm rodriguez | LB | 0.2680 | 0.2115 | -21.1% | both | projection_delta_applied |
| troy dye | LB | 0.2840 | 0.2259 | -20.5% | both | projection_delta_applied |
| trenton simpson | LB | 0.2780 | 0.2256 | -18.8% | both | projection_delta_applied |
| jordan magee | LB | 0.1790 | 0.1520 | -15.1% | no_new_data | no_new_data_projection_hold |
| baron browning | LB | 0.2020 | 0.1728 | -14.5% | fp_only | hold_new_source_without_legacy_projection |
| charles snowden | LB | 0.2030 | 0.1737 | -14.4% | no_new_data | no_new_data_projection_hold |
| jamal adams | LB | 0.2070 | 0.1773 | -14.3% | no_new_data | no_new_data_projection_hold |
| kyle van noy | LB | 0.2090 | 0.1791 | -14.3% | no_new_data | no_new_data_projection_hold |
| ej speed | LB | 0.2070 | 0.1774 | -14.3% | sleeper_only | projection_delta_applied |
| leo chenal | LB | 0.3580 | 0.3083 | -13.9% | both | projection_delta_applied |
| lacale london | LB | 0.2360 | 0.2035 | -13.8% | fp_only | hold_new_source_without_legacy_projection |
| anthony nelson | LB | 0.2590 | 0.2243 | -13.4% | no_new_data | no_new_data_projection_hold |
| anthony hill | LB | 0.2640 | 0.2288 | -13.3% | sleeper_only | projection_delta_applied |
| lathan ransom | DB | 0.2930 | 0.2540 | -13.3% | both | projection_delta_applied |
| dennis gardeck | LB | 0.2860 | 0.2487 | -13.0% | fp_only | hold_new_source_without_legacy_projection |
| shaq thompson | LB | 0.2920 | 0.2541 | -13.0% | no_new_data | no_new_data_projection_hold |
| bryce huff | LB | 0.3010 | 0.2622 | -12.9% | no_new_data | no_new_data_projection_hold |

## Decision interpretation

If this isolated candidate remains close to the earlier validated sensitivity shape while the full canonical recompute is much more volatile, that is strong evidence that the first V1 production bake should use this isolated bridge and leave historical-lineage normalization for a separate later migration. Mixing both changes in one release would make player-value movement impossible to attribute cleanly.

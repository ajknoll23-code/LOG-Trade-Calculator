# IDP V1 Strict Projection-Only Bridge Report

## Status

**Diagnostic release candidate; `index.html` was not modified.**

This is the only candidate that guarantees a player with no projection delta stays exactly unchanged. It intentionally defers replacement-baseline normalization because the actual pre-V1 baked table is already inconsistent with the current rank-32=0.65 formula.

## Why baseline normalization must be a separate migration

| Pos | Actual old live rank-32 player | Old prod_mult | Implied ratio | Expected normalized prod_mult |
|---|---|---:|---:|---:|
| LB | devin lloyd | 0.6910 | 1.0547 | 0.6500 |
| DL | jalen redmond | 0.6160 | 0.9547 | 0.6500 |
| DB | antoine winfield | 0.6620 | 1.0160 | 0.6500 |

A rank-32 re-normalization would therefore move players even when their projection is unchanged. That is a separate historical-lineage correction, not part of the V1 source change.

## Point scales used only for projection-delta conversion

| Pos | Reproducible old-model baseline | Rank-32 player |
|---|---:|---|
| LB | 182.11 | zaire franklin |
| DL | 131.27 | quinnen williams |
| DB | 155.26 | malik mustapha |

## True pre-V1 live -> strict projection-only change

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 164 | +2.2% | +12.5% | +29.1% | -22.4% | +59.4% |
| DL | 108 | +8.3% | +15.9% | +17.8% | -7.9% | +23.9% |
| DB | 132 | +4.5% | +18.9% | +22.2% | -18.3% | +51.4% |

## Source cohorts

| Cohort | N | Median | P90 | P95 |
|---|---:|---:|---:|---:|
| both | 273 | +7.2% | +20.1% | +28.6% |
| fp_only | 35 | +0.0% | +5.2% | +9.8% |
| sleeper_only | 44 | +0.0% | +0.0% | +0.0% |
| no_new_data | 52 | +0.0% | +0.0% | +0.0% |

## Exact-hold verification

- `no_new_data_exact_hold`: **52** players, maximum absolute change **0.000000%**
- `hold_new_source_without_legacy_projection`: **22** players, maximum absolute change **0.000000%**

## Clamp occupancy

| Pos | Old floor | New floor | Old ceiling | New ceiling |
|---|---:|---:|---:|---:|
| LB | 20 | 14 | 0 | 0 |
| DL | 4 | 4 | 0 | 0 |
| DB | 1 | 1 | 0 | 0 |

## Known anchors

| Player | Pos | Old | Candidate | Change | Cohort | Status |
|---|---|---:|---:|---:|---|---|
| bradley chubb | LB | 0.4110 | 0.5776 | +40.5% | both | projection_delta_applied |
| aidan hutchinson | DL | 0.9940 | 1.1089 | +11.6% | both | projection_delta_applied |
| myles garrett | DL | 1.1310 | 1.2563 | +11.1% | both | projection_delta_applied |
| fred warner | LB | 0.7730 | 0.7993 | +3.4% | both | projection_delta_applied |
| roquan smith | LB | 0.7760 | 0.7953 | +2.5% | both | projection_delta_applied |
| ej speed | LB | 0.2070 | 0.2071 | +0.0% | sleeper_only | projection_delta_applied |
| isaiah mcduffie | LB | 0.3740 | 0.2902 | -22.4% | both | projection_delta_applied |

## Top 20 risers

| Player | Pos | Old | Candidate | Change | Cohort |
|---|---|---:|---:|---:|---|
| denzel perryman | LB | 0.1730 | 0.2757 | +59.4% | both |
| aj haulcy | DB | 0.2120 | 0.3209 | +51.4% | both |
| bradley chubb | LB | 0.4110 | 0.5776 | +40.5% | both |
| eric murray | DB | 0.3080 | 0.4208 | +36.6% | both |
| khalil mack | LB | 0.2130 | 0.2860 | +34.3% | both |
| mike hughes | DB | 0.2750 | 0.3631 | +32.0% | both |
| omar speights | LB | 0.2820 | 0.3723 | +32.0% | both |
| jake golday | LB | 0.1500 | 0.1976 | +31.7% | both |
| christian elliss | LB | 0.3040 | 0.3977 | +30.8% | both |
| trevin wallace | LB | 0.3380 | 0.4411 | +30.5% | both |
| jacob rodriguez | LB | 0.2560 | 0.3327 | +30.0% | both |
| jevon holland | DB | 0.3410 | 0.4414 | +29.4% | both |
| justin strnad | LB | 0.2820 | 0.3642 | +29.1% | both |
| cody barton | LB | 0.4080 | 0.5266 | +29.1% | both |
| craig woodson | DB | 0.4040 | 0.5181 | +28.2% | both |
| christian harris | LB | 0.2830 | 0.3615 | +27.7% | both |
| derrick barnes | LB | 0.3620 | 0.4585 | +26.7% | both |
| andrew mukuba | DB | 0.3370 | 0.4179 | +24.0% | both |
| jonathan greenard | DL | 0.3460 | 0.4288 | +23.9% | both |
| adam butler | DL | 0.3250 | 0.3996 | +23.0% | both |

## Top 20 fallers

| Player | Pos | Old | Candidate | Change | Cohort |
|---|---|---:|---:|---:|---|
| isaiah mcduffie | LB | 0.3740 | 0.2902 | -22.4% | both |
| dmarco jackson | LB | 0.2140 | 0.1669 | -22.0% | both |
| nohl williams | DB | 0.3810 | 0.3114 | -18.3% | both |
| malcolm rodriguez | LB | 0.2680 | 0.2448 | -8.7% | both |
| troy dye | LB | 0.2840 | 0.2608 | -8.2% | both |
| lathan ransom | DB | 0.2930 | 0.2698 | -7.9% | both |
| jadeveon clowney | DL | 0.6440 | 0.5931 | -7.9% | fp_only |
| trenton simpson | LB | 0.2780 | 0.2605 | -6.3% | both |
| isaiah polamao | DB | 0.5340 | 0.5146 | -3.6% | both |
| coby bryant | DB | 0.5250 | 0.5072 | -3.4% | sleeper_only |
| derick hall | DL | 0.4330 | 0.4210 | -2.8% | fp_only |
| tyler nubin | DB | 0.4680 | 0.4599 | -1.7% | both |
| leo chenal | LB | 0.3580 | 0.3520 | -1.7% | both |
| zion young | DL | 0.3100 | 0.3051 | -1.6% | fp_only |
| tyrel dodson | LB | 0.7320 | 0.7243 | -1.1% | both |
| geno stone | DB | 0.6800 | 0.6753 | -0.7% | both |
| pat surtain | DB | 0.2820 | 0.2819 | -0.0% | sleeper_only |
| joey porter | DB | 0.2930 | 0.2929 | -0.0% | sleeper_only |
| jack gibbens | LB | 0.3540 | 0.3539 | -0.0% | sleeper_only |
| carlton davis | DB | 0.4180 | 0.4179 | -0.0% | sleeper_only |

## Interpretation

This report should be compared with both the full canonical recompute and the normalized isolated candidate. If this strict bridge is selected for the first V1 release, replacement-baseline normalization becomes an explicit later migration with its own validation rather than a hidden side effect of the projection-source change.

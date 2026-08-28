# IDP V1 Model-Delta Transport Candidate Report

## Status

**Preferred engineering candidate to evaluate for the first V1 production bake. `index.html` is unchanged.**

This candidate computes the old->V1 change inside one reproducible model, including rank-32 baseline movement, then transports only that change onto the actual pre-V1 live PROD_MULT table. It neither replaces live values with the regenerated old model nor forces the historically drifted live table through a fresh baseline normalization.

Comparable old/new model cohort: **330** of **404** live IDP keys.

## Internally consistent model baseline movement

| Pos | Old model baseline | Old rank-32 | V1 baseline | V1 rank-32 | Shift |
|---|---:|---|---:|---|---:|
| LB | 182.11 | zaire franklin | 188.32 | ernest jones | +3.4% |
| DL | 131.27 | quinnen williams | 137.01 | milton williams | +4.4% |
| DB | 155.26 | malik mustapha | 160.54 | caleb downs | +3.4% |

## True pre-V1 live -> transported V1 change

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 164 | +0.0% | +7.2% | +23.1% | -27.3% | +49.7% |
| DL | 108 | +2.2% | +8.6% | +12.0% | -12.7% | +14.9% |
| DB | 132 | +0.5% | +13.2% | +17.0% | -22.5% | +42.1% |

## Source cohorts

| Cohort | N | Median | P90 | P95 |
|---|---:|---:|---:|---:|
| both | 273 | +2.1% | +13.4% | +22.9% |
| fp_only | 35 | +0.0% | +0.7% | +4.1% |
| sleeper_only | 44 | -4.0% | -0.8% | +0.0% |
| no_new_data | 52 | +0.0% | +0.0% | +0.0% |

## Exact holds

- No comparable old projection: **74** players; maximum absolute change **0.000000%**

## Known anchors

| Player | Pos | Old | Candidate | Change | Cohort | Status |
|---|---|---:|---:|---:|---|---|
| bradley chubb | LB | 0.4110 | 0.5580 | +35.8% | both | model_delta_transported |
| aidan hutchinson | DL | 0.9940 | 1.0559 | +6.2% | both | model_delta_transported |
| myles garrett | DL | 1.1310 | 1.1966 | +5.8% | both | model_delta_transported |
| fred warner | LB | 0.7730 | 0.7699 | -0.4% | both | model_delta_transported |
| roquan smith | LB | 0.7760 | 0.7659 | -1.3% | both | model_delta_transported |
| ej speed | LB | 0.2070 | 0.1953 | -5.7% | sleeper_only | model_delta_transported |
| isaiah mcduffie | LB | 0.3740 | 0.2774 | -25.8% | both | model_delta_transported |

## Top 20 risers

| Player | Pos | Old | Candidate | Change | Cohort |
|---|---|---:|---:|---:|---|
| denzel perryman | LB | 0.1730 | 0.2590 | +49.7% | both |
| aj haulcy | DB | 0.2120 | 0.3012 | +42.1% | both |
| bradley chubb | LB | 0.4110 | 0.5580 | +35.8% | both |
| eric murray | DB | 0.3080 | 0.3980 | +29.2% | both |
| omar speights | LB | 0.2820 | 0.3564 | +26.4% | both |
| khalil mack | LB | 0.2130 | 0.2686 | +26.1% | both |
| christian elliss | LB | 0.3040 | 0.3799 | +25.0% | both |
| mike hughes | DB | 0.2750 | 0.3417 | +24.3% | both |
| cody barton | LB | 0.4080 | 0.5060 | +24.0% | both |
| trevin wallace | LB | 0.3380 | 0.4189 | +23.9% | both |
| jevon holland | DB | 0.3410 | 0.4206 | +23.3% | both |
| christian harris | LB | 0.2830 | 0.3485 | +23.1% | both |
| justin strnad | LB | 0.2820 | 0.3471 | +23.1% | both |
| jacob rodriguez | LB | 0.2560 | 0.3150 | +23.0% | both |
| craig woodson | DB | 0.4040 | 0.4960 | +22.8% | both |
| jake golday | LB | 0.1500 | 0.1841 | +22.7% | both |
| derrick barnes | LB | 0.3620 | 0.4392 | +21.3% | both |
| andrew mukuba | DB | 0.3370 | 0.3965 | +17.7% | both |
| dru phillips | DB | 0.6750 | 0.7903 | +17.1% | both |
| jiayir brown | DB | 0.4340 | 0.5078 | +17.0% | both |

## Top 20 fallers

| Player | Pos | Old | Candidate | Change | Cohort |
|---|---|---:|---:|---:|---|
| dmarco jackson | LB | 0.2140 | 0.1556 | -27.3% | both |
| isaiah mcduffie | LB | 0.3740 | 0.2774 | -25.8% | both |
| nohl williams | DB | 0.3810 | 0.2954 | -22.5% | both |
| troy dye | LB | 0.2840 | 0.2467 | -13.1% | both |
| lathan ransom | DB | 0.2930 | 0.2558 | -12.7% | both |
| jadeveon clowney | DL | 0.6440 | 0.5625 | -12.7% | fp_only |
| malcolm rodriguez | LB | 0.2680 | 0.2349 | -12.4% | both |
| trenton simpson | LB | 0.2780 | 0.2473 | -11.0% | both |
| zion young | DL | 0.3100 | 0.2809 | -9.4% | fp_only |
| derick hall | DL | 0.4330 | 0.3983 | -8.0% | fp_only |
| isaiah polamao | DB | 0.5340 | 0.4946 | -7.4% | both |
| coby bryant | DB | 0.5250 | 0.4875 | -7.1% | sleeper_only |
| joey porter | DB | 0.2930 | 0.2731 | -6.8% | sleeper_only |
| pat surtain | DB | 0.2820 | 0.2629 | -6.8% | sleeper_only |
| leo chenal | LB | 0.3580 | 0.3352 | -6.4% | both |
| aj terrell | DB | 0.2970 | 0.2782 | -6.3% | sleeper_only |
| gervon dexter | DL | 0.4290 | 0.4026 | -6.2% | sleeper_only |
| dj reed | DB | 0.3370 | 0.3165 | -6.1% | sleeper_only |
| tyler nubin | DB | 0.4680 | 0.4399 | -6.0% | both |
| billy bowman | DB | 0.3450 | 0.3248 | -5.9% | sleeper_only |

## Why this bridge is different

- It **does** preserve the V1 model’s legitimate replacement-baseline effect, because old and V1 baselines are recomputed inside the same reproducible comparable model.
- It **does not** import the regenerated old model’s absolute player values into production, because only the old->new model delta is transported.
- It **does not** re-normalize the historically drifted live table just because V1 is being deployed.
- It holds players with no comparable old projection exactly unchanged instead of inventing a zero or an unverifiable delta.


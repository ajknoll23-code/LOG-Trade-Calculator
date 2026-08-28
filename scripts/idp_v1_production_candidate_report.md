# IDP V1 Canonical Production Candidate Report

## Status

**Diagnostic candidate only. `index.html` was not modified.**

This candidate removes `prod_mult_pipeline_output.json` from the V1 computational path. It combines the canonical extracted history component with the validated category-level V1 projection and recomputes rank-32 LB/DL/DB baselines over the exact immutable pre-V1 live IDP table.

## Population / source coverage

- Live pre-V1 IDP keys evaluated: **404**
- Legacy model-position vs current valuation-position mismatches intentionally held separate from V1: **46**
- V1 source cohort `both`: **273**
- V1 source cohort `fp_only`: **35**
- V1 source cohort `no_new_data`: **52**
- V1 source cohort `sleeper_only`: **44**

Identity methods:
- `high_confidence_crosswalk`: **312**
- `league_sync+ppg_history_id`: **31**
- `free_agent_sync+ppg_history_id`: **24**
- `ppg_history_id`: **21**
- `league_sync`: **8**
- `no_stable_sleeper_id`: **8**

Fallback/hold counts:
- `hold_live_no_projection_lineage`: **52**

## Candidate replacement baselines

| Pos | Combined baseline | Rank-32 player |
|---|---:|---|
| LB | 188.32 | ernest jones |
| DL | 137.01 | milton williams |
| DB | 160.63 | julian love |

## True pre-V1 live -> canonical V1 prod_mult change

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 164 | +0.0% | +38.4% | +77.3% | -39.6% | +125.6% |
| DL | 108 | +9.5% | +52.4% | +73.8% | -40.9% | +141.5% |
| DB | 132 | +1.6% | +48.6% | +63.7% | -25.0% | +126.4% |

## Change by V1 source cohort

| Cohort | N | Median | P90 | P95 |
|---|---:|---:|---:|---:|
| both | 273 | +4.3% | +48.4% | +70.7% |
| fp_only | 35 | -2.9% | +69.1% | +91.4% |
| sleeper_only | 44 | -0.2% | +59.8% | +99.2% |
| no_new_data | 52 | +0.0% | +0.0% | +0.0% |

## Clamp occupancy

| Pos | Old floor | New floor | Old ceiling | New ceiling |
|---|---:|---:|---:|---:|
| LB | 20 | 12 | 0 | 0 |
| DL | 4 | 2 | 0 | 0 |
| DB | 1 | 1 | 0 | 0 |

## Known anchors

| Player | Pos | Old | Candidate | Change | Cohort | Identity |
|---|---|---:|---:|---:|---|---|
| bradley chubb | LB | 0.4110 | 0.4768 | +16.0% | both | high_confidence_crosswalk |
| aidan hutchinson | DL | 0.9940 | 1.1112 | +11.8% | both | high_confidence_crosswalk |
| myles garrett | DL | 1.1310 | 1.2641 | +11.8% | both | high_confidence_crosswalk |
| fred warner | LB | 0.7730 | 0.7626 | -1.3% | both | high_confidence_crosswalk |
| roquan smith | LB | 0.7760 | 0.7626 | -1.7% | both | high_confidence_crosswalk |
| ej speed | LB | 0.2070 | 0.2438 | +17.8% | sleeper_only | high_confidence_crosswalk |
| christian izien | n/a | n/a | n/a | n/a | n/a | not in live baseline |
| isaiah mcduffie | LB | 0.3740 | 0.2745 | -26.6% | both | high_confidence_crosswalk |

## Top 20 risers

| Player | Pos | Old | Candidate | Change | Source |
|---|---|---:|---:|---:|---|
| kayvon thibodeaux | DL | 0.2180 | 0.5265 | +141.5% | both |
| kayden mcdonald | DL | 0.1500 | 0.3598 | +139.9% | sleeper_only |
| aj haulcy | DB | 0.2120 | 0.4800 | +126.4% | both |
| denzel perryman | LB | 0.1730 | 0.3903 | +125.6% | both |
| avieon terrell | DB | 0.1620 | 0.3618 | +123.3% | fp_only |
| quinyon mitchell | DB | 0.2830 | 0.6106 | +115.8% | fp_only |
| cashius howell | DL | 0.1500 | 0.3210 | +114.0% | sleeper_only |
| jonathan greenard | DL | 0.3460 | 0.7365 | +112.9% | both |
| michael hoecht | LB | 0.1500 | 0.3081 | +105.4% | sleeper_only |
| jake golday | LB | 0.1500 | 0.2978 | +98.5% | both |
| kaleb elarmsorr | LB | 0.1500 | 0.2905 | +93.7% | both |
| devonte wyatt | DL | 0.3070 | 0.5939 | +93.5% | both |
| khalil mack | LB | 0.2130 | 0.4106 | +92.8% | both |
| mike hughes | DB | 0.2750 | 0.5271 | +91.7% | both |
| eric murray | DB | 0.3080 | 0.5710 | +85.4% | both |
| jahlani tavai | LB | 0.1500 | 0.2714 | +80.9% | fp_only |
| samson ebukam | LB | 0.1550 | 0.2802 | +80.8% | both |
| dj wonnum | LB | 0.1860 | 0.3353 | +80.3% | both |
| jaishawn barham | LB | 0.1500 | 0.2682 | +78.8% | both |
| milton williams | DL | 0.3650 | 0.6500 | +78.1% | both |

## Top 20 fallers

| Player | Pos | Old | Candidate | Change | Source |
|---|---|---:|---:|---:|---|
| poona ford | DL | 0.6380 | 0.3768 | -40.9% | both |
| jacob martin | LB | 0.3540 | 0.2138 | -39.6% | fp_only |
| alquadin muhammad | DL | 0.6620 | 0.4021 | -39.3% | fp_only |
| calais campbell | DL | 0.7560 | 0.4629 | -38.8% | fp_only |
| jermaine johnson | LB | 0.4340 | 0.2807 | -35.3% | sleeper_only |
| nolan smith | LB | 0.4360 | 0.2834 | -35.0% | sleeper_only |
| elandon roberts | LB | 0.4100 | 0.2668 | -34.9% | fp_only |
| von miller | LB | 0.3200 | 0.2094 | -34.6% | fp_only |
| harold landry | LB | 0.7410 | 0.5097 | -31.2% | sleeper_only |
| will anderson | LB | 0.9090 | 0.6334 | -30.3% | sleeper_only |
| jaelan phillips | LB | 0.6640 | 0.4653 | -29.9% | both |
| malcolm rodriguez | LB | 0.2680 | 0.1923 | -28.2% | both |
| joseph ossai | LB | 0.5030 | 0.3672 | -27.0% | both |
| isaiah mcduffie | LB | 0.3740 | 0.2745 | -26.6% | both |
| uchenna nwosu | LB | 0.5280 | 0.3938 | -25.4% | both |
| micah mcfadden | LB | 0.2840 | 0.2123 | -25.2% | fp_only |
| jaylinn hawkins | DB | 0.6730 | 0.5049 | -25.0% | both |
| rashan gary | LB | 0.5960 | 0.4478 | -24.9% | both |
| alex highsmith | LB | 0.7660 | 0.5792 | -24.4% | both |
| odafe oweh | LB | 0.5790 | 0.4381 | -24.3% | both |

## Interpretation guardrail

This report intentionally shows the result of a **full reproducible history+projection recomputation while preserving the legacy production-position grouping**. The separate current valuation position is surfaced explicitly. If movement is materially larger than the already-validated live-anchored projection-delta experiment, that difference is evidence of historical lineage drift in the old baked values -- not evidence that V1 projection math itself suddenly changed. A production decision should explicitly choose whether V1 is allowed to absorb that historical drift or whether the first V1 bake should isolate the projection-source change only.

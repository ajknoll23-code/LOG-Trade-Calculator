# Age Curve V2 — Phase 4 Bridge Calibration

Method: `age-curve-v2-phase4-bridge-calibration-v1`  
Status: **`RESEARCH_ONLY_AGE_BRIDGE_CALIBRATION`**

## Guardrail

**Research only. No deployed AGE_CURVE or player value is changed.**

Bridge formula:

`deployed_age + weight × (empirical_age − deployed_age)`

## Bridge results

| Variant | Hist MAE | Δ MAE | Hist Spearman | Δ Spearman | Median current Δ | P90 current Δ | Min pos rank ρ | Min top-24 | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `position_k25__w25__all_positions` | 2.1570 | -0.1006 | 0.6807 | +0.0055 | 5.7% | 9.7% | 0.9875 | 91.7% | PASS |
| `position_k25__w25__qb_control` | 2.1629 | -0.0946 | 0.6805 | +0.0054 | 5.8% | 9.9% | 0.9875 | 91.7% | PASS |
| `position_k25__w50__all_positions` | 2.0796 | -0.1779 | 0.6854 | +0.0103 | 11.4% | 19.5% | 0.9423 | 87.5% | PASS |
| `position_k25__w50__qb_control` | 2.0885 | -0.1691 | 0.6852 | +0.0101 | 11.5% | 19.7% | 0.9423 | 87.5% | PASS |
| `position_k25__w75__all_positions` | 2.0240 | -0.2335 | 0.6893 | +0.0141 | 17.2% | 29.2% | 0.8618 | 79.2% | FAIL |
| `position_k25__w75__qb_control` | 2.0337 | -0.2239 | 0.6890 | +0.0138 | 17.3% | 29.6% | 0.8618 | 79.2% | FAIL |
| `tier_k25__w25__all_positions` | 2.1391 | -0.1184 | 0.6826 | +0.0074 | 6.9% | 12.9% | 0.9324 | 87.5% | PASS |
| `tier_k25__w25__qb_control` | 2.1458 | -0.1117 | 0.6824 | +0.0073 | 7.0% | 13.0% | 0.9324 | 87.5% | PASS |
| `tier_k25__w50__all_positions` | 2.0504 | -0.2072 | 0.6889 | +0.0137 | 13.8% | 25.9% | 0.6940 | 62.5% | FAIL |
| `tier_k25__w50__qb_control` | 2.0603 | -0.1973 | 0.6885 | +0.0134 | 14.0% | 26.0% | 0.6940 | 62.5% | FAIL |
| `tier_k25__w75__all_positions` | 1.9922 | -0.2654 | 0.6935 | +0.0183 | 20.7% | 38.8% | 0.4914 | 58.3% | FAIL |
| `tier_k25__w75__qb_control` | 2.0026 | -0.2550 | 0.6930 | +0.0178 | 21.0% | 38.9% | 0.4914 | 58.3% | FAIL |
| `tier_k50__w25__all_positions` | 2.1433 | -0.1142 | 0.6817 | +0.0066 | 6.0% | 10.9% | 0.9450 | 87.5% | PASS |
| `tier_k50__w25__qb_control` | 2.1499 | -0.1076 | 0.6816 | +0.0064 | 6.3% | 11.1% | 0.9450 | 87.5% | PASS |
| `tier_k50__w50__all_positions` | 2.0564 | -0.2011 | 0.6873 | +0.0121 | 12.0% | 21.8% | 0.7388 | 62.5% | FAIL |
| `tier_k50__w50__qb_control` | 2.0663 | -0.1913 | 0.6870 | +0.0119 | 12.5% | 22.3% | 0.7388 | 62.5% | FAIL |
| `tier_k50__w75__all_positions` | 1.9968 | -0.2608 | 0.6916 | +0.0164 | 17.9% | 32.7% | 0.5532 | 58.3% | FAIL |
| `tier_k50__w75__qb_control` | 2.0075 | -0.2500 | 0.6911 | +0.0160 | 18.8% | 33.4% | 0.5532 | 58.3% | FAIL |

## Screened survivors

1. `position_k25__w50__all_positions`
2. `position_k25__w50__qb_control`
3. `tier_k25__w25__all_positions`
4. `tier_k50__w25__all_positions`
5. `tier_k25__w25__qb_control`
6. `tier_k50__w25__qb_control`
7. `position_k25__w25__all_positions`
8. `position_k25__w25__qb_control`

Monitoring leader: **`position_k25__w50__all_positions`**

This is **not a deployment choice**.

## Largest movers for monitoring leader

| Player | Pos | Age | Tier | Current | Shadow | Change |
|---|---|---:|---|---:|---:|---:|
| nic scourton | DL | 21 | depth | 1649 | 2166 | 31.4% |
| shemar stewart | DL | 22 | depth | 1055 | 1358 | 28.7% |
| mykel williams | DL | 22 | depth | 1454 | 1843 | 26.8% |
| walter nolen | DL | 22 | depth | 1803 | 2255 | 25.1% |
| mason graham | DL | 22 | depth | 1962 | 2439 | 24.3% |
| jalon walker | DL | 22 | depth | 2010 | 2495 | 24.1% |
| mason taylor | TE | 22 | depth | 1079 | 1330 | 23.3% |
| shemar james | LB | 22 | depth | 1389 | 1707 | 22.9% |
| geno smith | QB | 35 | rotation | 1897 | 2329 | 22.8% |
| elijah arroyo | TE | 23 | depth | 680 | 830 | 22.1% |
| chris brazzell | WR | 22 | depth | 578 | 705 | 22.0% |
| james pearce | LB | 22 | depth | 1808 | 2191 | 21.2% |
| abdul carter | DL | 22 | starter | 2956 | 3558 | 20.4% |
| terrance ferguson | TE | 23 | depth | 1126 | 1355 | 20.3% |
| tj hockenson | TE | 29 | rotation | 2305 | 1844 | -20.0% |
| juwan johnson | TE | 29 | rotation | 2932 | 2346 | -20.0% |
| fred warner | LB | 29 | starter | 4743 | 3797 | -19.9% |
| roquan smith | LB | 29 | starter | 4718 | 3777 | -19.9% |
| frankie luvu | LB | 29 | depth | 3074 | 2461 | -19.9% |
| zack baun | LB | 29 | starter | 4735 | 3791 | -19.9% |
| quincy williams | LB | 29 | starter | 4229 | 3386 | -19.9% |
| christian rozeboom | LB | 29 | depth | 2639 | 2113 | -19.9% |
| dre greenlaw | LB | 29 | depth | 3081 | 2467 | -19.9% |
| azeez alshaair | LB | 29 | rotation | 3841 | 3076 | -19.9% |
| jalen nailor | WR | 27 | rotation | 2618 | 2098 | -19.9% |

## Next step

Freeze the smallest stable survivor family before 2026 outcomes and grade against future realized production alongside the deployed control.

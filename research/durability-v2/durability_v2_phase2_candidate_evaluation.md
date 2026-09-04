# Durability / Availability V2 — Phase 2 Candidate Evaluation

Method: `durability-v2-phase2-candidate-evaluation-v1`  
Status: **`RESEARCH_ONLY_DURABILITY_CANDIDATE_EVALUATION`**

## Guardrail

**Research only. No deployed durability or player value is changed.**

Primary metric: **next-season availability MAE**.

The survivor-only and unconditional targets are intentionally kept separate. The former is the cleaner durability target; the latter also contains role loss, retirement, and league exit.

## Survivor Only target

### `survivor_only` — `one_year`

| Variant | N | MAE | Δ MAE | RMSE | Spearman | Δ Spearman | Pos improved | Folds improved | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `position_median` | 12488 | 0.2408 | +0.0118 | 0.3331 | 0.0991 | -0.2140 | 0/7 | 0/10 | FAIL |
| `deployed_r2_blend` | 12488 | 0.2290 | — | 0.3144 | 0.3131 | — | — | — | PASS |
| `own_raw` | 12488 | 0.2334 | +0.0044 | 0.3289 | 0.3472 | +0.0341 | 1/7 | 3/10 | FAIL |
| `trained_blend` | 12488 | 0.2163 | -0.0126 | 0.2955 | 0.3494 | +0.0362 | 7/7 | 10/10 | PASS |
| `ols_current` | 12488 | 0.2303 | +0.0013 | 0.2791 | 0.3490 | +0.0359 | 3/7 | 4/10 | FAIL |

Monitoring leader: **`trained_blend`**

### `survivor_only` — `two_year`

| Variant | N | MAE | Δ MAE | RMSE | Spearman | Δ Spearman | Pos improved | Folds improved | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `position_median` | 8735 | 0.2346 | +0.0110 | 0.3380 | 0.1099 | -0.1710 | 0/7 | 0/9 | FAIL |
| `deployed_r2_blend` | 8735 | 0.2236 | — | 0.3195 | 0.2809 | — | — | — | PASS |
| `own_raw` | 8735 | 0.2286 | +0.0050 | 0.3254 | 0.3189 | +0.0380 | 1/7 | 2/9 | FAIL |
| `trained_blend` | 8735 | 0.2134 | -0.0103 | 0.2998 | 0.3225 | +0.0417 | 7/7 | 9/9 | PASS |
| `ols_current` | 8735 | 0.2268 | +0.0032 | 0.2762 | 0.3207 | +0.0398 | 2/7 | 4/9 | FAIL |
| `mean_2year` | 8735 | 0.2195 | -0.0041 | 0.3017 | 0.3208 | +0.0399 | 5/7 | 5/9 | FAIL |
| `recency_2year` | 8735 | 0.2176 | -0.0061 | 0.3014 | 0.3314 | +0.0505 | 6/7 | 6/9 | FAIL |
| `ols_current_prior1` | 8735 | 0.2242 | +0.0005 | 0.2739 | 0.3340 | +0.0531 | 3/7 | 4/9 | FAIL |

Monitoring leader: **`trained_blend`**

### `survivor_only` — `three_year`

| Variant | N | MAE | Δ MAE | RMSE | Spearman | Δ Spearman | Pos improved | Folds improved | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `position_median` | 6017 | 0.2315 | +0.0096 | 0.3357 | 0.1143 | -0.1542 | 0/7 | 0/8 | FAIL |
| `deployed_r2_blend` | 6017 | 0.2219 | — | 0.3192 | 0.2685 | — | — | — | PASS |
| `own_raw` | 6017 | 0.2285 | +0.0066 | 0.3276 | 0.3001 | +0.0316 | 1/7 | 1/8 | FAIL |
| `trained_blend` | 6017 | 0.2137 | -0.0082 | 0.3031 | 0.3041 | +0.0356 | 7/7 | 8/8 | PASS |
| `ols_current` | 6017 | 0.2278 | +0.0059 | 0.2775 | 0.3007 | +0.0322 | 2/7 | 2/8 | FAIL |
| `mean_3year` | 6017 | 0.2177 | -0.0042 | 0.2975 | 0.2906 | +0.0221 | 4/7 | 7/8 | PASS |
| `recency_3year` | 6017 | 0.2145 | -0.0074 | 0.2969 | 0.3141 | +0.0456 | 6/7 | 7/8 | PASS |
| `ols_current_prior1_prior2` | 6017 | 0.2249 | +0.0030 | 0.2750 | 0.3109 | +0.0424 | 3/7 | 4/8 | FAIL |

Monitoring leader: **`trained_blend`**

## Unconditional target

### `unconditional` — `one_year`

| Variant | N | MAE | Δ MAE | RMSE | Spearman | Δ Spearman | Pos improved | Folds improved | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `position_median` | 16346 | 0.3714 | +0.0200 | 0.4730 | 0.0705 | -0.3084 | 0/7 | 0/10 | FAIL |
| `deployed_r2_blend` | 16346 | 0.3514 | — | 0.4470 | 0.3789 | — | — | — | PASS |
| `own_raw` | 16346 | 0.2843 | -0.0671 | 0.3929 | 0.4805 | +0.1016 | 7/7 | 10/10 | PASS |
| `trained_blend` | 16346 | 0.2843 | -0.0671 | 0.3929 | 0.4805 | +0.1016 | 7/7 | 10/10 | PASS |
| `ols_current` | 16346 | 0.2978 | -0.0535 | 0.3504 | 0.4771 | +0.0982 | 7/7 | 10/10 | PASS |

Monitoring leader: **`own_raw`**

### `unconditional` — `two_year`

| Variant | N | MAE | Δ MAE | RMSE | Spearman | Δ Spearman | Pos improved | Folds improved | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `position_median` | 11171 | 0.3630 | +0.0180 | 0.4797 | 0.0693 | -0.2940 | 0/7 | 0/9 | FAIL |
| `deployed_r2_blend` | 11171 | 0.3450 | — | 0.4550 | 0.3633 | — | — | — | PASS |
| `own_raw` | 11171 | 0.2870 | -0.0580 | 0.3988 | 0.4515 | +0.0882 | 7/7 | 9/9 | PASS |
| `trained_blend` | 11171 | 0.2870 | -0.0580 | 0.3988 | 0.4515 | +0.0882 | 7/7 | 9/9 | PASS |
| `ols_current` | 11171 | 0.2996 | -0.0454 | 0.3520 | 0.4471 | +0.0838 | 7/7 | 9/9 | PASS |
| `mean_2year` | 11171 | 0.2960 | -0.0490 | 0.3961 | 0.4421 | +0.0788 | 7/7 | 9/9 | PASS |
| `recency_2year` | 11171 | 0.2890 | -0.0560 | 0.3893 | 0.4600 | +0.0966 | 7/7 | 9/9 | PASS |
| `ols_current_prior1` | 11171 | 0.2956 | -0.0493 | 0.3490 | 0.4615 | +0.0981 | 7/7 | 9/9 | PASS |

Monitoring leader: **`own_raw`**

### `unconditional` — `three_year`

| Variant | N | MAE | Δ MAE | RMSE | Spearman | Δ Spearman | Pos improved | Folds improved | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `position_median` | 7695 | 0.3628 | +0.0172 | 0.4829 | 0.0840 | -0.2806 | 0/7 | 0/8 | FAIL |
| `deployed_r2_blend` | 7695 | 0.3455 | — | 0.4591 | 0.3646 | — | — | — | PASS |
| `own_raw` | 7695 | 0.2890 | -0.0566 | 0.4028 | 0.4454 | +0.0808 | 7/7 | 8/8 | PASS |
| `trained_blend` | 7695 | 0.2890 | -0.0566 | 0.4028 | 0.4454 | +0.0808 | 7/7 | 8/8 | PASS |
| `ols_current` | 7695 | 0.3009 | -0.0446 | 0.3535 | 0.4425 | +0.0779 | 7/7 | 8/8 | PASS |
| `mean_3year` | 7695 | 0.3091 | -0.0365 | 0.4104 | 0.4130 | +0.0484 | 7/7 | 8/8 | PASS |
| `recency_3year` | 7695 | 0.2957 | -0.0498 | 0.3962 | 0.4516 | +0.0870 | 7/7 | 8/8 | PASS |
| `ols_current_prior1_prior2` | 7695 | 0.2961 | -0.0494 | 0.3500 | 0.4553 | +0.0907 | 7/7 | 8/8 | PASS |

Monitoring leader: **`own_raw`**

## Training-fold optimized own-history weights

One-year family, median optimized weight across held-out folds:

| Target | QB | RB | WR | TE | DL | LB | DB |
|---|---:|---:|---:|---:|---:|---:|---:|
| survivor_only | 0.85 | 0.50 | 0.55 | 0.50 | 0.55 | 0.45 | 0.50 |
| unconditional | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

## Phase 3

- Survivor one-year leader: **`trained_blend`**
- Unconditional one-year leader: **`own_raw`**

Phase 3 should shadow current projected-games behavior only if the survivor-only track produces a stable non-control winner. Treat the unconditional track as a separate broader availability/survival diagnostic because it overlaps conceptually with Age V2, Production V2, and Opportunity V2. If longer-history variants win only on matched veteran cohorts, test them position-specifically rather than applying them to every player.

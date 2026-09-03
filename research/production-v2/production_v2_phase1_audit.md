# Production V2 — Phase 1 Lineage & Benchmark Audit

## Decision

**RESEARCH ONLY — no production change is authorized by this audit.**

Phase 1 is deliberately a lineage/coverage/blast-radius audit, not a claim that the benchmark formula is optimal.
It freezes the current player-value architecture and swaps only the production input in a counterfactual reconstruction.

- Current tracked players: **549**
- Phase-1 candidate values built: **518** (94.4%)
- Production files mutated: **0**
- `index.html` mutated: **No**

## Benchmark formula used only for Phase 1

1. **History:** canonical `scripts/model/production_history_component.py` (existing 2025 shrinkage + durability math, unchanged).
2. **Offense forward projection:** 50/50 Trade-Desk-normalized FantasyPros + league-scored Sleeper when both exist; single-source fallback otherwise. **Not calibrated.**
3. **IDP forward projection:** canonical `scripts/model/idp_v1_projection.py` V1 category ensemble.
4. **History vs forward:** 45% / 55%. **Inherited benchmark, not calibrated for V2.**
5. **Normalization:** existing research replacement ranks and `clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)`. **Benchmark only.**
6. **Held fixed:** current position weights, age curves, RB continuous age, role floors/rescues, QB/LB decline rules, and global scale.

## Data coverage

| Pos | Current | PPG row | Stable Sleeper ID | Sleeper proj | FP proj | Both rows | Usable forward | Candidate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| QB | 64 | 49 | 63 | 34 | 53 | 33 | 54 | 54 |
| RB | 97 | 77 | 96 | 89 | 78 | 74 | 93 | 93 |
| WR | 114 | 83 | 114 | 108 | 96 | 96 | 108 | 108 |
| TE | 44 | 34 | 44 | 43 | 37 | 37 | 43 | 43 |
| DL | 86 | 74 | 86 | 79 | 66 | 62 | 83 | 83 |
| LB | 79 | 64 | 78 | 68 | 68 | 62 | 74 | 74 |
| DB | 65 | 58 | 64 | 60 | 54 | 51 | 63 | 63 |

## Identity join diagnostics

- 2026 Sleeper stable IDs in current identity universe: **9419**
- FantasyPros rows mapped by unified production crosswalk: **922**
- Unified crosswalk manual-review rows skipped: **0**
- Minimum required FP coverage vs Sleeper per offensive position: **50.0%**

### Current PLAYER_DB → Sleeper resolution methods

- `current_2026_ambiguous_name_position`: **1**
- `current_2026_name_position_unique`: **106**
- `current_2026_no_candidate`: **3**
- `ppg_stable_id`: **439**

### Unified FantasyPros crosswalk methods used

- `name_collision_resolved_by_position_team`: **4**
- `name_position_team_confirmed`: **918**

## Data-quality flags

- `candidate_no_history_role_rescue_applied`: **7**
- `history_present_forward_missing`: **31**
- `missing_forward_projection`: **31**
- `missing_ppg_row`: **110**
- `missing_stable_sleeper_id`: **4**
- `ppg_position_mismatch_vs_current_player_db`: **23**
- `zero_game_history_records`: **110**

### Forward projection source counts

- `idp_no_forward_projection`: **8**
- `idp_v1_both`: **175**
- `idp_v1_fp_only`: **13**
- `idp_v1_sleeper_only`: **32**
- `missing_stable_sleeper_id`: **4**
- `offense_benchmark_fp50_sleeper50`: **240**
- `offense_fantasypros_only`: **24**
- `offense_no_forward_projection`: **19**
- `offense_sleeper_only`: **34**

## Phase-1 position baselines

These are diagnostic benchmark anchors only; Phase 2 will test whether this normalization should survive at all.

| Pos | Rank | Anchor player | Combined points | Candidate cohort |
|---|---:|---|---:|---:|
| QB | 18 | jordan love | 243.89 | 54 |
| RB | 32 | bhayshul tuten | 171.31 | 93 |
| WR | 36 | stefon diggs | 154.51 | 108 |
| TE | 15 | juwan johnson | 128.84 | 43 |
| DL | 32 | ed oliver | 150.19 | 83 |
| LB | 32 | tj edwards | 182.04 | 74 |
| DB | 32 | jalen pitre | 159.15 | 63 |

## Current vs Phase-1 movement

| Pos | N | Median FV change | P90 abs FV change | P95 abs FV change | Max abs FV change | Median abs PM delta |
|---|---:|---:|---:|---:|---:|---:|
| QB | 54 | 0.0% | 5.2% | 14.3% | 47.8% | 0.0019 |
| RB | 93 | -2.9% | 20.3% | 31.1% | 149.0% | 0.0298 |
| WR | 108 | -7.2% | 31.1% | 41.9% | 132.6% | 0.0543 |
| TE | 43 | -1.2% | 13.8% | 24.7% | 88.5% | 0.0148 |
| DL | 83 | -5.1% | 27.5% | 53.0% | 104.4% | 0.0366 |
| LB | 74 | 2.8% | 29.3% | 47.3% | 76.2% | 0.0206 |
| DB | 63 | -0.3% | 17.2% | 34.7% | 93.5% | 0.0031 |

## Rank stability

Ranks are measured on the exact common current/candidate cohort for each position.

| Pos | N | Spearman | Top-N | Top-N overlap | Max rank move |
|---|---:|---:|---:|---:|---:|
| QB | 54 | 0.9959 | 18 | 100.0% | 4 |
| RB | 93 | 0.9678 | 32 | 93.8% | 29 |
| WR | 108 | 0.9604 | 36 | 97.2% | 36 |
| TE | 43 | 0.9833 | 15 | 100.0% | 9 |
| DL | 83 | 0.9713 | 32 | 96.9% | 41 |
| LB | 74 | 0.9741 | 32 | 96.9% | 20 |
| DB | 63 | 0.9526 | 32 | 93.8% | 20 |

## Largest absolute final-value movers

Large movement is a **diagnostic signal**, not evidence that Phase 1 is right. These rows are where we inspect lineage first.

| Player | Pos | Current | Phase 1 | Change | PM current→P1 | Rank move | Forward source | History note |
|---|---|---:|---:|---:|---|---:|---|---|
| marshawn lloyd | RB | 907 | 2258 | 149.0% | 0.195→0.486 | +29 | offense_benchmark_fp50_sleeper50 | no_2025_data_full_shrink_to_position_mean |
| caleb douglas | WR | 687 | 1598 | 132.6% | 0.177→0.388 | +36 | offense_benchmark_fp50_sleeper50 | no_2025_data_full_shrink_to_position_mean |
| aaron donald | DL | 698 | 1427 | 104.4% | 0.220→0.450 | +5 | idp_v1_fp_only | no_2025_data_full_shrink_to_position_mean |
| kayvon thibodeaux | DL | 1182 | 2411 | 104.0% | 0.231→0.471 | +20 | idp_v1_both | real |
| emmanuel mcneilwarren | DB | 827 | 1600 | 93.5% | 0.220→0.410 | +0 | idp_v1_sleeper_only | no_2025_data_full_shrink_to_position_mean |
| justin joly | TE | 486 | 916 | 88.5% | 0.162→0.292 | +7 | offense_sleeper_only | no_2025_data_full_shrink_to_position_mean |
| malachi fields | WR | 864 | 1619 | 87.4% | 0.220→0.393 | +32 | offense_benchmark_fp50_sleeper50 | no_2025_data_full_shrink_to_position_mean |
| kaelon black | RB | 896 | 1647 | 83.8% | 0.183→0.336 | +23 | offense_benchmark_fp50_sleeper50 | no_2025_data_full_shrink_to_position_mean |
| zavion thomas | WR | 626 | 1133 | 81.0% | 0.162→0.283 | +11 | offense_benchmark_fp50_sleeper50 | no_2025_data_full_shrink_to_position_mean |
| jacob rodriguez | LB | 1682 | 2964 | 76.2% | 0.315→0.541 | +20 | idp_v1_both | no_2025_data_full_shrink_to_position_mean |
| kyle louis | LB | 968 | 1683 | 73.9% | 0.220→0.367 | +7 | idp_v1_fp_only | no_2025_data_full_shrink_to_position_mean |
| eli stowers | TE | 578 | 986 | 70.6% | 0.165→0.275 | +9 | offense_benchmark_fp50_sleeper50 | no_2025_data_full_shrink_to_position_mean |
| jonathan greenard | DL | 2007 | 3391 | 69.0% | 0.392→0.663 | +41 | idp_v1_both | real |
| mike washington | RB | 842 | 1421 | 68.8% | 0.172→0.290 | +22 | offense_sleeper_only | no_2025_data_full_shrink_to_position_mean |
| aj haulcy | DB | 1150 | 1919 | 66.9% | 0.301→0.485 | +0 | idp_v1_both | no_2025_data_full_shrink_to_position_mean |
| dangelo ponds | DB | 670 | 1099 | 64.0% | 0.242→0.372 | +0 | idp_v1_both | no_2025_data_full_shrink_to_position_mean |
| anthony hill | LB | 889 | 1389 | 56.2% | 0.249→0.366 | +6 | idp_v1_sleeper_only | no_2025_data_full_shrink_to_position_mean |
| peter woods | DL | 884 | 1375 | 55.5% | 0.291→0.424 | +3 | idp_v1_both | no_2025_data_full_shrink_to_position_mean |
| josiah trotter | LB | 924 | 1434 | 55.2% | 0.257→0.376 | +6 | idp_v1_both | no_2025_data_full_shrink_to_position_mean |
| kayden mcdonald | DL | 643 | 984 | 53.0% | 0.220→0.319 | +1 | idp_v1_sleeper_only | no_2025_data_full_shrink_to_position_mean |
| keldric faulk | DL | 892 | 1360 | 52.5% | 0.294→0.420 | +1 | idp_v1_both | no_2025_data_full_shrink_to_position_mean |
| zion young | DL | 1044 | 1558 | 49.2% | 0.281→0.405 | +3 | idp_v1_fp_only | no_2025_data_full_shrink_to_position_mean |
| jakobi lane | WR | 1055 | 1569 | 48.7% | 0.265→0.382 | +19 | offense_benchmark_fp50_sleeper50 | no_2025_data_full_shrink_to_position_mean |
| deshaun watson | QB | 1838 | 2717 | 47.8% | 0.257→0.380 | +3 | offense_benchmark_fp50_sleeper50 | no_2025_data_full_shrink_to_position_mean |
| deion burks | WR | 1676 | 887 | -47.1% | 0.350→0.189 | -30 | offense_sleeper_only | no_2025_data_full_shrink_to_position_mean |
| jake golday | LB | 1162 | 1663 | 43.1% | 0.220→0.312 | +3 | idp_v1_both | no_2025_data_full_shrink_to_position_mean |
| chris bell | WR | 1106 | 1580 | 42.9% | 0.277→0.384 | +17 | offense_benchmark_fp50_sleeper50 | no_2025_data_full_shrink_to_position_mean |
| kaleb elarmsorr | LB | 968 | 1370 | 41.5% | 0.220→0.304 | +0 | idp_v1_both | no_2025_data_full_shrink_to_position_mean |
| bryce lance | WR | 1037 | 1453 | 40.1% | 0.220→0.305 | +17 | offense_benchmark_fp50_sleeper50 | no_2025_data_full_shrink_to_position_mean |
| antonio williams | WR | 1102 | 1506 | 36.7% | 0.276→0.368 | +14 | offense_benchmark_fp50_sleeper50 | no_2025_data_full_shrink_to_position_mean |

## What Phase 1 does **not** prove

- It does **not** prove 50/50 FantasyPros/Sleeper is the best offensive projection blend.
- It does **not** prove 45/55 history/forward is the best weighting.
- It does **not** prove the replacement-rank baseline or linear `prod_mult` transform is correct.
- It does **not** change the current production table.
- It does **not** use market value to train Fundamental Value.

## Next step

If identity/coverage checks are clean, Phase 2 will calibrate **provider blend** and **history-vs-forward weighting** using only evidence that is temporally valid. The Phase-1 benchmark will not be deployed.

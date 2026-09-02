# Production V2 — Phase 1 Lineage & Benchmark Audit

## Decision

**RESEARCH ONLY — no production change is authorized by this audit.**

Phase 1 is deliberately a lineage/coverage/blast-radius audit, not a claim that the benchmark formula is optimal.
It freezes the current player-value architecture and swaps only the production input in a counterfactual reconstruction.

- Current tracked players: **549**
- Phase-1 candidate values built: **409** (74.5%)
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
| QB | 64 | 49 | 49 | 32 | 0 | 0 | 32 | 32 |
| RB | 97 | 77 | 77 | 74 | 0 | 0 | 74 | 74 |
| WR | 114 | 83 | 83 | 79 | 0 | 0 | 79 | 79 |
| TE | 44 | 34 | 34 | 33 | 0 | 0 | 33 | 33 |
| DL | 86 | 74 | 74 | 69 | 58 | 56 | 71 | 71 |
| LB | 79 | 64 | 64 | 59 | 58 | 54 | 63 | 63 |
| DB | 65 | 58 | 58 | 54 | 49 | 46 | 57 | 57 |

## Data-quality flags

- `history_present_forward_missing`: **140**
- `missing_forward_projection`: **140**
- `missing_ppg_row`: **110**
- `missing_stable_sleeper_id`: **110**
- `ppg_position_mismatch_vs_current_player_db`: **23**
- `zero_game_history_records`: **110**

### Forward projection source counts

- `idp_no_forward_projection`: **5**
- `idp_v1_both`: **156**
- `idp_v1_fp_only`: **9**
- `idp_v1_sleeper_only`: **26**
- `missing_stable_sleeper_id`: **110**
- `offense_no_forward_projection`: **25**
- `offense_sleeper_only`: **218**

## Phase-1 position baselines

These are diagnostic benchmark anchors only; Phase 2 will test whether this normalization should survive at all.

| Pos | Rank | Anchor player | Combined points | Candidate cohort |
|---|---:|---|---:|---:|
| QB | 18 | baker mayfield | 251.10 | 32 |
| RB | 32 | jordan mason | 165.48 | 74 |
| WR | 36 | dj moore | 153.47 | 79 |
| TE | 15 | dalton schultz | 128.84 | 33 |
| DL | 32 | ed oliver | 150.19 | 71 |
| LB | 32 | demetrius knight | 180.37 | 63 |
| DB | 32 | jalen pitre | 159.15 | 57 |

## Current vs Phase-1 movement

| Pos | N | Median FV change | P90 abs FV change | P95 abs FV change | Max abs FV change | Median abs PM delta |
|---|---:|---:|---:|---:|---:|---:|
| QB | 32 | -0.5% | 5.0% | 13.1% | 39.7% | 0.0150 |
| RB | 74 | -1.3% | 19.3% | 22.0% | 28.7% | 0.0240 |
| WR | 79 | -4.7% | 18.9% | 24.7% | 33.2% | 0.0371 |
| TE | 33 | 0.5% | 10.8% | 16.6% | 30.5% | 0.0244 |
| DL | 71 | -5.3% | 7.4% | 9.9% | 104.0% | 0.0356 |
| LB | 63 | 3.9% | 12.4% | 17.6% | 29.7% | 0.0264 |
| DB | 57 | -0.3% | 9.2% | 17.0% | 36.5% | 0.0027 |

## Rank stability

Ranks are measured on the exact common current/candidate cohort for each position.

| Pos | N | Spearman | Top-N | Top-N overlap | Max rank move |
|---|---:|---:|---:|---:|---:|
| QB | 32 | 0.9791 | 18 | 100.0% | 5 |
| RB | 74 | 0.9880 | 32 | 93.8% | 11 |
| WR | 79 | 0.9875 | 36 | 94.4% | 17 |
| TE | 33 | 0.9883 | 15 | 93.3% | 4 |
| DL | 71 | 0.9693 | 32 | 96.9% | 37 |
| LB | 63 | 0.9780 | 32 | 96.9% | 15 |
| DB | 57 | 0.9413 | 32 | 93.8% | 20 |

## Largest absolute final-value movers

Large movement is a **diagnostic signal**, not evidence that Phase 1 is right. These rows are where we inspect lineage first.

| Player | Pos | Current | Phase 1 | Change | PM current→P1 | Rank move | Forward source | History note |
|---|---|---:|---:|---:|---|---:|---|---|
| kayvon thibodeaux | DL | 1182 | 2411 | 104.0% | 0.231→0.471 | +16 | idp_v1_both | real |
| jonathan greenard | DL | 2007 | 3391 | 69.0% | 0.392→0.663 | +37 | idp_v1_both | real |
| tua tagovailoa | QB | 2803 | 3916 | 39.7% | 0.392→0.548 | +5 | offense_sleeper_only | real |
| jaylon carlies | DB | 1900 | 2594 | 36.5% | 0.397→0.542 | +12 | idp_v1_fp_only | real |
| isaac teslaa | WR | 1705 | 1139 | -33.2% | 0.310→0.207 | -7 | offense_sleeper_only | real |
| tory horton | WR | 1831 | 1273 | -30.5% | 0.381→0.268 | -7 | offense_sleeper_only | real |
| justin jefferson | WR | 3702 | 4830 | 30.5% | 0.673→0.878 | +17 | offense_sleeper_only | real |
| terrance ferguson | TE | 1126 | 783 | -30.5% | 0.312→0.221 | -2 | offense_sleeper_only | real |
| troy franklin | WR | 2119 | 1482 | -30.1% | 0.438→0.311 | -3 | offense_sleeper_only | real |
| andrew van ginkel | LB | 2528 | 3279 | 29.7% | 0.595→0.772 | +14 | idp_v1_both | real |
| kaden elliss | LB | 2990 | 2125 | -28.9% | 0.704→0.500 | -15 | idp_v1_both | real |
| keaton mitchell | RB | 1410 | 1815 | 28.7% | 0.288→0.371 | +4 | offense_sleeper_only | real |
| danny stutsman | LB | 1585 | 1149 | -27.5% | 0.297→0.218 | -1 | idp_v1_fp_only | real |
| emari demercado | RB | 804 | 588 | -26.9% | 0.205→0.150 | -11 | offense_sleeper_only | real |
| oronde gadsden | TE | 2004 | 1505 | -24.9% | 0.533→0.410 | -3 | offense_sleeper_only | real |
| dontayvion wicks | WR | 1375 | 1706 | 24.1% | 0.250→0.310 | +8 | offense_sleeper_only | real |
| kimani vidal | RB | 1946 | 1490 | -23.4% | 0.398→0.305 | -2 | offense_sleeper_only | real |
| rhamondre stevenson | RB | 2409 | 2961 | 22.9% | 0.672→0.826 | +11 | offense_sleeper_only | real |
| shedeur sanders | QB | 1550 | 1201 | -22.5% | 0.260→0.203 | +0 | offense_sleeper_only | real |
| travis hunter | WR | 2338 | 1818 | -22.2% | 0.481→0.379 | -2 | offense_sleeper_only | real |
| phil mafah | RB | 1282 | 1006 | -21.5% | 0.262→0.205 | -4 | offense_sleeper_only | real |
| malik davis | RB | 808 | 639 | -20.9% | 0.209→0.165 | -9 | offense_sleeper_only | real |
| isaiah davis | RB | 1116 | 1347 | 20.7% | 0.228→0.275 | +6 | offense_sleeper_only | real |
| elic ayomanor | WR | 1388 | 1112 | -19.9% | 0.292→0.235 | -5 | offense_sleeper_only | real |
| zach charbonnet | RB | 2583 | 2081 | -19.4% | 0.555→0.447 | -5 | offense_sleeper_only | real |
| ray davis | RB | 828 | 986 | 19.1% | 0.196→0.233 | +4 | offense_sleeper_only | real |
| jack bech | WR | 950 | 769 | -19.1% | 0.202→0.164 | -2 | offense_sleeper_only | real |
| jerry jeudy | WR | 2338 | 1897 | -18.9% | 0.425→0.345 | -2 | offense_sleeper_only | real |
| isiah pacheco | RB | 1558 | 1266 | -18.7% | 0.393→0.319 | -5 | offense_sleeper_only | real |
| cj gardnerjohnson | DB | 2445 | 2893 | 18.3% | 0.553→0.654 | +16 | idp_v1_both | real |

## What Phase 1 does **not** prove

- It does **not** prove 50/50 FantasyPros/Sleeper is the best offensive projection blend.
- It does **not** prove 45/55 history/forward is the best weighting.
- It does **not** prove the replacement-rank baseline or linear `prod_mult` transform is correct.
- It does **not** change the current production table.
- It does **not** use market value to train Fundamental Value.

## Next step

If identity/coverage checks are clean, Phase 2 will calibrate **provider blend** and **history-vs-forward weighting** using only evidence that is temporally valid. The Phase-1 benchmark will not be deployed.

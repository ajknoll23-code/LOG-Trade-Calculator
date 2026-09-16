# Cross-Position Apex Calibration V1 — Phase 1 Diagnostic

**Decision:** `PASS_CROSS_POSITION_APEX_CALIBRATION_V1_PHASE1_REVIEW_REQUIRED`

Research-only. Production is unchanged.

## Trigger

- Brian Burns FV: **7391** (overall **#5**, DL **#1**)
- Josh Allen FV: **6564** (overall **#10**, QB **#1**)
- Burns minus Allen: **+827 FV**
- Burns / Allen: **1.1260x**
- High-priority >=1.10x trigger: **YES**

## Exact FV factor decomposition

| Factor | Burns | Allen | Burns/Allen |
|---|---:|---:|---:|
| Position weight | 0.9300 | 1.3000 | 0.7154x |
| Age multiplier | 1.000000 | 1.000000 | 1.0000x |
| Effective PROD_MULT | 1.4449 | 0.9180 | 1.5740x |
| Product of factor ratios |  |  | 1.1260x |
| Observed FV ratio |  |  | 1.1260x |

## 2025-history lift versus 2026 projection

- Burns: 2025 **279.0**, 2026 projection **182.9**, 45/55 raw blend **226.1**
- Allen: 2025 **393.0**, 2026 projection **366.5**, 45/55 raw blend **378.4**
- Burns blend / projection: **1.2364x**
- Allen blend / projection: **1.0325x**
- Burns receives **+20.4 percentage points** more history lift than Allen before positional normalization.

## Neutral tie thresholds

These are sensitivity measurements, **not recommendations**.

- Burns PROD_MULT would tie Allen at **1.2833** vs current **1.4449** (-11.2%).
- DL position weight would tie Burns to Allen at **0.8260** vs current **0.9300** (-11.2%).
- QB position weight would tie Allen to Burns at **1.4639** vs current **1.3000** (+12.6%).

## League starter-demand context

| Pos | Dedicated league min | Theoretical max with flex | Rank-32 context |
|---|---:|---:|---|
| QB | 12 | 24 | `deeper_than_theoretical_max_starter_demand` |
| RB | 24 | 48 | `inside_starter_demand_range` |
| WR | 24 | 48 | `inside_starter_demand_range` |
| TE | 12 | 36 | `inside_starter_demand_range` |
| DL | 24 | 48 | `inside_starter_demand_range` |
| LB | 24 | 48 | `inside_starter_demand_range` |
| DB | 24 | 48 | `inside_starter_demand_range` |

## Overall top-20 FV

| Rank | Player | Pos | FV | PROD_MULT | Age mult |
|---:|---|---|---:|---:|---:|
| 1 | jahmyr gibbs | RB | 8841 | 1.5500 | 1.1652 |
| 2 | bijan robinson | RB | 8509 | 1.5500 | 1.1215 |
| 3 | puka nacua | WR | 8030 | 1.4600 | 1.0000 |
| 4 | jaxon smithnjigba | WR | 7568 | 1.3760 | 1.0000 |
| 5 | brian burns | DL | 7391 | 1.4449 | 1.0000 |
| 6 | ashton jeanty | RB | 7141 | 1.0890 | 1.3395 |
| 7 | jamarr chase | WR | 7023 | 1.2770 | 1.0000 |
| 8 | amonra st brown | WR | 6913 | 1.2570 | 1.0000 |
| 9 | devon achane | RB | 6632 | 1.3230 | 1.0241 |
| 10 | josh allen | QB | 6564 | 0.9180 | 1.0000 |
| 11 | byron young | DL | 6123 | 1.1970 | 1.0000 |
| 12 | james cook | RB | 5974 | 1.4360 | 0.8499 |
| 13 | will anderson | DL | 5961 | 1.1653 | 1.0000 |
| 14 | jonathan taylor | RB | 5906 | 1.5120 | 0.7980 |
| 15 | george pickens | WR | 5896 | 1.0720 | 1.0000 |
| 16 | nik bonitto | DL | 5864 | 1.1465 | 1.0000 |
| 17 | drake london | WR | 5852 | 1.0640 | 1.0000 |
| 18 | myles garrett | DL | 5655 | 1.1966 | 0.9240 |
| 19 | jalen hurts | QB | 5634 | 0.7880 | 1.0000 |
| 20 | maxx crosby | DL | 5621 | 1.0990 | 1.0000 |

## Integrity gates

| Gate | Result |
|---|---|
| `comparison_players_present` | PASS |
| `exact_player_value_factorization_reproduces_both` | PASS |
| `burns_allen_factor_ratio_identity_reproduced` | PASS |
| `league_format_readable` | PASS |
| `offense_phase1_trigger_still_high_priority` | PASS |

## Decision semantics

A PASS confirms that the current cross-position apex trigger is real and
freezes the diagnostic evidence needed to design Phase 2. It does not
identify a winning calibration lever and does not authorize deployment.

# Replacement Level / Positional Scale V2 — Phase 5 Prospective Evaluator

Method: `replacement-level-v2-phase5-prospective-v1`  
Status: **`COLLECTION_ONLY`**

## Guardrail

**Research only. No replacement-rank or production deployment is authorized.**

- Frozen candidate SHA256: `ab24d5d1a1483ada04c6ce44154dc58bba6b1ba16c520fbeaf71e199851297e6`
- Frozen at: **2026-09-05T22:16:28.841347Z**
- First eligible future week: **1**
- Completed consecutive weeks used: **[1, 2, 3]**
- Full frozen candidate universe: **518**
- Primary real-history cohort: **426**
- Primary players with an active game: **394**

## Frozen replacement-rank families

| Family | QB | RB | WR | TE | DL | LB | DB |
|---|---:|---:|---:|---:|---:|---:|---:|
| `legacy_control` | 18 | 32 | 36 | 15 | 32 | 32 | 32 |
| `prior_limited_evidence` | 18 | 26 | 34 | 15 | 23 | 32 | 30 |
| `stable_positions_only` | 18 | 25 | 28 | 15 | 16 | 28 | 22 |
| `full_phase2_leaders` | 29 | 25 | 28 | 11 | 16 | 28 | 22 |

## Primary prospective metric

Target: **future-only active-game PPG relative-production structure**.

The future replacement point is derived from the realized future data itself via the same candidate-independent SSE split used by the reviewed historical Test 3.

**Primary statistic: position-balanced mean MAE. Lower is better.**

| Family | Pos-balanced MAE | Pos-balanced RMSE | Pooled MAE | Δ MAE vs control | Positions available |
|---|---:|---:|---:|---:|---:|
| `legacy_control` | 0.3868 | 0.4854 | 0.3853 | — | 7 |
| `prior_limited_evidence` | 0.3712 | 0.4690 | 0.3670 | -0.0156 | 7 |
| `stable_positions_only` | 0.3569 | 0.4546 | 0.3496 | -0.0299 | 7 |
| `full_phase2_leaders` | 0.3404 | 0.4383 | 0.3385 | -0.0464 | 7 |

## Future-only replacement structure

| Pos | Future split rank | Replacement player | Active PPG at split |
|---|---:|---|---:|
| QB | 29 | baker mayfield | 12.4333 |
| RB | 22 | bucky irving | 14.2000 |
| WR | 11 | jalen coker | 15.0667 |
| TE | 14 | sam laporta | 9.1333 |
| DL | 15 | tuli tuipulotu | 12.1667 |
| LB | 11 | nick bolton | 15.6667 |
| DB | 26 | christian gonzalez | 8.7500 |

## Secondary availability-inclusive metric

The same candidate-independent future-relative-production test using cumulative total points.

| Family | Pos-balanced MAE | Δ MAE vs control | Pooled MAE |
|---|---:|---:|---:|
| `legacy_control` | 0.4413 | — | 0.4354 |
| `prior_limited_evidence` | 0.4270 | -0.0143 | 0.4175 |
| `stable_positions_only` | 0.4159 | -0.0254 | 0.4037 |
| `full_phase2_leaders` | 0.4036 | -0.0377 | 0.3946 |

## Readiness ladder

- Weeks 1–3: **collection only**
- Weeks 4–7: **early diagnostic only**
- Weeks 8–11: **calibration review eligible**
- Weeks 12–17: **stability review eligible**
- Week 18: **season-complete review**

## Interpretation

Lower MAE/RMSE is better. The primary decision statistic is position-balanced mean MAE for active-game PPG relative production. Do not select or deploy a replacement-rank family before calibration-review readiness. Weeks 1-3 are collection only; Weeks 4-7 are early diagnostics only. Promotion requires stable improvement versus the frozen legacy control across the aggregate and position-level errors and must be reconciled with the separately frozen Production V2, No-History/Rookie V2, Age Curve V2, Opportunity V2, and Durability V2 experiments.

## Fixed outside this experiment

- PM transform: `clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)`
- Global value scale: `55`
- `POSITION_WEIGHT`: unchanged
- Production V2 Phase 9: unchanged
- No-History/Rookie V2: unchanged
- Age Curve V2: unchanged
- Opportunity V2: unchanged
- Durability V2: unchanged

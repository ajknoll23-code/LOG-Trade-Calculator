# Production V2 — Phase 9 Prospective Evaluator

## Status

**EARLY_DIAGNOSTIC_ONLY**

- Production files mutated: **0**
- Deployment authorized: **No**
- Frozen candidate matrix: **120 V2 variants + deployed control**
- Completed consecutive weeks: **5**

## Frozen protocol

- Primary: **effective PROD_MULT vs realized active-game PPG**
- Secondary: Fundamental Value vs future total points
- Secondary: Fundamental Value vs realized active-game PPG
- Completed-week and leakage rules are reused from `scripts/validation/evaluate_model_history.py`.
- Predictions are frozen preseason and never rebuilt from later `index.html` state.

## Readiness ladder

- Weeks 1–3: collection only
- Weeks 4–7: early diagnostic only
- Weeks 8–11: calibration review eligible
- Weeks 12+: stability review eligible
- Week 18: season-complete review

## Completed outcome state

- Outcome refresh: `2026-10-13T20:42:12.738249Z`
- Completed weeks recognized: **[1, 2, 3, 4, 5]**
- Consecutive prefix used: **[1, 2, 3, 4, 5]**

## weeks_1_to_4

Weeks: **[1, 2, 3, 4]**  
Active normal-candidate players: **469**  
Deployed control rank: **121 / 121**  
Phase-8 monitoring reference rank: **62 / 121**

| Rank | Variant | FP wt | History wt | Ranks | Floor | Primary Spearman | Δ vs deployed | Pairwise |
|---:|---|---:|---:|---|---:|---:|---:|---:|
| 1 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.15` | 75% | 25% | evidence_hybrid | 0.15 | 0.647808 | 0.042297 | 0.737595 |
| 2 | `fp_0.00__history_0.25__documented__floor_0.20` | 0% | 25% | documented | 0.20 | 0.647645 | 0.042134 | 0.737916 |
| 3 | `fp_0.00__history_0.25__documented__floor_0.15` | 0% | 25% | documented | 0.15 | 0.647345 | 0.041834 | 0.736284 |
| 4 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.20` | 75% | 25% | evidence_hybrid | 0.20 | 0.647297 | 0.041786 | 0.738301 |
| 5 | `fp_0.00__history_0.25__documented__floor_0.10` | 0% | 25% | documented | 0.10 | 0.64692 | 0.041409 | 0.735659 |
| 6 | `fp_0.00__history_0.25__documented__floor_0.05` | 0% | 25% | documented | 0.05 | 0.646661 | 0.04115 | 0.735362 |
| 7 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.10` | 75% | 25% | evidence_hybrid | 0.10 | 0.646471 | 0.04096 | 0.736304 |
| 8 | `fp_0.25__history_0.25__evidence_hybrid__floor_0.20` | 25% | 25% | evidence_hybrid | 0.20 | 0.646429 | 0.040918 | 0.738063 |
| 9 | `fp_0.25__history_0.25__documented__floor_0.20` | 25% | 25% | documented | 0.20 | 0.646352 | 0.040841 | 0.737455 |
| 10 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.05` | 75% | 25% | evidence_hybrid | 0.05 | 0.646153 | 0.040642 | 0.735714 |

## Stability

Requires at least 8 completed consecutive weeks.

## Interpretation

The first 4-week diagnostic is available. It is intentionally too early to select provider/history/rank/floor settings.

Phase 9 never deploys a coefficient automatically. Any eventual winner must survive independent-window stability, position guardrails, bootstrap uncertainty, and comparison against the frozen deployed model before Phase 10.

# Production V2 — Phase 9 Prospective Evaluator

## Status

**COLLECTING_NO_CALIBRATION**

- Production files mutated: **0**
- Deployment authorized: **No**
- Frozen candidate matrix: **120 V2 variants + deployed control**
- Completed consecutive weeks: **3**

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

- Outcome refresh: `2026-09-29T19:53:42.835988Z`
- Completed weeks recognized: **[1, 2, 3]**
- Consecutive prefix used: **[1, 2, 3]**

## weeks_1_to_3_early

Weeks: **[1, 2, 3]**  
Active normal-candidate players: **467**  
Deployed control rank: **121 / 121**  
Phase-8 monitoring reference rank: **63 / 121**

| Rank | Variant | FP wt | History wt | Ranks | Floor | Primary Spearman | Δ vs deployed | Pairwise |
|---:|---|---:|---:|---|---:|---:|---:|---:|
| 1 | `fp_0.00__history_0.25__documented__floor_0.20` | 0% | 25% | documented | 0.20 | 0.634708 | 0.046302 | 0.731034 |
| 2 | `fp_0.00__history_0.25__documented__floor_0.15` | 0% | 25% | documented | 0.15 | 0.634125 | 0.045719 | 0.729342 |
| 3 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.15` | 75% | 25% | evidence_hybrid | 0.15 | 0.633721 | 0.045315 | 0.73039 |
| 4 | `fp_0.00__history_0.25__documented__floor_0.10` | 0% | 25% | documented | 0.10 | 0.633646 | 0.04524 | 0.728702 |
| 5 | `fp_0.00__history_0.25__documented__floor_0.05` | 0% | 25% | documented | 0.05 | 0.633627 | 0.045221 | 0.728475 |
| 6 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.20` | 75% | 25% | evidence_hybrid | 0.20 | 0.633243 | 0.044837 | 0.730981 |
| 7 | `fp_0.25__history_0.25__evidence_hybrid__floor_0.15` | 25% | 25% | evidence_hybrid | 0.15 | 0.633073 | 0.044667 | 0.72953 |
| 8 | `fp_0.25__history_0.25__documented__floor_0.20` | 25% | 25% | documented | 0.20 | 0.633065 | 0.044659 | 0.73028 |
| 9 | `fp_0.00__history_0.25__evidence_hybrid__floor_0.20` | 0% | 25% | evidence_hybrid | 0.20 | 0.632941 | 0.044535 | 0.731312 |
| 10 | `fp_0.25__history_0.25__evidence_hybrid__floor_0.20` | 25% | 25% | evidence_hybrid | 0.20 | 0.632904 | 0.044498 | 0.731184 |

## Stability

Requires at least 8 completed consecutive weeks.

## Interpretation

Phase 9 is collecting realized evidence. Results are smoke-test diagnostics only and must not influence coefficients.

Phase 9 never deploys a coefficient automatically. Any eventual winner must survive independent-window stability, position guardrails, bootstrap uncertainty, and comparison against the frozen deployed model before Phase 10.

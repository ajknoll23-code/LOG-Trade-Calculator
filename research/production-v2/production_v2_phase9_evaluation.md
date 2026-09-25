# Production V2 — Phase 9 Prospective Evaluator

## Status

**COLLECTING_NO_CALIBRATION**

- Production files mutated: **0**
- Deployment authorized: **No**
- Frozen candidate matrix: **120 V2 variants + deployed control**
- Completed consecutive weeks: **2**

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

- Outcome refresh: `2026-09-25T12:14:19.971987Z`
- Completed weeks recognized: **[1, 2]**
- Consecutive prefix used: **[1, 2]**

## weeks_1_to_2_early

Weeks: **[1, 2]**  
Active normal-candidate players: **456**  
Deployed control rank: **121 / 121**  
Phase-8 monitoring reference rank: **64 / 121**

| Rank | Variant | FP wt | History wt | Ranks | Floor | Primary Spearman | Δ vs deployed | Pairwise |
|---:|---|---:|---:|---|---:|---:|---:|---:|
| 1 | `fp_0.00__history_0.25__documented__floor_0.15` | 0% | 25% | documented | 0.15 | 0.594456 | 0.048437 | 0.712665 |
| 2 | `fp_0.00__history_0.25__documented__floor_0.20` | 0% | 25% | documented | 0.20 | 0.594159 | 0.04814 | 0.713892 |
| 3 | `fp_0.00__history_0.25__documented__floor_0.05` | 0% | 25% | documented | 0.05 | 0.59393 | 0.047911 | 0.711802 |
| 4 | `fp_0.00__history_0.25__documented__floor_0.10` | 0% | 25% | documented | 0.10 | 0.593691 | 0.047672 | 0.711936 |
| 5 | `fp_0.25__history_0.25__documented__floor_0.20` | 25% | 25% | documented | 0.20 | 0.593506 | 0.047487 | 0.713781 |
| 6 | `fp_0.25__history_0.25__documented__floor_0.15` | 25% | 25% | documented | 0.15 | 0.593431 | 0.047412 | 0.71267 |
| 7 | `fp_0.25__history_0.25__documented__floor_0.05` | 25% | 25% | documented | 0.05 | 0.592569 | 0.04655 | 0.711666 |
| 8 | `fp_0.25__history_0.25__documented__floor_0.10` | 25% | 25% | documented | 0.10 | 0.592517 | 0.046498 | 0.711827 |
| 9 | `fp_0.75__history_0.25__documented__floor_0.15` | 75% | 25% | documented | 0.15 | 0.591545 | 0.045526 | 0.712207 |
| 10 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.15` | 75% | 25% | evidence_hybrid | 0.15 | 0.591199 | 0.04518 | 0.71259 |

## Stability

Requires at least 8 completed consecutive weeks.

## Interpretation

Phase 9 is collecting realized evidence. Results are smoke-test diagnostics only and must not influence coefficients.

Phase 9 never deploys a coefficient automatically. Any eventual winner must survive independent-window stability, position guardrails, bootstrap uncertainty, and comparison against the frozen deployed model before Phase 10.

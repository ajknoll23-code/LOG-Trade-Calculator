# Production V2 — Phase 9 Prospective Evaluator

## Status

**COLLECTING_NO_CALIBRATION**

- Production files mutated: **0**
- Deployment authorized: **No**
- Frozen candidate matrix: **120 V2 variants + deployed control**
- Completed consecutive weeks: **1**

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

- Outcome refresh: `2026-09-18T21:46:13.721512Z`
- Completed weeks recognized: **[1]**
- Consecutive prefix used: **[1]**

## weeks_1_to_1_early

Weeks: **[1]**  
Active normal-candidate players: **435**  
Deployed control rank: **121 / 121**  
Phase-8 monitoring reference rank: **72 / 121**

| Rank | Variant | FP wt | History wt | Ranks | Floor | Primary Spearman | Δ vs deployed | Pairwise |
|---:|---|---:|---:|---|---:|---:|---:|---:|
| 1 | `fp_1.00__history_0.25__documented__floor_0.15` | 100% | 25% | documented | 0.15 | 0.499052 | 0.051554 | 0.678246 |
| 2 | `fp_0.75__history_0.25__documented__floor_0.15` | 75% | 25% | documented | 0.15 | 0.498656 | 0.051158 | 0.678197 |
| 3 | `fp_1.00__history_0.25__documented__floor_0.05` | 100% | 25% | documented | 0.05 | 0.498546 | 0.051048 | 0.677718 |
| 4 | `fp_0.75__history_0.25__documented__floor_0.05` | 75% | 25% | documented | 0.05 | 0.498317 | 0.050819 | 0.677826 |
| 5 | `fp_0.75__history_0.25__documented__floor_0.10` | 75% | 25% | documented | 0.10 | 0.49818 | 0.050682 | 0.677936 |
| 6 | `fp_1.00__history_0.25__documented__floor_0.20` | 100% | 25% | documented | 0.20 | 0.498158 | 0.05066 | 0.678317 |
| 7 | `fp_1.00__history_0.25__documented__floor_0.10` | 100% | 25% | documented | 0.10 | 0.498145 | 0.050647 | 0.677706 |
| 8 | `fp_0.75__history_0.25__documented__floor_0.20` | 75% | 25% | documented | 0.20 | 0.498033 | 0.050535 | 0.678481 |
| 9 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.15` | 75% | 25% | evidence_hybrid | 0.15 | 0.497913 | 0.050415 | 0.67878 |
| 10 | `fp_0.00__history_0.25__documented__floor_0.15` | 0% | 25% | documented | 0.15 | 0.497745 | 0.050247 | 0.677819 |

## Stability

Requires at least 8 completed consecutive weeks.

## Interpretation

Phase 9 is collecting realized evidence. Results are smoke-test diagnostics only and must not influence coefficients.

Phase 9 never deploys a coefficient automatically. Any eventual winner must survive independent-window stability, position guardrails, bootstrap uncertainty, and comparison against the frozen deployed model before Phase 10.

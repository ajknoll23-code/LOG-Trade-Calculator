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

- Outcome refresh: `2026-09-15T18:48:57.468525Z`
- Completed weeks recognized: **[1]**
- Consecutive prefix used: **[1]**

## weeks_1_to_1_early

Weeks: **[1]**  
Active normal-candidate players: **435**  
Deployed control rank: **121 / 121**  
Phase-8 monitoring reference rank: **72 / 121**

| Rank | Variant | FP wt | History wt | Ranks | Floor | Primary Spearman | Δ vs deployed | Pairwise |
|---:|---|---:|---:|---|---:|---:|---:|---:|
| 1 | `fp_1.00__history_0.25__documented__floor_0.15` | 100% | 25% | documented | 0.15 | 0.498168 | 0.051469 | 0.677993 |
| 2 | `fp_0.75__history_0.25__documented__floor_0.15` | 75% | 25% | documented | 0.15 | 0.497816 | 0.051117 | 0.677944 |
| 3 | `fp_1.00__history_0.25__documented__floor_0.05` | 100% | 25% | documented | 0.05 | 0.497661 | 0.050962 | 0.677466 |
| 4 | `fp_0.75__history_0.25__documented__floor_0.05` | 75% | 25% | documented | 0.05 | 0.497474 | 0.050775 | 0.677573 |
| 5 | `fp_0.75__history_0.25__documented__floor_0.10` | 75% | 25% | documented | 0.10 | 0.497338 | 0.050639 | 0.677683 |
| 6 | `fp_1.00__history_0.25__documented__floor_0.20` | 100% | 25% | documented | 0.20 | 0.497276 | 0.050577 | 0.678064 |
| 7 | `fp_1.00__history_0.25__documented__floor_0.10` | 100% | 25% | documented | 0.10 | 0.49726 | 0.050561 | 0.677454 |
| 8 | `fp_0.75__history_0.25__documented__floor_0.20` | 75% | 25% | documented | 0.20 | 0.497193 | 0.050494 | 0.678228 |
| 9 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.15` | 75% | 25% | evidence_hybrid | 0.15 | 0.49716 | 0.050461 | 0.678559 |
| 10 | `fp_0.00__history_0.25__documented__floor_0.15` | 0% | 25% | documented | 0.15 | 0.496952 | 0.050253 | 0.677534 |

## Stability

Requires at least 8 completed consecutive weeks.

## Interpretation

Phase 9 is collecting realized evidence. Results are smoke-test diagnostics only and must not influence coefficients.

Phase 9 never deploys a coefficient automatically. Any eventual winner must survive independent-window stability, position guardrails, bootstrap uncertainty, and comparison against the frozen deployed model before Phase 10.

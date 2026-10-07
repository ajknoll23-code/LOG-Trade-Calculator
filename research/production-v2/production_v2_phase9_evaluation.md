# Production V2 — Phase 9 Prospective Evaluator

## Status

**EARLY_DIAGNOSTIC_ONLY**

- Production files mutated: **0**
- Deployment authorized: **No**
- Frozen candidate matrix: **120 V2 variants + deployed control**
- Completed consecutive weeks: **4**

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

- Outcome refresh: `2026-10-07T19:34:38.859565Z`
- Completed weeks recognized: **[1, 2, 3, 4]**
- Consecutive prefix used: **[1, 2, 3, 4]**

## weeks_1_to_4

Weeks: **[1, 2, 3, 4]**  
Active normal-candidate players: **469**  
Deployed control rank: **121 / 121**  
Phase-8 monitoring reference rank: **62 / 121**

| Rank | Variant | FP wt | History wt | Ranks | Floor | Primary Spearman | Δ vs deployed | Pairwise |
|---:|---|---:|---:|---|---:|---:|---:|---:|
| 1 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.15` | 75% | 25% | evidence_hybrid | 0.15 | 0.648193 | 0.042391 | 0.73777 |
| 2 | `fp_0.00__history_0.25__documented__floor_0.20` | 0% | 25% | documented | 0.20 | 0.647988 | 0.042186 | 0.738055 |
| 3 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.20` | 75% | 25% | evidence_hybrid | 0.20 | 0.647687 | 0.041885 | 0.738477 |
| 4 | `fp_0.00__history_0.25__documented__floor_0.15` | 0% | 25% | documented | 0.15 | 0.647684 | 0.041882 | 0.736422 |
| 5 | `fp_0.00__history_0.25__documented__floor_0.10` | 0% | 25% | documented | 0.10 | 0.647259 | 0.041457 | 0.735796 |
| 6 | `fp_0.00__history_0.25__documented__floor_0.05` | 0% | 25% | documented | 0.05 | 0.647 | 0.041198 | 0.735499 |
| 7 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.10` | 75% | 25% | evidence_hybrid | 0.10 | 0.646858 | 0.041056 | 0.736479 |
| 8 | `fp_0.25__history_0.25__evidence_hybrid__floor_0.20` | 25% | 25% | evidence_hybrid | 0.20 | 0.64682 | 0.041018 | 0.738202 |
| 9 | `fp_0.25__history_0.25__documented__floor_0.20` | 25% | 25% | documented | 0.20 | 0.646698 | 0.040896 | 0.737576 |
| 10 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.05` | 75% | 25% | evidence_hybrid | 0.05 | 0.64654 | 0.040738 | 0.735888 |

## Stability

Requires at least 8 completed consecutive weeks.

## Interpretation

The first 4-week diagnostic is available. It is intentionally too early to select provider/history/rank/floor settings.

Phase 9 never deploys a coefficient automatically. Any eventual winner must survive independent-window stability, position guardrails, bootstrap uncertainty, and comparison against the frozen deployed model before Phase 10.

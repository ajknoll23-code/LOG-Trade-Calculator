# Production V2 — Phase 9 Prospective Evaluator

## Status

**CALIBRATION_REVIEW_ELIGIBLE_NOT_DEPLOYMENT**

- Production files mutated: **0**
- Deployment authorized: **No**
- Frozen candidate matrix: **120 V2 variants + deployed control**
- Completed consecutive weeks: **9**

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

- Outcome refresh: `2026-11-13T20:18:10.631921Z`
- Completed weeks recognized: **[1, 2, 3, 4, 5, 6, 7, 8, 9]**
- Consecutive prefix used: **[1, 2, 3, 4, 5, 6, 7, 8, 9]**

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

## weeks_5_to_8

Weeks: **[5, 6, 7, 8]**  
Active normal-candidate players: **460**  
Deployed control rank: **93 / 121**  
Phase-8 monitoring reference rank: **72 / 121**

| Rank | Variant | FP wt | History wt | Ranks | Floor | Primary Spearman | Δ vs deployed | Pairwise |
|---:|---|---:|---:|---|---:|---:|---:|---:|
| 1 | `fp_0.75__history_0.25__documented__floor_0.15` | 75% | 25% | documented | 0.15 | 0.549937 | 0.029117 | 0.69592 |
| 2 | `fp_0.75__history_0.25__documented__floor_0.20` | 75% | 25% | documented | 0.20 | 0.5496 | 0.02878 | 0.696679 |
| 3 | `fp_1.00__history_0.25__documented__floor_0.20` | 100% | 25% | documented | 0.20 | 0.549193 | 0.028373 | 0.696339 |
| 4 | `fp_1.00__history_0.25__documented__floor_0.15` | 100% | 25% | documented | 0.15 | 0.548735 | 0.027915 | 0.6954 |
| 5 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.15` | 75% | 25% | evidence_hybrid | 0.15 | 0.548718 | 0.027898 | 0.695611 |
| 6 | `fp_0.75__history_0.25__documented__floor_0.05` | 75% | 25% | documented | 0.05 | 0.548702 | 0.027882 | 0.694389 |
| 7 | `fp_0.25__history_0.25__documented__floor_0.20` | 25% | 25% | documented | 0.20 | 0.548387 | 0.027567 | 0.696403 |
| 8 | `fp_0.75__history_0.25__documented__floor_0.10` | 75% | 25% | documented | 0.10 | 0.548225 | 0.027405 | 0.694461 |
| 9 | `fp_0.50__history_0.25__documented__floor_0.20` | 50% | 25% | documented | 0.20 | 0.548169 | 0.027349 | 0.696234 |
| 10 | `fp_1.00__history_0.25__documented__floor_0.05` | 100% | 25% | documented | 0.05 | 0.548018 | 0.027198 | 0.693999 |

## weeks_1_to_8

Weeks: **[1, 2, 3, 4, 5, 6, 7, 8]**  
Active normal-candidate players: **493**  
Deployed control rank: **97 / 121**  
Phase-8 monitoring reference rank: **65 / 121**

| Rank | Variant | FP wt | History wt | Ranks | Floor | Primary Spearman | Δ vs deployed | Pairwise |
|---:|---|---:|---:|---|---:|---:|---:|---:|
| 1 | `fp_0.25__history_0.25__documented__floor_0.20` | 25% | 25% | documented | 0.20 | 0.644522 | 0.037782 | 0.73739 |
| 2 | `fp_0.75__history_0.25__documented__floor_0.20` | 75% | 25% | documented | 0.20 | 0.643918 | 0.037178 | 0.736747 |
| 3 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.15` | 75% | 25% | evidence_hybrid | 0.15 | 0.643849 | 0.037109 | 0.735763 |
| 4 | `fp_0.00__history_0.25__documented__floor_0.20` | 0% | 25% | documented | 0.20 | 0.643476 | 0.036736 | 0.737051 |
| 5 | `fp_0.75__history_0.25__documented__floor_0.15` | 75% | 25% | documented | 0.15 | 0.643465 | 0.036725 | 0.7354 |
| 6 | `fp_0.50__history_0.25__documented__floor_0.20` | 50% | 25% | documented | 0.20 | 0.643243 | 0.036503 | 0.736679 |
| 7 | `fp_0.75__history_0.25__evidence_hybrid__floor_0.20` | 75% | 25% | evidence_hybrid | 0.20 | 0.643012 | 0.036272 | 0.73679 |
| 8 | `fp_0.00__history_0.25__documented__floor_0.15` | 0% | 25% | documented | 0.15 | 0.6429 | 0.03616 | 0.734681 |
| 9 | `fp_0.25__history_0.25__documented__floor_0.15` | 25% | 25% | documented | 0.15 | 0.642781 | 0.036041 | 0.735109 |
| 10 | `fp_0.00__history_0.25__documented__floor_0.10` | 0% | 25% | documented | 0.10 | 0.64212 | 0.03538 | 0.733744 |

## Stability

- Weeks 1–4 top: `fp_0.75__history_0.25__evidence_hybrid__floor_0.15`
- Weeks 5–8 top: `fp_0.75__history_0.25__documented__floor_0.15`
- Weeks 1–8 top: `fp_0.25__history_0.25__documented__floor_0.20`
- Exact top stable across independent 4-week windows: **False**
- Top-10 overlap between Weeks 1–4 and 5–8: **2 / 10**

## Interpretation

Phase 9 has enough evidence for calibration review. Compare the first and second four-week windows, cumulative results, position guardrails, and paired bootstrap before shortlisting settings.

Phase 9 never deploys a coefficient automatically. Any eventual winner must survive independent-window stability, position guardrails, bootstrap uncertainty, and comparison against the frozen deployed model before Phase 10.

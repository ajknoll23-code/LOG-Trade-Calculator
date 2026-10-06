# Continuous Opportunity / Role Signal V2 — Phase 5 Prospective Evaluator

Method: `opportunity-v2-phase5-prospective-v1`  
Status: **`EARLY_DIAGNOSTIC_ONLY`**

## Guardrail

**Research only. Production deployment is not authorized.**

- Frozen candidate SHA256: `714e16500e36b45a302e8160a4c37c87a89297d6b4b3a2d9e80b654e43f0e611`
- Frozen at: **2026-09-03T21:46:45.440775Z**
- First eligible future week: **1**
- Completed consecutive weeks used: **[1, 2, 3, 4]**
- Eligible opportunity cohort: **426**
- Players with active game in current window: **387**

## Prospective metrics

Primary target: **Frozen Fundamental Value vs cumulative future fantasy points**.

| Variant | Total Spearman | Total pairwise | Active-PPG Spearman | Δ total Spearman vs control | Mean pos Δ total Spearman |
|---|---:|---:|---:|---:|---:|
| `deployed_control` | 0.5819 | 0.7107 | 0.5596 | — | — |
| `bridge_w50` | 0.5772 | 0.7087 | 0.5606 | -0.0047 | -0.0052 |
| `bridge_w40` | 0.5788 | 0.7095 | 0.5611 | -0.0031 | -0.0023 |

## Readiness ladder

- Weeks 1–3: **collection only**
- Weeks 4–7: **early diagnostic only**
- Weeks 8–11: **calibration review eligible**
- Weeks 12–17: **stability review eligible**
- Week 18: **season-complete review**

## Interpretation

Do not select or deploy an opportunity bridge before calibration-review readiness. Weeks 1-3 are collection only and Weeks 4-7 are early diagnostics only. Promotion requires stable overall and by-position improvement versus the frozen deployed control and must be reconciled with the separately frozen Production V2, No-History V2, and Age Curve V2 experiments.

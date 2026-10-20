# No-History / Rookie Value V2 — Phase 3 Prospective Evaluator

Method: `no-history-rookie-v2-phase3-prospective-v1`  
Status: **`EARLY_DIAGNOSTIC_ONLY`**

## Guardrail

**Research only. Production deployment is not authorized.**

- Frozen candidate SHA256: `e720f1e26c1dd137f9b3d14110cd2fe1a28843a012d5b01f2d185291398a70c6`
- Frozen at: **2026-09-03T18:50:10.024333Z**
- First eligible future week: **1**
- Completed consecutive weeks used: **[1, 2, 3, 4, 5, 6]**
- Eligible preseason cohort: **95**
- Players with an active game in current window: **77**

## Prospective metrics

Primary target: **Fundamental Value vs cumulative future fantasy points**.

| Prior weight | Total-points Spearman | Active-PPG FV Spearman | Active-PPG PM Spearman | Total-points pairwise |
|---:|---:|---:|---:|---:|
| 0.00 | 0.5642 | 0.5593 | 0.6121 | 0.7156 |
| 0.15 | 0.5579 | 0.5845 | 0.6270 | 0.7154 |
| 0.30 | 0.5410 | 0.6096 | 0.6421 | 0.7088 |
| 0.45 | 0.5099 | 0.6131 | 0.6480 | 0.6972 |

## Difference vs frozen 0% prospect-prior control

| Prior weight | Δ total-points Spearman | Δ active-PPG FV Spearman | Δ active-PPG PM Spearman | Δ total-points pairwise |
|---:|---:|---:|---:|---:|
| 0.15 | -0.0063 | +0.0253 | +0.0149 | -0.0001 |
| 0.30 | -0.0232 | +0.0504 | +0.0300 | -0.0068 |
| 0.45 | -0.0543 | +0.0538 | +0.0359 | -0.0183 |

## Readiness ladder

- Weeks 1–3: **collection only**
- Weeks 4–7: **early diagnostic only**
- Weeks 8–11: **calibration review eligible**
- Weeks 12–17: **stability review eligible**
- Week 18: **season-complete review**

## Interpretation

Do not select a prospect-prior weight before calibration-review readiness. Weeks 1-3 are collection only; Weeks 4-7 are early diagnostics only. Any eventual promotion requires stable advantage versus the frozen 0% prior control and position-level sanity review.

A higher prospect-prior weight should only advance if it improves the primary future-total-points ranking versus the frozen 0% control without creating material degradation in active-PPG ranking or position-level behavior. Current KTC or current Fundamental Value agreement is not a selection target.

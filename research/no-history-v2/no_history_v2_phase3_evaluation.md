# No-History / Rookie Value V2 — Phase 3 Prospective Evaluator

Method: `no-history-rookie-v2-phase3-prospective-v1`  
Status: **`EARLY_DIAGNOSTIC_ONLY`**

## Guardrail

**Research only. Production deployment is not authorized.**

- Frozen candidate SHA256: `e720f1e26c1dd137f9b3d14110cd2fe1a28843a012d5b01f2d185291398a70c6`
- Frozen at: **2026-09-03T18:50:10.024333Z**
- First eligible future week: **1**
- Completed consecutive weeks used: **[1, 2, 3, 4, 5]**
- Eligible preseason cohort: **95**
- Players with an active game in current window: **77**

## Prospective metrics

Primary target: **Fundamental Value vs cumulative future fantasy points**.

| Prior weight | Total-points Spearman | Active-PPG FV Spearman | Active-PPG PM Spearman | Total-points pairwise |
|---:|---:|---:|---:|---:|
| 0.00 | 0.5453 | 0.5181 | 0.5746 | 0.7098 |
| 0.15 | 0.5355 | 0.5356 | 0.5845 | 0.7055 |
| 0.30 | 0.5203 | 0.5607 | 0.5979 | 0.6995 |
| 0.45 | 0.4911 | 0.5633 | 0.5997 | 0.6872 |

## Difference vs frozen 0% prospect-prior control

| Prior weight | Δ total-points Spearman | Δ active-PPG FV Spearman | Δ active-PPG PM Spearman | Δ total-points pairwise |
|---:|---:|---:|---:|---:|
| 0.15 | -0.0098 | +0.0176 | +0.0098 | -0.0043 |
| 0.30 | -0.0250 | +0.0426 | +0.0232 | -0.0102 |
| 0.45 | -0.0542 | +0.0452 | +0.0251 | -0.0226 |

## Readiness ladder

- Weeks 1–3: **collection only**
- Weeks 4–7: **early diagnostic only**
- Weeks 8–11: **calibration review eligible**
- Weeks 12–17: **stability review eligible**
- Week 18: **season-complete review**

## Interpretation

Do not select a prospect-prior weight before calibration-review readiness. Weeks 1-3 are collection only; Weeks 4-7 are early diagnostics only. Any eventual promotion requires stable advantage versus the frozen 0% prior control and position-level sanity review.

A higher prospect-prior weight should only advance if it improves the primary future-total-points ranking versus the frozen 0% control without creating material degradation in active-PPG ranking or position-level behavior. Current KTC or current Fundamental Value agreement is not a selection target.

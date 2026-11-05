# Age Curve V2 — Phase 5 Prospective Evaluator

Method: `age-curve-v2-phase5-prospective-v1`  
Status: **`CALIBRATION_REVIEW_ELIGIBLE`**

## Guardrail

**Research only. Production deployment is not authorized.**

- Frozen candidate SHA256: `56e19f61b9d804a8982a3abbe0b3876b425d0392611f48b4f41595be520a9d1b`
- Frozen at: **2026-09-03T20:59:35.587961Z**
- First eligible future week: **1**
- Completed consecutive weeks used: **[1, 2, 3, 4, 5, 6, 7, 8]**
- Eligible real-history cohort: **441**
- Players with active game in current window: **417**

## Prospective metrics

Primary target: **Frozen Fundamental Value vs cumulative future fantasy points**.

| Variant | Total Spearman | Total pairwise | Active-PPG Spearman | Δ total Spearman vs control | Mean pos Δ total Spearman |
|---|---:|---:|---:|---:|---:|
| `deployed_control` | 0.5818 | 0.7104 | 0.5760 | — | — |
| `position_k25__w50__all_positions` | 0.5940 | 0.7146 | 0.5905 | +0.0122 | +0.0094 |
| `position_k25__w50__qb_control` | 0.5897 | 0.7134 | 0.5874 | +0.0079 | +0.0064 |
| `tier_k50__w25__all_positions` | 0.5843 | 0.7120 | 0.5802 | +0.0025 | +0.0035 |

## Readiness ladder

- Weeks 1–3: **collection only**
- Weeks 4–7: **early diagnostic only**
- Weeks 8–11: **calibration review eligible**
- Weeks 12–17: **stability review eligible**
- Week 18: **season-complete review**

## Interpretation

Do not select or deploy an age bridge before calibration-review readiness. Weeks 1-3 are collection only and Weeks 4-7 are early diagnostics only. Promotion requires stable overall and by-position improvement versus the frozen deployed control.

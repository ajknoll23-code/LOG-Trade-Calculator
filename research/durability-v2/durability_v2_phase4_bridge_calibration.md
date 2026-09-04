# Durability / Availability V2 — Phase 4 Bridge Calibration

Method: `durability-v2-phase4-bridge-calibration-v1`  
Status: **`RESEARCH_ONLY_DURABILITY_BRIDGE_CALIBRATION`**

## Guardrail

**Research only. No deployed durability or player value is changed.**

Bridge strength is selected from historical out-of-sample performance.
Current-board movement is only a stability gate.

## Historical survivor-only out-of-sample results

| Variant | N | MAE | Δ MAE | RMSE | Spearman | Δ Spearman | Pos improved | Folds improved | Hist pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `deployed_control` | 12488 | 0.2290 | — | 0.3144 | 0.3131 | — | — | — | PASS |
| `bridge_w25` | 12488 | 0.2239 | -0.0051 | 0.3058 | 0.3325 | +0.0194 | 7/7 | 10/10 | PASS |
| `bridge_w50` | 12488 | 0.2200 | -0.0090 | 0.2997 | 0.3424 | +0.0293 | 7/7 | 10/10 | PASS |
| `bridge_w75` | 12488 | 0.2174 | -0.0116 | 0.2962 | 0.3468 | +0.0337 | 7/7 | 10/10 | PASS |
| `bridge_w100` | 12488 | 0.2163 | -0.0126 | 0.2955 | 0.3494 | +0.0362 | 7/7 | 10/10 | PASS |

## Current-board stability

| Variant | Median abs FV | P90 abs FV | P95 abs FV | Max abs FV | P90 abs games Δ | Min pos rank ρ | Min top-N overlap | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `bridge_w25` | 0.3% | 2.4% | 2.9% | 12.7% | 0.73 | 0.9979 | 93.3% | PASS |
| `bridge_w50` | 0.7% | 4.7% | 5.8% | 23.1% | 1.46 | 0.9896 | 93.3% | PASS |
| `bridge_w75` | 1.0% | 7.1% | 8.7% | 25.8% | 2.19 | 0.9851 | 93.3% | PASS |
| `bridge_w100` | 1.3% | 9.4% | 11.6% | 32.7% | 2.92 | 0.9744 | 93.3% | PASS |

## Decision

- Monitoring leader: **`bridge_w100`**
- Conservative comparator: **`bridge_w50`**
- Deployment authorized: **No**

## Phase 5

Freeze deployed_control, monitoring_leader, and the prespecified conservative_comparator prospectively before the 2026 season. Primary prospective target should be games available / scheduled games among players with a frozen real-history durability signal. Do not mutate Production V2, Age Curve V2, Opportunity V2, or No-History V2.

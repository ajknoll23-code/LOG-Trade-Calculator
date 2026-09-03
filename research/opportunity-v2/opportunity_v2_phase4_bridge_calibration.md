# Continuous Opportunity / Role Signal V2 — Phase 4 Bridge Calibration

Method: `opportunity-v2-phase4-bridge-calibration-v1`  
Status: **`RESEARCH_ONLY_OPPORTUNITY_BRIDGE_CALIBRATION`**

## Guardrail

**Research only. No deployed ROLE_MULT or player value is changed.**

## Historical + current calibration

| Weight | Hist MAE | Δ MAE | Hist Spearman | Δ Spearman | Pos MAE improved | Folds improved | Current median | Current P90 | Min pos rank ρ | Min top-N | Pass |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0% | 2.1913 | — | 0.6740 | — | — | — | 0.0% | 0.0% | 1.0000 | 100.0% | PASS |
| 10% | 2.1876 | -0.0037 | 0.6750 | +0.0009 | 7/7 | 9/10 | 0.6% | 1.8% | 0.9967 | 95.8% | PASS |
| 25% | 2.1827 | -0.0086 | 0.6759 | +0.0019 | 7/7 | 9/10 | 1.4% | 4.6% | 0.9875 | 94.4% | PASS |
| 40% | 2.1788 | -0.0125 | 0.6763 | +0.0022 | 7/7 | 9/10 | 2.3% | 7.3% | 0.9711 | 91.7% | PASS |
| 50% | 2.1766 | -0.0147 | 0.6763 | +0.0022 | 7/7 | 9/10 | 2.9% | 9.1% | 0.9506 | 88.9% | PASS |
| 60% | 2.1749 | -0.0164 | 0.6760 | +0.0020 | 7/7 | 9/10 | 3.5% | 10.9% | 0.9303 | 87.5% | FAIL |
| 75% | 2.1732 | -0.0181 | 0.6754 | +0.0014 | 7/7 | 9/10 | 4.3% | 13.7% | 0.9198 | 83.3% | FAIL |
| 100% | 2.1727 | -0.0186 | 0.6734 | -0.0006 | 7/7 | 9/10 | 5.8% | 18.3% | 0.9094 | 83.3% | FAIL |

## By-position historical MAE delta vs 0% control

| Weight | QB | RB | WR | TE | DL | LB | DB |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10% | -0.0206 | -0.0036 | -0.0029 | -0.0008 | -0.0046 | -0.0022 | -0.0026 |
| 25% | -0.0480 | -0.0081 | -0.0064 | -0.0017 | -0.0106 | -0.0050 | -0.0062 |
| 40% | -0.0713 | -0.0109 | -0.0089 | -0.0021 | -0.0156 | -0.0073 | -0.0093 |
| 50% | -0.0853 | -0.0121 | -0.0101 | -0.0022 | -0.0186 | -0.0085 | -0.0110 |
| 60% | -0.0966 | -0.0127 | -0.0108 | -0.0022 | -0.0212 | -0.0095 | -0.0125 |
| 75% | -0.1074 | -0.0128 | -0.0114 | -0.0020 | -0.0243 | -0.0103 | -0.0141 |
| 100% | -0.1107 | -0.0104 | -0.0109 | -0.0011 | -0.0262 | -0.0104 | -0.0156 |

## Screening result

Survivors: `bridge_w50`, `bridge_w40`, `bridge_w25`, `bridge_w10`

Monitoring leader: **`bridge_w50`**

**Monitoring leader is not a deployment choice.**

## Phase 5

Freeze a small prospective family before Week 1: deployed control, the Phase-4 monitoring leader (bridge_w50), and one adjacent more-conservative survivor if available. Grade frozen Fundamental Values against completed 2026 outcomes. Never auto-deploy.

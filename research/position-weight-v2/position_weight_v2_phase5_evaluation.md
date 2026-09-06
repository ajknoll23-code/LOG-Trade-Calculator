# Position Weight / Cross-Position Economics V2 — Phase 5 Prospective Evaluator

Method: `position-weight-v2-phase5-prospective-v1`  
Status: **`READY_WAITING_FOR_COMPLETED_WEEK_1`**

## Guardrail

**Research only. No POSITION_WEIGHT deployment is authorized.**

- Frozen at: **2026-09-06T01:51:36.482597Z**
- Frozen prediction SHA256: `bfe708b0aa991a2cfbafbb008b60944349fc040134e4bcd67f8d3cf79691ca47`
- Completed consecutive weeks used: **none**
- Full structural-allocation universe: **549**
- Primary real-history cohort: **441**

## Frozen variants

| Variant | QB | RB | WR | TE | DL | LB | DB |
|---|---:|---:|---:|---:|---:|---:|---:|
| `deployed_control` | 1.300 | 0.890 | 1.000 | 0.820 | 0.930 | 1.120 | 0.870 |
| `bridge_50` | 1.757 | 1.222 | 1.000 | 0.753 | 0.813 | 1.095 | 0.765 |

## Primary prospective metric

**Cross-position pairwise ordering accuracy. Higher is better.**

Same-position pairs are excluded. A common global scale cannot change this metric.

| Variant | Players | Pairwise accuracy | Comparable cross-position pairs |
|---|---:|---:|---:|
| `deployed_control` | 0 | — | 0 |
| `bridge_50` | 0 | — | 0 |

Bridge-50 pairwise accuracy delta vs control: **—**

## Secondary normalized-error metric

| Variant | Min-max MAE | Min-max RMSE |
|---|---:|---:|
| `deployed_control` | — | — |
| `bridge_50` | — | — |

Bridge-50 normalized MAE delta vs control: **—**

## Weekly structural allocation audit

| Week | Usable | QB | RB | WR | TE | DL | LB | DB |
|---:|---|---:|---:|---:|---:|---:|---:|---:|

## Readiness ladder

- Weeks 1–3: **collection only**
- Weeks 4–7: **early diagnostic only**
- Weeks 8–11: **calibration review eligible**
- Weeks 12–17: **stability review eligible**
- Week 18: **season-complete review**

## Interpretation

Higher cross-position pairwise accuracy is better. Weeks 1-3 are collection only and Weeks 4-7 are early diagnostics only. Do not promote bridge_50 before calibration-review readiness. A promotion case requires improvement versus deployed control in the aggregate, no persistent collapse in major position-pair diagnostics, acceptable normalized-error behavior, and reconciliation with the separately frozen Replacement Level, Production, Age, No-History, Opportunity, and Durability experiments.

## Fixed outside this experiment

- Production multipliers: frozen preseason
- Age: excluded from this positional-economics score
- Replacement Level V2: unchanged
- PM transform: unchanged
- Global value scale: irrelevant to the primary metric
- No-History/Rookie V2: unchanged
- Age Curve V2: unchanged
- Opportunity V2: unchanged
- Durability V2: unchanged

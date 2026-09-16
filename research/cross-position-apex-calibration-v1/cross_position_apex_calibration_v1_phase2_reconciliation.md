# Cross-Position Apex Calibration V1 — Phase 2 Cross-Study Reconciliation

**Decision:** `HOLD_DEPLOYMENT_CONTINUE_FROZEN_COLLECTION`

**Research only. No production change is authorized.**

## Readiness

| Study | Completed weeks | Current stage |
|---|---:|---|
| `position_weight_v2` | 1 | `collection_only` |
| `replacement_level_v2` | 1 | `collection_only` |
| `production_v2` | 1 | `collection_only` |

## Frozen structural arms

Position Weight V2: `deployed_control` vs `bridge_50`.

Replacement Level V2: all four frozen rank families are preserved;
`stable_positions_only` is used only as the pre-frozen stability-restricted
current-board structural sensitivity arm.

Production V2: history 25% / 45% / 65% are reported as a frozen
sensitivity band at fixed FP=0.50, evidence-hybrid ranks, floor=0.15.
No Week-1 winner is selected.

## Brian Burns vs Josh Allen

| Sensitivity | Burns FV | Allen FV | Burns/Allen |
|---|---:|---:|---:|
| Current control | 7391 | 6564 | 1.1260 |
| Position Weight bridge_50 | 6458 | 8869 | 0.7282 |
| Replacement stable | 6545 | 6564 | 0.9971 |
| Production history 25% transport | 7056 | 6443 | 1.0951 |
| Production history 65% transport | 7545 | 6979 | 1.0811 |
| PW + replacement naive stress | 5719 | 8869 | 0.6448 |

## Double-count diagnostics

| Pair | N | Delta correlation | Same-direction share | Top-50 mover overlap |
|---|---:|---:|---:|---:|
| `position_weight_vs_replacement` | 457 | -0.3365 | 0.4814 | 0.6400 |
| `position_weight_vs_production_history25` | 518 | 0.0625 | 0.3649 | 0.0400 |
| `position_weight_vs_production_history65` | 518 | 0.2604 | 0.4479 | 0.1000 |
| `replacement_vs_production_history25` | 445 | -0.0193 | 0.3978 | 0.2200 |
| `replacement_vs_production_history65` | 445 | -0.0439 | 0.4022 | 0.2600 |

## Current top-20 tracking

| # | Player | Pos | Control | PW bridge | Repl stable | Hist25 transport | Hist65 transport | PW+Repl stress |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | jahmyr gibbs | RB | 8841 | 12138 | — | 9066 | 8865 | — |
| 2 | bijan robinson | RB | 8509 | 11682 | — | 8597 | 8666 | — |
| 3 | puka nacua | WR | 8030 | 8030 | 7476 | 8019 | 8087 | 7476 |
| 4 | jaxon smithnjigba | WR | 7568 | 7568 | 7043 | 7704 | 7476 | 7043 |
| 5 | brian burns | DL | 7391 | 6458 | 6545 | 7056 | 7545 | 5719 |
| 6 | ashton jeanty | RB | 7141 | 9804 | 5751 | 7275 | 7217 | 7895 |
| 7 | jamarr chase | WR | 7023 | 7023 | 6534 | 7211 | 6878 | 6534 |
| 8 | amonra st brown | WR | 6913 | 6913 | 6431 | 7079 | 6788 | 6431 |
| 9 | devon achane | RB | 6632 | 9106 | 5361 | 6515 | 6952 | 7360 |
| 10 | josh allen | QB | 6564 | 8869 | 6564 | 6443 | 6979 | 8869 |
| 11 | byron young | DL | 6123 | 5350 | 5413 | 5916 | 6179 | 4729 |
| 12 | james cook | RB | 5974 | 8202 | 4835 | 5955 | 6173 | 6638 |
| 13 | will anderson | DL | 5961 | 5208 | 5268 | 5686 | 6087 | 4603 |
| 14 | jonathan taylor | RB | 5906 | 8109 | 4784 | 5828 | 6163 | 6568 |
| 15 | george pickens | WR | 5896 | 5896 | 5479 | 5853 | 5972 | 5479 |
| 16 | nik bonitto | DL | 5864 | 5124 | 5182 | 5788 | 5792 | 4528 |
| 17 | drake london | WR | 5852 | 5852 | 5438 | 6003 | 5736 | 5438 |
| 18 | myles garrett | DL | 5655 | 4941 | 5000 | 5353 | 5820 | 4369 |
| 19 | jalen hurts | QB | 5634 | 7613 | 5634 | 5592 | 5920 | 7613 |
| 20 | maxx crosby | DL | 5621 | 4912 | 4965 | 5405 | 5701 | 4338 |

## Provenance / drift guardrail

- Position Weight freeze players with current PM/position drift: **22**
- Production freeze players with current FV drift: **83**

Those differences are expected to include legitimate post-freeze releases.
They are why Production V2 history-weight results are shown as transported
sensitivities rather than falsely presented as exact current-board candidates.

## Decision semantics

While all three studies remain before the eight-week calibration-review
window, this audit holds deployment and preserves the frozen collection.
No coefficient fitting or Week-1 arm selection occurs here.

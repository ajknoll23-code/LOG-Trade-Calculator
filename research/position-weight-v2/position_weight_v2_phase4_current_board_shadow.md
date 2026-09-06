# Position Weight / Cross-Position Economics V2 — Phase 4 Current-Board Shadow

**Research only. No POSITION_WEIGHT deployment is authorized.**

Method: `position-weight-v2-phase4-current-board-shadow-v1`
Board reference date: **2026-09-06**

## Isolation

- Live valuation formula reconstructed exactly: **Yes**
- POSITION_WEIGHT is the only changed component: **Yes**
- Global scale held at **55**

## Candidate weights

| Pos | Deployed | Phase-3 empirical | Bridge 50 | Bridge 75 | Bridge 100 |
|---|---:|---:|---:|---:|---:|
| QB | 1.300 | 2.213 | 1.757 | 1.985 | 2.213 |
| RB | 0.890 | 1.554 | 1.222 | 1.388 | 1.554 |
| WR | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| TE | 0.820 | 0.687 | 0.753 | 0.720 | 0.687 |
| DL | 0.930 | 0.695 | 0.813 | 0.754 | 0.695 |
| LB | 1.120 | 1.070 | 1.095 | 1.083 | 1.070 |
| DB | 0.870 | 0.660 | 0.765 | 0.713 | 0.660 |

## Current-board blast radius

| Variant | Safety | Global ρ | Top50 overlap | Top100 overlap | P90 abs FV Δ | Max Top100 pos-share Δ | QB median FV Δ |
|---|---|---:|---:|---:|---:|---:|---:|
| `bridge_50` | PASS | 0.9647 | +70.0% | +83.0% | +37.3% | +11.0% | +35.1% |
| `bridge_75` | FAIL | 0.9347 | +60.0% | +76.0% | +55.9% | +16.0% | +52.7% |
| `bridge_100` | FAIL | 0.8945 | +58.0% | +69.0% | +74.6% | +23.0% | +70.2% |

## Positional median FV movement

| Variant | QB | RB | WR | TE | DL | LB | DB |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bridge_50` | +35.1% | +37.3% | +0.0% | -8.1% | -12.6% | -2.2% | -12.1% |
| `bridge_75` | +52.7% | +55.9% | +0.0% | -12.2% | -18.9% | -3.3% | -18.1% |
| `bridge_100` | +70.2% | +74.6% | +0.0% | -16.2% | -25.2% | -4.4% | -24.1% |

## Phase 5 handoff

Recommended shadow variant: **`bridge_50`**
Prospective freeze authorized by this research phase: **True**

Passing the board-safety gates means only that the shadow does not create obvious current-board damage. It is not evidence to deploy. Any surviving candidate must still be frozen prospectively before Week 1.

## Guardrails

- deployment_authorized: **false**
- position_weight_change_authorized: **false**
- replacement_rank_change_authorized: **false**
- production_v2_change_authorized: **false**
- transform_change_authorized: **false**
- scale_change_authorized: **false**
- frozen prospective experiments touched: **false**

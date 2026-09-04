# Durability / Availability V2 — Phase 3 Shadow Audit

Method: `durability-v2-phase3-shadow-audit-v1`  
Status: **`RESEARCH_ONLY_DURABILITY_CURRENT_SHADOW`**

## Guardrail

**Research only. No deployed durability or player value is changed.**

The value numbers below are **fixed Production-V2-Phase-1 benchmark
values**, not a rewrite of current deployed Fundamental Value. This
keeps every production/age/position input fixed except projected
availability.

- Current real-history shadow cohort: **425**

## Full-sample trained survivor-only own-history weights

| Pos | N | Trained weight |
|---|---:|---:|
| QB | 597 | 85% |
| RB | 1145 | 50% |
| WR | 1755 | 55% |
| TE | 1051 | 50% |
| DL | 2489 | 55% |
| LB | 2275 | 45% |
| DB | 3176 | 50% |

## Current benchmark movement

| Variant | Changed | Median abs FV | P90 abs FV | Median games Δ | P90 abs games Δ | Min pos rank ρ | Min top-N overlap | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `trained_blend_w25` | 308 | 0.3% | 2.4% | +0.000 | 0.73 | 0.9979 | 93.3% | PASS |
| `trained_blend_w50` | 308 | 0.7% | 4.7% | +0.000 | 1.46 | 0.9896 | 93.3% | PASS |
| `trained_blend_w100` | 308 | 1.3% | 9.4% | +0.000 | 2.92 | 0.9744 | 93.3% | PASS |

## Largest full-strength movers

| Player | Pos | GP25 | Old weight | New weight | Old proj games | New proj games | Games Δ | Benchmark FV Δ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| micah mcfadden | LB | 1 | 8.5% | 45.0% | 14.72 | 9.25 | -5.47 | -32.7% |
| phil mafah | RB | 1 | 13.1% | 50.0% | 13.17 | 8.00 | -5.17 | -23.1% |
| nnamdi madubuike | DL | 2 | 19.6% | 55.0% | 14.07 | 8.75 | -5.32 | -23.0% |
| travis hunter | WR | 7 | 15.4% | 55.0% | 14.61 | 11.05 | -3.56 | -20.5% |
| ed oliver | DL | 3 | 19.6% | 55.0% | 14.26 | 9.30 | -4.96 | -20.3% |
| walter nolen | DL | 6 | 19.6% | 55.0% | 14.85 | 10.95 | -3.90 | -18.3% |
| jalen mcmillan | WR | 4 | 15.4% | 55.0% | 14.15 | 9.40 | -4.75 | -17.9% |
| nick bosa | DL | 3 | 19.6% | 55.0% | 14.26 | 9.30 | -4.96 | -17.5% |
| tory horton | WR | 8 | 15.4% | 55.0% | 14.76 | 11.60 | -3.16 | -17.1% |
| braelon allen | RB | 4 | 13.1% | 50.0% | 13.56 | 9.50 | -4.06 | -17.0% |
| malik nabers | WR | 4 | 15.4% | 55.0% | 14.15 | 9.40 | -4.75 | -16.7% |
| deshon elliott | DB | 5 | 10.8% | 50.0% | 14.81 | 10.50 | -4.31 | -15.6% |
| shemar stewart | DL | 8 | 19.6% | 55.0% | 15.24 | 12.05 | -3.19 | -15.3% |
| drake maye | QB | 17 | 37.6% | 85.0% | 12.63 | 15.95 | +3.32 | 14.1% |
| kerby joseph | DB | 6 | 10.8% | 50.0% | 14.92 | 11.00 | -3.92 | -14.0% |
| jaylon carlies | DB | 3 | 10.8% | 50.0% | 14.59 | 9.50 | -5.09 | -13.2% |
| matthew stafford | QB | 17 | 37.6% | 85.0% | 12.63 | 15.95 | +3.32 | 12.7% |
| caleb williams | QB | 17 | 37.6% | 85.0% | 12.63 | 15.95 | +3.32 | 12.6% |
| trevor lawrence | QB | 17 | 37.6% | 85.0% | 12.63 | 15.95 | +3.32 | 12.0% |
| audric estime | RB | 7 | 13.1% | 50.0% | 13.95 | 11.00 | -2.95 | -11.9% |
| bo nix | QB | 17 | 37.6% | 85.0% | 12.63 | 15.95 | +3.32 | 11.6% |
| dak prescott | QB | 17 | 37.6% | 85.0% | 12.63 | 15.95 | +3.32 | 11.6% |
| jared goff | QB | 17 | 37.6% | 85.0% | 12.63 | 15.95 | +3.32 | 11.5% |
| mykel williams | DL | 9 | 19.6% | 55.0% | 15.44 | 12.60 | -2.84 | -11.5% |
| baker mayfield | QB | 17 | 37.6% | 85.0% | 12.63 | 15.95 | +3.32 | 11.3% |

## Screening result

Survivors: `trained_blend_w25`, `trained_blend_w50`, `trained_blend_w100`

**Passing this screen is not deployment authorization.**

## Phase 4

Historically calibrate the bridge between deployed R2 durability weights and the trained survivor-only weights. Use the same leave-one-base-season-out protocol as Phase 2, testing bridge fractions rather than choosing 25/50/100 from current-board appearance. Do not deploy from Phase 3.

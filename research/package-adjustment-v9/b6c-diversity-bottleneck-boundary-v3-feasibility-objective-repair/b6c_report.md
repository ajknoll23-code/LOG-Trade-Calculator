# Package Adjustment V9 — B6C Catalog Diversity Bottleneck Boundary Audit

**Decision:** `DIAGNOSE_BROAD_RELAXATION_ONLY_SOURCE_EXPANSION_OR_SCOPE_REDUCTION_REQUIRED`

B6C is diagnostic only. It preserves the B6B STOP, all efficacy thresholds, the five-topology research scope, and the no-human-outcomes firewall.

## Original Tier C reproduction
- Joint Tier C (per-topology 24, global 60, side reuse 6): INFEASIBLE

## Direct anonymous 2v4 concentration diagnostic
- Reservoir: 127 trades; target: 120; only 7 trades can be omitted.
- Distinct players: 60; distinct side bundles: 110.
- Most frequent player appears in 54 of 127 trades.
- Any 120-trade subset must contain that player at least 47 times.
- Players that mathematically force a Tier C cap-24 violation in every 120-trade subset: 5.

## Constraint-family ablations
| Diagnostic | Feasible |
|---|---|
| counts_only | yes |
| side_only | no |
| player_caps_only_tier_c | no |
| tier_c_without_global_cap | no |
| tier_c_without_per_topology_cap | no |

## Single-topology Tier C diagnosis
| Topology | Tier C local feasible | First feasible player cap on grid (side cap 6) |
|---|---|---:|
| 2v3 | yes | 24 |
| 2v4 | no | none |
| 3v3 | yes | 24 |
| 3v4 | yes | 24 |
| 4v4 | yes | 24 |

## Drop-one-topology Tier C diagnosis
| Dropped topology | Remaining four feasible |
|---|---|
| 2v3 | no |
| 2v4 | yes |
| 3v3 | no |
| 3v4 | no |
| 4v4 | no |

## Prospective diagnostic envelopes
| Envelope | Per-topology cap | Global cap | Side cap | Feasible |
|---|---:|---:|---:|---|
| modest | 30 | 75 | 8 | no |
| aggressive diagnostic only | 36 | 90 | 10 | no |
| broad sanity only | 60 | 150 | 12 | yes |

## Next
Do not relax diversity this far. Preregister candidate-blind source expansion or an explicit additional topology-scope reduction before B7.

No B7 authorization, no human challenge catalog, and no production change are created by B6C.

# NextGen V2 M2b Prospective Failure Diagnostic

**Status:** `completed_posthoc_failure_diagnostic_research_only`

This is a post-hoc diagnostic over spent prospective evidence. It does not retune M2b, create M3, or authorize a production change.

## Frozen result reproduction

- M0 combined equal-cell log loss: **0.858674**
- M2b combined equal-cell log loss: **0.856747**
- Improvement (M0 - M2b): **0.001926**
- Required improvement: **0.005000**
- Bootstrap favorable fraction: **0.9612**

## Family diagnosis

| Family | M0 | M2b | Improvement |
|---|---:|---:|---:|
| core_concentration_2v2 | 0.777906 | 0.769977 | 0.007929 |
| fragmentation_filler | 1.461117 | 1.487953 | -0.026836 |
| structural_topology_3v3 | 0.759372 | 0.758071 | 0.001301 |

## Family × scale

| Family / scale | M0 weighted loss | M2b weighted loss | Improvement |
|---|---:|---:|---:|
| core_concentration_2v2|high | 0.769693 | 0.733068 | 0.036625 |
| core_concentration_2v2|low | 0.665381 | 0.664962 | 0.000419 |
| core_concentration_2v2|mid | 0.899545 | 0.909718 | -0.010173 |
| fragmentation_filler|high | 0.632834 | 0.636789 | -0.003954 |
| fragmentation_filler|low | 1.790019 | 1.832448 | -0.042430 |
| fragmentation_filler|mid | 1.960497 | 1.994623 | -0.034126 |
| structural_topology_3v3|high | 0.700356 | 0.676344 | 0.024012 |
| structural_topology_3v3|low | 0.714407 | 0.722091 | -0.007684 |
| structural_topology_3v3|mid | 0.837303 | 0.848978 | -0.011675 |

## Most harmful challenges

| Challenge | Family | Scale | Topology | Improvement |
|---|---|---|---|---:|
| `pkgnv2p1_core_concentration_2v2_high_core_70_30_r06` | core_concentration_2v2 | high | 2v2 | -0.240050 |
| `pkgnv2p1_core_concentration_2v2_mid_core_50_50_control_r01` | core_concentration_2v2 | mid | 2v2 | -0.074842 |
| `pkgnv2p1_fragmentation_filler_mid_frag_80_20_vs_80_10_10_r02` | fragmentation_filler | mid | 2v3 | -0.069977 |
| `pkgnv2p1_structural_topology_3v3_mid_holdout_70_20_10_vs_40_35_25_r03` | structural_topology_3v3 | mid | 3v3 | -0.068214 |
| `pkgnv2p1_structural_topology_3v3_low_holdout_70_20_10_vs_40_35_25_r04` | structural_topology_3v3 | low | 3v3 | -0.065659 |
| `pkgnv2p1_fragmentation_filler_low_frag_80_20_vs_80_10_10_r03` | fragmentation_filler | low | 2v3 | -0.065485 |
| `pkgnv2p1_fragmentation_filler_low_frag_80_20_vs_80_10_10_r01` | fragmentation_filler | low | 2v3 | -0.063870 |
| `pkgnv2p1_structural_topology_3v3_mid_holdout_60_25_15_vs_34_33_33_r04` | structural_topology_3v3 | mid | 3v3 | -0.063648 |
| `pkgnv2p1_fragmentation_filler_low_frag_80_20_vs_80_10_10_r05` | fragmentation_filler | low | 2v3 | -0.056117 |
| `pkgnv2p1_core_concentration_2v2_mid_core_70_30_r05` | core_concentration_2v2 | mid | 2v2 | -0.052856 |

## Most helpful challenges

| Challenge | Family | Scale | Topology | Improvement |
|---|---|---|---|---:|
| `pkgnv2p1_core_concentration_2v2_high_core_80_20_r04` | core_concentration_2v2 | high | 2v2 | 0.298945 |
| `pkgnv2p1_core_concentration_2v2_high_core_80_20_r05` | core_concentration_2v2 | high | 2v2 | 0.236208 |
| `pkgnv2p1_core_concentration_2v2_high_core_80_20_r01` | core_concentration_2v2 | high | 2v2 | 0.234247 |
| `pkgnv2p1_core_concentration_2v2_high_core_80_20_r02` | core_concentration_2v2 | high | 2v2 | 0.218022 |
| `pkgnv2p1_core_concentration_2v2_high_core_80_20_r03` | core_concentration_2v2 | high | 2v2 | 0.124072 |
| `pkgnv2p1_core_concentration_2v2_high_core_70_30_r05` | core_concentration_2v2 | high | 2v2 | 0.084531 |
| `pkgnv2p1_structural_topology_3v3_high_holdout_70_20_10_vs_40_35_25_r01` | structural_topology_3v3 | high | 3v3 | 0.063627 |
| `pkgnv2p1_core_concentration_2v2_high_core_70_30_r02` | core_concentration_2v2 | high | 2v2 | 0.060203 |
| `pkgnv2p1_core_concentration_2v2_high_core_70_30_r04` | core_concentration_2v2 | high | 2v2 | 0.053462 |
| `pkgnv2p1_structural_topology_3v3_high_holdout_70_20_10_vs_40_35_25_r02` | structural_topology_3v3 | high | 3v3 | 0.053266 |

## M3 design constraints

- Treat the exact 900-vote prospective dataset as spent development evidence; it may inform M3 design/training but may not serve as fresh confirmation.
- Do not patch or promote M2b in production; production remains V1.6.
- Do not force one universal package transform across core concentration, fragmentation/filler, and structural topology without a safety interaction.
- Give fragmentation/filler an explicit topology/family interaction or shrinkage path capable of reverting toward raw-FV M0 behavior.
- Any M3 fitting or model selection may use only evidence already designated as spent/development evidence.
- Freeze the complete M3 candidate and all evaluation rules before any new prospective exposure.
- Generate a fresh challenge catalog without using future outcomes or model-performance-driven selection.
- Require a fresh prospective holdout before any M3 production-eligibility decision.

## Next action

Use this diagnostic as spent development evidence to design research-only M3 candidates; do not evaluate production eligibility again until a fresh preregistered prospective holdout exists.

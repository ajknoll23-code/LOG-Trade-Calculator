# Package Adjustment V9 — B6D Candidate-Blind Current-Source Expansion and Scope Amendment

**Decision:** `PASS_FOUR_TOPOLOGY_SCOPE_AMENDMENT_DROP_2V4_240_TIER_C_RATE_FEASIBLE`

B6D is the prospective amendment required by B6C. It does not weaken q, theta_min=.60, the 7% fair band, Holm FWER=.05, or the Tier-C concentration rates.

## Current candidate-blind source freeze
- Source commit: `6da7b6ca809585954ba6c097e93848c191d3ee75`
- Current matched player source: **528** players
- FV >= 2500 candidate-frame players: **296**
- Old V7 source: 472 players; overlap 467; new current-source players 61; old-only 5.
- Source = current rostered players (excluding explicit Retired status) plus active league free agents; current runtime index.html FV is authoritative.
- value_uncertainty center-value cross-check is diagnostic only: artifact generated 2026-10-03T15:42:37.645188Z; 53 shared-player center mismatches; max absolute delta 13.
- Ambiguous normalized-name exclusions: **6**; collisions are excluded rather than merged.
- QB/RB/WR/TE/DL/LB/DB scope is continuous with V7; IDP is not newly introduced by B6D.
- No draft picks and no market values are used.

## Discordant breadth reservoirs
| Topology | Reservoir | Distinct players | Distinct sides | Discordant seen before cap |
|---|---:|---:|---:|---:|
| 2v3 | 3812 | 161 | 630 | 3812 |
| 2v4 | 256 | 66 | 136 | 256 |
| 3v3 | 5000 | 271 | 2925 | 78162 |
| 3v4 | 5000 | 296 | 3103 | 34057 |
| 4v4 | 5000 | 290 | 3369 | 104350 |

## Tier-C-rate feasibility
| Scope | Target/topology | Per-topology player cap | Global player cap | Side reuse cap | Feasible |
|---|---:|---:|---:|---:|---|
| five_topology | 120 | 24 | 60 | 6 | no |
| five_topology | 180 | 36 | 90 | 9 | no |
| five_topology | 240 | 48 | 120 | 12 | no |
| four_topology_drop_2v4 | 120 | 24 | 48 | 6 | yes |
| four_topology_drop_2v4 | 180 | 36 | 72 | 9 | yes |
| four_topology_drop_2v4 | 240 | 48 | 96 | 12 | yes |

## Prospective scope decision
- Frozen B7 V9 topology family: `2v3, 3v3, 3v4, 4v4`
- V1.7-only topology family: `2v2, 2v4`
- B7 is authorized as an **independent operating-characteristic confirmation only**. Human voting and human catalog generation remain unauthorized.

## Firewall
- No V9 human outcomes exist or are read.
- No V8 candidate performance is read.
- No selected challenge identities are written durably; MILP witnesses remain transient.
- Production Package Adjustment V1.7 is unchanged.

# Position Weight / Cross-Position Economics V2 — Phase 2 Ruleset Simulation

**Research only. No POSITION_WEIGHT change is authorized.**

Method: `position-weight-v2-phase2-ruleset-simulation-v1`

## Current ruleset snapshot

- Sleeper season: **2026**
- Teams: **12**
- `roster_positions`: `['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'SUPER_FLEX', 'K', 'DL', 'DL', 'LB', 'LB', 'DB', 'DB', 'IDP_FLEX', 'IDP_FLEX', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN']`

## Historical allocator validation

| Season | Mean abs error starters/team-week | Max abs error |
|---|---:|---:|
| 2024 | 0.124 | 0.222 |
| 2025 | 0.150 | 0.342 |

| Pos | 2024 observed/sim | 2025 observed/sim |
|---|---|---|
| QB | 1.759/1.815 | 1.713/1.787 |
| RB | 1.861/2.019 | 1.962/2.106 |
| WR | 2.361/2.162 | 2.246/2.102 |
| TE | 1.019/1.005 | 1.041/1.005 |
| DL | 2.083/2.009 | 2.357/2.056 |
| LB | 2.616/2.468 | 2.467/2.458 |
| DB | 2.301/2.523 | 2.144/2.486 |

## 2026-rules structural demand

| Pos | Structural starters/team-week | Median marginal-start pts | Median avg starter pts | Old observed demand | Ruleset Δ |
|---|---:|---:|---:|---:|---:|
| QB | 1.947 | 11.300 | 20.800 | 1.736 | 0.211 (+12.1%) |
| RB | 2.498 | 10.300 | 19.093 | 1.911 | 0.586 (+30.7%) |
| WR | 2.509 | 10.325 | 16.748 | 2.304 | 0.206 (+8.9%) |
| TE | 1.046 | 8.700 | 13.378 | 1.030 | 0.016 (+1.6%) |
| DL | 2.141 | 12.000 | 17.165 | 2.220 | -0.079 (-3.5%) |
| LB | 2.863 | 12.250 | 17.723 | 2.542 | 0.322 (+12.7%) |
| DB | 2.995 | 12.312 | 16.838 | 2.223 | 0.773 (+34.8%) |

## Interpretation

Historical validation measures how closely the league-wide optimal structural allocator resembles real manager starts under the same old rules. It is not expected to be perfect because ownership constraints and manager decisions are intentionally omitted.

The 2026-rules simulation then holds the player-performance samples fixed and changes only the slot structure, so the resulting positional demand movement is attributable to today's rules.

This phase still does **not** create candidate POSITION_WEIGHT values.

## Guardrails

- deployment_authorized: **false**
- position_weight_change_authorized: **false**
- replacement_rank_change_authorized: **false**
- production_v2_change_authorized: **false**
- transform_change_authorized: **false**
- scale_change_authorized: **false**
- frozen prospective experiments touched: **false**

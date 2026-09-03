# Continuous Opportunity / Role Signal V2 — Phase 1 Coverage Audit

Method: `opportunity-v2-phase1-coverage-v1`  
Status: **`RESEARCH_ONLY_CONTINUOUS_OPPORTUNITY_COVERAGE_AUDIT`**

## Guardrail

**Research only. No deployed ROLE_MULT or player value is changed.**

## Signal definition

Primary opportunity signal:

`sum(primary-unit game snap share) / scheduled team games`

For QB/RB/WR/TE the primary unit is offense. For DL/LB/DB it is defense.
Missing games contribute zero, so the signal includes both role and availability.

Secondary signal: average primary-unit snap share in games where the player
recorded primary-unit snaps.

## Historical coverage

- Historical seasons: **2015–2025**
- Player-seasons: **18250**
- GSIS-linkable player-seasons: **18222 (99.8%)**

| Pos | Player-seasons | GSIS coverage | Opp P25 | Opp P50 | Opp P75 | Active snap P50 | Y→Y+1 Spearman |
|---|---:|---:|---:|---:|---:|---:|---:|
| QB | 856 | 99.9% | 5.9% | 28.3% | 83.3% | 83.5% | 0.680 |
| RB | 1892 | 99.9% | 3.7% | 14.3% | 33.6% | 23.5% | 0.662 |
| WR | 2649 | 99.7% | 6.2% | 26.3% | 58.2% | 41.4% | 0.671 |
| TE | 1535 | 99.6% | 7.8% | 25.5% | 47.9% | 35.1% | 0.646 |
| DL | 3417 | 99.9% | 10.9% | 30.6% | 51.3% | 40.2% | 0.616 |
| LB | 3374 | 100.0% | 2.9% | 20.6% | 55.1% | 35.7% | 0.696 |
| DB | 4527 | 99.8% | 4.6% | 27.9% | 67.8% | 53.0% | 0.663 |

## Current tracked-player coverage

- Tracked players: **549**
- With 2025 opportunity: **428**
- With current Sleeper depth-chart order: **450**
- With PFR ID: **528**
- With GSIS ID: **532**
- No-history players: **108**

| Pos | Tracked | 2025 opp | Depth order | Median 2025 opp | Role vs opp ρ | Inverse depth vs opp ρ |
|---|---:|---:|---:|---:|---:|---:|
| QB | 64 | 50 | 53 | 56.8% | 0.766 | 0.680 |
| RB | 97 | 77 | 77 | 36.2% | 0.862 | 0.556 |
| WR | 114 | 80 | 95 | 59.8% | 0.472 | 0.382 |
| TE | 44 | 34 | 37 | 61.2% | 0.429 | 0.357 |
| DL | 86 | 72 | 66 | 60.7% | 0.510 | 0.332 |
| LB | 79 | 60 | 67 | 77.6% | 0.551 | 0.040 |
| DB | 65 | 55 | 55 | 86.3% | 0.491 | 0.247 |

## Deployed role labels vs 2025 opportunity

| Role | ROLE_MULT | Tracked | With 2025 opp | Opp P25 | Opp median | Opp P75 |
|---|---:|---:|---:|---:|---:|---:|
| Elite | 1.400 | 84 | 83 | 68.2% | 80.0% | 91.4% |
| Every-Down | 1.150 | 60 | 58 | 50.9% | 71.1% | 90.7% |
| Starter | 1.000 | 53 | 49 | 45.9% | 67.6% | 77.0% |
| Rotational | 0.650 | 127 | 111 | 48.3% | 62.9% | 75.2% |
| Understudy | 0.570 | 62 | 50 | 35.8% | 49.4% | 63.2% |
| Depth | 0.350 | 61 | 41 | 17.8% | 33.1% | 48.3% |
| Speculative | 0.220 | 102 | 36 | 7.6% | 19.3% | 28.1% |

## Largest role/opportunity disagreements

These are descriptive only. Current 2026 role/depth labels are not assumed
to be wrong merely because they differ from 2025 opportunity.

| Player | Pos | Role | 2025 opp | Active snap | Depth order | Percentile gap |
|---|---|---|---:|---:|---:|---:|
| fred warner | LB | Elite | 29.9% | 84.8% | 1 | 83.1% |
| byron young | DL | Elite | 29.8% | 29.8% | 1 | 82.4% |
| rashee rice | WR | Elite | 35.2% | 74.9% | 1 | 77.8% |
| cade otton | TE | Understudy | 88.0% | 93.5% | 1 | 72.7% |
| nick bosa | DL | Every-Down | 11.3% | 64.0% | 1 | 72.5% |
| malik nabers | WR | Every-Down | 18.7% | 79.5% | 1 | 70.3% |
| mason graham | DL | Understudy | 72.9% | 72.9% | 1 | 69.0% |
| tucker kraft | TE | Elite | 40.5% | 86.0% | 1 | 68.2% |
| jessie bates | DB | Rotational | 98.9% | 98.9% | — | 66.7% |
| deshon elliott | DB | Every-Down | 22.1% | 75.2% | 1 | 65.7% |
| luther burden | WR | Every-Down | 35.0% | 39.7% | — | 63.9% |
| nakobe dean | LB | Every-Down | 35.9% | 67.8% | 1 | 62.7% |
| elic ayomanor | WR | Depth | 75.8% | 80.6% | 4 | 62.0% |
| garrett wilson | WR | Every-Down | 35.8% | 87.0% | 1 | 61.4% |
| devin white | LB | Rotational | 99.4% | 99.4% | 2 | 61.0% |
| jerry jeudy | WR | Understudy | 84.5% | 84.5% | 3 | 60.8% |
| ed oliver | DL | Starter | 10.5% | 59.3% | 1 | 59.9% |
| nahshon wright | DB | Rotational | 96.8% | 96.8% | 1 | 59.3% |
| sam laporta | TE | Elite | 48.0% | 90.7% | 1 | 59.1% |
| nick emmanwori | DB | Elite | 69.9% | 84.9% | 1 | 58.3% |
| dalton kincaid | TE | Starter | 26.4% | 37.4% | 1 | 57.6% |
| tre tucker | WR | Rotational | 94.8% | 94.8% | 1 | 55.7% |
| christian watson | WR | Every-Down | 39.8% | 67.7% | 1 | 55.1% |
| dexter lawrence | DL | Understudy | 67.5% | 67.5% | — | 54.9% |
| theo johnson | TE | Understudy | 76.5% | 86.7% | 2 | 54.5% |

## Phase 2

Use only lagged/preseason-available opportunity features and test out-of-sample by historical base season whether continuous opportunity adds predictive value beyond current production alone. Do not use same-season future snap information. Candidate families should begin with position-normalized season opportunity share, active-game snap share, and year-over-year change; depth-chart order should remain a current/preseason diagnostic until historical depth snapshots are available.

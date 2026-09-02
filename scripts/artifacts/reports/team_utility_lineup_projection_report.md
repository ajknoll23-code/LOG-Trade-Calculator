# Team Utility Lineup Projection Artifact

## Status

**Generated projection-selection data only. Fundamental Value is unchanged.**

## Architecture

- QB/RB/WR/TE: Trade Desk league-scored Sleeper 2026 projections.
- Offensive fallback: normalized FantasyPros projection only when Sleeper is missing.
- DL/LB/DB: canonical validated IDP V1 category-level ensemble.
- Identity: stable Sleeper player ID.
- K: intentionally omitted; Team Utility must use Fundamental Value for the dedicated kicker slot until a validated kicker projection pipeline exists.
- Missing projection is never interpreted as zero.

## Artifact coverage

- Total projected players: **1022**
- Position counts: **{"DB": 211, "DL": 193, "LB": 147, "QB": 34, "RB": 126, "TE": 116, "WR": 195}**
- Source counts: **{"idp_v1_both": 356, "idp_v1_fp_only": 107, "idp_v1_sleeper_only": 88, "sleeper_league_scored": 471}**

## Current league validation

- Teams checked: **12**
- Teams with all 17 legal slots fillable: **12 / 12**
- Teams with a projection-complete non-K starting lineup: **12 / 12**
- Active non-K roster projection coverage: **93.26%**
- Selected non-K players needing fallback: **0**

## Team detail

| Team | Active non-K coverage | Legal starters | Missing projected starters |
|---|---:|---:|---:|
| Just Run Power | 95.0% | 17/17 | 0 |
| Sunday Brunson  | 94.9% | 17/17 | 0 |
| Narroway Farms M714 | 95.0% | 17/17 | 0 |
| Landry's Hat | 100.0% | 17/17 | 0 |
| Pullham Bluecocks  | 97.3% | 17/17 | 0 |
| Cock Mchorse 🐴 | 95.0% | 17/17 | 0 |
| Jersey Bagels | 83.8% | 17/17 | 0 |
| Apex Predators | 87.5% | 17/17 | 0 |
| Toddy2times | 95.0% | 17/17 | 0 |
| Moose Knuckles | 81.1% | 17/17 | 0 |
| <respectable team name> | 94.7% | 17/17 | 0 |
| Serious Gourmet Shit | 100.0% | 17/17 | 0 |

## Identity / provenance

- FantasyPros IDs mapped to Sleeper IDs: **474**
- Manual-review identity rows skipped: **0**

The artifact is deterministic: its input file SHA-256 hashes are stored in the JSON, and no wall-clock timestamp is embedded.


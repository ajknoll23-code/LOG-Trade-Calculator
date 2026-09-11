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

- Total projected players: **1071**
- Position counts: **{"DB": 206, "DL": 194, "LB": 148, "QB": 73, "RB": 131, "TE": 126, "WR": 193}**
- Source counts: **{"fantasypros_normalized_fallback": 100, "idp_v1_both": 356, "idp_v1_fp_only": 110, "idp_v1_no_new_data": 2, "idp_v1_sleeper_only": 80, "sleeper_league_scored": 423}**

## Current league validation

- Teams checked: **12**
- Teams with all 17 legal slots fillable: **12 / 12**
- Teams with a projection-complete non-K starting lineup: **12 / 12**
- Active non-K roster projection coverage: **96.28%**
- Selected non-K players needing fallback: **0**

## Team detail

| Team | Active non-K coverage | Legal starters | Missing projected starters |
|---|---:|---:|---:|
| Just Run Power | 100.0% | 17/17 | 0 |
| Sunday Brunson  | 97.1% | 17/17 | 0 |
| Narroway Farms M714 | 100.0% | 17/17 | 0 |
| Landry's Hat | 100.0% | 17/17 | 0 |
| Pullham Bluecocks  | 97.2% | 17/17 | 0 |
| Cock Mchorse 🐴 | 94.4% | 17/17 | 0 |
| Jersey Bagels | 82.9% | 17/17 | 0 |
| Apex Predators | 91.7% | 17/17 | 0 |
| Toddy2times | 100.0% | 17/17 | 0 |
| Moose Knuckles | 94.4% | 17/17 | 0 |
| <respectable team name> | 97.2% | 17/17 | 0 |
| Serious Gourmet Shit | 100.0% | 17/17 | 0 |

## Identity / provenance

- FantasyPros IDs mapped to Sleeper IDs: **962**
- Manual-review identity rows skipped: **0**

The artifact is deterministic: its input file SHA-256 hashes are stored in the JSON, and no wall-clock timestamp is embedded.


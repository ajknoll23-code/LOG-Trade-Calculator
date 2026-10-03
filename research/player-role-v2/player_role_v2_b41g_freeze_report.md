# Player Role V2 — B41G Pre-Holdout Freeze

- Result: **PASS_2025_HOLDOUT_PROTOCOL_AND_BASELINE_FROZEN**
- 2025 holdout opened: **No**
- B41C3 pass required before 2025 may be read: **Yes**
- B41F model changed: **No**
- B41E thresholds changed: **No**
- Production deployed: **No**

## Frozen best-single-signal baseline

| Position | Selected signal | Development LOSO MAE |
|---|---|---:|
| QB | `league_points__season_to_date_active_mean` | 0.177016 |
| RB | `league_points__season_to_date_active_mean` | 0.135733 |
| WR | `league_points__season_to_date_active_mean` | 0.153376 |
| TE | `target_share__season_to_date_active_mean` | 0.148813 |
| K | `league_points__season_to_date_active_mean` | 0.311635 |
| DL | `snap_share__season_to_date_active_mean` | 0.184878 |
| LB | `snap_share__last3_active_mean` | 0.131963 |
| DB | `snap_share__last3_active_mean` | 0.170779 |

No 2025 data were used to choose any baseline feature or pass criterion.

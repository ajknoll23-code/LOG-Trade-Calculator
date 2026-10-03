# Player Role V2 — B41D Development Model Selection

- Development seasons: **2019–2024 only**
- 2026 Week 4 opened: **No**
- 2025 holdout opened: **No**
- Historical projection features: **Excluded**
- Owner/team identity used: **No**
- Role tier thresholds derived: **No**
- Production change authorized: **No**

## Position model selection

| Position | Selected family | OOF MAE | OOF Spearman |
|---|---|---:|---:|
| QB | nonnegative_ridge_linear | 0.1721 | 0.6847 |
| RB | nonnegative_ridge_linear | 0.1296 | 0.8202 |
| WR | nonnegative_ridge_linear | 0.1455 | 0.7788 |
| TE | nonnegative_ridge_linear | 0.1406 | 0.7846 |
| K | nonnegative_ridge_linear | 0.2550 | 0.1347 |
| DL | nonnegative_ridge_linear | 0.1725 | 0.6791 |
| LB | nonnegative_ridge_linear | 0.1280 | 0.8205 |
| DB | nonnegative_ridge_linear | 0.1592 | 0.7212 |

B41C3 remains mandatory before production deployment.
The untouched 2025 Role V2 holdout remains mandatory before production deployment.

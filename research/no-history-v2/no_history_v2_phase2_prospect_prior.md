# No-History / Rookie Value V2 — Phase 2 Historical Prospect Prior

Method: `no-history-rookie-v2-phase2-prospect-prior-v1`  
Status: **`RESEARCH_ONLY_HISTORICAL_PROSPECT_PRIOR_SHADOW`**

## Guardrail

**Research only. No deployed player value, Production V2 coefficient, Market Value input, or `index.html` constant is changed.**

Formal variants preserve Phase-7 continuity for missing V2 candidates. Prior-only values for those players are diagnostics only.

## Historical calibration sample

- Draft cohorts: **2018–2024**
- Drafted tracked-position players: **1443**
- Primary outcome: **first two NFL seasons of custom-scored points per scheduled team game**
- Cross-validation: **leave one entire draft year out**

### Historical cohort by position

| Pos | N | Median pick | Median draft age | Median pts/team game | Median pts/stat row |
|---|---:|---:|---:|---:|---:|
| QB | 80 | 106.0 | 23.00 | 1.28 | 7.05 |
| RB | 149 | 134.0 | 22.19 | 2.96 | 5.51 |
| WR | 224 | 125.5 | 22.33 | 2.59 | 3.95 |
| TE | 101 | 121.0 | 22.62 | 1.37 | 3.15 |
| DL | 264 | 121.5 | 22.70 | 1.68 | 3.38 |
| LB | 262 | 137.5 | 22.55 | 2.16 | 4.28 |
| DB | 363 | 137.0 | 22.52 | 3.02 | 5.29 |

## Historical cross-validation

| Model | N | MAE ↓ | RMSE ↓ | Spearman ↑ |
|---|---:|---:|---:|---:|
| `position_ols_log_pick` | 1443 | 2.105 | 2.876 | 0.630 |
| `position_ols_log_pick_plus_draft_age` | 1443 | 2.109 | 2.880 | 0.633 |

### Position-specific monitoring model

| Pos | Selected historical model | Pick-only MAE | Pick+age MAE |
|---|---|---:|---:|
| QB | `position_ols_log_pick` | 3.531 | 3.584 |
| RB | `position_ols_log_pick` | 2.928 | 2.941 |
| WR | `position_ols_log_pick_plus_draft_age` | 2.431 | 2.426 |
| TE | `position_ols_log_pick` | 1.457 | 1.460 |
| DL | `position_ols_log_pick` | 1.203 | 1.210 |
| LB | `position_ols_log_pick` | 1.949 | 1.957 |
| DB | `position_ols_log_pick_plus_draft_age` | 2.202 | 2.191 |

The selected position model is a **research monitoring choice only**. It is not a deployed coefficient.

## 2026 prospect-prior coverage

- Phase-1 eligible players: **95**
- Historical prior available: **88**
- Prior + normal V2 candidate: **83**
- Missing historical prior: **7**

## Formal shadow blend sensitivity

Formal variants only apply the prior when a normal Production V2 candidate already exists. Missing-candidate players remain on the accepted continuity fallback.

| Prior weight | Prior applied | Median abs Δ vs Phase 8 | P90 abs Δ vs Phase 8 |
|---:|---:|---:|---:|
| 0.00 | 0 | 0.0% | 0.0% |
| 0.15 | 83 | 4.6% | 8.6% |
| 0.30 | 83 | 9.1% | 17.2% |
| 0.45 | 83 | 13.7% | 25.5% |

### 30% prior-weight diagnostic movers

This is a middle sensitivity setting for inspection, **not a recommended production weight**.

| Player | Pos | Pick | Phase 8 | Shadow | Change | V2 PM | Prior PM |
|---|---|---:|---:|---:|---:|---:|---:|
| ty simpson | QB | 13 | 783 | 1187 | +51.6% | 0.150 | 0.394 |
| jeremiyah love | RB | 3 | 2377 | 3390 | +42.6% | 0.653 | 1.361 |
| fernando mendoza | QB | 1 | 2112 | 2785 | +31.9% | 0.418 | 0.793 |
| carnell tate | WR | 4 | 2131 | 2668 | +25.2% | 0.571 | 0.937 |
| jordyn tyson | WR | 8 | 1855 | 2307 | +24.4% | 0.444 | 0.758 |
| r mason thomas | DL | 40 | 1479 | 1188 | -19.7% | 0.450 | 0.200 |
| derrick moore | DL | 44 | 2235 | 1799 | -19.5% | 0.494 | 0.187 |
| kyle louis | LB | 138 | 1683 | 1360 | -19.2% | 0.367 | 0.150 |
| zion young | DL | 45 | 1483 | 1228 | -17.2% | 0.387 | 0.184 |
| kevin coleman | WR | 177 | 1289 | 1069 | -17.1% | 0.319 | 0.150 |
| kaleb elarmsorr | LB | 126 | 1370 | 1147 | -16.3% | 0.304 | 0.150 |
| justin joly | TE | 152 | 916 | 771 | -15.8% | 0.292 | 0.150 |
| aj haulcy | DB | 78 | 1911 | 1610 | -15.8% | 0.483 | 0.248 |
| bryce lance | WR | 136 | 1436 | 1213 | -15.5% | 0.302 | 0.150 |
| cj allen | LB | 53 | 1958 | 1655 | -15.5% | 0.486 | 0.277 |
| keldric faulk | DL | 31 | 1289 | 1101 | -14.6% | 0.402 | 0.235 |
| eli raridon | TE | 95 | 830 | 712 | -14.2% | 0.267 | 0.150 |
| peter woods | DL | 29 | 1303 | 1121 | -14.0% | 0.405 | 0.244 |
| chris bell | WR | 94 | 1561 | 1346 | -13.8% | 0.380 | 0.220 |
| rueben bain | DL | 15 | 1834 | 1582 | -13.7% | 0.536 | 0.335 |
| treydan stukes | DB | 38 | 2472 | 2140 | -13.4% | 0.517 | 0.286 |
| jaishawn barham | LB | 92 | 1258 | 1091 | -13.3% | 0.281 | 0.165 |
| cyrus allen | WR | 176 | 1234 | 1073 | -13.0% | 0.260 | 0.150 |
| jacob rodriguez | LB | 43 | 2964 | 2580 | -13.0% | 0.541 | 0.319 |
| elijah sarratt | WR | 115 | 1222 | 1064 | -12.9% | 0.258 | 0.150 |

## Missing-V2 prior-only diagnostics

These values are **diagnostic only**. The formal shadow variants do not use them and preserve current-value continuity.

| Player | Pos | Pick | Current | Prior-only diagnostic | Change |
|---|---|---:|---:|---:|---:|
| chris johnson | DB | 27 | 1384 | 1353 | -2.2% |
| erick hunter | LB | — | 1162 | — | — |
| harold perkins jr | LB | 215 | 774 | 508 | -34.4% |
| cam miller | QB | 215 | 1438 | 976 | -32.1% |
| garrett nussmeier | QB | 249 | 1303 | 879 | -32.5% |
| haynes king | QB | — | 1438 | — | — |
| taylen green | QB | 182 | 1169 | 783 | -33.0% |
| donovan edwards | RB | — | 1077 | — | — |
| leveon moss | RB | — | 1077 | — | — |

## Interpretation

Phase 2 answers whether **draft capital and draft age contain historical out-of-sample signal under this league's scoring**, and what happens when that prior is blended modestly with Production V2 for current rookies.

It does **not** choose a production blend weight. Phase 3 should freeze the candidate family and grade the variants prospectively against future 2026 outcomes. Current Fundamental Value or KTC agreement must not be used to select the winner.

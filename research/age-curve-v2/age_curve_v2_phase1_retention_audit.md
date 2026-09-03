# Age Curve V2 — Phase 1 Historical Retention Audit

Method: `age-curve-v2-phase1-retention-v1`  
Status: **`RESEARCH_ONLY_HISTORICAL_AGE_RETENTION_AUDIT`**

## Guardrail

**Research only. No deployed age multiplier or player value is changed.**

This phase measures historical retention only. It does not fit or select replacement AGE_CURVE coefficients.

## Historical evidence

- Weekly stat seasons: **2015–2025**
- Base seasons with full Year +1 and +2 targets: **2015–2023**
- Player-season retention rows: **14102**

Primary retention target treats a missing future season as **zero**. That makes the curve dynasty-relevant: decline, lost role, retirement, and league exit all count.

## Current deployed age policy vs descriptive historical landmarks

| Pos | Current peak | Current floor age | Best observed Y+1 retention age | First material retention cliff |
|---|---:|---:|---:|---:|
| QB | 26–33 | 35 | 30 | 36 |
| RB | 23–25 | 30 | 22 | 27 |
| WR | 24–28 | 33 | 21 | 27 |
| TE | 25–29 | 34 | 21 | 29 |
| DL | 24–29 | 34 | 22 | 30 |
| LB | 24–29 | 32 | 21 | 28 |
| DB | 23–27 | 32 | 21 | 29 |

These landmarks are descriptive only; they are **not replacement coefficients**.

## Position-age Year +1 retention

### QB

| Age | N | Aggregate Y+1 retention | Aggregate Y+2 retention | Y+1 any-stat survival | Y+1 >= 50% current |
|---:|---:|---:|---:|---:|---:|
| 22 | 34 | 104.4% | 94.1% | 82.4% | 79.4% |
| 23 | 62 | 99.0% | 80.6% | 77.4% | 66.1% |
| 24 | 71 | 78.4% | 65.0% | 70.4% | 53.5% |
| 25 | 62 | 77.7% | 76.2% | 77.4% | 56.5% |
| 26 | 62 | 95.1% | 92.4% | 79.0% | 59.7% |
| 27 | 65 | 103.9% | 77.8% | 72.3% | 53.8% |
| 28 | 53 | 68.1% | 57.3% | 75.5% | 49.1% |
| 29 | 39 | 80.3% | 76.3% | 74.4% | 48.7% |
| 30 | 30 | 110.0% | 97.4% | 83.3% | 60.0% |
| 31 | 29 | 80.1% | 70.4% | 79.3% | 58.6% |
| 32 | 31 | 79.8% | 61.9% | 80.6% | 58.1% |
| 33 | 28 | 84.7% | 69.6% | 78.6% | 53.6% |
| 34 | 26 | 78.9% | 78.9% | 76.9% | 53.8% |
| 35 | 25 | 90.9% | 64.8% | 68.0% | 48.0% |
| 36 | 17 | 65.7% | 57.1% | 70.6% | 52.9% |

### RB

| Age | N | Aggregate Y+1 retention | Aggregate Y+2 retention | Y+1 any-stat survival | Y+1 >= 50% current |
|---:|---:|---:|---:|---:|---:|
| 21 | 55 | 94.4% | 98.1% | 94.5% | 69.1% |
| 22 | 171 | 111.8% | 100.3% | 75.4% | 65.5% |
| 23 | 236 | 93.0% | 80.5% | 80.5% | 59.7% |
| 24 | 262 | 86.7% | 74.9% | 74.8% | 54.2% |
| 25 | 206 | 82.4% | 65.3% | 74.8% | 56.8% |
| 26 | 164 | 77.5% | 47.7% | 76.8% | 55.5% |
| 27 | 134 | 67.5% | 49.2% | 69.4% | 47.0% |
| 28 | 96 | 68.1% | 37.3% | 69.8% | 40.6% |
| 29 | 72 | 57.9% | 44.1% | 61.1% | 37.5% |
| 30 | 48 | 55.4% | 20.6% | 60.4% | 45.8% |
| 31 | 30 | 36.7% | 23.7% | 50.0% | 23.3% |
| 32 | 18 | 78.1% | 35.0% | 61.1% | 50.0% |

### WR

| Age | N | Aggregate Y+1 retention | Aggregate Y+2 retention | Y+1 any-stat survival | Y+1 >= 50% current |
|---:|---:|---:|---:|---:|---:|
| 21 | 74 | 114.9% | 130.6% | 86.5% | 75.7% |
| 22 | 218 | 114.3% | 91.4% | 85.3% | 71.1% |
| 23 | 330 | 84.0% | 85.7% | 73.3% | 55.2% |
| 24 | 308 | 98.0% | 84.4% | 71.1% | 60.4% |
| 25 | 278 | 83.0% | 71.0% | 73.7% | 56.1% |
| 26 | 226 | 89.2% | 65.2% | 75.7% | 64.2% |
| 27 | 185 | 70.5% | 47.9% | 73.5% | 51.4% |
| 28 | 135 | 70.2% | 48.9% | 68.1% | 45.2% |
| 29 | 98 | 70.7% | 43.9% | 66.3% | 54.1% |
| 30 | 68 | 60.0% | 44.5% | 67.6% | 47.1% |
| 31 | 41 | 55.0% | 32.8% | 68.3% | 51.2% |
| 32 | 34 | 57.6% | 31.8% | 58.8% | 47.1% |
| 33 | 23 | 46.8% | 15.9% | 52.2% | 30.4% |

### TE

| Age | N | Aggregate Y+1 retention | Aggregate Y+2 retention | Y+1 any-stat survival | Y+1 >= 50% current |
|---:|---:|---:|---:|---:|---:|
| 21 | 17 | 121.4% | 97.8% | 88.2% | 76.5% |
| 22 | 74 | 97.3% | 118.3% | 86.5% | 60.8% |
| 23 | 154 | 120.2% | 113.5% | 81.8% | 70.1% |
| 24 | 171 | 93.5% | 76.1% | 74.9% | 62.6% |
| 25 | 157 | 86.8% | 72.8% | 73.9% | 55.4% |
| 26 | 134 | 79.7% | 77.7% | 70.9% | 51.5% |
| 27 | 109 | 96.7% | 78.0% | 73.4% | 54.1% |
| 28 | 91 | 84.4% | 62.4% | 78.0% | 62.6% |
| 29 | 70 | 66.9% | 46.4% | 71.4% | 40.0% |
| 30 | 53 | 60.1% | 47.2% | 62.3% | 43.4% |
| 31 | 38 | 73.0% | 60.1% | 63.2% | 50.0% |
| 32 | 23 | 76.1% | 42.2% | 56.5% | 52.2% |

### DL

| Age | N | Aggregate Y+1 retention | Aggregate Y+2 retention | Y+1 any-stat survival | Y+1 >= 50% current |
|---:|---:|---:|---:|---:|---:|
| 21 | 54 | 107.3% | 121.8% | 94.4% | 83.3% |
| 22 | 202 | 113.2% | 123.6% | 83.2% | 71.8% |
| 23 | 346 | 105.7% | 104.3% | 80.1% | 66.8% |
| 24 | 375 | 99.7% | 89.0% | 77.6% | 63.5% |
| 25 | 349 | 84.1% | 76.1% | 82.5% | 65.6% |
| 26 | 314 | 85.7% | 73.0% | 75.5% | 58.3% |
| 27 | 264 | 80.1% | 73.1% | 78.0% | 59.5% |
| 28 | 218 | 89.2% | 69.9% | 78.9% | 60.6% |
| 29 | 171 | 76.6% | 56.3% | 79.5% | 64.9% |
| 30 | 128 | 74.8% | 46.0% | 76.6% | 60.2% |
| 31 | 92 | 57.1% | 40.7% | 63.0% | 42.4% |
| 32 | 60 | 73.3% | 38.0% | 61.7% | 46.7% |
| 33 | 39 | 43.8% | 24.8% | 64.1% | 41.0% |
| 34 | 29 | 52.9% | 27.5% | 44.8% | 31.0% |
| 35 | 15 | 49.4% | 42.5% | 46.7% | 40.0% |

### LB

| Age | N | Aggregate Y+1 retention | Aggregate Y+2 retention | Y+1 any-stat survival | Y+1 >= 50% current |
|---:|---:|---:|---:|---:|---:|
| 21 | 50 | 121.7% | 115.8% | 96.0% | 82.0% |
| 22 | 226 | 112.6% | 105.1% | 87.6% | 71.7% |
| 23 | 393 | 102.2% | 104.5% | 82.2% | 63.6% |
| 24 | 416 | 100.1% | 96.7% | 81.7% | 63.9% |
| 25 | 368 | 95.2% | 82.0% | 76.1% | 58.2% |
| 26 | 300 | 81.1% | 69.7% | 79.0% | 57.0% |
| 27 | 243 | 84.2% | 65.1% | 74.9% | 57.6% |
| 28 | 188 | 69.9% | 48.2% | 78.7% | 51.6% |
| 29 | 148 | 70.4% | 45.4% | 67.6% | 50.0% |
| 30 | 101 | 55.9% | 37.1% | 60.4% | 36.6% |
| 31 | 64 | 60.5% | 37.7% | 56.2% | 37.5% |
| 32 | 38 | 68.4% | 38.2% | 65.8% | 47.4% |
| 33 | 28 | 62.9% | 52.0% | 64.3% | 39.3% |
| 34 | 18 | 75.3% | 57.1% | 66.7% | 55.6% |

### DB

| Age | N | Aggregate Y+1 retention | Aggregate Y+2 retention | Y+1 any-stat survival | Y+1 >= 50% current |
|---:|---:|---:|---:|---:|---:|
| 21 | 111 | 118.7% | 111.7% | 93.7% | 83.8% |
| 22 | 317 | 105.8% | 96.0% | 83.6% | 68.8% |
| 23 | 531 | 94.9% | 89.5% | 78.2% | 61.0% |
| 24 | 520 | 95.0% | 88.3% | 77.5% | 62.5% |
| 25 | 459 | 88.9% | 74.5% | 79.1% | 59.3% |
| 26 | 398 | 85.7% | 68.1% | 77.1% | 59.8% |
| 27 | 323 | 75.3% | 60.0% | 75.9% | 54.2% |
| 28 | 247 | 78.2% | 56.3% | 79.8% | 60.7% |
| 29 | 198 | 71.7% | 40.4% | 70.7% | 52.0% |
| 30 | 152 | 55.8% | 33.6% | 59.2% | 44.7% |
| 31 | 92 | 57.5% | 33.1% | 64.1% | 38.0% |
| 32 | 63 | 59.1% | 31.5% | 58.7% | 44.4% |
| 33 | 33 | 53.5% | 32.6% | 54.5% | 39.4% |
| 34 | 17 | 60.8% | 30.1% | 52.9% | 52.9% |

## Tier-sensitive retention

The same age can behave differently for an elite player and a depth player. The table below summarizes all ages within each current production tier before Phase 2 fits any age interaction.

| Pos | Tier | N | Y+1 retention | Y+2 retention | Y+1 any-stat survival |
|---|---|---:|---:|---:|---:|
| QB | elite | 69 | 77.3% | 70.4% | 95.7% |
| QB | starter | 194 | 88.3% | 74.0% | 95.9% |
| QB | rotation | 197 | 93.3% | 74.2% | 73.6% |
| QB | depth | 201 | 420.4% | 338.1% | 54.2% |
| RB | elite | 156 | 76.5% | 63.3% | 97.4% |
| RB | starter | 451 | 78.3% | 61.3% | 90.7% |
| RB | rotation | 453 | 91.3% | 68.7% | 72.0% |
| RB | depth | 456 | 220.3% | 193.2% | 50.7% |
| WR | elite | 208 | 80.0% | 73.0% | 98.6% |
| WR | starter | 612 | 79.3% | 61.0% | 91.5% |
| WR | rotation | 611 | 88.5% | 65.9% | 73.3% |
| WR | depth | 617 | 203.7% | 171.2% | 46.7% |
| TE | elite | 117 | 72.3% | 64.2% | 95.7% |
| TE | starter | 337 | 85.5% | 70.7% | 90.2% |
| TE | rotation | 334 | 99.7% | 77.3% | 73.7% |
| TE | depth | 342 | 193.7% | 208.5% | 52.3% |
| DL | elite | 271 | 73.3% | 70.0% | 95.9% |
| DL | starter | 801 | 83.9% | 68.6% | 91.9% |
| DL | rotation | 796 | 96.4% | 82.3% | 81.0% |
| DL | depth | 798 | 167.3% | 156.8% | 53.9% |
| LB | elite | 264 | 75.9% | 62.8% | 97.0% |
| LB | starter | 777 | 79.7% | 67.8% | 91.9% |
| LB | rotation | 781 | 113.9% | 101.0% | 78.6% |
| LB | depth | 778 | 196.4% | 187.0% | 55.9% |
| DB | elite | 351 | 71.0% | 59.3% | 97.7% |
| DB | starter | 1044 | 79.3% | 63.6% | 91.8% |
| DB | rotation | 1052 | 95.2% | 79.4% | 75.9% |
| DB | depth | 1034 | 207.8% | 186.2% | 54.6% |

## Next step

If historical retention cohorts are sufficiently populated, fit candidate age-value curves to future Year+1/Year+2 retention and compare them against the deployed age policy out of sample.

Phase 2 should test candidate curves out of sample by historical season rather than choosing ages because they visually fit this report.

# Trade Desk Value Uncertainty — Sensitivity Envelope V1

Method: `sensitivity-envelope-v1`  
Policy SHA256: `bafc53164f6d98448965c5d0b531b14be31a3d744f0e4a44d6cdac71b6c05247`

## Critical interpretation

**These ranges are not probability confidence intervals.** They are deterministic sensitivity envelopes around the deployed point value using currently observable projection disagreement, historical sampling noise, and availability-history signal.

- Players: **565**
- Width quartiles: Q25 **19.0%**, median **24.8%**, Q75 **32.6%**
- Provider coverage (0/1/2): **{'0': 47, '1': 88, '2': 430}**
- History coverage: **{'insufficient': 126, 'with_2plus_games': 439}**

## Position summary

| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |
|---|---:|---:|---:|---:|---:|
| QB | 64 | 39.7% | 4.7% | 17.2% | 28.9% |
| RB | 97 | 24.1% | 7.3% | 18.5% | 4.3% |
| WR | 114 | 26.3% | 9.7% | 22.5% | 6.9% |
| TE | 44 | 24.0% | 5.3% | 19.2% | 7.1% |
| DL | 86 | 25.2% | 10.7% | 21.0% | 5.2% |
| LB | 79 | 22.1% | 14.8% | 14.7% | 1.7% |
| DB | 65 | 20.7% | 14.3% | 14.4% | 1.9% |
| K | 16 | 30.8% | 20.2% | 20.9% | 10.4% |

## Widest current envelopes

| Player | Pos | Center | Low | High | Half-width | Tier |
|---|---|---:|---:|---:|---:|---|
| jameis winston | QB | 1086 | 0 | 2172 | 100.0% | very_high |
| tyrel dodson | LB | 4295 | 0 | 8590 | 100.0% | very_high |
| zion young | DL | 1013 | 20 | 2006 | 98.0% | very_high |
| malik nabers | WR | 4083 | 177 | 7989 | 95.7% | very_high |
| jack endries | TE | 673 | 55 | 1291 | 91.8% | very_high |
| dezhaun stribling | WR | 2190 | 192 | 4188 | 91.2% | very_high |
| dylan sampson | RB | 1530 | 149 | 2911 | 90.3% | very_high |
| adam randall | RB | 895 | 103 | 1687 | 88.5% | very_high |
| will johnson | DB | 2524 | 305 | 4743 | 87.9% | very_high |
| jake tonges | TE | 1108 | 199 | 2017 | 82.0% | very_high |
| nick bosa | DL | 4020 | 724 | 7316 | 82.0% | very_high |
| jordan james | RB | 776 | 146 | 1406 | 81.2% | very_high |
| brashard smith | RB | 739 | 143 | 1335 | 80.7% | very_high |
| jaxson dart | QB | 4351 | 846 | 7856 | 80.6% | very_high |
| bryce boettcher | LB | 1355 | 290 | 2420 | 78.6% | very_high |
| eli heidenreich | RB | 1077 | 242 | 1912 | 77.5% | very_high |
| jalen mcmillan | WR | 2452 | 610 | 4294 | 75.1% | very_high |
| jalyx hunt | DL | 3638 | 923 | 6353 | 74.6% | very_high |
| devon achane | RB | 6505 | 1701 | 11309 | 73.9% | very_high |
| skyler bell | WR | 1210 | 325 | 2095 | 73.2% | very_high |

## V1 guardrails

- The center value is unchanged from the deployed calculator.
- KTC/internal market ratings are not used as fundamental uncertainty truth.
- Injury status is not converted into an unvalidated point-value penalty.
- Missing-source imputation comes from observed position-cohort dispersion.
- The envelope will only receive a probability label after out-of-sample calibration supports one.

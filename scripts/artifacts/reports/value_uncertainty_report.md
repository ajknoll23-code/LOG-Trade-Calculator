# Trade Desk Value Uncertainty — Sensitivity Envelope V1

Method: `sensitivity-envelope-v1`  
Policy SHA256: `bafc53164f6d98448965c5d0b531b14be31a3d744f0e4a44d6cdac71b6c05247`

## Critical interpretation

**These ranges are not probability confidence intervals.** They are deterministic sensitivity envelopes around the deployed point value using currently observable projection disagreement, historical sampling noise, and availability-history signal.

- Players: **565**
- Width quartiles: Q25 **19.0%**, median **24.7%**, Q75 **31.4%**
- Provider coverage (0/1/2): **{'0': 47, '1': 87, '2': 431}**
- History coverage: **{'insufficient': 126, 'with_2plus_games': 439}**

## Position summary

| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |
|---|---:|---:|---:|---:|---:|
| QB | 64 | 35.5% | 3.3% | 17.2% | 28.9% |
| RB | 97 | 24.0% | 6.7% | 18.5% | 4.3% |
| WR | 114 | 25.9% | 8.5% | 22.5% | 6.9% |
| TE | 44 | 24.6% | 6.4% | 19.2% | 7.1% |
| DL | 86 | 25.2% | 10.2% | 21.0% | 5.2% |
| LB | 79 | 22.2% | 15.8% | 14.7% | 1.7% |
| DB | 65 | 19.6% | 11.9% | 14.4% | 1.9% |
| K | 16 | 29.7% | 18.4% | 20.9% | 10.4% |

## Widest current envelopes

| Player | Pos | Center | Low | High | Half-width | Tier |
|---|---|---:|---:|---:|---:|---|
| tyrel dodson | LB | 4295 | 0 | 8590 | 100.0% | very_high |
| zion young | DL | 1013 | 20 | 2006 | 98.0% | very_high |
| keandre lambertsmith | WR | 825 | 35 | 1615 | 95.7% | very_high |
| malik nabers | WR | 4083 | 175 | 7991 | 95.7% | very_high |
| cedric gray | LB | 4509 | 235 | 8783 | 94.8% | very_high |
| dezhaun stribling | WR | 2190 | 190 | 4190 | 91.3% | very_high |
| malik benson | WR | 1037 | 100 | 1974 | 90.4% | very_high |
| dylan sampson | RB | 1523 | 148 | 2898 | 90.3% | very_high |
| adam randall | RB | 890 | 103 | 1677 | 88.5% | very_high |
| jameis winston | QB | 1086 | 133 | 2039 | 87.8% | very_high |
| jake tonges | TE | 1108 | 199 | 2017 | 82.0% | very_high |
| nick bosa | DL | 4020 | 730 | 7310 | 81.8% | very_high |
| jordan james | RB | 772 | 147 | 1397 | 81.0% | very_high |
| bryce boettcher | LB | 1355 | 300 | 2410 | 77.9% | very_high |
| jalyx hunt | DL | 3638 | 923 | 6353 | 74.6% | very_high |
| eli heidenreich | RB | 1077 | 276 | 1878 | 74.4% | very_high |
| sirvocea dennis | LB | 3521 | 954 | 6088 | 72.9% | very_high |
| derick hall | DL | 2021 | 564 | 3478 | 72.1% | very_high |
| skyler bell | WR | 1210 | 360 | 2060 | 70.2% | very_high |
| sean tucker | RB | 1345 | 406 | 2284 | 69.8% | very_high |

## V1 guardrails

- The center value is unchanged from the deployed calculator.
- KTC/internal market ratings are not used as fundamental uncertainty truth.
- Injury status is not converted into an unvalidated point-value penalty.
- Missing-source imputation comes from observed position-cohort dispersion.
- The envelope will only receive a probability label after out-of-sample calibration supports one.

# Trade Desk Value Uncertainty — Sensitivity Envelope V1

Method: `sensitivity-envelope-v1`  
Policy SHA256: `bafc53164f6d98448965c5d0b531b14be31a3d744f0e4a44d6cdac71b6c05247`

## Critical interpretation

**These ranges are not probability confidence intervals.** They are deterministic sensitivity envelopes around the deployed point value using currently observable projection disagreement, historical sampling noise, and availability-history signal.

- Players: **565**
- Width quartiles: Q25 **19.5%**, median **25.0%**, Q75 **33.8%**
- Provider coverage (0/1/2): **{'0': 45, '1': 89, '2': 431}**
- History coverage: **{'insufficient': 126, 'with_2plus_games': 439}**

## Position summary

| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |
|---|---:|---:|---:|---:|---:|
| QB | 64 | 38.5% | 4.8% | 17.2% | 28.9% |
| RB | 97 | 25.3% | 9.3% | 18.5% | 4.3% |
| WR | 114 | 26.6% | 10.6% | 22.5% | 6.9% |
| TE | 44 | 24.4% | 8.8% | 19.2% | 7.1% |
| DL | 86 | 25.2% | 10.6% | 21.0% | 5.2% |
| LB | 79 | 21.9% | 14.6% | 14.7% | 1.7% |
| DB | 65 | 20.9% | 14.6% | 14.4% | 1.9% |
| K | 16 | 31.2% | 20.7% | 20.9% | 10.4% |

## Widest current envelopes

| Player | Pos | Center | Low | High | Half-width | Tier |
|---|---|---:|---:|---:|---:|---|
| jameis winston | QB | 1086 | 0 | 2172 | 100.0% | very_high |
| tyrel dodson | LB | 4295 | 0 | 8590 | 100.0% | very_high |
| malik nabers | WR | 4083 | 173 | 7993 | 95.8% | very_high |
| jack endries | TE | 673 | 50 | 1296 | 92.5% | very_high |
| dj giddens | RB | 737 | 56 | 1418 | 92.4% | very_high |
| dezhaun stribling | WR | 2190 | 192 | 4188 | 91.2% | very_high |
| dylan sampson | RB | 1544 | 150 | 2938 | 90.3% | very_high |
| adam randall | RB | 904 | 93 | 1715 | 89.7% | very_high |
| will johnson | DB | 2524 | 305 | 4743 | 87.9% | very_high |
| jordan james | RB | 783 | 134 | 1432 | 82.9% | very_high |
| nick bosa | DL | 4020 | 714 | 7326 | 82.2% | very_high |
| jake tonges | TE | 1108 | 199 | 2017 | 82.0% | very_high |
| jayden reed | WR | 3326 | 607 | 6045 | 81.7% | very_high |
| jaxson dart | QB | 4351 | 846 | 7856 | 80.6% | very_high |
| max klare | TE | 780 | 152 | 1408 | 80.5% | very_high |
| brashard smith | RB | 739 | 145 | 1333 | 80.4% | very_high |
| eli heidenreich | RB | 1077 | 218 | 1936 | 79.7% | very_high |
| sirvocea dennis | LB | 3521 | 890 | 6152 | 74.7% | very_high |
| devon achane | RB | 6425 | 1680 | 11170 | 73.9% | very_high |
| jalen mcmillan | WR | 2452 | 666 | 4238 | 72.8% | very_high |

## V1 guardrails

- The center value is unchanged from the deployed calculator.
- KTC/internal market ratings are not used as fundamental uncertainty truth.
- Injury status is not converted into an unvalidated point-value penalty.
- Missing-source imputation comes from observed position-cohort dispersion.
- The envelope will only receive a probability label after out-of-sample calibration supports one.

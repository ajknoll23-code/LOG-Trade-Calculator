# Trade Desk Value Uncertainty — Sensitivity Envelope V1

Method: `sensitivity-envelope-v1`  
Policy SHA256: `bafc53164f6d98448965c5d0b531b14be31a3d744f0e4a44d6cdac71b6c05247`

## Critical interpretation

**These ranges are not probability confidence intervals.** They are deterministic sensitivity envelopes around the deployed point value using currently observable projection disagreement, historical sampling noise, and availability-history signal.

- Players: **565**
- Width quartiles: Q25 **20.4%**, median **27.8%**, Q75 **38.7%**
- Provider coverage (0/1/2): **{'0': 41, '1': 41, '2': 483}**
- History coverage: **{'insufficient': 126, 'with_2plus_games': 439}**

## Position summary

| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |
|---|---:|---:|---:|---:|---:|
| QB | 64 | 44.5% | 11.1% | 17.2% | 28.9% |
| RB | 97 | 27.9% | 14.8% | 18.5% | 4.3% |
| WR | 114 | 28.7% | 15.4% | 22.5% | 6.9% |
| TE | 44 | 24.6% | 7.6% | 19.2% | 7.1% |
| DL | 87 | 26.5% | 11.6% | 20.9% | 5.2% |
| LB | 78 | 23.8% | 17.9% | 14.6% | 2.6% |
| DB | 65 | 24.0% | 16.7% | 14.4% | 1.9% |
| K | 16 | 36.6% | 28.2% | 20.9% | 10.4% |

## Widest current envelopes

| Player | Pos | Center | Low | High | Half-width | Tier |
|---|---|---:|---:|---:|---:|---|
| jameis winston | QB | 1086 | 0 | 2172 | 100.0% | very_high |
| tyrel dodson | LB | 4295 | 0 | 8590 | 100.0% | very_high |
| anthony richardson | QB | 879 | 16 | 1742 | 98.2% | very_high |
| malik nabers | WR | 4083 | 159 | 8007 | 96.1% | very_high |
| adam randall | RB | 932 | 38 | 1826 | 96.0% | very_high |
| jj mccarthy | QB | 813 | 53 | 1573 | 93.5% | very_high |
| eli heidenreich | RB | 1077 | 75 | 2079 | 93.0% | very_high |
| deshon elliott | DB | 2750 | 204 | 5296 | 92.6% | very_high |
| dezhaun stribling | WR | 2190 | 178 | 4202 | 91.9% | very_high |
| brashard smith | RB | 739 | 70 | 1408 | 90.6% | very_high |
| will johnson | DB | 2222 | 268 | 4176 | 87.9% | very_high |
| jordan james | RB | 807 | 105 | 1509 | 87.0% | very_high |
| nick bosa | DL | 3823 | 544 | 7102 | 85.8% | very_high |
| alec pierce | WR | 4405 | 689 | 8121 | 84.4% | very_high |
| shedeur sanders | QB | 1633 | 294 | 2972 | 82.0% | very_high |
| jake tonges | TE | 1108 | 199 | 2017 | 82.0% | very_high |
| jayden reed | WR | 3326 | 607 | 6045 | 81.7% | very_high |
| jalen mcmillan | WR | 2452 | 462 | 4442 | 81.2% | very_high |
| jaxson dart | QB | 5091 | 990 | 9192 | 80.6% | very_high |
| tommy devito | QB | 1573 | 323 | 2823 | 79.4% | very_high |

## V1 guardrails

- The center value is unchanged from the deployed calculator.
- KTC/internal market ratings are not used as fundamental uncertainty truth.
- Injury status is not converted into an unvalidated point-value penalty.
- Missing-source imputation comes from observed position-cohort dispersion.
- The envelope will only receive a probability label after out-of-sample calibration supports one.

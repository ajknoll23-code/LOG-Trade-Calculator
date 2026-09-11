# Trade Desk Value Uncertainty — Sensitivity Envelope V1

Method: `sensitivity-envelope-v1`  
Policy SHA256: `bafc53164f6d98448965c5d0b531b14be31a3d744f0e4a44d6cdac71b6c05247`

## Critical interpretation

**These ranges are not probability confidence intervals.** They are deterministic sensitivity envelopes around the deployed point value using currently observable projection disagreement, historical sampling noise, and availability-history signal.

- Players: **565**
- Width quartiles: Q25 **18.7%**, median **24.7%**, Q75 **30.9%**
- Provider coverage (0/1/2): **{'0': 52, '1': 97, '2': 416}**
- History coverage: **{'insufficient': 126, 'with_2plus_games': 439}**

## Position summary

| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |
|---|---:|---:|---:|---:|---:|
| QB | 64 | 37.5% | 2.5% | 17.2% | 28.9% |
| RB | 97 | 23.7% | 5.1% | 18.5% | 4.3% |
| WR | 114 | 25.7% | 5.2% | 22.5% | 6.9% |
| TE | 44 | 24.6% | 4.9% | 19.2% | 7.1% |
| DL | 86 | 25.0% | 9.2% | 21.0% | 5.2% |
| LB | 79 | 21.6% | 14.6% | 14.7% | 1.7% |
| DB | 65 | 19.7% | 12.8% | 14.4% | 1.9% |
| K | 16 | 28.4% | 16.2% | 20.9% | 10.4% |

## Widest current envelopes

| Player | Pos | Center | Low | High | Half-width | Tier |
|---|---|---:|---:|---:|---:|---|
| malik benson | WR | 1037 | 5 | 2069 | 99.5% | very_high |
| malik nabers | WR | 4088 | 173 | 8003 | 95.8% | very_high |
| eli heidenreich | RB | 1077 | 75 | 2079 | 93.0% | very_high |
| kaden elliss | LB | 2990 | 266 | 5714 | 91.1% | very_high |
| isiah pacheco | RB | 1554 | 144 | 2964 | 90.7% | very_high |
| devin white | LB | 3475 | 417 | 6533 | 88.0% | very_high |
| jameis winston | QB | 1073 | 180 | 1966 | 83.2% | very_high |
| nick bosa | DL | 3980 | 723 | 7237 | 81.8% | very_high |
| adam randall | RB | 883 | 210 | 1556 | 76.3% | very_high |
| malik willis | QB | 3711 | 1261 | 6161 | 66.0% | very_high |
| tank dell | WR | 2030 | 754 | 3306 | 62.8% | very_high |
| kyle williams | WR | 701 | 267 | 1135 | 61.8% | very_high |
| kaleb elarmsorr | LB | 968 | 392 | 1544 | 59.5% | very_high |
| nnamdi madubuike | DL | 2696 | 1166 | 4226 | 56.8% | very_high |
| ed oliver | DL | 3539 | 1543 | 5535 | 56.4% | very_high |
| jordan james | RB | 771 | 344 | 1198 | 55.4% | very_high |
| brashard smith | RB | 734 | 332 | 1136 | 54.8% | very_high |
| jack endries | TE | 673 | 306 | 1040 | 54.6% | very_high |
| riley leonard | QB | 783 | 357 | 1209 | 54.4% | very_high |
| anthony richardson | QB | 879 | 402 | 1356 | 54.3% | very_high |

## V1 guardrails

- The center value is unchanged from the deployed calculator.
- KTC/internal market ratings are not used as fundamental uncertainty truth.
- Injury status is not converted into an unvalidated point-value penalty.
- Missing-source imputation comes from observed position-cohort dispersion.
- The envelope will only receive a probability label after out-of-sample calibration supports one.

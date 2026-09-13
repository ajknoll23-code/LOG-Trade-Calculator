# Trade Desk Value Uncertainty — Sensitivity Envelope V1

Method: `sensitivity-envelope-v1`  
Policy SHA256: `bafc53164f6d98448965c5d0b531b14be31a3d744f0e4a44d6cdac71b6c05247`

## Critical interpretation

**These ranges are not probability confidence intervals.** They are deterministic sensitivity envelopes around the deployed point value using currently observable projection disagreement, historical sampling noise, and availability-history signal.

- Players: **565**
- Width quartiles: Q25 **18.8%**, median **24.6%**, Q75 **30.8%**
- Provider coverage (0/1/2): **{'0': 53, '1': 95, '2': 417}**
- History coverage: **{'insufficient': 126, 'with_2plus_games': 439}**

## Position summary

| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |
|---|---:|---:|---:|---:|---:|
| QB | 64 | 37.5% | 2.3% | 17.2% | 28.9% |
| RB | 97 | 23.9% | 5.1% | 18.5% | 4.3% |
| WR | 114 | 25.7% | 5.7% | 22.5% | 6.9% |
| TE | 44 | 24.6% | 6.1% | 19.2% | 7.1% |
| DL | 86 | 25.0% | 9.2% | 21.0% | 5.2% |
| LB | 79 | 21.7% | 15.1% | 14.7% | 1.7% |
| DB | 65 | 21.0% | 12.1% | 14.4% | 1.9% |
| K | 16 | 28.6% | 16.5% | 20.9% | 10.4% |

## Widest current envelopes

| Player | Pos | Center | Low | High | Half-width | Tier |
|---|---|---:|---:|---:|---:|---|
| jordan james | RB | 772 | 0 | 1544 | 100.0% | very_high |
| malik benson | WR | 1037 | 9 | 2065 | 99.2% | very_high |
| malik nabers | WR | 4088 | 174 | 8002 | 95.7% | very_high |
| kaden elliss | LB | 2990 | 266 | 5714 | 91.1% | very_high |
| isiah pacheco | RB | 1553 | 144 | 2962 | 90.7% | very_high |
| devin white | LB | 3475 | 417 | 6533 | 88.0% | very_high |
| adam randall | RB | 885 | 116 | 1654 | 86.9% | very_high |
| jameis winston | QB | 1073 | 180 | 1966 | 83.2% | very_high |
| nick bosa | DL | 3980 | 723 | 7237 | 81.8% | very_high |
| bryce boettcher | LB | 1355 | 299 | 2411 | 77.9% | very_high |
| malik willis | QB | 3711 | 1260 | 6162 | 66.0% | very_high |
| tank dell | WR | 2030 | 754 | 3306 | 62.8% | very_high |
| eli stowers | TE | 578 | 218 | 938 | 62.3% | very_high |
| nnamdi madubuike | DL | 2696 | 1121 | 4271 | 58.4% | very_high |
| kaleb elarmsorr | LB | 968 | 412 | 1524 | 57.4% | very_high |
| jack endries | TE | 673 | 289 | 1057 | 57.1% | very_high |
| ed oliver | DL | 3539 | 1542 | 5536 | 56.4% | very_high |
| brashard smith | RB | 734 | 332 | 1136 | 54.8% | very_high |
| eli heidenreich | RB | 1077 | 491 | 1663 | 54.4% | very_high |
| riley leonard | QB | 783 | 357 | 1209 | 54.4% | very_high |

## V1 guardrails

- The center value is unchanged from the deployed calculator.
- KTC/internal market ratings are not used as fundamental uncertainty truth.
- Injury status is not converted into an unvalidated point-value penalty.
- Missing-source imputation comes from observed position-cohort dispersion.
- The envelope will only receive a probability label after out-of-sample calibration supports one.

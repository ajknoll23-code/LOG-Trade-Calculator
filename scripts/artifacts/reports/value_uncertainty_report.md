# Trade Desk Value Uncertainty — Sensitivity Envelope V1

Method: `sensitivity-envelope-v1`  
Policy SHA256: `bafc53164f6d98448965c5d0b531b14be31a3d744f0e4a44d6cdac71b6c05247`

## Critical interpretation

**These ranges are not probability confidence intervals.** They are deterministic sensitivity envelopes around the deployed point value using currently observable projection disagreement, historical sampling noise, and availability-history signal.

- Players: **565**
- Width quartiles: Q25 **18.8%**, median **24.6%**, Q75 **31.3%**
- Provider coverage (0/1/2): **{'0': 46, '1': 103, '2': 416}**
- History coverage: **{'insufficient': 126, 'with_2plus_games': 439}**

## Position summary

| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |
|---|---:|---:|---:|---:|---:|
| QB | 64 | 37.6% | 2.6% | 17.2% | 28.9% |
| RB | 97 | 24.6% | 7.0% | 18.5% | 4.3% |
| WR | 114 | 25.6% | 7.0% | 22.5% | 6.9% |
| TE | 44 | 23.4% | 5.7% | 19.2% | 7.1% |
| DL | 86 | 24.9% | 9.5% | 21.0% | 5.2% |
| LB | 79 | 21.5% | 14.6% | 14.7% | 1.7% |
| DB | 65 | 19.8% | 12.9% | 14.4% | 1.9% |
| K | 16 | 28.8% | 16.8% | 20.9% | 10.4% |

## Widest current envelopes

| Player | Pos | Center | Low | High | Half-width | Tier |
|---|---|---:|---:|---:|---:|---|
| malik benson | WR | 1037 | 0 | 2074 | 100.0% | very_high |
| malik nabers | WR | 4088 | 171 | 8005 | 95.8% | very_high |
| kaden elliss | LB | 2990 | 266 | 5714 | 91.1% | very_high |
| devin white | LB | 3475 | 417 | 6533 | 88.0% | very_high |
| adam randall | RB | 878 | 146 | 1610 | 83.4% | very_high |
| jameis winston | QB | 1073 | 180 | 1966 | 83.2% | very_high |
| nick bosa | DL | 3980 | 723 | 7237 | 81.8% | very_high |
| kyle williams | WR | 701 | 181 | 1221 | 74.1% | very_high |
| brashard smith | RB | 734 | 247 | 1221 | 66.3% | very_high |
| malik willis | QB | 3711 | 1262 | 6160 | 66.0% | very_high |
| kaleb elarmsorr | LB | 968 | 392 | 1544 | 59.5% | very_high |
| nnamdi madubuike | DL | 2696 | 1163 | 4229 | 56.8% | very_high |
| ed oliver | DL | 3539 | 1542 | 5536 | 56.4% | very_high |
| bryce lance | WR | 1037 | 462 | 1612 | 55.4% | very_high |
| anthony richardson | QB | 879 | 401 | 1357 | 54.4% | very_high |
| riley leonard | QB | 783 | 357 | 1209 | 54.4% | very_high |
| tank dell | WR | 2030 | 932 | 3128 | 54.1% | very_high |
| jack endries | TE | 673 | 311 | 1035 | 53.8% | very_high |
| kimani vidal | RB | 1946 | 921 | 2971 | 52.7% | very_high |
| jordan james | RB | 767 | 374 | 1160 | 51.3% | very_high |

## V1 guardrails

- The center value is unchanged from the deployed calculator.
- KTC/internal market ratings are not used as fundamental uncertainty truth.
- Injury status is not converted into an unvalidated point-value penalty.
- Missing-source imputation comes from observed position-cohort dispersion.
- The envelope will only receive a probability label after out-of-sample calibration supports one.

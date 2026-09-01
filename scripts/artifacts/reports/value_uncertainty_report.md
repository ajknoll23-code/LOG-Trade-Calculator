# Trade Desk Value Uncertainty — Sensitivity Envelope V1

Method: `sensitivity-envelope-v1`  
Policy SHA256: `bafc53164f6d98448965c5d0b531b14be31a3d744f0e4a44d6cdac71b6c05247`

## Critical interpretation

**These ranges are not probability confidence intervals.** They are deterministic sensitivity envelopes around the deployed point value using currently observable projection disagreement, historical sampling noise, and availability-history signal.

- Players: **565**
- Width quartiles: Q25 **19.7%**, median **24.9%**, Q75 **29.5%**
- Provider coverage (0/1/2): **{'0': 70, '1': 322, '2': 173}**
- History coverage: **{'insufficient': 126, 'with_2plus_games': 439}**

## Position summary

| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |
|---|---:|---:|---:|---:|---:|
| QB | 64 | 38.5% | 11.7% | 17.2% | 28.9% |
| RB | 97 | 24.0% | 11.7% | 18.5% | 4.3% |
| WR | 114 | 26.2% | 11.7% | 22.5% | 6.9% |
| TE | 44 | 24.3% | 11.7% | 19.2% | 7.1% |
| DL | 86 | 24.9% | 9.5% | 21.0% | 5.2% |
| LB | 79 | 21.3% | 14.5% | 14.7% | 1.7% |
| DB | 65 | 19.8% | 12.9% | 14.4% | 1.9% |
| K | 16 | 29.5% | 18.1% | 20.9% | 10.4% |

## Widest current envelopes

| Player | Pos | Center | Low | High | Half-width | Tier |
|---|---|---:|---:|---:|---:|---|
| malik nabers | WR | 4088 | 149 | 8027 | 96.4% | very_high |
| jameis winston | QB | 1073 | 160 | 1986 | 85.1% | very_high |
| nick bosa | DL | 3980 | 723 | 7237 | 81.8% | very_high |
| malik willis | QB | 3711 | 1226 | 6196 | 67.0% | very_high |
| kaleb elarmsorr | LB | 968 | 392 | 1544 | 59.5% | very_high |
| riley leonard | QB | 783 | 335 | 1231 | 57.3% | very_high |
| anthony richardson | QB | 879 | 377 | 1381 | 57.2% | very_high |
| nnamdi madubuike | DL | 2696 | 1163 | 4229 | 56.8% | very_high |
| ed oliver | DL | 3539 | 1542 | 5536 | 56.4% | very_high |
| tyson bagent | QB | 1073 | 496 | 1650 | 53.8% | very_high |
| jalen milroe | QB | 783 | 363 | 1203 | 53.6% | very_high |
| tanner mckee | QB | 1073 | 497 | 1649 | 53.6% | very_high |
| quinn ewers | QB | 783 | 364 | 1202 | 53.6% | very_high |
| jalen mcmillan | WR | 2475 | 1199 | 3751 | 51.6% | very_high |
| davis mills | QB | 1073 | 523 | 1623 | 51.3% | very_high |
| jacob rodriguez | LB | 1682 | 830 | 2534 | 50.7% | very_high |
| joe milton | QB | 1073 | 534 | 1612 | 50.3% | very_high |
| dre greenlaw | LB | 3081 | 1540 | 4622 | 50.0% | very_high |
| deshon elliott | DB | 2911 | 1462 | 4360 | 49.8% | very_high |
| tucker kraft | TE | 3739 | 1879 | 5599 | 49.7% | very_high |

## V1 guardrails

- The center value is unchanged from the deployed calculator.
- KTC/internal market ratings are not used as fundamental uncertainty truth.
- Injury status is not converted into an unvalidated point-value penalty.
- Missing-source imputation comes from observed position-cohort dispersion.
- The envelope will only receive a probability label after out-of-sample calibration supports one.

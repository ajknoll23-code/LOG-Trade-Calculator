# Trade Desk Value Uncertainty — Sensitivity Envelope V1

Method: `sensitivity-envelope-v1`  
Policy SHA256: `bafc53164f6d98448965c5d0b531b14be31a3d744f0e4a44d6cdac71b6c05247`

## Critical interpretation

**These ranges are not probability confidence intervals.** They are deterministic sensitivity envelopes around the deployed point value using currently observable projection disagreement, historical sampling noise, and availability-history signal.

- Players: **565**
- Width quartiles: Q25 **19.9%**, median **25.0%**, Q75 **30.0%**
- Provider coverage (0/1/2): **{'0': 70, '1': 319, '2': 176}**
- History coverage: **{'insufficient': 126, 'with_2plus_games': 439}**

## Position summary

| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |
|---|---:|---:|---:|---:|---:|
| QB | 64 | 38.7% | 11.9% | 17.2% | 28.9% |
| RB | 97 | 24.1% | 11.9% | 18.5% | 4.3% |
| WR | 114 | 26.3% | 11.9% | 22.5% | 6.9% |
| TE | 44 | 24.4% | 11.9% | 19.2% | 7.1% |
| DL | 86 | 24.9% | 9.5% | 21.0% | 5.2% |
| LB | 79 | 21.5% | 14.6% | 14.7% | 1.7% |
| DB | 65 | 19.8% | 12.9% | 14.4% | 1.9% |
| K | 16 | 30.0% | 18.8% | 20.9% | 10.4% |

## Widest current envelopes

| Player | Pos | Center | Low | High | Half-width | Tier |
|---|---|---:|---:|---:|---:|---|
| malik nabers | WR | 4088 | 148 | 8028 | 96.4% | very_high |
| kaden elliss | LB | 2990 | 266 | 5714 | 91.1% | very_high |
| devin white | LB | 3475 | 417 | 6533 | 88.0% | very_high |
| jameis winston | QB | 1073 | 158 | 1988 | 85.3% | very_high |
| nick bosa | DL | 3980 | 723 | 7237 | 81.8% | very_high |
| malik willis | QB | 3711 | 1224 | 6198 | 67.0% | very_high |
| kaleb elarmsorr | LB | 968 | 392 | 1544 | 59.5% | very_high |
| riley leonard | QB | 783 | 333 | 1233 | 57.5% | very_high |
| anthony richardson | QB | 879 | 375 | 1383 | 57.4% | very_high |
| nnamdi madubuike | DL | 2696 | 1163 | 4229 | 56.8% | very_high |
| ed oliver | DL | 3539 | 1542 | 5536 | 56.4% | very_high |
| tyson bagent | QB | 1073 | 493 | 1653 | 54.1% | very_high |
| jalen milroe | QB | 783 | 361 | 1205 | 53.9% | very_high |
| tanner mckee | QB | 1073 | 495 | 1651 | 53.9% | very_high |
| quinn ewers | QB | 783 | 362 | 1204 | 53.8% | very_high |
| jalen mcmillan | WR | 2475 | 1197 | 3753 | 51.6% | very_high |
| davis mills | QB | 1073 | 520 | 1626 | 51.5% | very_high |
| jacob rodriguez | LB | 1682 | 830 | 2534 | 50.7% | very_high |
| joe milton | QB | 1073 | 531 | 1615 | 50.5% | very_high |
| dre greenlaw | LB | 3081 | 1540 | 4622 | 50.0% | very_high |

## V1 guardrails

- The center value is unchanged from the deployed calculator.
- KTC/internal market ratings are not used as fundamental uncertainty truth.
- Injury status is not converted into an unvalidated point-value penalty.
- Missing-source imputation comes from observed position-cohort dispersion.
- The envelope will only receive a probability label after out-of-sample calibration supports one.

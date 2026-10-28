# Trade Desk Value Uncertainty — Sensitivity Envelope V1

Method: `sensitivity-envelope-v1`  
Policy SHA256: `bafc53164f6d98448965c5d0b531b14be31a3d744f0e4a44d6cdac71b6c05247`

## Critical interpretation

**These ranges are not probability confidence intervals.** They are deterministic sensitivity envelopes around the deployed point value using currently observable projection disagreement, historical sampling noise, and availability-history signal.

- Players: **565**
- Width quartiles: Q25 **20.0%**, median **26.1%**, Q75 **35.9%**
- Provider coverage (0/1/2): **{'0': 42, '1': 45, '2': 478}**
- History coverage: **{'insufficient': 126, 'with_2plus_games': 439}**

## Position summary

| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |
|---|---:|---:|---:|---:|---:|
| QB | 64 | 42.3% | 5.9% | 17.2% | 28.9% |
| RB | 97 | 27.0% | 13.0% | 18.5% | 4.3% |
| WR | 114 | 28.6% | 14.2% | 22.5% | 6.9% |
| TE | 44 | 24.6% | 9.1% | 19.2% | 7.1% |
| DL | 86 | 25.2% | 10.7% | 21.0% | 5.2% |
| LB | 79 | 22.1% | 16.0% | 14.7% | 1.7% |
| DB | 65 | 21.9% | 14.6% | 14.4% | 1.9% |
| K | 16 | 32.3% | 22.3% | 20.9% | 10.4% |

## Widest current envelopes

| Player | Pos | Center | Low | High | Half-width | Tier |
|---|---|---:|---:|---:|---:|---|
| jameis winston | QB | 1086 | 0 | 2172 | 100.0% | very_high |
| tanner mckee | QB | 1073 | 0 | 2146 | 100.0% | very_high |
| tyrel dodson | LB | 4295 | 0 | 8590 | 100.0% | very_high |
| malik nabers | WR | 4083 | 163 | 8003 | 96.0% | very_high |
| jj mccarthy | QB | 813 | 53 | 1573 | 93.5% | very_high |
| dj giddens | RB | 737 | 56 | 1418 | 92.4% | very_high |
| adam randall | RB | 913 | 72 | 1754 | 92.1% | very_high |
| dezhaun stribling | WR | 2190 | 192 | 4188 | 91.2% | very_high |
| brashard smith | RB | 739 | 70 | 1408 | 90.6% | very_high |
| jack endries | TE | 673 | 64 | 1282 | 90.5% | very_high |
| eli heidenreich | RB | 1077 | 103 | 2051 | 90.5% | very_high |
| will johnson | DB | 2222 | 268 | 4176 | 87.9% | very_high |
| jordan james | RB | 791 | 100 | 1482 | 87.4% | very_high |
| nick bosa | DL | 3823 | 634 | 7012 | 83.4% | very_high |
| jake tonges | TE | 1108 | 199 | 2017 | 82.0% | very_high |
| jayden reed | WR | 3326 | 607 | 6045 | 81.7% | very_high |
| max klare | TE | 780 | 147 | 1413 | 81.1% | very_high |
| jaxson dart | QB | 5091 | 990 | 9192 | 80.6% | very_high |
| jahdae walker | WR | 825 | 206 | 1444 | 75.0% | very_high |
| sirvocea dennis | LB | 3521 | 887 | 6155 | 74.8% | very_high |

## V1 guardrails

- The center value is unchanged from the deployed calculator.
- KTC/internal market ratings are not used as fundamental uncertainty truth.
- Injury status is not converted into an unvalidated point-value penalty.
- Missing-source imputation comes from observed position-cohort dispersion.
- The envelope will only receive a probability label after out-of-sample calibration supports one.

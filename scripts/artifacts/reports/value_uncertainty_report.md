# Trade Desk Value Uncertainty — Sensitivity Envelope V1

Method: `sensitivity-envelope-v1`  
Policy SHA256: `bafc53164f6d98448965c5d0b531b14be31a3d744f0e4a44d6cdac71b6c05247`

## Critical interpretation

**These ranges are not probability confidence intervals.** They are deterministic sensitivity envelopes around the deployed point value using currently observable projection disagreement, historical sampling noise, and availability-history signal.

- Players: **565**
- Width quartiles: Q25 **19.6%**, median **25.5%**, Q75 **34.6%**
- Provider coverage (0/1/2): **{'0': 42, '1': 89, '2': 434}**
- History coverage: **{'insufficient': 126, 'with_2plus_games': 439}**

## Position summary

| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |
|---|---:|---:|---:|---:|---:|
| QB | 64 | 39.7% | 5.6% | 17.2% | 28.9% |
| RB | 97 | 25.2% | 10.8% | 18.5% | 4.3% |
| WR | 114 | 27.7% | 11.2% | 22.5% | 6.9% |
| TE | 44 | 24.6% | 9.0% | 19.2% | 7.1% |
| DL | 86 | 25.0% | 10.1% | 21.0% | 5.2% |
| LB | 79 | 22.1% | 15.4% | 14.7% | 1.7% |
| DB | 65 | 20.7% | 14.2% | 14.4% | 1.9% |
| K | 16 | 31.8% | 21.6% | 20.9% | 10.4% |

## Widest current envelopes

| Player | Pos | Center | Low | High | Half-width | Tier |
|---|---|---:|---:|---:|---:|---|
| jameis winston | QB | 1086 | 0 | 2172 | 100.0% | very_high |
| tanner mckee | QB | 1073 | 0 | 2146 | 100.0% | very_high |
| tyrel dodson | LB | 4295 | 0 | 8590 | 100.0% | very_high |
| malik nabers | WR | 4083 | 169 | 7997 | 95.9% | very_high |
| dj giddens | RB | 737 | 56 | 1418 | 92.4% | very_high |
| jack endries | TE | 673 | 55 | 1291 | 91.8% | very_high |
| dezhaun stribling | WR | 2190 | 192 | 4188 | 91.2% | very_high |
| adam randall | RB | 908 | 90 | 1726 | 90.1% | very_high |
| eli heidenreich | RB | 1077 | 110 | 2044 | 89.8% | very_high |
| will johnson | DB | 2222 | 268 | 4176 | 87.9% | very_high |
| jordan james | RB | 787 | 135 | 1439 | 82.9% | very_high |
| nick bosa | DL | 3823 | 661 | 6985 | 82.7% | very_high |
| jake tonges | TE | 1108 | 199 | 2017 | 82.0% | very_high |
| jayden reed | WR | 3326 | 607 | 6045 | 81.7% | very_high |
| jaxson dart | QB | 4351 | 846 | 7856 | 80.6% | very_high |
| brashard smith | RB | 739 | 148 | 1330 | 80.0% | very_high |
| max klare | TE | 780 | 173 | 1387 | 77.8% | very_high |
| sirvocea dennis | LB | 3521 | 887 | 6155 | 74.8% | very_high |
| devon achane | RB | 6415 | 1677 | 11153 | 73.9% | very_high |
| malik benson | WR | 1037 | 273 | 1801 | 73.6% | very_high |

## V1 guardrails

- The center value is unchanged from the deployed calculator.
- KTC/internal market ratings are not used as fundamental uncertainty truth.
- Injury status is not converted into an unvalidated point-value penalty.
- Missing-source imputation comes from observed position-cohort dispersion.
- The envelope will only receive a probability label after out-of-sample calibration supports one.

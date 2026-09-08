# Package Vote Fit Diagnostics V1

**Status: RESEARCH ONLY — no production consumer changed.**

## Data

- Counted package votes: `87`
- Unique voters: `9`
- Distinct challenges: `61`
- Package choices: `27`
- Target choices: `60`

## Diagnostic conclusion

- Status: `hold_research`
- Production promotion allowed: `False`

Warnings:
- current no-intercept lambda is on a grid boundary
- intercept-model lambda profile remains wide
- intercept-model lambda is on a grid boundary
- cluster bootstrap frequently lands on a lambda boundary
- FG does not materially improve the additive ratio model yet
- FG sign is not sufficiently stable across voter-cluster bootstrap samples

## Structural lambda comparison

| Model | alpha | lambda | beta | profile support | boundary | AIC |
|---|---:|---:|---:|---:|---:|---:|
| Current no-intercept | — | 1.000 | 2.000 | 0.0–1.0 | True | 122.16 |
| Structural + intercept | -0.846 | 0.000 | 0.400 | 0.0–1.0 | True | 113.74 |

## Additive FG diagnostics

| Model | coefficients | AIC |
|---|---|---:|
| Ratio only | `{'intercept': -0.8419281263011649, 'log_ratio': 0.3676437812271519}` | 111.74 |
| Ratio + FG | `{'intercept': -1.052704874056841, 'log_ratio': 0.5943167549035249, 'fg': 1.0446301936779}` | 113.67 |
| Ratio + FG + size3 | `{'intercept': -1.2074337754575653, 'log_ratio': 1.1409375706934533, 'fg': 3.355114091404098, 'size3': -0.6743744209974838}` | 113.94 |

- FG likelihood-ratio heuristic: stat `0.073`, p `0.7874`.
- Weighted corr(FG, size3): `0.3637686082936667`
- Weighted corr(FG, log raw ratio): `-0.3732540842271175`

## Voter-cluster bootstrap

- Reps: `400` (seed `20260908`)
- lambda median: `0.0`; 5–95%: `0.0`–`1.0`
- lambda boundary rate: `95.0%`
- FG coefficient median: `3.464490251987157`; negative in `33.2%` of reps
- size3 coefficient median: `-0.7350006978085699`; negative in `85.8%` of reps

## Leave-one-voter-out stability

- lambda median: `0.0`; 5–95%: `0.0`–`0.6099999999999997`
- FG coefficient median: `3.64926000928711`
- size3 coefficient median: `-0.668186816928878`

## Residuals by package size

| Size | Votes | Observed package % | Predicted % | Residual pp |
|---|---:|---:|---:|---:|
| 2 | 44 | 36.4 | 36.4 | -0.0 |
| 3 | 43 | 25.6 | 25.6 | -0.0 |

## Residuals by raw ratio target

| Ratio | Votes | Observed package % | Predicted % | Residual pp |
|---|---:|---:|---:|---:|
| 0.95 | 16 | 31.2 | 30.1 | +1.2 |
| 1.05 | 23 | 26.1 | 30.8 | -4.7 |
| 1.15 | 22 | 36.4 | 30.0 | +6.4 |
| 1.30 | 26 | 30.8 | 32.7 | -1.9 |

## Residuals by target position

| Position | Votes | Observed package % | Predicted % | Residual pp |
|---|---:|---:|---:|---:|
| TE | 14 | 0.0 | 33.2 | -33.2 |
| DB | 18 | 50.0 | 31.8 | +18.2 |
| LB | 12 | 50.0 | 33.2 | +16.8 |
| DL | 9 | 44.4 | 27.7 | +16.7 |
| WR | 13 | 15.4 | 28.9 | -13.5 |
| RB | 9 | 22.2 | 29.5 | -7.2 |
| QB | 12 | 33.3 | 31.1 | +2.2 |

## Largest target-anchor residuals

| Target | Votes | Observed package % | Predicted % | Residual pp |
|---|---:|---:|---:|---:|
| Brian Burns | 3 | 100.0 | 26.9 | +73.1 |
| Brock Bowers | 6 | 0.0 | 35.6 | -35.6 |
| Trey McBride | 8 | 0.0 | 31.5 | -31.5 |
| Nick Cross | 8 | 62.5 | 33.5 | +29.0 |
| Jahmyr Gibbs | 3 | 0.0 | 28.9 | -28.9 |
| Jaxon Smith-Njigba | 8 | 0.0 | 26.5 | -26.5 |
| Nick Bolton | 9 | 55.6 | 31.8 | +23.7 |
| Myles Garrett | 6 | 16.7 | 28.1 | -11.5 |
| Tykee Smith | 10 | 40.0 | 30.4 | +9.6 |
| Puka Nacua | 5 | 40.0 | 32.7 | +7.3 |
| Jack Campbell | 3 | 33.3 | 37.2 | -3.9 |
| Bijan Robinson | 6 | 33.3 | 29.7 | +3.6 |

## Interpretation guardrails

- The intercept model tests whether the old no-intercept lambda was absorbing a general consolidation preference.
- The additive FG test asks whether FG predicts package choice beyond raw package/target FV ratio.
- Package-size residuals test whether 3-for-1 behavior remains unexplained after FG.
- Bootstrap resamples whole voters, not individual ballots, so repeated opinions from one voter stay clustered.
- Profile support is a heuristic likelihood region, not a calibrated confidence interval.
- This file is research-only. No formula, Market Value input, Fundamental Value input, Team Utility input, or live verdict is changed.

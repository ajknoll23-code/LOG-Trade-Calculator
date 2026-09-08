# Package Vote V4 — 3-Player Indifference Diagnostics

**Status: RESEARCH ONLY — no production consumer changed.**

- Counted V4 votes: `300`
- Unique V4 voters: `15`
- Distinct challenges: `94`
- Distinct targets: `20`

## Candidate models

| Model | AIC | coefficients |
|---|---:|---|
| ratio_only | 399.55 | `{'intercept': -4.448586677336999, 'log_ratio': 6.191981771756014}` |
| ratio_plus_target | 401.47 | `{'intercept': -4.451472741233558, 'log_ratio': 6.196968512526889, 'target_z': -0.030996050333500502}` |
| ratio_plus_target_interaction | 402.34 | `{'intercept': -4.436425440991194, 'log_ratio': 6.16995768376068, 'target_z': -1.2507080288654873, 'ratio_x_target_z': 1.8257922919380187}` |

## 50% package-choice ratio estimates

### ratio_only

| Target reference | Target FV | 3-player ratio | Inside V4 range |
|---|---:|---:|---|
| p25 | 4269 | 2.051 | True |
| median | 5050 | 2.051 | True |
| p75 | 5558 | 2.051 | True |
| p90 | 6079 | 2.051 | True |

### ratio_plus_target

| Target reference | Target FV | 3-player ratio | Inside V4 range |
|---|---:|---:|---|
| p25 | 4269 | 2.045 | True |
| median | 5050 | 2.052 | True |
| p75 | 5558 | 2.056 | True |
| p90 | 6079 | 2.060 | True |

### ratio_plus_target_interaction

| Target reference | Target FV | 3-player ratio | Inside V4 range |
|---|---:|---:|---|
| p25 | 4269 | 2.068 | True |
| median | 5050 | 2.051 | True |
| p75 | 5558 | 2.044 | True |
| p90 | 6079 | 2.038 | True |

## Voter-cluster bootstrap

- Reps: `400`
- raw-ratio coefficient positive: `100.0%`
- target-value coefficient negative: `62.2%`
- median-target 3-player indifference median: `2.0487448866322993`
- within V4 tested range: `88.2%`

## V3 + V4 pooled sensitivity

- Frozen V3 3-player auxiliary votes: `145`
- V4 primary votes: `300`

## Conclusion

- Status: `three_player_indifference_signal_identified_not_production_ready`
- Production promotion allowed: `False`

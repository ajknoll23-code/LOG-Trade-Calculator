# Package Vote V3 — Indifference Calibration Diagnostics

**Status: RESEARCH ONLY — no production consumer changed.**

V3 asks how much raw FV a 2- or 3-player package must contain before voters become indifferent to the concentrated target asset.

- Counted V3 votes: `300`
- Unique V3 voters: `15`
- Distinct challenges: `162`
- Distinct targets: `20`

## Diagnostic conclusion

- Status: `hold_research`
- Lowest-AIC V3-only model: `ratio_plus_size_target_interaction`
- Production promotion allowed: `False`

Warnings:
- 50% package-choice indifference is not empirically bracketed by the tested ratio endpoints

## V3-only candidate models

| Model | AIC | coefficients |
|---|---:|---|
| ratio_only | 350.74 | `{'intercept': -2.2232468298850585, 'log_ratio': 4.0344879900834165}` |
| ratio_plus_size | 320.03 | `{'intercept': -1.9684406936779266, 'log_ratio': 5.223728159590618, 'size3': -1.626234191226245}` |
| ratio_plus_size_target | 312.67 | `{'intercept': -2.086366505458346, 'log_ratio': 5.355384261425635, 'size3': -1.6518156519336034, 'target_z': -0.45091449120106347}` |
| ratio_plus_size_target_interaction | 302.33 | `{'intercept': -2.5363231594378175, 'log_ratio': 6.357941590549705, 'size3': -1.6608832646892213, 'target_z': -1.7832832051717844, 'ratio_x_target_z': 3.548467125829478}` |

## Estimated 50% package-choice ratios

These are shadow estimates, not live adjustments.

### ratio_only

| Target reference | Target FV | 2-player ratio | 3-player ratio |
|---|---:|---:|---:|
| p25 | 4269 | 1.735 | 1.735 |
| median | 5050 | 1.735 | 1.735 |
| p75 | 5558 | 1.735 | 1.735 |
| p90 | 6079 | 1.735 | 1.735 |

### ratio_plus_size

| Target reference | Target FV | 2-player ratio | 3-player ratio |
|---|---:|---:|---:|
| p25 | 4269 | 1.458 | 1.990 |
| median | 5050 | 1.458 | 1.990 |
| p75 | 5558 | 1.458 | 1.990 |
| p90 | 6079 | 1.458 | 1.990 |

### ratio_plus_size_target

| Target reference | Target FV | 2-player ratio | 3-player ratio |
|---|---:|---:|---:|
| p25 | 4269 | 1.401 | 1.907 |
| median | 5050 | 1.486 | 2.023 |
| p75 | 5558 | 1.537 | 2.092 |
| p90 | 6079 | 1.586 | 2.159 |

### ratio_plus_size_target_interaction

| Target reference | Target FV | 2-player ratio | 3-player ratio |
|---|---:|---:|---:|
| p25 | 4269 | 1.410 | 2.105 |
| median | 5050 | 1.497 | 1.923 |
| p75 | 5558 | 1.523 | 1.872 |
| p90 | 6079 | 1.541 | 1.839 |

## Voter-cluster bootstrap

- Reps: `400`
- raw-ratio coefficient positive: `100.0%`
- 3-player coefficient negative: `100.0%`
- median-target 2-player indifference median: `1.4584583093308687`
- median-target 2-player 5–95%: `1.3860363517404264`–`1.522997233937055`
- median-target 3-player indifference median: `1.99599166389899`
- median-target 3-player 5–95%: `1.8571891810959702`–`2.1950050326235524`

## Target fixed-effects sensitivity

- Target count: `20`
- log-ratio coefficient: `9.382980626509054`
- size3 coefficient: `-2.751437479454109`

## V2 + V3 pooled sensitivity

- V2 auxiliary votes: `120`
- V3 primary votes: `300`
- Combined voters: `20`
- V2 remains a separately labeled lower-ratio auxiliary dataset; it does not replace fresh V3 voting.

## Guardrails

- V2 remains frozen.
- V3-only fit is primary.
- V2+V3 pooling is sensitivity analysis only.
- Bootstrap resamples whole voters.
- No diagnostic model changes live player values or trade verdicts.

# Package Adjustment V9 — B5C Calibration Integrity and Coverage Diagnostics

**Status:** `PASS_B5C_CALIBRATION_INTEGRITY_AND_COVERAGE_DIAGNOSTICS_ONLY`

B5C is a prospective diagnostic repair stage after B5B demonstrated that the original strict six-unpooled-UCB rule was infeasible. No V9 human outcomes exist and no candidate, final metric, gate, sample size, or catalog is frozen here.

## Posterior-predictive challenge-variance check

Decision: `NO_CLEAR_PPC_EVIDENCE_CHALLENGE_SD_IS_INFLATED`

Observed challenge vote-share SD: 0.3570
B5A point challenge SD: 5.4751
Flag metrics: none

## Joint nuisance assurance

Crossed-bootstrap refits: 500
Corr(sigma_challenge, sigma_voter): 0.139
Fraction jointly >= B5A p90/p90: 0.358
The p90/p90 combination remains a stress test; B5D should integrate over joint nuisance draws for primary assurance.

## Full-response effect calibration

Decision: `MATERIAL_EFFECT_LABEL_MISMATCH_FULL_PROCESS_RECALIBRATION_REQUIRED`

- benefit_0p020: labeled -0.0200; realized -0.0178; relative attenuation 11.2%
- benefit_0p030: labeled -0.0300; realized -0.0293; relative attenuation 2.3%
- benefit_0p040: labeled -0.0400; realized -0.0375; relative attenuation 6.1%

## Fixed-burden information / coverage diagnostic

| Votes/challenge | Challenges/topology | Two-way overall coverage | Two-way topo coverage | Challenge-unit overall coverage | Challenge-unit topo coverage |
|---:|---:|---:|---:|---:|---:|
| 2 | 120 | 0.935 | 0.947 | 0.935 | 0.951 |
| 4 | 60 | 0.969 | 0.946 | 0.969 | 0.949 |
| 6 | 40 | 0.935 | 0.946 | 0.931 | 0.950 |
| 8 | 30 | 0.946 | 0.948 | 0.946 | 0.950 |

## Firewall

- No production V1.7 predictions were evaluated on V8 votes.
- No V9 human outcomes exist or were read.
- No candidate, comparator implementation, metric, gate, sample size, or catalog is frozen.
- No production change is authorized.
- All six topologies remain the primary scope for the next prospective simulation; three-topology scoping is a fallback, not a B5C decision.

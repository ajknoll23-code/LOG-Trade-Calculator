# Package Adjustment V9 — B5D Prospective Rule and Burden Operating-Characteristic Screen

**Decision:** `STOP_NO_RULE_DESIGN_COMBINATION_MEETS_OC_TARGETS_WITHIN_PREFERRED_BURDEN`

B5D is synthetic screening only. It does not select or freeze a V9 model, comparator implementation, final metric, final gate, sample size, or human-vote catalog.

## Primary targets

- >=80% joint PASS power when full-process macro log-loss benefit is 0.020.
- <=5% false PASS under the null.
- >=95% detection when one topology is +0.020 worse while the other five are about -0.040 better.
- Preferred burden remains <=60 voters / <=1440 ballots / 24 ballots per voter.

## B5C repairs incorporated

- Integrates over the 500 crossed-bootstrap joint nuisance draws rather than using B5A p90/p90 as the sole assurance point.
- Recalibrates benefit and unsafe scenarios through the full Bernoulli + five-fold nuisance-refit response process.
- Screens 2/4/6/8 votes per challenge so independent-challenge information is evaluated directly.
- Keeps the strict six-unpooled-UCB B5B rule as a baseline.
- Adds only prospectively declared alternatives: hierarchical partial pooling plus a Bonferroni worst-vs-rest harm veto, and an overall+contrast rule with a hard point backstop.

Qualifying screening combinations: **0**

## Best diagnostic row by rule

| Rule | Estimator | Voters | R | C/topology | .020 power | Null false PASS | Unsafe detection | Qualifies |
|---|---|---:|---:|---:|---:|---:|---:|---|
| strict_6x_unpooled_ucb | two_way_cluster_t | 48 | 8 | 24 | 0.008 | 0.000 | 1.000 | no |
| hierarchical_ucb_plus_contrast_veto | challenge_unit_t | 60 | 2 | 120 | 0.383 | 0.000 | 0.567 | no |
| overall_plus_contrast_and_point_backstop | challenge_unit_t | 60 | 2 | 120 | 0.325 | 0.000 | 0.542 | no |

## Scientific stop

No screened rule/design combination met all three primary operating-characteristic targets inside the preferred burden. This is a valid scientific STOP and does not authorize threshold relaxation or V9 voting.

## Firewall

- No V9 human outcomes exist or were read.
- No production V1.7 predictions were evaluated on V8 votes.
- No V9 candidate or comparator implementation was used.
- No final gate, estimator, design, architecture, or catalog is frozen.
- No production change is authorized.

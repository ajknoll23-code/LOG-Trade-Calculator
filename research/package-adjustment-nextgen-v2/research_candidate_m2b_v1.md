# Package Adjustment NextGen V2 — Frozen M2b Research Candidate V1

**Status:** frozen first-wave research candidate

## Candidate

- Candidate ID: **pkgnv2-m2b-v1**
- Model: **M2b**
- Selected regularization lambda: **1.0**
- Beta: **115.030079790689**
- Delta-left: **0.249278582896**
- Slope increments: **[0.0, 0.0, 0.0362911410036889, 0.0074486570102035975]**
- Boundary flags: **none**

## Frozen evidence

- Exact checkpoint: **800 effective votes / 40 voters**
- Canonical ballot SHA-256:
`6377c7e800c713df4e1445bd2fd0dbb45430b9855a9935df16f3d9e2d9b5fa72`
- Successful amended-fit run: **34658221528**
- Successful amended-fit artifact digest:
`sha256:55c0e642f02edbd7978ff94293f37d3e1740d7c9d72d54599c52e19119c7ce74`

## Structural holdout result

- M0 combined log loss: **0.680669730932**
- M2b combined log loss: **0.660807570209**
- Absolute M2b improvement: **0.019862160724**
- M2b scale holdout log loss: **0.603703517483**
- M2b topology holdout log loss: **0.708394280813**

The structural scale and topology holdouts are now **spent**. They may not be
reused for candidate tuning, model selection, or parameter changes.

## Bootstrap evidence

- Valid voter-cluster draws: **500 / 500**
- M2b favorable vs M0: **0.914**
- M2b favorable vs M2a: **0.906**
- 90% percentile improvement interval vs M0:
**[-0.001289698135,
0.030439675758]**
- Median improvement vs M0:
**0.015591510506**

The preregistered favorable-fraction criterion passed. The interval's 5th
percentile is slightly negative, so this result must not be described as a
wholly-positive 90% improvement interval.

## Production status

**M2b is not a production candidate yet.**

Production remains Package Adjustment V1.6. This freeze authorizes no production
change and no automatic promotion.

Before M2b can become a production candidate, its exact frozen parameters must be
evaluated prospectively under a separately preregistered time holdout. No further
tuning against the spent structural holdouts is allowed.

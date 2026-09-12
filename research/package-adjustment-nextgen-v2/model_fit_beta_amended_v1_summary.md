# Package Adjustment NextGen V2 — Model Fit, Beta Amendment V1

**Status:** `fit_complete_research_only`

## Frozen evidence checkpoint

- Effective votes: **800**
- Distinct voters: **40**
- Canonical ballot SHA-256: `6377c7e800c713df4e1445bd2fd0dbb45430b9855a9935df16f3d9e2d9b5fa72`
- Exact checkpoint: **800 votes / 40 voters**

## Frozen beta-bound amendment

- Amendment: **pkgnv2-beta-bound-v1**
- Original beta upper bound: **50**
- Amended beta upper bound: **250**
- All other preregistered model/CV/bootstrap/selection rules: **unchanged**

## Structural-holdout status

- Scale holdout: **SPENT by this one-time execution**
- Topology holdout: **SPENT by this one-time execution**
- Repeat structural-holdout evaluation: **not allowed**
- Further tuning against these holdouts: **not allowed**

## Research safety

- Research only: **true**
- Production change authorized: **false**
- Automatic production promotion: **false**
- Raw ballots/voter IDs persisted: **false**

## Point estimates

| Model | Combined holdout log loss | Scale holdout | Topology holdout | Eligible |
|---|---:|---:|---:|:---:|
| M0 | 0.680670 | 0.643183 | 0.711909 | yes |
| M1 | 0.680670 | 0.643183 | 0.711909 | yes |
| M2a | 0.680670 | 0.643183 | 0.711909 | yes |
| M2b | 0.660808 | 0.603704 | 0.708394 | yes |

## Preregistered bootstrap

- Status: `complete`
- Valid voter-cluster draws: **500 / 500**
- M2a favorable vs M0: **0.520**
- M2b favorable vs M0: **0.914**
- M2b favorable vs M2a: **0.906**

## Frozen selection rule

- Selection status: `research_candidate_selected`
- Research candidate: **M2b**
- Production promotion authorized: **false**

## M2a fitted parameter

- p: **1.00000000**

## M2b regularization

- Selected lambda: **1.0**


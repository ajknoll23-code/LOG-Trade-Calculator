# Package Adjustment NextGen V2 — Evidence Maturity Plan

**Status: PREREGISTERED BEFORE NEXTGEN VOTING — RESEARCH ONLY. VOTING IS NOT ACTIVATED. PRODUCTION V1.6 IS UNCHANGED.**

## Frozen evidence anchor

- Frozen challenges: **129**
- Realized experimental cells: **24**
- Training cells: **13**
- Structural scale holdout cells: **5**
- Structural topology holdout cells: **6**
- Canonical challenge payload SHA-256: `fa52f72f6f4bdeaf1a5a935bde0fb5d0ec0fc85cc2b0d58236c2101d47d4f5ab`
- Frozen catalog SHA-256: `953d06fb4f7b870a981dedcb80d1bde0a609212cd03d506ce9746e9197d9f9b5`

## Planning evidence

This plan was fixed before any NextGen voting outcome existed.

The read-only maturity-planning audit was GitHub Actions run `34563171372`,
artifact `10185046287`, artifact ZIP SHA-256
`a806dd4e1aa362a9bf02caa732f6b6e6b7565cca1ef5e48de565cb7c1734241d`.

Historical participation showed 300 / 300 / 600 counted votes in V3 / V4 / V5,
with 15 / 15 / 30 voters and **36 unique pseudonymous voters across the three snapshots**.
Every historical phase record contained exactly 20 votes per voter.

## Frozen sampling schedule

Use `equal_cell_via_family_weights_v1`.

Family is selected first:

- core 2v2: **62.5%**
- fragmentation: **12.5%**
- structural 3v3: **25%**

Cell is then sampled uniformly within the selected family, which gives every one of
the 24 frozen cells probability **1/24**. Challenge ID is sampled uniformly within
the selected cell. Display side is randomized 50/50. FV remains hidden.

Sampling may not adapt to interim vote outcomes.

## Voter protection

- Daily valid NextGen cap: **20**
- Primary-evidence effective lifetime cap: **20**
- Voter identity and timestamp are retained for clustered inference.

The 20-vote effective cap matches the actual historical per-phase participation used
in the simulation and is stricter than the prior 30-vote effective lifetime ceiling.

## Primary evidence-maturity gate

The first maturity checkpoint is **800 valid effective votes**.

At that checkpoint all of the following must be true:

1. at least **800** valid effective votes;
2. at least **40 distinct voters**;
3. every one of the 24 cells has at least **15 valid effective votes**;
4. every one of the 24 cells has at least **10 distinct voters**.

Under the preregistered equal-cell schedule, the 20,000-draw planning simulation at
40 voters / 800 votes produced:

- P(all 24 cells have at least 15 votes): **0.9978**
- conservative lower bound P(all 24 cells have at least 10 distinct voters): **0.9998096**
- 10th-percentile minimum votes in any cell: **19**
- median minimum votes in any cell: **23**

## Stopping rule

Stopping is based only on preregistered coverage, never on whether the observed effect
is favorable, statistically significant, or agrees with production V1.6.

If the coverage gate is not satisfied at 800 valid effective votes, continue under the
same frozen sampling schedule in fixed **100-vote** increments.

The hard collection cap is **1200 valid effective votes**.

If any required coverage gate is still unsatisfied at 1200, stop collection and mark the
affected cell and family **coverage-unresolved**. Gates may not be relaxed.

## Primary uncertainty statistic

Primary uncertainty is a **90% percentile interval from a nonparametric voter-cluster
bootstrap**. Voter is the resampling unit and all ballots from a resampled voter move
together. Primary model comparison remains **held-out log loss**.

Maturity does not require the interval to exclude zero. Ambiguous model evidence is a
scientifically valid unresolved result and does not trigger outcome-contingent sampling.

## Holdout protection

- Training split: fit eligible.
- Structural scale holdout: never used for fitting or tuning.
- Structural topology holdout: never used for fitting or tuning.
- Neither structural holdout may select knots, regularization, or hyperparameters.
- After a candidate is frozen, a later prospective-time window is required and is not
  used for model selection.

## Unresolved evidence

At the 1200-vote hard cap, a cell is coverage-unresolved if it has fewer than 15 valid
effective votes or fewer than 10 distinct voters. A family is coverage-unresolved if any
required cell in that family is coverage-unresolved.

Outcome ambiguity is different from coverage failure: tied or uncertain model evidence
is reported as inferentially unresolved rather than extending collection because the
result is inconvenient.

## Remaining requirement before voting activation

This maturity plan does **not** activate voting.

Before activation, a separate frozen model-fit preregistration must define the exact M2a
fit, M2b spline parameterization, knot rule, regularization, optimizer, choice likelihood,
bootstrap implementation and draw count, model-selection rule, and solver tolerance.

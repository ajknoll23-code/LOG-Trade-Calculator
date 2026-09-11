# Package Adjustment NextGen V2 — Frozen Model-Fit Preregistration

**Status: FROZEN BEFORE NEXTGEN VOTING. RESEARCH ONLY. VOTING IS NOT ACTIVATED. PRODUCTION V1.6 IS UNCHANGED.**

## Evidence boundary

The exact 129-row challenge catalog and the evidence-maturity plan are already frozen.
This document freezes the executable fitting and selection method before any fit-eligible
NextGen vote is observed.

The executable specification is `fit_package_adjustment_nextgen_v2.py`. The JSON
preregistration records the exact numerical-library versions, fixed FV-derived knots,
optimizer settings, cross-validation rule, bootstrap rule, and model-selection thresholds.

## Models eligible in the first wave

M0 is raw summed FV. M1 is the exact frozen production V1.6 benchmark. Because every
frozen NextGen challenge is multi-piece versus multi-piece and controlled-live V1.6
deliberately fails closed for multi-v-multi, M1 is exactly identical to M0 on this
catalog. No V1.6 behavior is invented outside production support.

M2a is the homogeneous power equivalent:

`E_p(S) = (sum FV_i^p)^(1/p)`, with `1 <= p <= 3`.

M2b is a continuous degree-1 monotone-convex spline over normalized FV. Its knots are
frozen numerically from the frozen rostered-player FV distribution at 0, Q25, Q50,
Q75, V_REF, and the maximum frozen side-total domain. Segment slopes start at 1 and
can only increase. The whole spline is normalized so `g(1)=1`.

M2b therefore preserves singleton identity, is strictly increasing and
permutation-invariant, rewards concentration without a hard stud/filler threshold,
and supports an exact inverse without silent extrapolation. Any inverse-domain failure
is unresolved/fail-closed.

M3 is inactive because the exact production draft-pick FV source is not verified.
M4-M6 are not eligible for first-wave selection. Once structural holdout results have
been viewed, those challengers require a separate preregistration and fresh or
prospective evidence.

## Choice likelihood

For canonical Side A:

`P(A) = logistic(beta * (Score(A)-Score(B))/V_REF + delta_left * I(A displayed left))`

`beta > 0`. There is no generic intercept. The primary fitting loss is voter-capped
negative log likelihood averaged equally across experimental cells, preventing random
vote-count imbalance from making one cell dominate.

## Optimization

All fits use deterministic SciPy L-BFGS-B with the exact bounds, multistarts and
convergence tolerances stored in the JSON preregistration. A parameter hitting a
preregistered disallowed upper/bias boundary makes that fit unresolved rather than
triggering a wider post-hoc search.

## M2b regularization

The spline roughness penalty is the mean squared adjacent change in normalized segment
slopes. Lambda is chosen from the frozen grid using five-fold voter-cluster
cross-validation on **training cells only**. Voters are assigned to folds by a
deterministic salted SHA-256 ordering. Structural holdouts are never used to choose
knots, lambda, or any hyperparameter.

If multiple lambdas are within 0.001 log loss of the best training-CV value, choose the
largest lambda (the smoother model).

## Structural holdouts and selection

Primary selection uses equal-cell macro log loss across all 11 frozen structural
holdout cells. Scale and topology holdout losses are also required separately.

Starting from M0, a challenger must satisfy all of the following:

- improve combined structural-holdout log loss by at least 0.005;
- regress by no more than 0.005 on either the scale or topology holdout split;
- be favored in at least 80% of valid voter-cluster bootstrap draws; and
- pass optimizer, support, and hard mathematical invariants.

M2a is tested first. M2b is then compared to the current incumbent. If a threshold is
not met, retain the simpler incumbent. Incomplete bootstrap/optimizer evidence is
unresolved, not permission to relax a threshold.

## Bootstrap

Use 500 valid nonparametric voter-cluster bootstrap draws with the frozen seed.
Each voter's original capped ballot weight is computed once from the original sample
before resampling. Bootstrap multiplicity scales the entire voter cluster. The lifetime
cap is **not** recomputed inside a draw, inheriting the corrected V5 uncertainty method.

M2b's lambda is fixed to the original-sample training-CV choice inside bootstrap draws.
Draws missing any required training or structural-holdout cell, or with unresolved
optimization, are discarded and resampled up to the preregistered attempt cap.

## Production and prospective boundary

This procedure may select a **research candidate only**. It cannot alter production.
A later prospective-time holdout remains mandatory after candidate freeze. Any
production candidate still requires separate shadow/prospective evidence and explicit
human approval.

# Package Adjustment NextGen V2 — Beta-Bound Amendment V1

Status: **frozen pre-holdout optimizer-bound amendment**

## Change

Only the nuisance choice-sensitivity optimizer upper bound changes:

- Original beta upper bound: **50**
- Amended beta upper bound: **250**
- Original log-beta upper bound: `3.912023005428146`
- Amended log-beta upper bound: `5.521460917862246`

The rule that an optimizer solution at the upper beta boundary is unresolved remains unchanged.

## Why this amendment is allowed before holdout evaluation

The original frozen fit returned unresolved because beta hit the preregistered ceiling.
All subsequent diagnostics were explicitly training-only.

- Exact evidence checkpoint remained **800 effective votes / 40 voters**.
- Canonical ballot fingerprint remained
`6377c7e800c713df4e1445bd2fd0dbb45430b9855a9935df16f3d9e2d9b5fa72`.
- **407** training ballots were used in diagnostics.
- **393** structural-holdout ballots were discarded before fitting.
- Structural-holdout outcomes were **not evaluated**.

Full-training M0/M2a first resolved at tested beta cap **150**.
M2b lambda=0 CV folds were only **3/5 eligible at 150**, but **5/5 eligible at 250**.
At beta cap 250, the full frozen M2b CV procedure succeeded, selected lambda **1.0**,
and the final full-training M2b fit was eligible with beta approximately **115.0301**
and no disallowed boundary flags.

## What does not change

The challenge catalog, evidence, maturity rules, train/holdout split, model formulas,
spline knots, M2b lambda grid, five-fold voter CV assignment, CV selection rule,
bootstrap procedure, bootstrap seed, 500-valid-draw requirement, model-selection
thresholds, simplicity order, and production Package Adjustment V1.6 formula all
remain unchanged.

This amendment does **not** authorize a production change.

## Next execution rule

The next first-wave research fit must use the exact frozen 800-vote checkpoint and
the original fitter logic with only the beta upper bound replaced by **250**.
Once structural-holdout outcomes are evaluated under that frozen amended procedure,
no additional tuning using these holdouts is allowed.

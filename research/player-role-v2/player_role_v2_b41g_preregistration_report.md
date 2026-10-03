# Player Role V2 — B41G 2025 Holdout Preregistration

- 2025 holdout opened: **No**
- B41C3 required before any 2025 read: **Yes**
- B41F model weights changed: **No**
- B41E tier thresholds changed: **No**
- B41C2 scorer changed: **No**
- Final best-single-signal baseline implementation frozen from 2019–2024 only: **Yes**
- Production change authorized: **No**

## Frozen final holdout decision

The eventual one-shot 2025 evaluation passes only if all data-integrity gates and all four preregistered tests pass:

1. The frozen B41F model is strictly superior to the frozen best-single-signal baseline by the upper bound of a 20,000-replicate origin-week cluster-bootstrap 95% CI on macro-position MAE difference.
2. The lower bound of the corresponding pooled Spearman 95% CI is strictly positive.
3. Frozen seven-tier mean future-production percentile is non-decreasing from Speculative through Elite.
4. Frozen seven-tier mean future-snap percentile is non-decreasing across snap-relevant positions.

No 2025 result may be used to retune weights, features, thresholds, scoring, exclusions, or the pass rule.

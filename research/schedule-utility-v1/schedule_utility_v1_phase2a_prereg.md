# Schedule Utility V1 — Phase 2A Retrospective Predictive Validation Preregistration

**Decision:** `PREREGISTERED_RETROSPECTIVE_PREDICTIVE_VALIDATION`

No 2015-2025 target outcomes were opened in this phase.

## Frozen test

- Seasons: **2015-2025**
- Target weeks: **4-17**
- Cells: **7** (QB Half; RB/WR/TE Half and PPR)
- Unit: directional offense-vs-defense position/scoring matchup
- Baseline forecast: trailing offense-position mean in the same pre-target window
- LOG-SAPA forecast: baseline + frozen defense effect
- Fitted coefficients: **NONE**
- Target-week information in predictor: **PROHIBITED**

## Primary inference

- Metric: relative MAE improvement versus baseline
- Weighting: equal cells within season, then equal seasons
- Inference: exact one-sided sign-flip across 11 season effects
- Exact sign assignments: **2,048**
- Row-level independence is **not** assumed

## Frozen pass gate

- Mean relative MAE improvement >= **1.0%**
- Exact one-sided season sign-flip p <= **0.05**
- At least **5/7** cells have positive mean MAE improvement
- Worst cell mean relative MAE improvement >= **-2.0%**
- Every season-cell coverage >= **95%**
- **All** components must pass

Failure means `STOP_RETROSPECTIVE_PREDICTIVE_VALIDATION`. Threshold loosening or post-outcome cell cherry-picking is prohibited.

## Production impact

None. A Phase 2 pass authorizes only consideration of Phase 3 prospective shadow.

Next: **Phase 2B — historical data harvest and preregistered retrospective validation**.

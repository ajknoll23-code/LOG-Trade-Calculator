# Draft Class Strength V2 — B12 Top-60 Stable-Era Preregistration

## Status

B12 freezes a new V2 architecture before V2 outcome execution.

This is **not** an independent confirmatory test. It follows the V1 identity-coverage failure and the user-frozen decision to stop spending research effort on lower-draft-capital retired players.

## Population

- Seasons: 2014–2023
- Positions: QB/RB/WR/TE (FB→RB)
- NFL overall picks: 1–60 inclusive
- Include every eligible player
- No career-status or retirement filtering
- No outcome sorting or backfill
- Cohort SHA256: `1a70070d07c8fd5c9fca0ce0437ebec18a8ee0e8d43bd148705e142f5e581efc`
- Players: 188
- Identity coverage: 100%

## Primary target

For each class, sum frozen H3.O2 across the full top-60 skill-position cohort. Normalize that observed total by a leave-one-class-out expected total based only on six fixed NFL draft-capital bins: 1–10, 11–20, 21–30, 31–40, 41–50, 51–60.

Class score = ln(observed total / expected total).

## Primary null

50,000 permutations, seed 20261006. H3.O2 values are shuffled only within the six fixed NFL draft-capital bins while each class's exact bin-count skeleton is preserved.

## Gate

All required:

- p < 0.10
- excess class variance ratio >= 0.30
- 80% bootstrap lower bound > 0
- all 10 classes complete

Passing B13 authorizes predictor-source feasibility only. It does not authorize production or 2027 scoring.

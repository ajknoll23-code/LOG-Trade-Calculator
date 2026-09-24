# Draft Pick FV V7 — R1-R6 Full Absolute Scale / Tail Continuity

**Decision:** `FREEZE_V7_R1_R6_FULL_SCALE_PREREGISTRATION_SOURCE_FREEZE_NEXT`

## Research question

Can a jointly fitted R1-R6 Draft Pick Fundamental Value curve preserve historical O1 shape while retaining the large O2 accuracy gains observed in V6 and eliminating the R4-to-R5 structural discontinuity exposed by the V6 D1 diagnostic?

## Why V7 exists

- V6 D1 H3 O2 improvement vs C0: **64.41%**
- V6 D1 H3 O1 change vs C0: **-3.95%**
- V6 D1 R4 late: **585.43**
- Frozen deployed R5 early: **1414.00**

V6 is not being repaired. Those exposed development findings only motivate this separately preregistered R1-R6 study.

## Source design

- Historical development begins from the frozen 378 clean V6 leagues.
- Known full-72-pick seed counts by 2018-2023 are **4 / 11 / 12 / 8 / 17 / 12**.
- Historical expansion is deterministic and outcome-blind: the full 15-term capped MFL union is probed for every year, all clean 72-pick qualifiers are frozen, and there is no early stopping.
- Minimum historical source gate: **12 full R1-R6 leagues per year**.
- 2024 gets **no new search**. All 10 already-frozen clean 72-pick V6 holdout leagues are retained; minimum gate is 8.

## Candidate families

- **C1:** one global R1-R6 scalar — preserves deployed normalized shape.
- **C2:** six round-specific scalars, all rounds jointly fitted.
- **C3:** five-parameter smooth additive R1-R6 curve.
- **C4:** 72-slot monotone curve shrunk toward C3; alpha grid 6 through 1536 with edge-alpha ineligibility.

## Primary development gate

- Six-class LOYO H3 O2 equal-year/equal-cell macro MAE.
- >=5% improvement vs C0.
- Improvement in at least 5 of 6 held-out classes.
- Paired 10,000-replicate stable-player cluster bootstrap upper 95% < 0.
- Historical O1 normalized 18-cell shape regression vs C0 <=2%.
- H2/H4 sensitivity, round-level, R5-R6 tail, identity, retention, monotonicity, and hard-bound gates all remain mandatory.

## 2024 holdout

- H2 opened only after a final development candidate is frozen.
- H2 can stop the study but cannot authorize production.
- H3 is scored only after the complete 2026 regular season.
- External trade replay and market comparison occur only after H3 passes.

## Production

- YEAR_DISCOUNT remains frozen.
- No automatic deployment.
- Separate human production review remains mandatory.

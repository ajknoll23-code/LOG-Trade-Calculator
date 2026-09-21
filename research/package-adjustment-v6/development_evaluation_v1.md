# Package Adjustment V6 Development Evaluation

**Status:** `v6_candidate_frozen_research_only`

Production remains `v1.6-v5-size2-composition-overlay`.

## Cross-validated development results

| Model | CV loss | Improvement vs C1 | Positive folds | Eligible |
|---|---:|---:|---:|---|
| C0 raw control | 0.665557 | -0.000547 | — | control |
| C1 production | 0.665009 | — | — | baseline |
| C2 | 0.586787 | 0.078222 | 5 / 5 | YES |
| C4 | 0.587854 | 0.077155 | 5 / 5 | YES |
| C5 | 0.604039 | 0.060970 | 5 / 5 | NO |

## Profile regressions versus C1

- **C2:** 45/33/22 -0.028196; 50/30/20 -0.084938; 50/25/25 -0.068245; 55/30/15 -0.110836; 60/25/15 -0.060487; 60/20/20 -0.116629
- **C4:** 45/33/22 -0.015739; 50/30/20 -0.081262; 50/25/25 -0.065776; 55/30/15 -0.110813; 60/25/15 -0.071205; 60/20/20 -0.118136
- **C5:** 45/33/22 -0.028971; 50/30/20 -0.074365; 50/25/25 -0.057292; 55/30/15 -0.092498; 60/25/15 -0.026960; 60/20/20 -0.085734

## C5 near-HHI residual gate

- **50/30/20__vs__50/25/25:** |Δ residual| = 0.013442 (PASS)
- **60/25/15__vs__60/20/20:** |Δ residual| = 0.032854 (PASS)

## Frozen selection

Selected **C2** under the preregistered rules and refit it on all spent exact-700 development evidence.

Its parameters are frozen in `development_candidate_v1.json`. No production change is authorized.

Next: frozen Monte Carlo power analysis, then preregistered fresh prospective confirmation.

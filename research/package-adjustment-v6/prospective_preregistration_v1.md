# Package Adjustment V6 Prospective Preregistration

**Status:** `frozen_v6_prospective_preregistration`

Production remains `v1.6-v5-size2-composition-overlay`.

## Frozen confirmation target

- Candidate: **C2**
- q: **2.989759**
- First and only exact maturity checkpoint: **13,200 effective votes**
- Minimum distinct voters: **440**
- Minimum effective votes per cell: **220**
- Minimum distinct voters per cell: **147**
- Required cells: **24 / 24**

The 13,200-vote checkpoint comes directly from the frozen Monte Carlo power analysis. Coverage thresholds preserve the conservative proportions of the prior prospective framework, scaled to the larger checkpoint.

## One-time prospective pass gates

- Combined equal-cell macro log-loss improvement of at least **0.005** versus C1.
- One-sided 95% upper confidence bound for overall C2-minus-C1 loss is **< 0**.
- 45/33/22 one-sided 95% upper bound is **< +0.003**.
- Every other composition profile one-sided 95% upper bound is **< +0.005**.
- All conditions must pass; there is no refitting, retuning, or second model selection.

## Independence

The future catalog must be generated after this freeze, may not overlap exact development trade signatures, and may not use C2/C1 predictions or development vote outcomes to rank or select challenges. V6P1 uses a new transport namespace.

## Next action

Generate and freeze the fresh V6P1 prospective catalog. Do not activate voting until that catalog has been validated and frozen.

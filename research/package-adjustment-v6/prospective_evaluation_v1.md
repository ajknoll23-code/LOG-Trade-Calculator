# Package Adjustment V6P1 Prospective Confirmation

**Status:** `v6p1_feasible_prospective_primary_confirmation_passed_eligible_for_separate_human_review_with_all_safety_diagnostics_visible`

This is the one-time preregistered evaluation of frozen C2 against frozen C1 using only the immutable exact-1,800 prospective dataset.

## Primary confirmatory result

- C1 equal-cell macro log loss: **0.672003**
- C2 equal-cell macro log loss: **0.615360**
- D = C2 - C1: **-0.056643**
- Required point gate: **D <= -0.005** -- **PASS**
- One-sided 95% upper bound: **-0.026118**
- Required uncertainty gate: **upper bound < 0** -- **PASS**
- Overall primary confirmation: **PASS**

Crossed voter/challenge bootstrap: **5,000 valid draws** from **5,000 attempts**, frozen seed **20260924**.

## Mandatory safety-profile diagnostics

These are descriptive production-review diagnostics, not six additional pass/fail hypotheses.

| Profile | Eff votes | Voters | D C2-C1 | 95% interval | 95% UCB |
|---|---:|---:|---:|---:|---:|
| 45/33/22 | 299 | 45 | -0.033972 | [-0.119274, +0.055707] | +0.040018 |
| 50/30/20 | 311 | 45 | -0.037408 | [-0.119508, +0.055271] | +0.036308 |
| 50/25/25 | 294 | 45 | -0.032040 | [-0.123257, +0.058301] | +0.042498 |
| 55/30/15 | 335 | 45 | -0.080225 | [-0.153419, +0.007725] | -0.008154 |
| 60/25/15 | 283 | 45 | -0.086796 | [-0.165729, +0.002075] | -0.013595 |
| 60/20/20 | 278 | 45 | -0.069415 | [-0.165856, +0.044515] | +0.023041 |

## Governance

- No fitting, refitting, recalibration, tuning, cross-validation, or model selection was performed.
- Frozen C1 and C2 parameters were used exactly as preregistered.
- Production remains `v1.6-v5-size2-composition-overlay`.
- A primary PASS creates eligibility for a separate human production review only; it does not deploy C2.

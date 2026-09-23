# Draft Pick FV V5 — Research Closeout

**Final decision:** `STOP_NO_V5_R1_R2_PICK_FV_CANDIDATE`

V5 is closed. No candidate is eligible for production and no post-validation refit is permitted.

## What V5 established

- Deployed C0 validation H3 O2 macro MAE: **3088.01**
- C1_R1_GLOBAL_RESCALE: **45.25%** validation MAE improvement vs C0; failed gate(s): `all_18_monotone_nonincreasing, o1_shape_regression_le_2pct`.
- C2_R1_R2_ROUND_RESCALE: **68.05%** validation MAE improvement vs C0; failed gate(s): `all_18_monotone_nonincreasing`.
- C3_R1_R2_LOW_PARAMETER_TIER_CURVE: **74.33%** validation MAE improvement vs C0; failed gate(s): `all_18_monotone_nonincreasing, mature_H4_regression_vs_matched_H3_le_2pct`.

The strongest isolation is **C2**: it passed every preregistered gate except the all-18-cell monotonicity gate. Its fitted R1/R2 scale runs below the untouched deployed R3 table, creating an upward R2→R3 discontinuity.

C3 reduced validation error even further, but it also failed mature-H4 robustness, so its issue is not purely structural.

## Frozen mock trades

The prior frozen mock trades containing draft picks remain **unused by V5**. Because V5 produced no eligible candidate, there is nothing legitimate to replay against them yet. Keep them frozen for external confirmation after a successor study selects a candidate.

## Successor-study constraint

Do **not** repair V5. Validation has been opened. A successor study must preregister any expanded round scope or new curve family before fitting.

A natural next research question is whether expanding the fitted curve through the R2→R3 boundary — potentially through the already-audited R1–R4 source depth — can preserve monotonicity while retaining the scale improvement V5 found.

The 2022–2023 validation classes are now spent for successor candidate design/selection. A future design must account for that explicitly; it must not relabel them as fresh holdout.

## Production

- Production change authorized: **No**
- PICK_BASE changed: **No**
- YEAR_DISCOUNT changed: **No**
- Package Adjustment changed: **No**
- Fundamental Value player formulas changed: **No**

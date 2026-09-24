# Draft Pick FV V6 — Research Closeout

**Final decision:** `STOP_NO_V6_R1_R4_DEVELOPMENT_CANDIDATE`

V6 is closed. No development candidate passed every preregistered gate, no 2024 holdout outcomes were opened, and no production change is authorized.

## Development result

- C0 LOYO H3 O2 macro MAE: **2191.64**
- C1_ROUNDWISE_RESCALE_R1_R4: **1046.92** MAE (52.23% improvement vs C0); failed: `h3_o1_shape_regression_vs_C0_le_2pct`.
- C2_ANCHORED_ADDITIVE_ROUND_TIER_CURVE: **922.20** MAE (57.92% improvement vs C0); failed: `h3_o1_shape_regression_vs_C0_le_2pct, no_hard_numeric_bound_saturation`.
- C3_SHRUNK_MONOTONE_SLOT_CURVE_R1_R4: **918.81** MAE (58.08% improvement vs C0); failed: `c3_selected_alpha_not_grid_edge, h3_o1_shape_regression_vs_C0_le_2pct, no_hard_numeric_bound_saturation`.

## Boundary-free diagnostic

- D1 LOYO H3 O2 macro MAE: **779.92** (64.41% improvement vs C0).
- D1 H3 O1 shape error: **0.5587** vs C0 **0.5817**.
- D1 all-development R4 late: **585.43**.
- Frozen R5 early: **1414.00**.
- Splicing those values would create an upward jump of **828.57 (141.53%)**.

D1 was diagnostic-only and cannot be promoted. Its value is to show that the frozen R5 boundary is a serious hypothesis for the next study, not to establish that R5 is wrong.

## 2024 holdout

- Source/identity cohort frozen: **Yes**
- H2 outcomes opened by V6: **No**
- H3 outcomes opened by V6: **No**

## Production

- PICK_BASE changed: **No**
- YEAR_DISCOUNT changed: **No**
- R5-R6 changed: **No**
- Production change authorized: **No**

## Successor

Do not repair V6. A new preregistered study should test the full **R1-R6 absolute scale / tail continuity** problem, including whether a jointly fitted curve can preserve O1 shape while keeping the large O2 accuracy gains observed here.

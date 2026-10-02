# Schedule Utility V1 — Post-Run Zero-Fill Validity Audit

**Audit decision:** `PASS_POSTRUN_ZERO_FILL_VALIDITY_STOP_ROBUST`

This is an outcome-aware, non-gating validity audit. It cannot convert the frozen B31 STOP into PASS.

## Frozen B31 replay

- Exact primary replay matches B31: `True`
- Replayed decision: `STOP_RETROSPECTIVE_PREDICTIVE_VALIDATION`

## Zero-fill validity

- Target zero-fill records: `50`
- QB/RB zero-fill keys: `18`
- Frozen AMD-4 rule violations: `0`

## Predictor/target symmetry, Weeks 4-16

- Point mismatches: `0`
- Zero-fill identity mismatch groups: `0`

## Non-gating sensitivities

- Excluding ALL target zero fills: `STOP_RETROSPECTIVE_PREDICTIVE_VALIDATION`
- Excluding QB/RB target zero fills: `STOP_RETROSPECTIVE_PREDICTIVE_VALIDATION`
- Both remain STOP: `True`

## Governance

- Original B31 STOP remains binding regardless of sensitivity results.
- No Phase 3 authorization.
- No production authorization.
- No V1 retuning or threshold change.

## Zero-fill records

- 2016 W5 2016_05_PHI_DET · DET · TE · HALF_PPR · AMD-4 pass=True
- 2016 W5 2016_05_PHI_DET · DET · TE · PPR · AMD-4 pass=True
- 2016 W5 2016_05_SD_OAK · LV · TE · HALF_PPR · AMD-4 pass=True
- 2016 W5 2016_05_SD_OAK · LV · TE · PPR · AMD-4 pass=True
- 2016 W7 2016_07_BUF_MIA · MIA · TE · HALF_PPR · AMD-4 pass=True
- 2016 W7 2016_07_BUF_MIA · MIA · TE · PPR · AMD-4 pass=True
- 2016 W7 2016_07_HOU_DEN · DEN · TE · HALF_PPR · AMD-4 pass=True
- 2016 W7 2016_07_HOU_DEN · DEN · TE · PPR · AMD-4 pass=True
- 2016 W8 2016_08_GB_ATL · GB · TE · HALF_PPR · AMD-4 pass=True
- 2016 W8 2016_08_GB_ATL · GB · TE · PPR · AMD-4 pass=True
- 2016 W10 2016_10_LA_NYJ · NYJ · TE · HALF_PPR · AMD-4 pass=True
- 2016 W10 2016_10_LA_NYJ · NYJ · TE · PPR · AMD-4 pass=True
- 2018 W7 2018_07_HOU_JAX · HOU · TE · HALF_PPR · AMD-4 pass=True
- 2018 W7 2018_07_HOU_JAX · HOU · TE · PPR · AMD-4 pass=True
- 2018 W7 2018_07_NE_CHI · NE · TE · HALF_PPR · AMD-4 pass=True
- 2018 W7 2018_07_NE_CHI · NE · TE · PPR · AMD-4 pass=True
- 2020 W7 2020_07_GB_HOU · HOU · TE · HALF_PPR · AMD-4 pass=True
- 2020 W7 2020_07_GB_HOU · HOU · TE · PPR · AMD-4 pass=True
- 2020 W9 2020_09_NE_NYJ · NE · TE · HALF_PPR · AMD-4 pass=True
- 2020 W9 2020_09_NE_NYJ · NE · TE · PPR · AMD-4 pass=True
- 2020 W11 2020_11_ATL_NO · NO · QB · HALF_PPR · AMD-4 pass=True
- 2020 W11 2020_11_ATL_NO · NO · QB · PPR · AMD-4 pass=True
- 2020 W12 2020_12_NO_DEN · DEN · QB · HALF_PPR · AMD-4 pass=True
- 2020 W12 2020_12_NO_DEN · DEN · QB · PPR · AMD-4 pass=True
- 2020 W12 2020_12_NO_DEN · NO · QB · HALF_PPR · AMD-4 pass=True
- 2020 W12 2020_12_NO_DEN · NO · QB · PPR · AMD-4 pass=True
- 2020 W13 2020_13_NO_ATL · NO · QB · HALF_PPR · AMD-4 pass=True
- 2020 W13 2020_13_NO_ATL · NO · QB · PPR · AMD-4 pass=True
- 2020 W14 2020_14_NO_PHI · NO · QB · HALF_PPR · AMD-4 pass=True
- 2020 W14 2020_14_NO_PHI · NO · QB · PPR · AMD-4 pass=True
- 2020 W16 2020_16_CAR_WAS · CAR · TE · HALF_PPR · AMD-4 pass=True
- 2020 W16 2020_16_CAR_WAS · CAR · TE · PPR · AMD-4 pass=True
- 2021 W13 2021_13_DAL_NO · NO · QB · HALF_PPR · AMD-4 pass=True
- 2021 W13 2021_13_DAL_NO · NO · QB · PPR · AMD-4 pass=True
- 2021 W14 2021_14_NO_NYJ · NO · QB · HALF_PPR · AMD-4 pass=True
- 2021 W14 2021_14_NO_NYJ · NO · QB · PPR · AMD-4 pass=True
- 2021 W15 2021_15_NO_TB · NO · QB · HALF_PPR · AMD-4 pass=True
- 2021 W15 2021_15_NO_TB · NO · QB · PPR · AMD-4 pass=True
- 2021 W17 2021_17_CAR_NO · NO · QB · HALF_PPR · AMD-4 pass=True
- 2021 W17 2021_17_CAR_NO · NO · QB · PPR · AMD-4 pass=True
- 2021 W17 2021_17_DET_SEA · DET · TE · HALF_PPR · AMD-4 pass=True
- 2021 W17 2021_17_DET_SEA · DET · TE · PPR · AMD-4 pass=True
- 2023 W5 2023_05_CIN_ARI · CIN · TE · HALF_PPR · AMD-4 pass=True
- 2023 W5 2023_05_CIN_ARI · CIN · TE · PPR · AMD-4 pass=True
- 2023 W5 2023_05_NYG_MIA · MIA · TE · HALF_PPR · AMD-4 pass=True
- 2023 W5 2023_05_NYG_MIA · MIA · TE · PPR · AMD-4 pass=True
- 2023 W7 2023_07_PIT_LA · PIT · TE · HALF_PPR · AMD-4 pass=True
- 2023 W7 2023_07_PIT_LA · PIT · TE · PPR · AMD-4 pass=True
- 2023 W8 2023_08_KC_DEN · DEN · TE · HALF_PPR · AMD-4 pass=True
- 2023 W8 2023_08_KC_DEN · DEN · TE · PPR · AMD-4 pass=True

# Draft Pick FV V5 — Phase 4 Development Candidate Fit

**Status:** `DEVELOPMENT_FITS_FROZEN`

This phase fit C1/C2/C3 using only 2018–2021 development outcomes. It did not read or score locked validation and does not select a winner.

## Primary development fit

| Candidate | Development O2 macro MAE | Structural gate | Parameters |
|---|---:|---|---|
| C0_DEPLOYED | 2963.51 | PASS | `{}` |
| C1_R1_GLOBAL_RESCALE | 1784.50 | FAIL | `{"k1": 0.5}` |
| C2_R1_R2_ROUND_RESCALE | 1186.62 | FAIL | `{"k1": 0.5, "k2": 0.5}` |
| C3_R1_R2_LOW_PARAMETER_TIER_CURVE | 1083.51 | FAIL | `{"A": 3068.4042872, "b": 0.618744, "late_penalty": 0.486344, "mid_penalty": 0.351032}` |

## Firewalls

- Locked-validation outcomes read: **No**
- Validation scoring performed: **No**
- Candidate winner selected: **No**
- KTC/market values read: **No**
- Package-vote evidence read: **No**
- YEAR_DISCOUNT fit/changed: **No**
- R3–R6 fit/changed: **No**
- Production change authorized: **No**

## Sensitivity

A separate non-IDP-only development fit was frozen as required by the original V3/V5 contract. It is diagnostic only and cannot alter the primary fitted parameters.

## Next step

Phase 5 may open the locked 2022–2023 validation corpus for the first time and score these already-frozen candidate parameter vectors. No refitting is permitted.

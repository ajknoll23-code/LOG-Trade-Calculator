# Package Adjustment NextGen V2 — Sampling Contract Correction

**Status: CORRECTED BEFORE VALID EVIDENCE — production V1.6 unchanged.**

Post-run verification of activation run `34609048356` found that the browser
inherited V5 voter-roster filtering and applied recent-history filtering before
family/cell selection. That could change the intended experimental-cell probabilities.

No vote outcome was inspected to make this correction.

Corrected sampling is family → cell → challenge → randomized display. Voter roster
never changes package-research eligibility. Recent-history avoidance operates only
within the already-selected cell.

Original activation: `2026-09-11T14:15:44.570861+00:00`
Corrected valid-ballot start: `2026-09-11T15:22:18.334044+00:00`

Every NextGen transport row at or before that corrected start is excluded without
regard to choice. The browser also refuses submissions until then.

Outcome-blind transport rows observed when correction ran: **0**.
The timestamp cutoff—not this count—defines canonical validity.

Frozen catalog, maturity plan, fitter/model preregistration, historical V3/V4/V5
evidence, KTC transport isolation, and production V1.6 are unchanged.

# Exact Rookie Slot Curve V1 — Phase 0 Preregistration

**Status:** `FROZEN_BEFORE_EXACT_SLOT_SOURCE_DIAGNOSTICS`

Exact Rookie Slot Curve V1 is a successor study to the closed/deployed Draft Pick FV V10 model. It does not reopen V10.

## Primary architecture

The only authorized exact-slot estimator in V1 is **Option 1H**.

1. Estimate historical H3/O2 expected value on the **overall-pick axis 1–48**.
2. Preserve V10's frozen source membership and equal draft-class macro weighting.
3. Fit no market data.
4. Apply a global weighted monotone projection.
5. Preserve the twelve **pre-bridge V10 fundamental-core bucket means** exactly.
6. Apply the frozen V10 global market bridge only after the historical curve is frozen.

Option 3 is not separate evidence; bucket-mean preservation is a deterministic constraint inside Option 1H. A hierarchical/spline Option 2 is not automatically authorized in V1.

## Exact cell and weighting contract

The historical V7/V8 source is a 12-pick-per-round source. For the development corpus, `overall_slot = (round-1)*12 + within_round_pick`.

The twelve exact R1–R4 cells are:

- R1 early 1–4; R1 mid 5–8; R1 late 9–12
- R2 early 13–16; R2 mid 17–20; R2 late 21–24
- R3 early 25–28; R3 mid 29–32; R3 late 33–36
- R4 early 37–40; R4 mid 41–44; R4 late 45–48

Phase 0A must prove that every retained R1–R4 row satisfies this mapping and that the frozen V10 cell assignment is exactly the union shown above. Otherwise the study stops before outcomes.

Within each training class and V10 cell, the frozen `development_fit_weight_v8` weights are normalized exactly as V10. Each training class receives equal total cell weight. Slot masses are induced by those frozen weights. Full-data bucket constraints use all six development classes; each LOYO fold recomputes both slot masses and bucket anchors from the five training classes only.

This historical 12-pick source mapping is **not** a runtime 12-team assumption. Future exact-slot lookup must use known overall pick or the actual league draft size/order.

## Source-first gate

Phase 0A is outcome-blind. It must use an explicit source-field allowlist, physically restrict development inputs to classes 2018–2023, and prove that no 2024+ H3/O2 row, fantasy-point outcome, KTC, market or package-vote field was read.

The support thresholds are frozen in `phase0_preregistration.json` before the audit runs and cannot be relaxed afterward.

The Phase 0A precision-simulation code and pass criterion must be frozen in a separate reviewed commit **before** the occurrence corpus is materialized or read. That simulation may tighten or STOP; it may never weaken B52's support gates.

## Phase 1 validation

The exact-slot candidate must beat a V10 bucket incumbent refit independently inside every LOYO fold. Full-data anchors are forbidden inside LOYO.

The paired improvement is `V10 loss - exact-slot loss`; at least 5 of 6 classes must favor exact slots and the one-sided paired t statistic with df=5 must be at least **1.476** (`p <= 0.10`).

Spacing stability is evaluated on the **raw pre-projection** LOYO curves. Zero spacing counts as failure. A round fails spacing if any of its three buckets fails.

Projection movement is evaluated within each round as weighted absolute movement divided by weighted absolute raw level. The limit is 5%, and no individual slot may move more than 30%, in the full-data fit or any LOYO fit.

Before projection, exact-slot values must reconstruct every V10 pre-bridge cell EV with relative error at most **1e-9** under the fit-specific frozen weights.

If a round reverts to V10 buckets and the resulting hybrid is not globally monotone without altering frozen components, V1 stops. A hybrid must also re-pass the same incremental LOYO gate.

## R4 to R5 boundary

After the frozen exact R1–R4 curve is translated through V10's frozen global market bridge, but **before YEAR_DISCOUNT**, overall pick 48 must remain at least the frozen V10 R5-early `PICK_BASE` value **1394.2378677715392**.

The workflow asserts the frozen bridge multiplier is **2.24417411952795** and the 2027 year discount is **1.0**.

## Forward holdout

The 2024 class is reserved as the first genuine forward H3 holdout. Phase 0A and Phase 1 are physically restricted to 2018–2023, and reading any 2024 H3/O2 outcome row before maturity is a governance breach.

The holdout may not open before `2027-01-12T00:00:00Z`, after 2026 Week 18 completion and after a compatible pre-outcome 2024 source/weight contract is frozen.

The frozen holdout test is weighted 2024 H3/O2 MSE: the already-frozen V1 exact/hybrid candidate must have **strictly lower** MSE than the V10 pre-bridge bucket comparator trained only on 2018–2023. A tie fails. The holdout cannot rescue failed development gates and is required before Phase 3 production authorization.

## STOP is a valid result

If exact-slot support, mapping, concentration, effective sample size, precision, predictive superiority, spacing stability, projection stability, cell reconciliation, R4→R5 compatibility, forward holdout, or governance fails, V1 retains V10 early/mid/late.

There is no requirement that this research produce a 48-slot production curve.

## Production isolation

Phase 0 authorizes no production change, no year-discount change, no R5–R6 redesign, and no player FV, Package Adjustment, Team Utility, or trade-verdict change.

# Exact Rookie Slot Curve V1 — Phase 0A Precision Simulation Contract

**Status:** `FROZEN_BEFORE_PHASE0A_OCCURRENCE_CORPUS_READ`

This stage freezes the precision algorithm required by B52 **before** the historical occurrence corpus is opened by the Phase 0A source audit.

It does not read the 24,970-occurrence corpus and does not estimate exact-slot outcomes.

## Precision model

The model starts from the already-frozen V10 historical **bucket-level** relative 95% uncertainty and inflates it according to the loss of independent rookie-cluster information at an exact slot.

For every slot/year, Phase 0A will aggregate the frozen occurrence weights by stable rookie identity and calculate rookie-cluster Kish effective sample size.

For a slot `s` inside V10 cell `c`:

`s*_y = min(n_eff_slot,y, n_eff_cell,y)`

`R_s = sum_y(1/s*_y) / sum_y(1/n_eff_cell,y)`

`inflation_s = sqrt(max(1, R_s))`

A slot-year may legitimately have Kish n_eff above its parent cell. That is not an error. When it happens, B53 gives no favorable precision credit for the excess by using `s*_y=min(s_y,c_y)` and records the floor event.

and:

`predicted slot relative 95% half-width = V10 cell relative 95% half-width × inflation_s`

The first-versus-last slot spacing uncertainty in a four-slot V10 cell is evaluated conservatively with zero error correlation:

`sqrt(h_first² + h_last²)`

Both `h` values are relative to the same parent V10 pre-bridge bucket mean, giving the spacing proxy a fixed denominator consistent with later S3 bucket-relative values. No positive-correlation credit is allowed in the primary gate.

## Frozen precision gates

The Phase 0A precision component passes only if all are true:

- every one of 48 slots has predicted relative 95% half-width ≤ **40%**;
- at least **43/48** slots are ≤ **30%**;
- slots **1–4** are each ≤ **35%**;
- every one of 12 V10 buckets has conservative first↔last spacing half-width ≤ **50%**;
- at least **10/12** buckets have spacing half-width ≤ **40%**;
- deterministic Monte Carlo audit agrees with the analytic half-width within **0.01 absolute**.

These are necessary, not sufficient. All B52 source-support gates and later S2–S5 gates remain binding.

Failure means STOP Exact Slot V1 and retain V10, or preregister a separate lower-resolution successor. The thresholds may not be loosened after source diagnostics.

## Information firewall

The simulation accepts only a tiny outcome-blind support summary containing:

- cell ID;
- rookie-cluster Kish n_eff for the exact slot by class;
- rookie-cluster Kish n_eff for the parent V10 cell by class.

Extra fields are rejected.

It never accepts H3/O2 outcomes, fantasy points, exact-slot KTC/trade values, Package Adjustment votes, or 2024+ outcomes.

## Frozen code

`phase0a_precision_simulation.py`

SHA-256:

`3a3475377a1c0f68f12bbfd4f490a08f71b1c9244616a1d1c476198e62920d4c`

## Next stage

After this contract and code are independently reviewed and committed, Phase 0A may materialize the frozen pre-outcome occurrence corpus, construct the allowlisted support summary, run all B52 source gates, and execute this exact precision code by pinned hash.

## Ratio diagnostics

Phase 0A must report the min/median/max slot variance-information ratio and the count of slot-years where `slot n_eff > cell n_eff` triggered the no-credit floor.

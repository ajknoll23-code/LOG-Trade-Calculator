# B55 — Exact Rookie Slot Curve V1 — Pre-opening Governance Closeout

**Decision:** `STOP_EXACT_SLOT_V1_RETAIN_V10_OR_PREREGISTER_SEPARATE_LOWER_RESOLUTION_STUDY`

**Subdecision:** `SCIENTIFIC_STOP_BEFORE_OCCURRENCE_READ`

**Type:** Documented governance / design-certain STOP. **Not** an empirical B54 Phase 0A scientific result.

## Basis

B52's frozen `phase0_source_support_gates.concentration.provider_or_format_cluster_share_max` is **0.60**. Its only allowable exception is an *already-frozen source-weighting contract justifying the excess*. The frozen V6/V7 preregistrations define the eligible MyFantasyLeague, 12-team Superflex/2QB dynasty rookie-draft cohort, with weight balancing by year, cell, league and occurrence—not by provider or format. No explicit pre-B52 justification for exceeding the **provider/format concentration cap** was identified in the reviewed source-protocol evidence.

The V8 Phase 0J **2018 Round 6 source-availability exception** permits six eligible league groups where twelve were otherwise required. It addresses a different minimum-source gate; it is **not** a provider/format concentration waiver.

For a single-provider source, provider share is 100% by cohort design. This is **not** an observed result from opening the 24,970 source rows. Format is a *declared cohort property*, not independently measured per occurrence. No attempt was made to circumvent B52 by redefining the cluster unit or excluding the concentration gate.

## Evidence discipline

- B52 prereg SHA-256: `0f2d49eeac7c59027073924a03095eca349f2737eb8229202e52d8a06953fc15` (freeze commit `4b58551b4f4813b59ef558a27c8fa1452a0bb43c`).
- B53 precision freeze commit: `b72b5265e7f2129b28152effac512876e69a0d29`.
- Verified historical source and workflow **git blob** pins are recorded in the sibling JSON. The V6 and V7 freeze commits are checked as ancestors of the B52 freeze commit, and their pinned blobs are verified at their respective commits and at B52.
- Search inspected V6 structural prereg and pre-outcome amendment, V7 prereg and implementation contract, V8 Phase 0–1 source workflows (with several revisions), and the V8.1 carryforward prereg. Only the individually enumerated source files and workflows in the sibling JSON are Git-blob-pinned; the other workflow inspections are not independent historical content pins. No claim of exhaustive search of *all* repository history is made.
- No raw historical occurrence rows, H3/O2 outcomes, Package V9 votes, KTC/market evidence or 2024 holdout outcomes were opened for B54.

## Decision consequences

1. **Keep Draft Pick FV V10 deployed** and do not modify its values, runtime, or frozen release.
2. **Exact Slot V1 is closed at governance stage.** Neither source qualification nor exact-slot predictive performance has been evaluated on new data. Do not portray this as a failed exact-slot model.
3. B54 source engine V4 and definitions V3 remain **unfrozen / withdrawn**, not eligible for upload or run as V1.
4. A successor, if pursued, must have a **new V2 preregistration** that explicitly limits results to the single-provider 12-team Superflex/2QB cohort and states the loss of external validity. No B52 threshold is retroactively modified. No numeric support, league-concentration or precision threshold may be loosened in a successor. Any other design change must be justified from non-row evidence in the V2 preregistration and reviewed before any corpus read.
5. The 2024 holdout remains sealed until its original maturity gate, no earlier than `2027-01-12T00:00:00Z`.
6. Source artifact `10990665019` expires `2026-10-28T18:42:26Z`; expiry does not authorize opening or copying it outside a separately reviewed custody workflow.

No production authorization results from this closure.

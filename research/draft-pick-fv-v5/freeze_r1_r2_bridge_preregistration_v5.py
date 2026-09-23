#!/usr/bin/env python3
"""Freeze Draft Pick FV V5 R1/R2 bridge preregistration.

This stage is strictly pre-outcome. It uses already-audited source
feasibility evidence and the frozen V7 Phase 0 diagnosis to define a
narrower R1/R2 historical study. It does not read historical NFL
outcomes, fit candidates, score validation data, change production,
or use KTC/market values as a fit target.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

PHASE0 = ROOT / "research/package-adjustment-v7/phase0_pick_player_scale_bridge_v1.json"
PHASE0_MANIFEST = ROOT / "research/package-adjustment-v7/phase0_pick_player_scale_bridge_manifest_v1.json"
V4 = ROOT / "research/draft-pick-fv-v4/clean_source_recovery_v4.json"
V4_MANIFEST = ROOT / "research/draft-pick-fv-v4/clean_source_recovery_manifest_v4.json"
V3_PREREG = ROOT / "research/draft-pick-fv-v3/preregistration_v3.json"
V3_CLOSE = ROOT / "research/draft-pick-fv-v3/v3_closure.json"
LIVE = ROOT / "research/package-adjustment-production-candidate-v1/live_deployment.json"
INDEX = ROOT / "index.html"

OUT_SOURCE = HERE / "r1_r2_source_lineage_v5.json"
OUT_JSON = HERE / "r1_r2_bridge_preregistration_v5.json"
OUT_MD = HERE / "r1_r2_bridge_preregistration_v5.md"
OUT_MANIFEST = HERE / "r1_r2_bridge_preregistration_manifest_v5.json"

STUDY_ID = "draft-pick-fv-v5-r1-r2-player-equivalent-calibration"

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical_sha(obj: Any) -> str:
    raw = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def main() -> None:
    phase0 = load(PHASE0)
    phase0_manifest = load(PHASE0_MANIFEST)
    v4 = load(V4)
    v4_manifest = load(V4_MANIFEST)
    v3 = load(V3_PREREG)
    v3_close = load(V3_CLOSE)
    live = load(LIVE)

    assert phase0["decision"] == (
        "INVESTIGATE_DRAFT_PICK_TO_PLAYER_FV_BRIDGE_BEFORE_V7_PHASE1"
    )
    assert phase0["primary_summary"]["overall_material"] is True
    assert phase0["primary_summary"]["direction"] == (
        "PICKS_HIGH_RELATIVE_TO_SAME_MARKET_PLAYERS"
    )
    assert phase0_manifest["status"] == "frozen_completed_diagnostic"

    # Preserve both earlier scientific stops exactly.
    assert v3_close["status"] == "CLOSED_PRE_OUTCOME"
    assert v3_close["historical_player_outcomes_read"] is False
    assert v4["decision"] == "STOP_V4_CLEAN_SOURCE_RECOVERY_INSUFFICIENT"
    assert v4["primary_gate_pass"] is False
    assert v4["historical_player_outcomes_read"] is False
    assert v4["candidate_fit_performed"] is False
    assert v4["validation_scored"] is False
    assert v4_manifest["authorizes_outcome_ingestion"] is False

    # The R1-R4 clean cohort is already source-feasible; V4 stopped
    # only because the broader study also required deeper-round gates.
    combined = {
        y: int(v4["combined_clean_scope_counts_by_year"][y]["primary_r1_r4"])
        for y in ("2018", "2019", "2020", "2021", "2022", "2023")
    }
    v3_seed = {
        y: int(v4["v3_clean_seed_scope_counts_by_year"][y]["primary_r1_r4"])
        for y in combined
    }
    new_clean = {y: combined[y] - v3_seed[y] for y in combined}

    assert combined == {
        "2018": 31,
        "2019": 50,
        "2020": 59,
        "2021": 64,
        "2022": 90,
        "2023": 84,
    }
    assert sum(combined.values()) == 378
    assert sum(v3_seed.values()) == 172
    assert sum(new_clean.values()) == 206

    baseline = v3["frozen_deployed_baseline"]
    assert baseline["candidate_id"] == "C0_DEPLOYED"
    assert baseline["pick_base_2027"]["1"] == {
        "early": 7500, "late": 5244, "mid": 5854
    }
    assert baseline["pick_base_2027"]["2"] == {
        "early": 3906, "late": 3291, "mid": 3624
    }

    assert live["production_revision"] == "v1.7-v6-size3-c2-overlay"
    assert live["draft_pick_value_consumer_changed"] is False
    assert live["fundamental_value_consumer_changed"] is False

    generated = datetime.now(timezone.utc).isoformat()

    source_lineage = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "stage": "phase1_preregistration",
        "status": "frozen_pre_outcome_source_lineage",
        "generated_at_utc": generated,
        "research_only": True,
        "production_change_authorized": False,
        "historical_player_outcomes_read": False,
        "candidate_fit_performed": False,
        "validation_scored": False,
        "source_population": {
            "provider": "MyFantasyLeague",
            "years": [2018, 2019, 2020, 2021, 2022, 2023],
            "teams": 12,
            "format": "Superflex/2QB",
            "draft_pool": "Rookie-only",
            "mock_drafts": "excluded",
            "required_depth": "complete through Round 4",
            "v5_analysis_scope": "Rounds 1-2 only",
            "why_r4_complete_is_used": (
                "The inherited clean primary_r1_r4 cohort is the "
                "audited source population. V5 analyzes only its first "
                "24 actual slots and does not reopen the source search."
            ),
        },
        "clean_full_r4_counts_by_year": combined,
        "clean_full_r4_total": 378,
        "v3_clean_seed_counts_by_year": v3_seed,
        "v3_clean_seed_total": 172,
        "v4_new_clean_counts_by_year": new_clean,
        "v4_new_clean_total": 206,
        "existing_inherited_gate": {
            "name": "r1_r4_nonmock_total",
            "threshold": int(
                v4["frozen_source_sufficiency_gates"]["r1_r4_nonmock_total_min"]
            ),
            "observed": int(
                v4["primary_gates"]["r1_r4_nonmock_total"]["value"]
            ),
            "pass": bool(
                v4["primary_gates"]["r1_r4_nonmock_total"]["pass"]
            ),
        },
        "exact_phase2_catalog_rule": {
            "v3_seed": (
                "Use only V3 league_audit rows with "
                "positive_rookie_scope_contamination=false and "
                "scope.primary_r1_r4=true."
            ),
            "v4_expansion": (
                "Use only V4 new_source_evidence.rows with "
                "positive_contamination=false and "
                "primary_r1_r4=true."
            ),
            "deduplication": "draft_year + league_id",
            "expected_unique_total": 378,
            "expected_by_year": combined,
            "no_post_freeze_manual_inclusions": True,
            "no_additional_source_search": True,
        },
        "scientific_note": (
            "V4 remains a failed broad R1-R6 study. V5 does not "
            "lower or rewrite V4's R5/R6 thresholds; it asks a new, "
            "narrower R1/R2 question motivated by the later frozen "
            "V7 Phase 0 bridge diagnosis."
        ),
        "source_hashes": {
            "phase0_result_sha256": sha256_file(PHASE0),
            "phase0_manifest_sha256": sha256_file(PHASE0_MANIFEST),
            "v4_clean_source_recovery_sha256": sha256_file(V4),
            "v4_clean_source_manifest_sha256": sha256_file(V4_MANIFEST),
            "v3_preregistration_sha256": sha256_file(V3_PREREG),
            "v3_closure_sha256": sha256_file(V3_CLOSE),
        },
    }

    cells = [
        {"round": 1, "tier": "early", "exact_slots": [1, 2, 3, 4]},
        {"round": 1, "tier": "mid", "exact_slots": [5, 6, 7, 8]},
        {"round": 1, "tier": "late", "exact_slots": [9, 10, 11, 12]},
        {"round": 2, "tier": "early", "exact_slots": [13, 14, 15, 16]},
        {"round": 2, "tier": "mid", "exact_slots": [17, 18, 19, 20]},
        {"round": 2, "tier": "late", "exact_slots": [21, 22, 23, 24]},
    ]

    prereg = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "stage": "phase1_preregistration",
        "status": "FROZEN_PRE_OUTCOME",
        "generated_at_utc": generated,
        "research_only": True,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "historical_player_outcomes_read_before_freeze": False,
        "candidate_fit_performed_before_freeze": False,
        "validation_scored_before_freeze": False,
        "question": (
            "Using the already-audited clean historical 12-team "
            "Superflex/2QB rookie-draft source population, do realized "
            "first-three-season player-equivalent Fundamental Values "
            "support a better R1/R2 absolute scale and tier shape than "
            "the deployed pick table?"
        ),
        "motivation": {
            "phase0_decision": phase0["decision"],
            "phase0_direction": phase0["primary_summary"]["direction"],
            "phase0_primary_r1_material_high_count": int(
                phase0["primary_summary"]["material_high_count"]
            ),
            "phase0_primary_r1_case_count": int(
                phase0["primary_summary"]["primary_case_count"]
            ),
            "phase0_sensitivity_2027_early_2nd_classification": next(
                r["bridge"]["classification"]
                for r in phase0["cases"]
                if r["case_id"] == "2027_early_2nd"
            ),
            "interpretation": (
                "The external-market bridge diagnostic motivates the "
                "R1/R2 research question only. KTC/market values are "
                "not an outcome, fit target, weight, validation target, "
                "or production calibration source in V5."
            ),
        },
        "source_contract": source_lineage["source_population"],
        "phase2_source_catalog_rule": source_lineage[
            "exact_phase2_catalog_rule"
        ],
        "source_sufficiency": {
            "status": "established_pre_outcome_for_new_R1_R2_scope",
            "clean_full_r4_total": 378,
            "clean_full_r4_by_year": combined,
            "inherited_r1_r4_gate_threshold": 180,
            "inherited_r1_r4_gate_pass": True,
            "deep_round_gates": (
                "Not applicable to the new V5 estimand because R3-R6 "
                "are explicitly outside the V5 fitting scope and remain "
                "production-frozen."
            ),
        },
        "analysis_scope": {
            "rounds_fit": [1, 2],
            "exact_slots_fit": list(range(1, 25)),
            "production_cells_evaluated": cells,
            "rounds_3_to_6": "frozen at deployed values; never fit in V5",
            "team_count": 12,
            "tier_mapping": {
                "early": "slots 1-4 within round",
                "mid": "slots 5-8 within round",
                "late": "slots 9-12 within round",
            },
            "idp_format_policy": (
                "Primary R1/R2 fit uses the inherited all-nonmock "
                "primary_r1_r4 catalog; non-IDP-only R1/R2 results are "
                "required as a sensitivity analysis, matching the "
                "original V3 contract."
            ),
            "one_qb": "out of scope",
        },
        "development_and_validation": {
            "development_years": [2018, 2019, 2020, 2021],
            "locked_validation_years": [2022, 2023],
            "selection_requires_both_validation_years": True,
            "validation_is_never_used_for": [
                "candidate parameter fitting",
                "hyperparameter selection",
                "identity-rule changes",
                "outcome-definition changes",
                "source-rule changes",
                "candidate-family changes",
            ],
        },
        "historical_outcome_contract": v3["historical_outcome_contract"],
        "primary_outcomes": v3["primary_outcomes"],
        "frozen_scale_bridge": v3["frozen_scale_bridge"],
        "frozen_replacement_ranks": v3["frozen_replacement_ranks"],
        "fit_weighting": v3["fit_weighting"],
        "robustness": {
            "H2": v3["robustness"]["H2"],
            "H3": v3["robustness"]["H3"],
            "H4": v3["robustness"]["H4"],
            "r1_r2_nonidp_only": "required sensitivity report",
            "bootstrap_unit": (
                "stable player identity clustered within draft class; "
                "repeated selections of the same player are not "
                "independent observations"
            ),
        },
        "frozen_deployed_baseline": {
            "candidate_id": "C0_DEPLOYED",
            "fit_status": "baseline_only_never_refit",
            "pick_base_2027": baseline["pick_base_2027"],
            "year_discount_context_only": baseline[
                "year_discount_context_only"
            ],
            "v5_year_discount_policy": (
                "YEAR_DISCOUNT is not fit or changed in V5. Historical "
                "realized outcomes identify the PICK_BASE R1/R2 scale; "
                "future-year discount remains frozen for a separate "
                "question."
            ),
        },
        "candidate_families": {
            "C0_DEPLOYED": {
                "eligible": True,
                "parameters": 0,
                "definition": (
                    "Exact deployed PICK_BASE. Baseline only; never refit."
                ),
            },
            "C1_R1_GLOBAL_RESCALE": {
                "eligible": True,
                "parameters": 1,
                "bounds": {"k1": [0.50, 1.25]},
                "definition": (
                    "Multiply all three deployed R1 tier values by one "
                    "development-fit scalar k1. R2-R6 remain deployed."
                ),
            },
            "C2_R1_R2_ROUND_RESCALE": {
                "eligible": True,
                "parameters": 2,
                "bounds": {"k1": [0.50, 1.25], "k2": [0.50, 1.25]},
                "definition": (
                    "Apply separate development-fit scalars to deployed "
                    "R1 and R2 tier values. R3-R6 remain deployed."
                ),
            },
            "C3_R1_R2_LOW_PARAMETER_TIER_CURVE": {
                "eligible": True,
                "parameters": 4,
                "bounds": {
                    "A": [2500, 8500],
                    "b": [0.0, 1.5],
                    "mid_penalty": [0.0, 0.8],
                    "late_penalty": [0.0, 1.2],
                },
                "constraint": (
                    "0 <= mid_penalty <= late_penalty; generated R1/R2 "
                    "cells must be positive and non-increasing with "
                    "later draft slot."
                ),
                "definition": (
                    "value(round,tier) = A * exp(-b*I(round==2) - "
                    "tier_penalty[tier]); early penalty=0. R3-R6 remain "
                    "deployed."
                ),
            },
        },
        "candidate_fit": {
            "development_only": True,
            "objective": (
                "Equal-cell macro mean absolute error on O2 "
                "three_year_player_equivalent_fv across the six R1/R2 "
                "production cells, with each draft class contributing "
                "equal total weight."
            ),
            "optimizer_rule": (
                "Use deterministic bounded optimization. If multiple "
                "parameter vectors are numerically tied within 1e-9 "
                "objective value, choose lexicographically smallest "
                "rounded parameter vector."
            ),
            "validation_reuse_for_refit": False,
        },
        "selection": {
            "baseline": "C0_DEPLOYED",
            "winner_pool": [
                "C1_R1_GLOBAL_RESCALE",
                "C2_R1_R2_ROUND_RESCALE",
                "C3_R1_R2_LOW_PARAMETER_TIER_CURVE",
            ],
            "primary_metric": (
                "Locked-validation equal-cell macro MAE on O2 across "
                "the six R1/R2 production cells."
            ),
            "eligibility_gates": [
                "validation macro MAE improvement vs C0 >= 5%",
                (
                    "candidate must improve O2 macro MAE vs C0 in BOTH "
                    "2022 and 2023 validation classes"
                ),
                "O1 normalized-shape error regression vs C0 <= 2%",
                (
                    "H2 O2 macro-MAE regression vs candidate H3 primary "
                    "horizon <= 2% relative"
                ),
                (
                    "mature H4 O2 macro-MAE regression vs candidate H3 "
                    "primary horizon <= 2% relative"
                ),
                "all six fitted R1/R2 production cells positive",
                (
                    "after splicing onto untouched R3-R6, all 18 "
                    "production cells remain monotone non-increasing "
                    "with later draft slot"
                ),
                "R3-R6 deployed cells byte-for-byte/value-for-value unchanged",
                "identity resolution coverage >= 95%",
                "no forbidden data read before locked validation scoring",
            ],
            "winner_rule": (
                "Lowest locked-validation O2 macro MAE among eligible "
                "candidates; if within 1% relative MAE, choose fewer "
                "effective fitted degrees of freedom in order C1, C2, C3."
            ),
            "none_eligible": "STOP_NO_V5_R1_R2_PICK_FV_CANDIDATE",
            "winner_does_not_authorize_production": True,
        },
        "stage_gates": {
            "after_this_freeze": (
                "Build and freeze the exact 378-draft R1/R2 source "
                "catalog and identity map only. Do not read historical "
                "NFL outcomes yet."
            ),
            "after_source_catalog_freeze": (
                "Require exact source count/by-year reproduction, "
                "actual-slot completeness for slots 1-24, no positive "
                "rookie-scope contamination, duplicate checks, and "
                ">=95% identity resolution. Only then may the separate "
                "outcome-harvest workflow run."
            ),
            "after_outcome_harvest": (
                "Fit candidates on 2018-2021 development only, then "
                "score locked 2022-2023 exactly once."
            ),
            "after_selection": (
                "Freeze results. Any production change requires a "
                "separate explicit human review and deployment workflow."
            ),
        },
        "forbidden": [
            "reading historical NFL player outcomes before the exact source/identity catalog gate passes",
            "using KTC or any market value as a V5 fit target, loss, weight, or validation target",
            "using package-vote evidence in V5",
            "changing Package Adjustment",
            "changing Fundamental Value player formulas",
            "changing Market Value or Team Utility",
            "fitting or changing YEAR_DISCOUNT",
            "fitting R3-R6",
            "lowering V3/V4 historical source thresholds retroactively",
            "relabeling V3 or V4 as successful studies",
            "adding/removing candidate families after validation is read",
            "manual source inclusions after outcomes are observed",
            "automatic production promotion",
        ],
        "next_stage_if_freeze_passes": (
            "draft-pick-fv-v5-phase2-r1-r2-source-catalog-identity-freeze"
        ),
    }

    OUT_SOURCE.write_text(
        json.dumps(source_lineage, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUT_JSON.write_text(
        json.dumps(prereg, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    md = f"""# Draft Pick FV V5 — R1/R2 Bridge Preregistration

**Status:** `FROZEN_PRE_OUTCOME`

V7 Phase 0 found the deployed pick/player bridge materially high in all three
primary 2027 first-round cells. V5 opens a new, narrowly scoped R1/R2
historical study rather than asking Package Adjustment to compensate for an
upstream pick-value issue.

## Why V5 can proceed when V4 stopped

V4 remains stopped and is not being reinterpreted. Its broad R1-R6 design
failed the deep-round source gates. Separately, its already-audited clean
source evidence contains **378** twelve-team SF/2QB rookie drafts complete
through Round 4:

| Year | Clean full-R4 drafts |
|---:|---:|
| 2018 | {combined['2018']} |
| 2019 | {combined['2019']} |
| 2020 | {combined['2020']} |
| 2021 | {combined['2021']} |
| 2022 | {combined['2022']} |
| 2023 | {combined['2023']} |
| **Total** | **{sum(combined.values())}** |

The new V5 estimand uses only actual slots 1-24 (Rounds 1-2). R3-R6 are
production-frozen and are never fit.

## Frozen evaluation plan

Development is 2018-2021. Locked validation is 2022-2023 and must improve
in both validation years. The primary outcome is the inherited O2
three-year player-equivalent Fundamental Value. KTC/market values are
forbidden as fit targets; they served only as the Phase 0 diagnostic that
motivated this study.

Candidate families are frozen before outcomes: deployed baseline, one
global R1 rescale, separate R1/R2 rescale, and a low-parameter monotone
R1/R2 round-tier curve. A challenger must improve locked-validation macro
MAE by at least 5%, improve both 2022 and 2023, pass O1/H2/H4 robustness,
preserve full-table monotonicity, and leave R3-R6 untouched.

## Firewall

- Historical NFL outcomes read: **No**
- Candidate fit performed: **No**
- Validation scored: **No**
- KTC/market values used as fit target: **No**
- YEAR_DISCOUNT changed or fit: **No**
- Package Adjustment changed: **No**
- Production change authorized: **No**

## Next step

Freeze the exact 378-draft R1/R2 source catalog and identity map before any
historical NFL outcomes are read.
"""
    OUT_MD.write_text(
        "\n".join(line.rstrip() for line in md.splitlines()).strip() + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "stage": "phase1_preregistration",
        "status": "FROZEN_PRE_OUTCOME",
        "generated_at_utc": generated,
        "research_only": True,
        "production_change_authorized": False,
        "historical_player_outcomes_read": False,
        "candidate_fit_performed": False,
        "validation_scored": False,
        "source_catalog_frozen": False,
        "outcome_ingestion_authorized": False,
        "next_stage": prereg["next_stage_if_freeze_passes"],
        "input_hashes": {
            "phase0_result_sha256": sha256_file(PHASE0),
            "phase0_manifest_sha256": sha256_file(PHASE0_MANIFEST),
            "v4_clean_source_recovery_sha256": sha256_file(V4),
            "v4_clean_source_manifest_sha256": sha256_file(V4_MANIFEST),
            "v3_preregistration_sha256": sha256_file(V3_PREREG),
            "v3_closure_sha256": sha256_file(V3_CLOSE),
            "live_deployment_sha256": sha256_file(LIVE),
            "index_html_sha256": sha256_file(INDEX),
        },
        "output_hashes": {
            OUT_SOURCE.name: sha256_file(OUT_SOURCE),
            OUT_JSON.name: sha256_file(OUT_JSON),
            OUT_MD.name: sha256_file(OUT_MD),
        },
        "canonical_preregistration_sha256": canonical_sha(prereg),
        "source_lineage_canonical_sha256": canonical_sha(source_lineage),
    }
    OUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("PASS: Draft Pick FV V5 R1/R2 preregistration frozen pre-outcome.")
    print("NEXT=" + prereg["next_stage_if_freeze_passes"])

if __name__ == "__main__":
    main()

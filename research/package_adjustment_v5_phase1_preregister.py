#!/usr/bin/env python3
"""Close V4 and preregister Package Adjustment V5 before further outcome analysis.

V5 hypothesis:
V4's elite/fragmentation signal is useful overall, but draft picks are more
liquid/fungible than player pieces and should not incur the same fragmentation
penalty. V5 keeps the selected V4 s75 player-only behavior exactly unchanged,
while introducing preregistered pick-specific fragmentation/stud scaling.

This phase reads only the already-committed aggregate V4 evaluation result and
manifest. It does not read the 600 frozen ballots or individual human choices.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "research" / "package-adjustment-v4-elite-fragmentation"
V5 = ROOT / "research" / "package-adjustment-v5-liquid-picks"

V4_RESULT = V4 / "phase3_confirmation_evaluation.json"
V4_MANIFEST = V4 / "phase3_confirmation_evaluation_manifest.json"
V4_CLOSEOUT = V4 / "package_adjustment_v4_research_closeout.json"
V4_CLOSEOUT_MD = V4 / "package_adjustment_v4_research_closeout.md"

V5_PREREG = V5 / "phase1_structural_preregistration.json"
V5_MANIFEST = V5 / "phase1_manifest.json"

EXPECTED_V4_RESULT_BLOB = "dc293d2e21b1f15e32ded441d64e29e544774251"
EXPECTED_V4_MANIFEST_BLOB = "d86e12788f2ecfd4fce446e65831c66a7eb19009"

V4_SELECTED = "elite-frag-s75-p210-p330"
V4_RUNNER = "elite-frag-s50-p210-p330"

PICK_FRAGMENTATION_SCALES = [0.0, 0.33, 0.67, 1.0]
TOP_PICK_STUD_SCALES = [0.50, 0.75, 1.00]


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_candidates():
    out = []
    for pick_frag in PICK_FRAGMENTATION_SCALES:
        for top_pick_stud in TOP_PICK_STUD_SCALES:
            out.append({
                "id": (
                    "liquid-picks-"
                    f"pf{int(round(pick_frag * 100)):02d}-"
                    f"ts{int(round(top_pick_stud * 100)):03d}"
                ),
                "base_stud_strength": 0.75,
                "base_second_piece_discount": 0.10,
                "base_third_plus_discount": 0.30,
                "pick_fragmentation_scale": pick_frag,
                "top_pick_stud_scale": top_pick_stud,
            })
    return out


def main():
    for path in (V4_CLOSEOUT, V4_CLOSEOUT_MD, V5_PREREG, V5_MANIFEST):
        if path.exists():
            raise RuntimeError(f"Output already exists: {path}")

    if git_blob(V4_RESULT) != EXPECTED_V4_RESULT_BLOB:
        raise RuntimeError("V4 evaluation result drift")
    if git_blob(V4_MANIFEST) != EXPECTED_V4_MANIFEST_BLOB:
        raise RuntimeError("V4 evaluation manifest drift")

    result = json.loads(V4_RESULT.read_text(encoding="utf-8"))
    manifest = json.loads(V4_MANIFEST.read_text(encoding="utf-8"))

    assert result["status"] == "CONFIRMATION_FAILED_RESEARCH_ONLY"
    assert result["candidate_selection"]["selection_resolved"] is True
    assert result["candidate_selection"]["selected_candidate_id"] == V4_SELECTED
    assert result["candidate_selection"]["runner_up_candidate_id"] == V4_RUNNER
    assert result["candidate_selection"]["best_vs_runner_up_log_loss_gap"] == 0.019545491319
    assert result["production_candidate_eligible"] is False
    assert result["family_confirmation_supported"] is False
    assert manifest["one_time_evaluation_consumed"] is True
    assert manifest["production_candidate_eligible"] is False
    assert manifest["production_change_authorized"] is False

    s75 = result["candidate_results"][V4_SELECTED]
    s50 = result["candidate_results"][V4_RUNNER]

    assert s75["improvement_raw_minus_candidate"] == 0.045114306926
    assert s75["deployment_gates"]["improvement_gate_pass"] is True
    assert s75["deployment_gates"]["bootstrap_gate_pass"] is True
    assert s75["deployment_gates"]["group_safety_gate_pass"] is False
    assert s75["deployment_gates"]["all_24_frozen_cells_coverage_gate_pass"] is True
    assert s75["deployment_gates"]["challenge_cluster_bootstrap"]["favorable_fraction"] == 0.9716
    assert s75["deployment_gates"]["maximum_observed_group_regression"] == 0.086258867422

    assert s50["improvement_raw_minus_candidate"] == 0.025568815608
    assert s50["deployment_gates"]["improvement_gate_pass"] is True
    assert s50["deployment_gates"]["bootstrap_gate_pass"] is True
    assert s50["deployment_gates"]["group_safety_gate_pass"] is False
    assert s50["deployment_gates"]["maximum_observed_group_regression"] == 0.081646247039

    def find_group(candidate, topology, asset_mix):
        rows = candidate["deployment_gates"]["topology_x_asset_mix"]
        matches = [
            row for row in rows
            if row["topology"] == topology and row["asset_mix"] == asset_mix
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Group lookup drift: {topology}/{asset_mix}")
        return matches[0]

    s75_3v3_picks = find_group(s75, "3v3", "includes_picks")
    s50_3v3_picks = find_group(s50, "3v3", "includes_picks")

    assert s75_3v3_picks["regression_candidate_minus_raw"] == 0.086258867422
    assert s50_3v3_picks["regression_candidate_minus_raw"] == 0.081646247039

    now = datetime.now(timezone.utc).isoformat()

    closeout = {
        "schema_version": 1,
        "study_id": "package-adjustment-v4-elite-fragmentation",
        "status": "research_closed_no_production_successor",
        "closed": True,
        "closed_at_utc": now,
        "research_only": True,
        "one_time_confirmation_evaluation_consumed": True,
        "production_change_authorized": False,
        "production_revision_retained": "v1.6-v5-size2-composition-overlay",
        "candidate_selection": {
            "resolved": True,
            "selected_candidate_id": V4_SELECTED,
            "runner_up_candidate_id": V4_RUNNER,
            "best_vs_runner_up_log_loss_gap": 0.019545491319,
            "resolution_threshold": 0.002,
        },
        "selected_candidate_confirmation": {
            "raw_control_log_loss": result["raw_control"]["mean_held_out_log_loss"],
            "candidate_log_loss": s75["mean_held_out_log_loss"],
            "improvement_raw_minus_candidate": s75["improvement_raw_minus_candidate"],
            "minimum_required_improvement": 0.005,
            "improvement_gate_pass": True,
            "bootstrap_favorable_fraction": 0.9716,
            "minimum_required_bootstrap_favorable_fraction": 0.90,
            "bootstrap_gate_pass": True,
            "coverage_gate_pass": True,
            "maximum_allowed_topology_x_asset_mix_regression": 0.03,
            "maximum_observed_topology_x_asset_mix_regression": 0.086258867422,
            "group_safety_gate_pass": False,
            "failing_group": {
                "topology": "3v3",
                "asset_mix": "includes_picks",
                "regression_candidate_minus_raw": 0.086258867422,
                "effective_weight": s75_3v3_picks["effective_weight"],
            },
            "all_deployment_gates_pass": False,
        },
        "runner_up_confirmation": {
            "candidate_id": V4_RUNNER,
            "improvement_raw_minus_candidate": s50["improvement_raw_minus_candidate"],
            "bootstrap_favorable_fraction": s50["deployment_gates"]["challenge_cluster_bootstrap"]["favorable_fraction"],
            "maximum_observed_topology_x_asset_mix_regression": 0.081646247039,
            "group_safety_gate_pass": False,
            "same_failing_group": {
                "topology": "3v3",
                "asset_mix": "includes_picks",
                "regression_candidate_minus_raw": 0.081646247039,
                "effective_weight": s50_3v3_picks["effective_weight"],
            },
        },
        "scientific_conclusion": (
            "V4 demonstrated substantial aggregate confirmation signal versus raw "
            "addition, and candidate selection resolved decisively in favor of "
            "elite-frag-s75-p210-p330. Production eligibility nevertheless failed "
            "because the preregistered topology-by-asset-mix safety gate was violated "
            "in 3v3 trades containing picks. The runner-up showed the same failure "
            "pattern, so no V4 candidate may be promoted."
        ),
        "spent_confirmation_evidence": {
            "effective_votes": 600.0,
            "voter_clusters": 31,
            "distinct_challenges": 231,
            "cells": 24,
            "may_be_used_as_development_evidence_for_future_cycles": True,
            "may_not_be_reused_as_fresh_confirmation": True,
        },
        "governance": {
            "do_not_promote_v4": True,
            "do_not_relax_the_0_03_safety_gate_post_hoc": True,
            "do_not_substitute_s50_for_s75": True,
            "do_not_retune_v4_parameters_on_the_same_600_votes": True,
            "future_cycle_requires_new_preregistration_before_development": True,
            "future_cycle_requires_fresh_confirmation_after_candidate_freeze": True,
        },
        "next_action": (
            "Begin independent V5 liquid-pick research. Use V4 exact-600 only as "
            "spent development evidence; production remains V1.6."
        ),
    }
    V4_CLOSEOUT.write_text(
        json.dumps(closeout, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    closeout_md = f"""# Package Adjustment V4 — Research Closeout

**Status:** `research_closed_no_production_successor`

V4 selected `{V4_SELECTED}` decisively, with a **0.019545** held-out log-loss
gap over `{V4_RUNNER}`.

The selected candidate improved held-out log loss over raw addition by
**0.045114** and passed the **0.9716** challenge-cluster bootstrap gate.
It did not earn production eligibility because the frozen safety cap was
violated in **3v3 trades containing picks**:

- allowed maximum subgroup regression: **0.030000**
- observed s75 regression: **0.086259**
- observed s50 regression: **0.081646**

The V4 exact-600 confirmation evidence is now spent. It may be used for
development of a genuinely new preregistered architecture, but it may never
serve as fresh confirmation again.

Production remains `v1.6-v5-size2-composition-overlay`.
"""
    V4_CLOSEOUT_MD.write_text(closeout_md, encoding="utf-8")

    candidates = build_candidates()
    if len(candidates) != 12:
        raise RuntimeError("Expected exactly 12 V5 frozen candidates")

    prereg = {
        "schema_version": 1,
        "study_id": "package-adjustment-v5-liquid-picks",
        "phase": 1,
        "status": "FROZEN_BEFORE_SPENT_V4_DEVELOPMENT",
        "frozen": True,
        "frozen_at_utc": now,
        "research_only": True,
        "new_independent_research_cycle": True,
        "production_change_authorized": False,
        "production_revision_must_remain": "v1.6-v5-size2-composition-overlay",
        "development_evidence_boundary": {
            "v4_exact_600_role": "spent development evidence only",
            "v4_exact_600_may_count_as_fresh_confirmation": False,
            "old_v3_exact_600_may_count": False,
            "old_nextgen_900_may_count": False,
            "no_individual_v4_ballot_analysis_before_this_preregistration": True,
            "aggregate_v4_findings_allowed_to_define_hypothesis": [
                "s75 selected over s50 by 0.019545491319 held-out log loss",
                "s75 aggregate improvement versus raw = 0.045114306926",
                "s75 bootstrap favorable fraction = 0.9716",
                "s75 failed safety only because max group regression exceeded 0.03",
                "worst frozen group was 3v3 includes_picks at +0.086258867422",
                "s50 showed the same worst-group pattern at +0.081646247039",
            ],
        },
        "structural_hypothesis": {
            "name": "liquid-pick fragmentation",
            "statement": (
                "Draft picks are more liquid and fungible than player pieces. "
                "A KTC-style package adjustment should therefore apply less "
                "fragmentation penalty to draft-pick pieces than to player pieces, "
                "and should allow an elite draft pick to receive a smaller stud "
                "premium than an equally valued proven player."
            ),
            "not_allowed": [
                "topology-specific hardcoded 3v3 exception",
                "continuous optimization against V4 outcomes",
                "changing player-only V4 s75 behavior",
                "post-hoc threshold relaxation",
            ],
        },
        "base_player_only_contract": {
            "base_candidate_id": V4_SELECTED,
            "stud_strength": 0.75,
            "second_piece_discount": 0.10,
            "third_plus_discount": 0.30,
            "players_only_trade_scores_must_equal_v4_s75_exactly": True,
        },
        "v5_formula": {
            "asset_sort": "descending FV within each side",
            "top_asset": "v1",
            "second_asset": "v2 if present",
            "tail_assets": "v3 and later",
            "elite_factor": "clamp(v1 / 10000, 0, 1)",
            "top_stud_coefficient": (
                "0.75 for a player top asset; "
                "0.75 * top_pick_stud_scale for a draft-pick top asset"
            ),
            "second_piece_discount": (
                "0.10 for a player second asset; "
                "0.10 * pick_fragmentation_scale for a pick second asset"
            ),
            "third_plus_discount": (
                "0.30 for each player tail asset; "
                "0.30 * pick_fragmentation_scale for each pick tail asset"
            ),
            "side_effective_score": (
                "E = total_FV + elite_factor * "
                "(top_stud_coefficient*v1 - second_discount(v2)*v2 "
                "- sum(tail_discount(asset_i)*FV_i for i>=3))"
            ),
            "trade_score_delta": "(E_A-E_B)/(abs(E_A)+abs(E_B))",
            "display_adjustment": (
                "same bilateral effective-score interpretation as V4; "
                "1v1 remains display-quiet"
            ),
        },
        "candidate_grid": {
            "pick_fragmentation_scales": PICK_FRAGMENTATION_SCALES,
            "top_pick_stud_scales": TOP_PICK_STUD_SCALES,
            "candidate_count": 12,
            "candidates": candidates,
            "no_continuous_parameter_optimization": True,
            "no_topology_specific_parameters": True,
            "players_only_formula_frozen_to_v4_s75": True,
        },
        "asset_eligibility": {
            "players": {
                "allowed_positions": ["QB", "RB", "WR", "TE", "DL", "LB", "DB"],
                "positive_fv_required": True,
                "currently_rostered_required_for_new_catalogs": True,
                "retired_players_allowed": False,
                "explicitly_excluded_players": ["Joe Mixon"],
            },
            "draft_picks": {
                "years_allowed": [2027, 2028],
                "rounds_allowed": [1, 2, 3, 4],
                "slots_allowed": ["early", "mid", "late"],
                "2029_and_later_allowed": False,
            },
        },
        "hard_invariants": {
            "one_v_one_display_adjustment_zero": True,
            "side_swap_symmetry": True,
            "asset_order_invariance": True,
            "finite_nonnegative_display_adjustment": True,
            "positive_effective_side_score": True,
            "positive_effective_score_monotonicity_under_asset_value_increase": True,
            "adding_positive_piece_cannot_reduce_effective_side_score": True,
            "tiny_piece_continuity": True,
            "picks_first_class_assets": True,
            "multi_vs_multi_supported": True,
            "players_only_exact_v4_s75_equivalence": True,
            "stress_seed": 20260920,
            "stress_cases_per_shape": 1000,
            "stress_shapes": [
                "1v2", "1v3", "2v2", "2v3", "3v3", "3v4",
                "4v6", "5v6", "6v6", "1v10",
            ],
        },
        "phase2_spent_v4_development_plan": {
            "evidence": "frozen V4 exact-600 ballots, development-only",
            "cross_validation": "5-fold grouped by frozen voter cluster",
            "calibration": {
                "probability_link": (
                    "logistic(beta * normalized_effective_score_delta + "
                    "delta_left * I(canonical_A_displayed_left))"
                ),
                "beta_constraint": "beta > 0 via beta=exp(log_beta)",
                "calibration_parameters_refit_inside_each_training_fold": True,
            },
            "controls": [
                "raw-additive-control-g1.00",
                "v4-selected-elite-frag-s75-p210-p330",
            ],
            "candidate_selection": (
                "lowest mean held-out log loss among V5 candidates passing "
                "every invariant and development nomination gate"
            ),
            "development_nomination_gates": {
                "minimum_improvement_vs_raw_control": 0.005,
                "maximum_overall_log_loss_increase_vs_v4_s75": 0.005,
                "minimum_positive_folds_vs_raw": 3,
                "maximum_topology_x_asset_mix_regression_vs_raw": 0.02,
                "three_v_three_includes_picks_regression_vs_raw_must_be_at_most": 0.02,
                "players_only_predictions_must_equal_v4_s75": True,
            },
            "near_tie_rule": {
                "threshold_mean_log_loss": 0.001,
                "maximum_candidates_frozen": 2,
            },
            "if_no_candidate_passes": (
                "Close V5 without fresh voting. Do not widen the candidate grid "
                "against the same spent V4 outcomes."
            ),
        },
        "fresh_confirmation_contract_if_candidate_frozen": {
            "fresh_evidence_required": True,
            "new_vote_namespace": "__pkgv5c1__",
            "challenge_count": 240,
            "research_cell_design": "6 topologies x 2 asset mixes x 2 strata = 24 cells",
            "topologies": ["1v2", "1v3", "2v2", "2v3", "3v3", "3v4"],
            "asset_mix_groups": ["players_only", "includes_picks"],
            "challenge_strata": [
                "structural_disagreement",
                "balanced_broad",
            ],
            "structural_disagreement_definition": {
                "players_only": (
                    "V5/V4-s75 score is identical by construction; use frozen V4-s75 "
                    "versus raw disagreement to verify retained player-only signal"
                ),
                "includes_picks": (
                    "frozen V5 candidate versus V4-s75 disagreement, with raw as "
                    "an additional recorded control"
                ),
            },
            "challenges_per_cell": 10,
            "known_five_ktc_examples_excluded_exactly": True,
            "known_eight_historical_trades_excluded_exactly": True,
            "values_hidden_from_voters": True,
            "candidate_predictions_hidden_from_voters": True,
            "candidate_identity_hidden_from_voters": True,
            "display_side_randomization_required": True,
            "maturity": {
                "daily_valid_vote_cap_per_voter": 20,
                "effective_lifetime_vote_cap_per_voter": 30,
                "exact_effective_vote_checkpoints": [600, 700, 800],
                "minimum_distinct_voters": 30,
                "minimum_effective_votes_per_cell": 15,
                "minimum_distinct_voters_per_cell": 10,
                "outcome_blind_until_exact_checkpoint_freeze": True,
                "stop_rule": (
                    "Stop at first exact checkpoint where every coverage gate "
                    "passes; hard stop unresolved at 800 otherwise."
                ),
            },
            "evaluation": {
                "primary_metric": "5-fold voter-grouped held-out log loss",
                "raw_additive_control_required": True,
                "v4_s75_reference_required": True,
                "candidate_selection_if_two_frozen": (
                    "lowest mean held-out log loss; unresolved if "
                    "best-vs-runner-up gap < 0.002"
                ),
                "deployment_gates": {
                    "minimum_log_loss_improvement_vs_raw_control": 0.005,
                    "challenge_cluster_bootstrap_favorable_fraction_vs_raw": 0.90,
                    "maximum_topology_x_asset_mix_log_loss_regression_vs_raw": 0.03,
                    "all_24_cells_coverage_required": True,
                    "players_only_behavior_must_remain_v4_s75_equivalent": True,
                },
                "automatic_production_promotion_allowed": False,
                "production_change_if_any_gate_fails": False,
            },
        },
        "governance": {
            "v4_exact_600_is_spent_after_phase2_development": True,
            "no_reuse_as_v5_fresh_confirmation": True,
            "no_parameter_grid_expansion_after_phase2_outcomes": True,
            "no_ktc_development_examples_as_post_hoc_tiebreaker": True,
            "no_production_change_without_fresh_v5_confirmation": True,
        },
    }

    V5.mkdir(parents=True, exist_ok=True)
    V5_PREREG.write_text(
        json.dumps(prereg, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest_out = {
        "schema_version": 1,
        "status": "package_adjustment_v5_phase1_preregistration_manifest",
        "study_id": "package-adjustment-v5-liquid-picks",
        "phase": 1,
        "frozen": True,
        "frozen_at_utc": now,
        "production_change_authorized": False,
        "v4_individual_ballots_read_by_this_phase": False,
        "v4_aggregate_evaluation_only": True,
        "candidate_grid_count": len(candidates),
        "source_artifacts": {
            "v4_confirmation_evaluation": {
                "path": str(V4_RESULT.relative_to(ROOT)),
                "git_blob_sha": EXPECTED_V4_RESULT_BLOB,
                "sha256": sha256(V4_RESULT),
            },
            "v4_confirmation_manifest": {
                "path": str(V4_MANIFEST.relative_to(ROOT)),
                "git_blob_sha": EXPECTED_V4_MANIFEST_BLOB,
                "sha256": sha256(V4_MANIFEST),
            },
            "v4_closeout": {
                "path": str(V4_CLOSEOUT.relative_to(ROOT)),
                "sha256": sha256(V4_CLOSEOUT),
            },
        },
        "outputs": {
            "v5_preregistration": {
                "path": str(V5_PREREG.relative_to(ROOT)),
                "sha256": sha256(V5_PREREG),
            }
        },
        "next_action": (
            "Run V5 Phase 2 once against spent V4 exact-600 evidence under this "
            "frozen candidate grid and nomination contract."
        ),
    }
    V5_MANIFEST.write_text(
        json.dumps(manifest_out, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(V4_CLOSEOUT_MD.read_text(encoding="utf-8"))
    print("V5_PHASE1_STATUS=FROZEN_BEFORE_SPENT_V4_DEVELOPMENT")
    print("V5_CANDIDATE_COUNT=12")


if __name__ == "__main__":
    main()

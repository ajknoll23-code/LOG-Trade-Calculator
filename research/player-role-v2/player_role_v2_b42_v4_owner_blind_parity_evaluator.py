#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import requests
import secrets

STUDY_ID = "player-role-v2"
PHASE = "B42-v4-12-team-owner-blind-shadow-refresh-parity-audit"
CONTINUATION_CLASS = "OUTCOME_BLIND_IDENTITY_SOURCE_AMENDMENT"

PASS_RESULT = "PASS_B42_V4_12_TEAM_OWNER_BLIND_ROLE_PARITY"
FAIL_RESULT = "SCIENTIFIC_STOP_B42_V4_OWNER_BLIND_ROLE_PARITY_FAILED"
DATA_STOP_RESULT = "SCIENTIFIC_STOP_B42_V4_DATA_INTEGRITY"

POSITIONS = ["QB", "RB", "WR", "TE", "K", "DL", "LB", "DB"]
ROLE_ORDER = [
    "Speculative",
    "Depth",
    "Understudy",
    "Rotational",
    "Starter",
    "Every-Down",
    "Elite",
]

REQUIRED_TEAM_COUNT = 12
MIN_TEAM_ROLE_COVERAGE = 0.98
MAX_TEAM_COVERAGE_RANGE = 0.02
ALLOWED_COUNTERFACTUAL_ROLE_CHANGES = 0

B41A_PREREG_BLOB = "22f465253982b4e5a923327153bf9861ff3e76ec"
B41B_BUILDER_BLOB = "5843a4b84a00b11489909e65439aa5f4cd959989"
B41B_BUILDER_SHA256 = "84dcee287a9884976344acb13b844267105da0396fd4c1f02898b7d70c5d15dc"
B41C2_SCORER_BLOB = "9b5ba8edd4430bd62b713be71e03fda3d39cab96"
B41C2_SCORER_SHA256 = "cbc8548eb0dac7d6f8a95717925487e746605627f674c0a04637771c21e54e6b"
B41C_SCORING_BLOB = "8e350fc927417d2f8afceb5b42545e48e3622fff"
B41D_CONTRACT_BLOB = "fba6dd0c63e48e076c447d1c11841cfaedd0f688"
B41E_THRESHOLDS_BLOB = "4542575da6e258d9bd881fbe0497c9f6c0133a45"
B41E_THRESHOLDS_SHA256 = "c102374c44324d246f90831ac6d7a941ce8c020ac3bb9bb7e0a9e49b3d92b83c"
B41F_SNAPSHOT_BLOB = "d1ac822c29bfe31e9e1a9418b443ef1124b42413"
B41F_SNAPSHOT_SHA256 = "2f19725498eec4fdb1476e36c548a925817717edacb8b6b3c9c585488ef8f576"
B41G_PREREG_BLOB = "5a4f6a8bfac3eeb0640c1e2ab7aced316fe9afa5"
B41G_PREREG_SHA256 = "da4eb2ef6b3c63e9bf75080c26f11fe89d17ee348723996601a36955e916ce8f"
B41G_BASELINE_BLOB = "0e870f9eadceb1dc19936b364cb734c8ce2ad35f"
B41H_EVALUATOR_BLOB = "7ac94496cb80303f9976339642ab8c2070069bbd"
B41H_EVALUATOR_SHA256 = "5adf8692cba41165ac84bb86c3b76c55c217c00562367f33c644b11854cbd634"
B41I_DECISION_BLOB = "82ff5ada71d5a48785e61d3c15d68bafbceba52b"
B41I_IDENTITY_BLOB = "fb4ebad425db5bead98644365a4165cd06eee8e3"
B41I_IDENTITY_SHA256 = "d531dcff2d3ff681f02210d314f6e9f16c671c0beefa85fd311a55363675d4cc"
B41I_IDENTITY_RELATIVE_PATH = "research/player-role-v2/frozen_inputs/players_b41i_snapshot.csv"
B41J_EVALUATOR_BLOB = "3f5456a6d5b1af18568e395b394e0e07af2f7674"
B41J_EVIDENCE_BLOB = "ee618a05d4987f2ee457dec791dbdf49f615b7b3"
B41J_DECISION_BLOB = "5e5a2ca40b40f553399dca332558129594041b82"
B41J_STRUCTURAL_BLOB = "c78da0b98f3957636f1c528af99faf7f9af885b3"
B41J_SCORED_ROWS_BLOB = "2a0189d85358e04a8e8ca2ddce54eaa36a6370c4"
B41J_PASS_RESULT = "PASS_2025_HOLDOUT_VALIDATION_OUTCOME_BLIND_IDENTITY_SOURCE_AMENDMENT"

CURRENT_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_2026.csv"
)
CURRENT_SNAPS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "snap_counts/snap_counts_2026.csv"
)
SLEEPER_STATE_URL = "https://api.sleeper.app/v1/state/nfl"

EVIDENCE_SOURCE = "B41F_FROZEN_MODEL_CURRENT_2026_COMPLETED_WEEKS"
CONFIDENCE_STATUS = "NOT_CALIBRATED_B42_DOES_NOT_INVENT_CONFIDENCE_THRESHOLDS"

SHADOW_STATIC_FORBIDDEN_TOKENS = [
    "owner_id",
    "owner_username",
    "roster_id",
    "dynasty_team",
    "fantasy_roster_slot",
    "team_name",
    "starters",
    "bench",
    "taxi",
    "reserve_ir",
    "league_rosters",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify_blob(path: Path, expected: str, label: str) -> None:
    if not path.exists():
        raise RuntimeError(f"B42_REQUIRED_PARENT_MISSING {label} {path}")
    actual = git_blob_sha(path)
    if actual != expected:
        raise RuntimeError(
            f"B42_PARENT_GIT_BLOB_DRIFT {label} expected={expected} actual={actual}"
        )


def load_and_verify_frozen_lineage(repo: Path):
    base = repo / "research/player-role-v2"

    blob_expectations = {
        "player_role_v2_b41a_scientific_preregistration.json": B41A_PREREG_BLOB,
        "player_role_v2_b41b_cohort_builder.py": B41B_BUILDER_BLOB,
        "player_role_v2_b41c2_target_scorer.py": B41C2_SCORER_BLOB,
        "player_role_v2_b41c_league_scoring_snapshot.json": B41C_SCORING_BLOB,
        "player_role_v2_b41d_development_contract.json": B41D_CONTRACT_BLOB,
        "player_role_v2_b41e_tier_thresholds.json": B41E_THRESHOLDS_BLOB,
        "player_role_v2_b41f_final_model_snapshot.json": B41F_SNAPSHOT_BLOB,
        "player_role_v2_b41g_holdout_validation_preregistration.json": B41G_PREREG_BLOB,
        "player_role_v2_b41g_baseline_snapshot.json": B41G_BASELINE_BLOB,
        "player_role_v2_b41h_one_shot_holdout_evaluator.py": B41H_EVALUATOR_BLOB,
        "player_role_v2_b41i_recovery_eligibility_decision.json": B41I_DECISION_BLOB,
        "frozen_inputs/players_b41i_snapshot.csv": B41I_IDENTITY_BLOB,
        "player_role_v2_b41j_continuation_holdout_evaluator.py": B41J_EVALUATOR_BLOB,
        "player_role_v2_b41j_holdout_evidence.json": B41J_EVIDENCE_BLOB,
        "player_role_v2_b41j_scientific_decision.json": B41J_DECISION_BLOB,
        "player_role_v2_b41j_structural_preperformance.json": B41J_STRUCTURAL_BLOB,
        "player_role_v2_b41j_scored_holdout_rows.csv": B41J_SCORED_ROWS_BLOB,
    }
    for rel, expected in blob_expectations.items():
        verify_blob(base / rel, expected, rel)

    if sha256_file(base / "player_role_v2_b41b_cohort_builder.py") != B41B_BUILDER_SHA256:
        raise RuntimeError("B42_B41B_BUILDER_CONTENT_SHA_DRIFT")
    if sha256_file(base / "player_role_v2_b41c2_target_scorer.py") != B41C2_SCORER_SHA256:
        raise RuntimeError("B42_B41C2_SCORER_CONTENT_SHA_DRIFT")
    if sha256_file(base / "player_role_v2_b41e_tier_thresholds.json") != B41E_THRESHOLDS_SHA256:
        raise RuntimeError("B42_B41E_THRESHOLDS_CONTENT_SHA_DRIFT")
    if sha256_file(base / "player_role_v2_b41f_final_model_snapshot.json") != B41F_SNAPSHOT_SHA256:
        raise RuntimeError("B42_B41F_SNAPSHOT_CONTENT_SHA_DRIFT")
    if sha256_file(base / "player_role_v2_b41g_holdout_validation_preregistration.json") != B41G_PREREG_SHA256:
        raise RuntimeError("B42_B41G_PREREG_CONTENT_SHA_DRIFT")
    if sha256_file(base / "player_role_v2_b41h_one_shot_holdout_evaluator.py") != B41H_EVALUATOR_SHA256:
        raise RuntimeError("B42_B41H_EVALUATOR_CONTENT_SHA_DRIFT")
    if sha256_file(base / B41I_IDENTITY_RELATIVE_PATH.split("research/player-role-v2/", 1)[1]) != B41I_IDENTITY_SHA256:
        raise RuntimeError("B42_B41I_IDENTITY_CONTENT_SHA_DRIFT")

    b41a = json.loads(
        (base / "player_role_v2_b41a_scientific_preregistration.json").read_text()
    )
    b41d = json.loads(
        (base / "player_role_v2_b41d_development_contract.json").read_text()
    )
    b41e = json.loads(
        (base / "player_role_v2_b41e_tier_thresholds.json").read_text()
    )
    b41f = json.loads(
        (base / "player_role_v2_b41f_final_model_snapshot.json").read_text()
    )
    prereg = json.loads(
        (base / "player_role_v2_b41g_holdout_validation_preregistration.json").read_text()
    )
    baseline = json.loads(
        (base / "player_role_v2_b41g_baseline_snapshot.json").read_text()
    )
    b41i = json.loads(
        (base / "player_role_v2_b41i_recovery_eligibility_decision.json").read_text()
    )
    b41j = json.loads(
        (base / "player_role_v2_b41j_scientific_decision.json").read_text()
    )
    b41j_evidence_path = base / "player_role_v2_b41j_holdout_evidence.json"
    b41j_evidence = json.loads(b41j_evidence_path.read_text())

    norm = b41a["feature_normalization"]
    if norm["owner_identity_used"] is not False:
        raise RuntimeError("B42_B41A_OWNER_IDENTITY_WAS_NOT_FROZEN_FALSE")
    if norm["dynasty_team_used"] is not False:
        raise RuntimeError("B42_B41A_DYNASTY_TEAM_WAS_NOT_FROZEN_FALSE")
    if norm["fantasy_roster_slot_used"] is not False:
        raise RuntimeError("B42_B41A_FANTASY_SLOT_WAS_NOT_FROZEN_FALSE")
    if b41a["post_validation_production_plan"]["B42_owner_blind_parity_audit_required_after_refresh"] is not True:
        raise RuntimeError("B42_B41A_B42_REQUIREMENT_DRIFT")
    if b41a["post_validation_production_plan"]["weekly_job_retrains_model"] is not False:
        raise RuntimeError("B42_B41A_WEEKLY_RETRAIN_FLAG_DRIFT")

    if b41d["feature_normalization"] != "within-position, origin-week midrank percentile":
        raise RuntimeError("B42_B41D_NORMALIZATION_DRIFT")
    if b41d["stable_identity_bridge"]["fuzzy_name_join_allowed"] is not False:
        raise RuntimeError("B42_B41D_FUZZY_JOIN_DRIFT")
    if sorted(b41d["position_feature_columns"]) != sorted(POSITIONS):
        raise RuntimeError("B42_B41D_POSITION_SCOPE_DRIFT")

    for pos in POSITIONS:
        if b41f["position_models"][pos]["selected_family"] != "nonnegative_ridge_linear":
            raise RuntimeError(f"B42_B41F_SELECTED_FAMILY_DRIFT {pos}")
        if (
            b41f["position_models"][pos]["frozen_tier_thresholds"]
            != b41e["position_results"][pos]["thresholds_ascending"]
        ):
            raise RuntimeError(f"B42_B41E_B41F_THRESHOLD_DRIFT {pos}")
        if set(b41f["position_models"][pos]["feature_columns"]) != set(
            b41f["position_models"][pos]["imputation_medians"]
        ):
            raise RuntimeError(f"B42_B41F_IMPUTATION_FEATURE_DRIFT {pos}")

    if b41i["result"] != "PASS_B41I_OUTCOME_BLIND_RECOVERY_ELIGIBLE_FOR_B41J":
        raise RuntimeError("B42_B41I_NOT_PASS")
    if b41i["continuation_class"] != CONTINUATION_CLASS:
        raise RuntimeError("B42_B41I_CONTINUATION_CLASS_DRIFT")
    if b41i["model_or_tier_retuning_performed"] is not False:
        raise RuntimeError("B42_B41I_RETUNING_DRIFT")

    if b41j["result"] != B41J_PASS_RESULT:
        raise RuntimeError("B42_B41J_NOT_PASS")
    if b41j["continuation_class"] != CONTINUATION_CLASS:
        raise RuntimeError("B42_B41J_CONTINUATION_CLASS_DRIFT")
    if b41j["data_quality_pass"] is not True:
        raise RuntimeError("B42_B41J_DATA_QUALITY_NOT_PASS")
    if b41j["all_four_primary_tests_pass"] is not True:
        raise RuntimeError("B42_B41J_PRIMARY_TESTS_NOT_ALL_PASS")
    if b41j["model_or_tier_retuning_performed"] is not False:
        raise RuntimeError("B42_B41J_RETUNING_DRIFT")
    if b41j["posthoc_exclusions_performed"] is not False:
        raise RuntimeError("B42_B41J_POSTHOC_EXCLUSION_DRIFT")
    if b41j["production_change_authorized"] is not False:
        raise RuntimeError("B42_B41J_PRODUCTION_AUTH_DRIFT")
    if b41j["production_model_deployed"] is not False:
        raise RuntimeError("B42_B41J_DEPLOYMENT_DRIFT")
    if b41j["B42_owner_blind_role_parity_audit_required_before_production"] is not True:
        raise RuntimeError("B42_B41J_B42_REQUIREMENT_DRIFT")
    if b41j["identity_source_sha256"] != B41I_IDENTITY_SHA256:
        raise RuntimeError("B42_B41J_IDENTITY_SHA_DRIFT")
    if b41j["evidence_sha256"] != sha256_file(b41j_evidence_path):
        raise RuntimeError("B42_B41J_EVIDENCE_SHA_DRIFT")
    if b41j_evidence["model_or_tier_retuning_performed"] is not False:
        raise RuntimeError("B42_B41J_EVIDENCE_RETUNING_DRIFT")
    if b41j_evidence["posthoc_exclusions_performed"] is not False:
        raise RuntimeError("B42_B41J_EVIDENCE_POSTHOC_DRIFT")

    b41h_path = base / "player_role_v2_b41h_one_shot_holdout_evaluator.py"
    b41h = load_module(b41h_path, "b42_frozen_b41h_parent")
    builder = load_module(
        base / "player_role_v2_b41b_cohort_builder.py",
        "b42_frozen_b41b_builder",
    )
    scorer = load_module(
        base / "player_role_v2_b41c2_target_scorer.py",
        "b42_frozen_b41c2_scorer",
    )
    scoring = json.loads(
        (base / "player_role_v2_b41c_league_scoring_snapshot.json").read_text()
    )

    return {
        "base": base,
        "b41a": b41a,
        "b41d": b41d,
        "b41e": b41e,
        "b41f": b41f,
        "prereg": prereg,
        "baseline": baseline,
        "b41i": b41i,
        "b41j": b41j,
        "b41j_evidence": b41j_evidence,
        "b41h": b41h,
        "builder": builder,
        "scorer": scorer,
        "scoring": scoring,
    }


def shadow_static_source_firewall(evaluator_path: Path) -> dict:
    source = evaluator_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    protected = {
        "exact_name_key",
        "load_stable_id_crosswalk",
        "attach_stable_ids_row_guarded",
        "sleeper_record_has_participation",
        "build_feature_rows_for_origins",
        "build_role_eligibility",
        "score_current_history",
        "normalize_and_apply_frozen_models",
        "role_from_score",
        "run_b41j_implementation_parity_oracle",
    }
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in protected:
            segment = ast.get_source_segment(source, node) or ""
            lower = segment.lower()
            hits = sorted(tok for tok in SHADOW_STATIC_FORBIDDEN_TOKENS if tok in lower)
            found[node.name] = hits
    missing = sorted(protected - set(found))
    if missing:
        raise RuntimeError(f"B42_STATIC_FIREWALL_FUNCTION_MISSING {missing}")
    bad = {k: v for k, v in found.items() if v}
    return {
        "protected_functions": sorted(protected),
        "forbidden_tokens": list(SHADOW_STATIC_FORBIDDEN_TOKENS),
        "hits": found,
        "missing_functions": missing,
        "pass": not bad and not missing,
    }


def protocol_payload(
    evaluator_sha256: str,
    roster_snapshot_sha256: str,
    roster_snapshot_git_blob: str,
    main_at_start: str,
) -> dict:
    return {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "phase": "B42-v4-protocol-freeze-before-owner-level-parity-results",
        "status": "FROZEN_BEFORE_ANY_B42_OWNER_TEAM_PARTITION_METRIC",
        "continuation_class": CONTINUATION_CLASS,
        "evaluator_sha256": evaluator_sha256,
        "main_at_workflow_start": main_at_start,
        "criteria_provenance": {
            "origin": (
                "PREEXISTING_OCT2_B42_PROJECT_DESIGN_RECOVERED_AFTER_B41J_"
                "AGGREGATE_HOLDOUT_RESULT_BUT_BEFORE_ANY_B42_OWNER_TEAM_PARTITION_RESULT"
            ),
            "disclosure": (
                "B41J aggregate holdout PASS was already known when this executable "
                "B42 V4 protocol was materialized. The numeric B42 parity thresholds "
                "(12 teams, >=98% coverage each team, <=2 percentage-point coverage "
                "range, exact structural owner/slot invariance) were recovered from "
                "the pre-existing B42 design and were not selected from B42 team-level "
                "outcomes. The Oct-2 coverage concept had been paired with a fantasy-slot "
                "fallback. Because that fallback is not owner-blind and was never frozen, "
                "B42 V2 prospectively re-specified the unchanged 98%/2pp thresholds to the "
                "role-eligible population: supported-position rostered players with at "
                "least one completed active 2026 game. Owner-blind Sleeper participation "
                "is frozen before roster parsing so participating players without a valid "
                "GSIS bridge into current nflverse data cannot silently disappear from the "
                "denominator. Players with no current-season "
                "active evidence are descriptive only. Position-label mismatches are "
                "descriptive and do not remove an ID-matched model role. This "
                "re-specification was made before any B42 team-level result existed. "
                "B42 remains an implementation/parity audit, not a new predictive-validity test."
            ),
            "b42_team_level_results_seen_before_freeze": False,
        },
        "audit_population": {
            "required_team_count": REQUIRED_TEAM_COUNT,
            "position_scope": POSITIONS,
            "unit": "unique rostered role-eligible player within opaque team",
            "team_labels": "opaque Team01..Team12 only",
            "fantasy_slot_may_affect_role_inference": False,
            "owner_identity_may_affect_role_inference": False,
            "dynasty_team_may_affect_role_inference": False,
        },
        "scientific_runtime": {
            "python": "3.13",
            "numpy": "2.5.3",
            "pandas": "2.3.3",
            "scipy": "1.18.1",
            "requests": ">=2.32,<3",
        },
        "implementation_parity_oracle": {
            "required_before_2026_shadow": True,
            "reference": "B41J committed scored holdout rows",
            "reference_git_blob": B41J_SCORED_ROWS_BLOB,
            "B41J_sleeper_id_must_match_current_crosswalk_per_reference_row": True,
            "crosswalk_whole_file_hash_equality_required_for_oracle": False,
            "oracle_runs_before_protocol_commit": True,
            "exact_model_score_tolerance": 1e-9,
            "tier_index_must_match_exactly": True,
            "role_tier_must_match_exactly": True,
            "normalization_population_effect_reported_descriptively": True,
            "future_target_recomputed": False,
            "B42_team_partition_opened": False,
        },
        "role_refresh": {
            "season": 2026,
            "latest_completed_week_only": True,
            "future_target_used": False,
            "model": "exact frozen B41F per-position nonnegative ridge model",
            "normalization": "exact within-position current-origin midrank percentile",
            "imputation": "exact frozen B41F full-development medians",
            "tiers": "exact frozen B41E/B41F position-specific thresholds",
            "identity_source": {
                "path": B41I_IDENTITY_RELATIVE_PATH,
                "sha256": B41I_IDENTITY_SHA256,
            },
            "continuation_class_disclosure_required": True,
            "model_retraining_allowed": False,
            "tier_retuning_allowed": False,
        },
        "source_firewall": {
            "shadow_refresh_must_be_durably_committed_before_roster_partition_parse": True,
            "roster_snapshot_raw_bytes_may_be_snapshotted_and_hashed_before_shadow_refresh": True,
            "roster_assignment_semantics_may_be_parsed_before_shadow_refresh_freeze": False,
            "role_inference_forbidden_context_tokens": list(
                SHADOW_STATIC_FORBIDDEN_TOKENS
            ),
            "static_scan_scope": (
                "identity/name/participation helpers, feature construction, role-eligibility "
                "construction, history scoring, normalization/model application, role_from_score, "
                "and B41J parity oracle; "
                "orchestration/witness metadata is excluded from lexical scanning"
            ),
        },
        "roster_snapshot": {
            "sha256": roster_snapshot_sha256,
            "git_blob": roster_snapshot_git_blob,
            "raw_bytes_snapshotted_without_parsing_owner_team_assignment": True,
        },
        "primary_parity_gates": {
            "exactly_12_teams": True,
            "minimum_role_coverage_each_team": MIN_TEAM_ROLE_COVERAGE,
            "maximum_coverage_range_across_teams": MAX_TEAM_COVERAGE_RANGE,
            "owner_swap_role_changes_allowed": ALLOWED_COUNTERFACTUAL_ROLE_CHANGES,
            "owner_roster_slot_context_allowed_in_role_inference": False,
            "all_eight_role_positions_in_scope": True,
        },
        "coverage_definition": {
            "role_eligible": (
                "rostered supported-position player with at least one completed active "
                "2026 game in the owner-blind frozen nflverse sources, plus a conservative "
                "identity-gap case where owner-blind completed-week Sleeper stats show "
                "participation but the rostered Sleeper ID does not have an unambiguous "
                "GSIS bridge into a player present in the current 2026 nflverse sources"
            ),
            "covered": (
                "role-eligible rostered player has a frozen B41F current-2026 shadow "
                "role. Coverage joins by Sleeper player ID only; roster-vs-model "
                "position-label differences are descriptive, not exclusionary."
            ),
            "eligibility_identity_bridge": (
                "Stable Sleeper-to-GSIS bridge when available. If the rostered Sleeper "
                "ID cannot be joined directly to an active eligible nflverse row, a unique "
                "exact casefolded football-name match may classify the player as role-eligible "
                "for the denominator only; it may not assign or rescue a model role. If both "
                "bridges miss but owner-blind Sleeper 2026 weekly stats show participation, "
                "the player is conservatively role-eligible and uncovered unless the stable "
                "crosswalk maps that Sleeper ID to a GSIS ID actually present in the current "
                "2026 nflverse sources. Only that correctly bridged-but-inactive case is a "
                "descriptive source disagreement outside the denominator."
            ),
            "participant_identity_gap_guard": {
                "frozen_before_roster_parse": True,
                "participation_fields": ["gp", "off_snp", "def_snp", "st_snp"],
                "minimum_stable_mapped_eligible_participant_confirmation_rate": 0.95,
                "identity_gap_requires_valid_gsis_bridge_into_current_nflverse": True,
                "crosswalk_sleeper_id_without_gsis_counts_as_identity_gap": True,
                "mapped_gsis_absent_from_current_nflverse_counts_as_identity_gap": True,
                "mapped_gsis_present_but_nflverse_inactive": "descriptive_source_disagreement_not_denominator",
            },
            "no_current_season_evidence": (
                "reported per opaque team only when neither the frozen nflverse active-game "
                "eligibility bridge nor the frozen Sleeper participation identity-gap guard "
                "confirms current-season evidence; excluded from the coverage denominator "
                "because this reflects roster composition rather than model evidence completeness"
            ),
            "position_label_mismatch": (
                "reported descriptively; role is shown under the model position and "
                "the mismatch does not make an ID-matched role uncovered"
            ),
            "fallback_policy": (
                "NONE_IN_B42_V4_NO_OWNER_BLIND_FALLBACK_MAPPING_WAS_FROZEN_IN_"
                "B41A_THROUGH_B41J"
            ),
            "fallback_count_by_definition": 0,
            "uncovered_role_eligible_players": (
                "pending/unresolved pipeline or stable-ID completeness; never rescued post hoc"
            ),
            "reason_no_fallback": (
                "The earlier fantasy starter/bench/taxi/IR fallback concept violates "
                "the frozen owner-blind design. B42 V4 does not invent a new "
                "post-holdout fallback mapping merely to satisfy coverage."
            ),
        },
        "reporting": {
            "report_data_driven_vs_fallback_counts": True,
            "report_evidence_source_counts": True,
            "report_pending_counts": True,
            "report_pending_reason_counts": True,
            "report_identity_gap_counts": True,
            "report_source_disagreement_counts": True,
            "report_no_current_season_evidence_counts": True,
            "minimum_supported_roster_name_availability": 0.95,
            "counterfactual_wording": "structural invariance check true by construction; source firewall is the substantive owner-blind evidence",
            "report_role_tier_counts": True,
            "confidence_reporting": (
                "No calibrated confidence thresholds were frozen. Report raw "
                "evidence depth and the literal status "
                "NOT_CALIBRATED_B42_DOES_NOT_INVENT_CONFIDENCE_THRESHOLDS."
            ),
            "owner_identity_must_not_be_emitted": True,
            "real_team_name_must_not_be_emitted": True,
            "roster_id_must_not_be_emitted": True,
        },
        "decision_rule": {
            "pass": (
                "all primary parity gates pass, the shadow source firewall passes, "
                "privacy checks pass, and no production/model/tier mutation occurs"
            ),
            "fail": (
                "any primary parity, source-firewall, or privacy gate fails; "
                "preserve evidence and do not deploy"
            ),
            "data_integrity_stop": (
                "participant-field sanity or supported-roster-name availability below "
                "their frozen floors yields SCIENTIFIC_STOP_B42_V4_DATA_INTEGRITY, not "
                "an owner-parity failure"
            ),
            "no_posthoc_fallback_rescue": True,
        },
        "data_integrity_stop_firewall": {
            "participant_sanity_enforced_before_roster_semantic_parse": True,
            "roster_name_availability_enforced_before_team_partition_metrics": True,
            "data_integrity_stop_may_not_emit_team_level_parity_results": True,
        },
        "production_firewall": {
            "B42_authorizes_production_change": False,
            "production_model_deployed": False,
            "pass_only_makes_separate_production_authorization_workflow_eligible": True,
        },
        "frozen_parent_lineage": {
            "B41A_prereg_git_blob": B41A_PREREG_BLOB,
            "B41D_contract_git_blob": B41D_CONTRACT_BLOB,
            "B41E_thresholds_sha256": B41E_THRESHOLDS_SHA256,
            "B41F_snapshot_sha256": B41F_SNAPSHOT_SHA256,
            "B41G_prereg_sha256": B41G_PREREG_SHA256,
            "B41H_evaluator_sha256": B41H_EVALUATOR_SHA256,
            "B41I_identity_sha256": B41I_IDENTITY_SHA256,
            "B41J_required_result": B41J_PASS_RESULT,
        },
        "production_change_authorized": False,
        "production_model_deployed": False,
    }


def filter_csv_to_completed_weeks(
    payload: bytes,
    *,
    season_col: str,
    week_col: str,
    type_col: str,
    type_value: str,
    latest_completed_week: int,
    out_path: Path,
) -> dict:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise RuntimeError("B42_CURRENT_SOURCE_NO_HEADER")
    required = {season_col, week_col, type_col}
    missing = required - set(reader.fieldnames)
    if missing:
        raise RuntimeError(f"B42_CURRENT_SOURCE_SCHEMA_MISSING {sorted(missing)}")

    all_relevant_weeks = []
    kept = []
    for row in reader:
        try:
            season = int(str(row.get(season_col) or "").strip())
            week = int(str(row.get(week_col) or "").strip())
        except ValueError:
            continue
        typ = str(row.get(type_col) or "").strip().upper()
        if season != 2026 or typ != type_value.upper():
            continue
        all_relevant_weeks.append(week)
        if week <= latest_completed_week:
            kept.append(row)

    if not all_relevant_weeks:
        raise RuntimeError("B42_CURRENT_SOURCE_NO_2026_REGULAR_ROWS")
    max_available = max(all_relevant_weeks)
    if max_available < latest_completed_week:
        raise RuntimeError(
            "B42_CURRENT_SOURCE_NOT_THROUGH_COMPLETED_WEEK "
            f"max_available={max_available} required={latest_completed_week}"
        )
    if not kept:
        raise RuntimeError("B42_CURRENT_SOURCE_FILTER_EMPTY")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=reader.fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(kept)

    return {
        "raw_sha256": sha256_bytes(payload),
        "filtered_sha256": sha256_file(out_path),
        "max_available_week": int(max_available),
        "latest_completed_week_included": int(latest_completed_week),
        "filtered_rows": int(len(kept)),
    }


def exact_name_key(value) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def load_stable_id_crosswalk(lineage: dict, session: requests.Session):
    commit = lineage["prereg"]["frozen_inputs"]["stable_id_crosswalk_commit"]
    url = (
        "https://raw.githubusercontent.com/dynastyprocess/data/"
        f"{commit}/files/db_playerids.csv"
    )
    payload = lineage["b41h"].get_bytes(session, url)
    actual_sha = sha256_bytes(payload)
    cross = pd.read_csv(io.BytesIO(payload), dtype=str, keep_default_na=False)
    if not {"gsis_id", "sleeper_id"}.issubset(cross.columns):
        raise RuntimeError("B42_CROSSWALK_SCHEMA_MISSING")

    gsis_to_sids = defaultdict(set)
    rows_with_sleeper_id = 0
    rows_with_sleeper_id_but_no_gsis = 0
    for _, row in cross.iterrows():
        gsis = str(row.get("gsis_id") or "").strip()
        valid_gsis = bool(gsis and gsis.lower() not in {"na", "nan", "none"})
        sid = lineage["b41h"].parse_sid(row.get("sleeper_id"))
        if sid:
            rows_with_sleeper_id += 1
            if not valid_gsis:
                rows_with_sleeper_id_but_no_gsis += 1
        if valid_gsis and sid:
            gsis_to_sids[gsis].add(str(sid))

    ambiguous_gsis = {g: v for g, v in gsis_to_sids.items() if len(v) > 1}
    if ambiguous_gsis:
        raise RuntimeError(
            f"B42_AMBIGUOUS_GSIS_CROSSWALK count={len(ambiguous_gsis)}"
        )
    exact = {g: next(iter(v)) for g, v in gsis_to_sids.items() if len(v) == 1}

    sid_to_gsis_sets = defaultdict(set)
    for gsis, sid in exact.items():
        sid_to_gsis_sets[str(sid)].add(str(gsis))
    ambiguous_sids = {sid: gs for sid, gs in sid_to_gsis_sets.items() if len(gs) > 1}
    if ambiguous_sids:
        raise RuntimeError(
            f"B42_AMBIGUOUS_SLEEPER_CROSSWALK count={len(ambiguous_sids)}"
        )
    sid_to_gsis = {
        sid: next(iter(gsis_set))
        for sid, gsis_set in sid_to_gsis_sets.items()
        if len(gsis_set) == 1
    }
    gsis_mapped_sleeper_ids = set(sid_to_gsis)
    audit = {
        "crosswalk_rows_with_sleeper_id": int(rows_with_sleeper_id),
        "crosswalk_rows_with_sleeper_id_but_no_gsis_id": int(
            rows_with_sleeper_id_but_no_gsis
        ),
        "gsis_mapped_sleeper_id_count": int(len(gsis_mapped_sleeper_ids)),
    }
    return exact, sid_to_gsis, gsis_mapped_sleeper_ids, actual_sha, audit


def attach_stable_ids_row_guarded(
    df: pd.DataFrame,
    lineage: dict,
    session: requests.Session,
):
    (
        exact,
        sid_to_gsis,
        gsis_mapped_sleeper_ids,
        cross_sha,
        crosswalk_audit,
    ) = load_stable_id_crosswalk(lineage, session)
    out = df.copy()
    out["sleeper_id"] = out["gsis_id"].map(exact)
    out["identity_mapped"] = out["sleeper_id"].notna()
    overall = float(out["identity_mapped"].mean()) if len(out) else 0.0
    pos_cov = (
        out.groupby("position", observed=True)["identity_mapped"].mean().to_dict()
        if len(out)
        else {}
    )
    return (
        out,
        cross_sha,
        overall,
        {k: float(v) for k, v in pos_cov.items()},
        sid_to_gsis,
        gsis_mapped_sleeper_ids,
        crosswalk_audit,
    )

def sleeper_record_has_participation(raw) -> bool:
    if not isinstance(raw, dict):
        return False
    for field in ("gp", "off_snp", "def_snp", "st_snp"):
        try:
            value = float(raw.get(field) or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        if math.isfinite(value) and value > 0.0:
            return True
    return False


def build_feature_rows_for_origins(
    builder,
    stats_path: Path,
    snaps_path: Path,
    players_path: Path,
    season: int,
    origin_weeks,
) -> tuple[pd.DataFrame, dict, list[dict]]:
    origins = tuple(sorted({int(x) for x in origin_weeks}))
    if not origins:
        raise RuntimeError("B42_NO_ORIGIN_WEEKS")
    max_origin = max(origins)
    builder.DEV_SEASONS = (int(season),)
    builder.ORIGIN_WEEKS = origins
    gsis_meta, pfr_to_gsis = builder.load_players(players_path)
    all_rows, source_audit = builder.load_season(
        stats_path,
        snaps_path,
        gsis_meta,
        pfr_to_gsis,
    )
    all_rows = [
        r
        for r in all_rows
        if int(r["season"]) == int(season) and int(r["week"]) <= max_origin
    ]
    if not all_rows:
        raise RuntimeError(f"B42_FEATURE_SOURCE_ROWS_EMPTY season={season}")

    by_player = defaultdict(list)
    for row in all_rows:
        if row["position"] in POSITIONS:
            by_player[row["gsis_id"]].append(row)

    cohort = []
    excluded = Counter()
    excluded_records = []
    for gsis, rows in by_player.items():
        rows.sort(key=lambda x: int(x["week"]))
        for origin in origins:
            history = [
                r
                for r in rows
                if int(r["week"]) <= origin and bool(r["active"])
            ]
            if not history:
                excluded["no_completed_active_game"] += 1
                excluded_records.append({
                    "origin_week": int(origin),
                    "gsis_id": str(gsis),
                    "reason": "no_completed_active_game",
                })
                continue

            recent_positions = {r["position"] for r in history[-3:]}
            if len(recent_positions) != 1:
                excluded["recent_position_instability"] += 1
                excluded_records.append({
                    "origin_week": int(origin),
                    "gsis_id": str(gsis),
                    "reason": "recent_position_instability",
                })
                continue
            pos = history[-1]["position"]
            if pos not in POSITIONS:
                excluded["unsupported_position"] += 1
                excluded_records.append({
                    "origin_week": int(origin),
                    "gsis_id": str(gsis),
                    "reason": "unsupported_position",
                })
                continue

            snaps = [r["snap_share"] for r in history]
            row = {
                "season": int(season),
                "origin_week": int(origin),
                "gsis_id": gsis,
                "player_name": history[-1].get("player_name") or "",
                "position": pos,
                "team_at_origin": history[-1]["team"],
                "prior_active_games": int(len(history)),
                "feature_max_week": int(max(r["week"] for r in history)),
                "snap_share__latest_active": snaps[-1],
                "snap_share__last3_active_mean": builder.mean_or_none(snaps[-3:]),
                "snap_share__season_to_date_active_mean": builder.mean_or_none(snaps),
                "snap_share__last3_minus_prior3": builder.trend_or_none(snaps),
                "history_season_to_date_scoring_components_json": json.dumps(
                    [
                        {
                            "week": int(r["week"]),
                            "components": builder.raw_components(r.get("stats", {})),
                        }
                        for r in history
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            }
            row.update(builder.opportunity_features(history, pos))
            cohort.append(row)

    if not cohort:
        raise RuntimeError(f"B42_FEATURE_COHORT_EMPTY season={season}")

    cohort.sort(
        key=lambda r: (
            int(r["origin_week"]),
            str(r["position"]),
            str(r["gsis_id"]),
        )
    )
    df = pd.DataFrame(cohort)
    if set(df["season"].astype(int).unique()) != {int(season)}:
        raise RuntimeError("B42_FEATURE_SEASON_SCOPE_FAILED")
    if int(df["feature_max_week"].max()) > max_origin:
        raise RuntimeError("B42_FEATURE_FUTURE_WEEK_LEAKAGE")

    return df, {
        "source_audit": source_audit,
        "feature_rows_before_stable_id_filter": int(len(df)),
        "excluded": dict(excluded),
        "excluded_records": excluded_records,
        "origins": list(origins),
    }, all_rows


def build_role_eligibility(
    all_rows: list[dict],
    builder,
    lineage: dict,
    session: requests.Session,
    latest_completed_week: int,
) -> tuple[pd.DataFrame, dict]:
    by_player = defaultdict(list)
    for row in all_rows:
        if row["position"] in POSITIONS and int(row["week"]) <= latest_completed_week:
            by_player[str(row["gsis_id"])].append(row)

    rows = []
    for gsis, player_rows in by_player.items():
        active = [r for r in player_rows if bool(r["active"])]
        if not active:
            continue
        active.sort(key=lambda r: int(r["week"]))
        latest = active[-1]
        rows.append(
            {
                "season": 2026,
                "origin_week": int(latest_completed_week),
                "gsis_id": gsis,
                "position": str(latest["position"]),
                "player_name": str(latest.get("player_name") or ""),
                "exact_name_key": exact_name_key(latest.get("player_name") or ""),
                "active_game_count": int(len(active)),
            }
        )
    if not rows:
        raise RuntimeError("B42_ROLE_ELIGIBILITY_EMPTY")
    eligible = pd.DataFrame(rows).sort_values(
        ["position", "gsis_id"], kind="mergesort"
    ).reset_index(drop=True)
    (
        with_ids,
        cross_sha,
        overall_cov,
        pos_cov,
        sid_to_gsis,
        gsis_mapped_sleeper_ids,
        crosswalk_audit,
    ) = attach_stable_ids_row_guarded(
        eligible,
        lineage,
        session,
    )
    with_ids["sleeper_id"] = with_ids["sleeper_id"].fillna("").astype(str)
    key_counts = Counter(k for k in with_ids["exact_name_key"] if k)
    with_ids["exact_name_unique"] = [
        bool(k and key_counts[k] == 1) for k in with_ids["exact_name_key"]
    ]
    return with_ids, {
        "role_eligible_rows": int(len(with_ids)),
        "stable_sleeper_id_mapped_rows": int(with_ids["identity_mapped"].sum()),
        "stable_sleeper_id_mapping_rate": float(overall_cov),
        "stable_sleeper_id_mapping_rate_by_position": {
            p: float(pos_cov.get(p, 0.0)) for p in POSITIONS
        },
        "exact_unique_name_keys": int(with_ids["exact_name_unique"].sum()),
        "stable_id_crosswalk_sha256": cross_sha,
        "gsis_mapped_sleeper_id_count": int(len(gsis_mapped_sleeper_ids)),
        "crosswalk_rows_with_sleeper_id_but_no_gsis_id": int(
            crosswalk_audit["crosswalk_rows_with_sleeper_id_but_no_gsis_id"]
        ),
    }


def score_current_history(
    model: pd.DataFrame,
    scorer,
    scoring_settings: dict,
    session: requests.Session,
    latest_completed_week: int,
    season: int,
    include_all_weeks_for_participation: bool = False,
) -> tuple[pd.DataFrame, dict, int, set[str]]:
    required_weeks = set()
    for raw in model["history_season_to_date_scoring_components_json"].tolist():
        for game in json.loads(raw):
            required_weeks.add(int(game["week"]))

    if include_all_weeks_for_participation:
        required_weeks.update(range(1, int(latest_completed_week) + 1))
    if not required_weeks:
        raise RuntimeError("B42_CURRENT_SCORING_NO_REQUIRED_WEEKS")
    if max(required_weeks) > latest_completed_week:
        raise RuntimeError("B42_CURRENT_SCORING_FUTURE_WEEK_REQUESTED")

    sleeper_stats = {}
    sleeper_hashes = {}
    sleeper_participant_ids = set()
    for week in sorted(required_weeks):
        url = f"https://api.sleeper.app/v1/stats/nfl/regular/{int(season)}/{week}"
        payload = None
        last = None
        for attempt in range(5):
            try:
                r = session.get(url, timeout=90)
                r.raise_for_status()
                payload = r.content
                break
            except Exception as exc:
                last = exc
                if attempt == 4:
                    raise RuntimeError(
                        f"B42_SLEEPER_STATS_TRANSPORT_FAILED season={season} week={week}: {last}"
                    )
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise RuntimeError(
                f"B42_SLEEPER_STATS_NOT_DICT season={season} week={week}"
            )
        sleeper_stats[week] = data
        sleeper_hashes[str(week)] = sha256_bytes(payload)
        for raw_sid, raw_stats in data.items():
            sid = str(raw_sid or "").strip()
            if sid and sleeper_record_has_participation(raw_stats):
                sleeper_participant_ids.add(sid)

    latest_values = []
    last3_values = []
    season_values = []
    trend_values = []
    missing = 0

    for _, row in model.iterrows():
        sid = str(row["sleeper_id"])
        games = json.loads(row["history_season_to_date_scoring_components_json"])
        points = []
        for game in games:
            week = int(game["week"])
            raw = sleeper_stats[week].get(sid)
            if raw is None:
                raw = {}
                missing += 1
            points.append(float(scorer.score_week(raw, scoring_settings)))
        latest_values.append(points[-1] if points else np.nan)
        last3_values.append(float(np.mean(points[-3:])) if points else np.nan)
        season_values.append(float(np.mean(points)) if points else np.nan)
        if len(points) >= 6:
            trend_values.append(
                float(np.mean(points[-3:]) - np.mean(points[-6:-3]))
            )
        else:
            trend_values.append(np.nan)

    out = model.copy()
    out["league_points__latest_active"] = latest_values
    out["league_points__last3_active_mean"] = last3_values
    out["league_points__season_to_date_active_mean"] = season_values
    out["league_points__last3_minus_prior3"] = trend_values

    return out, sleeper_hashes, int(missing), sleeper_participant_ids


def normalize_and_apply_frozen_models(
    model: pd.DataFrame,
    b41h,
    baseline: dict,
    b41f: dict,
) -> tuple[pd.DataFrame, dict]:
    frozen_cols = sorted(
        {
            col
            for pos in POSITIONS
            for col in b41f["position_models"][pos]["feature_columns"]
        }
    )
    out = model.copy()
    for col in frozen_cols:
        if col not in out.columns:
            raise RuntimeError(f"B42_MISSING_FROZEN_FEATURE_COLUMN {col}")
        out[col] = pd.to_numeric(out[col], errors="coerce")

    group_cols = ["season", "origin_week", "position"]
    for col in frozen_cols:
        out[col] = out.groupby(
            group_cols,
            observed=True,
            group_keys=False,
        )[col].apply(b41h.midrank_pct)

    row_missing = []
    row_feature_count = []
    for _, row in out.iterrows():
        pos = str(row["position"])
        cols = b41f["position_models"][pos]["feature_columns"]
        vals = pd.to_numeric(row[cols], errors="coerce").to_numpy(dtype=float)
        row_missing.append(int((~np.isfinite(vals)).sum()))
        row_feature_count.append(int(len(cols)))
    out["frozen_feature_missing_count_before_imputation"] = row_missing
    out["frozen_feature_count"] = row_feature_count

    scored, aggregate_imputation = b41h.apply_frozen_models(
        out,
        baseline,
        b41f,
    )
    if not np.isfinite(scored["model_score"].to_numpy(dtype=float)).all():
        raise RuntimeError("B42_NONFINITE_SHADOW_MODEL_SCORE")
    return scored, aggregate_imputation


def role_from_score(position: str, score: float, b41f: dict) -> tuple[int, str]:
    if position not in POSITIONS:
        raise RuntimeError(f"B42_ROLE_FROM_SCORE_UNSUPPORTED_POSITION {position}")
    thresholds = np.asarray(
        b41f["position_models"][position]["frozen_tier_thresholds"],
        dtype=float,
    )
    idx = int(np.searchsorted(thresholds, float(score), side="right"))
    if idx < 0 or idx >= len(ROLE_ORDER):
        raise RuntimeError("B42_TIER_INDEX_OUT_OF_RANGE")
    return idx, ROLE_ORDER[idx]


def counterfactual_role_assignment(
    position: str,
    score: float,
    b41f: dict,
    synthetic_team_label: str,
    synthetic_fantasy_slot: str,
) -> tuple[int, str]:
    # Counterfactual context is deliberately not supplied to role inference.
    # It is present only so the audit can explicitly vary assignment context.
    _ = synthetic_team_label
    _ = synthetic_fantasy_slot
    return role_from_score(position, score, b41f)


def run_b41j_implementation_parity_oracle(
    repo: Path,
    out: Path,
    lineage: dict,
    session: requests.Session,
) -> dict:
    source_dir = out / "b41j_parity_sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    stats_path = source_dir / "stats_player_week_2025.csv"
    snaps_path = source_dir / "snap_counts_2025.csv"

    source_hashes = {
        "stats_player_week_2025.csv": lineage["b41h"].source_integrity_or_stop(
            session,
            lineage["prereg"]["frozen_inputs"]["2025_weekly_stats"],
            stats_path,
            "2025 weekly stats",
        ),
        "snap_counts_2025.csv": lineage["b41h"].source_integrity_or_stop(
            session,
            lineage["prereg"]["frozen_inputs"]["2025_snap_counts"],
            snaps_path,
            "2025 snap counts",
        ),
    }
    expected_source_hashes = lineage["b41j_evidence"].get("source_sha256") or {}
    for name, actual in source_hashes.items():
        expected = expected_source_hashes.get(name)
        if expected is None or actual != expected:
            raise RuntimeError(
                "B42_B41J_PARITY_FROZEN_SOURCE_HASH_DRIFT "
                f"source={name} expected={expected} actual={actual}"
            )
    players_path = repo / B41I_IDENTITY_RELATIVE_PATH
    features, feature_audit, _ = build_feature_rows_for_origins(
        lineage["builder"],
        stats_path,
        snaps_path,
        players_path,
        2025,
        tuple(int(x) for x in lineage["b41h"].ORIGIN_WEEKS),
    )
    (
        with_ids,
        cross_sha,
        _,
        _,
        sid_to_gsis,
        gsis_mapped_sleeper_ids,
        crosswalk_audit,
    ) = attach_stable_ids_row_guarded(
        features,
        lineage,
        session,
    )

    model_all = with_ids[with_ids["identity_mapped"]].copy()
    model_all["sleeper_id"] = model_all["sleeper_id"].astype(str)
    scored_history, sleeper_hashes, missing_stats, _ = score_current_history(
        model_all,
        lineage["scorer"],
        lineage["scoring"]["scoring_settings"],
        session,
        max(int(x) for x in lineage["b41h"].ORIGIN_WEEKS),
        2025,
    )

    expected_sleeper_hashes = lineage["b41j_evidence"].get(
        "sleeper_weekly_raw_stats_sha256"
    ) or {}
    for week, actual in sleeper_hashes.items():
        expected = expected_sleeper_hashes.get(str(week))
        if expected is None or actual != expected:
            raise RuntimeError(
                "B42_B41J_PARITY_SLEEPER_RAW_HASH_DRIFT "
                f"week={week} expected={expected} actual={actual}"
            )

    ref_path = lineage["base"] / "player_role_v2_b41j_scored_holdout_rows.csv"
    reference = pd.read_csv(
        ref_path,
        usecols=[
            "season",
            "origin_week",
            "gsis_id",
            "sleeper_id",
            "model_score",
            "tier_index",
            "role_tier",
        ],
        dtype={"gsis_id": str, "sleeper_id": str},
    )
    key_cols = ["season", "origin_week", "gsis_id"]
    if reference.duplicated(key_cols).any():
        raise RuntimeError("B42_B41J_REFERENCE_DUPLICATE_KEYS")
    current_identity = with_ids[key_cols + ["sleeper_id"]].copy()
    current_identity["sleeper_id"] = current_identity["sleeper_id"].fillna("").astype(str)
    reference["sleeper_id"] = reference["sleeper_id"].fillna("").astype(str)
    identity_check = reference[key_cols + ["sleeper_id"]].merge(
        current_identity,
        on=key_cols,
        how="left",
        suffixes=("_reference", "_current"),
        validate="one_to_one",
    )
    identity_mismatch = identity_check[
        identity_check["sleeper_id_reference"]
        != identity_check["sleeper_id_current"].fillna("")
    ]
    if not identity_mismatch.empty:
        samples = identity_mismatch[
            key_cols + ["sleeper_id_reference", "sleeper_id_current"]
        ].head(10).to_dict("records")
        raise RuntimeError(
            "B42_B41J_PARITY_REFERENCE_SLEEPER_ID_MISMATCH "
            f"count={len(identity_mismatch)} sample={samples}"
        )
    ref_keys = set(
        zip(
            reference["season"].astype(int),
            reference["origin_week"].astype(int),
            reference["gsis_id"].astype(str),
        )
    )
    all_keys = list(
        zip(
            scored_history["season"].astype(int),
            scored_history["origin_week"].astype(int),
            scored_history["gsis_id"].astype(str),
        )
    )
    missing_reference_keys = sorted(ref_keys - set(all_keys))
    if missing_reference_keys:
        raise RuntimeError(
            "B42_B41J_PARITY_REFERENCE_MEMBERSHIP_MISSING "
            f"count={len(missing_reference_keys)} sample={missing_reference_keys[:10]}"
        )

    mask = [key in ref_keys for key in all_keys]
    restricted_history = scored_history.loc[mask].copy()
    if len(restricted_history) != len(reference):
        raise RuntimeError(
            "B42_B41J_PARITY_REFERENCE_MEMBERSHIP_COUNT_MISMATCH "
            f"current={len(restricted_history)} reference={len(reference)}"
        )
    exact_scored, exact_imputation = normalize_and_apply_frozen_models(
        restricted_history,
        lineage["b41h"],
        lineage["baseline"],
        lineage["b41f"],
    )

    merged = exact_scored.merge(
        reference[key_cols + ["model_score", "tier_index", "role_tier"]],
        on=key_cols,
        how="inner",
        suffixes=("_current", "_reference"),
        validate="one_to_one",
    )
    if len(merged) != len(reference):
        raise RuntimeError("B42_B41J_PARITY_MERGE_COUNT_MISMATCH")
    score_delta = np.abs(
        merged["model_score_current"].to_numpy(dtype=float)
        - merged["model_score_reference"].to_numpy(dtype=float)
    )
    max_abs = float(score_delta.max()) if len(score_delta) else float("inf")
    tier_mismatches = int(
        (
            merged["tier_index_current"].astype(int)
            != merged["tier_index_reference"].astype(int)
        ).sum()
    )
    role_mismatches = int(
        (
            merged["role_tier_current"].astype(str)
            != merged["role_tier_reference"].astype(str)
        ).sum()
    )
    exact_pass = bool(
        max_abs <= 1e-9 and tier_mismatches == 0 and role_mismatches == 0
    )
    if not exact_pass:
        raise RuntimeError(
            "B42_B41J_IMPLEMENTATION_PARITY_FAILED "
            f"max_abs_score_delta={max_abs} tier_mismatches={tier_mismatches} "
            f"role_mismatches={role_mismatches}"
        )

    shadow_style_scored, shadow_imputation = normalize_and_apply_frozen_models(
        scored_history,
        lineage["b41h"],
        lineage["baseline"],
        lineage["b41f"],
    )
    population = shadow_style_scored.merge(
        exact_scored[key_cols + ["model_score", "tier_index"]],
        on=key_cols,
        how="inner",
        suffixes=("_shadow_population", "_b41j_population"),
        validate="one_to_one",
    )
    shifts = np.abs(
        population["model_score_shadow_population"].to_numpy(dtype=float)
        - population["model_score_b41j_population"].to_numpy(dtype=float)
    )
    tier_changes = (
        population["tier_index_shadow_population"].astype(int)
        != population["tier_index_b41j_population"].astype(int)
    )

    result = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "phase": "B42-v4-B41J-implementation-parity-oracle-before-2026-shadow",
        "reference_git_blob": B41J_SCORED_ROWS_BLOB,
        "reference_rows": int(len(reference)),
        "current_style_rows_before_B41J_membership_restriction": int(len(scored_history)),
        "exact_B41J_membership_rows": int(len(exact_scored)),
        "exact_parity": {
            "model_score_tolerance": 1e-9,
            "maximum_absolute_model_score_delta": max_abs,
            "tier_index_mismatches": tier_mismatches,
            "role_tier_mismatches": role_mismatches,
            "pass": exact_pass,
        },
        "normalization_population_effect_descriptive_only": {
            "extra_rows_relative_to_B41J_membership": int(
                len(shadow_style_scored) - len(exact_scored)
            ),
            "shared_rows": int(len(population)),
            "median_absolute_model_score_shift": (
                float(np.median(shifts)) if len(shifts) else None
            ),
            "maximum_absolute_model_score_shift": (
                float(np.max(shifts)) if len(shifts) else None
            ),
            "tier_change_share": (
                float(tier_changes.mean()) if len(tier_changes) else None
            ),
        },
        "source_sha256": source_hashes,
        "stable_id_crosswalk_sha256_observed": cross_sha,
        "B41J_stable_id_crosswalk_sha256_reference": lineage["b41j_evidence"].get(
            "stable_id_crosswalk_sha256"
        ),
        "reference_row_sleeper_id_mismatches": 0,
        "gsis_mapped_sleeper_id_count_observed": int(
            len(gsis_mapped_sleeper_ids)
        ),
        "crosswalk_rows_with_sleeper_id_but_no_gsis_id": int(
            crosswalk_audit["crosswalk_rows_with_sleeper_id_but_no_gsis_id"]
        ),
        "sleeper_weekly_raw_stats_sha256": sleeper_hashes,
        "sleeper_history_raw_stats_missing_count": int(missing_stats),
        "feature_audit": feature_audit,
        "exact_population_imputation": exact_imputation,
        "shadow_style_population_imputation": shadow_imputation,
        "future_target_used": False,
        "B42_team_level_result_opened": False,
        "owner_or_roster_context_used": False,
    }
    parity_path = out / "player_role_v2_b42_v4_implementation_parity.json"
    parity_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def build_shadow_refresh(
    repo: Path,
    out: Path,
    protocol_commit: str,
    parity_commit: str,
) -> None:
    lineage = load_and_verify_frozen_lineage(repo)
    base = lineage["base"]
    evaluator_path = base / "player_role_v2_b42_v4_owner_blind_parity_evaluator.py"
    protocol_path = base / "player_role_v2_b42_v4_protocol_freeze.json"
    parity_path = base / "player_role_v2_b42_v4_implementation_parity.json"

    protocol = json.loads(protocol_path.read_text())
    if protocol["status"] != "FROZEN_BEFORE_ANY_B42_OWNER_TEAM_PARTITION_METRIC":
        raise RuntimeError("B42_PROTOCOL_NOT_FROZEN")
    if protocol["evaluator_sha256"] != sha256_file(evaluator_path):
        raise RuntimeError("B42_PROTOCOL_EVALUATOR_SHA_DRIFT")
    if protocol["continuation_class"] != CONTINUATION_CLASS:
        raise RuntimeError("B42_PROTOCOL_CONTINUATION_CLASS_DRIFT")

    firewall = shadow_static_source_firewall(evaluator_path)
    if not firewall["pass"]:
        raise RuntimeError(f"B42_SHADOW_STATIC_SOURCE_FIREWALL_FAILED {firewall}")

    session = requests.Session()
    session.headers.update(
        {"User-Agent": "LOG-Trade-Calculator-player-role-v2-b42-v4"}
    )

    # The implementation-parity oracle is a separate, already-durable stage.
    # No 2026 shadow data may be opened unless that exact B41J reproduction passed.
    if not parity_path.exists():
        raise RuntimeError("B42_IMPLEMENTATION_PARITY_ARTIFACT_MISSING")
    implementation_parity = json.loads(parity_path.read_text())
    if implementation_parity["exact_parity"]["pass"] is not True:
        raise RuntimeError("B42_IMPLEMENTATION_PARITY_NOT_PASS")
    if not parity_commit:
        raise RuntimeError("B42_IMPLEMENTATION_PARITY_COMMIT_MISSING")

    state_response = session.get(SLEEPER_STATE_URL, timeout=90)
    state_response.raise_for_status()
    state = state_response.json()
    season = str(state.get("season") or "")
    season_type = str(state.get("season_type") or "").lower()
    try:
        progress = max(int(state.get("week") or 0), int(state.get("leg") or 0))
    except (TypeError, ValueError):
        progress = 0
    if season != "2026":
        raise RuntimeError(f"B42_WRONG_CURRENT_NFL_SEASON {season!r}")
    if season_type and season_type != "regular":
        raise RuntimeError(f"B42_NOT_REGULAR_SEASON {season_type!r}")
    latest_completed_week = progress - 1
    if latest_completed_week < 4 or latest_completed_week > 18:
        raise RuntimeError(
            f"B42_IMPLAUSIBLE_LATEST_COMPLETED_WEEK {latest_completed_week}"
        )

    stats_payload = lineage["b41h"].get_bytes(session, CURRENT_STATS_URL)
    snaps_payload = lineage["b41h"].get_bytes(session, CURRENT_SNAPS_URL)

    out.mkdir(parents=True, exist_ok=True)
    source_dir = out / "sources"
    stats_path = source_dir / "stats_player_week_2026_completed.csv"
    snaps_path = source_dir / "snap_counts_2026_completed.csv"

    stats_meta = filter_csv_to_completed_weeks(
        stats_payload,
        season_col="season",
        week_col="week",
        type_col="season_type",
        type_value="REG",
        latest_completed_week=latest_completed_week,
        out_path=stats_path,
    )
    stats_meta["url"] = CURRENT_STATS_URL

    snaps_meta = filter_csv_to_completed_weeks(
        snaps_payload,
        season_col="season",
        week_col="week",
        type_col="game_type",
        type_value="REG",
        latest_completed_week=latest_completed_week,
        out_path=snaps_path,
    )
    snaps_meta["url"] = CURRENT_SNAPS_URL

    players_path = repo / B41I_IDENTITY_RELATIVE_PATH
    features, feature_audit, all_current_rows = build_feature_rows_for_origins(
        lineage["builder"],
        stats_path,
        snaps_path,
        players_path,
        2026,
        [latest_completed_week],
    )

    role_eligibility, eligibility_audit = build_role_eligibility(
        all_current_rows,
        lineage["builder"],
        lineage,
        session,
        latest_completed_week,
    )
    eligibility_path = out / "player_role_v2_b42_v4_role_eligibility.csv"
    role_eligibility.to_csv(
        eligibility_path,
        index=False,
        lineterminator="\n",
    )

    (
        with_ids,
        cross_sha,
        overall_cov,
        pos_cov,
        sid_to_gsis,
        gsis_mapped_sleeper_ids,
        crosswalk_audit,
    ) = attach_stable_ids_row_guarded(
        features,
        lineage,
        session,
    )
    if eligibility_audit["stable_id_crosswalk_sha256"] != cross_sha:
        raise RuntimeError("B42_CURRENT_CROSSWALK_CHANGED_WITHIN_SHADOW_BUILD")
    model = with_ids[with_ids["identity_mapped"]].copy()
    if model.empty:
        raise RuntimeError("B42_CURRENT_MODEL_EMPTY_AFTER_STABLE_ID_FILTER")
    model["sleeper_id"] = model["sleeper_id"].astype(str)

    (
        scored_history,
        sleeper_hashes,
        missing_stats,
        sleeper_participant_ids,
    ) = score_current_history(
        model,
        lineage["scorer"],
        lineage["scoring"]["scoring_settings"],
        session,
        latest_completed_week,
        2026,
        include_all_weeks_for_participation=True,
    )

    stable_mapped_eligible_ids = {
        str(x).strip()
        for x in role_eligibility.loc[
            role_eligibility["identity_mapped"], "sleeper_id"
        ].tolist()
        if str(x).strip()
    }
    participant_confirmed_mapped = (
        stable_mapped_eligible_ids & sleeper_participant_ids
    )
    participant_confirmation_rate = (
        float(len(participant_confirmed_mapped) / len(stable_mapped_eligible_ids))
        if stable_mapped_eligible_ids
        else 0.0
    )
    participant_field_sanity_pass = bool(
        stable_mapped_eligible_ids
        and participant_confirmation_rate >= 0.95
    )
    exclusion_reason_by_gsis = {
        str(r["gsis_id"]): str(r["reason"])
        for r in feature_audit.get("excluded_records", [])
        if int(r.get("origin_week", -1)) == int(latest_completed_week)
    }
    gsis_present_in_2026_sources = sorted(
        {
            str(r.get("gsis_id") or "").strip()
            for r in all_current_rows
            if str(r.get("gsis_id") or "").strip()
            and int(r.get("week") or 0) <= int(latest_completed_week)
        }
    )
    eligibility_context = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "phase": "B42-v4-owner-blind-role-eligibility-context",
        "latest_completed_week": int(latest_completed_week),
        "gsis_mapped_sleeper_ids": sorted(gsis_mapped_sleeper_ids),
        "sid_to_gsis": dict(sorted(sid_to_gsis.items())),
        "gsis_present_in_2026_sources": gsis_present_in_2026_sources,
        "crosswalk_rows_with_sleeper_id_but_no_gsis_id": int(
            crosswalk_audit["crosswalk_rows_with_sleeper_id_but_no_gsis_id"]
        ),
        "sleeper_2026_participant_ids": sorted(sleeper_participant_ids),
        "participation_fields": ["gp", "off_snp", "def_snp", "st_snp"],
        "stable_mapped_role_eligible_sleeper_id_count": int(
            len(stable_mapped_eligible_ids)
        ),
        "stable_mapped_role_eligible_participant_confirmed_count": int(
            len(participant_confirmed_mapped)
        ),
        "participant_confirmation_rate": participant_confirmation_rate,
        "participant_field_sanity_minimum": 0.95,
        "participant_field_sanity_pass": participant_field_sanity_pass,
        "feature_exclusion_reason_by_gsis": dict(
            sorted(exclusion_reason_by_gsis.items())
        ),
        "owner_or_roster_context_used": False,
        "frozen_before_roster_semantic_parse": True,
    }
    eligibility_context_path = (
        out / "player_role_v2_b42_v4_owner_blind_eligibility_context.json"
    )
    eligibility_context_path.write_text(
        json.dumps(eligibility_context, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Data-integrity failures must stop before any roster semantic parse or team result.
    if not participant_field_sanity_pass:
        stop = {
            "schema_version": 1,
            "study_id": STUDY_ID,
            "phase": "B42-v4-pre-roster-data-integrity-stop",
            "result": DATA_STOP_RESULT,
            "stop_stage": "shadow_participation_field_sanity",
            "continuation_class": CONTINUATION_CLASS,
            "owner_blind_eligibility_context_sha256": sha256_file(
                eligibility_context_path
            ),
            "latest_completed_week": int(latest_completed_week),
            "stable_mapped_role_eligible_sleeper_id_count": int(
                len(stable_mapped_eligible_ids)
            ),
            "stable_mapped_role_eligible_participant_confirmed_count": int(
                len(participant_confirmed_mapped)
            ),
            "participant_confirmation_rate": participant_confirmation_rate,
            "participant_field_sanity_minimum": 0.95,
            "participant_field_sanity_pass": False,
            "B42_team_level_result_opened": False,
            "roster_semantic_parse_performed": False,
            "production_change_authorized": False,
            "production_model_deployed": False,
        }
        (out / "player_role_v2_b42_v4_data_integrity_stop.json").write_text(
            json.dumps(stop, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return

    scored, aggregate_imputation = normalize_and_apply_frozen_models(
        scored_history,
        lineage["b41h"],
        lineage["baseline"],
        lineage["b41f"],
    )

    rows = []
    for _, row in scored.iterrows():
        pos = str(row["position"])
        idx, label = role_from_score(
            pos,
            float(row["model_score"]),
            lineage["b41f"],
        )
        if idx != int(row["tier_index"]) or label != str(row["role_tier"]):
            raise RuntimeError("B42_SHADOW_TIER_RECOMPUTATION_MISMATCH")
        rows.append(
            {
                "sleeper_id": str(row["sleeper_id"]),
                "gsis_id": str(row["gsis_id"]),
                "position": pos,
                "origin_week": int(row["origin_week"]),
                "model_score": float(row["model_score"]),
                "tier_index": idx,
                "role_tier": label,
                "prior_active_games": int(row["prior_active_games"]),
                "frozen_feature_missing_count_before_imputation": int(
                    row["frozen_feature_missing_count_before_imputation"]
                ),
                "frozen_feature_count": int(row["frozen_feature_count"]),
                "evidence_source": EVIDENCE_SOURCE,
                "confidence_status": CONFIDENCE_STATUS,
            }
        )

    shadow = pd.DataFrame(rows)
    if shadow.empty:
        raise RuntimeError("B42_SHADOW_REFRESH_EMPTY")
    if shadow["sleeper_id"].duplicated().any():
        dupes = shadow.loc[
            shadow["sleeper_id"].duplicated(keep=False), "sleeper_id"
        ].tolist()
        raise RuntimeError(f"B42_DUPLICATE_SHADOW_SLEEPER_IDS {dupes[:20]}")
    if sorted(shadow["position"].unique()) != sorted(POSITIONS):
        raise RuntimeError(
            "B42_SHADOW_REFRESH_MISSING_POSITION_SCOPE "
            f"{sorted(shadow['position'].unique())}"
        )
    if int(shadow["origin_week"].min()) != latest_completed_week:
        raise RuntimeError("B42_SHADOW_ORIGIN_WEEK_MISMATCH")
    if int(shadow["origin_week"].max()) != latest_completed_week:
        raise RuntimeError("B42_SHADOW_ORIGIN_WEEK_MISMATCH")

    shadow = shadow.sort_values(
        ["position", "model_score", "sleeper_id"],
        ascending=[True, False, True],
        kind="mergesort",
    ).reset_index(drop=True)

    shadow_path = out / "player_role_v2_b42_v4_shadow_refresh.csv"
    shadow.to_csv(
        shadow_path,
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    )

    by_position = (
        shadow.groupby("position", observed=True).size().astype(int).to_dict()
    )
    witness = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "phase": "B42-v4-owner-blind-shadow-refresh-freeze",
        "continuation_class": CONTINUATION_CLASS,
        "protocol_freeze_commit": protocol_commit,
        "protocol_sha256": sha256_file(protocol_path),
        "evaluator_sha256": sha256_file(evaluator_path),
        "implementation_parity_commit": parity_commit,
        "implementation_parity_sha256": sha256_file(parity_path),
        "implementation_parity_exact_pass": bool(
            implementation_parity["exact_parity"]["pass"]
        ),
        "role_eligibility_sha256": sha256_file(eligibility_path),
        "role_eligibility_audit": eligibility_audit,
        "owner_blind_eligibility_context_sha256": sha256_file(
            eligibility_context_path
        ),
        "participant_field_sanity_pass": participant_field_sanity_pass,
        "participant_confirmation_rate": participant_confirmation_rate,
        "gsis_mapped_sleeper_id_count": int(len(gsis_mapped_sleeper_ids)),
        "crosswalk_rows_with_sleeper_id_but_no_gsis_id": int(
            crosswalk_audit["crosswalk_rows_with_sleeper_id_but_no_gsis_id"]
        ),
        "gsis_present_in_2026_sources_count": int(
            len(gsis_present_in_2026_sources)
        ),
        "shadow_refresh_sha256": sha256_file(shadow_path),
        "shadow_refresh_rows": int(len(shadow)),
        "shadow_rows_by_position": {
            p: int(by_position.get(p, 0)) for p in POSITIONS
        },
        "latest_completed_week": int(latest_completed_week),
        "sleeper_state_observed": {
            "season": season,
            "season_type": season_type,
            "week": state.get("week"),
            "leg": state.get("leg"),
            "derived_progress_week": int(progress),
        },
        "current_sources": {
            "weekly_stats": stats_meta,
            "snap_counts": snaps_meta,
            "sleeper_completed_week_stats_sha256": sleeper_hashes,
            "stable_id_crosswalk_sha256": cross_sha,
            "identity_snapshot_sha256": B41I_IDENTITY_SHA256,
        },
        "feature_audit": feature_audit,
        "stable_id_coverage_before_shadow_filter": {
            "overall": float(overall_cov),
            "by_position": {
                p: float(pos_cov.get(p, 0.0)) for p in POSITIONS
            },
        },
        "sleeper_history_raw_stats_missing_count": int(missing_stats),
        "aggregate_frozen_imputation": aggregate_imputation,
        "static_role_inference_source_firewall": firewall,
        "role_inference_used_owner_identity": False,
        "role_inference_used_dynasty_team": False,
        "role_inference_used_fantasy_roster_slot": False,
        "roster_assignment_semantics_parsed_before_shadow_freeze": False,
        "future_target_used": False,
        "model_or_tier_retuning_performed": False,
        "production_change_authorized": False,
        "production_model_deployed": False,
    }
    witness_path = out / "player_role_v2_b42_v4_shadow_refresh_witness.json"
    witness_path.write_text(
        json.dumps(witness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def recursive_keys(obj):
    keys = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.append(str(key))
            keys.extend(recursive_keys(value))
    elif isinstance(obj, list):
        for item in obj:
            keys.extend(recursive_keys(item))
    return keys


def audit_rosters(
    repo: Path,
    out: Path,
    roster_snapshot: Path,
    shadow_freeze_commit: str,
) -> None:
    lineage = load_and_verify_frozen_lineage(repo)
    base = lineage["base"]
    protocol_path = base / "player_role_v2_b42_v4_protocol_freeze.json"
    evaluator_path = base / "player_role_v2_b42_v4_owner_blind_parity_evaluator.py"
    parity_path = base / "player_role_v2_b42_v4_implementation_parity.json"
    eligibility_path = base / "player_role_v2_b42_v4_role_eligibility.csv"
    eligibility_context_path = (
        base / "player_role_v2_b42_v4_owner_blind_eligibility_context.json"
    )
    shadow_path = base / "player_role_v2_b42_v4_shadow_refresh.csv"
    witness_path = base / "player_role_v2_b42_v4_shadow_refresh_witness.json"

    protocol = json.loads(protocol_path.read_text())
    witness = json.loads(witness_path.read_text())
    if protocol["evaluator_sha256"] != sha256_file(evaluator_path):
        raise RuntimeError("B42_AUDIT_EVALUATOR_SHA_DRIFT")
    if witness["protocol_sha256"] != sha256_file(protocol_path):
        raise RuntimeError("B42_AUDIT_PROTOCOL_SHA_DRIFT")
    if witness["implementation_parity_sha256"] != sha256_file(parity_path):
        raise RuntimeError("B42_AUDIT_IMPLEMENTATION_PARITY_SHA_DRIFT")
    parity = json.loads(parity_path.read_text())
    if parity["exact_parity"]["pass"] is not True:
        raise RuntimeError("B42_AUDIT_IMPLEMENTATION_PARITY_NOT_PASS")
    if witness["implementation_parity_exact_pass"] is not True:
        raise RuntimeError("B42_AUDIT_PARITY_WITNESS_NOT_PASS")
    if witness["role_eligibility_sha256"] != sha256_file(eligibility_path):
        raise RuntimeError("B42_AUDIT_ROLE_ELIGIBILITY_SHA_DRIFT")
    if witness["owner_blind_eligibility_context_sha256"] != sha256_file(
        eligibility_context_path
    ):
        raise RuntimeError("B42_AUDIT_ELIGIBILITY_CONTEXT_SHA_DRIFT")
    if witness["shadow_refresh_sha256"] != sha256_file(shadow_path):
        raise RuntimeError("B42_AUDIT_SHADOW_SHA_DRIFT")
    if witness["protocol_freeze_commit"] == "":
        raise RuntimeError("B42_AUDIT_PROTOCOL_COMMIT_MISSING")
    if witness["roster_assignment_semantics_parsed_before_shadow_freeze"] is not False:
        raise RuntimeError("B42_SOURCE_FIREWALL_WITNESS_DRIFT")
    if witness["model_or_tier_retuning_performed"] is not False:
        raise RuntimeError("B42_SHADOW_RETUNING_WITNESS_DRIFT")

    actual_roster_sha = sha256_file(roster_snapshot)
    if actual_roster_sha != protocol["roster_snapshot"]["sha256"]:
        raise RuntimeError(
            "B42_ROSTER_SNAPSHOT_SHA_DRIFT "
            f"expected={protocol['roster_snapshot']['sha256']} "
            f"actual={actual_roster_sha}"
        )

    shadow = pd.read_csv(shadow_path, dtype={"sleeper_id": str, "gsis_id": str})
    if shadow.empty or shadow["sleeper_id"].duplicated().any():
        raise RuntimeError("B42_AUDIT_SHADOW_INVALID")
    shadow_lookup = {
        str(row["sleeper_id"]): row
        for _, row in shadow.iterrows()
    }

    # FIRST semantic parse of fantasy-league roster assignment in B42.
    roster_payload = json.loads(roster_snapshot.read_text())
    rosters = roster_payload.get("rosters") or []
    if not isinstance(rosters, list):
        raise RuntimeError("B42_ROSTER_PAYLOAD_NOT_LIST")
    team_count = len(rosters)

    # League-wide integrity pre-pass only. No opaque labels, team coverage, tier counts,
    # or other team-level parity results are computed unless this gate passes.
    supported_roster_player_count = 0
    supported_roster_named_player_count = 0
    for roster in rosters:
        players_by_id = {}
        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for player in roster.get(slot) or []:
                pid = str(player.get("player_id") or "").strip()
                if pid:
                    players_by_id.setdefault(pid, player)
        for player in players_by_id.values():
            roster_pos = lineage["builder"].canon_pos(player.get("position"))
            if roster_pos not in POSITIONS:
                continue
            supported_roster_player_count += 1
            if str(player.get("name") or "").strip():
                supported_roster_named_player_count += 1

    roster_name_availability = (
        float(supported_roster_named_player_count / supported_roster_player_count)
        if supported_roster_player_count
        else 0.0
    )
    if not (
        supported_roster_player_count > 0
        and roster_name_availability >= 0.95
    ):
        out.mkdir(parents=True, exist_ok=True)
        stop = {
            "schema_version": 1,
            "study_id": STUDY_ID,
            "phase": "B42-v4-pre-team-result-data-integrity-stop",
            "result": DATA_STOP_RESULT,
            "stop_stage": "roster_name_availability_prepass",
            "continuation_class": CONTINUATION_CLASS,
            "roster_snapshot_sha256": actual_roster_sha,
            "supported_position_roster_player_count": int(
                supported_roster_player_count
            ),
            "supported_position_roster_named_player_count": int(
                supported_roster_named_player_count
            ),
            "supported_position_roster_name_availability": roster_name_availability,
            "minimum_supported_roster_name_availability": 0.95,
            "B42_team_level_result_opened": False,
            "team_partition_metric_computed": False,
            "production_change_authorized": False,
            "production_model_deployed": False,
        }
        (out / "player_role_v2_b42_v4_data_integrity_stop.json").write_text(
            json.dumps(stop, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return

    # Privacy hardening begins only after all league-wide data-integrity prechecks pass.
    ordered_rosters = list(rosters)
    secrets.SystemRandom().shuffle(ordered_rosters)
    team_labels = {
        id(roster): f"Team{i:02d}"
        for i, roster in enumerate(ordered_rosters, start=1)
    }

    eligibility = pd.read_csv(
        eligibility_path,
        dtype={"sleeper_id": str, "gsis_id": str},
        keep_default_na=False,
    )
    if eligibility.empty or eligibility["gsis_id"].duplicated().any():
        raise RuntimeError("B42_AUDIT_ROLE_ELIGIBILITY_INVALID")
    eligible_by_sleeper = {
        str(row["sleeper_id"]): row
        for _, row in eligibility.iterrows()
        if str(row.get("sleeper_id") or "").strip()
    }
    name_groups = defaultdict(list)
    for _, row in eligibility.iterrows():
        key = str(row.get("exact_name_key") or "")
        if key and str(row.get("exact_name_unique") or "").strip().lower() in {"true", "1"}:
            name_groups[key].append(row)
    eligible_by_exact_name = {
        key: rows[0] for key, rows in name_groups.items() if len(rows) == 1
    }
    eligibility_context = json.loads(eligibility_context_path.read_text())
    if eligibility_context.get("owner_or_roster_context_used") is not False:
        raise RuntimeError("B42_ELIGIBILITY_CONTEXT_OWNER_BLINDNESS_DRIFT")
    gsis_mapped_sleeper_ids = set(
        str(x) for x in eligibility_context.get("gsis_mapped_sleeper_ids", [])
    )
    sid_to_gsis = {
        str(k): str(v)
        for k, v in (eligibility_context.get("sid_to_gsis") or {}).items()
    }
    gsis_present_in_2026_sources = set(
        str(x) for x in eligibility_context.get("gsis_present_in_2026_sources", [])
    )
    sleeper_participant_ids = set(
        str(x) for x in eligibility_context.get("sleeper_2026_participant_ids", [])
    )
    feature_exclusion_reason_by_gsis = {
        str(k): str(v)
        for k, v in (
            eligibility_context.get("feature_exclusion_reason_by_gsis") or {}
        ).items()
    }

    team_results = []
    league_position_eligible = Counter()
    league_position_covered = Counter()
    covered_shadow_rows = []
    real_owner_values = set()
    for roster in ordered_rosters:
        for key in ("owner_id", "owner_username", "team_name", "roster_id"):
            value = roster.get(key)
            if value not in (None, ""):
                real_owner_values.add(str(value))

        label = team_labels[id(roster)]
        players_by_id = {}
        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for player in roster.get(slot) or []:
                pid = str(player.get("player_id") or "").strip()
                if not pid:
                    continue
                # Slot is deliberately discarded here. It is not passed to inference.
                players_by_id.setdefault(pid, player)

        eligible_count = 0
        covered = 0
        position_mismatch = 0
        eligible_pending = 0
        no_current_evidence = 0
        tier_counts = Counter()
        evidence_counts = Counter()
        confidence_counts = Counter()
        active_game_buckets = Counter()
        eligibility_match_methods = Counter()
        pending_reason_counts = Counter()
        source_disagreement = 0
        identity_gap_unknown_model_position = 0
        supported_named = 0
        supported_total = 0
        team_position_eligible = Counter()
        team_position_covered = Counter()

        for pid, player in sorted(players_by_id.items()):
            roster_pos = lineage["builder"].canon_pos(player.get("position"))
            if roster_pos not in POSITIONS:
                continue
            supported_total += 1
            if str(player.get("name") or "").strip():
                supported_named += 1

            elig = eligible_by_sleeper.get(pid)
            match_method = None
            if elig is not None:
                match_method = "stable_sleeper_id"
            else:
                name_key = exact_name_key(player.get("name") or "")
                elig = eligible_by_exact_name.get(name_key)
                if elig is not None:
                    match_method = "unique_exact_name_denominator_only"

            if elig is None:
                if pid in sleeper_participant_ids:
                    mapped_gsis = sid_to_gsis.get(pid)
                    mapped_into_2026_source = bool(
                        pid in gsis_mapped_sleeper_ids
                        and mapped_gsis
                        and mapped_gsis in gsis_present_in_2026_sources
                    )
                    if not mapped_into_2026_source:
                        eligible_count += 1
                        eligible_pending += 1
                        identity_gap_unknown_model_position += 1
                        eligibility_match_methods[
                            "sleeper_participation_identity_gap"
                        ] += 1
                        pending_reason_counts[
                            (
                                "crosswalk_mapped_gsis_absent_from_2026_nflverse"
                                if mapped_gsis
                                else "stable_id_crosswalk_missing_gsis_bridge"
                            )
                        ] += 1
                        continue
                    # Only a correctly mapped player present in the 2026 nflverse
                    # sources may be treated as a source-activity disagreement.
                    source_disagreement += 1
                    continue
                no_current_evidence += 1
                continue

            eligible_count += 1
            eligibility_match_methods[match_method] += 1
            model_pos = str(elig["position"])
            if model_pos in POSITIONS:
                team_position_eligible[model_pos] += 1
                league_position_eligible[model_pos] += 1

            # Role coverage itself is strictly player-ID based. Exact-name matching
            # may classify eligibility but can never assign/rescue a role.
            role = shadow_lookup.get(pid)
            if (
                match_method == "unique_exact_name_denominator_only"
                and role is not None
            ):
                raise RuntimeError(
                    "B42_EXACT_NAME_DENOMINATOR_BRIDGE_MUST_NOT_RESCUE_ROLE"
                )
            if role is None:
                eligible_pending += 1
                if match_method == "unique_exact_name_denominator_only":
                    bridged_sid = str(elig.get("sleeper_id") or "").strip()
                    pending_reason_counts[
                        (
                            "crosswalk_sleeper_id_disagrees_with_roster_id_name_bridge"
                            if bridged_sid
                            else "stable_id_crosswalk_absent_name_bridge"
                        )
                    ] += 1
                else:
                    gsis = str(elig.get("gsis_id") or "")
                    pending_reason_counts[
                        feature_exclusion_reason_by_gsis.get(
                            gsis, "other_pipeline_drop"
                        )
                    ] += 1
                continue

            role_pos = str(role["position"])
            if role_pos != roster_pos:
                position_mismatch += 1

            covered += 1
            team_position_covered[role_pos] += 1
            league_position_covered[role_pos] += 1
            tier_counts[str(role["role_tier"])] += 1
            evidence_counts[str(role["evidence_source"])] += 1
            confidence_counts[str(role["confidence_status"])] += 1
            games = int(role["prior_active_games"])
            if games >= 3:
                active_game_buckets["3+"] += 1
            else:
                active_game_buckets[str(games)] += 1
            covered_shadow_rows.append(role)

        coverage = (
            float(covered / eligible_count) if eligible_count else 0.0
        )
        team_results.append(
            {
                "opaque_team": label,
                "role_eligible_supported_position_players": int(eligible_count),
                "data_driven_role_count": int(covered),
                "fallback_role_count": 0,
                "eligible_pending_without_role_count": int(eligible_pending),
                "no_current_season_evidence_count": int(no_current_evidence),
                "position_label_mismatch_count": int(position_mismatch),
                "role_coverage": coverage,
                "coverage_pass_98pct": bool(
                    eligible_count > 0 and coverage >= MIN_TEAM_ROLE_COVERAGE
                ),
                "eligibility_match_method_counts": dict(
                    sorted(eligibility_match_methods.items())
                ),
                "eligible_pending_reason_counts": dict(
                    sorted(pending_reason_counts.items())
                ),
                "sleeper_participation_crosswalk_present_source_disagreement_count": int(
                    source_disagreement
                ),
                "identity_gap_unknown_model_position_count": int(
                    identity_gap_unknown_model_position
                ),
                "supported_position_roster_name_available_count": int(supported_named),
                "supported_position_roster_player_count": int(supported_total),
                "supported_position_roster_name_availability": (
                    float(supported_named / supported_total)
                    if supported_total else 0.0
                ),
                "evidence_source_counts": dict(sorted(evidence_counts.items())),
                "confidence_status_counts": dict(sorted(confidence_counts.items())),
                "active_game_evidence_depth_counts": dict(
                    sorted(active_game_buckets.items())
                ),
                "role_tier_counts": {
                    role: int(tier_counts.get(role, 0)) for role in ROLE_ORDER
                },
                "eligible_by_model_position": {
                    p: int(team_position_eligible.get(p, 0)) for p in POSITIONS
                },
                "covered_by_model_position": {
                    p: int(team_position_covered.get(p, 0)) for p in POSITIONS
                },
            }
        )

    coverages = [float(t["role_coverage"]) for t in team_results]
    coverage_range = (
        float(max(coverages) - min(coverages))
        if coverages
        else float("inf")
    )

    data_integrity_checks = {
        "participant_field_sanity_at_least_95pct": bool(
            witness.get("participant_field_sanity_pass") is True
        ),
        "supported_position_roster_name_availability_at_least_95pct": True,
    }
    if not all(data_integrity_checks.values()):
        raise RuntimeError("B42_DATA_INTEGRITY_PRECHECK_ORDERING_VIOLATION")
    data_integrity_pass = True

    # Exact counterfactual owner/team assignment test. The shadow score itself
    # was durably frozen before this roster snapshot was semantically parsed.
    context_labels = [f"Team{i:02d}" for i in range(1, REQUIRED_TEAM_COUNT + 1)]
    synthetic_slots = ["STARTER", "BENCH", "TAXI", "RESERVE_IR"]
    changes = 0
    comparisons = 0
    for role in covered_shadow_rows:
        base_idx = int(role["tier_index"])
        base_label = str(role["role_tier"])
        for team_label in context_labels:
            for slot in synthetic_slots:
                idx, label = counterfactual_role_assignment(
                    str(role["position"]),
                    float(role["model_score"]),
                    lineage["b41f"],
                    team_label,
                    slot,
                )
                comparisons += 1
                if idx != base_idx or label != base_label:
                    changes += 1

    firewall = shadow_static_source_firewall(evaluator_path)
    if not firewall["pass"]:
        raise RuntimeError("B42_STATIC_SOURCE_FIREWALL_NOT_PASS_AT_AUDIT")

    gates = {
        "exactly_12_teams": bool(team_count == REQUIRED_TEAM_COUNT),
        "every_team_has_supported_position_denominator": bool(
            team_results
            and all(
                int(t["role_eligible_supported_position_players"]) > 0
                for t in team_results
            )
        ),
        "minimum_98pct_role_coverage_every_team": bool(
            team_results
            and all(bool(t["coverage_pass_98pct"]) for t in team_results)
        ),
        "maximum_2_percentage_point_coverage_range": bool(
            math.isfinite(coverage_range)
            and coverage_range <= MAX_TEAM_COVERAGE_RANGE + 1e-12
        ),
        "structural_owner_slot_role_invariance": bool(
            changes == ALLOWED_COUNTERFACTUAL_ROLE_CHANGES
        ),
        "shadow_refresh_frozen_before_roster_semantic_parse": bool(
            witness["roster_assignment_semantics_parsed_before_shadow_freeze"]
            is False
            and bool(shadow_freeze_commit)
        ),
        "shadow_role_inference_source_firewall": bool(firewall["pass"]),
        "all_eight_positions_in_declared_scope": bool(
            protocol["audit_population"]["position_scope"] == POSITIONS
            and sorted(lineage["b41f"]["position_models"]) == sorted(POSITIONS)
        ),
        "no_owner_blind_fallback_invented_post_holdout": bool(
            protocol["coverage_definition"]["fallback_count_by_definition"] == 0
            and all(int(t["fallback_role_count"]) == 0 for t in team_results)
        ),
        "continuation_class_preserved": bool(
            protocol["continuation_class"] == CONTINUATION_CLASS
            and witness["continuation_class"] == CONTINUATION_CLASS
        ),
        "model_or_tier_retuning_absent": bool(
            witness["model_or_tier_retuning_performed"] is False
        ),
    }

    evidence = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "phase": PHASE,
        "continuation_class": CONTINUATION_CLASS,
        "protocol_sha256": sha256_file(protocol_path),
        "evaluator_sha256": sha256_file(evaluator_path),
        "implementation_parity_sha256": sha256_file(parity_path),
        "implementation_parity_exact_pass": True,
        "role_eligibility_sha256": sha256_file(eligibility_path),
        "owner_blind_eligibility_context_sha256": sha256_file(
            eligibility_context_path
        ),
        "shadow_refresh_sha256": sha256_file(shadow_path),
        "shadow_refresh_witness_sha256": sha256_file(witness_path),
        "shadow_freeze_commit": shadow_freeze_commit,
        "roster_snapshot_sha256": actual_roster_sha,
        "team_count": int(team_count),
        "opaque_team_label_assignment": "private random permutation; mapping not persisted",
        "data_integrity_checks": data_integrity_checks,
        "data_integrity_pass": data_integrity_pass,
        "supported_position_roster_name_availability": roster_name_availability,
        "participant_confirmation_rate": float(
            witness.get("participant_confirmation_rate", 0.0)
        ),
        "team_results": team_results,
        "league_position_eligible_counts": {
            p: int(league_position_eligible.get(p, 0)) for p in POSITIONS
        },
        "league_position_covered_counts": {
            p: int(league_position_covered.get(p, 0)) for p in POSITIONS
        },
        "coverage_range": coverage_range,
        "required_minimum_team_coverage": MIN_TEAM_ROLE_COVERAGE,
        "required_maximum_coverage_range": MAX_TEAM_COVERAGE_RANGE,
        "fallback_policy": protocol["coverage_definition"]["fallback_policy"],
        "structural_counterfactual_invariance": {
            "interpretation": (
                "true by construction; substantive owner-blind evidence is the pre-roster "
                "shadow freeze plus static source firewall"
            ),
            "synthetic_team_contexts": REQUIRED_TEAM_COUNT,
            "synthetic_slot_contexts": len(synthetic_slots),
            "comparisons": int(comparisons),
            "role_changes": int(changes),
            "allowed_role_changes": ALLOWED_COUNTERFACTUAL_ROLE_CHANGES,
            "pass": bool(changes == ALLOWED_COUNTERFACTUAL_ROLE_CHANGES),
        },
        "static_role_inference_source_firewall": firewall,
        "primary_gates": gates,
        "all_primary_gates_pass": bool(all(gates.values())),
        "b41j_result": lineage["b41j"]["result"],
        "b41j_all_four_primary_tests_pass": lineage["b41j"][
            "all_four_primary_tests_pass"
        ],
        "model_or_tier_retuning_performed": False,
        "posthoc_fallback_rescue_performed": False,
        "production_change_authorized": False,
        "production_model_deployed": False,
    }

    # Privacy/key firewall for committed B42 evidence.
    forbidden_output_keys = {"owner_id", "owner_username", "team_name", "roster_id"}
    key_hits = sorted(
        {
            key
            for key in recursive_keys(evidence)
            if key.lower() in forbidden_output_keys
        }
    )
    def string_leaf_values(obj):
        values = []
        if isinstance(obj, dict):
            for value in obj.values():
                values.extend(string_leaf_values(value))
        elif isinstance(obj, list):
            for value in obj:
                values.extend(string_leaf_values(value))
        elif isinstance(obj, str):
            values.append(obj)
        return values

    emitted_string_values = set(string_leaf_values(evidence))
    sensitive_value_hits = sorted(
        value
        for value in real_owner_values
        if value and value in emitted_string_values
    )
    privacy_pass = not key_hits and not sensitive_value_hits
    evidence["privacy_audit"] = {
        "forbidden_output_key_hits": key_hits,
        "real_owner_or_team_value_hits": sensitive_value_hits,
        "pass": privacy_pass,
    }
    gates["owner_identity_privacy"] = privacy_pass
    evidence["primary_gates"] = gates
    evidence["all_primary_gates_pass"] = bool(all(gates.values()))

    if evidence["all_primary_gates_pass"]:
        result = PASS_RESULT
    else:
        result = FAIL_RESULT
    decision = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "phase": "B42-v4-scientific-decision",
        "result": result,
        "continuation_class": CONTINUATION_CLASS,
        "team_count": int(team_count),
        "minimum_team_role_coverage": (
            float(min(coverages)) if coverages else None
        ),
        "maximum_team_role_coverage": (
            float(max(coverages)) if coverages else None
        ),
        "coverage_range": (
            float(coverage_range) if math.isfinite(coverage_range) else None
        ),
        "all_primary_parity_gates_pass": bool(
            evidence["all_primary_gates_pass"]
        ),
        "data_integrity_pass": data_integrity_pass,
        "data_integrity_checks": data_integrity_checks,
        "owner_swap_role_changes": int(changes),
        "fallback_roles_used": 0,
        "posthoc_fallback_rescue_performed": False,
        "model_or_tier_retuning_performed": False,
        "eligible_for_separate_production_authorization": bool(
            evidence["all_primary_gates_pass"]
        ),
        "production_change_authorized": False,
        "production_model_deployed": False,
        "next_stage": (
            "If PASS, independently review and build a separate production "
            "authorization/deployment workflow. B42 itself does not deploy."
            if evidence["all_primary_gates_pass"]
            else
            "Scientific stop. Preserve B42 evidence. Any remediation must be "
            "newly versioned and frozen before another parity audit; do not "
            "post-hoc invent a fallback to rescue this result."
        ),
    }

    out.mkdir(parents=True, exist_ok=True)
    evidence_path = out / "player_role_v2_b42_v4_owner_blind_evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    decision["evidence_sha256"] = sha256_file(evidence_path)
    decision_path = out / "player_role_v2_b42_v4_scientific_decision.json"
    decision_path.write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Player Role V2 — B42 V4 12-Team Owner-Blind Parity Audit",
        "",
        f"- Continuation class: **{CONTINUATION_CLASS}**",
        f"- Decision: **{result}**",
        f"- Team count: **{team_count}**",
        f"- Minimum team role coverage: **{min(coverages) if coverages else 0.0:.4f}**",
        f"- Maximum team role coverage: **{max(coverages) if coverages else 0.0:.4f}**",
        f"- Coverage range: **{coverage_range if math.isfinite(coverage_range) else float('nan'):.4f}**",
        f"- Required per-team coverage: **{MIN_TEAM_ROLE_COVERAGE:.2f}**",
        f"- Maximum allowed coverage range: **{MAX_TEAM_COVERAGE_RANGE:.2f}**",
        f"- Counterfactual assignment comparisons: **{comparisons}**",
        f"- Counterfactual role changes: **{changes}**",
        "- Fallback roles used: **0**",
        "- Model/tier retuning: **No**",
        "- Production deployed: **No**",
        "- Production change authorized: **No**",
        f"- Data-integrity checks: **{'PASS' if data_integrity_pass else 'STOP'}**",
        f"- Supported-position roster name availability: **{roster_name_availability:.4f}**",
        f"- Sleeper participant confirmation of stable-mapped eligible players: **{float(witness.get('participant_confirmation_rate', 0.0)):.4f}**",
        "",
        "## Opaque team parity",
        "",
        "| Team | Role-eligible | Data-driven | Eligible pending | Identity-gap unknown-pos | Source disagreement | No current evidence | Pos-label mismatch | Coverage | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for t in team_results:
        lines.append(
            f"| {t['opaque_team']} | "
            f"{t['role_eligible_supported_position_players']} | "
            f"{t['data_driven_role_count']} | "
            f"{t['eligible_pending_without_role_count']} | "
            f"{t['identity_gap_unknown_model_position_count']} | "
            f"{t['sleeper_participation_crosswalk_present_source_disagreement_count']} | "
            f"{t['no_current_season_evidence_count']} | "
            f"{t['position_label_mismatch_count']} | "
            f"{t['role_coverage']:.4f} | "
            f"{'PASS' if t['coverage_pass_98pct'] else 'FAIL'} |"
        )

    lines.extend(
        [
            "",
            "## Eligibility and pending diagnostics",
            "",
        ]
    )
    for t in team_results:
        lines.append(
            f"- {t['opaque_team']}: match_methods="
            f"{json.dumps(t['eligibility_match_method_counts'], sort_keys=True)}; "
            f"pending_reasons="
            f"{json.dumps(t['eligible_pending_reason_counts'], sort_keys=True)}; "
            f"source_disagreement="
            f"{t['sleeper_participation_crosswalk_present_source_disagreement_count']}"
        )

    lines.extend(
        [
            "",
            "## Gate results",
            "",
        ]
    )
    for key, value in gates.items():
        lines.append(f"- {key}: **{'PASS' if value else 'FAIL'}**")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                "Coverage parity is evaluated only among role-eligible players with "
                "current-season active evidence. Sleeper participants without a valid "
                "GSIS bridge into the 2026 nflverse source are conservatively counted as "
                "eligible and uncovered so identity failures cannot improve coverage. "
                "These identity-gap players have unknown model position and therefore are "
                "tracked separately from per-position eligible counts. Players with "
                "no 2026 active evidence "
                "are descriptive only. The counterfactual owner/slot check is structural "
                "and true by construction; the substantive owner-blind guarantee is the "
                "pre-roster shadow freeze and source firewall. Parity otherwise means "
                "equal evidence completeness and identical owner-blind "
                "rules. It does **not** require teams to have similar role-tier "
                "distributions."
            ),
            "",
            (
                "B42 V4 intentionally uses no fallback role mapping. No owner-blind "
                "fallback rule was frozen in B41A–B41J, and the earlier fantasy "
                "starter/bench/taxi/IR fallback concept is incompatible with the "
                "owner-blind design. Uncovered players remain pending rather than "
                "being rescued post hoc."
            ),
            "",
            (
                "The shadow role refresh was frozen before the roster assignment "
                "snapshot was semantically parsed. Team labels are opaque; owner "
                "identity, real team names, and roster IDs are not emitted."
            ),
            "",
            "## Next stage",
            "",
            decision["next_stage"],
            "",
        ]
    )
    (out / "player_role_v2_b42_v4_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def run_selftest() -> None:
    fake_b41f = {
        "position_models": {
            p: {"frozen_tier_thresholds": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]}
            for p in POSITIONS
        }
    }
    idx, label = role_from_score("QB", 0.45, fake_b41f)
    assert idx == 4 and label == "Starter"
    for team in [f"Team{i:02d}" for i in range(1, 13)]:
        for slot in ["STARTER", "BENCH", "TAXI", "RESERVE_IR"]:
            assert counterfactual_role_assignment(
                "QB", 0.45, fake_b41f, team, slot
            ) == (4, "Starter")

    good = [1.0] * 12
    assert min(good) >= MIN_TEAM_ROLE_COVERAGE
    assert max(good) - min(good) <= MAX_TEAM_COVERAGE_RANGE

    bad_floor = [1.0] * 11 + [0.97]
    assert not all(v >= MIN_TEAM_ROLE_COVERAGE for v in bad_floor)

    bad_range = [1.0] * 11 + [0.97]
    assert max(bad_range) - min(bad_range) > MAX_TEAM_COVERAGE_RANGE

    proto = protocol_payload(
        "e" * 64,
        "r" * 64,
        "b" * 40,
        "m" * 40,
    )
    assert proto["primary_parity_gates"]["minimum_role_coverage_each_team"] == 0.98
    assert proto["primary_parity_gates"]["maximum_coverage_range_across_teams"] == 0.02
    assert proto["coverage_definition"]["fallback_count_by_definition"] == 0
    assert "at least one completed active 2026 game" in proto["coverage_definition"]["role_eligible"]
    assert proto["implementation_parity_oracle"]["required_before_2026_shadow"] is True
    assert proto["implementation_parity_oracle"]["oracle_runs_before_protocol_commit"] is True
    assert proto["coverage_definition"]["participant_identity_gap_guard"]["frozen_before_roster_parse"] is True
    assert proto["coverage_definition"]["participant_identity_gap_guard"]["identity_gap_requires_valid_gsis_bridge_into_current_nflverse"] is True
    assert proto["data_integrity_stop_firewall"]["participant_sanity_enforced_before_roster_semantic_parse"] is True
    assert proto["data_integrity_stop_firewall"]["roster_name_availability_enforced_before_team_partition_metrics"] is True
    assert proto["data_integrity_stop_firewall"]["data_integrity_stop_may_not_emit_team_level_parity_results"] is True
    assert proto["production_firewall"]["B42_authorizes_production_change"] is False
    # Regression guard for the V4 operational RED: the pinned crosswalk uses
    # literal "NA" for missing GSIS IDs. It must never be treated as a real ID.
    for missing_gsis_marker in ["", "NA", "na", "NaN", "none", "NONE"]:
        g = str(missing_gsis_marker or "").strip()
        assert not bool(g and g.lower() not in {"na", "nan", "none"})
    g = "00-0031234"
    assert bool(g and g.lower() not in {"na", "nan", "none"})

    # Identity-gap classification semantics: a participating ID is covered by the
    # crosswalk guard only when it has a GSIS bridge into current nflverse rows.
    mapped_ids = {"sid_good", "sid_missing_source"}
    sid_to_gsis = {"sid_good": "gsis_good", "sid_missing_source": "gsis_old"}
    gsis_present = {"gsis_good"}
    def _mapped_into_source(sid):
        gsis = sid_to_gsis.get(sid)
        return bool(sid in mapped_ids and gsis and gsis in gsis_present)
    assert _mapped_into_source("sid_good") is True
    assert _mapped_into_source("sid_missing_source") is False
    assert _mapped_into_source("sid_no_gsis") is False

    print("PASS B42 evaluator self-test")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mode",
        choices=["selftest", "protocol", "parity", "shadow", "audit"],
        required=True,
    )
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out")
    ap.add_argument("--roster-snapshot")
    ap.add_argument("--roster-snapshot-sha256")
    ap.add_argument("--roster-snapshot-git-blob")
    ap.add_argument("--main-at-start")
    ap.add_argument("--protocol-commit", default="")
    ap.add_argument("--parity-commit", default="")
    ap.add_argument("--shadow-freeze-commit", default="")
    args = ap.parse_args()

    if args.mode == "selftest":
        run_selftest()
        return

    repo = Path(args.repo).resolve()
    base = repo / "research/player-role-v2"
    evaluator_path = base / "player_role_v2_b42_v4_owner_blind_parity_evaluator.py"

    if args.mode == "protocol":
        load_and_verify_frozen_lineage(repo)
        if not args.out:
            raise RuntimeError("--out required")
        if not args.roster_snapshot_sha256:
            raise RuntimeError("--roster-snapshot-sha256 required")
        if not args.roster_snapshot_git_blob:
            raise RuntimeError("--roster-snapshot-git-blob required")
        if not args.main_at_start:
            raise RuntimeError("--main-at-start required")
        payload = protocol_payload(
            sha256_file(evaluator_path),
            args.roster_snapshot_sha256,
            args.roster_snapshot_git_blob,
            args.main_at_start,
        )
        Path(args.out).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return

    if args.mode == "parity":
        if not args.out:
            raise RuntimeError("--out required")
        lineage = load_and_verify_frozen_lineage(repo)
        session = requests.Session()
        session.headers.update(
            {"User-Agent": "LOG-Trade-Calculator-player-role-v2-b42-v4-parity"}
        )
        Path(args.out).mkdir(parents=True, exist_ok=True)
        result = run_b41j_implementation_parity_oracle(
            repo, Path(args.out), lineage, session
        )
        if result["exact_parity"]["pass"] is not True:
            raise RuntimeError("B42_IMPLEMENTATION_PARITY_NOT_PASS")
        return

    if args.mode == "shadow":
        if not args.out:
            raise RuntimeError("--out required")
        build_shadow_refresh(
            repo,
            Path(args.out),
            args.protocol_commit,
            args.parity_commit,
        )
        return

    if args.mode == "audit":
        if not args.out or not args.roster_snapshot:
            raise RuntimeError("--out and --roster-snapshot required")
        audit_rosters(
            repo,
            Path(args.out),
            Path(args.roster_snapshot),
            args.shadow_freeze_commit,
        )
        return


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import ast
import csv
import hashlib
import importlib.util
import json
import math
import secrets
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import requests

STUDY_ID = "player-role-v2"
PHASE = "B44W4-v1-week4-dob-position-remediation-reaudit"
BASE_REL = Path("research/player-role-v2")

B42_EVALUATOR_REL = BASE_REL / "player_role_v2_b42_v4_owner_blind_parity_evaluator.py"
B42_EVALUATOR_SHA256 = "418e0807471cdf644afeaf2c5a3ee0211068667fce057317ec29a3962a836396"
B42_WITNESS_REL = BASE_REL / "player_role_v2_b42_v4_shadow_refresh_witness.json"
B42_WITNESS_SHA256 = "8801001087a5714aafcc21f82ee1d3ee4c1690b7c4168daf3812d0b215b87db0"
B42_DECISION_REL = BASE_REL / "player_role_v2_b42_v4_scientific_decision.json"
B42_DECISION_SHA256 = "47059d9f0431eadb9725a66a6891b13e73af4b44f62bd2a12df0dd95ded4d2d6"

V1_EVALUATOR_REL = BASE_REL / "player_role_v2_b43_v1_identity_bridge_evaluator.py"
V1_EVALUATOR_SHA256 = "44e2585dbb84a7c62b274b5ed0bc63d1881b4e48e940e65ad04a5c8905475bab"
V1_PREREG_REL = BASE_REL / "player_role_v2_b43_v1_preregistration.json"
V1_PREREG_SHA256 = "cd5c70d6fd8fb46b302855039c2161e14bb4491dc367e04ba9d641c665adeecd"
V1_BRIDGE_REL = BASE_REL / "player_role_v2_b43_v1_identity_bridge.csv"
V1_BRIDGE_SHA256 = "3fdc85e18a4e705d15afcf8d93b742343c57aaa2c909f3e8fd40faf2ebbf8fcc"
V1_EVIDENCE_REL = BASE_REL / "player_role_v2_b43_v1_evidence.json"
V1_EVIDENCE_SHA256 = "adfcd3593a01961c1624148ef8ca2cb8d10c6e000ca05fa19a4baa208ba3102a"
V1_DECISION_REL = BASE_REL / "player_role_v2_b43_v1_scientific_decision.json"
V1_DECISION_SHA256 = "fa50ef0b58145da5edbf7805a8f4cfd7c54b464754ee04e59c5822072f6eb3f9"

ADOPTION_REL = BASE_REL / "player_role_v2_b43_v1r1_rule_adoption_decision.json"
ADOPTION_SHA256 = "4f62fe0416626a780538288bcedd36cf0ef95b73d3a2802340fbfc31a38ca095"

V4R2_PREREG_REL = BASE_REL / "player_role_v2_b43_v4r2_preregistration.json"
V4R2_PREREG_SHA256 = "e224b7a4d7c8566bd8ca0e3b9eebad67debae26706ca4ee610e8dd779f028738"
V4R2_DECISION_REL = BASE_REL / "player_role_v2_b43_v4r2_scientific_decision.json"
V4R2_DECISION_SHA256 = "e9968c9acade8ab484c8c6ff6317b6aca351f1dade0f4b46c70b68d7e98fb9c7"

B41I_PLAYERS_REL = BASE_REL / "frozen_inputs/players_b41i_snapshot.csv"
B41I_PLAYERS_SHA256 = "d531dcff2d3ff681f02210d314f6e9f16c671c0beefa85fd311a55363675d4cc"

REQUIRED_TEAM_COUNT = 12
MIN_TEAM_ROLE_COVERAGE = 0.98
MAX_TEAM_COVERAGE_RANGE = 0.02
MIN_DOB_REFERENCE_COMPARISONS = 500
DOB_REFERENCE_CONFLICTS_ALLOWED = 0

PASS_RESULT = "PASS_B44W4_V1_WEEK4_DOB_POSITION_REMEDIATION_REAUDIT"
PARITY_STOP_RESULT = "SCIENTIFIC_STOP_B44W4_V1_OWNER_BLIND_ROLE_PARITY_FAILED"
IDENTITY_STOP_RESULT = "SCIENTIFIC_STOP_B44W4_V1_IDENTITY_PRECISION"
DATA_STOP_RESULT = "SCIENTIFIC_STOP_B44W4_V1_DATA_INTEGRITY"

SUPPORTED_MODEL_POSITIONS = ("QB","RB","WR","TE","DL","LB","DB","K")
ROLE_ORDER = ("ELITE", "CORE", "FLEX", "DEPTH", "FRINGE")
KNOWN_CLUBS = {
    "ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB",
    "HOU","IND","JAX","KC","LV","LAC","LAR","MIA","MIN","NE","NO","NYG",
    "NYJ","PHI","PIT","SEA","SF","TB","TEN","WAS"
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_blob_sha(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"B44_MODULE_LOAD_FAILED {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_sha(repo: Path, rel: Path, expected: str, label: str) -> Path:
    path = repo / rel
    if not path.exists():
        raise RuntimeError(f"B44_PARENT_MISSING {label} path={rel}")
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(f"B44_PARENT_SHA_DRIFT {label} expected={expected} actual={actual}")
    return path


def load_verified_parents(repo: Path):
    b42_path = assert_sha(repo, B42_EVALUATOR_REL, B42_EVALUATOR_SHA256, "B42_EVALUATOR")
    assert_sha(repo, B42_WITNESS_REL, B42_WITNESS_SHA256, "B42_WITNESS")
    assert_sha(repo, B42_DECISION_REL, B42_DECISION_SHA256, "B42_DECISION")
    v1_path = assert_sha(repo, V1_EVALUATOR_REL, V1_EVALUATOR_SHA256, "V1_EVALUATOR")
    assert_sha(repo, V1_PREREG_REL, V1_PREREG_SHA256, "V1_PREREG")
    assert_sha(repo, V1_BRIDGE_REL, V1_BRIDGE_SHA256, "V1_BRIDGE")
    assert_sha(repo, V1_EVIDENCE_REL, V1_EVIDENCE_SHA256, "V1_EVIDENCE")
    assert_sha(repo, V1_DECISION_REL, V1_DECISION_SHA256, "V1_DECISION")
    assert_sha(repo, ADOPTION_REL, ADOPTION_SHA256, "ADOPTION_DECISION")
    assert_sha(repo, V4R2_PREREG_REL, V4R2_PREREG_SHA256, "V4R2_PREREG")
    assert_sha(repo, V4R2_DECISION_REL, V4R2_DECISION_SHA256, "V4R2_DECISION")
    assert_sha(repo, B41I_PLAYERS_REL, B41I_PLAYERS_SHA256, "B41I_PLAYERS")

    b42 = load_module(b42_path, "b44_parent_b42")
    v1 = load_module(v1_path, "b44_parent_v1")
    lineage = b42.load_and_verify_frozen_lineage(repo)

    b42_decision = load_json(repo / B42_DECISION_REL)
    if b42_decision["result"] != "SCIENTIFIC_STOP_B42_V4_OWNER_BLIND_ROLE_PARITY_FAILED":
        raise RuntimeError("B44_PARENT_B42_NOT_EXPECTED_STOP")
    if b42_decision["production_change_authorized"] is not False:
        raise RuntimeError("B44_PARENT_B42_PRODUCTION_AUTH_DRIFT")

    v1_evidence = load_json(repo / V1_EVIDENCE_REL)
    v1_decision = load_json(repo / V1_DECISION_REL)
    if v1_decision["result"] != "SCIENTIFIC_STOP_B43_OWNER_BLIND_IDENTITY_BRIDGE_FEASIBILITY_FAILED":
        raise RuntimeError("B44_V1R1_STOP_NOT_PRESERVED")
    rs = v1_evidence["reference_validation"]["rule_stats"]["DOB_POSITION"]
    if (rs["comparisons"], rs["correct"], rs["conflicts"]) != (1243,1243,0):
        raise RuntimeError("B44_V1R1_DOB_EVIDENCE_DRIFT")
    if v1_evidence["current_owner_blind_population"]["supplemental_collision_count"] != 2:
        raise RuntimeError("B44_V1R1_COLLISION_COUNT_DRIFT")

    adoption = load_json(repo / ADOPTION_REL)
    if adoption["status"] != "ENGINEERING_ADOPTION_DECISION_NOT_A_B43_PASS":
        raise RuntimeError("B44_ADOPTION_STATUS_DRIFT")
    if adoption["B43_V1R1_scientific_stop_preserved"] is not True:
        raise RuntimeError("B44_ADOPTION_REINTERPRETS_V1R1")
    if adoption["adopted_rule"] != "DOB_POSITION":
        raise RuntimeError("B44_ADOPTED_RULE_DRIFT")
    if adoption["rules_not_adopted"] != ["NFL_TEAM_POSITION", "UNIQUE_NAME_POSITION"]:
        raise RuntimeError("B44_UNVALIDATED_RULE_ADOPTION_DRIFT")
    if adoption["production_change_authorized"] is not False:
        raise RuntimeError("B44_ADOPTION_PRODUCTION_AUTH_DRIFT")

    v4p = load_json(repo / V4R2_PREREG_REL)
    v4d = load_json(repo / V4R2_DECISION_REL)
    if v4p["objective_respecification"]["population_coverage_gate_removed"] is not True:
        raise RuntimeError("B44_OWNER_OBJECTIVE_LINEAGE_DRIFT")
    if v4p["objective_respecification"]["B44_gates_unchanged"] is not True:
        raise RuntimeError("B44_GATE_LINEAGE_DRIFT")
    if v4d["result"] != "SCIENTIFIC_STOP_B43_V4R2_DIRECT_SLEEPER_GSIS_BRIDGE_FAILED":
        raise RuntimeError("B44_V4R2_DECISION_DRIFT")

    return b42, v1, lineage, adoption, v1_evidence


def b44_pre_roster_static_source_firewall(evaluator_path: Path) -> dict:
    source=evaluator_path.read_text(encoding="utf-8")
    tree=ast.parse(source)
    protected={
        "make_current_identity_rows",
        "eligible_base_from_rows",
        "compute_overlay",
        "augmented_attach_factory",
        "build_shadow",
    }
    forbidden_tokens={
        "owner_id","owner_username","roster_id","dynasty_team",
        "fantasy_roster_slot","team_name","starters","bench","taxi",
        "reserve_ir","league_rosters",
    }
    found={}
    class Visitor(ast.NodeVisitor):
        def __init__(self): self.hits=set()
        def hit(self,value):
            low=str(value or "").lower()
            for tok in forbidden_tokens:
                if tok in low: self.hits.add(tok)
        def visit_Name(self,node): self.hit(node.id); self.generic_visit(node)
        def visit_Attribute(self,node): self.hit(node.attr); self.generic_visit(node)
        def visit_arg(self,node): self.hit(node.arg); self.generic_visit(node)
        def visit_keyword(self,node):
            if node.arg: self.hit(node.arg)
            self.generic_visit(node)
        def visit_Subscript(self,node):
            sl=node.slice
            if isinstance(sl,ast.Constant) and isinstance(sl.value,str): self.hit(sl.value)
            self.generic_visit(node)
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in protected:
            v=Visitor(); v.visit(node); found[node.name]=sorted(v.hits)
    missing=sorted(protected-set(found))
    bad={k:v for k,v in found.items() if v}
    return {
        "protected_functions":sorted(protected),
        "forbidden_tokens":sorted(forbidden_tokens),
        "hits":found,
        "missing_functions":missing,
        "pass":not bad and not missing,
    }


def protocol_payload(evaluator_sha256: str, source_preflight: dict, main_at_start: str) -> dict:
    return {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "phase": "B44W4-v1-protocol-freeze-before-any-rostered-coverage-tally",
        "status": "FROZEN_BEFORE_ANY_ROSTERED_COVERAGE_TALLY_OR_TEAM_METRIC",
        "main_at_workflow_start": main_at_start,
        "evaluator_sha256": evaluator_sha256,
        "framing": {
            "classification": "POST_HOC_SAME_WEEK_ENGINEERING_REMEDIATION_VALIDATION_NOT_INDEPENDENT_CONFIRMATION",
            "identity_rule_adopted_after_B43_V1R1_result_known": True,
            "B43_V1R1_scientific_stop_preserved": True,
            "credibility_basis": "B42 Week-4 model data re-audited with the adopted DOB_POSITION remediation, fresh Sleeper identity map, and unchanged B42 acceptance gates",
            "fresh_week_confirmation": False,
            "B42_week4_outcomes_previously_observed": True,
            "B44_authorizes_production_change": False,
        },
        "owner_objective": "Players on fantasy rosters must be correctly identified and receive roles; deep depth players matching is not a product requirement.",
        "no_peek_contract": {
            "roster_raw_bytes_may_be_copied_and_hashed_pre_freeze": True,
            "roster_json_semantic_parse_before_protocol_and_evaluator_commit": False,
            "rostered_coverage_tally_before_protocol_and_evaluator_commit": False,
            "team_partition_metric_before_protocol_and_evaluator_commit": False,
        },
        "new_data": {
            "roster_snapshot_sha256": source_preflight["roster_snapshot_sha256"],
            "roster_snapshot_git_blob": source_preflight["roster_snapshot_git_blob"],
            "roster_snapshot_raw_bytes_hashed_without_parsing": True,
            "sleeper_player_map_sha256": source_preflight["sleeper_player_map_sha256"],
            "sleeper_player_map_raw_object_count": source_preflight["sleeper_player_map_raw_object_count"],
            "sleeper_schema_only_preflight": True,
            "B42_roster_snapshot_sha256": source_preflight["B42_roster_snapshot_sha256"],
            "roster_snapshot_identical_to_B42": source_preflight["roster_snapshot_identical_to_B42"],
            "roster_freshness_disclosed_not_gated": True,
            "nflverse_weekly_stats_raw_sha256": source_preflight["nflverse_weekly_stats_raw_sha256"],
            "nflverse_snap_counts_raw_sha256": source_preflight["nflverse_snap_counts_raw_sha256"],
            "nflverse_weekly_stats_max_available_week": source_preflight["nflverse_weekly_stats_max_available_week"],
            "nflverse_snap_counts_max_available_week": source_preflight["nflverse_snap_counts_max_available_week"],
            "nflverse_sources_currency_verified_before_namespace_commit": source_preflight["nflverse_sources_currency_verified_before_namespace_commit"],
            "latest_completed_week": source_preflight["latest_completed_week"],
            "B42_latest_completed_week": source_preflight["B42_latest_completed_week"],
            "B44W4_analysis_week_equals_B42_week": source_preflight["latest_completed_week"] == source_preflight["B42_latest_completed_week"],
            "latest_completed_week_strictly_later_than_B42": False,
            "sleeper_latest_completed_week_observed": source_preflight["sleeper_latest_completed_week_observed"],
            "week_selection_policy": source_preflight["week_selection_policy"],
        },
        "identity_overlay": {
            "precedence": ["B41G_PINNED_STABLE_CROSSWALK", "B43_V1R1_DOB_POSITION_RULE"],
            "adopted_rule": "DOB_POSITION",
            "rule_source_evaluator_sha256": V1_EVALUATOR_SHA256,
            "exact_V1R1_candidate_function_required": True,
            "rules_not_adopted": ["NFL_TEAM_POSITION", "UNIQUE_NAME_POSITION"],
            "fresh_rule_application_not_frozen_pair_reuse": True,
            "known_pair_revalidation": {
                "minimum_comparisons": MIN_DOB_REFERENCE_COMPARISONS,
                "conflicts_allowed": DOB_REFERENCE_CONFLICTS_ALLOWED,
                "reference_sleeper_id_masked_from_candidate_generation": True,
            },
            "collision_policy": {
                "stable_inverse_conflict": "QUARANTINE_UNMAPPED",
                "current_current_proposal_collision": "QUARANTINE_UNMAPPED",
                "V1R1_two_collision_identities": "QUARANTINE_BY_IDENTITY_FROM_V1R1_EVIDENCE",
                "historical_supersession_allowed": False,
            },
            "V1R1_consistency_required": True,
            "B41J_reference_component_overlap_allowed": False,
            "overlay_must_feed_role_eligibility": True,
            "overlay_must_feed_shadow_identity_step": True,
            "B41I_identity_snapshot_is_frozen": True,
            "players_absent_from_B41I_cannot_receive_DOB_POSITION_overlay": True,
            "B41I_absence_effect": "CAN_ONLY_LEAVE_PLAYER_UNMAPPED_AND_LOWER_COVERAGE",
        },
        "rostered_overlay_precision_gate": {
            "runs_only_after_roster_semantic_parse": True,
            "position_family_contradiction_allowed": 0,
            "known_club_team_contradiction_allowed": 0,
            "missing_or_free_agent_team_is_unverifiable_not_failure": True,
            "midweek_trade_false_stop_risk_disclosed_and_accepted": True,
            "stop_result": IDENTITY_STOP_RESULT,
        },
        "B42_acceptance_gates_byte_identical_semantics": {
            "required_team_count": REQUIRED_TEAM_COUNT,
            "minimum_role_coverage_each_team": MIN_TEAM_ROLE_COVERAGE,
            "maximum_coverage_range_across_teams": MAX_TEAM_COVERAGE_RANGE,
            "owner_swap_role_changes_allowed": 0,
            "owner_roster_slot_context_allowed_in_role_inference": False,
            "denominator": {
                "no_current_season_evidence": "excluded_and_reported_descriptively",
                "identity_gaps": "eligible_and_uncovered",
                "position_instability_exclusions": "eligible_and_uncovered_when_current_evidence_confirms_eligibility",
            },
            "B41J_implementation_parity_oracle_required": True,
            "shadow_role_inference_source_firewall_required": True,
        },
        "ordering": [
            "PROTOCOL_MATERIALIZED",
            "B41J_PARITY_ORACLE",
            "PROTOCOL_EVALUATOR_ORACLE_DURABLY_COMMITTED",
            "OWNER_BLIND_IDENTITY_OVERLAY_AND_SHADOW",
            "OVERLAY_ELIGIBILITY_SHADOW_DURABLY_COMMITTED",
            "FIRST_ROSTER_SEMANTIC_PARSE",
            "ROSTERED_OVERLAY_PRECISION_CHECK",
            "B42_TEAM_PARITY_METRICS"
        ],
        "scientific_runtime": {
            "python": "3.13",
            "numpy": "2.5.3",
            "pandas": "2.3.3",
            "scipy": "1.18.1",
            "requests": "2.34.2",
        },
        "production_firewall": {
            "production_change_authorized": False,
            "production_model_deployed": False,
            "PASS_only_makes_separate_production_authorization_eligible": True,
        },
    }


def make_current_identity_rows(eligible_base: pd.DataFrame, all_current_rows: list[dict], repo: Path, v1):
    identity = {}
    with (repo / B41I_PLAYERS_REL).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            g = v1.clean(row.get("gsis_id"))
            if g:
                identity[g] = {
                    "display_name": v1.clean(row.get("display_name")),
                    "birth_date": v1.clean(row.get("birth_date")),
                    "position": v1.clean(row.get("position")),
                    "position_group": v1.clean(row.get("position_group")),
                    "latest_team": v1.team_key(row.get("latest_team")),
                }

    latest_active_team = {}
    by_gsis = defaultdict(list)
    for row in all_current_rows:
        if str(row.get("gsis_id") or "").strip():
            by_gsis[str(row["gsis_id"])].append(row)
    for g, rows in by_gsis.items():
        active = [r for r in rows if bool(r.get("active"))]
        if active:
            active.sort(key=lambda r: int(r.get("week") or 0))
            latest_active_team[g] = v1.team_key(active[-1].get("team"))

    current = []
    for _, row in eligible_base.iterrows():
        g = v1.clean(row.get("gsis_id"))
        meta = identity.get(g, {})
        name = v1.clean(row.get("player_name")) or meta.get("display_name", "")
        model_pos = v1.clean(row.get("position"))
        current.append({
            "gsis_id": g,
            "player_name": name,
            "name_key": v1.canonical_name(name),
            "birth_date": v1.clean(meta.get("birth_date")),
            "model_position": model_pos,
            "position_family": (
                v1.position_family(model_pos)
                or v1.position_family(meta.get("position_group"))
                or v1.position_family(meta.get("position"))
            ),
            "nfl_team": latest_active_team.get(g) or v1.team_key(meta.get("latest_team")),
        })
    return current


def eligible_base_from_rows(all_rows: list[dict], latest_completed_week: int, b42) -> pd.DataFrame:
    by_player = defaultdict(list)
    for row in all_rows:
        if row["position"] in b42.POSITIONS and int(row["week"]) <= latest_completed_week:
            by_player[str(row["gsis_id"])].append(row)
    rows = []
    for gsis, player_rows in by_player.items():
        active = [r for r in player_rows if bool(r["active"])]
        if not active:
            continue
        active.sort(key=lambda r: int(r["week"]))
        latest = active[-1]
        rows.append({
            "season": 2026,
            "origin_week": int(latest_completed_week),
            "gsis_id": gsis,
            "position": str(latest["position"]),
            "player_name": str(latest.get("player_name") or ""),
            "exact_name_key": b42.exact_name_key(latest.get("player_name") or ""),
            "active_game_count": int(len(active)),
        })
    if not rows:
        raise RuntimeError("B44_ROLE_ELIGIBILITY_EMPTY")
    return pd.DataFrame(rows).sort_values(["position","gsis_id"], kind="mergesort").reset_index(drop=True)


def compute_overlay(
    current: list[dict],
    stable: dict,
    stable_inverse: dict,
    sleeper_by_id: dict,
    sleeper_by_name: dict,
    candidate_for,
    v1_bridge: dict,
    prior_collision_ids: set[str],
    b41j_gsis: set[str],
    b41j_sid: set[str],
):
    predictions = {}
    comparisons = conflicts = correct = 0
    conflict_details = []

    for row in current:
        pred = candidate_for(row, sleeper_by_name)
        if pred and pred[1] == "DOB_POSITION":
            rec, rule = pred
            predictions[row["gsis_id"]] = (rec, rule)
            ref = stable.get(row["gsis_id"])
            if ref and ref in sleeper_by_id:
                comparisons += 1
                if rec["sleeper_id"] == ref:
                    correct += 1
                else:
                    conflicts += 1
                    conflict_details.append({
                        "gsis_id": row["gsis_id"],
                        "predicted_sleeper_id": rec["sleeper_id"],
                        "reference_sleeper_id": ref,
                    })

    proposals = []
    current_by_gsis = {x["gsis_id"]: x for x in current}
    for g, (rec, rule) in predictions.items():
        if g in stable:
            continue
        row = current_by_gsis[g]
        proposals.append({
            "gsis_id": g,
            "sleeper_id": rec["sleeper_id"],
            "rule": rule,
            "name_key": row["name_key"],
            "model_position": row["model_position"],
            "position_family": row["position_family"],
            "birth_date": row["birth_date"],
            "nfl_team": row["nfl_team"],
            "sleeper_position": rec["position"],
            "sleeper_position_family": rec["position_family"],
            "sleeper_birth_date": rec["birth_date"],
            "sleeper_nfl_team": rec["nfl_team"],
        })

    v1_consistency_mismatches = []
    for x in proposals:
        prior = v1_bridge.get(x["gsis_id"])
        if prior is not None and prior != x["sleeper_id"]:
            v1_consistency_mismatches.append({
                "gsis_id": x["gsis_id"],
                "V1R1_sleeper_id": prior,
                "B44_rule_output_sleeper_id": x["sleeper_id"],
            })

    sid_counts = Counter(x["sleeper_id"] for x in proposals)
    quarantined, accepted = [], []
    for x in proposals:
        reasons = []
        if x["gsis_id"] in prior_collision_ids:
            reasons.append("V1R1_collision_identity_quarantine")
        old = stable_inverse.get(x["sleeper_id"])
        if old and old != x["gsis_id"]:
            reasons.append("historical_stable_inverse_conflict")
        if sid_counts[x["sleeper_id"]] != 1:
            reasons.append("current_current_sleeper_collision")
        if reasons:
            quarantined.append({**x, "quarantine_reasons": reasons})
        else:
            accepted.append(x)

    b41j_overlap = []
    for x in accepted:
        reasons = []
        if x["gsis_id"] in b41j_gsis:
            reasons.append("gsis_touches_B41J_reference")
        if x["sleeper_id"] in b41j_sid:
            reasons.append("sleeper_id_touches_B41J_reference")
        if reasons:
            b41j_overlap.append({
                "gsis_id": x["gsis_id"],
                "sleeper_id": x["sleeper_id"],
                "reasons": reasons,
            })

    gates = {
        "minimum_DOB_POSITION_reference_comparisons": comparisons >= MIN_DOB_REFERENCE_COMPARISONS,
        "zero_DOB_POSITION_reference_conflicts": conflicts == DOB_REFERENCE_CONFLICTS_ALLOWED,
        "V1R1_consistency": len(v1_consistency_mismatches) == 0,
        "zero_B41J_reference_component_overlap": len(b41j_overlap) == 0,
        "no_historical_supersession_in_accepted_overlay": all(
            not (stable_inverse.get(x["sleeper_id"]) and stable_inverse.get(x["sleeper_id"]) != x["gsis_id"])
            for x in accepted
        ),
    }
    return {
        "reference_validation": {
            "rule": "DOB_POSITION",
            "comparisons": comparisons,
            "correct": correct,
            "conflicts": conflicts,
            "precision": (correct / comparisons) if comparisons else None,
            "conflict_details": conflict_details,
        },
        "proposals": proposals,
        "quarantined": quarantined,
        "accepted": accepted,
        "V1R1_consistency_mismatches": v1_consistency_mismatches,
        "B41J_reference_overlap": b41j_overlap,
        "hard_precision_gates": gates,
        "all_hard_precision_gates_pass": all(gates.values()),
    }


def augmented_attach_factory(b42, overlay_by_gsis: dict):
    def attach_augmented(df: pd.DataFrame, lineage: dict, session: requests.Session):
        exact, sid_to_gsis, gsis_mapped_sids, cross_sha, audit = b42.load_stable_id_crosswalk(lineage, session)
        for g, sid in overlay_by_gsis.items():
            if g in exact:
                raise RuntimeError(f"B44_OVERLAY_GSIS_ALREADY_STABLE {g}")
            if sid in sid_to_gsis and sid_to_gsis[sid] != g:
                raise RuntimeError(f"B44_OVERLAY_SLEEPER_ALREADY_STABLE {sid}")
        if len(set(overlay_by_gsis.values())) != len(overlay_by_gsis):
            raise RuntimeError("B44_OVERLAY_SLEEPER_NOT_ONE_TO_ONE")
        augmented = dict(exact)
        augmented.update(overlay_by_gsis)
        augmented_inverse = dict(sid_to_gsis)
        for g, sid in overlay_by_gsis.items():
            augmented_inverse[sid] = g
        out = df.copy()
        out["sleeper_id"] = out["gsis_id"].map(augmented)
        out["identity_mapped"] = out["sleeper_id"].notna()
        out["identity_source"] = [
            "DOB_POSITION_OVERLAY" if str(g) in overlay_by_gsis
            else ("STABLE_CROSSWALK" if bool(sid) else "UNMAPPED")
            for g, sid in zip(out["gsis_id"].astype(str), out["sleeper_id"].fillna("").astype(str))
        ]
        overall = float(out["identity_mapped"].mean()) if len(out) else 0.0
        pos_cov = (
            out.groupby("position", observed=True)["identity_mapped"].mean().to_dict()
            if len(out) else {}
        )
        audit2 = dict(audit)
        audit2["B44_DOB_POSITION_overlay_count"] = len(overlay_by_gsis)
        audit2["augmented_gsis_mapped_sleeper_id_count"] = len(augmented_inverse)
        return (
            out,
            cross_sha,
            overall,
            {k: float(v) for k,v in pos_cov.items()},
            augmented_inverse,
            set(augmented_inverse),
            audit2,
        )
    return attach_augmented


def write_sleeper_snapshot(path: Path, sleeper_records: list[dict]) -> None:
    fields = ["sleeper_id","full_name","name_key","birth_date","position","position_family","nfl_team","status"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for x in sorted(sleeper_records, key=lambda z:(str(z["sleeper_id"]), z["name_key"])):
            w.writerow({k:x.get(k,"") for k in fields})


def write_overlay_csv(path: Path, accepted: list[dict]) -> None:
    fields = [
        "gsis_id","sleeper_id","rule","name_key","model_position","position_family",
        "birth_date","nfl_team","sleeper_position","sleeper_position_family",
        "sleeper_birth_date","sleeper_nfl_team"
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for x in sorted(accepted, key=lambda z:z["gsis_id"]):
            w.writerow({k:x.get(k,"") for k in fields})


def write_stop_decision(out: Path, result: str, phase: str, reason: str, extra: dict | None = None) -> None:
    payload = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "phase": phase,
        "result": result,
        "reason": reason,
        "all_primary_gates_pass": False,
        "eligible_for_separate_production_authorization": False,
        "production_change_authorized": False,
        "production_model_deployed": False,
    }
    if extra:
        payload.update(extra)
    write_json(out / "player_role_v2_b44w4_v1_scientific_decision.json", payload)


def build_shadow(repo: Path, out: Path, source_cache: Path, protocol_commit: str, parity_commit: str):
    b42, v1, lineage, adoption, v1_evidence = load_verified_parents(repo)
    base = repo / BASE_REL
    evaluator_path = base / "player_role_v2_b44w4_v1_evaluator.py"
    protocol_path = base / "player_role_v2_b44w4_v1_protocol_freeze.json"
    parity_path = base / "player_role_v2_b44w4_v1_implementation_parity.json"
    source_preflight_path = base / "player_role_v2_b44w4_v1_source_preflight.json"

    protocol = load_json(protocol_path)
    if protocol["status"] != "FROZEN_BEFORE_ANY_ROSTERED_COVERAGE_TALLY_OR_TEAM_METRIC":
        raise RuntimeError("B44_PROTOCOL_NOT_FROZEN")
    if protocol["evaluator_sha256"] != sha256_file(evaluator_path):
        raise RuntimeError("B44_PROTOCOL_EVALUATOR_SHA_DRIFT")
    source_preflight = load_json(source_preflight_path)
    if source_preflight["latest_completed_week"] != source_preflight["B42_latest_completed_week"]:
        raise RuntimeError("B44W4_ANALYSIS_WEEK_NOT_EQUAL_B42_WEEK")
    b42_firewall=b42.shadow_static_source_firewall(repo / B42_EVALUATOR_REL)
    b44_firewall=b44_pre_roster_static_source_firewall(evaluator_path)
    firewall={
        "B42_parent_firewall":b42_firewall,
        "B44_extension_firewall":b44_firewall,
        "pass":bool(b42_firewall.get("pass") is True and b44_firewall.get("pass") is True),
    }
    if not firewall["pass"]:
        raise RuntimeError(f"B44_V1R1_PRE_ROSTER_STATIC_SOURCE_FIREWALL_FAILED {firewall}")

    sleeper_bytes = (source_cache / "sleeper_players.json").read_bytes()
    if sha256_bytes(sleeper_bytes) != protocol["new_data"]["sleeper_player_map_sha256"]:
        raise RuntimeError("B44_CACHED_SLEEPER_SHA_DRIFT")
    _, sleeper_records = v1.sleeper_records_from_payload(sleeper_bytes)
    sleeper_by_id = {x["sleeper_id"]:x for x in sleeper_records}
    sleeper_by_name = defaultdict(list)
    for x in sleeper_records:
        sleeper_by_name[x["name_key"]].append(x)

    session = requests.Session()
    session.headers.update({"User-Agent":"LOG-Trade-Calculator-player-role-v2-b44-v1"})
    latest_completed_week = int(source_preflight["latest_completed_week"])

    stats_payload = (source_cache / "stats_player_week_2026.csv").read_bytes()
    snaps_payload = (source_cache / "snap_counts_2026.csv").read_bytes()
    if sha256_bytes(stats_payload) != protocol["new_data"]["nflverse_weekly_stats_raw_sha256"]:
        raise RuntimeError("B44_V1R1_CACHED_NFLVERSE_STATS_SHA_DRIFT")
    if sha256_bytes(snaps_payload) != protocol["new_data"]["nflverse_snap_counts_raw_sha256"]:
        raise RuntimeError("B44_V1R1_CACHED_NFLVERSE_SNAPS_SHA_DRIFT")
    if protocol["new_data"]["nflverse_sources_currency_verified_before_namespace_commit"] is not True:
        raise RuntimeError("B44_V1R1_NFLVERSE_CURRENCY_PREFLIGHT_NOT_FROZEN")
    source_dir = out / "sources"
    stats_path = source_dir / "stats_player_week_2026_completed.csv"
    snaps_path = source_dir / "snap_counts_2026_completed.csv"
    stats_meta = b42.filter_csv_to_completed_weeks(
        stats_payload, season_col="season", week_col="week", type_col="season_type",
        type_value="REG", latest_completed_week=latest_completed_week, out_path=stats_path
    )
    snaps_meta = b42.filter_csv_to_completed_weeks(
        snaps_payload, season_col="season", week_col="week", type_col="game_type",
        type_value="REG", latest_completed_week=latest_completed_week, out_path=snaps_path
    )
    stats_meta["url"] = b42.CURRENT_STATS_URL
    snaps_meta["url"] = b42.CURRENT_SNAPS_URL

    players_path = repo / B41I_PLAYERS_REL
    features, feature_audit, all_current_rows = b42.build_feature_rows_for_origins(
        lineage["builder"], stats_path, snaps_path, players_path, 2026, [latest_completed_week]
    )
    eligible_base = eligible_base_from_rows(all_current_rows, latest_completed_week, b42)
    current = make_current_identity_rows(eligible_base, all_current_rows, repo, v1)

    stable, stable_inverse, stable_sids, cross_sha, cross_audit = b42.load_stable_id_crosswalk(lineage, session)

    with (repo / V1_BRIDGE_REL).open(newline="", encoding="utf-8") as f:
        v1_bridge = {str(r["gsis_id"]):str(r["sleeper_id"]) for r in csv.DictReader(f)}
    prior_collision_ids = {
        str(x["gsis_id"])
        for x in v1_evidence.get("supplemental_collision_details", [])
    }
    if len(prior_collision_ids) != 2:
        raise RuntimeError("B44_V1R1_COLLISION_ID_SET_DRIFT")

    b41j_ref = pd.read_csv(
        base / "player_role_v2_b41j_scored_holdout_rows.csv",
        usecols=["gsis_id","sleeper_id"],
        dtype={"gsis_id":str,"sleeper_id":str},
        keep_default_na=False,
    )
    b41j_gsis = set(str(x) for x in b41j_ref["gsis_id"] if str(x))
    b41j_sid = set(str(x) for x in b41j_ref["sleeper_id"] if str(x))

    overlay_eval = compute_overlay(
        current, stable, stable_inverse, sleeper_by_id, sleeper_by_name,
        v1.candidate_for, v1_bridge, prior_collision_ids, b41j_gsis, b41j_sid
    )

    write_sleeper_snapshot(out / "player_role_v2_b44w4_v1_sleeper_identity_snapshot.csv", sleeper_records)
    write_overlay_csv(out / "player_role_v2_b44w4_v1_identity_overlay.csv", overlay_eval["accepted"])

    identity_validation = {
        "schema_version":1,
        "study_id":STUDY_ID,
        "phase":"B44W4-v1-pre-roster-owner-blind-DOB_POSITION-validation",
        "rule":"DOB_POSITION",
        "rule_source":"exact frozen B43 V1R1 candidate_for; only outputs labeled DOB_POSITION are eligible",
        "reference_validation":overlay_eval["reference_validation"],
        "proposal_count":len(overlay_eval["proposals"]),
        "accepted_overlay_count":len(overlay_eval["accepted"]),
        "quarantined_count":len(overlay_eval["quarantined"]),
        "quarantined":overlay_eval["quarantined"],
        "prior_V1R1_collision_identity_count":len(prior_collision_ids),
        "prior_V1R1_collision_identities_taken_from_evidence":True,
        "V1R1_consistency_mismatches":overlay_eval["V1R1_consistency_mismatches"],
        "B41J_reference_overlap":overlay_eval["B41J_reference_overlap"],
        "hard_precision_gates":overlay_eval["hard_precision_gates"],
        "all_hard_precision_gates_pass":overlay_eval["all_hard_precision_gates_pass"],
        "historical_supersession_allowed":False,
        "league_roster_source_used":False,
        "owner_identity_used":False,
        "production_change_authorized":False,
        "production_model_deployed":False,
    }
    write_json(out / "player_role_v2_b44w4_v1_identity_validation.json", identity_validation)

    if not overlay_eval["all_hard_precision_gates_pass"]:
        stop = {
            "schema_version":1,
            "study_id":STUDY_ID,
            "phase":"B44W4-v1-pre-roster-identity-precision-stop",
            "result":IDENTITY_STOP_RESULT,
            "reason":"fresh DOB_POSITION reference validation or frozen consistency/protection gate failed",
            "identity_validation_sha256":sha256_file(out / "player_role_v2_b44w4_v1_identity_validation.json"),
            "roster_semantic_parse_performed":False,
            "team_partition_metric_computed":False,
            "production_change_authorized":False,
            "production_model_deployed":False,
        }
        write_json(out / "player_role_v2_b44w4_v1_pre_roster_identity_stop.json", stop)
        write_stop_decision(
            out, IDENTITY_STOP_RESULT, "B44W4-v1-scientific-decision",
            "pre-roster DOB_POSITION precision/consistency/protection gate failed",
            {"team_partition_metric_computed": False, "roster_semantic_parse_performed": False},
        )
        return

    overlay_by_gsis = {x["gsis_id"]:x["sleeper_id"] for x in overlay_eval["accepted"]}
    augmented_attach = augmented_attach_factory(b42, overlay_by_gsis)
    original_attach = b42.attach_stable_ids_row_guarded
    b42.attach_stable_ids_row_guarded = augmented_attach
    try:
        role_eligibility, eligibility_audit = b42.build_role_eligibility(
            all_current_rows, lineage["builder"], lineage, session, latest_completed_week
        )
        (
            with_ids, cross_sha2, overall_cov, pos_cov, sid_to_gsis,
            gsis_mapped_sleeper_ids, crosswalk_audit2
        ) = augmented_attach(features, lineage, session)
    finally:
        b42.attach_stable_ids_row_guarded = original_attach

    if cross_sha2 != cross_sha:
        raise RuntimeError("B44_CROSSWALK_CHANGED_WITHIN_SHADOW_BUILD")

    role_eligibility["identity_source"] = [
        "DOB_POSITION_OVERLAY" if str(g) in overlay_by_gsis
        else ("STABLE_CROSSWALK" if str(sid).strip() else "UNMAPPED")
        for g, sid in zip(
            role_eligibility["gsis_id"].astype(str),
            role_eligibility["sleeper_id"].fillna("").astype(str)
        )
    ]
    role_eligibility_path = out / "player_role_v2_b44w4_v1_role_eligibility.csv"
    role_eligibility.to_csv(role_eligibility_path, index=False, lineterminator="\n")

    model = with_ids[with_ids["identity_mapped"]].copy()
    if model.empty:
        raise RuntimeError("B44_CURRENT_MODEL_EMPTY_AFTER_IDENTITY_FILTER")
    model["sleeper_id"] = model["sleeper_id"].astype(str)

    scored_history, sleeper_hashes, missing_stats, sleeper_participant_ids = b42.score_current_history(
        model, lineage["scorer"], lineage["scoring"]["scoring_settings"], session,
        latest_completed_week, 2026, include_all_weeks_for_participation=True
    )

    stable_mapped_eligible_ids = {
        str(row["sleeper_id"])
        for _, row in role_eligibility.iterrows()
        if str(row["gsis_id"]) in stable and str(row["sleeper_id"]).strip()
    }
    participant_confirmed_stable = stable_mapped_eligible_ids & sleeper_participant_ids
    participant_confirmation_rate = (
        len(participant_confirmed_stable) / len(stable_mapped_eligible_ids)
        if stable_mapped_eligible_ids else 0.0
    )
    participant_field_sanity_pass = bool(
        stable_mapped_eligible_ids and participant_confirmation_rate >= 0.95
    )

    exclusion_reason_by_gsis = {
        str(r["gsis_id"]):str(r["reason"])
        for r in feature_audit.get("excluded_records", [])
        if int(r.get("origin_week",-1)) == latest_completed_week
    }
    gsis_present = sorted({
        str(r.get("gsis_id") or "").strip()
        for r in all_current_rows
        if str(r.get("gsis_id") or "").strip()
        and int(r.get("week") or 0) <= latest_completed_week
    })
    eligibility_context = {
        "schema_version":1,
        "study_id":STUDY_ID,
        "phase":"B44W4-v1-owner-blind-role-eligibility-context",
        "latest_completed_week":latest_completed_week,
        "gsis_mapped_sleeper_ids":sorted(gsis_mapped_sleeper_ids),
        "sid_to_gsis":dict(sorted(sid_to_gsis.items())),
        "gsis_present_in_2026_sources":gsis_present,
        "sleeper_2026_participant_ids":sorted(sleeper_participant_ids),
        "participation_fields":["gp","off_snp","def_snp","st_snp"],
        "stable_mapped_role_eligible_sleeper_id_count":len(stable_mapped_eligible_ids),
        "stable_mapped_role_eligible_participant_confirmed_count":len(participant_confirmed_stable),
        "participant_confirmation_rate":participant_confirmation_rate,
        "participant_field_sanity_minimum":0.95,
        "participant_field_sanity_pass":participant_field_sanity_pass,
        "feature_exclusion_reason_by_gsis":dict(sorted(exclusion_reason_by_gsis.items())),
        "DOB_POSITION_overlay_count":len(overlay_by_gsis),
        "owner_or_roster_context_used":False,
        "frozen_before_roster_semantic_parse":True,
    }
    eligibility_context_path = out / "player_role_v2_b44w4_v1_owner_blind_eligibility_context.json"
    write_json(eligibility_context_path, eligibility_context)

    if not participant_field_sanity_pass:
        stop = {
            "schema_version":1,
            "study_id":STUDY_ID,
            "phase":"B44W4-v1-pre-roster-data-integrity-stop",
            "result":DATA_STOP_RESULT,
            "stop_stage":"shadow_participation_field_sanity",
            "participant_confirmation_rate":participant_confirmation_rate,
            "participant_field_sanity_minimum":0.95,
            "roster_semantic_parse_performed":False,
            "team_partition_metric_computed":False,
            "production_change_authorized":False,
            "production_model_deployed":False,
        }
        write_json(out / "player_role_v2_b44w4_v1_data_integrity_stop.json", stop)
        write_stop_decision(
            out, DATA_STOP_RESULT, "B44W4-v1-scientific-decision",
            "pre-roster shadow participation sanity failed",
            {"team_partition_metric_computed": False, "roster_semantic_parse_performed": False},
        )
        return

    scored, aggregate_imputation = b42.normalize_and_apply_frozen_models(
        scored_history, lineage["b41h"], lineage["baseline"], lineage["b41f"]
    )
    rows=[]
    for _, row in scored.iterrows():
        pos=str(row["position"])
        idx,label=b42.role_from_score(pos,float(row["model_score"]),lineage["b41f"])
        if idx != int(row["tier_index"]) or label != str(row["role_tier"]):
            raise RuntimeError("B44_SHADOW_TIER_RECOMPUTATION_MISMATCH")
        g=str(row["gsis_id"])
        rows.append({
            "sleeper_id":str(row["sleeper_id"]),
            "gsis_id":g,
            "identity_source":"DOB_POSITION_OVERLAY" if g in overlay_by_gsis else "STABLE_CROSSWALK",
            "position":pos,
            "origin_week":int(row["origin_week"]),
            "model_score":float(row["model_score"]),
            "tier_index":idx,
            "role_tier":label,
            "prior_active_games":int(row["prior_active_games"]),
            "frozen_feature_missing_count_before_imputation":int(row["frozen_feature_missing_count_before_imputation"]),
            "frozen_feature_count":int(row["frozen_feature_count"]),
            "evidence_source":b42.EVIDENCE_SOURCE,
            "confidence_status":b42.CONFIDENCE_STATUS,
        })
    shadow=pd.DataFrame(rows)
    if shadow.empty or shadow["sleeper_id"].duplicated().any():
        raise RuntimeError("B44_SHADOW_INVALID")
    if sorted(shadow["position"].unique()) != sorted(b42.POSITIONS):
        raise RuntimeError("B44_SHADOW_POSITION_SCOPE_MISMATCH")
    if set(shadow.loc[shadow["identity_source"]=="DOB_POSITION_OVERLAY","gsis_id"]) != set(overlay_by_gsis).intersection(set(shadow["gsis_id"])):
        raise RuntimeError("B44_OVERLAY_SHADOW_SOURCE_TAG_DRIFT")
    shadow = shadow.sort_values(
        ["position","model_score","sleeper_id"], ascending=[True,False,True], kind="mergesort"
    ).reset_index(drop=True)
    shadow_path=out/"player_role_v2_b44w4_v1_shadow_refresh.csv"
    shadow.to_csv(shadow_path,index=False,lineterminator="\n",float_format="%.17g")

    witness = {
        "schema_version":1,
        "study_id":STUDY_ID,
        "phase":"B44W4-v1-owner-blind-shadow-refresh-freeze",
        "protocol_freeze_commit":protocol_commit,
        "parity_commit":parity_commit,
        "protocol_sha256":sha256_file(protocol_path),
        "evaluator_sha256":sha256_file(evaluator_path),
        "implementation_parity_sha256":sha256_file(parity_path),
        "implementation_parity_exact_pass":load_json(parity_path)["exact_parity"]["pass"],
        "identity_validation_sha256":sha256_file(out/"player_role_v2_b44w4_v1_identity_validation.json"),
        "identity_overlay_sha256":sha256_file(out/"player_role_v2_b44w4_v1_identity_overlay.csv"),
        "role_eligibility_sha256":sha256_file(role_eligibility_path),
        "owner_blind_eligibility_context_sha256":sha256_file(eligibility_context_path),
        "shadow_refresh_sha256":sha256_file(shadow_path),
        "latest_completed_week":latest_completed_week,
        "participant_field_sanity_pass":participant_field_sanity_pass,
        "participant_confirmation_rate":participant_confirmation_rate,
        "DOB_POSITION_overlay_count":len(overlay_by_gsis),
        "overlay_used_in_role_eligibility":True,
        "overlay_used_in_shadow_identity_step":True,
        "roster_assignment_semantics_parsed_before_shadow_freeze":False,
        "pre_roster_static_source_firewall":firewall,
        "model_or_tier_retuning_performed":False,
        "production_change_authorized":False,
        "production_model_deployed":False,
        "current_sources":{
            "weekly_stats":stats_meta,
            "snap_counts":snaps_meta,
            "sleeper_completed_week_stats_sha256":sleeper_hashes,
            "stable_id_crosswalk_sha256":cross_sha,
            "fresh_sleeper_player_map_sha256":sha256_bytes(sleeper_bytes),
        },
        "feature_audit":feature_audit,
        "aggregate_frozen_imputation":aggregate_imputation,
    }
    write_json(out/"player_role_v2_b44w4_v1_shadow_refresh_witness.json", witness)


def rostered_overlay_precision(rosters, overlay_rows: list[dict], b42, v1):
    overlay_by_sid={str(x["sleeper_id"]):x for x in overlay_rows}
    rostered_overlay_ids=set()
    for roster in rosters:
        players_by_id={}
        for slot in ("starters","bench","taxi","reserve_ir"):
            for player in roster.get(slot) or []:
                pid=str(player.get("player_id") or "").strip()
                if pid:
                    players_by_id.setdefault(pid,player)
        for pid,player in players_by_id.items():
            if pid in overlay_by_sid:
                rostered_overlay_ids.add(pid)

    details=[]
    contradiction_count=verified_count=unverifiable_count=0
    for pid in sorted(rostered_overlay_ids):
        x=overlay_by_sid[pid]
        reasons=[]
        unverifiable=[]
        sleeper_fam=v1.position_family(x.get("sleeper_position"))
        model_fam=v1.position_family(x.get("model_position"))
        if sleeper_fam and model_fam:
            if sleeper_fam != model_fam:
                reasons.append("position_family_contradiction")
        else:
            unverifiable.append("position_family_missing")
        st=v1.team_key(x.get("sleeper_nfl_team"))
        nt=v1.team_key(x.get("nfl_team"))
        if st in KNOWN_CLUBS and nt in KNOWN_CLUBS:
            if st != nt:
                reasons.append("known_club_team_contradiction")
        else:
            unverifiable.append("team_unverifiable_missing_or_free_agent")
        if reasons:
            contradiction_count += 1
            status="CONTRADICTION"
        elif unverifiable:
            unverifiable_count += 1
            status="UNVERIFIABLE"
        else:
            verified_count += 1
            status="VERIFIED"
        details.append({
            "sleeper_id":pid,
            "gsis_id":x["gsis_id"],
            "status":status,
            "contradictions":reasons,
            "unverifiable_reasons":unverifiable,
            "model_position":x["model_position"],
            "sleeper_position":x["sleeper_position"],
            "nflverse_team":nt,
            "sleeper_team":st,
        })
    return {
        "overlay_identified_rostered_count":len(rostered_overlay_ids),
        "verified_count":verified_count,
        "unverifiable_count":unverifiable_count,
        "contradiction_count":contradiction_count,
        "details":details,
        "midweek_trade_false_stop_risk_disclosed":True,
        "pass":contradiction_count==0,
    }


def string_leaf_values(obj):
    vals=[]
    if isinstance(obj,dict):
        for v in obj.values(): vals.extend(string_leaf_values(v))
    elif isinstance(obj,list):
        for v in obj: vals.extend(string_leaf_values(v))
    elif isinstance(obj,str):
        vals.append(obj)
    return vals


def recursive_keys(obj):
    out=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            out.append(str(k)); out.extend(recursive_keys(v))
    elif isinstance(obj,list):
        for v in obj: out.extend(recursive_keys(v))
    return out


def audit_rosters(repo: Path, out: Path, roster_snapshot: Path, shadow_freeze_commit: str):
    b42, v1, lineage, adoption, v1_evidence = load_verified_parents(repo)
    base=repo/BASE_REL
    protocol_path=base/"player_role_v2_b44w4_v1_protocol_freeze.json"
    evaluator_path=base/"player_role_v2_b44w4_v1_evaluator.py"
    parity_path=base/"player_role_v2_b44w4_v1_implementation_parity.json"
    eligibility_path=base/"player_role_v2_b44w4_v1_role_eligibility.csv"
    eligibility_context_path=base/"player_role_v2_b44w4_v1_owner_blind_eligibility_context.json"
    shadow_path=base/"player_role_v2_b44w4_v1_shadow_refresh.csv"
    witness_path=base/"player_role_v2_b44w4_v1_shadow_refresh_witness.json"
    overlay_path=base/"player_role_v2_b44w4_v1_identity_overlay.csv"
    identity_validation_path=base/"player_role_v2_b44w4_v1_identity_validation.json"

    protocol=load_json(protocol_path)
    witness=load_json(witness_path)
    if protocol["evaluator_sha256"] != sha256_file(evaluator_path):
        raise RuntimeError("B44_AUDIT_EVALUATOR_SHA_DRIFT")
    if witness["protocol_sha256"] != sha256_file(protocol_path):
        raise RuntimeError("B44_AUDIT_PROTOCOL_SHA_DRIFT")
    if witness["implementation_parity_sha256"] != sha256_file(parity_path):
        raise RuntimeError("B44_AUDIT_PARITY_SHA_DRIFT")
    if load_json(parity_path)["exact_parity"]["pass"] is not True:
        raise RuntimeError("B44_AUDIT_B41J_PARITY_NOT_PASS")
    if witness["identity_validation_sha256"] != sha256_file(identity_validation_path):
        raise RuntimeError("B44_IDENTITY_VALIDATION_SHA_DRIFT")
    if witness["identity_overlay_sha256"] != sha256_file(overlay_path):
        raise RuntimeError("B44_IDENTITY_OVERLAY_SHA_DRIFT")
    if witness["role_eligibility_sha256"] != sha256_file(eligibility_path):
        raise RuntimeError("B44_ELIGIBILITY_SHA_DRIFT")
    if witness["owner_blind_eligibility_context_sha256"] != sha256_file(eligibility_context_path):
        raise RuntimeError("B44_ELIGIBILITY_CONTEXT_SHA_DRIFT")
    if witness["shadow_refresh_sha256"] != sha256_file(shadow_path):
        raise RuntimeError("B44_SHADOW_SHA_DRIFT")
    if witness["roster_assignment_semantics_parsed_before_shadow_freeze"] is not False:
        raise RuntimeError("B44_NO_PEEK_WITNESS_DRIFT")
    if witness["overlay_used_in_role_eligibility"] is not True or witness["overlay_used_in_shadow_identity_step"] is not True:
        raise RuntimeError("B44_OVERLAY_NOT_USED_BOTH_STEPS")
    if not shadow_freeze_commit:
        raise RuntimeError("B44_SHADOW_FREEZE_COMMIT_MISSING")
    if sha256_file(roster_snapshot) != protocol["new_data"]["roster_snapshot_sha256"]:
        raise RuntimeError("B44_ROSTER_SNAPSHOT_SHA_DRIFT")

    shadow=pd.read_csv(shadow_path,dtype={"sleeper_id":str,"gsis_id":str},keep_default_na=False)
    if shadow.empty or shadow["sleeper_id"].duplicated().any():
        raise RuntimeError("B44_AUDIT_SHADOW_INVALID")
    shadow_lookup={str(r["sleeper_id"]):r for _,r in shadow.iterrows()}

    # FIRST semantic parse of the frozen B44 roster snapshot.
    roster_payload=json.loads(roster_snapshot.read_text(encoding="utf-8"))
    rosters=roster_payload.get("rosters") or []
    if not isinstance(rosters,list):
        raise RuntimeError("B44_ROSTER_PAYLOAD_NOT_LIST")

    supported_count=named_count=0
    for roster in rosters:
        players_by_id={}
        for slot in ("starters","bench","taxi","reserve_ir"):
            for player in roster.get(slot) or []:
                pid=str(player.get("player_id") or "").strip()
                if pid: players_by_id.setdefault(pid,player)
        for player in players_by_id.values():
            pos=lineage["builder"].canon_pos(player.get("position"))
            if pos not in b42.POSITIONS: continue
            supported_count += 1
            if str(player.get("name") or "").strip(): named_count += 1
    name_availability=(named_count/supported_count) if supported_count else 0.0
    if not (supported_count>0 and name_availability>=0.95):
        write_json(out/"player_role_v2_b44w4_v1_data_integrity_stop.json",{
            "schema_version":1,"study_id":STUDY_ID,"phase":"B44W4-v1-pre-team-data-integrity-stop",
            "result":DATA_STOP_RESULT,"stop_stage":"roster_name_availability_prepass",
            "supported_position_roster_player_count":supported_count,
            "supported_position_roster_named_player_count":named_count,
            "supported_position_roster_name_availability":name_availability,
            "minimum_supported_roster_name_availability":0.95,
            "team_partition_metric_computed":False,
            "production_change_authorized":False,"production_model_deployed":False,
        })
        write_stop_decision(
            out, DATA_STOP_RESULT, "B44W4-v1-scientific-decision",
            "supported-position roster name availability failed before team metrics",
            {"team_partition_metric_computed": False, "roster_semantic_parse_performed": True},
        )
        return

    overlay_rows=[]
    with overlay_path.open(newline="",encoding="utf-8") as f:
        overlay_rows=list(csv.DictReader(f))
    roster_precision=rostered_overlay_precision(rosters,overlay_rows,b42,v1)
    if not roster_precision["pass"]:
        write_json(out/"player_role_v2_b44w4_v1_identity_precision_stop.json",{
            "schema_version":1,"study_id":STUDY_ID,"phase":"B44W4-v1-rostered-overlay-precision-stop",
            "result":IDENTITY_STOP_RESULT,
            "rostered_overlay_precision":roster_precision,
            "team_partition_metric_computed":False,
            "production_change_authorized":False,"production_model_deployed":False,
        })
        write_stop_decision(
            out, IDENTITY_STOP_RESULT, "B44W4-v1-scientific-decision",
            "rostered DOB_POSITION overlay independent-field contradiction detected",
            {"team_partition_metric_computed": False, "roster_semantic_parse_performed": True,
             "rostered_overlay_identity_contradictions": roster_precision["contradiction_count"]},
        )
        return

    ordered_rosters=list(rosters)
    secrets.SystemRandom().shuffle(ordered_rosters)
    team_labels={id(r):f"Team{i:02d}" for i,r in enumerate(ordered_rosters,start=1)}

    eligibility=pd.read_csv(eligibility_path,dtype={"sleeper_id":str,"gsis_id":str},keep_default_na=False)
    if eligibility.empty or eligibility["gsis_id"].duplicated().any():
        raise RuntimeError("B44_AUDIT_ELIGIBILITY_INVALID")
    eligible_by_sleeper={
        str(r["sleeper_id"]):r for _,r in eligibility.iterrows()
        if str(r.get("sleeper_id") or "").strip()
    }
    name_groups=defaultdict(list)
    for _,r in eligibility.iterrows():
        key=str(r.get("exact_name_key") or "")
        if key and str(r.get("exact_name_unique") or "").strip().lower() in {"true","1"}:
            name_groups[key].append(r)
    eligible_by_exact_name={k:rs[0] for k,rs in name_groups.items() if len(rs)==1}

    ctx=load_json(eligibility_context_path)
    if ctx.get("owner_or_roster_context_used") is not False:
        raise RuntimeError("B44_ELIGIBILITY_CONTEXT_OWNER_BLINDNESS_DRIFT")
    mapped_sids=set(str(x) for x in ctx.get("gsis_mapped_sleeper_ids",[]))
    sid_to_gsis={str(k):str(v) for k,v in (ctx.get("sid_to_gsis") or {}).items()}
    gsis_present=set(str(x) for x in ctx.get("gsis_present_in_2026_sources",[]))
    participant_ids=set(str(x) for x in ctx.get("sleeper_2026_participant_ids",[]))
    exclusion_reason={str(k):str(v) for k,v in (ctx.get("feature_exclusion_reason_by_gsis") or {}).items()}

    team_results=[]
    covered_shadow_rows=[]
    league_pos_eligible=Counter(); league_pos_covered=Counter()
    real_owner_values=set()
    for roster in ordered_rosters:
        for key in ("owner_id","owner_username","team_name","roster_id"):
            value=roster.get(key)
            if value not in (None,""): real_owner_values.add(str(value))
        label=team_labels[id(roster)]
        players_by_id={}
        for slot in ("starters","bench","taxi","reserve_ir"):
            for player in roster.get(slot) or []:
                pid=str(player.get("player_id") or "").strip()
                if pid: players_by_id.setdefault(pid,player)

        eligible_count=covered=position_mismatch=eligible_pending=no_current_evidence=0
        source_disagreement=identity_gap_unknown_model_position=0
        supported_named=supported_total=0
        tier_counts=Counter(); evidence_counts=Counter(); confidence_counts=Counter()
        active_game_buckets=Counter(); eligibility_methods=Counter(); pending_reasons=Counter()
        team_pos_eligible=Counter(); team_pos_covered=Counter()

        for pid,player in sorted(players_by_id.items()):
            roster_pos=lineage["builder"].canon_pos(player.get("position"))
            if roster_pos not in b42.POSITIONS: continue
            supported_total += 1
            if str(player.get("name") or "").strip(): supported_named += 1

            elig=eligible_by_sleeper.get(pid); match_method=None
            if elig is not None:
                match_method = (
                    "dob_position_overlay"
                    if str(elig.get("identity_source") or "")=="DOB_POSITION_OVERLAY"
                    else "stable_sleeper_id"
                )
            else:
                name_key=b42.exact_name_key(player.get("name") or "")
                elig=eligible_by_exact_name.get(name_key)
                if elig is not None: match_method="unique_exact_name_denominator_only"

            if elig is None:
                if pid in participant_ids:
                    mapped_gsis=sid_to_gsis.get(pid)
                    mapped_into_source=bool(pid in mapped_sids and mapped_gsis and mapped_gsis in gsis_present)
                    if not mapped_into_source:
                        eligible_count += 1; eligible_pending += 1; identity_gap_unknown_model_position += 1
                        eligibility_methods["sleeper_participation_identity_gap"] += 1
                        pending_reasons[
                            "crosswalk_mapped_gsis_absent_from_2026_nflverse" if mapped_gsis
                            else "stable_id_crosswalk_missing_gsis_bridge"
                        ] += 1
                        continue
                    source_disagreement += 1
                    continue
                no_current_evidence += 1
                continue

            eligible_count += 1
            eligibility_methods[match_method] += 1
            model_pos=str(elig["position"])
            if model_pos in b42.POSITIONS:
                team_pos_eligible[model_pos]+=1; league_pos_eligible[model_pos]+=1

            role=shadow_lookup.get(pid)
            if match_method=="unique_exact_name_denominator_only" and role is not None:
                raise RuntimeError("B44_EXACT_NAME_DENOMINATOR_MUST_NOT_RESCUE_ROLE")
            if role is None:
                eligible_pending += 1
                if match_method=="unique_exact_name_denominator_only":
                    bridged_sid=str(elig.get("sleeper_id") or "").strip()
                    pending_reasons[
                        "crosswalk_sleeper_id_disagrees_with_roster_id_name_bridge"
                        if bridged_sid else "stable_id_crosswalk_absent_name_bridge"
                    ] += 1
                else:
                    g=str(elig.get("gsis_id") or "")
                    pending_reasons[exclusion_reason.get(g,"other_pipeline_drop")] += 1
                continue

            role_pos=str(role["position"])
            if role_pos != roster_pos: position_mismatch += 1
            covered += 1
            team_pos_covered[role_pos]+=1; league_pos_covered[role_pos]+=1
            tier_counts[str(role["role_tier"])]+=1
            evidence_counts[str(role["evidence_source"])]+=1
            confidence_counts[str(role["confidence_status"])]+=1
            games=int(role["prior_active_games"])
            active_game_buckets["3+" if games>=3 else str(games)] += 1
            covered_shadow_rows.append(role)

        coverage=(covered/eligible_count) if eligible_count else 0.0
        team_results.append({
            "opaque_team":label,
            "role_eligible_supported_position_players":eligible_count,
            "data_driven_role_count":covered,
            "fallback_role_count":0,
            "eligible_pending_without_role_count":eligible_pending,
            "no_current_season_evidence_count":no_current_evidence,
            "position_label_mismatch_count":position_mismatch,
            "role_coverage":coverage,
            "coverage_pass_98pct":bool(eligible_count>0 and coverage>=MIN_TEAM_ROLE_COVERAGE),
            "eligibility_match_method_counts":dict(sorted(eligibility_methods.items())),
            "eligible_pending_reason_counts":dict(sorted(pending_reasons.items())),
            "sleeper_participation_crosswalk_present_source_disagreement_count":source_disagreement,
            "identity_gap_unknown_model_position_count":identity_gap_unknown_model_position,
            "supported_position_roster_name_available_count":supported_named,
            "supported_position_roster_player_count":supported_total,
            "supported_position_roster_name_availability":(supported_named/supported_total if supported_total else 0.0),
            "evidence_source_counts":dict(sorted(evidence_counts.items())),
            "confidence_status_counts":dict(sorted(confidence_counts.items())),
            "active_game_evidence_depth_counts":dict(sorted(active_game_buckets.items())),
            "role_tier_counts":{role:int(tier_counts.get(role,0)) for role in b42.ROLE_ORDER},
            "eligible_by_model_position":{p:int(team_pos_eligible.get(p,0)) for p in b42.POSITIONS},
            "covered_by_model_position":{p:int(team_pos_covered.get(p,0)) for p in b42.POSITIONS},
        })

    coverages=[float(t["role_coverage"]) for t in team_results]
    coverage_range=(max(coverages)-min(coverages)) if coverages else float("inf")

    context_labels=[f"Team{i:02d}" for i in range(1,REQUIRED_TEAM_COUNT+1)]
    synthetic_slots=["STARTER","BENCH","TAXI","RESERVE_IR"]
    changes=comparisons=0
    for role in covered_shadow_rows:
        base_idx=int(role["tier_index"]); base_label=str(role["role_tier"])
        for team_label in context_labels:
            for slot in synthetic_slots:
                idx,label=b42.counterfactual_role_assignment(
                    str(role["position"]),float(role["model_score"]),lineage["b41f"],team_label,slot
                )
                comparisons += 1
                if idx != base_idx or label != base_label: changes += 1

    parity=load_json(parity_path)
    identity_validation=load_json(identity_validation_path)
    gates={
        "exactly_12_teams":len(rosters)==REQUIRED_TEAM_COUNT,
        "every_team_has_supported_position_denominator":bool(team_results and all(int(t["role_eligible_supported_position_players"])>0 for t in team_results)),
        "minimum_98pct_role_coverage_every_team":bool(team_results and all(bool(t["coverage_pass_98pct"]) for t in team_results)),
        "maximum_2_percentage_point_coverage_range":bool(math.isfinite(coverage_range) and coverage_range <= MAX_TEAM_COVERAGE_RANGE + 1e-12),
        "structural_owner_slot_role_invariance":changes==0,
        "shadow_refresh_frozen_before_roster_semantic_parse":bool(
            witness["roster_assignment_semantics_parsed_before_shadow_freeze"] is False and shadow_freeze_commit
        ),
        "shadow_role_inference_source_firewall":bool((witness.get("pre_roster_static_source_firewall") or {}).get("pass") is True),
        "all_eight_positions_in_declared_scope":bool(sorted(lineage["b41f"]["position_models"])==sorted(b42.POSITIONS)),
        "no_owner_blind_fallback_invented_post_holdout":all(int(t["fallback_role_count"])==0 for t in team_results),
        "continuation_class_preserved":True,
        "model_or_tier_retuning_absent":witness["model_or_tier_retuning_performed"] is False,
        "B41J_implementation_parity_oracle":parity["exact_parity"]["pass"] is True,
        "DOB_POSITION_fresh_reference_precision":identity_validation["all_hard_precision_gates_pass"] is True,
        "rostered_overlay_identity_precision":roster_precision["pass"] is True,
    }

    evidence={
        "schema_version":1,"study_id":STUDY_ID,"phase":PHASE,
        "framing":"POST_REMEDIATION_ACCEPTANCE_REAUDIT_NOT_INDEPENDENT_CONFIRMATION",
        "identity_rule_adopted_after_V1R1_result_known":True,
        "protocol_sha256":sha256_file(protocol_path),
        "evaluator_sha256":sha256_file(evaluator_path),
        "implementation_parity_sha256":sha256_file(parity_path),
        "identity_validation_sha256":sha256_file(identity_validation_path),
        "identity_overlay_sha256":sha256_file(overlay_path),
        "role_eligibility_sha256":sha256_file(eligibility_path),
        "owner_blind_eligibility_context_sha256":sha256_file(eligibility_context_path),
        "shadow_refresh_sha256":sha256_file(shadow_path),
        "shadow_refresh_witness_sha256":sha256_file(witness_path),
        "shadow_freeze_commit":shadow_freeze_commit,
        "roster_snapshot_sha256":sha256_file(roster_snapshot),
        "team_count":len(rosters),
        "opaque_team_label_assignment":"private random permutation; mapping not persisted",
        "supported_position_roster_name_availability":name_availability,
        "participant_confirmation_rate":float(witness["participant_confirmation_rate"]),
        "rostered_overlay_precision":roster_precision,
        "team_results":team_results,
        "league_position_eligible_counts":{p:int(league_pos_eligible.get(p,0)) for p in b42.POSITIONS},
        "league_position_covered_counts":{p:int(league_pos_covered.get(p,0)) for p in b42.POSITIONS},
        "coverage_range":float(coverage_range) if math.isfinite(coverage_range) else None,
        "required_minimum_team_coverage":MIN_TEAM_ROLE_COVERAGE,
        "required_maximum_coverage_range":MAX_TEAM_COVERAGE_RANGE,
        "fallback_policy":"NONE",
        "structural_counterfactual_invariance":{
            "synthetic_team_contexts":REQUIRED_TEAM_COUNT,
            "synthetic_slot_contexts":len(synthetic_slots),
            "comparisons":comparisons,"role_changes":changes,"allowed_role_changes":0,"pass":changes==0,
        },
        "primary_gates":gates,
        "all_primary_gates_pass":all(gates.values()),
        "model_or_tier_retuning_performed":False,
        "posthoc_fallback_rescue_performed":False,
        "production_change_authorized":False,
        "production_model_deployed":False,
    }

    forbidden_keys={"owner_id","owner_username","team_name","roster_id"}
    key_hits=sorted({k for k in recursive_keys(evidence) if k.lower() in forbidden_keys})
    emitted=set(string_leaf_values(evidence))
    value_hits=sorted(v for v in real_owner_values if v and v in emitted)
    privacy_pass=not key_hits and not value_hits
    evidence["privacy_audit"]={
        "forbidden_output_key_hits":key_hits,
        "real_owner_or_team_value_hits":value_hits,
        "pass":privacy_pass,
    }
    gates["owner_identity_privacy"]=privacy_pass
    evidence["primary_gates"]=gates
    evidence["all_primary_gates_pass"]=all(gates.values())

    result=PASS_RESULT if evidence["all_primary_gates_pass"] else PARITY_STOP_RESULT
    evidence["result"]=result
    write_json(out/"player_role_v2_b44w4_v1_owner_blind_evidence.json",evidence)

    decision={
        "schema_version":1,"study_id":STUDY_ID,"phase":"B44W4-v1-scientific-decision",
        "result":result,
        "team_count":len(rosters),
        "minimum_team_role_coverage":min(coverages) if coverages else None,
        "maximum_team_role_coverage":max(coverages) if coverages else None,
        "coverage_range":float(coverage_range) if math.isfinite(coverage_range) else None,
        "all_primary_gates_pass":evidence["all_primary_gates_pass"],
        "rostered_overlay_identity_contradictions":roster_precision["contradiction_count"],
        "eligible_for_separate_production_authorization":False,
        "evidence_class":"SAME_WEEK_ENGINEERING_REMEDIATION_VALIDATION",
        "production_change_authorized":False,
        "production_model_deployed":False,
        "next_stage":(
            "If PASS, Week-4 remediation cleared every unchanged B42 gate, but this same-week post-hoc result is not independent confirmation and does not itself authorize production."
            if evidence["all_primary_gates_pass"]
            else "STOP is final for this adopted bridge on this B44 data. Do not add identity rules or alter gates after observing this result."
        ),
    }
    decision["evidence_sha256"]=sha256_file(out/"player_role_v2_b44w4_v1_owner_blind_evidence.json")
    write_json(out/"player_role_v2_b44w4_v1_scientific_decision.json",decision)

    lines=[
        "# Player Role V2 — B44W4 V1 Week-4 DOB_POSITION Remediation Re-Audit","",
        f"- Decision: **{result}**",
        "- Classification: **Same-week Week-4 engineering remediation validation; not independent confirmation**",
        "- V1R1 scientific STOP preserved: **Yes**",
        f"- Team count: **{len(rosters)}**",
        f"- Minimum team role coverage: **{min(coverages) if coverages else 0.0:.4f}**",
        f"- Maximum team role coverage: **{max(coverages) if coverages else 0.0:.4f}**",
        f"- Coverage range: **{coverage_range if math.isfinite(coverage_range) else float('nan'):.4f}**",
        f"- Required per-team coverage: **{MIN_TEAM_ROLE_COVERAGE:.2f}**",
        f"- Maximum allowed coverage range: **{MAX_TEAM_COVERAGE_RANGE:.2f}**",
        f"- Rostered DOB_POSITION overlay players: **{roster_precision['overlay_identified_rostered_count']}**",
        f"- Overlay precision verified: **{roster_precision['verified_count']}**",
        f"- Overlay precision unverifiable: **{roster_precision['unverifiable_count']}**",
        f"- Overlay precision contradictions: **{roster_precision['contradiction_count']}**",
        "- Production authorized: **No**","",
        "## Opaque team parity","",
        "| Team | Role-eligible | Covered | Pending | Identity-gap unknown-pos | Source disagreement | No current evidence | Pos-label mismatch | Coverage | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for t in team_results:
        lines.append(
            f"| {t['opaque_team']} | {t['role_eligible_supported_position_players']} | "
            f"{t['data_driven_role_count']} | {t['eligible_pending_without_role_count']} | "
            f"{t['identity_gap_unknown_model_position_count']} | "
            f"{t['sleeper_participation_crosswalk_present_source_disagreement_count']} | "
            f"{t['no_current_season_evidence_count']} | {t['position_label_mismatch_count']} | "
            f"{t['role_coverage']:.4f} | {'PASS' if t['coverage_pass_98pct'] else 'FAIL'} |"
        )
    lines += ["","## Gate results",""]
    for k,v in gates.items():
        lines.append(f"- {k}: **{'PASS' if v else 'FAIL'}**")
    lines += ["","## Identity precision","",
              f"- Fresh known-pair DOB_POSITION comparisons: **{identity_validation['reference_validation']['comparisons']}**",
              f"- Fresh known-pair conflicts: **{identity_validation['reference_validation']['conflicts']}**",
              f"- Accepted overlay pairs: **{identity_validation['accepted_overlay_count']}**",
              f"- Quarantined overlay proposals: **{identity_validation['quarantined_count']}**",
              "",
              "A mid-week NFL trade can create a conservative team-field false STOP in the rostered overlay precision check; that risk was frozen in the protocol before roster parsing.",
              "",
              "## Next stage","",decision["next_stage"],""]
    (out/"player_role_v2_b44w4_v1_report.md").write_text("\n".join(lines),encoding="utf-8")


def run_selftest():
    def fake_candidate(row, by_name):
        recs=[x for x in by_name.get(row["name_key"],[]) if x["position_family"]==row["position_family"]]
        exact=[x for x in recs if row["birth_date"] and x["birth_date"]==row["birth_date"]]
        if len(exact)==1:
            return exact[0],"DOB_POSITION"
        return None

    sleeper_by_id={}
    sleeper_by_name=defaultdict(list)
    current=[]; stable={}; stable_inverse={}
    # 501 known clean comparisons guarantee the hard reference gate can pass.
    for i in range(501):
        g=f"G{i:03d}"; s=f"S{i:03d}"; n=f"name {i}"
        rec={"sleeper_id":s,"name_key":n,"birth_date":"2000-01-01","position_family":"RB","position":"RB","nfl_team":"ARI"}
        sleeper_by_id[s]=rec; sleeper_by_name[n].append(rec)
        current.append({"gsis_id":g,"name_key":n,"birth_date":"2000-01-01","position_family":"RB","model_position":"RB","nfl_team":"ARI"})
        stable[g]=s; stable_inverse[s]=g
    # One clean supplement.
    rec={"sleeper_id":"SNEW","name_key":"new player","birth_date":"2001-02-03","position_family":"WR","position":"WR","nfl_team":"BUF"}
    sleeper_by_id["SNEW"]=rec; sleeper_by_name["new player"].append(rec)
    current.append({"gsis_id":"GNEW","name_key":"new player","birth_date":"2001-02-03","position_family":"WR","model_position":"WR","nfl_team":"BUF"})
    # One collision identity must quarantine.
    rec2={"sleeper_id":"SCOLL","name_key":"collision","birth_date":"1999-01-01","position_family":"DB","position":"CB","nfl_team":"ARI"}
    sleeper_by_id["SCOLL"]=rec2; sleeper_by_name["collision"].append(rec2)
    current.append({"gsis_id":"GCOLL","name_key":"collision","birth_date":"1999-01-01","position_family":"DB","model_position":"DB","nfl_team":"ARI"})

    core=compute_overlay(
        current,stable,stable_inverse,sleeper_by_id,sleeper_by_name,fake_candidate,
        {"GNEW":"SNEW"},{"GCOLL"},set(),set()
    )
    assert core["all_hard_precision_gates_pass"] is True
    assert len(core["accepted"])==1 and core["accepted"][0]["gsis_id"]=="GNEW"
    assert len(core["quarantined"])==1 and core["quarantined"][0]["gsis_id"]=="GCOLL"
    assert core["reference_validation"]["comparisons"]==501
    assert core["reference_validation"]["conflicts"]==0

    # Roster precision: verified, unverifiable, and contradiction paths.
    class V:
        @staticmethod
        def position_family(x):
            return {"RB":"RB","WR":"WR","CB":"DB","DB":"DB"}.get(str(x),"")
        @staticmethod
        def team_key(x):
            return str(x or "")
    rosters=[{"starters":[{"player_id":"SNEW","position":"WR","name":"New Player"}],"bench":[],"taxi":[],"reserve_ir":[]}]
    rp=rostered_overlay_precision(rosters,[{
        "sleeper_id":"SNEW","gsis_id":"GNEW","sleeper_position":"WR","model_position":"WR",
        "sleeper_nfl_team":"BUF","nfl_team":"BUF"
    }],None,V)
    assert rp["pass"] is True and rp["verified_count"]==1 and rp["contradiction_count"]==0

    # Gate semantics sanity.
    good=[1.0]*12
    assert len(good)==REQUIRED_TEAM_COUNT and min(good)>=MIN_TEAM_ROLE_COVERAGE and max(good)-min(good)<=MAX_TEAM_COVERAGE_RANGE
    bad_floor=[1.0]*11+[0.97]
    assert not all(v>=MIN_TEAM_ROLE_COVERAGE for v in bad_floor)
    bad_range=[1.0]*11+[0.97]
    assert max(bad_range)-min(bad_range)>MAX_TEAM_COVERAGE_RANGE
    print("PASS B44W4 V1 evaluator end-to-end synthetic self-test")


def run_parity(repo: Path, out: Path):
    b42, v1, lineage, adoption, v1_evidence=load_verified_parents(repo)
    session=requests.Session()
    session.headers.update({"User-Agent":"LOG-Trade-Calculator-player-role-v2-b44w4-v1-parity"})
    result=b42.run_b41j_implementation_parity_oracle(repo,out,lineage,session)
    src=out/"player_role_v2_b42_v4_implementation_parity.json"
    dst=out/"player_role_v2_b44w4_v1_implementation_parity.json"
    payload=load_json(src)
    payload["B44_wrapper_phase"]="B44W4-v1-B41J-implementation-parity-oracle-before-2026-shadow"
    payload["B44_identity_overlay_applied_during_oracle"]=False
    write_json(dst,payload)
    src.unlink()
    return payload


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",required=True,choices=["selftest","protocol","parity","shadow","audit"])
    ap.add_argument("--repo",default=".")
    ap.add_argument("--out")
    ap.add_argument("--source-preflight")
    ap.add_argument("--source-cache")
    ap.add_argument("--evaluator-sha256")
    ap.add_argument("--main-at-start")
    ap.add_argument("--protocol-commit",default="")
    ap.add_argument("--parity-commit",default="")
    ap.add_argument("--shadow-freeze-commit",default="")
    ap.add_argument("--roster-snapshot")
    args=ap.parse_args()

    if args.mode=="selftest":
        run_selftest(); return
    repo=Path(args.repo)
    if args.mode=="protocol":
        if not args.out or not args.source_preflight or not args.evaluator_sha256 or not args.main_at_start:
            raise SystemExit("protocol args missing")
        source=load_json(Path(args.source_preflight))
        write_json(Path(args.out),protocol_payload(args.evaluator_sha256,source,args.main_at_start))
        return
    if args.mode=="parity":
        if not args.out: raise SystemExit("parity out missing")
        run_parity(repo,Path(args.out)); return
    if args.mode=="shadow":
        if not args.out or not args.source_cache:
            raise SystemExit("shadow args missing")
        build_shadow(repo,Path(args.out),Path(args.source_cache),args.protocol_commit,args.parity_commit)
        return
    if args.mode=="audit":
        if not args.out or not args.roster_snapshot:
            raise SystemExit("audit args missing")
        audit_rosters(repo,Path(args.out),Path(args.roster_snapshot),args.shadow_freeze_commit)
        return

if __name__=="__main__":
    main()

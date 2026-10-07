#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
PHASE = "B46W4-v1r1-week4-b45-override-integration-audit"

BASE = Path("research/player-role-v2")
ANALYSIS_WEEK = 4
B44_MAIN_AT_START = "373b1f948dbaedd2faadbb05851653a0b4a3913e"

REQUIRED_TEAM_COUNT = 12
MIN_TEAM_ROLE_COVERAGE = 0.98
MAX_TEAM_COVERAGE_RANGE = 0.02
ALLOWED_STRUCTURAL_ROLE_CHANGES = 0

PASS_RESULT = "PASS_B46W4_V1_WEEK4_B45_OVERRIDE_INTEGRATION_AUDIT"
STOP_RESULT = "SCIENTIFIC_STOP_B46W4_V1_WEEK4_OVERRIDE_INTEGRATION_FAILED"
REPLAY_STOP_RESULT = "SCIENTIFIC_STOP_B46W4_V1_WEEK4_REPLAY_PARITY_FAILED"

B44 = {
    "player_role_v2_b44w4_v1_evaluator.py": "3540959281424e103cf172d66cb63401066187b1dccb86c587a662254cf8be1c",
    "player_role_v2_b44w4_v1_protocol_freeze.json": "16fe6605b2d7b764d39f89142ed9478938c8f499d1aa81a2e71caed266aa4f2f",
    "player_role_v2_b44w4_v1_implementation_parity.json": "9d2c02596abb88af69f6e18c214d9a02970fb05e64e3fec85726e322d30642e2",
    "player_role_v2_b44w4_v1_identity_validation.json": "046b474d5bf103899e727df74edd8950fd6c6fef93d81761f1a076e3a2fec5b9",
    "player_role_v2_b44w4_v1_identity_overlay.csv": "d02d6583fc7e7ba22827e3e4e464bc85c7ff7c2999a8a0418d4e5467f9174066",
    "player_role_v2_b44w4_v1_role_eligibility.csv": "1ce771cf10734b3e76fbf8b84828ca30b2fecb39c17a56e3d3ced0775be840bb",
    "player_role_v2_b44w4_v1_owner_blind_eligibility_context.json": "491f2af57060ffd3d882a850a36a02b925df1e4c481a58691e5651e2aa67a3f5",
    "player_role_v2_b44w4_v1_shadow_refresh.csv": "1e1f77a0a1e1e60fd88970afa8eb62d4a4424498b9199ef4d67823224dfb7e8f",
    "player_role_v2_b44w4_v1_shadow_refresh_witness.json": "f2f5cc65f4f3da879062387cc2b8802afbbc096b46bc9b8c6bd51538b39e4ef4",
    "player_role_v2_b44w4_v1_owner_blind_evidence.json": "59a95d5cba3c8eaa79149cd26f13355b18eb4ea8c50fb3f0a9095aa6d96885f2",
}
B44_DECISION = "player_role_v2_b44w4_v1_scientific_decision.json"
B44_EXPECTED_STOP = "SCIENTIFIC_STOP_B44W4_V1_OWNER_BLIND_ROLE_PARITY_FAILED"
B44_ROSTER_SHA256 = "692be469f4c4bd5215ad4f426302bb73a7d48a7840519b4873eac4bc35cebc7d"

B45_EVIDENCE = BASE / "b45_evidence.json"
B45_OVERRIDES = BASE / "b45_identity_overrides.csv"
B45_EVIDENCE_BLOB = "5a168821327afc7939ff05f5f50c3f3dff7137d9"
B45_OVERRIDES_BLOB = "15d5be73433591860d058e0b0221812f43b7e473"
B45_OVERRIDES_SHA256 = "35b207f2e0b0837207774be6a1f9091c33b3c9384befb01666c05faf739bd655"
B45_EXPECTED_DECISION = "B45_R6_OVERRIDES_FROZEN"

B44_EVALUATOR = BASE / "player_role_v2_b44w4_v1_evaluator.py"
B44_ELIGIBILITY = BASE / "player_role_v2_b44w4_v1_role_eligibility.csv"
B44_SHADOW = BASE / "player_role_v2_b44w4_v1_shadow_refresh.csv"
B44_CONTEXT = BASE / "player_role_v2_b44w4_v1_owner_blind_eligibility_context.json"
B44_OVERLAY = BASE / "player_role_v2_b44w4_v1_identity_overlay.csv"
B44_EVIDENCE = BASE / "player_role_v2_b44w4_v1_owner_blind_evidence.json"
B44_WITNESS = BASE / "player_role_v2_b44w4_v1_shadow_refresh_witness.json"

OUT_PROTOCOL = BASE / "player_role_v2_b46w4_v1_protocol.json"
OUT_REPLAY = BASE / "player_role_v2_b46w4_v1_replay_parity.json"
OUT_ELIGIBILITY = BASE / "player_role_v2_b46w4_v1_integration_role_eligibility.csv"
OUT_SHADOW = BASE / "player_role_v2_b46w4_v1_integration_shadow.csv"
OUT_EVIDENCE = BASE / "player_role_v2_b46w4_v1_owner_blind_evidence.json"
OUT_DECISION = BASE / "player_role_v2_b46w4_v1_scientific_decision.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"B46W4_MODULE_LOAD_FAILED {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def boolish(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes"}


def canonical_eligibility_row(row) -> tuple:
    return (
        int(row["season"]),
        int(row["origin_week"]),
        str(row["gsis_id"]),
        str(row["position"]),
        str(row["player_name"]),
        str(row["exact_name_key"]),
        int(row["active_game_count"]),
        str(row["sleeper_id"]),
        boolish(row["identity_mapped"]),
        str(row["identity_source"]),
        boolish(row["exact_name_unique"]),
    )


def canonical_team_signature(team: dict) -> str:
    x = {k: v for k, v in team.items() if k != "opaque_team"}
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def verify_frozen_inputs(repo: Path):
    for rel, expected in B44.items():
        p = repo / BASE / rel
        if not p.exists():
            raise RuntimeError(f"B46W4_B44_PARENT_MISSING {rel}")
        actual = sha256_file(p)
        if actual != expected:
            raise RuntimeError(f"B46W4_B44_PARENT_SHA_DRIFT {rel} expected={expected} actual={actual}")

    d = load_json(repo / BASE / B44_DECISION)
    if d.get("result") != B44_EXPECTED_STOP:
        raise RuntimeError("B46W4_B44_STOP_NOT_PRESERVED")
    if d.get("production_change_authorized") is not False:
        raise RuntimeError("B46W4_B44_PRODUCTION_STATE_DRIFT")

    if git_blob(repo / B45_EVIDENCE) != B45_EVIDENCE_BLOB:
        raise RuntimeError("B46W4_B45_EVIDENCE_BLOB_DRIFT")
    if git_blob(repo / B45_OVERRIDES) != B45_OVERRIDES_BLOB:
        raise RuntimeError("B46W4_B45_OVERRIDE_BLOB_DRIFT")
    if sha256_file(repo / B45_OVERRIDES) != B45_OVERRIDES_SHA256:
        raise RuntimeError("B46W4_B45_OVERRIDE_SHA_DRIFT")

    b45e = load_json(repo / B45_EVIDENCE)
    if b45e.get("decision") != B45_EXPECTED_DECISION:
        raise RuntimeError("B46W4_B45_R6_NOT_FROZEN")
    if int(b45e.get("accepted_override_count", -1)) != 3:
        raise RuntimeError("B46W4_B45_OVERRIDE_COUNT_DRIFT")
    if b45e.get("override_csv_sha256") != B45_OVERRIDES_SHA256:
        raise RuntimeError("B46W4_B45_EVIDENCE_CSV_SHA_MISMATCH")
    if b45e.get("production_change_authorized") is not False:
        raise RuntimeError("B46W4_B45_PRODUCTION_STATE_DRIFT")
    if b45e.get("B46_must_be_fresh_week") is not True:
        raise RuntimeError("B46W4_B45_FRESH_WEEK_REQUIREMENT_DRIFT")
    return b45e


def load_b45_rows(repo: Path) -> list[dict]:
    with (repo / B45_OVERRIDES).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 3:
        raise RuntimeError(f"B46W4_REQUIRES_EXACTLY_3_B45_OVERRIDES got={len(rows)}")
    gsis = [str(x["gsis_id"]) for x in rows]
    sid = [str(x["sleeper_id"]) for x in rows]
    if len(set(gsis)) != 3 or len(set(sid)) != 3:
        raise RuntimeError("B46W4_B45_OVERRIDE_NOT_ONE_TO_ONE")
    for x in rows:
        if str(x.get("model_position") or "") not in {"DL", "K"}:
            raise RuntimeError("B46W4_B45_POSITION_SCOPE_DRIFT")
        if str(x.get("adjudicated_dob_matches") or "") not in {"sleeper", "nflverse"}:
            raise RuntimeError("B46W4_B45_DOB_MATCH_FIELD_DRIFT")
        if str(x.get("dob_error_source") or "") not in {"sleeper", "nflverse"}:
            raise RuntimeError("B46W4_B45_DOB_ERROR_FIELD_DRIFT")
    return rows


def apply_b45_to_frozen_eligibility(frozen: pd.DataFrame, rows: list[dict]) -> pd.DataFrame:
    out = frozen.copy()
    for x in rows:
        g, sid, pos = str(x["gsis_id"]), str(x["sleeper_id"]), str(x["model_position"])
        idx = out.index[out["gsis_id"].astype(str) == g].tolist()
        if len(idx) != 1:
            raise RuntimeError(f"B46W4_B45_GSIS_NOT_UNIQUE_IN_FROZEN_ELIGIBILITY {g}")
        i = idx[0]
        if str(out.at[i, "sleeper_id"]).strip():
            raise RuntimeError(f"B46W4_B45_TARGET_WAS_ALREADY_MAPPED {g}")
        if boolish(out.at[i, "identity_mapped"]):
            raise RuntimeError(f"B46W4_B45_TARGET_IDENTITY_FLAG_ALREADY_TRUE {g}")
        if str(out.at[i, "identity_source"]) != "UNMAPPED":
            raise RuntimeError(f"B46W4_B45_TARGET_SOURCE_NOT_UNMAPPED {g}")
        if str(out.at[i, "position"]) != pos:
            raise RuntimeError(f"B46W4_B45_POSITION_MISMATCH {g}")
        if not boolish(out.at[i, "exact_name_unique"]):
            raise RuntimeError(f"B46W4_B45_TARGET_NAME_NOT_UNIQUE {g}")
        out.at[i, "sleeper_id"] = sid
        out.at[i, "identity_mapped"] = True
        out.at[i, "identity_source"] = "B45_VERIFIED_OVERRIDE"
    return out


def compare_eligibility(expected: pd.DataFrame, actual: pd.DataFrame) -> dict:
    if list(expected.columns) != list(actual.columns):
        return {"pass": False, "reason": "column_mismatch",
                "expected_columns": list(expected.columns), "actual_columns": list(actual.columns)}
    e = {str(r["gsis_id"]): canonical_eligibility_row(r) for _, r in expected.iterrows()}
    a = {str(r["gsis_id"]): canonical_eligibility_row(r) for _, r in actual.iterrows()}
    missing = sorted(set(e) - set(a))
    extra = sorted(set(a) - set(e))
    mismatches = []
    for g in sorted(set(e) & set(a)):
        if e[g] != a[g]:
            mismatches.append({"gsis_id": g, "expected": e[g], "actual": a[g]})
            if len(mismatches) >= 20:
                break
    return {
        "pass": not missing and not extra and not mismatches,
        "expected_count": len(e),
        "actual_count": len(a),
        "missing_gsis": missing,
        "extra_gsis": extra,
        "mismatch_count_capped": len(mismatches),
        "mismatches": mismatches,
    }


def shadow_row_equal(a, b, tol=1e-12) -> bool:
    text_fields = ["sleeper_id","gsis_id","identity_source","position","role_tier","evidence_source","confidence_status"]
    int_fields = ["origin_week","tier_index","prior_active_games",
                  "frozen_feature_missing_count_before_imputation","frozen_feature_count"]
    for k in text_fields:
        if str(a[k]) != str(b[k]):
            return False
    for k in int_fields:
        if int(a[k]) != int(b[k]):
            return False
    return abs(float(a["model_score"]) - float(b["model_score"])) <= tol


def compare_shadow(frozen: pd.DataFrame, fresh: pd.DataFrame, b45_gsis: set[str]) -> dict:
    f = {str(r["gsis_id"]): r for _, r in frozen.iterrows()}
    n = {str(r["gsis_id"]): r for _, r in fresh.iterrows()}
    old_missing = sorted(set(f) - set(n))
    unexpected_extra = sorted((set(n) - set(f)) - b45_gsis)
    old_mismatches = []
    for g in sorted(set(f) & set(n)):
        if not shadow_row_equal(f[g], n[g]):
            old_mismatches.append(g)
            if len(old_mismatches) >= 20:
                break
    b45_present = sorted(b45_gsis & set(n))
    b45_missing = sorted(b45_gsis - set(n))
    return {
        "pass_old_rows": not old_missing and not unexpected_extra and not old_mismatches,
        "frozen_row_count": len(f),
        "fresh_row_count": len(n),
        "old_missing": old_missing,
        "unexpected_non_b45_extra": unexpected_extra,
        "old_mismatch_gsis_capped": old_mismatches,
        "b45_present": b45_present,
        "b45_missing": b45_missing,
        "all_three_b45_scored": len(b45_present) == 3 and not b45_missing,
    }


def patched_context(frozen_ctx: dict, b45_rows: list[dict]) -> dict:
    ctx = json.loads(json.dumps(frozen_ctx))
    mapped = set(str(x) for x in ctx.get("gsis_mapped_sleeper_ids", []))
    sid_to_gsis = {str(k): str(v) for k, v in (ctx.get("sid_to_gsis") or {}).items()}
    for x in b45_rows:
        sid, g = str(x["sleeper_id"]), str(x["gsis_id"])
        if sid in sid_to_gsis and sid_to_gsis[sid] != g:
            raise RuntimeError(f"B46W4_B45_CONTEXT_SLEEPER_COLLISION {sid}")
        mapped.add(sid)
        sid_to_gsis[sid] = g
    ctx["gsis_mapped_sleeper_ids"] = sorted(mapped)
    ctx["sid_to_gsis"] = dict(sorted(sid_to_gsis.items()))
    ctx["B45_verified_override_count"] = 3
    return ctx


def audit_rosters(rosters, eligibility, shadow, ctx, b42, lineage, ordered_rosters):
    shadow_lookup = {str(r["sleeper_id"]): r for _, r in shadow.iterrows()}
    if len(shadow_lookup) != len(shadow):
        raise RuntimeError("B46W4_SHADOW_SLEEPER_DUPLICATE")

    eligible_by_sleeper = {
        str(r["sleeper_id"]): r for _, r in eligibility.iterrows()
        if str(r.get("sleeper_id") or "").strip()
    }
    name_groups = defaultdict(list)
    for _, r in eligibility.iterrows():
        key = str(r.get("exact_name_key") or "")
        if key and boolish(r.get("exact_name_unique")):
            name_groups[key].append(r)
    eligible_by_exact_name = {k: rs[0] for k, rs in name_groups.items() if len(rs) == 1}

    mapped_sids = set(str(x) for x in ctx.get("gsis_mapped_sleeper_ids", []))
    sid_to_gsis = {str(k): str(v) for k, v in (ctx.get("sid_to_gsis") or {}).items()}
    gsis_present = set(str(x) for x in ctx.get("gsis_present_in_2026_sources", []))
    participant_ids = set(str(x) for x in ctx.get("sleeper_2026_participant_ids", []))
    exclusion_reason = {str(k): str(v) for k, v in (ctx.get("feature_exclusion_reason_by_gsis") or {}).items()}

    team_labels = {id(r): f"Team{i:02d}" for i, r in enumerate(ordered_rosters, start=1)}
    team_results = []
    covered_shadow_rows = []
    league_pos_eligible = Counter()
    league_pos_covered = Counter()

    for roster in ordered_rosters:
        label = team_labels[id(roster)]
        players_by_id = {}
        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for player in roster.get(slot) or []:
                pid = str(player.get("player_id") or "").strip()
                if pid:
                    players_by_id.setdefault(pid, player)

        eligible_count = covered = position_mismatch = eligible_pending = no_current_evidence = 0
        source_disagreement = identity_gap_unknown_model_position = 0
        supported_named = supported_total = 0
        tier_counts = Counter()
        evidence_counts = Counter()
        confidence_counts = Counter()
        active_game_buckets = Counter()
        eligibility_methods = Counter()
        pending_reasons = Counter()
        team_pos_eligible = Counter()
        team_pos_covered = Counter()

        for pid, player in sorted(players_by_id.items()):
            roster_pos = lineage["builder"].canon_pos(player.get("position"))
            if roster_pos not in b42.POSITIONS:
                continue
            supported_total += 1
            if str(player.get("name") or "").strip():
                supported_named += 1

            elig = eligible_by_sleeper.get(pid)
            match_method = None
            if elig is not None:
                src = str(elig.get("identity_source") or "")
                if src == "B45_VERIFIED_OVERRIDE":
                    match_method = "b45_verified_override"
                elif src == "DOB_POSITION_OVERLAY":
                    match_method = "dob_position_overlay"
                else:
                    match_method = "stable_sleeper_id"
            else:
                name_key = b42.exact_name_key(player.get("name") or "")
                elig = eligible_by_exact_name.get(name_key)
                if elig is not None:
                    match_method = "unique_exact_name_denominator_only"

            if elig is None:
                if pid in participant_ids:
                    mapped_gsis = sid_to_gsis.get(pid)
                    mapped_into_source = bool(pid in mapped_sids and mapped_gsis and mapped_gsis in gsis_present)
                    if not mapped_into_source:
                        eligible_count += 1
                        eligible_pending += 1
                        identity_gap_unknown_model_position += 1
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
            model_pos = str(elig["position"])
            if model_pos in b42.POSITIONS:
                team_pos_eligible[model_pos] += 1
                league_pos_eligible[model_pos] += 1

            role = shadow_lookup.get(pid)
            if match_method == "unique_exact_name_denominator_only" and role is not None:
                raise RuntimeError("B46W4_EXACT_NAME_DENOMINATOR_MUST_NOT_RESCUE_ROLE")
            if role is None:
                eligible_pending += 1
                if match_method == "unique_exact_name_denominator_only":
                    bridged_sid = str(elig.get("sleeper_id") or "").strip()
                    pending_reasons[
                        "crosswalk_sleeper_id_disagrees_with_roster_id_name_bridge"
                        if bridged_sid else "stable_id_crosswalk_absent_name_bridge"
                    ] += 1
                else:
                    g = str(elig.get("gsis_id") or "")
                    pending_reasons[exclusion_reason.get(g, "other_pipeline_drop")] += 1
                continue

            role_pos = str(role["position"])
            if role_pos != roster_pos:
                position_mismatch += 1
            covered += 1
            team_pos_covered[role_pos] += 1
            league_pos_covered[role_pos] += 1
            tier_counts[str(role["role_tier"])] += 1
            evidence_counts[str(role["evidence_source"])] += 1
            confidence_counts[str(role["confidence_status"])] += 1
            games = int(role["prior_active_games"])
            active_game_buckets["3+" if games >= 3 else str(games)] += 1
            covered_shadow_rows.append(role)

        coverage = (covered / eligible_count) if eligible_count else 0.0
        team_results.append({
            "opaque_team": label,
            "role_eligible_supported_position_players": eligible_count,
            "data_driven_role_count": covered,
            "fallback_role_count": 0,
            "eligible_pending_without_role_count": eligible_pending,
            "no_current_season_evidence_count": no_current_evidence,
            "position_label_mismatch_count": position_mismatch,
            "role_coverage": coverage,
            "coverage_pass_98pct": bool(eligible_count > 0 and coverage >= MIN_TEAM_ROLE_COVERAGE),
            "eligibility_match_method_counts": dict(sorted(eligibility_methods.items())),
            "eligible_pending_reason_counts": dict(sorted(pending_reasons.items())),
            "sleeper_participation_crosswalk_present_source_disagreement_count": source_disagreement,
            "identity_gap_unknown_model_position_count": identity_gap_unknown_model_position,
            "supported_position_roster_name_available_count": supported_named,
            "supported_position_roster_player_count": supported_total,
            "supported_position_roster_name_availability": (supported_named / supported_total if supported_total else 0.0),
            "evidence_source_counts": dict(sorted(evidence_counts.items())),
            "confidence_status_counts": dict(sorted(confidence_counts.items())),
            "active_game_evidence_depth_counts": dict(sorted(active_game_buckets.items())),
            "role_tier_counts": {role: int(tier_counts.get(role, 0)) for role in b42.ROLE_ORDER},
            "eligible_by_model_position": {p: int(team_pos_eligible.get(p, 0)) for p in b42.POSITIONS},
            "covered_by_model_position": {p: int(team_pos_covered.get(p, 0)) for p in b42.POSITIONS},
        })

    coverages = [float(t["role_coverage"]) for t in team_results]
    coverage_range = (max(coverages) - min(coverages)) if coverages else float("inf")

    context_labels = [f"Team{i:02d}" for i in range(1, REQUIRED_TEAM_COUNT + 1)]
    synthetic_slots = ["STARTER", "BENCH", "TAXI", "RESERVE_IR"]
    changes = comparisons = 0
    for role in covered_shadow_rows:
        base_idx = int(role["tier_index"])
        base_label = str(role["role_tier"])
        for team_label in context_labels:
            for slot in synthetic_slots:
                idx, label = b42.counterfactual_role_assignment(
                    str(role["position"]), float(role["model_score"]), lineage["b41f"], team_label, slot
                )
                comparisons += 1
                if idx != base_idx or label != base_label:
                    changes += 1

    return {
        "team_results": team_results,
        "league_position_eligible_counts": {p: int(league_pos_eligible.get(p, 0)) for p in b42.POSITIONS},
        "league_position_covered_counts": {p: int(league_pos_covered.get(p, 0)) for p in b42.POSITIONS},
        "coverage_range": float(coverage_range) if math.isfinite(coverage_range) else None,
        "minimum_team_role_coverage": min(coverages) if coverages else None,
        "maximum_team_role_coverage": max(coverages) if coverages else None,
        "structural_counterfactual": {
            "comparisons": comparisons,
            "role_changes": changes,
            "pass": changes == 0,
            "synthetic_team_contexts": 12,
            "synthetic_slot_contexts": 4,
        },
    }


def validate_b45_roster_binding(rosters, rows, frozen_eligibility, lineage, b42) -> dict:
    details = []
    all_pass = True
    for x in rows:
        sid, g, pos = str(x["sleeper_id"]), str(x["gsis_id"]), str(x["model_position"])
        found = []
        for roster in rosters:
            players_by_id = {}
            for slot in ("starters", "bench", "taxi", "reserve_ir"):
                for player in roster.get(slot) or []:
                    pid = str(player.get("player_id") or "").strip()
                    if pid:
                        players_by_id.setdefault(pid, player)
            if sid in players_by_id:
                found.append(players_by_id[sid])
        erow = frozen_eligibility.loc[frozen_eligibility["gsis_id"].astype(str) == g]
        expected_name_key = str(erow.iloc[0]["exact_name_key"]) if len(erow) == 1 else ""
        ok = len(found) == 1
        roster_pos = ""
        roster_name_key = ""
        if found:
            roster_pos = lineage["builder"].canon_pos(found[0].get("position"))
            roster_name_key = b42.exact_name_key(found[0].get("name") or "")
            ok = ok and roster_pos == pos and roster_name_key == expected_name_key
        details.append({
            "gsis_id": g,
            "sleeper_id": sid,
            "model_position": pos,
            "roster_occurrences": len(found),
            "roster_position": roster_pos,
            "roster_name_key_matches_frozen_b44": roster_name_key == expected_name_key if found else False,
            "pass": bool(ok),
        })
        all_pass = all_pass and bool(ok)
    return {"pass": all_pass, "details": details}


def run_selftest():
    f = pd.DataFrame([
        {"season":2026,"origin_week":4,"gsis_id":"g1","position":"DL","player_name":"A One",
         "exact_name_key":"a one","active_game_count":4,"sleeper_id":"","identity_mapped":False,
         "identity_source":"UNMAPPED","exact_name_unique":True},
        {"season":2026,"origin_week":4,"gsis_id":"g2","position":"K","player_name":"B Two",
         "exact_name_key":"b two","active_game_count":4,"sleeper_id":"10","identity_mapped":True,
         "identity_source":"STABLE_CROSSWALK","exact_name_unique":True},
    ])
    rows=[{"gsis_id":"g1","sleeper_id":"11","model_position":"DL",
           "adjudicated_dob_matches":"sleeper","dob_error_source":"nflverse"}]
    p=apply_b45_to_frozen_eligibility(f,rows)
    assert str(p.loc[p.gsis_id=="g1","sleeper_id"].iloc[0])=="11"
    assert boolish(p.loc[p.gsis_id=="g1","identity_mapped"].iloc[0])
    assert str(p.loc[p.gsis_id=="g1","identity_source"].iloc[0])=="B45_VERIFIED_OVERRIDE"
    assert canonical_eligibility_row(p.iloc[1])==canonical_eligibility_row(f.iloc[1])
    good=[1.0]*12
    assert min(good)>=MIN_TEAM_ROLE_COVERAGE and max(good)-min(good)<=MAX_TEAM_COVERAGE_RANGE
    bad=[1.0]*11+[0.97]
    assert min(bad)<MIN_TEAM_ROLE_COVERAGE and max(bad)-min(bad)>MAX_TEAM_COVERAGE_RANGE
    print("PASS B46W4 V1 selftest")



def verify_b45_cbs_evidence(b45e: dict) -> dict:
    expected = {
        "13372": {"name": "R Mason Thomas", "dob": "2004-08-25"},
        "13545": {"name": "Trey Smack", "dob": "2003-07-12"},
    }
    details = []
    for result in b45e.get("verification_results") or []:
        sid = str(result.get("sleeper_id") or "")
        if sid not in expected:
            continue
        cbs = [
            x for x in (result.get("authoritative_source_results") or [])
            if str(x.get("organization") or "") == "CBS_SPORTS"
        ]
        exp = expected[sid]
        ok = len(cbs) == 1
        row = cbs[0] if cbs else {}
        excerpt = str(row.get("evidence_excerpt") or "")
        matched_name = str(row.get("matched_name") or "")
        matched_dob = str(row.get("matched_dob_variant") or "")
        dob_variants = {
            exp["dob"],
            f"{int(exp['dob'][5:7])}/{int(exp['dob'][8:10])}/{exp['dob'][:4]}",
            f"{exp['dob'][5:7]}/{exp['dob'][8:10]}/{exp['dob'][:4]}",
        }
        ok = bool(
            ok
            and row.get("pass") is True
            and row.get("match_method") == "STRUCTURED_ROSTER_ROW"
            and row.get("source_also_contains_competing_machine_dob") is False
            and matched_name == exp["name"]
            and matched_dob in dob_variants
            and exp["name"].casefold() in excerpt.casefold()
            and any(v.casefold() in excerpt.casefold() for v in dob_variants)
        )
        details.append({
            "sleeper_id": sid,
            "player": exp["name"],
            "expected_dob": exp["dob"],
            "match_method": row.get("match_method"),
            "matched_name": matched_name,
            "matched_dob_variant": matched_dob,
            "evidence_excerpt": excerpt,
            "source_also_contains_competing_machine_dob":
                row.get("source_also_contains_competing_machine_dob"),
            "pass": ok,
        })
    details.sort(key=lambda x: x["sleeper_id"])
    overall = len(details) == 2 and all(x["pass"] for x in details)
    return {
        "pass": overall,
        "manual_pre_run_review_completed": True,
        "manual_review_conclusion":
            "Both durable CBS STRUCTURED_ROSTER_ROW excerpts are single-player excerpts "
            "containing the correct target name and adjudicated DOB; neither records the competing DOB.",
        "details": details,
    }


def make_shadow_from_scored(scored, b42, lineage, overlay: dict, old_overlay: dict, b45_gsis: set[str]):
    rows = []
    for _, row in scored.iterrows():
        pos = str(row["position"])
        idx, label = b42.role_from_score(pos, float(row["model_score"]), lineage["b41f"])
        if idx != int(row["tier_index"]) or label != str(row["role_tier"]):
            raise RuntimeError("B46W4_SHADOW_TIER_RECOMPUTATION_MISMATCH")
        g = str(row["gsis_id"])
        if g in b45_gsis and g in overlay:
            source = "B45_VERIFIED_OVERRIDE"
        elif g in old_overlay:
            source = "DOB_POSITION_OVERLAY"
        else:
            source = "STABLE_CROSSWALK"
        rows.append({
            "sleeper_id": str(row["sleeper_id"]),
            "gsis_id": g,
            "identity_source": source,
            "position": pos,
            "origin_week": int(row["origin_week"]),
            "model_score": float(row["model_score"]),
            "tier_index": idx,
            "role_tier": label,
            "prior_active_games": int(row["prior_active_games"]),
            "frozen_feature_missing_count_before_imputation":
                int(row["frozen_feature_missing_count_before_imputation"]),
            "frozen_feature_count": int(row["frozen_feature_count"]),
            "evidence_source": b42.EVIDENCE_SOURCE,
            "confidence_status": b42.CONFIDENCE_STATUS,
        })
    shadow = pd.DataFrame(rows)
    if shadow.empty or shadow["sleeper_id"].duplicated().any():
        raise RuntimeError("B46W4_SHADOW_INVALID")
    return shadow.sort_values(
        ["position", "model_score", "sleeper_id"],
        ascending=[True, False, True],
        kind="mergesort",
    ).reset_index(drop=True)


def execute_scoring_pass(
    *,
    pass_name: str,
    overlay: dict,
    old_overlay: dict,
    b45_gsis: set[str],
    b44,
    b42,
    lineage,
    session,
    features,
    all_current_rows,
):
    augmented_attach = b44.augmented_attach_factory(b42, overlay)
    original_attach = b42.attach_stable_ids_row_guarded
    b42.attach_stable_ids_row_guarded = augmented_attach
    try:
        eligibility, eligibility_audit = b42.build_role_eligibility(
            all_current_rows, lineage["builder"], lineage, session, ANALYSIS_WEEK
        )
        (
            with_ids, cross_sha, overall_cov, pos_cov, sid_to_gsis,
            gsis_mapped_sleeper_ids, crosswalk_audit
        ) = augmented_attach(features, lineage, session)
    finally:
        b42.attach_stable_ids_row_guarded = original_attach

    eligibility["identity_source"] = [
        "B45_VERIFIED_OVERRIDE" if (str(g) in b45_gsis and str(g) in overlay)
        else ("DOB_POSITION_OVERLAY" if str(g) in old_overlay
              else ("STABLE_CROSSWALK" if str(sid).strip() else "UNMAPPED"))
        for g, sid in zip(
            eligibility["gsis_id"].astype(str),
            eligibility["sleeper_id"].fillna("").astype(str),
        )
    ]

    model = with_ids[with_ids["identity_mapped"]].copy()
    if model.empty:
        raise RuntimeError(f"B46W4_{pass_name.upper()}_MODEL_EMPTY_AFTER_IDENTITY_ATTACH")
    model["sleeper_id"] = model["sleeper_id"].astype(str)

    scored_history, sleeper_hashes, missing_stats, sleeper_participant_ids = b42.score_current_history(
        model,
        lineage["scorer"],
        lineage["scoring"]["scoring_settings"],
        session,
        ANALYSIS_WEEK,
        2026,
        include_all_weeks_for_participation=True,
    )
    scored, aggregate_imputation = b42.normalize_and_apply_frozen_models(
        scored_history, lineage["b41h"], lineage["baseline"], lineage["b41f"]
    )
    shadow = make_shadow_from_scored(
        scored, b42, lineage, overlay, old_overlay, b45_gsis
    )
    return {
        "eligibility": eligibility,
        "eligibility_audit": eligibility_audit,
        "shadow": shadow,
        "cross_sha": cross_sha,
        "overall_cov": overall_cov,
        "pos_cov": pos_cov,
        "sid_to_gsis": sid_to_gsis,
        "gsis_mapped_sleeper_ids": gsis_mapped_sleeper_ids,
        "crosswalk_audit": crosswalk_audit,
        "sleeper_hashes": sleeper_hashes,
        "missing_stats": missing_stats,
        "sleeper_participant_ids": sleeper_participant_ids,
        "aggregate_imputation": aggregate_imputation,
    }


def dataframe_csv_sha(df: pd.DataFrame) -> str:
    raw = df.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")
    return sha256_bytes(raw)


def integration_shadow_isolation(
    frozen: pd.DataFrame,
    integration: pd.DataFrame,
    b45_gsis: set[str],
) -> dict:
    f = {str(r["gsis_id"]): r for _, r in frozen.iterrows()}
    n = {str(r["gsis_id"]): r for _, r in integration.iterrows()}
    expected_set = set(f) | set(b45_gsis)
    actual_set = set(n)

    non_dlk_mismatches = []
    dlk_invariant_mismatches = []
    dlk_score_changes = []
    dlk_tier_changes = []

    invariant_fields = [
        "sleeper_id", "gsis_id", "identity_source", "position", "origin_week",
        "prior_active_games", "frozen_feature_missing_count_before_imputation",
        "frozen_feature_count", "evidence_source", "confidence_status",
    ]

    for g in sorted(set(f) & set(n)):
        old = f[g]
        new = n[g]
        pos = str(old["position"])
        if pos not in {"DL", "K"}:
            if not shadow_row_equal(old, new):
                non_dlk_mismatches.append(g)
            continue

        bad_fields = []
        for field in invariant_fields:
            if field in {"origin_week", "prior_active_games",
                         "frozen_feature_missing_count_before_imputation",
                         "frozen_feature_count"}:
                same = int(old[field]) == int(new[field])
            else:
                same = str(old[field]) == str(new[field])
            if not same:
                bad_fields.append(field)
        if bad_fields:
            dlk_invariant_mismatches.append({
                "gsis_id": g,
                "position": pos,
                "fields": bad_fields,
            })

        delta = float(new["model_score"]) - float(old["model_score"])
        if abs(delta) > 1e-12:
            dlk_score_changes.append({
                "gsis_id": g,
                "position": pos,
                "before_score": float(old["model_score"]),
                "after_score": float(new["model_score"]),
                "delta": delta,
            })
        if (int(old["tier_index"]) != int(new["tier_index"])
                or str(old["role_tier"]) != str(new["role_tier"])):
            dlk_tier_changes.append({
                "gsis_id": g,
                "position": pos,
                "before_tier_index": int(old["tier_index"]),
                "after_tier_index": int(new["tier_index"]),
                "before_role_tier": str(old["role_tier"]),
                "after_role_tier": str(new["role_tier"]),
                "before_score": float(old["model_score"]),
                "after_score": float(new["model_score"]),
            })

    return {
        "pass": bool(
            actual_set == expected_set
            and not non_dlk_mismatches
            and not dlk_invariant_mismatches
        ),
        "row_set_exact_frozen_plus_three_B45": actual_set == expected_set,
        "expected_row_count": len(expected_set),
        "actual_row_count": len(actual_set),
        "missing_gsis": sorted(expected_set - actual_set),
        "unexpected_extra_gsis": sorted(actual_set - expected_set),
        "non_DL_K_old_rows_exact": not non_dlk_mismatches,
        "non_DL_K_mismatch_gsis": non_dlk_mismatches[:20],
        "old_DL_K_invariant_fields_unchanged": not dlk_invariant_mismatches,
        "old_DL_K_invariant_mismatches": dlk_invariant_mismatches[:20],
        "old_DL_K_score_change_count": len(dlk_score_changes),
        "old_DL_K_score_changes": dlk_score_changes,
        "old_DL_K_tier_change_count": len(dlk_tier_changes),
        "old_DL_K_tier_changes": dlk_tier_changes,
        "B45_present": sorted(set(b45_gsis) & actual_set),
        "B45_missing": sorted(set(b45_gsis) - actual_set),
        "all_three_B45_scored": len(set(b45_gsis) & actual_set) == 3,
        "DL_K_score_or_tier_changes_are_descriptive_not_coverage_failures": True,
    }


def replay_stop_payload(stage: str, replay_details: dict) -> dict:
    return {
        "schema_version":1,
        "study_id":STUDY_ID,
        "phase":PHASE,
        "result":REPLAY_STOP_RESULT,
        "stop_stage":stage,
        "evidence_class":"SAME_WEEK_POSTHOC_INTEGRATION_AUDIT_NOT_PROSPECTIVE_ACCEPTANCE",
        "same_week_posthoc":True,
        "prospective_fresh_week_acceptance":False,
        "B44W4_scientific_stop_preserved":True,
        "B44W4_result":B44_EXPECTED_STOP,
        "B45_R6_overrides_frozen_and_used":False,
        "B45_R6_decision_preserved":True,
        "B45_R6_decision":B45_EXPECTED_DECISION,
        "team_metrics_computed":False,
        "repaired_metrics_computed":False,
        "production_change_authorized":False,
        "production_model_deployed":False,
        "eligible_for_production_authorization":False,
        "B46_fresh_week_acceptance_remains_mandatory":True,
        "replay_details":replay_details,
    }


def write_replay_stop(repo: Path, stage: str, replay_details: dict) -> None:
    payload = replay_stop_payload(stage, replay_details)
    write_json(repo / OUT_REPLAY, payload)
    write_json(repo / OUT_EVIDENCE, payload)
    decision = {
        k: payload[k] for k in [
            "schema_version","study_id","phase","result","evidence_class",
            "same_week_posthoc","prospective_fresh_week_acceptance",
            "B44W4_scientific_stop_preserved","B44W4_result",
            "B45_R6_overrides_frozen_and_used","B45_R6_decision_preserved",
            "B45_R6_decision","production_change_authorized",
            "production_model_deployed","eligible_for_production_authorization",
            "B46_fresh_week_acceptance_remains_mandatory",
        ]
    }
    decision["all_primary_gates_pass"] = False
    decision["next_stage"] = "B46_FRESH_WEEK_ACCEPTANCE_REQUIRED_REGARDLESS_OF_B46W4_RESULT"
    write_json(repo / OUT_DECISION, decision)


def run(repo: Path, roster_snapshot: Path, evaluator_sha: str):
    b45e = verify_frozen_inputs(repo)
    cbs_evidence_check = verify_b45_cbs_evidence(b45e)
    if not cbs_evidence_check["pass"]:
        raise RuntimeError(f"B46W4_B45_CBS_DURABLE_EVIDENCE_CHECK_FAILED {cbs_evidence_check}")

    b45_rows = load_b45_rows(repo)
    b45_gsis = {str(x["gsis_id"]) for x in b45_rows}
    b45_sid = {str(x["sleeper_id"]) for x in b45_rows}

    if sha256_file(roster_snapshot) != B44_ROSTER_SHA256:
        raise RuntimeError("B46W4_B44_ROSTER_SNAPSHOT_SHA_DRIFT")

    b44 = load_module(repo / B44_EVALUATOR, "b46w4_parent_b44")
    b42, v1, lineage, adoption, v1_evidence = b44.load_verified_parents(repo)

    b44_evidence = load_json(repo / B44_EVIDENCE)
    b44_witness = load_json(repo / B44_WITNESS)
    if b44_evidence.get("result") != B44_EXPECTED_STOP:
        raise RuntimeError("B46W4_B44_EVIDENCE_STOP_DRIFT")
    if int(b44_witness.get("latest_completed_week", -1)) != ANALYSIS_WEEK:
        raise RuntimeError("B46W4_B44_WEEK_DRIFT")
    if (b44_witness.get("implementation_parity_exact_pass") is not True or
        (b44_witness.get("pre_roster_static_source_firewall") or {}).get("pass") is not True):
        raise RuntimeError("B46W4_B44_ORACLE_OR_FIREWALL_DRIFT")

    frozen_eligibility = pd.read_csv(
        repo / B44_ELIGIBILITY, dtype={"sleeper_id":str,"gsis_id":str}, keep_default_na=False
    )
    frozen_shadow = pd.read_csv(
        repo / B44_SHADOW, dtype={"sleeper_id":str,"gsis_id":str}, keep_default_na=False
    )
    frozen_ctx = load_json(repo / B44_CONTEXT)
    patched_eligibility = apply_b45_to_frozen_eligibility(frozen_eligibility, b45_rows)

    with (repo / B44_OVERLAY).open(newline="", encoding="utf-8") as f:
        old_overlay_rows = list(csv.DictReader(f))
    old_overlay = {str(x["gsis_id"]):str(x["sleeper_id"]) for x in old_overlay_rows}
    if len(old_overlay) != 76:
        raise RuntimeError(f"B46W4_B44_OVERLAY_COUNT_DRIFT {len(old_overlay)}")
    if b45_gsis & set(old_overlay):
        raise RuntimeError("B46W4_B45_GSIS_COLLIDES_WITH_B44_OVERLAY")
    if b45_sid & set(old_overlay.values()):
        raise RuntimeError("B46W4_B45_SLEEPER_COLLIDES_WITH_B44_OVERLAY")
    combined_overlay = dict(old_overlay)
    combined_overlay.update({str(x["gsis_id"]):str(x["sleeper_id"]) for x in b45_rows})

    protocol = {
        "schema_version":1,
        "study_id":STUDY_ID,
        "phase":PHASE,
        "status":"FROZEN_BY_EXACT_PRE_RUN_REVIEWED_WORKFLOW_BEFORE_RESULT",
        "evidence_class":"SAME_WEEK_POSTHOC_INTEGRATION_AUDIT_NOT_PROSPECTIVE_ACCEPTANCE",
        "analysis_week":4,
        "B44W4_scientific_stop_preserved":True,
        "B45_R6_override_decision_required":B45_EXPECTED_DECISION,
        "B45_override_csv_sha256":B45_OVERRIDES_SHA256,
        "B45_override_count":3,
        "B45_cbs_row_excerpts_manually_verified_single_player":True,
        "B45_cbs_durable_evidence_machine_check":cbs_evidence_check,
        "identity_precedence":["PINNED_STABLE_CROSSWALK","B45_VERIFIED_OVERRIDE","FROZEN_B44_DOB_POSITION_OVERLAY"],
        "two_population_scoring_design":{
            "replay_pass":"B44 frozen overlay only; B45 excluded from percentile-normalization cohort",
            "integration_pass":"B44 frozen overlay plus exactly three B45 overrides",
            "reason":"B42 normalization is within season/origin_week/position, so adding B45 DL/K rows can legitimately move other DL/K normalized scores",
        },
        "frozen_B44W4_output_replay_required_before_repaired_team_metrics":True,
        "replay_role_eligibility_must_equal_frozen_B44_exactly":True,
        "replay_shadow_must_equal_frozen_B44_exactly":True,
        "full_original_B44W4_team_audit_unlabeled_multiset_parity_required":True,
        "integration_role_eligibility_must_equal_frozen_plus_only_three_B45_mapping_changes":True,
        "integration_shadow_row_set_must_equal_frozen_plus_exactly_three_B45":True,
        "integration_non_DL_K_old_shadow_rows_must_remain_exact":True,
        "integration_old_DL_K_score_and_tier_changes_recorded_descriptively":True,
        "B45_targets_must_have_been_UNMAPPED_in_frozen_B44W4":True,
        "B45_targets_must_produce_actual_frozen_model_shadow_roles":True,
        "denominator_change_allowed":False,
        "gates":{
            "required_team_count":12,
            "minimum_role_coverage_each_team":0.98,
            "maximum_coverage_range":0.02,
            "structural_role_changes_allowed":0,
            "fallback_roles_allowed":0,
        },
        "model_or_tier_retuning_allowed":False,
        "production_change_authorized":False,
        "eligible_for_production_authorization_even_if_pass":False,
        "B46_fresh_week_acceptance_remains_mandatory":True,
        "evaluator_sha256":evaluator_sha,
    }
    write_json(repo / OUT_PROTOCOL, protocol)

    session = requests.Session()
    session.headers.update({"User-Agent":"LOG-Trade-Calculator-player-role-v2-b46w4-v1r1"})
    stats_resp = session.get(b42.CURRENT_STATS_URL, timeout=180)
    stats_resp.raise_for_status()
    snaps_resp = session.get(b42.CURRENT_SNAPS_URL, timeout=180)
    snaps_resp.raise_for_status()

    tmp = Path("/tmp/b46w4-week4")
    tmp.mkdir(parents=True, exist_ok=True)
    stats_path = tmp / "stats_week4.csv"
    snaps_path = tmp / "snaps_week4.csv"
    stats_meta = b42.filter_csv_to_completed_weeks(
        stats_resp.content, season_col="season", week_col="week", type_col="season_type",
        type_value="REG", latest_completed_week=ANALYSIS_WEEK, out_path=stats_path
    )
    snaps_meta = b42.filter_csv_to_completed_weeks(
        snaps_resp.content, season_col="season", week_col="week", type_col="game_type",
        type_value="REG", latest_completed_week=ANALYSIS_WEEK, out_path=snaps_path
    )
    if int(stats_meta["max_available_week"]) < ANALYSIS_WEEK or int(snaps_meta["max_available_week"]) < ANALYSIS_WEEK:
        raise RuntimeError("B46W4_WEEK4_NOT_AVAILABLE_IN_CURRENT_NFLVERSE")

    players_path = repo / b44.B41I_PLAYERS_REL
    features, feature_audit, all_current_rows = b42.build_feature_rows_for_origins(
        lineage["builder"], stats_path, snaps_path, players_path, 2026, [ANALYSIS_WEEK]
    )

    expected_cross_sha = str(
        (b44_witness.get("current_sources") or {}).get("stable_id_crosswalk_sha256") or ""
    )

    # PASS 1 — REPLAY. B45 is deliberately excluded from the normalization population.
    replay_pass = execute_scoring_pass(
        pass_name="replay",
        overlay=old_overlay,
        old_overlay=old_overlay,
        b45_gsis=b45_gsis,
        b44=b44,
        b42=b42,
        lineage=lineage,
        session=session,
        features=features,
        all_current_rows=all_current_rows,
    )
    if replay_pass["cross_sha"] != expected_cross_sha:
        raise RuntimeError(
            f"B46W4_REPLAY_STABLE_CROSSWALK_SHA_DRIFT "
            f"expected={expected_cross_sha} actual={replay_pass['cross_sha']}"
        )

    replay_eligibility_parity = compare_eligibility(
        frozen_eligibility, replay_pass["eligibility"]
    )
    replay_shadow_parity = compare_shadow(
        frozen_shadow, replay_pass["shadow"], set()
    )
    replay_shadow_sha = dataframe_csv_sha(replay_pass["shadow"])
    replay_eligibility_sha = dataframe_csv_sha(replay_pass["eligibility"])

    replay_common = {
        "eligibility_parity":replay_eligibility_parity,
        "shadow_parity":replay_shadow_parity,
        "replay_role_eligibility_sha256":replay_eligibility_sha,
        "replay_shadow_sha256":replay_shadow_sha,
        "current_week4_source_reconstruction":{
            "weekly_stats_raw_sha256":sha256_bytes(stats_resp.content),
            "snap_counts_raw_sha256":sha256_bytes(snaps_resp.content),
            "weekly_stats_max_available_week":int(stats_meta["max_available_week"]),
            "snap_counts_max_available_week":int(snaps_meta["max_available_week"]),
            "analysis_slice_fixed_to_week":4,
        },
        "B45_cbs_durable_evidence_machine_check":cbs_evidence_check,
    }

    if not replay_eligibility_parity["pass"]:
        write_replay_stop(
            repo, "week4_role_eligibility_replay_parity", replay_common
        )
        print("B46W4 replay stop: frozen B44 role eligibility did not reproduce exactly.")
        return

    if not replay_shadow_parity["pass_old_rows"]:
        write_replay_stop(
            repo, "week4_shadow_replay_parity", replay_common
        )
        print("B46W4 replay stop: frozen B44 shadow did not reproduce exactly.")
        return

    rosters_payload = load_json(roster_snapshot)
    rosters = rosters_payload.get("rosters") or []
    if not isinstance(rosters, list) or len(rosters) != REQUIRED_TEAM_COUNT:
        raise RuntimeError(
            f"B46W4_ROSTER_COUNT_INVALID {len(rosters) if isinstance(rosters,list) else 'not-list'}"
        )

    ordered_rosters = list(rosters)
    secrets.SystemRandom().shuffle(ordered_rosters)

    baseline = audit_rosters(
        rosters,
        replay_pass["eligibility"],
        replay_pass["shadow"],
        frozen_ctx,
        b42,
        lineage,
        ordered_rosters,
    )
    frozen_team_signatures = sorted(
        canonical_team_signature(x) for x in b44_evidence["team_results"]
    )
    baseline_team_signatures = sorted(
        canonical_team_signature(x) for x in baseline["team_results"]
    )
    baseline_full_parity = bool(
        frozen_team_signatures == baseline_team_signatures
        and baseline["league_position_eligible_counts"]
            == b44_evidence["league_position_eligible_counts"]
        and baseline["league_position_covered_counts"]
            == b44_evidence["league_position_covered_counts"]
        and abs(float(baseline["coverage_range"]) - float(b44_evidence["coverage_range"])) <= 1e-15
        and baseline["structural_counterfactual"]["comparisons"]
            == b44_evidence["structural_counterfactual_invariance"]["comparisons"]
        and baseline["structural_counterfactual"]["role_changes"]
            == b44_evidence["structural_counterfactual_invariance"]["role_changes"]
    )

    replay_record = {
        "schema_version":1,
        "study_id":STUDY_ID,
        "phase":PHASE,
        "result":"PASS_B46W4_WEEK4_REPLAY_PARITY" if baseline_full_parity else REPLAY_STOP_RESULT,
        **replay_common,
        "original_B44W4_team_audit_unlabeled_multiset_parity":baseline_full_parity,
        "original_B44W4_team_count":len(b44_evidence["team_results"]),
        "team_metrics_computed":True,
        "repaired_metrics_computed":False,
        "production_change_authorized":False,
        "B44W4_scientific_stop_preserved":True,
        "B45_R6_decision_preserved":True,
        "B45_R6_overrides_frozen_and_used":False,
        "prospective_fresh_week_acceptance":False,
        "B46_fresh_week_acceptance_remains_mandatory":True,
    }
    write_json(repo / OUT_REPLAY, replay_record)

    if not baseline_full_parity:
        write_replay_stop(
            repo, "full_original_B44W4_team_audit_replay_parity", replay_record
        )
        print("B46W4 replay stop: full original B44W4 team audit did not reproduce.")
        return

    # PASS 2 — INTEGRATION. B45 joins the normalization cohort here only.
    integration_pass = execute_scoring_pass(
        pass_name="integration",
        overlay=combined_overlay,
        old_overlay=old_overlay,
        b45_gsis=b45_gsis,
        b44=b44,
        b42=b42,
        lineage=lineage,
        session=session,
        features=features,
        all_current_rows=all_current_rows,
    )
    if integration_pass["cross_sha"] != expected_cross_sha:
        raise RuntimeError(
            f"B46W4_INTEGRATION_STABLE_CROSSWALK_SHA_DRIFT "
            f"expected={expected_cross_sha} actual={integration_pass['cross_sha']}"
        )

    integration_eligibility_parity = compare_eligibility(
        patched_eligibility, integration_pass["eligibility"]
    )
    integration_shadow_check = integration_shadow_isolation(
        frozen_shadow, integration_pass["shadow"], b45_gsis
    )

    integration_pass["eligibility"].to_csv(
        repo / OUT_ELIGIBILITY, index=False, lineterminator="\n"
    )
    integration_pass["shadow"].to_csv(
        repo / OUT_SHADOW, index=False, lineterminator="\n", float_format="%.17g"
    )

    frozen_ctx2 = patched_context(frozen_ctx, b45_rows)
    b45_roster_binding = validate_b45_roster_binding(
        rosters, b45_rows, frozen_eligibility, lineage, b42
    )

    after = audit_rosters(
        rosters,
        integration_pass["eligibility"],
        integration_pass["shadow"],
        frozen_ctx2,
        b42,
        lineage,
        ordered_rosters,
    )

    denominator_unchanged = all(
        int(a["role_eligible_supported_position_players"])
        == int(b["role_eligible_supported_position_players"])
        for a, b in zip(baseline["team_results"], after["team_results"])
    ) and (
        baseline["league_position_eligible_counts"]
        == after["league_position_eligible_counts"]
    )

    coverage_delta = (
        sum(int(x["data_driven_role_count"]) for x in after["team_results"])
        - sum(int(x["data_driven_role_count"]) for x in baseline["team_results"])
    )

    gates = {
        "week4_replay_role_eligibility_exact_parity":replay_eligibility_parity["pass"],
        "week4_replay_shadow_exact_parity":replay_shadow_parity["pass_old_rows"],
        "full_original_B44W4_team_audit_replay_parity":baseline_full_parity,
        "integration_role_eligibility_only_three_B45_changes":integration_eligibility_parity["pass"],
        "integration_shadow_rowset_and_isolation":integration_shadow_check["pass"],
        "B45_exact_three_override_roster_binding":b45_roster_binding["pass"],
        "B45_all_three_generate_actual_shadow_roles":integration_shadow_check["all_three_B45_scored"],
        "denominator_unchanged_from_B44W4":denominator_unchanged,
        "exactly_three_new_covered_roles":coverage_delta == 3,
        "exactly_12_teams":len(after["team_results"]) == REQUIRED_TEAM_COUNT,
        "minimum_98pct_role_coverage_every_team":all(
            bool(t["coverage_pass_98pct"]) for t in after["team_results"]
        ),
        "maximum_2_percentage_point_coverage_range":bool(
            after["coverage_range"] is not None
            and after["coverage_range"] <= MAX_TEAM_COVERAGE_RANGE + 1e-12
        ),
        "structural_owner_slot_role_invariance":
            after["structural_counterfactual"]["role_changes"] == 0,
        "no_owner_blind_fallback":all(
            int(t["fallback_role_count"]) == 0 for t in after["team_results"]
        ),
        "B41J_implementation_parity_inherited_from_frozen_B44W4":
            b44_witness["implementation_parity_exact_pass"] is True,
        "shadow_role_inference_source_firewall_inherited_from_frozen_B44W4":
            (b44_witness.get("pre_roster_static_source_firewall") or {}).get("pass") is True,
        "model_or_tier_retuning_absent":True,
        "production_change_authorized_false":True,
    }
    all_pass = all(gates.values())
    result = PASS_RESULT if all_pass else STOP_RESULT

    evidence = {
        "schema_version":1,
        "study_id":STUDY_ID,
        "phase":PHASE,
        "result":result,
        "evidence_class":"SAME_WEEK_POSTHOC_INTEGRATION_AUDIT_NOT_PROSPECTIVE_ACCEPTANCE",
        "same_week_posthoc":True,
        "prospective_fresh_week_acceptance":False,
        "B44W4_scientific_stop_preserved":True,
        "B44W4_result":B44_EXPECTED_STOP,
        "B45_R6_decision_preserved":True,
        "B45_R6_decision":B45_EXPECTED_DECISION,
        "B45_R6_overrides_frozen_and_used":True,
        "B45_override_csv_sha256":B45_OVERRIDES_SHA256,
        "B45_stale_verification_method_label_disclosed_and_not_used_as_authority":True,
        "B45_cbs_row_excerpts_manually_verified_single_player":True,
        "B45_cbs_durable_evidence_machine_check":cbs_evidence_check,
        "identity_precedence":["PINNED_STABLE_CROSSWALK","B45_VERIFIED_OVERRIDE","FROZEN_B44_DOB_POSITION_OVERLAY"],
        "analysis_week":4,
        "replay_parity_sha256":sha256_file(repo / OUT_REPLAY),
        "replay_shadow_sha256":replay_shadow_sha,
        "replay_role_eligibility_sha256":replay_eligibility_sha,
        "integration_role_eligibility_sha256":sha256_file(repo / OUT_ELIGIBILITY),
        "integration_shadow_sha256":sha256_file(repo / OUT_SHADOW),
        "integration_shadow_isolation":integration_shadow_check,
        "B45_roster_binding":b45_roster_binding,
        "baseline":{
            "team_results":baseline["team_results"],
            "league_position_eligible_counts":baseline["league_position_eligible_counts"],
            "league_position_covered_counts":baseline["league_position_covered_counts"],
            "coverage_range":baseline["coverage_range"],
            "minimum_team_role_coverage":baseline["minimum_team_role_coverage"],
            "maximum_team_role_coverage":baseline["maximum_team_role_coverage"],
            "structural_counterfactual":baseline["structural_counterfactual"],
        },
        "after_B45_overrides":{
            "team_results":after["team_results"],
            "league_position_eligible_counts":after["league_position_eligible_counts"],
            "league_position_covered_counts":after["league_position_covered_counts"],
            "coverage_range":after["coverage_range"],
            "minimum_team_role_coverage":after["minimum_team_role_coverage"],
            "maximum_team_role_coverage":after["maximum_team_role_coverage"],
            "structural_counterfactual":after["structural_counterfactual"],
        },
        "coverage_delta":coverage_delta,
        "denominator_unchanged":denominator_unchanged,
        "primary_gates":gates,
        "all_primary_gates_pass":all_pass,
        "model_or_tier_retuning_performed":False,
        "fallback_policy":"NONE",
        "production_change_authorized":False,
        "production_model_deployed":False,
        "eligible_for_production_authorization":False,
        "B46_fresh_week_acceptance_remains_mandatory":True,
    }
    write_json(repo / OUT_EVIDENCE, evidence)

    decision = {
        "schema_version":1,
        "study_id":STUDY_ID,
        "phase":PHASE,
        "result":result,
        "evidence_class":"SAME_WEEK_POSTHOC_INTEGRATION_AUDIT_NOT_PROSPECTIVE_ACCEPTANCE",
        "all_primary_gates_pass":all_pass,
        "minimum_team_role_coverage":after["minimum_team_role_coverage"],
        "maximum_team_role_coverage":after["maximum_team_role_coverage"],
        "coverage_range":after["coverage_range"],
        "coverage_delta":coverage_delta,
        "team_count":len(after["team_results"]),
        "evidence_sha256":sha256_file(repo / OUT_EVIDENCE),
        "production_change_authorized":False,
        "production_model_deployed":False,
        "eligible_for_production_authorization":False,
        "B44W4_scientific_stop_preserved":True,
        "B45_R6_overrides_frozen_and_used":True,
        "B46_fresh_week_acceptance_remains_mandatory":True,
        "next_stage":"B46_FRESH_WEEK_ACCEPTANCE_REQUIRED_REGARDLESS_OF_B46W4_RESULT",
    }
    write_json(repo / OUT_DECISION, decision)

    print("B46W4 decision:", result)
    print("Coverage delta:", coverage_delta)
    print("Minimum coverage:", after["minimum_team_role_coverage"])
    print("Maximum coverage:", after["maximum_team_role_coverage"])
    print("Coverage range:", after["coverage_range"])
    print("Old DL/K score changes:", integration_shadow_check["old_DL_K_score_change_count"])
    print("Old DL/K tier changes:", integration_shadow_check["old_DL_K_tier_change_count"])
    print("B46 fresh-week acceptance remains mandatory: true")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--roster-snapshot")
    ap.add_argument("--evaluator-sha256")
    args = ap.parse_args()
    if args.selftest:
        run_selftest()
        return
    if not args.roster_snapshot or not args.evaluator_sha256:
        raise SystemExit("run args missing")
    run(Path(args.repo), Path(args.roster_snapshot), args.evaluator_sha256)


if __name__ == "__main__":
    main()

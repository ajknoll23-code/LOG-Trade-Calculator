#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import requests

SUPPORTED_MODEL_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DL", "LB", "DB"}
MISSING = {"", "na", "nan", "none", "null", "n/a"}
SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}
NON_CLUB_TEAM_CODES = {"FA", "UFA", "RFA"}
REFERENCE_MIN_COMPARISONS_TOTAL = 500
RULE_MIN_REFERENCE_COMPARISONS = 50
MIN_COMBINED_CURRENT_ELIGIBLE_COVERAGE = 0.995


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def clean(value) -> str:
    x = str(value if value is not None else "").strip()
    return "" if x.casefold() in MISSING else x


def parse_sid(value) -> str | None:
    x = clean(value)
    if not x:
        return None
    if re.fullmatch(r"\d+\.0+", x):
        x = x.split(".", 1)[0]
    return x if re.fullmatch(r"\d+", x) else None


def canonical_name(value) -> str:
    x = clean(value)
    if not x:
        return ""
    x = unicodedata.normalize("NFKD", x)
    x = "".join(ch for ch in x if not unicodedata.combining(ch))
    x = x.casefold()
    x = re.sub(r"[^a-z0-9]+", " ", x)
    tokens = [t for t in x.split() if t]
    while tokens and tokens[-1] in SUFFIX_TOKENS:
        tokens.pop()
    merged = []
    i = 0
    while i < len(tokens):
        if len(tokens[i]) == 1:
            run = []
            while i < len(tokens) and len(tokens[i]) == 1:
                run.append(tokens[i])
                i += 1
            merged.append("".join(run))
        else:
            merged.append(tokens[i])
            i += 1
    return " ".join(merged)


def team_key(value) -> str:
    x = re.sub(r"[^A-Z]", "", clean(value).upper())
    aliases = {
        "ARI": "ARI", "ATL": "ATL", "BAL": "BAL", "BUF": "BUF",
        "CAR": "CAR", "CHI": "CHI", "CIN": "CIN", "CLE": "CLE",
        "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GB": "GB",
        "GBP": "GB", "HOU": "HOU", "IND": "IND", "JAC": "JAX",
        "JAX": "JAX", "KC": "KC", "KCC": "KC", "LV": "LV",
        "LVR": "LV", "LAC": "LAC", "LAR": "LAR", "MIA": "MIA",
        "MIN": "MIN", "NE": "NE", "NEP": "NE", "NO": "NO",
        "NOS": "NO", "NYG": "NYG", "NYJ": "NYJ", "PHI": "PHI",
        "PIT": "PIT", "SEA": "SEA", "SF": "SF", "SFO": "SF",
        "TB": "TB", "TBB": "TB", "TEN": "TEN", "WAS": "WAS",
        "WSH": "WAS",
    }
    normalized = aliases.get(x, x)
    return "" if normalized in NON_CLUB_TEAM_CODES else normalized


def position_family(value) -> str:
    x = clean(value).upper()
    if x in {"QB"}:
        return "QB"
    if x in {"RB", "FB", "HB"}:
        return "RB"
    if x in {"WR"}:
        return "WR"
    if x in {"TE"}:
        return "TE"
    if x in {"K", "PK"}:
        return "K"
    if x in {"DL", "DE", "DT", "NT", "EDGE", "ED", "LB", "ILB", "OLB"}:
        return "FRONT7"
    if x in {"DB", "CB", "S", "FS", "SS"}:
        return "DB"
    return ""


def source_get(session: requests.Session, url: str, attempts: int = 4) -> bytes:
    err = None
    for i in range(attempts):
        try:
            r = session.get(url, timeout=45)
            r.raise_for_status()
            return r.content
        except Exception as exc:
            err = exc
            if i + 1 < attempts:
                time.sleep(2 ** i)
    raise RuntimeError(f"B43_SOURCE_FETCH_FAILED url={url} error={err}")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_crosswalk_bytes(payload: bytes):
    text = payload.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    required = {"gsis_id", "sleeper_id"}
    if not rows or not required.issubset(rows[0]):
        raise RuntimeError("B43_CROSSWALK_SCHEMA_MISSING")
    gsis_to_sids = defaultdict(set)
    sid_to_gsis = defaultdict(set)
    missing_gsis_with_sid = 0
    for row in rows:
        g = clean(row.get("gsis_id"))
        sid = parse_sid(row.get("sleeper_id"))
        if sid and not g:
            missing_gsis_with_sid += 1
        if g and sid:
            gsis_to_sids[g].add(sid)
            sid_to_gsis[sid].add(g)
    ambiguous_gsis = {g: sorted(v) for g, v in gsis_to_sids.items() if len(v) > 1}
    ambiguous_sid = {s: sorted(v) for s, v in sid_to_gsis.items() if len(v) > 1}
    if ambiguous_gsis:
        raise RuntimeError(f"B43_REAL_AMBIGUOUS_GSIS_CROSSWALK count={len(ambiguous_gsis)}")
    if ambiguous_sid:
        raise RuntimeError(f"B43_REAL_AMBIGUOUS_SLEEPER_CROSSWALK count={len(ambiguous_sid)}")
    exact = {g: next(iter(v)) for g, v in gsis_to_sids.items()}
    inverse = {s: next(iter(v)) for s, v in sid_to_gsis.items()}
    return exact, inverse, {
        "rows_with_sleeper_id_but_missing_gsis": int(missing_gsis_with_sid),
        "exact_pair_count": int(len(exact)),
    }


def sleeper_records_from_payload(payload: bytes):
    raw = json.loads(payload)
    if not isinstance(raw, dict):
        raise RuntimeError("B43_SLEEPER_PLAYER_MAP_NOT_OBJECT")
    records = []
    for key, rec in raw.items():
        if not isinstance(rec, dict):
            continue
        sid = parse_sid(rec.get("player_id") or key)
        if not sid:
            continue
        first = clean(rec.get("first_name"))
        last = clean(rec.get("last_name"))
        full = clean(rec.get("full_name")) or " ".join(x for x in (first, last) if x)
        name_key = canonical_name(full)
        pos = clean(rec.get("position"))
        fam = position_family(pos)
        if not name_key or not fam:
            continue
        records.append({
            "sleeper_id": sid,
            "full_name": full,
            "name_key": name_key,
            "birth_date": clean(rec.get("birth_date")),
            "position": pos,
            "position_family": fam,
            "nfl_team": team_key(rec.get("team")),
            "status": clean(rec.get("status")),
        })
    return raw, records


def sleeper_records_from_snapshot_csv(payload: bytes):
    text = payload.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    required = {"sleeper_id","full_name","name_key","birth_date","position","position_family","nfl_team","status"}
    if not rows or not required.issubset(rows[0]):
        raise RuntimeError("B43_V2R1_SLEEPER_SNAPSHOT_SCHEMA_MISSING")
    records = []
    for row in rows:
        sid = parse_sid(row.get("sleeper_id"))
        name_key = canonical_name(row.get("name_key") or row.get("full_name"))
        fam = clean(row.get("position_family")) or position_family(row.get("position"))
        if not sid or not name_key or not fam:
            continue
        records.append({
            "sleeper_id": sid,
            "full_name": clean(row.get("full_name")),
            "name_key": name_key,
            "birth_date": clean(row.get("birth_date")),
            "position": clean(row.get("position")),
            "position_family": fam,
            "nfl_team": team_key(row.get("nfl_team")),
            "status": clean(row.get("status")),
        })
    return records


def load_current_eligible_and_nfl_identity(repo: Path):
    base = repo / "research/player-role-v2"
    evidence = load_json(base / "player_role_v2_b42_v4_owner_blind_evidence.json")
    elig_path = base / "player_role_v2_b42_v4_role_eligibility.csv"
    if sha256_file(elig_path) != evidence["role_eligibility_sha256"]:
        raise RuntimeError("B43_B42_ROLE_ELIGIBILITY_HASH_MISMATCH")
    with elig_path.open(newline="", encoding="utf-8") as f:
        eligible = list(csv.DictReader(f))
    eligible = [r for r in eligible if clean(r.get("gsis_id")) and clean(r.get("position")) in SUPPORTED_MODEL_POSITIONS]

    players_path = base / "frozen_inputs/players_b41i_snapshot.csv"
    expected_players_sha = "d531dcff2d3ff681f02210d314f6e9f16c671c0beefa85fd311a55363675d4cc"
    if sha256_file(players_path) != expected_players_sha:
        raise RuntimeError("B43_NFLVERSE_IDENTITY_SNAPSHOT_HASH_MISMATCH")
    identity = {}
    with players_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            g = clean(row.get("gsis_id"))
            if g:
                identity[g] = {
                    "display_name": clean(row.get("display_name")),
                    "birth_date": clean(row.get("birth_date")),
                    "position": clean(row.get("position")),
                    "position_group": clean(row.get("position_group")),
                    "latest_team": team_key(row.get("latest_team")),
                }
    current = []
    for row in eligible:
        g = clean(row.get("gsis_id"))
        meta = identity.get(g, {})
        name = clean(row.get("player_name")) or meta.get("display_name", "")
        model_pos = clean(row.get("position"))
        current.append({
            "gsis_id": g,
            "player_name": name,
            "name_key": canonical_name(name),
            "birth_date": clean(meta.get("birth_date")),
            "model_position": model_pos,
            "position_family": position_family(model_pos) or position_family(meta.get("position_group")) or position_family(meta.get("position")),
            "nfl_team": team_key(meta.get("latest_team")),
        })
    return current


def load_b41i_identity_map(repo: Path):
    base = repo / "research/player-role-v2"
    players_path = base / "frozen_inputs/players_b41i_snapshot.csv"
    expected_players_sha = "d531dcff2d3ff681f02210d314f6e9f16c671c0beefa85fd311a55363675d4cc"
    if sha256_file(players_path) != expected_players_sha:
        raise RuntimeError("B43_NFLVERSE_IDENTITY_SNAPSHOT_HASH_MISMATCH")
    out = {}
    with players_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            g = clean(row.get("gsis_id"))
            if not g:
                continue
            name = clean(row.get("display_name"))
            fam = position_family(row.get("position_group")) or position_family(row.get("position"))
            out[g] = {
                "name_key": canonical_name(name),
                "birth_date": clean(row.get("birth_date")),
                "position_family": fam,
            }
    return out


def masked_reference_row(row: dict, rule: str) -> dict:
    if rule == "DOB_POSITION":
        return row
    masked = dict(row)
    masked["birth_date"] = ""
    return masked


def collision_is_duplicate_identity(proposal: dict, other_gsis_ids, b41i_identity: dict) -> bool:
    base = b41i_identity.get(proposal["gsis_id"])
    if not base or not base.get("name_key") or not base.get("birth_date") or not base.get("position_family"):
        return False
    others = sorted(set(other_gsis_ids) - {proposal["gsis_id"]})
    if not others:
        return False
    for g in others:
        other = b41i_identity.get(g)
        if not other or not other.get("name_key") or not other.get("birth_date") or not other.get("position_family"):
            return False
        if (other["name_key"], other["birth_date"], other["position_family"]) != (
            base["name_key"], base["birth_date"], base["position_family"]
        ):
            return False
    return True


RULE_ORDER = ("DOB_POSITION", "NFL_TEAM_POSITION", "UNIQUE_NAME_POSITION")


def contradiction_filtered_candidates(nfl_row: dict, sleeper_by_name: dict[str, list[dict]]):
    candidates = [
        x for x in sleeper_by_name.get(nfl_row["name_key"], [])
        if x["position_family"] == nfl_row["position_family"]
    ]
    bd = nfl_row["birth_date"]
    if bd:
        candidates = [x for x in candidates if not x["birth_date"] or x["birth_date"] == bd]
    return candidates


def candidate_for_rule(nfl_row: dict, sleeper_by_name: dict[str, list[dict]], rule: str):
    candidates = contradiction_filtered_candidates(nfl_row, sleeper_by_name)
    if not candidates:
        return None
    if rule == "DOB_POSITION":
        bd = nfl_row["birth_date"]
        if not bd:
            return None
        exact = [x for x in candidates if x["birth_date"] and x["birth_date"] == bd]
        return exact[0] if len(exact) == 1 else None
    if rule == "NFL_TEAM_POSITION":
        team = nfl_row["nfl_team"]
        if not team:
            return None
        exact = [x for x in candidates if x["nfl_team"] and x["nfl_team"] == team]
        return exact[0] if len(exact) == 1 else None
    if rule == "UNIQUE_NAME_POSITION":
        return candidates[0] if len(candidates) == 1 else None
    raise RuntimeError(f"B43_V2R1_UNKNOWN_RULE {rule}")


def candidate_for(nfl_row: dict, sleeper_by_name: dict[str, list[dict]]):
    for rule in RULE_ORDER:
        rec = candidate_for_rule(nfl_row, sleeper_by_name, rule)
        if rec is not None:
            return rec, rule
    return None


def protocol_payload() -> dict:
    return {
        "schema_version": 3,
        "study_id": "player-role-v2",
        "phase": "B43-v2r1-owner-blind-identity-bridge-remediation-feasibility",
        "status": "FROZEN_BEFORE_B43_V2R1_IDENTITY_BRIDGE_RESULTS",
        "motivation": (
            "B43 V1 produced a valid scientific STOP. The blocked V2 pre-run candidate correctly repaired priority-routing starvation, "
            "but independent review found that lower-priority reference trials still benefited from DOB filtering and that V2's accepted-bridge "
            "collision gate was tautological. V2R1 prospectively repairs both issues before any V2/V2R1 identity result is opened, while preserving "
            "the matcher priority, identity rules, 99.5% coverage threshold, and production firewall."
        ),
        "scientific_boundary": {
            "B42_team_level_results_are_prior_observed_evidence": True,
            "B43_V1_results_are_prior_observed_evidence": True,
            "B43_V2R1_is_post_V1_remediation_not_independent_confirmation": True,
            "B43_V2_pre_run_review_is_prior_design_feedback_not_result_evidence": True,
            "B43_may_not_parse_or_use_league_rosters": True,
            "B43_may_not_use_owner_identity_or_fantasy_roster_partition": True,
            "player_specific_exceptions_allowed": False,
            "role_model_or_tier_changes_allowed": False,
            "posthoc_B42_or_B43V1_player_list_may_be_encoded": False,
        },
        "sources": {
            "current_football_population": "exact B42 V4 owner-blind role-eligibility artifact",
            "nfl_identity_metadata": "exact frozen B41I nflverse player snapshot",
            "reference_identity_pairs": "exact B41G-pinned dynastyprocess stable-ID crosswalk",
            "candidate_sleeper_identity_source": "exact committed B43 V1 Sleeper identity snapshot; no V2R1 Sleeper refetch",
        },
        "matching_rules_in_fixed_priority": [
            "DOB_POSITION: canonical name + compatible model/Sleeper position family + exact nonmissing birth date, unique candidate",
            "NFL_TEAM_POSITION: canonical name + compatible position family + exact normalized NFL club, unique candidate; free-agent/status codes are not clubs",
            "UNIQUE_NAME_POSITION: canonical name + compatible position family, exactly one Sleeper candidate",
        ],
        "matcher_priority_changed_from_B43_V1": False,
        "dob_contradiction_veto": True,
        "dob_contradiction_veto_semantics": "In application, when nflverse DOB is nonmissing, discard any candidate with a different nonmissing DOB before any rule; if none remain, return no match.",
        "lower_priority_reference_validation_dob_mask": True,
        "lower_priority_reference_validation_dob_mask_semantics": "For NFL_TEAM_POSITION and UNIQUE_NAME_POSITION known-pair gate trials, validate on a copy of the reference row with birth_date blank so those rules must disambiguate without DOB filtering. DOB-informed lower-rule trials are descriptive only.",
        "non_club_team_codes_excluded_from_team_rule": sorted(NON_CLUB_TEAM_CODES),
        "canonical_name_rule": "Unicode NFKD; remove combining marks; casefold; replace non-alphanumeric runs with spaces; collapse whitespace; remove terminal Jr/Sr/II/III/IV/V suffix tokens",
        "position_compatibility": "QB/RB/WR/TE/K/DB exact families; DL and LB share FRONT7 to tolerate platform-vs-model edge classification",
        "validation_design": {
            "reference_pairs_are_not_used_to_generate_candidate_features": True,
            "each_rule_is_evaluated_independently_on_every_known_reference_row_for_which_that_rule_can_make_a_unique_prediction": True,
            "priority_matcher_output_is_not_used_to_allocate_reference_trials_to_rules": True,
            "lower_priority_rules_gate_on_birth_date_masked_reference_trials": True,
            "birth_date_informed_lower_rule_trials_are_descriptive_only": True,
            "known_stable_ID_pairs_are_masked_truth_for_known_pair_reference_precision": True,
            "rule_application_is_allowed_only_if_that_rule_has_at_least_50_gating_reference_comparisons_and_zero_gating_reference_conflicts_and_zero_collision_evidence_conflicts": True,
            "minimum_total_reference_comparisons_across_final_eligible_rules": REFERENCE_MIN_COMPARISONS_TOTAL,
        },
        "collision_evidence": {
            "classifier_specified_after_B43_V1_observed_two_collisions": True,
            "proposal_collision_may_enter_accepted_bridge": False,
            "duplicate_identity_definition": "Every other GSIS claimant of the same Sleeper ID must exist in frozen B41I with the same canonical name, same nonmissing birth date, and same position family as the proposing GSIS ID.",
            "nonduplicate_stable_or_supplemental_sleeper_collision_counts_as_rule_conflict": True,
            "rule_with_any_collision_evidence_conflict_is_ineligible": True,
            "accepted_bridge_one_to_one_is_structural_invariant_not_primary_gate": True,
        },
        "primary_gates": {
            "no_roster_or_owner_context": True,
            "minimum_total_reference_comparisons_across_eligible_rules": REFERENCE_MIN_COMPARISONS_TOTAL,
            "reference_and_collision_conflicts_allowed_per_eligible_rule": 0,
            "minimum_reference_comparisons_per_applied_rule": RULE_MIN_REFERENCE_COMPARISONS,
            "minimum_base_plus_supplemental_current_eligible_coverage": MIN_COMBINED_CURRENT_ELIGIBLE_COVERAGE,
            "minimum_supplemental_mapping_count": 1,
        },
        "production_firewall": {
            "B43_authorizes_production_change": False,
            "B43_deploys_model": False,
            "B44_owner_blind_reaudit_required_after_B43_pass": True,
            "B44_must_be_framed_as_post_remediation_acceptance_not_independent_confirmation": True,
            "original_B44_minimum_team_coverage": 0.98,
            "original_B44_maximum_team_coverage_range": 0.02,
        },
    }

def run_selftest() -> None:
    assert canonical_name("A.J. Example") == canonical_name("AJ Example") == "aj example"
    assert canonical_name("John Smith Jr.") == "john smith"
    assert clean("NA") == ""
    assert parse_sid("1234.0") == "1234"
    assert parse_sid("NA") is None
    assert position_family("DL") == position_family("LB") == "FRONT7"
    assert team_key("KCC") == team_key("KC") == "KC"
    assert team_key("FA") == team_key("FA*") == team_key("UFA") == team_key("RFA") == ""
    sleepers = {
        "aj example": [{"sleeper_id":"1","name_key":"aj example","birth_date":"2003-01-01","position_family":"DB","nfl_team":"ARI"}],
        "casey sample": [{"sleeper_id":"2","name_key":"casey sample","birth_date":"","position_family":"FRONT7","nfl_team":"CLE"}],
        "unique sample": [{"sleeper_id":"4","name_key":"unique sample","birth_date":"","position_family":"WR","nfl_team":""}],
        "conflict person": [{"sleeper_id":"3","name_key":"conflict person","birth_date":"1999-01-01","position_family":"WR","nfl_team":"ARI"}],
        "masked homonym": [
            {"sleeper_id":"7","name_key":"masked homonym","birth_date":"1999-01-01","position_family":"WR","nfl_team":"ARI"},
            {"sleeper_id":"8","name_key":"masked homonym","birth_date":"2001-01-01","position_family":"WR","nfl_team":"ARI"},
        ],
    }
    row={"name_key":"aj example","birth_date":"2003-01-01","position_family":"DB","nfl_team":"ARI"}
    got=candidate_for(row,sleepers)
    assert got and got[0]["sleeper_id"]=="1" and got[1]=="DOB_POSITION"
    assert candidate_for_rule(row,sleepers,"DOB_POSITION")["sleeper_id"]=="1"
    assert candidate_for_rule(masked_reference_row(row,"NFL_TEAM_POSITION"),sleepers,"NFL_TEAM_POSITION")["sleeper_id"]=="1"
    assert candidate_for_rule(masked_reference_row(row,"UNIQUE_NAME_POSITION"),sleepers,"UNIQUE_NAME_POSITION")["sleeper_id"]=="1"
    team_row={"name_key":"casey sample","birth_date":"","position_family":"FRONT7","nfl_team":"CLE"}
    assert candidate_for_rule(team_row,sleepers,"NFL_TEAM_POSITION")["sleeper_id"]=="2"
    unique_row={"name_key":"unique sample","birth_date":"","position_family":"WR","nfl_team":""}
    assert candidate_for_rule(unique_row,sleepers,"UNIQUE_NAME_POSITION")["sleeper_id"]=="4"
    conflict_row={"name_key":"conflict person","birth_date":"2001-01-01","position_family":"WR","nfl_team":"ARI"}
    assert candidate_for(conflict_row,sleepers) is None
    assert candidate_for_rule(conflict_row,sleepers,"NFL_TEAM_POSITION") is None
    assert candidate_for_rule(conflict_row,sleepers,"UNIQUE_NAME_POSITION") is None
    homonym_row={"name_key":"masked homonym","birth_date":"2001-01-01","position_family":"WR","nfl_team":"ARI"}
    assert candidate_for_rule(homonym_row,sleepers,"UNIQUE_NAME_POSITION")["sleeper_id"]=="8"
    assert candidate_for_rule(masked_reference_row(homonym_row,"UNIQUE_NAME_POSITION"),sleepers,"UNIQUE_NAME_POSITION") is None
    assert candidate_for_rule(masked_reference_row(homonym_row,"NFL_TEAM_POSITION"),sleepers,"NFL_TEAM_POSITION") is None
    dup_map={
        "G1":{"name_key":"same person","birth_date":"2000-01-01","position_family":"WR"},
        "G2":{"name_key":"same person","birth_date":"2000-01-01","position_family":"WR"},
        "G3":{"name_key":"different person","birth_date":"2000-01-01","position_family":"WR"},
    }
    proposal={"gsis_id":"G1","sleeper_id":"99","rule":"UNIQUE_NAME_POSITION"}
    assert collision_is_duplicate_identity(proposal,{"G2"},dup_map) is True
    assert collision_is_duplicate_identity(proposal,{"G3"},dup_map) is False
    sample=b"gsis_id,sleeper_id\nNA,100\n,101\n00-1,102\n"
    exact,inv,audit=load_crosswalk_bytes(sample)
    assert exact=={"00-1":"102"}
    assert inv=={"102":"00-1"}
    assert audit["rows_with_sleeper_id_but_missing_gsis"]==2
    print("PASS B43 V2R1 evaluator self-test")

def source_preflight(repo: Path, out: Path, session: requests.Session) -> None:
    base=repo/"research/player-role-v2"
    v1e=load_json(base/"player_role_v2_b43_v1_evidence.json")
    v1d=load_json(base/"player_role_v2_b43_v1_scientific_decision.json")
    if v1d["result"]!="SCIENTIFIC_STOP_B43_OWNER_BLIND_IDENTITY_BRIDGE_FEASIBILITY_FAILED":
        raise RuntimeError("B43_V2R1_PARENT_V1_NOT_EXPECTED_STOP")
    prereg=load_json(base/"player_role_v2_b41g_holdout_validation_preregistration.json")
    commit=prereg["frozen_inputs"]["stable_id_crosswalk_commit"]
    if commit!=v1e["source_integrity"]["stable_crosswalk_commit"]:
        raise RuntimeError("B43_V2R1_CROSSWALK_COMMIT_DRIFT_FROM_V1")
    cross_url=f"https://raw.githubusercontent.com/dynastyprocess/data/{commit}/files/db_playerids.csv"
    cross_bytes=source_get(session,cross_url)
    if sha256_bytes(cross_bytes)!=v1e["source_integrity"]["stable_crosswalk_sha256"]:
        raise RuntimeError("B43_V2R1_CROSSWALK_BYTES_DRIFT_FROM_V1")
    cross_rows=list(csv.DictReader(io.StringIO(cross_bytes.decode("utf-8-sig"))))
    if not cross_rows or not {"gsis_id","sleeper_id"}.issubset(cross_rows[0]):
        raise RuntimeError("B43_V2R1_PREFLIGHT_CROSSWALK_SCHEMA")
    snapshot_path=base/"player_role_v2_b43_v1_sleeper_identity_snapshot.csv"
    sleeper_bytes=snapshot_path.read_bytes()
    if sha256_bytes(sleeper_bytes)!=v1e["sleeper_identity_snapshot_sha256"]:
        raise RuntimeError("B43_V2R1_SLEEPER_SNAPSHOT_DRIFT_FROM_V1")
    records=sleeper_records_from_snapshot_csv(sleeper_bytes)
    if len(records)<1000:
        raise RuntimeError(f"B43_V2R1_SLEEPER_SUPPORTED_IDENTITY_ROWS_TOO_SMALL count={len(records)}")
    current=load_current_eligible_and_nfl_identity(repo)
    if len(current)!=v1e["current_owner_blind_population"]["eligible_gsis_rows"]:
        raise RuntimeError("B43_V2R1_CURRENT_ELIGIBLE_POPULATION_DRIFT_FROM_V1")
    out.mkdir(parents=True,exist_ok=True)
    (out/"stable_crosswalk.csv").write_bytes(cross_bytes)
    (out/"sleeper_identity_snapshot.csv").write_bytes(sleeper_bytes)
    write_json(out/"source_preflight.json",{
        "status":"PASS_SOURCE_SCHEMA_ONLY_NO_B43_V2R1_IDENTITY_RESULT_COMPUTED",
        "stable_crosswalk_sha256":sha256_bytes(cross_bytes),
        "sleeper_identity_snapshot_sha256":sha256_bytes(sleeper_bytes),
        "sleeper_supported_identity_row_count":len(records),
        "current_owner_blind_eligible_row_count":len(current),
        "B43_V2R1_identity_mapping_metric_computed":False,
        "league_roster_source_used":False,
        "sleeper_live_endpoint_refetched":False,
    })


def run_evaluation(repo: Path, out: Path, session: requests.Session, source_cache: Path | None = None) -> dict:
    base=repo/"research/player-role-v2"
    b42_decision=load_json(base/"player_role_v2_b42_v4_scientific_decision.json")
    b43v1_decision=load_json(base/"player_role_v2_b43_v1_scientific_decision.json")
    b43v1_evidence=load_json(base/"player_role_v2_b43_v1_evidence.json")
    if b42_decision["result"]!="SCIENTIFIC_STOP_B42_V4_OWNER_BLIND_ROLE_PARITY_FAILED":
        raise RuntimeError("B43_V2R1_PARENT_B42_DECISION_NOT_EXPECTED_STOP")
    if b43v1_decision["result"]!="SCIENTIFIC_STOP_B43_OWNER_BLIND_IDENTITY_BRIDGE_FEASIBILITY_FAILED":
        raise RuntimeError("B43_V2R1_PARENT_V1_DECISION_NOT_EXPECTED_STOP")
    if b42_decision["production_change_authorized"] is not False or b42_decision["production_model_deployed"] is not False:
        raise RuntimeError("B43_V2R1_PARENT_PRODUCTION_FIREWALL_BROKEN")
    prereg=load_json(base/"player_role_v2_b41g_holdout_validation_preregistration.json")
    commit=prereg["frozen_inputs"]["stable_id_crosswalk_commit"]
    cross_url=f"https://raw.githubusercontent.com/dynastyprocess/data/{commit}/files/db_playerids.csv"
    if source_cache is not None:
        cross_bytes=(source_cache/"stable_crosswalk.csv").read_bytes()
        sleeper_bytes=(source_cache/"sleeper_identity_snapshot.csv").read_bytes()
    else:
        cross_bytes=source_get(session,cross_url)
        sleeper_bytes=(base/"player_role_v2_b43_v1_sleeper_identity_snapshot.csv").read_bytes()
    if sha256_bytes(cross_bytes)!=b43v1_evidence["source_integrity"]["stable_crosswalk_sha256"]:
        raise RuntimeError("B43_V2R1_EVAL_CROSSWALK_DRIFT_FROM_V1")
    if sha256_bytes(sleeper_bytes)!=b43v1_evidence["sleeper_identity_snapshot_sha256"]:
        raise RuntimeError("B43_V2R1_EVAL_SLEEPER_SNAPSHOT_DRIFT_FROM_V1")
    stable,stable_inverse,cross_audit=load_crosswalk_bytes(cross_bytes)
    sleeper_records=sleeper_records_from_snapshot_csv(sleeper_bytes)
    sleeper_by_id={x["sleeper_id"]:x for x in sleeper_records}
    sleeper_by_name=defaultdict(list)
    for x in sleeper_records:
        sleeper_by_name[x["name_key"]].append(x)
    current=load_current_eligible_and_nfl_identity(repo)
    if len({x["gsis_id"] for x in current})!=len(current):
        raise RuntimeError("B43_V2R1_DUPLICATE_CURRENT_GSIS_ROWS")
    if len(current)!=b43v1_evidence["current_owner_blind_population"]["eligible_gsis_rows"]:
        raise RuntimeError("B43_V2R1_CURRENT_POPULATION_DRIFT_FROM_V1")

    b41i_identity=load_b41i_identity_map(repo)

    predictions={}
    for row in current:
        pred=candidate_for(row,sleeper_by_name)
        if pred:
            rec,rule=pred
            predictions[row["gsis_id"]]={"sleeper_id":rec["sleeper_id"],"rule":rule}

    # Gating reference trials: DOB_POSITION uses the frozen row unchanged.
    # Lower-priority rules are tested with birth_date blank so they must
    # disambiguate under the information conditions in which they are needed.
    rule_reference={r:{"comparisons":0,"conflicts":0,"correct":0} for r in RULE_ORDER}
    rule_reference_dob_informed={r:{"comparisons":0,"conflicts":0,"correct":0} for r in RULE_ORDER}
    total_reference_predictions=0
    total_reference_conflicts=0
    total_dob_informed_predictions=0
    total_dob_informed_conflicts=0
    for row in current:
        ref_sid=stable.get(row["gsis_id"])
        if not ref_sid or ref_sid not in sleeper_by_id:
            continue
        for rule in RULE_ORDER:
            gating_row=masked_reference_row(row,rule)
            rec=candidate_for_rule(gating_row,sleeper_by_name,rule)
            if rec is not None:
                total_reference_predictions+=1
                rule_reference[rule]["comparisons"]+=1
                if rec["sleeper_id"]==ref_sid:
                    rule_reference[rule]["correct"]+=1
                else:
                    rule_reference[rule]["conflicts"]+=1
                    total_reference_conflicts+=1

            informed_rec=candidate_for_rule(row,sleeper_by_name,rule)
            if informed_rec is not None:
                total_dob_informed_predictions+=1
                rule_reference_dob_informed[rule]["comparisons"]+=1
                if informed_rec["sleeper_id"]==ref_sid:
                    rule_reference_dob_informed[rule]["correct"]+=1
                else:
                    rule_reference_dob_informed[rule]["conflicts"]+=1
                    total_dob_informed_conflicts+=1

    for stats in rule_reference.values():
        stats["precision"]=(stats["correct"]/stats["comparisons"]) if stats["comparisons"] else None
    for stats in rule_reference_dob_informed.values():
        stats["precision"]=(stats["correct"]/stats["comparisons"]) if stats["comparisons"] else None

    reference_eligible_pre_collision={}
    for rule,stats in rule_reference.items():
        reference_eligible_pre_collision[rule]=bool(
            stats["comparisons"]>=RULE_MIN_REFERENCE_COMPARISONS and stats["conflicts"]==0
        )
        stats["reference_eligible_before_collision_evidence"]=reference_eligible_pre_collision[rule]

    # Build a provisional target-population proposal set only from rules that
    # pass their DOB-masked/unchanged known-pair reference trial. Collisions
    # are then treated as additional rule-level evidence before final eligibility.
    provisional_proposals=[]
    for row in current:
        g=row["gsis_id"]
        if g in stable:
            continue
        pred=predictions.get(g)
        if not pred or not reference_eligible_pre_collision.get(pred["rule"],False):
            continue
        provisional_proposals.append({
            "gsis_id":g,
            "sleeper_id":pred["sleeper_id"],
            "rule":pred["rule"],
            "name_key":row["name_key"],
            "model_position":row["model_position"],
            "position_family":row["position_family"],
            "birth_date":row["birth_date"],
            "nfl_team":row["nfl_team"],
        })

    provisional_sid_counts=Counter(x["sleeper_id"] for x in provisional_proposals)
    provisional_gsis_counts=Counter(x["gsis_id"] for x in provisional_proposals)
    provisional_sid_claimants=defaultdict(set)
    for x in provisional_proposals:
        provisional_sid_claimants[x["sleeper_id"]].add(x["gsis_id"])
    collision_rule_conflicts=Counter()
    collision_rule_duplicate_identities=Counter()
    collision_evidence=[]
    for x in provisional_proposals:
        reasons=[]
        if provisional_sid_counts[x["sleeper_id"]]!=1:
            reasons.append("supplemental_sleeper_id_collision")
        if provisional_gsis_counts[x["gsis_id"]]!=1:
            reasons.append("supplemental_gsis_id_collision")
        stable_claimant=stable_inverse.get(x["sleeper_id"])
        if stable_claimant and stable_claimant!=x["gsis_id"]:
            reasons.append("conflicts_with_existing_stable_pair")
        if not reasons:
            continue
        other_claimants=set(provisional_sid_claimants.get(x["sleeper_id"],set()))-{x["gsis_id"]}
        if stable_claimant and stable_claimant!=x["gsis_id"]:
            other_claimants.add(stable_claimant)
        duplicate_identity=collision_is_duplicate_identity(x,other_claimants,b41i_identity)
        classification="DUPLICATE_IDENTITY_NOT_RULE_ERROR" if duplicate_identity else "RULE_CONFLICT"
        if duplicate_identity:
            collision_rule_duplicate_identities[x["rule"]]+=1
        else:
            collision_rule_conflicts[x["rule"]]+=1
        collision_evidence.append({
            "gsis_id":x["gsis_id"],
            "sleeper_id":x["sleeper_id"],
            "rule":x["rule"],
            "reasons":reasons,
            "other_claimant_gsis_ids":sorted(other_claimants),
            "classification":classification,
        })

    rule_eligible={}
    for rule,stats in rule_reference.items():
        stats["collision_evidence_conflicts"]=int(collision_rule_conflicts.get(rule,0))
        stats["collision_duplicate_identity_count"]=int(collision_rule_duplicate_identities.get(rule,0))
        stats["eligibility_conflicts_total"]=int(stats["conflicts"]+stats["collision_evidence_conflicts"])
        rule_eligible[rule]=bool(
            reference_eligible_pre_collision[rule] and stats["collision_evidence_conflicts"]==0
        )
        stats["eligible_for_supplemental_application"]=rule_eligible[rule]

    eligible_reference_comparisons=sum(
        stats["comparisons"] for rule,stats in rule_reference.items() if rule_eligible[rule]
    )
    eligible_reference_conflicts=sum(
        stats["conflicts"] for rule,stats in rule_reference.items() if rule_eligible[rule]
    )
    eligible_collision_conflicts=sum(
        stats["collision_evidence_conflicts"] for rule,stats in rule_reference.items() if rule_eligible[rule]
    )

    # Final proposals are rebuilt after collision evidence can disqualify a rule.
    # There is no fallback to a weaker rule when the priority-winning rule is ineligible.
    proposals=[]
    for row in current:
        g=row["gsis_id"]
        if g in stable:
            continue
        pred=predictions.get(g)
        if not pred or not rule_eligible.get(pred["rule"],False):
            continue
        proposals.append({
            "gsis_id":g,
            "sleeper_id":pred["sleeper_id"],
            "rule":pred["rule"],
            "name_key":row["name_key"],
            "model_position":row["model_position"],
            "position_family":row["position_family"],
            "birth_date":row["birth_date"],
            "nfl_team":row["nfl_team"],
        })

    sid_counts=Counter(x["sleeper_id"] for x in proposals)
    gsis_counts=Counter(x["gsis_id"] for x in proposals)
    sid_claimants=defaultdict(set)
    for x in proposals:
        sid_claimants[x["sleeper_id"]].add(x["gsis_id"])
    final_quarantined_collisions=[]
    accepted=[]
    for x in proposals:
        reasons=[]
        if sid_counts[x["sleeper_id"]]!=1:
            reasons.append("supplemental_sleeper_id_collision")
        if gsis_counts[x["gsis_id"]]!=1:
            reasons.append("supplemental_gsis_id_collision")
        stable_claimant=stable_inverse.get(x["sleeper_id"])
        if stable_claimant and stable_claimant!=x["gsis_id"]:
            reasons.append("conflicts_with_existing_stable_pair")
        if reasons:
            other_claimants=set(sid_claimants.get(x["sleeper_id"],set()))-{x["gsis_id"]}
            if stable_claimant and stable_claimant!=x["gsis_id"]:
                other_claimants.add(stable_claimant)
            if not collision_is_duplicate_identity(x,other_claimants,b41i_identity):
                raise RuntimeError(f"B43_V2R1_FINAL_COLLISION_SURVIVED_RULE_DISQUALIFICATION gsis={x['gsis_id']} sid={x['sleeper_id']} rule={x['rule']}")
            final_quarantined_collisions.append({
                "gsis_id":x["gsis_id"],
                "sleeper_id":x["sleeper_id"],
                "rule":x["rule"],
                "reasons":reasons,
                "other_claimant_gsis_ids":sorted(other_claimants),
                "classification":"DUPLICATE_IDENTITY_NOT_RULE_ERROR",
            })
        else:
            accepted.append(x)
    if len(accepted)+len(final_quarantined_collisions)!=len(proposals):
        raise RuntimeError("B43_V2R1_PROPOSAL_PARTITION_BROKEN")

    # Accepted-bridge one-to-one safety is a structural invariant, not a pass-by-construction gate.
    accepted_sid_counts=Counter(x["sleeper_id"] for x in accepted)
    accepted_gsis_counts=Counter(x["gsis_id"] for x in accepted)
    accepted_conflicts=[]
    for x in accepted:
        reasons=[]
        if accepted_sid_counts[x["sleeper_id"]]!=1:
            reasons.append("accepted_sleeper_id_collision")
        if accepted_gsis_counts[x["gsis_id"]]!=1:
            reasons.append("accepted_gsis_id_collision")
        stable_claimant=stable_inverse.get(x["sleeper_id"])
        if stable_claimant and stable_claimant!=x["gsis_id"]:
            reasons.append("accepted_conflict_with_existing_stable_pair")
        if reasons:
            accepted_conflicts.append({"gsis_id":x["gsis_id"],"sleeper_id":x["sleeper_id"],"reasons":reasons})
    if accepted_conflicts:
        raise RuntimeError(f"B43_V2R1_ACCEPTED_BRIDGE_STRUCTURAL_INVARIANT_BROKEN count={len(accepted_conflicts)}")

    current_count=len(current)
    base_mapped=sum(1 for x in current if x["gsis_id"] in stable)
    accepted_gsis={x["gsis_id"] for x in accepted}
    combined_mapped=sum(1 for x in current if x["gsis_id"] in stable or x["gsis_id"] in accepted_gsis)
    combined_coverage=combined_mapped/current_count if current_count else 0.0
    used_rules=sorted({x["rule"] for x in accepted})
    gates={
        "no_roster_or_owner_context":True,
        "minimum_total_reference_comparisons_across_eligible_rules":eligible_reference_comparisons>=REFERENCE_MIN_COMPARISONS_TOTAL,
        "zero_reference_and_collision_conflicts_among_applied_rules":all(rule_reference[r]["eligibility_conflicts_total"]==0 for r in used_rules),
        "every_applied_rule_independently_validated":all(rule_eligible[r] for r in used_rules),
        "minimum_base_plus_supplemental_current_eligible_coverage":combined_coverage>=MIN_COMBINED_CURRENT_ELIGIBLE_COVERAGE,
        "minimum_supplemental_mapping_count":len(accepted)>=1,
    }
    all_pass=all(gates.values())

    out.mkdir(parents=True, exist_ok=True)
    snapshot_path=out/"player_role_v2_b43_v2r1_sleeper_identity_snapshot.csv"
    snapshot_path.write_bytes(sleeper_bytes)
    if sha256_file(snapshot_path)!=b43v1_evidence["sleeper_identity_snapshot_sha256"]:
        raise RuntimeError("B43_V2R1_OUTPUT_SNAPSHOT_NOT_EXACT_V1_SOURCE")

    bridge_path = out / "player_role_v2_b43_v2r1_identity_bridge.csv"
    with bridge_path.open("w", newline="", encoding="utf-8") as f:
        fields = ["gsis_id","sleeper_id","rule","name_key","model_position","position_family","birth_date","nfl_team"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for x in sorted(accepted, key=lambda z:z["gsis_id"]):
            w.writerow({k:x.get(k,"") for k in fields})

    evidence = {
        "schema_version":3,
        "study_id":"player-role-v2",
        "phase":"B43-v2r1-owner-blind-identity-bridge-remediation-feasibility",
        "result":"PASS_B43_V2R1_OWNER_BLIND_IDENTITY_BRIDGE_FEASIBILITY_FROZEN_FOR_B44_REAUDIT" if all_pass else "SCIENTIFIC_STOP_B43_V2R1_OWNER_BLIND_IDENTITY_BRIDGE_FEASIBILITY_FAILED",
        "all_primary_gates_pass":all_pass,
        "primary_gates":gates,
        "thresholds":{
            "minimum_total_reference_comparisons_across_eligible_rules":REFERENCE_MIN_COMPARISONS_TOTAL,
            "minimum_reference_comparisons_per_applied_rule":RULE_MIN_REFERENCE_COMPARISONS,
            "reference_and_collision_conflicts_allowed_per_eligible_rule":0,
            "minimum_base_plus_supplemental_current_eligible_coverage":MIN_COMBINED_CURRENT_ELIGIBLE_COVERAGE,
        },
        "source_integrity":{
            "stable_crosswalk_commit":commit,
            "stable_crosswalk_sha256":sha256_bytes(cross_bytes),
            "stable_crosswalk_audit":cross_audit,
            "candidate_sleeper_source":"exact_committed_B43_V1_identity_snapshot",
            "sleeper_identity_snapshot_sha256":sha256_bytes(sleeper_bytes),
            "sleeper_supported_identity_row_count":len(sleeper_records),
            "live_sleeper_endpoint_refetched_in_V2R1":False,
            "b42_role_eligibility_sha256":sha256_file(base / "player_role_v2_b42_v4_role_eligibility.csv"),
            "b41i_nfl_identity_snapshot_sha256":sha256_file(base / "frozen_inputs/players_b41i_snapshot.csv"),
        },
        "reference_validation":{
            "gating_design":"DOB_POSITION unchanged; NFL_TEAM_POSITION and UNIQUE_NAME_POSITION evaluated with birth_date masked",
            "total_gating_reference_predictions_all_candidate_rules":total_reference_predictions,
            "total_gating_reference_conflicts_all_candidate_rules":total_reference_conflicts,
            "eligible_rule_reference_comparisons":eligible_reference_comparisons,
            "eligible_rule_reference_conflicts":eligible_reference_conflicts,
            "eligible_rule_collision_evidence_conflicts":eligible_collision_conflicts,
            "rule_stats":rule_reference,
            "dob_informed_descriptive":{
                "total_predictions":total_dob_informed_predictions,
                "total_conflicts":total_dob_informed_conflicts,
                "rule_stats":rule_reference_dob_informed,
                "used_for_eligibility":False,
            },
        },
        "collision_evidence":{
            "classifier_specified_after_B43_V1_observed_two_collisions":True,
            "provisional_collision_count":len(collision_evidence),
            "provisional_collision_details":collision_evidence,
            "rule_conflict_counts":{r:int(collision_rule_conflicts.get(r,0)) for r in RULE_ORDER},
            "duplicate_identity_counts":{r:int(collision_rule_duplicate_identities.get(r,0)) for r in RULE_ORDER},
            "final_quarantined_duplicate_identity_collision_count":len(final_quarantined_collisions),
            "final_quarantined_duplicate_identity_collisions":final_quarantined_collisions,
        },
        "current_owner_blind_population":{
            "eligible_gsis_rows":current_count,
            "base_stable_mapping_count":base_mapped,
            "base_stable_mapping_coverage":base_mapped/current_count if current_count else 0.0,
            "provisional_supplemental_proposal_count":len(provisional_proposals),
            "final_supplemental_proposal_count":len(proposals),
            "supplemental_accepted_count":len(accepted),
            "supplemental_quarantined_duplicate_identity_collision_count":len(final_quarantined_collisions),
            "combined_mapped_count":combined_mapped,
            "combined_mapping_coverage":combined_coverage,
            "unresolved_count":current_count-combined_mapped,
            "accepted_rule_counts":dict(Counter(x["rule"] for x in accepted)),
        },
        "accepted_bridge_structural_invariant":{
            "one_to_one_and_no_stable_pair_conflict":True,
            "conflict_count":len(accepted_conflicts),
            "conflict_details":accepted_conflicts,
            "implemented_as_assertion_not_primary_gate":True,
        },
        "league_roster_source_used":False,
        "owner_identity_used":False,
        "fantasy_roster_partition_used":False,
        "player_specific_exception_count":0,
        "matching_priority_changed_from_B43_V1":False,
        "independent_rule_validation_harness_added":True,
        "lower_priority_reference_trials_birth_date_masked":True,
        "collision_classifier_frozen_before_V2R1_result":True,
        "B43_V2R1_is_post_V1_remediation_not_independent_confirmation":True,
        "model_or_tier_retuning_performed":False,
        "production_change_authorized":False,
        "production_model_deployed":False,
        "B44_owner_blind_reaudit_required_after_pass":True,
        "sleeper_identity_snapshot_sha256":sha256_file(snapshot_path),
        "identity_bridge_sha256":sha256_file(bridge_path),
    }
    write_json(out / "player_role_v2_b43_v2r1_evidence.json", evidence)

    decision = {
        "schema_version":3,
        "study_id":"player-role-v2",
        "phase":"B43-v2r1-scientific-decision",
        "result":evidence["result"],
        "all_primary_gates_pass":all_pass,
        "combined_mapping_coverage":combined_coverage,
        "supplemental_accepted_count":len(accepted),
        "gating_reference_conflicts_among_eligible_rules":eligible_reference_conflicts,
        "collision_evidence_conflicts_among_eligible_rules":eligible_collision_conflicts,
        "provisional_collision_evidence_count":len(collision_evidence),
        "final_quarantined_duplicate_identity_collision_count":len(final_quarantined_collisions),
        "accepted_bridge_structural_conflict_count":len(accepted_conflicts),
        "eligible_rule_status":rule_eligible,
        "eligible_for_B44_owner_blind_reaudit":all_pass,
        "production_change_authorized":False,
        "production_model_deployed":False,
        "next_stage":"If PASS, B44 must use this exact frozen V2R1 bridge and exact V2R1 snapshot without changing matching rules, model weights, tiers, or the original 98%/2pp parity gates, and must be described as a post-remediation acceptance re-audit rather than an independent confirmation. If STOP, preserve evidence and preregister a new identity-source study before any further team audit.",
    }
    write_json(out / "player_role_v2_b43_v2r1_scientific_decision.json", decision)

    report = [
        "# Player Role V2 — B43 V2R1 Owner-Blind Identity Bridge Remediation Feasibility",
        "",
        f"- Decision: **{evidence['result']}**",
        f"- Current owner-blind active eligible GSIS rows: **{current_count}**",
        f"- Base stable mappings: **{base_mapped} ({base_mapped/current_count:.4f})**" if current_count else "- Base stable mappings: **0**",
        f"- Supplemental accepted mappings: **{len(accepted)}**",
        f"- Combined mapping coverage: **{combined_coverage:.4f}**",
        f"- Minimum required combined coverage: **{MIN_COMBINED_CURRENT_ELIGIBLE_COVERAGE:.4f}**",
        f"- Gating reference comparisons across final eligible rules: **{eligible_reference_comparisons}**",
        f"- Gating reference conflicts across final eligible rules: **{eligible_reference_conflicts}**",
        f"- Collision-evidence conflicts across final eligible rules: **{eligible_collision_conflicts}**",
        f"- Provisional collision evidence rows: **{len(collision_evidence)}**",
        f"- Final duplicate-identity collision rows quarantined: **{len(final_quarantined_collisions)}**",
        "- Accepted-bridge structural conflicts: **0 (asserted invariant)**",
        "- League roster source used: **No**",
        "- Owner/fantasy-team context used: **No**",
        "- Player-specific exceptions: **0**",
        "- Model/tier retuning: **No**",
        "- Production authorized: **No**",
        "",
        "## Rule validation",
        "",
        "Lower-priority gate trials mask nflverse birth date. DOB-informed lower-rule trials are descriptive only. Reference-comparison totals are rule-level trials and may overlap the same known rows across rules.",
        "",
        "| Rule | Gating comparisons | Gating conflicts | Gating precision | Collision conflicts | DOB-informed comparisons (descriptive) | DOB-informed conflicts | Final eligible | Accepted supplements |",
        "|---|---:|---:|---:|---:|---:|---:|:---:|---:|",
    ]
    acc_counts=Counter(x["rule"] for x in accepted)
    for rule in RULE_ORDER:
        s=rule_reference[rule]
        d=rule_reference_dob_informed[rule]
        prec="NA" if s["precision"] is None else f"{s['precision']:.6f}"
        report.append(
            f"| {rule} | {s['comparisons']} | {s['conflicts']} | {prec} | {s['collision_evidence_conflicts']} | "
            f"{d['comparisons']} | {d['conflicts']} | {'YES' if rule_eligible[rule] else 'NO'} | {acc_counts.get(rule,0)} |"
        )
    report += [
        "",
        "## Gate results",
        "",
    ]
    for k,v in gates.items():
        report.append(f"- {k}: **{'PASS' if v else 'FAIL'}**")
    report += [
        "",
        "## Interpretation",
        "",
        "B43 V2R1 is a disclosed post-V1 re-analysis on frozen data. It preserves the V1 application matcher and DOB contradiction veto. For gate validation, NFL_TEAM_POSITION and UNIQUE_NAME_POSITION are evaluated with birth date masked so they must stand on name/position/team information without hidden DOB disambiguation. The corresponding DOB-informed results are reported only descriptively.",
        "",
        "Collision evidence is not discarded. A stable-map or supplemental Sleeper-ID collision is classified as duplicate identity only when every other claimant is present in frozen B41I with the same canonical name, same nonmissing birth date, and same position family. Otherwise the collision counts as a conflict against the rule that produced the proposal and makes that rule ineligible. All collision proposals remain quarantined from the bridge.",
        "",
        "The accepted bridge's one-to-one/stable-map safety is enforced as a structural assertion rather than presented as a primary scientific gate. No individual B42- or B43-V1-missed player, Sleeper ID, or exception is hard-coded.",
        "",
        "If B43 V2R1 passes, the exact frozen bridge is eligible only for a separately preregistered B44 owner-blind post-remediation acceptance re-audit under the original B42 98% minimum-team-coverage and 2-percentage-point range gates.",
    ]
    (out / "player_role_v2_b43_v2r1_report.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    return evidence


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["selftest","protocol","source-preflight","evaluate"], required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out")
    ap.add_argument("--source-cache")
    args=ap.parse_args()
    if args.mode=="selftest":
        run_selftest(); return
    repo=Path(args.repo).resolve()
    if args.mode=="protocol":
        if not args.out: raise RuntimeError("--out required")
        write_json(Path(args.out), protocol_payload()); return
    session=requests.Session(); session.headers.update({"User-Agent":"LOG-Trade-Calculator-player-role-v2-b43-v2r1"})
    if not args.out: raise RuntimeError("--out required")
    out=Path(args.out)
    if args.mode=="source-preflight":
        source_preflight(repo,out,session); return
    if args.mode=="evaluate":
        cache=Path(args.source_cache) if args.source_cache else None
        run_evaluation(repo,out,session,cache)
        return

if __name__=="__main__":
    main()

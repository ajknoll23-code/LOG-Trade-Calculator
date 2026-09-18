#!/usr/bin/env python3
"""Validate the deployed IDP V1 production bake against the true pre-V1 live table.

This is the post-deployment counterpart to prepare_idp_v1_bake.py.
It never edits index.html. It verifies that the deployed PROD_MULT_DATA table is
exactly the approved model-delta transport candidate (including exact holds),
then measures the true user-visible old->new Trade Desk value/rank movement
using the immutable pre-V1 baseline.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import snapshot_values

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
INDEX = REPO_ROOT / "index.html"
BASELINE = REPO_ROOT / "model" / "releases" / "idp-v1" / "prod_mult_pre_v1_baseline.json"
CANDIDATE = REPO_ROOT / "model" / "releases" / "idp-v1" / "idp_v1_model_delta_transport_candidate.json"
PATCH = REPO_ROOT / "model" / "releases" / "idp-v1" / "idp_v1_prod_mult_patch.json"
POSITION_LINEAGE_RELEASE = REPO_ROOT / "model" / "releases" / "idp-position-lineage-v1" / "release.json"
FOURFORFOUR_PROVISIONAL_RELEASE = REPO_ROOT / "model" / "releases" / "fourforfour-idp-provisional-10pct-v1" / "release.json"
FOURFORFOUR_OFFENSE_RELEASE = REPO_ROOT / "model" / "releases" / "fourforfour-offense-provisional-10pct-v1" / "release.json"
FOURFORFOUR_LIVE_ROLE_R1_RELEASE = REPO_ROOT / "model" / "releases" / "fourforfour-offense-live-role-r1-v1" / "release.json"
FOURFORFOUR_CONFIDENCE_C2_RELEASE = REPO_ROOT / "model" / "releases" / "fourforfour-offense-confidence-c2-v1" / "release.json"
JSON_OUT = SCRIPT_DIR / "idp_v1_final_deployment_validation.json"
REPORT = SCRIPT_DIR / "idp_v1_final_deployment_validation.md"
IDP_POSITIONS = ("LB", "DL", "DB")
OFFENSE_POSITIONS = ("QB", "RB", "WR", "TE")
ANCHORS = (
    "bradley chubb", "aidan hutchinson", "myles garrett", "fred warner",
    "roquan smith", "ej speed", "isaiah mcduffie", "christian izien",
)


def percentile(values, q):
    vals = sorted(values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    x = (len(vals) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    if lo == hi:
        return vals[lo]
    return vals[lo] + (vals[hi] - vals[lo]) * (x - lo)


def summary(values):
    vals = [v for v in values if v is not None and math.isfinite(v)]
    if not vals:
        return {"n": 0, "median": None, "p90": None, "p95": None, "min": None, "max": None}
    return {
        "n": len(vals),
        "median": statistics.median(vals),
        "p90": percentile(vals, 0.90),
        "p95": percentile(vals, 0.95),
        "min": min(vals),
        "max": max(vals),
    }


def rank_map(values):
    by_pos = defaultdict(list)
    for key, row in values.items():
        if row["pos"] in IDP_POSITIONS:
            by_pos[row["pos"]].append((row["value"], key))
    ranks = {}
    for pos, arr in by_pos.items():
        arr.sort(key=lambda x: (-x[0], x[1]))
        for i, (_, key) in enumerate(arr, 1):
            ranks[key] = i
    return ranks


def fmt_value(v):
    s = f"{float(v):.4f}".rstrip("0").rstrip(".")
    return float(s if "." in s else s + ".0")


def canonical_prod_mult_hash(values):
    payload = json.dumps(
        {k: float(values[k]) for k in sorted(values)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_deployment():
    cfg = snapshot_values.load_from_html(INDEX)
    baseline_doc = json.load(open(BASELINE, encoding="utf-8"))
    baseline = {k: float(v) for k, v in baseline_doc["values"].items()}
    candidate = json.load(open(CANDIDATE, encoding="utf-8"))
    patch = json.load(open(PATCH, encoding="utf-8"))
    current = {k: float(v) for k, v in cfg["prod_mult"].items()}

    # Layer-aware deployed-table integrity.
    #
    # The immutable IDP V1 release remains the historical base release. A later
    # approved position-lineage release may intentionally replace a narrow set
    # of those deployed raw multipliers. Validate V1 against its own immutable
    # baseline/candidate first, then validate any successor overlay on top.
    if set(current) != set(baseline):
        missing = sorted(set(baseline) - set(current))
        extra = sorted(set(current) - set(baseline))
        raise AssertionError(
            "PROD_MULT key set changed across deployed IDP stack; "
            f"missing={missing[:10]} extra={extra[:10]}"
        )

    patch_by_key = {e["key"]: e for e in patch["entries"]}
    expected_changed = set(patch_by_key)

    v1_expected = dict(baseline)
    for key, e in patch_by_key.items():
        if abs(float(e["old"]) - baseline[key]) > 1e-12:
            raise AssertionError(
                f"patch old value no longer matches immutable baseline: {key}"
            )
        v1_expected[key] = fmt_value(e["new"])

    v1_changed = {
        k for k in baseline
        if abs(v1_expected[k] - baseline[k]) > 1e-12
    }
    if v1_changed != expected_changed:
        missing = sorted(expected_changed - v1_changed)
        unexpected = sorted(v1_changed - expected_changed)
        raise AssertionError(
            "reconstructed V1 changed-key set != approved patch; "
            f"missing={missing[:10]} unexpected={unexpected[:10]}"
        )

    for key, row in candidate["players"].items():
        if key not in v1_expected:
            raise AssertionError(
                f"candidate key missing from reconstructed V1 PROD_MULT: {key}"
            )
        expected = fmt_value(row["candidate_prod_mult"])
        if abs(v1_expected[key] - expected) > 1e-12:
            raise AssertionError(
                f"reconstructed V1 candidate mismatch {key}: "
                f"expected {expected}, got {v1_expected[key]}"
            )

    for key, e in patch_by_key.items():
        if abs(fmt_value(e["new"]) - v1_expected[key]) > 1e-12:
            raise AssertionError(
                f"patch new value no longer matches reconstructed V1 value: {key}"
            )

    lineage_release = None
    lineage_candidates = {}
    lineage_holds = {}
    expected_current = dict(v1_expected)

    if POSITION_LINEAGE_RELEASE.exists():
        lineage_release = json.load(
            open(POSITION_LINEAGE_RELEASE, encoding="utf-8")
        )
        if lineage_release.get("release_id") != "idp-position-lineage-v1":
            raise AssertionError(
                "unexpected Position Lineage release_id: "
                f"{lineage_release.get('release_id')}"
            )

        candidate_rows = lineage_release.get("candidate_overrides") or []
        hold_rows = lineage_release.get("held_rows") or []
        if len(candidate_rows) != 24 or len(hold_rows) != 3:
            raise AssertionError(
                "Position Lineage release count mismatch: "
                f"candidates={len(candidate_rows)} holds={len(hold_rows)}"
            )

        lineage_candidates = {row["key"]: row for row in candidate_rows}
        lineage_holds = {row["key"]: row for row in hold_rows}
        if len(lineage_candidates) != len(candidate_rows):
            raise AssertionError("duplicate Position Lineage candidate key")
        if len(lineage_holds) != len(hold_rows):
            raise AssertionError("duplicate Position Lineage hold key")
        if set(lineage_candidates) & set(lineage_holds):
            raise AssertionError("Position Lineage candidate/hold key sets overlap")

        for key, row in lineage_candidates.items():
            if key not in v1_expected:
                raise AssertionError(
                    f"Position Lineage candidate missing from V1 table: {key}"
                )
            base = float(row["deployed_raw_prod_mult"])
            if abs(v1_expected[key] - base) > 1e-12:
                raise AssertionError(
                    f"Position Lineage base mismatch {key}: "
                    f"release={base}, reconstructed_v1={v1_expected[key]}"
                )
            expected_current[key] = fmt_value(row["candidate_raw_prod_mult"])

        for key, row in lineage_holds.items():
            if key not in v1_expected:
                raise AssertionError(
                    f"Position Lineage hold missing from V1 table: {key}"
                )
            base = float(row["deployed_raw_prod_mult"])
            if abs(v1_expected[key] - base) > 1e-12:
                raise AssertionError(
                    f"Position Lineage hold base mismatch {key}: "
                    f"release={base}, reconstructed_v1={v1_expected[key]}"
                )

    provisional_release = None
    offense_release = None
    live_role_r1_release = None
    confidence_c2_release = None
    if FOURFORFOUR_PROVISIONAL_RELEASE.exists():
        provisional_release = json.load(
            open(FOURFORFOUR_PROVISIONAL_RELEASE, encoding="utf-8")
        )
        if provisional_release.get("release_id") != "fourforfour-idp-provisional-10pct-v1":
            raise AssertionError(
                "unexpected provisional 4for4 release_id: "
                f"{provisional_release.get('release_id')}"
            )
        expected_policy_fp = (
            "8cf918c3c1d254ebf84dbff3a755375ceae9b7afe095233a921f7579180863d7"
        )
        if provisional_release.get("policy_fingerprint_sha256") != expected_policy_fp:
            raise AssertionError("provisional 4for4 policy fingerprint drifted")
        if provisional_release.get("outcome_data_used") is not False:
            raise AssertionError("provisional 4for4 release used outcome data")
        if provisional_release.get("week2_realized_outcomes_read") is not False:
            raise AssertionError("provisional 4for4 release read Week 2 outcomes")

        reconstructed_base_hash = canonical_prod_mult_hash(expected_current)
        if (
            provisional_release.get("base_prod_mult_canonical_sha256")
            != reconstructed_base_hash
        ):
            raise AssertionError(
                "provisional 4for4 base hash does not match reconstructed V1 + Position Lineage stack"
            )

        idp_deployed_hash = provisional_release.get(
            "deployed_prod_mult_canonical_sha256"
        )
        if int(provisional_release.get("prod_mult_entry_count", -1)) != len(current):
            raise AssertionError("provisional 4for4 PROD_MULT entry count drifted")
        if int(provisional_release.get("raw_prod_mult_changed_count", 0)) <= 0:
            raise AssertionError("provisional 4for4 release has no recorded production changes")

        live_hash = canonical_prod_mult_hash(current)
        if FOURFORFOUR_OFFENSE_RELEASE.exists():
            offense_release = json.load(
                open(FOURFORFOUR_OFFENSE_RELEASE, encoding="utf-8")
            )
            if (
                offense_release.get("release_id")
                != "fourforfour-offense-provisional-10pct-v1"
            ):
                raise AssertionError(
                    "unexpected offense 4for4 release_id: "
                    f"{offense_release.get('release_id')}"
                )
            if offense_release.get("realized_outcomes_used") is not False:
                raise AssertionError("offense 4for4 successor used realized outcomes")
            if offense_release.get("private_row_level_4for4_output_persisted") is not False:
                raise AssertionError("offense 4for4 successor persisted private row-level data")
            if abs(float((offense_release.get("policy") or {}).get("fourforfour_weight", -1)) - 0.10) > 1e-12:
                raise AssertionError("offense 4for4 successor weight drifted")
            if (
                offense_release.get("green_shadow_aggregate_contract_sha256")
                != "17396075883e56f4eff39d574fd0c2011e742a787b91404b37b7470133b143a5"
            ):
                raise AssertionError("offense green-shadow aggregate fingerprint drifted")
            if offense_release.get("base_prod_mult_canonical_sha256") != idp_deployed_hash:
                raise AssertionError(
                    "offense successor base hash does not chain from deployed IDP successor"
                )
            offense_deployed_hash = offense_release.get(
                "deployed_prod_mult_canonical_sha256"
            )
            if int(offense_release.get("prod_mult_entry_count", -1)) != len(current):
                raise AssertionError("offense successor PROD_MULT entry count drifted")
            if int(offense_release.get("eligible_count", -1)) != 274:
                raise AssertionError("offense successor eligible count drifted")
            if int(offense_release.get("raw_prod_mult_changed_count", -1)) != 237:
                raise AssertionError("offense successor changed count drifted")
            if set(offense_release.get("scope") or []) != set(OFFENSE_POSITIONS):
                raise AssertionError("offense successor scope drifted")

            if FOURFORFOUR_LIVE_ROLE_R1_RELEASE.exists():
                live_role_r1_release = json.load(
                    open(FOURFORFOUR_LIVE_ROLE_R1_RELEASE, encoding="utf-8")
                )
                if (
                    live_role_r1_release.get("release_id")
                    != "fourforfour-offense-live-role-r1-v1"
                ):
                    raise AssertionError(
                        "unexpected 4for4 offense live-role R1 release_id"
                    )
                if (
                    live_role_r1_release.get("private_row_level_4for4_output_persisted")
                    is not False
                ):
                    raise AssertionError("live-role R1 persisted private 4for4 rows")
                if (
                    live_role_r1_release.get("row_level_snap_output_persisted")
                    is not False
                ):
                    raise AssertionError("live-role R1 persisted row-level snap data")
                if (
                    live_role_r1_release.get("frozen_opportunity_v2_modified")
                    is not False
                ):
                    raise AssertionError("live-role R1 modified frozen Opportunity V2")
                if (
                    live_role_r1_release.get("base_prod_mult_canonical_sha256")
                    != offense_deployed_hash
                ):
                    raise AssertionError(
                        "live-role R1 base does not chain from offense 10% successor"
                    )
                r1_deployed_hash = live_role_r1_release.get(
                    "deployed_prod_mult_canonical_sha256"
                )
                if int(live_role_r1_release.get("signal_count", -1)) != 22:
                    raise AssertionError("live-role R1 signal count drifted")
                if int(live_role_r1_release.get("raw_prod_mult_changed_count", -1)) != 22:
                    raise AssertionError("live-role R1 changed count drifted")
                if set(live_role_r1_release.get("scope") or []) != set(OFFENSE_POSITIONS):
                    raise AssertionError("live-role R1 scope drifted")
                policy = live_role_r1_release.get("policy") or {}
                if abs(float(policy.get("raw_prod_mult_cap", -1)) - 0.005) > 1e-12:
                    raise AssertionError("live-role R1 cap drifted")

                if FOURFORFOUR_CONFIDENCE_C2_RELEASE.exists():
                    confidence_c2_release = json.load(
                        open(FOURFORFOUR_CONFIDENCE_C2_RELEASE, encoding="utf-8")
                    )
                    if confidence_c2_release.get("release_id") != "fourforfour-offense-confidence-c2-v1":
                        raise AssertionError("unexpected confidence C2 release_id")
                    if confidence_c2_release.get("base_prod_mult_canonical_sha256") != r1_deployed_hash:
                        raise AssertionError("confidence C2 base hash mismatch")
                    if confidence_c2_release.get("deployed_prod_mult_canonical_sha256") != live_hash:
                        raise AssertionError("live PROD_MULT does not match confidence C2 hash")
                    if confidence_c2_release.get("private_row_level_4for4_output_persisted") is not False:
                        raise AssertionError("confidence C2 persisted private rows")
                    if confidence_c2_release.get("confidence_is_standalone_value_signal") is not False:
                        raise AssertionError("confidence C2 became standalone value signal")
                    if int(confidence_c2_release.get("eligible_three_source", -1)) != 227:
                        raise AssertionError("confidence C2 eligible count drifted")
                    if int(confidence_c2_release.get("low_confidence_player_count", -1)) != 17:
                        raise AssertionError("confidence C2 low count drifted")
                    if int(confidence_c2_release.get("raw_prod_mult_changed_count", -1)) != 14:
                        raise AssertionError("confidence C2 changed count drifted")
                    cpolicy = confidence_c2_release.get("policy") or {}
                    if abs(float(cpolicy.get("nominal_forward_weight", -1)) - 0.55) > 1e-12:
                        raise AssertionError("confidence C2 nominal weight drifted")
                    if abs(float(cpolicy.get("low_confidence_forward_weight", -1)) - 0.50) > 1e-12:
                        raise AssertionError("confidence C2 low weight drifted")
                    if abs(float(cpolicy.get("transport_strength", -1)) - 0.25) > 1e-12:
                        raise AssertionError("confidence C2 transport drifted")
                    if abs(float(cpolicy.get("raw_prod_mult_delta_cap", -1)) - 0.005) > 1e-12:
                        raise AssertionError("confidence C2 cap drifted")
                elif r1_deployed_hash != live_hash:
                    raise AssertionError(
                        "live PROD_MULT does not match live-role R1 successor hash"
                    )
            elif offense_deployed_hash != live_hash:
                raise AssertionError(
                    "live PROD_MULT does not match frozen offense successor hash"
                )
        elif idp_deployed_hash != live_hash:
            raise AssertionError(
                "live PROD_MULT does not match frozen provisional 4for4 IDP successor hash"
            )
    else:
        current_mismatches = []
        for key in baseline:
            if abs(current[key] - expected_current[key]) > 1e-12:
                current_mismatches.append((key, expected_current[key], current[key]))
        if current_mismatches:
            raise AssertionError(
                "live PROD_MULT does not match V1 + approved successor stack: "
                f"{current_mismatches[:10]}"
            )

    lineage_changed = {
        key for key in v1_expected
        if abs(expected_current[key] - v1_expected[key]) > 1e-12
    }
    if lineage_release is not None and lineage_changed != set(lineage_candidates):
        missing = sorted(set(lineage_candidates) - lineage_changed)
        unexpected = sorted(lineage_changed - set(lineage_candidates))
        raise AssertionError(
            "Position Lineage changed-key set mismatch: "
            f"missing={missing[:10]} unexpected={unexpected[:10]}"
        )

    actual_changed = v1_changed
    current_stack_changed = {
        k for k in baseline
        if abs(current[k] - baseline[k]) > 1e-12
    }

    # Preserve historical V1 movement independently of successor layers.
    old_cfg = dict(cfg)
    old_cfg["prod_mult"] = dict(baseline)
    v1_cfg = dict(cfg)
    v1_cfg["prod_mult"] = dict(v1_expected)

    old_values = snapshot_values.compute_all_values(old_cfg)
    new_values = snapshot_values.compute_all_values(v1_cfg)
    current_values = snapshot_values.compute_all_values(cfg)
    old_ranks, new_ranks = rank_map(old_values), rank_map(new_values)

    # After the approved offense successor, QB/RB/WR/TE may move.
    # K and all other non-IDP positions remain strict exact holds.
    non_idp_diffs = []
    offense_successor_value_changes = 0
    for key, old in old_values.items():
        if old["pos"] in IDP_POSITIONS:
            continue
        if current_values[key]["value"] == old["value"]:
            continue
        if offense_release is not None and old["pos"] in OFFENSE_POSITIONS:
            offense_successor_value_changes += 1
            continue
        non_idp_diffs.append(
            (key, old["value"], current_values[key]["value"])
        )
    if non_idp_diffs:
        raise AssertionError(
            f"unexpected non-IDP final values changed outside approved offense successor: "
            f"{non_idp_diffs[:10]}"
        )

    rows = []
    final_changes_by_pos = defaultdict(list)
    raw_changes_by_pos = defaultdict(list)
    for key, old in old_values.items():
        if old["pos"] not in IDP_POSITIONS:
            continue
        new = new_values[key]
        pct = (new["value"] / old["value"] - 1) * 100 if old["value"] else None
        raw_old = baseline.get(key)
        raw_new = v1_expected.get(key)
        raw_pct = ((raw_new / raw_old - 1) * 100) if raw_old and raw_new is not None else None
        cand = candidate["players"].get(key, {})
        row = {
            "key": key,
            "pos": old["pos"],
            "old_value": old["value"],
            "new_value": new["value"],
            "value_pct_change": pct,
            "old_rank": old_ranks.get(key),
            "new_rank": new_ranks.get(key),
            "rank_change": (new_ranks[key] - old_ranks[key]) if key in old_ranks and key in new_ranks else None,
            "old_effective_prod_mult": old["prod_mult"],
            "new_effective_prod_mult": new["prod_mult"],
            "old_raw_prod_mult": raw_old,
            "new_raw_prod_mult": raw_new,
            "raw_prod_mult_pct_change": raw_pct,
            "source_cohort": cand.get("v1_source_cohort"),
            "update_status": cand.get("update_status"),
            "legacy_model_position": cand.get("legacy_model_position"),
            "current_valuation_position": cand.get("current_valuation_position"),
        }
        rows.append(row)
        final_changes_by_pos[old["pos"]].append(pct)
        if raw_pct is not None:
            raw_changes_by_pos[old["pos"]].append(raw_pct)

    # Rank stability.
    rank_stability = {}
    for pos in IDP_POSITIONS:
        rel = [r for r in rows if r["pos"] == pos and (r["old_rank"] <= 36 or r["new_rank"] <= 36)]
        rank_stability[pos] = {
            "top24_movers_ge5": sum(1 for r in rel if (r["old_rank"] <= 24 or r["new_rank"] <= 24) and abs(r["rank_change"]) >= 5),
            "top36_movers_ge5": sum(1 for r in rel if abs(r["rank_change"]) >= 5),
            "max_abs_rank_move_top36": max([abs(r["rank_change"]) for r in rel], default=0),
        }

    # Source-cohort behavior on candidate keys, measured in raw prod_mult and
    # final Trade Desk values where the player exists in PLAYER_DB.
    by_cohort_raw = defaultdict(list)
    by_cohort_final = defaultdict(list)
    for key, cand in candidate["players"].items():
        cohort = cand["v1_source_cohort"]
        old_raw, new_raw = baseline[key], v1_expected[key]
        by_cohort_raw[cohort].append((new_raw / old_raw - 1) * 100 if old_raw else None)
        match = next((r for r in rows if r["key"] == key), None)
        if match:
            by_cohort_final[cohort].append(match["value_pct_change"])

    clamp = {
        "pre_v1_raw_candidate_floor_0_15": sum(1 for k in candidate["players"] if abs(baseline[k] - 0.15) < 1e-12),
        "pre_v1_raw_candidate_ceiling_1_55": sum(1 for k in candidate["players"] if abs(baseline[k] - 1.55) < 1e-12),
        "deployed_raw_candidate_floor_0_15": sum(1 for k in candidate["players"] if abs(v1_expected[k] - 0.15) < 1e-12),
        "deployed_raw_candidate_ceiling_1_55": sum(1 for k in candidate["players"] if abs(v1_expected[k] - 1.55) < 1e-12),
    }

    row_map = {r["key"]: r for r in rows}
    anchor_rows = {}
    for key in ANCHORS:
        cand = candidate["players"].get(key)
        if not cand:
            anchor_rows[key] = None
            continue
        final_row = row_map.get(key)
        anchor_rows[key] = {
            "key": key,
            "pos": final_row["pos"] if final_row else cand.get("current_valuation_position"),
            "legacy_model_position": cand.get("legacy_model_position"),
            "current_valuation_position": cand.get("current_valuation_position"),
            "old_raw_prod_mult": baseline.get(key),
            "new_raw_prod_mult": v1_expected.get(key),
            "raw_prod_mult_pct_change": (
                (v1_expected[key] / baseline[key] - 1) * 100
            ) if baseline.get(key) else None,
            "source_cohort": cand.get("v1_source_cohort"),
            "update_status": cand.get("update_status"),
            "old_value": final_row.get("old_value") if final_row else None,
            "new_value": final_row.get("new_value") if final_row else None,
            "value_pct_change": final_row.get("value_pct_change") if final_row else None,
            "rank_change": final_row.get("rank_change") if final_row else None,
        }

    result = {
        "status": "PASS",
        "deployment_method": candidate["method"],
        "pre_v1_prod_mult_entry_count": len(baseline),
        "deployed_prod_mult_entry_count": len(current),
        "approved_changed_entry_count": len(expected_changed),
        "actual_changed_entry_count": len(actual_changed),
        "current_stack_changed_entry_count": len(current_stack_changed),
        "position_lineage_overlay_active": lineage_release is not None,
        "provisional_4for4_overlay_active": provisional_release is not None,
        "provisional_4for4_policy_fingerprint_sha256": (
            provisional_release.get("policy_fingerprint_sha256")
            if provisional_release is not None else None
        ),
        "provisional_4for4_changed_entry_count": (
            int(provisional_release.get("raw_prod_mult_changed_count", 0))
            if provisional_release is not None else 0
        ),
        "provisional_4for4_offense_overlay_active": offense_release is not None,
        "provisional_4for4_offense_changed_entry_count": (
            int(offense_release.get("raw_prod_mult_changed_count", 0))
            if offense_release is not None else 0
        ),
        "provisional_4for4_offense_eligible_count": (
            int(offense_release.get("eligible_count", 0))
            if offense_release is not None else 0
        ),
        "provisional_4for4_offense_green_shadow_sha256": (
            offense_release.get("green_shadow_aggregate_contract_sha256")
            if offense_release is not None else None
        ),
        "fourforfour_live_role_r1_active": live_role_r1_release is not None,
        "fourforfour_live_role_r1_signal_count": (
            int(live_role_r1_release.get("signal_count", 0))
            if live_role_r1_release is not None else 0
        ),
        "fourforfour_live_role_r1_changed_entry_count": (
            int(live_role_r1_release.get("raw_prod_mult_changed_count", 0))
            if live_role_r1_release is not None else 0
        ),
        "offense_successor_final_value_changes": offense_successor_value_changes,
        "position_lineage_overlay_candidate_count": len(lineage_candidates),
        "position_lineage_overlay_hold_count": len(lineage_holds),
        "position_lineage_overlay_changed_entry_count": len(lineage_changed),
        "candidate_player_count": len(candidate["players"]),
        "exact_hold_candidate_count": len(candidate["players"]) - len(expected_changed),
        "non_idp_final_value_changes": len(non_idp_diffs),
        "internal_old_model_baseline_by_position": candidate["old_model_baseline_by_position"],
        "internal_new_model_baseline_by_position": candidate["new_model_baseline_by_position"],
        "internal_baseline_pct_change": {
            p: (candidate["new_model_baseline_by_position"][p] / candidate["old_model_baseline_by_position"][p] - 1) * 100
            for p in IDP_POSITIONS
        },
        "raw_prod_mult_change_by_current_position": {p: summary(raw_changes_by_pos[p]) for p in IDP_POSITIONS},
        "final_value_change_by_position": {p: summary(final_changes_by_pos[p]) for p in IDP_POSITIONS},
        "rank_stability": rank_stability,
        "source_cohort_counts": Counter(r["v1_source_cohort"] for r in candidate["players"].values()),
        "update_status_counts": Counter(r["update_status"] for r in candidate["players"].values()),
        "source_cohort_raw_prod_mult_change": {k: summary(v) for k, v in sorted(by_cohort_raw.items())},
        "source_cohort_final_value_change": {k: summary(v) for k, v in sorted(by_cohort_final.items())},
        "clamp_occupancy": clamp,
        "anchors": anchor_rows,
        "largest_final_value_movers": sorted(rows, key=lambda r: abs(r["value_pct_change"] or 0), reverse=True)[:30],
        "largest_raw_prod_mult_movers": sorted([r for r in rows if r["raw_prod_mult_pct_change"] is not None], key=lambda r: abs(r["raw_prod_mult_pct_change"]), reverse=True)[:30],
        "position_lineage_mismatch_count": sum(1 for r in candidate["players"].values() if r.get("legacy_model_position") != r.get("current_valuation_position")),
    }
    # Counter is JSON serializable only after conversion.
    result["source_cohort_counts"] = dict(result["source_cohort_counts"])
    result["update_status_counts"] = dict(result["update_status_counts"])
    return result


def _fmt_pct(v):
    return "n/a" if v is None else f"{v:+.1f}%"


def build_report(result):
    lines = [
        "# IDP V1 Final Production Deployment Validation",
        "",
        "## Verdict",
        "",
        "**PASS — the live `index.html` PROD_MULT table exactly matches the approved IDP V1 release and all recognized successor layers.**",
        "",
        f"- Deployment method: `{result['deployment_method']}`",
        f"- Immutable pre-V1 PROD_MULT entries: **{result['pre_v1_prod_mult_entry_count']}**",
        f"- Candidate IDP keys: **{result['candidate_player_count']}**",
        f"- Approved/deployed raw PROD_MULT changes: **{result['actual_changed_entry_count']}**",
        f"- Exact candidate holds: **{result['exact_hold_candidate_count']}**",
        f"- Floor-rescue discontinuity guards: **{result['update_status_counts'].get('exact_hold_floor_rescue_discontinuity_guard', 0)}**",
        f"- Non-IDP final-value changes: **{result['non_idp_final_value_changes']}**",
        f"- Frozen V1 legacy/current position mismatches: **{result['position_lineage_mismatch_count']}**",
        f"- Position Lineage V1 successor active: **{result['position_lineage_overlay_active']}**",
        f"- Provisional 4for4 10% successor active: **{result['provisional_4for4_overlay_active']}**",
        f"- Provisional 4for4 changed PROD_MULT entries: **{result['provisional_4for4_changed_entry_count']}**",
        f"- Provisional 4for4 offense 10% successor active: **{result['provisional_4for4_offense_overlay_active']}**",
        f"- Provisional 4for4 offense eligible players: **{result['provisional_4for4_offense_eligible_count']}**",
        f"- Provisional 4for4 offense changed PROD_MULT entries: **{result['provisional_4for4_offense_changed_entry_count']}**",
        f"- Provisional 4for4 offense final-value changes: **{result['offense_successor_final_value_changes']}**",
        f"- 4for4 offense live-role R1 active: **{result['fourforfour_live_role_r1_active']}**",
        f"- 4for4 offense live-role R1 signals: **{result['fourforfour_live_role_r1_signal_count']}**",
        f"- 4for4 offense live-role R1 changed PROD_MULT entries: **{result['fourforfour_live_role_r1_changed_entry_count']}**",
        f"- Position Lineage V1 approved overrides: **{result['position_lineage_overlay_candidate_count']}**",
        f"- Position Lineage V1 explicit holds: **{result['position_lineage_overlay_hold_count']}**",
        f"- Current stacked changed PROD_MULT entries vs pre-V1: **{result['current_stack_changed_entry_count']}**",
        "",
        "## Internal V1 replacement-baseline movement",
        "",
    ]
    for pos in IDP_POSITIONS:
        lines.append(f"- {pos}: **{result['internal_baseline_pct_change'][pos]:+.1f}%**")

    lines += ["", "## True live old → deployed raw PROD_MULT movement", "", "| Pos | N | Median | P90 | P95 | Min | Max |", "|---|---:|---:|---:|---:|---:|---:|"]
    for pos in IDP_POSITIONS:
        s = result["raw_prod_mult_change_by_current_position"][pos]
        lines.append(f"| {pos} | {s['n']} | {_fmt_pct(s['median'])} | {_fmt_pct(s['p90'])} | {_fmt_pct(s['p95'])} | {_fmt_pct(s['min'])} | {_fmt_pct(s['max'])} |")

    lines += ["", "## True live old → deployed final Trade Desk value movement", "", "| Pos | N | Median | P90 | P95 | Min | Max |", "|---|---:|---:|---:|---:|---:|---:|"]
    for pos in IDP_POSITIONS:
        s = result["final_value_change_by_position"][pos]
        lines.append(f"| {pos} | {s['n']} | {_fmt_pct(s['median'])} | {_fmt_pct(s['p90'])} | {_fmt_pct(s['p95'])} | {_fmt_pct(s['min'])} | {_fmt_pct(s['max'])} |")

    lines += ["", "## Rank stability", "", "| Pos | Top-24 movers >=5 | Top-36 movers >=5 | Max abs top-36 move |", "|---|---:|---:|---:|"]
    for pos in IDP_POSITIONS:
        s = result["rank_stability"][pos]
        lines.append(f"| {pos} | {s['top24_movers_ge5']} | {s['top36_movers_ge5']} | {s['max_abs_rank_move_top36']} |")

    lines += ["", "## Source-cohort behavior", "", "| Cohort | N candidate | Raw PROD_MULT median | Raw P95 | Final-value median* | Final P95* |", "|---|---:|---:|---:|---:|---:|"]
    for cohort, n in sorted(result["source_cohort_counts"].items()):
        raw = result["source_cohort_raw_prod_mult_change"][cohort]
        fin = result["source_cohort_final_value_change"].get(cohort, {"median": None, "p95": None})
        lines.append(f"| {cohort} | {n} | {_fmt_pct(raw['median'])} | {_fmt_pct(raw['p95'])} | {_fmt_pct(fin['median'])} | {_fmt_pct(fin['p95'])} |")
    lines.append("")
    lines.append("* Final-value cohort summaries include only candidate keys that are present in current `PLAYER_DB`.")

    c = result["clamp_occupancy"]
    lines += [
        "", "## Raw clamp occupancy among the 404 candidate IDPs", "",
        f"- Pre-V1 floor 0.15: **{c['pre_v1_raw_candidate_floor_0_15']}**",
        f"- Deployed floor 0.15: **{c['deployed_raw_candidate_floor_0_15']}**",
        f"- Pre-V1 ceiling 1.55: **{c['pre_v1_raw_candidate_ceiling_1_55']}**",
        f"- Deployed ceiling 1.55: **{c['deployed_raw_candidate_ceiling_1_55']}**",
        "",
        "## Known anchors", "",
        "| Player | Pos | Old raw | New raw | Raw change | Old value | New value | Final change | Rank move | Cohort |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key in ANCHORS:
        r = result["anchors"].get(key)
        if not r:
            continue
        old_val = "—" if r['old_value'] is None else str(r['old_value'])
        new_val = "—" if r['new_value'] is None else str(r['new_value'])
        final_change = "—" if r['value_pct_change'] is None else _fmt_pct(r['value_pct_change'])
        rank_move = "—" if r['rank_change'] is None else f"{r['rank_change']:+d}"
        lines.append(
            f"| {key} | {r['pos'] or ''} | {r['old_raw_prod_mult']:.4f} | {r['new_raw_prod_mult']:.4f} | "
            f"{_fmt_pct(r['raw_prod_mult_pct_change'])} | {old_val} | {new_val} | "
            f"{final_change} | {rank_move} | {r.get('source_cohort') or ''} |"
        )

    lines += ["", "## Largest final-value movers", "", "| Player | Pos | Old | New | Change | Rank move | Cohort/status |", "|---|---|---:|---:|---:|---:|---|"]
    for r in result["largest_final_value_movers"][:20]:
        label = "/".join(x for x in (r.get("source_cohort"), r.get("update_status")) if x)
        lines.append(f"| {r['key']} | {r['pos']} | {r['old_value']} | {r['new_value']} | {_fmt_pct(r['value_pct_change'])} | {r['rank_change']:+d} | {label} |")

    lines += [
        "", "## Release attribution", "",
        "- The OLD side is reconstructed from the immutable pre-V1 `PROD_MULT_DATA` snapshot.",
        "- The NEW side is the actual deployed `index.html`.",
        "- All other valuation constants, age curves, role-floor behavior, and position weights are held identical.",
        "- Offense values are unchanged through IDP V1/Position Lineage/IDP 4for4; when the approved 4for4 offense successor is active, its full-table hash and aggregate release contract are validated separately.",
        "- The 46 legacy/current IDP position mismatches remain explicitly isolated from this V1 projection release.",
    ]
    return "\n".join(lines) + "\n"


def main():
    result = validate_deployment()
    JSON_OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(build_report(result), encoding="utf-8")
    print(f"PASS final IDP V1 deployment validation: {result['actual_changed_entry_count']} approved PROD_MULT changes deployed")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()

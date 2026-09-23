#!/usr/bin/env python3
"""Exact-live prospective/OOS monitor for Package Adjustment V1.7.

V1.7 preserves all controlled-live size-2 behavior from V1.6 and adds the
human-approved V6 C2 overlay for exact one-player-vs-three-player, player-only
trades inside the frozen prospective catalog geometry. Outside V6 geometry,
the frozen V4 size-3 envelope remains the legacy fallback. The monitor never
changes, disables, tunes, or promotes production.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import package_adjustment_exact_live_oos_v1_6 as base

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
LIVE = ROOT / "research/package-adjustment-production-candidate-v1/live_deployment.json"
EVIDENCE = ROOT / "research/package-adjustment-v1/prospective/trade_evidence.json"
WORKFLOW = ROOT / ".github/workflows/package-adjustment-audit-step4-exact-live-oos.yml"
DISPATCHER = ROOT / "scripts/validation/package_adjustment_exact_live_oos.py"
THIS_SCRIPT = ROOT / "scripts/validation/package_adjustment_exact_live_oos_v1_7.py"

V3 = ROOT / "research/package-adjustment-v3/package_vote_challenges_v3.json"
V4 = ROOT / "research/package-adjustment-v4/package_vote_challenges_v4.json"
V5 = ROOT / "research/package-adjustment-v5/package_vote_challenges_v5.json"
V6_CATALOG = ROOT / "research/package-adjustment-v6/package_vote_challenges_v6_prospective_v1.json"
V6_FROZEN = ROOT / "research/package-adjustment-v6/prospective_exact_1800_frozen_v1.json"
V6_EVAL = ROOT / "research/package-adjustment-v6/prospective_evaluation_v1.json"
V6_REVIEW = ROOT / "research/package-adjustment-v6/production_review_v1.json"
CANDIDATE = ROOT / "research/package-adjustment-v6/production_candidate_v1.json"

OUT_DIR = ROOT / "research/package-adjustment-production-candidate-v1/prospective"
MANIFEST = OUT_DIR / "release_manifest_v1_7.json"
OUT_JSON = OUT_DIR / "exact_live_oos_validation.json"
OUT_MD = OUT_DIR / "exact_live_oos_validation.md"

PRODUCTION_REVISION = "v1.7-v6-size3-c2-overlay"
RELEASE_ID = "package-adjustment-exact-live-v1.7-v6-c2-size3"
CANDIDATE_ID = "package-adjustment-v6-c2-size3-overlay-candidate-v1"
WORKFLOW_MARKER = "PACKAGE_ADJUSTMENT_OOS_DISPATCHER_V1"
EPS = 1e-12
EXPECTED_POSITIONS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]

MAX_PRETRADE_SNAPSHOT_AGE_HOURS = 48.0
MAX_EVIDENCE_STREAM_STALENESS_HOURS = 8.0
INITIAL_ALIGNMENT_MAX_EVIDENCE_STREAM_STALENESS_HOURS = 26.0

read_json = base.read_json
sha256 = base.sha256
canonical_hash = base.canonical_hash
finite_positive = base.finite_positive
parse_iso = base.parse_iso
log_interp_clamped = base.log_interp_clamped
size2_composition_assessment = base.size2_composition_assessment
summarize = base.summarize


def _extract_profiles(index_text):
    m = re.search(
        r"size3V6Profiles:\s*Object\.freeze\(\[(.*?)\]\),\s*size3V6ApexLevels:",
        index_text,
        flags=re.S,
    )
    if not m:
        raise RuntimeError("Could not extract size3V6Profiles")
    rows = re.findall(
        r"label:\s*'([^']+)'\s*,\s*shares:\s*Object\.freeze\(\[\s*"
        r"([0-9.eE+-]+)\s*,\s*([0-9.eE+-]+)\s*,\s*([0-9.eE+-]+)\s*\]\)",
        m.group(1),
        flags=re.S,
    )
    if len(rows) != 6:
        raise RuntimeError(f"Expected 6 V6 profiles, found {len(rows)}")
    return [
        {"label": label, "shares": [float(a), float(b), float(c)]}
        for label, a, b, c in rows
    ]


def _extract_apex_levels(index_text):
    m = re.search(
        r"size3V6ApexLevels:\s*Object\.freeze\(\[(.*?)\]\),",
        index_text,
        flags=re.S,
    )
    if not m:
        raise RuntimeError("Could not extract size3V6ApexLevels")
    vals = [float(x) for x in re.findall(r"[0-9.]+", m.group(1))]
    if vals != [0.7, 0.8, 0.9, 0.97]:
        raise RuntimeError(f"Unexpected V6 apex levels: {vals}")
    return vals


def extract_formula(index_text: str):
    meaningful = base.extract_number(
        index_text,
        r"meaningfulPieceMinTargetShare:\s*([0-9.eE+-]+)",
        "meaningfulPieceMinTargetShare",
    )
    size3_multiplier = base.extract_number(
        index_text,
        r"size3Multiplier:\s*([0-9.eE+-]+)",
        "size3Multiplier",
    )
    q = base.extract_number(
        index_text,
        r"size3V6Q:\s*([0-9.eE+-]+)",
        "size3V6Q",
    )
    comp_tol = base.extract_number(
        index_text,
        r"size3V6CompositionTolerance:\s*([0-9.eE+-]+)",
        "size3V6CompositionTolerance",
    )
    apex_tol = base.extract_number(
        index_text,
        r"size3V6ApexTolerance:\s*([0-9.eE+-]+)",
        "size3V6ApexTolerance",
    )

    pm = re.search(
        r"supportedPlayerPositions:\s*Object\.freeze\(\[(.*?)\]\),",
        index_text,
        flags=re.S,
    )
    if not pm:
        raise RuntimeError("Could not extract supportedPlayerPositions")
    positions = re.findall(r"['\"]([A-Z]+)['\"]", pm.group(1))
    if positions != EXPECTED_POSITIONS:
        raise RuntimeError(f"Unexpected V1.7 supported positions: {positions}")

    v3 = base.extract_object(
        index_text,
        "size2CompositionEnvelope",
        ("largestMin", "largestMax", "smallestMin", "smallestMax"),
    )
    v5 = base.extract_object(
        index_text,
        "size2V5CompositionOverlay",
        ("largestShareMinExclusive", "largestShareMaxInclusive", "factor55", "factor60"),
    )
    v4 = base.extract_object(
        index_text,
        "size3CompositionEnvelope",
        ("largestMin", "largestMax", "middleMin", "middleMax", "smallestMin", "smallestMax"),
    )

    rm = re.search(
        r"size2ReferencePoints:\s*Object\.freeze\(\[(.*?)\]\),",
        index_text,
        flags=re.S,
    )
    if not rm:
        raise RuntimeError("Could not extract size2ReferencePoints")
    refs = [
        {"target_fv": float(target), "ratio": float(ratio)}
        for target, ratio in re.findall(
            r"targetFv:\s*([0-9.eE+-]+)\s*,\s*ratio:\s*([0-9.eE+-]+)",
            rm.group(1),
        )
    ]
    if len(refs) != 4:
        raise RuntimeError(f"Expected 4 size2 reference points, found {len(refs)}")
    refs.sort(key=lambda r: r["target_fv"])

    required = (
        "function packageAdjustmentSize3V6Assessment(",
        "premiumTier = '3-player-v6';",
        "size3Source = 'V6';",
        "packageAssets.length === 3",
        "reason:'size3_composition_outside_evidence_supported_envelope'",
        "function packageAdjustmentSize2CompositionFactor(",
        "premiumTier = '2-player-v5';",
        "allAssets.some(a => a.type !== 'player')",
        "reason:'unsupported_position'",
        "packageValues.some(v => v >= targetFv)",
        "function packageAdjustmentForTrade(){",
    )
    missing = [token for token in required if token not in index_text]
    if missing:
        raise RuntimeError(f"V1.7 live contract markers missing: {missing}")

    return {
        "meaningful_piece_min_target_share": meaningful,
        "size2": {
            "source": "V1.5 target curve + frozen V3 core + hardened V5 composition overlay",
            "reference_points": refs,
            "v3_composition_policy": v3.get("policy"),
            "v3_composition_envelope": {
                "largest_min": v3["largestMin"],
                "largest_max": v3["largestMax"],
                "smallest_min": v3["smallestMin"],
                "smallest_max": v3["smallestMax"],
                "comparison_epsilon": EPS,
            },
            "v5_overlay": {
                "policy": v5.get("policy"),
                "largest_share_min_exclusive": v5["largestShareMinExclusive"],
                "largest_share_max_inclusive": v5["largestShareMaxInclusive"],
                "factor_55_45": v5["factor55"],
                "factor_60_40": v5["factor60"],
                "factor_floor": 1.0,
                "interpolation": "piecewise_linear",
            },
        },
        "size3": {
            "legacy_v4": {
                "source": "V4 ratio_only fallback outside V6 geometry",
                "multiplier": size3_multiplier,
                "composition_policy": v4.get("policy"),
                "composition_envelope": {
                    "largest_min": v4["largestMin"],
                    "largest_max": v4["largestMax"],
                    "middle_min": v4["middleMin"],
                    "middle_max": v4["middleMax"],
                    "smallest_min": v4["smallestMin"],
                    "smallest_max": v4["smallestMax"],
                    "comparison_epsilon": EPS,
                },
            },
            "v6_c2_overlay": {
                "source": "frozen prospective V6P1 C2 candidate",
                "q": q,
                "score_package": "(sum(v_i**q))**(1/q)",
                "target_multiplier": "sum(v_i)/score_package",
                "exact_raw_package_size_required": 3,
                "composition_profiles": _extract_profiles(index_text),
                "max_abs_composition_share_error": comp_tol,
                "apex_levels": _extract_apex_levels(index_text),
                "max_abs_apex_ratio_error": apex_tol,
                "precedence": "V6 first inside frozen geometry; otherwise V4 fallback",
            },
        },
        "scope_contract": {
            "player_only": True,
            "supported_player_positions": positions,
            "one_for_package_only": True,
            "package_piece_must_be_below_target": True,
            "meaningful_package_sizes": [2, 3],
            "tiny_pieces_count_in_raw_package_fv": True,
            "tiny_pieces_excluded_from_size2_and_v4_composition": True,
            "v6_requires_exactly_three_raw_package_players": True,
            "v6_outside_geometry_fails_closed_to_no_v6_adjustment": True,
            "legacy_v4_fallback_preserved": True,
            "size2_support_ceiling": "60/40",
        },
    }


def size3_v4_assessment(values, formula):
    ordered = sorted((float(x) for x in values), reverse=True)
    if len(ordered) != 3:
        return False, None
    total = sum(ordered)
    if not (total > 0):
        return False, None
    shares = {
        "largest": ordered[0] / total,
        "middle": ordered[1] / total,
        "smallest": ordered[2] / total,
    }
    e = formula["size3"]["legacy_v4"]["composition_envelope"]
    ok = (
        e["largest_min"] - EPS <= shares["largest"] <= e["largest_max"] + EPS
        and e["middle_min"] - EPS <= shares["middle"] <= e["middle_max"] + EPS
        and e["smallest_min"] - EPS <= shares["smallest"] <= e["smallest_max"] + EPS
    )
    return ok, shares


def size3_v6_assessment(values, target_fv, formula):
    ordered = sorted((float(x) for x in values), reverse=True)
    target = float(target_fv)
    if len(ordered) != 3 or not (target > 0):
        return {"supported": False}

    total = sum(ordered)
    shares_list = [x / total for x in ordered]
    shares = {
        "largest": shares_list[0],
        "middle": shares_list[1],
        "smallest": shares_list[2],
    }
    cfg = formula["size3"]["v6_c2_overlay"]

    profile = None
    best_profile_error = None
    for row in cfg["composition_profiles"]:
        err = max(abs(shares_list[i] - float(row["shares"][i])) for i in range(3))
        if err <= float(cfg["max_abs_composition_share_error"]) + EPS:
            if best_profile_error is None or err < best_profile_error:
                best_profile_error = err
                profile = row["label"]

    apex_ratio = ordered[0] / target
    apex_level = None
    best_apex_error = None
    for level in cfg["apex_levels"]:
        err = abs(apex_ratio - float(level))
        if err <= float(cfg["max_abs_apex_ratio_error"]) + EPS:
            if best_apex_error is None or err < best_apex_error:
                best_apex_error = err
                apex_level = float(level)

    if profile is None or apex_level is None:
        return {
            "supported": False,
            "shares": shares,
            "profile": profile,
            "apex_ratio": apex_ratio,
            "apex_level": apex_level,
        }

    q = float(cfg["q"])
    score = sum(x ** q for x in ordered) ** (1.0 / q)
    multiplier = total / score
    if not (multiplier > 1.0):
        raise RuntimeError("V6 C2 multiplier must exceed 1")

    return {
        "supported": True,
        "shares": shares,
        "profile": profile,
        "profile_max_abs_error": best_profile_error,
        "apex_ratio": apex_ratio,
        "apex_level": apex_level,
        "apex_abs_error": best_apex_error,
        "candidate_score": score,
        "multiplier": multiplier,
    }


def verify_live_metadata(live, formula, candidate):
    if live.get("status") != "controlled_live":
        raise RuntimeError("Package Adjustment is not controlled_live")
    if live.get("production_formula_enabled") is not True:
        raise RuntimeError("Package Adjustment production formula is not enabled")
    if live.get("production_revision") != PRODUCTION_REVISION:
        raise RuntimeError("V1.7 monitor dispatched for wrong revision")
    if live.get("package_adjustment_candidate_id") != CANDIDATE_ID:
        raise RuntimeError("V1.7 live candidate id mismatch")
    if live.get("package_adjustment_candidate_spec_sha256") != candidate["candidate_spec_sha256"]:
        raise RuntimeError("V1.7 live candidate spec hash mismatch")
    if live.get("package_adjustment_evidence_fingerprint_sha256") != candidate["source_evidence_fingerprint_sha256"]:
        raise RuntimeError("V1.7 live evidence fingerprint mismatch")
    if live.get("formula_v1_7_exact") != formula:
        raise RuntimeError("V1.7 exact formula metadata differs from source")
    for key in (
        "fundamental_value_consumer_changed",
        "market_value_consumer_changed",
        "draft_pick_value_consumer_changed",
        "team_utility_consumer_changed",
    ):
        if live.get(key) is not False:
            raise RuntimeError(f"Unexpected V1.7 consumer change: {key}")
    if live.get("trade_verdict_consumer_changed") is not True:
        raise RuntimeError("V1.7 must affect Trade Verdict only")


def verify_release_manifest(manifest, live, formula, candidate):
    if manifest.get("status") != "exact_live_oos_release_manifest":
        raise RuntimeError("Unexpected V1.7 release manifest status")
    if manifest.get("frozen") is not True:
        raise RuntimeError("V1.7 release manifest is not frozen")
    if manifest.get("release_id") != RELEASE_ID:
        raise RuntimeError("Unexpected V1.7 release id")
    if manifest.get("production_revision_at_release") != PRODUCTION_REVISION:
        raise RuntimeError("V1.7 release revision mismatch")
    if manifest.get("candidate_id") != CANDIDATE_ID:
        raise RuntimeError("V1.7 release candidate id mismatch")
    if manifest.get("candidate_spec_sha256") != candidate["candidate_spec_sha256"]:
        raise RuntimeError("V1.7 release candidate spec hash mismatch")
    if manifest.get("source_evidence_fingerprint_sha256") != candidate["source_evidence_fingerprint_sha256"]:
        raise RuntimeError("V1.7 release evidence fingerprint mismatch")

    fingerprint = canonical_hash(formula)
    if manifest.get("exact_live_formula_sha256") != fingerprint:
        raise RuntimeError("Exact V1.7 formula changed since release")
    if manifest.get("exact_live_formula") != formula:
        raise RuntimeError("Exact V1.7 formula payload differs from release")

    artifacts = manifest.get("release_artifact_sha256") or {}
    expected = {
        "v3_frozen_catalog": sha256(V3),
        "v4_frozen_catalog": sha256(V4),
        "v5_frozen_catalog": sha256(V5),
        "v6_prospective_catalog": sha256(V6_CATALOG),
        "v6_exact_1800_dataset": sha256(V6_FROZEN),
        "v6_prospective_evaluation": sha256(V6_EVAL),
        "v6_production_review": sha256(V6_REVIEW),
        "candidate_spec_file": sha256(CANDIDATE),
        "monitor_workflow": sha256(WORKFLOW),
        "monitor_dispatcher": sha256(DISPATCHER),
        "v1_7_monitor": sha256(THIS_SCRIPT),
    }
    mismatches = {
        k: {"manifest": artifacts.get(k), "current": v}
        for k, v in expected.items()
        if artifacts.get(k) != v
    }
    if mismatches:
        raise RuntimeError(f"V1.7 release lineage drift: {mismatches}")

    if WORKFLOW_MARKER not in WORKFLOW.read_text(encoding="utf-8"):
        raise RuntimeError("Permanent OOS workflow lost dispatcher marker")
    if PRODUCTION_REVISION not in WORKFLOW.read_text(encoding="utf-8"):
        raise RuntimeError("Permanent OOS workflow does not allow V1.7")
    if PRODUCTION_REVISION not in DISPATCHER.read_text(encoding="utf-8"):
        raise RuntimeError("OOS dispatcher does not route V1.7")
    if live.get("production_revision") != manifest.get("production_revision_at_release"):
        raise RuntimeError("Current live revision differs from V1.7 release")


def classify_trade(trade, manifest):
    created_ms = int(trade.get("created_epoch_ms") or 0)
    cutoff_ms = int(manifest["oos_cutoff_epoch_ms"])
    out = {
        "transaction_id": str(trade.get("transaction_id") or ""),
        "created_at_utc": trade.get("created_at_utc"),
        "created_epoch_ms": created_ms,
        "eligible_for_exact_live_oos": False,
    }
    if created_ms <= cutoff_ms:
        out["exclusion_reason"] = "trade_not_strictly_after_exact_live_release"
        return out
    if not trade.get("eligible_for_numeric_package_research"):
        out["exclusion_reason"] = trade.get("exclusion_reason") or "not_numeric_prospective_evidence"
        return out

    snap = trade.get("pretrade_snapshot") or {}
    try:
        age_hours = float(snap.get("age_hours_at_trade"))
    except (TypeError, ValueError):
        out["exclusion_reason"] = "missing_pretrade_snapshot_age"
        return out
    if not math.isfinite(age_hours) or age_hours < 0:
        out["exclusion_reason"] = "invalid_pretrade_snapshot_age"
        return out
    if age_hours > MAX_PRETRADE_SNAPSHOT_AGE_HOURS:
        out["exclusion_reason"] = "pretrade_snapshot_older_than_48h"
        return out

    sides = trade.get("sides") or []
    if len(sides) != 2:
        out["exclusion_reason"] = "non_two_sided_trade"
        return out

    formula = manifest["exact_live_formula"]
    supported_positions = set(formula["scope_contract"]["supported_player_positions"])
    parsed = []
    for side in sides:
        assets = side.get("received_assets") or []
        if not assets:
            out["exclusion_reason"] = "empty_trade_side"
            return out
        if any(str(a.get("type") or "") != "player" for a in assets):
            out["exclusion_reason"] = "pick_or_nonplayer_asset_present"
            return out
        unsupported = sorted({
            str(a.get("pos") or "").upper()
            for a in assets
            if str(a.get("pos") or "").upper() not in supported_positions
        })
        if unsupported:
            out["exclusion_reason"] = "unsupported_player_position"
            return out
        vals = [finite_positive(a.get("fv")) for a in assets]
        if any(v is None for v in vals):
            out["exclusion_reason"] = "unresolved_player_fv"
            return out
        parsed.append((side, assets, [float(v) for v in vals]))

    counts = [len(x[1]) for x in parsed]
    if counts == [1, 1]:
        out["exclusion_reason"] = "one_for_one_trade"
        return out
    if counts[0] == 1 and counts[1] >= 2:
        target_i, package_i = 0, 1
    elif counts[1] == 1 and counts[0] >= 2:
        target_i, package_i = 1, 0
    else:
        out["exclusion_reason"] = "multi_vs_multi_trade"
        return out

    target_side, target_assets, target_values = parsed[target_i]
    package_side, package_assets, package_values = parsed[package_i]
    target_fv = float(target_values[0])

    if any(v >= target_fv for v in package_values):
        out["exclusion_reason"] = "package_contains_asset_at_or_above_target_fv"
        return out

    threshold = target_fv * float(formula["meaningful_piece_min_target_share"])
    meaningful = [v for v in package_values if v >= threshold]
    tiny = [v for v in package_values if v < threshold]
    size = len(meaningful)

    if size == 1:
        out["exclusion_reason"] = "effective_one_for_one_after_tiny_piece_filter"
        return out
    if size not in (2, 3):
        out["exclusion_reason"] = "unsupported_meaningful_package_size"
        return out

    v6 = None
    composition_factor = 1.0

    if size == 2:
        ok, shares, factor, source = size2_composition_assessment(meaningful, formula)
        if not ok:
            out["exclusion_reason"] = "unsupported_size2_composition"
            return out
        base_multiplier, interpolation_status = log_interp_clamped(
            target_fv, formula["size2"]["reference_points"]
        )
        multiplier = base_multiplier * float(factor)
        model_source = f"exact_live_size2_{source}"
        composition_source = source
        composition_factor = float(factor)
    else:
        if len(package_values) == 3:
            v6 = size3_v6_assessment(package_values, target_fv, formula)
        if v6 and v6.get("supported"):
            shares = v6["shares"]
            multiplier = float(v6["multiplier"])
            interpolation_status = "c2_pnorm_exact"
            model_source = "exact_live_v6_c2_size3"
            composition_source = "V6"
        else:
            ok, shares = size3_v4_assessment(meaningful, formula)
            if not ok:
                out["exclusion_reason"] = "unsupported_size3_composition"
                return out
            multiplier = float(formula["size3"]["legacy_v4"]["multiplier"])
            interpolation_status = "constant"
            model_source = "exact_live_v4_size3_fallback"
            composition_source = "V4"

    raw_package_fv = sum(package_values)
    actual_ratio = raw_package_fv / target_fv
    required_fv = target_fv * multiplier
    coverage = raw_package_fv / required_fv
    exact_err = abs(math.log(max(actual_ratio, 1e-12) / multiplier))
    raw_err = abs(math.log(max(actual_ratio, 1e-12)))

    out.update({
        "eligible_for_exact_live_oos": True,
        "exclusion_reason": None,
        "pretrade_snapshot": snap,
        "pretrade_snapshot_age_hours": age_hours,
        "target_player": target_assets[0].get("name"),
        "target_player_id": target_assets[0].get("player_id"),
        "target_pos": target_assets[0].get("pos"),
        "target_fv": target_fv,
        "concentrated_roster_id": target_side.get("roster_id"),
        "concentrated_team_name": target_side.get("team_name"),
        "package_roster_id": package_side.get("roster_id"),
        "package_team_name": package_side.get("team_name"),
        "package_players": [a.get("name") for a in package_assets],
        "package_player_fvs": package_values,
        "meaningful_package_size": size,
        "meaningful_package_shares": shares,
        "composition_source": composition_source,
        "composition_factor": composition_factor,
        "tiny_piece_fvs_ignored_for_size_and_composition": tiny,
        "raw_package_fv": raw_package_fv,
        "raw_package_to_target_ratio": actual_ratio,
        "exact_live_required_multiplier": multiplier,
        "exact_live_required_package_fv": required_fv,
        "package_to_exact_live_requirement_ratio": coverage,
        "package_pct_from_exact_live_requirement": (coverage - 1.0) * 100.0,
        "package_meets_or_exceeds_exact_live_requirement": raw_package_fv >= required_fv,
        "exact_live_abs_log_error_to_observed_exchange_ratio": exact_err,
        "raw_additive_abs_log_error_to_observed_exchange_ratio": raw_err,
        "exact_live_closer_than_raw_additive": exact_err < raw_err,
        "model_source": model_source,
        "interpolation_status": interpolation_status,
    })
    if v6 and v6.get("supported"):
        out["v6_composition_profile"] = v6["profile"]
        out["v6_apex_ratio"] = v6["apex_ratio"]
        out["v6_apex_level"] = v6["apex_level"]
        out["v6_candidate_score"] = v6["candidate_score"]
    return out


def run_live_monitor():
    required = (
        INDEX, LIVE, EVIDENCE, WORKFLOW, DISPATCHER, THIS_SCRIPT,
        V3, V4, V5, V6_CATALOG, V6_FROZEN, V6_EVAL, V6_REVIEW, CANDIDATE, MANIFEST,
    )
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError(f"V1.7 exact-live OOS prerequisite missing: {missing}")

    candidate = read_json(CANDIDATE)
    live = read_json(LIVE)
    evidence = read_json(EVIDENCE)
    manifest = read_json(MANIFEST)

    formula = extract_formula(INDEX.read_text(encoding="utf-8"))
    verify_live_metadata(live, formula, candidate)
    verify_release_manifest(manifest, live, formula, candidate)

    if evidence.get("status") != "research_only_prospective_trade_evidence":
        raise RuntimeError("Unexpected prospective trade evidence status")
    if evidence.get("consumer_changed") is not False:
        raise RuntimeError("Prospective evidence unexpectedly changed a consumer")
    method = evidence.get("methodology") or {}
    for key in (
        "all_completed_current_league_trades",
        "player_only_trades_included",
        "post_trade_values_never_substituted",
        "requires_snapshot_strictly_before_trade",
    ):
        if method.get(key) is not True:
            raise RuntimeError(f"Anti-hindsight evidence contract failed: {key}")

    evidence_generated = parse_iso(evidence["generated_at_utc"])
    now_dt = datetime.now(timezone.utc)
    evidence_age_hours = (now_dt - evidence_generated).total_seconds() / 3600.0
    if evidence_age_hours < -0.1:
        raise RuntimeError("Prospective evidence timestamp is in the future")

    release_dt = parse_iso(manifest["released_at_utc"])
    since_release_hours = (now_dt - release_dt).total_seconds() / 3600.0
    allowed_staleness = (
        INITIAL_ALIGNMENT_MAX_EVIDENCE_STREAM_STALENESS_HOURS
        if since_release_hours <= 26.0
        else MAX_EVIDENCE_STREAM_STALENESS_HOURS
    )
    if evidence_age_hours > allowed_staleness:
        raise RuntimeError(
            f"Prospective evidence stream is stale: {evidence_age_hours:.2f}h > "
            f"{allowed_staleness:.2f}h"
        )

    f = manifest["exact_live_formula"]
    v3_ok, _, v3_factor, v3_source = size2_composition_assessment([51, 49], f)
    v5_ok, _, v5_factor, v5_source = size2_composition_assessment([55, 45], f)
    max_ok, _, max_factor, max_source = size2_composition_assessment([60, 40], f)
    too_far, _, _, _ = size2_composition_assessment([60.01, 39.99], f)
    if not v3_ok or v3_source != "V3" or abs(v3_factor - 1) > EPS:
        raise RuntimeError("Frozen V3 core self-test failed")
    if not v5_ok or v5_source != "V5" or v5_factor <= 1:
        raise RuntimeError("V5 55/45 self-test failed")
    if not max_ok or max_source != "V5" or abs(max_factor - 1) > EPS:
        raise RuntimeError("V5 60/40 self-test failed")
    if too_far:
        raise RuntimeError("V5 fail-closed ceiling self-test failed")

    v6 = size3_v6_assessment([80, 43.6363636364, 21.8181818182], 100, f)
    if not v6.get("supported") or v6.get("profile") != "55/30/15":
        raise RuntimeError("V6 C2 self-test failed")
    v4_ok, _ = size3_v4_assessment([45, 33, 22], f)
    if not v4_ok:
        raise RuntimeError("Legacy V4 fallback self-test failed")

    rows = [
        classify_trade(t, manifest)
        for t in (evidence.get("trades") or {}).values()
    ]
    rows.sort(key=lambda r: int(r.get("created_epoch_ms") or 0))
    observations = [r for r in rows if r.get("eligible_for_exact_live_oos")]
    summary = summarize(observations, rows)

    result = {
        "schema_version": 3,
        "status": "controlled_live_exact_formula_prospective_oos_monitoring",
        "generated_at_utc": now_dt.isoformat(),
        "consumer_changed": False,
        "fundamental_value_consumer_changed": False,
        "market_value_consumer_changed": False,
        "draft_pick_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "trade_verdict_consumer_changed": False,
        "production_formula_enabled": True,
        "automatic_production_change_allowed": False,
        "release": {
            "release_id": manifest["release_id"],
            "released_at_utc": manifest["released_at_utc"],
            "oos_cutoff_epoch_ms": manifest["oos_cutoff_epoch_ms"],
            "production_revision_at_release": manifest["production_revision_at_release"],
            "exact_live_formula_sha256": manifest["exact_live_formula_sha256"],
            "candidate_spec_sha256": manifest["candidate_spec_sha256"],
            "source_evidence_fingerprint_sha256": manifest["source_evidence_fingerprint_sha256"],
        },
        "evidence_stream": {
            "source": str(EVIDENCE.relative_to(ROOT)),
            "source_generated_at_utc": evidence["generated_at_utc"],
            "source_age_hours_at_evaluation": evidence_age_hours,
            "max_allowed_staleness_hours": allowed_staleness,
            "anti_hindsight_contract_verified": True,
        },
        "methodology": manifest["methodology"],
        "summary": summary,
        "observations": observations,
        "all_trade_classifications": rows,
        "interpretation_guardrail": (
            "Completed trades are revealed-preference observations, not exact fair-value labels. "
            "OOS maturity gates trigger human review only. This monitor never changes production."
        ),
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    gates = summary["evidence_maturity_gates"]
    md = [
        "# Package Adjustment - Exact-Live Prospective/OOS Monitor (V1.7)",
        "",
        f"Generated: {now_dt.isoformat()}",
        "",
        f"- Revision: `{PRODUCTION_REVISION}`",
        f"- Release: `{RELEASE_ID}`",
        "- Size2: V3/V5 unchanged.",
        "- Size3: V6 C2 overlay inside frozen geometry; V4 fallback preserved.",
        "",
        f"- Supported OOS trades: **{summary['supported_oos_trade_count']}**",
        f"- Size2 OOS trades: **{summary['by_package_size']['2']['trade_count']}**",
        f"- Size3 OOS trades: **{summary['by_package_size']['3']['trade_count']}**",
        "",
    ]
    for key, passed in gates["passed"].items():
        md.append(f"- {'PASS' if passed else 'WAIT'} - {key}")
    md.extend([
        "",
        f"All gates passed: **{gates['all_passed']}**",
        "",
        "Passing these gates triggers review only. It never changes production automatically.",
        "",
    ])
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"V1.7 exact-live OOS monitor complete: {len(observations)} eligible observations")
    print("Production changed by monitor: False")


def main():
    run_live_monitor()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Exact-live prospective/OOS monitor for Package Adjustment V1.6.

V1.6 preserves the V1.5 target-sensitive two-player multiplier curve and
frozen V3 core, adds the human-reviewed V5 composition overlay only
through 60/40, and leaves frozen V4 three-player behavior unchanged.

This monitor is dormant until live_deployment.json reports the exact
V1.6 controlled-live revision and the immutable V1.6 release manifest
exists. It never promotes, disables, recalibrates, or modifies production.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
LIVE = ROOT / "research/package-adjustment-production-candidate-v1/live_deployment.json"
EVIDENCE = ROOT / "research/package-adjustment-v1/prospective/trade_evidence.json"
WORKFLOW = ROOT / ".github/workflows/package-adjustment-audit-step4-exact-live-oos.yml"
DISPATCHER = ROOT / "scripts/validation/package_adjustment_exact_live_oos.py"
THIS_SCRIPT = ROOT / "scripts/validation/package_adjustment_exact_live_oos_v1_6.py"
V3 = ROOT / "research/package-adjustment-v3/package_vote_challenges_v3.json"
V4 = ROOT / "research/package-adjustment-v4/package_vote_challenges_v4.json"
V5 = ROOT / "research/package-adjustment-v5/package_vote_challenges_v5.json"
CANDIDATE = ROOT / "research/package-adjustment-v5/production_candidate_design.json"
SHADOW = ROOT / "research/package-adjustment-v5/shadow_regression_hardening.json"
HARDENING = ROOT / "research/package-adjustment-v5/evidence_hardening.json"

OUT_DIR = ROOT / "research/package-adjustment-production-candidate-v1/prospective"
MANIFEST = OUT_DIR / "release_manifest_v1_6.json"
OUT_JSON = OUT_DIR / "exact_live_oos_validation.json"
OUT_MD = OUT_DIR / "exact_live_oos_validation.md"

PRODUCTION_REVISION = "v1.6-v5-size2-composition-overlay"
RELEASE_ID = "package-adjustment-exact-live-v1.6-v5-composition"
CANDIDATE_ID = "package-adjustment-v5-size2-composition-overlay-candidate-v1"
WORKFLOW_MARKER = "PACKAGE_ADJUSTMENT_OOS_DISPATCHER_V1"

MAX_PRETRADE_SNAPSHOT_AGE_HOURS = 48.0
MAX_EVIDENCE_STREAM_STALENESS_HOURS = 8.0
INITIAL_ALIGNMENT_MAX_EVIDENCE_STREAM_STALENESS_HOURS = 26.0
MIN_OOS_SUPPORTED_TRADES = 10
MIN_DISTINCT_TARGETS = 6
MIN_SIZE2_TRADES = 3
MIN_SIZE3_TRADES = 3
EPS = 1e-12

EXPECTED_POSITIONS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())

def canonical_hash(obj) -> str:
    return sha256_bytes(
        json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    )

def finite_positive(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x > 0 else None

def parse_iso(value):
    s = str(value or "").strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def percentile(values, q):
    xs = sorted(float(x) for x in values)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    t = pos - lo
    return xs[lo] * (1 - t) + xs[hi] * t

def extract_number(text: str, pattern: str, label: str) -> float:
    m = re.search(pattern, text, flags=re.S)
    if not m:
        raise RuntimeError(f"Could not extract {label} from exact live source")
    return float(m.group(1))

def extract_object(text: str, object_name: str, fields):
    m = re.search(
        rf"{re.escape(object_name)}:\s*Object\.freeze\(\{{(.*?)\}}\),",
        text,
        flags=re.S,
    )
    if not m:
        raise RuntimeError(f"Could not extract {object_name}")
    body = m.group(1)
    out = {}
    for field in fields:
        fm = re.search(rf"\b{re.escape(field)}:\s*([0-9.eE+-]+)", body)
        if not fm:
            raise RuntimeError(f"Could not extract {object_name}.{field}")
        out[field] = float(fm.group(1))
    pm = re.search(r"\bpolicy:\s*'([^']+)'", body)
    if pm:
        out["policy"] = pm.group(1)
    return out

def extract_formula(index_text: str):
    meaningful = extract_number(
        index_text,
        r"meaningfulPieceMinTargetShare:\s*([0-9.eE+-]+)",
        "meaningfulPieceMinTargetShare",
    )
    size3_multiplier = extract_number(
        index_text,
        r"size3Multiplier:\s*([0-9.eE+-]+)",
        "size3Multiplier",
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
        raise RuntimeError(f"Unexpected V1.6 supported positions: {positions}")

    v3 = extract_object(
        index_text,
        "size2CompositionEnvelope",
        ("largestMin", "largestMax", "smallestMin", "smallestMax"),
    )
    v5 = extract_object(
        index_text,
        "size2V5CompositionOverlay",
        (
            "largestShareMinExclusive",
            "largestShareMaxInclusive",
            "factor55",
            "factor60",
        ),
    )
    v4 = extract_object(
        index_text,
        "size3CompositionEnvelope",
        (
            "largestMin", "largestMax",
            "middleMin", "middleMax",
            "smallestMin", "smallestMax",
        ),
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
        "function packageAdjustmentSize2CompositionFactor(",
        "function packageAdjustmentAssessment(){",
        "size2V5CompositionOverlay",
        "premiumTier = '2-player-v5';",
        "reason:'size2_composition_outside_evidence_supported_envelope'",
        "allAssets.some(a => a.type !== 'player')",
        "reason:'unsupported_position'",
        "packageValues.some(v => v >= targetFv)",
        "if(meaningful.length > 3){",
        "if(meaningful.length === 3){",
        "const rawPackageFv = packageValues.reduce((s,v) => s + v, 0);",
        "const meaningfulPackageFv = meaningful.reduce((s,v) => s + v, 0);",
        "function packageAdjustmentForTrade(){",
    )
    missing = [token for token in required if token not in index_text]
    if missing:
        raise RuntimeError(f"V1.6 live contract markers missing: {missing}")

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
            "source": "V4 ratio_only",
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
        "scope_contract": {
            "player_only": True,
            "supported_player_positions": positions,
            "position_scope_policy": (
                "frozen_v3_v4_target_and_package_position_intersection_fail_closed"
            ),
            "one_for_package_only": True,
            "package_piece_must_be_below_target": True,
            "meaningful_package_sizes": [2, 3],
            "tiny_pieces_count_in_raw_package_fv": True,
            "tiny_pieces_excluded_from_composition": True,
            "unsupported_composition_fails_closed": True,
            "size2_support_ceiling": "60/40",
        },
    }

def assert_close(a, b, label, tol=1e-12):
    if abs(float(a) - float(b)) > tol:
        raise RuntimeError(f"V1.6 metadata/source mismatch for {label}: {a} != {b}")

def log_interp_clamped(target_fv, refs):
    target = finite_positive(target_fv)
    if target is None:
        raise ValueError("target_fv must be positive")
    refs = sorted(refs, key=lambda r: float(r["target_fv"]))
    if target <= float(refs[0]["target_fv"]):
        return float(refs[0]["ratio"]), "clamped_low"
    if target >= float(refs[-1]["target_fv"]):
        return float(refs[-1]["ratio"]), "clamped_high"
    lx = math.log(target)
    for a, b in zip(refs, refs[1:]):
        afv = float(a["target_fv"])
        bfv = float(b["target_fv"])
        if afv <= target <= bfv:
            la, lb = math.log(afv), math.log(bfv)
            w = 0.0 if lb == la else (lx - la) / (lb - la)
            return (
                float(a["ratio"]) + w * (float(b["ratio"]) - float(a["ratio"])),
                "interpolated",
            )
    raise RuntimeError("size2 interpolation interval not found")

def size2_composition_assessment(meaningful, formula):
    ordered = sorted((float(x) for x in meaningful), reverse=True)
    if len(ordered) != 2:
        return False, None, None, None
    total = sum(ordered)
    if not (total > 0):
        return False, None, None, None
    largest = ordered[0] / total
    smallest = ordered[1] / total
    shares = {"largest": largest, "smallest": smallest}

    v3 = formula["size2"]["v3_composition_envelope"]
    in_v3 = (
        v3["largest_min"] - EPS <= largest <= v3["largest_max"] + EPS
        and v3["smallest_min"] - EPS <= smallest <= v3["smallest_max"] + EPS
    )
    if in_v3:
        return True, shares, 1.0, "V3"

    v5 = formula["size2"]["v5_overlay"]
    lower = float(v5["largest_share_min_exclusive"])
    upper = float(v5["largest_share_max_inclusive"])
    if not (largest > lower + EPS) or largest > upper + EPS:
        return False, shares, None, None

    f55 = float(v5["factor_55_45"])
    f60 = float(v5["factor_60_40"])
    if largest <= 0.55:
        span = 0.55 - lower
        w = 0.0 if span <= 0 else (largest - lower) / span
        factor = 1.0 + w * (f55 - 1.0)
    else:
        span = 0.60 - 0.55
        w = 0.0 if span <= 0 else (largest - 0.55) / span
        factor = f55 + w * (f60 - f55)
    factor = max(float(v5.get("factor_floor", 1.0)), factor)
    return True, shares, factor, "V5"

def size3_composition_assessment(meaningful, formula):
    ordered = sorted((float(x) for x in meaningful), reverse=True)
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
    e = formula["size3"]["composition_envelope"]
    ok = (
        e["largest_min"] - EPS <= shares["largest"] <= e["largest_max"] + EPS
        and e["middle_min"] - EPS <= shares["middle"] <= e["middle_max"] + EPS
        and e["smallest_min"] - EPS <= shares["smallest"] <= e["smallest_max"] + EPS
    )
    return ok, shares

def composition_assessment(meaningful, size, formula):
    if size == 2:
        ok, shares, factor, source = size2_composition_assessment(meaningful, formula)
        return ok, shares, factor, source
    if size == 3:
        ok, shares = size3_composition_assessment(meaningful, formula)
        return ok, shares, 1.0 if ok else None, "V4" if ok else None
    return False, None, None, None

def required_multiplier(formula, target_fv, size, composition_factor=1.0, source=None):
    if size == 2:
        base, status = log_interp_clamped(
            target_fv, formula["size2"]["reference_points"]
        )
        factor = float(composition_factor)
        return base * factor, status, f"exact_live_size2_{source or 'unknown'}"
    if size == 3:
        return (
            float(formula["size3"]["multiplier"]),
            "constant",
            "exact_live_v4_size3",
        )
    raise ValueError("unsupported meaningful package size")

def verify_live_metadata(live, formula, candidate):
    if live.get("status") != "controlled_live":
        raise RuntimeError("Package Adjustment is not controlled_live")
    if live.get("production_formula_enabled") is not True:
        raise RuntimeError("Package Adjustment production formula is not enabled")
    if live.get("production_revision") != PRODUCTION_REVISION:
        raise RuntimeError(
            f"V1.6 monitor dispatched for wrong production revision: "
            f"{live.get('production_revision')}"
        )

    if live.get("package_adjustment_candidate_id") != CANDIDATE_ID:
        raise RuntimeError("V1.6 live candidate id mismatch")
    if live.get("package_adjustment_candidate_spec_sha256") != candidate["candidate_spec_sha256"]:
        raise RuntimeError("V1.6 live candidate spec hash mismatch")
    if (
        live.get("package_adjustment_evidence_fingerprint_sha256")
        != candidate["source_evidence_fingerprint_sha256"]
    ):
        raise RuntimeError("V1.6 live evidence fingerprint mismatch")

    lf = live.get("formula") or {}
    assert_close(
        lf["meaningful_piece_min_target_share"],
        formula["meaningful_piece_min_target_share"],
        "meaningful threshold",
    )
    assert_close(
        lf["size3_multiplier"],
        formula["size3"]["multiplier"],
        "size3 multiplier",
    )
    if lf.get("supported_player_positions") != EXPECTED_POSITIONS:
        raise RuntimeError("V1.6 supported-position metadata mismatch")

    live_v3 = lf.get("size2_composition_envelope") or {}
    for key, field in (
        ("largest_min", "largest_min"),
        ("largest_max", "largest_max"),
        ("smallest_min", "smallest_min"),
        ("smallest_max", "smallest_max"),
    ):
        assert_close(
            live_v3[field],
            formula["size2"]["v3_composition_envelope"][key],
            f"V3 {key}",
        )

    live_v5 = lf.get("size2_v5_composition_overlay") or {}
    expected_v5 = formula["size2"]["v5_overlay"]
    for key in (
        "largest_share_min_exclusive",
        "largest_share_max_inclusive",
        "factor_55_45",
        "factor_60_40",
        "factor_floor",
    ):
        assert_close(live_v5[key], expected_v5[key], f"V5 overlay {key}")
    if live_v5.get("policy") != expected_v5.get("policy"):
        raise RuntimeError("V1.6 V5 composition policy metadata mismatch")

def verify_release_manifest(manifest, live, formula, candidate, shadow):
    if manifest.get("status") != "exact_live_oos_release_manifest":
        raise RuntimeError("Unexpected V1.6 OOS release manifest status")
    if manifest.get("frozen") is not True:
        raise RuntimeError("V1.6 OOS release manifest is not frozen")
    if manifest.get("release_id") != RELEASE_ID:
        raise RuntimeError("Unexpected V1.6 OOS release id")
    if manifest.get("production_revision_at_release") != PRODUCTION_REVISION:
        raise RuntimeError("V1.6 release revision mismatch")
    if manifest.get("candidate_id") != CANDIDATE_ID:
        raise RuntimeError("V1.6 release candidate id mismatch")
    if manifest.get("candidate_spec_sha256") != candidate["candidate_spec_sha256"]:
        raise RuntimeError("V1.6 release candidate spec hash mismatch")
    if (
        manifest.get("source_evidence_fingerprint_sha256")
        != candidate["source_evidence_fingerprint_sha256"]
    ):
        raise RuntimeError("V1.6 release evidence fingerprint mismatch")
    if shadow["conclusion"].get("shadow_regression_passed") is not True:
        raise RuntimeError("V1.6 source shadow regression no longer passes")

    fingerprint = canonical_hash(formula)
    if manifest.get("exact_live_formula_sha256") != fingerprint:
        raise RuntimeError("Exact V1.6 live formula changed since release")
    if manifest.get("exact_live_formula") != formula:
        raise RuntimeError("Exact V1.6 live formula payload differs from release")

    artifacts = manifest.get("release_artifact_sha256") or {}
    expected_artifacts = {
        "v3_frozen_catalog": sha256(V3),
        "v4_frozen_catalog": sha256(V4),
        "v5_frozen_catalog": sha256(V5),
        "candidate_spec": sha256(CANDIDATE),
        "shadow_regression": sha256(SHADOW),
        "monitor_workflow": sha256(WORKFLOW),
        "monitor_dispatcher": sha256(DISPATCHER),
        "v1_6_monitor": sha256(THIS_SCRIPT),
    }
    mismatches = {
        key: {"manifest": artifacts.get(key), "current": value}
        for key, value in expected_artifacts.items()
        if artifacts.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"V1.6 release lineage drift: {mismatches}")

    if WORKFLOW_MARKER not in WORKFLOW.read_text(encoding="utf-8"):
        raise RuntimeError("Permanent OOS workflow lost transition dispatcher marker")
    if PRODUCTION_REVISION not in DISPATCHER.read_text(encoding="utf-8"):
        raise RuntimeError("OOS dispatcher no longer routes V1.6")

    if live.get("production_revision") != manifest.get("production_revision_at_release"):
        raise RuntimeError("Current live revision differs from V1.6 release revision")

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
        out["exclusion_reason"] = (
            trade.get("exclusion_reason") or "not_numeric_prospective_evidence"
        )
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
        out["pretrade_snapshot_age_hours"] = age_hours
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
            out["unsupported_positions"] = unsupported
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
        out["meaningful_package_size"] = size
        return out

    ok, shares, factor, composition_source = composition_assessment(
        meaningful, size, formula
    )
    if not ok:
        out["exclusion_reason"] = f"unsupported_size{size}_composition"
        out["meaningful_package_size"] = size
        out["meaningful_package_shares"] = shares
        return out

    raw_package_fv = sum(package_values)
    actual_ratio = raw_package_fv / target_fv
    multiplier, interpolation_status, model_source = required_multiplier(
        formula,
        target_fv,
        size,
        composition_factor=factor,
        source=composition_source,
    )
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
        "composition_factor": factor,
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
    return out

def summarize(observations, rows):
    reasons = Counter(
        r.get("exclusion_reason") or "unknown"
        for r in rows
        if not r.get("eligible_for_exact_live_oos")
    )
    by_size = {}
    for size in (2, 3):
        sub = [r for r in observations if int(r["meaningful_package_size"]) == size]
        coverage = [r["package_to_exact_live_requirement_ratio"] for r in sub]
        actual = [r["raw_package_to_target_ratio"] for r in sub]
        req = [r["exact_live_required_multiplier"] for r in sub]
        by_size[str(size)] = {
            "trade_count": len(sub),
            "median_observed_package_to_target_ratio": statistics.median(actual) if actual else None,
            "median_exact_live_required_multiplier": statistics.median(req) if req else None,
            "median_package_to_exact_live_requirement_ratio": statistics.median(coverage) if coverage else None,
            "within_10pct_of_requirement_pct": (
                100.0 * sum(0.90 <= x <= 1.10 for x in coverage) / len(coverage)
                if coverage else None
            ),
            "within_20pct_of_requirement_pct": (
                100.0 * sum(0.80 <= x <= 1.20 for x in coverage) / len(coverage)
                if coverage else None
            ),
        }

    coverages = [r["package_to_exact_live_requirement_ratio"] for r in observations]
    exact_errors = [r["exact_live_abs_log_error_to_observed_exchange_ratio"] for r in observations]
    raw_errors = [r["raw_additive_abs_log_error_to_observed_exchange_ratio"] for r in observations]
    targets = {
        str(r.get("target_player_id") or r.get("target_player"))
        for r in observations
    }
    gates = {
        "supported_oos_trades": len(observations) >= MIN_OOS_SUPPORTED_TRADES,
        "distinct_targets": len(targets) >= MIN_DISTINCT_TARGETS,
        "size2_coverage": by_size["2"]["trade_count"] >= MIN_SIZE2_TRADES,
        "size3_coverage": by_size["3"]["trade_count"] >= MIN_SIZE3_TRADES,
    }
    return {
        "logged_trade_count": len(rows),
        "supported_oos_trade_count": len(observations),
        "excluded_trade_count": len(rows) - len(observations),
        "distinct_target_count": len(targets),
        "exclusion_reasons": dict(sorted(reasons.items())),
        "by_package_size": by_size,
        "overall": {
            "median_package_to_exact_live_requirement_ratio": statistics.median(coverages) if coverages else None,
            "p25_package_to_exact_live_requirement_ratio": percentile(coverages, 0.25) if coverages else None,
            "p75_package_to_exact_live_requirement_ratio": percentile(coverages, 0.75) if coverages else None,
            "within_10pct_of_exact_live_requirement_pct": (
                100.0 * sum(0.90 <= x <= 1.10 for x in coverages) / len(coverages)
                if coverages else None
            ),
            "within_20pct_of_exact_live_requirement_pct": (
                100.0 * sum(0.80 <= x <= 1.20 for x in coverages) / len(coverages)
                if coverages else None
            ),
            "median_exact_live_abs_log_error": statistics.median(exact_errors) if exact_errors else None,
            "median_raw_additive_abs_log_error": statistics.median(raw_errors) if raw_errors else None,
            "exact_live_closer_than_raw_additive_pct": (
                100.0 * sum(r["exact_live_closer_than_raw_additive"] for r in observations) / len(observations)
                if observations else None
            ),
        },
        "evidence_maturity_gates": {
            "thresholds": {
                "supported_oos_trades": MIN_OOS_SUPPORTED_TRADES,
                "distinct_targets": MIN_DISTINCT_TARGETS,
                "size2_trades": MIN_SIZE2_TRADES,
                "size3_trades": MIN_SIZE3_TRADES,
            },
            "passed": gates,
            "all_passed": all(gates.values()),
            "effect": "review_ready_only; never auto-changes production",
        },
    }

def validate_proposed_index(index_path: Path):
    candidate = read_json(CANDIDATE)
    readiness = read_json(ROOT / "research/package-adjustment-v5/promotion_readiness.json")
    text = index_path.read_text(encoding="utf-8")
    formula = extract_formula(text)

    if sha256(index_path) != readiness["proposed_index_patch"]["proposed_index_sha256"]:
        raise RuntimeError("Temporary proposed index SHA differs from reviewed readiness artifact")

    v5 = formula["size2"]["v5_overlay"]
    assert_close(v5["largest_share_min_exclusive"], 0.5230278884462152, "V5 lower boundary")
    assert_close(v5["largest_share_max_inclusive"], 0.60, "V5 upper boundary")
    assert_close(v5["factor_55_45"], candidate["multiplier_policy"]["candidate_factor_55_45"], "55/45 factor")
    assert_close(v5["factor_60_40"], candidate["multiplier_policy"]["candidate_factor_60_40"], "60/40 factor")

    tests = []
    def check_pair(name, a, b, expected, factor=None):
        ok, shares, got, source = size2_composition_assessment([a, b], formula)
        if ok is not expected:
            raise RuntimeError(f"{name}: support {ok} != {expected}")
        if factor is not None:
            assert_close(got, factor, name, tol=1e-9)
        tests.append({
            "name": name,
            "supported": ok,
            "largest_share": None if shares is None else shares["largest"],
            "factor": got,
            "source": source,
        })

    check_pair("50_50_legacy_gap", 50, 50, False)
    check_pair("51_49_frozen_v3", 51, 49, True, 1.0)
    check_pair("55_45_v5_anchor", 55, 45, True, float(v5["factor_55_45"]))
    check_pair("56_44_v5_interior", 56, 44, True)
    check_pair("60_40_v5_ceiling", 60, 40, True, 1.0)
    check_pair("above_60_40_fail_closed", 60.01, 39.99, False)
    check_pair("65_35_fail_closed", 65, 35, False)

    ok3, shares3 = size3_composition_assessment([45, 33, 22], formula)
    if not ok3:
        raise RuntimeError("Frozen V4 45/33/22 self-test failed")
    bad3, _ = size3_composition_assessment([55, 24, 21], formula)
    if bad3:
        raise RuntimeError("Unsupported V4 composition unexpectedly passed")

    base, _ = log_interp_clamped(5896, formula["size2"]["reference_points"])
    ok, shares, factor, source = size2_composition_assessment([4153, 3258], formula)
    if not ok or source != "V5":
        raise RuntimeError("Motivating 56/44 case is not V5-supported")
    mult = base * factor
    assert_close(mult, 1.73491004, "motivating case multiplier", tol=2e-8)

    return {
        "formula_sha256": canonical_hash(formula),
        "tests": tests,
        "v4_supported": ok3,
        "motivating_case": {
            "largest_share": shares["largest"],
            "composition_factor": factor,
            "multiplier": mult,
        },
    }

def run_live_monitor():
    required = (
        INDEX, LIVE, EVIDENCE, WORKFLOW, DISPATCHER, THIS_SCRIPT,
        V3, V4, V5, CANDIDATE, SHADOW, HARDENING, MANIFEST,
    )
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError(f"V1.6 exact-live OOS prerequisite missing: {missing}")

    candidate = read_json(CANDIDATE)
    shadow = read_json(SHADOW)
    live = read_json(LIVE)
    evidence = read_json(EVIDENCE)
    manifest = read_json(MANIFEST)

    if candidate.get("candidate_id") != CANDIDATE_ID:
        raise RuntimeError("Unexpected V1.6 candidate id")
    if candidate.get("candidate_spec_sha256") != shadow.get("candidate_spec_sha256"):
        raise RuntimeError("Candidate/shadow hash mismatch")

    formula = extract_formula(INDEX.read_text(encoding="utf-8"))
    verify_live_metadata(live, formula, candidate)
    verify_release_manifest(manifest, live, formula, candidate, shadow)

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
            f"Prospective evidence stream is stale: {evidence_age_hours:.2f}h > {allowed_staleness:.2f}h"
        )

    # Exact release-boundary composition self-tests.
    f = manifest["exact_live_formula"]
    v3_ok, _, v3_factor, v3_source = size2_composition_assessment([51, 49], f)
    v5_ok, _, v5_factor, v5_source = size2_composition_assessment([55, 45], f)
    max_ok, _, max_factor, max_source = size2_composition_assessment([60, 40], f)
    too_far, _, _, _ = size2_composition_assessment([60.01, 39.99], f)
    v4_ok, _ = size3_composition_assessment([45, 33, 22], f)
    if not v3_ok or v3_source != "V3" or abs(v3_factor - 1) > EPS:
        raise RuntimeError("Frozen V3 core release self-test failed")
    if not v5_ok or v5_source != "V5" or v5_factor <= 1:
        raise RuntimeError("V5 55/45 release self-test failed")
    if not max_ok or max_source != "V5" or abs(max_factor - 1) > EPS:
        raise RuntimeError("V5 60/40 ceiling release self-test failed")
    if too_far or not v4_ok:
        raise RuntimeError("V1.6 fail-closed/V4 release self-test failed")

    rows = [
        classify_trade(t, manifest)
        for t in (evidence.get("trades") or {}).values()
    ]
    rows.sort(key=lambda r: int(r.get("created_epoch_ms") or 0))
    observations = [r for r in rows if r.get("eligible_for_exact_live_oos")]
    summary = summarize(observations, rows)

    result = {
        "schema_version": 2,
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
            "scheduled_run_max_allowed_staleness_hours": MAX_EVIDENCE_STREAM_STALENESS_HOURS,
            "initial_alignment_max_allowed_staleness_hours": INITIAL_ALIGNMENT_MAX_EVIDENCE_STREAM_STALENESS_HOURS,
            "anti_hindsight_contract_verified": True,
        },
        "methodology": manifest["methodology"],
        "summary": summary,
        "observations": observations,
        "all_trade_classifications": rows,
        "interpretation_guardrail": (
            "Completed trades are revealed-preference observations, not exact fair-value labels. "
            "OOS maturity gates trigger human review only. This monitor never auto-adjusts, "
            "disables, promotes, or recalibrates the live Package Adjustment."
        ),
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    gates = summary["evidence_maturity_gates"]
    md = [
        "# Package Adjustment — Exact-Live Prospective/OOS Monitor (V1.6)",
        "",
        f"Generated: {now_dt.isoformat()}",
        "",
        "## Release",
        "",
        f"- Revision: `{PRODUCTION_REVISION}`",
        f"- Release: `{RELEASE_ID}`",
        f"- Formula SHA-256: `{manifest['exact_live_formula_sha256']}`",
        f"- Candidate spec SHA-256: `{manifest['candidate_spec_sha256']}`",
        "- Size2: frozen V3 core + hardened V5 overlay through 60/40.",
        "- Size3: frozen V4 unchanged.",
        "- 65/35+ remains fail closed.",
        "",
        "## OOS evidence",
        "",
        f"- Supported OOS trades: **{summary['supported_oos_trade_count']}**",
        f"- Distinct concentrated targets: **{summary['distinct_target_count']}**",
        f"- Size2 OOS trades: **{summary['by_package_size']['2']['trade_count']}**",
        f"- Size3 OOS trades: **{summary['by_package_size']['3']['trade_count']}**",
        f"- Evidence stream age: **{evidence_age_hours:.2f} hours**",
        "",
        "## Evidence maturity gates",
        "",
    ]
    for key, passed in gates["passed"].items():
        md.append(f"- {'PASS' if passed else 'WAIT'} — {key}")
    md.extend([
        "",
        f"All gates passed: **{gates['all_passed']}**",
        "",
        "Passing these gates triggers review only. It never changes production automatically.",
        "",
    ])
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"V1.6 exact-live OOS monitor complete: {len(observations)} eligible observations")
    print("Production changed by monitor: False")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-proposed-index", type=Path)
    args = parser.parse_args()
    if args.validate_proposed_index:
        result = validate_proposed_index(args.validate_proposed_index)
        print(json.dumps(result, indent=2, sort_keys=True))
        print("V1.6 proposed-index monitor readiness: PASS")
        return
    run_live_monitor()

if __name__ == "__main__":
    main()

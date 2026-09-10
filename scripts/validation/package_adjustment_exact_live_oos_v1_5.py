#!/usr/bin/env python3
# AUTO-EXTERNALIZED FROM THE EXACT CONTROLLED-LIVE V1.5 OOS WORKFLOW.
# This file preserves the previous inline monitor logic byte-for-logic;
# it is retained as the V1.5 compatibility implementation.

from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import math
import re
import statistics
import time

ROOT = Path(".")
INDEX = ROOT / "index.html"
LIVE = ROOT / "research/package-adjustment-production-candidate-v1/live_deployment.json"
PLAN = ROOT / "research/package-adjustment-production-candidate-v1/audit_clean_plan.md"
V3 = ROOT / "research/package-adjustment-v3/package_vote_challenges_v3.json"
V4 = ROOT / "research/package-adjustment-v4/package_vote_challenges_v4.json"
STEP2 = ROOT / "research/package-adjustment-production-candidate-v1/audit_step2_policy_hardening.json"
STEP3 = ROOT / "research/package-adjustment-production-candidate-v1/audit_step3_policy_hardening.json"
STEP6 = ROOT / "research/package-adjustment-production-candidate-v1/audit_step6_policy_hardening.json"
EVIDENCE = ROOT / "research/package-adjustment-v1/prospective/trade_evidence.json"
WORKFLOW = ROOT / ".github/workflows/package-adjustment-audit-step4-exact-live-oos.yml"

OUT_DIR = ROOT / "research/package-adjustment-production-candidate-v1/prospective"
PREVIOUS_MANIFEST = OUT_DIR / "release_manifest.json"
MANIFEST = OUT_DIR / "release_manifest_v1_5.json"
OUT_JSON = OUT_DIR / "exact_live_oos_validation.json"
OUT_MD = OUT_DIR / "exact_live_oos_validation.md"

MAX_PRETRADE_SNAPSHOT_AGE_HOURS = 48.0
MAX_EVIDENCE_STREAM_STALENESS_HOURS = 8.0
INITIAL_ALIGNMENT_MAX_EVIDENCE_STREAM_STALENESS_HOURS = 26.0
MIN_OOS_SUPPORTED_TRADES = 10
MIN_DISTINCT_TARGETS = 6
MIN_SIZE2_TRADES = 3
MIN_SIZE3_TRADES = 3
EPS = 1e-12

for p in (INDEX, LIVE, PLAN, V3, V4, STEP2, STEP3, STEP6, EVIDENCE, WORKFLOW, PREVIOUS_MANIFEST):
    if not p.exists():
        raise RuntimeError(f"Required file missing: {p}")

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()

def sha256(path):
    return sha256_bytes(path.read_bytes())

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

def extract_number(text, pattern, label):
    m = re.search(pattern, text, flags=re.S)
    if not m:
        raise RuntimeError(f"Could not extract {label} from exact live source")
    return float(m.group(1))

def extract_envelope(text, object_name, fields):
    m = re.search(
        rf"{re.escape(object_name)}:\s*Object\.freeze\(\{{(.*?)\}}\),",
        text,
        flags=re.S,
    )
    if not m:
        raise RuntimeError(f"Could not extract {object_name} from exact live source")
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

def extract_formula(index_text):
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
    supported_positions = re.findall(r"['\"]([A-Z]+)['\"]", pm.group(1))
    expected_positions = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]
    if supported_positions != expected_positions:
        raise RuntimeError(
            f"Unexpected exact-live supported positions: {supported_positions}"
        )
    size2_env = extract_envelope(
        index_text,
        "size2CompositionEnvelope",
        ("largestMin", "largestMax", "smallestMin", "smallestMax"),
    )
    size3_env = extract_envelope(
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
    refs = []
    for target, ratio in re.findall(
        r"targetFv:\s*([0-9.eE+-]+)\s*,\s*ratio:\s*([0-9.eE+-]+)",
        rm.group(1),
    ):
        refs.append({"target_fv": float(target), "ratio": float(ratio)})
    if len(refs) != 4:
        raise RuntimeError(f"Expected 4 size2 reference points, found {len(refs)}")
    refs.sort(key=lambda r: r["target_fv"])

    required_contract_markers = [
        "function packageAdjustmentAssessment(){",
        "allAssets.some(a => a.type !== 'player')",
        "PACKAGE_ADJUSTMENT_PRODUCTION_V1.supportedPlayerPositions",
        ".filter(pos => !supportedPositions.includes(pos))",
        "reason:'unsupported_position'",
        "if(aAssets.length === 1 && bAssets.length >= 2){",
        "else if(bAssets.length === 1 && aAssets.length >= 2){",
        "packageValues.some(v => v >= targetFv)",
        "if(meaningful.length > 3){",
        "if(meaningful.length === 2){",
        "PACKAGE_ADJUSTMENT_PRODUCTION_V1.size2CompositionEnvelope",
        "if(meaningful.length === 3){",
        "PACKAGE_ADJUSTMENT_PRODUCTION_V1.size3CompositionEnvelope",
        "const rawPackageFv = packageValues.reduce((s,v) => s + v, 0);",
        "const meaningfulPackageFv = meaningful.reduce((s,v) => s + v, 0);",
        "function packageAdjustmentForTrade(){",
        "Package Adjustment · Not Applied",
    ]
    missing = [m for m in required_contract_markers if m not in index_text]
    if missing:
        raise RuntimeError(
            "Exact-live source contract marker(s) missing: " + json.dumps(missing)
        )

    return {
        "meaningful_piece_min_target_share": meaningful,
        "size2": {
            "source": "V3 ratio_plus_size_target",
            "reference_points": refs,
            "composition_policy": size2_env.get("policy"),
            "composition_envelope": {
                "largest_min": size2_env["largestMin"],
                "largest_max": size2_env["largestMax"],
                "smallest_min": size2_env["smallestMin"],
                "smallest_max": size2_env["smallestMax"],
                "comparison_epsilon": EPS,
            },
        },
        "size3": {
            "source": "V4 ratio_only",
            "multiplier": size3_multiplier,
            "composition_policy": size3_env.get("policy"),
            "composition_envelope": {
                "largest_min": size3_env["largestMin"],
                "largest_max": size3_env["largestMax"],
                "middle_min": size3_env["middleMin"],
                "middle_max": size3_env["middleMax"],
                "smallest_min": size3_env["smallestMin"],
                "smallest_max": size3_env["smallestMax"],
                "comparison_epsilon": EPS,
            },
        },
        "scope_contract": {
            "player_only": True,
            "supported_player_positions": supported_positions,
            "position_scope_policy": "frozen_v3_v4_target_and_package_position_intersection_fail_closed",
            "one_for_package_only": True,
            "package_piece_must_be_below_target": True,
            "meaningful_package_sizes": [2, 3],
            "tiny_pieces_count_in_raw_package_fv": True,
            "tiny_pieces_excluded_from_composition": True,
            "unsupported_composition_fails_closed": True,
        },
    }

def canonical_hash(obj):
    payload = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return sha256_bytes(payload)

def assert_close(a, b, label):
    if abs(float(a) - float(b)) > 1e-12:
        raise RuntimeError(f"Exact-live metadata/source mismatch for {label}: {a} != {b}")

def verify_live_metadata(live, formula):
    if live.get("status") != "controlled_live":
        raise RuntimeError("Package Adjustment is not controlled_live")
    if live.get("production_formula_enabled") is not True:
        raise RuntimeError("Package Adjustment production formula is not enabled")

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

    if lf.get("size2_source") != formula["size2"]["source"]:
        raise RuntimeError("size2 source mismatch")
    if lf.get("size3_source") != formula["size3"]["source"]:
        raise RuntimeError("size3 source mismatch")
    if lf.get("supported_player_positions") != formula["scope_contract"]["supported_player_positions"]:
        raise RuntimeError("supported player position scope mismatch")
    if lf.get("position_scope_policy") != formula["scope_contract"]["position_scope_policy"]:
        raise RuntimeError("position scope policy mismatch")
    if live.get("production_revision") != "v1.5-audit-step6-scope-ui-idp":
        raise RuntimeError(
            f"Unexpected production revision for V1.5 monitor: {live.get('production_revision')}"
        )
    if lf.get("size2_composition_policy") != "frozen_v3_size2_rectangular_empirical_hull_fail_closed":
        raise RuntimeError("Unexpected live size2 composition policy")
    if lf.get("size3_composition_policy") != "frozen_v4_rectangular_empirical_hull_fail_closed":
        raise RuntimeError("Unexpected live size3 composition policy")

    for key, val in formula["size2"]["composition_envelope"].items():
        if key == "comparison_epsilon":
            continue
        assert_close(
            lf["size2_composition_envelope"][key],
            val,
            f"size2 envelope {key}",
        )
    for key, val in formula["size3"]["composition_envelope"].items():
        if key == "comparison_epsilon":
            continue
        assert_close(
            lf["size3_composition_envelope"][key],
            val,
            f"size3 envelope {key}",
        )

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
            t = 0.0 if lb == la else (lx - la) / (lb - la)
            ratio = float(a["ratio"]) + t * (
                float(b["ratio"]) - float(a["ratio"])
            )
            return ratio, "interpolated"
    raise RuntimeError("size2 interpolation interval not found")

def composition_supported(meaningful, size, formula):
    ordered = sorted((float(x) for x in meaningful), reverse=True)
    total = sum(ordered)
    if not (total > 0):
        return False, None

    if size == 2:
        shares = {
            "largest": ordered[0] / total,
            "smallest": ordered[1] / total,
        }
        e = formula["size2"]["composition_envelope"]
        ok = (
            e["largest_min"] - EPS <= shares["largest"] <= e["largest_max"] + EPS
            and e["smallest_min"] - EPS <= shares["smallest"] <= e["smallest_max"] + EPS
        )
        return ok, shares

    if size == 3:
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

    return False, None

def required_multiplier(formula, target_fv, size):
    if size == 2:
        mult, status = log_interp_clamped(
            target_fv, formula["size2"]["reference_points"]
        )
        return mult, status, "exact_live_v3_size2"
    if size == 3:
        return (
            float(formula["size3"]["multiplier"]),
            "constant",
            "exact_live_v4_size3",
        )
    raise ValueError("unsupported meaningful package size")

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
            trade.get("exclusion_reason")
            or "not_numeric_prospective_evidence"
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

    parsed = []
    for side in sides:
        assets = side.get("received_assets") or []
        if not assets:
            out["exclusion_reason"] = "empty_trade_side"
            return out
        if any(str(a.get("type") or "") != "player" for a in assets):
            out["exclusion_reason"] = "pick_or_nonplayer_asset_present"
            return out
        supported_positions = set(
            manifest["exact_live_formula"]["scope_contract"]["supported_player_positions"]
        )
        unsupported_positions = sorted({
            str(a.get("pos") or "").upper()
            for a in assets
            if str(a.get("pos") or "").upper() not in supported_positions
        })
        if unsupported_positions:
            out["exclusion_reason"] = "unsupported_player_position"
            out["unsupported_positions"] = unsupported_positions
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

    formula = manifest["exact_live_formula"]
    threshold = target_fv * float(
        formula["meaningful_piece_min_target_share"]
    )
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

    ok, shares = composition_supported(meaningful, size, formula)
    if not ok:
        out["exclusion_reason"] = f"unsupported_size{size}_composition"
        out["meaningful_package_size"] = size
        out["meaningful_package_shares"] = shares
        return out

    raw_package_fv = sum(package_values)
    actual_ratio = raw_package_fv / target_fv
    multiplier, interpolation_status, model_source = required_multiplier(
        formula, target_fv, size
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
        sub = [
            r for r in observations
            if int(r["meaningful_package_size"]) == size
        ]
        coverage = [
            r["package_to_exact_live_requirement_ratio"] for r in sub
        ]
        actual = [r["raw_package_to_target_ratio"] for r in sub]
        req = [r["exact_live_required_multiplier"] for r in sub]
        by_size[str(size)] = {
            "trade_count": len(sub),
            "median_observed_package_to_target_ratio": (
                statistics.median(actual) if actual else None
            ),
            "median_exact_live_required_multiplier": (
                statistics.median(req) if req else None
            ),
            "median_package_to_exact_live_requirement_ratio": (
                statistics.median(coverage) if coverage else None
            ),
            "within_10pct_of_requirement_pct": (
                100.0 * sum(0.90 <= x <= 1.10 for x in coverage) / len(coverage)
                if coverage else None
            ),
            "within_20pct_of_requirement_pct": (
                100.0 * sum(0.80 <= x <= 1.20 for x in coverage) / len(coverage)
                if coverage else None
            ),
        }

    coverages = [
        r["package_to_exact_live_requirement_ratio"]
        for r in observations
    ]
    exact_errors = [
        r["exact_live_abs_log_error_to_observed_exchange_ratio"]
        for r in observations
    ]
    raw_errors = [
        r["raw_additive_abs_log_error_to_observed_exchange_ratio"]
        for r in observations
    ]
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
            "median_package_to_exact_live_requirement_ratio": (
                statistics.median(coverages) if coverages else None
            ),
            "p25_package_to_exact_live_requirement_ratio": (
                percentile(coverages, 0.25) if coverages else None
            ),
            "p75_package_to_exact_live_requirement_ratio": (
                percentile(coverages, 0.75) if coverages else None
            ),
            "within_10pct_of_exact_live_requirement_pct": (
                100.0 * sum(0.90 <= x <= 1.10 for x in coverages) / len(coverages)
                if coverages else None
            ),
            "within_20pct_of_exact_live_requirement_pct": (
                100.0 * sum(0.80 <= x <= 1.20 for x in coverages) / len(coverages)
                if coverages else None
            ),
            "median_exact_live_abs_log_error": (
                statistics.median(exact_errors) if exact_errors else None
            ),
            "median_raw_additive_abs_log_error": (
                statistics.median(raw_errors) if raw_errors else None
            ),
            "exact_live_closer_than_raw_additive_pct": (
                100.0 * sum(
                    r["exact_live_closer_than_raw_additive"]
                    for r in observations
                ) / len(observations)
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
            "effect": (
                "review_ready_only; never auto-changes production"
            ),
        },
    }

index_text = INDEX.read_text(encoding="utf-8")
live = read_json(LIVE)
evidence = read_json(EVIDENCE)
exact_formula = extract_formula(index_text)
verify_live_metadata(live, exact_formula)
formula_fingerprint = canonical_hash(exact_formula)

# Verify the upstream anti-hindsight evidence stream is healthy/fresh.
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

OUT_DIR.mkdir(parents=True, exist_ok=True)
first_release = not MANIFEST.exists()
allowed_evidence_staleness_hours = (
    INITIAL_ALIGNMENT_MAX_EVIDENCE_STREAM_STALENESS_HOURS
    if first_release
    else MAX_EVIDENCE_STREAM_STALENESS_HOURS
)
if evidence_age_hours > allowed_evidence_staleness_hours:
    raise RuntimeError(
        "Prospective evidence stream is stale: "
        f"{evidence_age_hours:.2f}h > {allowed_evidence_staleness_hours:.2f}h"
    )

previous_manifest = read_json(PREVIOUS_MANIFEST)
if previous_manifest.get("status") != "exact_live_oos_release_manifest":
    raise RuntimeError("Unexpected original Step 4 release manifest status")
if previous_manifest.get("frozen") is not True:
    raise RuntimeError("Original Step 4 release manifest is not frozen")
if previous_manifest.get("release_id") != "package-adjustment-exact-live-v1.4-step4":
    raise RuntimeError("Unexpected original Step 4 release id")

if first_release:
    if live.get("production_revision") != "v1.5-audit-step6-scope-ui-idp":
        raise RuntimeError("V1.5 production revision required before monitor realignment")

    hardening = live.setdefault("audit_hardening", {})
    if hardening.get("step6_live_hardening_complete") is not True:
        raise RuntimeError("Step 6 live hardening is not marked complete")
    if hardening.get("kicker_package_adjustment_excluded") is not True:
        raise RuntimeError("Kicker scope hardening is not active")
    if hardening.get("idp_uses_same_package_adjustment_rules_as_offense") is not True:
        raise RuntimeError("IDP consistency hardening is not active")

    release_ms = int(time.time() * 1000)
    release_dt = datetime.fromtimestamp(
        release_ms / 1000.0, tz=timezone.utc
    )

    # Monitoring metadata only; the V1.5 verdict formula is unchanged.
    live["exact_live_prospective_monitoring"] = True
    live["postlaunch_monitoring_required"] = True
    live["monitoring_release_id"] = "package-adjustment-exact-live-v1.5-step6-realignment"
    live["monitoring_release_at_utc"] = release_dt.isoformat()
    hardening["exact_live_oos_release_manifest"] = True
    hardening["exact_live_prospective_monitoring"] = True
    hardening["exact_live_monitor_revision_aligned"] = True
    hardening["step6_monitor_realign_required"] = False
    hardening["step6_gate_complete"] = True
    hardening["oos_requires_post_release_trade"] = True
    hardening["oos_requires_pretrade_snapshot_within_48h"] = True
    LIVE.write_text(
        json.dumps(live, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    plan = PLAN.read_text(encoding="utf-8")
    old_plan = "\n".join([
        "- [ ] Step 6 — Unsupported-shape UI + scope guards + IDP consistency",
        "  - Live scope/UI hardening installed: unsupported shapes now explain why Package Adjustment was not applied.",
        "  - Package Adjustment is explicitly limited to QB/RB/WR/TE/DL/LB/DB, the frozen V3/V4 evidence-supported positions.",
        "  - K is fail-closed; DL/LB/DB use the same evidence-bounded Package Adjustment rules as offense.",
        "  - Pending before this gate closes: re-freeze/re-align the exact-live Step 4 OOS monitor to production revision V1.5.",
    ])
    new_plan = "\n".join([
        "- [x] Step 6 — Unsupported-shape UI + scope guards + IDP consistency",
        "  - Unsupported shapes explain why Package Adjustment was not applied while raw FV/verdict behavior remains available.",
        "  - Package Adjustment is explicitly limited to QB/RB/WR/TE/DL/LB/DB; K fails closed.",
        "  - DL/LB/DB use the same evidence-bounded Package Adjustment rules as offense.",
        "  - Exact-live prospective/OOS monitoring is re-frozen and revision-aligned to production V1.5.",
    ])
    if old_plan not in plan:
        raise RuntimeError("Expected pending Step 6 plan block not found")
    PLAN.write_text(plan.replace(old_plan, new_plan, 1), encoding="utf-8")

    manifest = {
        "schema_version": 2,
        "status": "exact_live_oos_release_manifest",
        "frozen": True,
        "release_id": "package-adjustment-exact-live-v1.5-step6-realignment",
        "released_at_utc": release_dt.isoformat(),
        "oos_cutoff_epoch_ms": release_ms,
        "production_formula_enabled": True,
        "production_status": "controlled_live",
        "production_revision_at_release": live["production_revision"],
        "supersedes_for_active_monitoring": previous_manifest["release_id"],
        "previous_release_manifest_sha256": sha256(PREVIOUS_MANIFEST),
        "exact_live_formula": exact_formula,
        "exact_live_formula_sha256": formula_fingerprint,
        "release_artifact_sha256": {
            "index_html_at_release": sha256(INDEX),
            "live_deployment_at_release": sha256(LIVE),
            "v3_frozen_catalog": sha256(V3),
            "v4_frozen_catalog": sha256(V4),
            "step2_hardening": sha256(STEP2),
            "step3_hardening": sha256(STEP3),
            "step6_hardening": sha256(STEP6),
            "original_v1_4_release_manifest": sha256(PREVIOUS_MANIFEST),
            "monitor_workflow": sha256(WORKFLOW),
        },
        "methodology": {
            "only_trades_strictly_after_release_cutoff": True,
            "only_pretrade_fv_snapshots": True,
            "max_pretrade_snapshot_age_hours": MAX_PRETRADE_SNAPSHOT_AGE_HOURS,
            "player_only": True,
            "supported_player_positions": exact_formula["scope_contract"]["supported_player_positions"],
            "unsupported_positions_fail_closed": True,
            "supported_shapes": [
                "1-for-2 meaningful supported-position players inside frozen V3 composition envelope",
                "1-for-3 meaningful supported-position players inside frozen V4 composition envelope",
            ],
            "picks_excluded": True,
            "multi_vs_multi_excluded": True,
            "package_asset_at_or_above_target_excluded": True,
            "unsupported_composition_fails_closed": True,
            "tiny_assets_keep_raw_fv_but_not_size_or_composition_classification": True,
            "completed_trades_are_revealed_preference_not_exact_fair_value_labels": True,
            "automatic_production_change_allowed": False,
        },
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
else:
    manifest = read_json(MANIFEST)
    if manifest.get("status") != "exact_live_oos_release_manifest":
        raise RuntimeError("Unexpected V1.5 release manifest status")
    if manifest.get("frozen") is not True:
        raise RuntimeError("V1.5 release manifest is not frozen")
    if manifest.get("release_id") != "package-adjustment-exact-live-v1.5-step6-realignment":
        raise RuntimeError("Unexpected active V1.5 release id")
    if manifest.get("production_revision_at_release") != "v1.5-audit-step6-scope-ui-idp":
        raise RuntimeError("V1.5 manifest production revision mismatch")
    if manifest.get("exact_live_formula_sha256") != formula_fingerprint:
        raise RuntimeError(
            "Exact live Package Adjustment formula changed since V1.5 release. "
            "A new reviewed release manifest is required."
        )
    if manifest.get("exact_live_formula") != exact_formula:
        raise RuntimeError("Exact live formula payload differs from frozen V1.5 manifest")
    current_workflow_sha256 = sha256(WORKFLOW)
    frozen_workflow_sha256 = manifest["release_artifact_sha256"]["monitor_workflow"]
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    transition_dispatcher_marker = "PACKAGE_ADJUSTMENT_OOS_DISPATCHER_V1"
    workflow_identity_ok = (
        current_workflow_sha256 == frozen_workflow_sha256
        or transition_dispatcher_marker in workflow_text
    )
    if not workflow_identity_ok:
        raise RuntimeError(
            "Exact-live monitor workflow changed since V1.5 release and is not "
            "the reviewed transition dispatcher workflow"
        )
    if sha256(PREVIOUS_MANIFEST) != manifest.get("previous_release_manifest_sha256"):
        raise RuntimeError("Original V1.4 release manifest drift detected")
    if live.get("exact_live_prospective_monitoring") is not True:
        raise RuntimeError("Live metadata no longer marks exact-live monitoring active")
    hardening = live.get("audit_hardening") or {}
    if hardening.get("exact_live_monitor_revision_aligned") is not True:
        raise RuntimeError("Exact-live monitor is not marked revision-aligned")
    if hardening.get("step6_monitor_realign_required") is not False:
        raise RuntimeError("Step 6 monitor realignment is unexpectedly still required")

# Self-test exact composition behavior from the frozen manifest.
f = manifest["exact_live_formula"]
if f["scope_contract"]["supported_player_positions"] != ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]:
    raise RuntimeError("Exact-live supported-position self-test failed")
if "K" in f["scope_contract"]["supported_player_positions"]:
    raise RuntimeError("K must remain outside exact-live Package Adjustment scope")
ok2, _ = composition_supported([51.0, 49.0], 2, f)
bad2, _ = composition_supported([60.0, 40.0], 2, f)
ok3, _ = composition_supported([45.0, 33.0, 22.0], 3, f)
bad3, _ = composition_supported([55.0, 24.0, 21.0], 3, f)
if not ok2 or bad2 or not ok3 or bad3:
    raise RuntimeError("Exact-live composition self-test failed")

rows = [
    classify_trade(t, manifest)
    for t in (evidence.get("trades") or {}).values()
]
rows.sort(key=lambda r: int(r.get("created_epoch_ms") or 0))
observations = [
    r for r in rows if r.get("eligible_for_exact_live_oos")
]

# Every included observation must prove the anti-hindsight cutoff contract.
for obs in observations:
    if int(obs["created_epoch_ms"]) <= int(manifest["oos_cutoff_epoch_ms"]):
        raise RuntimeError("OOS cutoff violation")
    if float(obs["pretrade_snapshot_age_hours"]) > MAX_PRETRADE_SNAPSHOT_AGE_HOURS:
        raise RuntimeError("Pretrade snapshot age violation")

summary = summarize(observations, rows)

result = {
    "schema_version": 1,
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
    },
    "evidence_stream": {
        "source": str(EVIDENCE),
        "source_generated_at_utc": evidence["generated_at_utc"],
        "source_age_hours_at_evaluation": evidence_age_hours,
        "max_allowed_staleness_hours": allowed_evidence_staleness_hours,
        "scheduled_run_max_allowed_staleness_hours": MAX_EVIDENCE_STREAM_STALENESS_HOURS,
        "initial_alignment_max_allowed_staleness_hours": INITIAL_ALIGNMENT_MAX_EVIDENCE_STREAM_STALENESS_HOURS,
        "anti_hindsight_contract_verified": True,
    },
    "methodology": manifest["methodology"],
    "summary": summary,
    "observations": observations,
    "all_trade_classifications": rows,
    "interpretation_guardrail": (
        "Completed trades are revealed-preference observations, not exact "
        "fair-value labels. OOS maturity gates trigger human review only. "
        "This monitor never auto-adjusts, disables, promotes, or recalibrates "
        "the live Package Adjustment."
    ),
}
OUT_JSON.write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

def fmt(value, digits=3):
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"

gates = summary["evidence_maturity_gates"]
md = [
    "# Package Adjustment — Exact-Live Prospective/OOS Monitor (V1.5)",
    "",
    f"Generated: {result['generated_at_utc']}",
    "",
    "## Release",
    "",
    f"- Release ID: **{manifest['release_id']}**",
    f"- OOS cutoff: **{manifest['released_at_utc']}**",
    f"- Production revision at release: **{manifest['production_revision_at_release']}**",
    f"- Exact-live formula SHA256: `{manifest['exact_live_formula_sha256']}`",
    "",
    "Only trades strictly after the release cutoff can enter the OOS sample.",
    "The evaluator uses the exact live V3 size2 curve, V3 51/49 composition",
    "envelope, V4 size3 multiplier, V4 45/33/22 composition envelope,",
    "meaningful-piece threshold, tiny-padding behavior, and fail-closed scope.",
    "",
    "## Current evidence",
    "",
    f"- Logged trades classified: **{summary['logged_trade_count']}**",
    f"- Supported exact-live OOS trades: **{summary['supported_oos_trade_count']}**",
    f"- Distinct concentrated targets: **{summary['distinct_target_count']}**",
    f"- Size2 OOS trades: **{summary['by_package_size']['2']['trade_count']}**",
    f"- Size3 OOS trades: **{summary['by_package_size']['3']['trade_count']}**",
    f"- Evidence stream age: **{fmt(evidence_age_hours, 2)} hours**",
    "",
    "## Evidence maturity gates",
    "",
    f"- Supported trades >= {MIN_OOS_SUPPORTED_TRADES}: **{gates['passed']['supported_oos_trades']}**",
    f"- Distinct targets >= {MIN_DISTINCT_TARGETS}: **{gates['passed']['distinct_targets']}**",
    f"- Size2 trades >= {MIN_SIZE2_TRADES}: **{gates['passed']['size2_coverage']}**",
    f"- Size3 trades >= {MIN_SIZE3_TRADES}: **{gates['passed']['size3_coverage']}**",
    f"- All maturity gates passed: **{gates['all_passed']}**",
    "",
    "These gates only indicate that enough prospective evidence exists for",
    "another human review. They do **not** authorize an automatic formula change.",
    "",
    "## Audit state",
    "",
    "Exact-live monitoring is revision-aligned to production V1.5 and its release manifest is frozen.",
    "Step 6 is complete. The next audit gate is **Step 7 — Permanent Package Adjustment repo regression suite**.",
    "",
]
OUT_MD.write_text("\n".join(md), encoding="utf-8")

print("Step 4 exact-live OOS monitoring complete.")
print("First release:", first_release)
print("Release:", manifest["release_id"])
print("Formula SHA256:", manifest["exact_live_formula_sha256"])
print("Supported OOS trades:", summary["supported_oos_trade_count"])
print("Maturity gates all passed:", gates["all_passed"])

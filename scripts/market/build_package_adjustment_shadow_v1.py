#!/usr/bin/env python3
"""Package Adjustment Shadow V1 — research only.

Converts Package Preference V3 indifference diagnostics into three explicit,
non-production candidate adjustment curves:

1) simple_ratio_plus_size
   - constant 2-player / 3-player indifference multipliers from V3's
     ratio_plus_size model.
2) target_sensitive_monotonic
   - preferred shadow candidate for torture testing.
   - piecewise log-FV interpolation through V3 ratio_plus_size_target
     indifference reference points.
   - clamped outside the observed target-FV reference band; no extrapolation.
3) target_interaction_diagnostic_only
   - lowest-AIC V3 candidate, retained for diagnostics only because its
     target interaction is not economically monotonic/stable enough to promote.

No player Fundamental Value is changed. No Market Value, Team Utility, roster
utility, draft-pick liquidity, or live trade verdict is changed. The output is
only a shadow "trade-equivalent concentrated value" for the exact V3-supported
shape: one concentrated player versus 2 or 3 meaningful lesser players.

Meaningful package piece = at least 6% of target FV, matching V3's generator
minimum. Tiny throw-ins do not manufacture a 3-player penalty.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIAG = ROOT / "research" / "package-adjustment-v3" / "package_vote_v3_fit_diagnostics.json"
V3_RESULTS = ROOT / "research" / "package-adjustment-v3" / "package_vote_v3_results.json"
V3_CHALLENGES = ROOT / "research" / "package-adjustment-v3" / "package_vote_challenges_v3.json"
OUT_DIR = ROOT / "research" / "package-adjustment-shadow-v1"
OUT_JSON = OUT_DIR / "package_adjustment_shadow_v1.json"
OUT_MD = OUT_DIR / "package_adjustment_shadow_v1.md"

MIN_MEANINGFUL_PIECE_TO_TARGET = 0.06
SUPPORTED_PACKAGE_SIZES = (2, 3)
TESTED_RATIO_MIN = 1.10
TESTED_RATIO_MAX = 1.85


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite_positive(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x > 0 else None


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def extract_reference_points(diag_doc, model_name, package_size):
    estimates = (
        diag_doc.get("diagnostics", {})
        .get("indifference_estimates", {})
        .get(model_name, {})
    )
    key = f"size{int(package_size)}_ratio_50"
    refs = []
    for label in ("p25", "median", "p75", "p90"):
        row = estimates.get(label) or {}
        fv = finite_positive(row.get("target_fv"))
        ratio = finite_positive(row.get(key))
        if fv is None or ratio is None:
            raise RuntimeError(f"missing {model_name}/{label}/{key} diagnostic")
        refs.append({"label": label, "target_fv": fv, "ratio": ratio})
    refs.sort(key=lambda r: r["target_fv"])
    return refs


def log_interp_clamped(target_fv, refs):
    target = finite_positive(target_fv)
    if target is None:
        raise ValueError("target_fv must be positive")
    if target <= refs[0]["target_fv"]:
        return float(refs[0]["ratio"]), "clamped_low"
    if target >= refs[-1]["target_fv"]:
        return float(refs[-1]["ratio"]), "clamped_high"
    lx = math.log(target)
    for a, b in zip(refs, refs[1:]):
        if a["target_fv"] <= target <= b["target_fv"]:
            la, lb = math.log(a["target_fv"]), math.log(b["target_fv"])
            t = 0.0 if lb == la else (lx - la) / (lb - la)
            ratio = a["ratio"] + t * (b["ratio"] - a["ratio"])
            return float(ratio), "interpolated"
    raise AssertionError("interpolation interval not found")


def simple_multiplier(diag_doc, package_size):
    estimates = diag_doc["diagnostics"]["indifference_estimates"]["ratio_plus_size"]
    key = f"size{int(package_size)}_ratio_50"
    ratio = finite_positive(estimates["median"].get(key))
    if ratio is None:
        raise RuntimeError(f"missing simple {key}")
    return ratio


def candidate_multiplier(diag_doc, candidate, target_fv, package_size):
    if package_size not in SUPPORTED_PACKAGE_SIZES:
        raise ValueError("unsupported package size")
    if candidate == "simple_ratio_plus_size":
        return simple_multiplier(diag_doc, package_size), "constant"
    if candidate == "target_sensitive_monotonic":
        refs = extract_reference_points(diag_doc, "ratio_plus_size_target", package_size)
        return log_interp_clamped(target_fv, refs)
    if candidate == "target_interaction_diagnostic_only":
        refs = extract_reference_points(diag_doc, "ratio_plus_size_target_interaction", package_size)
        return log_interp_clamped(target_fv, refs)
    raise ValueError(f"unknown candidate {candidate}")


def classify_package(target_fv, package_values):
    target = finite_positive(target_fv)
    if target is None:
        return {"supported": False, "reason": "invalid_target_fv"}
    parsed = []
    for value in package_values:
        x = finite_positive(value)
        if x is not None:
            parsed.append(x)
    if not parsed:
        return {"supported": False, "reason": "empty_package"}
    if any(x >= target for x in parsed):
        return {
            "supported": False,
            "reason": "package_contains_asset_at_or_above_target",
            "raw_package_fv": sum(parsed),
        }
    threshold = target * MIN_MEANINGFUL_PIECE_TO_TARGET
    meaningful = [x for x in parsed if x >= threshold]
    tiny = [x for x in parsed if x < threshold]
    size = len(meaningful)
    if size == 1:
        return {
            "supported": False,
            "reason": "effective_one_for_one_null",
            "meaningful_package_size": size,
            "meaningful_values": meaningful,
            "tiny_values_ignored_for_size": tiny,
            "raw_package_fv": sum(parsed),
        }
    if size not in SUPPORTED_PACKAGE_SIZES:
        return {
            "supported": False,
            "reason": "unsupported_meaningful_package_size",
            "meaningful_package_size": size,
            "meaningful_values": meaningful,
            "tiny_values_ignored_for_size": tiny,
            "raw_package_fv": sum(parsed),
        }
    return {
        "supported": True,
        "reason": "v3_supported_shape",
        "meaningful_package_size": size,
        "meaningful_values": meaningful,
        "tiny_values_ignored_for_size": tiny,
        "raw_package_fv": sum(parsed),
        "raw_package_to_target_ratio": sum(parsed) / target,
    }


def evaluate_one_vs_package(diag_doc, target_fv, package_values, candidate):
    target = finite_positive(target_fv)
    shape = classify_package(target_fv, package_values)
    if target is None or not shape.get("supported"):
        return {
            "candidate": candidate,
            "supported": False,
            "reason": shape.get("reason", "invalid_target_fv"),
            "value_adjustment": 0.0,
            "trade_equivalent_target_value": target or 0.0,
            "shape": shape,
        }
    size = int(shape["meaningful_package_size"])
    multiplier, interpolation_status = candidate_multiplier(
        diag_doc, candidate, target, size
    )
    multiplier = max(1.0, float(multiplier))
    adjustment = target * (multiplier - 1.0)
    extrapolated_multiplier = not (TESTED_RATIO_MIN <= multiplier <= TESTED_RATIO_MAX)
    evidence = (
        "within_v3_tested_ratio_range"
        if not extrapolated_multiplier
        else "model_implied_beyond_v3_tested_ratio_range"
    )
    return {
        "candidate": candidate,
        "supported": True,
        "reason": "v3_supported_shape",
        "target_fv": target,
        "meaningful_package_size": size,
        "raw_package_fv": shape["raw_package_fv"],
        "raw_package_to_target_ratio": shape["raw_package_to_target_ratio"],
        "indifference_multiplier": multiplier,
        "value_adjustment": adjustment,
        "trade_equivalent_target_value": target + adjustment,
        "interpolation_status": interpolation_status,
        "evidence_status": evidence,
        "tiny_values_ignored_for_size": shape["tiny_values_ignored_for_size"],
    }


def evaluate_trade(diag_doc, side_a_values, side_b_values, candidate):
    # Exact V3 shape only: one player vs a package. Reverse orientation is okay.
    a = [x for x in (finite_positive(v) for v in side_a_values) if x is not None]
    b = [x for x in (finite_positive(v) for v in side_b_values) if x is not None]
    if len(a) == 1 and len(b) >= 1:
        r = evaluate_one_vs_package(diag_doc, a[0], b, candidate)
        r["concentrated_side"] = "A"
        return r
    if len(b) == 1 and len(a) >= 1:
        r = evaluate_one_vs_package(diag_doc, b[0], a, candidate)
        r["concentrated_side"] = "B"
        return r
    return {
        "candidate": candidate,
        "supported": False,
        "reason": "unsupported_multi_vs_multi_or_empty_shape",
        "value_adjustment": 0.0,
        "concentrated_side": None,
    }


def validate_source(diag_doc, results_doc):
    if not diag_doc.get("diagnostic_gates", {}).get("all_passed"):
        raise RuntimeError("V3 diagnostic gates are not all passed")
    if not results_doc.get("summary", {}).get("diagnostic_data_gates", {}).get("all_passed"):
        raise RuntimeError("V3 result gates are not all passed")
    if diag_doc.get("diagnostics", {}).get("conclusion", {}).get("production_promotion_allowed") is not False:
        raise RuntimeError("unexpected V3 production-promotion state")
    required = {
        "ratio_plus_size",
        "ratio_plus_size_target",
        "ratio_plus_size_target_interaction",
    }
    models = set(diag_doc.get("diagnostics", {}).get("models", {}))
    estimates = set(diag_doc.get("diagnostics", {}).get("indifference_estimates", {}))
    if not required.issubset(models) or not required.issubset(estimates):
        raise RuntimeError("required V3 candidate models/estimates missing")


def torture_tests(diag_doc):
    tests = {}

    # 1-for-1 null via only one meaningful package piece.
    r = evaluate_one_vs_package(diag_doc, 8000, [7000], "target_sensitive_monotonic")
    assert not r["supported"] and r["value_adjustment"] == 0
    tests["one_for_one_null"] = "PASS"

    # Multi-v-multi is deliberately unsupported, preventing accidental double tax.
    r = evaluate_trade(diag_doc, [5000, 2000], [4500, 2500], "target_sensitive_monotonic")
    assert not r["supported"] and r["value_adjustment"] == 0
    tests["balanced_multi_vs_multi_unsupported_null"] = "PASS"

    # Package with an equal/better asset is outside V3's construction domain.
    r = evaluate_one_vs_package(diag_doc, 5000, [5000, 1000], "target_sensitive_monotonic")
    assert not r["supported"]
    tests["package_with_equal_or_better_asset_unsupported"] = "PASS"

    # Four meaningful pieces are not extrapolated from 2/3-player evidence.
    r = evaluate_one_vs_package(diag_doc, 5000, [1500, 1400, 1300, 1200], "target_sensitive_monotonic")
    assert not r["supported"]
    tests["four_meaningful_pieces_unsupported"] = "PASS"

    # Tiny third piece below 6% target cannot manufacture a size-3 penalty.
    two = evaluate_one_vs_package(diag_doc, 5000, [3000, 2000], "target_sensitive_monotonic")
    padded = evaluate_one_vs_package(diag_doc, 5000, [3000, 2000, 100], "target_sensitive_monotonic")
    assert two["meaningful_package_size"] == padded["meaningful_package_size"] == 2
    assert abs(two["indifference_multiplier"] - padded["indifference_multiplier"]) < 1e-12
    tests["tiny_throw_in_padding_resistance"] = "PASS"

    # At same target, 3 meaningful pieces must require more than 2 in monotonic candidate.
    two = evaluate_one_vs_package(diag_doc, 5000, [3000, 2000], "target_sensitive_monotonic")
    three = evaluate_one_vs_package(diag_doc, 5000, [2200, 1600, 1200], "target_sensitive_monotonic")
    assert three["indifference_multiplier"] > two["indifference_multiplier"]
    tests["three_piece_premium_above_two_piece"] = "PASS"

    # The target-sensitive model is required to be nondecreasing over its own
    # empirical reference points for each supported size.
    for size in SUPPORTED_PACKAGE_SIZES:
        refs = extract_reference_points(diag_doc, "ratio_plus_size_target", size)
        ratios = [r["ratio"] for r in refs]
        assert all(b >= a - 1e-12 for a, b in zip(ratios, ratios[1:]))
    tests["target_sensitive_reference_monotonicity"] = "PASS"

    # Clamp prevents unvalidated target-FV extrapolation.
    refs2 = extract_reference_points(diag_doc, "ratio_plus_size_target", 2)
    low, _ = candidate_multiplier(diag_doc, "target_sensitive_monotonic", 1000, 2)
    high, _ = candidate_multiplier(diag_doc, "target_sensitive_monotonic", 20000, 2)
    assert abs(low - refs2[0]["ratio"]) < 1e-12
    assert abs(high - refs2[-1]["ratio"]) < 1e-12
    tests["target_fv_extrapolation_clamped"] = "PASS"

    # Simple candidate must reproduce the V3 diagnostic's median multipliers.
    for size in SUPPORTED_PACKAGE_SIZES:
        m = simple_multiplier(diag_doc, size)
        direct = diag_doc["diagnostics"]["indifference_estimates"]["ratio_plus_size"]["median"][f"size{size}_ratio_50"]
        assert abs(m - float(direct)) < 1e-12
    tests["simple_candidate_matches_v3_diagnostic"] = "PASS"

    # Adjustment can never be negative.
    for candidate in (
        "simple_ratio_plus_size",
        "target_sensitive_monotonic",
        "target_interaction_diagnostic_only",
    ):
        r = evaluate_one_vs_package(diag_doc, 5000, [3000, 2000], candidate)
        assert r["value_adjustment"] >= 0
    tests["nonnegative_adjustment"] = "PASS"

    # Reverse orientation must preserve the same concentrated-side adjustment.
    ab = evaluate_trade(diag_doc, [5000], [3000, 2000], "target_sensitive_monotonic")
    ba = evaluate_trade(diag_doc, [3000, 2000], [5000], "target_sensitive_monotonic")
    assert ab["concentrated_side"] == "A" and ba["concentrated_side"] == "B"
    assert abs(ab["value_adjustment"] - ba["value_adjustment"]) < 1e-12
    tests["side_swap_symmetry"] = "PASS"

    # V3's current 3-player estimate is mostly beyond the tested 1.85 endpoint;
    # preserve this as a warning rather than silently declaring it calibrated.
    mid3 = evaluate_one_vs_package(diag_doc, 5049.5, [2200, 1600, 1249.5], "target_sensitive_monotonic")
    assert mid3["evidence_status"] == "model_implied_beyond_v3_tested_ratio_range"
    tests["three_player_extrapolation_is_explicit"] = "PASS"

    return tests


def reference_table(diag_doc):
    # Use the V3 target reference values so candidate comparisons are directly
    # tied back to the diagnostic artifact.
    refs = extract_reference_points(diag_doc, "ratio_plus_size_target", 2)
    rows = []
    for ref in refs:
        target = ref["target_fv"]
        row = {"reference": ref["label"], "target_fv": target, "candidates": {}}
        for candidate in (
            "simple_ratio_plus_size",
            "target_sensitive_monotonic",
            "target_interaction_diagnostic_only",
        ):
            c = {}
            for size in SUPPORTED_PACKAGE_SIZES:
                mult, status = candidate_multiplier(diag_doc, candidate, target, size)
                c[str(size)] = {
                    "indifference_multiplier": mult,
                    "value_adjustment": target * (mult - 1.0),
                    "trade_equivalent_target_value": target * mult,
                    "interpolation_status": status,
                    "within_v3_tested_ratio_range": TESTED_RATIO_MIN <= mult <= TESTED_RATIO_MAX,
                }
            row["candidates"][candidate] = c
        rows.append(row)
    return rows



def catalog_replay(diag_doc):
    doc = read_json(V3_CHALLENGES)
    challenges = doc.get("challenges") or []
    if len(challenges) < 140:
        raise RuntimeError("V3 frozen challenge catalog unexpectedly small")
    rows = []
    for ch in challenges:
        target = float(ch["target_fv"])
        package_values = [float(p["fv"]) for p in ch["package"]]
        for candidate in (
            "simple_ratio_plus_size",
            "target_sensitive_monotonic",
            "target_interaction_diagnostic_only",
        ):
            r = evaluate_one_vs_package(diag_doc, target, package_values, candidate)
            if not r.get("supported"):
                raise RuntimeError(f"frozen V3 challenge not supported by shadow: {ch['id']}")
            rows.append({
                "challenge_id": ch["id"],
                "target_tier": ch.get("target_tier"),
                "target_pos": ch.get("target", {}).get("pos"),
                "package_size": int(ch["package_size"]),
                "ratio_target": float(ch["ratio_target"]),
                "raw_ratio": float(ch["raw_package_to_target_ratio"]),
                "candidate": candidate,
                "indifference_multiplier": r["indifference_multiplier"],
                "value_adjustment": r["value_adjustment"],
                "trade_equivalent_target_value": r["trade_equivalent_target_value"],
                "raw_package_fv": r["raw_package_fv"],
                "package_minus_shadow_required_fv": r["raw_package_fv"] - r["trade_equivalent_target_value"],
                "package_meets_or_exceeds_shadow_requirement": r["raw_package_fv"] >= r["trade_equivalent_target_value"],
                "evidence_status": r["evidence_status"],
            })

    summary = {}
    for candidate in sorted({r["candidate"] for r in rows}):
        summary[candidate] = {}
        for size in SUPPORTED_PACKAGE_SIZES:
            sub = [r for r in rows if r["candidate"] == candidate and r["package_size"] == size]
            summary[candidate][str(size)] = {
                "challenge_count": len(sub),
                "median_indifference_multiplier": statistics.median(r["indifference_multiplier"] for r in sub),
                "median_value_adjustment": statistics.median(r["value_adjustment"] for r in sub),
                "offers_meeting_shadow_requirement_pct": 100.0 * sum(r["package_meets_or_exceeds_shadow_requirement"] for r in sub) / len(sub),
                "model_implied_beyond_tested_ratio_range_pct": 100.0 * sum(r["evidence_status"] == "model_implied_beyond_v3_tested_ratio_range" for r in sub) / len(sub),
            }
    return {
        "challenge_count": len(challenges),
        "row_count": len(rows),
        "summary": summary,
        "rows": rows,
    }

def build_payload(diag_doc, results_doc):
    validate_source(diag_doc, results_doc)
    tests = torture_tests(diag_doc)
    replay = catalog_replay(diag_doc)
    boot = diag_doc["diagnostics"].get("voter_cluster_bootstrap", {})
    conclusion = diag_doc["diagnostics"].get("conclusion", {})
    simple_2 = simple_multiplier(diag_doc, 2)
    simple_3 = simple_multiplier(diag_doc, 3)

    p25_2 = extract_reference_points(diag_doc, "ratio_plus_size_target", 2)[0]
    p90_2 = extract_reference_points(diag_doc, "ratio_plus_size_target", 2)[-1]
    p25_3 = extract_reference_points(diag_doc, "ratio_plus_size_target", 3)[0]
    p90_3 = extract_reference_points(diag_doc, "ratio_plus_size_target", 3)[-1]

    payload = {
        "schema_version": 1,
        "status": "research_only_shadow",
        "method": "package-adjustment-shadow-v1-from-v3-indifference",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "consumer_changed": False,
        "fundamental_value_consumer_changed": False,
        "market_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "trade_verdict_consumer_changed": False,
        "production_formula_enabled": False,
        "production_promotion_allowed": False,
        "source": {
            "v3_diagnostics_sha256": sha256(DIAG),
            "v3_results_sha256": sha256(V3_RESULTS),
            "v3_challenges_sha256": sha256(V3_CHALLENGES),
            "counted_votes": diag_doc.get("data", {}).get("counted_votes"),
            "unique_voters": diag_doc.get("data", {}).get("unique_voters"),
            "distinct_challenges": diag_doc.get("data", {}).get("distinct_challenges"),
            "distinct_targets": diag_doc.get("data", {}).get("distinct_targets"),
            "v3_lowest_aic_model": conclusion.get("lowest_aic_model"),
            "v3_warning": conclusion.get("warnings", []),
        },
        "applicability": {
            "supported_shape": "one concentrated player vs 2 or 3 meaningful lesser players",
            "meaningful_piece_min_target_share": MIN_MEANINGFUL_PIECE_TO_TARGET,
            "all_package_pieces_must_be_below_target_fv": True,
            "draft_picks_supported": False,
            "multi_vs_multi_supported": False,
            "four_plus_meaningful_package_pieces_supported": False,
            "roster_specific_effects_included": False,
            "team_utility_separate": True,
        },
        "candidates": {
            "simple_ratio_plus_size": {
                "role": "baseline_shadow_candidate",
                "source_model": "ratio_plus_size",
                "size2_multiplier": simple_2,
                "size3_multiplier": simple_3,
                "size2_evidence": "within_tested_range",
                "size3_evidence": "mostly_extrapolated_beyond_tested_range",
                "eligible_for_torture_testing": True,
                "eligible_for_production": False,
            },
            "target_sensitive_monotonic": {
                "role": "preferred_shadow_candidate_for_torture_testing",
                "source_model": "ratio_plus_size_target",
                "interpolation": "piecewise_linear_in_log_target_fv_clamped_to_p25_p90_reference_band",
                "size2_reference_range": {
                    "target_fv_low": p25_2["target_fv"],
                    "multiplier_low": p25_2["ratio"],
                    "target_fv_high": p90_2["target_fv"],
                    "multiplier_high": p90_2["ratio"],
                },
                "size3_reference_range": {
                    "target_fv_low": p25_3["target_fv"],
                    "multiplier_low": p25_3["ratio"],
                    "target_fv_high": p90_3["target_fv"],
                    "multiplier_high": p90_3["ratio"],
                },
                "eligible_for_torture_testing": True,
                "eligible_for_production": False,
            },
            "target_interaction_diagnostic_only": {
                "role": "diagnostic_only_lowest_aic_candidate",
                "source_model": "ratio_plus_size_target_interaction",
                "reason_not_preferred": "target interaction is not monotonic/economically stable enough for promotion",
                "eligible_for_torture_testing": True,
                "eligible_for_production": False,
            },
        },
        "bootstrap_evidence": {
            "ratio_positive_rate_pct": boot.get("ratio_positive_rate_pct"),
            "size3_negative_rate_pct": boot.get("size3_negative_rate_pct"),
            "median_target_size2_indifference_ratio": boot.get("median_target_size2_indifference_ratio"),
            "median_target_size3_indifference_ratio": boot.get("median_target_size3_indifference_ratio"),
            "size2_indifference_within_tested_range_pct": boot.get("size2_indifference_within_tested_range_pct"),
            "size3_indifference_within_tested_range_pct": boot.get("size3_indifference_within_tested_range_pct"),
        },
        "reference_table": reference_table(diag_doc),
        "frozen_v3_catalog_replay": replay,
        "torture_tests": tests,
        "torture_tests_all_passed": all(v == "PASS" for v in tests.values()),
        "recommendation": {
            "shadow_candidate_to_carry_forward": "target_sensitive_monotonic",
            "two_player_signal_status": "strong_shadow_signal_within_tested_ratio_range",
            "three_player_signal_status": "strong_directional_size_penalty_but_indifference_level_requires_higher_ratio_extension",
            "next_validation": (
                "Continue V3/OOS collection and extend 3-player indifference testing above 1.85x before any live promotion."
            ),
        },
    }
    return payload


def write_report(payload):
    lines = [
        "# Package Adjustment Shadow V1",
        "",
        "**Status: RESEARCH ONLY — no live calculator consumer changed.**",
        "",
        "This shadow converts V3 package-vote indifference evidence into candidate KTC-style value adjustments without changing player FV.",
        "",
        "## Supported shape",
        "",
        "- One concentrated player versus 2 or 3 meaningful lesser players.",
        f"- A meaningful package piece must be at least `{MIN_MEANINGFUL_PIECE_TO_TARGET:.0%}` of target FV, matching V3 construction.",
        "- Tiny throw-ins do not increase package size.",
        "- Picks, 4+ meaningful pieces, and multi-v-multi are not modeled.",
        "",
        "## Candidate models",
        "",
        "### 1. Simple ratio + package size",
        "",
        f"- 2-player indifference multiplier: `{payload['candidates']['simple_ratio_plus_size']['size2_multiplier']:.3f}x`",
        f"- 3-player indifference multiplier: `{payload['candidates']['simple_ratio_plus_size']['size3_multiplier']:.3f}x`",
        "",
        "### 2. Target-sensitive monotonic — preferred shadow candidate",
        "",
        "Uses V3's monotonic ratio+size+target model and interpolates only inside the empirical p25-p90 target-FV band; values outside are clamped rather than extrapolated.",
        "",
        "### 3. Target interaction — diagnostic only",
        "",
        "Retains the lowest-AIC V3 interaction model for comparison, but it is not promotion-eligible because its target interaction is not economically monotonic enough.",
        "",
        "## Reference adjustments",
        "",
        "| Target ref | Target FV | Monotonic 2p multiplier | 2p adjustment | Monotonic 3p multiplier | 3p adjustment |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["reference_table"]:
        m = row["candidates"]["target_sensitive_monotonic"]
        lines.append(
            f"| {row['reference']} | {row['target_fv']:.0f} | "
            f"{m['2']['indifference_multiplier']:.3f}x | {m['2']['value_adjustment']:.0f} | "
            f"{m['3']['indifference_multiplier']:.3f}x | {m['3']['value_adjustment']:.0f} |"
        )
    replay = payload["frozen_v3_catalog_replay"]["summary"]
    lines += [
        "",
        "## Frozen V3 challenge-catalog replay",
        "",
        f"Replayed all `{payload['frozen_v3_catalog_replay']['challenge_count']}` frozen V3 trade shapes through all three candidates.",
        "",
        "| Candidate | Size | Challenges | Median multiplier | Median adjustment | Offers meeting shadow requirement | Beyond tested ratio range |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for candidate in ("simple_ratio_plus_size", "target_sensitive_monotonic", "target_interaction_diagnostic_only"):
        for size in SUPPORTED_PACKAGE_SIZES:
            x = replay[candidate][str(size)]
            lines.append(
                f"| {candidate} | {size} | {x['challenge_count']} | {x['median_indifference_multiplier']:.3f}x | "
                f"{x['median_value_adjustment']:.0f} | {x['offers_meeting_shadow_requirement_pct']:.1f}% | "
                f"{x['model_implied_beyond_tested_ratio_range_pct']:.1f}% |"
            )
    lines += [
        "",
        "## Evidence guardrails",
        "",
        f"- Raw-ratio coefficient positive in voter-cluster bootstrap: `{payload['bootstrap_evidence']['ratio_positive_rate_pct']}%`",
        f"- 3-player coefficient negative in voter-cluster bootstrap: `{payload['bootstrap_evidence']['size3_negative_rate_pct']}%`",
        f"- 2-player indifference estimates within tested ratio range: `{payload['bootstrap_evidence']['size2_indifference_within_tested_range_pct']}%`",
        f"- 3-player indifference estimates within tested ratio range: `{payload['bootstrap_evidence']['size3_indifference_within_tested_range_pct']}%`",
        "- Therefore the 2-player shadow is materially better identified than the 3-player indifference level.",
        "",
        "## Torture tests",
        "",
    ]
    for name, status in payload["torture_tests"].items():
        lines.append(f"- {name}: `{status}`")
    lines += [
        "",
        "## Recommendation",
        "",
        "Carry `target_sensitive_monotonic` forward as the shadow candidate. Do not promote live yet. Continue V3/OOS collection and extend the 3-player experiment above 1.85x.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def write_outputs():
    diag_doc = read_json(DIAG)
    results_doc = read_json(V3_RESULTS)
    payload = build_payload(diag_doc, results_doc)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(payload)
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    return payload


def check_outputs():
    if not OUT_JSON.exists() or not OUT_MD.exists():
        raise RuntimeError("shadow outputs missing")
    payload = read_json(OUT_JSON)
    assert payload["status"] == "research_only_shadow"
    assert payload["production_formula_enabled"] is False
    assert payload["production_promotion_allowed"] is False
    assert payload["consumer_changed"] is False
    assert payload["fundamental_value_consumer_changed"] is False
    assert payload["market_value_consumer_changed"] is False
    assert payload["team_utility_consumer_changed"] is False
    assert payload["trade_verdict_consumer_changed"] is False
    assert payload["torture_tests_all_passed"] is True
    assert payload["source"]["v3_diagnostics_sha256"] == sha256(DIAG)
    assert payload["source"]["v3_results_sha256"] == sha256(V3_RESULTS)
    assert payload["source"]["v3_challenges_sha256"] == sha256(V3_CHALLENGES)
    assert payload["frozen_v3_catalog_replay"]["challenge_count"] >= 140
    assert payload["recommendation"]["shadow_candidate_to_carry_forward"] == "target_sensitive_monotonic"
    print("Package Adjustment Shadow V1 check passed.")


def synthetic_diag_for_selftest():
    # Mirrors the current V3 result shape but is deliberately tiny and local.
    def rows(a2, a3):
        fvs = [4000.0, 5000.0, 6000.0, 7000.0]
        labels = ["p25", "median", "p75", "p90"]
        return {
            label: {
                "target_fv": fv,
                "size2_ratio_50": a2[i],
                "size3_ratio_50": a3[i],
            }
            for i, (label, fv) in enumerate(zip(labels, fvs))
        }
    return {
        "diagnostic_gates": {"all_passed": True},
        "diagnostics": {
            "conclusion": {"production_promotion_allowed": False, "lowest_aic_model": "ratio_plus_size_target_interaction", "warnings": []},
            "models": {
                "ratio_plus_size": {},
                "ratio_plus_size_target": {},
                "ratio_plus_size_target_interaction": {},
            },
            "indifference_estimates": {
                "ratio_plus_size": rows([1.46]*4, [1.99]*4),
                "ratio_plus_size_target": rows([1.40,1.48,1.54,1.59], [1.90,2.02,2.09,2.16]),
                "ratio_plus_size_target_interaction": rows([1.41,1.50,1.52,1.54], [2.10,1.92,1.87,1.84]),
            },
            "voter_cluster_bootstrap": {
                "ratio_positive_rate_pct": 100.0,
                "size3_negative_rate_pct": 100.0,
                "size2_indifference_within_tested_range_pct": 100.0,
                "size3_indifference_within_tested_range_pct": 5.0,
            },
        },
    }


def selftest():
    diag = synthetic_diag_for_selftest()
    # Core interpolation / padding / applicability tests on synthetic doc.
    tests = torture_tests(diag)
    assert all(v == "PASS" for v in tests.values())
    mid, status = candidate_multiplier(diag, "target_sensitive_monotonic", 5000, 2)
    assert status == "interpolated" or abs(mid - 1.48) < 1e-12
    r = evaluate_one_vs_package(diag, 5000, [3000, 2000], "simple_ratio_plus_size")
    assert r["supported"] and abs(r["indifference_multiplier"] - 1.46) < 1e-12
    print("Package Adjustment Shadow V1 self-test passed.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    if args.write:
        write_outputs()
    if args.check:
        check_outputs()
    if not (args.selftest or args.write or args.check):
        write_outputs()


if __name__ == "__main__":
    main()

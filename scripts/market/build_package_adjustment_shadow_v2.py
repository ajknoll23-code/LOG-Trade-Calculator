#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V3_DIAG = ROOT / "research" / "package-adjustment-v3" / "package_vote_v3_fit_diagnostics.json"
V3_RESULTS = ROOT / "research" / "package-adjustment-v3" / "package_vote_v3_results.json"
V3_CHALLENGES = ROOT / "research" / "package-adjustment-v3" / "package_vote_challenges_v3.json"
V4_DIAG = ROOT / "research" / "package-adjustment-v4" / "package_vote_v4_fit_diagnostics.json"
V4_RESULTS = ROOT / "research" / "package-adjustment-v4" / "package_vote_v4_results.json"
V4_CHALLENGES = ROOT / "research" / "package-adjustment-v4" / "package_vote_challenges_v4.json"
OUT_DIR = ROOT / "research" / "package-adjustment-shadow-v2"
OUT_JSON = OUT_DIR / "package_adjustment_shadow_v2.json"
OUT_MD = OUT_DIR / "package_adjustment_shadow_v2.md"
PRELAUNCH_VOTE_FREEZE = ROOT / "research/package-adjustment-production-candidate-v1/prelaunch-vote-freeze/manifest.json"

MIN_MEANINGFUL_PIECE_TO_TARGET = 0.06


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite_positive(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x > 0 else None


def v3_size2_refs(v3_diag):
    src = v3_diag["diagnostics"]["indifference_estimates"]["ratio_plus_size_target"]
    refs = []
    for label in ("p25", "median", "p75", "p90"):
        row = src[label]
        refs.append({
            "label": label,
            "target_fv": float(row["target_fv"]),
            "ratio": float(row["size2_ratio_50"]),
        })
    refs.sort(key=lambda r: r["target_fv"])
    return refs


def log_interp_clamped(target_fv, refs):
    target = finite_positive(target_fv)
    if target is None:
        raise ValueError("target_fv must be positive")
    if target <= refs[0]["target_fv"]:
        return refs[0]["ratio"], "clamped_low"
    if target >= refs[-1]["target_fv"]:
        return refs[-1]["ratio"], "clamped_high"
    lx = math.log(target)
    for a, b in zip(refs, refs[1:]):
        if a["target_fv"] <= target <= b["target_fv"]:
            la, lb = math.log(a["target_fv"]), math.log(b["target_fv"])
            t = (lx - la) / (lb - la)
            return a["ratio"] + t * (b["ratio"] - a["ratio"]), "interpolated"
    raise AssertionError("interpolation interval missing")


def v4_size3_multiplier(v4_diag):
    return float(
        v4_diag["diagnostics"]["indifference_estimates"]["ratio_only"]["median"]["ratio_50"]
    )


def preferred_multiplier(v3_diag, v4_diag, target_fv, size):
    if int(size) == 2:
        ratio, status = log_interp_clamped(target_fv, v3_size2_refs(v3_diag))
        return ratio, status, "V3 ratio_plus_size_target"
    if int(size) == 3:
        return v4_size3_multiplier(v4_diag), "constant", "V4 ratio_only"
    raise ValueError("unsupported package size")


def classify_package(target_fv, package_values):
    target = finite_positive(target_fv)
    if target is None:
        return {"supported": False, "reason": "invalid_target_fv"}

    parsed = [x for x in (finite_positive(v) for v in package_values) if x is not None]
    if not parsed:
        return {"supported": False, "reason": "empty_package"}
    if any(x >= target for x in parsed):
        return {"supported": False, "reason": "package_contains_asset_at_or_above_target"}

    threshold = target * MIN_MEANINGFUL_PIECE_TO_TARGET
    meaningful = [x for x in parsed if x >= threshold]
    tiny = [x for x in parsed if x < threshold]
    size = len(meaningful)

    if size == 1:
        return {
            "supported": False,
            "reason": "effective_one_for_one_null",
            "meaningful_package_size": 1,
            "tiny_values_ignored_for_size": tiny,
            "raw_package_fv": sum(parsed),
        }
    if size not in (2, 3):
        return {
            "supported": False,
            "reason": "unsupported_meaningful_package_size",
            "meaningful_package_size": size,
            "tiny_values_ignored_for_size": tiny,
            "raw_package_fv": sum(parsed),
        }

    return {
        "supported": True,
        "reason": "v3_v4_supported_shape",
        "meaningful_package_size": size,
        "tiny_values_ignored_for_size": tiny,
        "raw_package_fv": sum(parsed),
        "raw_package_to_target_ratio": sum(parsed) / target,
    }


def evaluate_one_vs_package(v3_diag, v4_diag, target_fv, package_values):
    target = finite_positive(target_fv)
    shape = classify_package(target_fv, package_values)
    if target is None or not shape.get("supported"):
        return {
            "supported": False,
            "reason": shape.get("reason", "invalid_target_fv"),
            "value_adjustment": 0.0,
            "trade_equivalent_target_value": target or 0.0,
            "shape": shape,
        }

    size = int(shape["meaningful_package_size"])
    multiplier, interpolation_status, source_model = preferred_multiplier(
        v3_diag, v4_diag, target, size
    )
    adjustment = target * (multiplier - 1.0)
    return {
        "supported": True,
        "reason": "v3_v4_supported_shape",
        "target_fv": target,
        "meaningful_package_size": size,
        "raw_package_fv": shape["raw_package_fv"],
        "raw_package_to_target_ratio": shape["raw_package_to_target_ratio"],
        "indifference_multiplier": multiplier,
        "value_adjustment": adjustment,
        "trade_equivalent_target_value": target * multiplier,
        "interpolation_status": interpolation_status,
        "source_model": source_model,
        "evidence_status": (
            "v3_model_estimate_inside_tested_range"
            if size == 2
            else "v4_empirically_bracketed_inside_tested_range"
        ),
        "tiny_values_ignored_for_size": shape["tiny_values_ignored_for_size"],
    }


def evaluate_trade(v3_diag, v4_diag, side_a_values, side_b_values):
    a = [x for x in (finite_positive(v) for v in side_a_values) if x is not None]
    b = [x for x in (finite_positive(v) for v in side_b_values) if x is not None]
    if len(a) == 1 and b:
        r = evaluate_one_vs_package(v3_diag, v4_diag, a[0], b)
        r["concentrated_side"] = "A"
        return r
    if len(b) == 1 and a:
        r = evaluate_one_vs_package(v3_diag, v4_diag, b[0], a)
        r["concentrated_side"] = "B"
        return r
    return {
        "supported": False,
        "reason": "unsupported_multi_vs_multi_or_empty_shape",
        "value_adjustment": 0.0,
        "concentrated_side": None,
    }


def validate_sources(v3_diag, v3_results, v4_diag, v4_results):
    assert v3_diag["diagnostic_gates"]["all_passed"] is True
    assert v3_results["summary"]["diagnostic_data_gates"]["all_passed"] is True
    assert v4_diag["diagnostic_gates"]["all_passed"] is True
    assert v4_results["summary"]["diagnostic_data_gates"]["all_passed"] is True
    assert v4_diag["diagnostics"]["conclusion"]["production_promotion_allowed"] is False
    assert v4_results["summary"]["empirical_indifference_bracketing"]["fifty_pct_bracketed_by_endpoints"] is True

    # V4 target-value term did not improve the fit; use the simpler ratio-only
    # 3-player calibration rather than inventing target sensitivity.
    aic_ratio_only = float(v4_diag["diagnostics"]["models"]["ratio_only"]["aic"])
    aic_ratio_target = float(v4_diag["diagnostics"]["models"]["ratio_plus_target"]["aic"])
    if aic_ratio_only > aic_ratio_target:
        raise RuntimeError("V4 ratio-only no longer has the better AIC")


def torture_tests(v3_diag, v4_diag):
    tests = {}

    r = evaluate_one_vs_package(v3_diag, v4_diag, 8000, [7000])
    assert not r["supported"] and r["value_adjustment"] == 0
    tests["one_for_one_null"] = "PASS"

    r = evaluate_trade(v3_diag, v4_diag, [5000, 2000], [4500, 2500])
    assert not r["supported"] and r["value_adjustment"] == 0
    tests["multi_vs_multi_unsupported_null"] = "PASS"

    r = evaluate_one_vs_package(v3_diag, v4_diag, 5000, [5000, 1000])
    assert not r["supported"]
    tests["equal_or_better_package_asset_unsupported"] = "PASS"

    r = evaluate_one_vs_package(v3_diag, v4_diag, 5000, [1500, 1400, 1300, 1200])
    assert not r["supported"]
    tests["four_meaningful_pieces_unsupported"] = "PASS"

    two = evaluate_one_vs_package(v3_diag, v4_diag, 5000, [3000, 2000])
    padded = evaluate_one_vs_package(v3_diag, v4_diag, 5000, [3000, 2000, 100])
    assert two["meaningful_package_size"] == padded["meaningful_package_size"] == 2
    assert abs(two["indifference_multiplier"] - padded["indifference_multiplier"]) < 1e-12
    tests["tiny_throw_in_padding_resistance"] = "PASS"

    refs = v3_size2_refs(v3_diag)
    assert all(b["ratio"] >= a["ratio"] for a, b in zip(refs, refs[1:]))
    tests["two_player_target_curve_monotonic"] = "PASS"

    for target in (4269.25, 5049.5, 5558.25, 6078.7):
        m2, _, _ = preferred_multiplier(v3_diag, v4_diag, target, 2)
        m3, _, _ = preferred_multiplier(v3_diag, v4_diag, target, 3)
        assert m3 > m2
    tests["three_player_premium_above_two_player"] = "PASS"

    m3s = [preferred_multiplier(v3_diag, v4_diag, t, 3)[0] for t in (3000, 5000, 8000)]
    assert max(m3s) - min(m3s) < 1e-12
    tests["three_player_target_neutral"] = "PASS"

    r3 = evaluate_one_vs_package(v3_diag, v4_diag, 5000, [4000, 3500, 2750])
    assert r3["evidence_status"] == "v4_empirically_bracketed_inside_tested_range"
    tests["three_player_no_longer_extrapolated"] = "PASS"

    ab = evaluate_trade(v3_diag, v4_diag, [5000], [3000, 2000])
    ba = evaluate_trade(v3_diag, v4_diag, [3000, 2000], [5000])
    assert ab["concentrated_side"] == "A" and ba["concentrated_side"] == "B"
    assert abs(ab["value_adjustment"] - ba["value_adjustment"]) < 1e-12
    tests["side_swap_symmetry"] = "PASS"

    return tests


def reference_table(v3_diag, v4_diag):
    rows = []
    for ref in v3_size2_refs(v3_diag):
        target = ref["target_fv"]
        m2, s2, _ = preferred_multiplier(v3_diag, v4_diag, target, 2)
        m3, s3, _ = preferred_multiplier(v3_diag, v4_diag, target, 3)
        rows.append({
            "reference": ref["label"],
            "target_fv": target,
            "size2_multiplier": m2,
            "size2_adjustment": target * (m2 - 1.0),
            "size2_trade_equivalent": target * m2,
            "size2_status": s2,
            "size3_multiplier": m3,
            "size3_adjustment": target * (m3 - 1.0),
            "size3_trade_equivalent": target * m3,
            "size3_status": s3,
        })
    return rows


def replay(v3_diag, v4_diag):
    v3 = read_json(V3_CHALLENGES)
    v4 = read_json(V4_CHALLENGES)
    rows = []

    for ch in v3["challenges"]:
        if int(ch["package_size"]) != 2:
            continue
        r = evaluate_one_vs_package(
            v3_diag, v4_diag, float(ch["target_fv"]), [float(p["fv"]) for p in ch["package"]]
        )
        rows.append((2, r))

    for ch in v4["challenges"]:
        r = evaluate_one_vs_package(
            v3_diag, v4_diag, float(ch["target_fv"]), [float(p["fv"]) for p in ch["package"]]
        )
        rows.append((3, r))

    summary = {}
    for size in (2, 3):
        sub = [r for s, r in rows if s == size]
        summary[str(size)] = {
            "shape_count": len(sub),
            "median_multiplier": statistics.median(r["indifference_multiplier"] for r in sub),
            "median_adjustment": statistics.median(r["value_adjustment"] for r in sub),
            "offers_meeting_requirement_pct": 100.0 * sum(
                r["raw_package_fv"] >= r["trade_equivalent_target_value"] for r in sub
            ) / len(sub),
        }
    return summary


def build_payload():
    v3_diag = read_json(V3_DIAG)
    v3_results = read_json(V3_RESULTS)
    v4_diag = read_json(V4_DIAG)
    v4_results = read_json(V4_RESULTS)
    validate_sources(v3_diag, v3_results, v4_diag, v4_results)

    tests = torture_tests(v3_diag, v4_diag)
    refs = reference_table(v3_diag, v4_diag)
    v3_boot = v3_diag["diagnostics"]["voter_cluster_bootstrap"]
    v4_boot = v4_diag["diagnostics"]["voter_cluster_bootstrap"]
    m3 = v4_size3_multiplier(v4_diag)

    return {
        "schema_version": 2,
        "status": "research_only_shadow",
        "method": "package-adjustment-shadow-v2-v3-2p-v4-3p",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "consumer_changed": False,
        "fundamental_value_consumer_changed": False,
        "market_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "trade_verdict_consumer_changed": False,
        "production_formula_enabled": False,
        "production_promotion_allowed": False,
        "preferred_candidate": "hybrid_v3_2p_target_sensitive_v4_3p_ratio_only",
        "source": {
            "v3_diagnostics_sha256": sha256(V3_DIAG),
            "v3_results_sha256": sha256(V3_RESULTS),
            "v3_challenges_sha256": sha256(V3_CHALLENGES),
            "v4_diagnostics_sha256": sha256(V4_DIAG),
            "v4_results_sha256": sha256(V4_RESULTS),
            "v4_challenges_sha256": sha256(V4_CHALLENGES),
            "v3_counted_votes": v3_diag["data"]["counted_votes"],
            "v3_unique_voters": v3_diag["data"]["unique_voters"],
            "v4_counted_votes": v4_diag["data"]["counted_votes"],
            "v4_unique_voters": v4_diag["data"]["unique_voters"],
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
        "size2": {
            "source_experiment": "V3",
            "source_model": "ratio_plus_size_target",
            "curve": "target_sensitive_monotonic_log_fv_clamped_p25_p90",
            "reference_points": v3_size2_refs(v3_diag),
            "bootstrap_median_target": v3_boot.get("median_target_size2_indifference_ratio"),
            "bootstrap_within_tested_range_pct": v3_boot.get("size2_indifference_within_tested_range_pct"),
        },
        "size3": {
            "source_experiment": "V4",
            "source_model": "ratio_only",
            "curve": "constant",
            "multiplier": m3,
            "raw_2_05_package_choice_pct": v4_results["summary"]["by_ratio_target"]["2.05"]["package_choice_pct"],
            "empirical_bracketing": v4_results["summary"]["empirical_indifference_bracketing"],
            "bootstrap_median_target": v4_boot.get("median_target_indifference_ratio"),
            "bootstrap_within_tested_range_pct": v4_boot.get("indifference_within_tested_range_pct"),
            "ratio_positive_rate_pct": v4_boot.get("ratio_positive_rate_pct"),
            "target_z_negative_rate_pct": v4_boot.get("target_z_negative_rate_pct"),
            "aic_ratio_only": v4_diag["diagnostics"]["models"]["ratio_only"]["aic"],
            "aic_ratio_plus_target": v4_diag["diagnostics"]["models"]["ratio_plus_target"]["aic"],
        },
        "reference_adjustments": refs,
        "frozen_shape_replay_summary": replay(v3_diag, v4_diag),
        "torture_tests": tests,
        "torture_tests_all_passed": all(v == "PASS" for v in tests.values()),
        "recommendation": {
            "carry_forward": "hybrid_v3_2p_target_sensitive_v4_3p_ratio_only",
            "live_promotion_now": False,
            "reason": (
                "V4 resolves the 3-player extrapolation problem, but V3/V4 use overlapping controlled targets. "
                "Freeze this shadow and validate prospectively/out-of-sample before live promotion."
            ),
        },
    }


def write_report(p):
    lines = [
        "# Package Adjustment Shadow V2",
        "",
        "**Status: RESEARCH ONLY — no live calculator consumer changed.**",
        "",
        "## Preferred hybrid",
        "",
        "- 2-player package: V3 target-sensitive monotonic curve.",
        f"- 3-player package: V4 ratio-only constant at `{p['size3']['multiplier']:.3f}x`.",
        "",
        "## Why 3-player changed",
        "",
        f"- V4 package choice at 2.05x: `{p['size3']['raw_2_05_package_choice_pct']:.1f}%`.",
        f"- V4 bootstrap indifference inside tested range: `{p['size3']['bootstrap_within_tested_range_pct']:.2f}%`.",
        f"- V4 ratio coefficient positive: `{p['size3']['ratio_positive_rate_pct']:.1f}%` of voter-cluster bootstraps.",
        f"- Ratio-only AIC `{p['size3']['aic_ratio_only']:.2f}` vs ratio+target `{p['size3']['aic_ratio_plus_target']:.2f}`.",
        "",
        "## Reference adjustments",
        "",
        "| Target ref | Target FV | 2p multiplier | 2p adjustment | 3p multiplier | 3p adjustment |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in p["reference_adjustments"]:
        lines.append(
            f"| {r['reference']} | {r['target_fv']:.0f} | {r['size2_multiplier']:.3f}x | {r['size2_adjustment']:.0f} | "
            f"{r['size3_multiplier']:.3f}x | {r['size3_adjustment']:.0f} |"
        )
    lines += [
        "",
        "## Guardrails",
        "",
        "- 1-for-1: zero adjustment.",
        "- Multi-v-multi: unsupported.",
        "- 4+ meaningful pieces: unsupported.",
        "- Picks: unsupported.",
        "- Tiny throw-ins below 6% of target FV do not increase package size.",
        "- Team Utility remains separate.",
        "",
        "## Promotion",
        "",
        "Do not promote live yet. Freeze this curve and validate prospectively/out-of-sample.",
        "",
        "## Torture tests",
        "",
    ]
    for name, status in p["torture_tests"].items():
        lines.append(f"- {name}: `{status}`")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def selftest():
    fake_v3 = {
        "diagnostics": {"indifference_estimates": {
            "ratio_plus_size_target": {
                "p25":{"target_fv":4000,"size2_ratio_50":1.40},
                "median":{"target_fv":5000,"size2_ratio_50":1.48},
                "p75":{"target_fv":6000,"size2_ratio_50":1.54},
                "p90":{"target_fv":7000,"size2_ratio_50":1.58},
            }
        }}
    }
    fake_v4 = {"diagnostics":{"indifference_estimates":{"ratio_only":{"median":{"ratio_50":2.05}}}}}
    two = evaluate_one_vs_package(fake_v3, fake_v4, 5000, [3000, 2000])
    three = evaluate_one_vs_package(fake_v3, fake_v4, 5000, [2200, 1600, 1200])
    assert two["supported"] and three["supported"]
    assert two["meaningful_package_size"] == 2 and three["meaningful_package_size"] == 3
    assert three["indifference_multiplier"] > two["indifference_multiplier"]
    tiny = evaluate_one_vs_package(fake_v3, fake_v4, 5000, [3000, 2000, 100])
    assert tiny["meaningful_package_size"] == 2
    print("Package Adjustment Shadow V2 self-test passed.")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    if PRELAUNCH_VOTE_FREEZE.exists():
        freeze = read_json(PRELAUNCH_VOTE_FREEZE)
        if freeze.get('status') != 'package_adjustment_prelaunch_vote_evidence_freeze':
            raise RuntimeError('Unexpected pre-launch vote freeze status')
        if freeze.get('frozen') is not True:
            raise RuntimeError('Pre-launch vote freeze is not frozen')
        print(
            'Pre-launch Package Adjustment calibration is frozen; '
            'Shadow V2 rebuild from post-launch vote evidence is disabled.'
        )
        return
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(payload)
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    print("3-player multiplier:", payload["size3"]["multiplier"])
    print("Torture tests all passed:", payload["torture_tests_all_passed"])

if __name__ == "__main__":
    main()

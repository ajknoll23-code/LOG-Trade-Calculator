#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARDENING_PATH = ROOT / "research/package-adjustment-v5/evidence_hardening.json"
OUT_JSON = ROOT / "research/package-adjustment-v5/production_candidate_design.json"
OUT_MD = ROOT / "research/package-adjustment-v5/production_candidate_design.md"
OUT_METHOD = ROOT / "research/package-adjustment-v5/production_candidate_methodology.md"

CANDIDATE_ID = "package-adjustment-v5-size2-composition-overlay-candidate-v1"
PRODUCTION_REVISION = "v1.5-audit-step6-scope-ui-idp"

# Exact controlled-live V1.5 size-2 core.
V3_LARGEST_MIN = 0.5044104156375697
V3_LARGEST_MAX = 0.5230278884462152
V3_SMALLEST_MIN = 0.4769721115537849
V3_SMALLEST_MAX = 0.49558958436243034
V3_REFERENCE_POINTS = (
    (4269.25, 1.4007986955507035),
    (5049.5, 1.485881276187134),
    (5558.25, 1.5368431747111482),
    (6078.700000000002, 1.5859349498155657),
)

EXPANSION_MAX_LARGEST_SHARE = 0.60
ANCHOR_55_SHARE = 0.55
ANCHOR_60_SHARE = 0.60
MAX_INTERIOR_EVIDENCE_GAP = 0.01

SUPPORTED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def live_size2_multiplier(target_fv: float) -> float | None:
    t = float(target_fv)
    if not (t > 0):
        return None
    refs = V3_REFERENCE_POINTS
    if t <= refs[0][0]:
        return refs[0][1]
    if t >= refs[-1][0]:
        return refs[-1][1]
    lt = math.log(t)
    for (ta, ra), (tb, rb) in zip(refs, refs[1:]):
        if ta <= t <= tb:
            la, lb = math.log(ta), math.log(tb)
            w = 0.0 if lb == la else (lt - la) / (lb - la)
            return ra + w * (rb - ra)
    return None

def lerp(x, x0, y0, x1, y1):
    if abs(x1 - x0) <= 1e-15:
        return float(y0)
    w = (float(x) - float(x0)) / (float(x1) - float(x0))
    return float(y0) + w * (float(y1) - float(y0))

def candidate_composition_factor(largest_share: float, factor55: float, factor60: float):
    s = float(largest_share)

    # Preserve the frozen V3 core EXACTLY. Values below the V3 lower
    # edge remain unsupported, just as they are in controlled-live V1.5.
    if V3_LARGEST_MIN <= s <= V3_LARGEST_MAX:
        return 1.0

    # V5 expansion begins immediately outside the V3 upper boundary
    # and stops at the nominal 60/40 review ceiling. No 65/35+ support.
    if s <= V3_LARGEST_MAX or s > EXPANSION_MAX_LARGEST_SHARE:
        return None

    # The 55/45 hardened point is above the live curve. The 60/40
    # hardened point is ~1.0; floor at 1.0 so this expansion study
    # can never reduce the established V1.5 consolidation premium.
    f55 = max(1.0, float(factor55))
    f60 = max(1.0, float(factor60))

    if s <= ANCHOR_55_SHARE:
        return lerp(s, V3_LARGEST_MAX, 1.0, ANCHOR_55_SHARE, f55)
    return lerp(s, ANCHOR_55_SHARE, f55, ANCHOR_60_SHARE, f60)

def candidate_multiplier(target_fv: float, largest_share: float, factor55: float, factor60: float):
    base = live_size2_multiplier(target_fv)
    factor = candidate_composition_factor(largest_share, factor55, factor60)
    if base is None or factor is None:
        return None
    return base * factor

def selftest():
    f55 = 1.133281
    f60 = 0.999321

    assert candidate_composition_factor(V3_LARGEST_MIN - 1e-6, f55, f60) is None
    assert abs(candidate_composition_factor(V3_LARGEST_MIN, f55, f60) - 1.0) < 1e-12
    assert abs(candidate_composition_factor(V3_LARGEST_MAX, f55, f60) - 1.0) < 1e-12

    just_outside = candidate_composition_factor(V3_LARGEST_MAX + 1e-8, f55, f60)
    assert just_outside is not None and just_outside >= 1.0

    assert abs(candidate_composition_factor(0.55, f55, f60) - f55) < 1e-12
    assert abs(candidate_composition_factor(0.60, f55, f60) - 1.0) < 1e-12
    assert candidate_composition_factor(0.600001, f55, f60) is None

    # Continuity checks at the V3 boundary and 55/45 anchor.
    eps = 1e-8
    left55 = candidate_composition_factor(0.55 - eps, f55, f60)
    right55 = candidate_composition_factor(0.55 + eps, f55, f60)
    assert abs(left55 - right55) < 1e-6

    example_share = 4153.0 / (4153.0 + 3258.0)
    example_factor = candidate_composition_factor(example_share, f55, f60)
    assert example_factor is not None
    assert 1.10 < example_factor < 1.12

    m = candidate_multiplier(5896.0, example_share, f55, f60)
    assert m is not None and m > 1.70

    print("Package Adjustment V5 production-candidate design self-test passed.")

def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    hard = read_json(HARDENING_PATH)

    if hard.get("status") != "v5_evidence_hardening_complete":
        raise RuntimeError("V5 evidence hardening is not complete")
    if hard.get("research_only") is not True:
        raise RuntimeError("V5 hardening must remain research-only")
    if hard.get("production_formula_changed") is not False:
        raise RuntimeError("Production formula changed before candidate design")
    if hard.get("production_candidate_implemented") is not False:
        raise RuntimeError("Unexpected pre-existing production candidate implementation")
    if hard.get("production_promotion_allowed") is not False:
        raise RuntimeError("Unexpected production promotion permission")
    if hard["conclusion"].get("evidence_supported_expansion_ceiling_for_review") != "60/40":
        raise RuntimeError("Hardened evidence ceiling is not 60/40")

    comp = hard["composition_hardening"]
    for label in ("55/45", "60/40"):
        if comp[label].get("evidence_supported_for_expansion_review") is not True:
            raise RuntimeError(f"{label} is not hardened for expansion review")
    for label in ("65/35", "70/30", "75/25"):
        if comp[label].get("evidence_supported_for_expansion_review") is not False:
            raise RuntimeError(f"{label} unexpectedly supported for expansion review")

    point55 = comp["55/45"]["normalized_to_live_v3"]["point"]
    point60 = comp["60/40"]["normalized_to_live_v3"]["point"]
    if not point55.get("bracketed") or not point60.get("bracketed"):
        raise RuntimeError("Supported V5 bands require bracketed normalized point fits")

    observed55 = float(point55["ratio"])
    observed60 = float(point60["ratio"])
    factor55 = max(1.0, observed55)
    factor60 = max(1.0, observed60)

    ranges = hard["catalog_composition_ranges"]
    v3_to_55_gap = float(ranges["55/45"]["actual_largest_share_min"]) - V3_LARGEST_MAX
    gap_55_to_60 = float(ranges["60/40"]["gap_from_previous_supported_max"])
    max_gap = max(v3_to_55_gap, gap_55_to_60)
    if max_gap > MAX_INTERIOR_EVIDENCE_GAP:
        raise RuntimeError(
            f"Interior composition evidence gap too large for candidate interpolation: {max_gap}"
        )

    example_target_fv = 5896.0
    example_package = [4153.0, 3258.0]
    example_total = sum(example_package)
    example_share = max(example_package) / example_total
    example_raw_ratio = example_total / example_target_fv
    example_base = live_size2_multiplier(example_target_fv)
    example_factor = candidate_composition_factor(example_share, factor55, factor60)
    example_mult = candidate_multiplier(
        example_target_fv, example_share, factor55, factor60
    )
    if example_base is None or example_factor is None or example_mult is None:
        raise RuntimeError("Reference 56/44 use case unexpectedly unsupported by candidate")

    boundary_tests = []
    for share in (
        V3_LARGEST_MIN - 1e-6,
        V3_LARGEST_MIN,
        V3_LARGEST_MAX,
        V3_LARGEST_MAX + 1e-6,
        0.525,
        0.55,
        0.56,
        0.575,
        0.60,
        0.600001,
        0.65,
    ):
        factor = candidate_composition_factor(share, factor55, factor60)
        boundary_tests.append({
            "largest_meaningful_package_share": round(share, 12),
            "supported": factor is not None,
            "composition_factor": None if factor is None else round(factor, 9),
        })

    candidate = {
        "candidate_id": CANDIDATE_ID,
        "status": "shadow_candidate_design_complete",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "source_evidence_fingerprint_sha256": hard["evidence_freeze"]["evidence_fingerprint_sha256"],
        "source_counted_votes": int(hard["evidence_freeze"]["counted_votes"]),
        "source_unique_voters": int(hard["evidence_freeze"]["unique_voters"]),
        "production_revision": PRODUCTION_REVISION,
        "production_formula_changed": False,
        "production_candidate_implemented": False,
        "production_promotion_allowed": False,
        "automatic_production_change_allowed": False,
        "fundamental_value_consumer_changed": False,
        "market_value_consumer_changed": False,
        "draft_pick_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "trade_verdict_consumer_changed": False,
        "candidate_review_allowed": True,
        "candidate_review_recommendation": "advance_to_shadow_regression_hardening",
        "scope": {
            "package_size": 2,
            "supported_positions": list(SUPPORTED_POSITIONS),
            "picks_supported": False,
            "multi_vs_multi_supported": False,
            "four_plus_meaningful_players_supported": False,
            "meaningful_piece_min_target_share": 0.06,
            "all_package_players_must_remain_below_target_fv": True,
            "tiny_throw_in_semantics": "unchanged_from_v1_5_full_raw_fv_counts",
            "size3_policy": "unchanged_v4",
        },
        "composition_policy": {
            "existing_v3_core_unchanged": {
                "largest_min": V3_LARGEST_MIN,
                "largest_max": V3_LARGEST_MAX,
                "smallest_min": V3_SMALLEST_MIN,
                "smallest_max": V3_SMALLEST_MAX,
                "composition_factor": 1.0,
            },
            "v5_expansion_largest_share_min_exclusive": V3_LARGEST_MAX,
            "v5_expansion_largest_share_max_inclusive": EXPANSION_MAX_LARGEST_SHARE,
            "bands_65_35_and_more_imbalanced": "unsupported_fail_closed",
            "interior_evidence_gap_limit": MAX_INTERIOR_EVIDENCE_GAP,
            "observed_max_interior_gap": round(max_gap, 9),
            "interpolation_policy": (
                "piecewise_linear_composition_factor_between_v3_boundary_55_45_and_60_40_anchors"
            ),
            "no_extrapolation_beyond_60_40": True,
        },
        "multiplier_policy": {
            "baseline": "exact_controlled_live_v1_5_size2_target_curve",
            "live_reference_points": [
                {"target_fv": t, "ratio": r} for t, r in V3_REFERENCE_POINTS
            ],
            "normalized_hardened_factor_55_45_observed": observed55,
            "normalized_hardened_factor_60_40_observed": observed60,
            "candidate_factor_55_45": factor55,
            "candidate_factor_60_40": factor60,
            "candidate_factor_floor": 1.0,
            "rationale_for_floor": (
                "V5 composition expansion may add consolidation premium but may not reduce "
                "the already-controlled-live V1.5 size2 premium."
            ),
            "anchors": [
                {"largest_share": V3_LARGEST_MAX, "factor": 1.0, "source": "frozen_v3_boundary"},
                {"largest_share": 0.55, "factor": factor55, "source": "hardened_v5_55_45_point"},
                {"largest_share": 0.60, "factor": factor60, "source": "hardened_v5_60_40_point_with_floor"},
            ],
        },
        "hardened_evidence": {
            "55/45": {
                "votes": comp["55/45"]["votes"],
                "normalized_point_factor": observed55,
                "voter_bootstrap": comp["55/45"]["normalized_to_live_v3"]["voter_cluster_bootstrap"],
                "target_bootstrap": comp["55/45"]["normalized_to_live_v3"]["target_cluster_bootstrap"],
                "leave_one_voter_out": comp["55/45"]["normalized_to_live_v3"]["leave_one_voter_out"],
            },
            "60/40": {
                "votes": comp["60/40"]["votes"],
                "normalized_point_factor": observed60,
                "voter_bootstrap": comp["60/40"]["normalized_to_live_v3"]["voter_cluster_bootstrap"],
                "target_bootstrap": comp["60/40"]["normalized_to_live_v3"]["target_cluster_bootstrap"],
                "leave_one_voter_out": comp["60/40"]["normalized_to_live_v3"]["leave_one_voter_out"],
            },
        },
        "boundary_tests": boundary_tests,
        "reference_use_case_56_44": {
            "target_fv": example_target_fv,
            "package_fv": example_total,
            "largest_package_share": round(example_share, 9),
            "raw_package_to_target_ratio": round(example_raw_ratio, 9),
            "live_v1_5_size2_multiplier": round(example_base, 9),
            "candidate_composition_factor": round(example_factor, 9),
            "candidate_multiplier": round(example_mult, 9),
            "candidate_trade_equivalent_target_fv": round(example_target_fv * example_mult, 3),
            "supported_by_candidate": True,
        },
        "conclusion": {
            "production_change_recommended": False,
            "production_review_required": True,
            "shadow_regression_hardening_required": True,
            "reason": (
                "candidate_formula_defined_from_hardened_55_45_and_60_40_evidence_"
                "but_not_yet_implemented_or_regression_hardened"
            ),
        },
    }

    canonical = json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode("utf-8")
    candidate["candidate_spec_sha256"] = sha256_bytes(canonical)

    OUT_JSON.write_text(
        json.dumps(candidate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Package Adjustment V5 — Production Candidate Design",
        "",
        "**SHADOW CANDIDATE ONLY — controlled-live V1.5 is unchanged.**",
        "",
        f"- Candidate: `{CANDIDATE_ID}`",
        f"- Frozen evidence: `{candidate['source_counted_votes']}` votes / `{candidate['source_unique_voters']}` voters",
        f"- Evidence fingerprint: `{candidate['source_evidence_fingerprint_sha256']}`",
        "- Expansion review ceiling: **60/40**",
        "- 65/35 and more imbalanced packages: **unsupported / fail closed**",
        "",
        "## Candidate formula",
        "",
        "The exact V1.5 target-sensitive size-2 multiplier remains the baseline.",
        "A composition factor is layered on top only outside the existing frozen V3 core:",
        "",
        f"- Existing V3 core through largest-share `{V3_LARGEST_MAX:.6f}`: factor **1.000x**",
        f"- 55/45 anchor: factor **{factor55:.6f}x**",
        f"- 60/40 anchor: factor **{factor60:.6f}x**",
        "- Between anchors: piecewise-linear interpolation.",
        "- The factor is floored at 1.000x, so V5 cannot reduce the existing V1.5 premium.",
        "- Above 60/40: fail closed.",
        "",
        "## Why this candidate",
        "",
        "- 55/45 and 60/40 both survived voter-cluster and target-cluster hardening.",
        "- 65/35 failed hardened expansion review, so the candidate stops before it.",
        "- The frozen V3 core is not recalibrated from the V5 50/50 validation band.",
        "- Narrow interior coverage gaps are bridged only by interpolation; no extrapolation is allowed beyond 60/40.",
        "",
        "## 56/44 reference case",
        "",
        f"- Largest share: `{example_share:.4%}`",
        f"- Raw package/target ratio: `{example_raw_ratio:.3f}x`",
        f"- Live V1.5 target multiplier: `{example_base:.3f}x`",
        f"- V5 composition factor: `{example_factor:.3f}x`",
        f"- Shadow candidate multiplier: `{example_mult:.3f}x`",
        f"- Shadow trade-equivalent target FV: `{example_target_fv * example_mult:,.0f}`",
        "",
        "## Next gate",
        "",
        "This file does **not** implement the formula. The next step is a separate shadow regression/adversarial hardening pass against exact production semantics and boundary cases before any human-reviewed live promotion.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    method = """# Package Adjustment V5 — Production Candidate Methodology

**Status: SHADOW DESIGN ONLY. No live consumer is changed.**

## Design choice

The candidate preserves the exact controlled-live V1.5 target-sensitive two-player curve and treats V5 as a composition overlay rather than a replacement model.

The frozen V3 composition core remains untouched. Hardened V5 evidence supports expansion review through the 55/45 and 60/40 bands, while 65/35 fails the hardening rule. Therefore the candidate supports no composition more imbalanced than 60/40.

## Composition factor

The hardened V5 normalized 50% crossing is interpreted as a multiplicative factor on the existing V1.5 size-2 threshold:

`candidate multiplier = live V1.5 size-2 multiplier(target FV) × composition factor`

The factor is anchored at:
- frozen V3 upper composition boundary: 1.000x;
- 55/45 hardened normalized point;
- 60/40 hardened normalized point, floored at 1.000x.

Piecewise-linear interpolation is used between these anchors to avoid discontinuous trade verdicts. This interpolation is candidate engineering, not a new research finding. It bridges only the small interior spacing between evidence-supported bands and does not extend beyond the nominal 60/40 boundary.

## Conservative floor

The 60/40 hardened normalized point is slightly below 1.0. This study was designed to determine whether composition justifies expansion of the existing Package Adjustment, not to reduce the already-controlled-live V1.5 consolidation premium. The candidate therefore floors every V5 composition factor at 1.0.

## Production invariants

The candidate design does not alter Fundamental Value, Market Value, draft-pick values, Team Utility, or size-3 V4 Package Adjustment. Picks, multi-v-multi trades, 4+ meaningful package players, unsupported positions, and package pieces at or above target FV remain fail-closed exactly as before.

## Promotion policy

Candidate definition is not production approval. A separate shadow implementation must reproduce exact V1.5 behavior inside the existing V3 core, apply the new overlay only in the V5 review-supported region, and pass adversarial boundary/regression tests before a human-reviewed promotion decision.
"""
    OUT_METHOD.write_text(
        "\n".join(line[10:] if line.startswith("          ") else line for line in method.splitlines()) + "\n",
        encoding="utf-8",
    )

    print("Wrote:", OUT_JSON.relative_to(ROOT))
    print("Wrote:", OUT_MD.relative_to(ROOT))
    print("Wrote:", OUT_METHOD.relative_to(ROOT))
    print("Candidate 55/45 factor:", factor55)
    print("Candidate 60/40 factor:", factor60)
    print("Reference 56/44 factor:", round(example_factor, 9))
    print("Production remains unchanged.")

if __name__ == "__main__":
    main()

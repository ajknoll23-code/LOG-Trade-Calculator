#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import package_vote_v5_pipeline as pipe
import package_vote_v5_fit_diagnostics as diag

CATALOG_PATH = ROOT / "research/package-adjustment-v5/package_vote_challenges_v5.json"
RELEASE_PATH = ROOT / "research/package-adjustment-v5/release_manifest.json"
RESULTS_PATH = ROOT / "research/package-adjustment-v5/package_vote_v5_results.json"
DIAGNOSTICS_PATH = ROOT / "research/package-adjustment-v5/package_vote_v5_fit_diagnostics.json"
OUT_JSON = ROOT / "research/package-adjustment-v5/evidence_hardening.json"
OUT_MD = ROOT / "research/package-adjustment-v5/evidence_hardening.md"

BOOTSTRAP_DRAWS = 500
BOOTSTRAP_SEED_VOTER = 20260910
BOOTSTRAP_SEED_TARGET = 20260911
MIN_BOOTSTRAP_BRACKET_PCT = 80.0
COMPOSITIONS = ("50/50", "55/45", "60/40", "65/35", "70/30", "75/25")
EXPANSION_BANDS = ("55/45", "60/40", "65/35", "70/30", "75/25")

# Exact controlled-live V1.5 two-player target-sensitive curve.
V3_REFERENCE_POINTS = (
    (4269.25, 1.4007986955507035),
    (5049.5, 1.485881276187134),
    (5558.25, 1.5368431747111482),
    (6078.700000000002, 1.5859349498155657),
)
V3_LARGEST_SHARE_MAX = 0.5230278884462152


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def v3_multiplier(target_fv: float) -> float | None:
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


def canonical_evidence_hash(rows):
    records = []
    for r in rows:
        records.append("|".join([
            str(r.get("timestamp") or ""),
            str(r.get("voter_roster_id") or ""),
            str(r.get("challenge_id") or ""),
            str(r.get("choice") or ""),
            str(r.get("left_canonical_side") or ""),
        ]))
    payload = "\n".join(sorted(records)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_frozen_evidence(catalog_doc, release, results):
    # Freeze to the aggregator's generated_at timestamp. New sheet rows arriving
    # after that instant are deliberately excluded so this hardening run audits
    # exactly the committed aggregation result instead of racing the live sheet.
    cutoff = pipe.parse_timestamp_utc(results["generated_at_utc"])
    if cutoff is None:
        raise RuntimeError("invalid V5 result generated_at_utc")

    parsed = []
    for source_row in pipe.fetch_rows():
        if not pipe.is_package_v5_row(source_row):
            continue
        row = pipe.parse_row(source_row)
        if row is None:
            continue
        ts = pipe.parse_timestamp_utc(row.get("timestamp"))
        if ts is None or ts > cutoff:
            continue
        parsed.append(row)

    post, pre_release, invalid_ts = pipe.filter_after_release(parsed, release)
    capped, daily_cap_dropped = pipe.apply_daily_cap(post)
    catalog = {c["id"]: c for c in catalog_doc["challenges"]}
    valid = [r for r in capped if r["challenge_id"] in catalog]

    expected = int(results["summary"]["raw_vote_count"])
    if len(valid) != expected:
        raise RuntimeError(
            "Frozen V5 evidence count drift vs committed aggregation result: "
            f"{len(valid)} != {expected}"
        )

    return valid, catalog, {
        "aggregator_generated_at_utc": results["generated_at_utc"],
        "pre_release_rows_excluded": pre_release,
        "invalid_timestamp_rows_excluded": invalid_ts,
        "daily_cap_rows_dropped": daily_cap_dropped,
        "evidence_fingerprint_sha256": canonical_evidence_hash(valid),
    }


def annotate_rows(rows, catalog):
    out = []
    for row in rows:
        c = catalog[row["challenge_id"]]
        target_fv = float(c["target_fv"])
        live_mult = v3_multiplier(target_fv)
        if live_mult is None:
            raise RuntimeError(f"No V3 multiplier for target FV {target_fv}")
        raw_ratio = float(c["raw_package_to_target_ratio"])
        largest_share = float(c["component_profile"]["actual_package_shares"][0])
        out.append({
            **row,
            "composition": c["composition_target"]["label"],
            "target_key": c["target"]["key"],
            "target_fv": target_fv,
            "raw_ratio": raw_ratio,
            "live_v3_multiplier": live_mult,
            "normalized_to_live_v3": raw_ratio / live_mult,
            "largest_package_share": largest_share,
        })
    return out


def normalized_curve(rows, original_voter_weights, row_multiplier=None):
    if row_multiplier is None:
        row_multiplier = lambda row: 1.0

    # Aggregate at the challenge-normalized-ratio level before PAVA. The same
    # challenge has one target FV and one normalized ratio, so repeated ballots
    # add mass without creating order-dependent duplicate x coordinates.
    cells = defaultdict(lambda: {
        "package_mass": 0.0,
        "total_mass": 0.0,
        "raw_votes": 0,
        "package_votes": 0,
        "targets": set(),
        "challenges": set(),
    })

    for row in rows:
        mult = float(row_multiplier(row))
        if mult <= 0:
            continue
        voter = row["voter_roster_id"]
        base = float(original_voter_weights[voter]["ballot_weight"])
        w = base * mult
        x = round(float(row["normalized_to_live_v3"]), 12)
        cell = cells[x]
        cell["raw_votes"] += 1
        cell["package_votes"] += int(row["choice"] == "P")
        cell["total_mass"] += w
        if row["choice"] == "P":
            cell["package_mass"] += w
        cell["targets"].add(row["target_key"])
        cell["challenges"].add(row["challenge_id"])

    xs = sorted(cells)
    package_mass = [cells[x]["package_mass"] for x in xs]
    total_mass = [cells[x]["total_mass"] for x in xs]
    if not xs:
        return {
            "point": {"bracketed": False, "ratio": None, "reason": "no_rows"},
            "blocks": [],
            "x_min": None,
            "x_max": None,
            "raw_votes": 0,
        }

    fitted, blocks = diag.pava_non_decreasing(xs, package_mass, total_mass)
    point = diag.indifference_from_curve(xs, fitted)
    return {
        "point": point,
        "blocks": blocks,
        "x_min": min(xs),
        "x_max": max(xs),
        "raw_votes": sum(cells[x]["raw_votes"] for x in xs),
    }


def summarize_point(point):
    return {
        k: (round(float(v), 6) if isinstance(v, float) else v)
        for k, v in point.items()
    }


def bootstrap_cluster(rows, original_voter_weights, cluster_field, seed, draws=BOOTSTRAP_DRAWS):
    clusters = sorted({row[cluster_field] for row in rows})
    if not clusters:
        return {
            "draws": draws,
            "bracketed_draws": 0,
            "bracketed_pct": 0.0,
            "median_factor": None,
            "ci90_low": None,
            "ci90_high": None,
        }

    rng = random.Random(seed)
    values = []
    bracketed = 0
    for _ in range(draws):
        multiplicity = defaultdict(int)
        for _i in clusters:
            multiplicity[rng.choice(clusters)] += 1
        fit = normalized_curve(
            rows,
            original_voter_weights,
            row_multiplier=lambda row: multiplicity.get(row[cluster_field], 0),
        )
        point = fit["point"]
        if point.get("bracketed"):
            bracketed += 1
            values.append(float(point["ratio"]))

    return {
        "draws": draws,
        "bracketed_draws": bracketed,
        "bracketed_pct": round(100.0 * bracketed / draws, 2) if draws else 0.0,
        "median_factor": round(statistics.median(values), 6) if values else None,
        "ci90_low": round(diag.quantile(values, 0.05), 6) if values else None,
        "ci90_high": round(diag.quantile(values, 0.95), 6) if values else None,
    }


def leave_one_voter_out(rows, original_voter_weights):
    voters = sorted({row["voter_roster_id"] for row in rows})
    values = []
    unbracketed = 0
    for omitted in voters:
        fit = normalized_curve(
            rows,
            original_voter_weights,
            row_multiplier=lambda row, omitted=omitted: (
                0.0 if row["voter_roster_id"] == omitted else 1.0
            ),
        )
        point = fit["point"]
        if point.get("bracketed"):
            values.append(float(point["ratio"]))
        else:
            unbracketed += 1
    return {
        "voters_tested": len(voters),
        "bracketed_fits": len(values),
        "unbracketed_fits": unbracketed,
        "factor_min": round(min(values), 6) if values else None,
        "factor_max": round(max(values), 6) if values else None,
        "factor_median": round(statistics.median(values), 6) if values else None,
    }


def composition_catalog_ranges(catalog_doc):
    grouped = defaultdict(list)
    for c in catalog_doc["challenges"]:
        label = c["composition_target"]["label"]
        grouped[label].append(float(c["component_profile"]["actual_package_shares"][0]))

    out = {}
    prev_max = V3_LARGEST_SHARE_MAX
    for label in COMPOSITIONS:
        vals = grouped[label]
        lo, hi = min(vals), max(vals)
        gap = max(0.0, lo - prev_max)
        out[label] = {
            "challenge_count": len(vals),
            "actual_largest_share_min": round(lo, 6),
            "actual_largest_share_max": round(hi, 6),
            "gap_from_previous_supported_max": round(gap, 6),
        }
        prev_max = max(prev_max, hi)
    return out


def selftest():
    for target_fv, ratio in V3_REFERENCE_POINTS:
        got = v3_multiplier(target_fv)
        assert got is not None and abs(got - ratio) < 1e-12
    mids = [v3_multiplier(x) for x in (4300, 5000, 5500, 6000)]
    assert all(x is not None for x in mids)
    assert all(a <= b for a, b in zip(mids, mids[1:]))

    # Contract checks for the mature path we depend on.
    for name in (
        "fetch_rows", "is_package_v5_row", "parse_row", "filter_after_release",
        "apply_daily_cap", "voter_weights", "parse_timestamp_utc",
    ):
        assert callable(getattr(pipe, name, None)), name
    for name in ("pava_non_decreasing", "indifference_from_curve", "quantile"):
        assert callable(getattr(diag, name, None)), name

    # Synthetic normalized crossing around 1.0.
    rows = []
    weights = {}
    for i, (x, choice) in enumerate(((0.90, "T"), (0.95, "T"), (1.05, "P"), (1.10, "P"))):
        voter = f"v{i}"
        rows.append({
            "voter_roster_id": voter,
            "normalized_to_live_v3": x,
            "choice": choice,
            "target_key": "t",
            "challenge_id": f"c{i}",
        })
        weights[voter] = {"ballot_weight": 1.0}
    fit = normalized_curve(rows, weights)
    assert fit["point"]["bracketed"] is True
    assert 0.95 <= float(fit["point"]["ratio"]) <= 1.05

    print("Package Adjustment V5 evidence-hardening self-test passed.")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    catalog_doc = read_json(CATALOG_PATH)
    release = read_json(RELEASE_PATH)
    results = read_json(RESULTS_PATH)
    diagnostics = read_json(DIAGNOSTICS_PATH)

    if catalog_doc.get("status") != "frozen_package_preference_v5" or catalog_doc.get("frozen") is not True:
        raise RuntimeError("unexpected/unfrozen V5 catalog")
    if release.get("status") != "package_adjustment_v5_composition_vote_release" or release.get("frozen") is not True:
        raise RuntimeError("unexpected/unfrozen V5 release")
    if results.get("status") != "research_only":
        raise RuntimeError("unexpected V5 results status")
    if diagnostics.get("status") != "research_diagnostics_complete":
        raise RuntimeError("V5 diagnostics are not mature/complete")
    if results["summary"]["diagnostic_data_gates"]["all_passed"] is not True:
        raise RuntimeError("V5 preregistered data gates are not all passed")
    if diagnostics["evidence"]["data_gates_all_passed"] is not True:
        raise RuntimeError("V5 diagnostic data gates are not all passed")

    rows, catalog, freeze_meta = load_frozen_evidence(catalog_doc, release, results)
    rows = annotate_rows(rows, catalog)
    original_voter_weights = pipe.voter_weights(rows)

    # Concentration is descriptive; no new post-hoc pass/fail threshold is invented.
    total_effective_mass = sum(
        float(original_voter_weights[v]["effective_votes"])
        for v in original_voter_weights
    )
    max_voter_mass = max(
        (float(x["effective_votes"]) for x in original_voter_weights.values()),
        default=0.0,
    )
    max_voter_share = (
        max_voter_mass / total_effective_mass if total_effective_mass > 0 else None
    )

    by_composition = {}
    for label in COMPOSITIONS:
        sub = [r for r in rows if r["composition"] == label]
        normalized = normalized_curve(sub, original_voter_weights)
        voter_boot = bootstrap_cluster(
            sub, original_voter_weights, "voter_roster_id", BOOTSTRAP_SEED_VOTER
        )
        target_boot = bootstrap_cluster(
            sub, original_voter_weights, "target_key", BOOTSTRAP_SEED_TARGET
        )
        lovo = leave_one_voter_out(sub, original_voter_weights)
        raw_diag = diagnostics["composition_diagnostics"][label]

        point_bracketed = bool(normalized["point"].get("bracketed"))
        voter_stable = (
            point_bracketed
            and voter_boot["bracketed_pct"] >= MIN_BOOTSTRAP_BRACKET_PCT
        )
        target_stable = (
            point_bracketed
            and target_boot["bracketed_pct"] >= MIN_BOOTSTRAP_BRACKET_PCT
        )
        raw_stable = bool(raw_diag.get("stable_within_tested_range"))

        by_composition[label] = {
            "votes": len(sub),
            "distinct_voters": len({r["voter_roster_id"] for r in sub}),
            "distinct_targets": len({r["target_key"] for r in sub}),
            "normalized_to_live_v3": {
                "definition": "raw_package_to_target_ratio / controlled_live_v1_5_size2_multiplier(target_fv)",
                "point": summarize_point(normalized["point"]),
                "tested_factor_min": round(float(normalized["x_min"]), 6),
                "tested_factor_max": round(float(normalized["x_max"]), 6),
                "voter_cluster_bootstrap": voter_boot,
                "target_cluster_bootstrap": target_boot,
                "leave_one_voter_out": lovo,
                "voter_bootstrap_stable": voter_stable,
                "target_bootstrap_stable": target_stable,
            },
            "existing_raw_ratio_diagnostic": {
                "indifference": raw_diag["indifference"],
                "bootstrap": raw_diag["bootstrap"],
                "stable_within_tested_range": raw_stable,
                "raw_weighted_monotonicity_reversals": raw_diag["raw_weighted_monotonicity_reversals"],
            },
            "evidence_supported_for_expansion_review": (
                label in EXPANSION_BANDS and raw_stable and voter_stable and target_stable
            ),
        }

    # Require contiguity from 55/45 outward; never leap over a failed band.
    ceiling = None
    for label in EXPANSION_BANDS:
        if by_composition[label]["evidence_supported_for_expansion_review"]:
            ceiling = label
        else:
            break

    ranges = composition_catalog_ranges(catalog_doc)

    doc = {
        "schema_version": 1,
        "status": "v5_evidence_hardening_complete",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "release_id": release["release_id"],
        "production_revision": "v1.5-audit-step6-scope-ui-idp",
        "production_formula_changed": False,
        "fundamental_value_consumer_changed": False,
        "market_value_consumer_changed": False,
        "draft_pick_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "trade_verdict_consumer_changed": False,
        "automatic_production_change_allowed": False,
        "production_promotion_allowed": False,
        "production_candidate_implemented": False,
        "evidence_freeze": {
            **freeze_meta,
            "counted_votes": len(rows),
            "unique_voters": len(original_voter_weights),
            "distinct_targets": len({r["target_key"] for r in rows}),
            "distinct_challenges": len({r["challenge_id"] for r in rows}),
        },
        "controlled_live_v1_5_anchor": {
            "size2_reference_points": [
                {"target_fv": t, "ratio": r} for t, r in V3_REFERENCE_POINTS
            ],
            "normalization": "raw_package_to_target_ratio / live_size2_target_multiplier",
        },
        "robustness_methodology": {
            "voter_cluster_bootstrap_draws": BOOTSTRAP_DRAWS,
            "target_cluster_bootstrap_draws": BOOTSTRAP_DRAWS,
            "minimum_bracket_pct_for_stability": MIN_BOOTSTRAP_BRACKET_PCT,
            "leave_one_voter_out": True,
            "extrapolation_allowed": False,
            "new_post_hoc_display_bias_gate_added": False,
        },
        "descriptive_checks": {
            "display_left_choice_pct": results["summary"]["display_left_choice_pct"],
            "total_effective_voter_mass": round(total_effective_mass, 6),
            "largest_single_voter_effective_mass_share": (
                round(max_voter_share, 6) if max_voter_share is not None else None
            ),
        },
        "catalog_composition_ranges": ranges,
        "composition_hardening": by_composition,
        "conclusion": {
            "evidence_supported_expansion_ceiling_for_review": ceiling,
            "production_change_recommended": False,
            "production_review_required": True,
            "formula_selection_deferred": True,
            "reason": (
                "robustness_complete_candidate_design_still_requires_human_review"
                if ceiling is not None
                else "no_contiguous_v5_expansion_band_passed_all_hardening_views"
            ),
        },
    }

    OUT_JSON.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(doc)
    print("Wrote V5 evidence hardening artifacts.")
    print("Frozen votes:", len(rows))
    print("Evidence-supported expansion ceiling for review:", ceiling)


def write_report(doc):
    lines = [
        "# Package Adjustment V5 — Evidence Hardening",
        "",
        "**RESEARCH ONLY — production V1.5 remains unchanged.**",
        "",
        f"- Generated: `{doc['generated_at_utc']}`",
        f"- Frozen counted votes: `{doc['evidence_freeze']['counted_votes']}`",
        f"- Unique voters: `{doc['evidence_freeze']['unique_voters']}`",
        f"- Evidence fingerprint: `{doc['evidence_freeze']['evidence_fingerprint_sha256']}`",
        f"- Expansion ceiling supported for review: `{doc['conclusion']['evidence_supported_expansion_ceiling_for_review']}`",
        "",
        "## Why this hardening exists",
        "",
        "The mature V5 raw-ratio fit is necessary but not sufficient for a production candidate. "
        "This pass re-expresses each ballot relative to the exact controlled-live V1.5 target-sensitive "
        "two-player curve, then checks sensitivity to both voters and target selection.",
        "",
        "## Composition robustness",
        "",
        "| Band | Raw fit stable | Live-V3 normalized factor | Voter bootstrap bracketed | Target bootstrap bracketed | Expansion review support |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for label in COMPOSITIONS:
        row = doc["composition_hardening"][label]
        norm = row["normalized_to_live_v3"]
        point = norm["point"]
        factor = "unbracketed" if not point.get("bracketed") else f"{point['ratio']:.3f}x"
        raw_ok = row["existing_raw_ratio_diagnostic"]["stable_within_tested_range"]
        vb = norm["voter_cluster_bootstrap"]["bracketed_pct"]
        tb = norm["target_cluster_bootstrap"]["bracketed_pct"]
        support = row["evidence_supported_for_expansion_review"]
        lines.append(
            f"| {label} | {raw_ok} | {factor} | {vb:.1f}% | {tb:.1f}% | {support} |"
        )

    lines += [
        "",
        "## Catalog composition coverage",
        "",
        "| Band | Actual largest-share min | Actual largest-share max | Gap from prior max |",
        "|---:|---:|---:|---:|",
    ]
    for label in COMPOSITIONS:
        row = doc["catalog_composition_ranges"][label]
        lines.append(
            f"| {label} | {row['actual_largest_share_min']:.3f} | "
            f"{row['actual_largest_share_max']:.3f} | {row['gap_from_previous_supported_max']:.3f} |"
        )

    lines += [
        "",
        "## Guardrails",
        "",
        "- No production formula is changed by this hardening pass.",
        "- No Fundamental Value, Market Value, draft-pick value, or Team Utility consumer changes.",
        "- No extrapolation beyond tested V5 evidence.",
        "- 50/50 remains the frozen V3 production anchor; V5 50/50 is a validation view, not an automatic replacement.",
        "- Expansion support must be contiguous from 55/45 outward; the analysis never jumps over a failed band.",
        "- A separate production-candidate design and human review are required before any live change.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

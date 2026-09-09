#!/usr/bin/env python3
from __future__ import annotations

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

CATALOG_PATH = ROOT / "research/package-adjustment-v5/package_vote_challenges_v5.json"
RELEASE_PATH = ROOT / "research/package-adjustment-v5/release_manifest.json"
RESULTS_PATH = ROOT / "research/package-adjustment-v5/package_vote_v5_results.json"
OUT_JSON = ROOT / "research/package-adjustment-v5/package_vote_v5_fit_diagnostics.json"
OUT_MD = ROOT / "research/package-adjustment-v5/package_vote_v5_fit_diagnostics.md"

BOOTSTRAP_DRAWS = 500
BOOTSTRAP_SEED = 20260909
MIN_BOOTSTRAP_BRACKET_PCT = 80.0
COMPOSITIONS = ("50/50", "55/45", "60/40", "65/35", "70/30", "75/25")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def quantile(values, q):
    if not values:
        return None
    xs = sorted(float(x) for x in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * float(q)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def pava_non_decreasing(ratios, package_mass, total_mass):
    """Weighted PAVA for monotone non-decreasing package-choice probability."""
    if not (len(ratios) == len(package_mass) == len(total_mass)):
        raise ValueError("PAVA inputs must have equal length")

    blocks = []
    for i, (r, p, t) in enumerate(zip(ratios, package_mass, total_mass)):
        t = float(t)
        p = float(p)
        if t <= 0:
            continue
        blocks.append({
            "start": i,
            "end": i,
            "ratio_lo": float(r),
            "ratio_hi": float(r),
            "package_mass": p,
            "total_mass": t,
            "prob": p / t,
        })

        while len(blocks) >= 2 and blocks[-2]["prob"] > blocks[-1]["prob"] + 1e-15:
            b = blocks.pop()
            a = blocks.pop()
            merged_p = a["package_mass"] + b["package_mass"]
            merged_t = a["total_mass"] + b["total_mass"]
            blocks.append({
                "start": a["start"],
                "end": b["end"],
                "ratio_lo": a["ratio_lo"],
                "ratio_hi": b["ratio_hi"],
                "package_mass": merged_p,
                "total_mass": merged_t,
                "prob": merged_p / merged_t,
            })

    fitted = [None] * len(ratios)
    for block in blocks:
        for idx in range(block["start"], block["end"] + 1):
            fitted[idx] = block["prob"]

    return fitted, blocks


def indifference_from_curve(ratios, probs):
    """Piecewise-linear 50% crossing; never extrapolates outside tested ratios."""
    observed = [(float(r), float(p)) for r, p in zip(ratios, probs) if p is not None]
    if not observed:
        return {
            "bracketed": False,
            "ratio": None,
            "reason": "no_observed_cells",
        }

    observed.sort()
    lo_r, lo_p = observed[0]
    hi_r, hi_p = observed[-1]

    if lo_p > 0.5:
        return {
            "bracketed": False,
            "ratio": None,
            "reason": "package_already_above_50_at_lowest_tested_ratio",
            "lowest_ratio": lo_r,
            "lowest_probability": lo_p,
            "highest_ratio": hi_r,
            "highest_probability": hi_p,
        }

    if hi_p < 0.5:
        return {
            "bracketed": False,
            "ratio": None,
            "reason": "package_still_below_50_at_highest_tested_ratio",
            "lowest_ratio": lo_r,
            "lowest_probability": lo_p,
            "highest_ratio": hi_r,
            "highest_probability": hi_p,
        }

    for r, p in observed:
        if abs(p - 0.5) <= 1e-15:
            return {
                "bracketed": True,
                "ratio": r,
                "reason": "exact_50_pct_cell",
            }

    for (r0, p0), (r1, p1) in zip(observed, observed[1:]):
        if p0 <= 0.5 <= p1:
            if abs(p1 - p0) <= 1e-15:
                return {
                    "bracketed": True,
                    "ratio": (r0 + r1) / 2.0,
                    "reason": "flat_50_pct_plateau",
                }
            frac = (0.5 - p0) / (p1 - p0)
            return {
                "bracketed": True,
                "ratio": r0 + frac * (r1 - r0),
                "reason": "piecewise_linear_interpolation",
                "bracket_low_ratio": r0,
                "bracket_low_probability": p0,
                "bracket_high_ratio": r1,
                "bracket_high_probability": p1,
            }

    raise RuntimeError("50% crossing should have been found after endpoint bracketing")


def build_cell_masses(rows, catalog, row_weight_multiplier=None):
    """Aggregate package/total effective mass by composition x ratio."""
    if row_weight_multiplier is None:
        row_weight_multiplier = lambda row: 1.0

    voter_weights = pipe.voter_weights(rows)
    cells = defaultdict(lambda: defaultdict(lambda: {
        "raw_votes": 0,
        "raw_package_votes": 0,
        "package_mass": 0.0,
        "total_mass": 0.0,
        "targets": set(),
        "challenges": set(),
    }))

    for row in rows:
        challenge = catalog.get(row["challenge_id"])
        if challenge is None:
            continue
        label = challenge["composition_target"]["label"]
        ratio = float(challenge["ratio_target"])
        base_weight = float(voter_weights[row["voter_roster_id"]]["ballot_weight"])
        multiplier = float(row_weight_multiplier(row))
        w = base_weight * multiplier
        if w <= 0:
            continue

        cell = cells[label][ratio]
        cell["raw_votes"] += 1
        if row["choice"] == "P":
            cell["raw_package_votes"] += 1
            cell["package_mass"] += w
        cell["total_mass"] += w
        cell["targets"].add(challenge["target"]["key"])
        cell["challenges"].add(challenge["id"])

    return cells


def analyze_cells(cells, catalog_doc):
    analyses = {}
    feasible = catalog_doc["design"]["feasible_ratio_grid_by_composition"]

    for label in COMPOSITIONS:
        ratios = [float(x) for x in feasible[label]]
        label_cells = cells.get(label, {})

        raw_rates = []
        package_mass = []
        total_mass = []
        cell_rows = []

        for ratio in ratios:
            c = label_cells.get(ratio)
            if c is None or c["total_mass"] <= 0:
                raw_rates.append(None)
                package_mass.append(0.0)
                total_mass.append(0.0)
                cell_rows.append({
                    "ratio": ratio,
                    "raw_votes": 0,
                    "raw_package_choice_pct": None,
                    "weighted_package_choice_pct": None,
                    "distinct_targets": 0,
                    "distinct_challenges": 0,
                })
                continue

            raw_rate = c["raw_package_votes"] / c["raw_votes"]
            weighted_rate = c["package_mass"] / c["total_mass"]
            raw_rates.append(weighted_rate)
            package_mass.append(c["package_mass"])
            total_mass.append(c["total_mass"])
            cell_rows.append({
                "ratio": ratio,
                "raw_votes": c["raw_votes"],
                "raw_package_choice_pct": round(100.0 * raw_rate, 3),
                "weighted_package_choice_pct": round(100.0 * weighted_rate, 3),
                "distinct_targets": len(c["targets"]),
                "distinct_challenges": len(c["challenges"]),
            })

        observed_idx = [i for i, t in enumerate(total_mass) if t > 0]
        observed_ratios = [ratios[i] for i in observed_idx]
        observed_package_mass = [package_mass[i] for i in observed_idx]
        observed_total_mass = [total_mass[i] for i in observed_idx]

        if not observed_idx:
            fitted_full = [None] * len(ratios)
            blocks = []
            crossing = {
                "bracketed": False,
                "ratio": None,
                "reason": "no_observed_cells",
            }
        else:
            fitted_observed, blocks = pava_non_decreasing(
                observed_ratios,
                observed_package_mass,
                observed_total_mass,
            )
            fitted_full = [None] * len(ratios)
            for idx, fitted in zip(observed_idx, fitted_observed):
                fitted_full[idx] = fitted
            crossing = indifference_from_curve(observed_ratios, fitted_observed)

        # Raw weighted-rate reversals are diagnostic only. PAVA fixes them
        # without pretending the noisy observed sequence is exactly monotone.
        reversals = 0
        last = None
        for value in raw_rates:
            if value is None:
                continue
            if last is not None and value < last - 1e-12:
                reversals += 1
            last = value

        for row, fitted in zip(cell_rows, fitted_full):
            row["isotonic_package_choice_pct"] = (
                round(100.0 * fitted, 3) if fitted is not None else None
            )

        analyses[label] = {
            "cells": cell_rows,
            "raw_weighted_monotonicity_reversals": reversals,
            "isotonic_blocks": [{
                "ratio_lo": round(float(b["ratio_lo"]), 6),
                "ratio_hi": round(float(b["ratio_hi"]), 6),
                "weighted_package_choice_pct": round(100.0 * float(b["prob"]), 3),
                "effective_vote_mass": round(float(b["total_mass"]), 6),
            } for b in blocks],
            "indifference": {
                k: (round(v, 6) if isinstance(v, float) else v)
                for k, v in crossing.items()
            },
        }

    return analyses


def cluster_bootstrap(rows, catalog, catalog_doc, draws=BOOTSTRAP_DRAWS):
    voters = sorted({row["voter_roster_id"] for row in rows})
    if not voters:
        return {
            label: {
                "draws": draws,
                "bracketed_draws": 0,
                "bracketed_pct": 0.0,
                "median_ratio": None,
                "ci90_low": None,
                "ci90_high": None,
            }
            for label in COMPOSITIONS
        }

    by_voter = defaultdict(list)
    for row in rows:
        by_voter[row["voter_roster_id"]].append(row)

    rng = random.Random(BOOTSTRAP_SEED)
    sampled_ratios = {label: [] for label in COMPOSITIONS}
    bracketed_counts = CounterCompat()

    for _ in range(draws):
        picks = [rng.choice(voters) for _ in voters]
        multiplicity = defaultdict(int)
        for voter in picks:
            multiplicity[voter] += 1

        sampled_rows = []
        for voter, mult in multiplicity.items():
            # Preserve each selected voter's capped ballot cluster. Repeating
            # the cluster by multiplicity is the standard nonparametric
            # cluster-bootstrap resample.
            for row in by_voter[voter]:
                sampled_rows.extend([row] * mult)

        cells = build_cell_masses(sampled_rows, catalog)
        analyses = analyze_cells(cells, catalog_doc)

        for label in COMPOSITIONS:
            ind = analyses[label]["indifference"]
            if ind["bracketed"]:
                sampled_ratios[label].append(float(ind["ratio"]))
                bracketed_counts[label] += 1

    out = {}
    for label in COMPOSITIONS:
        vals = sampled_ratios[label]
        bracketed = int(bracketed_counts[label])
        out[label] = {
            "draws": draws,
            "bracketed_draws": bracketed,
            "bracketed_pct": round(100.0 * bracketed / draws, 2) if draws else 0.0,
            "median_ratio": round(statistics.median(vals), 6) if vals else None,
            "ci90_low": round(quantile(vals, 0.05), 6) if vals else None,
            "ci90_high": round(quantile(vals, 0.95), 6) if vals else None,
        }
    return out


class CounterCompat(defaultdict):
    def __init__(self):
        super().__init__(int)


def write_report(doc):
    lines = [
        "# Package Adjustment V5 — Composition Fit Diagnostics",
        "",
        "**RESEARCH ONLY — no automatic production change is allowed.**",
        "",
        f"- Generated: `{doc['generated_at_utc']}`",
        f"- Status: `{doc['status']}`",
        f"- Production revision remains: `{doc['production_revision']}`",
        f"- Counted V5 votes: `{doc['evidence']['counted_votes']}`",
        f"- Unique V5 voters: `{doc['evidence']['unique_voters']}`",
        f"- Diagnostic data gates passed: `{doc['evidence']['data_gates_all_passed']}`",
        "",
    ]

    if doc["status"] == "waiting_for_maturity":
        lines += [
            "## Waiting for evidence",
            "",
            "The V5 vote experiment is live, but the preregistered evidence gates have not all passed.",
            "No composition indifference ratios are being promoted or extrapolated from immature data.",
            "",
        ]
    else:
        lines += [
            "## Estimated 50% indifference by composition",
            "",
            "| Composition | Indifference ratio | 90% voter-cluster bootstrap CI | Bootstrap bracketed |",
            "|---:|---:|---:|---:|",
        ]
        for label in COMPOSITIONS:
            row = doc["composition_diagnostics"][label]
            ind = row["indifference"]
            boot = row["bootstrap"]
            ratio = "unbracketed" if not ind["bracketed"] else f"{ind['ratio']:.3f}x"
            ci = (
                "n/a"
                if boot["ci90_low"] is None
                else f"{boot['ci90_low']:.3f}–{boot['ci90_high']:.3f}x"
            )
            lines.append(
                f"| {label} | {ratio} | {ci} | {boot['bracketed_pct']:.1f}% |"
            )

        lines += [
            "",
            "## Interpretation guardrails",
            "",
            "- Primary estimator: voter-capped weighted isotonic package-choice curve within each composition band.",
            "- 50% indifference is interpolated only between tested ratio cells.",
            "- No extrapolation is allowed outside a composition band's tested ratio range.",
            "- Uncertainty uses a voter-cluster bootstrap so one heavy voter is not treated as many independent people.",
            "- Any future production change still requires a separate reviewed hardening step.",
            "",
        ]

    lines += [
        "## Production isolation",
        "",
        "- Fundamental Value unchanged.",
        "- Market Value unchanged.",
        "- Draft-pick values unchanged.",
        "- Team Utility unchanged.",
        "- Controlled-live Package Adjustment V1.5 formula unchanged.",
        "- `production_promotion_allowed` remains `False` in this diagnostic artifact.",
        "",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def selftest():
    ratios = [1.1, 1.2, 1.3, 1.4]
    package = [2.0, 6.0, 4.0, 9.0]
    total = [10.0, 10.0, 10.0, 10.0]
    fitted, blocks = pava_non_decreasing(ratios, package, total)
    assert len(blocks) == 3
    assert abs(fitted[0] - 0.2) < 1e-12
    assert abs(fitted[1] - 0.5) < 1e-12
    assert abs(fitted[2] - 0.5) < 1e-12
    assert abs(fitted[3] - 0.9) < 1e-12

    crossing = indifference_from_curve(ratios, fitted)
    assert crossing["bracketed"] is True
    assert abs(crossing["ratio"] - 1.2) < 1e-12

    unbracketed = indifference_from_curve(
        [1.1, 1.2, 1.3],
        [0.1, 0.2, 0.3],
    )
    assert unbracketed["bracketed"] is False
    assert unbracketed["reason"] == "package_still_below_50_at_highest_tested_ratio"

    print("Package Preference V5 diagnostics self-test passed.")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    catalog_doc = read_json(CATALOG_PATH)
    release = read_json(RELEASE_PATH)
    results = read_json(RESULTS_PATH)

    if catalog_doc.get("status") != "frozen_package_preference_v5":
        raise RuntimeError("unexpected V5 catalog")
    if catalog_doc.get("frozen") is not True:
        raise RuntimeError("V5 catalog must be frozen")
    if release.get("status") != "package_adjustment_v5_composition_vote_release":
        raise RuntimeError("unexpected V5 release")
    if release.get("frozen") is not True:
        raise RuntimeError("V5 release must be frozen")
    if results.get("status") != "research_only":
        raise RuntimeError("unexpected V5 results status")

    gates = results["summary"]["diagnostic_data_gates"]
    now = datetime.now(timezone.utc).isoformat()

    common = {
        "schema_version": 1,
        "generated_at_utc": now,
        "research_only": True,
        "production_revision": "v1.5-audit-step6-scope-ui-idp",
        "production_formula_changed": False,
        "fundamental_value_consumer_changed": False,
        "market_value_consumer_changed": False,
        "draft_pick_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "trade_verdict_consumer_changed": False,
        "automatic_production_change_allowed": False,
        "production_promotion_allowed": False,
        "release_id": release["release_id"],
        "methodology": {
            "primary_estimator": "voter_capped_weighted_isotonic_by_composition",
            "indifference_definition": "piecewise_linear_50_pct_crossing_within_tested_cells",
            "extrapolation_allowed": False,
            "uncertainty": "nonparametric_voter_cluster_bootstrap",
            "bootstrap_draws": BOOTSTRAP_DRAWS,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "minimum_bootstrap_bracket_pct_for_stability": MIN_BOOTSTRAP_BRACKET_PCT,
        },
        "evidence": {
            "counted_votes": int(results["summary"]["raw_vote_count"]),
            "unique_voters": int(results["summary"]["unique_voters"]),
            "distinct_challenges": int(results["summary"]["distinct_challenges"]),
            "distinct_targets": int(results["summary"]["distinct_targets"]),
            "data_gates": gates["passed"],
            "data_gates_all_passed": bool(gates["all_passed"]),
        },
    }

    if not gates["all_passed"]:
        doc = {
            **common,
            "status": "waiting_for_maturity",
            "composition_diagnostics": {},
            "conclusion": {
                "fit_ready": False,
                "reason": "preregistered_v5_data_gates_not_all_passed",
                "production_change_recommended": False,
            },
        }
        OUT_JSON.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_report(doc)
        print("V5 diagnostics waiting for maturity.")
        print("Votes:", common["evidence"]["counted_votes"])
        print("Voters:", common["evidence"]["unique_voters"])
        return

    # Re-fetch the reserved V5 rows so voter-cluster uncertainty can be
    # calculated without storing raw ballots in the diagnostic artifact.
    raw = [pipe.parse_row(r) for r in pipe.fetch_rows() if pipe.is_package_v5_row(r)]
    raw = [r for r in raw if r is not None]
    post, _, _ = pipe.filter_after_release(raw, release)
    capped, _ = pipe.apply_daily_cap(post)

    catalog = {c["id"]: c for c in catalog_doc["challenges"]}
    valid = [r for r in capped if r["challenge_id"] in catalog]

    if len(valid) != int(results["summary"]["raw_vote_count"]):
        raise RuntimeError(
            "V5 diagnostic vote count drift vs aggregation result: "
            f"{len(valid)} != {results['summary']['raw_vote_count']}"
        )

    cells = build_cell_masses(valid, catalog)
    analyses = analyze_cells(cells, catalog_doc)
    bootstrap = cluster_bootstrap(valid, catalog, catalog_doc)

    composition_diagnostics = {}
    all_point_bracketed = True
    all_bootstrap_stable = True

    for label in COMPOSITIONS:
        point = analyses[label]
        boot = bootstrap[label]
        point_bracketed = bool(point["indifference"]["bracketed"])
        stable = (
            point_bracketed
            and float(boot["bracketed_pct"]) >= MIN_BOOTSTRAP_BRACKET_PCT
        )
        all_point_bracketed = all_point_bracketed and point_bracketed
        all_bootstrap_stable = all_bootstrap_stable and stable
        composition_diagnostics[label] = {
            **point,
            "bootstrap": boot,
            "stable_within_tested_range": stable,
        }

    fit_ready = all_point_bracketed and all_bootstrap_stable

    doc = {
        **common,
        "status": "research_diagnostics_complete",
        "composition_diagnostics": composition_diagnostics,
        "conclusion": {
            "fit_ready": fit_ready,
            "all_compositions_point_estimate_bracketed": all_point_bracketed,
            "all_compositions_bootstrap_stable": all_bootstrap_stable,
            "production_change_recommended": False,
            "production_review_allowed": fit_ready,
            "reason": (
                "all_composition_indifference_points_stable_within_tested_ranges"
                if fit_ready
                else "one_or_more_composition_bands_not_stably_bracketed"
            ),
        },
    }

    OUT_JSON.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(doc)

    print("Wrote V5 fit diagnostics.")
    print("Fit ready for human production review:", fit_ready)
    for label in COMPOSITIONS:
        ind = composition_diagnostics[label]["indifference"]
        boot = composition_diagnostics[label]["bootstrap"]
        print(label, "indifference:", ind, "bootstrap:", boot)


if __name__ == "__main__":
    main()


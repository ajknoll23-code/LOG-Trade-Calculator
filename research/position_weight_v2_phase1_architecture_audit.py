#!/usr/bin/env python3
"""
Position Weight / Cross-Position Economics V2 — Phase 1 architecture audit.

Research only. No POSITION_WEIGHT change is authorized.

Purpose
-------
Replacement Level V2 has now isolated and frozen the within-position
normalization question. POSITION_WEIGHT has a different job: translate one unit
of normalized relative production into cross-position dynasty/economic value.

This Phase 1 does NOT create new weights. It inventories three independent
signals that must not be conflated:

1. Current POSITION_WEIGHT from index.html.
2. Historical lineup demand from roster-economics start-rate research.
3. Historical absolute scoring scale at each frozen replacement rank family
   using 2024-2025 league-scored weekly points.

The key scoring-scale diagnostic is:
    replacement PPG at position / replacement PPG at WR

If two players are both 1.5x their position replacement level, the absolute
lineup-point surplus represented by that same relative-production increment
depends on the position's replacement PPG. That is a cross-position scale issue;
it is not the same thing as replacement-rank selection.

Likewise, effective lineup demand is an exposure/scarcity signal; directly
mapping "more starters" into POSITION_WEIGHT would be unjustified because it
ignores scoring leverage and player supply.

Outputs
-------
research/position-weight-v2/position_weight_v2_phase1_architecture_audit.json
research/position-weight-v2/position_weight_v2_phase1_architecture_audit.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

INDEX_HTML = REPO_ROOT / "index.html"
ROBUSTNESS_JSON = (
    REPO_ROOT
    / "research"
    / "roster-economics"
    / "roster_economics_robustness.json"
)
WEEKLY_POINTS_JSON = (
    REPO_ROOT
    / "research"
    / "roster-economics"
    / "weekly_points_by_season.json"
)
REPLACEMENT_PHASE5_FROZEN = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase5_frozen_candidates.json"
)

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "position-weight-v2"
    / "position_weight_v2_phase1_architecture_audit.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "position-weight-v2"
    / "position_weight_v2_phase1_architecture_audit.md"
)

METHOD_VERSION = "position-weight-v2-phase1-architecture-audit-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
REFERENCE_POSITION = "WR"
SEASONS = ("2024", "2025")
MIN_GAMES = 3
REGULAR_SEASON_MAX_WEEK = 18

EXPECTED_REPLACEMENT_METHOD = "replacement-level-v2-phase5-prospective-v1"
EXPECTED_FAMILIES = (
    "legacy_control",
    "prior_limited_evidence",
    "stable_positions_only",
    "full_phase2_leaders",
)


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def round_numbers(obj, digits=6):
    if isinstance(obj, dict):
        return {k: round_numbers(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_numbers(v, digits) for v in obj]
    if isinstance(obj, float):
        return round(obj, digits) if math.isfinite(obj) else None
    return obj


def median(values):
    vals = [
        float(v)
        for v in values
        if v is not None and math.isfinite(float(v))
    ]
    return statistics.median(vals) if vals else None


def coefficient_of_variation(values):
    vals = [
        float(v)
        for v in values
        if v is not None and math.isfinite(float(v))
    ]
    if len(vals) < 2:
        return None
    mean = statistics.fmean(vals)
    if abs(mean) < 1e-12:
        return None
    return statistics.pstdev(vals) / abs(mean)


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def validate_inputs(
    robustness: dict[str, Any],
    frozen: dict[str, Any],
) -> None:
    positions = robustness.get("positions")
    if not isinstance(positions, dict):
        raise RuntimeError("roster economics robustness positions missing")

    for pos in TRACKED_POSITIONS:
        row = positions.get(pos)
        if not isinstance(row, dict):
            raise RuntimeError(f"roster economics missing {pos}")
        if row.get("effective_demand") is None:
            raise RuntimeError(f"{pos}: effective demand missing")
        coverage = row.get("coverage_ranks")
        if not isinstance(coverage, dict):
            raise RuntimeError(f"{pos}: coverage ranks missing")
        for pct in ("80", "90", "95"):
            if coverage.get(pct) is None:
                raise RuntimeError(f"{pos}: {pct}% coverage rank missing")

    if frozen.get("method_version") != EXPECTED_REPLACEMENT_METHOD:
        raise RuntimeError("unexpected Replacement Level V2 Phase-5 method")
    if frozen.get("variant_manifest") != list(EXPECTED_FAMILIES):
        raise RuntimeError("Replacement Level V2 frozen family manifest changed")
    if frozen.get("deployment_authorized") is not False:
        raise RuntimeError("Replacement Level V2 unexpectedly authorizes deployment")
    if int(frozen.get("cohort_size") or 0) != 518:
        raise RuntimeError("Replacement Level V2 frozen cohort size changed")

    variants = frozen.get("variants")
    if not isinstance(variants, dict):
        raise RuntimeError("Replacement Level V2 variants missing")
    for family in EXPECTED_FAMILIES:
        row = variants.get(family)
        if not isinstance(row, dict):
            raise RuntimeError(f"replacement family missing: {family}")
        ranks = row.get("replacement_ranks")
        if not isinstance(ranks, dict):
            raise RuntimeError(f"{family}: replacement ranks missing")
        for pos in TRACKED_POSITIONS:
            rank = int(ranks.get(pos) or 0)
            if rank <= 0:
                raise RuntimeError(f"{family}/{pos}: invalid replacement rank")


def regular_season_ppg_rows(
    weekly_points: dict[str, Any],
    season: str,
    pos: str,
) -> list[dict[str, Any]]:
    seasons = weekly_points.get("seasons")
    if not isinstance(seasons, dict):
        raise RuntimeError("weekly points missing seasons object")
    players = seasons.get(season)
    if not isinstance(players, dict):
        raise RuntimeError(f"weekly points missing season {season}")

    rows = []
    for pid, rec in players.items():
        if str(rec.get("pos_bucket") or "").upper() != pos:
            continue
        weekly = rec.get("weekly_points")
        if not isinstance(weekly, dict):
            continue

        points = []
        for week_raw, value in weekly.items():
            try:
                week = int(week_raw)
                pts = float(value)
            except (TypeError, ValueError):
                continue
            if 1 <= week <= REGULAR_SEASON_MAX_WEEK and math.isfinite(pts):
                points.append(pts)

        if len(points) < MIN_GAMES:
            continue

        rows.append({
            "player_id": str(pid),
            "name": rec.get("name") or str(pid),
            "games": len(points),
            "ppg": statistics.fmean(points),
            "total_points": sum(points),
        })

    rows.sort(key=lambda r: (-float(r["ppg"]), str(r["name"])))
    return rows


def replacement_scoring_scale(
    weekly_points: dict[str, Any],
    ranks: dict[str, int],
) -> dict[str, Any]:
    by_season = {}
    for season in SEASONS:
        pos_rows = {}
        for pos in TRACKED_POSITIONS:
            rows = regular_season_ppg_rows(weekly_points, season, pos)
            rank = int(ranks[pos])
            if len(rows) < rank:
                raise RuntimeError(
                    f"{season}/{pos}: only {len(rows)} eligible rows for rank {rank}"
                )
            anchor = rows[rank - 1]
            pos_rows[pos] = {
                "rank": rank,
                "eligible_player_count": len(rows),
                "replacement_player": anchor["name"],
                "replacement_ppg": float(anchor["ppg"]),
            }

        wr_ppg = float(pos_rows[REFERENCE_POSITION]["replacement_ppg"])
        if wr_ppg <= 0:
            raise RuntimeError(f"{season}: WR replacement PPG non-positive")
        for pos in TRACKED_POSITIONS:
            pos_rows[pos]["replacement_ppg_ratio_vs_wr"] = (
                float(pos_rows[pos]["replacement_ppg"]) / wr_ppg
            )
        by_season[season] = pos_rows

    summary = {}
    for pos in TRACKED_POSITIONS:
        ppgs = [
            by_season[season][pos]["replacement_ppg"]
            for season in SEASONS
        ]
        ratios = [
            by_season[season][pos]["replacement_ppg_ratio_vs_wr"]
            for season in SEASONS
        ]
        summary[pos] = {
            "median_replacement_ppg": median(ppgs),
            "median_replacement_ppg_ratio_vs_wr": median(ratios),
            "season_to_season_ratio_cv": coefficient_of_variation(ratios),
            "by_season": {
                season: by_season[season][pos]
                for season in SEASONS
            },
        }

    return {
        "by_season": by_season,
        "summary_by_position": summary,
    }


def build_result():
    robustness = read_json(ROBUSTNESS_JSON)
    weekly_points = read_json(WEEKLY_POINTS_JSON)
    frozen = read_json(REPLACEMENT_PHASE5_FROZEN)
    validate_inputs(robustness, frozen)

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    weights = {
        pos: float(cfg["position_weight"][pos])
        for pos in TRACKED_POSITIONS
    }
    wr_weight = weights[REFERENCE_POSITION]
    if wr_weight <= 0:
        raise RuntimeError("WR POSITION_WEIGHT must be positive")

    roster_positions = robustness["positions"]
    wr_demand = float(
        roster_positions[REFERENCE_POSITION]["effective_demand"]
    )
    if wr_demand <= 0:
        raise RuntimeError("WR effective demand must be positive")

    rank_families = {
        family: {
            pos: int(
                frozen["variants"][family]["replacement_ranks"][pos]
            )
            for pos in TRACKED_POSITIONS
        }
        for family in EXPECTED_FAMILIES
    }

    scoring = {
        family: replacement_scoring_scale(
            weekly_points,
            rank_families[family],
        )
        for family in EXPECTED_FAMILIES
    }

    positions = {}
    for pos in TRACKED_POSITIONS:
        r = roster_positions[pos]
        current_weight_ratio = weights[pos] / wr_weight
        demand_ratio = float(r["effective_demand"]) / wr_demand

        family_scoring_ratios = {
            family: float(
                scoring[family]["summary_by_position"][pos][
                    "median_replacement_ppg_ratio_vs_wr"
                ]
            )
            for family in EXPECTED_FAMILIES
        }

        scoring_ratio_values = list(family_scoring_ratios.values())
        scoring_ratio_median = median(scoring_ratio_values)
        scoring_ratio_cv = coefficient_of_variation(scoring_ratio_values)

        boot = r.get("bootstrap_50pct_crossing") or {}
        coverage = r.get("coverage_ranks") or {}
        crossing = (r.get("bin_width_sensitivity") or {}).get(
            "crossing_by_width"
        ) or {}

        positions[pos] = {
            "current_position_weight": weights[pos],
            "current_weight_ratio_vs_wr": current_weight_ratio,
            "roster_economics": {
                "effective_demand": float(r["effective_demand"]),
                "effective_demand_ratio_vs_wr": demand_ratio,
                "coverage_rank_80": int(coverage["80"]),
                "coverage_rank_90": int(coverage["90"]),
                "coverage_rank_95": int(coverage["95"]),
                "bootstrap_50pct_crossing_median": boot.get("median"),
                "bootstrap_50pct_crossing_p10": boot.get("p10"),
                "bootstrap_50pct_crossing_p90": boot.get("p90"),
                "bootstrap_resolved": boot.get("n_resolved"),
                "bin_width_crossing_rank_1": crossing.get("1"),
                "bin_width_crossing_rank_3": crossing.get("3"),
                "bin_width_crossing_rank_5": crossing.get("5"),
                "bin_width_crossing_stable": (
                    (r.get("bin_width_sensitivity") or {}).get("stable")
                ),
            },
            "replacement_scoring_scale": {
                "ratio_vs_wr_by_frozen_rank_family": family_scoring_ratios,
                "median_ratio_vs_wr_across_families": scoring_ratio_median,
                "cv_across_families": scoring_ratio_cv,
                "family_detail": {
                    family: scoring[family]["summary_by_position"][pos]
                    for family in EXPECTED_FAMILIES
                },
            },
            "diagnostic_only_comparisons": {
                "current_weight_divided_by_demand_ratio": (
                    current_weight_ratio / demand_ratio
                    if demand_ratio > 0 else None
                ),
                "current_weight_divided_by_scoring_scale_ratio": (
                    current_weight_ratio / scoring_ratio_median
                    if scoring_ratio_median and scoring_ratio_median > 0
                    else None
                ),
                "demand_times_scoring_scale_index_vs_wr": (
                    demand_ratio * scoring_ratio_median
                    if scoring_ratio_median is not None else None
                ),
            },
        }

    return round_numbers({
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_POSITION_WEIGHT_ARCHITECTURE_AUDIT",
        "deployment_authorized": False,
        "position_weight_change_authorized": False,
        "replacement_rank_change_authorized": False,
        "production_v2_change_authorized": False,
        "transform_change_authorized": False,
        "scale_change_authorized": False,
        "frozen_prospective_experiments_touched": False,
        "reference_position": REFERENCE_POSITION,
        "current_position_weights": weights,
        "frozen_replacement_rank_families": rank_families,
        "positions": positions,
        "architecture_findings": {
            "replacement_rank_job": (
                "within-position production normalization; already frozen in "
                "Replacement Level V2 Phase 5"
            ),
            "position_weight_job": (
                "cross-position translation of normalized production into "
                "league-specific economic/lineup value"
            ),
            "effective_demand_is_not_a_weight_target": True,
            "replacement_ppg_ratio_is_not_a_weight_target": True,
            "market_value_is_not_used_as_ground_truth": True,
            "reason_not_to_map_demand_directly": (
                "start exposure ignores absolute scoring leverage and player supply"
            ),
            "reason_not_to_map_replacement_ppg_directly": (
                "absolute scoring leverage ignores lineup demand/scarcity and "
                "cross-position opportunity cost"
            ),
            "phase2_required": (
                "historical out-of-sample marginal-lineup-utility calibration "
                "that combines scoring surplus and observed lineup demand while "
                "holding replacement ranks fixed within each tested family"
            ),
        },
        "phase2_design_constraints": {
            "must_use_preweek_or_training_only_prediction_inputs": True,
            "future_target_must_be_out_of_sample": True,
            "replacement_rank_family_must_be_held_fixed_per_scenario": True,
            "position_weights_must_be_the_only_cross_position_scaler_varied": True,
            "do_not_use_current_fundamental_value_as_target": True,
            "do_not_use_market_value_as_target": True,
            "do_not_jointly_calibrate_global_scale": True,
            "do_not_jointly_calibrate_pm_transform": True,
            "do_not_jointly_calibrate_age_or_role": True,
            "do_not_retest_no_history_semantics": True,
        },
        "input_sha256": {
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
            str(ROBUSTNESS_JSON.relative_to(REPO_ROOT)): sha256(
                ROBUSTNESS_JSON
            ),
            str(WEEKLY_POINTS_JSON.relative_to(REPO_ROOT)): sha256(
                WEEKLY_POINTS_JSON
            ),
            str(REPLACEMENT_PHASE5_FROZEN.relative_to(REPO_ROOT)): sha256(
                REPLACEMENT_PHASE5_FROZEN
            ),
        },
    })


def fmt(value, digits=3):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def render_md(result):
    lines = [
        "# Position Weight / Cross-Position Economics V2 — Phase 1 Architecture Audit",
        "",
        "**Research only. No POSITION_WEIGHT change is authorized.**",
        "",
        f"Method: `{result['method_version']}`",
        "",
        "## Architecture",
        "",
        "- **Replacement rank:** within-position production normalization. This is already isolated and frozen prospectively.",
        "- **POSITION_WEIGHT:** cross-position translation of the same normalized production unit into league-specific economic value.",
        "- **Global scale:** absolute display/value-unit scale; not calibrated here.",
        "",
        "Phase 1 deliberately does **not** turn start demand or replacement PPG directly into a new weight. Each is only one axis of cross-position economics.",
        "",
        "## Current weights versus independent league signals",
        "",
        "| Pos | Current PW | PW vs WR | Effective demand | Demand vs WR | 80/90/95% start coverage | Bootstrap 50% crossing | Median replacement-PPG scale vs WR | Rank-family scale CV |",
        "|---|---:|---:|---:|---:|---|---|---:|---:|",
    ]

    for pos in TRACKED_POSITIONS:
        p = result["positions"][pos]
        r = p["roster_economics"]
        s = p["replacement_scoring_scale"]
        crossing = (
            f"{r['bootstrap_50pct_crossing_median']} "
            f"[{r['bootstrap_50pct_crossing_p10']}, "
            f"{r['bootstrap_50pct_crossing_p90']}]"
        )
        lines.append(
            f"| {pos} | {fmt(p['current_position_weight'], 2)} | "
            f"{fmt(p['current_weight_ratio_vs_wr'], 3)} | "
            f"{fmt(r['effective_demand'], 2)} | "
            f"{fmt(r['effective_demand_ratio_vs_wr'], 3)} | "
            f"{r['coverage_rank_80']}/{r['coverage_rank_90']}/{r['coverage_rank_95']} | "
            f"{crossing} | "
            f"{fmt(s['median_ratio_vs_wr_across_families'], 3)} | "
            f"{fmt(s['cv_across_families'], 3)} |"
        )

    lines += [
        "",
        "## Historical replacement scoring scale by frozen rank family",
        "",
        "Each cell is the median 2024–2025 replacement PPG ratio versus WR under that already-frozen replacement-rank family.",
        "",
        "| Pos | Legacy | Prior evidence | Stable-only | Full leaders |",
        "|---|---:|---:|---:|---:|",
    ]

    for pos in TRACKED_POSITIONS:
        ratios = result["positions"][pos]["replacement_scoring_scale"][
            "ratio_vs_wr_by_frozen_rank_family"
        ]
        lines.append(
            f"| {pos} | {fmt(ratios['legacy_control'])} | "
            f"{fmt(ratios['prior_limited_evidence'])} | "
            f"{fmt(ratios['stable_positions_only'])} | "
            f"{fmt(ratios['full_phase2_leaders'])} |"
        )

    lines += [
        "",
        "## Diagnostic mismatches",
        "",
        "These are **not candidate weights**. They only show where the current multiplier is far from either raw-demand scale or absolute replacement-scoring scale.",
        "",
        "| Pos | Current PW / demand index | Current PW / scoring-scale index | Demand × scoring index vs WR |",
        "|---|---:|---:|---:|",
    ]
    for pos in TRACKED_POSITIONS:
        d = result["positions"][pos]["diagnostic_only_comparisons"]
        lines.append(
            f"| {pos} | "
            f"{fmt(d['current_weight_divided_by_demand_ratio'])} | "
            f"{fmt(d['current_weight_divided_by_scoring_scale_ratio'])} | "
            f"{fmt(d['demand_times_scoring_scale_index_vs_wr'])} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "A direct `effective demand → POSITION_WEIGHT` mapping is rejected because it ignores absolute scoring leverage and available supply.",
        "",
        "A direct `replacement PPG ratio → POSITION_WEIGHT` mapping is also rejected because it ignores how often the position occupies scarce lineup slots.",
        "",
        "Market Value is intentionally **not** used as ground truth. Fundamental Value should remain independently grounded in league scoring/economics rather than being trained to imitate the market layer.",
        "",
        "## Phase 2",
        "",
        "Build a historical out-of-sample **marginal lineup utility** target. The target should combine:",
        "",
        "1. future realized scoring surplus above a future-only replacement structure, and",
        "2. observed lineup demand/exposure for the position.",
        "",
        "Then test cross-position weight families while holding replacement rank, PM transform, age, role, no-history semantics, and global scale fixed. POSITION_WEIGHT must be the only cross-position scaler allowed to move.",
        "",
        "## Guardrails",
        "",
        "- deployment_authorized: **false**",
        "- position_weight_change_authorized: **false**",
        "- replacement_rank_change_authorized: **false**",
        "- production_v2_change_authorized: **false**",
        "- transform_change_authorized: **false**",
        "- scale_change_authorized: **false**",
        "- frozen prospective experiments touched: **false**",
        "",
    ]
    return "\n".join(lines)


def run_selftest():
    assert median([1, 3, 2]) == 2
    assert abs(coefficient_of_variation([1.0, 1.0]) - 0.0) < 1e-12

    synthetic = {
        "seasons": {
            "2024": {
                **{
                    f"wr{i}": {
                        "pos_bucket": "WR",
                        "name": f"wr{i}",
                        "weekly_points": {"1": 20-i, "2": 20-i, "3": 20-i},
                    }
                    for i in range(1, 8)
                },
                **{
                    f"qb{i}": {
                        "pos_bucket": "QB",
                        "name": f"qb{i}",
                        "weekly_points": {"1": 30-i, "2": 30-i, "3": 30-i},
                    }
                    for i in range(1, 8)
                },
            },
            "2025": {
                **{
                    f"wr{i}": {
                        "pos_bucket": "WR",
                        "name": f"wr{i}",
                        "weekly_points": {"1": 18-i, "2": 18-i, "3": 18-i},
                    }
                    for i in range(1, 8)
                },
                **{
                    f"qb{i}": {
                        "pos_bucket": "QB",
                        "name": f"qb{i}",
                        "weekly_points": {"1": 28-i, "2": 28-i, "3": 28-i},
                    }
                    for i in range(1, 8)
                },
            },
        }
    }
    # Exercise the basic row builder independently of the 7-position rank-family
    # function, which intentionally requires the real full positional universe.
    wr_rows = regular_season_ppg_rows(synthetic, "2024", "WR")
    qb_rows = regular_season_ppg_rows(synthetic, "2024", "QB")
    assert len(wr_rows) == 7 and len(qb_rows) == 7
    assert qb_rows[0]["ppg"] > wr_rows[0]["ppg"]

    print("PASS Position Weight V2 Phase 1 self-test.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        if not args.write and not args.check:
            return

    result = build_result()
    rendered_json = json.dumps(result, indent=2, sort_keys=True) + "\n"
    rendered_md = render_md(result).rstrip() + "\n"

    if args.write:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(rendered_json, encoding="utf-8")
        OUTPUT_MD.write_text(rendered_md, encoding="utf-8")
        print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
        print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")

    if args.check:
        if not OUTPUT_JSON.exists() or not OUTPUT_MD.exists():
            raise RuntimeError("Phase 1 outputs missing; run --write first")
        if OUTPUT_JSON.read_text(encoding="utf-8") != rendered_json:
            raise RuntimeError("Phase 1 JSON is stale or non-deterministic")
        if OUTPUT_MD.read_text(encoding="utf-8") != rendered_md:
            raise RuntimeError("Phase 1 Markdown is stale or non-deterministic")
        for field in (
            "deployment_authorized",
            "position_weight_change_authorized",
            "replacement_rank_change_authorized",
            "production_v2_change_authorized",
            "transform_change_authorized",
            "scale_change_authorized",
        ):
            if result.get(field) is not False:
                raise RuntimeError(f"guardrail failed: {field}")
        if result.get("frozen_prospective_experiments_touched") is not False:
            raise RuntimeError("frozen prospective experiment guardrail failed")
        print("PASS Position Weight V2 Phase 1 checks.")

    if not args.write and not args.check and not args.selftest:
        print(rendered_md)


if __name__ == "__main__":
    main()

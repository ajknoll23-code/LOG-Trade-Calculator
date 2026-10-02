#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics

HALF_CELLS = ("QB_HALF", "RB_HALF", "WR_HALF", "TE_HALF")


def avg_ranks(values):
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    ranks = [0.0] * len(values)
    j = 0
    while j < len(order):
        k = j + 1
        v = values[order[j]]
        while k < len(order) and values[order[k]] == v:
            k += 1
        rank = ((j + 1) + k) / 2.0
        for t in range(j, k):
            ranks[order[t]] = rank
        j = k
    return ranks


def pearson(x, y):
    if len(x) != len(y) or len(x) < 2:
        return None
    mx = statistics.fmean(x)
    my = statistics.fmean(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    sx = sum(v * v for v in dx)
    sy = sum(v * v for v in dy)
    if sx <= 0 or sy <= 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / math.sqrt(sx * sy)


def spearman(x, y):
    return pearson(avg_ranks(x), avg_ranks(y))


def group_diagnostics(rows):
    effects = [float(r["defense_effect"]) for r in rows]
    residuals = [
        float(r["actual"]) - float(r["baseline_forecast"])
        for r in rows
    ]
    rho = spearman(effects, residuals)

    ordered = sorted(
        zip(effects, residuals, rows),
        key=lambda z: (
            z[0],
            str(z[2]["defense_team"]),
            str(z[2]["offense_team"]),
            str(z[2]["game_id"]),
        ),
    )

    q = max(1, len(ordered) // 4)
    hard_q = [x[1] for x in ordered[:q]]
    easy_q = [x[1] for x in ordered[-q:]]
    spread = statistics.fmean(easy_q) - statistics.fmean(hard_q)

    t = max(1, len(ordered) // 3)
    hard_t = [x[1] for x in ordered[:t]]
    easy_t = [x[1] for x in ordered[-t:]]
    neutral_t = [x[1] for x in ordered[t:len(ordered) - t]]
    if not neutral_t:
        neutral_t = residuals

    return {
        "n": len(rows),
        "spearman_defense_effect_vs_realized_residual": rho,
        "easy_minus_hard_quartile_residual_points": spread,
        "tier_mean_residual_points": {
            "Hard": statistics.fmean(hard_t),
            "Neutral": statistics.fmean(neutral_t),
            "Easy": statistics.fmean(easy_t),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    all_rows = json.loads(Path(args.rows).read_text(encoding="utf-8"))
    rows = [r for r in all_rows if r["cell"] in HALF_CELLS]
    if not rows:
        raise RuntimeError("no Half-PPR B31 rows found")

    groups = defaultdict(list)
    for r in rows:
        groups[(int(r["season"]), int(r["week"]), r["cell"])].append(r)

    group_results = {}
    per_cell = defaultdict(
        lambda: {"rho": [], "spread": [], "tiers": defaultdict(list)}
    )
    excluded_constant_groups = []

    for key in sorted(groups):
        season, week, cell = key
        g = group_diagnostics(groups[key])
        group_results[f"{season}_W{week}_{cell}"] = g

        rho = g["spearman_defense_effect_vs_realized_residual"]
        if rho is None:
            excluded_constant_groups.append(f"{season}_W{week}_{cell}")
        else:
            per_cell[cell]["rho"].append(rho)

        per_cell[cell]["spread"].append(
            g["easy_minus_hard_quartile_residual_points"]
        )
        for tier, value in g["tier_mean_residual_points"].items():
            per_cell[cell]["tiers"][tier].append(value)

    cell_summary = {}
    for cell in HALF_CELLS:
        d = per_cell[cell]
        if not d["rho"] or not d["spread"]:
            raise RuntimeError(f"insufficient ordinal diagnostics for {cell}")
        cell_summary[cell] = {
            "eligible_week_cells_for_spearman": len(d["rho"]),
            "mean_week_cell_spearman": statistics.fmean(d["rho"]),
            "median_week_cell_spearman": statistics.median(d["rho"]),
            "positive_spearman_fraction": (
                sum(x > 0 for x in d["rho"]) / len(d["rho"])
            ),
            "mean_easy_minus_hard_quartile_residual_points": (
                statistics.fmean(d["spread"])
            ),
            "positive_quartile_spread_fraction": (
                sum(x > 0 for x in d["spread"]) / len(d["spread"])
            ),
            "mean_tier_residual_points": {
                tier: statistics.fmean(d["tiers"][tier])
                for tier in ("Hard", "Neutral", "Easy")
            },
        }

    pooled_rho = statistics.fmean(
        cell_summary[cell]["mean_week_cell_spearman"]
        for cell in HALF_CELLS
    )
    pooled_spread = statistics.fmean(
        cell_summary[cell][
            "mean_easy_minus_hard_quartile_residual_points"
        ]
        for cell in HALF_CELLS
    )
    pooled_tiers = {
        tier: statistics.fmean(
            cell_summary[cell]["mean_tier_residual_points"][tier]
            for cell in HALF_CELLS
        )
        for tier in ("Hard", "Neutral", "Easy")
    }

    development_positive = pooled_rho > 0 and pooled_spread > 0
    tier_ordered = (
        pooled_tiers["Easy"]
        > pooled_tiers["Neutral"]
        > pooled_tiers["Hard"]
    )

    result = {
        "schema_version": 1,
        "study_id": "schedule-utility-v1",
        "phase": "historical-ordinal-development-diagnostic",
        "status": (
            "DEVELOPMENT_ORDINAL_SIGNAL_POSITIVE_CONTINUE_TO_B33"
            if development_positive
            else (
                "RECONSIDER_BEFORE_B33_"
                "NONPOSITIVE_HISTORICAL_ORDINAL_SIGNAL"
            )
        ),
        "governance": {
            "2015_2025_are_consumed": True,
            "confirmatory_evidence": False,
            "production_authorization": False,
            "may_change_b31_stop": False,
            "purpose": (
                "development-only directional check before spending "
                "prospective 2026 weeks"
            ),
        },
        "population": {
            "seasons": [2015, 2025],
            "target_weeks": [4, 17],
            "scoring_mode": "HALF_PPR_ONLY",
            "cells_equal_weight": list(HALF_CELLS),
            "row_count": len(rows),
            "group_unit": "season-week-cell",
        },
        "definitions": {
            "realized_residual": (
                "actual team-position fantasy points minus frozen "
                "trailing offense baseline"
            ),
            "ordinal_predictor": (
                "frozen LOG-SAPA defense_effect; larger means easier matchup"
            ),
            "spearman": (
                "within season-week-cell Spearman(defense_effect, "
                "realized_residual)"
            ),
            "quartile_spread": (
                "mean realized residual in easiest defense-effect quartile "
                "minus hardest quartile"
            ),
            "historical_signal_continue_rule": (
                "pooled equal-position mean Spearman > 0 AND pooled "
                "equal-position mean easy-minus-hard quartile spread > 0"
            ),
            "tier_ordering": (
                "descriptive only; not part of the continue rule"
            ),
        },
        "pooled_equal_position": {
            "mean_week_cell_spearman": pooled_rho,
            "mean_easy_minus_hard_quartile_residual_points": pooled_spread,
            "mean_tier_residual_points": pooled_tiers,
            "tier_means_ordered_easy_gt_neutral_gt_hard": tier_ordered,
        },
        "per_cell": cell_summary,
        "excluded_constant_spearman_groups": excluded_constant_groups,
        "group_diagnostics": group_results,
        "next": {
            "b33_may_be_frozen_if_status_positive": development_positive,
            "if_nonpositive": (
                "reconsider ordinal shadow design before consuming "
                "prospective weeks"
            ),
        },
    }

    Path(args.out).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": result["status"],
        "pooled_mean_spearman": pooled_rho,
        "pooled_easy_minus_hard_quartile_spread": pooled_spread,
        "tier_means": pooled_tiers,
        "tier_ordered": tier_ordered,
        "row_count": len(rows),
    }, indent=2))


if __name__ == "__main__":
    main()

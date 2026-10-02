#!/usr/bin/env python3
"""
Schedule Utility V1 — Phase 2A frozen retrospective validation analysis.

This module contains pure analysis functions only. It performs no network I/O,
no source download, and no target-outcome loading by itself.

Primary question:
Does the already-frozen LOG-SAPA defense adjustment improve next-game
team-position fantasy-point forecasts over offense form alone?
"""

from __future__ import annotations

from collections import defaultdict
import itertools
import math
import statistics
from typing import Iterable, Mapping

SEASONS = tuple(range(2015, 2026))
CELLS = (
    "QB_HALF", "RB_HALF", "WR_HALF", "TE_HALF",
    "RB_PPR", "WR_PPR", "TE_PPR",
)
TARGET_WEEK_MIN = 4
TARGET_WEEK_MAX = 17
EXPECTED_DIRECTIONAL_MATCHUPS_PER_SEASON = 416
MIN_COVERAGE_FRACTION_PER_SEASON_CELL = 0.95

PRIMARY_MIN_MEAN_RELATIVE_MAE_IMPROVEMENT = 0.01
PRIMARY_MAX_ONE_SIDED_SIGNFLIP_P = 0.05
PRIMARY_MIN_POSITIVE_CELLS = 5
PRIMARY_MIN_WORST_CELL_RELATIVE_MAE_IMPROVEMENT = -0.02


def _finite(x) -> float:
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"non-finite value: {x!r}")
    return v


def mae(errors: Iterable[float]) -> float:
    vals = [abs(_finite(x)) for x in errors]
    if not vals:
        raise ValueError("MAE requires at least one error")
    return statistics.fmean(vals)


def rmse(errors: Iterable[float]) -> float:
    vals = [_finite(x) for x in errors]
    if not vals:
        raise ValueError("RMSE requires at least one error")
    return math.sqrt(statistics.fmean(x * x for x in vals))


def relative_improvement(baseline_metric: float, adjusted_metric: float) -> float:
    baseline_metric = _finite(baseline_metric)
    adjusted_metric = _finite(adjusted_metric)
    if baseline_metric <= 0:
        raise ValueError("baseline metric must be > 0")
    return (baseline_metric - adjusted_metric) / baseline_metric


def exact_one_sided_signflip_p(values: Iterable[float]) -> float:
    """
    Exact one-sided sign-flip test on season-level effects.

    H1: mean effect > 0.

    Every one of the 2^n sign assignments is enumerated. The exact p-value is
    the fraction whose mean is >= the observed all-positive-sign mean.
    No Monte Carlo approximation and no +1 correction are used.
    """
    vals = tuple(_finite(v) for v in values)
    if not vals:
        raise ValueError("sign-flip test requires values")
    observed = statistics.fmean(vals)
    extreme = 0
    total = 0
    for signs in itertools.product((-1.0, 1.0), repeat=len(vals)):
        perm_mean = statistics.fmean(s * v for s, v in zip(signs, vals))
        total += 1
        if perm_mean >= observed - 1e-15:
            extreme += 1
    return extreme / total


def _validate_row(row: Mapping[str, object]) -> dict:
    required = {
        "season", "week", "cell", "actual",
        "baseline_forecast", "adjusted_forecast", "defense_effect",
    }
    missing = required - set(row)
    if missing:
        raise KeyError(f"evaluation row missing fields: {sorted(missing)}")

    season = int(row["season"])
    week = int(row["week"])
    cell = str(row["cell"])

    if season not in SEASONS:
        raise ValueError(f"season outside frozen evaluation set: {season}")
    if not (TARGET_WEEK_MIN <= week <= TARGET_WEEK_MAX):
        raise ValueError(f"week outside frozen target range: {week}")
    if cell not in CELLS:
        raise ValueError(f"unknown cell: {cell}")

    actual = _finite(row["actual"])
    baseline = _finite(row["baseline_forecast"])
    adjusted = _finite(row["adjusted_forecast"])
    defense_effect = _finite(row["defense_effect"])

    # Frozen identity: adjusted forecast must be baseline + defense effect.
    if abs(adjusted - (baseline + defense_effect)) > 1e-9:
        raise ValueError("adjusted forecast identity violated")

    return {
        "season": season,
        "week": week,
        "cell": cell,
        "actual": actual,
        "baseline_forecast": baseline,
        "adjusted_forecast": adjusted,
        "defense_effect": defense_effect,
    }


def evaluate(rows: Iterable[Mapping[str, object]]) -> dict:
    clean = [_validate_row(row) for row in rows]
    if not clean:
        raise ValueError("no evaluation rows")

    grouped: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for row in clean:
        grouped[(row["season"], row["cell"])].append(row)

    expected_groups = {(s, c) for s in SEASONS for c in CELLS}
    if set(grouped) != expected_groups:
        missing = sorted(expected_groups - set(grouped))
        extra = sorted(set(grouped) - expected_groups)
        raise ValueError(f"season-cell group mismatch; missing={missing}, extra={extra}")

    min_required = math.ceil(
        EXPECTED_DIRECTIONAL_MATCHUPS_PER_SEASON
        * MIN_COVERAGE_FRACTION_PER_SEASON_CELL
    )

    season_cell = {}
    for season in SEASONS:
        for cell in CELLS:
            g = grouped[(season, cell)]
            n = len(g)
            if n < min_required:
                raise ValueError(
                    f"coverage gate failed for {season} {cell}: "
                    f"{n} < {min_required}"
                )
            if n > EXPECTED_DIRECTIONAL_MATCHUPS_PER_SEASON:
                raise ValueError(
                    f"too many directional matchups for {season} {cell}: {n}"
                )

            base_err = [r["baseline_forecast"] - r["actual"] for r in g]
            adj_err = [r["adjusted_forecast"] - r["actual"] for r in g]

            base_mae = mae(base_err)
            adj_mae = mae(adj_err)
            base_rmse = rmse(base_err)
            adj_rmse = rmse(adj_err)

            season_cell[(season, cell)] = {
                "n": n,
                "coverage_fraction": n / EXPECTED_DIRECTIONAL_MATCHUPS_PER_SEASON,
                "baseline_mae": base_mae,
                "adjusted_mae": adj_mae,
                "relative_mae_improvement": relative_improvement(base_mae, adj_mae),
                "baseline_rmse": base_rmse,
                "adjusted_rmse": adj_rmse,
                "relative_rmse_improvement": relative_improvement(base_rmse, adj_rmse),
            }

    # Equal-weight cells within each season, then equal-weight seasons.
    season_effects = {}
    for season in SEASONS:
        season_effects[season] = statistics.fmean(
            season_cell[(season, cell)]["relative_mae_improvement"]
            for cell in CELLS
        )

    cell_effects = {}
    for cell in CELLS:
        effects = [
            season_cell[(season, cell)]["relative_mae_improvement"]
            for season in SEASONS
        ]
        cell_effects[cell] = {
            "mean_relative_mae_improvement": statistics.fmean(effects),
            "median_relative_mae_improvement": statistics.median(effects),
            "positive_seasons": sum(v > 0 for v in effects),
            "exact_one_sided_signflip_p": exact_one_sided_signflip_p(effects),
            "mean_relative_rmse_improvement": statistics.fmean(
                season_cell[(season, cell)]["relative_rmse_improvement"]
                for season in SEASONS
            ),
        }

    primary_effect = statistics.fmean(season_effects.values())
    primary_p = exact_one_sided_signflip_p(season_effects.values())
    positive_cells = sum(
        payload["mean_relative_mae_improvement"] > 0
        for payload in cell_effects.values()
    )
    worst_cell = min(
        payload["mean_relative_mae_improvement"]
        for payload in cell_effects.values()
    )

    primary_gate = {
        "mean_relative_mae_improvement_at_least_0_01":
            primary_effect >= PRIMARY_MIN_MEAN_RELATIVE_MAE_IMPROVEMENT,
        "one_sided_signflip_p_at_most_0_05":
            primary_p <= PRIMARY_MAX_ONE_SIDED_SIGNFLIP_P,
        "positive_cells_at_least_5":
            positive_cells >= PRIMARY_MIN_POSITIVE_CELLS,
        "worst_cell_not_below_minus_0_02":
            worst_cell >= PRIMARY_MIN_WORST_CELL_RELATIVE_MAE_IMPROVEMENT,
    }
    passed = all(primary_gate.values())

    return {
        "primary": {
            "equal_season_equal_cell_mean_relative_mae_improvement": primary_effect,
            "exact_one_sided_season_signflip_p": primary_p,
            "positive_cells": positive_cells,
            "worst_cell_mean_relative_mae_improvement": worst_cell,
            "gate_components": primary_gate,
            "pass": passed,
            "decision": (
                "PASS_RETROSPECTIVE_PREDICTIVE_VALIDATION"
                if passed
                else "STOP_RETROSPECTIVE_PREDICTIVE_VALIDATION"
            ),
        },
        "season_effects": season_effects,
        "cell_effects": cell_effects,
        "coverage": {
            "expected_directional_matchups_per_season_cell":
                EXPECTED_DIRECTIONAL_MATCHUPS_PER_SEASON,
            "minimum_fraction_per_season_cell":
                MIN_COVERAGE_FRACTION_PER_SEASON_CELL,
            "minimum_rows_per_season_cell": min_required,
            "observed_total_rows": len(clean),
        },
    }


def selftest() -> None:
    # Exact sign-flip: all 11 equal positive effects -> 1 / 2^11.
    p = exact_one_sided_signflip_p([0.02] * 11)
    assert abs(p - (1 / 2048)) < 1e-15

    # One positive effect -> exact p = 1/2.
    p1 = exact_one_sided_signflip_p([0.02])
    assert abs(p1 - 0.5) < 1e-15

    assert abs(relative_improvement(10.0, 9.0) - 0.1) < 1e-15
    assert abs(mae([-2, 1, 3]) - 2.0) < 1e-15
    assert abs(rmse([3, 4]) - math.sqrt(12.5)) < 1e-15

    # Identity guard.
    good = {
        "season": 2015, "week": 4, "cell": "QB_HALF",
        "actual": 20.0, "baseline_forecast": 18.0,
        "defense_effect": 1.5, "adjusted_forecast": 19.5,
    }
    assert _validate_row(good)["adjusted_forecast"] == 19.5

    bad = dict(good, adjusted_forecast=99.0)
    try:
        _validate_row(bad)
    except ValueError as exc:
        assert "identity" in str(exc)
    else:
        raise AssertionError("adjusted forecast identity guard failed")

    print("PASS: Phase 2A frozen analysis synthetic selftest")


if __name__ == "__main__":
    selftest()

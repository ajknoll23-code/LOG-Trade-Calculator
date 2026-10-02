#!/usr/bin/env python3
"""
Schedule Utility V1 — Phase 2A amended retrospective validation analysis.

Outcome-blind amendment to the frozen Phase 2A analysis.
Primary predictor, primary estimand, thresholds, and inference are unchanged.

Changes:
- schedule-derived expected rows by season;
- explicit common paired evaluation sample;
- duplicate matchup protection;
- explicit season/cell coverage denominator;
- unchanged exact season-level sign-flip primary inference.
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
    Exact one-sided sign-flip test over season-level aggregate effects.

    Exact under the frozen null assumption that season effects are independent
    and symmetric about zero. No row-level independence is assumed.
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


def _validate_expected_rows(expected_rows_by_season: Mapping[int | str, object]) -> dict[int, int]:
    expected = {}
    for season in SEASONS:
        raw = (
            expected_rows_by_season.get(season)
            if season in expected_rows_by_season
            else expected_rows_by_season.get(str(season))
        )
        if raw is None:
            raise KeyError(f"missing schedule-derived expected row count for {season}")
        n = int(raw)
        if n <= 0 or n % 2 != 0:
            raise ValueError(f"invalid schedule-derived directional count for {season}: {n}")
        # Sanity bound only. Do NOT hard-code 416 as the denominator.
        if not (380 <= n <= 420):
            raise ValueError(f"implausible Weeks 4-17 directional count for {season}: {n}")
        expected[season] = n
    return expected


def _validate_row(row: Mapping[str, object]) -> dict:
    required = {
        "season", "week", "game_id", "offense_team", "defense_team", "cell",
        "actual", "baseline_forecast", "adjusted_forecast", "defense_effect",
    }
    missing = required - set(row)
    if missing:
        raise KeyError(f"evaluation row missing fields: {sorted(missing)}")

    season = int(row["season"])
    week = int(row["week"])
    cell = str(row["cell"])
    game_id = str(row["game_id"]).strip()
    offense = str(row["offense_team"]).strip().upper()
    defense = str(row["defense_team"]).strip().upper()

    if season not in SEASONS:
        raise ValueError(f"season outside frozen evaluation set: {season}")
    if not (TARGET_WEEK_MIN <= week <= TARGET_WEEK_MAX):
        raise ValueError(f"week outside frozen target range: {week}")
    if cell not in CELLS:
        raise ValueError(f"unknown cell: {cell}")
    if not game_id or not offense or not defense or offense == defense:
        raise ValueError("invalid matchup identity")

    actual = _finite(row["actual"])
    baseline = _finite(row["baseline_forecast"])
    adjusted = _finite(row["adjusted_forecast"])
    defense_effect = _finite(row["defense_effect"])

    if abs(adjusted - (baseline + defense_effect)) > 1e-9:
        raise ValueError("adjusted forecast identity violated")

    return {
        "season": season,
        "week": week,
        "game_id": game_id,
        "offense_team": offense,
        "defense_team": defense,
        "cell": cell,
        "actual": actual,
        "baseline_forecast": baseline,
        "adjusted_forecast": adjusted,
        "defense_effect": defense_effect,
    }


def evaluate(
    rows: Iterable[Mapping[str, object]],
    expected_rows_by_season: Mapping[int | str, object],
) -> dict:
    """
    `rows` MUST be the common paired sample:
    a row exists only when actual, baseline forecast, and adjusted forecast all
    exist for that exact matchup. Baseline and adjusted MAE are therefore
    computed on exactly identical rows.
    """
    expected = _validate_expected_rows(expected_rows_by_season)
    clean = [_validate_row(row) for row in rows]
    if not clean:
        raise ValueError("no evaluation rows")

    seen = set()
    grouped: dict[tuple[int, str], list[dict]] = defaultdict(list)

    for row in clean:
        key = (
            row["season"], row["week"], row["game_id"],
            row["offense_team"], row["defense_team"], row["cell"],
        )
        if key in seen:
            raise ValueError(f"duplicate evaluation matchup: {key}")
        seen.add(key)
        grouped[(row["season"], row["cell"])].append(row)

    expected_groups = {(s, c) for s in SEASONS for c in CELLS}
    if set(grouped) != expected_groups:
        missing = sorted(expected_groups - set(grouped))
        extra = sorted(set(grouped) - expected_groups)
        raise ValueError(f"season-cell group mismatch; missing={missing}, extra={extra}")

    season_cell = {}
    coverage_failures = []

    for season in SEASONS:
        denom = expected[season]
        min_required = math.ceil(denom * MIN_COVERAGE_FRACTION_PER_SEASON_CELL)

        for cell in CELLS:
            g = grouped[(season, cell)]
            n = len(g)
            if n > denom:
                raise ValueError(
                    f"covered rows exceed schedule denominator for {season} {cell}: "
                    f"{n} > {denom}"
                )
            if n < min_required:
                coverage_failures.append({
                    "season": season,
                    "cell": cell,
                    "covered": n,
                    "expected": denom,
                    "coverage_fraction": n / denom,
                    "minimum_required": min_required,
                })

            base_err = [r["baseline_forecast"] - r["actual"] for r in g]
            adj_err = [r["adjusted_forecast"] - r["actual"] for r in g]

            base_mae = mae(base_err)
            adj_mae = mae(adj_err)
            base_rmse = rmse(base_err)
            adj_rmse = rmse(adj_err)

            # Same exact paired rows are used for both metrics.
            season_cell[(season, cell)] = {
                "n": n,
                "expected": denom,
                "coverage_fraction": n / denom,
                "baseline_mae": base_mae,
                "adjusted_mae": adj_mae,
                "relative_mae_improvement": relative_improvement(base_mae, adj_mae),
                "mean_paired_absolute_error_difference_points":
                    statistics.fmean(
                        abs(r["baseline_forecast"] - r["actual"])
                        - abs(r["adjusted_forecast"] - r["actual"])
                        for r in g
                    ),
                "baseline_rmse": base_rmse,
                "adjusted_rmse": adj_rmse,
                "relative_rmse_improvement": relative_improvement(base_rmse, adj_rmse),
            }

    # Coverage is a hard primary gate; fail evaluation before outcome verdict.
    if coverage_failures:
        raise ValueError(f"coverage gate failed: {coverage_failures}")

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
            "mean_paired_absolute_error_difference_points": statistics.fmean(
                season_cell[(season, cell)][
                    "mean_paired_absolute_error_difference_points"
                ]
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
        "coverage_passed_all_season_cells": True,
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
            "denominator_source": "played regular-season schedule Weeks 4-17 by season",
            "expected_rows_by_season": expected,
            "minimum_fraction_per_season_cell":
                MIN_COVERAGE_FRACTION_PER_SEASON_CELL,
            "common_paired_sample_required": True,
            "observed_total_rows": len(clean),
        },
    }


def selftest() -> None:
    p = exact_one_sided_signflip_p([0.02] * 11)
    assert abs(p - (1 / 2048)) < 1e-15
    assert abs(exact_one_sided_signflip_p([0.02]) - 0.5) < 1e-15
    assert abs(relative_improvement(10.0, 9.0) - 0.1) < 1e-15
    assert abs(mae([-2, 1, 3]) - 2.0) < 1e-15
    assert abs(rmse([3, 4]) - math.sqrt(12.5)) < 1e-15

    assert _validate_expected_rows({s: 416 for s in SEASONS})[2015] == 416
    # Schedule-derived anomaly is allowed; 416 is NOT hard-coded.
    assert _validate_expected_rows({
        **{s: 416 for s in SEASONS if s != 2022},
        2022: 414,
    })[2022] == 414

    good = {
        "season": 2015, "week": 4, "game_id": "2015_04_X_Y",
        "offense_team": "X", "defense_team": "Y", "cell": "QB_HALF",
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

    print("PASS: amended Phase 2A synthetic selftest")


if __name__ == "__main__":
    selftest()

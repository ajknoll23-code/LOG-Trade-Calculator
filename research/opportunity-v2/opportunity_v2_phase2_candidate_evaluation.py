#!/usr/bin/env python3
"""
Continuous Opportunity / Role Signal V2 — Phase 2 candidate evaluation.

RESEARCH ONLY. No deployed ROLE_MULT, PROD_MULT_DATA, AGE_CURVE, Production V2,
Market Value, or player value is changed.

Question
--------
Does LAGGED opportunity improve future production prediction AFTER current
production is already known?

This is deliberately stricter than asking whether snaps correlate with scoring.
Current production already contains a large amount of role information. A useful
opportunity layer must explain future production beyond that baseline.

Historical inputs
-----------------
Phase 1 frozen descriptive dataset:
    research/opportunity-v2/opportunity_v2_phase1_coverage_audit.json

nflverse weekly player stats, 2015-2025, scored under the same historical
custom-scoring proxy used by No-History V2 and Age Curve V2.

Base seasons:
    2015-2024

Target:
    next-season custom-scored points / scheduled team games

A player with no future weekly scoring rows receives ZERO future production.
That intentionally includes role loss / league exit in the target.

Cross-validation
----------------
Leave one BASE SEASON out at a time. Models are fit separately by position.

Candidate family
----------------
1. production_only
   current points/team-game

2. production_plus_season_opportunity
   + Phase-1 season opportunity share
   (sum game snap share / scheduled team games)

3. production_plus_active_snap
   + active-game snap share
   (role intensity when the player records primary-unit snaps)

4. production_plus_active_and_availability
   + active-game snap share
   + primary-game availability share

5. production_plus_season_opportunity_change
   + season opportunity share
   + year-over-year opportunity change
   + prior-opportunity-present indicator

No hand-authored opportunity coefficient is used. Each position/fold coefficient
is estimated only from the training rows.

Outputs
-------
research/opportunity-v2/opportunity_v2_phase2_candidate_evaluation.json
research/opportunity-v2/opportunity_v2_phase2_candidate_evaluation.md

Usage
-----
python3 research/opportunity-v2/opportunity_v2_phase2_candidate_evaluation.py --selftest
python3 research/opportunity-v2/opportunity_v2_phase2_candidate_evaluation.py --write
python3 research/opportunity-v2/opportunity_v2_phase2_candidate_evaluation.py --check
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import requests


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]

PHASE1_JSON = (
    REPO_ROOT
    / "research"
    / "opportunity-v2"
    / "opportunity_v2_phase1_coverage_audit.json"
)
SCORING_SCRIPT = (
    REPO_ROOT
    / "research"
    / "no-history-v2"
    / "no_history_v2_phase2_prospect_prior.py"
)

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "opportunity-v2"
    / "opportunity_v2_phase2_candidate_evaluation.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "opportunity-v2"
    / "opportunity_v2_phase2_candidate_evaluation.md"
)

NFLVERSE_WEEKLY_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{season}.csv"
)

METHOD_VERSION = "opportunity-v2-phase2-candidate-evaluation-v1"
PHASE1_METHOD = "opportunity-v2-phase1-coverage-v1"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
STAT_YEARS = tuple(range(2015, 2026))
BASE_YEARS = tuple(range(2015, 2025))
HTTP_TIMEOUT_SECONDS = 90
MIN_POSITION_TRAIN_ROWS = 40

VARIANTS = {
    "production_only": (
        "current_points_per_team_game",
    ),
    "production_plus_season_opportunity": (
        "current_points_per_team_game",
        "season_opportunity_share",
    ),
    "production_plus_active_snap": (
        "current_points_per_team_game",
        "active_game_snap_share",
    ),
    "production_plus_active_and_availability": (
        "current_points_per_team_game",
        "active_game_snap_share",
        "primary_game_availability_share",
    ),
    "production_plus_season_opportunity_change": (
        "current_points_per_team_game",
        "season_opportunity_share",
        "opportunity_change",
        "prior_opportunity_present",
    ),
}
CONTROL = "production_only"


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON: {path.relative_to(REPO_ROOT)}: {exc}"
        ) from exc


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def finite(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


def scheduled_games(season: int) -> int:
    return 16 if season <= 2020 else 17


def load_module(path: Path, name: str):
    if not path.exists():
        raise RuntimeError(f"Missing module: {path.relative_to(REPO_ROOT)}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path.relative_to(REPO_ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch_csv_rows(
    url: str,
    session: requests.Session,
) -> list[dict[str, Any]]:
    response = session.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.text)))
    if not rows:
        raise RuntimeError(f"No CSV rows returned from {url}")
    return [dict(r) for r in rows]


def rankdata(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda x: (x[1], x[0]))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg
        i = j
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    if den <= 0:
        return None
    return sum(a*b for a, b in zip(dx, dy)) / den


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    return pearson(rankdata(xs), rankdata(ys))


def mae(actual: list[float], pred: list[float]) -> float | None:
    if not actual or len(actual) != len(pred):
        return None
    return statistics.fmean(abs(a - p) for a, p in zip(actual, pred))


def rmse(actual: list[float], pred: list[float]) -> float | None:
    if not actual or len(actual) != len(pred):
        return None
    return math.sqrt(
        statistics.fmean((a - p) ** 2 for a, p in zip(actual, pred))
    )


def metric_bundle(rows: list[dict[str, Any]], pred_field: str) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "mae": None,
            "rmse": None,
            "spearman": None,
            "pearson": None,
        }

    actual = [float(r["year1_points_per_team_game"]) for r in rows]
    pred = [float(r[pred_field]) for r in rows]

    return {
        "n": len(rows),
        "mae": mae(actual, pred),
        "rmse": rmse(actual, pred),
        "spearman": spearman(pred, actual),
        "pearson": pearson(pred, actual),
    }


def fit_ols(
    train_rows: list[dict[str, Any]],
    feature_names: tuple[str, ...],
) -> np.ndarray:
    if len(train_rows) < MIN_POSITION_TRAIN_ROWS:
        raise RuntimeError(
            f"Too few training rows for OLS: {len(train_rows)}"
        )

    x = np.asarray(
        [
            [1.0] + [float(row[name]) for name in feature_names]
            for row in train_rows
        ],
        dtype=float,
    )
    y = np.asarray(
        [float(row["year1_points_per_team_game"]) for row in train_rows],
        dtype=float,
    )

    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    return beta


def predict_ols(
    beta: np.ndarray,
    row: dict[str, Any],
    feature_names: tuple[str, ...],
) -> float:
    x = np.asarray(
        [1.0] + [float(row[name]) for name in feature_names],
        dtype=float,
    )
    pred = float(np.dot(x, beta))
    # Future fantasy production cannot be negative. This is the only bound.
    return max(0.0, pred)


def build_production_lookup(
    stats_by_season: dict[int, list[dict[str, Any]]],
    scorer,
) -> tuple[
    dict[tuple[str, int], float],
    dict[tuple[str, int], int],
]:
    totals: dict[tuple[str, int], float] = defaultdict(float)
    rows_count: dict[tuple[str, int], int] = defaultdict(int)

    for season, rows in stats_by_season.items():
        for row in rows:
            player_id = str(row.get("player_id") or "").strip()
            if not player_id:
                continue
            key = (player_id, season)
            totals[key] += float(scorer(row))
            rows_count[key] += 1

    return dict(totals), dict(rows_count)


def validate_phase1(phase1: dict[str, Any]) -> None:
    if phase1.get("method_version") != PHASE1_METHOD:
        raise RuntimeError("Unexpected Opportunity Phase-1 method version")
    if phase1.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 1 unexpectedly authorizes deployment")
    if phase1.get("role_mult_change_authorized") is not False:
        raise RuntimeError("Phase 1 unexpectedly authorizes ROLE_MULT change")

    hist = phase1.get("historical_summary") or {}
    if int(hist.get("player_seasons") or 0) < 15000:
        raise RuntimeError("Phase-1 historical opportunity sample unexpectedly small")
    if float(hist.get("gsis_identity_coverage_pct") or 0.0) < 95.0:
        raise RuntimeError("Phase-1 GSIS linkage too low for Phase 2")


def build_model_rows(
    phase1: dict[str, Any],
    production_totals: dict[tuple[str, int], float],
    production_rows: dict[tuple[str, int], int],
) -> list[dict[str, Any]]:
    opportunity_rows = phase1.get("historical_player_seasons")
    if not isinstance(opportunity_rows, list):
        raise RuntimeError("Phase 1 missing historical_player_seasons")

    opp_lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for row in opportunity_rows:
        if not isinstance(row, dict):
            continue
        gsis_id = str(row.get("gsis_id") or "").strip()
        season = int(row.get("season") or 0)
        pos = str(row.get("pos") or "").strip().upper()

        if not gsis_id or season not in STAT_YEARS or pos not in TRACKED_POSITIONS:
            continue

        key = (gsis_id, season)
        if key in opp_lookup:
            raise RuntimeError(
                f"Duplicate GSIS-season opportunity row: {gsis_id} {season}"
            )
        opp_lookup[key] = row

    out = []
    for (gsis_id, season), opp in sorted(
        opp_lookup.items(),
        key=lambda item: (
            item[0][1],
            item[1]["pos"],
            item[1]["player"],
            item[0][0],
        ),
    ):
        if season not in BASE_YEARS:
            continue

        next_season = season + 1
        current_points = float(production_totals.get((gsis_id, season), 0.0))
        future_points = float(
            production_totals.get((gsis_id, next_season), 0.0)
        )

        prior = opp_lookup.get((gsis_id, season - 1))
        prior_present = 1.0 if prior is not None else 0.0
        current_opp = finite(opp.get("season_opportunity_share"))
        prior_opp = (
            finite(prior.get("season_opportunity_share"))
            if prior is not None else current_opp
        )

        out.append(
            {
                "player_id": gsis_id,
                "player": opp.get("player"),
                "pos": opp.get("pos"),
                "season": season,
                "current_points_per_team_game": (
                    current_points / scheduled_games(season)
                ),
                "year1_points_per_team_game": (
                    future_points / scheduled_games(next_season)
                ),
                "current_stat_rows": int(
                    production_rows.get((gsis_id, season), 0)
                ),
                "year1_stat_rows": int(
                    production_rows.get((gsis_id, next_season), 0)
                ),
                "season_opportunity_share": current_opp,
                "active_game_snap_share": finite(
                    opp.get("active_game_snap_share")
                ),
                "primary_game_availability_share": finite(
                    opp.get("primary_game_availability_share")
                ),
                "opportunity_change": current_opp - prior_opp,
                "prior_opportunity_present": prior_present,
            }
        )

    if len(out) < 14000:
        raise RuntimeError(
            f"Opportunity Phase-2 model sample unexpectedly sparse: {len(out)}"
        )

    return out


def build_oof_predictions(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    predictions = [dict(r) for r in rows]
    fold_coefficients: dict[str, Any] = {}

    for held_year in BASE_YEARS:
        fold_coefficients[str(held_year)] = {}

        for pos in TRACKED_POSITIONS:
            train = [
                r for r in rows
                if r["season"] != held_year and r["pos"] == pos
            ]
            test_indices = [
                i for i, r in enumerate(rows)
                if r["season"] == held_year and r["pos"] == pos
            ]

            if not test_indices:
                continue
            if len(train) < MIN_POSITION_TRAIN_ROWS:
                raise RuntimeError(
                    f"Too few {pos} training rows with held year {held_year}: "
                    f"{len(train)}"
                )

            fold_coefficients[str(held_year)][pos] = {}

            for variant, features in VARIANTS.items():
                beta = fit_ols(train, features)
                fold_coefficients[str(held_year)][pos][variant] = {
                    "features": list(features),
                    "coefficients": [float(x) for x in beta],
                    "training_rows": len(train),
                    "test_rows": len(test_indices),
                }

                pred_field = f"pred__{variant}"
                for idx in test_indices:
                    predictions[idx][pred_field] = predict_ols(
                        beta,
                        rows[idx],
                        features,
                    )

    expected_fields = {f"pred__{v}" for v in VARIANTS}
    for row in predictions:
        missing = expected_fields.difference(row)
        if missing:
            raise RuntimeError(
                f"OOF prediction missing fields for {row['player']} "
                f"{row['season']}: {sorted(missing)}"
            )

    return predictions, fold_coefficients


def evaluate_predictions(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    overall = {}
    by_position = {}
    by_fold = {}

    for variant in VARIANTS:
        field = f"pred__{variant}"
        overall[variant] = metric_bundle(rows, field)

    for pos in TRACKED_POSITIONS:
        cohort = [r for r in rows if r["pos"] == pos]
        by_position[pos] = {}
        for variant in VARIANTS:
            by_position[pos][variant] = metric_bundle(
                cohort,
                f"pred__{variant}",
            )

    for season in BASE_YEARS:
        cohort = [r for r in rows if r["season"] == season]
        by_fold[str(season)] = {}
        for variant in VARIANTS:
            by_fold[str(season)][variant] = metric_bundle(
                cohort,
                f"pred__{variant}",
            )

    control = overall[CONTROL]
    comparison = {}
    for variant, metrics in overall.items():
        if variant == CONTROL:
            continue

        pos_improvements = 0
        pos_regressions = 0
        pos_deltas = {}
        for pos in TRACKED_POSITIONS:
            cur = by_position[pos][variant]
            base = by_position[pos][CONTROL]
            mae_delta = (
                float(cur["mae"]) - float(base["mae"])
                if cur["mae"] is not None and base["mae"] is not None
                else None
            )
            spear_delta = (
                float(cur["spearman"]) - float(base["spearman"])
                if cur["spearman"] is not None and base["spearman"] is not None
                else None
            )
            pos_deltas[pos] = {
                "mae_delta_vs_control": mae_delta,
                "spearman_delta_vs_control": spear_delta,
            }
            if mae_delta is not None:
                if mae_delta < 0:
                    pos_improvements += 1
                elif mae_delta > 0:
                    pos_regressions += 1

        fold_improvements = 0
        fold_deltas = {}
        for season in BASE_YEARS:
            cur = by_fold[str(season)][variant]
            base = by_fold[str(season)][CONTROL]
            d = (
                float(cur["mae"]) - float(base["mae"])
                if cur["mae"] is not None and base["mae"] is not None
                else None
            )
            fold_deltas[str(season)] = d
            if d is not None and d < 0:
                fold_improvements += 1

        comparison[variant] = {
            "overall_mae_delta_vs_control": (
                float(metrics["mae"]) - float(control["mae"])
                if metrics["mae"] is not None and control["mae"] is not None
                else None
            ),
            "overall_rmse_delta_vs_control": (
                float(metrics["rmse"]) - float(control["rmse"])
                if metrics["rmse"] is not None and control["rmse"] is not None
                else None
            ),
            "overall_spearman_delta_vs_control": (
                float(metrics["spearman"]) - float(control["spearman"])
                if metrics["spearman"] is not None
                and control["spearman"] is not None
                else None
            ),
            "positions_with_mae_improvement": pos_improvements,
            "positions_with_mae_regression": pos_regressions,
            "folds_with_mae_improvement": fold_improvements,
            "total_folds": len(BASE_YEARS),
            "by_position_deltas": pos_deltas,
            "by_fold_mae_delta": fold_deltas,
        }

    return {
        "overall": overall,
        "by_position": by_position,
        "by_fold": by_fold,
        "comparison_vs_production_only": comparison,
    }


def choose_monitoring_leader(
    evaluation: dict[str, Any],
) -> str | None:
    candidates = []
    comparison = evaluation["comparison_vs_production_only"]
    overall = evaluation["overall"]

    for variant in VARIANTS:
        if variant == CONTROL:
            continue
        comp = comparison[variant]

        # A candidate must improve overall MAE and a majority of positions.
        if comp["overall_mae_delta_vs_control"] is None:
            continue
        if comp["overall_mae_delta_vs_control"] >= 0:
            continue
        if comp["positions_with_mae_improvement"] < 4:
            continue

        candidates.append(variant)

    if not candidates:
        return None

    candidates.sort(
        key=lambda v: (
            float(overall[v]["mae"]),
            -float(overall[v]["spearman"] or -999),
            -int(comparison[v]["folds_with_mae_improvement"]),
            v,
        )
    )
    return candidates[0]


def summarize_sample(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_pos = {}
    for pos in TRACKED_POSITIONS:
        cohort = [r for r in rows if r["pos"] == pos]
        by_pos[pos] = {
            "rows": len(cohort),
            "base_rows_with_scoring_stats": sum(
                1 for r in cohort if r["current_stat_rows"] > 0
            ),
            "future_rows_with_scoring_stats": sum(
                1 for r in cohort if r["year1_stat_rows"] > 0
            ),
            "future_zero_production_rows": sum(
                1 for r in cohort
                if float(r["year1_points_per_team_game"]) == 0.0
            ),
            "rows_with_prior_opportunity": sum(
                1 for r in cohort
                if float(r["prior_opportunity_present"]) > 0.5
            ),
        }

    return {
        "rows": len(rows),
        "base_seasons": list(BASE_YEARS),
        "future_target_seasons": list(range(2016, 2026)),
        "with_base_scoring_stats": sum(
            1 for r in rows if r["current_stat_rows"] > 0
        ),
        "with_future_scoring_stats": sum(
            1 for r in rows if r["year1_stat_rows"] > 0
        ),
        "future_zero_production_rows": sum(
            1 for r in rows
            if float(r["year1_points_per_team_game"]) == 0.0
        ),
        "with_prior_opportunity": sum(
            1 for r in rows
            if float(r["prior_opportunity_present"]) > 0.5
        ),
        "by_position": by_pos,
    }


def build_result(
    session: requests.Session | None = None,
) -> dict[str, Any]:
    phase1 = read_json(PHASE1_JSON)
    validate_phase1(phase1)

    scoring = load_module(
        SCORING_SCRIPT,
        "no_history_v2_phase2_for_opportunity_v2",
    )

    sess = session or requests.Session()
    stats_by_season = {}
    for season in STAT_YEARS:
        print(f"Downloading nflverse weekly player stats {season}...")
        stats_by_season[season] = fetch_csv_rows(
            NFLVERSE_WEEKLY_URL.format(season=season),
            session=sess,
        )

    totals, row_counts = build_production_lookup(
        stats_by_season,
        scoring.score_nflverse_week,
    )
    rows = build_model_rows(
        phase1,
        totals,
        row_counts,
    )
    predictions, fold_coefficients = build_oof_predictions(rows)
    evaluation = evaluate_predictions(predictions)
    leader = choose_monitoring_leader(evaluation)

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": "RESEARCH_ONLY_OPPORTUNITY_INCREMENTAL_PREDICTION_AUDIT",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "role_mult_change_authorized": False,
        "opportunity_formula_authorized": False,
        "protocol": {
            "base_seasons": list(BASE_YEARS),
            "target": (
                "next-season custom-scored points per scheduled team game; "
                "missing future production remains zero"
            ),
            "cross_validation": "leave_one_base_season_out",
            "model_scope": "position_specific_ordinary_least_squares",
            "negative_prediction_bound": 0.0,
            "control": CONTROL,
            "candidate_features": {
                key: list(value) for key, value in VARIANTS.items()
            },
            "same_season_future_opportunity_used": False,
            "current_depth_chart_order_used": False,
        },
        "sample": summarize_sample(predictions),
        "evaluation": evaluation,
        "monitoring_leader": leader,
        "monitoring_leader_is_deployment_choice": False,
        "fold_coefficients": fold_coefficients,
        "oof_predictions": predictions,
        "phase3_handoff": (
            "If an opportunity candidate improves future production beyond the "
            "production-only control across the overall sample and most positions, "
            "apply the surviving candidate(s) to current real-history players as a "
            "research-only shadow. Keep Production V2 frozen and do not rewrite its "
            "forward blend. The opportunity layer should be evaluated as a role/"
            "durability signal, not as a replacement forward-projection engine."
            if leader else
            "No opportunity candidate cleared the minimum incremental-evidence "
            "screen. Do not create a current-value opportunity shadow unless Phase 2 "
            "is redesigned with a materially different leakage-safe feature family."
        ),
    }


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def signed(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    return f"{float(value):+.{digits}f}"


def render_markdown(result: dict[str, Any]) -> str:
    sample = result["sample"]
    evaluation = result["evaluation"]
    overall = evaluation["overall"]
    comparison = evaluation["comparison_vs_production_only"]

    lines = [
        "# Continuous Opportunity / Role Signal V2 — Phase 2 Candidate Evaluation",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No deployed ROLE_MULT or player value is changed.**",
        "",
        "## Historical protocol",
        "",
        f"- Base seasons: **{sample['base_seasons'][0]}–{sample['base_seasons'][-1]}**",
        f"- Evaluation rows: **{sample['rows']}**",
        f"- Future-zero rows: **{sample['future_zero_production_rows']}**",
        "- Target: **next-season custom-scored points per scheduled team game**",
        "- Cross-validation: **leave one base season out**",
        "- Model: **position-specific OLS**",
        "- Missing future production: **zero**",
        "",
        "## Overall out-of-fold results",
        "",
        "| Variant | MAE | RMSE | Spearman | Pearson | Δ MAE vs production | "
        "Δ Spearman | Pos MAE improved | Folds MAE improved |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for variant in VARIANTS:
        metrics = overall[variant]
        if variant == CONTROL:
            mae_delta = None
            spear_delta = None
            pos_imp = "—"
            fold_imp = "—"
        else:
            comp = comparison[variant]
            mae_delta = comp["overall_mae_delta_vs_control"]
            spear_delta = comp["overall_spearman_delta_vs_control"]
            pos_imp = f"{comp['positions_with_mae_improvement']}/7"
            fold_imp = (
                f"{comp['folds_with_mae_improvement']}/"
                f"{comp['total_folds']}"
            )

        lines.append(
            f"| `{variant}` | {fmt(metrics['mae'])} | {fmt(metrics['rmse'])} | "
            f"{fmt(metrics['spearman'])} | {fmt(metrics['pearson'])} | "
            f"{signed(mae_delta)} | {signed(spear_delta)} | "
            f"{pos_imp} | {fold_imp} |"
        )

    lines.extend(
        [
            "",
            "## By-position Spearman",
            "",
            "| Variant | QB | RB | WR | TE | DL | LB | DB |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for variant in VARIANTS:
        vals = []
        for pos in TRACKED_POSITIONS:
            vals.append(
                fmt(
                    evaluation["by_position"][pos][variant]["spearman"]
                )
            )
        lines.append(
            f"| `{variant}` | " + " | ".join(vals) + " |"
        )

    lines.extend(
        [
            "",
            "## By-position MAE delta vs production-only",
            "",
            "| Variant | QB | RB | WR | TE | DL | LB | DB |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for variant in VARIANTS:
        if variant == CONTROL:
            continue
        vals = []
        for pos in TRACKED_POSITIONS:
            vals.append(
                signed(
                    comparison[variant]["by_position_deltas"][pos][
                        "mae_delta_vs_control"
                    ]
                )
            )
        lines.append(
            f"| `{variant}` | " + " | ".join(vals) + " |"
        )

    lines.extend(
        [
            "",
            "## Monitoring result",
            "",
            f"Monitoring leader: **`{result['monitoring_leader'] or 'none'}`**",
            "",
            "**This is not a deployment choice.**",
            "",
            "## Phase 3",
            "",
            result["phase3_handoff"],
            "",
        ]
    )

    return "\n".join(lines)


def write_outputs(result: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(render_markdown(result), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


def check_outputs() -> None:
    result = read_json(OUTPUT_JSON)

    if result.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Opportunity V2 Phase-2 method mismatch")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Opportunity Phase 2 production mutation guardrail failed")
    if result.get("deployment_authorized") is not False:
        raise RuntimeError("Opportunity Phase 2 unexpectedly authorizes deployment")
    if result.get("role_mult_change_authorized") is not False:
        raise RuntimeError("Opportunity Phase 2 unexpectedly authorizes ROLE_MULT")
    if result.get("opportunity_formula_authorized") is not False:
        raise RuntimeError("Opportunity Phase 2 unexpectedly authorizes formula")

    sample = result.get("sample") or {}
    if int(sample.get("rows") or 0) < 14000:
        raise RuntimeError("Opportunity Phase-2 historical sample unexpectedly small")

    overall = (result.get("evaluation") or {}).get("overall") or {}
    if set(overall) != set(VARIANTS):
        raise RuntimeError("Opportunity Phase-2 candidate family mismatch")

    for variant in VARIANTS:
        metrics = overall.get(variant) or {}
        if int(metrics.get("n") or 0) != int(sample["rows"]):
            raise RuntimeError(f"Opportunity Phase-2 incomplete OOF coverage: {variant}")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Opportunity Phase-2 markdown missing")
    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Overall out-of-fold results",
        "By-position Spearman",
        "Monitoring result",
        "Phase 3",
    ):
        if marker not in text:
            raise RuntimeError(
                f"Opportunity Phase-2 report missing marker: {marker}"
            )

    print("Continuous Opportunity V2 Phase-2 outputs passed guardrails.")


def run_selftest() -> None:
    synthetic = []
    for year in (2020, 2021, 2022):
        for i in range(60):
            prod = i / 10.0
            opp = i / 60.0
            future = 0.7 * prod + 2.0 * opp
            synthetic.append(
                {
                    "season": year,
                    "pos": "WR",
                    "current_points_per_team_game": prod,
                    "year1_points_per_team_game": future,
                    "season_opportunity_share": opp,
                    "active_game_snap_share": opp,
                    "primary_game_availability_share": opp,
                    "opportunity_change": 0.0,
                    "prior_opportunity_present": 1.0,
                }
            )

    train = [r for r in synthetic if r["season"] != 2022]
    test = [r for r in synthetic if r["season"] == 2022]

    beta_control = fit_ols(train, VARIANTS["production_only"])
    beta_opp = fit_ols(
        train,
        VARIANTS["production_plus_season_opportunity"],
    )

    pred_control = [
        predict_ols(
            beta_control,
            r,
            VARIANTS["production_only"],
        )
        for r in test
    ]
    pred_opp = [
        predict_ols(
            beta_opp,
            r,
            VARIANTS["production_plus_season_opportunity"],
        )
        for r in test
    ]
    actual = [r["year1_points_per_team_game"] for r in test]

    assert mae(actual, pred_opp) is not None
    assert mae(actual, pred_control) is not None
    assert float(mae(actual, pred_opp)) <= float(mae(actual, pred_control)) + 1e-9

    assert scheduled_games(2020) == 16
    assert scheduled_games(2021) == 17

    print(
        "Continuous Opportunity V2 Phase-2 self-test passed: OLS, candidate "
        "incremental signal, nonnegative prediction, and season-length rules."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return
    if args.check:
        check_outputs()
        return

    result = build_result()

    if args.write:
        write_outputs(result)
    else:
        print(render_markdown(result))


if __name__ == "__main__":
    main()

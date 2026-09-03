#!/usr/bin/env python3
"""
Age Curve V2 — Phase 2 out-of-sample candidate evaluation.

RESEARCH ONLY. No deployed AGE_CURVE or player value is changed.

Purpose
-------
Phase 1 established a large historical retention sample. Phase 2 asks a harder
question:

    Does an empirical age-retention adjustment predict future production better
    than the currently deployed age-policy shape?

The test is leakage-safe by base season:
- hold out one historical base season,
- fit age-retention factors on every other base season,
- predict the held-out players' future Year+1 / Year+2 production,
- repeat for every base season.

Primary target
--------------
Mean of Year+1 and Year+2 custom-scored points per scheduled team game.

This is deliberately simple and horizon-neutral: no hand-selected discount
weight is used between Year+1 and Year+2.

Controls / candidates
---------------------
1. current_production_only
   No age adjustment. Current custom points/team-game predicts future output.

2. deployed_age_policy_proxy
   Current production multiplied by the current deployed ageMultiplier() shape.
   Historical PROD_MULT_DATA does not exist, so within-position-season current
   production percentile is mapped to the deployed PM range 0.15-1.55 and the
   Phase-1 production tier is mapped to a role. This is explicitly a historical
   proxy for the deployed age layer, not a byte-identical historical replay.

3. empirical_position_age_k25
4. empirical_position_age_k50
   Position + exact-age historical retention, shrunk toward the position mean.

5. empirical_tier_age_k25
6. empirical_tier_age_k50
   Position + current production tier + exact age, hierarchically shrunk first
   toward the position-age estimate and then toward the position mean.

The k values are sensitivity variants, not selected production coefficients.

Outputs
-------
research/age-curve-v2/age_curve_v2_phase2_candidate_evaluation.json
research/age-curve-v2/age_curve_v2_phase2_candidate_evaluation.md

Usage
-----
python3 research/age-curve-v2/age_curve_v2_phase2_candidate_evaluation.py --selftest
python3 research/age-curve-v2/age_curve_v2_phase2_candidate_evaluation.py --write
python3 research/age-curve-v2/age_curve_v2_phase2_candidate_evaluation.py --check
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

INDEX_HTML = REPO_ROOT / "index.html"
PHASE1_JSON = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase1_retention_audit.json"
)
PHASE1_SCRIPT = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase1_retention_audit.py"
)

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase2_candidate_evaluation.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase2_candidate_evaluation.md"
)

METHOD_VERSION = "age-curve-v2-phase2-candidate-evaluation-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
TIER_NAMES = ("elite", "starter", "rotation", "depth")
SHRINKAGE_VARIANTS = (25.0, 50.0)

CONTROL_CURRENT = "current_production_only"
CONTROL_DEPLOYED = "deployed_age_policy_proxy"
POSITION_TEMPLATE = "empirical_position_age_k{n}"
TIER_TEMPLATE = "empirical_tier_age_k{n}"

FACTOR_MIN = 0.25
FACTOR_MAX = 1.50
MIN_CORRELATION_N = 3

ROLE_BY_TIER = {
    "elite": "Elite",
    "starter": "Starter",
    "rotation": "Rotational",
    "depth": "Depth",
}


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


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


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
    if len(xs) != len(ys) or len(xs) < MIN_CORRELATION_N:
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if den <= 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / den


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < MIN_CORRELATION_N:
        return None
    return pearson(rankdata(xs), rankdata(ys))


def mae(actual: list[float], pred: list[float]) -> float | None:
    if not actual:
        return None
    return statistics.fmean(abs(a - p) for a, p in zip(actual, pred))


def rmse(actual: list[float], pred: list[float]) -> float | None:
    if not actual:
        return None
    return math.sqrt(
        statistics.fmean((a - p) ** 2 for a, p in zip(actual, pred))
    )


def pairwise_accuracy(
    pred: list[float],
    actual: list[float],
) -> tuple[float | None, int]:
    concordant = 0
    comparable = 0
    for i in range(len(pred)):
        for j in range(i + 1, len(pred)):
            dx = pred[i] - pred[j]
            dy = actual[i] - actual[j]
            if dx == 0 or dy == 0:
                continue
            comparable += 1
            if (dx > 0) == (dy > 0):
                concordant += 1
    if comparable == 0:
        return None, 0
    return concordant / comparable, comparable


def metric_bundle(
    rows: list[dict[str, Any]],
    pred_field: str,
    actual_field: str,
) -> dict[str, Any]:
    pred = []
    actual = []
    for row in rows:
        p = row.get(pred_field)
        y = row.get(actual_field)
        if p is None or y is None:
            continue
        p = float(p)
        y = float(y)
        if not math.isfinite(p) or not math.isfinite(y):
            continue
        pred.append(p)
        actual.append(y)

    acc, pairs = pairwise_accuracy(pred, actual)
    return {
        "n": len(pred),
        "mae": mae(actual, pred),
        "rmse": rmse(actual, pred),
        "pearson": pearson(pred, actual),
        "spearman": spearman(pred, actual),
        "pairwise_ordering_accuracy": acc,
        "comparable_pairs": pairs,
    }


def load_module(path: Path, name: str):
    if not path.exists():
        raise RuntimeError(f"Missing module source: {path.relative_to(REPO_ROOT)}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path.relative_to(REPO_ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def validate_phase1(phase1_json: dict[str, Any]) -> None:
    if phase1_json.get("method_version") != "age-curve-v2-phase1-retention-v1":
        raise RuntimeError("Unexpected Age Curve Phase-1 method version")
    if phase1_json.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 1 unexpectedly authorizes deployment")
    if phase1_json.get("age_curve_change_authorized") is not False:
        raise RuntimeError("Phase 1 unexpectedly authorizes AGE_CURVE changes")
    hist = phase1_json.get("historical_window") or {}
    if int(hist.get("retention_row_count") or 0) < 10000:
        raise RuntimeError("Phase-1 retention sample is unexpectedly small")


def add_production_percentiles(
    retention_rows: list[dict[str, Any]],
) -> None:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in retention_rows:
        grouped[(row["pos"], int(row["season"]))].append(row)

    for cohort in grouped.values():
        ordered = sorted(
            cohort,
            key=lambda r: (
                float(r["current_points_per_team_game"]),
                r["player_id"],
            ),
        )
        n = len(ordered)
        if n == 1:
            ordered[0]["production_percentile"] = 0.5
            continue

        i = 0
        while i < n:
            j = i + 1
            value = float(ordered[i]["current_points_per_team_game"])
            while (
                j < n
                and float(ordered[j]["current_points_per_team_game"]) == value
            ):
                j += 1
            avg_index = ((i + j - 1) / 2.0)
            pct = avg_index / (n - 1)
            for k in range(i, j):
                ordered[k]["production_percentile"] = pct
            i = j


def deployed_proxy_factor(
    row: dict[str, Any],
    cfg: dict[str, Any],
    snapshot_values,
) -> float:
    pct = float(row["production_percentile"])
    pm = 0.15 + 1.40 * clamp(pct, 0.0, 1.0)
    role = ROLE_BY_TIER[row["production_tier"]]

    factor = snapshot_values.age_multiplier(
        row["pos"],
        int(row["age"]),
        role,
        pm,
        pm,
        cfg,
    )
    return clamp(float(factor), FACTOR_MIN, FACTOR_MAX)


def primary_target(row: dict[str, Any]) -> float:
    return (
        float(row["year1_points_per_team_game"])
        + float(row["year2_points_per_team_game"])
    ) / 2.0


def ratio_sums(
    rows: list[dict[str, Any]],
) -> tuple[float, float, float]:
    current_sum = sum(float(r["current_points_per_team_game"]) for r in rows)
    target_sum = sum(primary_target(r) for r in rows)
    ratio = target_sum / current_sum if current_sum > 0 else 1.0
    return current_sum, target_sum, ratio


def shrunk_ratio(
    current_sum: float,
    target_sum: float,
    prior_ratio: float,
    prior_strength: float,
    typical_current: float,
) -> float:
    """
    Convert a pseudo-player prior strength into current-production mass so the
    shrinkage scale is comparable across positions.
    """
    prior_mass = max(1e-9, prior_strength * max(typical_current, 1e-6))
    numerator = target_sum + prior_mass * prior_ratio
    denominator = current_sum + prior_mass
    if denominator <= 0:
        return clamp(prior_ratio, FACTOR_MIN, FACTOR_MAX)
    return clamp(numerator / denominator, FACTOR_MIN, FACTOR_MAX)


def fit_empirical_factors(
    training: list[dict[str, Any]],
    prior_strength: float,
) -> dict[str, Any]:
    by_pos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_pos_age: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    by_pos_tier_age: dict[
        tuple[str, str, int], list[dict[str, Any]]
    ] = defaultdict(list)

    for row in training:
        pos = row["pos"]
        age = int(row["age"])
        tier = row["production_tier"]
        by_pos[pos].append(row)
        by_pos_age[(pos, age)].append(row)
        by_pos_tier_age[(pos, tier, age)].append(row)

    pos_ratio = {}
    typical_current = {}

    for pos in TRACKED_POSITIONS:
        cohort = by_pos[pos]
        _, _, ratio = ratio_sums(cohort)
        pos_ratio[pos] = clamp(ratio, FACTOR_MIN, FACTOR_MAX)
        typical_current[pos] = median(
            [float(r["current_points_per_team_game"]) for r in cohort]
        ) or 1.0

    age_factor = {}
    age_n = {}
    for (pos, age), cohort in by_pos_age.items():
        current_sum, target_sum, _ = ratio_sums(cohort)
        factor = shrunk_ratio(
            current_sum,
            target_sum,
            pos_ratio[pos],
            prior_strength,
            typical_current[pos],
        )
        age_factor[(pos, age)] = factor
        age_n[(pos, age)] = len(cohort)

    tier_age_factor = {}
    tier_age_n = {}
    for (pos, tier, age), cohort in by_pos_tier_age.items():
        parent = age_factor.get((pos, age), pos_ratio[pos])
        current_sum, target_sum, _ = ratio_sums(cohort)
        factor = shrunk_ratio(
            current_sum,
            target_sum,
            parent,
            prior_strength,
            typical_current[pos],
        )
        tier_age_factor[(pos, tier, age)] = factor
        tier_age_n[(pos, tier, age)] = len(cohort)

    return {
        "prior_strength": prior_strength,
        "position_ratio": pos_ratio,
        "position_age_factor": age_factor,
        "position_age_n": age_n,
        "tier_age_factor": tier_age_factor,
        "tier_age_n": tier_age_n,
    }


def nearest_age_factor(
    mapping: dict[tuple, float],
    prefix: tuple,
    requested_age: int,
    fallback: float,
) -> float:
    exact_key = (*prefix, requested_age)
    if exact_key in mapping:
        return mapping[exact_key]

    candidates = []
    for key, value in mapping.items():
        if key[:-1] == prefix:
            candidates.append((abs(int(key[-1]) - requested_age), int(key[-1]), value))
    if not candidates:
        return fallback
    candidates.sort(key=lambda x: (x[0], x[1]))
    return float(candidates[0][2])


def empirical_factor(
    row: dict[str, Any],
    fitted: dict[str, Any],
    tier_sensitive: bool,
) -> float:
    pos = row["pos"]
    age = int(row["age"])
    base = float(fitted["position_ratio"][pos])

    if tier_sensitive:
        tier = row["production_tier"]
        return nearest_age_factor(
            fitted["tier_age_factor"],
            (pos, tier),
            age,
            nearest_age_factor(
                fitted["position_age_factor"],
                (pos,),
                age,
                base,
            ),
        )

    return nearest_age_factor(
        fitted["position_age_factor"],
        (pos,),
        age,
        base,
    )


def build_cv_predictions(
    retention_rows: list[dict[str, Any]],
    cfg: dict[str, Any],
    snapshot_values,
) -> list[dict[str, Any]]:
    predictions = []

    base_years = sorted({int(r["season"]) for r in retention_rows})

    for test_year in base_years:
        training = [r for r in retention_rows if int(r["season"]) != test_year]
        testing = [r for r in retention_rows if int(r["season"]) == test_year]

        fits = {
            k: fit_empirical_factors(training, k)
            for k in SHRINKAGE_VARIANTS
        }

        for row in testing:
            current = float(row["current_points_per_team_game"])
            record = {
                "player_id": row["player_id"],
                "player": row["player"],
                "pos": row["pos"],
                "season": int(row["season"]),
                "age": int(row["age"]),
                "production_tier": row["production_tier"],
                "current_points_per_team_game": current,
                "year1_points_per_team_game": float(
                    row["year1_points_per_team_game"]
                ),
                "year2_points_per_team_game": float(
                    row["year2_points_per_team_game"]
                ),
                "forward_mean_points_per_team_game": primary_target(row),
                CONTROL_CURRENT: current,
                CONTROL_DEPLOYED: current
                * deployed_proxy_factor(row, cfg, snapshot_values),
            }

            for k, fitted in fits.items():
                n = int(k)
                record[POSITION_TEMPLATE.format(n=n)] = current * empirical_factor(
                    row,
                    fitted,
                    tier_sensitive=False,
                )
                record[TIER_TEMPLATE.format(n=n)] = current * empirical_factor(
                    row,
                    fitted,
                    tier_sensitive=True,
                )

            predictions.append(record)

    return predictions


def model_keys() -> list[str]:
    keys = [CONTROL_CURRENT, CONTROL_DEPLOYED]
    for k in SHRINKAGE_VARIANTS:
        n = int(k)
        keys.append(POSITION_TEMPLATE.format(n=n))
        keys.append(TIER_TEMPLATE.format(n=n))
    return keys


def evaluate_models(
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    out = {}
    actual_fields = {
        "forward_mean": "forward_mean_points_per_team_game",
        "year1": "year1_points_per_team_game",
        "year2": "year2_points_per_team_game",
    }

    for model in model_keys():
        overall = {
            target: metric_bundle(predictions, model, actual_field)
            for target, actual_field in actual_fields.items()
        }

        by_position = {}
        for pos in TRACKED_POSITIONS:
            cohort = [r for r in predictions if r["pos"] == pos]
            by_position[pos] = {
                target: metric_bundle(cohort, model, actual_field)
                for target, actual_field in actual_fields.items()
            }

        out[model] = {
            "overall": overall,
            "by_position": by_position,
        }

    return out


def fit_full_sample_curves(
    retention_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    out = {}
    for k in SHRINKAGE_VARIANTS:
        fitted = fit_empirical_factors(retention_rows, k)
        n = int(k)

        position_age = {}
        tier_age = {}
        for pos in TRACKED_POSITIONS:
            position_age[pos] = {}
            ages = sorted(
                {
                    int(key[1])
                    for key in fitted["position_age_factor"]
                    if key[0] == pos
                }
            )
            for age in ages:
                position_age[pos][str(age)] = {
                    "factor": fitted["position_age_factor"][(pos, age)],
                    "n": fitted["position_age_n"][(pos, age)],
                }

            tier_age[pos] = {}
            for tier in TIER_NAMES:
                tier_age[pos][tier] = {}
                tier_ages = sorted(
                    {
                        int(key[2])
                        for key in fitted["tier_age_factor"]
                        if key[0] == pos and key[1] == tier
                    }
                )
                for age in tier_ages:
                    tier_age[pos][tier][str(age)] = {
                        "factor": fitted["tier_age_factor"][(pos, tier, age)],
                        "n": fitted["tier_age_n"][(pos, tier, age)],
                    }

        out[f"k{n}"] = {
            "prior_strength_pseudo_players": k,
            "position_ratio": fitted["position_ratio"],
            "position_age": position_age,
            "tier_age": tier_age,
        }

    return out


def primary_summary(
    evaluation: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for model in model_keys():
        metrics = evaluation[model]["overall"]["forward_mean"]
        rows.append(
            {
                "model": model,
                "n": metrics["n"],
                "mae": metrics["mae"],
                "rmse": metrics["rmse"],
                "spearman": metrics["spearman"],
                "pearson": metrics["pearson"],
                "pairwise_ordering_accuracy": metrics[
                    "pairwise_ordering_accuracy"
                ],
            }
        )
    return rows


def rank_research_candidates(
    summary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Descriptive monitoring rank only.
    Primary sort = lower MAE; tie-break = higher Spearman.
    This does not authorize deployment.
    """
    empirical = [
        row for row in summary
        if row["model"] not in {CONTROL_CURRENT, CONTROL_DEPLOYED}
    ]
    empirical.sort(
        key=lambda r: (
            float(r["mae"]) if r["mae"] is not None else float("inf"),
            -float(r["spearman"]) if r["spearman"] is not None else float("inf"),
            r["model"],
        )
    )
    return empirical


def build_result(
    session: requests.Session | None = None,
) -> dict[str, Any]:
    phase1_json = read_json(PHASE1_JSON)
    validate_phase1(phase1_json)

    phase1 = load_module(PHASE1_SCRIPT, "age_curve_v2_phase1")
    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    sess = session or requests.Session()

    print("Downloading nflverse player metadata...")
    players_rows = phase1.fetch_csv_rows(
        phase1.NFLVERSE_PLAYERS_URL,
        sess,
    )

    stats_by_season = {}
    for season in phase1.STAT_YEARS:
        print(f"Downloading nflverse weekly player stats {season}...")
        stats_by_season[season] = phase1.fetch_csv_rows(
            phase1.NFLVERSE_WEEKLY_URL.format(season=season),
            sess,
        )

    scorer_module = phase1.load_phase2_module()
    metadata = phase1.build_player_metadata(players_rows)
    seasons = phase1.build_player_seasons(
        metadata,
        stats_by_season,
        scorer_module.score_nflverse_week,
    )
    phase1.assign_tiers(seasons)
    retention_rows = phase1.build_retention_rows(seasons)

    if len(retention_rows) < 10000:
        raise RuntimeError(
            f"Historical retention cohort unexpectedly sparse: {len(retention_rows)}"
        )

    add_production_percentiles(retention_rows)

    predictions = build_cv_predictions(
        retention_rows,
        cfg,
        snapshot_values,
    )
    evaluation = evaluate_models(predictions)
    summary = primary_summary(evaluation)
    research_rank = rank_research_candidates(summary)
    full_curves = fit_full_sample_curves(retention_rows)

    deployed_summary = next(
        row for row in summary if row["model"] == CONTROL_DEPLOYED
    )
    current_summary = next(
        row for row in summary if row["model"] == CONTROL_CURRENT
    )

    candidate_deltas = []
    for row in research_rank:
        candidate_deltas.append(
            {
                **row,
                "mae_delta_vs_current_only": (
                    row["mae"] - current_summary["mae"]
                    if row["mae"] is not None
                    and current_summary["mae"] is not None
                    else None
                ),
                "mae_delta_vs_deployed_proxy": (
                    row["mae"] - deployed_summary["mae"]
                    if row["mae"] is not None
                    and deployed_summary["mae"] is not None
                    else None
                ),
                "spearman_delta_vs_current_only": (
                    row["spearman"] - current_summary["spearman"]
                    if row["spearman"] is not None
                    and current_summary["spearman"] is not None
                    else None
                ),
                "spearman_delta_vs_deployed_proxy": (
                    row["spearman"] - deployed_summary["spearman"]
                    if row["spearman"] is not None
                    and deployed_summary["spearman"] is not None
                    else None
                ),
            }
        )

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": "RESEARCH_ONLY_OUT_OF_SAMPLE_AGE_CURVE_CANDIDATES",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "age_curve_change_authorized": False,
        "historical_sample": {
            "retention_rows": len(retention_rows),
            "base_years": sorted(
                {int(r["season"]) for r in retention_rows}
            ),
            "cross_validation": "leave_one_base_season_out",
        },
        "primary_target": (
            "mean of Year+1 and Year+2 custom-scored points per scheduled team game"
        ),
        "controls": {
            CONTROL_CURRENT: (
                "current custom points/team-game; no age adjustment"
            ),
            CONTROL_DEPLOYED: (
                "historical proxy for current deployed ageMultiplier(); "
                "within-position-season production percentile maps to PM 0.15-1.55"
            ),
        },
        "candidate_family": {
            "position_age": (
                "position + exact-age forward retention, shrunk toward "
                "position mean"
            ),
            "tier_age": (
                "position + production-tier + exact-age retention, "
                "hierarchically shrunk toward position-age"
            ),
            "shrinkage_pseudo_player_variants": list(SHRINKAGE_VARIANTS),
            "factor_bounds_research_only": [FACTOR_MIN, FACTOR_MAX],
        },
        "primary_model_summary": summary,
        "candidate_deltas_vs_controls": candidate_deltas,
        "full_evaluation": evaluation,
        "full_sample_candidate_curves": full_curves,
        "monitoring_leader": (
            research_rank[0]["model"] if research_rank else None
        ),
        "monitoring_leader_is_deployment_choice": False,
        "guardrail": (
            "The monitoring leader is descriptive only. No AGE_CURVE constant "
            "should change until current-player shadow impacts are audited and "
            "the chosen candidate is checked for position/tier stability."
        ),
        "phase3_handoff": (
            "Apply the strongest historical candidate(s) to the current player "
            "database as shadow age multipliers, compare rank/value movement, "
            "and freeze a small candidate family for prospective 2026 review."
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
    lines = [
        "# Age Curve V2 — Phase 2 Out-of-Sample Candidate Evaluation",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No deployed AGE_CURVE or player value is changed.**",
        "",
        f"- Historical player-season rows: "
        f"**{result['historical_sample']['retention_rows']}**",
        f"- Cross-validation: **{result['historical_sample']['cross_validation']}**",
        f"- Primary target: **{result['primary_target']}**",
        "",
        "## Overall out-of-sample results",
        "",
        "| Model | N | MAE ↓ | RMSE ↓ | Spearman ↑ | Pearson ↑ | Pairwise ↑ |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for row in result["primary_model_summary"]:
        lines.append(
            f"| `{row['model']}` | {row['n']} | "
            f"{fmt(row['mae'])} | {fmt(row['rmse'])} | "
            f"{fmt(row['spearman'])} | {fmt(row['pearson'])} | "
            f"{fmt(row['pairwise_ordering_accuracy'])} |"
        )

    lines.extend(
        [
            "",
            "## Empirical candidate improvement vs controls",
            "",
            "| Candidate | Δ MAE vs current-only | Δ MAE vs deployed proxy | "
            "Δ Spearman vs current-only | Δ Spearman vs deployed proxy |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for row in result["candidate_deltas_vs_controls"]:
        lines.append(
            f"| `{row['model']}` | "
            f"{signed(row['mae_delta_vs_current_only'])} | "
            f"{signed(row['mae_delta_vs_deployed_proxy'])} | "
            f"{signed(row['spearman_delta_vs_current_only'])} | "
            f"{signed(row['spearman_delta_vs_deployed_proxy'])} |"
        )

    lines.extend(
        [
            "",
            "## By-position primary-target Spearman",
            "",
            "| Model | QB | RB | WR | TE | DL | LB | DB |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for model in [
        row["model"] for row in result["primary_model_summary"]
    ]:
        eval_row = result["full_evaluation"][model]["by_position"]
        cells = []
        for pos in TRACKED_POSITIONS:
            cells.append(
                fmt(eval_row[pos]["forward_mean"]["spearman"])
            )
        lines.append(
            f"| `{model}` | " + " | ".join(cells) + " |"
        )

    lines.extend(
        [
            "",
            "## Monitoring result",
            "",
            f"- Best empirical candidate by primary MAE: "
            f"**`{result['monitoring_leader']}`**",
            "- This is **not a deployment choice**.",
            "",
            result["guardrail"],
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
        raise RuntimeError("Age Curve Phase-2 method_version mismatch")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Phase 2 lost production mutation guardrail")
    if result.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 2 unexpectedly authorizes deployment")
    if result.get("age_curve_change_authorized") is not False:
        raise RuntimeError("Phase 2 unexpectedly authorizes AGE_CURVE change")

    sample = result.get("historical_sample") or {}
    if int(sample.get("retention_rows") or 0) < 10000:
        raise RuntimeError("Phase-2 sample is implausibly small")

    summary = result.get("primary_model_summary") or []
    names = {row.get("model") for row in summary}
    expected = set(model_keys())
    if names != expected:
        raise RuntimeError(
            f"Phase-2 model family mismatch: {sorted(names)}"
        )

    if not OUTPUT_MD.exists():
        raise RuntimeError("Phase-2 markdown report missing")
    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Overall out-of-sample results",
        "Empirical candidate improvement vs controls",
        "By-position primary-target Spearman",
    ):
        if marker not in text:
            raise RuntimeError(f"Phase-2 markdown missing marker: {marker}")

    print("Age Curve V2 Phase-2 outputs passed guardrails.")


def run_selftest() -> None:
    synthetic = []
    for season in (2019, 2020, 2021):
        for age, current, future in (
            (23, 10.0, 11.0),
            (24, 10.0, 10.0),
            (29, 10.0, 7.0),
            (30, 10.0, 5.0),
        ):
            synthetic.append(
                {
                    "player_id": f"{season}-{age}",
                    "player": f"p-{season}-{age}",
                    "pos": "WR",
                    "season": season,
                    "age": age,
                    "production_tier": "starter",
                    "current_points_per_team_game": current,
                    "year1_points_per_team_game": future,
                    "year2_points_per_team_game": future,
                }
            )

    fitted = fit_empirical_factors(synthetic, 25.0)
    young = empirical_factor(
        synthetic[0],
        fitted,
        tier_sensitive=False,
    )
    old_row = next(r for r in synthetic if r["age"] == 30)
    old = empirical_factor(
        old_row,
        fitted,
        tier_sensitive=False,
    )
    assert young > old

    assert abs(primary_target(synthetic[0]) - 11.0) < 1e-9
    assert clamp(2.0, FACTOR_MIN, FACTOR_MAX) == FACTOR_MAX
    assert clamp(0.1, FACTOR_MIN, FACTOR_MAX) == FACTOR_MIN

    metrics = metric_bundle(
        [
            {"p": 1.0, "y": 1.0},
            {"p": 2.0, "y": 2.0},
            {"p": 3.0, "y": 3.0},
        ],
        "p",
        "y",
    )
    assert abs(metrics["spearman"] - 1.0) < 1e-9
    assert abs(metrics["mae"]) < 1e-9

    print(
        "Age Curve V2 Phase-2 self-test passed: hierarchical retention fit, "
        "young-vs-old direction, forward target, bounds, and metrics."
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

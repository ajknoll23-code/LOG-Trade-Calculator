#!/usr/bin/env python3
"""
No-History / Rookie Value V2 — Phase 2 historical prospect-prior calibration.

RESEARCH ONLY. No deployed player value is changed.

Purpose
-------
Phase 1 showed enough coverage to test a prospect prior:
- rookie / second-year identity
- NFL draft capital
- age
- existing Production V2 forward/history shadow signal

This phase avoids a hand-authored "pick X = value Y" curve. Instead it:
1. Downloads historical nflverse player metadata and weekly player stats.
2. Re-scores 2018-2025 weekly outcomes under this league's custom scoring.
3. Builds completed 2018-2024 draft cohorts with two NFL seasons of outcomes.
4. Cross-validates draft-capital-only vs draft-capital+age models by leaving one
   draft year out at a time.
5. Fits a position-specific historical prospect prior.
6. Converts the prior onto the existing Production V2 PM scale using the same
   Phase-8 replacement baselines and affine transform.
7. Emits research-only blend variants for 2026 eligible players that ALREADY
   have a normal V2 candidate.
8. Keeps the accepted Phase-7 continuity fallback unchanged for missing V2
   candidates, while reporting a prior-only diagnostic separately.

No formula in this file is authorized for production deployment.

Historical target
-----------------
Primary target:
    custom-scored first-two-NFL-season points / scheduled team games

This intentionally rewards both performance and earning/retaining opportunity.
It is a prospect-success target, not an active-game PPG target.

Secondary:
    custom-scored points / nflverse weekly stat rows

The historical scoring port covers the league's material offensive and IDP
scoring fields. nflverse player stats do not expose every rare Sleeper scoring
event identically (for example every possible offensive fumble-recovery TD or
special-teams forced/recovered fumble), so this is explicitly a calibration
proxy rather than a claim of byte-identical Sleeper scoring.

Outputs
-------
research/no-history-v2/no_history_v2_phase2_prospect_prior.json
research/no-history-v2/no_history_v2_phase2_prospect_prior.md

Usage
-----
python3 research/no-history-v2/no_history_v2_phase2_prospect_prior.py --selftest
python3 research/no-history-v2/no_history_v2_phase2_prospect_prior.py --write
python3 research/no-history-v2/no_history_v2_phase2_prospect_prior.py --check
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import requests


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

INDEX_HTML = REPO_ROOT / "index.html"
PHASE1_COVERAGE_PATH = (
    REPO_ROOT
    / "research"
    / "no-history-v2"
    / "no_history_v2_phase1_coverage_audit.json"
)
PROD_PHASE1_PATH = (
    REPO_ROOT
    / "research"
    / "production-v2"
    / "production_v2_phase1_audit.json"
)
PHASE8_PATH = (
    REPO_ROOT
    / "research"
    / "production-v2"
    / "production_v2_phase8_shadow_model.json"
)

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "no-history-v2"
    / "no_history_v2_phase2_prospect_prior.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "no-history-v2"
    / "no_history_v2_phase2_prospect_prior.md"
)

NFLVERSE_PLAYERS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "players/players.csv"
)
NFLVERSE_WEEKLY_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{season}.csv"
)

METHOD_VERSION = "no-history-rookie-v2-phase2-prospect-prior-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
HISTORICAL_DRAFT_YEARS = tuple(range(2018, 2025))
HISTORICAL_STAT_YEARS = tuple(range(2018, 2026))

REFERENCE_VARIANT = "evidence_hybrid__floor_0.15"
BLEND_WEIGHTS = (0.00, 0.15, 0.30, 0.45)
PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_FLOOR = 0.15
PM_CEILING = 1.55
GLOBAL_VALUE_SCALE = 55.0
HTTP_TIMEOUT_SECONDS = 90

MODEL_PICK_ONLY = "position_ols_log_pick"
MODEL_PICK_AGE = "position_ols_log_pick_plus_draft_age"
MIN_POSITION_TRAIN_ROWS = 12
EPS = 1e-12

# Rare scoring elements not consistently exposed in nflverse's weekly
# player-stats schema with the same semantics as Sleeper.
KNOWN_PROXY_GAPS = (
    "offensive fumble-recovery touchdown",
    "blocked-kick scoring when not represented in unified player stats",
    "special-teams forced/recovered fumble scoring when not represented",
)


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


def finite_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def int_or_none(value: Any) -> int | None:
    x = finite_or_none(value)
    if x is None:
        return None
    n = int(round(x))
    if abs(x - n) > 1e-9:
        return None
    return n


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(float(v) for v in values)
    if len(vals) == 1:
        return vals[0]
    idx = (len(vals) - 1) * clamp(q, 0.0, 1.0)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    t = idx - lo
    return vals[lo] * (1 - t) + vals[hi] * t


def rankdata(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda x: (x[1], x[0]))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
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
    if len(xs) < 2:
        return None
    return pearson(rankdata(xs), rankdata(ys))


def rmse(actual: list[float], pred: list[float]) -> float | None:
    if not actual:
        return None
    return math.sqrt(
        statistics.fmean((a - p) ** 2 for a, p in zip(actual, pred))
    )


def mae(actual: list[float], pred: list[float]) -> float | None:
    if not actual:
        return None
    return statistics.fmean(abs(a - p) for a, p in zip(actual, pred))


def scheduled_games(season: int) -> int:
    return 16 if season <= 2020 else 17


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def fetch_csv_rows(
    url: str,
    session: requests.Session,
) -> list[dict[str, str]]:
    response = session.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    text = response.text
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise RuntimeError(f"No CSV rows returned from {url}")
    return rows


def normalize_position_group(
    position: Any,
    position_group: Any,
) -> str | None:
    pos = str(position or "").upper().strip()
    group = str(position_group or "").upper().strip()

    if group in {"QB", "RB", "WR", "TE"}:
        return group
    if pos in {"QB", "RB", "WR", "TE"}:
        return pos

    if group == "DL" or pos in {"DE", "DT", "NT", "DL"}:
        return "DL"
    if group == "LB" or pos in {"LB", "ILB", "OLB", "EDGE"}:
        return "LB"
    if group == "DB" or pos in {"CB", "DB", "FS", "SS", "S"}:
        return "DB"

    return None


def parse_birth_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def draft_age(birth: date | None, draft_year: int) -> float | None:
    if birth is None:
        return None
    # Use April 25 as a stable draft-date approximation across cohorts.
    as_of = date(draft_year, 4, 25)
    days = (as_of - birth).days
    if days <= 0:
        return None
    age = days / 365.2425
    return age if 18.0 <= age <= 30.0 else None


def row_value(row: dict[str, Any], *names: str) -> float:
    for name in names:
        if name in row:
            x = finite_or_none(row.get(name))
            if x is not None:
                return x
    return 0.0


def score_nflverse_week(row: dict[str, Any]) -> float:
    """
    Score one nflverse weekly player-stat row under the material components of
    this league's custom scoring, mirroring scripts/model/ppg_pipeline.py.
    """
    pts = 0.0

    pass_yd = row_value(row, "passing_yards")
    pts += pass_yd * 0.04
    pts += row_value(row, "passing_tds") * 4.0
    pts += row_value(row, "passing_2pt_conversions") * 2.0
    pts += row_value(
        row, "passing_interceptions", "interceptions"
    ) * -2.0
    if pass_yd >= 400:
        pts += 3.0
    elif pass_yd >= 300:
        pts += 2.0

    rush_yd = row_value(row, "rushing_yards")
    pts += row_value(row, "carries", "rushing_attempts") * 0.2
    pts += rush_yd * 0.1
    pts += row_value(row, "rushing_tds") * 6.0
    pts += row_value(row, "rushing_2pt_conversions") * 2.0
    if rush_yd >= 200:
        pts += 3.0
    elif rush_yd >= 100:
        pts += 2.0

    rec_yd = row_value(row, "receiving_yards")
    pts += row_value(row, "receptions") * 0.5
    pts += rec_yd * 0.1
    pts += row_value(row, "receiving_tds") * 6.0
    pts += row_value(row, "receiving_2pt_conversions") * 2.0
    if rec_yd >= 200:
        pts += 3.0
    elif rec_yd >= 100:
        pts += 2.0

    # Avoid double-counting lost fumbles: use aggregate when present, otherwise
    # sum the disjoint passing/rushing/receiving components.
    if "fumbles_lost" in row and finite_or_none(row.get("fumbles_lost")) is not None:
        fum_lost = row_value(row, "fumbles_lost")
    else:
        fum_lost = (
            row_value(row, "sack_fumbles_lost")
            + row_value(row, "rushing_fumbles_lost")
            + row_value(row, "receiving_fumbles_lost")
        )
    pts += fum_lost * -2.0

    solo = row_value(row, "def_tackles_solo")
    ast = row_value(
        row, "def_tackle_assists", "def_tackles_with_assist"
    )
    pts += solo * 1.5
    pts += ast * 0.75
    pts += row_value(row, "def_tackles_for_loss") * 2.0

    sacks = row_value(row, "def_sacks")
    pts += sacks * 3.0
    pts += row_value(row, "def_qb_hits") * 2.0

    ints = row_value(row, "def_interceptions")
    pts += ints * 6.0
    pts += row_value(row, "def_fumble_recovery_opp") * 4.0
    pts += row_value(row, "def_fumbles_forced") * 3.0
    pts += row_value(row, "def_safety") * 3.0
    pts += row_value(row, "def_tds") * 6.0

    pd = row_value(row, "def_pass_defended")
    pts += pd * 3.0

    if (solo + ast) >= 10:
        pts += 2.0
    if sacks >= 2:
        pts += 2.0
    if pd >= 3:
        pts += 2.0

    pts += row_value(row, "special_teams_tds") * 6.0

    return pts


def historical_player_metadata(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out = {}
    for row in rows:
        gsis_id = str(row.get("gsis_id") or "").strip()
        draft_year = int_or_none(row.get("draft_year"))
        draft_pick = int_or_none(row.get("draft_pick"))
        if not gsis_id or draft_year not in HISTORICAL_DRAFT_YEARS:
            continue
        if draft_pick is None or not (1 <= draft_pick <= 300):
            continue

        pos = normalize_position_group(
            row.get("position"),
            row.get("position_group"),
        )
        if pos not in TRACKED_POSITIONS:
            continue

        birth = parse_birth_date(row.get("birth_date"))
        age = draft_age(birth, draft_year)

        out[gsis_id] = {
            "player_id": gsis_id,
            "player": str(row.get("display_name") or "").strip() or gsis_id,
            "pos": pos,
            "draft_year": draft_year,
            "draft_round": int_or_none(row.get("draft_round")),
            "draft_pick": draft_pick,
            "draft_age": age,
        }
    return out


def build_historical_outcomes(
    players_rows: list[dict[str, Any]],
    stats_by_season: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    metadata = historical_player_metadata(players_rows)
    point_sums: dict[str, float] = defaultdict(float)
    row_counts: dict[str, int] = defaultdict(int)
    season_rows: dict[str, set[tuple[int, int]]] = defaultdict(set)

    for season, rows in stats_by_season.items():
        for row in rows:
            player_id = str(row.get("player_id") or "").strip()
            meta = metadata.get(player_id)
            if meta is None:
                continue

            if season not in {
                meta["draft_year"],
                meta["draft_year"] + 1,
            }:
                continue

            week = int_or_none(row.get("week"))
            if week is None:
                continue

            point_sums[player_id] += score_nflverse_week(row)
            row_counts[player_id] += 1
            season_rows[player_id].add((season, week))

    out = []
    for player_id, meta in metadata.items():
        draft_year = int(meta["draft_year"])
        second = draft_year + 1
        possible_games = scheduled_games(draft_year) + scheduled_games(second)

        total_points = float(point_sums.get(player_id, 0.0))
        rows_count = int(row_counts.get(player_id, 0))

        ppg_possible = total_points / possible_games
        active_row_ppg = (
            total_points / rows_count
            if rows_count > 0
            else 0.0
        )

        out.append(
            {
                **meta,
                "first_two_year_total_points": total_points,
                "possible_team_games": possible_games,
                "weekly_stat_rows": rows_count,
                "points_per_team_game": ppg_possible,
                "points_per_stat_row": active_row_ppg,
            }
        )

    return out


def design_matrix(
    rows: list[dict[str, Any]],
    model: str,
    age_center: float,
) -> np.ndarray:
    data = []
    for row in rows:
        log_pick = math.log(float(row["draft_pick"]))
        if model == MODEL_PICK_ONLY:
            data.append([1.0, log_pick])
        elif model == MODEL_PICK_AGE:
            age = row.get("draft_age")
            if age is None:
                raise RuntimeError("Age model received missing draft_age")
            data.append([1.0, log_pick, float(age) - age_center])
        else:
            raise ValueError(model)
    return np.asarray(data, dtype=float)


def fit_position_model(
    rows: list[dict[str, Any]],
    model: str,
) -> dict[str, Any] | None:
    usable = list(rows)
    if model == MODEL_PICK_AGE:
        usable = [r for r in usable if r.get("draft_age") is not None]

    n_features = 2 if model == MODEL_PICK_ONLY else 3
    if len(usable) < max(MIN_POSITION_TRAIN_ROWS, n_features + 2):
        return None

    age_values = [
        float(r["draft_age"])
        for r in usable
        if r.get("draft_age") is not None
    ]
    age_center = statistics.median(age_values) if age_values else 0.0

    x = design_matrix(usable, model, age_center)
    y = np.asarray(
        [float(r["points_per_team_game"]) for r in usable],
        dtype=float,
    )

    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    return {
        "model": model,
        "n": len(usable),
        "age_center": age_center,
        "coefficients": [float(v) for v in beta],
    }


def predict_position_model(
    fitted: dict[str, Any],
    row: dict[str, Any],
) -> float | None:
    model = fitted["model"]
    if model == MODEL_PICK_AGE and row.get("draft_age") is None:
        return None

    x = design_matrix(
        [row],
        model,
        float(fitted["age_center"]),
    )[0]
    beta = np.asarray(fitted["coefficients"], dtype=float)
    pred = float(x @ beta)
    return max(0.0, pred)


def leave_one_draft_year_out(
    historical: list[dict[str, Any]],
    model: str,
) -> dict[str, Any]:
    predictions = []

    for test_year in HISTORICAL_DRAFT_YEARS:
        training = [r for r in historical if r["draft_year"] != test_year]
        testing = [r for r in historical if r["draft_year"] == test_year]

        for pos in TRACKED_POSITIONS:
            train_pos = [r for r in training if r["pos"] == pos]
            test_pos = [r for r in testing if r["pos"] == pos]

            fitted = fit_position_model(train_pos, model)
            if fitted is None:
                continue

            for row in test_pos:
                pred = predict_position_model(fitted, row)
                if pred is None:
                    continue
                predictions.append(
                    {
                        "player": row["player"],
                        "pos": pos,
                        "draft_year": test_year,
                        "draft_pick": row["draft_pick"],
                        "draft_age": row.get("draft_age"),
                        "actual": row["points_per_team_game"],
                        "predicted": pred,
                    }
                )

    actual = [float(r["actual"]) for r in predictions]
    pred = [float(r["predicted"]) for r in predictions]

    by_position = {}
    for pos in TRACKED_POSITIONS:
        cohort = [r for r in predictions if r["pos"] == pos]
        a = [float(r["actual"]) for r in cohort]
        p = [float(r["predicted"]) for r in cohort]
        by_position[pos] = {
            "n": len(cohort),
            "mae": mae(a, p),
            "rmse": rmse(a, p),
            "spearman": spearman(a, p),
        }

    return {
        "model": model,
        "n": len(predictions),
        "mae": mae(actual, pred),
        "rmse": rmse(actual, pred),
        "spearman": spearman(actual, pred),
        "by_position": by_position,
        "predictions": predictions,
    }


def choose_position_models(
    cv_results: dict[str, dict[str, Any]],
) -> dict[str, str]:
    out = {}
    for pos in TRACKED_POSITIONS:
        candidates = []
        for model in (MODEL_PICK_ONLY, MODEL_PICK_AGE):
            row = cv_results[model]["by_position"][pos]
            if row["n"] > 0 and row["mae"] is not None:
                candidates.append((float(row["mae"]), model))
        if not candidates:
            continue
        candidates.sort(key=lambda x: (x[0], x[1]))
        out[pos] = candidates[0][1]
    return out


def fit_final_models(
    historical: list[dict[str, Any]],
    choices: dict[str, str],
) -> dict[str, dict[str, Any]]:
    out = {}
    for pos, model in choices.items():
        cohort = [r for r in historical if r["pos"] == pos]
        fitted = fit_position_model(cohort, model)
        if fitted is None:
            raise RuntimeError(f"Could not fit final {pos} model")
        out[pos] = fitted
    return out


def load_2026_eligible(
    coverage: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = coverage.get("prospect_prior_eligible_players")
    if not isinstance(rows, list) or len(rows) < 50:
        raise RuntimeError("Phase-1 eligible cohort is missing or sparse")
    return rows


def reference_phase8(phase8: dict[str, Any]) -> tuple[dict, dict]:
    variants = phase8.get("variants") or {}
    reference = variants.get(REFERENCE_VARIANT)
    if not isinstance(reference, dict):
        raise RuntimeError(f"Phase-8 reference variant missing: {REFERENCE_VARIANT}")
    players = reference.get("players")
    baselines = reference.get("baselines")
    if not isinstance(players, dict) or not isinstance(baselines, dict):
        raise RuntimeError("Phase-8 reference players/baselines missing")
    return players, baselines


def prior_pm_from_points(
    pos: str,
    predicted_points_per_game: float,
    baselines: dict[str, Any],
) -> dict[str, float]:
    baseline_points = float(baselines[pos]["combined_points"])
    season_points = predicted_points_per_game * 17.0
    ratio = season_points / baseline_points
    unclamped = PM_INTERCEPT + PM_RATIO_SLOPE * ratio
    raw_pm = clamp(unclamped, PM_FLOOR, PM_CEILING)
    return {
        "predicted_points_per_team_game": predicted_points_per_game,
        "season_equivalent_points_17g": season_points,
        "baseline_points": baseline_points,
        "ratio_to_baseline": ratio,
        "raw_unclamped_pm": unclamped,
        "raw_prod_mult": raw_pm,
    }


def historical_position_age_fallback(
    historical: list[dict[str, Any]],
    pos: str,
) -> float:
    ages = [
        float(r["draft_age"])
        for r in historical
        if r["pos"] == pos and r.get("draft_age") is not None
    ]
    if not ages:
        raise RuntimeError(f"No historical draft ages for {pos}")
    return statistics.median(ages)


def current_draft_age(
    row: dict[str, Any],
    historical: list[dict[str, Any]],
) -> float:
    draft = row.get("draft") or {}
    direct = finite_or_none(draft.get("draft_age"))
    if direct is not None:
        return direct

    age = finite_or_none(row.get("age"))
    if age is not None:
        return age

    return historical_position_age_fallback(historical, row["pos"])


def build_current_prior_rows(
    eligible: list[dict[str, Any]],
    historical: list[dict[str, Any]],
    final_models: dict[str, dict[str, Any]],
    phase8_players: dict[str, Any],
    baselines: dict[str, Any],
) -> list[dict[str, Any]]:
    out = []

    for row in eligible:
        draft = row.get("draft") or {}
        draft_pick = int_or_none(draft.get("pick"))
        draft_season = int_or_none(draft.get("season"))
        pos = row["pos"]
        player = row["player"]

        base = {
            "player": player,
            "pos": pos,
            "age": row.get("age"),
            "role": row.get("role"),
            "current_fundamental_value": row.get("current_fundamental_value"),
            "experience_class": row.get("experience_class"),
            "production_v2_candidate_present": bool(
                row.get("production_v2_candidate_present")
            ),
            "draft_year": draft_season,
            "draft_pick": draft_pick,
            "draft_round": int_or_none(draft.get("round")),
            "draft_age": None,
            "prior_available": False,
            "prior_model": final_models.get(pos, {}).get("model"),
            "prior": None,
            "phase8_reference": phase8_players.get(player),
        }

        if draft_pick is None or pos not in final_models:
            out.append(base)
            continue

        age = current_draft_age(row, historical)
        predict_row = {
            "draft_pick": draft_pick,
            "draft_age": age,
        }
        pred_ppg = predict_position_model(final_models[pos], predict_row)
        if pred_ppg is None:
            out.append(base)
            continue

        base["draft_age"] = age
        base["prior_available"] = True
        base["prior"] = prior_pm_from_points(
            pos,
            pred_ppg,
            baselines,
        )
        out.append(base)

    return out


def apply_effective_pm(role: str, raw_pm: float) -> float:
    if role == "Elite" and raw_pm < 0.65:
        return 0.65
    return raw_pm


def compute_value(
    player: str,
    pos: str,
    role: str,
    raw_pm: float,
    cfg: dict[str, Any],
    snapshot_values,
) -> dict[str, Any]:
    info = cfg["player_db"][player]
    age = info["age"]
    effective_pm = apply_effective_pm(role, raw_pm)

    age_mult = snapshot_values.effective_age_multiplier(
        pos,
        age,
        role,
        player,
        effective_pm,
        raw_pm,
        cfg,
    )
    position_weight = float(cfg["position_weight"].get(pos, 1.0))
    value = math.floor(
        100.0
        * position_weight
        * age_mult
        * effective_pm
        * GLOBAL_VALUE_SCALE
        + 0.5
    )

    return {
        "value": int(value),
        "raw_prod_mult": raw_pm,
        "effective_prod_mult": effective_pm,
        "age_mult": float(age_mult),
        "position_weight": position_weight,
    }


def build_blend_variants(
    current_rows: list[dict[str, Any]],
    cfg: dict[str, Any],
    snapshot_values,
) -> dict[str, Any]:
    variants = {}

    for weight in BLEND_WEIGHTS:
        key = f"prospect_prior_weight_{weight:.2f}"
        players = {}
        moved = []

        for row in current_rows:
            player = row["player"]
            ref = row.get("phase8_reference") or {}
            has_candidate = row["production_v2_candidate_present"]
            prior_available = row["prior_available"]

            # Formal variants preserve accepted continuity for missing V2 candidates.
            if not has_candidate:
                players[player] = {
                    "source": "continuity_unchanged_missing_v2_candidate",
                    "value": int(row["current_fundamental_value"]),
                    "prior_applied": False,
                }
                continue

            ref_raw_pm = finite_or_none(ref.get("raw_prod_mult"))
            if ref_raw_pm is None:
                raise RuntimeError(
                    f"{player}: normal V2 candidate missing Phase-8 raw PM"
                )

            if not prior_available or weight == 0.0:
                raw_pm = ref_raw_pm
                prior_applied = False
            else:
                prior_pm = float(row["prior"]["raw_prod_mult"])
                raw_pm = (1.0 - weight) * ref_raw_pm + weight * prior_pm
                raw_pm = clamp(raw_pm, PM_FLOOR, PM_CEILING)
                prior_applied = True

            computed = compute_value(
                player,
                row["pos"],
                str(row["role"]),
                raw_pm,
                cfg,
                snapshot_values,
            )
            ref_value = int(ref["value"])
            change_pct = (
                (computed["value"] - ref_value) / ref_value
                if ref_value
                else None
            )
            record = {
                "source": (
                    "v2_plus_historical_prospect_prior"
                    if prior_applied
                    else "phase8_reference_unchanged"
                ),
                "reference_value": ref_value,
                "prior_applied": prior_applied,
                "prior_weight": weight,
                **computed,
                "change_vs_phase8": computed["value"] - ref_value,
                "change_pct_vs_phase8": change_pct,
            }
            players[player] = record

            if prior_applied:
                moved.append(
                    {
                        "player": player,
                        "pos": row["pos"],
                        "draft_pick": row["draft_pick"],
                        "reference_value": ref_value,
                        "shadow_value": computed["value"],
                        "change_pct": change_pct,
                        "v2_raw_pm": ref_raw_pm,
                        "prior_raw_pm": row["prior"]["raw_prod_mult"],
                        "blended_raw_pm": raw_pm,
                    }
                )

        change_values = [
            float(r["change_pct"])
            for r in moved
            if r["change_pct"] is not None
        ]
        moved.sort(
            key=lambda r: (
                -abs(r["change_pct"] or 0.0),
                r["player"],
            )
        )

        variants[key] = {
            "prior_weight": weight,
            "formal_missing_candidate_policy": (
                "Phase-7 continuity retained; prospect prior never replaces "
                "a missing V2 candidate in formal variants."
            ),
            "eligible_player_count": len(current_rows),
            "prior_applied_count": len(moved),
            "median_abs_change_pct_vs_phase8": (
                median([abs(x) for x in change_values])
                if change_values
                else 0.0
            ),
            "p90_abs_change_pct_vs_phase8": (
                percentile([abs(x) for x in change_values], 0.90)
                if change_values
                else 0.0
            ),
            "largest_movers": moved[:30],
            "players": players,
        }

    return variants


def prior_only_missing_candidate_diagnostics(
    current_rows: list[dict[str, Any]],
    cfg: dict[str, Any],
    snapshot_values,
) -> list[dict[str, Any]]:
    out = []

    for row in current_rows:
        if row["production_v2_candidate_present"]:
            continue

        rec = {
            "player": row["player"],
            "pos": row["pos"],
            "draft_pick": row["draft_pick"],
            "current_value": row["current_fundamental_value"],
            "prior_available": row["prior_available"],
            "diagnostic_only": True,
            "production_authorized": False,
            "prior_only_value": None,
            "change_pct_vs_current": None,
        }

        if row["prior_available"]:
            raw_pm = float(row["prior"]["raw_prod_mult"])
            computed = compute_value(
                row["player"],
                row["pos"],
                str(row["role"]),
                raw_pm,
                cfg,
                snapshot_values,
            )
            current = int(row["current_fundamental_value"])
            rec["prior_only_value"] = computed["value"]
            rec["prior_raw_prod_mult"] = raw_pm
            rec["change_pct_vs_current"] = (
                (computed["value"] - current) / current
                if current
                else None
            )

        out.append(rec)

    out.sort(key=lambda r: (r["pos"], r["player"]))
    return out


def historical_summary(
    historical: list[dict[str, Any]],
) -> dict[str, Any]:
    by_position = {}
    for pos in TRACKED_POSITIONS:
        cohort = [r for r in historical if r["pos"] == pos]
        by_position[pos] = {
            "n": len(cohort),
            "median_draft_pick": median(
                [float(r["draft_pick"]) for r in cohort]
            ),
            "median_draft_age": median(
                [
                    float(r["draft_age"])
                    for r in cohort
                    if r.get("draft_age") is not None
                ]
            ),
            "median_points_per_team_game": median(
                [float(r["points_per_team_game"]) for r in cohort]
            ),
            "median_points_per_stat_row": median(
                [float(r["points_per_stat_row"]) for r in cohort]
            ),
        }
    return {
        "draft_years": list(HISTORICAL_DRAFT_YEARS),
        "player_count": len(historical),
        "by_position": by_position,
    }


def compact_cv(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": result["model"],
        "n": result["n"],
        "mae": result["mae"],
        "rmse": result["rmse"],
        "spearman": result["spearman"],
        "by_position": result["by_position"],
    }


def build_result(
    session: requests.Session | None = None,
) -> dict[str, Any]:
    sess = session or requests.Session()

    coverage = read_json(PHASE1_COVERAGE_PATH)
    phase1 = read_json(PROD_PHASE1_PATH)
    phase8 = read_json(PHASE8_PATH)

    if coverage.get("production_files_mutated") != 0:
        raise RuntimeError("Phase-1 coverage audit lost research-only guardrail")
    if phase8.get("deployment_authorized") is not False:
        raise RuntimeError("Phase-8 unexpectedly authorizes deployment")

    eligible = load_2026_eligible(coverage)
    phase8_players, baselines = reference_phase8(phase8)

    print("Downloading nflverse player metadata...")
    players_rows = fetch_csv_rows(NFLVERSE_PLAYERS_URL, sess)

    stats_by_season = {}
    for season in HISTORICAL_STAT_YEARS:
        print(f"Downloading nflverse weekly player stats {season}...")
        stats_by_season[season] = fetch_csv_rows(
            NFLVERSE_WEEKLY_URL.format(season=season),
            sess,
        )

    historical = build_historical_outcomes(
        players_rows,
        stats_by_season,
    )
    if len(historical) < 600:
        raise RuntimeError(
            f"Historical prospect cohort unexpectedly sparse: {len(historical)}"
        )

    cv_results = {
        MODEL_PICK_ONLY: leave_one_draft_year_out(
            historical,
            MODEL_PICK_ONLY,
        ),
        MODEL_PICK_AGE: leave_one_draft_year_out(
            historical,
            MODEL_PICK_AGE,
        ),
    }

    choices = choose_position_models(cv_results)
    if set(choices) != set(TRACKED_POSITIONS):
        raise RuntimeError(
            f"Missing position model choices: {set(TRACKED_POSITIONS) - set(choices)}"
        )

    final_models = fit_final_models(historical, choices)

    current_rows = build_current_prior_rows(
        eligible,
        historical,
        final_models,
        phase8_players,
        baselines,
    )

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    blend_variants = build_blend_variants(
        current_rows,
        cfg,
        snapshot_values,
    )

    missing_diagnostics = prior_only_missing_candidate_diagnostics(
        current_rows,
        cfg,
        snapshot_values,
    )

    prior_available = sum(1 for r in current_rows if r["prior_available"])
    candidate_and_prior = sum(
        1
        for r in current_rows
        if r["prior_available"] and r["production_v2_candidate_present"]
    )

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": "RESEARCH_ONLY_HISTORICAL_PROSPECT_PRIOR_SHADOW",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "production_v2_mutated": False,
        "market_value_mutated": False,
        "guardrail": (
            "Formal variants preserve Phase-7 continuity for missing V2 "
            "candidates. Prior-only values for those players are diagnostics only."
        ),
        "historical_method": {
            "draft_cohorts": list(HISTORICAL_DRAFT_YEARS),
            "weekly_stats_seasons": list(HISTORICAL_STAT_YEARS),
            "primary_target": (
                "custom_scored_first_two_season_points_per_scheduled_team_game"
            ),
            "secondary_target": "custom_scored_points_per_nflverse_weekly_stat_row",
            "cross_validation": "leave_one_draft_year_out",
            "candidate_models": [
                MODEL_PICK_ONLY,
                MODEL_PICK_AGE,
            ],
            "position_specific_model_selection": (
                "lowest leave-one-draft-year-out MAE within each position; "
                "research monitoring choice only"
            ),
            "known_scoring_proxy_gaps": list(KNOWN_PROXY_GAPS),
        },
        "sources": {
            "nflverse_players": NFLVERSE_PLAYERS_URL,
            "nflverse_weekly_template": NFLVERSE_WEEKLY_URL,
            "phase1_coverage": str(PHASE1_COVERAGE_PATH.relative_to(REPO_ROOT)),
            "production_v2_phase1": str(PROD_PHASE1_PATH.relative_to(REPO_ROOT)),
            "production_v2_phase8": str(PHASE8_PATH.relative_to(REPO_ROOT)),
        },
        "historical_summary": historical_summary(historical),
        "cross_validation": {
            MODEL_PICK_ONLY: compact_cv(cv_results[MODEL_PICK_ONLY]),
            MODEL_PICK_AGE: compact_cv(cv_results[MODEL_PICK_AGE]),
            "position_model_choice": choices,
        },
        "final_position_models": final_models,
        "current_2026_summary": {
            "eligible_players": len(current_rows),
            "prior_available": prior_available,
            "prior_and_normal_v2_candidate": candidate_and_prior,
            "missing_prior": len(current_rows) - prior_available,
            "formal_blend_weights": list(BLEND_WEIGHTS),
            "formal_missing_candidate_policy": (
                "continuity retained; no prior-only replacement"
            ),
        },
        "current_2026_players": current_rows,
        "blend_variants": blend_variants,
        "missing_v2_candidate_prior_only_diagnostics": missing_diagnostics,
        "phase3_handoff": {
            "purpose": (
                "Freeze the prospect-prior candidate family prospectively and "
                "grade it against future 2026 outcomes. Do not select a blend "
                "weight from current Fundamental Value or KTC alignment."
            ),
            "deployment_authorized": False,
        },
    }


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def pct(value: Any) -> str:
    if value is None:
        return "—"
    return f"{100.0 * float(value):.1f}%"


def signed_pct(value: Any) -> str:
    if value is None:
        return "—"
    return f"{100.0 * float(value):+.1f}%"


def render_markdown(result: dict[str, Any]) -> str:
    hist = result["historical_summary"]
    cv = result["cross_validation"]
    cur = result["current_2026_summary"]

    lines = [
        "# No-History / Rookie Value V2 — Phase 2 Historical Prospect Prior",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No deployed player value, Production V2 coefficient, "
        "Market Value input, or `index.html` constant is changed.**",
        "",
        result["guardrail"],
        "",
        "## Historical calibration sample",
        "",
        f"- Draft cohorts: **{hist['draft_years'][0]}–{hist['draft_years'][-1]}**",
        f"- Drafted tracked-position players: **{hist['player_count']}**",
        "- Primary outcome: **first two NFL seasons of custom-scored points per "
        "scheduled team game**",
        "- Cross-validation: **leave one entire draft year out**",
        "",
        "### Historical cohort by position",
        "",
        "| Pos | N | Median pick | Median draft age | Median pts/team game | "
        "Median pts/stat row |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for pos in TRACKED_POSITIONS:
        row = hist["by_position"][pos]
        lines.append(
            f"| {pos} | {row['n']} | "
            f"{fmt(row['median_draft_pick'], 1)} | "
            f"{fmt(row['median_draft_age'], 2)} | "
            f"{fmt(row['median_points_per_team_game'], 2)} | "
            f"{fmt(row['median_points_per_stat_row'], 2)} |"
        )

    lines.extend(
        [
            "",
            "## Historical cross-validation",
            "",
            "| Model | N | MAE ↓ | RMSE ↓ | Spearman ↑ |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for model in (MODEL_PICK_ONLY, MODEL_PICK_AGE):
        row = cv[model]
        lines.append(
            f"| `{model}` | {row['n']} | "
            f"{fmt(row['mae'])} | {fmt(row['rmse'])} | "
            f"{fmt(row['spearman'])} |"
        )

    lines.extend(
        [
            "",
            "### Position-specific monitoring model",
            "",
            "| Pos | Selected historical model | Pick-only MAE | Pick+age MAE |",
            "|---|---|---:|---:|",
        ]
    )
    for pos in TRACKED_POSITIONS:
        choice = cv["position_model_choice"][pos]
        p0 = cv[MODEL_PICK_ONLY]["by_position"][pos]
        p1 = cv[MODEL_PICK_AGE]["by_position"][pos]
        lines.append(
            f"| {pos} | `{choice}` | {fmt(p0['mae'])} | {fmt(p1['mae'])} |"
        )

    lines.extend(
        [
            "",
            "The selected position model is a **research monitoring choice only**. "
            "It is not a deployed coefficient.",
            "",
            "## 2026 prospect-prior coverage",
            "",
            f"- Phase-1 eligible players: **{cur['eligible_players']}**",
            f"- Historical prior available: **{cur['prior_available']}**",
            f"- Prior + normal V2 candidate: **{cur['prior_and_normal_v2_candidate']}**",
            f"- Missing historical prior: **{cur['missing_prior']}**",
            "",
            "## Formal shadow blend sensitivity",
            "",
            "Formal variants only apply the prior when a normal Production V2 "
            "candidate already exists. Missing-candidate players remain on the "
            "accepted continuity fallback.",
            "",
            "| Prior weight | Prior applied | Median abs Δ vs Phase 8 | "
            "P90 abs Δ vs Phase 8 |",
            "|---:|---:|---:|---:|",
        ]
    )

    for key, row in result["blend_variants"].items():
        lines.append(
            f"| {row['prior_weight']:.2f} | {row['prior_applied_count']} | "
            f"{pct(row['median_abs_change_pct_vs_phase8'])} | "
            f"{pct(row['p90_abs_change_pct_vs_phase8'])} |"
        )

    reference_key = "prospect_prior_weight_0.30"
    ref = result["blend_variants"][reference_key]
    lines.extend(
        [
            "",
            "### 30% prior-weight diagnostic movers",
            "",
            "This is a middle sensitivity setting for inspection, **not a recommended "
            "production weight**.",
            "",
            "| Player | Pos | Pick | Phase 8 | Shadow | Change | V2 PM | Prior PM |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for row in ref["largest_movers"][:25]:
        lines.append(
            f"| {row['player']} | {row['pos']} | "
            f"{row['draft_pick'] if row['draft_pick'] is not None else '—'} | "
            f"{row['reference_value']} | {row['shadow_value']} | "
            f"{signed_pct(row['change_pct'])} | "
            f"{fmt(row['v2_raw_pm'])} | {fmt(row['prior_raw_pm'])} |"
        )

    lines.extend(
        [
            "",
            "## Missing-V2 prior-only diagnostics",
            "",
            "These values are **diagnostic only**. The formal shadow variants do not "
            "use them and preserve current-value continuity.",
            "",
            "| Player | Pos | Pick | Current | Prior-only diagnostic | Change |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )

    for row in result["missing_v2_candidate_prior_only_diagnostics"]:
        lines.append(
            f"| {row['player']} | {row['pos']} | "
            f"{row['draft_pick'] if row['draft_pick'] is not None else '—'} | "
            f"{row['current_value']} | "
            f"{row['prior_only_value'] if row['prior_only_value'] is not None else '—'} | "
            f"{signed_pct(row['change_pct_vs_current'])} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Phase 2 answers whether **draft capital and draft age contain historical "
            "out-of-sample signal under this league's scoring**, and what happens "
            "when that prior is blended modestly with Production V2 for current "
            "rookies.",
            "",
            "It does **not** choose a production blend weight. Phase 3 should freeze "
            "the candidate family and grade the variants prospectively against "
            "future 2026 outcomes. Current Fundamental Value or KTC agreement must "
            "not be used to select the winner.",
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
        raise RuntimeError("Phase-2 method_version mismatch")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Phase-2 lost production mutation guardrail")
    if result.get("deployment_authorized") is not False:
        raise RuntimeError("Phase-2 unexpectedly authorizes deployment")
    if result.get("production_v2_mutated") is not False:
        raise RuntimeError("Phase-2 unexpectedly mutates Production V2")
    if result.get("market_value_mutated") is not False:
        raise RuntimeError("Phase-2 unexpectedly mutates Market Value")

    hist = result.get("historical_summary") or {}
    if int(hist.get("player_count") or 0) < 600:
        raise RuntimeError("Phase-2 historical cohort is implausibly small")

    cur = result.get("current_2026_summary") or {}
    if int(cur.get("eligible_players") or 0) < 80:
        raise RuntimeError("Phase-2 2026 eligible cohort is implausibly small")

    variants = result.get("blend_variants") or {}
    expected = {
        f"prospect_prior_weight_{w:.2f}"
        for w in BLEND_WEIGHTS
    }
    if set(variants) != expected:
        raise RuntimeError("Phase-2 blend variant manifest changed unexpectedly")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Phase-2 markdown report missing")

    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Historical cross-validation",
        "Formal shadow blend sensitivity",
        "Missing-V2 prior-only diagnostics",
    ):
        if marker not in text:
            raise RuntimeError(f"Phase-2 markdown missing marker: {marker}")

    print("No-History / Rookie V2 Phase-2 outputs passed guardrails.")


def run_selftest() -> None:
    synthetic = {
        "passing_yards": "325",
        "passing_tds": "2",
        "passing_interceptions": "1",
        "passing_2pt_conversions": "1",
        "carries": "5",
        "rushing_yards": "40",
        "rushing_tds": "1",
        "rushing_2pt_conversions": "0",
        "receptions": "0",
        "receiving_yards": "0",
        "receiving_tds": "0",
        "receiving_2pt_conversions": "0",
        "sack_fumbles_lost": "0",
        "rushing_fumbles_lost": "1",
        "receiving_fumbles_lost": "0",
    }
    # Passing: 13 + 8 - 2 + 2 + 2 bonus = 23
    # Rushing: 1 + 4 + 6 = 11
    # Fumble lost: -2
    # Total = 32
    assert abs(score_nflverse_week(synthetic) - 32.0) < 1e-9

    idp = {
        "def_tackles_solo": "8",
        "def_tackle_assists": "4",
        "def_tackles_for_loss": "2",
        "def_sacks": "2",
        "def_qb_hits": "3",
        "def_interceptions": "1",
        "def_fumble_recovery_opp": "1",
        "def_fumbles_forced": "1",
        "def_safety": "0",
        "def_tds": "0",
        "def_pass_defended": "3",
        "special_teams_tds": "0",
    }
    # 12 solo + 3 assists + 4 TFL + 6 sacks + 6 hits + 6 int
    # +4 FR +3 FF +9 PD + tackle bonus2 + sack bonus2 + PD bonus2 = 59
    assert abs(score_nflverse_week(idp) - 59.0) < 1e-9

    assert scheduled_games(2020) == 16
    assert scheduled_games(2021) == 17

    rows = [
        {
            "draft_pick": 10,
            "draft_age": 21.0,
            "points_per_team_game": 10.0,
        },
        {
            "draft_pick": 30,
            "draft_age": 22.0,
            "points_per_team_game": 7.0,
        },
        {
            "draft_pick": 60,
            "draft_age": 23.0,
            "points_per_team_game": 4.0,
        },
        {
            "draft_pick": 100,
            "draft_age": 22.0,
            "points_per_team_game": 2.0,
        },
    ] * 4

    fitted = fit_position_model(rows, MODEL_PICK_AGE)
    assert fitted is not None
    p10 = predict_position_model(
        fitted,
        {"draft_pick": 10, "draft_age": 21.0},
    )
    p100 = predict_position_model(
        fitted,
        {"draft_pick": 100, "draft_age": 22.0},
    )
    assert p10 is not None and p100 is not None and p10 > p100

    print(
        "No-History / Rookie V2 Phase-2 self-test passed: custom scoring, "
        "schedule denominators, OLS fit/prediction, and draft-capital direction."
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

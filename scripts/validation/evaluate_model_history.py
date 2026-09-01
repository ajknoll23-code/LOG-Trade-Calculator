#!/usr/bin/env python3
"""
evaluate_model_history.py

Out-of-sample evaluator for Trade Desk historical model snapshots.

This is the GRADING side of Improvement #2:

    research/model-history/snapshots/*.json
        = what the deployed calculator/source evidence said at the time

    research/model-history/outcomes/2026.json
        = what players actually produced afterward under the league's exact
          scoring rules, captured by capture_realized_outcomes.py

The protocol is intentionally frozen in code as FUNDAMENTAL_BACKTEST_V1.
Do not tune the production model from these results and then silently change
this evaluator. A methodology change requires a new protocol version.

Key leakage protections
-----------------------
1. The NFL scoring period containing the snapshot is NEVER graded.
   The first eligible target is the following scoring period. This makes a
   Friday snapshot safe even if Thursday-night results already exist.

2. A target week is considered complete only when BOTH:
     - that week exists in the realized-outcome file, and
     - the outcome file was refreshed on/after that week's completion boundary.
   The completion boundary is derived from Sleeper's season_start_date as
   start_date + 6 days + 7*(week-1), matching the Tuesday post-week refresh
   design. A manual mid-week full refresh therefore cannot leak a partial week.

3. Fixed horizons are only scored when EVERY required week is complete.
   There is no "grade on whatever games we currently have" behavior.

4. Repeated snapshots with the same fundamental predictions and the same first
   eligible future week are deduplicated. The latest capture is retained so
   manual workflow testing cannot overweight one model state.

Targets
-------
A) value_vs_total_points
   Full Trade Desk value versus future TOTAL fantasy points.
   Missing games remain zero. This is the roster-value / availability target.

B) value_vs_active_ppg
   Full Trade Desk value versus fantasy points per active game.
   Players with zero active games in the horizon are excluded.

C) prod_mult_vs_active_ppg
   Production multiplier versus fantasy points per active game.
   This isolates production-rate signal from age and positional economics.

Horizons
--------
- next 4 completed future weeks
- next 8 completed future weeks
- rest of regular season (through Week 18)

Metrics
-------
- Pearson correlation
- Spearman rank correlation
- pairwise ordering accuracy (ties excluded)
- min-max normalized MAE / RMSE (relative-structure diagnostic)
- tie-aware top-12 / top-24 / top-50 hit rate (overall only)

Subgroups
---------
- position
- offense / IDP / kicker
- age band
- role
- real-production-history lineage

Usage
-----
    python3 scripts/validation/evaluate_model_history.py
    python3 scripts/validation/evaluate_model_history.py --write
    python3 scripts/validation/evaluate_model_history.py --selftest

Outputs with --write
--------------------
    research/model-history/evaluation/latest.json
    research/model-history/evaluation/latest.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "research" / "model-history" / "snapshots"
OUTCOMES_PATH = REPO_ROOT / "research" / "model-history" / "outcomes" / "2026.json"
OUTPUT_DIR = REPO_ROOT / "research" / "model-history" / "evaluation"
OUTPUT_JSON = OUTPUT_DIR / "latest.json"
OUTPUT_MD = OUTPUT_DIR / "latest.md"

SEASON = "2026"
REGULAR_SEASON_LAST_WEEK = 18
MIN_CORRELATION_N = 3
TOP_NS = (12, 24, 50)

PROTOCOL = {
    "protocol_version": "fundamental-v1",
    "season": SEASON,
    "prediction_target_separation": {
        "current_scoring_period_excluded": True,
        "first_eligible_week_rule": (
            "If capture is before Sleeper season_start_date, first eligible week is 1. "
            "Otherwise determine the Sleeper 7-day scoring period containing the "
            "capture date and begin with the following period."
        ),
        "completed_week_rule": (
            "Week W is eligible only if it exists in outcomes AND outcomes.refreshed_at_utc "
            "is on/after season_start_date + 6 days + 7*(W-1)."
        ),
        "fixed_horizon_requires_every_week_complete": True,
    },
    "horizons": {
        "future_4w": 4,
        "future_8w": 8,
        "rest_of_season": "first_eligible_week_through_week_18",
    },
    "snapshot_deduplication": (
        "Within the same first eligible future week, snapshots with identical "
        "calculator value/prod_mult predictions are deduplicated; latest capture wins."
    ),
    "targets": {
        "value_vs_total_points": (
            "Trade Desk value vs total realized points; no-game weeks remain zero."
        ),
        "value_vs_active_ppg": (
            "Trade Desk value vs realized points per active game; zero-active-game players excluded."
        ),
        "prod_mult_vs_active_ppg": (
            "Production multiplier vs realized points per active game; zero-active-game players excluded."
        ),
    },
    "metrics": [
        "pearson",
        "spearman",
        "pairwise_ordering_accuracy",
        "minmax_normalized_mae",
        "minmax_normalized_rmse",
        "tie_aware_top_n_hit_rate_overall",
    ],
    "subgroups": ["position", "unit", "age_band", "role", "production_history_lineage"],
}

PROTOCOL_SHA256 = hashlib.sha256(
    json.dumps(PROTOCOL, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Required file does not exist: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}") from exc


def parse_utc(value: str) -> datetime:
    if not value:
        raise RuntimeError("Missing required UTC timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"Invalid UTC timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid date: {value!r}") from exc


def sha256_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def rankdata(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < MIN_CORRELATION_N or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(vx * vy)


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < MIN_CORRELATION_N or len(xs) != len(ys):
        return None
    return pearson(rankdata(xs), rankdata(ys))


def pairwise_ordering_accuracy(xs: list[float], ys: list[float]) -> tuple[float | None, int]:
    concordant = 0
    comparable = 0
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            dx = xs[i] - xs[j]
            dy = ys[i] - ys[j]
            if dx == 0 or dy == 0:
                continue
            comparable += 1
            if (dx > 0) == (dy > 0):
                concordant += 1
    if not comparable:
        return None, 0
    return concordant / comparable, comparable


def minmax_errors(xs: list[float], ys: list[float]) -> tuple[float | None, float | None]:
    if len(xs) < 2 or len(xs) != len(ys):
        return None, None
    xlo, xhi = min(xs), max(xs)
    ylo, yhi = min(ys), max(ys)
    if xhi == xlo or yhi == ylo:
        return None, None
    xn = [(x - xlo) / (xhi - xlo) for x in xs]
    yn = [(y - ylo) / (yhi - ylo) for y in ys]
    errors = [a - b for a, b in zip(xn, yn)]
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
    return mae, rmse


def tie_aware_top_n_hit_rate(
    names: list[str], predictions: list[float], outcomes: list[float], n: int
) -> dict[str, Any] | None:
    if not names or len(names) != len(predictions) or len(names) != len(outcomes):
        return None
    n_eff = min(n, len(names))
    predicted_order = sorted(
        range(len(names)),
        key=lambda i: (-predictions[i], names[i]),
    )
    predicted_top = predicted_order[:n_eff]

    realized_sorted = sorted(outcomes, reverse=True)
    threshold = realized_sorted[n_eff - 1]
    realized_top_including_ties = {
        i for i, value in enumerate(outcomes) if value >= threshold
    }
    hits = sum(1 for i in predicted_top if i in realized_top_including_ties)
    return {
        "requested_n": n,
        "effective_n": n_eff,
        "realized_boundary_score": round(float(threshold), 6),
        "realized_top_set_size_including_ties": len(realized_top_including_ties),
        "hits": hits,
        "hit_rate": round(hits / n_eff, 6) if n_eff else None,
    }


def metric_bundle(
    names: list[str],
    predictions: list[float],
    outcomes: list[float],
    include_top_n: bool = False,
) -> dict[str, Any]:
    if len(names) != len(predictions) or len(names) != len(outcomes):
        raise RuntimeError("Metric vectors have inconsistent lengths")

    p = pearson(predictions, outcomes)
    s = spearman(predictions, outcomes)
    pair_acc, comparable_pairs = pairwise_ordering_accuracy(predictions, outcomes)
    mae, rmse = minmax_errors(predictions, outcomes)

    result: dict[str, Any] = {
        "n": len(names),
        "pearson": round(p, 6) if p is not None else None,
        "spearman": round(s, 6) if s is not None else None,
        "pairwise_ordering_accuracy": round(pair_acc, 6) if pair_acc is not None else None,
        "comparable_pairs": comparable_pairs,
        "minmax_normalized_mae": round(mae, 6) if mae is not None else None,
        "minmax_normalized_rmse": round(rmse, 6) if rmse is not None else None,
    }
    if include_top_n:
        result["top_n"] = {
            str(n): tie_aware_top_n_hit_rate(names, predictions, outcomes, n)
            for n in TOP_NS
        }
    return result


def age_band(age: int | float | None) -> str:
    if age is None:
        return "unknown"
    age = float(age)
    if age <= 23:
        return "23_or_younger"
    if age <= 27:
        return "24_to_27"
    if age <= 31:
        return "28_to_31"
    return "32_plus"


def unit_bucket(pos: str) -> str:
    if pos in {"QB", "RB", "WR", "TE"}:
        return "offense"
    if pos in {"DL", "LB", "DB"}:
        return "idp"
    if pos == "K":
        return "kicker"
    return "other"


def first_eligible_future_week(captured_at_utc: str, season_start_date: str) -> int:
    capture_day = parse_utc(captured_at_utc).date()
    start = parse_date(season_start_date)
    if capture_day < start:
        return 1
    scoring_period = ((capture_day - start).days // 7) + 1
    return scoring_period + 1


def completion_date_for_week(season_start_date: str, week: int) -> date:
    if week < 1:
        raise RuntimeError(f"Invalid NFL week: {week}")
    start = parse_date(season_start_date)
    return start + timedelta(days=6 + 7 * (week - 1))


def completed_outcome_weeks(outcomes: dict[str, Any]) -> list[int]:
    state = outcomes.get("sleeper_state_at_refresh") or {}
    season_start_date = state.get("season_start_date")
    if not season_start_date:
        raise RuntimeError("Outcome file is missing Sleeper season_start_date")
    refreshed_day = parse_utc(outcomes.get("refreshed_at_utc")).date()
    weeks = outcomes.get("weeks") or {}
    completed = []
    for key in weeks:
        try:
            week = int(key)
        except (TypeError, ValueError):
            continue
        if 1 <= week <= REGULAR_SEASON_LAST_WEEK:
            if refreshed_day >= completion_date_for_week(season_start_date, week):
                completed.append(week)
    return sorted(set(completed))


def validate_outcomes(outcomes: dict[str, Any]) -> None:
    if outcomes.get("schema_version") != 1:
        raise RuntimeError("Unexpected realized-outcome schema_version")
    if str(outcomes.get("season")) != SEASON:
        raise RuntimeError(f"Expected outcome season {SEASON}")
    if outcomes.get("identity_coverage_pct") != 100.0:
        raise RuntimeError(
            f"Fundamental evaluator requires 100% identity coverage; got "
            f"{outcomes.get('identity_coverage_pct')}"
        )
    if outcomes.get("unresolved_model_keys"):
        raise RuntimeError("Fundamental evaluator refuses unresolved outcome identities")
    if outcomes.get("duplicate_model_key_identity_groups"):
        raise RuntimeError(
            "Fundamental evaluator refuses duplicate model-key identity groups to avoid double-counting"
        )
    state = outcomes.get("sleeper_state_at_refresh") or {}
    if not state.get("season_start_date"):
        raise RuntimeError("Outcome file is missing sleeper_state_at_refresh.season_start_date")


def prediction_fingerprint(snapshot: dict[str, Any]) -> str:
    values = (snapshot.get("model") or {}).get("calculator_values") or {}
    compact = {
        key: {
            "value": row.get("value"),
            "prod_mult": row.get("prod_mult"),
            "pos": row.get("pos"),
            "age": row.get("age"),
            "role": row.get("role"),
            "has_real_prod_data": row.get("has_real_prod_data"),
            "no_real_production_history": row.get("no_real_production_history"),
        }
        for key, row in values.items()
        if isinstance(row, dict)
    }
    return sha256_json(compact)


def load_snapshot_file(path: Path) -> dict[str, Any]:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid snapshot JSON: {path}: {exc}") from exc

    if snapshot.get("schema_version") != 1:
        raise RuntimeError(f"Unexpected snapshot schema in {path.name}")
    values = (snapshot.get("model") or {}).get("calculator_values")
    if not isinstance(values, dict) or len(values) < 500:
        raise RuntimeError(f"Snapshot calculator_values unexpectedly small in {path.name}")
    if not snapshot.get("captured_at_utc"):
        raise RuntimeError(f"Snapshot missing captured_at_utc: {path.name}")
    snapshot["_source_filename"] = path.name
    return snapshot


def load_snapshots(snapshot_dir: Path = SNAPSHOT_DIR) -> list[dict[str, Any]]:
    if not snapshot_dir.exists():
        raise RuntimeError(f"Snapshot directory does not exist: {snapshot_dir}")
    paths = sorted(snapshot_dir.glob("*.json"))
    if not paths:
        raise RuntimeError(f"No historical model snapshots found in {snapshot_dir}")
    return [load_snapshot_file(path) for path in paths]


def dedupe_prediction_states(
    snapshots: list[dict[str, Any]],
    season_start_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Group by first eligible future week + fundamental prediction fingerprint.
    Keep the latest capture in each group.
    """
    groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for snapshot in snapshots:
        first_week = first_eligible_future_week(
            snapshot["captured_at_utc"], season_start_date
        )
        fp = prediction_fingerprint(snapshot)
        snapshot["_first_eligible_week"] = first_week
        snapshot["_prediction_fingerprint"] = fp
        groups[(first_week, fp)].append(snapshot)

    retained = []
    dedup_audit = []
    for (first_week, fp), group in groups.items():
        group = sorted(group, key=lambda s: parse_utc(s["captured_at_utc"]))
        keep = group[-1]
        retained.append(keep)
        if len(group) > 1:
            dedup_audit.append({
                "first_eligible_week": first_week,
                "prediction_fingerprint_sha256": fp,
                "retained": keep.get("_source_filename"),
                "retained_captured_at_utc": keep["captured_at_utc"],
                "discarded": [
                    {
                        "filename": s.get("_source_filename"),
                        "captured_at_utc": s["captured_at_utc"],
                    }
                    for s in group[:-1]
                ],
            })

    retained.sort(key=lambda s: parse_utc(s["captured_at_utc"]))
    dedup_audit.sort(key=lambda r: (r["first_eligible_week"], r["retained_captured_at_utc"]))
    return retained, dedup_audit


def build_week_maps(outcomes: dict[str, Any]) -> dict[int, dict[str, dict[str, float]]]:
    """
    Return week -> model_key -> {points, games}. A duplicate key within one week
    is treated as an integrity error rather than silently double-counted.
    """
    result: dict[int, dict[str, dict[str, float]]] = {}
    for week_key, payload in (outcomes.get("weeks") or {}).items():
        week = int(week_key)
        mapping: dict[str, dict[str, float]] = {}
        for row in (payload or {}).get("players", []):
            points = float(row.get("fantasy_points") or 0.0)
            raw = row.get("raw_stats_used") or {}
            games = float(raw.get("gp") or 1.0)
            for model_key in row.get("model_keys") or []:
                if model_key in mapping:
                    raise RuntimeError(
                        f"Outcome week {week} contains duplicate model key {model_key!r}"
                    )
                mapping[model_key] = {"points": points, "games": games}
        result[week] = mapping
    return result


def horizon_weeks(first_week: int, horizon_name: str) -> list[int] | None:
    if first_week > REGULAR_SEASON_LAST_WEEK:
        return None
    if horizon_name == "future_4w":
        end = first_week + 3
        if end > REGULAR_SEASON_LAST_WEEK:
            return None
        return list(range(first_week, end + 1))
    if horizon_name == "future_8w":
        end = first_week + 7
        if end > REGULAR_SEASON_LAST_WEEK:
            return None
        return list(range(first_week, end + 1))
    if horizon_name == "rest_of_season":
        return list(range(first_week, REGULAR_SEASON_LAST_WEEK + 1))
    raise RuntimeError(f"Unknown horizon: {horizon_name}")


def aggregate_records(
    snapshot: dict[str, Any],
    weeks: list[int],
    week_maps: dict[int, dict[str, dict[str, float]]],
) -> list[dict[str, Any]]:
    values = snapshot["model"]["calculator_values"]
    records = []
    for model_key, info in values.items():
        total_points = 0.0
        active_games = 0.0
        for week in weeks:
            row = week_maps.get(week, {}).get(model_key)
            if row:
                total_points += row["points"]
                active_games += row["games"]

        active_ppg = total_points / active_games if active_games > 0 else None
        records.append({
            "model_key": model_key,
            "pos": info.get("pos"),
            "age": info.get("age"),
            "age_band": age_band(info.get("age")),
            "role": info.get("role"),
            "unit": unit_bucket(str(info.get("pos") or "")),
            "production_history_lineage": (
                "no_real_history"
                if info.get("no_real_production_history")
                else "real_history"
            ),
            "value": float(info.get("value") or 0.0),
            "prod_mult": float(info.get("prod_mult") or 0.0),
            "total_points": round(total_points, 6),
            "active_games": round(active_games, 6),
            "active_ppg": round(active_ppg, 6) if active_ppg is not None else None,
        })
    return records


def score_records(records: list[dict[str, Any]], include_top_n: bool) -> dict[str, Any]:
    names = [r["model_key"] for r in records]
    values = [r["value"] for r in records]
    totals = [r["total_points"] for r in records]

    active = [r for r in records if r["active_ppg"] is not None]
    active_names = [r["model_key"] for r in active]
    active_values = [r["value"] for r in active]
    active_prod = [r["prod_mult"] for r in active]
    active_ppg = [r["active_ppg"] for r in active]

    return {
        "player_count": len(records),
        "active_player_count": len(active),
        "value_vs_total_points": metric_bundle(
            names, values, totals, include_top_n=include_top_n
        ),
        "value_vs_active_ppg": metric_bundle(
            active_names, active_values, active_ppg, include_top_n=False
        ),
        "prod_mult_vs_active_ppg": metric_bundle(
            active_names, active_prod, active_ppg, include_top_n=False
        ),
    }


def subgroup_scores(records: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[str(record.get(field) or "unknown")].append(record)
    return {
        group: score_records(rows, include_top_n=False)
        for group, rows in sorted(groups.items())
    }


def evaluate_state(
    snapshot: dict[str, Any],
    completed_weeks: set[int],
    week_maps: dict[int, dict[str, dict[str, float]]],
) -> dict[str, Any]:
    first_week = int(snapshot["_first_eligible_week"])
    result: dict[str, Any] = {
        "snapshot": {
            "filename": snapshot.get("_source_filename"),
            "captured_at_utc": snapshot["captured_at_utc"],
            "refresh_mode": snapshot.get("refresh_mode"),
            "state_fingerprint_sha256": snapshot.get("state_fingerprint_sha256"),
            "prediction_fingerprint_sha256": snapshot["_prediction_fingerprint"],
            "first_eligible_future_week": first_week,
            "player_count": len(snapshot["model"]["calculator_values"]),
        },
        "horizons": {},
    }

    for horizon_name in ("future_4w", "future_8w", "rest_of_season"):
        weeks = horizon_weeks(first_week, horizon_name)
        if weeks is None:
            result["horizons"][horizon_name] = {
                "status": "not_applicable_season_boundary",
                "weeks": [],
            }
            continue

        missing = [w for w in weeks if w not in completed_weeks]
        if missing:
            result["horizons"][horizon_name] = {
                "status": "pending",
                "weeks": weeks,
                "missing_or_incomplete_weeks": missing,
            }
            continue

        records = aggregate_records(snapshot, weeks, week_maps)
        result["horizons"][horizon_name] = {
            "status": "evaluated",
            "weeks": weeks,
            "overall": score_records(records, include_top_n=True),
            "by_position": subgroup_scores(records, "pos"),
            "by_unit": subgroup_scores(records, "unit"),
            "by_age_band": subgroup_scores(records, "age_band"),
            "by_role": subgroup_scores(records, "role"),
            "by_production_history_lineage": subgroup_scores(
                records, "production_history_lineage"
            ),
        }

    return result


def build_evaluation(
    snapshots: list[dict[str, Any]],
    outcomes: dict[str, Any],
) -> dict[str, Any]:
    validate_outcomes(outcomes)

    state = outcomes["sleeper_state_at_refresh"]
    season_start_date = state["season_start_date"]
    completed = completed_outcome_weeks(outcomes)
    completed_set = set(completed)
    week_maps = build_week_maps(outcomes)

    states, dedup_audit = dedupe_prediction_states(snapshots, season_start_date)
    evaluations = [
        evaluate_state(snapshot, completed_set, week_maps)
        for snapshot in states
    ]

    evaluated_horizon_count = sum(
        1
        for item in evaluations
        for horizon in item["horizons"].values()
        if horizon["status"] == "evaluated"
    )
    pending_horizon_count = sum(
        1
        for item in evaluations
        for horizon in item["horizons"].values()
        if horizon["status"] == "pending"
    )

    return {
        "schema_version": 1,
        "protocol": PROTOCOL,
        "protocol_sha256": PROTOCOL_SHA256,
        "season": SEASON,
        "inputs": {
            "snapshot_count_seen": len(snapshots),
            "prediction_state_count_after_dedup": len(states),
            "outcomes_refreshed_at_utc": outcomes.get("refreshed_at_utc"),
            "outcome_identity_coverage_pct": outcomes.get("identity_coverage_pct"),
            "season_start_date": season_start_date,
            "completed_outcome_weeks": completed,
        },
        "summary": {
            "evaluated_horizon_count": evaluated_horizon_count,
            "pending_horizon_count": pending_horizon_count,
            "deduplicated_snapshot_count": len(snapshots) - len(states),
        },
        "snapshot_deduplication_audit": dedup_audit,
        "evaluations": evaluations,
    }


def fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_markdown(payload: dict[str, Any]) -> str:
    inp = payload["inputs"]
    summary = payload["summary"]

    lines = [
        "# Trade Desk Historical Fundamental Backtest",
        "",
        f"Protocol: `{PROTOCOL['protocol_version']}`  ",
        f"Protocol SHA256: `{payload['protocol_sha256']}`",
        "",
        "## Status",
        "",
        f"- Snapshots seen: **{inp['snapshot_count_seen']}**",
        f"- Prediction states after deduplication: **{inp['prediction_state_count_after_dedup']}**",
        f"- Deduplicated repeated snapshots: **{summary['deduplicated_snapshot_count']}**",
        f"- Outcome identity coverage: **{inp['outcome_identity_coverage_pct']}%**",
        f"- Completed realized weeks available: **{inp['completed_outcome_weeks']}**",
        f"- Evaluated snapshot/horizon combinations: **{summary['evaluated_horizon_count']}**",
        f"- Pending snapshot/horizon combinations: **{summary['pending_horizon_count']}**",
        "",
        "## Frozen V1 leakage rules",
        "",
        "The scoring period containing a snapshot is excluded. Fixed 4-week and "
        "8-week horizons are not graded until every required future week is complete. "
        "A week is only treated as complete when the realized-outcome refresh timestamp "
        "is on/after its Tuesday completion boundary derived from Sleeper's season start date.",
        "",
    ]

    evaluated_rows = []
    for item in payload["evaluations"]:
        meta = item["snapshot"]
        for horizon_name, horizon in item["horizons"].items():
            if horizon["status"] != "evaluated":
                continue
            overall = horizon["overall"]
            vt = overall["value_vs_total_points"]
            pp = overall["prod_mult_vs_active_ppg"]
            evaluated_rows.append((
                meta["captured_at_utc"],
                meta["first_eligible_future_week"],
                horizon_name,
                vt["spearman"],
                vt["pairwise_ordering_accuracy"],
                pp["spearman"],
                overall["active_player_count"],
            ))

    lines.extend([
        "## Evaluated horizons",
        "",
    ])
    if not evaluated_rows:
        lines.extend([
            "No horizon is mature enough to grade yet. This is expected before the first "
            "four post-snapshot regular-season weeks have completed.",
            "",
        ])
    else:
        lines.extend([
            "| Snapshot | First future week | Horizon | Value↔total Spearman | Pairwise acc. | ProdMult↔active PPG Spearman | Active players |",
            "|---|---:|---|---:|---:|---:|---:|",
        ])
        for row in evaluated_rows:
            lines.append(
                f"| {row[0]} | {row[1]} | {row[2]} | {fmt(row[3])} | "
                f"{fmt(row[4])} | {fmt(row[5])} | {row[6]} |"
            )
        lines.append("")

    lines.extend([
        "## Interpretation guardrails",
        "",
        "- `value_vs_total_points` is the roster-value/availability target.",
        "- `prod_mult_vs_active_ppg` is the cleaner production-rate target.",
        "- KTC is **not** treated as fundamental truth here; future market calibration is a separate target.",
        "- This evaluator reports evidence. It does not automatically rewrite player values or model constants.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    print(
        f"Historical evaluator wrote {OUTPUT_JSON.relative_to(REPO_ROOT)} and "
        f"{OUTPUT_MD.relative_to(REPO_ROOT)} | "
        f"evaluated_horizons={payload['summary']['evaluated_horizon_count']} | "
        f"completed_weeks={payload['inputs']['completed_outcome_weeks']}"
    )


def synthetic_snapshot(
    captured_at: str,
    filename: str,
    values: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "captured_at_utc": captured_at,
        "refresh_mode": "manual",
        "state_fingerprint_sha256": "a" * 64,
        "model": {"calculator_values": values},
        "_source_filename": filename,
    }


def run_selftest() -> None:
    assert first_eligible_future_week("2026-09-01T12:00:00Z", "2026-09-09") == 1
    assert first_eligible_future_week("2026-09-15T15:00:00Z", "2026-09-09") == 2
    assert first_eligible_future_week("2026-09-18T15:00:00Z", "2026-09-09") == 3

    players: dict[str, dict[str, Any]] = {}
    for i in range(12):
        # Descending model value and production multiplier.
        rank_strength = 12 - i
        players[f"player {i+1:02d}"] = {
            "pos": "QB" if i < 6 else "WR",
            "age": 22 + (i % 8),
            "role": "Elite" if i < 4 else ("Starter" if i < 8 else "Depth"),
            "value": rank_strength * 100,
            "prod_mult": rank_strength / 10,
            "has_real_prod_data": i >= 3,
            "no_real_production_history": i < 3,
        }

    # Two identical pre-season predictions for the same first future week:
    # dedupe must retain the later one.
    snapshots = [
        synthetic_snapshot(
            "2026-08-31T20:00:00Z", "a.json", players
        ),
        synthetic_snapshot(
            "2026-09-01T05:00:00Z", "b.json", players
        ),
        # Same prediction but a Friday in Week 2 -> first eligible Week 3.
        synthetic_snapshot(
            "2026-09-18T15:00:00Z", "c.json", players
        ),
    ]

    weeks: dict[str, Any] = {}
    for week in range(1, 6):
        rows = []
        for i, (name, info) in enumerate(players.items()):
            strength = 12 - i
            rows.append({
                "sleeper_id": str(i + 1),
                "player": name,
                "model_keys": [name],
                "model_positions": [info["pos"]],
                "fantasy_points": float(strength * 2),
                "raw_stats_used": {"gp": 1},
            })
        weeks[str(week)] = {"players": rows}

    # Refreshed on Week 4's Tuesday completion boundary. Week 5 exists in
    # the payload deliberately, but MUST NOT be treated as complete.
    outcomes = {
        "schema_version": 1,
        "season": "2026",
        "refreshed_at_utc": "2026-10-06T15:00:00Z",
        "identity_coverage_pct": 100.0,
        "unresolved_model_keys": [],
        "duplicate_model_key_identity_groups": {},
        "sleeper_state_at_refresh": {
            "season": "2026",
            "season_type": "regular",
            "season_start_date": "2026-09-09",
            "week": 5,
        },
        "weeks": weeks,
    }

    completed = completed_outcome_weeks(outcomes)
    assert completed == [1, 2, 3, 4], completed

    payload = build_evaluation(snapshots, outcomes)
    assert payload["inputs"]["prediction_state_count_after_dedup"] == 2
    assert payload["summary"]["deduplicated_snapshot_count"] == 1

    first = payload["evaluations"][0]
    assert first["snapshot"]["filename"] == "b.json"
    assert first["snapshot"]["first_eligible_future_week"] == 1

    h4 = first["horizons"]["future_4w"]
    assert h4["status"] == "evaluated"
    assert h4["weeks"] == [1, 2, 3, 4]
    assert h4["overall"]["value_vs_total_points"]["spearman"] == 1.0
    assert h4["overall"]["value_vs_total_points"]["pairwise_ordering_accuracy"] == 1.0
    assert h4["overall"]["prod_mult_vs_active_ppg"]["spearman"] == 1.0

    assert first["horizons"]["future_8w"]["status"] == "pending"

    second = payload["evaluations"][1]
    assert second["snapshot"]["first_eligible_future_week"] == 3
    assert second["horizons"]["future_4w"]["status"] == "pending"
    assert 5 in second["horizons"]["future_4w"]["missing_or_incomplete_weeks"]

    print(
        "evaluate_model_history self-test passed: leakage boundary, week-completion "
        "guard, deduplication, 4-week grading, and ranking metrics."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate historical Trade Desk predictions against realized outcomes."
    )
    parser.add_argument("--write", action="store_true", help="Write latest.json/latest.md")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    snapshots = load_snapshots()
    outcomes = read_json(OUTCOMES_PATH)
    payload = build_evaluation(snapshots, outcomes)

    if args.write:
        write_outputs(payload)
    else:
        print(json.dumps({
            "protocol_version": PROTOCOL["protocol_version"],
            "protocol_sha256": PROTOCOL_SHA256,
            "snapshot_count_seen": payload["inputs"]["snapshot_count_seen"],
            "prediction_state_count_after_dedup": payload["inputs"]["prediction_state_count_after_dedup"],
            "completed_outcome_weeks": payload["inputs"]["completed_outcome_weeks"],
            "evaluated_horizon_count": payload["summary"]["evaluated_horizon_count"],
            "pending_horizon_count": payload["summary"]["pending_horizon_count"],
        }, indent=2))


if __name__ == "__main__":
    main()

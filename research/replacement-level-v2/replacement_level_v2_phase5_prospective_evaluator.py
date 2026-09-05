#!/usr/bin/env python3
"""
Replacement Level / Positional Scale V2 — Phase 5 prospective evaluator.

FREEZE BEFORE WEEK 1. GRADE ONLY FUTURE EVIDENCE.

Research only. No deployed replacement rank, Production V2 input, PM transform,
POSITION_WEIGHT, global scale, or frozen prospective experiment is changed.

Frozen rank families
--------------------
- legacy_control
- prior_limited_evidence
- stable_positions_only
- full_phase2_leaders

Primary target
--------------
Prospective analogue of the reviewed historical baseline-backtester Test 3:

1. Freeze each family's preseason predicted production ratio:
       predicted_ratio = preseason_combined_points / family_preseason_baseline
2. After completed future weeks exist, derive a FUTURE-ONLY natural production
   split independently of every candidate family.
3. Define:
       future_ratio = realized_active_game_ppg / future_replacement_active_ppg
4. Score predicted_ratio vs future_ratio by MAE/RMSE.
5. Lower error is better.

The future target is intentionally candidate-independent. We do NOT define the
future denominator using each candidate's own proposed rank; that would make the
target partly candidate-defined and would not match the reviewed Test-3 method.

Primary aggregation
-------------------
Position-balanced mean MAE across QB/RB/WR/TE/DL/LB/DB so larger position
cohorts do not dominate the decision.

Secondary target
----------------
The same future-only relative-production test using cumulative total points.
This includes availability and is supporting evidence, not the primary baseline
decision target.

Cohort isolation
----------------
All 518 complete Production-V2 Phase-1 candidates are frozen so the future-only
position structure is derived from the full candidate universe. The primary
error cohort is the 426 players with real production history, keeping the
separately frozen No-History/Rookie V2 experiment out of the replacement-rank
decision.

Readiness
---------
0 weeks: ready / waiting
1-3: collection only
4-7: early diagnostic only
8-11: calibration review eligible
12-17: stability review eligible
18: season complete review

Immutable once created
----------------------
research/replacement-level-v2/replacement_level_v2_phase5_frozen_candidates.json

Refreshable
-----------
research/replacement-level-v2/replacement_level_v2_phase5_evaluation.json
research/replacement-level-v2/replacement_level_v2_phase5_evaluation.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
VALIDATION_DIR = REPO_ROOT / "scripts" / "validation"

PHASE1_JSON = (
    REPO_ROOT
    / "research"
    / "production-v2"
    / "production_v2_phase1_audit.json"
)
PHASE2_JSON = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase2_historical_backtest.json"
)
PHASE4_JSON = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase4_combined_identifiability_audit.json"
)
OUTCOMES_PATH = (
    REPO_ROOT
    / "research"
    / "model-history"
    / "outcomes"
    / "2026.json"
)

FROZEN_PATH = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase5_frozen_candidates.json"
)
OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase5_evaluation.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase5_evaluation.md"
)

METHOD_VERSION = "replacement-level-v2-phase5-prospective-v1"
PHASE2_METHOD = "replacement-level-v2-phase2-historical-backtest-v1"
PHASE4_METHOD = "replacement-level-v2-phase4-combined-identifiability-v1"

SEASON = "2026"
REGULAR_SEASON_LAST_WEEK = 18
MAX_FUTURE_SPLIT_RANK = 60
MIN_SPLIT_GROUP = 5
MIN_POSITION_TARGET_N = 15

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
SELECTED_FAMILIES = (
    "legacy_control",
    "prior_limited_evidence",
    "stable_positions_only",
    "full_phase2_leaders",
)
CONTROL = "legacy_control"

EXPECTED_TRANSFORM = {
    "intercept": -0.1,
    "ratio_slope": 0.75,
    "floor": 0.15,
    "ceiling": 1.55,
}
EXPECTED_SCALE = 55.0


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON: {path}: {exc}") from exc


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def load_model_evaluator():
    if str(VALIDATION_DIR) not in sys.path:
        sys.path.insert(0, str(VALIDATION_DIR))
    import evaluate_model_history  # type: ignore
    return evaluate_model_history


def sse_reduction_for_split(values_sorted: list[float], split_rank: int):
    n = len(values_sorted)
    if split_rank < 1 or split_rank >= n:
        return None
    a = values_sorted[:split_rank]
    b = values_sorted[split_rank:]
    if not a or not b:
        return None
    mean_all = statistics.fmean(values_sorted)
    before = sum((x - mean_all) ** 2 for x in values_sorted)
    mean_a = statistics.fmean(a)
    mean_b = statistics.fmean(b)
    after = (
        sum((x - mean_a) ** 2 for x in a)
        + sum((x - mean_b) ** 2 for x in b)
    )
    return before - after


def find_best_split(
    values_sorted: list[float],
    min_group: int = MIN_SPLIT_GROUP,
):
    n = len(values_sorted)
    best_split = None
    best_reduction = -1.0
    for split_rank in range(min_group, n - min_group):
        reduction = sse_reduction_for_split(values_sorted, split_rank)
        if reduction is not None and reduction > best_reduction:
            best_reduction = reduction
            best_split = split_rank
    return best_split


def validate_upstream(
    phase1: dict[str, Any],
    phase2: dict[str, Any],
    phase4: dict[str, Any],
) -> None:
    if phase2.get("method_version") != PHASE2_METHOD:
        raise RuntimeError("Unexpected Replacement Level V2 Phase-2 method")
    if phase4.get("method_version") != PHASE4_METHOD:
        raise RuntimeError("Unexpected Replacement Level V2 Phase-4 method")

    for payload_name, payload in (("Phase 2", phase2), ("Phase 4", phase4)):
        for field in (
            "deployment_authorized",
            "production_v2_change_authorized",
            "replacement_rank_change_authorized",
            "position_weight_change_authorized",
            "scale_change_authorized",
        ):
            if payload.get(field) is not False:
                raise RuntimeError(
                    f"{payload_name} unexpectedly authorizes {field}"
                )

    if phase4.get("transform_change_authorized") is not False:
        raise RuntimeError("Phase 4 unexpectedly authorizes transform change")
    if phase4.get("frozen_prospective_experiments_touched") is not False:
        raise RuntimeError("Phase 4 says frozen experiments were touched")

    decision = phase4.get("decision") or {}
    if decision.get("phase5_should_freeze_rank_families_only") is not True:
        raise RuntimeError("Phase 4 no longer authorizes rank-family-only freeze")
    if decision.get("global_scale_is_identified") is not False:
        raise RuntimeError("Phase 4 unexpectedly identifies global scale")
    if decision.get("affine_transform_spacing_is_identified") is not False:
        raise RuntimeError("Phase 4 unexpectedly identifies affine transform")

    recommendation = phase4.get("phase5_freeze_recommendation") or {}
    if recommendation.get("control") != CONTROL:
        raise RuntimeError("Phase 4 control family changed")
    comparators = recommendation.get("comparators")
    if comparators != list(SELECTED_FAMILIES[1:]):
        raise RuntimeError("Phase 4 comparator manifest changed")

    transform = recommendation.get("transform")
    if not isinstance(transform, dict):
        raise RuntimeError("Phase 4 frozen transform missing")
    for key, expected in EXPECTED_TRANSFORM.items():
        if abs(float(transform.get(key)) - expected) > 1e-12:
            raise RuntimeError(f"Phase 4 transform changed at {key}")

    if abs(float(recommendation.get("global_scale")) - EXPECTED_SCALE) > 1e-12:
        raise RuntimeError("Phase 4 global scale changed")

    rank_families = phase4.get("rank_families")
    if not isinstance(rank_families, dict):
        raise RuntimeError("Phase 4 rank families missing")
    if tuple(rank_families.keys()) != SELECTED_FAMILIES:
        # JSON preserves insertion order from the generated artifact. Still,
        # compare as a set too so the error is clear if only order changed.
        if set(rank_families) != set(SELECTED_FAMILIES):
            raise RuntimeError("Phase 4 rank family membership changed")

    scenarios = phase4.get("scenarios") or {}
    for family in SELECTED_FAMILIES[1:]:
        row = scenarios.get(family)
        if not isinstance(row, dict):
            raise RuntimeError(f"Phase 4 scenario missing: {family}")
        if row.get("combined_board_safety_pass") is not True:
            raise RuntimeError(f"Phase 4 family failed board safety: {family}")

    players = phase1.get("players")
    if not isinstance(players, dict):
        raise RuntimeError("Production V2 Phase 1 players missing")

    cohort_policy = phase4.get("prospective_cohort_policy") or {}
    if int(cohort_policy.get("phase1_candidate_count") or 0) != 518:
        raise RuntimeError("Phase 4 Phase-1 candidate count changed")
    if int(cohort_policy.get("real_history_primary_count") or 0) != 426:
        raise RuntimeError("Phase 4 real-history primary count changed")


def build_frozen_payload() -> dict[str, Any]:
    phase1 = read_json(PHASE1_JSON)
    phase2 = read_json(PHASE2_JSON)
    phase4 = read_json(PHASE4_JSON)
    validate_upstream(phase1, phase2, phase4)

    outcomes = read_json(OUTCOMES_PATH)
    state = outcomes.get("sleeper_state_at_refresh") or {}
    season_start_date = state.get("season_start_date")
    if not season_start_date:
        raise RuntimeError("Outcome file missing season_start_date")

    frozen_at = now_utc()
    model_eval = load_model_evaluator()
    if (
        model_eval.parse_utc(frozen_at).date()
        >= model_eval.parse_date(season_start_date)
    ):
        raise RuntimeError(
            "Refusing to create Replacement Level V2 Phase-5 frozen candidates "
            f"on/after 2026 season start ({season_start_date})."
        )

    source_players = phase1["players"]
    players: dict[str, dict[str, Any]] = {}
    for key in sorted(source_players):
        rec = source_players[key]
        if rec.get("candidate") is None:
            continue
        combined = rec.get("phase1_combined_points")
        pos = str(rec.get("pos") or "").upper()
        if combined is None or pos not in TRACKED_POSITIONS:
            continue

        no_history = bool(
            ((rec.get("current") or {}).get("no_real_production_history"))
        )
        players[key] = {
            "pos": pos,
            "phase1_combined_points": float(combined),
            "primary_real_history_eligible": not no_history,
            "no_real_production_history": no_history,
        }

    if len(players) != 518:
        raise RuntimeError(
            f"Expected 518 complete Phase-1 candidates, got {len(players)}"
        )
    primary_count = sum(
        1 for rec in players.values()
        if rec["primary_real_history_eligible"]
    )
    if primary_count != 426:
        raise RuntimeError(
            f"Expected 426 real-history primary players, got {primary_count}"
        )

    rank_families = phase4["rank_families"]
    scenarios = phase4["scenarios"]

    variants: dict[str, dict[str, Any]] = {}
    for family in SELECTED_FAMILIES:
        ranks = {
            pos: int(rank_families[family][pos])
            for pos in TRACKED_POSITIONS
        }
        baselines = scenarios[family].get("baselines")
        if not isinstance(baselines, dict):
            raise RuntimeError(f"{family}: Phase 4 baselines missing")

        baseline_manifest = {}
        predictions = {}
        for pos in TRACKED_POSITIONS:
            row = baselines.get(pos)
            if not isinstance(row, dict):
                raise RuntimeError(f"{family}/{pos}: baseline missing")
            if int(row.get("rank")) != ranks[pos]:
                raise RuntimeError(
                    f"{family}/{pos}: baseline rank disagrees with family rank"
                )
            points = float(row.get("combined_points") or 0.0)
            if points <= 0:
                raise RuntimeError(f"{family}/{pos}: non-positive baseline")
            baseline_manifest[pos] = {
                "rank": ranks[pos],
                "player": row.get("player"),
                "combined_points": points,
                "cohort_size": int(row.get("cohort_size") or 0),
            }

        for key, info in players.items():
            pos = info["pos"]
            baseline = baseline_manifest[pos]["combined_points"]
            predictions[key] = {
                "predicted_production_ratio": (
                    info["phase1_combined_points"] / baseline
                ),
                "preseason_baseline_rank": ranks[pos],
                "preseason_baseline_points": baseline,
            }

        variants[family] = {
            "replacement_ranks": ranks,
            "baselines": baseline_manifest,
            "predictions": predictions,
        }

    payload = {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "FROZEN_PRESEASON_REPLACEMENT_LEVEL_CANDIDATES",
        "research_only": True,
        "deployment_authorized": False,
        "production_v2_change_authorized": False,
        "replacement_rank_change_authorized": False,
        "position_weight_change_authorized": False,
        "transform_change_authorized": False,
        "scale_change_authorized": False,
        "frozen_at_utc": frozen_at,
        "source_phase1_sha256": canonical_sha256(phase1),
        "source_phase2_sha256": canonical_sha256(phase2),
        "source_phase4_sha256": canonical_sha256(phase4),
        "cohort_size": len(players),
        "primary_real_history_cohort_size": primary_count,
        "players": players,
        "variant_manifest": list(SELECTED_FAMILIES),
        "variants": variants,
        "protocol": {
            "season": SEASON,
            "control_variant": CONTROL,
            "primary_target": (
                "preseason_predicted_production_ratio_vs_future_only_"
                "active_game_ppg_relative_production_structure"
            ),
            "primary_metric": "position_balanced_mean_mae",
            "secondary_target": (
                "preseason_predicted_production_ratio_vs_future_only_"
                "cumulative_total_points_relative_production_structure"
            ),
            "future_target_denominator": (
                "candidate-independent future-only SSE-reduction natural split, "
                "matching reviewed historical Test 3"
            ),
            "future_split_top_n_cap": MAX_FUTURE_SPLIT_RANK,
            "future_split_min_group": MIN_SPLIT_GROUP,
            "full_candidate_universe_for_future_structure": True,
            "primary_error_cohort_real_history_only": True,
            "no_history_rookie_v2_experiment_unchanged": True,
            "production_v2_phase9_experiment_unchanged": True,
            "transform": dict(EXPECTED_TRANSFORM),
            "global_scale": EXPECTED_SCALE,
            "position_weights": "held fixed; not part of this experiment",
            "deployment_authorized": False,
        },
    }
    payload["frozen_prediction_sha256"] = canonical_sha256(
        {
            "players": payload["players"],
            "variant_manifest": payload["variant_manifest"],
            "variants": payload["variants"],
            "protocol": payload["protocol"],
        }
    )
    return payload


def freeze_if_needed() -> dict[str, Any]:
    # Preserve an existing immutable preseason freeze before applying the date
    # guard. Scheduled in-season runs must never rebuild predictions.
    if FROZEN_PATH.exists():
        frozen = read_json(FROZEN_PATH)
        if frozen.get("method_version") != METHOD_VERSION:
            raise RuntimeError("Existing Replacement Level V2 Phase-5 method mismatch")
        if frozen.get("variant_manifest") != list(SELECTED_FAMILIES):
            raise RuntimeError("Existing Phase-5 rank-family manifest changed")
        if int(frozen.get("cohort_size") or 0) != 518:
            raise RuntimeError("Existing Phase-5 frozen cohort size changed")
        if int(frozen.get("primary_real_history_cohort_size") or 0) != 426:
            raise RuntimeError("Existing Phase-5 primary cohort size changed")
        print(
            "Frozen Replacement Level V2 Phase-5 candidates already exist; "
            "preserving immutable preseason predictions."
        )
        return frozen

    payload = build_frozen_payload()
    FROZEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    FROZEN_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote immutable {FROZEN_PATH.relative_to(REPO_ROOT)}")
    return payload


def consecutive_prefix(completed_weeks: list[int], first_week: int) -> list[int]:
    completed = set(int(w) for w in completed_weeks)
    out = []
    week = int(first_week)
    while week <= REGULAR_SEASON_LAST_WEEK and week in completed:
        out.append(week)
        week += 1
    return out


def aggregate_realized(
    players: list[str],
    weeks: list[int],
    week_maps: dict[int, dict[str, dict[str, float]]],
) -> dict[str, dict[str, float | None]]:
    out = {
        player: {
            "total_points": 0.0,
            "active_games": 0.0,
            "active_ppg": None,
        }
        for player in players
    }

    for week in weeks:
        mapping = week_maps.get(week, {})
        for player in players:
            row = mapping.get(player)
            if row is None:
                continue
            out[player]["total_points"] = (
                float(out[player]["total_points"] or 0.0)
                + float(row.get("points") or 0.0)
            )
            out[player]["active_games"] = (
                float(out[player]["active_games"] or 0.0)
                + float(row.get("games") or 0.0)
            )

    for player in players:
        points = float(out[player]["total_points"] or 0.0)
        games = float(out[player]["active_games"] or 0.0)
        out[player]["active_ppg"] = points / games if games > 0 else None

    return out


def future_structure_for_position(
    frozen: dict[str, Any],
    realized: dict[str, dict[str, float | None]],
    pos: str,
    target_field: str,
) -> dict[str, Any]:
    rows = []
    for player, info in frozen["players"].items():
        if info["pos"] != pos:
            continue
        value = realized[player].get(target_field)
        if value is None:
            continue
        rows.append((player, float(value)))

    rows.sort(key=lambda kv: (-kv[1], kv[0]))
    capped = rows[:MAX_FUTURE_SPLIT_RANK]
    values = [value for _, value in capped]

    if len(values) < MIN_POSITION_TARGET_N:
        return {
            "available": False,
            "reason": "insufficient_future_target_rows",
            "target_row_count": len(values),
        }

    split = find_best_split(values)
    if split is None:
        return {
            "available": False,
            "reason": "future_split_unresolved",
            "target_row_count": len(values),
        }

    replacement_value = float(values[split - 1])
    if replacement_value <= 0:
        return {
            "available": False,
            "reason": "future_replacement_value_nonpositive",
            "target_row_count": len(values),
            "future_split_rank": split,
            "future_replacement_value": replacement_value,
        }

    actual_ratio = {
        player: (
            float(realized[player][target_field]) / replacement_value
            if realized[player].get(target_field) is not None
            else None
        )
        for player, info in frozen["players"].items()
        if info["pos"] == pos
    }

    return {
        "available": True,
        "target_row_count": len(rows),
        "future_split_search_count": len(values),
        "future_split_rank": split,
        "future_replacement_player": capped[split - 1][0],
        "future_replacement_value": replacement_value,
        "actual_ratio": actual_ratio,
    }


def error_bundle(errors: list[float]) -> dict[str, Any]:
    if not errors:
        return {
            "n": 0,
            "mae": None,
            "rmse": None,
            "median_absolute_error": None,
            "p90_absolute_error": None,
        }
    abs_errors = sorted(abs(e) for e in errors)
    n = len(errors)
    idx90 = int(math.ceil(0.90 * n)) - 1
    idx90 = max(0, min(n - 1, idx90))
    return {
        "n": n,
        "mae": statistics.fmean(abs_errors),
        "rmse": math.sqrt(statistics.fmean(e * e for e in errors)),
        "median_absolute_error": statistics.median(abs_errors),
        "p90_absolute_error": abs_errors[idx90],
    }


def evaluate_target(
    frozen: dict[str, Any],
    realized: dict[str, dict[str, float | None]],
    target_field: str,
) -> dict[str, Any]:
    structure = {
        pos: future_structure_for_position(
            frozen, realized, pos, target_field
        )
        for pos in TRACKED_POSITIONS
    }

    variants = {}
    for family in frozen["variant_manifest"]:
        by_position = {}
        pooled_errors = []

        for pos in TRACKED_POSITIONS:
            target = structure[pos]
            if not target.get("available"):
                by_position[pos] = {
                    "available": False,
                    "reason": target.get("reason"),
                    "future_split_rank": target.get("future_split_rank"),
                    "future_replacement_value": target.get(
                        "future_replacement_value"
                    ),
                    "metrics": error_bundle([]),
                }
                continue

            errors = []
            for player, info in frozen["players"].items():
                if info["pos"] != pos:
                    continue
                if not info["primary_real_history_eligible"]:
                    continue
                actual = target["actual_ratio"].get(player)
                if actual is None:
                    continue
                pred = float(
                    frozen["variants"][family]["predictions"][player][
                        "predicted_production_ratio"
                    ]
                )
                errors.append(pred - float(actual))

            metrics = error_bundle(errors)
            pooled_errors.extend(errors)
            by_position[pos] = {
                "available": metrics["n"] >= 1,
                "future_split_rank": target["future_split_rank"],
                "future_replacement_player": target[
                    "future_replacement_player"
                ],
                "future_replacement_value": target[
                    "future_replacement_value"
                ],
                "metrics": metrics,
            }

        pos_maes = [
            row["metrics"]["mae"]
            for row in by_position.values()
            if row["available"] and row["metrics"]["mae"] is not None
        ]
        pos_rmses = [
            row["metrics"]["rmse"]
            for row in by_position.values()
            if row["available"] and row["metrics"]["rmse"] is not None
        ]

        variants[family] = {
            "position_balanced_mean_mae": (
                statistics.fmean(pos_maes) if pos_maes else None
            ),
            "position_balanced_mean_rmse": (
                statistics.fmean(pos_rmses) if pos_rmses else None
            ),
            "positions_available": len(pos_maes),
            "pooled": error_bundle(pooled_errors),
            "by_position": by_position,
        }

    future_structure = {}
    for pos, row in structure.items():
        future_structure[pos] = {
            k: v for k, v in row.items()
            if k != "actual_ratio"
        }

    return {
        "target_field": target_field,
        "future_structure": future_structure,
        "variants": variants,
    }


def delta(value: Any, control: Any):
    if value is None or control is None:
        return None
    return float(value) - float(control)


def deltas_vs_control(target_result: dict[str, Any]) -> dict[str, Any]:
    variants = target_result["variants"]
    control = variants[CONTROL]
    out = {}
    for family, row in variants.items():
        if family == CONTROL:
            continue

        by_pos = {}
        for pos in TRACKED_POSITIONS:
            cur = row["by_position"][pos]["metrics"]
            base = control["by_position"][pos]["metrics"]
            by_pos[pos] = {
                "mae_delta": delta(cur.get("mae"), base.get("mae")),
                "rmse_delta": delta(cur.get("rmse"), base.get("rmse")),
            }

        out[family] = {
            "position_balanced_mean_mae_delta": delta(
                row.get("position_balanced_mean_mae"),
                control.get("position_balanced_mean_mae"),
            ),
            "position_balanced_mean_rmse_delta": delta(
                row.get("position_balanced_mean_rmse"),
                control.get("position_balanced_mean_rmse"),
            ),
            "pooled_mae_delta": delta(
                row["pooled"].get("mae"),
                control["pooled"].get("mae"),
            ),
            "by_position": by_pos,
        }
    return out


def readiness(weeks: int) -> str:
    if weeks <= 0:
        return "READY_WAITING_FOR_COMPLETED_WEEK_1"
    if weeks <= 3:
        return "COLLECTION_ONLY"
    if weeks <= 7:
        return "EARLY_DIAGNOSTIC_ONLY"
    if weeks <= 11:
        return "CALIBRATION_REVIEW_ELIGIBLE"
    if weeks <= 17:
        return "STABILITY_REVIEW_ELIGIBLE"
    return "SEASON_COMPLETE_REVIEW"


def build_evaluation(frozen: dict[str, Any]) -> dict[str, Any]:
    model_eval = load_model_evaluator()
    outcomes = read_json(OUTCOMES_PATH)
    model_eval.validate_outcomes(outcomes)

    state = outcomes.get("sleeper_state_at_refresh") or {}
    season_start_date = state.get("season_start_date")
    if not season_start_date:
        raise RuntimeError("Outcome file missing season_start_date")

    first_week = model_eval.first_eligible_future_week(
        frozen["frozen_at_utc"],
        season_start_date,
    )
    completed = model_eval.completed_outcome_weeks(outcomes)
    usable = consecutive_prefix(completed, first_week)
    week_maps = model_eval.build_week_maps(outcomes)

    player_names = sorted(frozen["players"])
    realized = aggregate_realized(player_names, usable, week_maps)

    if usable:
        primary = evaluate_target(frozen, realized, "active_ppg")
        secondary = evaluate_target(frozen, realized, "total_points")
    else:
        empty_realized = realized
        primary = evaluate_target(frozen, empty_realized, "active_ppg")
        secondary = evaluate_target(frozen, empty_realized, "total_points")

    active_primary = sum(
        1
        for player, info in frozen["players"].items()
        if info["primary_real_history_eligible"]
        and float(realized[player].get("active_games") or 0.0) > 0
    )

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": readiness(len(usable)),
        "research_only": True,
        "deployment_authorized": False,
        "production_v2_change_authorized": False,
        "replacement_rank_change_authorized": False,
        "position_weight_change_authorized": False,
        "transform_change_authorized": False,
        "scale_change_authorized": False,
        "production_files_mutated": 0,
        "frozen_prediction_sha256": frozen["frozen_prediction_sha256"],
        "frozen_at_utc": frozen["frozen_at_utc"],
        "first_eligible_week": first_week,
        "completed_outcome_weeks": completed,
        "completed_consecutive_weeks_used": usable,
        "completed_consecutive_week_count": len(usable),
        "frozen_candidate_universe_count": frozen["cohort_size"],
        "primary_real_history_cohort_count": frozen[
            "primary_real_history_cohort_size"
        ],
        "primary_players_with_active_game": active_primary,
        "primary_active_game_ppg_relative_production": primary,
        "secondary_total_points_relative_production": secondary,
        "primary_deltas_vs_control": deltas_vs_control(primary),
        "secondary_deltas_vs_control": deltas_vs_control(secondary),
        "realized_player_outcomes": realized,
        "interpretation_guardrail": (
            "Lower MAE/RMSE is better. The primary decision statistic is "
            "position-balanced mean MAE for active-game PPG relative production. "
            "Do not select or deploy a replacement-rank family before calibration-"
            "review readiness. Weeks 1-3 are collection only; Weeks 4-7 are early "
            "diagnostics only. Promotion requires stable improvement versus the "
            "frozen legacy control across the aggregate and position-level errors "
            "and must be reconciled with the separately frozen Production V2, "
            "No-History/Rookie V2, Age Curve V2, Opportunity V2, and Durability V2 "
            "experiments."
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


def render_markdown(result: dict[str, Any], frozen: dict[str, Any]) -> str:
    lines = [
        "# Replacement Level / Positional Scale V2 — Phase 5 Prospective Evaluator",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No replacement-rank or production deployment is authorized.**",
        "",
        f"- Frozen candidate SHA256: `{result['frozen_prediction_sha256']}`",
        f"- Frozen at: **{result['frozen_at_utc']}**",
        f"- First eligible future week: **{result['first_eligible_week']}**",
        f"- Completed consecutive weeks used: **{result['completed_consecutive_weeks_used'] or 'none'}**",
        f"- Full frozen candidate universe: **{result['frozen_candidate_universe_count']}**",
        f"- Primary real-history cohort: **{result['primary_real_history_cohort_count']}**",
        f"- Primary players with an active game: **{result['primary_players_with_active_game']}**",
        "",
        "## Frozen replacement-rank families",
        "",
        "| Family | QB | RB | WR | TE | DL | LB | DB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for family in SELECTED_FAMILIES:
        ranks = frozen["variants"][family]["replacement_ranks"]
        lines.append(
            f"| `{family}` | {ranks['QB']} | {ranks['RB']} | {ranks['WR']} | "
            f"{ranks['TE']} | {ranks['DL']} | {ranks['LB']} | {ranks['DB']} |"
        )

    lines += [
        "",
        "## Primary prospective metric",
        "",
        "Target: **future-only active-game PPG relative-production structure**.",
        "",
        "The future replacement point is derived from the realized future data itself via "
        "the same candidate-independent SSE split used by the reviewed historical Test 3.",
        "",
        "**Primary statistic: position-balanced mean MAE. Lower is better.**",
        "",
        "| Family | Pos-balanced MAE | Pos-balanced RMSE | Pooled MAE | Δ MAE vs control | Positions available |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    primary = result["primary_active_game_ppg_relative_production"]
    for family in SELECTED_FAMILIES:
        row = primary["variants"][family]
        d = (
            None if family == CONTROL
            else result["primary_deltas_vs_control"][family][
                "position_balanced_mean_mae_delta"
            ]
        )
        lines.append(
            f"| `{family}` | {fmt(row['position_balanced_mean_mae'])} | "
            f"{fmt(row['position_balanced_mean_rmse'])} | "
            f"{fmt(row['pooled'].get('mae'))} | {signed(d)} | "
            f"{row['positions_available']} |"
        )

    lines += [
        "",
        "## Future-only replacement structure",
        "",
        "| Pos | Future split rank | Replacement player | Active PPG at split |",
        "|---|---:|---|---:|",
    ]
    for pos in TRACKED_POSITIONS:
        row = primary["future_structure"][pos]
        lines.append(
            f"| {pos} | "
            f"{row.get('future_split_rank') if row.get('available') else '—'} | "
            f"{row.get('future_replacement_player') or '—'} | "
            f"{fmt(row.get('future_replacement_value'))} |"
        )

    lines += [
        "",
        "## Secondary availability-inclusive metric",
        "",
        "The same candidate-independent future-relative-production test using cumulative total points.",
        "",
        "| Family | Pos-balanced MAE | Δ MAE vs control | Pooled MAE |",
        "|---|---:|---:|---:|",
    ]
    secondary = result["secondary_total_points_relative_production"]
    for family in SELECTED_FAMILIES:
        row = secondary["variants"][family]
        d = (
            None if family == CONTROL
            else result["secondary_deltas_vs_control"][family][
                "position_balanced_mean_mae_delta"
            ]
        )
        lines.append(
            f"| `{family}` | {fmt(row['position_balanced_mean_mae'])} | "
            f"{signed(d)} | {fmt(row['pooled'].get('mae'))} |"
        )

    lines += [
        "",
        "## Readiness ladder",
        "",
        "- Weeks 1–3: **collection only**",
        "- Weeks 4–7: **early diagnostic only**",
        "- Weeks 8–11: **calibration review eligible**",
        "- Weeks 12–17: **stability review eligible**",
        "- Week 18: **season-complete review**",
        "",
        "## Interpretation",
        "",
        result["interpretation_guardrail"],
        "",
        "## Fixed outside this experiment",
        "",
        "- PM transform: `clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)`",
        "- Global value scale: `55`",
        "- `POSITION_WEIGHT`: unchanged",
        "- Production V2 Phase 9: unchanged",
        "- No-History/Rookie V2: unchanged",
        "- Age Curve V2: unchanged",
        "- Opportunity V2: unchanged",
        "- Durability V2: unchanged",
        "",
    ]
    return "\n".join(lines)


def write_evaluation(result: dict[str, Any], frozen: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(
        render_markdown(result, frozen),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


def check_outputs() -> None:
    frozen = read_json(FROZEN_PATH)
    result = read_json(OUTPUT_JSON)

    if frozen.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Frozen Replacement Level V2 Phase-5 method mismatch")
    if result.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Replacement Level V2 Phase-5 evaluation method mismatch")

    if frozen.get("variant_manifest") != list(SELECTED_FAMILIES):
        raise RuntimeError("Frozen Phase-5 family manifest changed")
    if int(frozen.get("cohort_size") or 0) != 518:
        raise RuntimeError("Frozen Phase-5 full cohort changed")
    if int(frozen.get("primary_real_history_cohort_size") or 0) != 426:
        raise RuntimeError("Frozen Phase-5 primary cohort changed")

    for payload in (frozen, result):
        for field in (
            "deployment_authorized",
            "production_v2_change_authorized",
            "replacement_rank_change_authorized",
            "position_weight_change_authorized",
            "transform_change_authorized",
            "scale_change_authorized",
        ):
            if payload.get(field) is not False:
                raise RuntimeError(f"Phase 5 guardrail failed: {field}")

    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Phase-5 production mutation guardrail failed")

    if (
        result.get("frozen_prediction_sha256")
        != frozen.get("frozen_prediction_sha256")
    ):
        raise RuntimeError("Phase-5 evaluation/freeze SHA mismatch")

    protocol = frozen.get("protocol") or {}
    if protocol.get("control_variant") != CONTROL:
        raise RuntimeError("Frozen Phase-5 control changed")
    if protocol.get("primary_metric") != "position_balanced_mean_mae":
        raise RuntimeError("Frozen Phase-5 primary metric changed")
    if protocol.get("primary_error_cohort_real_history_only") is not True:
        raise RuntimeError("Frozen Phase-5 cohort isolation changed")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Replacement Level V2 Phase-5 markdown missing")
    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Primary prospective metric",
        "Future-only replacement structure",
        "Readiness ladder",
        "position-balanced mean MAE",
    ):
        if marker not in text:
            raise RuntimeError(f"Phase-5 report missing marker: {marker}")

    print("Replacement Level V2 Phase-5 outputs passed guardrails.")


def run_selftest() -> None:
    assert consecutive_prefix([], 1) == []
    assert consecutive_prefix([1, 2, 3], 1) == [1, 2, 3]
    assert consecutive_prefix([1, 3], 1) == [1]

    assert readiness(0) == "READY_WAITING_FOR_COMPLETED_WEEK_1"
    assert readiness(3) == "COLLECTION_ONLY"
    assert readiness(8) == "CALIBRATION_REVIEW_ELIGIBLE"
    assert readiness(18) == "SEASON_COMPLETE_REVIEW"

    # Recover a known future cliff.
    values = [30.0 - i * 0.3 for i in range(20)] + [10.0] * 20
    assert find_best_split(values) == 20

    errs = [0.1, -0.2, 0.3]
    bundle = error_bundle(errs)
    assert abs(bundle["mae"] - 0.2) < 1e-12
    assert abs(bundle["rmse"] - math.sqrt((0.01 + 0.04 + 0.09) / 3)) < 1e-12

    # Denominator magnitude matters even when ordering is identical.
    actual = [2.0, 1.5, 1.0]
    correct = [2.0, 1.5, 1.0]
    wrong = [1.0, 0.75, 0.5]
    correct_mae = error_bundle([p-a for p, a in zip(correct, actual)])["mae"]
    wrong_mae = error_bundle([p-a for p, a in zip(wrong, actual)])["mae"]
    assert correct_mae < wrong_mae

    print(
        "Replacement Level V2 Phase-5 self-test passed: future split recovery, "
        "error metrics, denominator magnitude discrimination, completed-week "
        "prefix, and readiness."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return
    if args.check:
        check_outputs()
        return

    frozen = freeze_if_needed() if args.freeze else read_json(FROZEN_PATH)
    result = build_evaluation(frozen)

    if args.write:
        write_evaluation(result, frozen)
    else:
        print(render_markdown(result, frozen))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Age Curve V2 — Phase 5 prospective evaluator.

FREEZE BEFORE WEEK 1. GRADE LATER.

Research only. No deployed AGE_CURVE or player value is changed.

Frozen family
-------------
- deployed_control
- position_k25__w50__all_positions
- position_k25__w50__qb_control
- tier_k50__w25__all_positions

Why these variants
------------------
Phase 4 identified eight screened survivors. This is the smallest useful family:
1. deployed control;
2. strongest screened historical/current-stability bridge;
3. same bridge with QB held on deployed aging;
4. conservative tier-sensitive alternative.

Only CURRENT real-history players are graded. NO_REAL_PRODUCTION_HISTORY players
are excluded because every candidate intentionally leaves them unchanged and
their inclusion would dilute age-curve discrimination.

Primary target
--------------
Frozen Fundamental Value vs cumulative future fantasy points.

Secondary target
----------------
Frozen Fundamental Value vs future active-game PPG.

All variants share the same current production multipliers and position weights;
only the age factor differs, so variant-to-variant differences isolate the age
layer within the current value architecture.

Leakage controls
----------------
Reuses scripts/validation/evaluate_model_history.py for:
- outcome integrity validation
- completed-week determination
- exact league-scored weekly outcome maps
- metric bundles

No partial week is graded.

Readiness
---------
0 weeks: ready / waiting
1-3: collection only
4-7: early diagnostic only
8-11: calibration review eligible
12-17: stability review eligible
18: season complete review

Outputs
-------
Immutable once created:
research/age-curve-v2/age_curve_v2_phase5_frozen_candidates.json

Refreshable:
research/age-curve-v2/age_curve_v2_phase5_evaluation.json
research/age-curve-v2/age_curve_v2_phase5_evaluation.md

Usage
-----
python3 research/age-curve-v2/age_curve_v2_phase5_prospective_evaluator.py --selftest
python3 research/age-curve-v2/age_curve_v2_phase5_prospective_evaluator.py --freeze --write
python3 research/age-curve-v2/age_curve_v2_phase5_prospective_evaluator.py --write
python3 research/age-curve-v2/age_curve_v2_phase5_prospective_evaluator.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
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

PHASE3_SCRIPT = (
    REPO_ROOT / "research" / "age-curve-v2" / "age_curve_v2_phase3_shadow_audit.py"
)
PHASE3_JSON = (
    REPO_ROOT / "research" / "age-curve-v2" / "age_curve_v2_phase3_shadow_audit.json"
)
PHASE4_SCRIPT = (
    REPO_ROOT / "research" / "age-curve-v2" / "age_curve_v2_phase4_bridge_calibration.py"
)
PHASE4_JSON = (
    REPO_ROOT / "research" / "age-curve-v2" / "age_curve_v2_phase4_bridge_calibration.json"
)

OUTCOMES_PATH = (
    REPO_ROOT / "research" / "model-history" / "outcomes" / "2026.json"
)

FROZEN_PATH = (
    REPO_ROOT / "research" / "age-curve-v2" / "age_curve_v2_phase5_frozen_candidates.json"
)
OUTPUT_JSON = (
    REPO_ROOT / "research" / "age-curve-v2" / "age_curve_v2_phase5_evaluation.json"
)
OUTPUT_MD = (
    REPO_ROOT / "research" / "age-curve-v2" / "age_curve_v2_phase5_evaluation.md"
)

METHOD_VERSION = "age-curve-v2-phase5-prospective-v1"
SEASON = "2026"
REGULAR_SEASON_LAST_WEEK = 18

CONTROL = "deployed_control"
SELECTED_VARIANTS = (
    CONTROL,
    "position_k25__w50__all_positions",
    "position_k25__w50__qb_control",
    "tier_k50__w25__all_positions",
)
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")


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


def load_module(path: Path, name: str):
    if not path.exists():
        raise RuntimeError(f"Missing module: {path.relative_to(REPO_ROOT)}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path.relative_to(REPO_ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_model_evaluator():
    if str(VALIDATION_DIR) not in sys.path:
        sys.path.insert(0, str(VALIDATION_DIR))
    import evaluate_model_history  # type: ignore
    return evaluate_model_history


def validate_upstream(phase3: dict[str, Any], phase4: dict[str, Any]) -> None:
    if phase3.get("method_version") != "age-curve-v2-phase3-shadow-audit-v1":
        raise RuntimeError("Unexpected Phase-3 method version")
    if phase4.get("method_version") != "age-curve-v2-phase4-bridge-calibration-v1":
        raise RuntimeError("Unexpected Phase-4 method version")

    for payload in (phase3, phase4):
        if payload.get("deployment_authorized") is not False:
            raise RuntimeError("Upstream age research unexpectedly authorizes deployment")
        if payload.get("age_curve_change_authorized") is not False:
            raise RuntimeError("Upstream age research unexpectedly authorizes AGE_CURVE changes")

    screening = phase4.get("screening") or {}
    for key in SELECTED_VARIANTS[1:]:
        row = screening.get(key)
        if not isinstance(row, dict):
            raise RuntimeError(f"Selected Phase-5 variant missing Phase-4 screening: {key}")
        if not row.get("passes_all_research_screening_gates"):
            raise RuntimeError(f"Selected Phase-5 variant did not pass Phase-4 gates: {key}")


def build_current_selected_predictions(
    phase3: dict[str, Any],
    phase4: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
    phase3_module = load_module(PHASE3_SCRIPT, "age_curve_v2_phase3_for_p5")
    phase4_module = load_module(PHASE4_SCRIPT, "age_curve_v2_phase4_for_p5")

    snapshot_values = phase3_module.load_snapshot_values()
    cfg = snapshot_values.load_from_html(phase3_module.INDEX_HTML)

    direct_control = phase3["variants"]["deployed_control"]["players"]
    bridge_outputs = phase4_module.current_bridge_outputs(
        phase3,
        phase3_module,
        cfg,
    )

    eligible_players = {}
    for player, row in direct_control.items():
        if row.get("no_real_production_history"):
            continue
        eligible_players[player] = {
            "pos": row["pos"],
            "age": row["age"],
            "role": row["role"],
            "effective_prod_mult": float(row["effective_prod_mult"]),
            "deployed_age_mult": float(row["deployed_age_mult"]),
        }

    if len(eligible_players) < 400:
        raise RuntimeError(
            f"Real-history Phase-5 cohort unexpectedly small: {len(eligible_players)}"
        )

    variants: dict[str, dict[str, dict[str, Any]]] = {}

    variants[CONTROL] = {}
    for player in sorted(eligible_players):
        row = direct_control[player]
        variants[CONTROL][player] = {
            "value": int(row["deployed_value"]),
            "age_mult": float(row["deployed_age_mult"]),
        }

    for key in SELECTED_VARIANTS[1:]:
        source = bridge_outputs.get(key)
        if not isinstance(source, dict):
            raise RuntimeError(f"Could not rebuild selected bridge: {key}")
        variants[key] = {}
        for player in sorted(eligible_players):
            row = source[player]
            variants[key][player] = {
                "value": int(row["shadow_value"]),
                "age_mult": float(row["bridge_age_mult"]),
            }

    return eligible_players, variants


def build_frozen_payload() -> dict[str, Any]:
    phase3 = read_json(PHASE3_JSON)
    phase4 = read_json(PHASE4_JSON)
    validate_upstream(phase3, phase4)

    players, variants = build_current_selected_predictions(phase3, phase4)

    # Freeze at the actual first successful Phase-5 run time. Phase 4 did not
    # persist a generated_at_utc field, so pretending otherwise would create a
    # false provenance timestamp. The freeze itself must still be preseason.
    frozen_at = now_utc()

    outcomes = read_json(OUTCOMES_PATH)
    season_start_date = (
        (outcomes.get("sleeper_state_at_refresh") or {}).get("season_start_date")
    )
    if not season_start_date:
        raise RuntimeError("Outcome file missing season_start_date for freeze guardrail")

    model_eval = load_model_evaluator()
    if model_eval.parse_utc(frozen_at).date() >= model_eval.parse_date(season_start_date):
        raise RuntimeError(
            "Refusing to create Age Curve Phase-5 frozen candidates on/after "
            f"2026 season start ({season_start_date})."
        )

    payload = {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "FROZEN_PRESEASON_AGE_CURVE_CANDIDATES",
        "research_only": True,
        "deployment_authorized": False,
        "age_curve_change_authorized": False,
        "frozen_at_utc": frozen_at,
        "source_phase4_method_version": phase4.get("method_version"),
        "source_phase4_sha256": canonical_sha256(phase4),
        "cohort_definition": (
            "current tracked QB/RB/WR/TE/DL/LB/DB players with real production history"
        ),
        "cohort_size": len(players),
        "players": players,
        "variant_manifest": list(SELECTED_VARIANTS),
        "variants": variants,
        "protocol": {
            "season": SEASON,
            "control_variant": CONTROL,
            "primary_target": "fundamental_value_vs_cumulative_future_total_points",
            "secondary_target": "fundamental_value_vs_future_active_game_ppg",
            "no_history_players_excluded": True,
            "reason_no_history_excluded": (
                "All age candidates intentionally leave no-history players unchanged; "
                "including them would dilute age-curve discrimination."
            ),
            "deployment_authorized": False,
        },
    }
    payload["frozen_prediction_sha256"] = canonical_sha256(
        {
            "players": payload["players"],
            "variants": payload["variants"],
            "protocol": payload["protocol"],
        }
    )
    return payload


def freeze_if_needed() -> dict[str, Any]:
    # IMPORTANT: preserve an existing immutable preseason freeze BEFORE
    # rebuilding any candidate payload or evaluating the preseason date guard.
    # Scheduled in-season runs use --freeze --write, so rebuilding first would
    # incorrectly fail on/after season start even though the valid frozen file
    # already exists and should simply be graded.
    if FROZEN_PATH.exists():
        existing = read_json(FROZEN_PATH)
        if existing.get("method_version") != METHOD_VERSION:
            raise RuntimeError("Existing frozen Age Curve Phase-5 method mismatch")
        if existing.get("variant_manifest") != list(SELECTED_VARIANTS):
            raise RuntimeError("Existing frozen Age Curve Phase-5 candidate family changed")
        print(
            "Frozen Age Curve Phase-5 candidate file already exists; "
            "preserving immutable preseason predictions."
        )
        return existing

    # Only a brand-new freeze is allowed to build current candidates and pass
    # through build_frozen_payload()'s preseason creation guardrail.
    proposed = build_frozen_payload()

    FROZEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    FROZEN_PATH.write_text(
        json.dumps(proposed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote immutable {FROZEN_PATH.relative_to(REPO_ROOT)}")
    return proposed


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
    out: dict[str, dict[str, float | None]] = {
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
            out[player]["total_points"] = float(out[player]["total_points"] or 0.0) + float(
                row.get("points") or 0.0
            )
            out[player]["active_games"] = float(out[player]["active_games"] or 0.0) + float(
                row.get("games") or 0.0
            )

    for player in players:
        games = float(out[player]["active_games"] or 0.0)
        points = float(out[player]["total_points"] or 0.0)
        out[player]["active_ppg"] = points / games if games > 0 else None

    return out


def metrics_for(
    model_eval,
    frozen: dict[str, Any],
    realized: dict[str, dict[str, float | None]],
) -> dict[str, Any]:
    out = {}

    for variant in frozen["variant_manifest"]:
        predictions = frozen["variants"][variant]

        names_total = []
        pred_total = []
        actual_total = []

        names_ppg = []
        pred_ppg = []
        actual_ppg = []

        by_position = {}

        for player in sorted(frozen["players"]):
            pred = float(predictions[player]["value"])
            total = float(realized[player]["total_points"] or 0.0)

            names_total.append(player)
            pred_total.append(pred)
            actual_total.append(total)

            ppg = realized[player]["active_ppg"]
            if ppg is not None:
                names_ppg.append(player)
                pred_ppg.append(pred)
                actual_ppg.append(float(ppg))

        overall_total = model_eval.metric_bundle(
            names_total,
            pred_total,
            actual_total,
            include_top_n=False,
        )
        overall_ppg = model_eval.metric_bundle(
            names_ppg,
            pred_ppg,
            actual_ppg,
            include_top_n=False,
        )

        for pos in TRACKED_POSITIONS:
            pos_players = [
                p for p, info in frozen["players"].items()
                if info["pos"] == pos
            ]

            p_names_total = []
            p_pred_total = []
            p_actual_total = []
            p_names_ppg = []
            p_pred_ppg = []
            p_actual_ppg = []

            for player in sorted(pos_players):
                pred = float(predictions[player]["value"])
                total = float(realized[player]["total_points"] or 0.0)

                p_names_total.append(player)
                p_pred_total.append(pred)
                p_actual_total.append(total)

                ppg = realized[player]["active_ppg"]
                if ppg is not None:
                    p_names_ppg.append(player)
                    p_pred_ppg.append(pred)
                    p_actual_ppg.append(float(ppg))

            by_position[pos] = {
                "value_vs_total_points": model_eval.metric_bundle(
                    p_names_total,
                    p_pred_total,
                    p_actual_total,
                    include_top_n=False,
                ),
                "value_vs_active_ppg": model_eval.metric_bundle(
                    p_names_ppg,
                    p_pred_ppg,
                    p_actual_ppg,
                    include_top_n=False,
                ),
            }

        out[variant] = {
            "overall": {
                "value_vs_total_points": overall_total,
                "value_vs_active_ppg": overall_ppg,
            },
            "by_position": by_position,
        }

    return out


def delta(a: Any, b: Any) -> float | None:
    if a is None or b is None:
        return None
    return round(float(a) - float(b), 6)


def deltas_vs_control(metrics: dict[str, Any]) -> dict[str, Any]:
    control = metrics[CONTROL]
    out = {}

    for variant, row in metrics.items():
        if variant == CONTROL:
            continue

        result = {}
        for target in ("value_vs_total_points", "value_vs_active_ppg"):
            cur = row["overall"][target]
            base = control["overall"][target]
            result[target] = {
                "spearman_delta": delta(cur.get("spearman"), base.get("spearman")),
                "pearson_delta": delta(cur.get("pearson"), base.get("pearson")),
                "pairwise_delta": delta(
                    cur.get("pairwise_ordering_accuracy"),
                    base.get("pairwise_ordering_accuracy"),
                ),
                "minmax_mae_delta": delta(
                    cur.get("minmax_normalized_mae"),
                    base.get("minmax_normalized_mae"),
                ),
            }

        pos_spearman_deltas = []
        for pos in TRACKED_POSITIONS:
            cur = row["by_position"][pos]["value_vs_total_points"].get("spearman")
            base = control["by_position"][pos]["value_vs_total_points"].get("spearman")
            d = delta(cur, base)
            if d is not None:
                pos_spearman_deltas.append(d)

        result["position_total_points_spearman"] = {
            "mean_delta": (
                statistics.fmean(pos_spearman_deltas)
                if pos_spearman_deltas else None
            ),
            "min_delta": min(pos_spearman_deltas) if pos_spearman_deltas else None,
            "max_delta": max(pos_spearman_deltas) if pos_spearman_deltas else None,
        }
        out[variant] = result

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

    players = sorted(frozen["players"])
    realized = aggregate_realized(players, usable, week_maps)
    metrics = metrics_for(model_eval, frozen, realized)

    active_count = sum(
        1 for row in realized.values()
        if float(row.get("active_games") or 0.0) > 0
    )

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": readiness(len(usable)),
        "research_only": True,
        "deployment_authorized": False,
        "age_curve_change_authorized": False,
        "production_files_mutated": 0,
        "frozen_prediction_sha256": frozen["frozen_prediction_sha256"],
        "frozen_at_utc": frozen["frozen_at_utc"],
        "first_eligible_week": first_week,
        "completed_outcome_weeks": completed,
        "completed_consecutive_weeks_used": usable,
        "completed_consecutive_week_count": len(usable),
        "eligible_real_history_player_count": len(players),
        "players_with_active_game_in_window": active_count,
        "metrics": metrics,
        "deltas_vs_deployed_control": deltas_vs_control(metrics),
        "realized_player_outcomes": realized,
        "interpretation_guardrail": (
            "Do not select or deploy an age bridge before calibration-review "
            "readiness. Weeks 1-3 are collection only and Weeks 4-7 are early "
            "diagnostics only. Promotion requires stable overall and by-position "
            "improvement versus the frozen deployed control."
        ),
    }


def fmt(v: Any, d: int = 4) -> str:
    if v is None:
        return "—"
    return f"{float(v):.{d}f}"


def signed(v: Any, d: int = 4) -> str:
    if v is None:
        return "—"
    return f"{float(v):+.{d}f}"


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Age Curve V2 — Phase 5 Prospective Evaluator",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. Production deployment is not authorized.**",
        "",
        f"- Frozen candidate SHA256: `{result['frozen_prediction_sha256']}`",
        f"- Frozen at: **{result['frozen_at_utc']}**",
        f"- First eligible future week: **{result['first_eligible_week']}**",
        f"- Completed consecutive weeks used: "
        f"**{result['completed_consecutive_weeks_used'] or 'none'}**",
        f"- Eligible real-history cohort: "
        f"**{result['eligible_real_history_player_count']}**",
        f"- Players with active game in current window: "
        f"**{result['players_with_active_game_in_window']}**",
        "",
        "## Prospective metrics",
        "",
        "Primary target: **Frozen Fundamental Value vs cumulative future fantasy points**.",
        "",
        "| Variant | Total Spearman | Total pairwise | Active-PPG Spearman | "
        "Δ total Spearman vs control | Mean pos Δ total Spearman |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for variant in SELECTED_VARIANTS:
        row = result["metrics"][variant]
        total = row["overall"]["value_vs_total_points"]
        ppg = row["overall"]["value_vs_active_ppg"]

        if variant == CONTROL:
            d_total = None
            d_pos = None
        else:
            delta_row = result["deltas_vs_deployed_control"][variant]
            d_total = delta_row["value_vs_total_points"]["spearman_delta"]
            d_pos = delta_row["position_total_points_spearman"]["mean_delta"]

        lines.append(
            f"| `{variant}` | {fmt(total.get('spearman'))} | "
            f"{fmt(total.get('pairwise_ordering_accuracy'))} | "
            f"{fmt(ppg.get('spearman'))} | {signed(d_total)} | {signed(d_pos)} |"
        )

    lines.extend(
        [
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
        ]
    )

    return "\n".join(lines)


def write_evaluation(result: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(render_markdown(result), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


def check_outputs() -> None:
    frozen = read_json(FROZEN_PATH)
    result = read_json(OUTPUT_JSON)

    if frozen.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Frozen Phase-5 method mismatch")
    if result.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Evaluation Phase-5 method mismatch")

    for payload in (frozen, result):
        if payload.get("deployment_authorized") is not False:
            raise RuntimeError("Phase 5 unexpectedly authorizes deployment")
        if payload.get("age_curve_change_authorized") is not False:
            raise RuntimeError("Phase 5 unexpectedly authorizes AGE_CURVE change")

    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Phase-5 production mutation guardrail failed")

    if frozen.get("variant_manifest") != list(SELECTED_VARIANTS):
        raise RuntimeError("Frozen Phase-5 candidate family changed")

    if int(frozen.get("cohort_size") or 0) < 400:
        raise RuntimeError("Frozen Phase-5 cohort unexpectedly small")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Phase-5 markdown missing")
    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Prospective metrics",
        "Readiness ladder",
        "Eligible real-history cohort",
    ):
        if marker not in text:
            raise RuntimeError(f"Phase-5 report missing marker: {marker}")

    print("Age Curve V2 Phase-5 outputs passed guardrails.")


def run_selftest() -> None:
    assert consecutive_prefix([], 1) == []
    assert consecutive_prefix([1, 2, 3], 1) == [1, 2, 3]
    assert consecutive_prefix([1, 3], 1) == [1]
    assert readiness(0) == "READY_WAITING_FOR_COMPLETED_WEEK_1"
    assert readiness(3) == "COLLECTION_ONLY"
    assert readiness(8) == "CALIBRATION_REVIEW_ELIGIBLE"
    assert readiness(18) == "SEASON_COMPLETE_REVIEW"

    synthetic_maps = {
        1: {
            "a": {"points": 10.0, "games": 1.0},
            "b": {"points": 5.0, "games": 1.0},
        },
        2: {
            "a": {"points": 20.0, "games": 1.0},
        },
    }
    agg = aggregate_realized(["a", "b"], [1, 2], synthetic_maps)
    assert agg["a"]["total_points"] == 30.0
    assert agg["a"]["active_ppg"] == 15.0
    assert agg["b"]["total_points"] == 5.0

    print(
        "Age Curve V2 Phase-5 self-test passed: completed-week prefix, readiness, "
        "and realized-outcome aggregation."
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
        write_evaluation(result)
    else:
        print(render_markdown(result))


if __name__ == "__main__":
    main()

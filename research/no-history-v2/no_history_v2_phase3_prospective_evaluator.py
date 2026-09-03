#!/usr/bin/env python3
"""
No-History / Rookie Value V2 — Phase 3 prospective 2026 evaluator.

INSTALL/FREEZE BEFORE WEEK 1. GRADE LATER.

Research only. This evaluator never mutates index.html, Production V2,
Market Value, or deployed player values.

Inputs
------
Phase 2 historical prospect-prior candidate family:
    research/no-history-v2/no_history_v2_phase2_prospect_prior.json

Realized league-scored outcomes:
    research/model-history/outcomes/2026.json

The realized outcome file is produced by capture_realized_outcomes.py and uses
the project's exact ppg_pipeline.score_week() league scorer.

Frozen candidate family
-----------------------
On the first --freeze run, this script freezes the Phase-2 2026 eligible cohort
and all formal prospect-prior weights:
    0.00 / 0.15 / 0.30 / 0.45

The frozen file is immutable. Later runs grade that same preseason prediction
state and never rebuild it from current index.html or current Production V2.

Primary target
--------------
Prospect-prior Fundamental Value vs cumulative future league fantasy points.

This aligns with Phase 2's historical prospect-success target: performance plus
earning/retaining opportunity.

Secondary targets
-----------------
- Fundamental Value vs future active-game PPG
- raw production multiplier vs future active-game PPG

Leakage controls
----------------
Reuses scripts/validation/evaluate_model_history.py for:
- outcome integrity validation
- season-start parsing
- completed-week determination
- week outcome maps
- metric_bundle()

No partial week is graded.

Readiness
---------
0 weeks: ready / waiting
1-3: collection only
4-7: early diagnostic only
8-11: calibration review eligible
12-17: stability review eligible
18: season-complete review

No result authorizes production deployment automatically.

Outputs
-------
Immutable once created:
    research/no-history-v2/no_history_v2_phase3_frozen_candidates.json

Refreshable:
    research/no-history-v2/no_history_v2_phase3_evaluation.json
    research/no-history-v2/no_history_v2_phase3_evaluation.md

Usage
-----
python3 research/no-history-v2/no_history_v2_phase3_prospective_evaluator.py --selftest
python3 research/no-history-v2/no_history_v2_phase3_prospective_evaluator.py --freeze --write
python3 research/no-history-v2/no_history_v2_phase3_prospective_evaluator.py --write
python3 research/no-history-v2/no_history_v2_phase3_prospective_evaluator.py --check
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

PHASE2_PATH = (
    REPO_ROOT
    / "research"
    / "no-history-v2"
    / "no_history_v2_phase2_prospect_prior.json"
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
    / "no-history-v2"
    / "no_history_v2_phase3_frozen_candidates.json"
)
OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "no-history-v2"
    / "no_history_v2_phase3_evaluation.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "no-history-v2"
    / "no_history_v2_phase3_evaluation.md"
)

METHOD_VERSION = "no-history-rookie-v2-phase3-prospective-v1"
SEASON = "2026"
VARIANT_WEIGHTS = (0.00, 0.15, 0.30, 0.45)
CONTROL_KEY = "prospect_prior_weight_0.00"
REGULAR_SEASON_LAST_WEEK = 18
MIN_CORRELATION_N = 3


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON: {path.relative_to(REPO_ROOT)}: {exc}"
        ) from exc


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def variant_key(weight: float) -> str:
    return f"prospect_prior_weight_{weight:.2f}"


def load_model_evaluator():
    if str(VALIDATION_DIR) not in sys.path:
        sys.path.insert(0, str(VALIDATION_DIR))
    import evaluate_model_history  # type: ignore
    return evaluate_model_history


def frozen_candidate_payload(phase2: dict[str, Any]) -> dict[str, Any]:
    if phase2.get("method_version") != (
        "no-history-rookie-v2-phase2-prospect-prior-v1"
    ):
        raise RuntimeError("Unexpected Phase-2 prospect-prior method version")
    if phase2.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 2 unexpectedly authorizes deployment")
    if phase2.get("production_files_mutated") != 0:
        raise RuntimeError("Phase 2 lost research-only mutation guardrail")

    current_rows = phase2.get("current_2026_players")
    if not isinstance(current_rows, list) or len(current_rows) < 80:
        raise RuntimeError("Phase-2 2026 cohort is missing or sparse")

    manifest = []
    players = {}

    for row in current_rows:
        if not isinstance(row, dict):
            continue
        player = str(row.get("player") or "").strip()
        if not player:
            continue
        players[player] = {
            "pos": row.get("pos"),
            "age": row.get("age"),
            "role": row.get("role"),
            "experience_class": row.get("experience_class"),
            "draft_year": row.get("draft_year"),
            "draft_pick": row.get("draft_pick"),
            "production_v2_candidate_present": bool(
                row.get("production_v2_candidate_present")
            ),
            "prior_available": bool(row.get("prior_available")),
        }

    expected_keys = {variant_key(w) for w in VARIANT_WEIGHTS}
    variants = phase2.get("blend_variants") or {}
    if set(variants) != expected_keys:
        raise RuntimeError(
            f"Unexpected Phase-2 variant manifest: {sorted(variants)}"
        )

    frozen_variants = {}
    for weight in VARIANT_WEIGHTS:
        key = variant_key(weight)
        source = variants[key]
        source_players = source.get("players") or {}

        predictions = {}
        for player in sorted(players):
            row = source_players.get(player)
            if not isinstance(row, dict):
                raise RuntimeError(f"{key}: missing frozen player {player}")
            value = row.get("value")
            if value is None:
                raise RuntimeError(f"{key}: player {player} missing value")
            raw_pm = row.get("raw_prod_mult")
            predictions[player] = {
                "value": int(value),
                "raw_prod_mult": (
                    float(raw_pm) if raw_pm is not None else None
                ),
                "source": row.get("source"),
                "prior_applied": bool(row.get("prior_applied")),
            }

        frozen_variants[key] = {
            "prior_weight": weight,
            "predictions": predictions,
        }
        manifest.append(
            {
                "variant": key,
                "prior_weight": weight,
            }
        )

    frozen_at = str(phase2.get("generated_at_utc") or "").strip()
    if not frozen_at:
        raise RuntimeError("Phase 2 missing generated_at_utc")

    payload = {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "FROZEN_PRESEASON_PROSPECT_PRIOR_CANDIDATES",
        "research_only": True,
        "deployment_authorized": False,
        "frozen_at_utc": frozen_at,
        "source_phase2_method_version": phase2.get("method_version"),
        "source_phase2_generated_at_utc": phase2.get("generated_at_utc"),
        "cohort_size": len(players),
        "players": players,
        "variant_manifest": manifest,
        "variants": frozen_variants,
        "protocol": {
            "season": SEASON,
            "control_variant": CONTROL_KEY,
            "primary_target": "fundamental_value_vs_future_total_points",
            "secondary_targets": [
                "fundamental_value_vs_future_active_ppg",
                "raw_prod_mult_vs_future_active_ppg",
            ],
            "formal_prior_weights": list(VARIANT_WEIGHTS),
            "missing_v2_policy": (
                "Phase-7 continuity remains frozen exactly as emitted by Phase 2."
            ),
            "completed_week_rule": (
                "Reuse scripts/validation/evaluate_model_history.py "
                "completed_outcome_weeks()."
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
    phase2 = read_json(PHASE2_PATH)
    proposed = frozen_candidate_payload(phase2)

    if FROZEN_PATH.exists():
        existing = read_json(FROZEN_PATH)
        if existing.get("method_version") != METHOD_VERSION:
            raise RuntimeError("Existing frozen candidate method version mismatch")

        # The preseason file is immutable. Do not replace it just because later
        # Phase-2 inputs or source data changed.
        print(
            "Frozen prospect-prior candidate file already exists; "
            "preserving immutable preseason predictions."
        )
        return existing

    FROZEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    FROZEN_PATH.write_text(
        json.dumps(proposed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote immutable {FROZEN_PATH.relative_to(REPO_ROOT)}")
    return proposed


def consecutive_prefix(
    completed_weeks: list[int],
    first_week: int,
) -> list[int]:
    completed = set(int(w) for w in completed_weeks)
    out = []
    week = int(first_week)
    while week <= REGULAR_SEASON_LAST_WEEK and week in completed:
        out.append(week)
        week += 1
    return out


def aggregate_realized(
    player_keys: list[str],
    weeks: list[int],
    week_maps: dict[int, dict[str, dict[str, float]]],
) -> dict[str, dict[str, float]]:
    out = {
        player: {
            "total_points": 0.0,
            "active_games": 0.0,
        }
        for player in player_keys
    }

    for week in weeks:
        mapping = week_maps.get(week, {})
        for player in player_keys:
            row = mapping.get(player)
            if row is None:
                continue
            out[player]["total_points"] += float(row.get("points") or 0.0)
            out[player]["active_games"] += float(row.get("games") or 0.0)

    for player in player_keys:
        games = out[player]["active_games"]
        out[player]["active_ppg"] = (
            out[player]["total_points"] / games
            if games > 0
            else None
        )
    return out


def metric_bundle_for_target(
    model_eval,
    predictions: dict[str, dict[str, Any]],
    realized: dict[str, dict[str, float]],
    pred_field: str,
    outcome_field: str,
) -> dict[str, Any]:
    names = []
    pred = []
    actual = []

    for player in sorted(predictions):
        p = predictions[player].get(pred_field)
        y = realized[player].get(outcome_field)
        if p is None or y is None:
            continue
        try:
            p = float(p)
            y = float(y)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(p) or not math.isfinite(y):
            continue
        names.append(player)
        pred.append(p)
        actual.append(y)

    return model_eval.metric_bundle(
        names,
        pred,
        actual,
        include_top_n=False,
    )


def variant_metrics(
    model_eval,
    frozen: dict[str, Any],
    realized: dict[str, dict[str, float]],
) -> dict[str, Any]:
    out = {}

    for manifest in frozen["variant_manifest"]:
        key = manifest["variant"]
        predictions = frozen["variants"][key]["predictions"]

        out[key] = {
            "prior_weight": manifest["prior_weight"],
            "fundamental_value_vs_total_points": metric_bundle_for_target(
                model_eval,
                predictions,
                realized,
                "value",
                "total_points",
            ),
            "fundamental_value_vs_active_ppg": metric_bundle_for_target(
                model_eval,
                predictions,
                realized,
                "value",
                "active_ppg",
            ),
            "raw_prod_mult_vs_active_ppg": metric_bundle_for_target(
                model_eval,
                predictions,
                realized,
                "raw_prod_mult",
                "active_ppg",
            ),
        }

    return out


def difference(value: Any, control: Any) -> float | None:
    if value is None or control is None:
        return None
    return round(float(value) - float(control), 6)


def variant_deltas(metrics: dict[str, Any]) -> dict[str, Any]:
    control = metrics[CONTROL_KEY]
    out = {}

    for key, row in metrics.items():
        if key == CONTROL_KEY:
            continue

        targets = {}
        for target in (
            "fundamental_value_vs_total_points",
            "fundamental_value_vs_active_ppg",
            "raw_prod_mult_vs_active_ppg",
        ):
            current = row[target]
            base = control[target]
            targets[target] = {
                "spearman_delta_vs_control": difference(
                    current.get("spearman"),
                    base.get("spearman"),
                ),
                "pearson_delta_vs_control": difference(
                    current.get("pearson"),
                    base.get("pearson"),
                ),
                "pairwise_accuracy_delta_vs_control": difference(
                    current.get("pairwise_ordering_accuracy"),
                    base.get("pairwise_ordering_accuracy"),
                ),
                "minmax_mae_delta_vs_control": difference(
                    current.get("minmax_normalized_mae"),
                    base.get("minmax_normalized_mae"),
                ),
            }

        out[key] = {
            "prior_weight": row["prior_weight"],
            "targets": targets,
        }

    return out


def readiness(completed_count: int) -> str:
    if completed_count <= 0:
        return "READY_WAITING_FOR_COMPLETED_WEEK_1"
    if completed_count <= 3:
        return "COLLECTION_ONLY"
    if completed_count <= 7:
        return "EARLY_DIAGNOSTIC_ONLY"
    if completed_count <= 11:
        return "CALIBRATION_REVIEW_ELIGIBLE"
    if completed_count <= 17:
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
    usable_weeks = consecutive_prefix(completed, first_week)
    week_maps = model_eval.build_week_maps(outcomes)

    player_keys = sorted(frozen["players"])
    realized = aggregate_realized(
        player_keys,
        usable_weeks,
        week_maps,
    )
    metrics = variant_metrics(model_eval, frozen, realized)

    active_players = sum(
        1
        for row in realized.values()
        if float(row.get("active_games") or 0.0) > 0
    )

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": readiness(len(usable_weeks)),
        "research_only": True,
        "deployment_authorized": False,
        "production_files_mutated": 0,
        "market_value_mutated": False,
        "production_v2_mutated": False,
        "frozen_candidate_sha256": frozen["frozen_prediction_sha256"],
        "frozen_at_utc": frozen["frozen_at_utc"],
        "first_eligible_week": first_week,
        "completed_outcome_weeks": completed,
        "completed_consecutive_weeks_used": usable_weeks,
        "completed_consecutive_week_count": len(usable_weeks),
        "eligible_player_count": len(player_keys),
        "players_with_active_game_in_window": active_players,
        "outcome_refreshed_at_utc": outcomes.get("refreshed_at_utc"),
        "metrics": metrics,
        "deltas_vs_zero_prior_control": variant_deltas(metrics),
        "realized_player_outcomes": realized,
        "interpretation_guardrail": (
            "Do not select a prospect-prior weight before calibration-review "
            "readiness. Weeks 1-3 are collection only; Weeks 4-7 are early "
            "diagnostics only. Any eventual promotion requires stable advantage "
            "versus the frozen 0% prior control and position-level sanity review."
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
    weeks = result["completed_consecutive_weeks_used"]
    metrics = result["metrics"]
    deltas = result["deltas_vs_zero_prior_control"]

    lines = [
        "# No-History / Rookie Value V2 — Phase 3 Prospective Evaluator",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. Production deployment is not authorized.**",
        "",
        f"- Frozen candidate SHA256: `{result['frozen_candidate_sha256']}`",
        f"- Frozen at: **{result['frozen_at_utc']}**",
        f"- First eligible future week: **{result['first_eligible_week']}**",
        f"- Completed consecutive weeks used: "
        f"**{weeks if weeks else 'none'}**",
        f"- Eligible preseason cohort: **{result['eligible_player_count']}**",
        f"- Players with an active game in current window: "
        f"**{result['players_with_active_game_in_window']}**",
        "",
        "## Prospective metrics",
        "",
        "Primary target: **Fundamental Value vs cumulative future fantasy points**.",
        "",
        "| Prior weight | Total-points Spearman | Active-PPG FV Spearman | "
        "Active-PPG PM Spearman | Total-points pairwise |",
        "|---:|---:|---:|---:|---:|",
    ]

    for weight in VARIANT_WEIGHTS:
        key = variant_key(weight)
        row = metrics[key]
        lines.append(
            f"| {weight:.2f} | "
            f"{fmt(row['fundamental_value_vs_total_points']['spearman'])} | "
            f"{fmt(row['fundamental_value_vs_active_ppg']['spearman'])} | "
            f"{fmt(row['raw_prod_mult_vs_active_ppg']['spearman'])} | "
            f"{fmt(row['fundamental_value_vs_total_points']['pairwise_ordering_accuracy'])} |"
        )

    lines.extend(
        [
            "",
            "## Difference vs frozen 0% prospect-prior control",
            "",
            "| Prior weight | Δ total-points Spearman | Δ active-PPG FV Spearman | "
            "Δ active-PPG PM Spearman | Δ total-points pairwise |",
            "|---:|---:|---:|---:|---:|",
        ]
    )

    for weight in VARIANT_WEIGHTS:
        if weight == 0.0:
            continue
        key = variant_key(weight)
        row = deltas[key]["targets"]
        total = row["fundamental_value_vs_total_points"]
        fv_ppg = row["fundamental_value_vs_active_ppg"]
        pm_ppg = row["raw_prod_mult_vs_active_ppg"]
        lines.append(
            f"| {weight:.2f} | "
            f"{signed(total['spearman_delta_vs_control'])} | "
            f"{signed(fv_ppg['spearman_delta_vs_control'])} | "
            f"{signed(pm_ppg['spearman_delta_vs_control'])} | "
            f"{signed(total['pairwise_accuracy_delta_vs_control'])} |"
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
            "A higher prospect-prior weight should only advance if it improves the "
            "primary future-total-points ranking versus the frozen 0% control "
            "without creating material degradation in active-PPG ranking or "
            "position-level behavior. Current KTC or current Fundamental Value "
            "agreement is not a selection target.",
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
        raise RuntimeError("Frozen candidate method version mismatch")
    if frozen.get("deployment_authorized") is not False:
        raise RuntimeError("Frozen candidates unexpectedly authorize deployment")
    if result.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Evaluation method version mismatch")
    if result.get("deployment_authorized") is not False:
        raise RuntimeError("Evaluation unexpectedly authorizes deployment")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Evaluation lost production mutation guardrail")
    if result.get("market_value_mutated") is not False:
        raise RuntimeError("Evaluation unexpectedly mutates Market Value")
    if result.get("production_v2_mutated") is not False:
        raise RuntimeError("Evaluation unexpectedly mutates Production V2")

    if int(result.get("eligible_player_count") or 0) < 80:
        raise RuntimeError("Frozen prospect cohort is implausibly small")

    metric_keys = set((result.get("metrics") or {}).keys())
    expected = {variant_key(w) for w in VARIANT_WEIGHTS}
    if metric_keys != expected:
        raise RuntimeError("Prospective variant manifest changed unexpectedly")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Prospective markdown report missing")

    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Prospective metrics",
        "Difference vs frozen 0% prospect-prior control",
        "Readiness ladder",
    ):
        if marker not in text:
            raise RuntimeError(f"Prospective markdown missing marker: {marker}")

    print("No-History / Rookie V2 Phase-3 outputs passed guardrails.")


def run_selftest() -> None:
    assert consecutive_prefix([], 1) == []
    assert consecutive_prefix([1, 2, 3], 1) == [1, 2, 3]
    assert consecutive_prefix([1, 3], 1) == [1]
    assert consecutive_prefix([2, 3], 1) == []
    assert readiness(0) == "READY_WAITING_FOR_COMPLETED_WEEK_1"
    assert readiness(3) == "COLLECTION_ONLY"
    assert readiness(4) == "EARLY_DIAGNOSTIC_ONLY"
    assert readiness(8) == "CALIBRATION_REVIEW_ELIGIBLE"
    assert readiness(12) == "STABILITY_REVIEW_ELIGIBLE"
    assert readiness(18) == "SEASON_COMPLETE_REVIEW"

    synthetic_week_maps = {
        1: {
            "a": {"points": 10.0, "games": 1.0},
            "b": {"points": 5.0, "games": 1.0},
        },
        2: {
            "a": {"points": 20.0, "games": 1.0},
        },
    }
    agg = aggregate_realized(["a", "b", "c"], [1, 2], synthetic_week_maps)
    assert agg["a"]["total_points"] == 30.0
    assert agg["a"]["active_games"] == 2.0
    assert agg["a"]["active_ppg"] == 15.0
    assert agg["b"]["total_points"] == 5.0
    assert agg["b"]["active_ppg"] == 5.0
    assert agg["c"]["total_points"] == 0.0
    assert agg["c"]["active_ppg"] is None

    print(
        "No-History / Rookie V2 Phase-3 self-test passed: completed-week prefix, "
        "readiness ladder, and realized-outcome aggregation."
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

    if args.freeze:
        frozen = freeze_if_needed()
    else:
        frozen = read_json(FROZEN_PATH)

    result = build_evaluation(frozen)

    if args.write:
        write_evaluation(result)
    else:
        print(render_markdown(result))


if __name__ == "__main__":
    main()

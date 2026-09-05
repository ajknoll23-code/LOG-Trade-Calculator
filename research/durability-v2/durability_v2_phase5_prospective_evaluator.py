#!/usr/bin/env python3
"""Durability / Availability V2 — Phase 5 prospective evaluator.

Research only. Freeze before Week 1; grade the frozen availability predictions
against completed 2026 outcomes. No deployed model component is changed.

Frozen family:
- deployed_control
- bridge_w100 (Phase-4 monitoring leader)
- bridge_w50  (prespecified conservative comparator)

Primary authoritative target:
    full-season realized games played / 17 scheduled games

Interim runs are collection/diagnostic only because bye weeks make
"games played / completed league weeks" an imperfect availability denominator.
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

PHASE3_JSON = REPO_ROOT / "research" / "durability-v2" / "durability_v2_phase3_shadow_audit.json"
PHASE4_JSON = REPO_ROOT / "research" / "durability-v2" / "durability_v2_phase4_bridge_calibration.json"
OUTCOMES_PATH = REPO_ROOT / "research" / "model-history" / "outcomes" / "2026.json"
FROZEN_PATH = REPO_ROOT / "research" / "durability-v2" / "durability_v2_phase5_frozen_candidates.json"
OUTPUT_JSON = REPO_ROOT / "research" / "durability-v2" / "durability_v2_phase5_evaluation.json"
OUTPUT_MD = REPO_ROOT / "research" / "durability-v2" / "durability_v2_phase5_evaluation.md"

METHOD_VERSION = "durability-v2-phase5-prospective-v1"
PHASE3_METHOD = "durability-v2-phase3-shadow-audit-v1"
PHASE4_METHOD = "durability-v2-phase4-bridge-calibration-v1"
SEASON = "2026"
REGULAR_SEASON_LAST_WEEK = 18
SCHEDULED_GAMES = 17
CONTROL = "deployed_control"
SELECTED_VARIANTS = (CONTROL, "bridge_w100", "bridge_w50")
PHASE3_SOURCE = {
    CONTROL: "deployed_control",
    "bridge_w100": "trained_blend_w100",
    "bridge_w50": "trained_blend_w50",
}
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def load_model_evaluator():
    if str(VALIDATION_DIR) not in sys.path:
        sys.path.insert(0, str(VALIDATION_DIR))
    import evaluate_model_history  # type: ignore
    return evaluate_model_history


def validate_upstream(phase3: dict[str, Any], phase4: dict[str, Any]) -> None:
    if phase3.get("method_version") != PHASE3_METHOD:
        raise RuntimeError("Unexpected Durability Phase-3 method version")
    if phase4.get("method_version") != PHASE4_METHOD:
        raise RuntimeError("Unexpected Durability Phase-4 method version")
    for payload in (phase3, phase4):
        if payload.get("deployment_authorized") is not False:
            raise RuntimeError("Upstream Durability research unexpectedly authorizes deployment")
        if payload.get("durability_change_authorized") is not False:
            raise RuntimeError("Upstream Durability research unexpectedly authorizes durability change")
        if payload.get("history_component_change_authorized") is not False:
            raise RuntimeError("Upstream Durability research unexpectedly authorizes history change")
    if phase4.get("monitoring_leader") != "bridge_w100":
        raise RuntimeError("Phase-4 monitoring leader changed; expected bridge_w100")
    if phase4.get("conservative_comparator") != "bridge_w50":
        raise RuntimeError("Phase-4 conservative comparator changed; expected bridge_w50")
    for variant in SELECTED_VARIANTS[1:]:
        if (phase4.get("historical_screening") or {}).get(variant, {}).get("passes") is not True:
            raise RuntimeError(f"Selected variant failed historical screen: {variant}")
        if (phase4.get("current_screening") or {}).get(variant, {}).get("passes") is not True:
            raise RuntimeError(f"Selected variant failed current screen: {variant}")


def build_frozen_payload() -> dict[str, Any]:
    phase3 = read_json(PHASE3_JSON)
    phase4 = read_json(PHASE4_JSON)
    validate_upstream(phase3, phase4)

    source_players = phase3.get("players")
    if not isinstance(source_players, dict) or len(source_players) < 350:
        raise RuntimeError("Durability Phase-3 current-player cohort missing/sparse")

    players: dict[str, dict[str, Any]] = {}
    variants: dict[str, dict[str, dict[str, Any]]] = {v: {} for v in SELECTED_VARIANTS}

    for player, row in sorted(source_players.items()):
        pos = str(row.get("pos") or "").upper()
        if pos not in TRACKED_POSITIONS:
            continue
        source_variants = row.get("variants") or {}
        if not all(PHASE3_SOURCE[v] in source_variants for v in SELECTED_VARIANTS):
            continue

        players[player] = {
            "pos": pos,
            "role": row.get("role"),
            "games_played_2025": row.get("games_played_2025"),
            "own_availability_2025": row.get("own_availability_2025"),
            "position_median_availability_2025": row.get("position_median_availability_2025"),
            "deployed_own_weight": row.get("deployed_own_weight"),
            "trained_own_weight": row.get("trained_own_weight"),
        }
        for variant in SELECTED_VARIANTS:
            src_name = PHASE3_SOURCE[variant]
            src = source_variants[src_name]
            variants[variant][player] = {
                "predicted_availability_2026": float(src["projected_availability_2026"]),
                "projected_games_2026": float(src["projected_games_2026"]),
                "own_history_weight": float(src["own_weight"]),
                "phase3_source_variant": src_name,
            }

    if len(players) < 350:
        raise RuntimeError(f"Durability Phase-5 freeze cohort unexpectedly small: {len(players)}")
    for variant in SELECTED_VARIANTS:
        if set(variants[variant]) != set(players):
            raise RuntimeError(f"Durability Phase-5 coverage mismatch: {variant}")

    frozen_at = now_utc()
    outcomes = read_json(OUTCOMES_PATH)
    season_start_date = (outcomes.get("sleeper_state_at_refresh") or {}).get("season_start_date")
    if not season_start_date:
        raise RuntimeError("Outcome file missing season_start_date")
    model_eval = load_model_evaluator()
    if model_eval.parse_utc(frozen_at).date() >= model_eval.parse_date(season_start_date):
        raise RuntimeError(
            "Refusing to create Durability Phase-5 frozen candidates on/after "
            f"2026 season start ({season_start_date})."
        )

    payload = {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "FROZEN_PRESEASON_DURABILITY_CANDIDATES",
        "research_only": True,
        "deployment_authorized": False,
        "durability_change_authorized": False,
        "history_component_change_authorized": False,
        "frozen_at_utc": frozen_at,
        "source_phase3_method_version": phase3.get("method_version"),
        "source_phase3_sha256": canonical_sha256(phase3),
        "source_phase4_method_version": phase4.get("method_version"),
        "source_phase4_sha256": canonical_sha256(phase4),
        "cohort_definition": (
            "current tracked real-history QB/RB/WR/TE/DL/LB/DB players in Durability Phase-3 "
            "with deployed, 100%, and 50% projected 2026 availability"
        ),
        "cohort_size": len(players),
        "players": players,
        "variant_manifest": list(SELECTED_VARIANTS),
        "variants": variants,
        "protocol": {
            "season": SEASON,
            "scheduled_games": SCHEDULED_GAMES,
            "control_variant": CONTROL,
            "primary_target": "season_complete_realized_games_played_divided_by_17",
            "primary_metric": "availability_MAE",
            "secondary_metrics": ["RMSE", "Spearman", "Pearson"],
            "interim_metrics_authoritative": False,
            "interim_reason": "bye weeks make games/completed-league-weeks an imperfect denominator",
            "production_v2_frozen_unchanged": True,
            "age_curve_v2_frozen_unchanged": True,
            "opportunity_v2_frozen_unchanged": True,
            "no_history_v2_frozen_unchanged": True,
            "deployment_authorized": False,
        },
    }
    payload["frozen_prediction_sha256"] = canonical_sha256(
        {"players": payload["players"], "variants": payload["variants"], "protocol": payload["protocol"]}
    )
    return payload


def freeze_if_needed() -> dict[str, Any]:
    # Existing immutable freeze is checked FIRST; do not re-run preseason guard in-season.
    if FROZEN_PATH.exists():
        existing = read_json(FROZEN_PATH)
        if existing.get("method_version") != METHOD_VERSION:
            raise RuntimeError("Existing frozen Durability Phase-5 method mismatch")
        if existing.get("variant_manifest") != list(SELECTED_VARIANTS):
            raise RuntimeError("Existing frozen Durability Phase-5 candidate family changed")
        print("Frozen Durability Phase-5 file exists; preserving immutable preseason predictions.")
        return existing

    proposed = build_frozen_payload()
    FROZEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    FROZEN_PATH.write_text(json.dumps(proposed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote immutable {FROZEN_PATH.relative_to(REPO_ROOT)}")
    return proposed


def consecutive_prefix(completed_weeks: list[int], first_week: int) -> list[int]:
    completed = set(int(w) for w in completed_weeks)
    out: list[int] = []
    week = int(first_week)
    while week <= REGULAR_SEASON_LAST_WEEK and week in completed:
        out.append(week)
        week += 1
    return out


def aggregate_games(
    players: list[str],
    weeks: list[int],
    week_maps: dict[int, dict[str, dict[str, float]]],
) -> dict[str, int]:
    out = {player: 0 for player in players}
    for week in weeks:
        mapping = week_maps.get(week, {})
        for player in players:
            row = mapping.get(player)
            if row is not None:
                out[player] += int(round(float(row.get("games") or 0.0)))
    return out


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
    if len(xs) != len(ys) or len(xs) < 5:
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
    if len(xs) < 5:
        return None
    return pearson(rankdata(xs), rankdata(ys))


def metric_bundle(pred: list[float], actual: list[float]) -> dict[str, Any]:
    if len(pred) != len(actual) or not pred:
        return {"n": 0, "mae": None, "rmse": None, "spearman": None, "pearson": None, "bias": None}
    return {
        "n": len(pred),
        "mae": statistics.fmean(abs(a-p) for p, a in zip(pred, actual)),
        "rmse": math.sqrt(statistics.fmean((a-p)**2 for p, a in zip(pred, actual))),
        "spearman": spearman(pred, actual),
        "pearson": pearson(pred, actual),
        "bias": statistics.fmean(p-a for p, a in zip(pred, actual)),
    }


def availability_metrics(
    frozen: dict[str, Any],
    games: dict[str, int],
    denominator: float,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for variant in frozen["variant_manifest"]:
        all_pred: list[float] = []
        all_actual: list[float] = []
        by_position: dict[str, Any] = {}
        for player in sorted(frozen["players"]):
            all_pred.append(float(frozen["variants"][variant][player]["predicted_availability_2026"]))
            all_actual.append(min(1.0, float(games[player]) / denominator))
        for pos in TRACKED_POSITIONS:
            names = [p for p, info in frozen["players"].items() if info["pos"] == pos]
            p_pred = [float(frozen["variants"][variant][p]["predicted_availability_2026"]) for p in names]
            p_actual = [min(1.0, float(games[p]) / denominator) for p in names]
            by_position[pos] = metric_bundle(p_pred, p_actual)
        out[variant] = {"overall": metric_bundle(all_pred, all_actual), "by_position": by_position}
    return out


def deltas_vs_control(metrics: dict[str, Any]) -> dict[str, Any]:
    base = metrics[CONTROL]
    out: dict[str, Any] = {}
    for variant, row in metrics.items():
        if variant == CONTROL:
            continue
        cur = row["overall"]
        b = base["overall"]
        out[variant] = {
            "mae_delta": float(cur["mae"]) - float(b["mae"]),
            "rmse_delta": float(cur["rmse"]) - float(b["rmse"]),
            "spearman_delta": (
                float(cur["spearman"]) - float(b["spearman"])
                if cur["spearman"] is not None and b["spearman"] is not None else None
            ),
            "pearson_delta": (
                float(cur["pearson"]) - float(b["pearson"])
                if cur["pearson"] is not None and b["pearson"] is not None else None
            ),
            "positions_with_lower_mae": sum(
                1 for pos in TRACKED_POSITIONS
                if float(row["by_position"][pos]["mae"]) < float(base["by_position"][pos]["mae"])
            ),
        }
    return out


def status_for(weeks: int) -> str:
    if weeks <= 0:
        return "READY_WAITING_FOR_COMPLETED_WEEK_1"
    if weeks < REGULAR_SEASON_LAST_WEEK:
        return "COLLECTION_ONLY_INTERIM_BYE_UNADJUSTED"
    return "SEASON_COMPLETE_REVIEW"


def build_evaluation(frozen: dict[str, Any]) -> dict[str, Any]:
    model_eval = load_model_evaluator()
    outcomes = read_json(OUTCOMES_PATH)
    model_eval.validate_outcomes(outcomes)
    season_start_date = (outcomes.get("sleeper_state_at_refresh") or {}).get("season_start_date")
    if not season_start_date:
        raise RuntimeError("Outcome file missing season_start_date")

    first_week = model_eval.first_eligible_future_week(frozen["frozen_at_utc"], season_start_date)
    completed = model_eval.completed_outcome_weeks(outcomes)
    usable = consecutive_prefix(completed, first_week)
    week_maps = model_eval.build_week_maps(outcomes)
    players = sorted(frozen["players"])
    games = aggregate_games(players, usable, week_maps)

    interim_metrics = None
    interim_deltas = None
    if usable:
        interim_metrics = availability_metrics(frozen, games, float(len(usable)))
        interim_deltas = deltas_vs_control(interim_metrics)

    season_complete = len(usable) == REGULAR_SEASON_LAST_WEEK and usable == list(range(1, 19))
    final_metrics = None
    final_deltas = None
    if season_complete:
        final_metrics = availability_metrics(frozen, games, float(SCHEDULED_GAMES))
        final_deltas = deltas_vs_control(final_metrics)

    realized = {
        p: {
            "games_played_in_completed_window": games[p],
            "interim_bye_unadjusted_participation_rate": min(1.0, games[p] / len(usable)) if usable else None,
            "season_complete_availability": min(1.0, games[p] / SCHEDULED_GAMES) if season_complete else None,
        }
        for p in players
    }

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": status_for(len(usable)),
        "research_only": True,
        "deployment_authorized": False,
        "durability_change_authorized": False,
        "history_component_change_authorized": False,
        "production_files_mutated": 0,
        "frozen_prediction_sha256": frozen["frozen_prediction_sha256"],
        "frozen_at_utc": frozen["frozen_at_utc"],
        "first_eligible_week": first_week,
        "completed_outcome_weeks": completed,
        "completed_consecutive_weeks_used": usable,
        "completed_consecutive_week_count": len(usable),
        "eligible_durability_player_count": len(players),
        "season_complete_authoritative_target_available": season_complete,
        "interim_metrics_bye_unadjusted_non_authoritative": interim_metrics,
        "interim_deltas_vs_control_non_authoritative": interim_deltas,
        "season_complete_authoritative_metrics": final_metrics,
        "season_complete_deltas_vs_control": final_deltas,
        "realized_player_availability": realized,
        "interpretation_guardrail": (
            "Do not promote or reject a Durability V2 candidate from interim bye-unadjusted metrics. "
            "The authoritative prospective target is full-season games played / 17 after all 18 "
            "regular-season weeks are safely complete."
        ),
    }


def fmt(v: Any, d: int = 4) -> str:
    return "—" if v is None else f"{float(v):.{d}f}"


def signed(v: Any, d: int = 4) -> str:
    return "—" if v is None else f"{float(v):+.{d}f}"


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Durability / Availability V2 — Phase 5 Prospective Evaluator",
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
        f"- Completed consecutive weeks used: **{result['completed_consecutive_weeks_used'] or 'none'}**",
        f"- Eligible durability cohort: **{result['eligible_durability_player_count']}**",
        "",
        "## Primary prospective target",
        "",
        "**Full-season realized games played / 17 scheduled games.**",
        "",
        "This becomes authoritative only after all 18 regular-season weeks are safely complete.",
        "Interim participation diagnostics are bye-unadjusted and cannot authorize promotion.",
        "",
    ]

    final_metrics = result["season_complete_authoritative_metrics"]
    if final_metrics is None:
        lines += ["## Current state", "", "Authoritative full-season durability metrics are **not available yet**.", ""]
        interim = result["interim_metrics_bye_unadjusted_non_authoritative"]
        deltas = result["interim_deltas_vs_control_non_authoritative"]
        if interim is not None:
            lines += [
                "### Interim bye-unadjusted diagnostic — non-authoritative",
                "",
                "| Variant | MAE | RMSE | Spearman | Δ MAE vs control | Δ Spearman | Pos lower MAE |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
            for variant in SELECTED_VARIANTS:
                row = interim[variant]["overall"]
                if variant == CONTROL:
                    d_mae = d_sp = None
                    pos = "—"
                else:
                    d = deltas[variant]
                    d_mae = d["mae_delta"]
                    d_sp = d["spearman_delta"]
                    pos = f"{d['positions_with_lower_mae']}/7"
                lines.append(
                    f"| `{variant}` | {fmt(row['mae'])} | {fmt(row['rmse'])} | {fmt(row['spearman'])} | "
                    f"{signed(d_mae)} | {signed(d_sp)} | {pos} |"
                )
            lines.append("")
    else:
        deltas = result["season_complete_deltas_vs_control"]
        lines += [
            "## Season-complete authoritative results",
            "",
            "| Variant | MAE | RMSE | Spearman | Pearson | Δ MAE vs control | Δ Spearman | Pos lower MAE |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for variant in SELECTED_VARIANTS:
            row = final_metrics[variant]["overall"]
            if variant == CONTROL:
                d_mae = d_sp = None
                pos = "—"
            else:
                d = deltas[variant]
                d_mae = d["mae_delta"]
                d_sp = d["spearman_delta"]
                pos = f"{d['positions_with_lower_mae']}/7"
            lines.append(
                f"| `{variant}` | {fmt(row['mae'])} | {fmt(row['rmse'])} | {fmt(row['spearman'])} | "
                f"{fmt(row['pearson'])} | {signed(d_mae)} | {signed(d_sp)} | {pos} |"
            )
        lines.append("")

    lines += ["## Interpretation", "", result["interpretation_guardrail"], ""]
    return "\n".join(lines)


def write_evaluation(result: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(result), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


def check_outputs() -> None:
    frozen = read_json(FROZEN_PATH)
    result = read_json(OUTPUT_JSON)
    if frozen.get("method_version") != METHOD_VERSION or result.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Durability Phase-5 method mismatch")
    for payload in (frozen, result):
        if payload.get("deployment_authorized") is not False:
            raise RuntimeError("Durability Phase 5 unexpectedly authorizes deployment")
        if payload.get("durability_change_authorized") is not False:
            raise RuntimeError("Durability Phase 5 unexpectedly authorizes durability change")
        if payload.get("history_component_change_authorized") is not False:
            raise RuntimeError("Durability Phase 5 unexpectedly authorizes history change")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Durability Phase-5 mutation guardrail failed")
    if frozen.get("variant_manifest") != list(SELECTED_VARIANTS):
        raise RuntimeError("Frozen Durability Phase-5 family changed")
    if int(frozen.get("cohort_size") or 0) < 350:
        raise RuntimeError("Frozen Durability Phase-5 cohort too small")
    if result.get("frozen_prediction_sha256") != frozen.get("frozen_prediction_sha256"):
        raise RuntimeError("Durability Phase-5 freeze/evaluation SHA mismatch")
    if not OUTPUT_MD.exists():
        raise RuntimeError("Durability Phase-5 markdown missing")
    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in ("Research only", "Primary prospective target", "Eligible durability cohort", "Interpretation"):
        if marker not in text:
            raise RuntimeError(f"Durability Phase-5 report missing marker: {marker}")
    print("Durability / Availability V2 Phase-5 outputs passed guardrails.")


def run_selftest() -> None:
    assert consecutive_prefix([], 1) == []
    assert consecutive_prefix([1, 2, 3], 1) == [1, 2, 3]
    assert consecutive_prefix([1, 3], 1) == [1]
    assert status_for(0) == "READY_WAITING_FOR_COMPLETED_WEEK_1"
    assert status_for(5) == "COLLECTION_ONLY_INTERIM_BYE_UNADJUSTED"
    assert status_for(18) == "SEASON_COMPLETE_REVIEW"
    week_maps = {1: {"a": {"games": 1.0}, "b": {"games": 0.0}}, 2: {"a": {"games": 1.0}, "b": {"games": 1.0}}}
    agg = aggregate_games(["a", "b"], [1, 2], week_maps)
    assert agg == {"a": 2, "b": 1}
    m = metric_bundle([0.2, 0.4, 0.6, 0.8, 1.0], [0.2, 0.4, 0.6, 0.8, 1.0])
    assert m["mae"] == 0.0
    assert abs(float(m["spearman"]) - 1.0) < 1e-12
    print(
        "Durability / Availability V2 Phase-5 self-test passed: immutable-freeze helpers, "
        "completed-week semantics, availability aggregation, and metrics."
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

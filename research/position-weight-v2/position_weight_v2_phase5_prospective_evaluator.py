#!/usr/bin/env python3
"""
Position Weight / Cross-Position Economics V2 — Phase 5 prospective evaluator.

FREEZE BEFORE WEEK 1. GRADE ONLY FUTURE 2026 EVIDENCE.

Research only. No POSITION_WEIGHT deployment is authorized.

Frozen variants
---------------
- deployed_control
- bridge_50

The Phase-4 bridge_75 and bridge_100 variants failed current-board safety and
are intentionally excluded.

Primary prospective target
--------------------------
For each completed 2026 week:
1. Use the exact league scoring captured in research/model-history/outcomes/2026.json.
2. Under the real 2026 roster slot structure frozen by Position Weight V2
   Phase 2, allocate league-wide structural starters to maximize realized points.
3. An active player receives his realized fantasy points as lineup utility if
   structurally started, otherwise 0.
4. Aggregate each player's utility per active game across completed weeks.

Primary metric
--------------
Cross-position pairwise ordering accuracy.

Only pairs from DIFFERENT positions are scored. This is a particularly clean
POSITION_WEIGHT metric:
- a common global multiplicative scale cancels completely;
- same-position ordering is intentionally excluded;
- production/age/replacement logic is frozen before the season;
- the only difference between arms is the position multiplier.

Secondary metric
----------------
Global min-max normalized MAE/RMSE between frozen prediction score and realized
active-game lineup utility. This is also invariant to any positive common global
scale.

Prediction score
----------------
effective_prod_mult * position_weight

Age is intentionally excluded from the prospective score because the historical
Position Weight V2 calibration target isolated current-season lineup economics.
Age Curve V2 is a separate frozen prospective experiment.

Cohort isolation
----------------
The full frozen PLAYER_DB universe is used to derive the weekly structural
starter allocation. The primary scoring cohort excludes
NO_REAL_PRODUCTION_HISTORY players so this study does not re-test the separately
frozen No-History/Rookie V2 experiment.

Immutable once created
----------------------
research/position-weight-v2/position_weight_v2_phase5_frozen_candidates.json

Refreshable
-----------
research/position-weight-v2/position_weight_v2_phase5_evaluation.json
research/position-weight-v2/position_weight_v2_phase5_evaluation.md
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
SCRIPTS = REPO_ROOT / "scripts"
VALIDATION_DIR = SCRIPTS / "validation"

INDEX_HTML = REPO_ROOT / "index.html"
PHASE2_JSON = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase2_ruleset_simulation.json"
)
PHASE3_JSON = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase3_historical_calibration.json"
)
PHASE4_JSON = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase4_current_board_shadow.json"
)
OUTCOMES_PATH = (
    REPO_ROOT / "research" / "model-history" / "outcomes" / "2026.json"
)

FROZEN_PATH = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase5_frozen_candidates.json"
)
OUTPUT_JSON = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase5_evaluation.json"
)
OUTPUT_MD = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase5_evaluation.md"
)

METHOD_VERSION = "position-weight-v2-phase5-prospective-v1"
PHASE2_METHOD = "position-weight-v2-phase2-ruleset-simulation-v1"
PHASE3_METHOD = "position-weight-v2-phase3-historical-calibration-v1"
PHASE4_METHOD = "position-weight-v2-phase4-current-board-shadow-v1"

SEASON = "2026"
REGULAR_SEASON_LAST_WEEK = 18
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
OFFENSE = ("QB", "RB", "WR", "TE")
IDP = ("DL", "LB", "DB")
VARIANTS = ("deployed_control", "bridge_50")
CONTROL = "deployed_control"

FLEX_ELIGIBLE = {
    "FLEX": ("RB", "WR", "TE"),
    "SUPER_FLEX": ("QB", "RB", "WR", "TE"),
    "IDP_FLEX": ("DL", "LB", "DB"),
    "REC_FLEX": ("WR", "TE"),
    "WRRB_FLEX": ("WR", "RB"),
}


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def load_model_evaluator():
    if str(VALIDATION_DIR) not in sys.path:
        sys.path.insert(0, str(VALIDATION_DIR))
    import evaluate_model_history  # type: ignore
    return evaluate_model_history


def validate_upstream(phase2, phase3, phase4):
    if phase2.get("method_version") != PHASE2_METHOD:
        raise RuntimeError("unexpected Position Weight V2 Phase-2 method")
    if phase3.get("method_version") != PHASE3_METHOD:
        raise RuntimeError("unexpected Position Weight V2 Phase-3 method")
    if phase4.get("method_version") != PHASE4_METHOD:
        raise RuntimeError("unexpected Position Weight V2 Phase-4 method")

    for name, payload in (
        ("Phase 2", phase2),
        ("Phase 3", phase3),
        ("Phase 4", phase4),
    ):
        for field in (
            "deployment_authorized",
            "position_weight_change_authorized",
            "replacement_rank_change_authorized",
            "production_v2_change_authorized",
            "transform_change_authorized",
            "scale_change_authorized",
        ):
            if payload.get(field) is not False:
                raise RuntimeError(f"{name} guardrail changed: {field}")
        if payload.get("frozen_prospective_experiments_touched") is not False:
            raise RuntimeError(f"{name} says frozen prospective experiments changed")

    selected = (phase3.get("alpha_selection") or {}).get("selected") or {}
    if selected.get("historical_screen_pass") is not True:
        raise RuntimeError("Phase 3 historical screen no longer passes")
    if abs(float(selected.get("alpha")) - 1.0) > 1e-12:
        raise RuntimeError("Phase 3 selected alpha changed")

    rec = phase4.get("phase5_recommendation") or {}
    if rec.get("recommended_shadow_variant") != "bridge_50":
        raise RuntimeError("Phase 4 no longer recommends bridge_50")
    if rec.get("prospective_freeze_authorized") is not True:
        raise RuntimeError("Phase 4 no longer authorizes prospective freeze")
    if (phase4.get("scenarios") or {}).get("bridge_50", {}).get(
        "board_safety_pass"
    ) is not True:
        raise RuntimeError("Phase 4 bridge_50 no longer passes board safety")
    for rejected in ("bridge_75", "bridge_100"):
        if (phase4.get("scenarios") or {}).get(rejected, {}).get(
            "board_safety_pass"
        ) is not False:
            raise RuntimeError(f"Phase 4 rejected arm unexpectedly changed: {rejected}")

    current = phase2.get("current_2026_ruleset_source") or {}
    if str(current.get("season")) != SEASON:
        raise RuntimeError("Phase 2 current ruleset is not 2026")
    if int(current.get("total_rosters") or 0) != 12:
        raise RuntimeError("Phase 2 current ruleset team count changed")


def build_frozen_payload():
    phase2 = read_json(PHASE2_JSON)
    phase3 = read_json(PHASE3_JSON)
    phase4 = read_json(PHASE4_JSON)
    validate_upstream(phase2, phase3, phase4)

    outcomes = read_json(OUTCOMES_PATH)
    evaluator = load_model_evaluator()
    evaluator.validate_outcomes(outcomes)
    state = outcomes.get("sleeper_state_at_refresh") or {}
    season_start_date = state.get("season_start_date")
    if not season_start_date:
        raise RuntimeError("outcomes missing season_start_date")

    frozen_at = now_utc()
    if evaluator.parse_utc(frozen_at).date() >= evaluator.parse_date(season_start_date):
        raise RuntimeError(
            "refusing to create Position Weight V2 Phase-5 freeze on/after "
            f"season start {season_start_date}"
        )

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    deployed = {
        pos: float(phase4["deployed_position_weights"][pos])
        for pos in TRACKED_POSITIONS
    }
    bridge50 = {
        pos: float(
            phase4["scenarios"]["bridge_50"]["position_weights"][pos]
        )
        for pos in TRACKED_POSITIONS
    }
    html_weights = {
        pos: float(cfg["position_weight"][pos])
        for pos in TRACKED_POSITIONS
    }
    if html_weights != deployed:
        raise RuntimeError("live index.html POSITION_WEIGHT changed before freeze")

    players = {}
    for key, info in sorted(cfg["player_db"].items()):
        pos = info["pos"]
        if pos not in TRACKED_POSITIONS:
            continue
        role = info["role"]
        pm, raw_pm = snapshot_values.production_multiplier(
            key,
            role,
            cfg["prod_mult"],
            cfg["no_real_history"],
            cfg["role_mult"],
        )
        players[key] = {
            "pos": pos,
            "effective_prod_mult": float(pm),
            "raw_prod_mult": (
                float(raw_pm) if raw_pm is not None else None
            ),
            "primary_real_history_eligible": key not in cfg["no_real_history"],
        }

    if len(players) < 500:
        raise RuntimeError(f"frozen player universe unexpectedly small: {len(players)}")
    primary_count = sum(
        1 for row in players.values()
        if row["primary_real_history_eligible"]
    )
    if primary_count < 350:
        raise RuntimeError(
            f"primary real-history cohort unexpectedly small: {primary_count}"
        )

    variants = {}
    for name, weights in (
        ("deployed_control", deployed),
        ("bridge_50", bridge50),
    ):
        predictions = {
            key: {
                "prediction_score": (
                    float(row["effective_prod_mult"])
                    * float(weights[row["pos"]])
                )
            }
            for key, row in players.items()
        }
        variants[name] = {
            "position_weights": weights,
            "predictions": predictions,
        }

    current = phase2["current_2026_ruleset_source"]
    payload = {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "FROZEN_PRESEASON_POSITION_WEIGHT_CANDIDATES",
        "research_only": True,
        "deployment_authorized": False,
        "position_weight_change_authorized": False,
        "replacement_rank_change_authorized": False,
        "production_v2_change_authorized": False,
        "transform_change_authorized": False,
        "scale_change_authorized": False,
        "frozen_at_utc": frozen_at,
        "full_candidate_universe_count": len(players),
        "primary_real_history_cohort_count": primary_count,
        "players": players,
        "variant_manifest": list(VARIANTS),
        "variants": variants,
        "ruleset": {
            "season": str(current["season"]),
            "teams": int(current["total_rosters"]),
            "roster_positions": list(current["roster_positions"]),
        },
        "protocol": {
            "season": SEASON,
            "control_variant": CONTROL,
            "primary_target": "active_game_structural_lineup_utility",
            "primary_metric": "cross_position_pairwise_ordering_accuracy",
            "secondary_metric": "global_minmax_normalized_mae_rmse",
            "prediction_score": "effective_prod_mult_times_position_weight",
            "age_excluded_from_prediction": True,
            "global_scale_invariant": True,
            "same_position_pairs_excluded": True,
            "primary_error_cohort_real_history_only": True,
            "full_universe_used_for_structural_allocation": True,
            "deployment_authorized": False,
        },
        "source_sha256": {
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
            str(PHASE2_JSON.relative_to(REPO_ROOT)): sha256(PHASE2_JSON),
            str(PHASE3_JSON.relative_to(REPO_ROOT)): sha256(PHASE3_JSON),
            str(PHASE4_JSON.relative_to(REPO_ROOT)): sha256(PHASE4_JSON),
        },
    }
    payload["frozen_prediction_sha256"] = canonical_sha256({
        "players": payload["players"],
        "variant_manifest": payload["variant_manifest"],
        "variants": payload["variants"],
        "ruleset": payload["ruleset"],
        "protocol": payload["protocol"],
    })
    return payload


def freeze_if_needed():
    if FROZEN_PATH.exists():
        frozen = read_json(FROZEN_PATH)
        if frozen.get("method_version") != METHOD_VERSION:
            raise RuntimeError("existing Position Weight Phase-5 method mismatch")
        if frozen.get("variant_manifest") != list(VARIANTS):
            raise RuntimeError("existing Position Weight Phase-5 variants changed")
        print("Existing Position Weight V2 Phase-5 freeze preserved.")
        return frozen

    payload = build_frozen_payload()
    FROZEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    FROZEN_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote immutable {FROZEN_PATH.relative_to(REPO_ROOT)}")
    return payload


def ruleset_structure(frozen):
    roster_positions = frozen["ruleset"]["roster_positions"]
    teams = int(frozen["ruleset"]["teams"])

    per_team = {}
    for slot in roster_positions:
        if slot == "BN":
            continue
        per_team[slot] = per_team.get(slot, 0) + 1

    dedicated = {
        pos: int(per_team.get(pos, 0)) * teams
        for pos in TRACKED_POSITIONS
    }
    flex = {
        slot: int(per_team.get(slot, 0)) * teams
        for slot in FLEX_ELIGIBLE
        if int(per_team.get(slot, 0)) > 0
    }
    return dedicated, flex


def distribute_flex_slots(positions, dedicated, scores, flex_counts):
    positions = tuple(positions)
    idx = {pos: i for i, pos in enumerate(positions)}
    zero = tuple(0 for _ in positions)

    for pos in positions:
        if len(scores[pos]) < int(dedicated[pos]):
            return None

    dp = {zero: 0.0}
    slot_instances = []
    for slot, count in sorted(flex_counts.items()):
        eligible = tuple(p for p in FLEX_ELIGIBLE[slot] if p in idx)
        for _ in range(int(count)):
            slot_instances.append((slot, eligible))

    for _, eligible in slot_instances:
        nxt = {}
        for state, total in dp.items():
            for pos in eligible:
                i = idx[pos]
                player_idx = int(dedicated[pos]) + int(state[i])
                if player_idx >= len(scores[pos]):
                    continue
                value = float(scores[pos][player_idx][1])
                ns = list(state)
                ns[i] += 1
                ns = tuple(ns)
                nv = total + value
                if ns not in nxt or nv > nxt[ns]:
                    nxt[ns] = nv
        if not nxt:
            return None
        dp = nxt

    best_state = max(dp.items(), key=lambda kv: kv[1])[0]
    return {
        pos: int(dedicated[pos]) + int(best_state[idx[pos]])
        for pos in positions
    }


def structural_selected_for_week(frozen, week_map):
    dedicated, flex = ruleset_structure(frozen)

    scores = {pos: [] for pos in TRACKED_POSITIONS}
    for key, row in frozen["players"].items():
        pos = row["pos"]
        outcome = week_map.get(key)
        if not outcome:
            continue
        games = float(outcome.get("games") or 0.0)
        if games <= 0:
            continue
        points = float(outcome.get("points") or 0.0)
        scores[pos].append((key, points))

    for pos in TRACKED_POSITIONS:
        scores[pos].sort(key=lambda kv: (-kv[1], kv[0]))

    offense_flex = {
        slot: count for slot, count in flex.items()
        if set(FLEX_ELIGIBLE[slot]).issubset(set(OFFENSE))
    }
    idp_flex = {
        slot: count for slot, count in flex.items()
        if set(FLEX_ELIGIBLE[slot]).issubset(set(IDP))
    }

    offense_counts = distribute_flex_slots(
        OFFENSE, dedicated, scores, offense_flex
    )
    idp_counts = distribute_flex_slots(
        IDP, dedicated, scores, idp_flex
    )
    if offense_counts is None or idp_counts is None:
        return None

    counts = {**offense_counts, **idp_counts}
    selected = {}
    for pos in TRACKED_POSITIONS:
        n = int(counts[pos])
        if len(scores[pos]) < n:
            return None
        selected[pos] = set(key for key, _ in scores[pos][:n])

    return {
        "selected": selected,
        "counts": counts,
        "active_counts": {
            pos: len(scores[pos]) for pos in TRACKED_POSITIONS
        },
    }


def aggregate_realized_utility(frozen, usable_weeks, week_maps):
    player_rows = {
        key: {
            "active_games": 0.0,
            "structural_utility_points": 0.0,
            "structural_start_games": 0,
        }
        for key in frozen["players"]
    }
    weekly_audit = {}
    accepted_weeks = []

    for week in usable_weeks:
        week_map = week_maps.get(week, {})
        structural = structural_selected_for_week(frozen, week_map)
        if structural is None:
            weekly_audit[str(week)] = {
                "usable": False,
                "reason": "insufficient_active_players_for_structural_slots",
            }
            break

        accepted_weeks.append(week)
        selected = structural["selected"]

        for key, info in frozen["players"].items():
            outcome = week_map.get(key)
            if not outcome:
                continue
            games = float(outcome.get("games") or 0.0)
            if games <= 0:
                continue
            points = float(outcome.get("points") or 0.0)
            player_rows[key]["active_games"] += games
            if key in selected[info["pos"]]:
                player_rows[key]["structural_utility_points"] += points
                player_rows[key]["structural_start_games"] += 1

        weekly_audit[str(week)] = {
            "usable": True,
            "structural_start_counts": structural["counts"],
            "active_player_counts": structural["active_counts"],
        }

    for key, row in player_rows.items():
        games = float(row["active_games"])
        row["active_game_structural_utility"] = (
            float(row["structural_utility_points"]) / games
            if games > 0 else None
        )

    return accepted_weeks, player_rows, weekly_audit


def cross_position_pairwise_accuracy(records):
    concordant = 0
    comparable = 0
    by_pair = {}

    for i in range(len(records)):
        a = records[i]
        for j in range(i + 1, len(records)):
            b = records[j]
            if a["pos"] == b["pos"]:
                continue
            dy = float(a["actual"]) - float(b["actual"])
            if dy == 0:
                continue
            dp = float(a["pred"]) - float(b["pred"])
            pair_key = tuple(sorted((a["pos"], b["pos"])))
            rec = by_pair.setdefault(
                " vs ".join(pair_key),
                {"correct": 0.0, "comparable": 0},
            )
            comparable += 1
            rec["comparable"] += 1
            if dp == 0:
                concordant += 0.5
                rec["correct"] += 0.5
            elif (dp > 0 and dy > 0) or (dp < 0 and dy < 0):
                concordant += 1
                rec["correct"] += 1

    for rec in by_pair.values():
        rec["accuracy"] = (
            rec["correct"] / rec["comparable"]
            if rec["comparable"] else None
        )

    return {
        "accuracy": concordant / comparable if comparable else None,
        "comparable_pairs": comparable,
        "by_position_pair": by_pair,
    }


def minmax_error_bundle(preds, actuals):
    if len(preds) < 2 or len(preds) != len(actuals):
        return {"n": len(preds), "mae": None, "rmse": None}
    px0, px1 = min(preds), max(preds)
    ay0, ay1 = min(actuals), max(actuals)
    if px1 == px0 or ay1 == ay0:
        return {"n": len(preds), "mae": None, "rmse": None}
    pn = [(x-px0)/(px1-px0) for x in preds]
    an = [(y-ay0)/(ay1-ay0) for y in actuals]
    errors = [p-a for p, a in zip(pn, an)]
    return {
        "n": len(errors),
        "mae": statistics.fmean(abs(e) for e in errors),
        "rmse": math.sqrt(statistics.fmean(e*e for e in errors)),
    }


def score_variant(frozen, variant, realized):
    records = []
    for key, info in frozen["players"].items():
        if not info["primary_real_history_eligible"]:
            continue
        actual = realized[key].get("active_game_structural_utility")
        if actual is None:
            continue
        pred = float(
            frozen["variants"][variant]["predictions"][key]["prediction_score"]
        )
        records.append({
            "key": key,
            "pos": info["pos"],
            "pred": pred,
            "actual": float(actual),
        })

    pairwise = cross_position_pairwise_accuracy(records)
    normalized = minmax_error_bundle(
        [r["pred"] for r in records],
        [r["actual"] for r in records],
    )

    return {
        "player_count": len(records),
        "cross_position_pairwise": pairwise,
        "global_minmax_normalized_error": normalized,
    }


def readiness(weeks):
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


def consecutive_prefix(completed_weeks):
    completed = set(int(w) for w in completed_weeks)
    out = []
    week = 1
    while week <= REGULAR_SEASON_LAST_WEEK and week in completed:
        out.append(week)
        week += 1
    return out


def build_evaluation(frozen):
    evaluator = load_model_evaluator()
    outcomes = read_json(OUTCOMES_PATH)
    evaluator.validate_outcomes(outcomes)
    completed = evaluator.completed_outcome_weeks(outcomes)
    candidate_weeks = consecutive_prefix(completed)
    week_maps = evaluator.build_week_maps(outcomes)

    usable_weeks, realized, weekly_audit = aggregate_realized_utility(
        frozen, candidate_weeks, week_maps
    )

    scores = {
        variant: score_variant(frozen, variant, realized)
        for variant in VARIANTS
    }

    control_acc = scores[CONTROL]["cross_position_pairwise"]["accuracy"]
    candidate_acc = scores["bridge_50"]["cross_position_pairwise"]["accuracy"]
    control_mae = scores[CONTROL]["global_minmax_normalized_error"]["mae"]
    candidate_mae = scores["bridge_50"]["global_minmax_normalized_error"]["mae"]

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": readiness(len(usable_weeks)),
        "research_only": True,
        "deployment_authorized": False,
        "position_weight_change_authorized": False,
        "replacement_rank_change_authorized": False,
        "production_v2_change_authorized": False,
        "transform_change_authorized": False,
        "scale_change_authorized": False,
        "production_files_mutated": 0,
        "frozen_at_utc": frozen["frozen_at_utc"],
        "frozen_prediction_sha256": frozen["frozen_prediction_sha256"],
        "completed_outcome_weeks": completed,
        "completed_consecutive_weeks_available": candidate_weeks,
        "completed_consecutive_weeks_used": usable_weeks,
        "completed_consecutive_week_count": len(usable_weeks),
        "weekly_structural_audit": weekly_audit,
        "realized_player_utility": realized,
        "variant_scores": scores,
        "bridge_50_vs_control": {
            "pairwise_accuracy_delta": (
                candidate_acc - control_acc
                if candidate_acc is not None and control_acc is not None
                else None
            ),
            "normalized_mae_delta": (
                candidate_mae - control_mae
                if candidate_mae is not None and control_mae is not None
                else None
            ),
        },
        "interpretation_guardrail": (
            "Higher cross-position pairwise accuracy is better. Weeks 1-3 are "
            "collection only and Weeks 4-7 are early diagnostics only. Do not "
            "promote bridge_50 before calibration-review readiness. A promotion "
            "case requires improvement versus deployed control in the aggregate, "
            "no persistent collapse in major position-pair diagnostics, acceptable "
            "normalized-error behavior, and reconciliation with the separately "
            "frozen Replacement Level, Production, Age, No-History, Opportunity, "
            "and Durability experiments."
        ),
    }


def fmt(value, digits=4):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def signed(value, digits=4):
    if value is None:
        return "—"
    return f"{float(value):+.{digits}f}"


def render_md(result, frozen):
    lines = [
        "# Position Weight / Cross-Position Economics V2 — Phase 5 Prospective Evaluator",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No POSITION_WEIGHT deployment is authorized.**",
        "",
        f"- Frozen at: **{result['frozen_at_utc']}**",
        f"- Frozen prediction SHA256: `{result['frozen_prediction_sha256']}`",
        f"- Completed consecutive weeks used: **{result['completed_consecutive_weeks_used'] or 'none'}**",
        f"- Full structural-allocation universe: **{frozen['full_candidate_universe_count']}**",
        f"- Primary real-history cohort: **{frozen['primary_real_history_cohort_count']}**",
        "",
        "## Frozen variants",
        "",
        "| Variant | QB | RB | WR | TE | DL | LB | DB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for variant in VARIANTS:
        w = frozen["variants"][variant]["position_weights"]
        lines.append(
            f"| `{variant}` | {fmt(w['QB'],3)} | {fmt(w['RB'],3)} | "
            f"{fmt(w['WR'],3)} | {fmt(w['TE'],3)} | {fmt(w['DL'],3)} | "
            f"{fmt(w['LB'],3)} | {fmt(w['DB'],3)} |"
        )

    lines += [
        "",
        "## Primary prospective metric",
        "",
        "**Cross-position pairwise ordering accuracy. Higher is better.**",
        "",
        "Same-position pairs are excluded. A common global scale cannot change this metric.",
        "",
        "| Variant | Players | Pairwise accuracy | Comparable cross-position pairs |",
        "|---|---:|---:|---:|",
    ]

    for variant in VARIANTS:
        row = result["variant_scores"][variant]
        pair = row["cross_position_pairwise"]
        lines.append(
            f"| `{variant}` | {row['player_count']} | "
            f"{fmt(pair['accuracy'])} | {pair['comparable_pairs']} |"
        )

    delta = result["bridge_50_vs_control"]
    lines += [
        "",
        f"Bridge-50 pairwise accuracy delta vs control: **{signed(delta['pairwise_accuracy_delta'])}**",
        "",
        "## Secondary normalized-error metric",
        "",
        "| Variant | Min-max MAE | Min-max RMSE |",
        "|---|---:|---:|",
    ]
    for variant in VARIANTS:
        err = result["variant_scores"][variant]["global_minmax_normalized_error"]
        lines.append(
            f"| `{variant}` | {fmt(err['mae'])} | {fmt(err['rmse'])} |"
        )

    lines += [
        "",
        f"Bridge-50 normalized MAE delta vs control: **{signed(delta['normalized_mae_delta'])}**",
        "",
        "## Weekly structural allocation audit",
        "",
        "| Week | Usable | QB | RB | WR | TE | DL | LB | DB |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for week in result["completed_consecutive_weeks_used"]:
        audit = result["weekly_structural_audit"][str(week)]
        c = audit["structural_start_counts"]
        lines.append(
            f"| {week} | Yes | {c['QB']} | {c['RB']} | {c['WR']} | "
            f"{c['TE']} | {c['DL']} | {c['LB']} | {c['DB']} |"
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
        "- Production multipliers: frozen preseason",
        "- Age: excluded from this positional-economics score",
        "- Replacement Level V2: unchanged",
        "- PM transform: unchanged",
        "- Global value scale: irrelevant to the primary metric",
        "- No-History/Rookie V2: unchanged",
        "- Age Curve V2: unchanged",
        "- Opportunity V2: unchanged",
        "- Durability V2: unchanged",
        "",
    ]
    return "\n".join(lines)


def write_evaluation(result, frozen):
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(
        render_md(result, frozen).rstrip() + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


def check_outputs():
    frozen = read_json(FROZEN_PATH)
    result = read_json(OUTPUT_JSON)

    if frozen.get("method_version") != METHOD_VERSION:
        raise RuntimeError("frozen Position Weight Phase-5 method mismatch")
    if result.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Position Weight Phase-5 evaluation method mismatch")
    if frozen.get("variant_manifest") != list(VARIANTS):
        raise RuntimeError("Position Weight Phase-5 variant manifest changed")

    for payload in (frozen, result):
        for field in (
            "deployment_authorized",
            "position_weight_change_authorized",
            "replacement_rank_change_authorized",
            "production_v2_change_authorized",
            "transform_change_authorized",
            "scale_change_authorized",
        ):
            if payload.get(field) is not False:
                raise RuntimeError(f"Phase-5 guardrail failed: {field}")

    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Phase-5 production mutation guardrail failed")
    if result.get("frozen_prediction_sha256") != frozen.get(
        "frozen_prediction_sha256"
    ):
        raise RuntimeError("Phase-5 evaluation/freeze SHA mismatch")

    protocol = frozen.get("protocol") or {}
    if protocol.get("primary_metric") != (
        "cross_position_pairwise_ordering_accuracy"
    ):
        raise RuntimeError("Phase-5 primary metric changed")
    if protocol.get("global_scale_invariant") is not True:
        raise RuntimeError("Phase-5 scale invariance guardrail changed")
    if protocol.get("same_position_pairs_excluded") is not True:
        raise RuntimeError("Phase-5 pairwise scope changed")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Position Weight Phase-5 Markdown missing")
    print("PASS Position Weight V2 Phase 5 checks.")


def run_selftest():
    assert consecutive_prefix([]) == []
    assert consecutive_prefix([1, 2, 3]) == [1, 2, 3]
    assert consecutive_prefix([1, 3]) == [1]

    synthetic = [
        {"pos": "QB", "pred": 2.0, "actual": 20.0},
        {"pos": "WR", "pred": 1.0, "actual": 10.0},
        {"pos": "RB", "pred": 1.5, "actual": 15.0},
    ]
    pair = cross_position_pairwise_accuracy(synthetic)
    assert abs(pair["accuracy"] - 1.0) < 1e-12

    # Positive global scale must not change pairwise ordering.
    scaled = [
        {**r, "pred": r["pred"] * 55.0}
        for r in synthetic
    ]
    pair2 = cross_position_pairwise_accuracy(scaled)
    assert pair2["accuracy"] == pair["accuracy"]

    err = minmax_error_bundle([1, 2, 3], [10, 20, 30])
    assert abs(err["mae"]) < 1e-12
    assert abs(err["rmse"]) < 1e-12

    assert readiness(0) == "READY_WAITING_FOR_COMPLETED_WEEK_1"
    assert readiness(8) == "CALIBRATION_REVIEW_ELIGIBLE"
    print("PASS Position Weight V2 Phase 5 self-test.")


def main():
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
        print(render_md(result, frozen))


if __name__ == "__main__":
    main()

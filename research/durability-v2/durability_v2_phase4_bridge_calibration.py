#!/usr/bin/env python3
"""
Durability / Availability V2 — Phase 4 historical bridge calibration.

RESEARCH ONLY. No deployed durability, production, age, opportunity, market,
or player-value file is changed.

Purpose
-------
Phase 2 validated a survivor-only, position-specific trained availability blend.
Phase 3 showed 25%, 50%, and 100% bridges can be transported into the current
value architecture without broad board instability.

Phase 4 now chooses bridge strength HISTORICALLY with leave-one-base-season-out
cross-validation. Current-board movement is a guardrail only, never the primary
selection criterion.

Historical variants
-------------------
- deployed_control: existing position R^2 weight
- bridge_w25
- bridge_w50
- bridge_w75
- bridge_w100

For each held-out base season:
1. derive the position median from the OTHER seasons;
2. choose the position's trained own-history weight on the OTHER seasons only;
3. bridge from deployed R^2 to that trained weight;
4. score next-season survivor-only availability on the held-out season.

Primary metric: MAE.
Secondary: RMSE, Spearman, Pearson.
No player from the held-out season is used to choose that fold's trained weight.

Current-board transport
-----------------------
Phase 4 reuses the exact fixed transport inputs already written by Phase 3 and
adds the missing 75% bridge. This is only a stability audit. Historical OOF
performance determines the monitoring leader.

Outputs
-------
research/durability-v2/durability_v2_phase4_bridge_calibration.json
research/durability-v2/durability_v2_phase4_bridge_calibration.md
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

PHASE1_JSON = (
    REPO_ROOT / "research" / "durability-v2"
    / "durability_v2_phase1_availability_audit.json"
)
PHASE2_JSON = (
    REPO_ROOT / "research" / "durability-v2"
    / "durability_v2_phase2_candidate_evaluation.json"
)
PHASE3_JSON = (
    REPO_ROOT / "research" / "durability-v2"
    / "durability_v2_phase3_shadow_audit.json"
)
INDEX_HTML = REPO_ROOT / "index.html"

OUTPUT_JSON = (
    REPO_ROOT / "research" / "durability-v2"
    / "durability_v2_phase4_bridge_calibration.json"
)
OUTPUT_MD = (
    REPO_ROOT / "research" / "durability-v2"
    / "durability_v2_phase4_bridge_calibration.md"
)

METHOD_VERSION = "durability-v2-phase4-bridge-calibration-v1"
PHASE1_METHOD = "durability-v2-phase1-availability-audit-v1"
PHASE2_METHOD = "durability-v2-phase2-candidate-evaluation-v1"
PHASE3_METHOD = "durability-v2-phase3-shadow-audit-v1"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
BASE_SEASONS = tuple(range(2015, 2025))
TRAIN_WEIGHT_GRID = tuple(i / 20.0 for i in range(21))
BRIDGES = {
    "deployed_control": 0.00,
    "bridge_w25": 0.25,
    "bridge_w50": 0.50,
    "bridge_w75": 0.75,
    "bridge_w100": 1.00,
}

HISTORY_WEIGHT = 0.45
FORWARD_WEIGHT = 0.55
PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55
GLOBAL_VALUE_SCALE = 55.0

HISTORICAL_SCREEN = {
    "mae_must_beat_control": True,
    "spearman_delta_min": -0.005,
    "positions_with_mae_improvement_min": 5,
    "fold_improvement_share_min": 0.80,
}

CURRENT_SCREEN = {
    "median_abs_value_change_pct_max": 0.10,
    "p90_abs_value_change_pct_max": 0.20,
    "min_position_rank_spearman": 0.95,
    "min_position_top_n_overlap": 0.85,
}


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(float(v) for v in values)
    if len(vals) == 1:
        return vals[0]
    idx = (len(vals) - 1) * max(0.0, min(1.0, q))
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    t = idx - lo
    return vals[lo] * (1.0 - t) + vals[hi] * t


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


def descending_ranks(values: list[float]) -> list[float]:
    return rankdata([-float(v) for v in values])


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


def value_spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    return pearson(descending_ranks(xs), descending_ranks(ys))


def metric_bundle(rows: list[dict[str, Any]], pred_field: str) -> dict[str, Any]:
    if not rows:
        return {"n": 0, "mae": None, "rmse": None, "spearman": None, "pearson": None}
    actual = [float(r["target"]) for r in rows]
    pred = [float(r[pred_field]) for r in rows]
    return {
        "n": len(rows),
        "mae": statistics.fmean(abs(a-p) for a, p in zip(actual, pred)),
        "rmse": math.sqrt(statistics.fmean((a-p)**2 for a, p in zip(actual, pred))),
        "spearman": spearman(pred, actual),
        "pearson": pearson(pred, actual),
    }


def validate_inputs(
    p1: dict[str, Any],
    p2: dict[str, Any],
    p3: dict[str, Any],
) -> None:
    if p1.get("method_version") != PHASE1_METHOD:
        raise RuntimeError("Unexpected Durability Phase-1 method")
    if p2.get("method_version") != PHASE2_METHOD:
        raise RuntimeError("Unexpected Durability Phase-2 method")
    if p3.get("method_version") != PHASE3_METHOD:
        raise RuntimeError("Unexpected Durability Phase-3 method")
    if (
        p2["targets"]["survivor_only"]["families"]["one_year"]
        .get("monitoring_leader")
        != "trained_blend"
    ):
        raise RuntimeError("Phase-2 survivor leader is no longer trained_blend")
    if int(p3.get("current_shadow_cohort_size") or 0) < 350:
        raise RuntimeError("Phase-3 current shadow cohort unexpectedly small")


def deployed_r2_weights(p1: dict[str, Any]) -> dict[str, float]:
    deployed = (
        p1.get("legacy_methodology", {})
        .get("deployed_durability_results", {})
    )
    out = {}
    for pos in TRACKED_POSITIONS:
        value = (deployed.get(pos) or {}).get("r_squared")
        if value is None:
            raise RuntimeError(f"Missing deployed durability R2 for {pos}")
        out[pos] = clamp(float(value), 0.0, 1.0)
    return out


def survivor_rows(p1: dict[str, Any]) -> list[dict[str, Any]]:
    source = p1.get("survivor_only_transition_rows")
    if not isinstance(source, list):
        raise RuntimeError("Phase 1 missing survivor_only_transition_rows")
    rows = []
    for r in source:
        pos = str(r.get("pos") or "")
        season = int(r.get("season"))
        if pos not in TRACKED_POSITIONS or season not in BASE_SEASONS:
            continue
        rows.append({
            "sleeper_id": str(r["sleeper_id"]),
            "pos": pos,
            "season": season,
            "current": float(r["current_availability"]),
            "target": float(r["next_availability"]),
        })
    if len(rows) < 10000:
        raise RuntimeError(f"Survivor row sample unexpectedly small: {len(rows)}")
    return rows


def fit_position(
    train: list[dict[str, Any]],
    pos: str,
) -> tuple[float, float, float]:
    cohort = [r for r in train if r["pos"] == pos]
    if len(cohort) < 100:
        raise RuntimeError(f"{pos}: training cohort too small ({len(cohort)})")
    med = statistics.median(float(r["current"]) for r in cohort)

    best = None
    for weight in TRAIN_WEIGHT_GRID:
        mae = statistics.fmean(
            abs(
                float(r["target"])
                - (
                    weight * float(r["current"])
                    + (1.0-weight) * med
                )
            )
            for r in cohort
        )
        candidate = (mae, abs(weight-0.5), weight)
        if best is None or candidate < best:
            best = candidate

    assert best is not None
    return med, float(best[2]), float(best[0])


def build_oof(
    p1: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = survivor_rows(p1)
    deployed = deployed_r2_weights(p1)
    out = []
    fold_params = {}

    for held in BASE_SEASONS:
        train = [r for r in rows if r["season"] != held]
        test = [r for r in rows if r["season"] == held]
        params = {}

        for pos in TRACKED_POSITIONS:
            med, trained_weight, train_mae = fit_position(train, pos)
            params[pos] = {
                "training_n": sum(1 for r in train if r["pos"] == pos),
                "test_n": sum(1 for r in test if r["pos"] == pos),
                "training_position_median": med,
                "deployed_r2_weight": deployed[pos],
                "trained_weight": trained_weight,
                "trained_weight_training_mae": train_mae,
            }

            for row in test:
                if row["pos"] != pos:
                    continue
                rec = dict(row)
                for variant, bridge in BRIDGES.items():
                    weight = (
                        deployed[pos]
                        + bridge * (trained_weight - deployed[pos])
                    )
                    rec[f"weight__{variant}"] = weight
                    rec[f"pred__{variant}"] = (
                        weight * float(row["current"])
                        + (1.0-weight) * med
                    )
                out.append(rec)

        fold_params[str(held)] = params

    if len(out) != len(rows):
        raise RuntimeError(
            f"OOF coverage mismatch: predictions={len(out)} rows={len(rows)}"
        )
    return out, fold_params


def evaluate_oof(rows: list[dict[str, Any]]) -> dict[str, Any]:
    variants = tuple(BRIDGES)

    overall = {
        v: metric_bundle(rows, f"pred__{v}")
        for v in variants
    }

    by_position = {}
    for pos in TRACKED_POSITIONS:
        cohort = [r for r in rows if r["pos"] == pos]
        by_position[pos] = {
            v: metric_bundle(cohort, f"pred__{v}")
            for v in variants
        }

    by_fold = {}
    for season in BASE_SEASONS:
        cohort = [r for r in rows if r["season"] == season]
        by_fold[str(season)] = {
            v: metric_bundle(cohort, f"pred__{v}")
            for v in variants
        }

    return {
        "overall": overall,
        "by_position": by_position,
        "by_fold": by_fold,
    }


def comparisons(evaluation: dict[str, Any]) -> dict[str, Any]:
    control = evaluation["overall"]["deployed_control"]
    out = {}

    for variant in BRIDGES:
        if variant == "deployed_control":
            continue
        cur = evaluation["overall"][variant]

        pos_improved = 0
        pos_delta = {}
        for pos in TRACKED_POSITIONS:
            a = evaluation["by_position"][pos][variant]["mae"]
            b = evaluation["by_position"][pos]["deployed_control"]["mae"]
            delta = float(a) - float(b)
            pos_delta[pos] = delta
            if delta < 0:
                pos_improved += 1

        fold_improved = 0
        fold_delta = {}
        for season in BASE_SEASONS:
            key = str(season)
            a = evaluation["by_fold"][key][variant]["mae"]
            b = evaluation["by_fold"][key]["deployed_control"]["mae"]
            delta = float(a) - float(b)
            fold_delta[key] = delta
            if delta < 0:
                fold_improved += 1

        out[variant] = {
            "mae_delta_vs_control": (
                float(cur["mae"]) - float(control["mae"])
            ),
            "rmse_delta_vs_control": (
                float(cur["rmse"]) - float(control["rmse"])
            ),
            "spearman_delta_vs_control": (
                float(cur["spearman"]) - float(control["spearman"])
            ),
            "pearson_delta_vs_control": (
                float(cur["pearson"]) - float(control["pearson"])
            ),
            "positions_with_mae_improvement": pos_improved,
            "folds_with_mae_improvement": fold_improved,
            "folds_compared": len(BASE_SEASONS),
            "fold_improvement_share": fold_improved / len(BASE_SEASONS),
            "by_position_mae_delta": pos_delta,
            "by_fold_mae_delta": fold_delta,
        }

    return out


def historical_screen(
    evaluation: dict[str, Any],
    comp: dict[str, Any],
) -> dict[str, Any]:
    control = evaluation["overall"]["deployed_control"]
    out = {}

    for variant in BRIDGES:
        if variant == "deployed_control":
            out[variant] = {"control": True, "passes": True, "checks": {}}
            continue

        row = evaluation["overall"][variant]
        c = comp[variant]
        checks = {
            "mae_beats_control": float(row["mae"]) < float(control["mae"]),
            "spearman_delta": (
                float(c["spearman_delta_vs_control"])
                >= HISTORICAL_SCREEN["spearman_delta_min"]
            ),
            "positions_with_mae_improvement": (
                int(c["positions_with_mae_improvement"])
                >= HISTORICAL_SCREEN["positions_with_mae_improvement_min"]
            ),
            "fold_improvement_share": (
                float(c["fold_improvement_share"])
                >= HISTORICAL_SCREEN["fold_improvement_share_min"]
            ),
        }
        out[variant] = {
            "control": False,
            "passes": all(checks.values()),
            "checks": checks,
        }
    return out


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def candidate_value(
    key: str,
    raw_pm: float,
    cfg: dict[str, Any],
    snapshot_values,
) -> int:
    info = cfg["player_db"][key]
    effective_pm, raw_seen = snapshot_values.production_multiplier(
        key,
        info["role"],
        {key: raw_pm},
        cfg["no_real_history"],
        cfg["role_mult"],
    )
    age_mult = snapshot_values.effective_age_multiplier(
        info["pos"],
        info["age"],
        info["role"],
        key,
        effective_pm,
        raw_seen,
        cfg,
    )
    pw = cfg["position_weight"].get(info["pos"], 1.0)
    return math.floor(
        100 * pw * age_mult * effective_pm * GLOBAL_VALUE_SCALE + 0.5
    )


def top_n(pos: str, n: int) -> int:
    ranks = {"QB": 18, "RB": 32, "WR": 36, "TE": 15, "DL": 32, "LB": 32, "DB": 32}
    return min(ranks[pos], n)


def current_transport(
    p3: dict[str, Any],
) -> dict[str, Any]:
    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)
    players = p3.get("players")
    if not isinstance(players, dict):
        raise RuntimeError("Phase 3 missing players")

    variants = [v for v in BRIDGES if v != "deployed_control"]
    candidate_values = {v: {} for v in variants}
    control_values = {}
    game_changes = {v: [] for v in variants}
    pct_changes = {v: [] for v in variants}

    for key, row in players.items():
        if key not in cfg["player_db"]:
            continue

        control = row["variants"]["deployed_control"]
        control_value = float(control["value"])
        control_values[key] = control_value

        deployed_weight = float(row["deployed_own_weight"])
        trained_weight = float(row["trained_own_weight"])
        own_avail = float(row["own_availability_2025"])
        med_avail = float(row["position_median_availability_2025"])
        shrunk_ppg = float(row["shrunk_ppg"])
        forward = float(row["forward_projection"])
        baseline = float(row["fixed_phase1_baseline_points"])

        for variant in variants:
            bridge = BRIDGES[variant]
            own_weight = (
                deployed_weight
                + bridge * (trained_weight - deployed_weight)
            )
            projected_avail = (
                own_weight * own_avail
                + (1.0-own_weight) * med_avail
            )
            games = projected_avail * 17.0
            history_component = shrunk_ppg * games
            combined = (
                HISTORY_WEIGHT * history_component
                + FORWARD_WEIGHT * forward
            )
            ratio = combined / baseline
            raw_pm = clamp(
                PM_INTERCEPT + PM_RATIO_SLOPE * ratio,
                PM_MIN,
                PM_MAX,
            )
            value = candidate_value(
                key,
                raw_pm,
                cfg,
                snapshot_values,
            )
            candidate_values[variant][key] = float(value)
            game_changes[variant].append(
                games - float(control["projected_games_2026"])
            )
            if control_value > 0:
                pct_changes[variant].append(
                    (float(value)-control_value)/control_value
                )

    out = {}
    for variant in variants:
        by_position = {}
        min_rho = 1.0
        min_overlap = 1.0

        for pos in TRACKED_POSITIONS:
            keys = [
                k for k, row in players.items()
                if row["pos"] == pos
                and k in candidate_values[variant]
                and k in control_values
            ]
            cur = [control_values[k] for k in keys]
            cand = [candidate_values[variant][k] for k in keys]
            rho = value_spearman(cur, cand)

            n_top = top_n(pos, len(keys))
            cur_top = set(
                sorted(keys, key=lambda k: (-control_values[k], k))[:n_top]
            )
            cand_top = set(
                sorted(keys, key=lambda k: (-candidate_values[variant][k], k))[:n_top]
            )
            overlap = len(cur_top & cand_top)/n_top if n_top else 1.0
            if rho is not None:
                min_rho = min(min_rho, rho)
            min_overlap = min(min_overlap, overlap)

            by_position[pos] = {
                "n": len(keys),
                "rank_spearman_vs_control": rho,
                "top_n": n_top,
                "top_n_overlap_share": overlap,
            }

        abs_pct = [abs(x) for x in pct_changes[variant]]
        abs_games = [abs(x) for x in game_changes[variant]]
        out[variant] = {
            "n": len(candidate_values[variant]),
            "changed_players": sum(
                1 for k, v in candidate_values[variant].items()
                if v != control_values[k]
            ),
            "median_abs_value_change_pct": statistics.median(abs_pct),
            "p90_abs_value_change_pct": percentile(abs_pct, 0.90),
            "p95_abs_value_change_pct": percentile(abs_pct, 0.95),
            "max_abs_value_change_pct": max(abs_pct),
            "median_projected_games_change": statistics.median(
                game_changes[variant]
            ),
            "p90_abs_projected_games_change": percentile(abs_games, 0.90),
            "min_position_rank_spearman": min_rho,
            "min_position_top_n_overlap": min_overlap,
            "by_position": by_position,
        }

    return out


def current_screen(current: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for variant, row in current.items():
        checks = {
            "median_abs_value_change_pct": (
                float(row["median_abs_value_change_pct"])
                <= CURRENT_SCREEN["median_abs_value_change_pct_max"]
            ),
            "p90_abs_value_change_pct": (
                float(row["p90_abs_value_change_pct"])
                <= CURRENT_SCREEN["p90_abs_value_change_pct_max"]
            ),
            "min_position_rank_spearman": (
                float(row["min_position_rank_spearman"])
                >= CURRENT_SCREEN["min_position_rank_spearman"]
            ),
            "min_position_top_n_overlap": (
                float(row["min_position_top_n_overlap"])
                >= CURRENT_SCREEN["min_position_top_n_overlap"]
            ),
        }
        out[variant] = {
            "passes": all(checks.values()),
            "checks": checks,
        }
    return out


def choose_candidates(
    evaluation: dict[str, Any],
    historical: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    survivors = [
        v for v in BRIDGES
        if v != "deployed_control"
        and historical[v]["passes"]
        and current[v]["passes"]
    ]

    survivors.sort(
        key=lambda v: (
            float(evaluation["overall"][v]["mae"]),
            -float(evaluation["overall"][v]["spearman"]),
            BRIDGES[v],
        )
    )
    leader = survivors[0] if survivors else None

    # Prespecified conservative comparator: best passing variant at <=50% bridge.
    conservative_pool = [v for v in survivors if BRIDGES[v] <= 0.50]
    conservative_pool.sort(
        key=lambda v: (
            float(evaluation["overall"][v]["mae"]),
            -float(evaluation["overall"][v]["spearman"]),
        )
    )
    conservative = conservative_pool[0] if conservative_pool else None

    return {
        "survivors": survivors,
        "monitoring_leader": leader,
        "conservative_comparator": conservative,
    }


def build_result() -> dict[str, Any]:
    p1 = read_json(PHASE1_JSON)
    p2 = read_json(PHASE2_JSON)
    p3 = read_json(PHASE3_JSON)
    validate_inputs(p1, p2, p3)

    oof, fold_params = build_oof(p1)
    evaluation = evaluate_oof(oof)
    comp = comparisons(evaluation)
    hist_screen = historical_screen(evaluation, comp)
    current = current_transport(p3)
    cur_screen = current_screen(current)
    selected = choose_candidates(
        evaluation,
        hist_screen,
        cur_screen,
    )

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_DURABILITY_BRIDGE_CALIBRATION",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "durability_change_authorized": False,
        "history_component_change_authorized": False,
        "primary_target": "survivor-only next-season availability",
        "primary_metric": "leave-one-base-season-out MAE",
        "variant_manifest": BRIDGES,
        "historical_screen_thresholds": HISTORICAL_SCREEN,
        "current_screen_thresholds": CURRENT_SCREEN,
        "fold_parameters": fold_params,
        "oof_predictions": oof,
        "historical_evaluation": evaluation,
        "comparison_vs_deployed_control": comp,
        "historical_screening": hist_screen,
        "current_transport_stability": current,
        "current_screening": cur_screen,
        **selected,
        "phase5_handoff": (
            "Freeze deployed_control, monitoring_leader, and the prespecified "
            "conservative_comparator prospectively before the 2026 season. "
            "Primary prospective target should be games available / scheduled "
            "games among players with a frozen real-history durability signal. "
            "Do not mutate Production V2, Age Curve V2, Opportunity V2, or "
            "No-History V2."
            if selected["monitoring_leader"]
            else
            "No bridge survived both historical and current-board gates. "
            "Do not create a prospective durability experiment."
        ),
    }


def fmt(v: Any, d: int = 4) -> str:
    return "—" if v is None else f"{float(v):.{d}f}"


def signed(v: Any, d: int = 4) -> str:
    return "—" if v is None else f"{float(v):+.{d}f}"


def pct(v: Any, d: int = 1) -> str:
    return "—" if v is None else f"{100*float(v):.{d}f}%"


def render_markdown(result: dict[str, Any]) -> str:
    ev = result["historical_evaluation"]["overall"]
    comp = result["comparison_vs_deployed_control"]

    lines = [
        "# Durability / Availability V2 — Phase 4 Bridge Calibration",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No deployed durability or player value is changed.**",
        "",
        "Bridge strength is selected from historical out-of-sample performance.",
        "Current-board movement is only a stability gate.",
        "",
        "## Historical survivor-only out-of-sample results",
        "",
        "| Variant | N | MAE | Δ MAE | RMSE | Spearman | Δ Spearman | "
        "Pos improved | Folds improved | Hist pass |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for variant in BRIDGES:
        row = ev[variant]
        if variant == "deployed_control":
            delta_mae = delta_sp = None
            pos_imp = folds = "—"
        else:
            c = comp[variant]
            delta_mae = c["mae_delta_vs_control"]
            delta_sp = c["spearman_delta_vs_control"]
            pos_imp = f"{c['positions_with_mae_improvement']}/7"
            folds = f"{c['folds_with_mae_improvement']}/{c['folds_compared']}"
        lines.append(
            f"| `{variant}` | {row['n']} | {fmt(row['mae'])} | "
            f"{signed(delta_mae)} | {fmt(row['rmse'])} | "
            f"{fmt(row['spearman'])} | {signed(delta_sp)} | "
            f"{pos_imp} | {folds} | "
            f"{'PASS' if result['historical_screening'][variant]['passes'] else 'FAIL'} |"
        )

    lines.extend([
        "",
        "## Current-board stability",
        "",
        "| Variant | Median abs FV | P90 abs FV | P95 abs FV | Max abs FV | "
        "P90 abs games Δ | Min pos rank ρ | Min top-N overlap | Pass |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ])

    for variant in BRIDGES:
        if variant == "deployed_control":
            continue
        row = result["current_transport_stability"][variant]
        lines.append(
            f"| `{variant}` | "
            f"{pct(row['median_abs_value_change_pct'])} | "
            f"{pct(row['p90_abs_value_change_pct'])} | "
            f"{pct(row['p95_abs_value_change_pct'])} | "
            f"{pct(row['max_abs_value_change_pct'])} | "
            f"{fmt(row['p90_abs_projected_games_change'], 2)} | "
            f"{fmt(row['min_position_rank_spearman'])} | "
            f"{pct(row['min_position_top_n_overlap'])} | "
            f"{'PASS' if result['current_screening'][variant]['passes'] else 'FAIL'} |"
        )

    lines.extend([
        "",
        "## Decision",
        "",
        f"- Monitoring leader: **`{result['monitoring_leader'] or 'none'}`**",
        f"- Conservative comparator: **`{result['conservative_comparator'] or 'none'}`**",
        "- Deployment authorized: **No**",
        "",
        "## Phase 5",
        "",
        result["phase5_handoff"],
        "",
    ])
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
        raise RuntimeError("Durability Phase-4 method mismatch")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Durability Phase-4 mutation guardrail failed")

    for key in (
        "deployment_authorized",
        "durability_change_authorized",
        "history_component_change_authorized",
    ):
        if result.get(key) is not False:
            raise RuntimeError(f"Durability Phase 4 unexpectedly authorizes {key}")

    if int(result["historical_evaluation"]["overall"]["deployed_control"]["n"]) < 10000:
        raise RuntimeError("Durability Phase-4 OOF sample unexpectedly small")

    expected = set(BRIDGES)
    if set(result.get("historical_evaluation", {}).get("overall", {})) != expected:
        raise RuntimeError("Durability Phase-4 historical variant mismatch")
    if set(result.get("current_transport_stability", {})) != expected - {"deployed_control"}:
        raise RuntimeError("Durability Phase-4 current variant mismatch")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Durability Phase-4 markdown missing")
    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Historical survivor-only",
        "Current-board stability",
        "Monitoring leader",
        "Phase 5",
    ):
        if marker not in text:
            raise RuntimeError(f"Durability Phase-4 report missing marker: {marker}")

    print("Durability / Availability V2 Phase-4 outputs passed guardrails.")


def run_selftest() -> None:
    dep = 0.10
    trained = 0.50
    assert abs(dep + 0.25*(trained-dep) - 0.20) < 1e-12
    assert abs(dep + 0.50*(trained-dep) - 0.30) < 1e-12
    assert abs(dep + 0.75*(trained-dep) - 0.40) < 1e-12
    assert abs(dep + 1.00*(trained-dep) - 0.50) < 1e-12

    assert abs(spearman([1,2,3,4,5], [10,20,30,40,50]) - 1.0) < 1e-12

    fake = []
    for season in (2019, 2020, 2021):
        for i in range(120):
            cur = (i % 20) / 20.0
            fake.append({
                "pos": "RB",
                "season": season,
                "current": cur,
                "target": 0.25 + 0.5*cur,
            })
    med, weight, mae = fit_position(fake, "RB")
    assert 0 <= med <= 1
    assert 0 <= weight <= 1
    assert mae >= 0

    print(
        "Durability / Availability V2 Phase-4 self-test passed: "
        "bridge interpolation, correlation helpers, and training-only fit."
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

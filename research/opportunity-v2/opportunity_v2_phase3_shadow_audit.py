#!/usr/bin/env python3
"""
Continuous Opportunity / Role Signal V2 — Phase 3 current-player shadow audit.

RESEARCH ONLY. No deployed ROLE_MULT, PROD_MULT_DATA, AGE_CURVE, Production V2,
Market Value, or player value is changed.

Purpose
-------
Phase 2 found a small but broad incremental benefit from:
    production_plus_season_opportunity_change

This phase does NOT turn that model into a new production engine.

Instead:
1. Refit the Phase-2 production-only control and monitoring leader on the full
   historical sample, separately by position.
2. For current REAL-HISTORY players with 2025 opportunity evidence, estimate:
       leader expected future production / control expected future production
   This isolates the incremental opportunity residual from production itself.
3. Winsorize the residual ratio using historical out-of-fold 5th/95th percentiles
   by position so current low-base edge cases cannot explode.
4. Apply that residual only as a research shadow to the CURRENT deployed
   Fundamental Value:
       shadow = deployed_value * (1 + bridge_weight * (ratio - 1))
5. Audit current movement and rank stability for 25%, 50%, and full-residual
   diagnostic bridges.

No candidate is authorized for deployment here.

Inputs
------
research/opportunity-v2/opportunity_v2_phase1_coverage_audit.json
research/opportunity-v2/opportunity_v2_phase2_candidate_evaluation.json
research/production-v2/production_v2_phase1_audit.json

Outputs
-------
research/opportunity-v2/opportunity_v2_phase3_shadow_audit.json
research/opportunity-v2/opportunity_v2_phase3_shadow_audit.md

Usage
-----
python3 research/opportunity-v2/opportunity_v2_phase3_shadow_audit.py --selftest
python3 research/opportunity-v2/opportunity_v2_phase3_shadow_audit.py --write
python3 research/opportunity-v2/opportunity_v2_phase3_shadow_audit.py --check
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]

PHASE1_JSON = (
    REPO_ROOT
    / "research"
    / "opportunity-v2"
    / "opportunity_v2_phase1_coverage_audit.json"
)
PHASE2_JSON = (
    REPO_ROOT
    / "research"
    / "opportunity-v2"
    / "opportunity_v2_phase2_candidate_evaluation.json"
)
PROD_PHASE1_JSON = (
    REPO_ROOT
    / "research"
    / "production-v2"
    / "production_v2_phase1_audit.json"
)

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "opportunity-v2"
    / "opportunity_v2_phase3_shadow_audit.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "opportunity-v2"
    / "opportunity_v2_phase3_shadow_audit.md"
)

METHOD_VERSION = "opportunity-v2-phase3-shadow-audit-v1"
PHASE1_METHOD = "opportunity-v2-phase1-coverage-v1"
PHASE2_METHOD = "opportunity-v2-phase2-candidate-evaluation-v1"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
CONTROL = "production_only"
LEADER = "production_plus_season_opportunity_change"
BRIDGE_WEIGHTS = (0.25, 0.50, 1.00)
EPS = 1e-9

CONTROL_FEATURES = (
    "current_points_per_team_game",
)
LEADER_FEATURES = (
    "current_points_per_team_game",
    "season_opportunity_share",
    "opportunity_change",
    "prior_opportunity_present",
)

# Screening thresholds are current-board stability guardrails only.
# They do NOT authorize deployment.
SCREEN_THRESHOLDS = {
    "median_abs_change_pct_max": 0.10,
    "p90_abs_change_pct_max": 0.20,
    "min_position_rank_spearman": 0.95,
    "min_position_top_n_overlap": 0.85,
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


def finite(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(float(v) for v in values)
    if len(vals) == 1:
        return vals[0]
    q = max(0.0, min(1.0, float(q)))
    idx = (len(vals) - 1) * q
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


def fit_ols(
    rows: list[dict[str, Any]],
    features: tuple[str, ...],
) -> np.ndarray:
    if len(rows) < 20:
        raise RuntimeError(f"Too few OLS rows: {len(rows)}")
    x = np.asarray(
        [
            [1.0] + [float(row[name]) for name in features]
            for row in rows
        ],
        dtype=float,
    )
    y = np.asarray(
        [float(row["year1_points_per_team_game"]) for row in rows],
        dtype=float,
    )
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    return beta


def predict(
    beta: np.ndarray,
    row: dict[str, Any],
    features: tuple[str, ...],
) -> float:
    x = np.asarray(
        [1.0] + [float(row[name]) for name in features],
        dtype=float,
    )
    return max(0.0, float(np.dot(x, beta)))


def validate_inputs(
    phase1: dict[str, Any],
    phase2: dict[str, Any],
    production: dict[str, Any],
) -> None:
    if phase1.get("method_version") != PHASE1_METHOD:
        raise RuntimeError("Unexpected Opportunity Phase-1 method")
    if phase2.get("method_version") != PHASE2_METHOD:
        raise RuntimeError("Unexpected Opportunity Phase-2 method")
    if phase2.get("monitoring_leader") != LEADER:
        raise RuntimeError(
            f"Phase-2 monitoring leader changed; expected {LEADER!r}, got "
            f"{phase2.get('monitoring_leader')!r}"
        )
    if phase1.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 1 unexpectedly authorizes deployment")
    if phase2.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 2 unexpectedly authorizes deployment")
    players = production.get("players")
    if not isinstance(players, dict) or len(players) < 500:
        raise RuntimeError("Production V2 Phase-1 player matrix missing/sparse")


def full_sample_coefficients(
    phase2: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    rows = phase2.get("oof_predictions")
    if not isinstance(rows, list) or len(rows) < 14000:
        raise RuntimeError("Phase 2 OOF rows missing/sparse")

    out = {}
    for pos in TRACKED_POSITIONS:
        cohort = [r for r in rows if r.get("pos") == pos]
        control_beta = fit_ols(cohort, CONTROL_FEATURES)
        leader_beta = fit_ols(cohort, LEADER_FEATURES)
        out[pos] = {
            "n": len(cohort),
            CONTROL: {
                "features": list(CONTROL_FEATURES),
                "coefficients": [float(x) for x in control_beta],
            },
            LEADER: {
                "features": list(LEADER_FEATURES),
                "coefficients": [float(x) for x in leader_beta],
            },
        }
    return out


def historical_ratio_bounds(
    phase2: dict[str, Any],
) -> dict[str, dict[str, float]]:
    rows = phase2.get("oof_predictions")
    if not isinstance(rows, list):
        raise RuntimeError("Phase 2 missing OOF predictions")

    out = {}
    for pos in TRACKED_POSITIONS:
        ratios = []
        for row in rows:
            if row.get("pos") != pos:
                continue
            control = finite(row.get(f"pred__{CONTROL}"))
            leader = finite(row.get(f"pred__{LEADER}"))
            if control <= EPS:
                continue
            ratio = leader / control
            if math.isfinite(ratio) and ratio > 0:
                ratios.append(ratio)

        if len(ratios) < 100:
            raise RuntimeError(
                f"{pos}: too few historical residual ratios: {len(ratios)}"
            )
        lo = percentile(ratios, 0.05)
        hi = percentile(ratios, 0.95)
        med = percentile(ratios, 0.50)
        assert lo is not None and hi is not None and med is not None
        out[pos] = {
            "n": len(ratios),
            "p05": lo,
            "median": med,
            "p95": hi,
        }
    return out


def build_historical_opportunity_lookup(
    phase1: dict[str, Any],
) -> dict[tuple[str, int], dict[str, Any]]:
    rows = phase1.get("historical_player_seasons")
    if not isinstance(rows, list):
        raise RuntimeError("Phase 1 missing historical_player_seasons")

    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        gsis_id = str(row.get("gsis_id") or "").strip()
        season = int(row.get("season") or 0)
        if not gsis_id or not season:
            continue
        key = (gsis_id, season)
        if key in out:
            raise RuntimeError(f"Duplicate opportunity row: {key}")
        out[key] = row
    return out


def round_value(x: float) -> int:
    return int(math.floor(float(x) + 0.5))


def build_current_shadow_rows(
    phase1: dict[str, Any],
    production: dict[str, Any],
    coefficients: dict[str, dict[str, Any]],
    bounds: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    current_rows = phase1.get("current_players")
    if not isinstance(current_rows, list):
        raise RuntimeError("Phase 1 missing current_players")

    prod_players = production["players"]
    historical_opp = build_historical_opportunity_lookup(phase1)

    out = []

    for current in current_rows:
        player = str(current.get("player") or "")
        pos = str(current.get("pos") or "")
        if pos not in TRACKED_POSITIONS:
            continue

        prod = prod_players.get(player)
        if not isinstance(prod, dict):
            continue

        current_info = prod.get("current") or {}
        if current_info.get("no_real_production_history") is True:
            continue

        history = prod.get("history") or {}
        true_ppg = history.get("true_ppg_2025")
        games = int(history.get("games_played_2025") or 0)
        if true_ppg is None or games <= 0:
            continue

        gsis_id = str(
            ((current.get("nflverse") or {}).get("gsis_id")) or ""
        ).strip()
        if not gsis_id:
            continue

        opp_2025 = historical_opp.get((gsis_id, 2025))
        if not isinstance(opp_2025, dict):
            continue

        current_opp = finite(opp_2025.get("season_opportunity_share"))
        prior = historical_opp.get((gsis_id, 2024))
        prior_present = 1.0 if prior is not None else 0.0
        prior_opp = (
            finite(prior.get("season_opportunity_share"))
            if prior is not None else current_opp
        )

        feature_row = {
            "current_points_per_team_game": (
                float(true_ppg) * games / 17.0
            ),
            "season_opportunity_share": current_opp,
            "opportunity_change": current_opp - prior_opp,
            "prior_opportunity_present": prior_present,
        }

        control_beta = np.asarray(
            coefficients[pos][CONTROL]["coefficients"],
            dtype=float,
        )
        leader_beta = np.asarray(
            coefficients[pos][LEADER]["coefficients"],
            dtype=float,
        )
        control_pred = predict(control_beta, feature_row, CONTROL_FEATURES)
        leader_pred = predict(leader_beta, feature_row, LEADER_FEATURES)

        raw_ratio = (
            leader_pred / control_pred
            if control_pred > EPS
            else 1.0
        )
        lo = float(bounds[pos]["p05"])
        hi = float(bounds[pos]["p95"])
        clipped_ratio = max(lo, min(hi, raw_ratio))

        deployed_value = int(current_info.get("fundamental_value") or 0)
        if deployed_value <= 0:
            continue

        shadows = {}
        for weight in BRIDGE_WEIGHTS:
            multiplier = 1.0 + weight * (clipped_ratio - 1.0)
            value = max(1, round_value(deployed_value * multiplier))
            key = f"opportunity_residual_w{int(weight * 100)}"
            shadows[key] = {
                "bridge_weight": weight,
                "multiplier": multiplier,
                "shadow_value": value,
                "change": value - deployed_value,
                "change_pct": (
                    (value - deployed_value) / deployed_value
                ),
            }

        out.append(
            {
                "player": player,
                "pos": pos,
                "age": prod.get("age"),
                "role": prod.get("role"),
                "deployed_value": deployed_value,
                "true_ppg_2025": float(true_ppg),
                "games_played_2025": games,
                "current_points_per_team_game": feature_row[
                    "current_points_per_team_game"
                ],
                "season_opportunity_share_2025": current_opp,
                "season_opportunity_share_2024": (
                    prior_opp if prior_present else None
                ),
                "opportunity_change": feature_row["opportunity_change"],
                "prior_opportunity_present": bool(prior_present),
                "control_expected_future_ppg": control_pred,
                "leader_expected_future_ppg": leader_pred,
                "raw_opportunity_residual_ratio": raw_ratio,
                "historical_ratio_p05": lo,
                "historical_ratio_p95": hi,
                "clipped_opportunity_residual_ratio": clipped_ratio,
                "ratio_was_clipped": abs(clipped_ratio - raw_ratio) > 1e-12,
                "shadows": shadows,
            }
        )

    out.sort(key=lambda r: (r["pos"], r["player"]))

    if len(out) < 350:
        raise RuntimeError(
            f"Current opportunity shadow cohort unexpectedly small: {len(out)}"
        )
    return out


def top_n_for_position(pos: str, n: int) -> int:
    if pos == "QB":
        return min(18, n)
    if pos == "TE":
        return min(15, n)
    return min(24, n)


def movement_summary(
    rows: list[dict[str, Any]],
    variant: str,
) -> dict[str, Any]:
    changes = [
        abs(float(r["shadows"][variant]["change_pct"]))
        for r in rows
    ]

    by_position = {}
    min_rho = 1.0
    min_overlap = 1.0

    for pos in TRACKED_POSITIONS:
        cohort = [r for r in rows if r["pos"] == pos]
        deployed = [float(r["deployed_value"]) for r in cohort]
        shadow = [
            float(r["shadows"][variant]["shadow_value"])
            for r in cohort
        ]
        rho = spearman(deployed, shadow)

        n_top = top_n_for_position(pos, len(cohort))
        current_sorted = sorted(
            cohort,
            key=lambda r: (-r["deployed_value"], r["player"]),
        )[:n_top]
        shadow_sorted = sorted(
            cohort,
            key=lambda r: (
                -r["shadows"][variant]["shadow_value"],
                r["player"],
            ),
        )[:n_top]
        cur_set = {r["player"] for r in current_sorted}
        shadow_set = {r["player"] for r in shadow_sorted}
        overlap = (
            len(cur_set & shadow_set) / n_top
            if n_top else 1.0
        )

        by_position[pos] = {
            "n": len(cohort),
            "rank_spearman_vs_deployed": rho,
            "top_n": n_top,
            "top_n_overlap_share": overlap,
        }

        if rho is not None:
            min_rho = min(min_rho, rho)
        min_overlap = min(min_overlap, overlap)

    return {
        "n": len(rows),
        "changed_players": sum(
            1 for r in rows
            if r["shadows"][variant]["shadow_value"] != r["deployed_value"]
        ),
        "median_abs_change_pct": percentile(changes, 0.50),
        "p90_abs_change_pct": percentile(changes, 0.90),
        "p95_abs_change_pct": percentile(changes, 0.95),
        "max_abs_change_pct": max(changes) if changes else None,
        "ratio_clipped_players": sum(
            1 for r in rows if r["ratio_was_clipped"]
        ),
        "min_position_rank_spearman": min_rho,
        "min_position_top_n_overlap": min_overlap,
        "by_position": by_position,
    }


def screen_variant(summary: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "median_abs_change_pct": (
            float(summary["median_abs_change_pct"])
            <= SCREEN_THRESHOLDS["median_abs_change_pct_max"]
        ),
        "p90_abs_change_pct": (
            float(summary["p90_abs_change_pct"])
            <= SCREEN_THRESHOLDS["p90_abs_change_pct_max"]
        ),
        "min_position_rank_spearman": (
            float(summary["min_position_rank_spearman"])
            >= SCREEN_THRESHOLDS["min_position_rank_spearman"]
        ),
        "min_position_top_n_overlap": (
            float(summary["min_position_top_n_overlap"])
            >= SCREEN_THRESHOLDS["min_position_top_n_overlap"]
        ),
    }
    return {
        "checks": checks,
        "passes_current_board_stability_screen": all(checks.values()),
    }


def largest_movers(
    rows: list[dict[str, Any]],
    variant: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        shadow = row["shadows"][variant]
        out.append(
            {
                "player": row["player"],
                "pos": row["pos"],
                "role": row["role"],
                "deployed_value": row["deployed_value"],
                "shadow_value": shadow["shadow_value"],
                "change": shadow["change"],
                "change_pct": shadow["change_pct"],
                "opportunity_2025": row[
                    "season_opportunity_share_2025"
                ],
                "opportunity_2024": row[
                    "season_opportunity_share_2024"
                ],
                "opportunity_change": row["opportunity_change"],
                "raw_ratio": row["raw_opportunity_residual_ratio"],
                "clipped_ratio": row[
                    "clipped_opportunity_residual_ratio"
                ],
                "ratio_was_clipped": row["ratio_was_clipped"],
            }
        )

    out.sort(
        key=lambda r: (
            -abs(float(r["change_pct"])),
            r["pos"],
            r["player"],
        )
    )
    return out[:limit]


def build_result() -> dict[str, Any]:
    phase1 = read_json(PHASE1_JSON)
    phase2 = read_json(PHASE2_JSON)
    production = read_json(PROD_PHASE1_JSON)
    validate_inputs(phase1, phase2, production)

    coefficients = full_sample_coefficients(phase2)
    bounds = historical_ratio_bounds(phase2)
    rows = build_current_shadow_rows(
        phase1,
        production,
        coefficients,
        bounds,
    )

    summaries = {}
    screening = {}
    movers = {}
    for weight in BRIDGE_WEIGHTS:
        variant = f"opportunity_residual_w{int(weight * 100)}"
        summaries[variant] = movement_summary(rows, variant)
        screening[variant] = screen_variant(summaries[variant])
        movers[variant] = largest_movers(rows, variant)

    survivors = [
        variant
        for variant in (
            "opportunity_residual_w25",
            "opportunity_residual_w50",
        )
        if screening[variant]["passes_current_board_stability_screen"]
    ]

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_CURRENT_PLAYER_OPPORTUNITY_SHADOW_AUDIT",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "role_mult_change_authorized": False,
        "opportunity_formula_authorized": False,
        "phase2_monitoring_leader": LEADER,
        "phase2_evidence": {
            "overall": phase2["evaluation"]["overall"][LEADER],
            "comparison_vs_control": phase2["evaluation"][
                "comparison_vs_production_only"
            ][LEADER],
        },
        "shadow_protocol": {
            "cohort": (
                "current tracked real-history QB/RB/WR/TE/DL/LB/DB with "
                "2025 opportunity evidence and production identity"
            ),
            "current_production_feature": (
                "2025 true_ppg * games_played / 17, matching historical "
                "points-per-scheduled-team-game scale"
            ),
            "residual": (
                "full-sample leader expected future PPG / full-sample "
                "production-only expected future PPG"
            ),
            "residual_winsorization": (
                "position-specific historical Phase-2 out-of-fold ratio "
                "5th/95th percentiles"
            ),
            "bridge_formula": (
                "deployed_value * (1 + weight * (clipped_ratio - 1))"
            ),
            "bridge_weights": list(BRIDGE_WEIGHTS),
            "no_history_isolated": True,
            "production_v2_frozen_unchanged": True,
        },
        "historical_full_sample_coefficients": coefficients,
        "historical_ratio_bounds": bounds,
        "screen_thresholds": SCREEN_THRESHOLDS,
        "current_shadow_cohort_size": len(rows),
        "movement_summaries": summaries,
        "screening": screening,
        "screened_survivors": survivors,
        "largest_movers": movers,
        "current_players": rows,
        "phase4_handoff": (
            "If one or more conservative bridges survive the current-board "
            "stability screen, Phase 4 should historically calibrate the bridge "
            "weight itself rather than choosing 25% or 50% from current-board "
            "appearance. Re-run the Phase-2 historical protocol with the residual "
            "bridge layered on the production-only control and select a weight "
            "using out-of-sample accuracy plus current-board stability. Do not "
            "deploy from Phase 3."
            if survivors else
            "No conservative opportunity bridge survives current-board stability. "
            "Stop this workstream or redesign the residual transformation before "
            "any prospective freeze."
        ),
    }


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def pct(value: Any, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{100.0 * float(value):.{digits}f}%"


def signed_pct(value: Any, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{100.0 * float(value):+.{digits}f}%"


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Continuous Opportunity / Role Signal V2 — Phase 3 Shadow Audit",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No deployed ROLE_MULT or player value is changed.**",
        "",
        "## Why residualize opportunity?",
        "",
        "Phase 2 already controls for current production. This shadow therefore",
        "uses only the leader/control prediction ratio, so the opportunity layer",
        "cannot simply re-add production that the deployed model already knows.",
        "",
        f"- Current shadow cohort: **{result['current_shadow_cohort_size']}**",
        "- No-history players: **isolated / unchanged**",
        "- Production V2: **frozen / unchanged**",
        "- Residual bounds: **historical position-specific OOF P05/P95**",
        "",
        "## Current-board movement",
        "",
        "| Variant | Changed | Median abs | P90 abs | Max abs | Clipped ratios | "
        "Min pos rank ρ | Min top-N overlap | Pass |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for variant in (
        "opportunity_residual_w25",
        "opportunity_residual_w50",
        "opportunity_residual_w100",
    ):
        summary = result["movement_summaries"][variant]
        passed = result["screening"][variant][
            "passes_current_board_stability_screen"
        ]
        lines.append(
            f"| `{variant}` | {summary['changed_players']} | "
            f"{pct(summary['median_abs_change_pct'])} | "
            f"{pct(summary['p90_abs_change_pct'])} | "
            f"{pct(summary['max_abs_change_pct'])} | "
            f"{summary['ratio_clipped_players']} | "
            f"{fmt(summary['min_position_rank_spearman'])} | "
            f"{pct(summary['min_position_top_n_overlap'])} | "
            f"{'PASS' if passed else 'FAIL'} |"
        )

    lines.extend(
        [
            "",
            "## Historical residual-ratio bounds",
            "",
            "| Pos | N | P05 | Median | P95 |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for pos in TRACKED_POSITIONS:
        row = result["historical_ratio_bounds"][pos]
        lines.append(
            f"| {pos} | {row['n']} | {fmt(row['p05'])} | "
            f"{fmt(row['median'])} | {fmt(row['p95'])} |"
        )

    lines.extend(
        [
            "",
            "## Largest 25% bridge movers",
            "",
            "| Player | Pos | Role | Deployed | Shadow | Δ | 2025 opp | "
            "2024 opp | Opp Δ | Ratio |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for row in result["largest_movers"]["opportunity_residual_w25"][:25]:
        lines.append(
            f"| {row['player']} | {row['pos']} | {row['role']} | "
            f"{row['deployed_value']} | {row['shadow_value']} | "
            f"{signed_pct(row['change_pct'])} | "
            f"{pct(row['opportunity_2025'])} | "
            f"{pct(row['opportunity_2024'])} | "
            f"{signed_pct(row['opportunity_change'])} | "
            f"{fmt(row['clipped_ratio'])} |"
        )

    survivors = result["screened_survivors"]
    lines.extend(
        [
            "",
            "## Screening result",
            "",
            (
                "Conservative current-board survivors: "
                + ", ".join(f"`{x}`" for x in survivors)
                if survivors
                else "Conservative current-board survivors: **none**"
            ),
            "",
            "**Passing this screen is not deployment authorization.**",
            "",
            "## Phase 4",
            "",
            result["phase4_handoff"],
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
        raise RuntimeError("Opportunity Phase-3 method mismatch")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Opportunity Phase 3 mutation guardrail failed")
    if result.get("deployment_authorized") is not False:
        raise RuntimeError("Opportunity Phase 3 unexpectedly authorizes deployment")
    if result.get("role_mult_change_authorized") is not False:
        raise RuntimeError("Opportunity Phase 3 unexpectedly authorizes ROLE_MULT")
    if result.get("opportunity_formula_authorized") is not False:
        raise RuntimeError("Opportunity Phase 3 unexpectedly authorizes formula")
    if int(result.get("current_shadow_cohort_size") or 0) < 350:
        raise RuntimeError("Opportunity Phase-3 current shadow cohort too small")

    summaries = result.get("movement_summaries") or {}
    expected = {
        "opportunity_residual_w25",
        "opportunity_residual_w50",
        "opportunity_residual_w100",
    }
    if set(summaries) != expected:
        raise RuntimeError("Opportunity Phase-3 shadow variant family mismatch")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Opportunity Phase-3 markdown missing")
    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Current-board movement",
        "Historical residual-ratio bounds",
        "Screening result",
        "Phase 4",
    ):
        if marker not in text:
            raise RuntimeError(
                f"Opportunity Phase-3 report missing marker: {marker}"
            )

    print("Continuous Opportunity V2 Phase-3 outputs passed guardrails.")


def run_selftest() -> None:
    rows = []
    for i in range(50):
        cur = i / 5.0
        opp = i / 50.0
        rows.append(
            {
                "current_points_per_team_game": cur,
                "season_opportunity_share": opp,
                "opportunity_change": opp * 0.2,
                "prior_opportunity_present": 1.0,
                "year1_points_per_team_game": 0.8 * cur + 1.5 * opp,
            }
        )

    control_beta = fit_ols(rows, CONTROL_FEATURES)
    leader_beta = fit_ols(rows, LEADER_FEATURES)
    test = rows[25]
    control = predict(control_beta, test, CONTROL_FEATURES)
    leader = predict(leader_beta, test, LEADER_FEATURES)
    assert control >= 0
    assert leader >= 0

    deployed = 5000
    ratio = 1.10
    shadow25 = round_value(deployed * (1 + 0.25 * (ratio - 1)))
    shadow50 = round_value(deployed * (1 + 0.50 * (ratio - 1)))
    assert shadow25 == 5125
    assert shadow50 == 5250

    assert abs(spearman([1, 2, 3], [10, 20, 30]) - 1.0) < 1e-9

    print(
        "Continuous Opportunity V2 Phase-3 self-test passed: full-sample OLS, "
        "residual bridge math, rounding, and rank metrics."
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

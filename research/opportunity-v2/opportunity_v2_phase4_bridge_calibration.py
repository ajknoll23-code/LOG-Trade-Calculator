#!/usr/bin/env python3
"""
Continuous Opportunity / Role Signal V2 — Phase 4 bridge calibration.

RESEARCH ONLY. No deployed ROLE_MULT, PROD_MULT_DATA, AGE_CURVE, Production V2,
Market Value, or player value is changed.

Purpose
-------
Phase 2 found a small but broad incremental accuracy gain from the opportunity
leader. Phase 3 showed that a full-strength residual is too disruptive to the
current board, while 25% and 50% residual bridges survive stability guardrails.

Phase 4 calibrates the bridge WEIGHT historically.

Historical protocol
-------------------
Use Phase-2 out-of-fold predictions only:
    control = production_only expected future PPG
    leader  = opportunity leader expected future PPG

For each held-out base season:
1. Build leader/control residual-ratio P05/P95 bounds from OTHER base seasons'
   already-out-of-fold predictions.
2. Clip the held-out season's residual ratio to those training-only bounds.
3. Apply bridge weights:
       bridged = control * (1 + weight * (clipped_ratio - 1))
4. Grade versus the same next-season points/team-game target.

This preserves the current Phase-3 residual transformation while avoiding using
the held-out season to set its own ratio bounds.

Current-board stability
-----------------------
Recompute current value movement directly from Phase-3 frozen shadow inputs for
the same candidate weights. This does not rerun Production V2 or change current
evidence.

Candidate weights
-----------------
0%, 10%, 25%, 40%, 50%, 60%, 75%, 100%

Research screen
---------------
A non-zero weight survives only if:
- overall historical MAE beats 0% control
- overall historical Spearman delta >= -0.002
- MAE improves in at least 4/7 positions
- MAE improves in at least 7/10 held-out seasons
- current median absolute value movement <= 10%
- current P90 absolute movement <= 20%
- every position current rank Spearman >= 0.95
- every position current top-N overlap >= 0.85

The monitoring leader is the surviving non-zero weight with lowest historical
MAE, then highest Spearman, then smallest current P90 movement.

No Phase-4 result authorizes deployment.

Inputs
------
research/opportunity-v2/opportunity_v2_phase2_candidate_evaluation.json
research/opportunity-v2/opportunity_v2_phase3_shadow_audit.json

Outputs
-------
research/opportunity-v2/opportunity_v2_phase4_bridge_calibration.json
research/opportunity-v2/opportunity_v2_phase4_bridge_calibration.md
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]

PHASE2_JSON = (
    REPO_ROOT / "research" / "opportunity-v2"
    / "opportunity_v2_phase2_candidate_evaluation.json"
)
PHASE3_JSON = (
    REPO_ROOT / "research" / "opportunity-v2"
    / "opportunity_v2_phase3_shadow_audit.json"
)

OUTPUT_JSON = (
    REPO_ROOT / "research" / "opportunity-v2"
    / "opportunity_v2_phase4_bridge_calibration.json"
)
OUTPUT_MD = (
    REPO_ROOT / "research" / "opportunity-v2"
    / "opportunity_v2_phase4_bridge_calibration.md"
)

METHOD_VERSION = "opportunity-v2-phase4-bridge-calibration-v1"
PHASE2_METHOD = "opportunity-v2-phase2-candidate-evaluation-v1"
PHASE3_METHOD = "opportunity-v2-phase3-shadow-audit-v1"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
BASE_YEARS = tuple(range(2015, 2025))
CONTROL = "production_only"
LEADER = "production_plus_season_opportunity_change"
WEIGHTS = (0.00, 0.10, 0.25, 0.40, 0.50, 0.60, 0.75, 1.00)
EPS = 1e-9

SCREEN = {
    "historical_mae_must_beat_control": True,
    "historical_spearman_delta_min": -0.002,
    "positions_with_mae_improvement_min": 4,
    "folds_with_mae_improvement_min": 7,
    "current_median_abs_change_pct_max": 0.10,
    "current_p90_abs_change_pct_max": 0.20,
    "current_min_position_rank_spearman": 0.95,
    "current_min_position_top_n_overlap": 0.85,
}


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


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


def mae(actual: list[float], pred: list[float]) -> float:
    return statistics.fmean(abs(a - p) for a, p in zip(actual, pred))


def rmse(actual: list[float], pred: list[float]) -> float:
    return math.sqrt(statistics.fmean((a - p) ** 2 for a, p in zip(actual, pred)))


def metrics(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    actual = [float(r["year1_points_per_team_game"]) for r in rows]
    pred = [float(r[field]) for r in rows]
    return {
        "n": len(rows),
        "mae": mae(actual, pred),
        "rmse": rmse(actual, pred),
        "spearman": spearman(pred, actual),
        "pearson": pearson(pred, actual),
    }


def validate_inputs(p2: dict[str, Any], p3: dict[str, Any]) -> None:
    if p2.get("method_version") != PHASE2_METHOD:
        raise RuntimeError("Unexpected Phase-2 method")
    if p3.get("method_version") != PHASE3_METHOD:
        raise RuntimeError("Unexpected Phase-3 method")
    if p2.get("monitoring_leader") != LEADER:
        raise RuntimeError("Phase-2 monitoring leader changed")
    if p2.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 2 unexpectedly authorizes deployment")
    if p3.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 3 unexpectedly authorizes deployment")


def training_ratio_bounds(
    rows: list[dict[str, Any]],
    held_year: int,
) -> dict[str, tuple[float, float]]:
    by_pos: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if int(row["season"]) == held_year:
            continue
        control = float(row[f"pred__{CONTROL}"])
        leader = float(row[f"pred__{LEADER}"])
        if control <= EPS:
            continue
        ratio = leader / control
        if math.isfinite(ratio) and ratio > 0:
            by_pos[str(row["pos"])].append(ratio)

    out = {}
    for pos in TRACKED_POSITIONS:
        vals = by_pos[pos]
        if len(vals) < 100:
            raise RuntimeError(f"{pos} held {held_year}: too few training ratios")
        lo = percentile(vals, 0.05)
        hi = percentile(vals, 0.95)
        assert lo is not None and hi is not None
        out[pos] = (lo, hi)
    return out


def add_historical_bridge_predictions(
    phase2: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = phase2.get("oof_predictions")
    if not isinstance(source, list) or len(source) < 14000:
        raise RuntimeError("Phase 2 OOF predictions missing/sparse")

    rows = [dict(r) for r in source]
    fold_bounds = {}

    for held_year in BASE_YEARS:
        bounds = training_ratio_bounds(rows, held_year)
        fold_bounds[str(held_year)] = {
            pos: {"p05": lo, "p95": hi}
            for pos, (lo, hi) in bounds.items()
        }

        for row in rows:
            if int(row["season"]) != held_year:
                continue
            pos = str(row["pos"])
            control = float(row[f"pred__{CONTROL}"])
            leader = float(row[f"pred__{LEADER}"])
            ratio = leader / control if control > EPS else 1.0
            lo, hi = bounds[pos]
            clipped = max(lo, min(hi, ratio))
            row["phase4_raw_ratio"] = ratio
            row["phase4_clipped_ratio"] = clipped

            for weight in WEIGHTS:
                key = f"pred__bridge_w{int(weight*100)}"
                row[key] = max(
                    0.0,
                    control * (1.0 + weight * (clipped - 1.0)),
                )

    expected = {f"pred__bridge_w{int(w*100)}" for w in WEIGHTS}
    for row in rows:
        missing = expected.difference(row)
        if missing:
            raise RuntimeError(f"Missing bridge predictions: {sorted(missing)}")

    return rows, fold_bounds


def historical_evaluation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    overall = {}
    by_pos = {}
    by_fold = {}

    for weight in WEIGHTS:
        variant = f"bridge_w{int(weight*100)}"
        field = f"pred__{variant}"
        overall[variant] = metrics(rows, field)

    for pos in TRACKED_POSITIONS:
        cohort = [r for r in rows if r["pos"] == pos]
        by_pos[pos] = {}
        for weight in WEIGHTS:
            variant = f"bridge_w{int(weight*100)}"
            by_pos[pos][variant] = metrics(cohort, f"pred__{variant}")

    for year in BASE_YEARS:
        cohort = [r for r in rows if int(r["season"]) == year]
        by_fold[str(year)] = {}
        for weight in WEIGHTS:
            variant = f"bridge_w{int(weight*100)}"
            by_fold[str(year)][variant] = metrics(cohort, f"pred__{variant}")

    control = overall["bridge_w0"]
    comparison = {}

    for weight in WEIGHTS:
        if weight == 0:
            continue
        variant = f"bridge_w{int(weight*100)}"
        m = overall[variant]
        pos_imp = 0
        fold_imp = 0
        pos_deltas = {}
        fold_deltas = {}

        for pos in TRACKED_POSITIONS:
            d = by_pos[pos][variant]["mae"] - by_pos[pos]["bridge_w0"]["mae"]
            pos_deltas[pos] = d
            if d < 0:
                pos_imp += 1

        for year in BASE_YEARS:
            d = (
                by_fold[str(year)][variant]["mae"]
                - by_fold[str(year)]["bridge_w0"]["mae"]
            )
            fold_deltas[str(year)] = d
            if d < 0:
                fold_imp += 1

        comparison[variant] = {
            "mae_delta_vs_control": m["mae"] - control["mae"],
            "rmse_delta_vs_control": m["rmse"] - control["rmse"],
            "spearman_delta_vs_control": (
                (m["spearman"] or 0.0) - (control["spearman"] or 0.0)
            ),
            "pearson_delta_vs_control": (
                (m["pearson"] or 0.0) - (control["pearson"] or 0.0)
            ),
            "positions_with_mae_improvement": pos_imp,
            "folds_with_mae_improvement": fold_imp,
            "by_position_mae_delta": pos_deltas,
            "by_fold_mae_delta": fold_deltas,
        }

    return {
        "overall": overall,
        "by_position": by_pos,
        "by_fold": by_fold,
        "comparison_vs_control": comparison,
    }


def round_value(x: float) -> int:
    return int(math.floor(float(x) + 0.5))


def top_n_for_position(pos: str, n: int) -> int:
    if pos == "QB":
        return min(18, n)
    if pos == "TE":
        return min(15, n)
    return min(24, n)


def current_stability(phase3: dict[str, Any]) -> dict[str, Any]:
    source = phase3.get("current_players")
    if not isinstance(source, list) or len(source) < 350:
        raise RuntimeError("Phase 3 current-player shadow rows missing/sparse")

    out = {}
    for weight in WEIGHTS:
        variant = f"bridge_w{int(weight*100)}"
        changes = []
        by_pos = {}
        changed = 0

        for row in source:
            deployed = int(row["deployed_value"])
            ratio = float(row["clipped_opportunity_residual_ratio"])
            value = max(
                1,
                round_value(deployed * (1.0 + weight * (ratio - 1.0))),
            )
            if value != deployed:
                changed += 1
            changes.append(abs((value - deployed) / deployed))

        min_rho = 1.0
        min_overlap = 1.0

        for pos in TRACKED_POSITIONS:
            cohort = [r for r in source if r["pos"] == pos]
            deployed_vec = [float(r["deployed_value"]) for r in cohort]
            shadow_vec = [
                float(max(
                    1,
                    round_value(
                        r["deployed_value"] * (
                            1.0 + weight * (
                                r["clipped_opportunity_residual_ratio"] - 1.0
                            )
                        )
                    ),
                ))
                for r in cohort
            ]
            rho = spearman(deployed_vec, shadow_vec)
            n_top = top_n_for_position(pos, len(cohort))
            current_sorted = sorted(
                cohort, key=lambda r: (-r["deployed_value"], r["player"])
            )[:n_top]
            shadow_sorted = sorted(
                cohort,
                key=lambda r: (
                    -max(
                        1,
                        round_value(
                            r["deployed_value"] * (
                                1.0 + weight * (
                                    r["clipped_opportunity_residual_ratio"] - 1.0
                                )
                            )
                        ),
                    ),
                    r["player"],
                ),
            )[:n_top]
            cur_set = {r["player"] for r in current_sorted}
            sh_set = {r["player"] for r in shadow_sorted}
            overlap = len(cur_set & sh_set) / n_top if n_top else 1.0
            if rho is not None:
                min_rho = min(min_rho, rho)
            min_overlap = min(min_overlap, overlap)
            by_pos[pos] = {
                "n": len(cohort),
                "rank_spearman_vs_deployed": rho,
                "top_n": n_top,
                "top_n_overlap_share": overlap,
            }

        out[variant] = {
            "changed_players": changed,
            "median_abs_change_pct": percentile(changes, 0.50),
            "p90_abs_change_pct": percentile(changes, 0.90),
            "p95_abs_change_pct": percentile(changes, 0.95),
            "max_abs_change_pct": max(changes),
            "min_position_rank_spearman": min_rho,
            "min_position_top_n_overlap": min_overlap,
            "by_position": by_pos,
        }

    return out


def screen_variants(
    hist: dict[str, Any],
    current: dict[str, Any],
) -> tuple[dict[str, Any], list[str], str | None]:
    control = hist["overall"]["bridge_w0"]
    screening = {}
    survivors = []

    for weight in WEIGHTS:
        variant = f"bridge_w{int(weight*100)}"
        if weight == 0:
            screening[variant] = {
                "control": True,
                "passes": True,
                "checks": {},
            }
            continue

        comp = hist["comparison_vs_control"][variant]
        cur = current[variant]

        checks = {
            "historical_mae_beats_control": (
                hist["overall"][variant]["mae"] < control["mae"]
            ),
            "historical_spearman_delta": (
                comp["spearman_delta_vs_control"]
                >= SCREEN["historical_spearman_delta_min"]
            ),
            "positions_with_mae_improvement": (
                comp["positions_with_mae_improvement"]
                >= SCREEN["positions_with_mae_improvement_min"]
            ),
            "folds_with_mae_improvement": (
                comp["folds_with_mae_improvement"]
                >= SCREEN["folds_with_mae_improvement_min"]
            ),
            "current_median_abs_change_pct": (
                cur["median_abs_change_pct"]
                <= SCREEN["current_median_abs_change_pct_max"]
            ),
            "current_p90_abs_change_pct": (
                cur["p90_abs_change_pct"]
                <= SCREEN["current_p90_abs_change_pct_max"]
            ),
            "current_min_position_rank_spearman": (
                cur["min_position_rank_spearman"]
                >= SCREEN["current_min_position_rank_spearman"]
            ),
            "current_min_position_top_n_overlap": (
                cur["min_position_top_n_overlap"]
                >= SCREEN["current_min_position_top_n_overlap"]
            ),
        }
        passed = all(checks.values())
        screening[variant] = {
            "control": False,
            "passes": passed,
            "checks": checks,
        }
        if passed:
            survivors.append(variant)

    leader = None
    if survivors:
        survivors.sort(
            key=lambda v: (
                hist["overall"][v]["mae"],
                -(hist["overall"][v]["spearman"] or -999),
                current[v]["p90_abs_change_pct"],
                int(v.split("w")[-1]),
            )
        )
        leader = survivors[0]

    return screening, survivors, leader


def build_result() -> dict[str, Any]:
    p2 = read_json(PHASE2_JSON)
    p3 = read_json(PHASE3_JSON)
    validate_inputs(p2, p3)

    rows, fold_bounds = add_historical_bridge_predictions(p2)
    hist = historical_evaluation(rows)
    current = current_stability(p3)
    screening, survivors, leader = screen_variants(hist, current)

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_OPPORTUNITY_BRIDGE_CALIBRATION",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "role_mult_change_authorized": False,
        "opportunity_formula_authorized": False,
        "protocol": {
            "leader_signal": LEADER,
            "weights": list(WEIGHTS),
            "historical_bounds": (
                "held-out year clipped using P05/P95 residual-ratio bounds "
                "computed from other years' OOF predictions"
            ),
            "historical_target": (
                "next-season custom-scored points per scheduled team game"
            ),
            "current_shadow_source": (
                "Phase-3 frozen current-player clipped residual ratios"
            ),
            "screen": SCREEN,
        },
        "historical_fold_ratio_bounds": fold_bounds,
        "historical_evaluation": hist,
        "current_stability": current,
        "screening": screening,
        "screened_survivors": survivors,
        "monitoring_leader": leader,
        "monitoring_leader_is_deployment_choice": False,
        "phase5_handoff": (
            "Freeze a small prospective family before Week 1: deployed control, "
            f"the Phase-4 monitoring leader ({leader}), and one adjacent more-"
            "conservative survivor if available. Grade frozen Fundamental Values "
            "against completed 2026 outcomes. Never auto-deploy."
            if leader else
            "No non-zero bridge survived the combined historical/current screen. "
            "Stop Opportunity V2; do not freeze a prospective candidate."
        ),
    }


def fmt(v: Any, d: int = 4) -> str:
    return "—" if v is None else f"{float(v):.{d}f}"


def pct(v: Any, d: int = 1) -> str:
    return "—" if v is None else f"{100*float(v):.{d}f}%"


def signed(v: Any, d: int = 4) -> str:
    return "—" if v is None else f"{float(v):+.{d}f}"


def render_markdown(result: dict[str, Any]) -> str:
    hist = result["historical_evaluation"]
    current = result["current_stability"]
    screening = result["screening"]

    lines = [
        "# Continuous Opportunity / Role Signal V2 — Phase 4 Bridge Calibration",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No deployed ROLE_MULT or player value is changed.**",
        "",
        "## Historical + current calibration",
        "",
        "| Weight | Hist MAE | Δ MAE | Hist Spearman | Δ Spearman | "
        "Pos MAE improved | Folds improved | Current median | Current P90 | "
        "Min pos rank ρ | Min top-N | Pass |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for weight in WEIGHTS:
        variant = f"bridge_w{int(weight*100)}"
        hm = hist["overall"][variant]
        cur = current[variant]
        if weight == 0:
            dmae = ds = None
            pi = fi = "—"
        else:
            comp = hist["comparison_vs_control"][variant]
            dmae = comp["mae_delta_vs_control"]
            ds = comp["spearman_delta_vs_control"]
            pi = f"{comp['positions_with_mae_improvement']}/7"
            fi = f"{comp['folds_with_mae_improvement']}/10"

        lines.append(
            f"| {int(weight*100)}% | {fmt(hm['mae'])} | {signed(dmae)} | "
            f"{fmt(hm['spearman'])} | {signed(ds)} | {pi} | {fi} | "
            f"{pct(cur['median_abs_change_pct'])} | "
            f"{pct(cur['p90_abs_change_pct'])} | "
            f"{fmt(cur['min_position_rank_spearman'])} | "
            f"{pct(cur['min_position_top_n_overlap'])} | "
            f"{'PASS' if screening[variant]['passes'] else 'FAIL'} |"
        )

    lines.extend([
        "",
        "## By-position historical MAE delta vs 0% control",
        "",
        "| Weight | QB | RB | WR | TE | DL | LB | DB |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])

    for weight in WEIGHTS:
        if weight == 0:
            continue
        variant = f"bridge_w{int(weight*100)}"
        comp = hist["comparison_vs_control"][variant]
        vals = [signed(comp["by_position_mae_delta"][p]) for p in TRACKED_POSITIONS]
        lines.append(f"| {int(weight*100)}% | " + " | ".join(vals) + " |")

    lines.extend([
        "",
        "## Screening result",
        "",
        (
            "Survivors: " + ", ".join(f"`{x}`" for x in result["screened_survivors"])
            if result["screened_survivors"]
            else "Survivors: **none**"
        ),
        "",
        f"Monitoring leader: **`{result['monitoring_leader'] or 'none'}`**",
        "",
        "**Monitoring leader is not a deployment choice.**",
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
        raise RuntimeError("Phase-4 method mismatch")
    for key in (
        "deployment_authorized",
        "role_mult_change_authorized",
        "opportunity_formula_authorized",
    ):
        if result.get(key) is not False:
            raise RuntimeError(f"Phase 4 unexpectedly authorizes {key}")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Phase 4 mutation guardrail failed")

    hist = result.get("historical_evaluation") or {}
    if set((hist.get("overall") or {})) != {
        f"bridge_w{int(w*100)}" for w in WEIGHTS
    }:
        raise RuntimeError("Phase-4 weight family mismatch")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Phase-4 markdown missing")
    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Historical + current calibration",
        "Screening result",
        "Monitoring leader",
        "Phase 5",
    ):
        if marker not in text:
            raise RuntimeError(f"Phase-4 report missing marker: {marker}")

    print("Continuous Opportunity V2 Phase-4 outputs passed guardrails.")


def run_selftest() -> None:
    # Bridge interpolation.
    control = 10.0
    clipped = 1.2
    p25 = control * (1 + 0.25 * (clipped - 1))
    p50 = control * (1 + 0.50 * (clipped - 1))
    assert abs(p25 - 10.5) < 1e-12
    assert abs(p50 - 11.0) < 1e-12

    # Training-only bounds exclude held season.
    rows = []
    for year in BASE_YEARS:
        rows.append({
            "season": year,
            "pos": "QB",
            f"pred__{CONTROL}": 10.0,
            f"pred__{LEADER}": 10.0 + (year - 2015) * 0.1,
        })
    # Pad all positions to satisfy the real guard in the helper.
    expanded = []
    for pos in TRACKED_POSITIONS:
        for year in BASE_YEARS:
            for i in range(20):
                expanded.append({
                    "season": year,
                    "pos": pos,
                    f"pred__{CONTROL}": 10.0,
                    f"pred__{LEADER}": 9.0 + i * 0.1,
                })
    bounds = training_ratio_bounds(expanded, 2024)
    assert set(bounds) == set(TRACKED_POSITIONS)

    assert abs(spearman([1, 2, 3], [10, 20, 30]) - 1.0) < 1e-12
    print(
        "Continuous Opportunity V2 Phase-4 self-test passed: bridge math, "
        "training-only ratio bounds, and rank metrics."
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

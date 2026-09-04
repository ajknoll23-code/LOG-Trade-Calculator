#!/usr/bin/env python3
"""
Durability / Availability V2 — Phase 3 current-player shadow audit.

RESEARCH ONLY. No deployed durability, PROD_MULT_DATA, Production V2,
Age Curve V2, Opportunity V2, Market Value, or player value is changed.

Purpose
-------
Phase 2 found that, on the survivor-only target, a training-fold optimized
own-history blend beat the deployed R^2 blend:
- all 7 positions
- all 10 held-out seasons
- lower MAE and higher rank correlation

Phase 3 transports only that durability change into the current 2026 value
architecture.

Isolation rule
--------------
Use Production V2 Phase 1 as a FIXED transport layer:
- current canonical 2025 shrunk PPG: fixed
- current 2026 forward projection: fixed
- history/forward 45/55 blend: fixed
- Phase-1 position replacement baseline: fixed
- prod_mult affine transform: fixed
- age / position / role safeguards: fixed

Only projected availability changes.

This avoids conflating Durability V2 with a fresh Production V2 experiment.

Variants
--------
- deployed_control: current R^2 durability weight
- trained_blend_w25: 25% bridge from deployed weight to full-sample trained weight
- trained_blend_w50: 50% bridge
- trained_blend_w100: full trained weight

Full-sample trained weights
---------------------------
After Phase-2 cross-validation validated the model class, Phase 3 refits the
simple position-specific own-history weight on ALL historical survivor-only
rows. This is used only for the current shadow; it does not revise the Phase-2
out-of-sample metrics.

Outputs
-------
research/durability-v2/durability_v2_phase3_shadow_audit.json
research/durability-v2/durability_v2_phase3_shadow_audit.md
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
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
PRODUCTION_PHASE1_JSON = (
    REPO_ROOT / "research" / "production-v2"
    / "production_v2_phase1_audit.json"
)
INDEX_HTML = REPO_ROOT / "index.html"

OUTPUT_JSON = (
    REPO_ROOT / "research" / "durability-v2"
    / "durability_v2_phase3_shadow_audit.json"
)
OUTPUT_MD = (
    REPO_ROOT / "research" / "durability-v2"
    / "durability_v2_phase3_shadow_audit.md"
)

METHOD_VERSION = "durability-v2-phase3-shadow-audit-v1"
PHASE1_METHOD = "durability-v2-phase1-availability-audit-v1"
PHASE2_METHOD = "durability-v2-phase2-candidate-evaluation-v1"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
BRIDGES = (0.25, 0.50, 1.00)
BLEND_GRID = tuple(i / 20.0 for i in range(21))

HISTORY_WEIGHT = 0.45
FORWARD_WEIGHT = 0.55
PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55
GLOBAL_VALUE_SCALE = 55.0

SCREEN = {
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


def average_ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda x: (-x[1], x[0]))
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
    return pearson(average_ranks(xs), average_ranks(ys))


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def validate_inputs(
    p1: dict[str, Any],
    p2: dict[str, Any],
    prod: dict[str, Any],
) -> None:
    if p1.get("method_version") != PHASE1_METHOD:
        raise RuntimeError("Unexpected Durability Phase-1 method")
    if p2.get("method_version") != PHASE2_METHOD:
        raise RuntimeError("Unexpected Durability Phase-2 method")
    if p2.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 2 unexpectedly authorizes deployment")

    fam = (
        p2.get("targets", {})
        .get("survivor_only", {})
        .get("families", {})
        .get("one_year", {})
    )
    if fam.get("monitoring_leader") != "trained_blend":
        raise RuntimeError(
            "Phase-2 survivor one-year leader changed; expected trained_blend"
        )
    if "players" not in prod or "phase1_baselines" not in prod:
        raise RuntimeError("Production V2 Phase-1 transport data missing")


def survivor_rows_by_position(
    phase1: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    rows = phase1.get("survivor_only_transition_rows")
    if not isinstance(rows, list):
        raise RuntimeError("Phase 1 missing survivor transition rows")
    out = {pos: [] for pos in TRACKED_POSITIONS}
    for row in rows:
        pos = str(row.get("pos") or "")
        if pos in out:
            out[pos].append(row)
    return out


def full_sample_trained_weights(
    phase1: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    grouped = survivor_rows_by_position(phase1)
    out = {}

    for pos, rows in grouped.items():
        if len(rows) < 100:
            raise RuntimeError(f"{pos}: survivor training sample too small")
        currents = [float(r["current_availability"]) for r in rows]
        median = statistics.median(currents)

        scored = []
        for weight in BLEND_GRID:
            errors = []
            for row in rows:
                pred = (
                    weight * float(row["current_availability"])
                    + (1.0 - weight) * median
                )
                errors.append(abs(float(row["next_availability"]) - pred))
            scored.append((statistics.fmean(errors), weight))

        scored.sort(key=lambda x: (x[0], abs(x[1] - 0.5), x[1]))
        best_mae, best_weight = scored[0]
        out[pos] = {
            "n": len(rows),
            "historical_position_median_availability": median,
            "trained_own_weight": best_weight,
            "training_mae": best_mae,
        }
    return out


def candidate_final_value(
    key: str,
    raw_pm: float,
    cfg: dict[str, Any],
    snapshot_values,
) -> dict[str, Any]:
    info = cfg["player_db"][key]
    pos = info["pos"]
    age = info["age"]
    role = info["role"]

    effective_pm, raw_seen = snapshot_values.production_multiplier(
        key,
        role,
        {key: raw_pm},
        cfg["no_real_history"],
        cfg["role_mult"],
    )
    age_mult = snapshot_values.effective_age_multiplier(
        pos,
        age,
        role,
        key,
        effective_pm,
        raw_seen,
        cfg,
    )
    pw = cfg["position_weight"].get(pos, 1.0)
    value = math.floor(
        100 * pw * age_mult * effective_pm * GLOBAL_VALUE_SCALE + 0.5
    )
    return {
        "value": value,
        "raw_prod_mult": raw_pm,
        "effective_prod_mult": effective_pm,
        "age_mult": age_mult,
    }


def top_n_for_position(pos: str, n: int) -> int:
    if pos == "QB":
        return min(18, n)
    if pos == "TE":
        return min(15, n)
    return min(32 if pos in {"RB", "DL", "LB", "DB"} else 36, n)


def build_shadow(
    phase1: dict[str, Any],
    prod: dict[str, Any],
) -> dict[str, Any]:
    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)
    trained = full_sample_trained_weights(phase1)

    variants = ["deployed_control"] + [
        f"trained_blend_w{int(w*100)}" for w in BRIDGES
    ]
    players = {}

    for key, rec in prod["players"].items():
        if key not in cfg["player_db"]:
            continue
        pos = rec.get("pos")
        if pos not in TRACKED_POSITIONS:
            continue

        hist = rec.get("history") or {}
        forward = rec.get("forward") or {}
        own_avail = hist.get("own_avail_2025")
        med_avail = hist.get("position_median_avail_2025")
        shrunk_ppg = hist.get("shrunk_ppg")
        forward_projection = forward.get("projection")

        # This shadow is intentionally only real-history + usable forward rows.
        if (
            own_avail is None
            or med_avail is None
            or shrunk_ppg is None
            or forward_projection is None
        ):
            continue

        deployed_weight = float(hist.get("own_weight_durability") or 0.0)
        trained_weight = float(trained[pos]["trained_own_weight"])
        baseline = float(prod["phase1_baselines"][pos]["combined_points"])

        row = {
            "player": key,
            "pos": pos,
            "age": rec.get("age"),
            "role": rec.get("role"),
            "games_played_2025": hist.get("games_played_2025"),
            "true_ppg_2025": hist.get("true_ppg_2025"),
            "own_availability_2025": float(own_avail),
            "position_median_availability_2025": float(med_avail),
            "deployed_own_weight": deployed_weight,
            "trained_own_weight": trained_weight,
            "shrunk_ppg": float(shrunk_ppg),
            "forward_projection": float(forward_projection),
            "fixed_phase1_baseline_points": baseline,
            "current_deployed_fundamental_value": (
                rec.get("current") or {}
            ).get("fundamental_value"),
            "variants": {},
        }

        weight_map = {"deployed_control": deployed_weight}
        for bridge in BRIDGES:
            weight_map[f"trained_blend_w{int(bridge*100)}"] = (
                deployed_weight
                + bridge * (trained_weight - deployed_weight)
            )

        for variant, own_weight in weight_map.items():
            projected_avail = (
                own_weight * float(own_avail)
                + (1.0 - own_weight) * float(med_avail)
            )
            projected_games = projected_avail * 17.0
            history_component = float(shrunk_ppg) * projected_games
            combined = (
                HISTORY_WEIGHT * history_component
                + FORWARD_WEIGHT * float(forward_projection)
            )
            ratio = combined / baseline
            raw_pm = clamp(
                PM_INTERCEPT + PM_RATIO_SLOPE * ratio,
                PM_MIN,
                PM_MAX,
            )
            fv = candidate_final_value(
                key,
                raw_pm,
                cfg,
                snapshot_values,
            )
            row["variants"][variant] = {
                "own_weight": own_weight,
                "projected_availability_2026": projected_avail,
                "projected_games_2026": projected_games,
                "history_component": history_component,
                "combined_points": combined,
                "ratio_to_fixed_phase1_baseline": ratio,
                **fv,
            }

        players[key] = row

    if len(players) < 350:
        raise RuntimeError(
            f"Durability Phase-3 current shadow cohort too small: {len(players)}"
        )

    return {
        "trained_weights": trained,
        "variants": variants,
        "players": players,
    }


def summarize_variant(
    players: dict[str, dict[str, Any]],
    variant: str,
) -> dict[str, Any]:
    pct_changes = []
    game_changes = []

    for row in players.values():
        control = row["variants"]["deployed_control"]
        cand = row["variants"][variant]
        cv = float(control["value"])
        vv = float(cand["value"])
        if cv > 0:
            pct_changes.append((vv - cv) / cv)
        game_changes.append(
            float(cand["projected_games_2026"])
            - float(control["projected_games_2026"])
        )

    by_position = {}
    min_rho = 1.0
    min_overlap = 1.0

    for pos in TRACKED_POSITIONS:
        cohort = [r for r in players.values() if r["pos"] == pos]
        control_vals = [
            float(r["variants"]["deployed_control"]["value"])
            for r in cohort
        ]
        candidate_vals = [
            float(r["variants"][variant]["value"])
            for r in cohort
        ]
        rho = spearman(control_vals, candidate_vals)

        n_top = top_n_for_position(pos, len(cohort))
        cur_top = {
            r["player"]
            for r in sorted(
                cohort,
                key=lambda r: (
                    -r["variants"]["deployed_control"]["value"],
                    r["player"],
                ),
            )[:n_top]
        }
        cand_top = {
            r["player"]
            for r in sorted(
                cohort,
                key=lambda r: (
                    -r["variants"][variant]["value"],
                    r["player"],
                ),
            )[:n_top]
        }
        overlap = len(cur_top & cand_top) / n_top if n_top else 1.0

        if rho is not None:
            min_rho = min(min_rho, rho)
        min_overlap = min(min_overlap, overlap)

        pos_changes = []
        pos_games = []
        for r in cohort:
            c = float(r["variants"]["deployed_control"]["value"])
            v = float(r["variants"][variant]["value"])
            if c > 0:
                pos_changes.append((v-c)/c)
            pos_games.append(
                float(r["variants"][variant]["projected_games_2026"])
                - float(r["variants"]["deployed_control"]["projected_games_2026"])
            )

        by_position[pos] = {
            "n": len(cohort),
            "median_value_change_pct": (
                statistics.median(pos_changes) if pos_changes else None
            ),
            "p90_abs_value_change_pct": percentile(
                [abs(x) for x in pos_changes], 0.90
            ),
            "median_projected_games_change": (
                statistics.median(pos_games) if pos_games else None
            ),
            "rank_spearman_vs_control": rho,
            "top_n": n_top,
            "top_n_overlap_share": overlap,
        }

    abs_changes = [abs(x) for x in pct_changes]
    return {
        "n": len(players),
        "changed_players": sum(
            1
            for r in players.values()
            if r["variants"][variant]["value"]
            != r["variants"]["deployed_control"]["value"]
        ),
        "median_value_change_pct": (
            statistics.median(pct_changes) if pct_changes else None
        ),
        "median_abs_value_change_pct": (
            statistics.median(abs_changes) if abs_changes else None
        ),
        "p90_abs_value_change_pct": percentile(abs_changes, 0.90),
        "p95_abs_value_change_pct": percentile(abs_changes, 0.95),
        "max_abs_value_change_pct": max(abs_changes) if abs_changes else None,
        "median_projected_games_change": (
            statistics.median(game_changes) if game_changes else None
        ),
        "p90_abs_projected_games_change": percentile(
            [abs(x) for x in game_changes], 0.90
        ),
        "min_position_rank_spearman": min_rho,
        "min_position_top_n_overlap": min_overlap,
        "by_position": by_position,
    }


def stability_screen(summary: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "median_abs_value_change_pct": (
            float(summary["median_abs_value_change_pct"])
            <= SCREEN["median_abs_value_change_pct_max"]
        ),
        "p90_abs_value_change_pct": (
            float(summary["p90_abs_value_change_pct"])
            <= SCREEN["p90_abs_value_change_pct_max"]
        ),
        "min_position_rank_spearman": (
            float(summary["min_position_rank_spearman"])
            >= SCREEN["min_position_rank_spearman"]
        ),
        "min_position_top_n_overlap": (
            float(summary["min_position_top_n_overlap"])
            >= SCREEN["min_position_top_n_overlap"]
        ),
    }
    return {
        "checks": checks,
        "passes_current_board_stability": all(checks.values()),
    }


def largest_movers(
    players: dict[str, dict[str, Any]],
    variant: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    out = []
    for row in players.values():
        control = row["variants"]["deployed_control"]
        cand = row["variants"][variant]
        c = float(control["value"])
        v = float(cand["value"])
        pct = (v-c)/c if c else None
        out.append({
            "player": row["player"],
            "pos": row["pos"],
            "role": row["role"],
            "games_played_2025": row["games_played_2025"],
            "own_availability_2025": row["own_availability_2025"],
            "deployed_own_weight": row["deployed_own_weight"],
            "trained_own_weight": row["trained_own_weight"],
            "control_projected_games": control["projected_games_2026"],
            "candidate_projected_games": cand["projected_games_2026"],
            "projected_games_change": (
                cand["projected_games_2026"]
                - control["projected_games_2026"]
            ),
            "control_benchmark_value": control["value"],
            "candidate_benchmark_value": cand["value"],
            "value_change_pct": pct,
        })
    out.sort(
        key=lambda r: (
            -abs(float(r["value_change_pct"] or 0.0)),
            r["player"],
        )
    )
    return out[:limit]


def build_result() -> dict[str, Any]:
    p1 = read_json(PHASE1_JSON)
    p2 = read_json(PHASE2_JSON)
    prod = read_json(PRODUCTION_PHASE1_JSON)
    validate_inputs(p1, p2, prod)

    shadow = build_shadow(p1, prod)
    summaries = {}
    screens = {}
    movers = {}

    for variant in shadow["variants"]:
        if variant == "deployed_control":
            continue
        summaries[variant] = summarize_variant(
            shadow["players"],
            variant,
        )
        screens[variant] = stability_screen(summaries[variant])
        movers[variant] = largest_movers(
            shadow["players"],
            variant,
        )

    survivors = [
        v for v in shadow["variants"]
        if v != "deployed_control"
        and screens[v]["passes_current_board_stability"]
    ]

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_DURABILITY_CURRENT_SHADOW",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "durability_change_authorized": False,
        "history_component_change_authorized": False,
        "transport_protocol": {
            "transport": "Production V2 Phase 1 fixed benchmark",
            "fixed_components": [
                "2025 shrunk PPG",
                "2026 forward projection",
                "45/55 history-forward weights",
                "Phase-1 replacement baseline",
                "prod_mult affine transform",
                "position weights",
                "age multiplier",
                "role safeguards",
                "global value scale",
            ],
            "changed_component": (
                "projected 2026 availability weight only"
            ),
            "benchmark_value_not_deployed_value": True,
        },
        "phase2_survivor_one_year_evidence": (
            p2["targets"]["survivor_only"]["families"]["one_year"]
            ["evaluation"]
        ),
        "historical_full_sample_trained_weights": (
            shadow["trained_weights"]
        ),
        "current_shadow_cohort_size": len(shadow["players"]),
        "variant_manifest": shadow["variants"],
        "movement_summaries": summaries,
        "screening": screens,
        "screened_survivors": survivors,
        "largest_movers": movers,
        "players": shadow["players"],
        "phase4_handoff": (
            "Historically calibrate the bridge between deployed R2 durability "
            "weights and the trained survivor-only weights. Use the same "
            "leave-one-base-season-out protocol as Phase 2, testing bridge "
            "fractions rather than choosing 25/50/100 from current-board "
            "appearance. Do not deploy from Phase 3."
            if survivors
            else
            "No durability bridge survived current-board stability. Stop or "
            "redesign before any prospective freeze."
        ),
    }


def fmt(v: Any, d: int = 4) -> str:
    return "—" if v is None else f"{float(v):.{d}f}"


def pct(v: Any, d: int = 1) -> str:
    return "—" if v is None else f"{100*float(v):.{d}f}%"


def signed(v: Any, d: int = 3) -> str:
    return "—" if v is None else f"{float(v):+.{d}f}"


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Durability / Availability V2 — Phase 3 Shadow Audit",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No deployed durability or player value is changed.**",
        "",
        "The value numbers below are **fixed Production-V2-Phase-1 benchmark",
        "values**, not a rewrite of current deployed Fundamental Value. This",
        "keeps every production/age/position input fixed except projected",
        "availability.",
        "",
        f"- Current real-history shadow cohort: "
        f"**{result['current_shadow_cohort_size']}**",
        "",
        "## Full-sample trained survivor-only own-history weights",
        "",
        "| Pos | N | Trained weight |",
        "|---|---:|---:|",
    ]

    for pos in TRACKED_POSITIONS:
        row = result["historical_full_sample_trained_weights"][pos]
        lines.append(
            f"| {pos} | {row['n']} | {pct(row['trained_own_weight'], 0)} |"
        )

    lines.extend([
        "",
        "## Current benchmark movement",
        "",
        "| Variant | Changed | Median abs FV | P90 abs FV | "
        "Median games Δ | P90 abs games Δ | Min pos rank ρ | "
        "Min top-N overlap | Pass |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ])

    for variant in (
        "trained_blend_w25",
        "trained_blend_w50",
        "trained_blend_w100",
    ):
        s = result["movement_summaries"][variant]
        passed = result["screening"][variant][
            "passes_current_board_stability"
        ]
        lines.append(
            f"| `{variant}` | {s['changed_players']} | "
            f"{pct(s['median_abs_value_change_pct'])} | "
            f"{pct(s['p90_abs_value_change_pct'])} | "
            f"{signed(s['median_projected_games_change'])} | "
            f"{fmt(s['p90_abs_projected_games_change'], 2)} | "
            f"{fmt(s['min_position_rank_spearman'])} | "
            f"{pct(s['min_position_top_n_overlap'])} | "
            f"{'PASS' if passed else 'FAIL'} |"
        )

    lines.extend([
        "",
        "## Largest full-strength movers",
        "",
        "| Player | Pos | GP25 | Old weight | New weight | "
        "Old proj games | New proj games | Games Δ | Benchmark FV Δ |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])

    for row in result["largest_movers"]["trained_blend_w100"][:25]:
        lines.append(
            f"| {row['player']} | {row['pos']} | "
            f"{row['games_played_2025']} | "
            f"{pct(row['deployed_own_weight'])} | "
            f"{pct(row['trained_own_weight'])} | "
            f"{fmt(row['control_projected_games'], 2)} | "
            f"{fmt(row['candidate_projected_games'], 2)} | "
            f"{signed(row['projected_games_change'], 2)} | "
            f"{pct(row['value_change_pct'])} |"
        )

    lines.extend([
        "",
        "## Screening result",
        "",
        (
            "Survivors: "
            + ", ".join(f"`{v}`" for v in result["screened_survivors"])
            if result["screened_survivors"]
            else "Survivors: **none**"
        ),
        "",
        "**Passing this screen is not deployment authorization.**",
        "",
        "## Phase 4",
        "",
        result["phase4_handoff"],
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
        raise RuntimeError("Durability Phase-3 method mismatch")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Durability Phase-3 mutation guardrail failed")

    for key in (
        "deployment_authorized",
        "durability_change_authorized",
        "history_component_change_authorized",
    ):
        if result.get(key) is not False:
            raise RuntimeError(f"Durability Phase 3 unexpectedly authorizes {key}")

    if int(result.get("current_shadow_cohort_size") or 0) < 350:
        raise RuntimeError("Durability Phase-3 shadow cohort too small")

    expected = {
        "trained_blend_w25",
        "trained_blend_w50",
        "trained_blend_w100",
    }
    if set(result.get("movement_summaries") or {}) != expected:
        raise RuntimeError("Durability Phase-3 variant family mismatch")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Durability Phase-3 markdown missing")
    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Full-sample trained survivor-only",
        "Current benchmark movement",
        "Screening result",
        "Phase 4",
    ):
        if marker not in text:
            raise RuntimeError(
                f"Durability Phase-3 report missing marker: {marker}"
            )

    print("Durability / Availability V2 Phase-3 outputs passed guardrails.")


def run_selftest() -> None:
    assert clamp(-1, 0, 1) == 0
    assert clamp(2, 0, 1) == 1
    assert abs(spearman([1,2,3], [10,20,30]) - 1.0) < 1e-12

    deployed = 0.10
    trained = 0.50
    w25 = deployed + 0.25*(trained-deployed)
    w50 = deployed + 0.50*(trained-deployed)
    assert abs(w25 - 0.20) < 1e-12
    assert abs(w50 - 0.30) < 1e-12

    own = 0.50
    med = 0.90
    old = deployed*own + (1-deployed)*med
    new = trained*own + (1-trained)*med
    assert new < old

    print(
        "Durability / Availability V2 Phase-3 self-test passed: bridge math, "
        "availability direction, clamping, and rank metrics."
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

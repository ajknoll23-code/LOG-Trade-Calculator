#!/usr/bin/env python3
"""
Age Curve V2 — Phase 4 bridge calibration.

RESEARCH ONLY. No deployed AGE_CURVE or player value is changed.

Why this phase exists
---------------------
Phase 2 showed strong historical out-of-sample value in empirical age-retention
signals. Phase 3 showed that inserting the raw retention factor directly into
the current dynasty-value age slot is too aggressive for present-day values.

Phase 4 therefore tests a BRIDGE:

    bridge_age_factor =
        deployed_age_factor
        + weight * (empirical_age_factor - deployed_age_factor)

Weights:
    25%, 50%, 75%

Empirical sources:
    empirical_position_age_k25
    empirical_tier_age_k25
    empirical_tier_age_k50

QB policies:
    all_positions  = blend QB too
    qb_control     = QB remains on deployed age factor

The same bridge is tested:
1. historically, with leave-one-base-season-out future-production predictions;
2. on the current player database, using the Phase-3 frozen shadow outputs.

This lets us find the smallest blend that preserves most historical improvement
while keeping current value/rank movement sane.

No-history isolation
--------------------
Current NO_REAL_PRODUCTION_HISTORY players remain on the deployed age factor in
all current-player bridge variants. Rookie/no-history research stays separate.

Outputs
-------
research/age-curve-v2/age_curve_v2_phase4_bridge_calibration.json
research/age-curve-v2/age_curve_v2_phase4_bridge_calibration.md

Usage
-----
python3 research/age-curve-v2/age_curve_v2_phase4_bridge_calibration.py --selftest
python3 research/age-curve-v2/age_curve_v2_phase4_bridge_calibration.py --write
python3 research/age-curve-v2/age_curve_v2_phase4_bridge_calibration.py --check
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

import requests


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]

PHASE2_SCRIPT = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase2_candidate_evaluation.py"
)
PHASE2_JSON = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase2_candidate_evaluation.json"
)
PHASE3_JSON = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase3_shadow_audit.json"
)

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase4_bridge_calibration.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase4_bridge_calibration.md"
)

METHOD_VERSION = "age-curve-v2-phase4-bridge-calibration-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
BLEND_WEIGHTS = (0.25, 0.50, 0.75)
QB_POLICIES = ("all_positions", "qb_control")

SOURCE_MAP = {
    "position_k25": "empirical_position_age_k25",
    "tier_k25": "empirical_tier_age_k25",
    "tier_k50": "empirical_tier_age_k50",
}

DEPLOYED_KEY = "deployed_age_policy_proxy"

# Current-player stability gates. These are research screening thresholds,
# not production policy.
MAX_MEDIAN_ABS_CHANGE = 0.15
MAX_P90_ABS_CHANGE = 0.30
MIN_POSITION_RANK_SPEARMAN = 0.90
MIN_TOP24_OVERLAP = 0.80


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing input: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON: {path}: {exc}") from exc


def load_module(path: Path, name: str):
    if not path.exists():
        raise RuntimeError(f"Missing module: {path.relative_to(REPO_ROOT)}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path.relative_to(REPO_ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(float(v) for v in values)
    if len(vals) == 1:
        return vals[0]
    idx = (len(vals) - 1) * clamp(q, 0.0, 1.0)
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
    denom = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    if denom <= 0:
        return None
    return sum(a*b for a, b in zip(dx, dy)) / denom


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    return pearson(rankdata(xs), rankdata(ys))


def variant_key(source: str, weight: float, qb_policy: str) -> str:
    return f"{source}__w{int(round(weight*100)):02d}__{qb_policy}"


def validate_inputs(phase2_json: dict[str, Any], phase3: dict[str, Any]) -> None:
    if phase2_json.get("method_version") != "age-curve-v2-phase2-candidate-evaluation-v1":
        raise RuntimeError("Unexpected Phase-2 method version")
    if phase3.get("method_version") != "age-curve-v2-phase3-shadow-audit-v1":
        raise RuntimeError("Unexpected Phase-3 method version")
    for payload in (phase2_json, phase3):
        if payload.get("deployment_authorized") is not False:
            raise RuntimeError("Upstream research unexpectedly authorizes deployment")
        if payload.get("age_curve_change_authorized") is not False:
            raise RuntimeError("Upstream research unexpectedly authorizes AGE_CURVE change")


def rebuild_historical_predictions(phase2):
    """
    Recreate the Phase-2 OOF prediction rows. This is intentionally the same
    historical machinery rather than a new scoring implementation.
    """
    phase1_json = phase2.read_json(phase2.PHASE1_JSON)
    phase2.validate_phase1(phase1_json)

    phase1 = phase2.load_module(phase2.PHASE1_SCRIPT, "age_curve_v2_phase1_for_p4")
    snapshot_values = phase2.load_snapshot_values()
    cfg = snapshot_values.load_from_html(phase2.INDEX_HTML)

    sess = requests.Session()
    print("Downloading nflverse player metadata...")
    players_rows = phase1.fetch_csv_rows(phase1.NFLVERSE_PLAYERS_URL, sess)

    stats_by_season = {}
    for season in phase1.STAT_YEARS:
        print(f"Downloading nflverse weekly player stats {season}...")
        stats_by_season[season] = phase1.fetch_csv_rows(
            phase1.NFLVERSE_WEEKLY_URL.format(season=season),
            sess,
        )

    scorer_module = phase1.load_phase2_module()
    metadata = phase1.build_player_metadata(players_rows)
    seasons = phase1.build_player_seasons(
        metadata,
        stats_by_season,
        scorer_module.score_nflverse_week,
    )
    phase1.assign_tiers(seasons)
    retention_rows = phase1.build_retention_rows(seasons)
    phase2.add_production_percentiles(retention_rows)

    predictions = phase2.build_cv_predictions(
        retention_rows,
        cfg,
        snapshot_values,
    )
    if len(predictions) < 10000:
        raise RuntimeError("Historical prediction rows unexpectedly sparse")
    return predictions


def add_historical_bridges(
    rows: list[dict[str, Any]],
) -> list[str]:
    keys = []
    for source_short, source_field in SOURCE_MAP.items():
        for weight in BLEND_WEIGHTS:
            for qb_policy in QB_POLICIES:
                key = variant_key(source_short, weight, qb_policy)
                keys.append(key)
                for row in rows:
                    deployed = float(row[DEPLOYED_KEY])
                    empirical = float(row[source_field])
                    use_weight = (
                        0.0 if qb_policy == "qb_control" and row["pos"] == "QB"
                        else weight
                    )
                    row[key] = deployed + use_weight * (empirical - deployed)
    return keys


def historical_metrics(phase2, rows, keys):
    actual_field = "forward_mean_points_per_team_game"
    deployed = phase2.metric_bundle(rows, DEPLOYED_KEY, actual_field)

    out = {}
    for key in keys:
        m = phase2.metric_bundle(rows, key, actual_field)
        out[key] = {
            **m,
            "mae_delta_vs_deployed": (
                m["mae"] - deployed["mae"]
                if m["mae"] is not None and deployed["mae"] is not None else None
            ),
            "spearman_delta_vs_deployed": (
                m["spearman"] - deployed["spearman"]
                if m["spearman"] is not None and deployed["spearman"] is not None else None
            ),
        }
    return deployed, out


def current_bridge_outputs(phase3: dict[str, Any], phase3_module, cfg):
    direct_variants = phase3["variants"]
    control = direct_variants["deployed_control"]["players"]

    out = {}
    for source_short, direct_key in SOURCE_MAP.items():
        empirical_players = direct_variants[direct_key]["players"]

        for weight in BLEND_WEIGHTS:
            for qb_policy in QB_POLICIES:
                key = variant_key(source_short, weight, qb_policy)
                players = {}

                for player, base in control.items():
                    emp = empirical_players[player]

                    d_age = float(base["deployed_age_mult"])
                    e_age = float(emp["shadow_age_mult"])
                    use_weight = weight

                    if qb_policy == "qb_control" and base["pos"] == "QB":
                        use_weight = 0.0
                    if base["no_real_production_history"]:
                        use_weight = 0.0

                    bridge_age = d_age + use_weight * (e_age - d_age)
                    deployed_value = int(base["deployed_value"])
                    shadow_value = phase3_module.round_value(
                        cfg["position_weight"].get(base["pos"], 1.0),
                        bridge_age,
                        float(base["effective_prod_mult"]),
                    )

                    change = shadow_value - deployed_value
                    players[player] = {
                        "pos": base["pos"],
                        "age": base["age"],
                        "role": base["role"],
                        "tier": base["production_tier_proxy"],
                        "no_real_production_history": base["no_real_production_history"],
                        "deployed_age_mult": d_age,
                        "empirical_age_mult": e_age,
                        "bridge_age_mult": bridge_age,
                        "deployed_value": deployed_value,
                        "shadow_value": shadow_value,
                        "change_pct": (
                            change / deployed_value if deployed_value else None
                        ),
                        "effective_weight": use_weight,
                    }

                out[key] = players
    return out


def summarize_current(players: dict[str, dict[str, Any]]) -> dict[str, Any]:
    changed = [
        r for r in players.values()
        if r["shadow_value"] != r["deployed_value"]
    ]
    abs_changes = [
        abs(float(r["change_pct"]))
        for r in changed
        if r["change_pct"] is not None
    ]

    by_position = {}
    for pos in TRACKED_POSITIONS:
        cohort = [(p, r) for p, r in players.items() if r["pos"] == pos]
        deployed_vals = [float(r["deployed_value"]) for _, r in cohort]
        shadow_vals = [float(r["shadow_value"]) for _, r in cohort]

        current_order = [
            p for p, _ in sorted(
                cohort, key=lambda x: (-x[1]["deployed_value"], x[0])
            )
        ]
        shadow_order = [
            p for p, _ in sorted(
                cohort, key=lambda x: (-x[1]["shadow_value"], x[0])
            )
        ]
        n_top = min(24, len(cohort))
        overlap = len(set(current_order[:n_top]) & set(shadow_order[:n_top]))

        by_position[pos] = {
            "n": len(cohort),
            "spearman_deployed_vs_shadow": spearman(deployed_vals, shadow_vals),
            "top24_overlap_share": overlap / n_top if n_top else None,
        }

    movers = sorted(
        (
            {
                "player": p,
                **r,
            }
            for p, r in players.items()
            if r["change_pct"] is not None
        ),
        key=lambda r: (-abs(float(r["change_pct"])), r["player"]),
    )[:30]

    min_pos_s = min(
        float(v["spearman_deployed_vs_shadow"])
        for v in by_position.values()
        if v["spearman_deployed_vs_shadow"] is not None
    )
    min_top = min(
        float(v["top24_overlap_share"])
        for v in by_position.values()
        if v["top24_overlap_share"] is not None
    )

    return {
        "player_count": len(players),
        "changed_count": len(changed),
        "median_abs_change_pct": median(abs_changes),
        "p90_abs_change_pct": percentile(abs_changes, 0.90),
        "min_position_rank_spearman": min_pos_s,
        "min_position_top24_overlap_share": min_top,
        "by_position": by_position,
        "largest_movers": movers,
    }


def screen_candidate(hist: dict[str, Any], cur: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "historical_mae_beats_deployed": (
            hist["mae_delta_vs_deployed"] is not None
            and hist["mae_delta_vs_deployed"] < 0
        ),
        "historical_spearman_not_worse": (
            hist["spearman_delta_vs_deployed"] is not None
            and hist["spearman_delta_vs_deployed"] >= 0
        ),
        "current_median_abs_change_le_15pct": (
            cur["median_abs_change_pct"] is not None
            and cur["median_abs_change_pct"] <= MAX_MEDIAN_ABS_CHANGE
        ),
        "current_p90_abs_change_le_30pct": (
            cur["p90_abs_change_pct"] is not None
            and cur["p90_abs_change_pct"] <= MAX_P90_ABS_CHANGE
        ),
        "every_position_rank_spearman_ge_090": (
            cur["min_position_rank_spearman"] >= MIN_POSITION_RANK_SPEARMAN
        ),
        "every_position_top24_overlap_ge_080": (
            cur["min_position_top24_overlap_share"] >= MIN_TOP24_OVERLAP
        ),
    }
    return {
        "passes_all_research_screening_gates": all(checks.values()),
        "checks": checks,
    }


def build_result():
    phase2_json = read_json(PHASE2_JSON)
    phase3 = read_json(PHASE3_JSON)
    validate_inputs(phase2_json, phase3)

    phase2 = load_module(PHASE2_SCRIPT, "age_curve_v2_phase2_for_p4")
    phase3_module = load_module(
        REPO_ROOT / "research" / "age-curve-v2" / "age_curve_v2_phase3_shadow_audit.py",
        "age_curve_v2_phase3_for_p4",
    )

    hist_rows = rebuild_historical_predictions(phase2)
    keys = add_historical_bridges(hist_rows)
    deployed_metrics, hist = historical_metrics(phase2, hist_rows, keys)

    snapshot_values = phase3_module.load_snapshot_values()
    cfg = snapshot_values.load_from_html(phase3_module.INDEX_HTML)
    current_players = current_bridge_outputs(phase3, phase3_module, cfg)
    current = {
        key: summarize_current(players)
        for key, players in current_players.items()
    }

    screening = {
        key: screen_candidate(hist[key], current[key])
        for key in keys
    }

    survivors = [
        key for key in keys
        if screening[key]["passes_all_research_screening_gates"]
    ]
    survivors.sort(
        key=lambda key: (
            float(hist[key]["mae"]),
            -float(hist[key]["spearman"]),
            float(current[key]["median_abs_change_pct"] or 999),
            key,
        )
    )

    # "Monitoring leader" is the best screened bridge, not deployment approval.
    leader = survivors[0] if survivors else None

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_AGE_BRIDGE_CALIBRATION",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "age_curve_change_authorized": False,
        "historical_protocol": {
            "cross_validation": "leave_one_base_season_out",
            "target": "mean Year+1 and Year+2 points per scheduled team game",
            "deployed_control": deployed_metrics,
        },
        "bridge_formula": (
            "deployed_age + weight * (empirical_age - deployed_age)"
        ),
        "sources": SOURCE_MAP,
        "weights": list(BLEND_WEIGHTS),
        "qb_policies": list(QB_POLICIES),
        "screening_thresholds": {
            "max_median_abs_current_value_change": MAX_MEDIAN_ABS_CHANGE,
            "max_p90_abs_current_value_change": MAX_P90_ABS_CHANGE,
            "min_every_position_rank_spearman": MIN_POSITION_RANK_SPEARMAN,
            "min_every_position_top24_overlap": MIN_TOP24_OVERLAP,
        },
        "historical_metrics": hist,
        "current_shadow_summaries": current,
        "screening": screening,
        "screened_survivors": survivors,
        "monitoring_leader": leader,
        "monitoring_leader_is_deployment_choice": False,
        "guardrail": (
            "A screened survivor only earns eligibility for a prospective freeze. "
            "It does not authorize production deployment."
        ),
        "phase5_handoff": (
            "Freeze the smallest stable survivor family before 2026 outcomes and "
            "grade against future realized production alongside the deployed control."
            if survivors else
            "No bridge met the preregistered stability gates; keep the deployed age "
            "curve and redesign the bridge before prospective testing."
        ),
    }


def fmt(v: Any, d: int = 4) -> str:
    if v is None:
        return "—"
    return f"{float(v):.{d}f}"


def pct(v: Any) -> str:
    if v is None:
        return "—"
    return f"{100*float(v):.1f}%"


def signed(v: Any, d: int = 4) -> str:
    if v is None:
        return "—"
    return f"{float(v):+.{d}f}"


def render_markdown(result):
    lines = [
        "# Age Curve V2 — Phase 4 Bridge Calibration",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No deployed AGE_CURVE or player value is changed.**",
        "",
        "Bridge formula:",
        "",
        "`deployed_age + weight × (empirical_age − deployed_age)`",
        "",
        "## Bridge results",
        "",
        "| Variant | Hist MAE | Δ MAE | Hist Spearman | Δ Spearman | "
        "Median current Δ | P90 current Δ | Min pos rank ρ | Min top-24 | Pass |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    keys = sorted(result["historical_metrics"])
    for key in keys:
        h = result["historical_metrics"][key]
        c = result["current_shadow_summaries"][key]
        s = result["screening"][key]
        lines.append(
            f"| `{key}` | {fmt(h['mae'])} | {signed(h['mae_delta_vs_deployed'])} | "
            f"{fmt(h['spearman'])} | {signed(h['spearman_delta_vs_deployed'])} | "
            f"{pct(c['median_abs_change_pct'])} | {pct(c['p90_abs_change_pct'])} | "
            f"{fmt(c['min_position_rank_spearman'])} | "
            f"{pct(c['min_position_top24_overlap_share'])} | "
            f"{'PASS' if s['passes_all_research_screening_gates'] else 'FAIL'} |"
        )

    lines.extend([
        "",
        "## Screened survivors",
        "",
    ])
    if result["screened_survivors"]:
        for i, key in enumerate(result["screened_survivors"], 1):
            lines.append(f"{i}. `{key}`")
    else:
        lines.append("**None.**")

    lines.extend([
        "",
        f"Monitoring leader: **`{result['monitoring_leader'] or 'none'}`**",
        "",
        "This is **not a deployment choice**.",
        "",
        "## Largest movers for monitoring leader",
        "",
    ])

    leader = result["monitoring_leader"]
    if leader:
        lines.extend([
            "| Player | Pos | Age | Tier | Current | Shadow | Change |",
            "|---|---|---:|---|---:|---:|---:|",
        ])
        for row in result["current_shadow_summaries"][leader]["largest_movers"][:25]:
            lines.append(
                f"| {row['player']} | {row['pos']} | {row['age']} | "
                f"{row['tier'] or 'no-history'} | {row['deployed_value']} | "
                f"{row['shadow_value']} | {pct(row['change_pct'])} |"
            )

    lines.extend([
        "",
        "## Next step",
        "",
        result["phase5_handoff"],
        "",
    ])
    return "\n".join(lines)


def write_outputs(result):
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(render_markdown(result), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


def check_outputs():
    result = read_json(OUTPUT_JSON)
    if result.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Phase-4 method mismatch")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Phase-4 production mutation guardrail failed")
    if result.get("deployment_authorized") is not False:
        raise RuntimeError("Phase-4 unexpectedly authorizes deployment")
    if result.get("age_curve_change_authorized") is not False:
        raise RuntimeError("Phase-4 unexpectedly authorizes AGE_CURVE change")

    expected = {
        variant_key(source, weight, qb)
        for source in SOURCE_MAP
        for weight in BLEND_WEIGHTS
        for qb in QB_POLICIES
    }
    if set(result.get("historical_metrics", {})) != expected:
        raise RuntimeError("Phase-4 bridge family mismatch")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Phase-4 markdown missing")
    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Bridge results",
        "Screened survivors",
        "Monitoring leader",
    ):
        if marker not in text:
            raise RuntimeError(f"Phase-4 report missing marker: {marker}")

    print("Age Curve V2 Phase-4 outputs passed guardrails.")


def run_selftest():
    d, e = 0.80, 1.20
    assert abs((d + 0.25*(e-d)) - 0.90) < 1e-9
    assert variant_key("tier_k50", 0.25, "qb_control") == "tier_k50__w25__qb_control"

    h = {"mae_delta_vs_deployed": -0.1, "spearman_delta_vs_deployed": 0.01}
    c = {
        "median_abs_change_pct": 0.10,
        "p90_abs_change_pct": 0.20,
        "min_position_rank_spearman": 0.95,
        "min_position_top24_overlap_share": 0.90,
    }
    assert screen_candidate(h, c)["passes_all_research_screening_gates"]

    print("Age Curve V2 Phase-4 self-test passed: bridge math, naming, screening.")


def main():
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

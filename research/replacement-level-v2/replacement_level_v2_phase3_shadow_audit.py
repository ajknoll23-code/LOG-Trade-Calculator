#!/usr/bin/env python3
"""
Replacement Level / Positional Scale V2 — Phase 3 current-board shadow audit.

Research-only blast-radius analysis for the Phase-2 replacement-rank shortlists.

What changes in each scenario:
    ONE position's replacement rank.

What stays fixed:
    - Production V2 Phase-1 combined production inputs
    - history / forward blend
    - no-history semantics
    - role floors
    - age logic
    - position weights
    - PM transform
    - global value scale
    - every other position's replacement rank

This is not a deployment and does not modify any frozen prospective experiment.

Outputs:
  research/replacement-level-v2/replacement_level_v2_phase3_shadow_audit.json
  research/replacement-level-v2/replacement_level_v2_phase3_shadow_audit.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

PHASE2_PATH = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase2_historical_backtest.json"
)
PRODUCTION_PHASE1_PATH = (
    REPO_ROOT
    / "research"
    / "production-v2"
    / "production_v2_phase1_audit.json"
)
INDEX_HTML = REPO_ROOT / "index.html"

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase3_shadow_audit.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase3_shadow_audit.md"
)

METHOD_VERSION = "replacement-level-v2-phase3-current-board-shadow-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")

LEGACY_RANKS = {
    "QB": 18,
    "RB": 32,
    "WR": 36,
    "TE": 15,
    "DL": 32,
    "LB": 32,
    "DB": 32,
}

PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55
GLOBAL_VALUE_SCALE = 55.0

# These are deliberately broad "do no obvious damage" gates, not calibration
# targets. Replacement-rank changes are structural and can move a whole position
# more than the player-level bridge studies did.
SAFETY_GATES = {
    "median_abs_target_value_change_pct_max": 0.30,
    "p90_abs_target_value_change_pct_max": 0.40,
    "global_spearman_min": 0.97,
    "global_top100_overlap_min": 0.90,
    "target_top100_share_delta_abs_max": 0.10,
}


def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def percentile(values, q):
    vals = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    q = clamp(float(q), 0.0, 1.0)
    idx = (len(vals) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    frac = idx - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def summarize(values):
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not vals:
        return {"n": 0}
    abs_vals = [abs(v) for v in vals]
    return {
        "n": len(vals),
        "median": statistics.median(vals),
        "median_abs": statistics.median(abs_vals),
        "p90_abs": percentile(abs_vals, 0.90),
        "p95_abs": percentile(abs_vals, 0.95),
        "max_abs": max(abs_vals),
        "min": min(vals),
        "max": max(vals),
    }


def rankdata(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def pearson(xs, ys):
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)
    if dx <= 0 or dy <= 0:
        return None
    return num / math.sqrt(dx * dy)


def spearman(xs, ys):
    if len(xs) < 3:
        return None
    return pearson(rankdata(xs), rankdata(ys))


def round_numbers(obj, digits=6):
    if isinstance(obj, dict):
        return {k: round_numbers(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_numbers(v, digits) for v in obj]
    if isinstance(obj, float):
        return round(obj, digits) if math.isfinite(obj) else None
    return obj


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def validate_inputs(phase2, production_phase1):
    if phase2.get("method_version") != "replacement-level-v2-phase2-historical-backtest-v1":
        raise RuntimeError("unexpected Replacement Level V2 Phase 2 method version")

    for field in (
        "deployment_authorized",
        "production_v2_change_authorized",
        "replacement_rank_change_authorized",
        "position_weight_change_authorized",
        "scale_change_authorized",
    ):
        if phase2.get(field) is not False:
            raise RuntimeError(f"Phase 2 guardrail changed unexpectedly: {field}")
    if phase2.get("frozen_prospective_experiments_touched") is not False:
        raise RuntimeError("Phase 2 says frozen experiments were touched")

    p1_ranks = (
        (production_phase1.get("benchmark_assumptions") or {}).get("replacement_rank")
        or {}
    )
    normalized = {k: int(v) for k, v in p1_ranks.items()}
    if normalized != LEGACY_RANKS:
        raise RuntimeError(
            f"Production V2 Phase 1 legacy ranks changed unexpectedly: {normalized}"
        )

    positions = phase2.get("positions") or {}
    for pos in TRACKED_POSITIONS:
        rec = positions.get(pos) or {}
        shortlist = rec.get("phase3_shortlist_ranks")
        if not isinstance(shortlist, list) or not shortlist:
            raise RuntimeError(f"{pos}: Phase 2 shortlist missing")
        shortlist = [int(x) for x in shortlist]
        if LEGACY_RANKS[pos] not in shortlist:
            raise RuntimeError(f"{pos}: legacy control missing from Phase 3 shortlist")


def candidate_final_value(key, raw_pm, cfg, snapshot_values):
    info = cfg["player_db"][key]
    pos = info["pos"]
    role = info["role"]
    age = info["age"]

    effective_pm, raw_pm_returned = snapshot_values.production_multiplier(
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
        raw_pm_returned,
        cfg,
    )
    pw = cfg["position_weight"].get(pos, 1.0)
    value = math.floor(
        100 * pw * age_mult * effective_pm * GLOBAL_VALUE_SCALE + 0.5
    )
    return {
        "raw_prod_mult": raw_pm,
        "effective_prod_mult": effective_pm,
        "age_mult": age_mult,
        "position_weight": pw,
        "fundamental_value": value,
        "raw_floor_hit": abs(raw_pm - PM_MIN) < 1e-12,
        "raw_ceiling_hit": abs(raw_pm - PM_MAX) < 1e-12,
    }


def scenario_for_ranks(phase1_players, ranks, cfg, snapshot_values):
    baselines = {}
    for pos in TRACKED_POSITIONS:
        cohort = [
            rec
            for rec in phase1_players.values()
            if rec.get("pos") == pos
            and rec.get("phase1_combined_points") is not None
        ]
        cohort.sort(
            key=lambda r: (-float(r["phase1_combined_points"]), r["key"])
        )
        rank = int(ranks[pos])
        if len(cohort) < rank:
            raise RuntimeError(
                f"{pos}: only {len(cohort)} complete rows for baseline rank {rank}"
            )
        anchor = cohort[rank - 1]
        points = float(anchor["phase1_combined_points"])
        if points <= 0:
            raise RuntimeError(f"{pos}: non-positive baseline points {points}")
        baselines[pos] = {
            "rank": rank,
            "player": anchor["key"],
            "combined_points": points,
            "cohort_size": len(cohort),
        }

    players = {}
    for key, rec in phase1_players.items():
        combined = rec.get("phase1_combined_points")
        if combined is None:
            players[key] = None
            continue
        pos = rec["pos"]
        baseline = baselines[pos]["combined_points"]
        ratio = float(combined) / baseline
        raw_pm = clamp(
            PM_INTERCEPT + PM_RATIO_SLOPE * ratio,
            PM_MIN,
            PM_MAX,
        )
        row = candidate_final_value(key, raw_pm, cfg, snapshot_values)
        row.update({
            "ratio_to_baseline": ratio,
            "baseline_points": baseline,
            "baseline_rank": int(ranks[pos]),
        })
        players[key] = row

    return players, baselines


def ranked_keys(players):
    rows = [
        (key, row)
        for key, row in players.items()
        if row is not None
    ]
    rows.sort(key=lambda kv: (-int(kv[1]["fundamental_value"]), kv[0]))
    return [key for key, _ in rows]


def top_overlap(control_order, candidate_order, n):
    a = set(control_order[:n])
    b = set(candidate_order[:n])
    denom = min(n, len(a), len(b))
    return len(a & b) / denom if denom else None


def position_share(order, phase1_players, pos, n):
    keys = order[:n]
    if not keys:
        return None
    return (
        sum(1 for key in keys if phase1_players[key].get("pos") == pos)
        / len(keys)
    )


def global_rank_map(order):
    return {key: i + 1 for i, key in enumerate(order)}


def build_scenario_metrics(
    pos,
    rank,
    phase1_players,
    control_players,
    candidate_players,
    control_baselines,
    candidate_baselines,
):
    control_order = ranked_keys(control_players)
    candidate_order = ranked_keys(candidate_players)
    control_rank = global_rank_map(control_order)
    candidate_rank_map = global_rank_map(candidate_order)

    non_target_mutations = []
    target_pct_changes = []
    target_pm_changes = []
    target_rank_moves = []
    target_control_values = []
    target_candidate_values = []
    floor_hits = 0
    ceiling_hits = 0
    target_n = 0

    for key, rec in phase1_players.items():
        control = control_players.get(key)
        cand = candidate_players.get(key)
        if control is None and cand is None:
            continue
        if control is None or cand is None:
            raise RuntimeError(f"{pos} rank {rank}: scenario coverage changed for {key}")

        if rec.get("pos") != pos:
            if int(control["fundamental_value"]) != int(cand["fundamental_value"]):
                non_target_mutations.append(key)
            continue

        target_n += 1
        cv = int(control["fundamental_value"])
        nv = int(cand["fundamental_value"])
        if cv:
            target_pct_changes.append((nv - cv) / cv)
        target_pm_changes.append(
            float(cand["effective_prod_mult"]) - float(control["effective_prod_mult"])
        )
        target_control_values.append(cv)
        target_candidate_values.append(nv)
        target_rank_moves.append(
            int(candidate_rank_map[key]) - int(control_rank[key])
        )
        floor_hits += int(bool(cand["raw_floor_hit"]))
        ceiling_hits += int(bool(cand["raw_ceiling_hit"]))

    if non_target_mutations:
        raise RuntimeError(
            f"{pos} rank {rank}: non-target positions changed; "
            f"sample={non_target_mutations[:10]}"
        )

    all_keys = [
        key for key in control_order
        if key in candidate_rank_map
    ]
    global_rho = spearman(
        [control_rank[k] for k in all_keys],
        [candidate_rank_map[k] for k in all_keys],
    )

    control_share_100 = position_share(control_order, phase1_players, pos, 100)
    candidate_share_100 = position_share(candidate_order, phase1_players, pos, 100)
    share_delta_100 = (
        candidate_share_100 - control_share_100
        if control_share_100 is not None and candidate_share_100 is not None
        else None
    )

    value_summary = summarize(target_pct_changes)
    rank_summary = summarize(target_rank_moves)

    gates = {
        "median_abs_target_value_change_pct": (
            value_summary.get("median_abs") is not None
            and value_summary["median_abs"]
            <= SAFETY_GATES["median_abs_target_value_change_pct_max"]
        ),
        "p90_abs_target_value_change_pct": (
            value_summary.get("p90_abs") is not None
            and value_summary["p90_abs"]
            <= SAFETY_GATES["p90_abs_target_value_change_pct_max"]
        ),
        "global_spearman": (
            global_rho is not None
            and global_rho >= SAFETY_GATES["global_spearman_min"]
        ),
        "global_top100_overlap": (
            top_overlap(control_order, candidate_order, 100) is not None
            and top_overlap(control_order, candidate_order, 100)
            >= SAFETY_GATES["global_top100_overlap_min"]
        ),
        "target_top100_share_delta": (
            share_delta_100 is not None
            and abs(share_delta_100)
            <= SAFETY_GATES["target_top100_share_delta_abs_max"]
        ),
    }

    return {
        "position": pos,
        "candidate_rank": int(rank),
        "is_legacy_control": int(rank) == LEGACY_RANKS[pos],
        "baseline": candidate_baselines[pos],
        "control_baseline": control_baselines[pos],
        "baseline_points_change_pct": (
            (
                float(candidate_baselines[pos]["combined_points"])
                - float(control_baselines[pos]["combined_points"])
            )
            / float(control_baselines[pos]["combined_points"])
        ),
        "target_player_count": target_n,
        "target_value_change_pct": value_summary,
        "target_effective_pm_delta": summarize(target_pm_changes),
        "target_global_rank_movement": rank_summary,
        "candidate_floor_share": floor_hits / target_n if target_n else None,
        "candidate_ceiling_share": ceiling_hits / target_n if target_n else None,
        "within_position_value_spearman": spearman(
            target_control_values, target_candidate_values
        ),
        "global_rank_spearman": global_rho,
        "global_top50_overlap": top_overlap(control_order, candidate_order, 50),
        "global_top100_overlap": top_overlap(control_order, candidate_order, 100),
        "control_target_share_top50": position_share(
            control_order, phase1_players, pos, 50
        ),
        "candidate_target_share_top50": position_share(
            candidate_order, phase1_players, pos, 50
        ),
        "control_target_share_top100": control_share_100,
        "candidate_target_share_top100": candidate_share_100,
        "target_share_top100_delta": share_delta_100,
        "non_target_value_mutation_count": 0,
        "safety_gates": gates,
        "board_safety_pass": all(gates.values()),
    }


def candidate_primary_mae(phase2_pos, rank):
    window = (
        phase2_pos.get("all_candidate_metrics_by_window", {})
        .get("4", {})
        .get("candidates", {})
        .get(str(rank), {})
    )
    value = window.get("median_mae")
    return float(value) if value is not None else None


def build_result():
    phase2 = read_json(PHASE2_PATH)
    production_phase1 = read_json(PRODUCTION_PHASE1_PATH)
    validate_inputs(phase2, production_phase1)

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)
    phase1_players = production_phase1.get("players")
    if not isinstance(phase1_players, dict):
        raise RuntimeError("Production V2 Phase 1 JSON missing players object")

    control_players, control_baselines = scenario_for_ranks(
        phase1_players,
        LEGACY_RANKS,
        cfg,
        snapshot_values,
    )

    # Critical isolation gate: control reconstruction must reproduce Production V2
    # Phase 1 exactly before any replacement-rank shadow is trusted.
    mismatches = []
    max_delta = 0
    for key, rec in phase1_players.items():
        p1 = rec.get("candidate")
        ctl = control_players.get(key)
        if p1 is None and ctl is None:
            continue
        if p1 is None or ctl is None:
            mismatches.append(key)
            continue
        delta = int(ctl["fundamental_value"]) - int(p1["value"])
        max_delta = max(max_delta, abs(delta))
        if delta != 0:
            mismatches.append(key)
    if mismatches:
        raise RuntimeError(
            "Legacy-rank control does not reproduce Production V2 Phase 1; "
            f"sample={mismatches[:10]}"
        )

    positions = {}
    for pos in TRACKED_POSITIONS:
        p2 = phase2["positions"][pos]
        shortlist = [int(x) for x in p2["phase3_shortlist_ranks"]]
        scenarios = {}

        for rank in shortlist:
            ranks = dict(LEGACY_RANKS)
            ranks[pos] = rank
            candidate_players, candidate_baselines = scenario_for_ranks(
                phase1_players,
                ranks,
                cfg,
                snapshot_values,
            )
            metrics = build_scenario_metrics(
                pos,
                rank,
                phase1_players,
                control_players,
                candidate_players,
                control_baselines,
                candidate_baselines,
            )
            metrics["phase2_primary_median_mae"] = candidate_primary_mae(p2, rank)
            metrics["phase2_primary_mae_vs_legacy_pct"] = None
            legacy_mae = candidate_primary_mae(p2, LEGACY_RANKS[pos])
            if metrics["phase2_primary_median_mae"] is not None and legacy_mae:
                metrics["phase2_primary_mae_vs_legacy_pct"] = (
                    metrics["phase2_primary_median_mae"] - legacy_mae
                ) / legacy_mae
            scenarios[str(rank)] = metrics

        safe_noncontrol = [
            rec for rec in scenarios.values()
            if not rec["is_legacy_control"]
            and rec["board_safety_pass"]
            and rec["phase2_primary_median_mae"] is not None
        ]
        safe_noncontrol.sort(
            key=lambda rec: (
                float(rec["phase2_primary_median_mae"]),
                abs(int(rec["candidate_rank"]) - LEGACY_RANKS[pos]),
                int(rec["candidate_rank"]),
            )
        )
        recommended = safe_noncontrol[0]["candidate_rank"] if safe_noncontrol else LEGACY_RANKS[pos]

        positions[pos] = {
            "legacy_control_rank": LEGACY_RANKS[pos],
            "phase2_primary_leader_rank": int(p2["primary_leader_rank"]),
            "phase2_shortlist_ranks": shortlist,
            "recommended_rank_for_phase4": int(recommended),
            "recommended_is_noncontrol": int(recommended) != LEGACY_RANKS[pos],
            "scenarios": scenarios,
        }

    return round_numbers({
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_CURRENT_BOARD_SHADOW_AUDIT",
        "deployment_authorized": False,
        "production_v2_change_authorized": False,
        "replacement_rank_change_authorized": False,
        "position_weight_change_authorized": False,
        "transform_change_authorized": False,
        "scale_change_authorized": False,
        "frozen_prospective_experiments_touched": False,
        "scope": {
            "scenario_strategy": "one position at a time",
            "all_non_target_replacement_ranks": "legacy control",
            "position_weights": "held fixed from index.html",
            "pm_transform": {
                "intercept": PM_INTERCEPT,
                "ratio_slope": PM_RATIO_SLOPE,
                "min": PM_MIN,
                "max": PM_MAX,
            },
            "global_value_scale": GLOBAL_VALUE_SCALE,
        },
        "safety_gates": SAFETY_GATES,
        "isolation_gate": {
            "legacy_control_exactly_reproduces_production_v2_phase1": True,
            "max_fundamental_value_reproduction_delta": max_delta,
        },
        "positions": positions,
        "input_sha256": {
            str(PHASE2_PATH.relative_to(REPO_ROOT)): sha256(PHASE2_PATH),
            str(PRODUCTION_PHASE1_PATH.relative_to(REPO_ROOT)): sha256(
                PRODUCTION_PHASE1_PATH
            ),
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
        },
        "next_step": (
            "Phase 4 should use only board-safe historically supported replacement "
            "ranks, then audit PM transform/global scale and cross-position economics "
            "without changing POSITION_WEIGHT in the same calibration."
        ),
    })


def fmt(value, digits=3):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def fmt_pct(value):
    if value is None:
        return "—"
    return f"{100.0 * float(value):+.1f}%"


def render_md(result):
    lines = [
        "# Replacement Level / Positional Scale V2 — Phase 3 Current-Board Shadow Audit",
        "",
        "**Research only. No deployment or frozen prospective experiment is changed.**",
        "",
        f"Method: `{result['method_version']}`",
        "",
        "## Isolation",
        "",
        "- Legacy-rank reconstruction reproduces Production V2 Phase 1 exactly: **Yes**",
        f"- Maximum fundamental-value reproduction delta: **{result['isolation_gate']['max_fundamental_value_reproduction_delta']}**",
        "- Every scenario changes **one position's replacement rank only**.",
        "",
        "## Summary",
        "",
        "| Pos | Legacy | Phase-2 leader | Phase-3 shortlist | Board-safe recommendation | Leader safety | Median FV Δ | P90 abs FV Δ | Global ρ | Top100 overlap | Top100 share Δ |",
        "|---|---:|---:|---|---:|---|---:|---:|---:|---:|---:|",
    ]

    for pos in TRACKED_POSITIONS:
        p = result["positions"][pos]
        leader = p["scenarios"][str(p["phase2_primary_leader_rank"])]
        lines.append(
            f"| {pos} | {p['legacy_control_rank']} | {p['phase2_primary_leader_rank']} | "
            f"{', '.join(str(x) for x in p['phase2_shortlist_ranks'])} | "
            f"{p['recommended_rank_for_phase4']} | "
            f"{'PASS' if leader['board_safety_pass'] else 'FAIL'} | "
            f"{fmt_pct(leader['target_value_change_pct'].get('median'))} | "
            f"{fmt_pct(leader['target_value_change_pct'].get('p90_abs'))} | "
            f"{fmt(leader['global_rank_spearman'], 4)} | "
            f"{fmt_pct(leader['global_top100_overlap'])} | "
            f"{fmt_pct(leader['target_share_top100_delta'])} |"
        )

    lines += ["", "## Scenario detail", ""]

    for pos in TRACKED_POSITIONS:
        p = result["positions"][pos]
        lines += [
            f"### {pos}",
            "",
            f"- Legacy control: **{p['legacy_control_rank']}**",
            f"- Phase-2 historical leader: **{p['phase2_primary_leader_rank']}**",
            f"- Board-safe recommendation for Phase 4: **{p['recommended_rank_for_phase4']}**",
            "",
            "| Rank | Hist MAE | Hist Δ vs legacy | Baseline pts Δ | Median FV Δ | P90 abs FV Δ | P95 abs FV Δ | Global ρ | Top50 overlap | Top100 overlap | Top100 pos-share Δ | Safety |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        for rank in p["phase2_shortlist_ranks"]:
            s = p["scenarios"][str(rank)]
            lines.append(
                f"| {rank} | {fmt(s['phase2_primary_median_mae'], 4)} | "
                f"{fmt_pct(s['phase2_primary_mae_vs_legacy_pct'])} | "
                f"{fmt_pct(s['baseline_points_change_pct'])} | "
                f"{fmt_pct(s['target_value_change_pct'].get('median'))} | "
                f"{fmt_pct(s['target_value_change_pct'].get('p90_abs'))} | "
                f"{fmt_pct(s['target_value_change_pct'].get('p95_abs'))} | "
                f"{fmt(s['global_rank_spearman'], 4)} | "
                f"{fmt_pct(s['global_top50_overlap'])} | "
                f"{fmt_pct(s['global_top100_overlap'])} | "
                f"{fmt_pct(s['target_share_top100_delta'])} | "
                f"{'PASS' if s['board_safety_pass'] else 'FAIL'} |"
            )
        lines.append("")

    lines += [
        "## Safety gates",
        "",
        f"- median absolute target-position FV change ≤ **{100*SAFETY_GATES['median_abs_target_value_change_pct_max']:.0f}%**",
        f"- P90 absolute target-position FV change ≤ **{100*SAFETY_GATES['p90_abs_target_value_change_pct_max']:.0f}%**",
        f"- global Spearman rank correlation ≥ **{SAFETY_GATES['global_spearman_min']:.2f}**",
        f"- global top-100 overlap ≥ **{100*SAFETY_GATES['global_top100_overlap_min']:.0f}%**",
        f"- absolute target-position top-100 share change ≤ **{100*SAFETY_GATES['target_top100_share_delta_abs_max']:.0f} percentage points**",
        "",
        "These are broad damage-control gates, not evidence that a candidate is calibrated.",
        "",
        "## Guardrails",
        "",
        "- deployment_authorized: **false**",
        "- production_v2_change_authorized: **false**",
        "- replacement_rank_change_authorized: **false**",
        "- position_weight_change_authorized: **false**",
        "- transform_change_authorized: **false**",
        "- scale_change_authorized: **false**",
        "- frozen prospective experiments touched: **false**",
        "",
        "## Next step",
        "",
        "Phase 4 will carry only historically supported, board-safe replacement ranks "
        "into a separate PM-transform/global-scale audit. POSITION_WEIGHT remains "
        "fixed so replacement normalization and positional economics stay identifiable.",
        "",
    ]
    return "\n".join(lines)


def run_selftest():
    assert abs(spearman([1, 2, 3], [3, 2, 1]) + 1.0) < 1e-12
    assert top_overlap(["a", "b", "c"], ["a", "c", "d"], 2) == 0.5
    s = summarize([-0.1, 0.2, -0.3])
    assert abs(s["median_abs"] - 0.2) < 1e-12
    print("PASS Replacement Level V2 Phase 3 self-test.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        if not args.write and not args.check:
            return

    result = build_result()
    rendered_json = json.dumps(result, indent=2, sort_keys=True) + "\n"
    rendered_md = render_md(result).rstrip() + "\n"

    if args.write:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(rendered_json, encoding="utf-8")
        OUTPUT_MD.write_text(rendered_md, encoding="utf-8")
        print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
        print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")

    if args.check:
        if not OUTPUT_JSON.exists() or not OUTPUT_MD.exists():
            raise RuntimeError("Phase 3 outputs do not exist; run --write first")
        if OUTPUT_JSON.read_text(encoding="utf-8") != rendered_json:
            raise RuntimeError("Phase 3 JSON is stale or non-deterministic")
        if OUTPUT_MD.read_text(encoding="utf-8") != rendered_md:
            raise RuntimeError("Phase 3 Markdown is stale or non-deterministic")
        for field in (
            "deployment_authorized",
            "production_v2_change_authorized",
            "replacement_rank_change_authorized",
            "position_weight_change_authorized",
            "transform_change_authorized",
            "scale_change_authorized",
        ):
            if result.get(field) is not False:
                raise RuntimeError(f"guardrail failed: {field}")
        if result.get("frozen_prospective_experiments_touched") is not False:
            raise RuntimeError("frozen experiment guardrail failed")
        if not result["isolation_gate"][
            "legacy_control_exactly_reproduces_production_v2_phase1"
        ]:
            raise RuntimeError("control reproduction gate failed")
        print("PASS Replacement Level V2 Phase 3 checks.")

    if not args.write and not args.check and not args.selftest:
        print(rendered_md)


if __name__ == "__main__":
    main()

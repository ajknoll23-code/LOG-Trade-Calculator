#!/usr/bin/env python3
"""
Replacement Level / Positional Scale V2 — Phase 4 combined-board and
transform/scale identifiability audit.

Research only.

Phase 1 established the league-economics candidate grids.
Phase 2 historically tested replacement ranks one position at a time.
Phase 3 proved the shortlisted ranks are individually safe on the current board.

Phase 4 now:
1. combines the shortlisted replacement-rank families on one board;
2. quantifies total and cross-position blast radius;
3. audits raw-PM floor/ceiling/rescue interactions;
4. proves which remaining constants are NOT identified by the available target;
5. emits the exact replacement-rank families that may be prospectively frozen
   in Phase 5.

This phase deliberately does NOT optimize:
- affine PM slope/intercept,
- hard floor/ceiling,
- POSITION_WEIGHT,
- global value scale.

Why:
The historical Phase-2 target is future relative production. It can identify
which denominator/replacement rank best predicts that future relative structure,
but it contains no observed absolute dynasty-value target capable of identifying
the multiplicative global value scale. Likewise, an arbitrary monotone affine
mapping from production ratio to "dynasty PM" is not identified absent an
external value target; floor/ceiling compression is already frozen for
prospective testing in Production V2 Phase 9.

Outputs:
  research/replacement-level-v2/replacement_level_v2_phase4_combined_identifiability_audit.json
  research/replacement-level-v2/replacement_level_v2_phase4_combined_identifiability_audit.md
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]

PHASE2_PATH = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase2_historical_backtest.json"
)
PHASE3_PATH = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase3_shadow_audit.json"
)
PHASE3_PY = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase3_shadow_audit.py"
)
PRODUCTION_PHASE1_PATH = (
    REPO_ROOT
    / "research"
    / "production-v2"
    / "production_v2_phase1_audit.json"
)
PRODUCTION_PHASE6_PATH = (
    REPO_ROOT
    / "research"
    / "production-v2"
    / "production_v2_phase6_transform_compression_audit.json"
)
PRODUCTION_PHASE9_PATH = (
    REPO_ROOT
    / "research"
    / "production-v2"
    / "production_v2_phase9_preseason_candidates.json"
)
INDEX_HTML = REPO_ROOT / "index.html"

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase4_combined_identifiability_audit.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase4_combined_identifiability_audit.md"
)

METHOD_VERSION = "replacement-level-v2-phase4-combined-identifiability-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")

EXPECTED_PHASE2_METHOD = "replacement-level-v2-phase2-historical-backtest-v1"
EXPECTED_PHASE3_METHOD = "replacement-level-v2-phase3-current-board-shadow-v2"

CURRENT_TRANSFORM = {
    "intercept": -0.10,
    "ratio_slope": 0.75,
    "floor": 0.15,
    "ceiling": 1.55,
}
CURRENT_GLOBAL_SCALE = 55.0
SCALE_SENSITIVITY = (45.0, 55.0, 65.0)

# Combined-board gates are intentionally broad. These are damage-control
# constraints only; passing them does not establish calibration.
COMBINED_SAFETY_GATES = {
    "global_rank_spearman_min": 0.94,
    "global_top100_overlap_min": 0.82,
    "p90_abs_all_player_fv_change_pct_max": 0.50,
    "max_abs_position_share_top100_delta": 0.12,
}


def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(values):
    out = []
    for value in values:
        try:
            x = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            out.append(x)
    return out


def percentile(values, q):
    vals = sorted(finite(values))
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    q = max(0.0, min(1.0, float(q)))
    idx = (len(vals) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    frac = idx - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def summarize(values):
    vals = finite(values)
    if not vals:
        return {"n": 0}
    abs_vals = [abs(x) for x in vals]
    return {
        "n": len(vals),
        "median": statistics.median(vals),
        "median_abs": statistics.median(abs_vals),
        "p90_abs": percentile(abs_vals, 0.90),
        "p95_abs": percentile(abs_vals, 0.95),
        "min": min(vals),
        "max": max(vals),
        "max_abs": max(abs_vals),
    }


def round_numbers(obj, digits=6):
    if isinstance(obj, dict):
        return {k: round_numbers(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_numbers(v, digits) for v in obj]
    if isinstance(obj, float):
        return round(obj, digits) if math.isfinite(obj) else None
    return obj


def load_phase3_module():
    if not PHASE3_PY.exists():
        raise RuntimeError(f"missing {PHASE3_PY.relative_to(REPO_ROOT)}")
    spec = importlib.util.spec_from_file_location(
        "replacement_level_v2_phase3_module", PHASE3_PY
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import Phase 3 module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_snapshot_values():
    scripts = REPO_ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def validate_inputs(phase2, phase3, production_phase1, phase3mod):
    if phase2.get("method_version") != EXPECTED_PHASE2_METHOD:
        raise RuntimeError("unexpected Phase 2 method version")
    if phase3.get("method_version") != EXPECTED_PHASE3_METHOD:
        raise RuntimeError("unexpected Phase 3 method version")

    for doc_name, doc in (("Phase 2", phase2), ("Phase 3", phase3)):
        for field in (
            "deployment_authorized",
            "production_v2_change_authorized",
            "replacement_rank_change_authorized",
            "position_weight_change_authorized",
            "scale_change_authorized",
        ):
            if doc.get(field) is not False:
                raise RuntimeError(f"{doc_name} guardrail changed: {field}")
        if doc.get("frozen_prospective_experiments_touched") is not False:
            raise RuntimeError(f"{doc_name} says frozen experiments were touched")

    if phase3.get("transform_change_authorized") is not False:
        raise RuntimeError("Phase 3 transform guardrail changed")

    isolation = phase3.get("isolation_gate") or {}
    if isolation.get("legacy_control_exactly_reproduces_production_v2_phase1") is not True:
        raise RuntimeError("Phase 3 control reproduction was not exact")
    if int(isolation.get("max_fundamental_value_reproduction_delta", -1)) != 0:
        raise RuntimeError("Phase 3 control reproduction delta is nonzero")
    if isolation.get("index_html_sha_matches_phase1_input") is not True:
        raise RuntimeError("Phase 3 index SHA gate did not pass")

    if tuple(phase3mod.TRACKED_POSITIONS) != TRACKED_POSITIONS:
        raise RuntimeError("Phase 3 tracked positions changed")
    if dict(phase3mod.LEGACY_RANKS) != {
        "QB": 18, "RB": 32, "WR": 36, "TE": 15,
        "DL": 32, "LB": 32, "DB": 32,
    }:
        raise RuntimeError("Phase 3 legacy ranks changed unexpectedly")

    recorded_index_sha = (production_phase1.get("input_sha256") or {}).get("index.html")
    if not recorded_index_sha or recorded_index_sha != sha256(INDEX_HTML):
        raise RuntimeError(
            "index.html no longer matches the Production V2 Phase 1 input snapshot"
        )

    for required in (PRODUCTION_PHASE6_PATH, PRODUCTION_PHASE9_PATH):
        if not required.exists():
            raise RuntimeError(
                f"required frozen transform context missing: {required.relative_to(REPO_ROOT)}"
            )


def build_rank_families(phase2, phase3, legacy):
    full = {}
    stable_only = {}
    prior = {}

    for pos in TRACKED_POSITIONS:
        p2 = phase2["positions"][pos]
        p3 = phase3["positions"][pos]

        rec = int(p3["recommended_rank_for_phase4"])
        if not p3.get("recommended_is_noncontrol") and rec != int(legacy[pos]):
            raise RuntimeError(f"{pos}: malformed Phase 3 recommendation metadata")

        # Every carried non-control recommendation must itself have passed the
        # current-board safety gates in Phase 3.
        scenario = p3["scenarios"][str(rec)]
        if not scenario.get("board_safety_pass"):
            raise RuntimeError(f"{pos}: recommended rank {rec} was not board-safe")

        full[pos] = rec
        stable = bool(p2.get("stable_same_leader_across_2_4_6_week_windows"))
        stable_only[pos] = rec if stable else int(legacy[pos])
        prior[pos] = int(p2["prior_limited_evidence_rank"])

    families = {
        "legacy_control": dict(legacy),
        "prior_limited_evidence": prior,
        "stable_positions_only": stable_only,
        "full_phase2_leaders": full,
    }

    # Ensure the variants are distinct; otherwise a redundant prospective arm
    # would add no information.
    seen = {}
    for name, ranks in families.items():
        key = tuple((p, int(ranks[p])) for p in TRACKED_POSITIONS)
        if key in seen:
            raise RuntimeError(
                f"redundant rank families: {name} duplicates {seen[key]}"
            )
        seen[key] = name

    return families


def ranked_keys(players):
    rows = [(k, r) for k, r in players.items() if r is not None]
    rows.sort(key=lambda kv: (-int(kv[1]["fundamental_value"]), kv[0]))
    return [k for k, _ in rows]


def rank_map(order):
    return {key: i + 1 for i, key in enumerate(order)}


def top_overlap(a_order, b_order, n):
    a = set(a_order[:n])
    b = set(b_order[:n])
    denom = min(n, len(a), len(b))
    return len(a & b) / denom if denom else None


def top_position_shares(order, phase1_players, n):
    keys = order[:n]
    if not keys:
        return {p: None for p in TRACKED_POSITIONS}
    return {
        p: sum(1 for key in keys if phase1_players[key]["pos"] == p) / len(keys)
        for p in TRACKED_POSITIONS
    }


def is_role_rescue(key, rec, cfg, phase1_players):
    if rec is None:
        return False
    role = phase1_players[key]["role"]
    raw_pm = rec["raw_prod_mult"]
    eff_pm = rec["effective_prod_mult"]
    return bool(
        key in cfg["no_real_history"]
        and role != "Elite"
        and raw_pm is not None
        and float(raw_pm) <= CURRENT_TRANSFORM["floor"] + 1e-12
        and eff_pm is not None
        and float(eff_pm) > float(raw_pm) + 1e-12
    )


def compression_by_position(players, cfg, phase1_players):
    out = {}
    for pos in TRACKED_POSITIONS:
        keys = [
            key for key, p in phase1_players.items()
            if p["pos"] == pos and players.get(key) is not None
        ]
        if not keys:
            out[pos] = {"n": 0}
            continue
        floors = sum(bool(players[k]["raw_floor_hit"]) for k in keys)
        ceilings = sum(bool(players[k]["raw_ceiling_hit"]) for k in keys)
        rescues = sum(is_role_rescue(k, players[k], cfg, phase1_players) for k in keys)
        out[pos] = {
            "n": len(keys),
            "raw_floor_count": floors,
            "raw_floor_share": floors / len(keys),
            "raw_ceiling_count": ceilings,
            "raw_ceiling_share": ceilings / len(keys),
            "current_semantics_role_rescue_count": rescues,
            "current_semantics_role_rescue_share": rescues / len(keys),
        }
    return out


def board_metrics(name, ranks, players, control_players, cfg, phase1_players, phase3mod):
    control_order = ranked_keys(control_players)
    order = ranked_keys(players)
    control_rank = rank_map(control_order)
    rank = rank_map(order)

    all_pct = []
    per_pos_pct = {p: [] for p in TRACKED_POSITIONS}
    rank_moves = []
    movers = []

    for key in control_order:
        ctl = control_players.get(key)
        cand = players.get(key)
        if ctl is None or cand is None:
            raise RuntimeError(f"{name}: scenario coverage changed for {key}")
        cv = int(ctl["fundamental_value"])
        nv = int(cand["fundamental_value"])
        pct = ((nv - cv) / cv) if cv else None
        if pct is not None:
            all_pct.append(pct)
            per_pos_pct[phase1_players[key]["pos"]].append(pct)
            movers.append({
                "player": key,
                "pos": phase1_players[key]["pos"],
                "control_value": cv,
                "scenario_value": nv,
                "change_pct": pct,
                "control_rank": control_rank[key],
                "scenario_rank": rank[key],
                "rank_move": rank[key] - control_rank[key],
            })
        rank_moves.append(rank[key] - control_rank[key])

    movers.sort(key=lambda r: (-abs(r["change_pct"]), r["player"]))

    ctl_share100 = top_position_shares(control_order, phase1_players, 100)
    cand_share100 = top_position_shares(order, phase1_players, 100)
    share_delta = {
        p: cand_share100[p] - ctl_share100[p]
        for p in TRACKED_POSITIONS
    }

    rho = phase3mod.spearman(
        [control_rank[k] for k in control_order],
        [rank[k] for k in control_order],
    )
    overlap100 = top_overlap(control_order, order, 100)
    all_summary = summarize(all_pct)
    max_abs_share_delta = max(abs(v) for v in share_delta.values())

    gates = {
        "global_rank_spearman": (
            rho is not None
            and rho >= COMBINED_SAFETY_GATES["global_rank_spearman_min"]
        ),
        "global_top100_overlap": (
            overlap100 is not None
            and overlap100 >= COMBINED_SAFETY_GATES["global_top100_overlap_min"]
        ),
        "p90_abs_all_player_fv_change_pct": (
            all_summary.get("p90_abs") is not None
            and all_summary["p90_abs"]
            <= COMBINED_SAFETY_GATES["p90_abs_all_player_fv_change_pct_max"]
        ),
        "max_abs_position_share_top100_delta": (
            max_abs_share_delta
            <= COMBINED_SAFETY_GATES["max_abs_position_share_top100_delta"]
        ),
    }

    control_rescue = {
        key for key in control_order
        if is_role_rescue(key, control_players[key], cfg, phase1_players)
    }
    scenario_rescue = {
        key for key in order
        if is_role_rescue(key, players[key], cfg, phase1_players)
    }

    return {
        "name": name,
        "replacement_ranks": {p: int(ranks[p]) for p in TRACKED_POSITIONS},
        "candidate_player_count": len(order),
        "global_rank_spearman": rho,
        "global_top50_overlap": top_overlap(control_order, order, 50),
        "global_top100_overlap": overlap100,
        "all_player_fv_change_pct": all_summary,
        "global_rank_movement": summarize(rank_moves),
        "position_fv_change_pct": {
            p: summarize(per_pos_pct[p]) for p in TRACKED_POSITIONS
        },
        "control_top100_position_share": ctl_share100,
        "scenario_top100_position_share": cand_share100,
        "top100_position_share_delta": share_delta,
        "max_abs_top100_position_share_delta": max_abs_share_delta,
        "compression": compression_by_position(
            players, cfg, phase1_players
        ),
        "current_semantics_role_rescues": {
            "control_count": len(control_rescue),
            "scenario_count": len(scenario_rescue),
            "new_crossings": sorted(scenario_rescue - control_rescue),
            "removed_crossings": sorted(control_rescue - scenario_rescue),
        },
        "largest_absolute_movers": movers[:30],
        "safety_gates": gates,
        "combined_board_safety_pass": all(gates.values()),
    }


def scale_identifiability(reference_players, phase1_players):
    rows = [
        (key, rec)
        for key, rec in reference_players.items()
        if rec is not None
    ]
    if not rows:
        raise RuntimeError("no reference players for scale audit")

    # Pre-round value is K_i * scale. For any positive scale, ordering of K_i
    # is mathematically identical. The historical replacement target never
    # consumes this scale, so there is no loss function here that can select it.
    base_factor = {
        key: (
            100.0
            * float(rec["position_weight"])
            * float(rec["age_mult"])
            * float(rec["effective_prod_mult"])
        )
        for key, rec in rows
    }

    ref_scale = CURRENT_GLOBAL_SCALE
    ref_values = {
        key: math.floor(base_factor[key] * ref_scale + 0.5)
        for key in base_factor
    }
    ref_order = sorted(ref_values, key=lambda k: (-ref_values[k], k))
    ref_rank = rank_map(ref_order)

    sensitivity = {}
    for scale in SCALE_SENSITIVITY:
        values = {
            key: math.floor(base_factor[key] * scale + 0.5)
            for key in base_factor
        }
        order = sorted(values, key=lambda k: (-values[k], k))
        rmap = rank_map(order)
        rho = None
        if len(order) >= 3:
            # Local simple Spearman implementation via ranks from the fixed
            # deterministic integer board.
            xs = [ref_rank[k] for k in ref_order]
            ys = [rmap[k] for k in ref_order]
            mx = statistics.fmean(xs)
            my = statistics.fmean(ys)
            num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
            dx = sum((x-mx)**2 for x in xs)
            dy = sum((y-my)**2 for y in ys)
            rho = num / math.sqrt(dx*dy) if dx > 0 and dy > 0 else None
        ratios = [
            values[k] / ref_values[k]
            for k in values if ref_values[k] > 0
        ]
        sensitivity[str(int(scale))] = {
            "scale": scale,
            "expected_continuous_multiplier_vs_55": scale / ref_scale,
            "median_integer_value_multiplier_vs_55": (
                statistics.median(ratios) if ratios else None
            ),
            "integer_board_rank_spearman_vs_55": rho,
            "integer_board_top100_overlap_vs_55": top_overlap(
                ref_order, order, 100
            ),
        }

    return {
        "current_scale": CURRENT_GLOBAL_SCALE,
        "tested_scales": list(SCALE_SENSITIVITY),
        "mathematical_pre_round_rank_invariance_for_positive_scale": True,
        "identified_by_phase2_future_relative_production_target": False,
        "reason": (
            "Phase 2 evaluates replacement-denominator accuracy against future "
            "relative production. The global value scale is not present in that "
            "target or loss. Multiplying every pre-round FV by a positive constant "
            "cannot identify a preferred scale."
        ),
        "sensitivity": sensitivity,
        "phase5_policy": "hold scale at 55; do not pretend it was calibrated",
    }


def transform_identifiability():
    intercept = CURRENT_TRANSFORM["intercept"]
    slope = CURRENT_TRANSFORM["ratio_slope"]
    floor = CURRENT_TRANSFORM["floor"]
    ceiling = CURRENT_TRANSFORM["ceiling"]

    floor_ratio = (floor - intercept) / slope
    ceiling_ratio = (ceiling - intercept) / slope
    replacement_pm = intercept + slope * 1.0

    return {
        "current_transform": dict(CURRENT_TRANSFORM),
        "replacement_ratio_1_maps_to_pm": replacement_pm,
        "floor_activation_ratio": floor_ratio,
        "ceiling_activation_ratio": ceiling_ratio,
        "affine_slope_intercept_identified_by_phase2_target": False,
        "reason": (
            "Phase 2 identifies the replacement denominator using future relative "
            "production. It does not observe a correct absolute dynasty PM/FV for "
            "a given production ratio. Any unclipped positive monotone affine map "
            "preserves ordering, while changing its slope only changes arbitrary "
            "value spacing unless an external absolute-value target is supplied."
        ),
        "floor_ceiling_status": (
            "compression already audited in Production V2 Phase 6 and frozen for "
            "prospective outcome testing in Production V2 Phase 9"
        ),
        "phase5_policy": (
            "hold intercept=-0.10, slope=0.75, floor=0.15, ceiling=1.55; "
            "Replacement V2 Phase 5 tests rank families only"
        ),
    }


def build_result():
    phase2 = read_json(PHASE2_PATH)
    phase3 = read_json(PHASE3_PATH)
    production_phase1 = read_json(PRODUCTION_PHASE1_PATH)
    phase3mod = load_phase3_module()
    validate_inputs(phase2, phase3, production_phase1, phase3mod)

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)
    phase1_players = production_phase1.get("players")
    if not isinstance(phase1_players, dict):
        raise RuntimeError("Production V2 Phase 1 players object missing")

    legacy = dict(phase3mod.LEGACY_RANKS)
    families = build_rank_families(phase2, phase3, legacy)

    scenario_players = {}
    scenario_baselines = {}
    for name, ranks in families.items():
        players, baselines = phase3mod.scenario_for_ranks(
            phase1_players, ranks, cfg, snapshot_values
        )
        scenario_players[name] = players
        scenario_baselines[name] = baselines

    control = scenario_players["legacy_control"]

    # Recheck exact control parity against the stored Phase-1 candidate values.
    mismatches = []
    for key, rec in phase1_players.items():
        stored = rec.get("candidate")
        rebuilt = control.get(key)
        if stored is None and rebuilt is None:
            continue
        if stored is None or rebuilt is None:
            mismatches.append(key)
            continue
        if int(stored["value"]) != int(rebuilt["fundamental_value"]):
            mismatches.append(key)
    if mismatches:
        raise RuntimeError(
            "Phase 4 legacy control does not reproduce Phase 1; "
            f"sample={mismatches[:10]}"
        )

    scenarios = {}
    for name, ranks in families.items():
        scenarios[name] = board_metrics(
            name,
            ranks,
            scenario_players[name],
            control,
            cfg,
            phase1_players,
            phase3mod,
        )
        scenarios[name]["baselines"] = scenario_baselines[name]

    eligible = [
        name for name, rec in scenarios.items()
        if name != "legacy_control" and rec["combined_board_safety_pass"]
    ]

    # Cohort policy for prospective replacement testing: primary evaluation
    # excludes no-history players so it does not re-test the separate frozen
    # No-History/Rookie V2 problem or let ROLE_MULT threshold semantics decide
    # a replacement-rank study.
    candidate_keys = [
        key for key, rec in phase1_players.items()
        if rec.get("candidate") is not None
    ]
    real_history_keys = [
        key for key in candidate_keys
        if not bool(
            ((phase1_players[key].get("current") or {})
             .get("no_real_production_history"))
        )
    ]

    return round_numbers({
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_COMBINED_BOARD_AND_IDENTIFIABILITY_AUDIT",
        "deployment_authorized": False,
        "production_v2_change_authorized": False,
        "replacement_rank_change_authorized": False,
        "position_weight_change_authorized": False,
        "transform_change_authorized": False,
        "scale_change_authorized": False,
        "frozen_prospective_experiments_touched": False,
        "decision": {
            "replacement_ranks_are_empirically_testable": True,
            "global_scale_is_identified": False,
            "affine_transform_spacing_is_identified": False,
            "phase5_should_freeze_rank_families_only": True,
        },
        "rank_families": families,
        "scenarios": scenarios,
        "combined_safety_gates": COMBINED_SAFETY_GATES,
        "prospective_eligible_noncontrol_families": eligible,
        "prospective_cohort_policy": {
            "primary": "Phase-1 candidate players with real production history",
            "reason": (
                "isolate replacement normalization from the separately frozen "
                "No-History/Rookie V2 semantics experiment"
            ),
            "phase1_candidate_count": len(candidate_keys),
            "real_history_primary_count": len(real_history_keys),
            "no_history_excluded_from_primary_count": (
                len(candidate_keys) - len(real_history_keys)
            ),
        },
        "transform_identifiability": transform_identifiability(),
        "global_scale_identifiability": scale_identifiability(
            scenario_players["full_phase2_leaders"],
            phase1_players,
        ),
        "phase5_freeze_recommendation": {
            "control": "legacy_control",
            "comparators": [
                "prior_limited_evidence",
                "stable_positions_only",
                "full_phase2_leaders",
            ],
            "transform": dict(CURRENT_TRANSFORM),
            "global_scale": CURRENT_GLOBAL_SCALE,
            "position_weights": "hold current index.html POSITION_WEIGHT fixed",
            "primary_scoring_target": (
                "preseason predicted within-position production ratio versus "
                "future realized within-position relative production, using each "
                "family's own replacement rank"
            ),
            "secondary_scoring_target": (
                "raw/effective PM and FV versus cumulative future points; "
                "interpret as secondary because transform/scale are not identified here"
            ),
        },
        "context_not_modified": {
            "production_v2_phase6_transform_audit_sha256": sha256(
                PRODUCTION_PHASE6_PATH
            ),
            "production_v2_phase9_frozen_candidates_sha256": sha256(
                PRODUCTION_PHASE9_PATH
            ),
        },
        "input_sha256": {
            str(PHASE2_PATH.relative_to(REPO_ROOT)): sha256(PHASE2_PATH),
            str(PHASE3_PATH.relative_to(REPO_ROOT)): sha256(PHASE3_PATH),
            str(PHASE3_PY.relative_to(REPO_ROOT)): sha256(PHASE3_PY),
            str(PRODUCTION_PHASE1_PATH.relative_to(REPO_ROOT)): sha256(
                PRODUCTION_PHASE1_PATH
            ),
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
        },
    })


def fmt(value, digits=4):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def pct(value):
    if value is None:
        return "—"
    return f"{100.0 * float(value):+.1f}%"


def render_md(result):
    lines = [
        "# Replacement Level / Positional Scale V2 — Phase 4 Combined Board + Identifiability Audit",
        "",
        "**Research only. No production or frozen prospective experiment is changed.**",
        "",
        f"Method: `{result['method_version']}`",
        "",
        "## Decision",
        "",
        "- Replacement ranks: **empirically testable and ready for prospective freeze**",
        "- Global value scale 55: **not identified by the available historical target — hold fixed**",
        "- Affine PM slope/intercept: **not identified by the available historical target — hold fixed**",
        "- PM floor/ceiling: **already frozen for separate prospective testing in Production V2 Phase 9 — do not duplicate it here**",
        "",
        "Phase 4 therefore freezes the conversion layer conceptually: Replacement V2 Phase 5 will vary **replacement ranks only**.",
        "",
        "## Combined rank families",
        "",
        "| Family | QB | RB | WR | TE | DL | LB | DB | Safety | Global ρ | Top100 overlap | P90 abs FV Δ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|",
    ]
    for name in (
        "legacy_control",
        "prior_limited_evidence",
        "stable_positions_only",
        "full_phase2_leaders",
    ):
        ranks = result["rank_families"][name]
        s = result["scenarios"][name]
        lines.append(
            f"| `{name}` | {ranks['QB']} | {ranks['RB']} | {ranks['WR']} | "
            f"{ranks['TE']} | {ranks['DL']} | {ranks['LB']} | {ranks['DB']} | "
            f"{'PASS' if s['combined_board_safety_pass'] else 'FAIL'} | "
            f"{fmt(s['global_rank_spearman'])} | "
            f"{pct(s['global_top100_overlap'])} | "
            f"{pct(s['all_player_fv_change_pct'].get('p90_abs'))} |"
        )

    lines += [
        "",
        "## Combined-board positional movement",
        "",
        "| Family | QB med | RB med | WR med | TE med | DL med | LB med | DB med | Max abs Top100 share Δ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in (
        "prior_limited_evidence",
        "stable_positions_only",
        "full_phase2_leaders",
    ):
        s = result["scenarios"][name]
        pos = s["position_fv_change_pct"]
        lines.append(
            f"| `{name}` | {pct(pos['QB'].get('median'))} | "
            f"{pct(pos['RB'].get('median'))} | {pct(pos['WR'].get('median'))} | "
            f"{pct(pos['TE'].get('median'))} | {pct(pos['DL'].get('median'))} | "
            f"{pct(pos['LB'].get('median'))} | {pct(pos['DB'].get('median'))} | "
            f"{pct(s['max_abs_top100_position_share_delta'])} |"
        )

    lines += [
        "",
        "## Floor / rescue diagnostics",
        "",
        "Current deployed semantics can still turn a no-history raw-PM floor hit into `ROLE_MULT`. "
        "That is reported here but **excluded from the Phase-5 primary cohort** so Replacement V2 "
        "does not duplicate the separate No-History/Rookie V2 experiment.",
        "",
    ]
    for name in (
        "legacy_control",
        "prior_limited_evidence",
        "stable_positions_only",
        "full_phase2_leaders",
    ):
        resc = result["scenarios"][name]["current_semantics_role_rescues"]
        lines += [
            f"### `{name}`",
            "",
            f"- role rescues: **{resc['scenario_count']}**",
            f"- new rescue crossings vs control: **{len(resc['new_crossings'])}**",
            f"- removed rescue crossings vs control: **{len(resc['removed_crossings'])}**",
            "",
        ]

    ti = result["transform_identifiability"]
    lines += [
        "## Transform identifiability",
        "",
        f"- Current: `clamp({ti['current_transform']['intercept']:+.2f} + "
        f"{ti['current_transform']['ratio_slope']:.2f} × ratio, "
        f"{ti['current_transform']['floor']:.2f}, {ti['current_transform']['ceiling']:.2f})`",
        f"- Replacement ratio 1.0 maps to PM **{ti['replacement_ratio_1_maps_to_pm']:.2f}**",
        f"- Floor activates at ratio **{ti['floor_activation_ratio']:.3f}× replacement**",
        f"- Ceiling activates at ratio **{ti['ceiling_activation_ratio']:.3f}× replacement**",
        "- Historical Phase-2 target identifies affine spacing: **No**",
        "",
        "Reason: future relative production identifies the denominator. It does not provide an observed "
        "absolute dynasty PM/FV corresponding to each production ratio. Choosing a steeper or flatter "
        "monotone affine map from the same target would be an arbitrary value-spacing choice.",
        "",
        "## Global scale identifiability",
        "",
        "- Current global scale: **55**",
        "- Identified by Phase-2 future relative-production target: **No**",
        "- Positive pre-round scale preserves ordering mathematically: **Yes**",
        "",
        "| Scale | Expected value multiplier vs 55 | Median integer multiplier | Integer-board ρ | Top100 overlap |",
        "|---:|---:|---:|---:|---:|",
    ]
    gi = result["global_scale_identifiability"]
    for scale in ("45", "55", "65"):
        rec = gi["sensitivity"][scale]
        lines.append(
            f"| {scale} | {fmt(rec['expected_continuous_multiplier_vs_55'], 3)}× | "
            f"{fmt(rec['median_integer_value_multiplier_vs_55'], 3)}× | "
            f"{fmt(rec['integer_board_rank_spearman_vs_55'])} | "
            f"{pct(rec['integer_board_top100_overlap_vs_55'])} |"
        )

    cp = result["prospective_cohort_policy"]
    fr = result["phase5_freeze_recommendation"]
    lines += [
        "",
        "## Phase 5 handoff",
        "",
        f"- Phase-1 candidate cohort: **{cp['phase1_candidate_count']}**",
        f"- Primary real-history cohort: **{cp['real_history_primary_count']}**",
        f"- No-history players excluded from primary: **{cp['no_history_excluded_from_primary_count']}**",
        "",
        "Freeze these prospective arms:",
        "",
        "1. `legacy_control`",
        "2. `prior_limited_evidence`",
        "3. `stable_positions_only` — changes only positions whose Phase-2 leader was stable across 2/4/6-week windows",
        "4. `full_phase2_leaders` — also includes QB29 and TE11",
        "",
        f"Transform stays **{fr['transform']}**.",
        f"Global scale stays **{fr['global_scale']}**.",
        "POSITION_WEIGHT stays fixed.",
        "",
        "Primary scoring will compare each preseason rank family's predicted within-position production "
        "ratio with realized future within-position relative production. That directly tests the "
        "replacement denominator without pretending the transform or global scale were calibrated.",
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
    ]
    return "\n".join(lines)


def run_selftest():
    # Basic mathematical invariance checks.
    base = [1.0, 2.0, 3.0]
    for scale in (45.0, 55.0, 65.0):
        scaled = [x * scale for x in base]
        assert sorted(range(3), key=lambda i: -scaled[i]) == [2, 1, 0]

    floor_ratio = (
        CURRENT_TRANSFORM["floor"] - CURRENT_TRANSFORM["intercept"]
    ) / CURRENT_TRANSFORM["ratio_slope"]
    ceiling_ratio = (
        CURRENT_TRANSFORM["ceiling"] - CURRENT_TRANSFORM["intercept"]
    ) / CURRENT_TRANSFORM["ratio_slope"]
    assert abs(floor_ratio - (1.0 / 3.0)) < 1e-12
    assert abs(ceiling_ratio - 2.2) < 1e-12
    print("PASS Replacement Level V2 Phase 4 self-test.")


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
            raise RuntimeError("Phase 4 outputs do not exist; run --write first")
        if OUTPUT_JSON.read_text(encoding="utf-8") != rendered_json:
            raise RuntimeError("Phase 4 JSON is stale or non-deterministic")
        if OUTPUT_MD.read_text(encoding="utf-8") != rendered_md:
            raise RuntimeError("Phase 4 Markdown is stale or non-deterministic")

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
            raise RuntimeError("frozen prospective experiment guardrail failed")

        if result["decision"]["global_scale_is_identified"] is not False:
            raise RuntimeError("scale identifiability decision unexpectedly changed")
        if result["decision"]["affine_transform_spacing_is_identified"] is not False:
            raise RuntimeError("transform identifiability decision unexpectedly changed")
        if not result["prospective_eligible_noncontrol_families"]:
            raise RuntimeError("no non-control family survived combined-board safety")
        print("PASS Replacement Level V2 Phase 4 checks.")

    if not args.write and not args.check and not args.selftest:
        print(rendered_md)


if __name__ == "__main__":
    main()

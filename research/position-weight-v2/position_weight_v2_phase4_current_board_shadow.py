#!/usr/bin/env python3
"""
Position Weight / Cross-Position Economics V2 — Phase 4 current-board shadow.

Research only. No POSITION_WEIGHT change is authorized.

Phase 3 found a strong historical utility signal, but the full empirical
candidate is aggressive (especially QB/RB). Phase 4 therefore shadows three
fixed bridges from deployed weights toward the robust full-history candidate:

- bridge_50
- bridge_75
- bridge_100

Only POSITION_WEIGHT changes. Production, age, no-history semantics, role,
PM transform, replacement-rank research, and global scale remain untouched.

The current live valuation formula is reproduced exactly:
    round_js(100 * position_weight * age_mult * prod_mult * 55)

RB age is date-sensitive. --write freezes a board_reference_date into the
output; --check reuses that stored date so the audit remains deterministic.

Outputs:
  research/position-weight-v2/position_weight_v2_phase4_current_board_shadow.json
  research/position-weight-v2/position_weight_v2_phase4_current_board_shadow.md
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

INDEX_HTML = REPO_ROOT / "index.html"
PHASE1_JSON = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase1_architecture_audit.json"
)
PHASE3_JSON = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase3_historical_calibration.json"
)

OUTPUT_JSON = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase4_current_board_shadow.json"
)
OUTPUT_MD = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase4_current_board_shadow.md"
)

METHOD_VERSION = "position-weight-v2-phase4-current-board-shadow-v1"
PHASE1_METHOD = "position-weight-v2-phase1-architecture-audit-v1"
PHASE3_METHOD = "position-weight-v2-phase3-historical-calibration-v1"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
BRIDGES = (0.50, 0.75, 1.00)
GLOBAL_SCALE = 55.0

# Broad damage-control gates. Passing is NOT deployment evidence.
SAFETY_GATES = {
    "global_rank_spearman_min": 0.94,
    "global_top100_overlap_min": 0.82,
    "p90_abs_all_player_value_change_pct_max": 0.55,
    "max_abs_position_share_top100_delta_max": 0.12,
    "median_abs_qb_value_change_pct_max": 0.65,
    "median_abs_any_position_value_change_pct_max": 0.55,
}


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def round_js_positive(value: float) -> int:
    return int(math.floor(float(value) + 0.5))


def bridge_key(weight: float) -> str:
    return f"bridge_{int(round(100 * weight))}"


def round_numbers(obj, digits=6):
    if isinstance(obj, dict):
        return {k: round_numbers(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_numbers(v, digits) for v in obj]
    if isinstance(obj, float):
        return round(obj, digits) if math.isfinite(obj) else None
    return obj


def percentile(values, q):
    vals = sorted(
        float(v) for v in values
        if v is not None and math.isfinite(float(v))
    )
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    idx = (len(vals) - 1) * max(0.0, min(1.0, float(q)))
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    frac = idx - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def summarize(values):
    vals = [
        float(v) for v in values
        if v is not None and math.isfinite(float(v))
    ]
    if not vals:
        return {"n": 0}
    abs_vals = [abs(v) for v in vals]
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
    num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    dx = sum((x-mx)**2 for x in xs)
    dy = sum((y-my)**2 for y in ys)
    if dx <= 0 or dy <= 0:
        return None
    return num / math.sqrt(dx * dy)


def spearman(xs, ys):
    if len(xs) < 3:
        return None
    return pearson(rankdata(xs), rankdata(ys))


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def validate_inputs(phase1, phase3):
    if phase1.get("method_version") != PHASE1_METHOD:
        raise RuntimeError("unexpected Position Weight V2 Phase-1 method")
    if phase3.get("method_version") != PHASE3_METHOD:
        raise RuntimeError("unexpected Position Weight V2 Phase-3 method")

    for name, payload in (("Phase 1", phase1), ("Phase 3", phase3)):
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
            raise RuntimeError(f"{name} says frozen experiments changed")

    selected = (phase3.get("alpha_selection") or {}).get("selected") or {}
    if selected.get("historical_screen_pass") is not True:
        raise RuntimeError("Phase 3 historical screen did not pass")
    if abs(float(selected.get("alpha")) - 1.0) > 1e-12:
        raise RuntimeError("Phase 3 selected alpha changed from 1.00")

    handoff = phase3.get("phase4_handoff") or {}
    if handoff.get("candidate_authorized_for_shadow_only") is not True:
        raise RuntimeError("Phase 3 does not authorize current-board shadow")

    robust = (
        (phase3.get("full_history_candidate_weights") or {})
        .get("robust_median_candidate_weights")
    )
    if not isinstance(robust, dict):
        raise RuntimeError("Phase 3 robust candidate weights missing")
    for pos in TRACKED_POSITIONS:
        if float(robust.get(pos) or 0.0) <= 0:
            raise RuntimeError(f"Phase 3 invalid robust candidate weight: {pos}")


def make_weights(deployed, candidate, bridge):
    out = {}
    for pos in TRACKED_POSITIONS:
        out[pos] = (
            float(deployed[pos])
            + float(bridge) * (float(candidate[pos]) - float(deployed[pos]))
        )
        if out[pos] <= 0:
            raise RuntimeError(f"non-positive bridge weight for {pos}")
    out["WR"] = 1.0
    return out


def compute_base_rows(cfg, snapshot_values, as_of):
    rows = {}
    for key, info in cfg["player_db"].items():
        pos = info["pos"]
        if pos not in TRACKED_POSITIONS:
            continue
        role = info["role"]
        age = info["age"]

        pm, raw_pm = snapshot_values.production_multiplier(
            key,
            role,
            cfg["prod_mult"],
            cfg["no_real_history"],
            cfg["role_mult"],
        )
        am = snapshot_values.effective_age_multiplier(
            pos, age, role, key, pm, raw_pm, cfg, as_of=as_of
        )
        rows[key] = {
            "pos": pos,
            "age": age,
            "role": role,
            "prod_mult": float(pm),
            "age_mult": float(am),
            "base_without_position_weight": (
                100.0 * float(am) * float(pm) * GLOBAL_SCALE
            ),
        }
    return rows


def values_for_weights(base_rows, weights):
    return {
        key: round_js_positive(
            float(row["base_without_position_weight"])
            * float(weights[row["pos"]])
        )
        for key, row in base_rows.items()
    }


def ranked_keys(values):
    return sorted(values, key=lambda k: (-int(values[k]), k))


def rank_map(order):
    return {key: i + 1 for i, key in enumerate(order)}


def top_overlap(a, b, n):
    aa = set(a[:n])
    bb = set(b[:n])
    denom = min(n, len(aa), len(bb))
    return len(aa & bb) / denom if denom else None


def position_share(order, base_rows, pos, n):
    keys = order[:n]
    if not keys:
        return None
    return sum(1 for key in keys if base_rows[key]["pos"] == pos) / len(keys)


def scenario_metrics(
    name,
    weights,
    control_weights,
    base_rows,
    control_values,
):
    values = values_for_weights(base_rows, weights)
    control_order = ranked_keys(control_values)
    order = ranked_keys(values)
    control_ranks = rank_map(control_order)
    ranks = rank_map(order)

    all_pct = []
    rank_moves = []
    by_pos_pct = {pos: [] for pos in TRACKED_POSITIONS}
    movers = []

    for key, row in base_rows.items():
        cv = int(control_values[key])
        nv = int(values[key])
        pct = ((nv - cv) / cv) if cv else None
        if pct is not None:
            all_pct.append(pct)
            by_pos_pct[row["pos"]].append(pct)
            movers.append({
                "player": key,
                "pos": row["pos"],
                "control_value": cv,
                "scenario_value": nv,
                "change_pct": pct,
                "control_rank": control_ranks[key],
                "scenario_rank": ranks[key],
                "rank_move": ranks[key] - control_ranks[key],
            })
        rank_moves.append(ranks[key] - control_ranks[key])

    movers.sort(key=lambda x: (-abs(x["change_pct"]), x["player"]))

    rho = spearman(
        [control_ranks[k] for k in control_order],
        [ranks[k] for k in control_order],
    )
    overlap100 = top_overlap(control_order, order, 100)

    ctl_share100 = {
        pos: position_share(control_order, base_rows, pos, 100)
        for pos in TRACKED_POSITIONS
    }
    cand_share100 = {
        pos: position_share(order, base_rows, pos, 100)
        for pos in TRACKED_POSITIONS
    }
    share_delta = {
        pos: cand_share100[pos] - ctl_share100[pos]
        for pos in TRACKED_POSITIONS
    }
    max_abs_share_delta = max(abs(v) for v in share_delta.values())

    all_summary = summarize(all_pct)
    pos_summary = {
        pos: summarize(by_pos_pct[pos])
        for pos in TRACKED_POSITIONS
    }
    max_position_median_abs = max(
        float(pos_summary[pos].get("median_abs") or 0.0)
        for pos in TRACKED_POSITIONS
    )
    qb_median_abs = float(pos_summary["QB"].get("median_abs") or 0.0)

    gates = {
        "global_rank_spearman": (
            rho is not None
            and rho >= SAFETY_GATES["global_rank_spearman_min"]
        ),
        "global_top100_overlap": (
            overlap100 is not None
            and overlap100 >= SAFETY_GATES["global_top100_overlap_min"]
        ),
        "p90_abs_all_player_value_change_pct": (
            all_summary.get("p90_abs") is not None
            and all_summary["p90_abs"]
            <= SAFETY_GATES["p90_abs_all_player_value_change_pct_max"]
        ),
        "max_abs_position_share_top100_delta": (
            max_abs_share_delta
            <= SAFETY_GATES["max_abs_position_share_top100_delta_max"]
        ),
        "median_abs_qb_value_change_pct": (
            qb_median_abs
            <= SAFETY_GATES["median_abs_qb_value_change_pct_max"]
        ),
        "median_abs_any_position_value_change_pct": (
            max_position_median_abs
            <= SAFETY_GATES["median_abs_any_position_value_change_pct_max"]
        ),
    }

    return {
        "name": name,
        "position_weights": weights,
        "value_change_pct": all_summary,
        "position_value_change_pct": pos_summary,
        "global_rank_movement": summarize(rank_moves),
        "global_rank_spearman": rho,
        "global_top50_overlap": top_overlap(control_order, order, 50),
        "global_top100_overlap": overlap100,
        "control_top100_position_share": ctl_share100,
        "scenario_top100_position_share": cand_share100,
        "top100_position_share_delta": share_delta,
        "max_abs_top100_position_share_delta": max_abs_share_delta,
        "largest_absolute_movers": movers[:40],
        "safety_gates": gates,
        "board_safety_pass": all(gates.values()),
    }


def build_result(reference_date):
    phase1 = read_json(PHASE1_JSON)
    phase3 = read_json(PHASE3_JSON)
    validate_inputs(phase1, phase3)

    deployed = {
        pos: float(phase1["current_position_weights"][pos])
        for pos in TRACKED_POSITIONS
    }
    candidate = {
        pos: float(
            phase3["full_history_candidate_weights"]
            ["robust_median_candidate_weights"][pos]
        )
        for pos in TRACKED_POSITIONS
    }

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    html_weights = {
        pos: float(cfg["position_weight"][pos])
        for pos in TRACKED_POSITIONS
    }
    if html_weights != deployed:
        raise RuntimeError(
            f"index.html POSITION_WEIGHT changed from Phase 1: {html_weights}"
        )

    base_rows = compute_base_rows(
        cfg, snapshot_values, reference_date
    )
    control_values = values_for_weights(base_rows, deployed)

    # Exact isolation gate: reconstruct the same values from the loaded live
    # constants using the same fixed reference date and formula.
    isolation_mismatches = []
    for key, row in base_rows.items():
        direct = round_js_positive(
            100.0
            * deployed[row["pos"]]
            * row["age_mult"]
            * row["prod_mult"]
            * GLOBAL_SCALE
        )
        if direct != control_values[key]:
            isolation_mismatches.append(key)
    if isolation_mismatches:
        raise RuntimeError(
            f"control reconstruction mismatch: {isolation_mismatches[:10]}"
        )

    scenarios = {}
    for bridge in BRIDGES:
        key = bridge_key(bridge)
        weights = make_weights(deployed, candidate, bridge)
        scenarios[key] = scenario_metrics(
            key, weights, deployed, base_rows, control_values
        )
        scenarios[key]["bridge_fraction"] = bridge

    safe = [
        key for key in ("bridge_100", "bridge_75", "bridge_50")
        if scenarios[key]["board_safety_pass"]
    ]
    recommended = safe[0] if safe else "deployed_control"

    return round_numbers({
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_POSITION_WEIGHT_CURRENT_BOARD_SHADOW",
        "board_reference_date": reference_date.isoformat(),
        "deployment_authorized": False,
        "position_weight_change_authorized": False,
        "replacement_rank_change_authorized": False,
        "production_v2_change_authorized": False,
        "transform_change_authorized": False,
        "scale_change_authorized": False,
        "frozen_prospective_experiments_touched": False,
        "deployed_position_weights": deployed,
        "phase3_robust_candidate_weights": candidate,
        "safety_gates": SAFETY_GATES,
        "isolation_gate": {
            "live_formula_reconstructed_exactly": True,
            "reconstruction_mismatch_count": 0,
            "position_weight_is_only_changed_component": True,
            "global_scale": GLOBAL_SCALE,
        },
        "scenarios": scenarios,
        "phase5_recommendation": {
            "recommended_shadow_variant": recommended,
            "recommended_weights": (
                deployed if recommended == "deployed_control"
                else scenarios[recommended]["position_weights"]
            ),
            "prospective_freeze_authorized": recommended != "deployed_control",
            "deployment_authorized": False,
            "carry_control": True,
            "carry_neighbor_variants": (
                ["bridge_50", "bridge_75", "bridge_100"]
                if recommended != "deployed_control"
                else []
            ),
        },
        "input_sha256": {
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
            str(PHASE1_JSON.relative_to(REPO_ROOT)): sha256(PHASE1_JSON),
            str(PHASE3_JSON.relative_to(REPO_ROOT)): sha256(PHASE3_JSON),
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
        "# Position Weight / Cross-Position Economics V2 — Phase 4 Current-Board Shadow",
        "",
        "**Research only. No POSITION_WEIGHT deployment is authorized.**",
        "",
        f"Method: `{result['method_version']}`",
        f"Board reference date: **{result['board_reference_date']}**",
        "",
        "## Isolation",
        "",
        "- Live valuation formula reconstructed exactly: **Yes**",
        "- POSITION_WEIGHT is the only changed component: **Yes**",
        "- Global scale held at **55**",
        "",
        "## Candidate weights",
        "",
        "| Pos | Deployed | Phase-3 empirical | Bridge 50 | Bridge 75 | Bridge 100 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for pos in TRACKED_POSITIONS:
        lines.append(
            f"| {pos} | "
            f"{fmt(result['deployed_position_weights'][pos], 3)} | "
            f"{fmt(result['phase3_robust_candidate_weights'][pos], 3)} | "
            f"{fmt(result['scenarios']['bridge_50']['position_weights'][pos], 3)} | "
            f"{fmt(result['scenarios']['bridge_75']['position_weights'][pos], 3)} | "
            f"{fmt(result['scenarios']['bridge_100']['position_weights'][pos], 3)} |"
        )

    lines += [
        "",
        "## Current-board blast radius",
        "",
        "| Variant | Safety | Global ρ | Top50 overlap | Top100 overlap | P90 abs FV Δ | Max Top100 pos-share Δ | QB median FV Δ |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ("bridge_50", "bridge_75", "bridge_100"):
        row = result["scenarios"][key]
        lines.append(
            f"| `{key}` | {'PASS' if row['board_safety_pass'] else 'FAIL'} | "
            f"{fmt(row['global_rank_spearman'])} | "
            f"{pct(row['global_top50_overlap'])} | "
            f"{pct(row['global_top100_overlap'])} | "
            f"{pct(row['value_change_pct'].get('p90_abs'))} | "
            f"{pct(row['max_abs_top100_position_share_delta'])} | "
            f"{pct(row['position_value_change_pct']['QB'].get('median'))} |"
        )

    lines += [
        "",
        "## Positional median FV movement",
        "",
        "| Variant | QB | RB | WR | TE | DL | LB | DB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ("bridge_50", "bridge_75", "bridge_100"):
        row = result["scenarios"][key]["position_value_change_pct"]
        lines.append(
            f"| `{key}` | {pct(row['QB'].get('median'))} | "
            f"{pct(row['RB'].get('median'))} | {pct(row['WR'].get('median'))} | "
            f"{pct(row['TE'].get('median'))} | {pct(row['DL'].get('median'))} | "
            f"{pct(row['LB'].get('median'))} | {pct(row['DB'].get('median'))} |"
        )

    rec = result["phase5_recommendation"]
    lines += [
        "",
        "## Phase 5 handoff",
        "",
        f"Recommended shadow variant: **`{rec['recommended_shadow_variant']}`**",
        f"Prospective freeze authorized by this research phase: **{rec['prospective_freeze_authorized']}**",
        "",
        "Passing the board-safety gates means only that the shadow does not create obvious current-board damage. "
        "It is not evidence to deploy. Any surviving candidate must still be frozen prospectively before Week 1.",
        "",
        "## Guardrails",
        "",
        "- deployment_authorized: **false**",
        "- position_weight_change_authorized: **false**",
        "- replacement_rank_change_authorized: **false**",
        "- production_v2_change_authorized: **false**",
        "- transform_change_authorized: **false**",
        "- scale_change_authorized: **false**",
        "- frozen prospective experiments touched: **false**",
        "",
    ]
    return "\n".join(lines)


def run_selftest():
    assert round_js_positive(10.5) == 11
    assert round_js_positive(10.49) == 10

    deployed = {
        "QB": 1.30, "RB": 0.89, "WR": 1.0, "TE": 0.82,
        "DL": 0.93, "LB": 1.12, "DB": 0.87,
    }
    candidate = {
        "QB": 2.20, "RB": 1.50, "WR": 1.0, "TE": 0.70,
        "DL": 0.70, "LB": 1.05, "DB": 0.66,
    }
    mid = make_weights(deployed, candidate, 0.5)
    assert abs(mid["QB"] - 1.75) < 1e-12
    assert mid["WR"] == 1.0

    assert abs(spearman([1,2,3], [3,2,1]) + 1.0) < 1e-12
    print("PASS Position Weight V2 Phase 4 self-test.")


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
        if not OUTPUT_JSON.exists() or not OUTPUT_MD.exists():
            raise RuntimeError("Phase 4 outputs missing")
        stored = read_json(OUTPUT_JSON)
        ref = date.fromisoformat(stored["board_reference_date"])
        result = build_result(ref)
        rendered_json = json.dumps(result, indent=2, sort_keys=True) + "\n"
        rendered_md = render_md(result).rstrip() + "\n"
        if OUTPUT_JSON.read_text(encoding="utf-8") != rendered_json:
            raise RuntimeError("Phase 4 JSON is stale or non-deterministic")
        if OUTPUT_MD.read_text(encoding="utf-8") != rendered_md:
            raise RuntimeError("Phase 4 Markdown is stale or non-deterministic")
        for field in (
            "deployment_authorized",
            "position_weight_change_authorized",
            "replacement_rank_change_authorized",
            "production_v2_change_authorized",
            "transform_change_authorized",
            "scale_change_authorized",
        ):
            if result.get(field) is not False:
                raise RuntimeError(f"guardrail failed: {field}")
        if result.get("frozen_prospective_experiments_touched") is not False:
            raise RuntimeError("frozen experiment guardrail failed")
        print("PASS Position Weight V2 Phase 4 checks.")
        return

    ref = datetime.now(timezone.utc).date()
    result = build_result(ref)
    rendered_json = json.dumps(result, indent=2, sort_keys=True) + "\n"
    rendered_md = render_md(result).rstrip() + "\n"

    if args.write:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(rendered_json, encoding="utf-8")
        OUTPUT_MD.write_text(rendered_md, encoding="utf-8")
        print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
        print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")
    else:
        print(rendered_md)


if __name__ == "__main__":
    main()

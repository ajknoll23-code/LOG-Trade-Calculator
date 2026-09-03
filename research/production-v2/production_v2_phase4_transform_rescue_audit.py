#!/usr/bin/env python3
"""
Production V2 Phase 4 — transform + no-history rescue discontinuity audit.

WHY THIS EXISTS
---------------
Phase 3 changed ONLY the replacement denominator and exposed a structural edge
case: some no-history players can have a LOWER raw production multiplier under
a new baseline yet a HIGHER effective production multiplier after the current
lineage-gated role rescue fires at raw PM <= 0.15.

That is a discontinuity in the current production architecture.

This Phase 4 audit:
- changes NO production files,
- changes NO provider/history weights,
- changes NO position weights,
- changes NO age rules,
- changes NO baseline recommendation,
- and makes NO deployment.

It answers:
1. How much floor/ceiling compression does the affine transform create?
2. How often does the <=0.15 no-history rescue fire?
3. Does changing only the denominator create paradoxical movers where raw PM
   falls but effective PM rises?
4. Which roles/positions are exposed to the threshold jump?
5. Is a baseline/transform deployment blocked until rescue semantics are
   redesigned?

INPUTS
------
- research/production-v2/production_v2_phase1_audit.json
- research/production-v2/production_v2_phase3_baseline_normalization_audit.json
- index.html
- scripts/validation/snapshot_values.py

OUTPUTS
-------
- research/production-v2/production_v2_phase4_transform_rescue_audit.json
- research/production-v2/production_v2_phase4_transform_rescue_audit.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from collections import Counter, defaultdict

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

PHASE1_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase1_audit.json"
PHASE3_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase3_baseline_normalization_audit.json"
INDEX_HTML = REPO_ROOT / "index.html"
SNAPSHOT_VALUES_PATH = REPO_ROOT / "scripts" / "validation" / "snapshot_values.py"

OUTPUT_JSON = REPO_ROOT / "research" / "production-v2" / "production_v2_phase4_transform_rescue_audit.json"
OUTPUT_MD = REPO_ROOT / "research" / "production-v2" / "production_v2_phase4_transform_rescue_audit.md"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55


def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def percentile(values, q):
    vals = sorted(float(v) for v in values)
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
    return vals[lo] * (1 - frac) + vals[hi] * frac


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


def build_baselines(phase1_players, ranks):
    baselines = {}
    for pos in TRACKED_POSITIONS:
        cohort = [
            rec for rec in phase1_players.values()
            if rec.get("pos") == pos and rec.get("phase1_combined_points") is not None
        ]
        cohort.sort(key=lambda r: (-float(r["phase1_combined_points"]), r["key"]))
        rank = int(ranks[pos])
        if len(cohort) < rank:
            raise RuntimeError(f"{pos}: cohort {len(cohort)} smaller than rank {rank}")
        anchor = cohort[rank - 1]
        baselines[pos] = {
            "rank": rank,
            "player": anchor["key"],
            "combined_points": float(anchor["phase1_combined_points"]),
            "cohort_size": len(cohort),
        }
    return baselines


def transform_state(key, rec, cfg, baselines, snapshot_values):
    combined = rec.get("phase1_combined_points")
    if combined is None:
        return None

    pos = rec["pos"]
    baseline = float(baselines[pos]["combined_points"])
    ratio = float(combined) / baseline
    raw_unclamped = PM_INTERCEPT + PM_RATIO_SLOPE * ratio
    raw_clamped = clamp(raw_unclamped, PM_MIN, PM_MAX)

    info = cfg["player_db"][key]
    role = info["role"]
    role_estimate = float(cfg["role_mult"].get(role, 1.0))
    no_history = key in cfg["no_real_history"]

    effective_pm, raw_returned = snapshot_values.production_multiplier(
        key,
        role,
        {key: raw_clamped},
        cfg["no_real_history"],
        cfg["role_mult"],
    )

    elite_floor_applied = role == "Elite" and raw_clamped < 0.65
    rescue_applied = (
        not elite_floor_applied
        and raw_clamped <= PM_MIN
        and role_estimate > raw_clamped
        and no_history
        and abs(effective_pm - role_estimate) < 1e-12
    )

    return {
        "player": key,
        "pos": pos,
        "role": role,
        "no_real_history": no_history,
        "combined_points": float(combined),
        "baseline_points": baseline,
        "ratio_to_baseline": ratio,
        "raw_unclamped": raw_unclamped,
        "raw_clamped": raw_clamped,
        "effective_pm": float(effective_pm),
        "role_estimate": role_estimate,
        "floor_hit": abs(raw_clamped - PM_MIN) < 1e-12,
        "ceiling_hit": abs(raw_clamped - PM_MAX) < 1e-12,
        "elite_floor_applied": elite_floor_applied,
        "no_history_role_rescue_applied": rescue_applied,
        "threshold_jump_size_if_rescued": (
            role_estimate - PM_MIN
            if no_history and role != "Elite" and role_estimate > PM_MIN
            else 0.0
        ),
    }


def summarize_scenario(states):
    by_pos = {}
    for pos in TRACKED_POSITIONS:
        rows = [r for r in states.values() if r and r["pos"] == pos]
        floor = [r for r in rows if r["floor_hit"]]
        ceiling = [r for r in rows if r["ceiling_hit"]]
        rescued = [r for r in rows if r["no_history_role_rescue_applied"]]
        elite_floor = [r for r in rows if r["elite_floor_applied"]]
        by_pos[pos] = {
            "n": len(rows),
            "raw_floor_count": len(floor),
            "raw_floor_share": len(floor) / len(rows) if rows else None,
            "raw_ceiling_count": len(ceiling),
            "raw_ceiling_share": len(ceiling) / len(rows) if rows else None,
            "no_history_role_rescue_count": len(rescued),
            "no_history_role_rescue_share": len(rescued) / len(rows) if rows else None,
            "elite_floor_count": len(elite_floor),
            "effective_pm_summary": summarize([r["effective_pm"] for r in rows]),
            "raw_pm_summary": summarize([r["raw_clamped"] for r in rows]),
        }
    return by_pos


def build_result():
    phase1 = read_json(PHASE1_PATH)
    phase3 = read_json(PHASE3_PATH)

    if phase1.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 1 must be research-only")
    if phase3.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 3 must be research-only")
    if not (phase3.get("isolation_gate") or {}).get("documented_scenario_exactly_reproduces_phase1"):
        raise RuntimeError("Phase 3 did not reproduce Phase 1 exactly")

    documented_ranks = phase3.get("documented_ranks")
    hybrid_ranks = phase3.get("evidence_hybrid_ranks")
    if not isinstance(documented_ranks, dict) or not isinstance(hybrid_ranks, dict):
        raise RuntimeError("Phase 3 ranks missing")

    phase1_players = phase1.get("players")
    if not isinstance(phase1_players, dict):
        raise RuntimeError("Phase 1 players missing")

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    documented_baselines = build_baselines(phase1_players, documented_ranks)
    hybrid_baselines = build_baselines(phase1_players, hybrid_ranks)

    documented = {}
    hybrid = {}
    for key, rec in phase1_players.items():
        documented[key] = transform_state(key, rec, cfg, documented_baselines, snapshot_values)
        hybrid[key] = transform_state(key, rec, cfg, hybrid_baselines, snapshot_values)

    # Reproduce Phase 1 effective PM exactly under documented ranks.
    pm_mismatches = []
    for key, rec in phase1_players.items():
        candidate = rec.get("candidate")
        state = documented.get(key)
        if candidate is None and state is None:
            continue
        if candidate is None or state is None:
            pm_mismatches.append({"player": key, "reason": "presence_mismatch"})
            continue
        expected = float(candidate["production_multiplier"])
        actual = float(state["effective_pm"])
        if abs(expected - actual) > 1e-9:
            pm_mismatches.append({
                "player": key,
                "expected": expected,
                "actual": actual,
            })
    if pm_mismatches:
        raise RuntimeError(
            "Documented transform/rescue scenario does not reproduce Phase 1 PM; "
            f"sample={pm_mismatches[:5]}"
        )

    paradoxes = []
    rescue_crossings = []
    reverse_rescue_crossings = []
    floor_crossings = []
    by_position = {}
    role_exposure = defaultdict(lambda: {
        "players": 0,
        "no_history_players": 0,
        "documented_rescued": 0,
        "hybrid_rescued": 0,
        "max_threshold_jump": 0.0,
    })

    for key, rec in phase1_players.items():
        doc = documented.get(key)
        hyb = hybrid.get(key)
        if doc is None or hyb is None:
            continue

        role = doc["role"]
        role_exposure[role]["players"] += 1
        if doc["no_real_history"]:
            role_exposure[role]["no_history_players"] += 1
        if doc["no_history_role_rescue_applied"]:
            role_exposure[role]["documented_rescued"] += 1
        if hyb["no_history_role_rescue_applied"]:
            role_exposure[role]["hybrid_rescued"] += 1
        role_exposure[role]["max_threshold_jump"] = max(
            role_exposure[role]["max_threshold_jump"],
            doc["threshold_jump_size_if_rescued"],
            hyb["threshold_jump_size_if_rescued"],
        )

        raw_delta = hyb["raw_clamped"] - doc["raw_clamped"]
        effective_delta = hyb["effective_pm"] - doc["effective_pm"]

        row = {
            "player": key,
            "pos": doc["pos"],
            "role": role,
            "no_real_history": doc["no_real_history"],
            "documented_raw_pm": doc["raw_clamped"],
            "hybrid_raw_pm": hyb["raw_clamped"],
            "raw_pm_delta": raw_delta,
            "documented_effective_pm": doc["effective_pm"],
            "hybrid_effective_pm": hyb["effective_pm"],
            "effective_pm_delta": effective_delta,
            "documented_rescue": doc["no_history_role_rescue_applied"],
            "hybrid_rescue": hyb["no_history_role_rescue_applied"],
            "documented_floor_hit": doc["floor_hit"],
            "hybrid_floor_hit": hyb["floor_hit"],
            "role_estimate": doc["role_estimate"],
        }

        if raw_delta < -1e-12 and effective_delta > 1e-12:
            paradoxes.append(row)
        if not doc["no_history_role_rescue_applied"] and hyb["no_history_role_rescue_applied"]:
            rescue_crossings.append(row)
        if doc["no_history_role_rescue_applied"] and not hyb["no_history_role_rescue_applied"]:
            reverse_rescue_crossings.append(row)
        if doc["floor_hit"] != hyb["floor_hit"]:
            floor_crossings.append(row)

    paradoxes.sort(key=lambda r: (-r["effective_pm_delta"], r["player"]))
    rescue_crossings.sort(key=lambda r: (-r["effective_pm_delta"], r["player"]))
    reverse_rescue_crossings.sort(key=lambda r: (r["effective_pm_delta"], r["player"]))

    documented_summary = summarize_scenario(documented)
    hybrid_summary = summarize_scenario(hybrid)

    for pos in TRACKED_POSITIONS:
        pos_paradoxes = [r for r in paradoxes if r["pos"] == pos]
        pos_crossings = [r for r in rescue_crossings if r["pos"] == pos]
        pos_reverse = [r for r in reverse_rescue_crossings if r["pos"] == pos]
        by_position[pos] = {
            "documented": documented_summary[pos],
            "evidence_hybrid": hybrid_summary[pos],
            "paradoxical_raw_down_effective_up_count": len(pos_paradoxes),
            "new_rescue_crossing_count": len(pos_crossings),
            "reverse_rescue_crossing_count": len(pos_reverse),
        }

    # Exact architecture-level threshold jump sizes for non-Elite no-history roles.
    threshold_behavior = {}
    for role, role_mult in sorted(cfg["role_mult"].items()):
        role_mult = float(role_mult)
        if role == "Elite":
            threshold_behavior[role] = {
                "role_estimate": role_mult,
                "behavior": "Elite 0.65 floor takes precedence below 0.65",
                "jump_at_raw_0_15": 0.0,
            }
        elif role_mult > PM_MIN:
            threshold_behavior[role] = {
                "role_estimate": role_mult,
                "behavior": (
                    "no-history raw PM >0.15 stays raw; raw PM <=0.15 "
                    "jumps to role estimate"
                ),
                "jump_at_raw_0_15": role_mult - PM_MIN,
            }
        else:
            threshold_behavior[role] = {
                "role_estimate": role_mult,
                "behavior": "role estimate does not exceed floor",
                "jump_at_raw_0_15": 0.0,
            }

    blocked = bool(paradoxes or rescue_crossings or reverse_rescue_crossings)
    decision = (
        "BLOCK_BASELINE_OR_TRANSFORM_DEPLOYMENT_UNTIL_NO_HISTORY_RESCUE_IS_REDESIGNED"
        if blocked
        else "NO_RESCUE_DISCONTINUITY_FOUND_PROCEED_TO_TRANSFORM_SHAPE_AUDIT"
    )

    result = {
        "schema_version": 1,
        "phase": "Production V2 Phase 4",
        "status": "RESEARCH_ONLY_TRANSFORM_RESCUE_AUDIT",
        "production_mutation_authorized": False,
        "calibration_claim_authorized": False,
        "decision": decision,
        "deployment_blocked": blocked,
        "isolation_gate": {
            "documented_transform_rescue_reproduces_phase1_effective_pm": True,
            "phase1_pm_mismatch_count": 0,
        },
        "current_transform": {
            "formula": "clamp(-0.10 + 0.75 * ratio_to_replacement, 0.15, 1.55)",
            "floor": PM_MIN,
            "ceiling": PM_MAX,
        },
        "current_no_history_rescue_rule": (
            "After the Elite 0.65 floor, if raw PM <= 0.15, role estimate > raw PM, "
            "and player is in NO_REAL_PRODUCTION_HISTORY, effective PM becomes role estimate."
        ),
        "documented_ranks": documented_ranks,
        "evidence_hybrid_ranks": hybrid_ranks,
        "by_position": by_position,
        "role_threshold_behavior": threshold_behavior,
        "role_exposure": dict(sorted(role_exposure.items())),
        "paradoxical_raw_down_effective_up_count": len(paradoxes),
        "new_rescue_crossing_count": len(rescue_crossings),
        "reverse_rescue_crossing_count": len(reverse_rescue_crossings),
        "floor_status_crossing_count": len(floor_crossings),
        "paradoxical_players": paradoxes,
        "new_rescue_crossings": rescue_crossings,
        "reverse_rescue_crossings": reverse_rescue_crossings,
        "interpretation": (
            "A denominator or transform change is not isolated in the current architecture "
            "whenever it moves a no-history non-Elite player across raw PM 0.15. The effective "
            "production multiplier can jump to ROLE_MULT, creating discontinuous and potentially "
            "direction-reversing value movement. Any Production V2 redesign must resolve this "
            "before baseline or transform changes can be trusted."
        ),
        "next_step": (
            "Design and audit continuous no-history fallback semantics, then rerun the Phase-3 "
            "baseline comparison under those semantics before considering deployment."
            if blocked
            else
            "Proceed to broader transform-shape/floor-ceiling compression testing."
        ),
        "input_sha256": {
            str(PHASE1_PATH.relative_to(REPO_ROOT)): sha256(PHASE1_PATH),
            str(PHASE3_PATH.relative_to(REPO_ROOT)): sha256(PHASE3_PATH),
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
            str(SNAPSHOT_VALUES_PATH.relative_to(REPO_ROOT)): sha256(SNAPSHOT_VALUES_PATH),
        },
    }
    return round_numbers(result)


def pct(value):
    return "—" if value is None else f"{100.0 * float(value):.1f}%"


def render_md(result):
    lines = [
        "# Production V2 — Phase 4 Transform + No-History Rescue Audit",
        "",
        "## Decision",
        "",
        f"**{result['decision']}**",
        "",
        f"- Deployment blocked: **{'Yes' if result['deployment_blocked'] else 'No'}**",
        "- Production files mutated: **0**",
        "- Documented scenario reproduced Phase-1 effective production multipliers exactly: **Yes**",
        "",
        "## Why Phase 4 was required",
        "",
        "Phase 3 found that changing only the replacement denominator can push a no-history player across the raw-PM floor. The current production function then substitutes the player's role estimate, which can make effective PM rise even though raw PM fell.",
        "",
        "Current order of operations:",
        "",
        "1. Compute `raw PM = clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)`.",
        "2. Elite players below 0.65 are floored to 0.65.",
        "3. For other no-history players, if raw PM is `<= 0.15` and the role estimate is higher, effective PM becomes the role estimate.",
        "",
        "## Floor / rescue behavior by position",
        "",
        "| Pos | Doc floor | Hybrid floor | Doc rescues | Hybrid rescues | New rescue crossings | Raw↓ Effective↑ |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pos in TRACKED_POSITIONS:
        row = result["by_position"][pos]
        d = row["documented"]
        h = row["evidence_hybrid"]
        lines.append(
            f"| {pos} | {d['raw_floor_count']} ({pct(d['raw_floor_share'])}) | "
            f"{h['raw_floor_count']} ({pct(h['raw_floor_share'])}) | "
            f"{d['no_history_role_rescue_count']} | {h['no_history_role_rescue_count']} | "
            f"{row['new_rescue_crossing_count']} | "
            f"{row['paradoxical_raw_down_effective_up_count']} |"
        )

    lines += [
        "",
        "## Role threshold discontinuity",
        "",
        "| Role | Role estimate | Jump when no-history raw PM hits 0.15 |",
        "|---|---:|---:|",
    ]
    for role, row in result["role_threshold_behavior"].items():
        lines.append(
            f"| {role} | {row['role_estimate']:.2f} | {row['jump_at_raw_0_15']:+.2f} |"
        )

    lines += [
        "",
        "For non-Elite no-history players, the floor is therefore not merely a floor. It is a switch into a different model (`ROLE_MULT`). That is the discontinuity.",
        "",
        "## Paradoxical movers",
        "",
        "| Player | Pos | Role | Raw PM doc→hybrid | Effective PM doc→hybrid | Rescue doc→hybrid |",
        "|---|---|---|---|---|---|",
    ]
    if result["paradoxical_players"]:
        for row in result["paradoxical_players"][:30]:
            lines.append(
                f"| {row['player']} | {row['pos']} | {row['role']} | "
                f"{row['documented_raw_pm']:.3f}→{row['hybrid_raw_pm']:.3f} | "
                f"{row['documented_effective_pm']:.3f}→{row['hybrid_effective_pm']:.3f} | "
                f"{'yes' if row['documented_rescue'] else 'no'}→"
                f"{'yes' if row['hybrid_rescue'] else 'no'} |"
            )
    else:
        lines.append("| — | — | — | — | — | — |")

    lines += [
        "",
        "## Interpretation",
        "",
        result["interpretation"],
        "",
        "This means the Phase-3 evidence-hybrid rank set is **not rejected**, but it is **not yet a trustworthy deployable candidate** either. We first need continuous fallback semantics so changing a denominator cannot accidentally flip a player into a different valuation model.",
        "",
        "## Next step",
        "",
        result["next_step"],
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def canonical_json(result):
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def run_selftest():
    # Demonstrate the exact discontinuity abstractly.
    role_estimate = 0.22
    no_history = True

    raw_above = 0.151
    eff_above = raw_above
    raw_floor = 0.150
    eff_floor = role_estimate if no_history and role_estimate > raw_floor else raw_floor

    assert raw_floor < raw_above
    assert eff_floor > eff_above  # direction reversal caused by threshold rule

    # Elite behavior is separate: the 0.65 Elite floor takes precedence.
    elite_raw = 0.15
    elite_eff = 0.65 if elite_raw < 0.65 else elite_raw
    assert elite_eff == 0.65

    print("PASS Production V2 Phase-4 standalone self-test.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    if not args.write and not args.check:
        parser.error("choose --write or --check")

    result = build_result()
    json_text = canonical_json(result)
    md_text = render_md(result)

    if args.write:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json_text, encoding="utf-8")
        OUTPUT_MD.write_text(md_text, encoding="utf-8")
        print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
        print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")
        return

    if not OUTPUT_JSON.exists() or not OUTPUT_MD.exists():
        raise RuntimeError("Phase-4 outputs do not exist; run --write first")
    if OUTPUT_JSON.read_text(encoding="utf-8") != json_text:
        raise RuntimeError("Phase-4 JSON does not reproduce exactly")
    if OUTPUT_MD.read_text(encoding="utf-8") != md_text:
        raise RuntimeError("Phase-4 Markdown does not reproduce exactly")
    print("PASS Phase-4 exact-output check.")


if __name__ == "__main__":
    main()

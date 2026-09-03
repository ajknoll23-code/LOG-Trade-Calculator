#!/usr/bin/env python3
"""
Production V2 Phase 6 — affine transform compression audit.

PURPOSE
-------
Phase 5 removed the no-history ROLE_MULT threshold switch from the V2
candidate-present architecture. The next isolated structural question is the
legacy affine transform itself:

    clamp(-0.10 + 0.75 * ratio_to_replacement, 0.15, 1.55)

This audit DOES NOT choose replacement coefficients. It quantifies how much
production information the current hard floor/ceiling discards under both:
- documented replacement ranks, and
- the Phase-3 evidence-hybrid replacement ranks,

using the Phase-5 data-first candidate semantics.

Key facts:
- current floor 0.15 activates at ratio <= 1/3 of replacement;
- current ceiling 1.55 activates at ratio >= 2.20 x replacement.

The audit measures:
- floor/ceiling hit rates by position,
- how wide the underlying combined-production spread is inside the floor cohort,
- how many distinct production estimates are collapsed to one PM,
- sensitivity of floor-hit rates at diagnostic floors 0.05 / 0.10 / 0.15 / 0.20,
- value blast radius from those floor-only sensitivity settings,
- whether ceiling compression is material.

NO production files are mutated and NO alternative floor is recommended.
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

PHASE1_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase1_audit.json"
PHASE3_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase3_baseline_normalization_audit.json"
PHASE5_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase5_no_history_semantics_audit.json"
INDEX_HTML = REPO_ROOT / "index.html"
SNAPSHOT_VALUES_PATH = SCRIPTS / "validation" / "snapshot_values.py"

OUTPUT_JSON = REPO_ROOT / "research" / "production-v2" / "production_v2_phase6_transform_compression_audit.json"
OUTPUT_MD = REPO_ROOT / "research" / "production-v2" / "production_v2_phase6_transform_compression_audit.md"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")

PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
CURRENT_FLOOR = 0.15
CURRENT_CEILING = 1.55
DIAGNOSTIC_FLOORS = (0.05, 0.10, 0.15, 0.20)
GLOBAL_VALUE_SCALE = 55.0


def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


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
        baseline = float(anchor["phase1_combined_points"])
        if baseline <= 0:
            raise RuntimeError(f"{pos}: non-positive baseline")
        baselines[pos] = {
            "rank": rank,
            "player": anchor["key"],
            "combined_points": baseline,
            "cohort_size": len(cohort),
        }
    return baselines


def raw_unclamped(rec, baseline):
    combined = rec.get("phase1_combined_points")
    if combined is None:
        return None
    ratio = float(combined) / float(baseline)
    return PM_INTERCEPT + PM_RATIO_SLOPE * ratio


def data_first_effective_pm(role, clamped_pm):
    # Phase-5 semantics. The existing Elite safeguard remains intentionally fixed.
    if role == "Elite" and clamped_pm < 0.65:
        return 0.65
    return float(clamped_pm)


def final_value(key, raw_candidate_pm, effective_pm, cfg, snapshot_values):
    info = cfg["player_db"][key]
    pos = info["pos"]
    role = info["role"]
    age = info["age"]

    age_mult = snapshot_values.effective_age_multiplier(
        pos,
        age,
        role,
        key,
        effective_pm,
        raw_candidate_pm,
        cfg,
    )
    pw = float(cfg["position_weight"].get(pos, 1.0))
    value = math.floor(
        100 * pw * age_mult * effective_pm * GLOBAL_VALUE_SCALE + 0.5
    )
    return {
        "value": value,
        "age_mult": float(age_mult),
        "position_weight": pw,
    }


def scenario(phase1_players, ranks, floor, cfg, snapshot_values):
    baselines = build_baselines(phase1_players, ranks)
    rows = {}

    for key, rec in phase1_players.items():
        if rec.get("phase1_combined_points") is None:
            rows[key] = None
            continue

        baseline = baselines[rec["pos"]]["combined_points"]
        unclamped = raw_unclamped(rec, baseline)
        pm = clamp(unclamped, floor, CURRENT_CEILING)
        role = cfg["player_db"][key]["role"]
        effective = data_first_effective_pm(role, pm)
        fv = final_value(key, pm, effective, cfg, snapshot_values)

        rows[key] = {
            "player": key,
            "pos": rec["pos"],
            "role": role,
            "combined_points": float(rec["phase1_combined_points"]),
            "baseline_points": float(baseline),
            "ratio_to_baseline": float(rec["phase1_combined_points"]) / float(baseline),
            "raw_unclamped": unclamped,
            "raw_pm": pm,
            "effective_pm": effective,
            "floor_hit": unclamped <= floor + 1e-12,
            "ceiling_hit": unclamped >= CURRENT_CEILING - 1e-12,
            **fv,
        }
    return rows, baselines


def floor_threshold_ratio(floor):
    return (float(floor) - PM_INTERCEPT) / PM_RATIO_SLOPE


def ceiling_threshold_ratio():
    return (CURRENT_CEILING - PM_INTERCEPT) / PM_RATIO_SLOPE


def current_scenario_stats(rows):
    out = {}
    for pos in TRACKED_POSITIONS:
        pos_rows = [r for r in rows.values() if r and r["pos"] == pos]
        floor_rows = [r for r in pos_rows if r["floor_hit"]]
        ceiling_rows = [r for r in pos_rows if r["ceiling_hit"]]

        combined_floor = [r["combined_points"] for r in floor_rows]
        ratio_floor = [r["ratio_to_baseline"] for r in floor_rows]
        unclamped_floor = [r["raw_unclamped"] for r in floor_rows]

        unique_combined = len({round(x, 9) for x in combined_floor})
        unique_unclamped = len({round(x, 9) for x in unclamped_floor})
        distinct_collapsed = max(0, unique_unclamped - (1 if floor_rows else 0))

        out[pos] = {
            "n": len(pos_rows),
            "floor_count": len(floor_rows),
            "floor_share": len(floor_rows) / len(pos_rows) if pos_rows else None,
            "ceiling_count": len(ceiling_rows),
            "ceiling_share": len(ceiling_rows) / len(pos_rows) if pos_rows else None,
            "floor_unique_combined_estimates": unique_combined,
            "floor_unique_unclamped_pm_estimates": unique_unclamped,
            "distinct_pm_estimates_collapsed_by_floor": distinct_collapsed,
            "floor_combined_points_min": min(combined_floor) if combined_floor else None,
            "floor_combined_points_max": max(combined_floor) if combined_floor else None,
            "floor_combined_points_span": (
                max(combined_floor) - min(combined_floor)
                if combined_floor else None
            ),
            "floor_ratio_min": min(ratio_floor) if ratio_floor else None,
            "floor_ratio_max": max(ratio_floor) if ratio_floor else None,
            "floor_unclamped_pm_min": min(unclamped_floor) if unclamped_floor else None,
            "floor_unclamped_pm_max": max(unclamped_floor) if unclamped_floor else None,
        }
    return out


def compare_floor_to_current(current_rows, alternative_rows):
    out = {}
    for pos in TRACKED_POSITIONS:
        pct_changes = []
        pm_changes = []
        changed = 0
        for key, cur in current_rows.items():
            alt = alternative_rows.get(key)
            if cur is None or alt is None or cur["pos"] != pos:
                continue
            if cur["value"] != alt["value"]:
                changed += 1
            if cur["value"]:
                pct_changes.append(
                    (alt["value"] - cur["value"]) / cur["value"]
                )
            pm_changes.append(alt["effective_pm"] - cur["effective_pm"])

        out[pos] = {
            "changed_value_count": changed,
            "fundamental_value_change_pct": summarize(pct_changes),
            "effective_pm_delta": summarize(pm_changes),
        }
    return out


def build_floor_sensitivity(phase1_players, ranks, cfg, snapshot_values):
    current_rows, _ = scenario(
        phase1_players, ranks, CURRENT_FLOOR, cfg, snapshot_values
    )
    result = {}
    for floor in DIAGNOSTIC_FLOORS:
        rows, _ = scenario(phase1_players, ranks, floor, cfg, snapshot_values)
        stats = current_scenario_stats(rows)
        result[f"{floor:.2f}"] = {
            "floor": floor,
            "activation_ratio": floor_threshold_ratio(floor),
            "by_position": stats,
            "comparison_vs_current_0_15": compare_floor_to_current(
                current_rows, rows
            ),
        }
    return result


def build_result():
    phase1 = read_json(PHASE1_PATH)
    phase3 = read_json(PHASE3_PATH)
    phase5 = read_json(PHASE5_PATH)

    if phase1.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 1 must be research-only")
    if phase3.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 3 must be research-only")
    if phase5.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 5 must be research-only")

    decision5 = str(phase5.get("decision") or "")
    if decision5 != "CARRY_DATA_FIRST_NO_HISTORY_SEMANTICS_FORWARD_FOR_V2_CANDIDATE_COHORT":
        raise RuntimeError("Phase 5 data-first semantics were not accepted")

    inv = phase5.get("invariants") or {}
    if not inv.get("data_first_monotonicity_pass"):
        raise RuntimeError("Phase 5 monotonicity did not pass")

    phase1_players = phase1.get("players")
    documented_ranks = phase3.get("documented_ranks")
    hybrid_ranks = phase3.get("evidence_hybrid_ranks")
    if not isinstance(phase1_players, dict):
        raise RuntimeError("Phase 1 players missing")
    if not isinstance(documented_ranks, dict) or not isinstance(hybrid_ranks, dict):
        raise RuntimeError("Phase 3 ranks missing")

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    doc_rows, doc_baselines = scenario(
        phase1_players, documented_ranks, CURRENT_FLOOR, cfg, snapshot_values
    )
    hyb_rows, hyb_baselines = scenario(
        phase1_players, hybrid_ranks, CURRENT_FLOOR, cfg, snapshot_values
    )

    doc_stats = current_scenario_stats(doc_rows)
    hyb_stats = current_scenario_stats(hyb_rows)

    # Reproduce Phase-5 baseline effects exactly under data-first semantics.
    mismatches = []
    for pos in TRACKED_POSITIONS:
        expected = (
            phase5["by_position"][pos]
            ["hybrid_minus_documented_under_data_first"]
            ["fundamental_value_change_pct"]
        )
        actual_changes = []
        for key, doc in doc_rows.items():
            hyb = hyb_rows.get(key)
            if doc is None or hyb is None or doc["pos"] != pos:
                continue
            if doc["value"]:
                actual_changes.append((hyb["value"] - doc["value"]) / doc["value"])
        actual = summarize(actual_changes)
        for field in ("median", "p95_abs"):
            ev = expected.get(field)
            av = actual.get(field)
            if ev is None and av is None:
                continue
            if ev is None or av is None or round(float(av), 6) != round(float(ev), 6):
                mismatches.append({
                    "pos": pos,
                    "field": field,
                    "expected": ev,
                    "actual": av,
                })
    if mismatches:
        raise RuntimeError(
            "Phase-6 replay does not reproduce Phase-5 baseline effect; "
            f"sample={mismatches[:5]}"
        )

    doc_sensitivity = build_floor_sensitivity(
        phase1_players, documented_ranks, cfg, snapshot_values
    )
    hyb_sensitivity = build_floor_sensitivity(
        phase1_players, hybrid_ranks, cfg, snapshot_values
    )

    current_floor_material_positions = [
        pos for pos in TRACKED_POSITIONS
        if (doc_stats[pos]["floor_share"] or 0) >= 0.10
        or (hyb_stats[pos]["floor_share"] or 0) >= 0.10
    ]
    ceiling_material_positions = [
        pos for pos in TRACKED_POSITIONS
        if (doc_stats[pos]["ceiling_share"] or 0) >= 0.05
        or (hyb_stats[pos]["ceiling_share"] or 0) >= 0.05
    ]

    # Structural decision only. We explicitly do not choose a new floor.
    compression_material = bool(current_floor_material_positions)
    decision = (
        "KEEP_TRANSFORM_FLOOR_UNDEPLOYED_PENDING_PROSPECTIVE_CALIBRATION"
        if compression_material
        else "CURRENT_FLOOR_COMPRESSION_NOT_STRUCTURALLY_MATERIAL"
    )

    return round_numbers({
        "schema_version": 1,
        "phase": "Production V2 Phase 6",
        "status": "RESEARCH_ONLY_TRANSFORM_COMPRESSION_AUDIT",
        "production_mutation_authorized": False,
        "calibration_claim_authorized": False,
        "decision": decision,
        "current_transform": {
            "formula": "clamp(-0.10 + 0.75 * ratio_to_replacement, 0.15, 1.55)",
            "floor": CURRENT_FLOOR,
            "ceiling": CURRENT_CEILING,
            "floor_activation_ratio": floor_threshold_ratio(CURRENT_FLOOR),
            "ceiling_activation_ratio": ceiling_threshold_ratio(),
        },
        "interpretation": (
            "The hard PM floor is a compression mechanism, not merely a safety "
            "bound: every candidate below its activation ratio is assigned the "
            "same raw PM and loses production ordering at that layer. Phase 6 "
            "quantifies the compression but does not select a replacement floor "
            "without out-of-sample 2026 evidence."
        ),
        "documented_ranks": documented_ranks,
        "evidence_hybrid_ranks": hybrid_ranks,
        "documented_baselines": doc_baselines,
        "evidence_hybrid_baselines": hyb_baselines,
        "current_0_15_by_position": {
            "documented": doc_stats,
            "evidence_hybrid": hyb_stats,
        },
        "material_floor_compression_positions": current_floor_material_positions,
        "material_ceiling_compression_positions": ceiling_material_positions,
        "diagnostic_floor_sensitivity": {
            "note": (
                "0.05/0.10/0.15/0.20 are sensitivity points only. "
                "No floor is recommended by this audit."
            ),
            "documented_ranks": doc_sensitivity,
            "evidence_hybrid_ranks": hyb_sensitivity,
        },
        "next_step": (
            "Do not choose a new affine floor from cross-sectional aesthetics. "
            "Carry the floor sensitivity candidates into the prospective 2026 "
            "outcome evaluator frozen in Phase 2A. Separately audit the 31 "
            "missing-candidate players because their fallback semantics are still "
            "undefined for V2."
        ),
        "input_sha256": {
            str(PHASE1_PATH.relative_to(REPO_ROOT)): sha256(PHASE1_PATH),
            str(PHASE3_PATH.relative_to(REPO_ROOT)): sha256(PHASE3_PATH),
            str(PHASE5_PATH.relative_to(REPO_ROOT)): sha256(PHASE5_PATH),
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
            str(SNAPSHOT_VALUES_PATH.relative_to(REPO_ROOT)): sha256(SNAPSHOT_VALUES_PATH),
        },
    })


def pct(x):
    return "—" if x is None else f"{100.0 * float(x):.1f}%"


def signed_pct(x):
    return "—" if x is None else f"{100.0 * float(x):+.1f}%"


def render_md(result):
    lines = [
        "# Production V2 — Phase 6 Transform Compression Audit",
        "",
        "## Decision",
        "",
        f"**{result['decision']}**",
        "",
        "- Production files mutated: **0**",
        "- New transform coefficients selected: **No**",
        f"- Current floor activation: ratio ≤ **{result['current_transform']['floor_activation_ratio']:.3f}× replacement**",
        f"- Current ceiling activation: ratio ≥ **{result['current_transform']['ceiling_activation_ratio']:.2f}× replacement**",
        "",
        "The current `0.15` floor is not just a guardrail. It maps every player below one-third of replacement production to the same raw production multiplier.",
        "",
        "## Current 0.15 compression",
        "",
        "| Pos | Doc floor | Hybrid floor | Distinct PM estimates collapsed (doc / hybrid) | Ceiling doc / hybrid |",
        "|---|---:|---:|---:|---:|",
    ]

    doc = result["current_0_15_by_position"]["documented"]
    hyb = result["current_0_15_by_position"]["evidence_hybrid"]
    for pos in TRACKED_POSITIONS:
        lines.append(
            f"| {pos} | {doc[pos]['floor_count']} ({pct(doc[pos]['floor_share'])}) | "
            f"{hyb[pos]['floor_count']} ({pct(hyb[pos]['floor_share'])}) | "
            f"{doc[pos]['distinct_pm_estimates_collapsed_by_floor']} / "
            f"{hyb[pos]['distinct_pm_estimates_collapsed_by_floor']} | "
            f"{doc[pos]['ceiling_count']} / {hyb[pos]['ceiling_count']} |"
        )

    lines += [
        "",
        "## Floor sensitivity — hit rate by position",
        "",
        "These are diagnostics only, not recommendations.",
        "",
        "| Floor | Activation ratio | QB doc/hybrid | RB doc/hybrid | WR doc/hybrid | DL doc/hybrid |",
        "|---:|---:|---:|---:|---:|---:|",
    ]

    ds = result["diagnostic_floor_sensitivity"]["documented_ranks"]
    hs = result["diagnostic_floor_sensitivity"]["evidence_hybrid_ranks"]
    for floor_key in ("0.05", "0.10", "0.15", "0.20"):
        d = ds[floor_key]
        h = hs[floor_key]
        lines.append(
            f"| {float(floor_key):.2f} | {d['activation_ratio']:.3f}× | "
            f"{pct(d['by_position']['QB']['floor_share'])}/{pct(h['by_position']['QB']['floor_share'])} | "
            f"{pct(d['by_position']['RB']['floor_share'])}/{pct(h['by_position']['RB']['floor_share'])} | "
            f"{pct(d['by_position']['WR']['floor_share'])}/{pct(h['by_position']['WR']['floor_share'])} | "
            f"{pct(d['by_position']['DL']['floor_share'])}/{pct(h['by_position']['DL']['floor_share'])} |"
        )

    lines += [
        "",
        "## Value sensitivity versus the current 0.15 floor",
        "",
        "| Floor | QB P95 abs FV Δ (doc/hybrid) | RB P95 | WR P95 | DL P95 |",
        "|---:|---:|---:|---:|---:|",
    ]
    for floor_key in ("0.05", "0.10", "0.15", "0.20"):
        d = ds[floor_key]["comparison_vs_current_0_15"]
        h = hs[floor_key]["comparison_vs_current_0_15"]
        lines.append(
            f"| {float(floor_key):.2f} | "
            f"{pct(d['QB']['fundamental_value_change_pct'].get('p95_abs'))}/"
            f"{pct(h['QB']['fundamental_value_change_pct'].get('p95_abs'))} | "
            f"{pct(d['RB']['fundamental_value_change_pct'].get('p95_abs'))}/"
            f"{pct(h['RB']['fundamental_value_change_pct'].get('p95_abs'))} | "
            f"{pct(d['WR']['fundamental_value_change_pct'].get('p95_abs'))}/"
            f"{pct(h['WR']['fundamental_value_change_pct'].get('p95_abs'))} | "
            f"{pct(d['DL']['fundamental_value_change_pct'].get('p95_abs'))}/"
            f"{pct(h['DL']['fundamental_value_change_pct'].get('p95_abs'))} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        result["interpretation"],
        "",
        f"Positions with ≥10% floor compression under at least one normalization candidate: **{', '.join(result['material_floor_compression_positions']) or 'None'}**.",
        "",
        f"Positions with ≥5% ceiling compression: **{', '.join(result['material_ceiling_compression_positions']) or 'None'}**.",
        "",
        "The correct response is **not** to pick a prettier floor by eye. Phase 2A already froze the preseason evidence needed to test these candidates prospectively against real 2026 outcomes.",
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
    assert abs(floor_threshold_ratio(0.15) - (1.0 / 3.0)) < 1e-12
    assert abs(ceiling_threshold_ratio() - 2.2) < 1e-12
    assert floor_threshold_ratio(0.05) < floor_threshold_ratio(0.10) < floor_threshold_ratio(0.15) < floor_threshold_ratio(0.20)

    # Lowering only the floor cannot increase a clamped PM for the same input.
    x = 0.08
    assert clamp(x, 0.05, CURRENT_CEILING) <= clamp(x, 0.15, CURRENT_CEILING)

    # Data-first non-Elite semantics preserve raw PM ordering.
    assert data_first_effective_pm("Speculative", 0.10) < data_first_effective_pm("Speculative", 0.15)

    # Existing Elite floor remains separately held fixed.
    assert data_first_effective_pm("Elite", 0.15) == 0.65

    print("PASS Production V2 Phase-6 standalone self-test.")


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
        raise RuntimeError("Phase-6 outputs do not exist; run --write first")
    if OUTPUT_JSON.read_text(encoding="utf-8") != json_text:
        raise RuntimeError("Phase-6 JSON does not reproduce exactly")
    if OUTPUT_MD.read_text(encoding="utf-8") != md_text:
        raise RuntimeError("Phase-6 Markdown does not reproduce exactly")
    print("PASS Phase-6 exact-output check.")


if __name__ == "__main__":
    main()

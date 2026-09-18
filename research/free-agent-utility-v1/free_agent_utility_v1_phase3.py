#!/usr/bin/env python3
"""Free Agent Utility V1 — Phase 3 bounded candidate selection.

Research only.

Phase 2 established cohort-relative delta transport as the correct geometry.
Phase 3 holds transport strength fixed at 15% and tests absolute score-shift
caps. The selection rule is preregistered: choose the LARGEST cap that passes
every safety gate, preserving as much useful 4for4 signal as possible without
letting the secondary waiver signal dominate the existing board.

No player-level provider data or derived utility scores are persisted.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
RESEARCH = ROOT / "research" / "free-agent-utility-v1"
PHASE1_SCRIPT = RESEARCH / "free_agent_utility_v1_phase1.py"
PHASE2_SCRIPT = RESEARCH / "free_agent_utility_v1_phase2.py"
PHASE2_SUMMARY = RESEARCH / "phase2_delta_transport_summary.json"

OUT_JSON = RESEARCH / "phase3_bounded_candidate_summary.json"
OUT_MD = RESEARCH / "phase3_bounded_candidate_summary.md"

TRACKED = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
TRANSPORT_STRENGTH = 0.15
CAPS = (0.04, 0.06, 0.08)

MIN_TOP5_OVERLAP = 0.80
MIN_TOP10_OVERLAP = 0.80
MAX_POSITION_P95_ABS_RANK_MOVE = 8.0
MAX_POSITION_MAX_ABS_RANK_MOVE = 10.0
MIN_TOTAL_MATCHED_MOVE_GE3 = 40


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def summarize(values):
    vals = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not vals:
        return {"n": 0}

    def pct(q):
        if len(vals) == 1:
            return vals[0]
        x = (len(vals) - 1) * q
        lo = int(math.floor(x))
        hi = int(math.ceil(x))
        if lo == hi:
            return vals[lo]
        f = x - lo
        return vals[lo] * (1 - f) + vals[hi] * f

    abs_vals = sorted(abs(v) for v in vals)

    def abs_pct(q):
        if len(abs_vals) == 1:
            return abs_vals[0]
        x = (len(abs_vals) - 1) * q
        lo = int(math.floor(x))
        hi = int(math.ceil(x))
        if lo == hi:
            return abs_vals[lo]
        f = x - lo
        return abs_vals[lo] * (1 - f) + abs_vals[hi] * f

    return {
        "n": len(vals),
        "mean": statistics.fmean(vals),
        "median": statistics.median(vals),
        "median_abs": statistics.median(abs_vals),
        "p90_abs": abs_pct(0.90),
        "p95_abs": abs_pct(0.95),
        "max_abs": max(abs_vals),
        "min": vals[0],
        "max": vals[-1],
    }


def top_overlap(a, b, n):
    effective = min(n, len(a), len(b))
    if effective <= 0:
        return {
            "requested_n": n, "effective_n": 0,
            "overlap_count": 0, "overlap_share": None,
        }
    aa = {k for k, r in a.items() if r <= effective}
    bb = {k for k, r in b.items() if r <= effective}
    overlap = len(aa & bb)
    return {
        "requested_n": n,
        "effective_n": effective,
        "overlap_count": overlap,
        "overlap_share": overlap / effective,
    }


def build_matched_delta_inputs(rows, provider_rows, phase1):
    provider_idx = phase1.index_provider(provider_rows)
    by_pos = defaultdict(list)
    for r in rows:
        by_pos[r["pos"]].append(r)

    result = {}
    for pos in TRACKED:
        cohort = by_pos.get(pos, [])
        full_log_values = {r["sleeper_id"]: float(r["value"]) for r in cohort}
        full_log_pct = phase1.midrank_percentiles(full_log_values)

        matched = []
        provider_points = {}
        for r in cohort:
            cands = provider_idx.get((r["norm_name"], pos, r["team"]), [])
            if len(cands) == 1:
                matched.append(r)
                provider_points[r["sleeper_id"]] = float(cands[0]["points"])
            elif len(cands) > 1:
                raise RuntimeError(
                    f"ambiguous provider identity for {r['name']} {pos} {r['team']}"
                )

        matched_log_values = {
            r["sleeper_id"]: float(r["value"]) for r in matched
        }
        matched_log_pct = phase1.midrank_percentiles(matched_log_values)
        matched_f4_pct = phase1.midrank_percentiles(provider_points)
        deltas = {
            sid: matched_f4_pct[sid] - matched_log_pct[sid]
            for sid in matched_log_pct
        }
        if deltas and abs(statistics.fmean(deltas.values())) > 1e-12:
            raise RuntimeError(f"{pos}: matched delta lost mean-zero property")

        result[pos] = {
            "cohort": cohort,
            "full_log_values": full_log_values,
            "full_log_pct": full_log_pct,
            "deltas": deltas,
        }
    return result


def evaluate_cap(inputs, cap, phase1):
    by_position = {}
    all_matched_moves = []
    all_applied_shifts = []
    matched_n = 0
    capped_n = 0

    for pos in TRACKED:
        pack = inputs[pos]
        cohort = pack["cohort"]
        full_log_values = pack["full_log_values"]
        full_log_pct = pack["full_log_pct"]
        deltas = pack["deltas"]

        candidate_scores = {}
        applied_shifts = {}
        position_capped = 0

        for r in cohort:
            sid = r["sleeper_id"]
            base = full_log_pct[sid]
            if sid not in deltas:
                candidate_scores[sid] = base
                continue

            raw_shift = TRANSPORT_STRENGTH * deltas[sid]
            shift = clamp(raw_shift, -cap, cap)
            if abs(shift - raw_shift) > 1e-12:
                position_capped += 1
            applied_shifts[sid] = shift
            candidate_scores[sid] = clamp(base + shift, 0.0, 1.0)

        for r in cohort:
            sid = r["sleeper_id"]
            if sid not in deltas and candidate_scores[sid] != full_log_pct[sid]:
                raise RuntimeError(f"{pos}: unmatched player score changed")

        base_rank = phase1.ranks_desc(full_log_values)
        candidate_rank = phase1.ranks_desc(candidate_scores)

        matched_moves = [
            float(base_rank[sid] - candidate_rank[sid])
            for sid in deltas
        ]
        all_moves = [
            float(base_rank[sid] - candidate_rank[sid])
            for sid in base_rank
        ]

        top5 = top_overlap(base_rank, candidate_rank, 5)
        top10 = top_overlap(base_rank, candidate_rank, 10)
        rank_summary = summarize(matched_moves)

        position_pass = (
            top5["overlap_share"] >= MIN_TOP5_OVERLAP
            and top10["overlap_share"] >= MIN_TOP10_OVERLAP
            and rank_summary["p95_abs"] <= MAX_POSITION_P95_ABS_RANK_MOVE
            and rank_summary["max_abs"] <= MAX_POSITION_MAX_ABS_RANK_MOVE
        )

        by_position[pos] = {
            "current_n": len(cohort),
            "matched_n": len(deltas),
            "coverage": len(deltas) / len(cohort) if cohort else None,
            "capped_match_count": position_capped,
            "applied_shift": summarize(applied_shifts.values()),
            "spearman": phase1.spearman_from_ranks(base_rank, candidate_rank),
            "rank_move_all": summarize(all_moves),
            "rank_move_matched": rank_summary,
            "promotions": sum(x > 0 for x in matched_moves),
            "demotions": sum(x < 0 for x in matched_moves),
            "unchanged": sum(x == 0 for x in matched_moves),
            "move_ge_3_count": sum(abs(x) >= 3 for x in matched_moves),
            "move_ge_5_count": sum(abs(x) >= 5 for x in matched_moves),
            "top5_overlap": top5,
            "top10_overlap": top10,
            "safety_gate_pass": position_pass,
        }

        all_matched_moves.extend(matched_moves)
        all_applied_shifts.extend(applied_shifts.values())
        matched_n += len(deltas)
        capped_n += position_capped

    total_move3 = sum(abs(x) >= 3 for x in all_matched_moves)
    all_positions_pass = all(
        by_position[pos]["safety_gate_pass"] for pos in TRACKED
    )
    impact_floor_pass = total_move3 >= MIN_TOTAL_MATCHED_MOVE_GE3
    candidate_pass = all_positions_pass and impact_floor_pass

    return {
        "cap": cap,
        "transport_strength": TRANSPORT_STRENGTH,
        "matched_n": matched_n,
        "capped_match_count": capped_n,
        "applied_shift": summarize(all_applied_shifts),
        "matched_rank_move": summarize(all_matched_moves),
        "matched_move_ge_3_count": total_move3,
        "matched_move_ge_5_count": sum(abs(x) >= 5 for x in all_matched_moves),
        "all_positions_safety_pass": all_positions_pass,
        "impact_floor_pass": impact_floor_pass,
        "candidate_pass": candidate_pass,
        "by_position": by_position,
    }


def build_result(offense: Path, dl: Path, lb: Path, db: Path):
    phase1 = load_module(PHASE1_SCRIPT, "fa_util_phase1_for_phase3")

    phase2_summary = json.loads(PHASE2_SUMMARY.read_text(encoding="utf-8"))
    if phase2_summary.get("status") != "PASS_PHASE2_COHORT_RELATIVE_DELTA_TRANSPORT":
        raise RuntimeError("Phase 2 green summary missing or changed")
    if phase2_summary.get("production_changes") is not False:
        raise RuntimeError("Phase 2 unexpectedly changed production")
    if phase2_summary["methodology"]["primary_transport_strength"] != 0.25:
        raise RuntimeError("Phase 2 reference methodology drifted")

    current, runtime_meta = phase1.current_board_rows()
    data_backed = [r for r in current if r["has_real_data"]]
    provider = (
        phase1.read_offense(offense)
        + phase1.read_idp(dl, "DL")
        + phase1.read_idp(lb, "LB")
        + phase1.read_idp(db, "DB")
    )

    inputs = build_matched_delta_inputs(data_backed, provider, phase1)
    variants = {
        f"{int(round(cap * 1000)):03d}bp": evaluate_cap(inputs, cap, phase1)
        for cap in CAPS
    }

    passing = [
        v for v in variants.values()
        if v["candidate_pass"]
    ]
    selected = max(passing, key=lambda v: v["cap"]) if passing else None

    status = (
        "PASS_PHASE3_BOUNDED_CANDIDATE_SELECTED"
        if selected is not None
        else "HOLD_PHASE3_NO_SAFE_CANDIDATE"
    )

    return {
        "schema_version": 1,
        "study_id": "free-agent-utility-v1",
        "phase": 3,
        "status": status,
        "research_only": True,
        "production_changes": False,
        "production_authorized": False,
        "realized_outcomes_read": False,
        "private_row_level_4for4_output_persisted": False,
        "player_level_derived_4for4_output_persisted": False,
        "phase2_reference": {
            "summary_git_blob_expected": "22e592737b1da48ce8c964f672641f612790f04c",
            "phase2_primary_transport_strength":
                phase2_summary["methodology"]["primary_transport_strength"],
            "phase2_primary_matched_n": phase2_summary["primary"]["matched_n"],
        },
        "methodology": {
            "transport_strength": TRANSPORT_STRENGTH,
            "candidate_absolute_score_shift_caps": list(CAPS),
            "selection_rule": "largest_cap_passing_every_safety_gate",
            "unmatched_score": "exact_existing_log_percentile",
        },
        "safety_gates": {
            "minimum_top5_overlap_each_position": MIN_TOP5_OVERLAP,
            "minimum_top10_overlap_each_position": MIN_TOP10_OVERLAP,
            "maximum_position_p95_absolute_rank_move":
                MAX_POSITION_P95_ABS_RANK_MOVE,
            "maximum_position_absolute_rank_move":
                MAX_POSITION_MAX_ABS_RANK_MOVE,
            "minimum_total_matched_moves_3plus":
                MIN_TOTAL_MATCHED_MOVE_GE3,
        },
        "source_integrity": {
            "runtime": runtime_meta,
            "private_source_sha256": dict(phase1.EXPECTED_SHA256),
            "data_backed_free_agent_count": len(data_backed),
            "data_backed_by_position":
                dict(sorted(Counter(r["pos"] for r in data_backed).items())),
        },
        "variants": variants,
        "selected_candidate": selected,
    }


def render_md(result):
    lines = [
        "# Free Agent Utility V1 — Phase 3 Bounded Candidate Selection",
        "",
        f"Status: **{result['status']}**",
        "",
        "Research-only. No production file or live ranking changed.",
        "",
        "Phase 3 fixes transport strength at 15% and selects the largest "
        "absolute score-shift cap that passes every preregistered safety gate.",
        "",
    ]

    if result["selected_candidate"] is None:
        lines.extend([
            "## Selection",
            "",
            "**No cap passed every safety gate. Production remains blocked.**",
            "",
        ])
    else:
        s = result["selected_candidate"]
        lines.extend([
            "## Selected candidate",
            "",
            f"- Transport strength: **{int(TRANSPORT_STRENGTH * 100)}%**",
            f"- Absolute score-shift cap: **±{s['cap']:.3f}**",
            f"- Matched free agents: **{s['matched_n']}**",
            f"- Capped matches: **{s['capped_match_count']}**",
            f"- 3+ spot moves: **{s['matched_move_ge_3_count']}**",
            f"- 5+ spot moves: **{s['matched_move_ge_5_count']}**",
            "",
        ])

    lines.extend([
        "## Candidate comparison",
        "",
        "| Cap | Pass | Capped | >=3 moves | >=5 moves | Median abs move | P95 abs move |",
        "| ---: | :---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for key in sorted(result["variants"]):
        v = result["variants"][key]
        lines.append(
            f"| ±{v['cap']:.3f} | {'YES' if v['candidate_pass'] else 'NO'} | "
            f"{v['capped_match_count']} | {v['matched_move_ge_3_count']} | "
            f"{v['matched_move_ge_5_count']} | "
            f"{v['matched_rank_move']['median_abs']:.1f} | "
            f"{v['matched_rank_move']['p95_abs']:.1f} |"
        )

    if result["selected_candidate"] is not None:
        s = result["selected_candidate"]
        lines.extend([
            "",
            "## Selected candidate by position",
            "",
            "| Pos | Match | Spearman | >=3 | >=5 | Top-5 | Top-10 | P95 move | Max move |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for pos in TRACKED:
            r = s["by_position"][pos]
            lines.append(
                f"| {pos} | {r['matched_n']} | {r['spearman']:.4f} | "
                f"{r['move_ge_3_count']} | {r['move_ge_5_count']} | "
                f"{r['top5_overlap']['overlap_share']:.0%} | "
                f"{r['top10_overlap']['overlap_share']:.0%} | "
                f"{r['rank_move_matched']['p95_abs']:.1f} | "
                f"{r['rank_move_matched']['max_abs']:.1f} |"
            )

    lines.extend([
        "",
        "## Guards",
        "",
        "- Unmatched player scores remain exact LOG scores.",
        "- No raw 4for4 rows are persisted.",
        "- No player-level projection/rank/delta/utility score is persisted.",
        "- Fundamental Value and Free-Agent Production V2 remain frozen.",
        "- free-agent-board.html remains unchanged.",
        "- Phase 3 does not authorize production deployment.",
        "",
    ])
    return "\n".join(lines)


def run_selftest():
    assert clamp(0.10, -0.04, 0.04) == 0.04
    assert clamp(-0.10, -0.04, 0.04) == -0.04
    assert clamp(0.02, -0.04, 0.04) == 0.02

    fake = {
        "QB": {"safety_gate_pass": True},
        "RB": {"safety_gate_pass": True},
    }
    assert all(x["safety_gate_pass"] for x in fake.values())
    print("free_agent_utility_v1_phase3 self-test passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--offense", type=Path)
    parser.add_argument("--dl", type=Path)
    parser.add_argument("--lb", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return 0

    if any(p is None for p in (args.offense, args.dl, args.lb, args.db)):
        parser.error("--offense, --dl, --lb, and --db are required unless --selftest is used")

    result = build_result(args.offense, args.dl, args.lb, args.db)

    if args.write:
        OUT_JSON.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        OUT_MD.write_text(render_md(result), encoding="utf-8")

    selected = result["selected_candidate"]
    print(json.dumps({
        "status": result["status"],
        "selected_cap": None if selected is None else selected["cap"],
        "selected_move_ge_3": None if selected is None else selected["matched_move_ge_3_count"],
        "selected_move_ge_5": None if selected is None else selected["matched_move_ge_5_count"],
        "production_changes": result["production_changes"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

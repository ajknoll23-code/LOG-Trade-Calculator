#!/usr/bin/env python3
"""Free Agent Utility V1 — Phase 2 cohort-relative delta transport.

Research only. Phase 1 proved the private 4for4 source contains independent
ordering signal, but also exposed a scale mismatch:

* LOG percentile was measured within the free-agent cohort.
* 4for4 percentile was measured within the provider's full positional universe.

That is not an apples-to-apples blend and systematically depressed many
offensive free agents. Phase 2 removes that level mismatch.

For each position:
1. Keep the current LOG percentile across the full data-backed FA cohort.
2. Among only players with an exact 4for4 match, compute:
   a. LOG percentile inside that matched subset.
   b. 4for4 percentile inside that same matched subset.
3. Define delta = 4for4_matched_pct - LOG_matched_pct.
4. Transport only a bounded fraction of that delta onto the full-cohort
   LOG percentile.
5. Unmatched player scores remain exactly unchanged.

No player-level 4for4 data or derived utility score is persisted.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Iterable

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
RESEARCH = ROOT / "research" / "free-agent-utility-v1"
PHASE1_SCRIPT = RESEARCH / "free_agent_utility_v1_phase1.py"
PHASE1_SUMMARY = RESEARCH / "phase1_shadow_summary.json"

OUT_JSON = RESEARCH / "phase2_delta_transport_summary.json"
OUT_MD = RESEARCH / "phase2_delta_transport_summary.md"

TRACKED = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
STRENGTHS = (0.15, 0.25, 0.35)
PRIMARY_STRENGTH = 0.25


def load_phase1():
    spec = importlib.util.spec_from_file_location("fa_utility_v1_phase1_core", PHASE1_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to import Free Agent Utility V1 Phase 1 core")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def percentile(sorted_values: list[float], q: float):
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    x = (len(sorted_values) - 1) * q
    lo = int(math.floor(x))
    hi = int(math.ceil(x))
    if lo == hi:
        return sorted_values[lo]
    f = x - lo
    return sorted_values[lo] * (1 - f) + sorted_values[hi] * f


def summarize(values: Iterable[float]) -> dict:
    vals = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not vals:
        return {"n": 0}
    abs_vals = sorted(abs(v) for v in vals)
    return {
        "n": len(vals),
        "mean": statistics.fmean(vals),
        "median": statistics.median(vals),
        "median_abs": statistics.median(abs_vals),
        "p90_abs": percentile(abs_vals, 0.90),
        "p95_abs": percentile(abs_vals, 0.95),
        "max_abs": max(abs_vals),
        "min": vals[0],
        "max": vals[-1],
    }


def top_overlap(a: dict[str, int], b: dict[str, int], n: int) -> dict:
    if not a or not b:
        return {
            "requested_n": n,
            "effective_n": 0,
            "overlap_count": 0,
            "overlap_share": None,
        }
    effective = min(n, len(a), len(b))
    aa = {k for k, r in a.items() if r <= effective}
    bb = {k for k, r in b.items() if r <= effective}
    overlap = len(aa & bb)
    return {
        "requested_n": n,
        "effective_n": effective,
        "overlap_count": overlap,
        "overlap_share": overlap / effective if effective else None,
    }


def provider_inputs(phase1, offense: Path, dl: Path, lb: Path, db: Path) -> list[dict]:
    return (
        phase1.read_offense(offense)
        + phase1.read_idp(dl, "DL")
        + phase1.read_idp(lb, "LB")
        + phase1.read_idp(db, "DB")
    )


def evaluate_strength(rows: list[dict], provider_rows: list[dict], strength: float, phase1) -> dict:
    provider_idx = phase1.index_provider(provider_rows)
    current_by_pos = defaultdict(list)
    for row in rows:
        current_by_pos[row["pos"]].append(row)

    by_position = {}
    all_matched_moves = []
    all_deltas = []
    matched_n = 0
    total_clipped = 0

    for pos in TRACKED:
        cohort = current_by_pos.get(pos, [])
        if not cohort:
            by_position[pos] = {
                "current_n": 0,
                "matched_n": 0,
                "coverage": None,
            }
            continue

        full_log_values = {
            r["sleeper_id"]: float(r["value"])
            for r in cohort
        }
        full_log_pct = phase1.midrank_percentiles(full_log_values)

        matched = []
        provider_points_by_sid = {}
        for r in cohort:
            cands = provider_idx.get((r["norm_name"], pos, r["team"]), [])
            if len(cands) == 1:
                matched.append(r)
                provider_points_by_sid[r["sleeper_id"]] = float(cands[0]["points"])
            elif len(cands) > 1:
                raise RuntimeError(
                    f"ambiguous provider identity for {r['name']} {pos} {r['team']}"
                )

        matched_log_values = {
            r["sleeper_id"]: float(r["value"])
            for r in matched
        }
        matched_log_pct = phase1.midrank_percentiles(matched_log_values)
        matched_f4_pct = phase1.midrank_percentiles(provider_points_by_sid)

        deltas = {
            sid: matched_f4_pct[sid] - matched_log_pct[sid]
            for sid in matched_log_pct
        }

        # Because both percentile vectors are defined on the same matched
        # cohort, their means should be mathematically identical. This is the
        # key scale-balance property Phase 1 lacked.
        delta_mean = statistics.fmean(deltas.values()) if deltas else 0.0
        if abs(delta_mean) > 1e-12:
            raise RuntimeError(
                f"{pos}: matched-cohort percentile delta is not mean-zero: {delta_mean}"
            )

        candidate_scores = {}
        clipped = 0
        for r in cohort:
            sid = r["sleeper_id"]
            base = full_log_pct[sid]
            if sid not in deltas:
                candidate_scores[sid] = base
                continue
            raw = base + strength * deltas[sid]
            bounded = clamp(raw)
            if abs(raw - bounded) > 1e-12:
                clipped += 1
            candidate_scores[sid] = bounded

        # Explicitly prove unmatched player scores themselves did not move.
        for r in cohort:
            sid = r["sleeper_id"]
            if sid not in deltas and candidate_scores[sid] != full_log_pct[sid]:
                raise RuntimeError(f"{pos}: unmatched score changed for {sid}")

        base_rank = phase1.ranks_desc(full_log_values)
        candidate_rank = phase1.ranks_desc(candidate_scores)
        matched_ids = set(deltas)
        matched_moves = [
            float(base_rank[sid] - candidate_rank[sid])
            for sid in matched_ids
        ]
        all_moves = [
            float(base_rank[sid] - candidate_rank[sid])
            for sid in base_rank
        ]

        promotions = sum(x > 0 for x in matched_moves)
        demotions = sum(x < 0 for x in matched_moves)
        unchanged = sum(x == 0 for x in matched_moves)

        by_position[pos] = {
            "current_n": len(cohort),
            "matched_n": len(matched),
            "coverage": len(matched) / len(cohort),
            "delta_distribution": summarize(deltas.values()),
            "clipped_score_count": clipped,
            "spearman": phase1.spearman_from_ranks(base_rank, candidate_rank),
            "rank_move_all": summarize(all_moves),
            "rank_move_matched": summarize(matched_moves),
            "promotions": promotions,
            "demotions": demotions,
            "unchanged": unchanged,
            "move_ge_3_count": sum(abs(x) >= 3 for x in matched_moves),
            "move_ge_5_count": sum(abs(x) >= 5 for x in matched_moves),
            "top5_overlap": top_overlap(base_rank, candidate_rank, 5),
            "top10_overlap": top_overlap(base_rank, candidate_rank, 10),
        }

        all_matched_moves.extend(matched_moves)
        all_deltas.extend(deltas.values())
        matched_n += len(matched)
        total_clipped += clipped

    return {
        "transport_strength": strength,
        "cohort_n": len(rows),
        "matched_n": matched_n,
        "coverage": matched_n / len(rows) if rows else None,
        "delta_distribution": summarize(all_deltas),
        "matched_rank_move": summarize(all_matched_moves),
        "matched_move_ge_3_count": sum(abs(x) >= 3 for x in all_matched_moves),
        "matched_move_ge_5_count": sum(abs(x) >= 5 for x in all_matched_moves),
        "clipped_score_count": total_clipped,
        "by_position": by_position,
    }


def build_result(offense: Path, dl: Path, lb: Path, db: Path) -> dict:
    phase1 = load_phase1()

    phase1_summary = json.loads(PHASE1_SUMMARY.read_text(encoding="utf-8"))
    if phase1_summary.get("status") != "PASS_PHASE1_PRIVATE_SHADOW_COMPLETE":
        raise RuntimeError("Phase 1 green summary is missing or changed")
    if phase1_summary.get("production_changes") is not False:
        raise RuntimeError("Phase 1 unexpectedly reports production changes")
    if phase1_summary.get("private_row_level_4for4_output_persisted") is not False:
        raise RuntimeError("Phase 1 privacy contract changed")

    current, runtime_meta = phase1.current_board_rows()
    data_backed = [r for r in current if r["has_real_data"]]
    provider = provider_inputs(phase1, offense, dl, lb, db)

    variants = {
        f"{int(s * 100)}pct": evaluate_strength(data_backed, provider, s, phase1)
        for s in STRENGTHS
    }
    primary = variants[f"{int(PRIMARY_STRENGTH * 100)}pct"]

    coverage_ok = all(
        primary["by_position"][pos].get("coverage") is not None
        and primary["by_position"][pos]["coverage"] >= 0.50
        for pos in TRACKED
    )
    scale_balance_ok = all(
        abs(primary["by_position"][pos]["delta_distribution"].get("mean", 0.0)) <= 1e-12
        for pos in TRACKED
    )
    nondegenerate = primary["matched_move_ge_3_count"] >= 20

    decision = (
        "PASS_PHASE2_COHORT_RELATIVE_DELTA_TRANSPORT"
        if coverage_ok and scale_balance_ok and nondegenerate
        else "HOLD_PHASE2_FOR_REVIEW"
    )

    return {
        "schema_version": 1,
        "study_id": "free-agent-utility-v1",
        "phase": 2,
        "status": decision,
        "research_only": True,
        "production_changes": False,
        "production_authorized": False,
        "realized_outcomes_read": False,
        "private_row_level_4for4_output_persisted": False,
        "player_level_derived_4for4_output_persisted": False,
        "phase1_reference": {
            "summary_git_blob_expected": "065ed1bdaf0b37ff1ed6979cf02dec35da58a73f",
            "phase1_primary_weight": phase1_summary["methodology"]["primary_fourforfour_weight"],
            "phase1_primary_matched_n": phase1_summary["primary"]["matched_n"],
            "phase1_primary_coverage": phase1_summary["primary"]["coverage"],
            "phase1_raw_blend_median_projection_minus_log_percentile":
                phase1_summary["primary"]["projection_minus_log_percentile"]["median"],
        },
        "methodology": {
            "problem_fixed": "provider_full_position_percentile_vs_free_agent_percentile_scale_mismatch",
            "cohort": "current_free_agents_with_live_board_hasRealData_true",
            "identity": "exact_normalized_name_plus_position_plus_normalized_team",
            "base_signal": "full_data_backed_free_agent_cohort_log_percentile",
            "delta_signal": (
                "fourforfour_percentile_within_exact_matched_fa_subset_minus_"
                "log_percentile_within_same_exact_matched_fa_subset"
            ),
            "candidate_transport_strengths": list(STRENGTHS),
            "primary_transport_strength": PRIMARY_STRENGTH,
            "candidate_score": "clamp(full_log_pct + strength * matched_subset_delta, 0, 1)",
            "unmatched_score": "exact_full_log_percentile",
        },
        "gates": {
            "every_position_coverage_at_least_50pct": coverage_ok,
            "matched_subset_delta_mean_zero_by_construction": scale_balance_ok,
            "primary_has_at_least_20_matched_moves_of_3plus": nondegenerate,
        },
        "source_integrity": {
            "runtime": runtime_meta,
            "private_source_sha256": dict(phase1.EXPECTED_SHA256),
            "private_source_row_counts": dict(phase1.EXPECTED_ROW_COUNTS),
            "data_backed_free_agent_count": len(data_backed),
            "data_backed_by_position": dict(sorted(Counter(r["pos"] for r in data_backed).items())),
        },
        "variants": variants,
        "primary": primary,
    }


def render_md(result: dict) -> str:
    p = result["primary"]
    lines = [
        "# Free Agent Utility V1 — Phase 2 Cohort-Relative Delta Transport",
        "",
        f"Status: **{result['status']}**",
        "",
        "Research-only. No production file or live ranking changed.",
        "",
        "## Why Phase 2 exists",
        "",
        "Phase 1 mixed a free-agent-relative LOG percentile with a full-player-pool "
        "4for4 percentile. Phase 2 removes that level mismatch and transports only "
        "the relative ordering disagreement among the exact same matched free agents.",
        "",
        "## Frozen primary transport",
        "",
        f"- 4for4 disagreement transport strength: **{int(PRIMARY_STRENGTH * 100)}%**",
        f"- Data-backed FA cohort: **{p['cohort_n']}**",
        f"- Exact 4for4 matches: **{p['matched_n']}** ({p['coverage']:.1%})",
        f"- 3+ spot matched moves: **{p['matched_move_ge_3_count']}**",
        f"- 5+ spot matched moves: **{p['matched_move_ge_5_count']}**",
        f"- Clipped scores: **{p['clipped_score_count']}**",
        "",
        "## Position diagnostics",
        "",
        "| Pos | Cohort | Match | Coverage | Delta mean | Spearman | >=3 | >=5 | Top-5 | Top-10 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for pos in TRACKED:
        r = p["by_position"][pos]
        lines.append(
            f"| {pos} | {r['current_n']} | {r['matched_n']} | {r['coverage']:.1%} | "
            f"{r['delta_distribution']['mean']:.6f} | {r['spearman']:.4f} | "
            f"{r['move_ge_3_count']} | {r['move_ge_5_count']} | "
            f"{r['top5_overlap']['overlap_share']:.0%} | "
            f"{r['top10_overlap']['overlap_share']:.0%} |"
        )
    lines.extend([
        "",
        "## Guards",
        "",
        "- Unmatched player scores are unchanged.",
        "- No raw 4for4 row is persisted.",
        "- No player-level 4for4 projection, percentile, rank, delta, or utility score is persisted.",
        "- Fundamental Value is untouched.",
        "- Free-Agent Production V2 is untouched.",
        "- free-agent-board.html is untouched.",
        "- This phase does not authorize production deployment.",
        "",
    ])
    return "\n".join(lines)


def run_selftest():
    phase1 = load_phase1()

    # Same matched set, opposite order: mean delta must be zero.
    log = {"1": 100.0, "2": 90.0, "3": 80.0}
    f4 = {"1": 10.0, "2": 20.0, "3": 30.0}
    lp = phase1.midrank_percentiles(log)
    fp = phase1.midrank_percentiles(f4)
    delta = {k: fp[k] - lp[k] for k in log}
    assert abs(statistics.fmean(delta.values())) < 1e-12
    assert delta["1"] == -1.0
    assert delta["2"] == 0.0
    assert delta["3"] == 1.0

    # Unmatched score is exact base score.
    base = 0.7
    assert clamp(base) == base

    # Bounded transport.
    assert clamp(0.95 + 0.25 * 1.0) == 1.0
    assert clamp(0.05 + 0.25 * -1.0) == 0.0
    print("free_agent_utility_v1_phase2 self-test passed")


def main() -> int:
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

    print(json.dumps({
        "status": result["status"],
        "matched_n": result["primary"]["matched_n"],
        "coverage": result["primary"]["coverage"],
        "move_ge_3": result["primary"]["matched_move_ge_3_count"],
        "move_ge_5": result["primary"]["matched_move_ge_5_count"],
        "clipped": result["primary"]["clipped_score_count"],
        "production_changes": result["production_changes"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

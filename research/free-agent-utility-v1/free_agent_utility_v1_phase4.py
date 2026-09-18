#!/usr/bin/env python3
"""Free Agent Utility V1 — Phase 4 exact production-candidate shadow.

Research only.

This phase freezes the exact green Phase 3 candidate:
  * cohort-relative 4for4 delta transport = 15%
  * absolute score-shift cap = +/- 0.040
  * unmatched player score = exact existing LOG percentile

It then constructs the exact DERIVED artifact shape a production board could
consume: current data-backed free agents get only a Sleeper ID, position, and
final within-position priority rank.

Important:
  * No raw 4for4 row/projection/rank is persisted.
  * No player-level delta or utility score is persisted.
  * The production-candidate artifact exists only under /tmp in this phase.
  * The ALL section remains on the existing LOG value order.
  * Only position sections would consume the derived priority rank.
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

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
RESEARCH = ROOT / "research" / "free-agent-utility-v1"
PHASE1_SCRIPT = RESEARCH / "free_agent_utility_v1_phase1.py"
PHASE3_SUMMARY = RESEARCH / "phase3_bounded_candidate_summary.json"

OUT_JSON = RESEARCH / "phase4_production_candidate_shadow_summary.json"
OUT_MD = RESEARCH / "phase4_production_candidate_shadow_summary.md"

TRACKED = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
TRANSPORT_STRENGTH = 0.15
SHIFT_CAP = 0.04

EXPECTED_PHASE3_SUMMARY_BLOB = "31aade287a777608226fc6e03bdb33ae8e823c58"
EXPECTED_BOARD_BLOB = "a442ee5dfab51b0214977a7b64e91203bdce3a36"


def load_phase1():
    spec = importlib.util.spec_from_file_location(
        "fa_utility_phase1_for_phase4", PHASE1_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to import Phase 1 helper")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def canonical_sha(obj) -> str:
    payload = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def summarize(values):
    vals = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not vals:
        return {"n": 0}
    abs_vals = sorted(abs(v) for v in vals)

    def pct(arr, q):
        if len(arr) == 1:
            return arr[0]
        x = (len(arr) - 1) * q
        lo = int(math.floor(x))
        hi = int(math.ceil(x))
        if lo == hi:
            return arr[lo]
        f = x - lo
        return arr[lo] * (1 - f) + arr[hi] * f

    return {
        "n": len(vals),
        "mean": statistics.fmean(vals),
        "median": statistics.median(vals),
        "median_abs": statistics.median(abs_vals),
        "p90_abs": pct(abs_vals, 0.90),
        "p95_abs": pct(abs_vals, 0.95),
        "max_abs": max(abs_vals),
        "min": vals[0],
        "max": vals[-1],
    }


def top_overlap(a, b, n):
    effective = min(n, len(a), len(b))
    aa = {k for k, r in a.items() if r <= effective}
    bb = {k for k, r in b.items() if r <= effective}
    overlap = len(aa & bb)
    return {
        "effective_n": effective,
        "overlap_count": overlap,
        "overlap_share": overlap / effective if effective else None,
    }


def build_candidate(rows, provider_rows, phase1):
    provider_idx = phase1.index_provider(provider_rows)
    by_pos = defaultdict(list)
    for r in rows:
        by_pos[r["pos"]].append(r)

    artifact_players = []
    diagnostics = {}
    overall_moves = []
    matched_n = 0
    capped_n = 0

    for pos in TRACKED:
        cohort = by_pos[pos]
        current_values = {r["sleeper_id"]: float(r["value"]) for r in cohort}
        full_log_pct = phase1.midrank_percentiles(current_values)

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

        matched_values = {r["sleeper_id"]: float(r["value"]) for r in matched}
        matched_log_pct = phase1.midrank_percentiles(matched_values)
        matched_f4_pct = phase1.midrank_percentiles(provider_points)
        deltas = {
            sid: matched_f4_pct[sid] - matched_log_pct[sid]
            for sid in matched_log_pct
        }

        if deltas and abs(statistics.fmean(deltas.values())) > 1e-12:
            raise RuntimeError(f"{pos}: cohort-relative delta lost mean-zero property")

        candidate_scores = {}
        applied_shift = {}
        pos_capped = 0
        for r in cohort:
            sid = r["sleeper_id"]
            base = full_log_pct[sid]
            if sid not in deltas:
                candidate_scores[sid] = base
                continue

            raw_shift = TRANSPORT_STRENGTH * deltas[sid]
            shift = clamp(raw_shift, -SHIFT_CAP, SHIFT_CAP)
            if abs(raw_shift - shift) > 1e-12:
                pos_capped += 1
            applied_shift[sid] = shift
            candidate_scores[sid] = clamp(base + shift, 0.0, 1.0)

        current_rank = phase1.ranks_desc(current_values)
        priority_rank = phase1.ranks_desc(candidate_scores)

        # Exact production artifact: only identity, position, and final derived
        # rank. No provider magnitude, percentile, score, delta, or match flag.
        for r in cohort:
            sid = r["sleeper_id"]
            artifact_players.append({
                "player_id": sid,
                "pos": pos,
                "priority_rank": int(priority_rank[sid]),
            })

        matched_moves = [
            float(current_rank[sid] - priority_rank[sid])
            for sid in deltas
        ]
        all_moves = [
            float(current_rank[sid] - priority_rank[sid])
            for sid in current_rank
        ]

        diagnostics[pos] = {
            "cohort_n": len(cohort),
            "matched_n": len(deltas),
            "coverage": len(deltas) / len(cohort),
            "capped_match_count": pos_capped,
            "spearman": phase1.spearman_from_ranks(current_rank, priority_rank),
            "rank_move_matched": summarize(matched_moves),
            "rank_move_all": summarize(all_moves),
            "move_ge_3_count": sum(abs(x) >= 3 for x in matched_moves),
            "move_ge_5_count": sum(abs(x) >= 5 for x in matched_moves),
            "top5_overlap": top_overlap(current_rank, priority_rank, 5),
            "top10_overlap": top_overlap(current_rank, priority_rank, 10),
        }
        overall_moves.extend(matched_moves)
        matched_n += len(deltas)
        capped_n += pos_capped

    artifact_players.sort(key=lambda r: (r["pos"], r["priority_rank"], r["player_id"]))
    artifact = {
        "schema_version": 1,
        "study_id": "free-agent-utility-v1",
        "policy_id": "phase3-selected-15pct-cap040",
        "scope": "data_backed_free_agents_only",
        "all_section_policy": "existing_log_value_order_unchanged",
        "position_section_policy": "priority_rank_ascending",
        "players": artifact_players,
    }

    return artifact, {
        "matched_n": matched_n,
        "capped_match_count": capped_n,
        "matched_rank_move": summarize(overall_moves),
        "matched_move_ge_3_count": sum(abs(x) >= 3 for x in overall_moves),
        "matched_move_ge_5_count": sum(abs(x) >= 5 for x in overall_moves),
        "by_position": diagnostics,
    }


def validate_artifact(artifact, rows):
    players = artifact["players"]
    expected_ids = {r["sleeper_id"] for r in rows}
    actual_ids = {str(r["player_id"]) for r in players}

    if len(players) != len(rows):
        raise RuntimeError(f"artifact row count mismatch: {len(players)} != {len(rows)}")
    if actual_ids != expected_ids:
        raise RuntimeError("artifact Sleeper-ID coverage differs from data-backed cohort")
    if len(actual_ids) != len(players):
        raise RuntimeError("artifact contains duplicate player IDs")

    forbidden_key_fragments = (
        "fourforfour", "projection", "points", "percentile",
        "delta", "score", "matched", "provider",
    )
    for rec in players:
        if set(rec) != {"player_id", "pos", "priority_rank"}:
            raise RuntimeError(f"unexpected artifact row schema: {sorted(rec)}")
        for key in rec:
            lk = key.lower()
            if any(frag in lk for frag in forbidden_key_fragments):
                raise RuntimeError(f"forbidden provider-derived field name: {key}")

    by_pos = defaultdict(list)
    for rec in players:
        by_pos[rec["pos"]].append(int(rec["priority_rank"]))
    for pos in TRACKED:
        ranks = sorted(by_pos[pos])
        expected = list(range(1, len(ranks) + 1))
        if ranks != expected:
            raise RuntimeError(f"{pos}: priority ranks are not contiguous")


def compare_phase3(diag, phase3):
    selected = phase3["selected_candidate"]
    if selected is None:
        raise RuntimeError("Phase 3 did not select a candidate")
    if selected["transport_strength"] != TRANSPORT_STRENGTH:
        raise RuntimeError("Phase 3 transport strength drifted")
    if selected["cap"] != SHIFT_CAP:
        raise RuntimeError("Phase 3 selected cap drifted")

    exact_fields = (
        "matched_n",
        "capped_match_count",
        "matched_move_ge_3_count",
        "matched_move_ge_5_count",
    )
    for field in exact_fields:
        if diag[field] != selected[field]:
            raise RuntimeError(
                f"Phase 4 failed to reproduce Phase 3 {field}: "
                f"{diag[field]} != {selected[field]}"
            )

    for pos in TRACKED:
        got = diag["by_position"][pos]
        exp = selected["by_position"][pos]
        for field in ("matched_n", "capped_match_count", "move_ge_3_count", "move_ge_5_count"):
            if got[field] != exp[field]:
                raise RuntimeError(
                    f"{pos}: Phase 4 failed to reproduce Phase 3 {field}"
                )
        for key in ("top5_overlap", "top10_overlap"):
            if got[key]["overlap_count"] != exp[key]["overlap_count"]:
                raise RuntimeError(f"{pos}: Phase 4 {key} overlap drifted")


def build_result(offense: Path, dl: Path, lb: Path, db: Path, artifact_out: Path | None):
    phase1 = load_phase1()

    phase3 = json.loads(PHASE3_SUMMARY.read_text(encoding="utf-8"))
    if phase3.get("status") != "PASS_PHASE3_BOUNDED_CANDIDATE_SELECTED":
        raise RuntimeError("green Phase 3 summary missing or changed")
    if git_blob_sha(PHASE3_SUMMARY) != EXPECTED_PHASE3_SUMMARY_BLOB:
        raise RuntimeError("Phase 3 summary blob drifted")
    board = ROOT / "free-agent-board.html"
    if git_blob_sha(board) != EXPECTED_BOARD_BLOB:
        raise RuntimeError("free-agent-board.html drifted from Phase 4 preregistration")

    current, runtime_meta = phase1.current_board_rows()
    data_backed = [r for r in current if r["has_real_data"]]
    provider = (
        phase1.read_offense(offense)
        + phase1.read_idp(dl, "DL")
        + phase1.read_idp(lb, "LB")
        + phase1.read_idp(db, "DB")
    )

    artifact, diag = build_candidate(data_backed, provider, phase1)
    validate_artifact(artifact, data_backed)
    compare_phase3(diag, phase3)

    if artifact_out is not None:
        artifact_out.parent.mkdir(parents=True, exist_ok=True)
        artifact_out.write_text(
            json.dumps(artifact, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    # Final production-candidate guards. These mirror the selected Phase 3
    # safety contract and additionally require exact artifact coverage/schema.
    guard_results = {}
    for pos in TRACKED:
        d = diag["by_position"][pos]
        guard_results[pos] = {
            "top5_overlap_at_least_80pct":
                d["top5_overlap"]["overlap_share"] >= 0.80,
            "top10_overlap_at_least_80pct":
                d["top10_overlap"]["overlap_share"] >= 0.80,
            "p95_absolute_rank_move_at_most_8":
                d["rank_move_matched"]["p95_abs"] <= 8.0,
            "absolute_rank_move_at_most_10":
                d["rank_move_matched"]["max_abs"] <= 10.0,
        }

    all_guards = all(
        all(g.values()) for g in guard_results.values()
    )
    status = (
        "PASS_PHASE4_EXACT_PRODUCTION_CANDIDATE_SHADOW"
        if all_guards
        else "HOLD_PHASE4_PRODUCTION_CANDIDATE"
    )

    return {
        "schema_version": 1,
        "study_id": "free-agent-utility-v1",
        "phase": 4,
        "status": status,
        "research_only": True,
        "production_changes": False,
        "production_authorized": False,
        "realized_outcomes_read": False,
        "private_row_level_4for4_output_persisted": False,
        "player_level_candidate_artifact_persisted": False,
        "selected_policy": {
            "transport_strength": TRANSPORT_STRENGTH,
            "absolute_score_shift_cap": SHIFT_CAP,
            "all_section_policy": "existing_log_value_order_unchanged",
            "position_section_policy": "derived_priority_rank_ascending",
        },
        "phase3_reference": {
            "summary_git_blob": EXPECTED_PHASE3_SUMMARY_BLOB,
            "selected_cap": phase3["selected_candidate"]["cap"],
            "selected_transport_strength":
                phase3["selected_candidate"]["transport_strength"],
        },
        "candidate_artifact_contract": {
            "target_path_if_deployed": "data/free_agent_utility_v1.json",
            "row_count": len(artifact["players"]),
            "row_schema": ["player_id", "pos", "priority_rank"],
            "canonical_sha256": canonical_sha(artifact),
            "contains_raw_provider_data": False,
            "contains_provider_projection": False,
            "contains_provider_rank": False,
            "contains_player_level_delta": False,
            "contains_player_level_score": False,
        },
        "diagnostics": diag,
        "guard_results": guard_results,
        "source_integrity": {
            "board_git_blob": EXPECTED_BOARD_BLOB,
            "private_source_sha256": dict(phase1.EXPECTED_SHA256),
            "runtime": runtime_meta,
            "data_backed_free_agent_count": len(data_backed),
            "data_backed_by_position":
                dict(sorted(Counter(r["pos"] for r in data_backed).items())),
        },
    }


def render_md(result):
    d = result["diagnostics"]
    lines = [
        "# Free Agent Utility V1 — Phase 4 Exact Production-Candidate Shadow",
        "",
        f"Status: **{result['status']}**",
        "",
        "No production file or live board behavior changed.",
        "",
        "## Frozen candidate",
        "",
        "- 4for4 cohort-relative transport: **15%**",
        "- Absolute score-shift cap: **±0.040**",
        "- ALL section: **existing LOG value order unchanged**",
        "- Position sections: **derived priority rank**",
        f"- Candidate artifact rows: **{result['candidate_artifact_contract']['row_count']}**",
        "- Candidate artifact row fields: `player_id`, `pos`, `priority_rank` only",
        "",
        "## Exact reproduction",
        "",
        f"- Matched free agents: **{d['matched_n']}**",
        f"- Capped matches: **{d['capped_match_count']}**",
        f"- 3+ spot moves: **{d['matched_move_ge_3_count']}**",
        f"- 5+ spot moves: **{d['matched_move_ge_5_count']}**",
        f"- Median absolute matched move: **{d['matched_rank_move']['median_abs']:.1f}**",
        f"- P95 absolute matched move: **{d['matched_rank_move']['p95_abs']:.1f}**",
        "",
        "## Position-section behavior",
        "",
        "| Pos | Cohort | Match | Spearman | >=3 | >=5 | Top-5 | Top-10 | P95 move | Max move |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for pos in TRACKED:
        r = d["by_position"][pos]
        lines.append(
            f"| {pos} | {r['cohort_n']} | {r['matched_n']} | {r['spearman']:.4f} | "
            f"{r['move_ge_3_count']} | {r['move_ge_5_count']} | "
            f"{r['top5_overlap']['overlap_share']:.0%} | "
            f"{r['top10_overlap']['overlap_share']:.0%} | "
            f"{r['rank_move_matched']['p95_abs']:.1f} | "
            f"{r['rank_move_matched']['max_abs']:.1f} |"
        )
    lines.extend([
        "",
        "## Privacy / architecture",
        "",
        "- The simulated production artifact contains no raw 4for4 rows.",
        "- It contains no 4for4 projections, ranks, percentiles, or player-level deltas.",
        "- It contains no player-level utility score; only the final bounded within-position priority rank.",
        "- Fundamental Value and Free-Agent Production V2 remain untouched.",
        "- No cross-position ordering is derived from the utility percentile.",
        "- This phase does not authorize production deployment.",
        "",
    ])
    return "\n".join(lines)


def run_selftest():
    fake = {
        "players": [
            {"player_id": "1", "pos": "WR", "priority_rank": 1},
            {"player_id": "2", "pos": "WR", "priority_rank": 2},
        ]
    }
    rows = [
        {"sleeper_id": "1"},
        {"sleeper_id": "2"},
    ]
    validate_artifact(fake, rows)
    assert clamp(0.10, -SHIFT_CAP, SHIFT_CAP) == SHIFT_CAP
    assert clamp(-0.10, -SHIFT_CAP, SHIFT_CAP) == -SHIFT_CAP
    print("free_agent_utility_v1_phase4 self-test passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--offense", type=Path)
    parser.add_argument("--dl", type=Path)
    parser.add_argument("--lb", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--artifact-out", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return 0

    if any(p is None for p in (args.offense, args.dl, args.lb, args.db)):
        parser.error("--offense, --dl, --lb, and --db are required unless --selftest")

    result = build_result(
        args.offense, args.dl, args.lb, args.db, args.artifact_out
    )

    if args.write:
        OUT_JSON.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        OUT_MD.write_text(render_md(result), encoding="utf-8")

    print(json.dumps({
        "status": result["status"],
        "candidate_rows": result["candidate_artifact_contract"]["row_count"],
        "artifact_sha256":
            result["candidate_artifact_contract"]["canonical_sha256"],
        "move_ge_3": result["diagnostics"]["matched_move_ge_3_count"],
        "move_ge_5": result["diagnostics"]["matched_move_ge_5_count"],
        "production_changes": result["production_changes"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

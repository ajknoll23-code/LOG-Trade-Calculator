#!/usr/bin/env python3
"""Free Agent Utility V1 — Phase 1 private 4for4 shadow.

Research only. This study asks a narrow question:

    Does a bounded 4for4 season-projection signal improve the ordering of the
    existing data-backed Free Agent Board enough to justify a separate waiver
    utility layer?

The study never changes Fundamental Value, Free-Agent Production V2,
FA_PROD_MULT_DATA, PROD_MULT_DATA, or free-agent-board.html.

Privacy/licensing contract
--------------------------
* private 4for4 CSV rows are read only from runner-local paths
* no provider row, projection, rank, or player-level derived score is written
  to the repository
* persisted outputs are aggregate diagnostics only
* unmatched current free agents fall back exactly to their existing LOG signal

Frozen Phase-1 candidate family
-------------------------------
* cohort: current free agents with hasRealData=true on the live board
* positions: QB/RB/WR/TE/DL/LB/DB
* current LOG signal: within-position percentile of current board value
* 4for4 signal: within-position midrank percentile of 4for4 projected FF Pts
  across the provider's full position population
* identity: exact normalized name + current position + normalized current team
* candidate weights: 15%, 25%, 35% 4for4; primary = 25%
* unmatched fallback: exact current LOG percentile
* evaluation: coverage, Spearman rank correlation, top-N overlap, and rank
  movement distributions; no realized outcomes are read
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import sys
from typing import Iterable

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
RESEARCH = ROOT / "research" / "free-agent-utility-v1"
BOARD = ROOT / "free-agent-board.html"
FREE_AGENTS = ROOT / "data" / "free_agents.json"
VALIDATOR = ROOT / "scripts" / "validation" / "validate_free_agent_valuation_parity.py"

OUT_JSON = RESEARCH / "phase1_shadow_summary.json"
OUT_MD = RESEARCH / "phase1_shadow_summary.md"

TRACKED = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
OFFENSE = {"QB", "RB", "WR", "TE"}
WEIGHTS = (0.15, 0.25, 0.35)
PRIMARY_WEIGHT = 0.25

EXPECTED_SHA256 = {
    "offense": "488f8b7bf74b5e30ed515c7cde4b2049d1af6ad0d953ae7f78fd82561293af11",
    "DL": "a8ae4a3dc3ed7e24e102e9416467826dd93441cc6b18c0589ed8345aeca977f6",
    "LB": "957e3c03b604302d259393d3cd3c637d03ff15b6a51812bb23cc0d10830a8321",
    "DB": "7bc8fb440f171bc65ab82e4c2cf1ed88e4b53a6f64868461ac8a96cb08d9b079",
}
EXPECTED_ROW_COUNTS = {
    "offense": 476,
    "DL": 250,
    "LB": 136,
    "DB": 262,
}
EXPECTED_OFFENSE_BY_POS = {"QB": 64, "RB": 109, "WR": 171, "TE": 99}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value):
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def norm_name(value) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_team(value):
    if value in (None, ""):
        return None
    t = str(value).strip().upper()
    return {
        "JAC": "JAX",
        "WSH": "WAS",
        "OAK": "LV",
        "SD": "LAC",
        "STL": "LAR",
        "LA": "LAR",
    }.get(t, t)


def midrank_percentiles(values_by_key: dict[str, float]) -> dict[str, float]:
    """Return [0,1] midrank percentiles, with 1.0 best."""
    if not values_by_key:
        return {}
    ordered = sorted(values_by_key.items(), key=lambda kv: (kv[1], kv[0]))
    n = len(ordered)
    out = {}
    i = 0
    while i < n:
        j = i + 1
        value = ordered[i][1]
        while j < n and ordered[j][1] == value:
            j += 1
        avg_rank_zero_based = (i + (j - 1)) / 2.0
        pct = 1.0 if n == 1 else avg_rank_zero_based / (n - 1)
        for k, _ in ordered[i:j]:
            out[k] = pct
        i = j
    return out


def ranks_desc(values_by_key: dict[str, float]) -> dict[str, int]:
    ordered = sorted(values_by_key, key=lambda k: (-values_by_key[k], k))
    return {k: i + 1 for i, k in enumerate(ordered)}


def spearman_from_ranks(a: dict[str, int], b: dict[str, int]) -> float | None:
    keys = sorted(set(a) & set(b))
    n = len(keys)
    if n < 2:
        return None
    av = [float(a[k]) for k in keys]
    bv = [float(b[k]) for k in keys]
    am = statistics.fmean(av)
    bm = statistics.fmean(bv)
    num = sum((x - am) * (y - bm) for x, y in zip(av, bv))
    da = math.sqrt(sum((x - am) ** 2 for x in av))
    db = math.sqrt(sum((y - bm) ** 2 for y in bv))
    if da == 0 or db == 0:
        return None
    return num / (da * db)


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


def summarize_signed(values: Iterable[float]) -> dict:
    vals = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not vals:
        return {"n": 0}
    abs_vals = sorted(abs(v) for v in vals)
    return {
        "n": len(vals),
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
        return {"requested_n": n, "effective_n": 0, "overlap_count": 0, "overlap_share": None}
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


def load_validator():
    spec = importlib.util.spec_from_file_location("fa_utility_v1_validator", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to import free-agent valuation validator")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def current_board_rows() -> tuple[list[dict], dict]:
    validator = load_validator()
    board_text = BOARD.read_text(encoding="utf-8")
    fa_doc = read_json(FREE_AGENTS)
    runtime = validator._board_runtime_rows(board_text, fa_doc)

    tracked_runtime = [
        row for row in runtime["rows"]
        if str(row.get("pos") or "").upper() in TRACKED
    ]
    runtime_by_key = {}
    for row in tracked_runtime:
        key = (
            norm_name(row.get("name")),
            str(row.get("pos") or "").upper(),
            norm_team(row.get("team")),
        )
        if key in runtime_by_key:
            raise RuntimeError(f"duplicate runtime free-agent identity: {key}")
        runtime_by_key[key] = row

    out = []
    raw_seen = set()
    for raw in fa_doc.get("free_agents") or []:
        pos = str(raw.get("pos") or "").upper()
        if pos not in TRACKED:
            continue
        sid = str(raw.get("player_id") or "")
        if not sid:
            continue
        key = (norm_name(raw.get("name")), pos, norm_team(raw.get("team")))
        if key in raw_seen:
            raise RuntimeError(f"duplicate current free-agent name/position/team: {key}")
        raw_seen.add(key)
        runtime_row = runtime_by_key.get(key)
        if runtime_row is None:
            # Production board has explicit exclusions; anything omitted by
            # the runtime is intentionally outside this research cohort too.
            continue
        out.append({
            "sleeper_id": sid,
            "name": str(raw.get("name") or ""),
            "norm_name": norm_name(raw.get("name")),
            "pos": pos,
            "team": norm_team(raw.get("team")),
            "value": int(runtime_row["val"]),
            "has_real_data": bool(runtime_row["hasRealData"]),
        })

    if len(out) != len(tracked_runtime):
        raise RuntimeError(
            f"tracked free-agent/runtime accounting mismatch: {len(out)} != {len(tracked_runtime)}"
        )
    return out, {
        "rendered_tracked_count": len(tracked_runtime),
        "rendered_total_count": len(runtime["rows"]),
        "production_source_counts": runtime["production_source_counts"],
        "fa_prod_entry_count": runtime["fa_prod_entry_count"],
    }


def verify_private_file(label: str, path: Path):
    actual = sha256(path)
    expected = EXPECTED_SHA256[label]
    if actual != expected:
        raise RuntimeError(
            f"{label} private source SHA drift: expected={expected} actual={actual}"
        )


def read_offense(path: Path) -> list[dict]:
    verify_private_file("offense", path)
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != EXPECTED_ROW_COUNTS["offense"]:
        raise RuntimeError(f"offense row-count drift: {len(rows)}")
    required = {"PID", "Player", "Pos", "Team", "FF Pts"}
    missing = required - set(rows[0].keys() if rows else ())
    if missing:
        raise RuntimeError(f"offense missing columns: {sorted(missing)}")

    counts = Counter()
    out = []
    for row in rows:
        pos = str(row.get("Pos") or "").strip().upper()
        if pos not in OFFENSE:
            continue
        pts = finite(row.get("FF Pts"))
        name = str(row.get("Player") or "").strip()
        team = norm_team(row.get("Team"))
        pid = str(row.get("PID") or "").strip()
        if not pid or not name or not team or pts is None:
            raise RuntimeError("invalid offense provider row")
        counts[pos] += 1
        out.append({
            "source_id": f"offense:{pid}",
            "name": name,
            "norm_name": norm_name(name),
            "pos": pos,
            "team": team,
            "points": pts,
        })
    if dict(counts) != EXPECTED_OFFENSE_BY_POS:
        raise RuntimeError(f"offense position-count drift: {dict(counts)}")
    return out


def read_idp(path: Path, bucket: str) -> list[dict]:
    verify_private_file(bucket, path)
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != EXPECTED_ROW_COUNTS[bucket]:
        raise RuntimeError(f"{bucket} row-count drift: {len(rows)}")
    required = {"Player", "Team", "FF Pts"}
    missing = required - set(rows[0].keys() if rows else ())
    if missing:
        raise RuntimeError(f"{bucket} missing columns: {sorted(missing)}")

    out = []
    for i, row in enumerate(rows):
        name = str(row.get("Player") or "").strip()
        team = norm_team(row.get("Team"))
        pts = finite(row.get("FF Pts"))
        if not name or not team or pts is None:
            raise RuntimeError(f"invalid {bucket} provider row at index {i}")
        out.append({
            "source_id": f"{bucket}:{i}",
            "name": name,
            "norm_name": norm_name(name),
            "pos": bucket,
            "team": team,
            "points": pts,
        })
    return out


def index_provider(provider_rows: list[dict]):
    idx = defaultdict(list)
    for row in provider_rows:
        idx[(row["norm_name"], row["pos"], row["team"])].append(row)
    return idx


def provider_percentiles(provider_rows: list[dict]) -> dict[str, float]:
    out = {}
    by_pos = defaultdict(dict)
    for row in provider_rows:
        by_pos[row["pos"]][row["source_id"]] = float(row["points"])
    for vals in by_pos.values():
        out.update(midrank_percentiles(vals))
    return out


def evaluate_view(rows: list[dict], provider_rows: list[dict], weight: float) -> dict:
    provider_idx = index_provider(provider_rows)
    provider_pct = provider_percentiles(provider_rows)

    current_by_pos = defaultdict(list)
    for row in rows:
        current_by_pos[row["pos"]].append(row)

    result_by_pos = {}
    all_moves = []
    all_score_gaps = []
    matched_n = 0

    for pos in TRACKED:
        cohort = current_by_pos.get(pos, [])
        if not cohort:
            result_by_pos[pos] = {"current_n": 0, "matched_n": 0, "coverage": None}
            continue

        log_values = {r["sleeper_id"]: float(r["value"]) for r in cohort}
        log_pct = midrank_percentiles(log_values)

        candidate_scores = {}
        matched_ids = set()
        score_gaps = []
        for r in cohort:
            sid = r["sleeper_id"]
            cands = provider_idx.get((r["norm_name"], pos, r["team"]), [])
            if len(cands) == 1:
                f4pct = provider_pct[cands[0]["source_id"]]
                candidate_scores[sid] = (
                    (1.0 - weight) * log_pct[sid] + weight * f4pct
                )
                matched_ids.add(sid)
                score_gaps.append(f4pct - log_pct[sid])
            elif len(cands) == 0:
                candidate_scores[sid] = log_pct[sid]
            else:
                raise RuntimeError(
                    f"ambiguous provider identity for current free agent: "
                    f"{r['name']} {pos} {r['team']}"
                )

        base_rank = ranks_desc(log_values)
        candidate_rank = ranks_desc(candidate_scores)
        moves = [float(base_rank[sid] - candidate_rank[sid]) for sid in base_rank]
        matched_moves = [
            float(base_rank[sid] - candidate_rank[sid]) for sid in matched_ids
        ]

        result_by_pos[pos] = {
            "current_n": len(cohort),
            "matched_n": len(matched_ids),
            "coverage": len(matched_ids) / len(cohort),
            "spearman": spearman_from_ranks(base_rank, candidate_rank),
            "rank_move_all": summarize_signed(moves),
            "rank_move_matched": summarize_signed(matched_moves),
            "projection_minus_log_percentile": summarize_signed(score_gaps),
            "move_ge_3_count": sum(abs(x) >= 3 for x in matched_moves),
            "move_ge_5_count": sum(abs(x) >= 5 for x in matched_moves),
            "top5_overlap": top_overlap(base_rank, candidate_rank, 5),
            "top10_overlap": top_overlap(base_rank, candidate_rank, 10),
        }
        all_moves.extend(matched_moves)
        all_score_gaps.extend(score_gaps)
        matched_n += len(matched_ids)

    return {
        "weight": weight,
        "cohort_n": len(rows),
        "matched_n": matched_n,
        "coverage": matched_n / len(rows) if rows else None,
        "by_position": result_by_pos,
        "matched_rank_move": summarize_signed(all_moves),
        "projection_minus_log_percentile": summarize_signed(all_score_gaps),
        "matched_move_ge_3_count": sum(abs(x) >= 3 for x in all_moves),
        "matched_move_ge_5_count": sum(abs(x) >= 5 for x in all_moves),
    }


def build_result(offense: Path, dl: Path, lb: Path, db: Path) -> dict:
    current, runtime_meta = current_board_rows()
    provider = (
        read_offense(offense)
        + read_idp(dl, "DL")
        + read_idp(lb, "LB")
        + read_idp(db, "DB")
    )

    data_backed = [r for r in current if r["has_real_data"]]
    current_counts = Counter(r["pos"] for r in current)
    backed_counts = Counter(r["pos"] for r in data_backed)
    provider_counts = Counter(r["pos"] for r in provider)

    variants = {
        f"{int(w * 100)}pct": evaluate_view(data_backed, provider, w)
        for w in WEIGHTS
    }
    primary = variants[f"{int(PRIMARY_WEIGHT * 100)}pct"]

    return {
        "schema_version": 1,
        "study_id": "free-agent-utility-v1",
        "phase": 1,
        "status": "PASS_PHASE1_PRIVATE_SHADOW_COMPLETE",
        "research_only": True,
        "production_changes": False,
        "production_authorized": False,
        "realized_outcomes_read": False,
        "private_row_level_4for4_output_persisted": False,
        "player_level_derived_4for4_output_persisted": False,
        "scope": list(TRACKED),
        "methodology": {
            "cohort": "current_free_agents_with_live_board_hasRealData_true",
            "identity": "exact_normalized_name_plus_position_plus_normalized_team",
            "log_signal": "within_position_midrank_percentile_of_current_board_value",
            "fourforfour_signal": "within_position_midrank_percentile_of_provider_projected_ff_points",
            "candidate_weights": list(WEIGHTS),
            "primary_fourforfour_weight": PRIMARY_WEIGHT,
            "unmatched_fallback": "exact_current_log_percentile",
            "provider_row_level_persistence": False,
            "provider_player_level_score_persistence": False,
        },
        "source_integrity": {
            "private_source_sha256": dict(EXPECTED_SHA256),
            "private_source_row_counts": dict(EXPECTED_ROW_COUNTS),
            "provider_rows_by_position": dict(sorted(provider_counts.items())),
            "current_free_agents_by_position": dict(sorted(current_counts.items())),
            "data_backed_free_agents_by_position": dict(sorted(backed_counts.items())),
            "runtime": runtime_meta,
        },
        "variants": variants,
        "primary": primary,
    }


def render_md(result: dict) -> str:
    p = result["primary"]
    lines = [
        "# Free Agent Utility V1 — Phase 1 Private 4for4 Shadow",
        "",
        f"Status: **{result['status']}**",
        "",
        "Research-only. No production file or ranking was changed.",
        "",
        "## Frozen primary shadow",
        "",
        f"- 4for4 weight: **{int(PRIMARY_WEIGHT * 100)}%**",
        f"- Current LOG weight: **{int((1-PRIMARY_WEIGHT) * 100)}%**",
        f"- Data-backed free-agent cohort: **{p['cohort_n']}**",
        f"- Matched to private 4for4 source: **{p['matched_n']}** "
        f"({p['coverage']:.1%})",
        "- Unmatched fallback: exact existing LOG signal",
        "",
        "## Position diagnostics",
        "",
        "| Pos | Cohort | Matched | Coverage | Spearman | >=3 moves | >=5 moves |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for pos in TRACKED:
        row = p["by_position"][pos]
        cov = "—" if row.get("coverage") is None else f"{row['coverage']:.1%}"
        sp = "—" if row.get("spearman") is None else f"{row['spearman']:.4f}"
        lines.append(
            f"| {pos} | {row['current_n']} | {row['matched_n']} | {cov} | {sp} | "
            f"{row.get('move_ge_3_count', 0)} | {row.get('move_ge_5_count', 0)} |"
        )
    lines.extend([
        "",
        "## Privacy / production guards",
        "",
        "- No raw 4for4 row is written to the repository.",
        "- No player-level 4for4 projection, percentile, rank, or utility score is persisted.",
        "- Fundamental Value is untouched.",
        "- Free-Agent Production V2 is untouched.",
        "- The live Free Agent Board is untouched.",
        "- This phase does not authorize production deployment.",
        "",
    ])
    return "\n".join(lines)


def run_selftest():
    vals = {"a": 10.0, "b": 20.0, "c": 20.0, "d": 40.0}
    pct = midrank_percentiles(vals)
    assert pct["a"] == 0.0
    assert abs(pct["b"] - 0.5) < 1e-12
    assert abs(pct["c"] - 0.5) < 1e-12
    assert pct["d"] == 1.0

    ranks = ranks_desc({"a": 1.0, "b": 3.0, "c": 2.0})
    assert ranks == {"b": 1, "c": 2, "a": 3}
    assert abs(spearman_from_ranks(ranks, ranks) - 1.0) < 1e-12

    sample_current = [
        {"sleeper_id": "1", "name": "Alpha One", "norm_name": "alpha one",
         "pos": "WR", "team": "ARI", "value": 1000, "has_real_data": True},
        {"sleeper_id": "2", "name": "Beta Two", "norm_name": "beta two",
         "pos": "WR", "team": "ATL", "value": 900, "has_real_data": True},
        {"sleeper_id": "3", "name": "Gamma Three", "norm_name": "gamma three",
         "pos": "WR", "team": "BUF", "value": 800, "has_real_data": True},
    ]
    sample_provider = [
        {"source_id": "p1", "name": "Alpha One", "norm_name": "alpha one",
         "pos": "WR", "team": "ARI", "points": 10.0},
        {"source_id": "p2", "name": "Beta Two", "norm_name": "beta two",
         "pos": "WR", "team": "ATL", "points": 30.0},
        {"source_id": "p3", "name": "Other", "norm_name": "other",
         "pos": "WR", "team": "CAR", "points": 20.0},
    ]
    r = evaluate_view(sample_current, sample_provider, 0.25)
    assert r["cohort_n"] == 3
    assert r["matched_n"] == 2
    assert abs(r["coverage"] - 2 / 3) < 1e-12
    assert r["by_position"]["WR"]["current_n"] == 3
    print("free_agent_utility_v1_phase1 self-test passed")


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

    paths = [args.offense, args.dl, args.lb, args.db]
    if any(p is None for p in paths):
        parser.error(
            "--offense, --dl, --lb, and --db are required unless --selftest is used"
        )

    result = build_result(args.offense, args.dl, args.lb, args.db)

    if args.write:
        RESEARCH.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        OUT_MD.write_text(render_md(result), encoding="utf-8")
        print(f"WROTE {OUT_JSON.relative_to(ROOT)}")
        print(f"WROTE {OUT_MD.relative_to(ROOT)}")

    print(json.dumps({
        "status": result["status"],
        "cohort_n": result["primary"]["cohort_n"],
        "matched_n": result["primary"]["matched_n"],
        "coverage": result["primary"]["coverage"],
        "primary_weight": PRIMARY_WEIGHT,
        "production_changes": result["production_changes"],
        "private_row_level_4for4_output_persisted":
            result["private_row_level_4for4_output_persisted"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

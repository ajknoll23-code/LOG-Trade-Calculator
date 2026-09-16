#!/usr/bin/env python3
"""Free-Agent Production V2 Phase 2 shadow validation.

Uses only the frozen Phase 1 candidate and the real free-agent-board
runtime. No production files are written.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
RESEARCH = ROOT / "research" / "free-agent-production-v2"

PHASE1_JSON = RESEARCH / "free_agent_production_v2_phase1.json"
PHASE1_MD = RESEARCH / "free_agent_production_v2_phase1.md"
PHASE1_SCRIPT = RESEARCH / "free_agent_production_v2_phase1.py"
PHASE1_MANIFEST = RESEARCH / "phase1_manifest.json"
PREREG_JSON = RESEARCH / "phase2_preregistration.json"
PREREG_MD = RESEARCH / "phase2_preregistration.md"

OUT_JSON = RESEARCH / "free_agent_production_v2_phase2_shadow.json"
OUT_MD = RESEARCH / "free_agent_production_v2_phase2_shadow.md"
MANIFEST = RESEARCH / "phase2_manifest.json"

BOARD = ROOT / "free-agent-board.html"
FREE_AGENTS = ROOT / "data" / "free_agents.json"

TRACKED = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

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
    return {
        "n": len(vals),
        "mean": statistics.fmean(vals),
        "median": statistics.median(vals),
        "p10": pct(0.10),
        "p90": pct(0.90),
        "p95": pct(0.95),
        "min": vals[0],
        "max": vals[-1],
    }

def spearman_from_ordinal_rank_maps(a, b, ids):
    ids = list(ids)
    if len(ids) < 2:
        return 1.0
    xs = [float(a[i]) for i in ids]
    ys = [float(b[i]) for i in ids]
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else 1.0

def deterministic_ranks(rows_by_id, ids=None):
    selected = list(ids if ids is not None else rows_by_id.keys())
    ordered = sorted(
        selected,
        key=lambda sid: (
            -int(rows_by_id[sid]["val"]),
            str(rows_by_id[sid]["name"]),
            str(rows_by_id[sid]["pos"]),
            str(sid),
        ),
    )
    return {sid: i + 1 for i, sid in enumerate(ordered)}

def position_ranks(rows_by_id):
    out = {}
    groups = defaultdict(list)
    for sid, row in rows_by_id.items():
        groups[row["pos"]].append(sid)
    for pos, ids in groups.items():
        out[pos] = deterministic_ranks(rows_by_id, ids)
    return out

def attach_sleeper_ids(runtime_rows, free_doc, fa_validator):
    expected = [
        r for r in (free_doc.get("free_agents") or [])
        if r.get("pos")
        and (fa_validator.normalize_name(r.get("name")), r.get("pos"))
           not in fa_validator.EXCLUDED_FREE_AGENTS
    ]
    queues = defaultdict(deque)
    for row in runtime_rows:
        queues[(row.get("name"), row.get("pos"), row.get("team"))].append(row)

    out = {}
    for src in expected:
        key = (src.get("name"), src.get("pos"), src.get("team"))
        if not queues[key]:
            raise RuntimeError(f"Could not attach runtime row to Sleeper ID for {key!r}")
        row = queues[key].popleft()
        sid = str(src["player_id"])
        if sid in out:
            raise RuntimeError(f"Duplicate rendered Sleeper ID: {sid}")
        out[sid] = row

    leftovers = {
        key: len(q) for key, q in queues.items() if q
    }
    if leftovers:
        raise RuntimeError(f"Unmatched runtime rows remain: {list(leftovers.items())[:10]}")
    return out

def inject_shadow_overrides(board_text, overrides, sync_mod):
    _, end, _ = sync_mod._extract_const_object(board_text, "FA_PROD_MULT_DATA")
    payload = json.dumps(
        [
            {
                "key": r["name"],
                "pos": r["pos"],
                "prod": float(r["candidate_prod"]),
                "sleeper_id": str(r["sleeper_id"]),
            }
            for r in overrides
        ],
        separators=(",", ":"),
    )
    snippet = f"""
const __FA_PROD_V2_SHADOW_OVERRIDES = {payload};
for (const __o of __FA_PROD_V2_SHADOW_OVERRIDES) {{
  const __raw = FA_PROD_MULT_DATA[__o.key];
  const __list = Array.isArray(__raw) ? __raw : [__raw];
  let __matched = 0;
  for (const __entry of __list) {{
    if (__entry && __entry.pos === __o.pos) {{
      __entry.prod = __o.prod;
      __matched += 1;
    }}
  }}
  if (__matched !== 1) {{
    throw new Error(
      'FA V2 shadow override match failure for ' +
      __o.sleeper_id + ' ' + __o.key + ' ' + __o.pos + ': ' + __matched
    );
  }}
}}
"""
    return board_text[:end] + "\n" + snippet + board_text[end:]

def phase1_integrity(phase1, manifest):
    mismatches = []
    for rel, expected in (manifest.get("output_sha256") or {}).items():
        path = ROOT / rel
        actual = sha256(path) if path.exists() else "missing"
        if actual != expected:
            mismatches.append({"path": rel, "expected": expected, "actual": actual})
    return mismatches

def phase1_input_drift(phase1):
    drift = []
    for rel, expected in (phase1.get("input_sha256") or {}).items():
        path = ROOT / rel
        actual = sha256(path) if path.exists() else "missing"
        if actual != expected:
            drift.append({"path": rel, "expected": expected, "actual": actual})
    return drift

def build_result():
    scripts = ROOT / "scripts"
    validation = scripts / "validation"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    if str(validation) not in sys.path:
        sys.path.insert(0, str(validation))

    import validate_free_agent_valuation_parity as fa_validator
    from sync import sync_free_agent_valuation as sync_mod

    phase1 = read_json(PHASE1_JSON)
    manifest1 = read_json(PHASE1_MANIFEST)
    prereg = read_json(PREREG_JSON)
    free_doc = read_json(FREE_AGENTS)

    output_hash_mismatches = phase1_integrity(phase1, manifest1)
    input_drift = phase1_input_drift(phase1)

    parity_result = fa_validator.validate()
    board_text = BOARD.read_text(encoding="utf-8")
    current_runtime = fa_validator._board_runtime_rows(board_text, free_doc)
    current_by_id = attach_sleeper_ids(
        current_runtime["rows"], free_doc, fa_validator
    )

    phase1_rows = list(phase1.get("rows") or [])
    active_ids = {str(r["sleeper_id"]) for r in phase1_rows}
    candidates = [r for r in phase1_rows if r.get("candidate_prod") is not None]
    candidate_ids = {str(r["sleeper_id"]) for r in candidates}
    unresolved_ids = active_ids - candidate_ids

    shadow_board_text = inject_shadow_overrides(
        board_text, candidates, sync_mod
    )
    shadow_runtime = fa_validator._board_runtime_rows(
        shadow_board_text, free_doc
    )
    shadow_by_id = attach_sleeper_ids(
        shadow_runtime["rows"], free_doc, fa_validator
    )

    current_sources = {
        str(k): str(v)
        for k, v in current_runtime["production_source_by_id"].items()
    }
    shadow_sources = {
        str(k): str(v)
        for k, v in shadow_runtime["production_source_by_id"].items()
    }
    current_active_ids = {
        sid for sid, source in current_sources.items()
        if source == "fa_specific_prod"
        and current_by_id.get(sid, {}).get("pos") in TRACKED
    }

    candidate_by_id = {str(r["sleeper_id"]): r for r in candidates}

    current_board_rank = deterministic_ranks(current_by_id)
    shadow_board_rank = deterministic_ranks(shadow_by_id)
    current_active_rank = deterministic_ranks(current_by_id, active_ids)
    shadow_active_rank = deterministic_ranks(shadow_by_id, active_ids)
    current_pos_rank = position_ranks(current_by_id)
    shadow_pos_rank = position_ranks(shadow_by_id)

    candidate_rows = []
    metadata_violations = []
    monotonicity_violations = []
    invalid_candidate_values = []

    for sid in sorted(candidate_ids):
        old = current_by_id[sid]
        new = shadow_by_id[sid]
        src = candidate_by_id[sid]
        old_val = int(old["val"])
        new_val = int(new["val"])
        fv_delta = new_val - old_val
        prod_delta = float(src["candidate_prod"]) - float(src["deployed_prod"])

        metadata_fields = ("name", "pos", "team", "age", "role", "hasRealData")
        changed_meta = [
            f for f in metadata_fields if old.get(f) != new.get(f)
        ]
        if changed_meta:
            metadata_violations.append({
                "sleeper_id": sid,
                "fields": changed_meta,
            })

        if not isinstance(new.get("val"), int) or int(new["val"]) <= 0:
            invalid_candidate_values.append(sid)

        eps = 1e-12
        if (prod_delta > eps and fv_delta < 0) or (prod_delta < -eps and fv_delta > 0):
            monotonicity_violations.append({
                "sleeper_id": sid,
                "prod_delta": prod_delta,
                "fv_delta": fv_delta,
            })

        pos = old["pos"]
        candidate_rows.append({
            "sleeper_id": sid,
            "name": old["name"],
            "pos": pos,
            "team": old.get("team"),
            "age": old.get("age"),
            "role": old.get("role"),
            "deployed_prod": float(src["deployed_prod"]),
            "candidate_prod": float(src["candidate_prod"]),
            "prod_delta": prod_delta,
            "current_fv": old_val,
            "shadow_fv": new_val,
            "fv_delta": fv_delta,
            "abs_fv_delta": abs(fv_delta),
            "fv_pct_change": (
                fv_delta / old_val if old_val else None
            ),
            "current_board_rank": current_board_rank[sid],
            "shadow_board_rank": shadow_board_rank[sid],
            "board_rank_delta": shadow_board_rank[sid] - current_board_rank[sid],
            "current_active_rank": current_active_rank[sid],
            "shadow_active_rank": shadow_active_rank[sid],
            "active_rank_delta": shadow_active_rank[sid] - current_active_rank[sid],
            "current_position_rank": current_pos_rank[pos][sid],
            "shadow_position_rank": shadow_pos_rank[pos][sid],
            "position_rank_delta": shadow_pos_rank[pos][sid] - current_pos_rank[pos][sid],
            "forward_source": src["forward"]["source"],
        })

    noncandidate_changed = []
    unresolved_changed = []
    for sid in sorted(current_by_id):
        if sid in candidate_ids:
            continue
        old_val = int(current_by_id[sid]["val"])
        new_val = int(shadow_by_id[sid]["val"])
        if old_val != new_val:
            noncandidate_changed.append({
                "sleeper_id": sid,
                "name": current_by_id[sid]["name"],
                "pos": current_by_id[sid]["pos"],
                "current_fv": old_val,
                "shadow_fv": new_val,
            })
            if sid in unresolved_ids:
                unresolved_changed.append(sid)

    by_pos = {}
    for pos in TRACKED:
        rows = [r for r in candidate_rows if r["pos"] == pos]
        active_pos = [
            sid for sid in active_ids
            if current_by_id.get(sid, {}).get("pos") == pos
        ]
        unresolved_pos = [
            sid for sid in unresolved_ids
            if current_by_id.get(sid, {}).get("pos") == pos
        ]
        by_pos[pos] = {
            "active_fa_specific": len(active_pos),
            "candidate_count": len(rows),
            "unresolved_held": len(unresolved_pos),
            "changed_fv_count": sum(r["fv_delta"] != 0 for r in rows),
            "increased_fv_count": sum(r["fv_delta"] > 0 for r in rows),
            "decreased_fv_count": sum(r["fv_delta"] < 0 for r in rows),
            "unchanged_fv_count": sum(r["fv_delta"] == 0 for r in rows),
            "fv_delta": summarize([r["fv_delta"] for r in rows]),
            "abs_fv_delta": summarize([r["abs_fv_delta"] for r in rows]),
            "position_rank_abs_move": summarize(
                [abs(r["position_rank_delta"]) for r in rows]
            ),
        }

    def top_overlap(n):
        old = sorted(active_ids, key=lambda sid: current_active_rank[sid])[:n]
        new = sorted(active_ids, key=lambda sid: shadow_active_rank[sid])[:n]
        a, b = set(old), set(new)
        return {
            "n": min(n, len(active_ids)),
            "overlap_count": len(a & b),
            "overlap_share": len(a & b) / len(a) if a else 1.0,
        }

    phase1_pass = phase1.get("decision") == "PASS_FA_PROD_V2_PHASE1_LINEAGE_AND_FREEZE"
    frozen_candidate_count = int(
        phase1.get("counts", {}).get("reproducible_candidates", -1)
    )
    frozen_active_count = int(
        phase1.get("counts", {}).get("active_non_k_deployed_entries", -1)
    )

    gates = {
        "phase1_decision_pass": {
            "pass": phase1_pass,
            "decision": phase1.get("decision"),
        },
        "phase1_output_hashes_intact": {
            "pass": not output_hash_mismatches,
            "mismatches": output_hash_mismatches,
        },
        "phase1_input_snapshot_unchanged": {
            "pass": not input_drift,
            "drift": input_drift,
        },
        "frozen_candidate_count_exact": {
            "pass": len(candidate_ids) == frozen_candidate_count,
            "expected": frozen_candidate_count,
            "actual": len(candidate_ids),
        },
        "frozen_active_count_exact": {
            "pass": len(active_ids) == frozen_active_count,
            "expected": frozen_active_count,
            "actual": len(active_ids),
        },
        "current_runtime_active_identity_exact": {
            "pass": current_active_ids == active_ids,
            "missing_from_runtime": sorted(active_ids - current_active_ids),
            "extra_in_runtime": sorted(current_active_ids - active_ids),
        },
        "shadow_source_classification_unchanged": {
            "pass": current_sources == shadow_sources,
        },
        "unresolved_rows_held_exact": {
            "pass": not unresolved_changed,
            "unresolved_count": len(unresolved_ids),
            "changed_ids": unresolved_changed,
        },
        "all_non_candidate_rows_unchanged": {
            "pass": not noncandidate_changed,
            "changed_count": len(noncandidate_changed),
            "changed_rows": noncandidate_changed[:25],
        },
        "candidate_metadata_unchanged": {
            "pass": not metadata_violations,
            "violations": metadata_violations[:25],
        },
        "candidate_values_valid": {
            "pass": not invalid_candidate_values,
            "invalid_ids": invalid_candidate_values,
        },
        "candidate_fv_monotonic_with_prod": {
            "pass": not monotonicity_violations,
            "violations": monotonicity_violations[:25],
        },
        "free_agent_parity_and_roster_safety": {
            "pass": (
                parity_result.get("status") == "PASS"
                and int(parity_result.get("roster_overlap", -1)) == 0
            ),
            "validator_status": parity_result.get("status"),
            "roster_overlap": parity_result.get("roster_overlap"),
        },
    }

    all_pass = all(g["pass"] for g in gates.values())
    decision = (
        "PASS_FA_PROD_V2_PHASE2_SHADOW_VALIDATION"
        if all_pass
        else "STOP_FA_PROD_V2_PHASE2_SHADOW_VALIDATION"
    )

    largest_fv_movers = sorted(
        candidate_rows,
        key=lambda r: (-r["abs_fv_delta"], r["name"], r["sleeper_id"]),
    )[:40]
    largest_rank_movers = sorted(
        candidate_rows,
        key=lambda r: (-abs(r["active_rank_delta"]), r["name"], r["sleeper_id"]),
    )[:40]

    return {
        "study_id": "free-agent-production-v2",
        "phase": 2,
        "status": "SHADOW_VALIDATION_COMPLETE",
        "decision": decision,
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "preregistration_sha256": sha256(PREREG_JSON),
        "phase1": {
            "decision": phase1.get("decision"),
            "candidate_count": len(candidate_ids),
            "active_count": len(active_ids),
            "unresolved_held_count": len(unresolved_ids),
        },
        "gates": gates,
        "diagnostics": {
            "candidate_fv_delta": summarize(
                [r["fv_delta"] for r in candidate_rows]
            ),
            "candidate_abs_fv_delta": summarize(
                [r["abs_fv_delta"] for r in candidate_rows]
            ),
            "candidate_fv_pct_change": summarize(
                [r["fv_pct_change"] for r in candidate_rows]
            ),
            "candidate_changed_fv_count": sum(
                r["fv_delta"] != 0 for r in candidate_rows
            ),
            "candidate_increased_fv_count": sum(
                r["fv_delta"] > 0 for r in candidate_rows
            ),
            "candidate_decreased_fv_count": sum(
                r["fv_delta"] < 0 for r in candidate_rows
            ),
            "active_rank_spearman": spearman_from_ordinal_rank_maps(
                current_active_rank, shadow_active_rank, active_ids
            ),
            "top_overlap": {
                "top25": top_overlap(25),
                "top50": top_overlap(50),
                "top100": top_overlap(100),
            },
            "position_summary": by_pos,
            "largest_fv_movers": largest_fv_movers,
            "largest_active_rank_movers": largest_rank_movers,
        },
        "candidate_rows": candidate_rows,
        "next_step_if_pass": "SEPARATE_GUARDED_PRODUCTION_CONFIRMATION",
        "next_step_if_stop": "REPAIR_SHADOW_INVARIANT_BEFORE_DEPLOYMENT_CONSIDERATION",
    }

def markdown(r):
    g = r["gates"]
    d = r["diagnostics"]
    lines = [
        "# Free-Agent Production V2 — Phase 2 Shadow Validation",
        "",
        f"**Decision:** `{r['decision']}`",
        "",
        "This phase is shadow-only. No production change is authorized.",
        "",
        "## Frozen population",
        "",
        f"- Active FA-specific cohort: **{r['phase1']['active_count']}**",
        f"- Reproducible candidates: **{r['phase1']['candidate_count']}**",
        f"- Unresolved rows held at deployed values: **{r['phase1']['unresolved_held_count']}**",
        "",
        "## Hard gates",
        "",
        "| Gate | Result |",
        "|---|---|",
    ]
    for key, gate in g.items():
        lines.append(f"| `{key}` | {'PASS' if gate['pass'] else 'FAIL'} |")

    lines += [
        "",
        "## Shadow movement diagnostics",
        "",
        f"- Candidate rows with changed FV: **{d['candidate_changed_fv_count']}**",
        f"- Increased FV: **{d['candidate_increased_fv_count']}**",
        f"- Decreased FV: **{d['candidate_decreased_fv_count']}**",
        f"- Active-cohort rank Spearman: **{d['active_rank_spearman']:.4f}**",
        f"- Top-25 overlap: **{d['top_overlap']['top25']['overlap_share']:.1%}**",
        f"- Top-50 overlap: **{d['top_overlap']['top50']['overlap_share']:.1%}**",
        f"- Top-100 overlap: **{d['top_overlap']['top100']['overlap_share']:.1%}**",
        "",
        "### Position summary",
        "",
        "| Pos | Active | Candidate | Held | Median ΔFV | P90 | Max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pos in TRACKED:
        s = d["position_summary"][pos]
        fd = s["fv_delta"]
        lines.append(
            f"| {pos} | {s['active_fa_specific']} | {s['candidate_count']} | "
            f"{s['unresolved_held']} | {fd.get('median', 0):+.1f} | "
            f"{fd.get('p90', 0):+.1f} | {fd.get('max', 0):+.1f} |"
        )

    lines += [
        "",
        "### Largest FV movers",
        "",
        "| Player | Pos | Old FV | Shadow FV | ΔFV | Old Prod | New Prod |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in d["largest_fv_movers"][:20]:
        lines.append(
            f"| {row['name']} | {row['pos']} | {row['current_fv']} | "
            f"{row['shadow_fv']} | {row['fv_delta']:+d} | "
            f"{row['deployed_prod']:.3f} | {row['candidate_prod']:.3f} |"
        )

    lines += [
        "",
        "## Decision semantics",
        "",
        "A PASS proves the frozen candidate can be isolated inside the real board "
        "runtime without spillover or safety violations. It does **not** authorize "
        "deployment. Magnitude and rank movement remain diagnostics for the separate "
        "production-confirmation step.",
        "",
    ]
    return "\n".join(lines)

def write_outputs():
    result = build_result()
    OUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUT_MD.write_text(markdown(result) + "\n", encoding="utf-8")

    manifest = {
        "study_id": result["study_id"],
        "phase": 2,
        "decision": result["decision"],
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": result["repo_commit_sha_evaluated"],
        "preregistration_sha256": result["preregistration_sha256"],
        "phase1_manifest_sha256": sha256(PHASE1_MANIFEST),
        "output_sha256": {
            str(PREREG_JSON.relative_to(ROOT)): sha256(PREREG_JSON),
            str(PREREG_MD.relative_to(ROOT)): sha256(PREREG_MD),
            str(SCRIPT.relative_to(ROOT)): sha256(SCRIPT),
            str(OUT_JSON.relative_to(ROOT)): sha256(OUT_JSON),
            str(OUT_MD.relative_to(ROOT)): sha256(OUT_MD),
        },
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "decision": result["decision"],
        "candidate_count": result["phase1"]["candidate_count"],
        "unresolved_held_count": result["phase1"]["unresolved_held_count"],
        "changed_fv_count": result["diagnostics"]["candidate_changed_fv_count"],
        "rank_spearman": result["diagnostics"]["active_rank_spearman"],
    }, indent=2))

def selftest():
    rows = {
        "1": {"val": 100, "name": "a", "pos": "WR"},
        "2": {"val": 200, "name": "b", "pos": "WR"},
        "3": {"val": 200, "name": "a", "pos": "RB"},
    }
    ranks = deterministic_ranks(rows)
    assert ranks["3"] == 1
    assert ranks["2"] == 2
    assert ranks["1"] == 3
    assert summarize([1, 2, 3])["median"] == 2
    assert abs(spearman_from_ordinal_rank_maps(
        {"1": 1, "2": 2}, {"1": 1, "2": 2}, {"1", "2"}
    ) - 1.0) < 1e-12
    print("Free-Agent Production V2 Phase 2 self-test PASS")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if args.write:
        write_outputs()
        return
    ap.error("choose --selftest or --write")

if __name__ == "__main__":
    main()

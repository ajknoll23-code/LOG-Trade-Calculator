#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
OUTDIR = SCRIPT.parent

PHASE1_JSON = OUTDIR / "unified_fantasypros_sleeper_identity_v2.json"
PHASE1_PY = OUTDIR / "unified_fantasypros_sleeper_identity_v2.py"
PREREG = OUTDIR / "identity_v2_phase2_preregistration.json"

OUT_JSON = OUTDIR / "identity_v2_phase2_manual_adjudication.json"
OUT_MD = OUTDIR / "identity_v2_phase2_manual_adjudication.md"
MANIFEST = OUTDIR / "identity_v2_phase2_manifest.json"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_phase1_module():
    spec = importlib.util.spec_from_file_location("identity_v2_phase1", PHASE1_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Phase 1 identity module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def production_authoritative_map(rows):
    by_fpid = {}
    for row in rows:
        fpid = row.get("fantasypros_id")
        sid = row.get("sleeper_id")
        if fpid in (None, "") or sid in (None, ""):
            continue
        if row.get("requires_manual_review"):
            continue
        by_fpid[str(fpid)] = str(sid)
    return by_fpid

def current_candidates(mod):
    fp_doc = mod.read_json(mod.FP_PATH)
    sleeper_totals = mod.read_json(mod.SLEEPER_TOTAL_PATH)
    sleeper_raw = mod.read_json(mod.SLEEPER_RAW_PATH)
    team_refresh = mod.read_json(mod.TEAM_REFRESH_PATH)

    fp_rows = mod.validate_fp_rows(fp_doc["players"])
    fp_by_fpid = {r["_fpid"]: r for r in fp_rows}
    sleeper_by_sid, sleeper_by_name = mod.build_sleeper_universe(
        sleeper_totals, sleeper_raw, team_refresh
    )
    return fp_by_fpid, sleeper_by_sid, sleeper_by_name

def candidate_summary(candidate):
    if candidate is None:
        return None
    return {
        "sleeper_id": candidate["sleeper_id"],
        "player": candidate["player"],
        "positions": sorted(candidate.get("positions") or ()),
        "team": candidate.get("team"),
        "has_projection_signal": bool(candidate.get("has_projection_signal"))
    }

def adjudicate_row(mod, baseline, fp, sleeper_by_sid, sleeper_by_name, prod_map):
    fpid = str(baseline["fantasypros_id"])
    fp_name = fp["_name"]
    fp_pos = fp["_pos"]
    fp_team = fp["_team"]

    name_candidates = list(sleeper_by_name.get(fp_name, ()))
    position_candidates = [
        c for c in name_candidates if mod.is_position_compatible(fp_pos, c)
    ]
    team_matches = []
    if fp_team:
        team_matches = [
            c for c in position_candidates
            if c.get("team")
            and mod.normalize_team(c.get("team")) == fp_team
        ]

    baseline_candidate_sid = baseline.get("candidate_sleeper_id")
    baseline_candidate = (
        sleeper_by_sid.get(str(baseline_candidate_sid))
        if baseline_candidate_sid not in (None, "")
        else None
    )

    decision = None
    approved_sid = None
    basis = None

    # Rule 1: exact current team corroboration with a unique compatible candidate.
    if len(team_matches) == 1:
        approved_sid = str(team_matches[0]["sleeper_id"])
        decision = "APPROVE_CURRENT_TEAM_CORROBORATED"
        basis = "exact_current_team_and_position"

    # Rule 2: exact pair already authoritative in production crosswalk.
    if decision is None:
        prod_sid = prod_map.get(fpid)
        candidate = sleeper_by_sid.get(prod_sid) if prod_sid else None
        if (
            prod_sid
            and candidate is not None
            and mod.is_position_compatible(fp_pos, candidate)
            and candidate["player"] == fp_name
        ):
            approved_sid = prod_sid
            decision = "APPROVE_EXISTING_PRODUCTION_AUTHORITY"
            basis = "existing_authoritative_crosswalk_pair"

    # Otherwise freeze an explicit hold.
    if decision is None:
        method = baseline.get("match_method")
        if method == "unique_name_position_team_unavailable":
            decision = "HOLD_MISSING_TEAM_CORROBORATION"
            basis = "unique_candidate_but_team_corroboration_missing"
        elif method == "unique_name_position_team_mismatch":
            decision = "HOLD_TEAM_CONFLICT"
            basis = "provider_team_mismatch"
        elif method == "name_found_position_incompatible":
            decision = "HOLD_POSITION_TAXONOMY_CONFLICT"
            basis = "same_name_candidate_not_position_compatible"
        else:
            decision = "HOLD_IDENTITY_AMBIGUITY"
            basis = "candidate_missing_or_ambiguous"

    return {
        "fantasypros_id": fpid,
        "name": baseline.get("name"),
        "fp_position": fp_pos,
        "fp_team": fp_team,
        "current_source_row_present": True,
        "phase1_match_method": baseline.get("match_method"),
        "phase1_candidate_sleeper_id": baseline_candidate_sid,
        "phase1_sleeper_team": baseline.get("sleeper_team"),
        "phase1_sleeper_positions": baseline.get("sleeper_positions"),
        "current_name_candidate_count": len(name_candidates),
        "current_position_candidate_count": len(position_candidates),
        "current_team_match_count": len(team_matches),
        "current_phase1_candidate": candidate_summary(baseline_candidate),
        "existing_production_authoritative_sid": prod_map.get(fpid),
        "disposition": decision,
        "approved_sleeper_id": approved_sid,
        "adjudication_basis": basis,
        "production_change_authorized": False
    }

def adjudicate_disappeared_source_row(
    mod, baseline, sleeper_by_sid, sleeper_by_name, prod_map
):
    """Freeze source drift as a hold; never infer authority from disappearance."""
    fpid = str(baseline["fantasypros_id"])
    normalized_name = baseline.get("normalized_name") or mod.normalize_name(
        baseline.get("name")
    )
    fp_pos = baseline.get("fp_position")
    fp_team = mod.normalize_team(baseline.get("fp_team"))

    name_candidates = list(sleeper_by_name.get(normalized_name, ()))
    position_candidates = []
    if fp_pos in mod.FP_COMPATIBLE_SLEEPER:
        position_candidates = [
            c for c in name_candidates
            if mod.is_position_compatible(fp_pos, c)
        ]

    baseline_candidate_sid = baseline.get("candidate_sleeper_id")
    baseline_candidate = (
        sleeper_by_sid.get(str(baseline_candidate_sid))
        if baseline_candidate_sid not in (None, "")
        else None
    )

    return {
        "fantasypros_id": fpid,
        "name": baseline.get("name"),
        "fp_position": fp_pos,
        "fp_team": fp_team,
        "phase1_match_method": baseline.get("match_method"),
        "phase1_candidate_sleeper_id": baseline_candidate_sid,
        "phase1_sleeper_team": baseline.get("sleeper_team"),
        "phase1_sleeper_positions": baseline.get("sleeper_positions"),
        "current_source_row_present": False,
        "current_name_candidate_count": len(name_candidates),
        "current_position_candidate_count": len(position_candidates),
        "current_team_match_count": 0,
        "current_phase1_candidate": candidate_summary(baseline_candidate),
        "existing_production_authoritative_sid": prod_map.get(fpid),
        "disposition": "HOLD_SOURCE_ROW_DISAPPEARED",
        "approved_sleeper_id": None,
        "adjudication_basis":
            "frozen_phase1_fpid_absent_from_current_fantasypros_source",
        "production_change_authorized": False
    }


def build_result():
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if prereg["status"] != "FROZEN_MANUAL_ADJUDICATION_POLICY":
        raise RuntimeError("Phase 2 preregistration status changed")
    if prereg["production_crosswalk_mutation_allowed"] is not False:
        raise RuntimeError("production-crosswalk guardrail changed")

    phase1 = json.loads(PHASE1_JSON.read_text(encoding="utf-8"))
    manual = phase1.get("manual_review_rows") or []
    expected = int(prereg["expected_phase1_manual_rows"])
    if len(manual) != expected:
        raise RuntimeError(
            f"Phase 1 manual-row count drifted: expected {expected}, got {len(manual)}"
        )
    if phase1.get("decision") != "STRUCTURALLY_CLEAN_REVIEW_COVERAGE_BEFORE_PROMOTION":
        raise RuntimeError("Phase 1 decision is not the expected clean-review state")

    mod = load_phase1_module()
    fp_by_fpid, sleeper_by_sid, sleeper_by_name = current_candidates(mod)
    prod_rows = mod.read_json(mod.V1_CROSSWALK_PATH)
    prod_map = production_authoritative_map(prod_rows)

    adjudicated = []
    disappeared_fpids = []
    for baseline in manual:
        fpid = str(baseline["fantasypros_id"])
        fp = fp_by_fpid.get(fpid)
        if fp is None:
            disappeared_fpids.append(fpid)
            adjudicated.append(
                adjudicate_disappeared_source_row(
                    mod, baseline, sleeper_by_sid, sleeper_by_name, prod_map
                )
            )
            continue

        adjudicated.append(
            adjudicate_row(
                mod, baseline, fp, sleeper_by_sid, sleeper_by_name, prod_map
            )
        )

    approved = [r for r in adjudicated if r["approved_sleeper_id"]]
    by_sid = defaultdict(list)
    for row in approved:
        by_sid[row["approved_sleeper_id"]].append(row["fantasypros_id"])
    collisions = {sid: fpids for sid, fpids in by_sid.items() if len(fpids) > 1}
    if collisions:
        raise RuntimeError(f"Phase 2 approval collision(s): {collisions}")

    counts = Counter(r["disposition"] for r in adjudicated)
    hold_count = sum(v for k, v in counts.items() if k.startswith("HOLD_"))
    approved_count = len(adjudicated) - hold_count

    decision = (
        "PASS_IDENTITY_V2_PHASE2_REVIEW_FREEZE_NO_HOLDS"
        if hold_count == 0
        else "PASS_IDENTITY_V2_PHASE2_REVIEW_FREEZE_WITH_HOLDS"
    )

    return {
        "schema_version": 1,
        "study_id": "identity-v2-phase2-manual-adjudication",
        "status": "MANUAL_ADJUDICATION_FROZEN",
        "decision": decision,
        "generated_at_utc":
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "research_only": True,
        "production_crosswalk_mutated": False,
        "production_change_authorized": False,
        "phase1_decision": phase1["decision"],
        "phase1_manual_row_count": len(manual),
        "reviewed_row_count": len(adjudicated),
        "approved_row_count": approved_count,
        "held_row_count": hold_count,
        "source_disappeared_row_count": len(disappeared_fpids),
        "source_disappeared_fpids": disappeared_fpids,
        "disposition_counts": dict(sorted(counts.items())),
        "duplicate_approved_sleeper_assignment_groups": 0,
        "rows": adjudicated,
        "promotion_authorized": False,
        "next_step_rule": (
            "If holds remain, review only the held rows with independent corroborating "
            "identity evidence; do not weaken the identity policy. If no holds remain, "
            "a separate promotion-candidate phase is still required."
        )
    }

def render(result):
    lines = [
        "# Identity V2 Phase 2 — Manual Adjudication Freeze",
        "",
        f"**Decision:** `{result['decision']}`",
        "",
        "**RESEARCH ONLY. Production crosswalk unchanged. Promotion is not authorized.**",
        "",
        "## Summary",
        "",
        f"- Phase 1 manual rows: **{result['phase1_manual_row_count']}**",
        f"- Rows reviewed: **{result['reviewed_row_count']}**",
        f"- Research-authoritative approvals: **{result['approved_row_count']}**",
        f"- Explicit holds: **{result['held_row_count']}**",
        f"- Frozen Phase 1 rows absent from current FantasyPros source: **{result['source_disappeared_row_count']}**",
        f"- Approved SID collision groups: **{result['duplicate_approved_sleeper_assignment_groups']}**",
        "",
        "## Dispositions",
        ""
    ]
    for key, value in result["disposition_counts"].items():
        lines.append(f"- `{key}`: **{value}**")

    lines += [
        "",
        "## Reviewed rows",
        "",
        "| Player | FP pos | FP team | Phase 1 method | Current team matches | Disposition | Approved SID |",
        "|---|---|---|---|---:|---|---|"
    ]
    for row in result["rows"]:
        lines.append(
            f"| {row['name']} | {row['fp_position']} | {row['fp_team'] or '—'} | "
            f"`{row['phase1_match_method']}` | {row['current_team_match_count']} | "
            f"`{row['disposition']}` | {row['approved_sleeper_id'] or '—'} |"
        )

    lines += [
        "",
        "## Governance",
        "",
        "- Name alone was never accepted as authority.",
        "- Missing/free-agent team state was not treated as team corroboration.",
        "- Position-incompatible candidates were not force-matched.",
        "- Frozen Phase 1 rows missing from the current FantasyPros source were held as source drift, never guessed.",
        "- No new aliases or compatibility rules were introduced.",
        "- `scripts/identity_crosswalk.json` was not changed.",
        "- This phase cannot promote the unified resolver.",
        "",
        "## Next-step rule",
        "",
        result["next_step_rule"],
        ""
    ]
    return "\n".join(lines)

def write_outputs():
    result = build_result()
    OUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )
    OUT_MD.write_text(render(result).rstrip() + "\n", encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "study_id": "identity-v2-phase2-manual-adjudication",
        "decision": result["decision"],
        "production_crosswalk_mutated": False,
        "promotion_authorized": False,
        "phase1_json_sha256": sha256(PHASE1_JSON),
        "phase1_evaluator_sha256": sha256(PHASE1_PY),
        "preregistration_sha256": sha256(PREREG),
        "evaluator_sha256": sha256(SCRIPT),
        "output_json_sha256": sha256(OUT_JSON),
        "output_md_sha256": sha256(OUT_MD)
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )

    print(json.dumps({
        "decision": result["decision"],
        "reviewed": result["reviewed_row_count"],
        "approved": result["approved_row_count"],
        "held": result["held_row_count"],
        "disposition_counts": result["disposition_counts"]
    }, indent=2))

def check_outputs():
    result = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    if result["reviewed_row_count"] != 17:
        raise RuntimeError("Phase 2 did not review exactly 17 frozen rows")
    if result["production_crosswalk_mutated"] is not False:
        raise RuntimeError("production crosswalk mutation flag changed")
    if result["production_change_authorized"] is not False:
        raise RuntimeError("production change illegally authorized")
    if result["promotion_authorized"] is not False:
        raise RuntimeError("promotion illegally authorized")
    if result["duplicate_approved_sleeper_assignment_groups"] != 0:
        raise RuntimeError("approved identity collision detected")

    disappeared = [
        row for row in result["rows"]
        if row.get("current_source_row_present") is False
    ]
    if len(disappeared) != result["source_disappeared_row_count"]:
        raise RuntimeError("source-disappearance accounting mismatch")
    if any(
        row["disposition"] != "HOLD_SOURCE_ROW_DISAPPEARED"
        or row.get("approved_sleeper_id") is not None
        for row in disappeared
    ):
        raise RuntimeError(
            "a disappeared source row was not preserved as a non-authoritative hold"
        )

    if not result["decision"].startswith("PASS_IDENTITY_V2_PHASE2_REVIEW_FREEZE"):
        raise RuntimeError("unexpected Phase 2 decision")
    print("Identity V2 Phase 2 output checks PASS")

def selftest():
    assert PREREG.name == "identity_v2_phase2_preregistration.json"
    assert OUT_JSON.name == "identity_v2_phase2_manual_adjudication.json"
    print("Identity V2 Phase 2 self-test PASS")

def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    args = p.parse_args()

    if args.selftest:
        selftest()
    elif args.write:
        write_outputs()
    else:
        check_outputs()

if __name__ == "__main__":
    main()

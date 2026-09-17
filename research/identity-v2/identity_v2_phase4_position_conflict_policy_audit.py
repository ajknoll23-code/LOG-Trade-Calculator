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

PHASE1_PY = OUTDIR / "unified_fantasypros_sleeper_identity_v2.py"
PHASE2 = OUTDIR / "identity_v2_phase2_manual_adjudication.json"
PHASE3 = OUTDIR / "identity_v2_phase3_independent_corroboration.json"
PREREG = OUTDIR / "identity_v2_phase4_preregistration.json"
PROD_CROSSWALK = ROOT / "scripts" / "identity_crosswalk.json"

OUTJSON = OUTDIR / "identity_v2_phase4_position_conflict_policy_audit.json"
OUTMD = OUTDIR / "identity_v2_phase4_position_conflict_policy_audit.md"
MANIFEST = OUTDIR / "identity_v2_phase4_manifest.json"

EXPECTED_PHASE3 = {
    "26313": "OFFICIAL_POSITION_SUPPORTS_SLEEPER_TAXONOMY",
    "26157": "OFFICIAL_POSITION_TAXONOMY_REMAINS_AMBIGUOUS",
    "27959": "OFFICIAL_POSITION_SUPPORTS_FANTASYPROS_TAXONOMY",
    "28290": "OFFICIAL_POSITION_SUPPORTS_SLEEPER_TAXONOMY"
}

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_phase1():
    spec = importlib.util.spec_from_file_location("identity_v2_phase1", PHASE1_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Identity V2 Phase 1 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def current_inputs(mod):
    fp_doc = mod.read_json(mod.FP_PATH)
    totals = mod.read_json(mod.SLEEPER_TOTAL_PATH)
    raw = mod.read_json(mod.SLEEPER_RAW_PATH)
    teams = mod.read_json(mod.TEAM_REFRESH_PATH)
    fp_rows = mod.validate_fp_rows(fp_doc["players"])
    by_sid, by_name = mod.build_sleeper_universe(totals, raw, teams)
    return fp_rows, by_sid, by_name

def current_authoritative_sids():
    rows = json.loads(PROD_CROSSWALK.read_text(encoding="utf-8"))
    out = defaultdict(list)
    for row in rows:
        sid = row.get("sleeper_id")
        fpid = row.get("fantasypros_id")
        if sid in (None, "") or fpid in (None, ""):
            continue
        if row.get("requires_manual_review"):
            continue
        out[str(sid)].append(str(fpid))
    return out

def exact_name_team_override_candidate(mod, fp, sleeper_by_name):
    candidates = list(sleeper_by_name.get(fp["_name"], ()))
    team_matches = []
    if fp["_team"]:
        team_matches = [
            c for c in candidates
            if c.get("team")
            and mod.normalize_team(c.get("team")) == fp["_team"]
        ]
    if len(candidates) == 1 and len(team_matches) == 1:
        c = team_matches[0]
        return {
            "sleeper_id": str(c["sleeper_id"]),
            "team": c.get("team"),
            "positions": sorted(c.get("positions") or ()),
            "candidate_count": 1,
            "team_match_count": 1
        }
    return {
        "sleeper_id": None,
        "team": None,
        "positions": [],
        "candidate_count": len(candidates),
        "team_match_count": len(team_matches)
    }

def build():
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    phase2 = json.loads(PHASE2.read_text(encoding="utf-8"))
    phase3 = json.loads(PHASE3.read_text(encoding="utf-8"))

    if prereg["status"] != "FROZEN_POLICY_ARMS":
        raise RuntimeError("Phase 4 preregistration changed")
    if prereg["production_change_authorized"] is not False:
        raise RuntimeError("Phase 4 illegally authorizes production")
    if phase3["decision"] != "PASS_IDENTITY_V2_PHASE3_EXTERNAL_CORROBORATION_FREEZE":
        raise RuntimeError("Phase 3 decision mismatch")

    phase3_by_fpid = {
        str(row["fantasypros_id"]): row
        for row in phase3["rows"]
    }
    for fpid, expected in EXPECTED_PHASE3.items():
        actual = (phase3_by_fpid.get(fpid) or {}).get("classification")
        if actual != expected:
            raise RuntimeError(
                f"Phase 3 classification drift for {fpid}: "
                f"expected={expected}, actual={actual}"
            )

    targets = {
        str(k): v
        for k, v in prereg["frozen_explicit_target_fpids"].items()
    }
    ambiguous = {
        str(k): v
        for k, v in prereg["frozen_ambiguous_hold_fpids"].items()
    }

    mod = load_phase1()
    fp_rows, sleeper_by_sid, sleeper_by_name = current_inputs(mod)
    fp_by_fpid = {fp["_fpid"]: fp for fp in fp_rows}
    prior_by_sid = current_authoritative_sids()

    baseline = {}
    for fp in fp_rows:
        baseline[fp["_fpid"]] = mod.resolve_one(fp, sleeper_by_name)

    incompatible = [
        fp for fp in fp_rows
        if baseline[fp["_fpid"]].get("match_method")
        == "name_found_position_incompatible"
    ]

    generic_additions = {}
    generic_diagnostics = []
    for fp in incompatible:
        cand = exact_name_team_override_candidate(mod, fp, sleeper_by_name)
        if cand["sleeper_id"]:
            generic_additions[fp["_fpid"]] = cand["sleeper_id"]
        generic_diagnostics.append({
            "fantasypros_id": fp["_fpid"],
            "name": fp.get("name"),
            "fp_position": fp["_pos"],
            "fp_team": fp["_team"],
            "override_candidate": cand
        })

    explicit_additions = {}
    explicit_rows = []
    for fpid, expected_name in targets.items():
        fp = fp_by_fpid.get(fpid)
        if fp is None:
            raise RuntimeError(f"explicit target FPID missing: {fpid}")
        if str(fp.get("name") or "") != expected_name:
            raise RuntimeError(
                f"explicit target name drift for {fpid}: "
                f"{fp.get('name')!r} != {expected_name!r}"
            )
        if baseline[fpid].get("match_method") != "name_found_position_incompatible":
            raise RuntimeError(
                f"explicit target {fpid} no longer fails strictly by position"
            )
        cand = exact_name_team_override_candidate(mod, fp, sleeper_by_name)
        explicit_rows.append({
            "fantasypros_id": fpid,
            "name": expected_name,
            "fp_position": fp["_pos"],
            "fp_team": fp["_team"],
            "phase3_classification":
                phase3_by_fpid[fpid]["classification"],
            "override_candidate": cand
        })
        if cand["sleeper_id"]:
            explicit_additions[fpid] = cand["sleeper_id"]

    ambiguous_rows = []
    for fpid, expected_name in ambiguous.items():
        fp = fp_by_fpid.get(fpid)
        if fp is None:
            raise RuntimeError(f"ambiguous-hold FPID missing: {fpid}")
        cand = exact_name_team_override_candidate(mod, fp, sleeper_by_name)
        ambiguous_rows.append({
            "fantasypros_id": fpid,
            "name": expected_name,
            "fp_position": fp["_pos"],
            "fp_team": fp["_team"],
            "phase3_classification":
                phase3_by_fpid[fpid]["classification"],
            "generic_override_candidate": cand
        })

    # Explicit arm hard gates.
    gates = {}

    gates["three_targets_have_exact_unique_name_team_candidate"] = (
        set(explicit_additions) == set(targets)
    )

    # Explicit target SIDs must be distinct.
    gates["explicit_target_sids_unique"] = (
        len(set(explicit_additions.values()))
        == len(explicit_additions)
    )

    # An explicit addition may already be authoritative for the same FPID;
    # it may not be authoritative for another FPID.
    collision_details = []
    for fpid, sid in explicit_additions.items():
        existing_fpids = prior_by_sid.get(sid, [])
        conflicting = [x for x in existing_fpids if x != fpid]
        if conflicting:
            collision_details.append({
                "fantasypros_id": fpid,
                "sleeper_id": sid,
                "conflicting_existing_fpids": conflicting
            })
    gates["no_existing_authoritative_sid_collision"] = not collision_details

    gates["explicit_arm_exactly_three_fpids"] = (
        set(explicit_additions) == set(targets)
        and len(explicit_additions) == 3
    )

    gates["jonah_elliss_remains_outside_explicit_arm"] = (
        "26157" not in explicit_additions
    )

    # The explicit arm is definitionally restricted to the frozen target
    # set; prove no unrelated FPID is present.
    gates["zero_unrelated_explicit_changes"] = (
        not (set(explicit_additions) - set(targets))
    )

    all_gates_pass = all(gates.values())
    decision = (
        "PASS_EXPLICIT_EVIDENCE_BACKED_POSITION_OVERRIDE_CANDIDATE"
        if all_gates_pass
        else "STOP_EXPLICIT_POSITION_OVERRIDE_CANDIDATE_FAILED_GATES"
    )

    generic_extra_vs_explicit = sorted(
        set(generic_additions) - set(explicit_additions)
    )

    phase2_holds = {
        str(r["fantasypros_id"]): r["disposition"]
        for r in phase2["rows"]
        if r["disposition"].startswith("HOLD_")
    }

    return {
        "schema_version": 1,
        "study_id": "identity-v2-phase4-position-conflict-policy",
        "status": "POLICY_AUDIT_COMPLETE",
        "decision": decision,
        "generated_at_utc":
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "research_only": True,
        "production_change_authorized": False,
        "promotion_authorized": False,
        "current_strict_position_incompatible_row_count": len(incompatible),
        "generic_policy": {
            "status": "DIAGNOSTIC_ONLY",
            "new_authoritative_candidate_count": len(generic_additions),
            "candidate_fpids": dict(sorted(generic_additions.items())),
            "extra_fpids_beyond_explicit_evidence_set": generic_extra_vs_explicit,
            "diagnostics": generic_diagnostics
        },
        "explicit_evidence_backed_policy": {
            "target_count": len(targets),
            "qualified_target_count": len(explicit_additions),
            "candidate_fpids": dict(sorted(explicit_additions.items())),
            "rows": explicit_rows,
            "collision_details": collision_details,
            "hard_gates": gates,
            "all_hard_gates_pass": all_gates_pass
        },
        "ambiguous_hold_policy": {
            "rows": ambiguous_rows,
            "remains_held": True
        },
        "phase2_hold_dispositions": phase2_holds,
        "next_step_rule": (
            "A PASS authorizes only a separate production-candidate shadow "
            "that applies the three explicit mappings, re-runs the unified "
            "resolver/regression suite, and proves zero unrelated changes. "
            "It does not authorize deployment."
        )
    }

def render(r):
    generic = r["generic_policy"]
    explicit = r["explicit_evidence_backed_policy"]

    lines = [
        "# Identity V2 Phase 4 — Position-Conflict Policy Audit",
        "",
        f"**Decision:** `{r['decision']}`",
        "",
        "**RESEARCH ONLY. No production mapping or resolver policy is changed.**",
        "",
        "## Why this phase exists",
        "",
        "The production resolver already preserves an existing authoritative "
        "FPID↔Sleeper-ID pair across later position changes. The unresolved "
        "question is how to handle a **brand-new** match when the two providers "
        "disagree on position.",
        "",
        "## Current strict-policy population",
        "",
        f"- Fresh rows failing only at position compatibility: "
        f"**{r['current_strict_position_incompatible_row_count']}**",
        "",
        "## P1 — Generic exact-name + exact-team override",
        "",
        "**Diagnostic only; cannot be promoted by this phase.**",
        "",
        f"- Would create new candidates: "
        f"**{generic['new_authoritative_candidate_count']}**",
        f"- Extra FPIDs beyond the evidence-backed explicit set: "
        f"**{len(generic['extra_fpids_beyond_explicit_evidence_set'])}**",
        ""
    ]

    if generic["extra_fpids_beyond_explicit_evidence_set"]:
        lines.append(
            "- Extra FPIDs: "
            + ", ".join(
                f"`{x}`"
                for x in generic["extra_fpids_beyond_explicit_evidence_set"]
            )
        )
        lines.append("")

    lines += [
        "## P2 — Evidence-backed explicit override",
        "",
        f"- Frozen targets: **{explicit['target_count']}**",
        f"- Qualified targets: **{explicit['qualified_target_count']}**",
        f"- All hard gates pass: **{explicit['all_hard_gates_pass']}**",
        "",
        "| Player | FPID | FP pos | Team | Phase 3 evidence | Candidate SID | Sleeper positions |",
        "|---|---|---|---|---|---|---|"
    ]

    for row in explicit["rows"]:
        cand = row["override_candidate"]
        positions = ",".join(cand["positions"]) or "—"
        lines.append(
            f"| {row['name']} | `{row['fantasypros_id']}` | "
            f"{row['fp_position']} | {row['fp_team']} | "
            f"`{row['phase3_classification']}` | "
            f"{cand['sleeper_id'] or '—'} | {positions} |"
        )

    lines += [
        "",
        "### Hard gates",
        ""
    ]
    for gate, passed in explicit["hard_gates"].items():
        lines.append(f"- `{gate}`: **{'PASS' if passed else 'FAIL'}**")

    lines += [
        "",
        "## Ambiguous taxonomy hold",
        ""
    ]
    for row in r["ambiguous_hold_policy"]["rows"]:
        cand = row["generic_override_candidate"]
        lines.append(
            f"- **{row['name']}** (`{row['fantasypros_id']}`): "
            f"{row['fp_position']} vs Sleeper candidate positions "
            f"{cand['positions'] or '—'}; Phase 3 = "
            f"`{row['phase3_classification']}`. Remains held."
        )

    lines += [
        "",
        "## Governance",
        "",
        "- The generic rule is diagnostic only.",
        "- The explicit candidate is limited to the three frozen evidence-backed FPIDs.",
        "- Jonah Elliss remains held because the official OLB label is hybrid/ambiguous under the frozen policy.",
        "- No resolver source file or production crosswalk is changed.",
        "- Even a PASS only permits a separate production-candidate shadow.",
        "",
        "## Next-step rule",
        "",
        r["next_step_rule"],
        ""
    ]
    return "\n".join(lines)

def write():
    r = build()
    OUTJSON.write_text(
        json.dumps(r, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )
    OUTMD.write_text(render(r).rstrip() + "\n", encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "study_id": "identity-v2-phase4-position-conflict-policy",
        "decision": r["decision"],
        "production_change_authorized": False,
        "promotion_authorized": False,
        "phase2_sha256": sha256(PHASE2),
        "phase3_sha256": sha256(PHASE3),
        "preregistration_sha256": sha256(PREREG),
        "production_crosswalk_sha256": sha256(PROD_CROSSWALK),
        "evaluator_sha256": sha256(SCRIPT),
        "output_json_sha256": sha256(OUTJSON),
        "output_md_sha256": sha256(OUTMD)
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )

    print(json.dumps({
        "decision": r["decision"],
        "strict_position_incompatible_rows":
            r["current_strict_position_incompatible_row_count"],
        "generic_candidate_count":
            r["generic_policy"]["new_authoritative_candidate_count"],
        "generic_extra_fpids":
            r["generic_policy"]["extra_fpids_beyond_explicit_evidence_set"],
        "explicit_candidate_fpids":
            r["explicit_evidence_backed_policy"]["candidate_fpids"],
        "explicit_all_gates_pass":
            r["explicit_evidence_backed_policy"]["all_hard_gates_pass"]
    }, indent=2))

def check():
    r = json.loads(OUTJSON.read_text(encoding="utf-8"))
    if r["production_change_authorized"] is not False:
        raise RuntimeError("production change illegally authorized")
    if r["promotion_authorized"] is not False:
        raise RuntimeError("promotion illegally authorized")

    explicit = r["explicit_evidence_backed_policy"]
    expected = {"26313", "27959", "28290"}

    if r["decision"] == "PASS_EXPLICIT_EVIDENCE_BACKED_POSITION_OVERRIDE_CANDIDATE":
        if set(explicit["candidate_fpids"]) != expected:
            raise RuntimeError(
                "PASS decision does not contain exactly the three frozen targets"
            )
        if not explicit["all_hard_gates_pass"]:
            raise RuntimeError("PASS decision with failed hard gate")

    if "26157" in explicit["candidate_fpids"]:
        raise RuntimeError("Jonah Elliss entered explicit candidate arm")

    print("Identity V2 Phase 4 checks PASS")

def selftest():
    p = json.loads(PREREG.read_text(encoding="utf-8"))
    assert set(p["frozen_explicit_target_fpids"]) == {
        "26313", "27959", "28290"
    }
    assert set(p["frozen_ambiguous_hold_fpids"]) == {"26157"}
    assert p["promotion_authorized"] is False
    print("Identity V2 Phase 4 self-test PASS")

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
    elif args.write:
        write()
    else:
        check()

if __name__ == "__main__":
    main()

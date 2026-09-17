#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
OUTDIR = SCRIPT.parent

PHASE1_PY = OUTDIR / "unified_fantasypros_sleeper_identity_v2.py"
PHASE2 = OUTDIR / "identity_v2_phase2_manual_adjudication.json"
EVIDENCE = OUTDIR / "identity_v2_phase3_external_evidence.json"
PREREG = OUTDIR / "identity_v2_phase3_preregistration.json"

OUTJSON = OUTDIR / "identity_v2_phase3_independent_corroboration.json"
OUTMD = OUTDIR / "identity_v2_phase3_independent_corroboration.md"
MANIFEST = OUTDIR / "identity_v2_phase3_manifest.json"

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_phase1():
    spec = importlib.util.spec_from_file_location("identity_v2_phase1", PHASE1_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Identity V2 Phase 1 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def current_sleeper_candidates(mod):
    totals = mod.read_json(mod.SLEEPER_TOTAL_PATH)
    raw = mod.read_json(mod.SLEEPER_RAW_PATH)
    teams = mod.read_json(mod.TEAM_REFRESH_PATH)
    by_sid, by_name = mod.build_sleeper_universe(totals, raw, teams)
    return by_sid, by_name

def canon_external(pos, prereg):
    if pos in prereg["hybrid_external_positions"]:
        return "HYBRID"
    return prereg["canonical_external_position_map"].get(pos)

def classify(phase2_row, evidence_row, sleeper_by_name, mod, prereg):
    name = mod.normalize_name(phase2_row["name"])
    candidates = list(sleeper_by_name.get(name, ()))
    sleeper_labels = sorted({
        label
        for c in candidates
        for label in (c.get("positions") or ())
    })

    ext_pos = evidence_row["official_position"]
    ext_canon = canon_external(ext_pos, prereg)
    fp_pos = phase2_row.get("fp_position")

    # Transactional evidence explains a team/source hold, but never
    # selects a Sleeper SID on its own.
    if evidence_row["evidence_type"] == "transaction":
        classification = "EXTERNAL_TRANSACTION_EXPLAINS_SOURCE_DRIFT"

    elif evidence_row["evidence_type"] == "status_ambiguity":
        classification = "EXTERNAL_STATUS_REMAINS_AMBIGUOUS"

    elif ext_canon == "HYBRID":
        classification = "OFFICIAL_POSITION_TAXONOMY_REMAINS_AMBIGUOUS"

    else:
        fp_match = ext_canon == fp_pos
        sleeper_match = ext_canon in sleeper_labels

        if fp_match and not sleeper_match:
            classification = "OFFICIAL_POSITION_SUPPORTS_FANTASYPROS_TAXONOMY"
        elif sleeper_match and not fp_match:
            classification = "OFFICIAL_POSITION_SUPPORTS_SLEEPER_TAXONOMY"
        elif fp_match and sleeper_match:
            classification = "OFFICIAL_POSITION_BOTH_PROVIDERS_COMPATIBLE"
        else:
            classification = "OFFICIAL_POSITION_TAXONOMY_REMAINS_AMBIGUOUS"

    return {
        "fantasypros_id": phase2_row["fantasypros_id"],
        "name": phase2_row["name"],
        "phase2_disposition": phase2_row["disposition"],
        "fp_position": fp_pos,
        "current_sleeper_position_labels": sleeper_labels,
        "official_position": ext_pos,
        "official_team_or_status": evidence_row["official_team_or_status"],
        "external_evidence_type": evidence_row["evidence_type"],
        "external_source_url": evidence_row["source_url"],
        "external_source_note": evidence_row["source_note"],
        "classification": classification,
        "production_mapping_authorized": False
    }

def build():
    phase2 = json.loads(PHASE2.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))

    if phase2["decision"] != "PASS_IDENTITY_V2_PHASE2_REVIEW_FREEZE_WITH_HOLDS":
        raise RuntimeError("Phase 2 is not the expected hold-bearing freeze")
    if phase2["held_row_count"] != prereg["expected_phase2_hold_count"]:
        raise RuntimeError("Phase 2 hold count drifted")
    if evidence["production_change_authorized"] is not False:
        raise RuntimeError("external evidence artifact illegally authorizes production")
    if prereg["production_change_authorized"] is not False:
        raise RuntimeError("Phase 3 preregistration illegally authorizes production")

    holds = {
        str(row["fantasypros_id"]): row
        for row in phase2["rows"]
        if row["disposition"].startswith("HOLD_")
    }
    ext = {
        str(row["fantasypros_id"]): row
        for row in evidence["rows"]
    }

    if set(holds) != set(ext):
        missing = sorted(set(holds) - set(ext))
        extra = sorted(set(ext) - set(holds))
        raise RuntimeError(
            f"external evidence scope mismatch; missing={missing}, extra={extra}"
        )

    name_mismatches = []
    for fpid in sorted(holds):
        phase2_name = str(holds[fpid].get("name") or "").strip()
        evidence_name = str(ext[fpid].get("name") or "").strip()
        if phase2_name != evidence_name:
            name_mismatches.append({
                "fantasypros_id": fpid,
                "phase2_name": phase2_name,
                "evidence_name": evidence_name
            })
    if name_mismatches:
        raise RuntimeError(
            "external evidence player-name mismatch: "
            + json.dumps(name_mismatches, sort_keys=True)
        )

    mod = load_phase1()
    _, sleeper_by_name = current_sleeper_candidates(mod)

    rows = [
        classify(holds[fpid], ext[fpid], sleeper_by_name, mod, prereg)
        for fpid in sorted(holds)
    ]

    counts = Counter(row["classification"] for row in rows)
    taxonomy_question_rows = [
        row for row in rows
        if row["classification"].startswith("OFFICIAL_POSITION_")
    ]
    source_drift_rows = [
        row for row in rows
        if row["classification"] == "EXTERNAL_TRANSACTION_EXPLAINS_SOURCE_DRIFT"
    ]
    ambiguous_rows = [
        row for row in rows
        if row["classification"] in {
            "EXTERNAL_STATUS_REMAINS_AMBIGUOUS",
            "OFFICIAL_POSITION_TAXONOMY_REMAINS_AMBIGUOUS"
        }
    ]

    return {
        "schema_version": 1,
        "study_id": "identity-v2-phase3-independent-corroboration",
        "status": "INDEPENDENT_CORROBORATION_FROZEN",
        "decision": "PASS_IDENTITY_V2_PHASE3_EXTERNAL_CORROBORATION_FREEZE",
        "generated_at_utc":
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "research_only": True,
        "production_change_authorized": False,
        "promotion_authorized": False,
        "phase2_hold_count": len(holds),
        "reviewed_hold_count": len(rows),
        "classification_counts": dict(sorted(counts.items())),
        "transactional_source_drift_count": len(source_drift_rows),
        "taxonomy_question_count": len(taxonomy_question_rows),
        "still_ambiguous_count": len(ambiguous_rows),
        "rows": rows,
        "next_step_rule": prereg["next_step_rule"]
    }

def render(r):
    lines = [
        "# Identity V2 Phase 3 — Independent Corroboration Freeze",
        "",
        f"**Decision:** `{r['decision']}`",
        "",
        "**RESEARCH ONLY. No production identity or position-policy change is authorized.**",
        "",
        "## Summary",
        "",
        f"- Phase 2 holds reviewed: **{r['reviewed_hold_count']} / {r['phase2_hold_count']}**",
        f"- Transactional/source-drift explanations: **{r['transactional_source_drift_count']}**",
        f"- Position-taxonomy questions: **{r['taxonomy_question_count']}**",
        f"- Still ambiguous after external evidence: **{r['still_ambiguous_count']}**",
        "",
        "## Classification counts",
        ""
    ]
    for key, value in r["classification_counts"].items():
        lines.append(f"- `{key}`: **{value}**")

    lines += [
        "",
        "## Held-row reconciliation",
        "",
        "| Player | Phase 2 hold | FP pos | Sleeper labels | Official pos | Phase 3 classification |",
        "|---|---|---|---|---|---|"
    ]
    for row in r["rows"]:
        sleeper = ",".join(row["current_sleeper_position_labels"]) or "—"
        lines.append(
            f"| {row['name']} | `{row['phase2_disposition']}` | "
            f"{row['fp_position']} | {sleeper} | {row['official_position']} | "
            f"`{row['classification']}` |"
        )

    lines += [
        "",
        "## Governance",
        "",
        "- Official transactions may explain stale/blank team state but cannot select a Sleeper SID by themselves.",
        "- Official position labels may diagnose provider taxonomy disagreement but cannot alter the frozen compatibility policy.",
        "- Hybrid labels such as OLB/EDGE remain taxonomy-policy questions.",
        "- No production identity mapping is approved by this phase.",
        "- `scripts/identity_crosswalk.json` remains unchanged.",
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
        "study_id": "identity-v2-phase3-independent-corroboration",
        "decision": r["decision"],
        "production_change_authorized": False,
        "promotion_authorized": False,
        "phase2_sha256": sha256(PHASE2),
        "external_evidence_sha256": sha256(EVIDENCE),
        "preregistration_sha256": sha256(PREREG),
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
        "classification_counts": r["classification_counts"],
        "transactional_source_drift_count": r["transactional_source_drift_count"],
        "taxonomy_question_count": r["taxonomy_question_count"],
        "still_ambiguous_count": r["still_ambiguous_count"]
    }, indent=2))

def check():
    r = json.loads(OUTJSON.read_text(encoding="utf-8"))
    if r["reviewed_hold_count"] != 11:
        raise RuntimeError("Phase 3 did not review exactly 11 frozen holds")
    if r["production_change_authorized"] is not False:
        raise RuntimeError("production change illegally authorized")
    if r["promotion_authorized"] is not False:
        raise RuntimeError("promotion illegally authorized")
    if any(row["production_mapping_authorized"] for row in r["rows"]):
        raise RuntimeError("a held row illegally authorizes production")
    if r["decision"] != "PASS_IDENTITY_V2_PHASE3_EXTERNAL_CORROBORATION_FREEZE":
        raise RuntimeError("unexpected Phase 3 decision")
    print("Identity V2 Phase 3 checks PASS")

def selftest():
    p = json.loads(PREREG.read_text(encoding="utf-8"))
    assert p["expected_phase2_hold_count"] == 11
    assert "OLB" in p["hybrid_external_positions"]
    print("Identity V2 Phase 3 self-test PASS")

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

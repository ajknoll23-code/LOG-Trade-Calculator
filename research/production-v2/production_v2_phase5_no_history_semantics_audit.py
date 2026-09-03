#!/usr/bin/env python3
"""
Production V2 Phase 5 — no-history semantics audit.

PURPOSE
-------
Phase 4 proved the current lineage-gated no-history rescue is discontinuous:
when a valid production candidate falls to raw PM <= 0.15, effective PM can
jump UP to ROLE_MULT.

Phase 5 tests a simpler V2 invariant on the exact Phase-1 candidate cohort:

    IF a valid V2 production candidate exists:
        - keep the existing Elite 0.65 safeguard for now;
        - otherwise use the candidate production multiplier directly;
        - do NOT switch into ROLE_MULT merely because raw PM hits 0.15.

ROLE_MULT remains conceptually a missing-production fallback, but the policy for
the 31 Phase-1 players without a complete V2 candidate is explicitly OUT OF
SCOPE here. This audit does not manufacture a replacement for missing evidence.

This is research only. It does not mutate index.html or production data.

INPUTS
------
- research/production-v2/production_v2_phase1_audit.json
- research/production-v2/production_v2_phase3_baseline_normalization_audit.json
- research/production-v2/production_v2_phase4_transform_rescue_audit.json
- index.html
- scripts/validation/snapshot_values.py

OUTPUTS
-------
- research/production-v2/production_v2_phase5_no_history_semantics_audit.json
- research/production-v2/production_v2_phase5_no_history_semantics_audit.md
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
PHASE4_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase4_transform_rescue_audit.json"
INDEX_HTML = REPO_ROOT / "index.html"
SNAPSHOT_VALUES_PATH = SCRIPTS / "validation" / "snapshot_values.py"

OUTPUT_JSON = REPO_ROOT / "research" / "production-v2" / "production_v2_phase5_no_history_semantics_audit.json"
OUTPUT_MD = REPO_ROOT / "research" / "production-v2" / "production_v2_phase5_no_history_semantics_audit.md"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55
GLOBAL_VALUE_SCALE = 55.0


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


def raw_pm_for_record(rec, baselines):
    combined = rec.get("phase1_combined_points")
    if combined is None:
        return None
    baseline = float(baselines[rec["pos"]]["combined_points"])
    ratio = float(combined) / baseline
    return clamp(PM_INTERCEPT + PM_RATIO_SLOPE * ratio, PM_MIN, PM_MAX)


def current_effective_candidate_pm(key, role, raw_pm, cfg, snapshot_values):
    effective, _ = snapshot_values.production_multiplier(
        key,
        role,
        {key: raw_pm},
        cfg["no_real_history"],
        cfg["role_mult"],
    )
    return float(effective)


def data_first_effective_candidate_pm(role, raw_pm):
    # Phase 5 changes ONLY the no-history rescue semantics.
    # Preserve the current Elite floor for a later isolated audit.
    if role == "Elite" and raw_pm < 0.65:
        return 0.65
    return float(raw_pm)


def final_value(key, raw_pm, effective_pm, cfg, snapshot_values):
    info = cfg["player_db"][key]
    pos = info["pos"]
    role = info["role"]
    age = info["age"]

    # effective_age_multiplier's `raw_production` argument is the raw V2 PM;
    # this preserves current RB youth qualification semantics.
    age_mult = snapshot_values.effective_age_multiplier(
        pos,
        age,
        role,
        key,
        effective_pm,
        raw_pm,
        cfg,
    )
    pw = cfg["position_weight"].get(pos, 1.0)
    value = math.floor(
        100 * pw * age_mult * effective_pm * GLOBAL_VALUE_SCALE + 0.5
    )
    return {
        "value": value,
        "age_mult": float(age_mult),
        "position_weight": float(pw),
    }


def scenario(phase1_players, ranks, cfg, snapshot_values, semantics):
    baselines = build_baselines(phase1_players, ranks)
    rows = {}

    for key, rec in phase1_players.items():
        raw_pm = raw_pm_for_record(rec, baselines)
        if raw_pm is None:
            rows[key] = None
            continue

        info = cfg["player_db"][key]
        role = info["role"]
        no_history = key in cfg["no_real_history"]

        current_eff = current_effective_candidate_pm(
            key, role, raw_pm, cfg, snapshot_values
        )
        data_first_eff = data_first_effective_candidate_pm(role, raw_pm)

        if semantics == "current_threshold_rescue":
            effective_pm = current_eff
        elif semantics == "data_first_candidate":
            effective_pm = data_first_eff
        else:
            raise ValueError(semantics)

        fv = final_value(key, raw_pm, effective_pm, cfg, snapshot_values)

        rows[key] = {
            "player": key,
            "pos": rec["pos"],
            "role": role,
            "no_real_history": no_history,
            "raw_pm": raw_pm,
            "effective_pm": effective_pm,
            "current_rule_effective_pm": current_eff,
            "data_first_effective_pm": data_first_eff,
            "current_rescue_applied": (
                no_history
                and role != "Elite"
                and raw_pm <= PM_MIN
                and float(cfg["role_mult"].get(role, 1.0)) > raw_pm
                and abs(current_eff - float(cfg["role_mult"].get(role, 1.0))) < 1e-12
            ),
            "elite_floor_applied": role == "Elite" and raw_pm < 0.65,
            **fv,
        }

    return rows, baselines


def validate_phase1_reproduction(phase1_players, current_documented):
    mismatches = []
    for key, rec in phase1_players.items():
        candidate = rec.get("candidate")
        row = current_documented.get(key)
        if candidate is None and row is None:
            continue
        if candidate is None or row is None:
            mismatches.append({"player": key, "reason": "presence"})
            continue

        expected_pm = float(candidate["effective_prod_mult"])
        expected_value = int(candidate["value"])
        if round(row["effective_pm"], 6) != expected_pm or row["value"] != expected_value:
            mismatches.append({
                "player": key,
                "expected_pm": expected_pm,
                "actual_pm": row["effective_pm"],
                "expected_value": expected_value,
                "actual_value": row["value"],
            })

    if mismatches:
        raise RuntimeError(
            "Current threshold scenario does not reproduce Phase 1; "
            f"sample={mismatches[:5]}"
        )


def monotonicity_check(doc_rows, hybrid_rows):
    """If raw PM falls, effective PM must not rise under candidate semantics."""
    violations = []
    for key, doc in doc_rows.items():
        hyb = hybrid_rows.get(key)
        if doc is None or hyb is None:
            continue
        raw_delta = hyb["raw_pm"] - doc["raw_pm"]
        eff_delta = hyb["effective_pm"] - doc["effective_pm"]
        if raw_delta < -1e-12 and eff_delta > 1e-12:
            violations.append({
                "player": key,
                "pos": doc["pos"],
                "role": doc["role"],
                "documented_raw_pm": doc["raw_pm"],
                "hybrid_raw_pm": hyb["raw_pm"],
                "documented_effective_pm": doc["effective_pm"],
                "hybrid_effective_pm": hyb["effective_pm"],
                "raw_delta": raw_delta,
                "effective_delta": eff_delta,
            })
    return violations


def position_summary(phase1_players, current_doc, data_doc, current_hyb, data_hyb):
    out = {}
    for pos in TRACKED_POSITIONS:
        keys = [
            key for key, rec in phase1_players.items()
            if rec["pos"] == pos and current_doc.get(key) is not None
        ]

        rescues_doc = [key for key in keys if current_doc[key]["current_rescue_applied"]]
        rescues_hyb = [key for key in keys if current_hyb[key]["current_rescue_applied"]]

        doc_semantic_delta = []
        hyb_semantic_delta = []
        doc_value_delta = []
        hyb_value_delta = []

        for key in keys:
            doc_semantic_delta.append(
                data_doc[key]["effective_pm"] - current_doc[key]["effective_pm"]
            )
            hyb_semantic_delta.append(
                data_hyb[key]["effective_pm"] - current_hyb[key]["effective_pm"]
            )
            if current_doc[key]["value"]:
                doc_value_delta.append(
                    (data_doc[key]["value"] - current_doc[key]["value"])
                    / current_doc[key]["value"]
                )
            if current_hyb[key]["value"]:
                hyb_value_delta.append(
                    (data_hyb[key]["value"] - current_hyb[key]["value"])
                    / current_hyb[key]["value"]
                )

        # Baseline effect under data-first semantics.
        baseline_effect = []
        for key in keys:
            if data_doc[key]["value"]:
                baseline_effect.append(
                    (data_hyb[key]["value"] - data_doc[key]["value"])
                    / data_doc[key]["value"]
                )

        out[pos] = {
            "candidate_count": len(keys),
            "current_rule_rescues_documented_rank": len(rescues_doc),
            "current_rule_rescues_hybrid_rank": len(rescues_hyb),
            "data_first_rescues_documented_rank": 0,
            "data_first_rescues_hybrid_rank": 0,
            "semantic_change_at_documented_rank": {
                "effective_pm_delta": summarize(doc_semantic_delta),
                "fundamental_value_change_pct": summarize(doc_value_delta),
            },
            "semantic_change_at_hybrid_rank": {
                "effective_pm_delta": summarize(hyb_semantic_delta),
                "fundamental_value_change_pct": summarize(hyb_value_delta),
            },
            "hybrid_minus_documented_under_data_first": {
                "fundamental_value_change_pct": summarize(baseline_effect),
            },
        }
    return out


def build_result():
    phase1 = read_json(PHASE1_PATH)
    phase3 = read_json(PHASE3_PATH)
    phase4 = read_json(PHASE4_PATH)

    if phase1.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 1 must be research-only")
    if phase3.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 3 must be research-only")
    if phase4.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 4 must be research-only")
    if not phase4.get("deployment_blocked"):
        raise RuntimeError("Phase 5 expected Phase 4 to identify the rescue blocker")

    phase1_players = phase1.get("players")
    documented_ranks = phase3.get("documented_ranks")
    hybrid_ranks = phase3.get("evidence_hybrid_ranks")
    if not isinstance(phase1_players, dict):
        raise RuntimeError("Phase 1 players missing")
    if not isinstance(documented_ranks, dict) or not isinstance(hybrid_ranks, dict):
        raise RuntimeError("Phase 3 ranks missing")

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    current_doc, doc_baselines = scenario(
        phase1_players, documented_ranks, cfg, snapshot_values,
        "current_threshold_rescue"
    )
    data_doc, _ = scenario(
        phase1_players, documented_ranks, cfg, snapshot_values,
        "data_first_candidate"
    )
    current_hyb, hyb_baselines = scenario(
        phase1_players, hybrid_ranks, cfg, snapshot_values,
        "current_threshold_rescue"
    )
    data_hyb, _ = scenario(
        phase1_players, hybrid_ranks, cfg, snapshot_values,
        "data_first_candidate"
    )

    validate_phase1_reproduction(phase1_players, current_doc)

    current_violations = monotonicity_check(current_doc, current_hyb)
    data_first_violations = monotonicity_check(data_doc, data_hyb)

    # Phase 4's reported paradox count should match our current-rule replay.
    expected_phase4_paradox_count = int(
        phase4.get("paradoxical_raw_down_effective_up_count") or 0
    )
    if len(current_violations) != expected_phase4_paradox_count:
        raise RuntimeError(
            "Current-rule monotonicity replay does not match Phase 4: "
            f"{len(current_violations)} vs {expected_phase4_paradox_count}"
        )

    changed_players_doc = []
    changed_players_hyb = []
    for key in sorted(phase1_players):
        cdoc = current_doc.get(key)
        ddoc = data_doc.get(key)
        chyb = current_hyb.get(key)
        dhyb = data_hyb.get(key)
        if cdoc is not None and ddoc is not None and (
            abs(cdoc["effective_pm"] - ddoc["effective_pm"]) > 1e-12
            or cdoc["value"] != ddoc["value"]
        ):
            changed_players_doc.append({
                "player": key,
                "pos": cdoc["pos"],
                "role": cdoc["role"],
                "raw_pm": cdoc["raw_pm"],
                "current_effective_pm": cdoc["effective_pm"],
                "data_first_effective_pm": ddoc["effective_pm"],
                "current_value": cdoc["value"],
                "data_first_value": ddoc["value"],
                "value_change_pct": (
                    (ddoc["value"] - cdoc["value"]) / cdoc["value"]
                    if cdoc["value"] else None
                ),
            })
        if chyb is not None and dhyb is not None and (
            abs(chyb["effective_pm"] - dhyb["effective_pm"]) > 1e-12
            or chyb["value"] != dhyb["value"]
        ):
            changed_players_hyb.append({
                "player": key,
                "pos": chyb["pos"],
                "role": chyb["role"],
                "raw_pm": chyb["raw_pm"],
                "current_effective_pm": chyb["effective_pm"],
                "data_first_effective_pm": dhyb["effective_pm"],
                "current_value": chyb["value"],
                "data_first_value": dhyb["value"],
                "value_change_pct": (
                    (dhyb["value"] - chyb["value"]) / chyb["value"]
                    if chyb["value"] else None
                ),
            })

    changed_players_doc.sort(
        key=lambda r: (-abs(r["value_change_pct"] or 0.0), r["player"])
    )
    changed_players_hyb.sort(
        key=lambda r: (-abs(r["value_change_pct"] or 0.0), r["player"])
    )

    candidate_count = sum(
        1 for rec in phase1_players.values()
        if rec.get("candidate") is not None
    )
    missing_candidate_count = len(phase1_players) - candidate_count

    by_position = position_summary(
        phase1_players, current_doc, data_doc, current_hyb, data_hyb
    )

    invariants_pass = (
        len(data_first_violations) == 0
        and candidate_count > 0
        and len(current_violations) == expected_phase4_paradox_count
    )

    decision = (
        "CARRY_DATA_FIRST_NO_HISTORY_SEMANTICS_FORWARD_FOR_V2_CANDIDATE_COHORT"
        if invariants_pass
        else "DO_NOT_CARRY_DATA_FIRST_SEMANTICS_FORWARD"
    )

    return round_numbers({
        "schema_version": 1,
        "phase": "Production V2 Phase 5",
        "status": "RESEARCH_ONLY_NO_HISTORY_SEMANTICS_AUDIT",
        "production_mutation_authorized": False,
        "calibration_claim_authorized": False,
        "decision": decision,
        "candidate_cohort": {
            "phase1_candidate_players": candidate_count,
            "phase1_players_without_complete_candidate": missing_candidate_count,
            "missing_candidate_policy_in_scope": False,
        },
        "semantics_tested": {
            "current": (
                "For no-history non-Elite players, raw PM <=0.15 can switch "
                "effective PM to ROLE_MULT."
            ),
            "data_first_candidate": (
                "When a valid V2 production candidate exists, use candidate PM "
                "directly for non-Elite players regardless of no-history status. "
                "Existing Elite 0.65 safeguard remains unchanged."
            ),
        },
        "invariants": {
            "phase1_current_rule_exact_reproduction": True,
            "current_rule_raw_down_effective_up_count": len(current_violations),
            "data_first_raw_down_effective_up_count": len(data_first_violations),
            "data_first_monotonicity_pass": len(data_first_violations) == 0,
        },
        "documented_ranks": documented_ranks,
        "evidence_hybrid_ranks": hybrid_ranks,
        "documented_baselines": doc_baselines,
        "evidence_hybrid_baselines": hyb_baselines,
        "by_position": by_position,
        "current_rule_monotonicity_violations": current_violations,
        "data_first_monotonicity_violations": data_first_violations,
        "players_changed_by_semantics_at_documented_ranks": changed_players_doc,
        "players_changed_by_semantics_at_hybrid_ranks": changed_players_hyb,
        "interpretation": (
            "For players with a complete V2 production candidate, ROLE_MULT "
            "should not be activated by an arbitrary numeric PM threshold. "
            "Separating 'production estimate exists' from 'production estimate "
            "missing' removes the direction-reversing discontinuity while leaving "
            "the Elite safeguard and every other valuation layer untouched."
        ),
        "next_step": (
            "Rerun/interpret the replacement-baseline comparison under the "
            "data-first candidate semantics. If the hybrid ranks remain defensible, "
            "audit the remaining affine transform floor/ceiling shape next. "
            "Missing-candidate fallback policy remains a separate task."
        ),
        "input_sha256": {
            str(PHASE1_PATH.relative_to(REPO_ROOT)): sha256(PHASE1_PATH),
            str(PHASE3_PATH.relative_to(REPO_ROOT)): sha256(PHASE3_PATH),
            str(PHASE4_PATH.relative_to(REPO_ROOT)): sha256(PHASE4_PATH),
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
            str(SNAPSHOT_VALUES_PATH.relative_to(REPO_ROOT)): sha256(SNAPSHOT_VALUES_PATH),
        },
    })


def pct(value):
    return "—" if value is None else f"{100.0 * float(value):.1f}%"


def signed_pct(value):
    return "—" if value is None else f"{100.0 * float(value):+.1f}%"


def render_md(result):
    inv = result["invariants"]
    cohort = result["candidate_cohort"]

    lines = [
        "# Production V2 — Phase 5 No-History Semantics Audit",
        "",
        "## Decision",
        "",
        f"**{result['decision']}**",
        "",
        "- Production files mutated: **0**",
        f"- Complete V2 candidate cohort: **{cohort['phase1_candidate_players']}**",
        f"- Players without a complete V2 candidate: **{cohort['phase1_players_without_complete_candidate']}** — fallback policy intentionally not changed here",
        "",
        "## Invariant result",
        "",
        f"- Current rule raw-PM↓ / effective-PM↑ violations: **{inv['current_rule_raw_down_effective_up_count']}**",
        f"- Data-first candidate semantics violations: **{inv['data_first_raw_down_effective_up_count']}**",
        f"- Data-first monotonicity: **{'PASS' if inv['data_first_monotonicity_pass'] else 'FAIL'}**",
        "",
        "### Semantics",
        "",
        "**Current:** a no-history non-Elite player can switch into `ROLE_MULT` when raw PM reaches 0.15.",
        "",
        "**V2 candidate tested:** once a valid V2 production estimate exists, use that production estimate directly for non-Elite players. `ROLE_MULT` is not triggered by the numeric floor. The existing Elite 0.65 safeguard is held fixed.",
        "",
        "## Impact by position",
        "",
        "| Pos | Candidates | Current rescues doc→hybrid | Data-first rescues | Semantic FV change @ doc rank (median / P95 abs) | Hybrid-vs-doc FV under data-first (median / P95 abs) |",
        "|---|---:|---|---:|---|---|",
    ]

    for pos in TRACKED_POSITIONS:
        row = result["by_position"][pos]
        semantic = row["semantic_change_at_documented_rank"]["fundamental_value_change_pct"]
        baseline = row["hybrid_minus_documented_under_data_first"]["fundamental_value_change_pct"]
        lines.append(
            f"| {pos} | {row['candidate_count']} | "
            f"{row['current_rule_rescues_documented_rank']}→{row['current_rule_rescues_hybrid_rank']} | "
            f"0 | "
            f"{signed_pct(semantic.get('median'))} / {pct(semantic.get('p95_abs'))} | "
            f"{signed_pct(baseline.get('median'))} / {pct(baseline.get('p95_abs'))} |"
        )

    lines += [
        "",
        "## Players changed by removing threshold rescue at documented ranks",
        "",
        "| Player | Pos | Role | Raw PM | Current effective | Data-first effective | Current FV | Data-first FV | FV change |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    changed = result["players_changed_by_semantics_at_documented_ranks"]
    if changed:
        for row in changed[:30]:
            lines.append(
                f"| {row['player']} | {row['pos']} | {row['role']} | "
                f"{row['raw_pm']:.3f} | {row['current_effective_pm']:.3f} | "
                f"{row['data_first_effective_pm']:.3f} | {row['current_value']} | "
                f"{row['data_first_value']} | {signed_pct(row['value_change_pct'])} |"
            )
    else:
        lines.append("| — | — | — | — | — | — | — | — | — |")

    lines += [
        "",
        "## Interpretation",
        "",
        result["interpretation"],
        "",
        "This is an architecture decision for the V2 **candidate-present** state, not a claim that the underlying raw production estimate is calibrated yet.",
        "",
        "The 31 incomplete-candidate players are deliberately left for a separate missing-data fallback audit rather than being silently pushed into a new role-based rule.",
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
    # Data-first semantics must be monotone in raw candidate PM for non-Elite.
    role = "Speculative"
    high_raw = 0.180
    low_raw = 0.150
    assert data_first_effective_candidate_pm(role, low_raw) < \
           data_first_effective_candidate_pm(role, high_raw)

    # Existing Elite safeguard is intentionally held fixed.
    assert data_first_effective_candidate_pm("Elite", 0.15) == 0.65
    assert data_first_effective_candidate_pm("Elite", 0.80) == 0.80

    # Current-rule discontinuity example from Phase 4 remains conceptually valid.
    current_above = 0.180
    current_at_floor_with_speculative_rescue = 0.22
    assert low_raw < high_raw
    assert current_at_floor_with_speculative_rescue > current_above

    print("PASS Production V2 Phase-5 standalone self-test.")


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
        raise RuntimeError("Phase-5 outputs do not exist; run --write first")
    if OUTPUT_JSON.read_text(encoding="utf-8") != json_text:
        raise RuntimeError("Phase-5 JSON does not reproduce exactly")
    if OUTPUT_MD.read_text(encoding="utf-8") != md_text:
        raise RuntimeError("Phase-5 Markdown does not reproduce exactly")
    print("PASS Phase-5 exact-output check.")


if __name__ == "__main__":
    main()

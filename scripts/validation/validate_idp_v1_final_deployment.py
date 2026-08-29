#!/usr/bin/env python3
"""Validate the deployed IDP V1 production bake against the true pre-V1 live table.

This is the post-deployment counterpart to prepare_idp_v1_bake.py.
It never edits index.html. It verifies that the deployed PROD_MULT_DATA table is
exactly the approved model-delta transport candidate (including exact holds),
then measures the true user-visible old->new Trade Desk value/rank movement
using the immutable pre-V1 baseline.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import snapshot_values

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
INDEX = REPO_ROOT / "index.html"
BASELINE = SCRIPT_DIR / "prod_mult_pre_v1_baseline.json"
CANDIDATE = SCRIPT_DIR / "idp_v1_model_delta_transport_candidate.json"
PATCH = SCRIPT_DIR / "idp_v1_prod_mult_patch.json"
JSON_OUT = SCRIPT_DIR / "idp_v1_final_deployment_validation.json"
REPORT = SCRIPT_DIR / "idp_v1_final_deployment_validation.md"
IDP_POSITIONS = ("LB", "DL", "DB")
ANCHORS = (
    "bradley chubb", "aidan hutchinson", "myles garrett", "fred warner",
    "roquan smith", "ej speed", "isaiah mcduffie", "christian izien",
)


def percentile(values, q):
    vals = sorted(values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    x = (len(vals) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    if lo == hi:
        return vals[lo]
    return vals[lo] + (vals[hi] - vals[lo]) * (x - lo)


def summary(values):
    vals = [v for v in values if v is not None and math.isfinite(v)]
    if not vals:
        return {"n": 0, "median": None, "p90": None, "p95": None, "min": None, "max": None}
    return {
        "n": len(vals),
        "median": statistics.median(vals),
        "p90": percentile(vals, 0.90),
        "p95": percentile(vals, 0.95),
        "min": min(vals),
        "max": max(vals),
    }


def rank_map(values):
    by_pos = defaultdict(list)
    for key, row in values.items():
        if row["pos"] in IDP_POSITIONS:
            by_pos[row["pos"]].append((row["value"], key))
    ranks = {}
    for pos, arr in by_pos.items():
        arr.sort(key=lambda x: (-x[0], x[1]))
        for i, (_, key) in enumerate(arr, 1):
            ranks[key] = i
    return ranks


def fmt_value(v):
    s = f"{float(v):.4f}".rstrip("0").rstrip(".")
    return float(s if "." in s else s + ".0")


def validate_deployment():
    cfg = snapshot_values.load_from_html(INDEX)
    baseline_doc = json.load(open(BASELINE, encoding="utf-8"))
    baseline = {k: float(v) for k, v in baseline_doc["values"].items()}
    candidate = json.load(open(CANDIDATE, encoding="utf-8"))
    patch = json.load(open(PATCH, encoding="utf-8"))
    current = {k: float(v) for k, v in cfg["prod_mult"].items()}

    # Exact deployed-table integrity.
    if set(current) != set(baseline):
        missing = sorted(set(baseline) - set(current))
        extra = sorted(set(current) - set(baseline))
        raise AssertionError(f"PROD_MULT key set changed across V1 deployment; missing={missing[:10]} extra={extra[:10]}")

    patch_by_key = {e["key"]: e for e in patch["entries"]}
    actual_changed = {k for k in baseline if abs(current[k] - baseline[k]) > 1e-12}
    expected_changed = set(patch_by_key)
    if actual_changed != expected_changed:
        missing = sorted(expected_changed - actual_changed)
        unexpected = sorted(actual_changed - expected_changed)
        raise AssertionError(f"deployed changed-key set != approved patch; missing={missing[:10]} unexpected={unexpected[:10]}")

    for key, row in candidate["players"].items():
        if key not in current:
            raise AssertionError(f"candidate key missing from deployed PROD_MULT: {key}")
        expected = fmt_value(row["candidate_prod_mult"])
        if abs(current[key] - expected) > 1e-12:
            raise AssertionError(f"deployed candidate mismatch {key}: expected {expected}, got {current[key]}")

    for key, e in patch_by_key.items():
        if abs(float(e["old"]) - baseline[key]) > 1e-12:
            raise AssertionError(f"patch old value no longer matches immutable baseline: {key}")
        if abs(fmt_value(e["new"]) - current[key]) > 1e-12:
            raise AssertionError(f"patch new value no longer matches deployed value: {key}")

    # Reconstruct the exact old live valuation by swapping only PROD_MULT back
    # to the immutable baseline; every other current valuation constant remains
    # identical, which is exactly the release attribution we want.
    old_cfg = dict(cfg)
    old_cfg["prod_mult"] = dict(current)
    old_cfg["prod_mult"].update(baseline)
    old_values = snapshot_values.compute_all_values(old_cfg)
    new_values = snapshot_values.compute_all_values(cfg)
    old_ranks, new_ranks = rank_map(old_values), rank_map(new_values)

    # Non-IDP final values must be completely unchanged by this deployment.
    non_idp_diffs = []
    for key, old in old_values.items():
        if old["pos"] not in IDP_POSITIONS and new_values[key]["value"] != old["value"]:
            non_idp_diffs.append((key, old["value"], new_values[key]["value"]))
    if non_idp_diffs:
        raise AssertionError(f"non-IDP final values changed: {non_idp_diffs[:10]}")

    rows = []
    final_changes_by_pos = defaultdict(list)
    raw_changes_by_pos = defaultdict(list)
    for key, old in old_values.items():
        if old["pos"] not in IDP_POSITIONS:
            continue
        new = new_values[key]
        pct = (new["value"] / old["value"] - 1) * 100 if old["value"] else None
        raw_old = baseline.get(key)
        raw_new = current.get(key)
        raw_pct = ((raw_new / raw_old - 1) * 100) if raw_old and raw_new is not None else None
        cand = candidate["players"].get(key, {})
        row = {
            "key": key,
            "pos": old["pos"],
            "old_value": old["value"],
            "new_value": new["value"],
            "value_pct_change": pct,
            "old_rank": old_ranks.get(key),
            "new_rank": new_ranks.get(key),
            "rank_change": (new_ranks[key] - old_ranks[key]) if key in old_ranks and key in new_ranks else None,
            "old_effective_prod_mult": old["prod_mult"],
            "new_effective_prod_mult": new["prod_mult"],
            "old_raw_prod_mult": raw_old,
            "new_raw_prod_mult": raw_new,
            "raw_prod_mult_pct_change": raw_pct,
            "source_cohort": cand.get("v1_source_cohort"),
            "update_status": cand.get("update_status"),
            "legacy_model_position": cand.get("legacy_model_position"),
            "current_valuation_position": cand.get("current_valuation_position"),
        }
        rows.append(row)
        final_changes_by_pos[old["pos"]].append(pct)
        if raw_pct is not None:
            raw_changes_by_pos[old["pos"]].append(raw_pct)

    # Rank stability.
    rank_stability = {}
    for pos in IDP_POSITIONS:
        rel = [r for r in rows if r["pos"] == pos and (r["old_rank"] <= 36 or r["new_rank"] <= 36)]
        rank_stability[pos] = {
            "top24_movers_ge5": sum(1 for r in rel if (r["old_rank"] <= 24 or r["new_rank"] <= 24) and abs(r["rank_change"]) >= 5),
            "top36_movers_ge5": sum(1 for r in rel if abs(r["rank_change"]) >= 5),
            "max_abs_rank_move_top36": max([abs(r["rank_change"]) for r in rel], default=0),
        }

    # Source-cohort behavior on candidate keys, measured in raw prod_mult and
    # final Trade Desk values where the player exists in PLAYER_DB.
    by_cohort_raw = defaultdict(list)
    by_cohort_final = defaultdict(list)
    for key, cand in candidate["players"].items():
        cohort = cand["v1_source_cohort"]
        old_raw, new_raw = baseline[key], current[key]
        by_cohort_raw[cohort].append((new_raw / old_raw - 1) * 100 if old_raw else None)
        match = next((r for r in rows if r["key"] == key), None)
        if match:
            by_cohort_final[cohort].append(match["value_pct_change"])

    clamp = {
        "pre_v1_raw_candidate_floor_0_15": sum(1 for k in candidate["players"] if abs(baseline[k] - 0.15) < 1e-12),
        "pre_v1_raw_candidate_ceiling_1_55": sum(1 for k in candidate["players"] if abs(baseline[k] - 1.55) < 1e-12),
        "deployed_raw_candidate_floor_0_15": sum(1 for k in candidate["players"] if abs(current[k] - 0.15) < 1e-12),
        "deployed_raw_candidate_ceiling_1_55": sum(1 for k in candidate["players"] if abs(current[k] - 1.55) < 1e-12),
    }

    row_map = {r["key"]: r for r in rows}
    anchor_rows = {}
    for key in ANCHORS:
        cand = candidate["players"].get(key)
        if not cand:
            anchor_rows[key] = None
            continue
        final_row = row_map.get(key)
        anchor_rows[key] = {
            "key": key,
            "pos": final_row["pos"] if final_row else cand.get("current_valuation_position"),
            "legacy_model_position": cand.get("legacy_model_position"),
            "current_valuation_position": cand.get("current_valuation_position"),
            "old_raw_prod_mult": baseline.get(key),
            "new_raw_prod_mult": current.get(key),
            "raw_prod_mult_pct_change": ((current[key] / baseline[key] - 1) * 100) if baseline.get(key) else None,
            "source_cohort": cand.get("v1_source_cohort"),
            "update_status": cand.get("update_status"),
            "old_value": final_row.get("old_value") if final_row else None,
            "new_value": final_row.get("new_value") if final_row else None,
            "value_pct_change": final_row.get("value_pct_change") if final_row else None,
            "rank_change": final_row.get("rank_change") if final_row else None,
        }

    result = {
        "status": "PASS",
        "deployment_method": candidate["method"],
        "pre_v1_prod_mult_entry_count": len(baseline),
        "deployed_prod_mult_entry_count": len(current),
        "approved_changed_entry_count": len(expected_changed),
        "actual_changed_entry_count": len(actual_changed),
        "candidate_player_count": len(candidate["players"]),
        "exact_hold_candidate_count": len(candidate["players"]) - len(expected_changed),
        "non_idp_final_value_changes": len(non_idp_diffs),
        "internal_old_model_baseline_by_position": candidate["old_model_baseline_by_position"],
        "internal_new_model_baseline_by_position": candidate["new_model_baseline_by_position"],
        "internal_baseline_pct_change": {
            p: (candidate["new_model_baseline_by_position"][p] / candidate["old_model_baseline_by_position"][p] - 1) * 100
            for p in IDP_POSITIONS
        },
        "raw_prod_mult_change_by_current_position": {p: summary(raw_changes_by_pos[p]) for p in IDP_POSITIONS},
        "final_value_change_by_position": {p: summary(final_changes_by_pos[p]) for p in IDP_POSITIONS},
        "rank_stability": rank_stability,
        "source_cohort_counts": Counter(r["v1_source_cohort"] for r in candidate["players"].values()),
        "update_status_counts": Counter(r["update_status"] for r in candidate["players"].values()),
        "source_cohort_raw_prod_mult_change": {k: summary(v) for k, v in sorted(by_cohort_raw.items())},
        "source_cohort_final_value_change": {k: summary(v) for k, v in sorted(by_cohort_final.items())},
        "clamp_occupancy": clamp,
        "anchors": anchor_rows,
        "largest_final_value_movers": sorted(rows, key=lambda r: abs(r["value_pct_change"] or 0), reverse=True)[:30],
        "largest_raw_prod_mult_movers": sorted([r for r in rows if r["raw_prod_mult_pct_change"] is not None], key=lambda r: abs(r["raw_prod_mult_pct_change"]), reverse=True)[:30],
        "position_lineage_mismatch_count": sum(1 for r in candidate["players"].values() if r.get("legacy_model_position") != r.get("current_valuation_position")),
    }
    # Counter is JSON serializable only after conversion.
    result["source_cohort_counts"] = dict(result["source_cohort_counts"])
    result["update_status_counts"] = dict(result["update_status_counts"])
    return result


def _fmt_pct(v):
    return "n/a" if v is None else f"{v:+.1f}%"


def build_report(result):
    lines = [
        "# IDP V1 Final Production Deployment Validation",
        "",
        "## Verdict",
        "",
        "**PASS — the live `index.html` PROD_MULT table exactly matches the approved model-delta transport deployment.**",
        "",
        f"- Deployment method: `{result['deployment_method']}`",
        f"- Immutable pre-V1 PROD_MULT entries: **{result['pre_v1_prod_mult_entry_count']}**",
        f"- Candidate IDP keys: **{result['candidate_player_count']}**",
        f"- Approved/deployed raw PROD_MULT changes: **{result['actual_changed_entry_count']}**",
        f"- Exact candidate holds: **{result['exact_hold_candidate_count']}**",
        f"- Floor-rescue discontinuity guards: **{result['update_status_counts'].get('exact_hold_floor_rescue_discontinuity_guard', 0)}**",
        f"- Non-IDP final-value changes: **{result['non_idp_final_value_changes']}**",
        f"- Legacy/current position mismatches intentionally isolated: **{result['position_lineage_mismatch_count']}**",
        "",
        "## Internal V1 replacement-baseline movement",
        "",
    ]
    for pos in IDP_POSITIONS:
        lines.append(f"- {pos}: **{result['internal_baseline_pct_change'][pos]:+.1f}%**")

    lines += ["", "## True live old → deployed raw PROD_MULT movement", "", "| Pos | N | Median | P90 | P95 | Min | Max |", "|---|---:|---:|---:|---:|---:|---:|"]
    for pos in IDP_POSITIONS:
        s = result["raw_prod_mult_change_by_current_position"][pos]
        lines.append(f"| {pos} | {s['n']} | {_fmt_pct(s['median'])} | {_fmt_pct(s['p90'])} | {_fmt_pct(s['p95'])} | {_fmt_pct(s['min'])} | {_fmt_pct(s['max'])} |")

    lines += ["", "## True live old → deployed final Trade Desk value movement", "", "| Pos | N | Median | P90 | P95 | Min | Max |", "|---|---:|---:|---:|---:|---:|---:|"]
    for pos in IDP_POSITIONS:
        s = result["final_value_change_by_position"][pos]
        lines.append(f"| {pos} | {s['n']} | {_fmt_pct(s['median'])} | {_fmt_pct(s['p90'])} | {_fmt_pct(s['p95'])} | {_fmt_pct(s['min'])} | {_fmt_pct(s['max'])} |")

    lines += ["", "## Rank stability", "", "| Pos | Top-24 movers >=5 | Top-36 movers >=5 | Max abs top-36 move |", "|---|---:|---:|---:|"]
    for pos in IDP_POSITIONS:
        s = result["rank_stability"][pos]
        lines.append(f"| {pos} | {s['top24_movers_ge5']} | {s['top36_movers_ge5']} | {s['max_abs_rank_move_top36']} |")

    lines += ["", "## Source-cohort behavior", "", "| Cohort | N candidate | Raw PROD_MULT median | Raw P95 | Final-value median* | Final P95* |", "|---|---:|---:|---:|---:|---:|"]
    for cohort, n in sorted(result["source_cohort_counts"].items()):
        raw = result["source_cohort_raw_prod_mult_change"][cohort]
        fin = result["source_cohort_final_value_change"].get(cohort, {"median": None, "p95": None})
        lines.append(f"| {cohort} | {n} | {_fmt_pct(raw['median'])} | {_fmt_pct(raw['p95'])} | {_fmt_pct(fin['median'])} | {_fmt_pct(fin['p95'])} |")
    lines.append("")
    lines.append("* Final-value cohort summaries include only candidate keys that are present in current `PLAYER_DB`.")

    c = result["clamp_occupancy"]
    lines += [
        "", "## Raw clamp occupancy among the 404 candidate IDPs", "",
        f"- Pre-V1 floor 0.15: **{c['pre_v1_raw_candidate_floor_0_15']}**",
        f"- Deployed floor 0.15: **{c['deployed_raw_candidate_floor_0_15']}**",
        f"- Pre-V1 ceiling 1.55: **{c['pre_v1_raw_candidate_ceiling_1_55']}**",
        f"- Deployed ceiling 1.55: **{c['deployed_raw_candidate_ceiling_1_55']}**",
        "",
        "## Known anchors", "",
        "| Player | Pos | Old raw | New raw | Raw change | Old value | New value | Final change | Rank move | Cohort |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key in ANCHORS:
        r = result["anchors"].get(key)
        if not r:
            continue
        old_val = "—" if r['old_value'] is None else str(r['old_value'])
        new_val = "—" if r['new_value'] is None else str(r['new_value'])
        final_change = "—" if r['value_pct_change'] is None else _fmt_pct(r['value_pct_change'])
        rank_move = "—" if r['rank_change'] is None else f"{r['rank_change']:+d}"
        lines.append(
            f"| {key} | {r['pos'] or ''} | {r['old_raw_prod_mult']:.4f} | {r['new_raw_prod_mult']:.4f} | "
            f"{_fmt_pct(r['raw_prod_mult_pct_change'])} | {old_val} | {new_val} | "
            f"{final_change} | {rank_move} | {r.get('source_cohort') or ''} |"
        )

    lines += ["", "## Largest final-value movers", "", "| Player | Pos | Old | New | Change | Rank move | Cohort/status |", "|---|---|---:|---:|---:|---:|---|"]
    for r in result["largest_final_value_movers"][:20]:
        label = "/".join(x for x in (r.get("source_cohort"), r.get("update_status")) if x)
        lines.append(f"| {r['key']} | {r['pos']} | {r['old_value']} | {r['new_value']} | {_fmt_pct(r['value_pct_change'])} | {r['rank_change']:+d} | {label} |")

    lines += [
        "", "## Release attribution", "",
        "- The OLD side is reconstructed from the immutable pre-V1 `PROD_MULT_DATA` snapshot.",
        "- The NEW side is the actual deployed `index.html`.",
        "- All other valuation constants, age curves, role-floor behavior, and position weights are held identical.",
        "- Offense values are confirmed unchanged.",
        "- The 46 legacy/current IDP position mismatches remain explicitly isolated from this V1 projection release.",
    ]
    return "\n".join(lines) + "\n"


def main():
    result = validate_deployment()
    JSON_OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(build_report(result), encoding="utf-8")
    print(f"PASS final IDP V1 deployment validation: {result['actual_changed_entry_count']} approved PROD_MULT changes deployed")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()

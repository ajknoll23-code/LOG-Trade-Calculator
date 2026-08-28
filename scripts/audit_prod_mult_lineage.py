#!/usr/bin/env python3
"""Audit generated prod-mult lineage against an immutable baked live snapshot.

This script does not decide which side is "correct." It answers the narrower
engineering question: does the current generator reproduce the table that was
actually baked into production, and where is the drift concentrated?
"""

import argparse
import json
import math
import os
import statistics
from collections import defaultdict, Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASELINE = os.path.join(SCRIPT_DIR, "prod_mult_pre_v1_baseline.json")
DEFAULT_GENERATED = os.path.join(SCRIPT_DIR, "prod_mult_pipeline_output.json")
DEFAULT_REPORT = os.path.join(SCRIPT_DIR, "prod_mult_lineage_audit.md")
DEFAULT_JSON = os.path.join(SCRIPT_DIR, "prod_mult_lineage_audit.json")


def percentile(values, q):
    if not values:
        return None
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    idx = (len(vals) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    return vals[lo] + (vals[hi] - vals[lo]) * (idx - lo)


def stats(values):
    if not values:
        return {"n": 0, "median": None, "p90": None, "p95": None, "max": None}
    return {
        "n": len(values),
        "median": statistics.median(values),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "max": max(values),
    }


def fmt(x, digits=4):
    return "n/a" if x is None else f"{x:.{digits}f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    parser.add_argument("--generated", default=DEFAULT_GENERATED)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--json", default=DEFAULT_JSON)
    args = parser.parse_args()

    baseline_doc = json.load(open(args.baseline, encoding="utf-8"))
    baseline = baseline_doc["values"]
    generated_doc = json.load(open(args.generated, encoding="utf-8"))
    generated = generated_doc["players"]

    overlap = sorted(set(baseline) & set(generated))
    missing_generated = sorted(set(baseline) - set(generated))
    extra_generated = sorted(set(generated) - set(baseline))

    rows = []
    by_pos = defaultdict(list)
    by_source = defaultdict(list)
    exact = 0
    clamp_live = Counter()
    clamp_generated = Counter()

    for key in overlap:
        rec = generated[key]
        gen = rec.get("prod_mult_reconstructed")
        if gen is None:
            continue
        old = float(baseline[key])
        abs_diff = abs(gen - old)
        pct_diff = ((gen / old) - 1) * 100 if old else None
        if abs_diff < 1e-12:
            exact += 1
        pos = rec.get("pos") or "?"
        source = rec.get("proj_source") or "?"
        by_pos[pos].append(abs_diff)
        by_source[source].append(abs_diff)
        if old <= 0.1500001:
            clamp_live["floor"] += 1
        elif old >= 1.5499999:
            clamp_live["ceiling"] += 1
        if gen <= 0.1500001:
            clamp_generated["floor"] += 1
        elif gen >= 1.5499999:
            clamp_generated["ceiling"] += 1
        rows.append({
            "key": key,
            "pos": pos,
            "proj_source": source,
            "live": old,
            "generated": gen,
            "signed_diff": gen - old,
            "abs_diff": abs_diff,
            "pct_diff": pct_diff,
            "history_component": rec.get("history_component"),
            "proj_2026_blended": rec.get("proj_2026_blended"),
            "games_played_2025": rec.get("games_played_2025"),
            "sleeper_id": rec.get("sleeper_id"),
        })

    abs_diffs = [r["abs_diff"] for r in rows]
    overall = stats(abs_diffs)
    top = sorted(rows, key=lambda r: r["abs_diff"], reverse=True)[:30]

    result = {
        "baseline_source_sha256": baseline_doc.get("source_sha256"),
        "baseline_entry_count": len(baseline),
        "generated_player_count": len(generated),
        "overlap_key_count": len(overlap),
        "overlap_with_generated_prod_mult": len(rows),
        "exact_match_count": exact,
        "missing_from_generated": missing_generated,
        "extra_generated_count": len(extra_generated),
        "overall_abs_diff": overall,
        "by_position_abs_diff": {k: stats(v) for k, v in sorted(by_pos.items())},
        "by_projection_source_abs_diff": {k: stats(v) for k, v in sorted(by_source.items())},
        "live_clamp_counts": dict(clamp_live),
        "generated_clamp_counts": dict(clamp_generated),
        "top_drift": top,
        "generated_baseline_combined_by_position": generated_doc.get("baseline_combined_by_position", {}),
    }
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    lines = [
        "# PROD_MULT Lineage Audit",
        "",
        "## Verdict",
        "",
        "The current legacy generator does **not** reproduce the immutable pre-V1 baked production table. This report treats that as lineage drift; it does not assume the generator or the baked table is inherently correct.",
        "",
        "## Overall",
        "",
        f"- Immutable live baseline entries: **{len(baseline)}**",
        f"- Generated player records: **{len(generated)}**",
        f"- Overlapping keys: **{len(overlap)}**",
        f"- Overlap with a generated prod_mult: **{len(rows)}**",
        f"- Exact matches: **{exact}**",
        f"- Live keys absent from generated universe: **{len(missing_generated)}**",
        f"- Median absolute prod_mult drift: **{fmt(overall['median'])}**",
        f"- P90 absolute drift: **{fmt(overall['p90'])}**",
        f"- P95 absolute drift: **{fmt(overall['p95'])}**",
        f"- Maximum absolute drift: **{fmt(overall['max'])}**",
        "",
        "## Drift by position",
        "",
        "| Pos | N | Median abs | P90 | P95 | Max |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for pos, s in result["by_position_abs_diff"].items():
        lines.append(f"| {pos} | {s['n']} | {fmt(s['median'])} | {fmt(s['p90'])} | {fmt(s['p95'])} | {fmt(s['max'])} |")

    lines += [
        "",
        "## Drift by legacy projection-source cohort",
        "",
        "| Source | N | Median abs | P90 | P95 | Max |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for source, s in result["by_projection_source_abs_diff"].items():
        lines.append(f"| {source} | {s['n']} | {fmt(s['median'])} | {fmt(s['p90'])} | {fmt(s['p95'])} | {fmt(s['max'])} |")

    lines += [
        "",
        "## Largest absolute drifts",
        "",
        "| Player key | Pos | Live | Generated | Signed diff | Legacy projection source |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in top:
        lines.append(f"| {r['key']} | {r['pos']} | {r['live']:.4f} | {r['generated']:.4f} | {r['signed_diff']:+.4f} | {r['proj_source']} |")

    lines += [
        "",
        "## Interpretation",
        "",
        "- The durability files being restored makes the legacy generator runnable, but does **not** make it historically identical to the baked production table.",
        "- Therefore a new V1 bake must not describe the legacy generated JSON as the true old production baseline.",
        "- The immutable baked baseline should be used for user-visible before/after comparisons.",
        "- Reusable history/durability computation should be separated from the obsolete legacy projection blend before the V1 path is considered canonical.",
        "",
        "## Generated replacement baselines (diagnostic only)",
        "",
    ]
    for pos, val in result["generated_baseline_combined_by_position"].items():
        lines.append(f"- {pos}: {val:.4f}" if val is not None else f"- {pos}: n/a")

    with open(args.report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Wrote {args.report}")
    print(f"Wrote {args.json}")
    print(f"Exact matches: {exact}/{len(rows)}; median abs drift={fmt(overall['median'])}; p95={fmt(overall['p95'])}")


if __name__ == "__main__":
    main()

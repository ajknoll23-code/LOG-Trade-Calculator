#!/usr/bin/env python3
"""Build a diagnostic IDP V1 candidate anchored to the actually baked live prod_mult table.

Why this exists
---------------
The current legacy prod_mult generator is reproducible again, but it does not
reproduce the prod_mult values that were actually baked into production. A
straight re-run would therefore mix two changes:

  1. the intended V1 IDP projection-source change, and
  2. unrelated historical lineage drift in the legacy generator.

This script isolates (1) as much as the available repo data permits. For each
unclamped live IDP value, it reconstructs a dimensionless live ratio from the
actual baked prod_mult, places that ratio on the legacy generator's current
combined-point scale, then applies ONLY the 55%-weighted projection delta:

    anchored_combined = live_ratio * legacy_position_baseline
    candidate_combined = anchored_combined + 0.55 * (V1_proj - legacy_proj)

Replacement baselines are then recomputed at rank 32 and candidate prod_mults
are produced with the established formula.

This is intentionally a DIAGNOSTIC/CANDIDATE generator, not a production bake.
It never edits index.html.
"""

import argparse
import json
import math
import os
import statistics
from collections import Counter, defaultdict

from idp_v1_projection import compute_v1_projection

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASELINE_PATH = os.path.join(SCRIPT_DIR, "prod_mult_pre_v1_baseline.json")
LEGACY_PATH = os.path.join(SCRIPT_DIR, "prod_mult_pipeline_output.json")
FP_PATH = os.path.join(SCRIPT_DIR, "fantasypros_api_normalized_2026.json")
SLEEPER_PATH = os.path.join(SCRIPT_DIR, "sleeper_2026_idp_only.json")
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "identity_crosswalk.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "idp_v1_live_anchored_candidate.json")
REPORT_PATH = os.path.join(SCRIPT_DIR, "idp_v1_live_anchored_report.md")

IDP_POSITIONS = ("LB", "DL", "DB")
REPLACEMENT_RANK = 32
PROJECTION_WEIGHT = 0.55
FLOOR = 0.15
CEILING = 1.55


def pct(values, q):
    if not values:
        return None
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    x = (len(vals) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    if lo == hi:
        return vals[lo]
    return vals[lo] + (vals[hi] - vals[lo]) * (x - lo)


def summarize(values):
    if not values:
        return {"n": 0, "median": None, "p90": None, "p95": None, "min": None, "max": None}
    return {
        "n": len(values),
        "median": statistics.median(values),
        "p90": pct(values, 0.90),
        "p95": pct(values, 0.95),
        "min": min(values),
        "max": max(values),
    }


def clamp_prod(ratio):
    return max(FLOOR, min(CEILING, -0.10 + 0.75 * ratio))


def live_ratio_from_prod(live_prod, legacy_ratio=None):
    """Invert the live prod formula where possible.

    At a clamp boundary the exact pre-clamp ratio is unknowable. Use the
    current legacy ratio only as a within-bound estimate, constrained so it
    cannot contradict the observed clamp state.
    """
    floor_ratio = (FLOOR + 0.10) / 0.75
    ceiling_ratio = (CEILING + 0.10) / 0.75
    if FLOOR < live_prod < CEILING:
        return (live_prod + 0.10) / 0.75, "exact_unclamped"
    if live_prod <= FLOOR:
        if legacy_ratio is None:
            return floor_ratio, "floor_boundary_fallback"
        return min(float(legacy_ratio), floor_ratio), "floor_legacy_bounded"
    if legacy_ratio is None:
        return ceiling_ratio, "ceiling_boundary_fallback"
    return max(float(legacy_ratio), ceiling_ratio), "ceiling_legacy_bounded"


def load_sources():
    baseline_doc = json.load(open(BASELINE_PATH, encoding="utf-8"))
    legacy = json.load(open(LEGACY_PATH, encoding="utf-8"))
    fp_rows = json.load(open(FP_PATH, encoding="utf-8"))["players"]
    sleeper_rows = json.load(open(SLEEPER_PATH, encoding="utf-8"))
    crosswalk = json.load(open(CROSSWALK_PATH, encoding="utf-8"))

    fp = {p["fantasypros_id"]: p for p in fp_rows if p.get("query_position") == "IDP"}
    sleeper = {str(p["sleeper_id"]): p for p in sleeper_rows}
    sleeper_to_fp = {}
    for row in crosswalk:
        if row.get("match_confidence") == "high" and row.get("sleeper_id"):
            sleeper_to_fp[str(row["sleeper_id"])] = fp.get(row.get("fantasypros_id"))

    return baseline_doc, legacy, sleeper, sleeper_to_fp


def build_candidate(scale_multiplier=1.0):
    baseline_doc, legacy, sleeper, sleeper_to_fp = load_sources()
    live_values = baseline_doc["values"]
    legacy_players = legacy["players"]
    legacy_baselines = legacy["baseline_combined_by_position"]

    records = {}
    source_counts = Counter()
    hold_counts = Counter()

    # Start with the full legacy IDP universe for replacement-rank stability.
    # Live players get anchored to what production actually served; non-live
    # players retain the current generated combined value as a background pool.
    for key, rec in legacy_players.items():
        pos = rec.get("pos")
        if pos not in IDP_POSITIONS or rec.get("combined") is None:
            continue
        records[key] = {
            "key": key,
            "pos": pos,
            "is_live_key": key in live_values,
            "legacy_combined": rec.get("combined"),
            "legacy_proj": rec.get("proj_2026_blended"),
            "history_component": rec.get("history_component"),
            "sleeper_id": str(rec.get("sleeper_id")) if rec.get("sleeper_id") else None,
            "legacy_ratio": rec.get("ratio"),
            "legacy_prod_mult": rec.get("prod_mult_reconstructed"),
        }

    for key, row in records.items():
        pos = row["pos"]
        scale_baseline = float(legacy_baselines[pos]) * scale_multiplier
        legacy_combined = float(row["legacy_combined"]) * scale_multiplier

        if row["is_live_key"]:
            live_prod = float(live_values[key])
            ratio, anchor_method = live_ratio_from_prod(live_prod, row.get("legacy_ratio"))
            anchored_combined = ratio * scale_baseline
        else:
            live_prod = None
            anchor_method = "non_live_legacy_background"
            anchored_combined = legacy_combined

        sid = row.get("sleeper_id")
        fp_player = sleeper_to_fp.get(sid) if sid else None
        sleeper_player = sleeper.get(sid) if sid else None
        fp_stats = fp_player.get("raw_stats_used") if fp_player else None
        sleeper_stats = sleeper_player.get("raw_category_season_totals") if sleeper_player else None
        v1 = compute_v1_projection(fp_stats, sleeper_stats, row.get("legacy_proj"))
        source_counts[v1["source_cohort"]] += 1

        legacy_proj = row.get("legacy_proj")
        new_proj = v1["projection"]
        if not row["is_live_key"]:
            # Background-only players stay on legacy combined. This script is
            # explicitly for measuring/baking changes to values actually served.
            projection_delta = 0.0
            candidate_combined = anchored_combined
            update_status = "non_live_background_hold"
        elif legacy_proj is None and v1["source_cohort"] != "no_new_data":
            # No defensible delta exists: a new official source appeared where
            # the old pipeline had no projection at all. Hold rather than invent
            # an old zero. Surface these for a later targeted decision.
            projection_delta = 0.0
            candidate_combined = anchored_combined
            update_status = "hold_new_source_without_legacy_projection"
            hold_counts[update_status] += 1
        elif legacy_proj is None or new_proj is None:
            projection_delta = 0.0
            candidate_combined = anchored_combined
            update_status = "hold_no_comparable_projection"
            hold_counts[update_status] += 1
        else:
            projection_delta = float(new_proj) - float(legacy_proj)
            candidate_combined = anchored_combined + PROJECTION_WEIGHT * projection_delta
            update_status = "projection_delta_applied" if abs(projection_delta) > 1e-12 else "no_projection_delta"

        row.update({
            "live_prod_mult": live_prod,
            "anchor_method": anchor_method,
            "anchored_combined": anchored_combined,
            "v1_projection": new_proj,
            "v1_source_cohort": v1["source_cohort"],
            "fp_active": v1["fp_active"],
            "sleeper_active": v1["sleeper_active"],
            "projection_delta": projection_delta,
            "candidate_combined": candidate_combined,
            "update_status": update_status,
        })

    new_baselines = {}
    rank_players = {}
    for pos in IDP_POSITIONS:
        arr = sorted(
            ((r["candidate_combined"], key) for key, r in records.items() if r["pos"] == pos),
            reverse=True,
        )
        if len(arr) < REPLACEMENT_RANK:
            raise RuntimeError(f"{pos}: only {len(arr)} candidate combined values")
        value, key = arr[REPLACEMENT_RANK - 1]
        new_baselines[pos] = value
        rank_players[pos] = key

    for key, row in records.items():
        ratio = row["candidate_combined"] / new_baselines[row["pos"]]
        row["candidate_ratio"] = ratio
        row["candidate_prod_mult"] = round(clamp_prod(ratio), 4)
        if row["is_live_key"]:
            row["prod_mult_pct_change"] = (
                (row["candidate_prod_mult"] / row["live_prod_mult"] - 1) * 100
                if row["live_prod_mult"] else None
            )

    return {
        "method": "live_anchored_projection_delta_v1",
        "projection_weight": PROJECTION_WEIGHT,
        "scale_multiplier": scale_multiplier,
        "live_baseline_sha256": baseline_doc.get("source_sha256"),
        "legacy_scale_baseline_by_position": {
            p: float(legacy_baselines[p]) * scale_multiplier for p in IDP_POSITIONS
        },
        "candidate_baseline_by_position": new_baselines,
        "replacement_rank_player": rank_players,
        "source_cohort_counts_full_idp_universe": dict(source_counts),
        "hold_counts": dict(hold_counts),
        "players": records,
    }


def build_report(candidate, low_scale, high_scale):
    live_rows = [r for r in candidate["players"].values() if r["is_live_key"]]
    changed_rows = [r for r in live_rows if r.get("prod_mult_pct_change") is not None]
    by_pos = defaultdict(list)
    by_source = defaultdict(list)
    clamp_old = Counter()
    clamp_new = Counter()
    for r in changed_rows:
        by_pos[r["pos"]].append(r["prod_mult_pct_change"])
        by_source[r["v1_source_cohort"]].append(r["prod_mult_pct_change"])
        if r["live_prod_mult"] <= FLOOR + 1e-9:
            clamp_old["floor"] += 1
        if r["live_prod_mult"] >= CEILING - 1e-9:
            clamp_old["ceiling"] += 1
        if r["candidate_prod_mult"] <= FLOOR + 1e-9:
            clamp_new["floor"] += 1
        if r["candidate_prod_mult"] >= CEILING - 1e-9:
            clamp_new["ceiling"] += 1

    def row_summary(rows):
        return summarize(rows)

    largest = sorted(changed_rows, key=lambda r: abs(r["prod_mult_pct_change"]), reverse=True)[:30]

    # Scale robustness: compare candidate prod_mult at +/-10% legacy point scale.
    low = low_scale["players"]
    high = high_scale["players"]
    scale_spreads = []
    for r in changed_rows:
        key = r["key"]
        if key in low and key in high:
            scale_spreads.append(abs(high[key]["candidate_prod_mult"] - low[key]["candidate_prod_mult"]))

    lines = [
        "# IDP V1 Live-Anchored Candidate Report",
        "",
        "## Status",
        "",
        "**Diagnostic candidate only. This does not edit `index.html`.**",
        "",
        "The candidate anchors to the actual baked pre-V1 `prod_mult` values and applies only the V1-vs-legacy projection delta on the established 55% projection share. This avoids importing unrelated drift from the legacy history generator into the user-visible before/after comparison.",
        "",
        "## Baselines",
        "",
        "| Pos | Legacy point-scale baseline | Candidate baseline | Shift | Rank-32 player |",
        "|---|---:|---:|---:|---|",
    ]
    for pos in IDP_POSITIONS:
        old_b = candidate["legacy_scale_baseline_by_position"][pos]
        new_b = candidate["candidate_baseline_by_position"][pos]
        lines.append(f"| {pos} | {old_b:.2f} | {new_b:.2f} | {(new_b/old_b-1)*100:+.1f}% | {candidate['replacement_rank_player'][pos]} |")

    lines += ["", "## True live old -> candidate prod_mult change", "", "| Pos | N | Median | P90 | P95 | Min | Max |", "|---|---:|---:|---:|---:|---:|---:|"]
    for pos in IDP_POSITIONS:
        s = row_summary(by_pos[pos])
        lines.append(f"| {pos} | {s['n']} | {s['median']:+.1f}% | {s['p90']:+.1f}% | {s['p95']:+.1f}% | {s['min']:+.1f}% | {s['max']:+.1f}% |")

    lines += ["", "## Source cohorts", "", "| Cohort | N | Median change | P90 | P95 |", "|---|---:|---:|---:|---:|"]
    for source in ("both", "fp_only", "sleeper_only", "no_new_data"):
        vals = by_source.get(source, [])
        s = row_summary(vals)
        if s["n"]:
            lines.append(f"| {source} | {s['n']} | {s['median']:+.1f}% | {s['p90']:+.1f}% | {s['p95']:+.1f}% |")

    lines += [
        "",
        "## Holds / unresolved deltas",
        "",
    ]
    if candidate["hold_counts"]:
        for k, v in sorted(candidate["hold_counts"].items()):
            lines.append(f"- {k}: **{v}**")
    else:
        lines.append("- None")

    lines += [
        "",
        "## Clamp occupancy",
        "",
        f"- Old live floor: {clamp_old.get('floor',0)}; ceiling: {clamp_old.get('ceiling',0)}",
        f"- Candidate floor: {clamp_new.get('floor',0)}; ceiling: {clamp_new.get('ceiling',0)}",
        "",
        "## Largest absolute movers",
        "",
        "| Player | Pos | Old | Candidate | Change | Source | Projection delta | Status |",
        "|---|---|---:|---:|---:|---|---:|---|",
    ]
    for r in largest:
        lines.append(
            f"| {r['key']} | {r['pos']} | {r['live_prod_mult']:.4f} | {r['candidate_prod_mult']:.4f} | "
            f"{r['prod_mult_pct_change']:+.1f}% | {r['v1_source_cohort']} | {r['projection_delta']:+.1f} | {r['update_status']} |"
        )

    scale_summary = summarize(scale_spreads)
    lines += [
        "",
        "## Point-scale robustness (+/-10%)",
        "",
        "The live ratio itself is scale-free, but the projection delta is measured in fantasy points. To expose dependence on the legacy combined-point scale, the candidate was rerun at 90% and 110% of the current legacy position baselines.",
        "",
        f"- Median candidate prod_mult spread across the full +/-10% scale range: **{scale_summary['median']:.4f}**",
        f"- P95 spread: **{scale_summary['p95']:.4f}**",
        f"- Maximum spread: **{scale_summary['max']:.4f}**",
        "",
        "## Interpretation",
        "",
        "This method is deliberately conservative: it preserves what production actually valued before V1 and applies the new projection architecture as a delta instead of re-running every historical modeling choice. Rows where a new V1 source exists but the legacy pipeline had no comparable projection are held unchanged and surfaced rather than guessed.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()

    candidate = build_candidate(1.0)
    low = build_candidate(0.9)
    high = build_candidate(1.1)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(candidate, f, indent=2)
        f.write("\n")
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(build_report(candidate, low, high))

    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Conservative V1 candidate that isolates the projection-source change.

This is the production-oriented bridge between the immutable pre-V1 live
PROD_MULT table and the newly canonical/reproducible model inputs.

Why a bridge is needed
----------------------
A full recomputation from canonical history + V1 projections is reproducible,
but the old baked PROD_MULT table contains substantial historical lineage drift
relative to today's regenerated history model. Shipping that full recompute at
the same time as the V1 projection change would mix two independent changes.

This candidate therefore:
  1. treats the actual pre-V1 baked PROD_MULT as the authoritative starting
     player ratio (exactly invertible when not clamped),
  2. uses a freshly reproducible canonical OLD-model combined baseline only as
     the point-unit scale for translating a projection-points delta into ratio
     space,
  3. applies 55% * (V1 projection - legacy projection) and nothing else,
  4. recomputes rank-32 positional baselines,
  5. never reads prod_mult_pipeline_output.json and never edits index.html.

For players where V1 has a new source but the old projection is unavailable,
the projection delta is held at zero rather than pretending the old projection
was zero. Those cases are surfaced for future targeted work.
"""

from __future__ import annotations

import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from idp_v1_production_candidate import build_candidate as build_canonical_candidate

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR / "idp_v1_isolated_projection_candidate.json"
REPORT_PATH = SCRIPT_DIR / "idp_v1_isolated_projection_candidate_report.md"

IDP_POSITIONS = ("LB", "DL", "DB")
REPLACEMENT_RANK = 32
PROJECTION_WEIGHT = 0.55
FLOOR = 0.15
CEILING = 1.55


def clamp_prod(ratio):
    return max(FLOOR, min(CEILING, -0.10 + 0.75 * ratio))


def live_ratio_from_prod(live_prod, canonical_old_ratio=None):
    floor_ratio = (FLOOR + 0.10) / 0.75
    ceiling_ratio = (CEILING + 0.10) / 0.75
    if FLOOR < live_prod < CEILING:
        return (live_prod + 0.10) / 0.75, "exact_unclamped"
    if live_prod <= FLOOR:
        if canonical_old_ratio is None:
            return floor_ratio, "floor_boundary_fallback"
        return min(float(canonical_old_ratio), floor_ratio), "floor_canonical_old_bounded"
    if canonical_old_ratio is None:
        return ceiling_ratio, "ceiling_boundary_fallback"
    return max(float(canonical_old_ratio), ceiling_ratio), "ceiling_canonical_old_bounded"


def pct(values, q):
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


def summarize(values):
    if not values:
        return {"n": 0, "median": None, "p90": None, "p95": None, "min": None, "max": None}
    return {
        "n": len(values),
        "median": statistics.median(values),
        "p90": pct(values, .90),
        "p95": pct(values, .95),
        "min": min(values),
        "max": max(values),
    }


def build_candidate():
    canonical = build_canonical_candidate()
    src = canonical["players"]

    # Reconstruct the old model's point scale from current canonical history
    # + directly reconstructed legacy projection inputs. This scale is used
    # only to translate projection-point deltas; it is not allowed to replace
    # the old live player ratios.
    old_combined = {}
    old_baselines = {}
    old_baseline_players = {}
    for key, r in src.items():
        lp = r.get("legacy_projection_fallback")
        hc = r.get("history_component")
        if lp is not None and hc is not None:
            old_combined[key] = 0.45 * float(hc) + 0.55 * float(lp)

    for pos in IDP_POSITIONS:
        arr = sorted(
            [(v, k) for k, v in old_combined.items() if src[k]["pos"] == pos],
            reverse=True,
        )
        if len(arr) < REPLACEMENT_RANK:
            raise RuntimeError(f"{pos}: only {len(arr)} old-model combined rows")
        val, key = arr[REPLACEMENT_RANK - 1]
        old_baselines[pos] = val
        old_baseline_players[pos] = key

    records = {}
    hold_counts = Counter()
    anchor_counts = Counter()

    for key, r in src.items():
        pos = r["pos"]
        live_prod = float(r["old_live_prod_mult"])
        canonical_old_ratio = (
            old_combined[key] / old_baselines[pos]
            if key in old_combined
            else None
        )
        live_ratio, anchor_method = live_ratio_from_prod(live_prod, canonical_old_ratio)
        anchored_combined = live_ratio * old_baselines[pos]
        anchor_counts[anchor_method] += 1

        old_proj = r.get("legacy_projection_fallback")
        new_proj = r.get("v1_projection")
        cohort = r.get("v1_source_cohort")

        if cohort == "no_new_data":
            projection_delta = 0.0
            update_status = "no_new_data_projection_hold"
        elif old_proj is None:
            projection_delta = 0.0
            update_status = "hold_new_source_without_legacy_projection"
            hold_counts[update_status] += 1
        elif new_proj is None:
            projection_delta = 0.0
            update_status = "hold_no_comparable_projection"
            hold_counts[update_status] += 1
        else:
            projection_delta = float(new_proj) - float(old_proj)
            update_status = "projection_delta_applied"

        candidate_combined = anchored_combined + PROJECTION_WEIGHT * projection_delta
        records[key] = {
            **r,
            "canonical_old_combined": old_combined.get(key),
            "canonical_old_ratio": canonical_old_ratio,
            "canonical_old_point_baseline": old_baselines[pos],
            "anchor_method": anchor_method,
            "live_ratio_anchor": live_ratio,
            "anchored_combined": anchored_combined,
            "projection_delta": projection_delta,
            "candidate_combined": candidate_combined,
            "update_status": update_status,
        }

    new_baselines = {}
    new_baseline_players = {}
    for pos in IDP_POSITIONS:
        arr = sorted(
            [(r["candidate_combined"], key) for key, r in records.items() if r["pos"] == pos],
            reverse=True,
        )
        val, key = arr[REPLACEMENT_RANK - 1]
        new_baselines[pos] = val
        new_baseline_players[pos] = key

    for key, r in records.items():
        ratio = r["candidate_combined"] / new_baselines[r["pos"]]
        pm = round(clamp_prod(ratio), 4)
        r["candidate_ratio"] = ratio
        r["candidate_prod_mult"] = pm
        r["pct_change"] = (pm / r["old_live_prod_mult"] - 1) * 100 if r["old_live_prod_mult"] else None

    return {
        "method": "live_ratio_anchor_plus_reproducible_projection_delta_v1",
        "projection_weight": PROJECTION_WEIGHT,
        "replacement_rank": REPLACEMENT_RANK,
        "canonical_old_baseline_by_position": old_baselines,
        "canonical_old_replacement_player": old_baseline_players,
        "candidate_baseline_by_position": new_baselines,
        "candidate_replacement_player": new_baseline_players,
        "source_cohort_counts": canonical["source_cohort_counts"],
        "identity_method_counts": canonical["identity_method_counts"],
        "anchor_method_counts": dict(anchor_counts),
        "hold_counts": dict(hold_counts),
        "players": records,
    }


def build_report(candidate):
    rows = list(candidate["players"].values())
    by_pos = defaultdict(list)
    by_source = defaultdict(list)
    by_status = defaultdict(list)
    clamp_old = Counter()
    clamp_new = Counter()
    for r in rows:
        ch = r["pct_change"]
        by_pos[r["pos"]].append(ch)
        by_source[r["v1_source_cohort"]].append(ch)
        by_status[r["update_status"]].append(ch)
        if r["old_live_prod_mult"] <= FLOOR + 1e-9: clamp_old[(r["pos"],"floor")]+=1
        if r["old_live_prod_mult"] >= CEILING - 1e-9: clamp_old[(r["pos"],"ceiling")]+=1
        if r["candidate_prod_mult"] <= FLOOR + 1e-9: clamp_new[(r["pos"],"floor")]+=1
        if r["candidate_prod_mult"] >= CEILING - 1e-9: clamp_new[(r["pos"],"ceiling")]+=1

    anchors = ["bradley chubb","aidan hutchinson","myles garrett","fred warner","roquan smith","ej speed","isaiah mcduffie"]
    risers = sorted(rows, key=lambda r:r["pct_change"], reverse=True)[:20]
    fallers = sorted(rows, key=lambda r:r["pct_change"])[:20]

    lines = [
        "# IDP V1 Isolated Projection Candidate Report", "",
        "## Status", "",
        "**Preferred V1 bake candidate for validation; still does not edit `index.html`.**", "",
        "This path isolates the validated projection-source change from historical history/prod-mult drift. It does not read `prod_mult_pipeline_output.json`. The actual pre-V1 baked prod_mult supplies the starting player ratio; a freshly reproducible old-model baseline supplies only the point-unit conversion used for the 55%-weighted projection delta.", "",
        "## Old point-scale -> candidate baseline", "",
        "| Pos | Canonical old point baseline | Old rank-32 | Candidate baseline | New rank-32 | Shift |", "|---|---:|---|---:|---|---:|",
    ]
    for pos in IDP_POSITIONS:
        o=candidate['canonical_old_baseline_by_position'][pos]; n=candidate['candidate_baseline_by_position'][pos]
        lines.append(f"| {pos} | {o:.2f} | {candidate['canonical_old_replacement_player'][pos]} | {n:.2f} | {candidate['candidate_replacement_player'][pos]} | {(n/o-1)*100:+.1f}% |")

    lines += ["", "## True pre-V1 live -> isolated V1 prod_mult change", "", "| Pos | N | Median | P90 | P95 | Min | Max |", "|---|---:|---:|---:|---:|---:|---:|"]
    for pos in IDP_POSITIONS:
        s=summarize(by_pos[pos]); lines.append(f"| {pos} | {s['n']} | {s['median']:+.1f}% | {s['p90']:+.1f}% | {s['p95']:+.1f}% | {s['min']:+.1f}% | {s['max']:+.1f}% |")

    lines += ["", "## Source cohorts", "", "| Cohort | N | Median | P90 | P95 |", "|---|---:|---:|---:|---:|"]
    for c in ("both","fp_only","sleeper_only","no_new_data"):
        s=summarize(by_source.get(c,[]))
        if s['n']: lines.append(f"| {c} | {s['n']} | {s['median']:+.1f}% | {s['p90']:+.1f}% | {s['p95']:+.1f}% |")

    lines += ["", "## Holds", ""]
    if candidate['hold_counts']:
        for k,v in sorted(candidate['hold_counts'].items()): lines.append(f"- `{k}`: **{v}**")
    else: lines.append("- None")

    lines += ["", "## Anchor methods", ""]
    for k,v in sorted(candidate['anchor_method_counts'].items()): lines.append(f"- `{k}`: **{v}**")

    lines += ["", "## Clamp occupancy", "", "| Pos | Old floor | New floor | Old ceiling | New ceiling |", "|---|---:|---:|---:|---:|"]
    for pos in IDP_POSITIONS:
        lines.append(f"| {pos} | {clamp_old[(pos,'floor')]} | {clamp_new[(pos,'floor')]} | {clamp_old[(pos,'ceiling')]} | {clamp_new[(pos,'ceiling')]} |")

    lines += ["", "## Known anchors", "", "| Player | Pos | Old | Candidate | Change | Cohort | Status |", "|---|---|---:|---:|---:|---|---|"]
    for k in anchors:
        r=candidate['players'].get(k)
        if not r: continue
        lines.append(f"| {k} | {r['pos']} | {r['old_live_prod_mult']:.4f} | {r['candidate_prod_mult']:.4f} | {r['pct_change']:+.1f}% | {r['v1_source_cohort']} | {r['update_status']} |")

    def movers(title, arr):
        lines.extend(["",title,"","| Player | Pos | Old | Candidate | Change | Cohort | Status |","|---|---|---:|---:|---:|---|---|"])
        for r in arr:
            lines.append(f"| {r['key']} | {r['pos']} | {r['old_live_prod_mult']:.4f} | {r['candidate_prod_mult']:.4f} | {r['pct_change']:+.1f}% | {r['v1_source_cohort']} | {r['update_status']} |")
    movers("## Top 20 risers",risers); movers("## Top 20 fallers",fallers)

    lines += ["", "## Decision interpretation", "", "If this isolated candidate remains close to the earlier validated sensitivity shape while the full canonical recompute is much more volatile, that is strong evidence that the first V1 production bake should use this isolated bridge and leave historical-lineage normalization for a separate later migration. Mixing both changes in one release would make player-value movement impossible to attribute cleanly."]
    return "\n".join(lines)+"\n"


def run_selftest():
    assert abs(live_ratio_from_prod(.65)[0]-1.0)<1e-12
    assert live_ratio_from_prod(.15,.2)[0] <= (FLOOR+.10)/.75
    print("idp_v1_isolated_projection_candidate self-test passed.")


def main():
    if '--selftest' in os.sys.argv:
        run_selftest(); return
    c=build_candidate()
    with open(OUTPUT_PATH,'w',encoding='utf-8') as f:
        json.dump(c,f,indent=2); f.write('\n')
    REPORT_PATH.write_text(build_report(c),encoding='utf-8')
    print(f"Wrote {OUTPUT_PATH}"); print(f"Wrote {REPORT_PATH}")
    print('baselines',c['candidate_baseline_by_position']); print('holds',c['hold_counts'])

if __name__=='__main__': main()

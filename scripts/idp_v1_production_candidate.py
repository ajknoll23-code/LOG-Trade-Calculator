#!/usr/bin/env python3
"""Build the reproducible IDP V1 production candidate without stale lineage JSON.

This is the clean candidate path requested after the lineage audit:

    canonical 2025 history component
      + validated V1 2026 IDP category projection
      -> 45/55 combined value
      -> position replacement baseline (rank 32)
      -> prod_mult

The script never reads ``prod_mult_pipeline_output.json`` and never edits
``index.html``. The immutable pre-V1 baked PROD_MULT snapshot is used only for
before/after comparison and for the explicit no-new-data projection fallback
policy -- never as computational history lineage.

For V1 source identity:
  * FantasyPros is used only through high-confidence identity_crosswalk rows.
  * Sleeper can be used directly when a stable Sleeper ID is known from the
    crosswalk, real 2025 PPG output, or current league/free-agent sync data.
  * If neither provider has meaningful V1 category signal, the old 2026
    projection is reconstructed directly from the old raw source files and
    preserved as the fallback. No stale prod-mult lineage file is required.

This is a candidate/validation generator, not a production bake.
"""

from __future__ import annotations

import json
import math
import os
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from idp_v1_projection import compute_v1_projection

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

BASELINE_PATH = SCRIPT_DIR / "prod_mult_pre_v1_baseline.json"
HISTORY_PATH = SCRIPT_DIR / "production_history_components.json"
ALL_PLAYERS_PATH = SCRIPT_DIR / "all_players.json"
CURRENT_POSITION_PATH = SCRIPT_DIR / "player_positions.json"
FP_V1_PATH = SCRIPT_DIR / "fantasypros_api_normalized_2026.json"
SLEEPER_V1_PATH = SCRIPT_DIR / "sleeper_2026_idp_only.json"
CROSSWALK_PATH = SCRIPT_DIR / "identity_crosswalk.json"
LEGACY_FP_PATH = SCRIPT_DIR / "fantasypros_2026_projections.json"
LEGACY_SLEEPER_PATH = SCRIPT_DIR / "sleeper_2026_projections.json"
PPG_PATH = SCRIPT_DIR / "ppg_results.json"
LEAGUE_ROSTERS_PATH = REPO_ROOT / "data" / "league_rosters.json"
FREE_AGENTS_PATH = REPO_ROOT / "data" / "free_agents.json"
OUTPUT_PATH = SCRIPT_DIR / "idp_v1_production_candidate.json"
REPORT_PATH = SCRIPT_DIR / "idp_v1_production_candidate_report.md"

IDP_POSITIONS = ("LB", "DL", "DB")
REPLACEMENT_RANK = 32
HISTORY_WEIGHT = 0.45
PROJECTION_WEIGHT = 0.55
FLOOR = 0.15
CEILING = 1.55


def normalize_name(s):
    return re.sub(r"\s+", " ", re.sub(r"[.'\u2019-]", "", str(s).strip().lower()))


def load_aliases():
    src = (SCRIPT_DIR / "ppg_pipeline.py").read_text(encoding="utf-8")
    m = re.search(r"ALIASES\s*=\s*\{.*?\n\}", src, re.S)
    if not m:
        return {}
    ns = {}
    exec(m.group(0), ns)
    return ns.get("ALIASES", {})


def resolve_key(name, aliases):
    key = normalize_name(name)
    return aliases.get(key, key)


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


def legacy_projection_lookup(aliases):
    """Reconstruct the old 2026 projection input directly from source files.

    This is intentionally a fallback-only reconstruction. It does not carry
    history, baseline, ratio, or prod_mult from the stale legacy lineage JSON.
    """
    sl = {}
    for row in json.load(open(LEGACY_SLEEPER_PATH, encoding="utf-8")):
        key = resolve_key(row["player"], aliases)
        sl[key] = row.get("sleeper_2026_proj_total")

    fp = {}
    for row in json.load(open(LEGACY_FP_PATH, encoding="utf-8")):
        key = resolve_key(row["player"], aliases)
        fp[key] = row.get("fantasypros_2026_proj")

    out = {}
    for key in set(sl) | set(fp):
        s = sl.get(key)
        f = fp.get(key)
        if s is not None and f is not None:
            proj = 0.5 * float(f) + 0.5 * float(s)
            source = "legacy_blend_50_50"
        elif f is not None:
            proj = float(f)
            source = "legacy_fantasypros_only"
        elif s is not None:
            proj = float(s)
            source = "legacy_sleeper_only"
        else:
            proj = None
            source = "legacy_no_projection"
        out[key] = {"projection": proj, "source": source}
    return out


def _add_identity_candidate(store, key, pos, sleeper_id, method):
    if not sleeper_id or pos not in IDP_POSITIONS:
        return
    store[key].append({"sleeper_id": str(sleeper_id), "pos": pos, "method": method})


def build_sleeper_identity_map(aliases, positions, history_doc):
    """Resolve stable Sleeper IDs for live keys without unsafe name overwrite.

    Priority later is high-confidence crosswalk > real 2025 PPG ID > unique
    current sync name+position. Ambiguous current sync collisions are surfaced
    rather than guessed.
    """
    candidates = defaultdict(list)

    # Real history rows already carry IDs resolved by ppg_pipeline's guarded
    # matching/manual-overrides process.
    for key, row in history_doc["players"].items():
        sid = row.get("sleeper_id")
        pos = row.get("pos")
        if sid and pos in IDP_POSITIONS:
            _add_identity_candidate(candidates, key, pos, sid, "ppg_history_id")

    # Current roster/free-agent sync data is already Sleeper-ID keyed. Use
    # name + canonical position only when unique.
    roster_doc = json.load(open(LEAGUE_ROSTERS_PATH, encoding="utf-8"))
    for roster in roster_doc.get("rosters", []):
        for bucket in ("starters", "bench", "taxi", "reserve_ir"):
            for p in roster.get(bucket, []):
                fps = p.get("fantasy_positions") or []
                for pos in fps:
                    if pos in IDP_POSITIONS:
                        key = resolve_key(p.get("name", ""), aliases)
                        _add_identity_candidate(candidates, key, pos, p.get("player_id"), "league_sync")

    fa_doc = json.load(open(FREE_AGENTS_PATH, encoding="utf-8"))
    for p in fa_doc.get("free_agents", []):
        pos = p.get("pos")
        if pos in IDP_POSITIONS:
            key = resolve_key(p.get("name", ""), aliases)
            _add_identity_candidate(candidates, key, pos, p.get("player_id"), "free_agent_sync")

    resolved = {}
    ambiguous = {}
    for key, pos in positions.items():
        if pos not in IDP_POSITIONS:
            continue
        same_pos = [c for c in candidates.get(key, []) if c["pos"] == pos]
        ids = sorted({c["sleeper_id"] for c in same_pos})
        if len(ids) == 1:
            methods = sorted({c["method"] for c in same_pos if c["sleeper_id"] == ids[0]})
            resolved[key] = {"sleeper_id": ids[0], "method": "+".join(methods)}
        elif len(ids) > 1:
            ambiguous[key] = same_pos
    return resolved, ambiguous


def build_candidate():
    aliases = load_aliases()
    baseline_doc = json.load(open(BASELINE_PATH, encoding="utf-8"))
    baseline_values = baseline_doc["values"]
    history_doc = json.load(open(HISTORY_PATH, encoding="utf-8"))
    # IMPORTANT RELEASE-ATTRIBUTION CHOICE:
    # ``all_players.json`` is the position grouping used by the legacy production
    # lineage/history pipeline. Some EDGE/hybrid players now have a different
    # canonical valuation position in player_positions.json / PLAYER_DB. For the
    # first V1 projection-source release we intentionally preserve the legacy
    # model-position grouping inside the OLD-vs-NEW bridge so a position-lineage
    # migration is not silently bundled into the projection change. The final
    # Trade Desk value engine still uses the current PLAYER_DB valuation position.
    # A future canonical-position migration must be audited separately.
    positions = {p["key"]: p["pos"] for p in json.load(open(ALL_PLAYERS_PATH, encoding="utf-8"))}
    current_positions = json.load(open(CURRENT_POSITION_PATH, encoding="utf-8"))
    legacy_proj = legacy_projection_lookup(aliases)

    # Exact live IDP universe: only keys that were actually served pre-V1 and
    # have a known tracked IDP position. This deliberately excludes stale
    # all_players aliases that were removed from the live PROD_MULT table.
    live_idp_keys = sorted(k for k in baseline_values if positions.get(k) in IDP_POSITIONS)
    position_mismatches = [
        {"key": k, "legacy_model_position": positions[k], "current_valuation_position": current_positions[k]}
        for k in live_idp_keys
        if current_positions.get(k) in IDP_POSITIONS and current_positions[k] != positions[k]
    ]

    sleeper_identity, ambiguous_identity = build_sleeper_identity_map(aliases, positions, history_doc)

    fp_rows = json.load(open(FP_V1_PATH, encoding="utf-8"))["players"]
    fp_by_id = {p["fantasypros_id"]: p for p in fp_rows if p.get("query_position") == "IDP"}
    sleeper_rows = json.load(open(SLEEPER_V1_PATH, encoding="utf-8"))
    sleeper_by_id = {str(p["sleeper_id"]): p for p in sleeper_rows}

    high_crosswalk = {}
    for row in json.load(open(CROSSWALK_PATH, encoding="utf-8")):
        if row.get("match_confidence") != "high" or not row.get("sleeper_id"):
            continue
        key = resolve_key(row.get("name", ""), aliases)
        # Crosswalk positions are provider classification. Identity is safe to
        # reuse across those classifications. For first-release attribution,
        # baseline grouping intentionally remains on the legacy model position
        # documented above; current valuation position is surfaced separately.
        high_crosswalk[key] = row

    records = {}
    source_counts = Counter()
    identity_counts = Counter()
    fallback_counts = Counter()

    for key in live_idp_keys:
        pos = positions[key]
        history = history_doc["players"].get(key)
        if not history or history.get("history_component") is None:
            raise RuntimeError(f"{key}: canonical history component missing")

        cross = high_crosswalk.get(key)
        if cross:
            sid = str(cross["sleeper_id"])
            fp_player = fp_by_id.get(cross.get("fantasypros_id"))
            identity_method = "high_confidence_crosswalk"
        else:
            ident = sleeper_identity.get(key)
            sid = ident["sleeper_id"] if ident else None
            fp_player = None
            identity_method = ident["method"] if ident else "no_stable_sleeper_id"

        sleeper_player = sleeper_by_id.get(sid) if sid else None
        fp_stats = fp_player.get("raw_stats_used") if fp_player else None
        sleeper_stats = sleeper_player.get("raw_category_season_totals") if sleeper_player else None

        old = legacy_proj.get(key, {"projection": None, "source": "legacy_no_projection"})
        v1 = compute_v1_projection(fp_stats, sleeper_stats, old_proj=old["projection"])
        new_proj = v1["projection"]

        # If there is no V1 signal and no old projection at all, we cannot
        # honestly construct a new combined value. Keep the old live prod_mult
        # explicit and exclude the row from replacement-baseline computation.
        # This is surfaced, never silently treated as zero.
        if new_proj is None:
            combined = None
            status = "hold_live_no_projection_lineage"
            fallback_counts[status] += 1
        else:
            combined = HISTORY_WEIGHT * float(history["history_component"]) + PROJECTION_WEIGHT * float(new_proj)
            status = "computed"
            if v1["source_cohort"] == "no_new_data":
                fallback_counts[old["source"]] += 1

        source_counts[v1["source_cohort"]] += 1
        identity_counts[identity_method] += 1

        records[key] = {
            "key": key,
            "pos": pos,
            "legacy_model_position": pos,
            "current_valuation_position": current_positions.get(key, pos),
            "sleeper_id": sid,
            "identity_method": identity_method,
            "fantasypros_id": cross.get("fantasypros_id") if cross else None,
            "history_component": history["history_component"],
            "shrunk_ppg": history.get("shrunk_ppg"),
            "durability_projected_games_2026": history.get("durability_projected_games_2026"),
            "legacy_projection_fallback": old["projection"],
            "legacy_projection_source": old["source"],
            "v1_projection": new_proj,
            "v1_source_cohort": v1["source_cohort"],
            "fp_active": v1["fp_active"],
            "sleeper_active": v1["sleeper_active"],
            "fp_tackle_active": v1["fp_tackle_active"],
            "sleeper_tackle_active": v1["sleeper_tackle_active"],
            "combined": combined,
            "status": status,
            "old_live_prod_mult": float(baseline_values[key]),
        }

    baselines = {}
    baseline_players = {}
    for pos in IDP_POSITIONS:
        arr = sorted(
            [(r["combined"], key) for key, r in records.items() if r["pos"] == pos and r["combined"] is not None],
            reverse=True,
        )
        if len(arr) < REPLACEMENT_RANK:
            raise RuntimeError(f"{pos}: only {len(arr)} computable live players; need {REPLACEMENT_RANK}")
        val, key = arr[REPLACEMENT_RANK - 1]
        baselines[pos] = val
        baseline_players[pos] = key

    for key, r in records.items():
        if r["combined"] is None:
            r["candidate_prod_mult"] = r["old_live_prod_mult"]
            r["candidate_ratio"] = None
            r["pct_change"] = 0.0
            continue
        ratio = r["combined"] / baselines[r["pos"]]
        pm = round(clamp_prod(ratio), 4)
        r["candidate_ratio"] = ratio
        r["candidate_prod_mult"] = pm
        r["pct_change"] = (pm / r["old_live_prod_mult"] - 1) * 100 if r["old_live_prod_mult"] else None

    return {
        "method": "canonical_history_plus_idp_v1_projection",
        "history_weight": HISTORY_WEIGHT,
        "projection_weight": PROJECTION_WEIGHT,
        "replacement_rank": REPLACEMENT_RANK,
        "pre_v1_baseline_sha256": baseline_doc.get("source_sha256"),
        "live_idp_player_count": len(records),
        "candidate_baseline_by_position": baselines,
        "replacement_rank_player": baseline_players,
        "source_cohort_counts": dict(source_counts),
        "identity_method_counts": dict(identity_counts),
        "fallback_counts": dict(fallback_counts),
        "ambiguous_sync_identities_not_used": sorted(ambiguous_identity),
        "legacy_vs_current_position_mismatch_count": len(position_mismatches),
        "legacy_vs_current_position_mismatches": position_mismatches,
        "players": records,
    }


def final_value_proxy(prod_mult, pos, key):
    """No duplicate age/value model here: final-value checks are delegated.

    The report intentionally stays at prod_mult/rank level. The repository's
    repaired snapshot_values.py is the canonical final-value parity tool and
    will be used before any production bake.
    """
    return None


def build_report(candidate):
    rows = list(candidate["players"].values())
    by_pos = defaultdict(list)
    by_source = defaultdict(list)
    clamp_old = Counter()
    clamp_new = Counter()
    for r in rows:
        if r["pct_change"] is not None:
            by_pos[r["pos"]].append(r["pct_change"])
            by_source[r["v1_source_cohort"]].append(r["pct_change"])
        if r["old_live_prod_mult"] <= FLOOR + 1e-9:
            clamp_old[(r["pos"], "floor")] += 1
        if r["old_live_prod_mult"] >= CEILING - 1e-9:
            clamp_old[(r["pos"], "ceiling")] += 1
        if r["candidate_prod_mult"] <= FLOOR + 1e-9:
            clamp_new[(r["pos"], "floor")] += 1
        if r["candidate_prod_mult"] >= CEILING - 1e-9:
            clamp_new[(r["pos"], "ceiling")] += 1

    top_up = sorted(rows, key=lambda r: r.get("pct_change") if r.get("pct_change") is not None else -999, reverse=True)[:20]
    top_down = sorted(rows, key=lambda r: r.get("pct_change") if r.get("pct_change") is not None else 999)[:20]

    anchors = [
        "bradley chubb", "aidan hutchinson", "myles garrett", "fred warner",
        "roquan smith", "ej speed", "christian izien", "isaiah mcduffie",
    ]

    lines = [
        "# IDP V1 Canonical Production Candidate Report",
        "",
        "## Status",
        "",
        "**Diagnostic candidate only. `index.html` was not modified.**",
        "",
        "This candidate removes `prod_mult_pipeline_output.json` from the V1 computational path. It combines the canonical extracted history component with the validated category-level V1 projection and recomputes rank-32 LB/DL/DB baselines over the exact immutable pre-V1 live IDP table.",
        "",
        "## Population / source coverage",
        "",
        f"- Live pre-V1 IDP keys evaluated: **{candidate['live_idp_player_count']}**",
        f"- Legacy model-position vs current valuation-position mismatches intentionally held separate from V1: **{candidate['legacy_vs_current_position_mismatch_count']}**",
    ]
    for k, v in sorted(candidate["source_cohort_counts"].items()):
        lines.append(f"- V1 source cohort `{k}`: **{v}**")
    lines += ["", "Identity methods:"]
    for k, v in sorted(candidate["identity_method_counts"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- `{k}`: **{v}**")
    if candidate["fallback_counts"]:
        lines += ["", "Fallback/hold counts:"]
        for k, v in sorted(candidate["fallback_counts"].items()):
            lines.append(f"- `{k}`: **{v}**")

    lines += [
        "",
        "## Candidate replacement baselines",
        "",
        "| Pos | Combined baseline | Rank-32 player |",
        "|---|---:|---|",
    ]
    for pos in IDP_POSITIONS:
        lines.append(f"| {pos} | {candidate['candidate_baseline_by_position'][pos]:.2f} | {candidate['replacement_rank_player'][pos]} |")

    lines += [
        "",
        "## True pre-V1 live -> canonical V1 prod_mult change",
        "",
        "| Pos | N | Median | P90 | P95 | Min | Max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pos in IDP_POSITIONS:
        s = summarize(by_pos[pos])
        lines.append(f"| {pos} | {s['n']} | {s['median']:+.1f}% | {s['p90']:+.1f}% | {s['p95']:+.1f}% | {s['min']:+.1f}% | {s['max']:+.1f}% |")

    lines += ["", "## Change by V1 source cohort", "", "| Cohort | N | Median | P90 | P95 |", "|---|---:|---:|---:|---:|"]
    for cohort in ("both", "fp_only", "sleeper_only", "no_new_data"):
        s = summarize(by_source.get(cohort, []))
        if s["n"]:
            lines.append(f"| {cohort} | {s['n']} | {s['median']:+.1f}% | {s['p90']:+.1f}% | {s['p95']:+.1f}% |")

    lines += ["", "## Clamp occupancy", "", "| Pos | Old floor | New floor | Old ceiling | New ceiling |", "|---|---:|---:|---:|---:|"]
    for pos in IDP_POSITIONS:
        lines.append(
            f"| {pos} | {clamp_old[(pos,'floor')]} | {clamp_new[(pos,'floor')]} | "
            f"{clamp_old[(pos,'ceiling')]} | {clamp_new[(pos,'ceiling')]} |"
        )

    lines += ["", "## Known anchors", "", "| Player | Pos | Old | Candidate | Change | Cohort | Identity |", "|---|---|---:|---:|---:|---|---|"]
    for key in anchors:
        r = candidate["players"].get(key)
        if not r:
            lines.append(f"| {key} | n/a | n/a | n/a | n/a | n/a | not in live baseline |")
            continue
        lines.append(
            f"| {key} | {r['pos']} | {r['old_live_prod_mult']:.4f} | {r['candidate_prod_mult']:.4f} | "
            f"{r['pct_change']:+.1f}% | {r['v1_source_cohort']} | {r['identity_method']} |"
        )

    def add_movers(title, movers):
        lines.extend(["", title, "", "| Player | Pos | Old | Candidate | Change | Source |", "|---|---|---:|---:|---:|---|"])
        for r in movers:
            lines.append(
                f"| {r['key']} | {r['pos']} | {r['old_live_prod_mult']:.4f} | {r['candidate_prod_mult']:.4f} | "
                f"{r['pct_change']:+.1f}% | {r['v1_source_cohort']} |"
            )
    add_movers("## Top 20 risers", top_up)
    add_movers("## Top 20 fallers", top_down)

    lines += [
        "",
        "## Interpretation guardrail",
        "",
        "This report intentionally shows the result of a **full reproducible history+projection recomputation while preserving the legacy production-position grouping**. The separate current valuation position is surfaced explicitly. If movement is materially larger than the already-validated live-anchored projection-delta experiment, that difference is evidence of historical lineage drift in the old baked values -- not evidence that V1 projection math itself suddenly changed. A production decision should explicitly choose whether V1 is allowed to absorb that historical drift or whether the first V1 bake should isolate the projection-source change only.",
    ]
    return "\n".join(lines) + "\n"


def run_selftest():
    # Core algebra / clamp boundaries.
    assert abs(clamp_prod(1.0) - 0.65) < 1e-12
    assert clamp_prod(0.0) == FLOOR
    assert clamp_prod(99.0) == CEILING
    print("idp_v1_production_candidate self-test passed.")


def main():
    if "--selftest" in os.sys.argv:
        run_selftest()
        return
    candidate = build_candidate()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(candidate, f, indent=2)
        f.write("\n")
    REPORT_PATH.write_text(build_report(candidate), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print("Source cohorts:", candidate["source_cohort_counts"])
    print("Candidate baselines:", candidate["candidate_baseline_by_position"])


if __name__ == "__main__":
    main()

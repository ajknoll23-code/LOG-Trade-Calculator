#!/usr/bin/env python3
"""Production V2 Phase 1 research audit.

Purpose
-------
Build a transparent, research-only benchmark reconstruction of the current
Trade Desk production multiplier and compare it with the immutable production
state currently baked into index.html.

THIS FILE MUST NOT MUTATE PRODUCTION.

Phase 1 intentionally does NOT claim to have found the correct V2 formula.
The benchmark coefficients below are inherited/neutral starting points used to
validate data lineage, identity joins, coverage, and blast radius before any
coefficient calibration begins:

* history component: canonical existing 2025 shrinkage + durability module
* offense forward projection: 50% FantasyPros / 50% Sleeper when both exist
  (single-source fallback otherwise)
* IDP forward projection: canonical validated IDP V1 category-level ensemble
* history / forward blend: 45% / 55%
* replacement ranks: existing legacy research ranks
* prod_mult transform: clamp(-0.10 + 0.75 * ratio, 0.15, 1.55)

The candidate production multiplier is then passed through the CURRENT live
productionMultiplier/ageMultiplier/playerValue architecture via
scripts/validation/snapshot_values.py. Therefore Phase 1 changes only the
production input in the counterfactual; position weights, age curves, RB
continuous-age logic, role floors/rescues, and the global scale all remain
exactly current production behavior.

Outputs
-------
research/production-v2/production_v2_phase1_audit.json
research/production-v2/production_v2_phase1_audit.md

Usage
-----
python3 research/production-v2/production_v2_phase1_audit.py --selftest
python3 research/production-v2/production_v2_phase1_audit.py --write
python3 research/production-v2/production_v2_phase1_audit.py --check
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
from typing import Iterable

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
OFFENSE = {"QB", "RB", "WR", "TE"}
IDP = {"DL", "LB", "DB"}

# Deliberately benchmark-only starting assumptions. Phase 1 does not validate
# or authorize these constants for production.
HISTORY_WEIGHT = 0.45
FORWARD_WEIGHT = 0.55
OFFENSE_FP_WEIGHT = 0.50
REPLACEMENT_RANK = {
    "QB": 18,
    "RB": 32,
    "WR": 36,
    "TE": 15,
    "DL": 32,
    "LB": 32,
    "DB": 32,
}
PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55
GLOBAL_VALUE_SCALE = 55.0  # current live playerValue() scale; not recalibrated here

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

INDEX_HTML = REPO_ROOT / "index.html"
PPG_RESULTS = SCRIPTS / "ppg_results.json"
PPG_PIPELINE = SCRIPTS / "model" / "ppg_pipeline.py"
DURABILITY = SCRIPTS / "durability_results.json"
SLEEPER_TOTALS = SCRIPTS / "sleeper_2026_projections.json"
SLEEPER_RAW = SCRIPTS / "artifacts" / "generated" / "sleeper_2026_raw_categories.json"
FP_NORMALIZED = SCRIPTS / "fantasypros_api_normalized_2026.json"
IDENTITY = SCRIPTS / "identity_crosswalk.json"

OUTPUT_JSON = REPO_ROOT / "research" / "production-v2" / "production_v2_phase1_audit.json"
OUTPUT_MD = REPO_ROOT / "research" / "production-v2" / "production_v2_phase1_audit.md"


def normalize_name(value) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def finite_number(value):
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def percentile(values: Iterable[float], q: float):
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    q = max(0.0, min(1.0, q))
    idx = (len(vals) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    frac = idx - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def average_ranks(values):
    """Return 1-based average ranks, highest value = rank 1."""
    indexed = sorted(enumerate(values), key=lambda x: (-x[1], x[0]))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        # Positions are i+1 through j inclusive of the last 1-based slot j.
        avg = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg
        i = j
    return ranks


def pearson(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if den == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / den


def spearman(xs, ys):
    return pearson(average_ranks(xs), average_ranks(ys))


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def index_unique(rows, key_fn, label):
    out = {}
    duplicates = []
    for row in rows:
        key = key_fn(row)
        if key in (None, ""):
            continue
        key = str(key)
        if key in out:
            duplicates.append(key)
        else:
            out[key] = row
    if duplicates:
        sample = sorted(set(duplicates))[:10]
        raise RuntimeError(f"{label}: duplicate keys detected; sample={sample}")
    return out


def load_ppg_aliases():
    """Read the canonical PPG ALIASES dict without importing ppg_pipeline.

    ppg_pipeline imports requests because it can fetch live Sleeper data. Phase 1
    only needs its static alias source of truth, so parse the assignment with AST
    instead of executing network-capable module code.
    """
    tree = ast.parse(PPG_PIPELINE.read_text(encoding="utf-8"), filename=str(PPG_PIPELINE))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "ALIASES":
                    value = ast.literal_eval(node.value)
                    if not isinstance(value, dict):
                        raise RuntimeError("ppg_pipeline ALIASES is not a dict")
                    return {normalize_name(k): normalize_name(v) for k, v in value.items()}
    raise RuntimeError("Could not locate ALIASES in scripts/model/ppg_pipeline.py")


def canonical_ppg_key(key, aliases):
    norm = normalize_name(key)
    return aliases.get(norm, norm)


def _ppg_lineage_fingerprint(row):
    """Return the historical content that must agree for alias duplicates.

    ``ppg_pipeline.py`` can legitimately emit two rows with the same canonical
    player name when both an alias key and the canonical key exist in
    ``all_players.json``. Those rows should resolve to the same real Sleeper ID
    and carry the same historical stat line. The display/player key itself is
    deliberately excluded from this fingerprint.
    """
    ignored = {"player"}
    return {k: row.get(k) for k in sorted(row) if k not in ignored}


def build_ppg_lookup(rows, aliases):
    """Build a safe canonical-name lookup for historical PPG rows.

    Stable Sleeper ID is the identity authority. Alias/canonical duplicates are
    collapsed only when they point to the same stable ID AND their historical
    lineage is identical. Any real disagreement hard-fails rather than silently
    choosing a row.

    IMPORTANT: this lookup is only for matching current PLAYER_DB rows to their
    historical record. ``derive_history_constants`` still receives the original
    raw ``ppg_rows`` so Phase 1 preserves the existing canonical history math
    exactly and does not smuggle a history recalibration into this identity fix.
    """
    groups = {}
    for row in rows:
        raw_name = row.get("player")
        if not raw_name:
            continue
        key = canonical_ppg_key(raw_name, aliases)
        groups.setdefault(key, []).append(row)

    out = {}
    duplicate_groups = 0
    duplicate_rows_collapsed = 0

    for key, group in groups.items():
        if len(group) == 1:
            out[key] = group[0]
            continue

        duplicate_groups += 1
        sleeper_ids = {str(r.get("sleeper_id")) for r in group if r.get("sleeper_id") not in (None, "")}
        if len(sleeper_ids) != 1:
            raise RuntimeError(
                f"PPG results: canonical key {key!r} maps to conflicting stable Sleeper IDs: "
                f"{sorted(sleeper_ids) if sleeper_ids else 'none'}"
            )

        fingerprints = [_ppg_lineage_fingerprint(r) for r in group]
        first = fingerprints[0]
        if any(fp != first for fp in fingerprints[1:]):
            raise RuntimeError(
                f"PPG results: alias duplicates for {key!r} share Sleeper ID "
                f"{next(iter(sleeper_ids))} but historical lineage differs"
            )

        # Prefer the row whose stored name is already the canonical key, solely
        # for cleaner audit display. All lineage has already been proven equal.
        chosen = next(
            (r for r in group if normalize_name(r.get("player")) == key),
            group[0],
        )
        out[key] = chosen
        duplicate_rows_collapsed += len(group) - 1

    return out, {
        "raw_ppg_rows": len(rows),
        "canonical_ppg_keys": len(out),
        "alias_duplicate_groups_collapsed": duplicate_groups,
        "alias_duplicate_rows_collapsed": duplicate_rows_collapsed,
    }


def get_repo_modules():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from model import idp_v1_projection  # type: ignore
    from model import production_history_component  # type: ignore
    from projections import build_team_utility_lineup_projections as lineup_builder  # type: ignore
    from validation import snapshot_values  # type: ignore

    return idp_v1_projection, production_history_component, lineup_builder, snapshot_values


def validate_required_inputs():
    required = (
        INDEX_HTML,
        PPG_RESULTS,
        PPG_PIPELINE,
        DURABILITY,
        SLEEPER_TOTALS,
        SLEEPER_RAW,
        FP_NORMALIZED,
        IDENTITY,
    )
    missing = [str(p.relative_to(REPO_ROOT)) for p in required if not p.exists()]
    if missing:
        raise RuntimeError(f"missing required Phase-1 inputs: {missing}")


def build_forward_projection(
    pos,
    sid,
    sleeper_totals,
    sleeper_raw,
    fp_by_sleeper,
    idp_v1_projection,
):
    if not sid:
        return {
            "projection": None,
            "source": "missing_stable_sleeper_id",
            "sleeper_points": None,
            "fantasypros_points": None,
            "source_detail": {},
        }

    total_row = sleeper_totals.get(sid) or {}
    raw_row = sleeper_raw.get(sid) or {}
    fp_row = fp_by_sleeper.get(sid) or {}

    sleeper_points = finite_number(total_row.get("sleeper_2026_proj_total"))
    fp_points = finite_number(fp_row.get("trade_desk_normalized_points"))

    if pos in OFFENSE:
        if sleeper_points is not None and fp_points is not None:
            proj = OFFENSE_FP_WEIGHT * fp_points + (1 - OFFENSE_FP_WEIGHT) * sleeper_points
            source = "offense_benchmark_fp50_sleeper50"
        elif sleeper_points is not None:
            proj = sleeper_points
            source = "offense_sleeper_only"
        elif fp_points is not None:
            proj = fp_points
            source = "offense_fantasypros_only"
        else:
            proj = None
            source = "offense_no_forward_projection"
        return {
            "projection": proj,
            "source": source,
            "sleeper_points": sleeper_points,
            "fantasypros_points": fp_points,
            "source_detail": {},
        }

    if pos in IDP:
        sleeper_stats = raw_row.get("raw_category_season_totals")
        if not isinstance(sleeper_stats, dict):
            sleeper_stats = None
        fp_stats = fp_row.get("raw_stats_used")
        if not isinstance(fp_stats, dict):
            fp_stats = None

        result = idp_v1_projection.compute_v1_projection(
            fp_stats,
            sleeper_stats,
            old_proj=sleeper_points,
        )
        projection = finite_number(result.get("projection"))
        cohort = str(result.get("source_cohort") or "unknown")
        return {
            "projection": projection,
            "source": f"idp_v1_{cohort}" if projection is not None else "idp_no_forward_projection",
            "sleeper_points": sleeper_points,
            "fantasypros_points": fp_points,
            "source_detail": {
                "fp_active": bool(result.get("fp_active")),
                "sleeper_active": bool(result.get("sleeper_active")),
                "fp_tackle_active": bool(result.get("fp_tackle_active")),
                "sleeper_tackle_active": bool(result.get("sleeper_tackle_active")),
            },
        }

    raise ValueError(f"unsupported tracked position: {pos}")


def candidate_final_value(key, raw_candidate_pm, cfg, snapshot_values):
    info = cfg["player_db"][key]
    pos = info["pos"]
    age = info["age"]
    role = info["role"]

    effective_pm, raw_pm = snapshot_values.production_multiplier(
        key,
        role,
        {key: raw_candidate_pm},
        cfg["no_real_history"],
        cfg["role_mult"],
    )
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
    value = math.floor(100 * pw * age_mult * effective_pm * GLOBAL_VALUE_SCALE + 0.5)
    return {
        "value": value,
        "raw_prod_mult": raw_candidate_pm,
        "effective_prod_mult": effective_pm,
        "age_mult": age_mult,
        "elite_floor_applied": role == "Elite" and raw_candidate_pm < 0.65 and effective_pm == 0.65,
        "no_history_role_rescue_applied": (
            raw_candidate_pm <= 0.15
            and key in cfg["no_real_history"]
            and cfg["role_mult"].get(role, 1.0) > raw_candidate_pm
            and effective_pm == cfg["role_mult"].get(role, 1.0)
        ),
    }


def summarize_numeric(values):
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


def round_dict_numbers(obj, digits=6):
    if isinstance(obj, dict):
        return {k: round_dict_numbers(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_dict_numbers(v, digits) for v in obj]
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return None
        return round(obj, digits)
    return obj


def build_audit():
    validate_required_inputs()
    idp_v1_projection, history_mod, lineup_builder, snapshot_values = get_repo_modules()

    cfg = snapshot_values.load_from_html(INDEX_HTML)
    current_values = snapshot_values.compute_all_values(cfg)

    ppg_rows = read_json(PPG_RESULTS)
    durability = read_json(DURABILITY)
    sleeper_total_rows = read_json(SLEEPER_TOTALS)
    sleeper_raw_rows = read_json(SLEEPER_RAW)
    fp_doc = read_json(FP_NORMALIZED)
    crosswalk = read_json(IDENTITY)

    if not isinstance(ppg_rows, list):
        raise RuntimeError("scripts/ppg_results.json must be a list")
    if not isinstance(durability, dict):
        raise RuntimeError("scripts/durability_results.json must be an object")
    if not isinstance(sleeper_total_rows, list):
        raise RuntimeError("scripts/sleeper_2026_projections.json must be a list")
    if not isinstance(sleeper_raw_rows, list):
        raise RuntimeError("Sleeper raw category artifact must be a list")
    if not isinstance(fp_doc, dict) or not isinstance(fp_doc.get("players"), list):
        raise RuntimeError("FantasyPros normalized artifact missing players list")
    if not isinstance(crosswalk, list):
        raise RuntimeError("identity_crosswalk.json must be a list")

    aliases = load_ppg_aliases()
    ppg_by_key, ppg_lookup_stats = build_ppg_lookup(ppg_rows, aliases)
    sleeper_totals = index_unique(sleeper_total_rows, lambda r: r.get("sleeper_id"), "Sleeper totals")
    sleeper_raw = index_unique(sleeper_raw_rows, lambda r: r.get("sleeper_id"), "Sleeper raw")
    fp_by_sleeper, identity_stats = lineup_builder.build_fp_by_sleeper(fp_doc["players"], crosswalk)

    constants = history_mod.derive_history_constants(ppg_rows, durability)

    players = {}
    source_counts = Counter()
    coverage = {pos: Counter() for pos in TRACKED_POSITIONS}
    flags = Counter()

    for key in sorted(cfg["player_db"]):
        info = cfg["player_db"][key]
        pos = info["pos"]
        if pos not in TRACKED_POSITIONS:
            continue

        coverage[pos]["current_players"] += 1
        ppg_lookup_key = canonical_ppg_key(key, aliases)
        ppg = ppg_by_key.get(ppg_lookup_key)
        if ppg:
            coverage[pos]["ppg_row"] += 1
        else:
            flags["missing_ppg_row"] += 1

        sid = None
        if ppg and ppg.get("sleeper_id") is not None:
            sid = str(ppg.get("sleeper_id"))
            coverage[pos]["stable_sleeper_id"] += 1
        else:
            flags["missing_stable_sleeper_id"] += 1

        if ppg and str(ppg.get("pos")) != pos:
            flags["ppg_position_mismatch_vs_current_player_db"] += 1

        # Preserve canonical history behavior exactly in Phase 1. Potential
        # zero-game semantics are surfaced explicitly rather than silently fixed.
        history = history_mod.compute_history_for_player(pos, ppg, constants)
        if int(history.get("games_played_2025") or 0) == 0:
            flags["zero_game_history_records"] += 1
            if history.get("shrinkage_note") == "real":
                flags["zero_game_rows_treated_as_real_by_canonical_history"] += 1

        forward = build_forward_projection(
            pos,
            sid,
            sleeper_totals,
            sleeper_raw,
            fp_by_sleeper,
            idp_v1_projection,
        )
        source_counts[forward["source"]] += 1

        if sid and sid in sleeper_totals:
            coverage[pos]["sleeper_projection_row"] += 1
        if sid and sid in fp_by_sleeper:
            coverage[pos]["fantasypros_projection_row"] += 1
        if sid and sid in sleeper_totals and sid in fp_by_sleeper:
            coverage[pos]["both_provider_rows"] += 1
        if forward["projection"] is not None:
            coverage[pos]["usable_forward_projection"] += 1
        else:
            flags["missing_forward_projection"] += 1

        history_component = finite_number(history.get("history_component"))
        forward_projection = finite_number(forward.get("projection"))
        combined = None
        if history_component is not None and forward_projection is not None:
            combined = HISTORY_WEIGHT * history_component + FORWARD_WEIGHT * forward_projection
            coverage[pos]["phase1_combined"] += 1
        elif forward_projection is not None:
            # Should be rare because canonical history has a position-mean fallback,
            # but keep the state explicit rather than silently changing weighting.
            flags["forward_present_history_missing"] += 1
        elif history_component is not None:
            flags["history_present_forward_missing"] += 1

        current = current_values[key]
        players[key] = {
            "key": key,
            "pos": pos,
            "age": info["age"],
            "role": info["role"],
            "sleeper_id": sid,
            "ppg_lookup_key": ppg_lookup_key,
            "history": history,
            "forward": forward,
            "phase1_combined_points": combined,
            "current": {
                "raw_prod_mult": cfg["prod_mult"].get(key),
                "effective_prod_mult": current["prod_mult"],
                "age_mult": current["age_mult"],
                "fundamental_value": current["value"],
                "has_raw_prod_mult": key in cfg["prod_mult"],
                "no_real_production_history": key in cfg["no_real_history"],
            },
        }

    # Baselines are built over the same current PLAYER_DB candidate cohort.
    baselines = {}
    for pos in TRACKED_POSITIONS:
        cohort = [r for r in players.values() if r["pos"] == pos and r["phase1_combined_points"] is not None]
        cohort.sort(key=lambda r: (-r["phase1_combined_points"], r["key"]))
        rank = REPLACEMENT_RANK[pos]
        if len(cohort) < rank:
            raise RuntimeError(
                f"{pos}: only {len(cohort)} complete candidate records; cannot build replacement rank {rank}"
            )
        anchor = cohort[rank - 1]
        baseline_value = float(anchor["phase1_combined_points"])
        if baseline_value <= 0:
            raise RuntimeError(f"{pos}: non-positive Phase-1 baseline {baseline_value}")
        baselines[pos] = {
            "rank": rank,
            "player": anchor["key"],
            "combined_points": baseline_value,
            "cohort_size": len(cohort),
        }

    # Convert transparent combined points to benchmark PM and final FV using the
    # CURRENT production floors + age/position architecture.
    for key, rec in players.items():
        combined = rec["phase1_combined_points"]
        if combined is None:
            rec["candidate"] = None
            continue
        pos = rec["pos"]
        baseline = baselines[pos]["combined_points"]
        ratio = combined / baseline
        raw_pm = clamp(PM_INTERCEPT + PM_RATIO_SLOPE * ratio, PM_MIN, PM_MAX)
        candidate = candidate_final_value(key, raw_pm, cfg, snapshot_values)
        candidate["production_ratio_to_phase1_baseline"] = ratio
        candidate["phase1_baseline_points"] = baseline
        rec["candidate"] = candidate
        coverage[pos]["candidate_final_value"] += 1
        if candidate["elite_floor_applied"]:
            flags["candidate_elite_floor_applied"] += 1
        if candidate["no_history_role_rescue_applied"]:
            flags["candidate_no_history_role_rescue_applied"] += 1

    # Rank current and candidate values on the exact common candidate cohort.
    rank_summary = {}
    movement_summary = {}
    for pos in TRACKED_POSITIONS:
        cohort = [r for r in players.values() if r["pos"] == pos and r.get("candidate")]
        current_sorted = sorted(cohort, key=lambda r: (-r["current"]["fundamental_value"], r["key"]))
        candidate_sorted = sorted(cohort, key=lambda r: (-r["candidate"]["value"], r["key"]))
        current_rank = {r["key"]: i + 1 for i, r in enumerate(current_sorted)}
        candidate_rank = {r["key"]: i + 1 for i, r in enumerate(candidate_sorted)}

        for r in cohort:
            cur_v = r["current"]["fundamental_value"]
            cand_v = r["candidate"]["value"]
            r["comparison"] = {
                "fundamental_value_change": cand_v - cur_v,
                "fundamental_value_change_pct": ((cand_v - cur_v) / cur_v) if cur_v else None,
                "effective_prod_mult_change": r["candidate"]["effective_prod_mult"] - r["current"]["effective_prod_mult"],
                "current_rank_in_common_cohort": current_rank[r["key"]],
                "candidate_rank_in_common_cohort": candidate_rank[r["key"]],
                "rank_change": current_rank[r["key"]] - candidate_rank[r["key"]],
            }

        current_vec = [r["current"]["fundamental_value"] for r in cohort]
        candidate_vec = [r["candidate"]["value"] for r in cohort]
        rho = spearman(current_vec, candidate_vec)
        topn = min(REPLACEMENT_RANK[pos], len(cohort))
        cur_top = {r["key"] for r in current_sorted[:topn]}
        cand_top = {r["key"] for r in candidate_sorted[:topn]}
        rank_summary[pos] = {
            "n": len(cohort),
            "spearman_current_vs_phase1": rho,
            "top_n": topn,
            "top_n_overlap_count": len(cur_top & cand_top),
            "top_n_overlap_share": len(cur_top & cand_top) / topn if topn else None,
            "max_absolute_rank_change": max((abs(r["comparison"]["rank_change"]) for r in cohort), default=0),
        }

        pm_deltas = [r["comparison"]["effective_prod_mult_change"] for r in cohort]
        value_pct = [r["comparison"]["fundamental_value_change_pct"] for r in cohort if r["comparison"]["fundamental_value_change_pct"] is not None]
        movement_summary[pos] = {
            "effective_prod_mult_delta": summarize_numeric(pm_deltas),
            "fundamental_value_change_pct": summarize_numeric(value_pct),
        }

    mover_rows = []
    for rec in players.values():
        if not rec.get("candidate") or not rec.get("comparison"):
            continue
        pct = rec["comparison"]["fundamental_value_change_pct"]
        if pct is None:
            continue
        mover_rows.append({
            "player": rec["key"],
            "pos": rec["pos"],
            "current_value": rec["current"]["fundamental_value"],
            "phase1_value": rec["candidate"]["value"],
            "change_pct": pct,
            "current_effective_pm": rec["current"]["effective_prod_mult"],
            "phase1_effective_pm": rec["candidate"]["effective_prod_mult"],
            "rank_change": rec["comparison"]["rank_change"],
            "forward_source": rec["forward"]["source"],
            "history_note": rec["history"]["shrinkage_note"],
        })
    mover_rows.sort(key=lambda r: (-abs(r["change_pct"]), r["player"]))

    current_tracked = sum(1 for r in players.values())
    candidate_count = sum(1 for r in players.values() if r.get("candidate"))

    result = {
        "schema_version": 1,
        "phase": "Production V2 Phase 1",
        "status": "RESEARCH_ONLY_NO_PRODUCTION_CHANGE_AUTHORIZED",
        "purpose": (
            "Validate production-data lineage, identity joins, coverage, and blast radius using a transparent "
            "benchmark reconstruction before calibrating any Production V2 coefficient."
        ),
        "production_mutation_authorized": False,
        "benchmark_assumptions": {
            "history_component": "scripts/model/production_history_component.py, unchanged canonical V1 history math",
            "offense_forward": {
                "both_sources": "50% FantasyPros Trade-Desk-normalized points + 50% Sleeper league-scored points",
                "single_source": "use the one available source",
                "calibrated": False,
            },
            "idp_forward": "scripts/model/idp_v1_projection.py canonical category-level V1 ensemble",
            "history_weight": HISTORY_WEIGHT,
            "forward_weight": FORWARD_WEIGHT,
            "replacement_rank": REPLACEMENT_RANK,
            "prod_mult_transform": {
                "formula": "clamp(-0.10 + 0.75 * (combined / position_baseline), 0.15, 1.55)",
                "calibrated_for_v2": False,
            },
            "current_components_held_fixed": [
                "POSITION_WEIGHT",
                "AGE_CURVE",
                "RB continuous/fractional-age model",
                "ROLE_MULT floors/rescues",
                "QB post-peak floor",
                "LB post-peak decay power",
                "global player-value scale 55",
            ],
        },
        "input_sha256": {
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
            str(PPG_RESULTS.relative_to(REPO_ROOT)): sha256(PPG_RESULTS),
            str(PPG_PIPELINE.relative_to(REPO_ROOT)): sha256(PPG_PIPELINE),
            str(DURABILITY.relative_to(REPO_ROOT)): sha256(DURABILITY),
            str(SLEEPER_TOTALS.relative_to(REPO_ROOT)): sha256(SLEEPER_TOTALS),
            str(SLEEPER_RAW.relative_to(REPO_ROOT)): sha256(SLEEPER_RAW),
            str(FP_NORMALIZED.relative_to(REPO_ROOT)): sha256(FP_NORMALIZED),
            str(IDENTITY.relative_to(REPO_ROOT)): sha256(IDENTITY),
        },
        "identity_stats": {
            **identity_stats,
            "ppg_lookup": ppg_lookup_stats,
        },
        "data_quality": {
            "current_tracked_players": current_tracked,
            "phase1_candidate_players": candidate_count,
            "candidate_coverage_share": candidate_count / current_tracked if current_tracked else None,
            "flags": dict(sorted(flags.items())),
            "forward_source_counts": dict(sorted(source_counts.items())),
        },
        "coverage_by_position": {
            pos: dict(sorted(coverage[pos].items())) for pos in TRACKED_POSITIONS
        },
        "history_constants": {
            "shrinkage_k_by_position": constants.shrinkage_k_by_position,
            "position_mean_ppg": constants.position_mean_ppg,
            "position_median_availability_2025": constants.position_median_availability_2025,
            "own_weight_durability_by_position": constants.own_weight_durability_by_position,
        },
        "phase1_baselines": baselines,
        "movement_summary_by_position": movement_summary,
        "rank_stability_by_position": rank_summary,
        "largest_absolute_final_value_movers": mover_rows[:40],
        "players": {k: players[k] for k in sorted(players)},
        "next_step_if_data_quality_passes": (
            "Phase 2: calibrate provider blend and history-vs-forward weights out of sample / historically where valid; "
            "do not deploy Phase-1 benchmark coefficients."
        ),
    }
    return round_dict_numbers(result)


def pct(x, digits=1):
    if x is None:
        return "—"
    return f"{100 * x:.{digits}f}%"


def num(x, digits=3):
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def build_markdown(result):
    dq = result["data_quality"]
    lines = [
        "# Production V2 — Phase 1 Lineage & Benchmark Audit",
        "",
        "## Decision",
        "",
        "**RESEARCH ONLY — no production change is authorized by this audit.**",
        "",
        "Phase 1 is deliberately a lineage/coverage/blast-radius audit, not a claim that the benchmark formula is optimal.",
        "It freezes the current player-value architecture and swaps only the production input in a counterfactual reconstruction.",
        "",
        f"- Current tracked players: **{dq['current_tracked_players']}**",
        f"- Phase-1 candidate values built: **{dq['phase1_candidate_players']}** ({pct(dq['candidate_coverage_share'])})",
        "- Production files mutated: **0**",
        "- `index.html` mutated: **No**",
        "",
        "## Benchmark formula used only for Phase 1",
        "",
        "1. **History:** canonical `scripts/model/production_history_component.py` (existing 2025 shrinkage + durability math, unchanged).",
        "2. **Offense forward projection:** 50/50 Trade-Desk-normalized FantasyPros + league-scored Sleeper when both exist; single-source fallback otherwise. **Not calibrated.**",
        "3. **IDP forward projection:** canonical `scripts/model/idp_v1_projection.py` V1 category ensemble.",
        "4. **History vs forward:** 45% / 55%. **Inherited benchmark, not calibrated for V2.**",
        "5. **Normalization:** existing research replacement ranks and `clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)`. **Benchmark only.**",
        "6. **Held fixed:** current position weights, age curves, RB continuous age, role floors/rescues, QB/LB decline rules, and global scale.",
        "",
        "## Data coverage",
        "",
        "| Pos | Current | PPG row | Stable Sleeper ID | Sleeper proj | FP proj | Both rows | Usable forward | Candidate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for pos in TRACKED_POSITIONS:
        c = result["coverage_by_position"].get(pos, {})
        lines.append(
            f"| {pos} | {c.get('current_players',0)} | {c.get('ppg_row',0)} | {c.get('stable_sleeper_id',0)} | "
            f"{c.get('sleeper_projection_row',0)} | {c.get('fantasypros_projection_row',0)} | {c.get('both_provider_rows',0)} | "
            f"{c.get('usable_forward_projection',0)} | {c.get('candidate_final_value',0)} |"
        )

    lines += [
        "",
        "## Data-quality flags",
        "",
    ]
    flags = dq.get("flags") or {}
    if flags:
        for key, value in flags.items():
            lines.append(f"- `{key}`: **{value}**")
    else:
        lines.append("- None.")

    lines += [
        "",
        "### Forward projection source counts",
        "",
    ]
    for key, value in (dq.get("forward_source_counts") or {}).items():
        lines.append(f"- `{key}`: **{value}**")

    lines += [
        "",
        "## Phase-1 position baselines",
        "",
        "These are diagnostic benchmark anchors only; Phase 2 will test whether this normalization should survive at all.",
        "",
        "| Pos | Rank | Anchor player | Combined points | Candidate cohort |",
        "|---|---:|---|---:|---:|",
    ]
    for pos in TRACKED_POSITIONS:
        b = result["phase1_baselines"][pos]
        lines.append(
            f"| {pos} | {b['rank']} | {b['player']} | {b['combined_points']:.2f} | {b['cohort_size']} |"
        )

    lines += [
        "",
        "## Current vs Phase-1 movement",
        "",
        "| Pos | N | Median FV change | P90 abs FV change | P95 abs FV change | Max abs FV change | Median abs PM delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pos in TRACKED_POSITIONS:
        m = result["movement_summary_by_position"][pos]
        fv = m["fundamental_value_change_pct"]
        pm = m["effective_prod_mult_delta"]
        lines.append(
            f"| {pos} | {fv.get('n',0)} | {pct(fv.get('median'))} | {pct(fv.get('p90_abs'))} | "
            f"{pct(fv.get('p95_abs'))} | {pct(fv.get('max_abs'))} | {num(pm.get('median_abs'),4)} |"
        )

    lines += [
        "",
        "## Rank stability",
        "",
        "Ranks are measured on the exact common current/candidate cohort for each position.",
        "",
        "| Pos | N | Spearman | Top-N | Top-N overlap | Max rank move |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for pos in TRACKED_POSITIONS:
        r = result["rank_stability_by_position"][pos]
        lines.append(
            f"| {pos} | {r['n']} | {num(r.get('spearman_current_vs_phase1'),4)} | {r['top_n']} | "
            f"{pct(r.get('top_n_overlap_share'))} | {r['max_absolute_rank_change']} |"
        )

    lines += [
        "",
        "## Largest absolute final-value movers",
        "",
        "Large movement is a **diagnostic signal**, not evidence that Phase 1 is right. These rows are where we inspect lineage first.",
        "",
        "| Player | Pos | Current | Phase 1 | Change | PM current→P1 | Rank move | Forward source | History note |",
        "|---|---|---:|---:|---:|---|---:|---|---|",
    ]
    for r in result["largest_absolute_final_value_movers"][:30]:
        pm_text = f"{r['current_effective_pm']:.3f}→{r['phase1_effective_pm']:.3f}"
        lines.append(
            f"| {r['player']} | {r['pos']} | {r['current_value']} | {r['phase1_value']} | {pct(r['change_pct'])} | "
            f"{pm_text} | {r['rank_change']:+d} | {r['forward_source']} | {r['history_note']} |"
        )

    lines += [
        "",
        "## What Phase 1 does **not** prove",
        "",
        "- It does **not** prove 50/50 FantasyPros/Sleeper is the best offensive projection blend.",
        "- It does **not** prove 45/55 history/forward is the best weighting.",
        "- It does **not** prove the replacement-rank baseline or linear `prod_mult` transform is correct.",
        "- It does **not** change the current production table.",
        "- It does **not** use market value to train Fundamental Value.",
        "",
        "## Next step",
        "",
        "If identity/coverage checks are clean, Phase 2 will calibrate **provider blend** and **history-vs-forward weighting** using only evidence that is temporally valid. The Phase-1 benchmark will not be deployed.",
        "",
    ]
    return "\n".join(lines)


def json_text(result):
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def run_selftest():
    assert normalize_name("D'Andre Swift") == "dandre swift"
    assert normalize_name("Henry To'oTo'o") == "henry tootoo"
    assert normalize_name("Amon-Ra St. Brown") == "amonra st brown"
    aliases = {"a st brown": "amonra st brown"}
    assert canonical_ppg_key("a st brown", aliases) == "amonra st brown"

    # Real Phase-1 regression: ppg_pipeline can emit both an alias row and a
    # canonical-name row for the same real player. Same stable ID + identical
    # history must collapse safely.
    duplicate_fixture = [
        {
            "player": "a st brown", "pos": "WR", "sleeper_id": "7547",
            "games_played": 17, "true_ppg": 16.64, "weekly_points": [10.0, 20.0],
        },
        {
            "player": "amonra st brown", "pos": "WR", "sleeper_id": "7547",
            "games_played": 17, "true_ppg": 16.64, "weekly_points": [10.0, 20.0],
        },
    ]
    lookup, stats = build_ppg_lookup(duplicate_fixture, aliases)
    assert list(lookup) == ["amonra st brown"]
    assert lookup["amonra st brown"]["sleeper_id"] == "7547"
    assert stats["alias_duplicate_groups_collapsed"] == 1
    assert stats["alias_duplicate_rows_collapsed"] == 1

    # Same canonical name with conflicting stable IDs must remain a hard fail.
    conflict_fixture = [
        {"player": "a st brown", "pos": "WR", "sleeper_id": "7547", "true_ppg": 16.64},
        {"player": "amonra st brown", "pos": "WR", "sleeper_id": "9999", "true_ppg": 16.64},
    ]
    try:
        build_ppg_lookup(conflict_fixture, aliases)
        raise AssertionError("expected conflicting stable Sleeper IDs to hard-fail")
    except RuntimeError as exc:
        assert "conflicting stable Sleeper IDs" in str(exc)

    assert clamp(-1, 0.15, 1.55) == 0.15
    assert clamp(2, 0.15, 1.55) == 1.55
    assert abs(clamp(PM_INTERCEPT + PM_RATIO_SLOPE * 1.0, PM_MIN, PM_MAX) - 0.65) < 1e-12

    # At replacement ratio=1 the benchmark PM is 0.65. A ratio of 2 reaches
    # 1.40, still below the 1.55 cap.
    assert abs(PM_INTERCEPT + PM_RATIO_SLOPE * 2.0 - 1.40) < 1e-12

    # Average-rank tie handling and Spearman sanity.
    assert average_ranks([10, 5, 5]) == [1.0, 2.5, 2.5]
    assert abs(spearman([3, 2, 1], [30, 20, 10]) - 1.0) < 1e-12
    assert abs(spearman([3, 2, 1], [10, 20, 30]) + 1.0) < 1e-12

    assert abs(percentile([0, 10], 0.5) - 5) < 1e-12

    # Benchmark weighting must sum to one; this is a diagnostic invariant,
    # not an assertion that the weights are optimal.
    assert abs(HISTORY_WEIGHT + FORWARD_WEIGHT - 1.0) < 1e-12
    assert 0 <= OFFENSE_FP_WEIGHT <= 1

    print("PASS Production V2 Phase-1 standalone self-test.")


def write_outputs(result):
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json_text(result), encoding="utf-8")
    OUTPUT_MD.write_text(build_markdown(result), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


def check_outputs(result):
    expected_json = json_text(result)
    expected_md = build_markdown(result)
    problems = []
    if not OUTPUT_JSON.exists():
        problems.append(str(OUTPUT_JSON.relative_to(REPO_ROOT)))
    elif OUTPUT_JSON.read_text(encoding="utf-8") != expected_json:
        problems.append(str(OUTPUT_JSON.relative_to(REPO_ROOT)) + " (stale)")
    if not OUTPUT_MD.exists():
        problems.append(str(OUTPUT_MD.relative_to(REPO_ROOT)))
    elif OUTPUT_MD.read_text(encoding="utf-8") != expected_md:
        problems.append(str(OUTPUT_MD.relative_to(REPO_ROOT)) + " (stale)")
    if problems:
        raise RuntimeError("Phase-1 outputs missing/stale: " + ", ".join(problems))
    print("PASS Production V2 Phase-1 output check.")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    result = build_audit()
    if args.write:
        write_outputs(result)
    else:
        check_outputs(result)


if __name__ == "__main__":
    main()

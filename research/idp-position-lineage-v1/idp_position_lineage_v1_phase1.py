#!/usr/bin/env python3
"""IDP Position Lineage V1 Phase 1 — frozen lineage migration audit."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
RESEARCH = ROOT / "research" / "idp-position-lineage-v1"

RELEASE_DIR = ROOT / "model" / "releases" / "idp-v1"
RELEASE_MANIFEST = RELEASE_DIR / "idp_v1_release_manifest.json"
FROZEN_CANDIDATE = RELEASE_DIR / "idp_v1_model_delta_transport_candidate.json"
FROZEN_HISTORY = RELEASE_DIR / "production_history_components.json"
FINAL_V1_VALIDATION = RELEASE_DIR / "idp_v1_final_deployment_validation.json"
INDEX = ROOT / "index.html"
SNAPSHOT_VALUES = ROOT / "scripts" / "validation" / "snapshot_values.py"
LEAGUE_ROSTERS = ROOT / "data" / "league_rosters.json"
FREE_AGENTS = ROOT / "data" / "free_agents.json"
PLAYER_POSITIONS = (
    ROOT / "scripts" / "artifacts" / "generated" / "player_positions.json"
)
STARTER_AUDIT = (
    ROOT / "research" / "team-utility"
    / "team_utility_starter_objective_audit.py"
)

PREREG_JSON = RESEARCH / "phase1_preregistration.json"
PREREG_MD = RESEARCH / "phase1_preregistration.md"
OUT_JSON = RESEARCH / "idp_position_lineage_v1_phase1.json"
OUT_MD = RESEARCH / "idp_position_lineage_v1_phase1.md"
MANIFEST = RESEARCH / "phase1_manifest.json"

EXPECTED_MISMATCHES = 46
HISTORY_WEIGHT = 0.45
PROJECTION_WEIGHT = 0.55
PM_INTERCEPT = -0.10
PM_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55
IDP = {"DL", "LB", "DB"}

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def finite(value):
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def summarize(values):
    vals = sorted(
        float(v) for v in values
        if v is not None and math.isfinite(float(v))
    )
    if not vals:
        return {"n": 0}
    def pct(q):
        if len(vals) == 1:
            return vals[0]
        x = (len(vals) - 1) * q
        lo = int(math.floor(x))
        hi = int(math.ceil(x))
        if lo == hi:
            return vals[lo]
        f = x - lo
        return vals[lo] * (1 - f) + vals[hi] * f
    return {
        "n": len(vals),
        "mean": statistics.fmean(vals),
        "median": statistics.median(vals),
        "p10": pct(0.10),
        "p90": pct(0.90),
        "p95": pct(0.95),
        "min": vals[0],
        "max": vals[-1],
    }

def load_snapshot_module():
    sys.path.insert(0, str(ROOT / "scripts" / "validation"))
    import snapshot_values
    return snapshot_values

def load_current_production_cfg(snapshot_values):
    """Mirror the production valuation universe, including live rosters.

    index.html is the baked source of truth, but the browser also merges
    current league-roster rows at runtime. Some frozen IDP V1 lineage
    targets (for example Bradley Chubb) are legitimate current roster
    players whose key is not baked into static PLAYER_DB. Phase 1 must
    therefore evaluate the same merged universe rather than crashing or
    silently dropping those rows.
    """
    sys.path.insert(0, str(ROOT / "research" / "team-utility"))
    import team_utility_starter_objective_audit as starter_audit

    base_cfg = snapshot_values.load_from_html(INDEX)
    roster_doc = read_json(LEAGUE_ROSTERS)
    cfg = starter_audit.merge_live_league_into_cfg(base_cfg, roster_doc)

    unresolved = (
        cfg.get("live_merge_stats", {}).get("unresolved_positions") or []
    )
    if unresolved:
        raise RuntimeError(
            "production-parity live roster merge has unresolved positions: "
            + json.dumps(unresolved[:20], sort_keys=True)
        )
    return cfg

def classify_target_scope(mismatch_rows, current_values, free_doc):
    """Classify frozen targets without assuming they still render in core."""
    free_by_id = {
        str(r.get("player_id")): r
        for r in (free_doc.get("free_agents") or [])
        if r.get("player_id") not in (None, "")
    }
    out = {}
    for key, row in mismatch_rows:
        sid = row.get("sleeper_id")
        sid = str(sid) if sid not in (None, "") else None
        if key in current_values:
            out[key] = {
                "scope": "current_core",
                "free_agent_row": None,
            }
        elif sid and sid in free_by_id:
            out[key] = {
                "scope": "free_agent_only",
                "free_agent_row": free_by_id[sid],
            }
        else:
            out[key] = {
                "scope": "not_currently_rendered",
                "free_agent_row": None,
            }
    return out

def recompute_history(current_pos, old_history, frozen_history_doc):
    n = int(old_history.get("games_played_2025") or 0)
    true_ppg = finite(old_history.get("true_ppg_2025"))

    k = finite(
        frozen_history_doc["shrinkage_k_by_position"].get(current_pos)
    )
    mean_ppg = finite(
        frozen_history_doc["position_mean_ppg"].get(current_pos)
    )
    median_avail = finite(
        frozen_history_doc[
            "position_median_availability_2025"
        ].get(current_pos)
    )
    own_weight = finite(
        frozen_history_doc[
            "own_weight_durability_by_position"
        ].get(current_pos)
    )
    if own_weight is None:
        own_weight = 0.0

    if true_ppg is not None and k is not None and mean_ppg is not None:
        shrunk_ppg = (n * true_ppg + k * mean_ppg) / (n + k)
        shrinkage_note = "real"
    elif mean_ppg is not None:
        shrunk_ppg = mean_ppg
        shrinkage_note = "no_2025_data_full_shrink_to_position_mean"
    else:
        shrunk_ppg = None
        shrinkage_note = "no_position_mean_available"

    has_history = true_ppg is not None
    own_avail = min(1.0, n / 17.0) if has_history else None
    applied_own_weight = own_weight if has_history else 0.0

    if median_avail is not None:
        if has_history:
            projected_avail = (
                applied_own_weight * own_avail
                + (1.0 - applied_own_weight) * median_avail
            )
        else:
            projected_avail = median_avail
        projected_games = projected_avail * 17.0
    else:
        projected_avail = None
        projected_games = None

    component = (
        shrunk_ppg * projected_games
        if shrunk_ppg is not None and projected_games is not None
        else None
    )
    return {
        "games_played_2025": n,
        "true_ppg_2025": true_ppg,
        "shrinkage_k_used": k,
        "position_mean_ppg": mean_ppg,
        "shrunk_ppg": shrunk_ppg,
        "shrinkage_note": shrinkage_note,
        "own_weight_durability": applied_own_weight,
        "own_avail_2025": own_avail,
        "position_median_avail_2025": median_avail,
        "durability_projected_avail_2026": projected_avail,
        "durability_projected_games_2026": projected_games,
        "history_component": component,
    }

def ordinal_ranks(values, keys):
    ordered = sorted(
        keys,
        key=lambda k: (-int(values[k]["value"]), k),
    )
    return {key: i + 1 for i, key in enumerate(ordered)}

def verify_frozen_release_hashes(manifest):
    mismatches = []
    for rel, expected in manifest[
        "immutable_release_artifacts"
    ].items():
        path = ROOT / rel
        actual = sha256(path) if path.exists() else "missing"
        if actual != expected:
            mismatches.append({
                "path": rel,
                "expected": expected,
                "actual": actual,
            })
    return mismatches

def build_result():
    snapshot_values = load_snapshot_module()

    release_manifest = read_json(RELEASE_MANIFEST)
    frozen = read_json(FROZEN_CANDIDATE)
    history = read_json(FROZEN_HISTORY)
    final_v1 = read_json(FINAL_V1_VALIDATION)
    cfg = load_current_production_cfg(snapshot_values)
    current_values = snapshot_values.compute_all_values(cfg)
    position_map = read_json(PLAYER_POSITIONS)
    free_doc = read_json(FREE_AGENTS)

    hash_mismatches = verify_frozen_release_hashes(release_manifest)

    assert frozen["replacement_rank"] == 32
    assert abs(float(frozen["history_weight"]) - HISTORY_WEIGHT) < 1e-12
    assert abs(
        float(frozen["projection_weight"]) - PROJECTION_WEIGHT
    ) < 1e-12

    baselines = {
        str(k): float(v)
        for k, v in frozen[
            "new_model_baseline_by_position"
        ].items()
    }
    assert set(IDP).issubset(baselines)

    mismatch_rows = []
    for key, row in frozen["players"].items():
        legacy_pos = str(row.get("legacy_model_position") or "")
        current_pos = str(row.get("current_valuation_position") or "")
        if (
            legacy_pos in IDP
            and current_pos in IDP
            and legacy_pos != current_pos
        ):
            mismatch_rows.append((key, row))

    mismatch_rows.sort(key=lambda item: item[0])
    mismatch_keys = {key for key, _ in mismatch_rows}

    target_scope = classify_target_scope(
        mismatch_rows, current_values, free_doc
    )
    live_target_keys = {
        key
        for key, meta in target_scope.items()
        if meta["scope"] == "current_core"
    }
    free_agent_only_keys = {
        key
        for key, meta in target_scope.items()
        if meta["scope"] == "free_agent_only"
    }
    nonrendered_keys = {
        key
        for key, meta in target_scope.items()
        if meta["scope"] == "not_currently_rendered"
    }

    current_position_mismatches = []
    live_core_position_mismatches = []
    free_agent_position_mismatches = []
    deployed_raw_mismatches = []
    duplicate_sleeper_ids = []
    sleeper_seen = {}

    for key, row in mismatch_rows:
        frozen_current_pos = row["current_valuation_position"]
        mapped_pos = position_map.get(key)
        if mapped_pos != frozen_current_pos:
            current_position_mismatches.append({
                "key": key,
                "frozen_current_position": frozen_current_pos,
                "current_generated_position": mapped_pos,
            })

        scope_meta = target_scope[key]
        if scope_meta["scope"] == "current_core":
            info = cfg["player_db"].get(key)
            if (
                not info
                or info.get("pos") != frozen_current_pos
            ):
                live_core_position_mismatches.append({
                    "key": key,
                    "frozen_current_position": frozen_current_pos,
                    "live_core_position": (
                        info.get("pos") if info else None
                    ),
                })

            deployed = finite(cfg["prod_mult"].get(key))
            frozen_deployed = finite(row.get("candidate_prod_mult"))
            if (
                deployed is None
                or frozen_deployed is None
                or abs(deployed - frozen_deployed) > 1e-9
            ):
                deployed_raw_mismatches.append({
                    "key": key,
                    "current_raw_prod_mult": deployed,
                    "frozen_v1_deployed_prod_mult": frozen_deployed,
                })

        elif scope_meta["scope"] == "free_agent_only":
            fa = scope_meta["free_agent_row"] or {}
            fa_pos = str(fa.get("pos") or "")
            if fa_pos and fa_pos != frozen_current_pos:
                free_agent_position_mismatches.append({
                    "key": key,
                    "sleeper_id": row.get("sleeper_id"),
                    "frozen_current_position": frozen_current_pos,
                    "current_free_agent_position": fa_pos,
                })

        sid = row.get("sleeper_id")
        if sid not in (None, ""):
            sid = str(sid)
            if sid in sleeper_seen and sleeper_seen[sid] != key:
                duplicate_sleeper_ids.append({
                    "sleeper_id": sid,
                    "keys": [sleeper_seen[sid], key],
                })
            sleeper_seen[sid] = key

    candidate_prod = dict(cfg["prod_mult"])
    rows = []
    hold_counts = {}
    floor_guarded = []
    recomputed = 0

    for key, row in mismatch_rows:
        legacy_pos = row["legacy_model_position"]
        current_pos = row["current_valuation_position"]
        live_raw = finite(cfg["prod_mult"].get(key))
        frozen_hist = history["players"].get(key)
        v1_projection = finite(row.get("v1_projection"))
        legacy_combined = finite(row.get("new_model_combined"))

        reason = None
        current_scope = target_scope[key]["scope"]
        current_history = None
        current_combined = None
        legacy_clean_pm = None
        current_clean_pm = None
        lineage_delta = None
        proposed_raw = live_raw
        final_raw = live_raw
        guarded = False

        if current_scope != "current_core":
            reason = (
                "current_scope_hold_" + current_scope
            )
        elif frozen_hist is None:
            reason = "missing_frozen_history_record"
        elif (
            live_raw is None
            or v1_projection is None
            or legacy_combined is None
        ):
            reason = "no_comparable_frozen_v1_projection_or_model"
        else:
            current_history = recompute_history(
                current_pos, frozen_hist, history
            )
            current_history_component = finite(
                current_history.get("history_component")
            )
            if current_history_component is None:
                reason = "current_position_history_unavailable"
            else:
                current_combined = (
                    HISTORY_WEIGHT * current_history_component
                    + PROJECTION_WEIGHT * v1_projection
                )
                legacy_ratio = (
                    legacy_combined / baselines[legacy_pos]
                )
                current_ratio = (
                    current_combined / baselines[current_pos]
                )
                legacy_clean_pm = clamp(
                    PM_INTERCEPT + PM_SLOPE * legacy_ratio,
                    PM_MIN,
                    PM_MAX,
                )
                current_clean_pm = clamp(
                    PM_INTERCEPT + PM_SLOPE * current_ratio,
                    PM_MIN,
                    PM_MAX,
                )
                lineage_delta = current_clean_pm - legacy_clean_pm
                proposed_raw = clamp(
                    live_raw + lineage_delta,
                    PM_MIN,
                    PM_MAX,
                )

                info = cfg["player_db"].get(key)
                if info is None:
                    reason = "missing_current_production_player_db_row"
                    proposed_raw = live_raw
                    final_raw = live_raw
                else:
                    role = info["role"]
                    role_estimate = float(
                        cfg["role_mult"].get(role, 1.0)
                    )
                    no_history = key in cfg["no_real_history"]

                if (
                    info is not None
                    and
                    no_history
                    and live_raw <= PM_MIN + 1e-12
                    and proposed_raw > PM_MIN + 1e-12
                    and proposed_raw < role_estimate - 1e-12
                ):
                    final_raw = live_raw
                    guarded = True
                    reason = "exact_floor_no_history_rescue_guard"
                    floor_guarded.append(key)
                else:
                    final_raw = round(proposed_raw, 4)
                    recomputed += 1

        if reason:
            hold_counts[reason] = hold_counts.get(reason, 0) + 1

        if (
            current_scope == "current_core"
            and final_raw is not None
        ):
            candidate_prod[key] = final_raw

        rows.append({
            "key": key,
            "sleeper_id": row.get("sleeper_id"),
            "legacy_model_position": legacy_pos,
            "current_valuation_position": current_pos,
            "current_scope": current_scope,
            "v1_projection": v1_projection,
            "legacy_history_component": finite(
                row.get("history_component")
            ),
            "current_position_history": current_history,
            "legacy_combined": legacy_combined,
            "current_combined": current_combined,
            "legacy_clean_model_prod_mult": legacy_clean_pm,
            "current_clean_model_prod_mult": current_clean_pm,
            "position_lineage_delta_raw": lineage_delta,
            "deployed_raw_prod_mult": live_raw,
            "proposed_raw_prod_mult_pre_guard": proposed_raw,
            "candidate_raw_prod_mult": final_raw,
            "status": (
                "candidate"
                if reason is None
                else "hold"
            ),
            "hold_reason": reason,
            "floor_rescue_guarded": guarded,
            "current_fv": None,
            "candidate_fv": None,
            "fv_delta": None,
            "fv_pct_change": None,
            "effective_current_prod_mult": None,
            "effective_candidate_prod_mult": None,
        })

    candidate_cfg = copy.deepcopy(cfg)
    candidate_cfg["prod_mult"] = candidate_prod
    candidate_values = snapshot_values.compute_all_values(candidate_cfg)

    non_target_changes = []
    offense_changes = []
    invalid_candidate_values = []
    direction_violations = []

    for key in current_values:
        old = current_values[key]
        new = candidate_values[key]
        if old["value"] != new["value"]:
            if key not in mismatch_keys:
                non_target_changes.append({
                    "key": key,
                    "pos": old["pos"],
                    "current_fv": old["value"],
                    "candidate_fv": new["value"],
                })
            if old["pos"] in {"QB", "RB", "WR", "TE", "K"}:
                offense_changes.append(key)

    row_by_key = {r["key"]: r for r in rows}
    for key in sorted(live_target_keys):
        old = current_values[key]
        new = candidate_values[key]
        if not isinstance(new["value"], int) or new["value"] <= 0:
            invalid_candidate_values.append(key)

        candidate_raw = finite(
            row_by_key[key]["candidate_raw_prod_mult"]
        )
        deployed_raw = finite(
            row_by_key[key]["deployed_raw_prod_mult"]
        )
        raw_delta = (
            candidate_raw - deployed_raw
            if (
                candidate_raw is not None
                and deployed_raw is not None
            )
            else 0.0
        )
        fv_delta = int(new["value"]) - int(old["value"])
        eps = 1e-12
        if (
            (raw_delta > eps and fv_delta < 0)
            or (raw_delta < -eps and fv_delta > 0)
        ):
            direction_violations.append({
                "key": key,
                "raw_delta": raw_delta,
                "fv_delta": fv_delta,
            })

        row_by_key[key].update({
            "current_fv": int(old["value"]),
            "candidate_fv": int(new["value"]),
            "fv_delta": fv_delta,
            "fv_pct_change": (
                fv_delta / old["value"]
                if old["value"] else None
            ),
            "effective_current_prod_mult": old["prod_mult"],
            "effective_candidate_prod_mult": new["prod_mult"],
        })

    changed_target_keys = sorted(
        key for key in live_target_keys
        if current_values[key]["value"]
        != candidate_values[key]["value"]
    )

    rank_summary = {}
    for pos in sorted(IDP):
        keys = sorted(
            key for key, value in current_values.items()
            if value["pos"] == pos
        )
        old_rank = ordinal_ranks(current_values, keys)
        new_rank = ordinal_ranks(candidate_values, keys)
        movers = [
            {
                "key": key,
                "current_rank": old_rank[key],
                "candidate_rank": new_rank[key],
                "rank_delta": new_rank[key] - old_rank[key],
            }
            for key in keys
            if key in live_target_keys
        ]
        rank_summary[pos] = {
            "target_count": len(movers),
            "max_abs_rank_move": max(
                (abs(m["rank_delta"]) for m in movers),
                default=0,
            ),
            "top24_movers_ge5": sum(
                1 for m in movers
                if m["current_rank"] <= 24
                and abs(m["rank_delta"]) >= 5
            ),
            "top36_movers_ge5": sum(
                1 for m in movers
                if m["current_rank"] <= 36
                and abs(m["rank_delta"]) >= 5
            ),
        }

    classification_complete = (
        len(rows) == len(mismatch_rows)
        and all(
            r["status"] in {"candidate", "hold"}
            for r in rows
        )
    )

    unguarded_rescue = [
        r["key"]
        for r in rows
        if (
            r["key"] in cfg["no_real_history"]
            and r["deployed_raw_prod_mult"] is not None
            and float(r["deployed_raw_prod_mult"]) <= PM_MIN + 1e-12
            and float(r["candidate_raw_prod_mult"]) > PM_MIN + 1e-12
            and float(r["candidate_raw_prod_mult"])
                < float(
                    cfg["role_mult"].get(
                        (
                            cfg["player_db"].get(r["key"]) or {}
                        ).get("role"),
                        1.0,
                    )
                ) - 1e-12
        )
    ]

    gates = {
        "immutable_release_hashes_match": {
            "pass": not hash_mismatches,
            "mismatches": hash_mismatches,
        },
        "target_count_exact_46": {
            "pass": len(mismatch_rows) == EXPECTED_MISMATCHES,
            "expected": EXPECTED_MISMATCHES,
            "actual": len(mismatch_rows),
        },
        "current_positions_match_frozen_target": {
            "pass": not current_position_mismatches,
            "mismatches": current_position_mismatches,
        },
        "live_core_positions_match_frozen_target": {
            "pass": not live_core_position_mismatches,
            "mismatches": live_core_position_mismatches,
        },
        "free_agent_positions_match_frozen_target": {
            "pass": not free_agent_position_mismatches,
            "mismatches": free_agent_position_mismatches,
        },
        "live_roster_merge_resolved": {
            "pass": not (
                cfg.get("live_merge_stats", {}).get(
                    "unresolved_positions"
                ) or []
            ),
            "merge_stats": cfg.get("live_merge_stats", {}),
        },
        "deployed_raw_matches_frozen_v1": {
            "pass": not deployed_raw_mismatches,
            "mismatches": deployed_raw_mismatches,
        },
        "target_identity_unique": {
            "pass": not duplicate_sleeper_ids,
            "duplicate_sleeper_ids": duplicate_sleeper_ids,
        },
        "classification_complete": {
            "pass": classification_complete,
        },
        "no_unguarded_floor_rescue_discontinuity": {
            "pass": not unguarded_rescue,
            "unguarded_keys": unguarded_rescue,
        },
        "candidate_values_valid": {
            "pass": not invalid_candidate_values,
            "invalid_keys": invalid_candidate_values,
        },
        "prod_direction_fv_monotonic": {
            "pass": not direction_violations,
            "violations": direction_violations,
        },
        "zero_non_target_fv_changes": {
            "pass": not non_target_changes,
            "changes": non_target_changes[:25],
        },
        "zero_offense_fv_changes": {
            "pass": not offense_changes,
            "keys": offense_changes,
        },
    }

    all_pass = all(g["pass"] for g in gates.values())
    if not all_pass:
        decision = (
            "STOP_IDP_POSITION_LINEAGE_V1_PHASE1_INTEGRITY_FAILURE"
        )
    elif not changed_target_keys:
        decision = (
            "STOP_IDP_POSITION_LINEAGE_V1_NO_MATERIAL_CANDIDATE"
        )
    else:
        decision = (
            "PASS_IDP_POSITION_LINEAGE_V1_PHASE1_CANDIDATE_FREEZE"
        )

    fv_deltas = [
        row_by_key[k]["fv_delta"]
        for k in live_target_keys
        if row_by_key[k]["fv_delta"] is not None
    ]
    pct_deltas = [
        row_by_key[k]["fv_pct_change"]
        for k in live_target_keys
        if row_by_key[k]["fv_pct_change"] is not None
    ]
    raw_deltas = []
    for k in live_target_keys:
        c = finite(row_by_key[k]["candidate_raw_prod_mult"])
        d = finite(row_by_key[k]["deployed_raw_prod_mult"])
        if c is not None and d is not None:
            raw_deltas.append(c - d)

    largest = sorted(
        rows,
        key=lambda r: (
            -abs(r.get("fv_delta") or 0),
            r["key"],
        ),
    )[:25]

    return {
        "study_id": "idp-position-lineage-v1",
        "phase": 1,
        "status": "FROZEN_AUDIT_COMPLETE",
        "decision": decision,
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "frozen_idp_release_id": release_manifest.get(
            "release_id"
        ),
        "frozen_idp_validation_status": final_v1.get(
            "status"
        ),
        "methodology": {
            "target": (
                "frozen IDP V1 rows where legacy_model_position "
                "differs from current_valuation_position"
            ),
            "target_position_authority": (
                "frozen current_valuation_position verified "
                "against current PLAYER_DB"
            ),
            "history_weight": HISTORY_WEIGHT,
            "projection_weight": PROJECTION_WEIGHT,
            "replacement_rank": 32,
            "frozen_v1_baseline_by_position": baselines,
            "prod_transform": (
                "clamp(-0.10 + 0.75 * ratio, 0.15, 1.55)"
            ),
            "transport": (
                "candidate live raw PM = deployed live raw PM + "
                "(clean current-position V1 PM - clean "
                "legacy-position V1 PM)"
            ),
        },
        "counts": {
            "target_mismatch_rows": len(mismatch_rows),
            "current_core_target_rows": len(live_target_keys),
            "free_agent_only_target_rows": len(free_agent_only_keys),
            "not_currently_rendered_target_rows": len(nonrendered_keys),
            "recomputed_candidates": recomputed,
            "explicit_holds": len(mismatch_rows) - recomputed,
            "floor_rescue_guarded": len(floor_guarded),
            "changed_target_fv_rows": len(changed_target_keys),
            "non_target_fv_changes": len(non_target_changes),
            "offense_fv_changes": len(offense_changes),
            "target_rows_with_sleeper_id": sum(
                r.get("sleeper_id") not in (None, "")
                for _, r in mismatch_rows
            ),
            "hold_reason_counts": dict(
                sorted(hold_counts.items())
            ),
        },
        "gates": gates,
        "movement": {
            "raw_prod_mult_delta": summarize(raw_deltas),
            "fv_delta": summarize(fv_deltas),
            "fv_pct_change": summarize(pct_deltas),
            "rank_summary_by_current_position": rank_summary,
            "largest_absolute_fv_movers": largest,
        },
        "rows": rows,
        "input_sha256": {
            str(RELEASE_MANIFEST.relative_to(ROOT)): sha256(
                RELEASE_MANIFEST
            ),
            str(FROZEN_CANDIDATE.relative_to(ROOT)): sha256(
                FROZEN_CANDIDATE
            ),
            str(FROZEN_HISTORY.relative_to(ROOT)): sha256(
                FROZEN_HISTORY
            ),
            str(FINAL_V1_VALIDATION.relative_to(ROOT)): sha256(
                FINAL_V1_VALIDATION
            ),
            str(INDEX.relative_to(ROOT)): sha256(INDEX),
            str(SNAPSHOT_VALUES.relative_to(ROOT)): sha256(
                SNAPSHOT_VALUES
            ),
            str(LEAGUE_ROSTERS.relative_to(ROOT)): sha256(
                LEAGUE_ROSTERS
            ),
            str(FREE_AGENTS.relative_to(ROOT)): sha256(
                FREE_AGENTS
            ),
            str(PLAYER_POSITIONS.relative_to(ROOT)): sha256(
                PLAYER_POSITIONS
            ),
            str(STARTER_AUDIT.relative_to(ROOT)): sha256(
                STARTER_AUDIT
            ),
        },
    }

def markdown(r):
    c = r["counts"]
    m = r["movement"]
    lines = [
        "# IDP Position Lineage V1 — Phase 1 Audit",
        "",
        f"**Decision:** `{r['decision']}`",
        "",
        "Research-only. Production is unchanged.",
        "",
        "## Frozen cohort",
        "",
        f"- Position-lineage mismatches: **{c['target_mismatch_rows']}**",
        f"- Current-core targets: **{c['current_core_target_rows']}**",
        f"- Free-agent-only targets held: **{c['free_agent_only_target_rows']}**",
        f"- Not-currently-rendered targets held: **{c['not_currently_rendered_target_rows']}**",
        f"- Recomputed candidates: **{c['recomputed_candidates']}**",
        f"- Explicit holds: **{c['explicit_holds']}**",
        f"- Floor-rescue guarded holds: **{c['floor_rescue_guarded']}**",
        f"- Target rows with stable Sleeper ID: **{c['target_rows_with_sleeper_id']}**",
        f"- Target rows with changed FV: **{c['changed_target_fv_rows']}**",
        "",
        "## Hard gates",
        "",
        "| Gate | Result |",
        "|---|---|",
    ]
    for key, gate in r["gates"].items():
        lines.append(
            f"| `{key}` | {'PASS' if gate['pass'] else 'FAIL'} |"
        )

    lines += [
        "",
        "## Movement",
        "",
        f"- Median raw PROD_MULT delta: **{m['raw_prod_mult_delta'].get('median', 0):+.4f}**",
        f"- P90 absolute-style raw delta endpoint: **{m['raw_prod_mult_delta'].get('p90', 0):+.4f}**",
        f"- Median FV delta: **{m['fv_delta'].get('median', 0):+.1f}**",
        f"- P90 FV delta: **{m['fv_delta'].get('p90', 0):+.1f}**",
        f"- Minimum FV delta: **{m['fv_delta'].get('min', 0):+.1f}**",
        f"- Maximum FV delta: **{m['fv_delta'].get('max', 0):+.1f}**",
        "",
        "### Rank stability by current position",
        "",
        "| Pos | Target N | Max abs rank move | Top-24 movers >=5 | Top-36 movers >=5 |",
        "|---|---:|---:|---:|---:|",
    ]
    for pos in sorted(IDP):
        s = m["rank_summary_by_current_position"][pos]
        lines.append(
            f"| {pos} | {s['target_count']} | "
            f"{s['max_abs_rank_move']} | "
            f"{s['top24_movers_ge5']} | "
            f"{s['top36_movers_ge5']} |"
        )

    lines += [
        "",
        "### Largest FV movers",
        "",
        "| Player | Legacy pos | Current pos | Old FV | Candidate FV | Delta | Status |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in m["largest_absolute_fv_movers"][:20]:
        lines.append(
            f"| {row['key']} | {row['legacy_model_position']} | "
            f"{row['current_valuation_position']} | "
            f"{row.get('current_fv', 0)} | "
            f"{row.get('candidate_fv', 0)} | "
            f"{row.get('fv_delta', 0):+d} | "
            f"{row['status']} |"
        )

    lines += [
        "",
        "## Decision semantics",
        "",
        "A PASS freezes an isolated position-lineage candidate for "
        "shadow validation. It does not authorize deployment.",
        "",
    ]
    return "\n".join(lines)

def write_outputs():
    result = build_result()
    OUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUT_MD.write_text(markdown(result) + "\n", encoding="utf-8")

    manifest = {
        "study_id": result["study_id"],
        "phase": 1,
        "decision": result["decision"],
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": result[
            "repo_commit_sha_evaluated"
        ],
        "preregistration_sha256": sha256(PREREG_JSON),
        "output_sha256": {
            str(PREREG_JSON.relative_to(ROOT)): sha256(
                PREREG_JSON
            ),
            str(PREREG_MD.relative_to(ROOT)): sha256(
                PREREG_MD
            ),
            str(SCRIPT.relative_to(ROOT)): sha256(SCRIPT),
            str(OUT_JSON.relative_to(ROOT)): sha256(OUT_JSON),
            str(OUT_MD.relative_to(ROOT)): sha256(OUT_MD),
        },
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "decision": result["decision"],
        "target_mismatch_rows": result["counts"][
            "target_mismatch_rows"
        ],
        "recomputed_candidates": result["counts"][
            "recomputed_candidates"
        ],
        "explicit_holds": result["counts"]["explicit_holds"],
        "changed_target_fv_rows": result["counts"][
            "changed_target_fv_rows"
        ],
    }, indent=2))

def selftest():
    history = {
        "shrinkage_k_by_position": {"DL": 4.0},
        "position_mean_ppg": {"DL": 8.0},
        "position_median_availability_2025": {"DL": 1.0},
        "own_weight_durability_by_position": {"DL": 0.2},
    }
    old = {
        "games_played_2025": 17,
        "true_ppg_2025": 10.0,
    }
    rec = recompute_history("DL", old, history)
    expected_ppg = (17 * 10.0 + 4.0 * 8.0) / 21.0
    assert abs(rec["shrunk_ppg"] - expected_ppg) < 1e-12
    assert rec["durability_projected_games_2026"] == 17.0
    assert clamp(2.0, 0.15, 1.55) == 1.55
    assert clamp(0.0, 0.15, 1.55) == 0.15

    fake_rows = [
        ("core", {"sleeper_id": "1"}),
        ("fa", {"sleeper_id": "2"}),
        ("gone", {"sleeper_id": "3"}),
    ]
    scopes = classify_target_scope(
        fake_rows,
        {"core": {"value": 1}},
        {
            "free_agents": [
                {"player_id": "2", "name": "FA", "pos": "DB"}
            ]
        },
    )
    assert scopes["core"]["scope"] == "current_core"
    assert scopes["fa"]["scope"] == "free_agent_only"
    assert scopes["gone"]["scope"] == "not_currently_rendered"

    print("IDP Position Lineage V1 Phase 1 self-test PASS")

def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--selftest", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    write_outputs()

if __name__ == "__main__":
    main()

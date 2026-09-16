#!/usr/bin/env python3
"""IDP Position Lineage V1 Phase 1B — current-core successor audit."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
RESEARCH = ROOT / "research" / "idp-position-lineage-v1"
RELEASE = ROOT / "model" / "releases" / "idp-v1"

PREREG = RESEARCH / "phase1b_preregistration.json"
COHORT = RESEARCH / "phase1b_current_core_cohort.json"
PHASE1 = RESEARCH / "idp_position_lineage_v1_phase1.json"
PHASE1_MANIFEST = RESEARCH / "phase1_manifest.json"
FROZEN = RELEASE / "idp_v1_model_delta_transport_candidate.json"
HISTORY = RELEASE / "production_history_components.json"
RELEASE_MANIFEST = RELEASE / "idp_v1_release_manifest.json"
INDEX = ROOT / "index.html"
ROSTERS = ROOT / "data" / "league_rosters.json"
POSITIONS = (
    ROOT / "scripts" / "artifacts" / "generated" / "player_positions.json"
)

OUT_JSON = RESEARCH / "idp_position_lineage_v1_phase1b.json"
OUT_MD = RESEARCH / "idp_position_lineage_v1_phase1b.md"
MANIFEST = RESEARCH / "phase1b_manifest.json"

HISTORY_WEIGHT = 0.45
PROJECTION_WEIGHT = 0.55
PM_INTERCEPT = -0.10
PM_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55
IDP = {"DL", "LB", "DB"}

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def finite(value):
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

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

def load_runtime():
    sys.path.insert(0, str(ROOT / "scripts" / "validation"))
    sys.path.insert(0, str(ROOT / "research" / "team-utility"))
    import snapshot_values
    import team_utility_starter_objective_audit as starter_audit

    base = snapshot_values.load_from_html(INDEX)
    rosters = read_json(ROSTERS)
    merged = starter_audit.merge_live_league_into_cfg(base, rosters)
    unresolved = (
        merged.get("live_merge_stats", {}).get("unresolved_positions") or []
    )
    if unresolved:
        raise RuntimeError(
            "live merge unresolved positions: "
            + json.dumps(unresolved[:20], sort_keys=True)
        )
    return snapshot_values, merged

def recompute_history(current_pos, old_history, history_doc):
    n = int(old_history.get("games_played_2025") or 0)
    true_ppg = finite(old_history.get("true_ppg_2025"))
    k = finite(history_doc["shrinkage_k_by_position"].get(current_pos))
    mean = finite(history_doc["position_mean_ppg"].get(current_pos))
    median_avail = finite(
        history_doc[
            "position_median_availability_2025"
        ].get(current_pos)
    )
    own_weight = finite(
        history_doc[
            "own_weight_durability_by_position"
        ].get(current_pos)
    )
    if own_weight is None:
        own_weight = 0.0

    if true_ppg is not None and k is not None and mean is not None:
        shrunk = (n * true_ppg + k * mean) / (n + k)
    elif mean is not None:
        shrunk = mean
    else:
        return None

    if median_avail is None:
        return None

    if true_ppg is not None:
        own_avail = min(1.0, n / 17.0)
        projected_avail = (
            own_weight * own_avail
            + (1.0 - own_weight) * median_avail
        )
    else:
        projected_avail = median_avail

    return {
        "history_component": shrunk * projected_avail * 17.0,
        "shrunk_ppg": shrunk,
        "projected_games": projected_avail * 17.0,
    }

def verify_release_hashes(manifest):
    errors = []
    for rel, expected in manifest[
        "immutable_release_artifacts"
    ].items():
        path = ROOT / rel
        actual = sha256(path) if path.exists() else "missing"
        if actual != expected:
            errors.append({
                "path": rel,
                "expected": expected,
                "actual": actual,
            })
    return errors

def ordinal_ranks(values, keys):
    ordered = sorted(
        keys,
        key=lambda k: (-int(values[k]["value"]), k),
    )
    return {key: i + 1 for i, key in enumerate(ordered)}

def build():
    prereg = read_json(PREREG)
    cohort_doc = read_json(COHORT)
    phase1 = read_json(PHASE1)
    phase1_manifest = read_json(PHASE1_MANIFEST)
    frozen = read_json(FROZEN)
    history = read_json(HISTORY)
    release_manifest = read_json(RELEASE_MANIFEST)
    positions = read_json(POSITIONS)

    snapshot_values, cfg = load_runtime()
    current_values = snapshot_values.compute_all_values(cfg)

    release_hash_errors = verify_release_hashes(release_manifest)

    phase1_hash_errors = []
    for rel, expected in phase1_manifest["output_sha256"].items():
        path = ROOT / rel
        actual = sha256(path) if path.exists() else "missing"
        if actual != expected:
            phase1_hash_errors.append({
                "path": rel,
                "expected": expected,
                "actual": actual,
            })

    frozen_players = frozen["players"]
    baselines = {
        pos: float(v)
        for pos, v in frozen[
            "new_model_baseline_by_position"
        ].items()
    }

    cohort = list(cohort_doc["rows"])
    cohort_keys = [r["key"] for r in cohort]
    cohort_set = set(cohort_keys)

    position_errors = []
    deployed_raw_errors = []
    for row in cohort:
        key = row["key"]
        current = row["current_position"]
        legacy = row["legacy_model_position"]
        info = cfg["player_db"].get(key)

        if positions.get(key) != current:
            position_errors.append({
                "key": key,
                "frozen_current": current,
                "generated_current": positions.get(key),
            })
        if not info or info.get("pos") != current:
            position_errors.append({
                "key": key,
                "frozen_current": current,
                "live_current": info.get("pos") if info else None,
            })
        if legacy == current:
            position_errors.append({
                "key": key,
                "reason": "legacy_equals_current",
            })

        deployed = finite(cfg["prod_mult"].get(key))
        expected = finite(row["deployed_v1_raw_prod_mult"])
        if (
            deployed is None
            or expected is None
            or abs(deployed - expected) > 1e-9
        ):
            deployed_raw_errors.append({
                "key": key,
                "deployed": deployed,
                "expected_v1": expected,
            })

    candidate_prod = dict(cfg["prod_mult"])
    rows = []
    hold_counts = {}
    guarded = []

    for cohort_row in cohort:
        key = cohort_row["key"]
        legacy = cohort_row["legacy_model_position"]
        current = cohort_row["current_position"]
        frozen_row = frozen_players[key]
        hist = history["players"].get(key)
        live_raw = finite(cfg["prod_mult"].get(key))
        projection = finite(frozen_row.get("v1_projection"))
        legacy_combined = finite(
            frozen_row.get("new_model_combined")
        )

        reason = None
        current_hist = None
        legacy_clean = None
        current_clean = None
        delta = None
        candidate_raw = live_raw

        if (
            hist is None
            or live_raw is None
            or projection is None
            or legacy_combined is None
        ):
            reason = "no_comparable_frozen_v1_projection_or_model"
        else:
            current_hist = recompute_history(
                current, hist, history
            )
            if current_hist is None:
                reason = "current_position_history_unavailable"
            else:
                current_combined = (
                    HISTORY_WEIGHT
                    * current_hist["history_component"]
                    + PROJECTION_WEIGHT * projection
                )
                legacy_clean = clamp(
                    PM_INTERCEPT
                    + PM_SLOPE
                    * (legacy_combined / baselines[legacy]),
                    PM_MIN,
                    PM_MAX,
                )
                current_clean = clamp(
                    PM_INTERCEPT
                    + PM_SLOPE
                    * (current_combined / baselines[current]),
                    PM_MIN,
                    PM_MAX,
                )
                delta = current_clean - legacy_clean
                proposed = clamp(
                    live_raw + delta, PM_MIN, PM_MAX
                )

                info = cfg["player_db"][key]
                role_estimate = float(
                    cfg["role_mult"].get(info["role"], 1.0)
                )
                no_history = key in cfg["no_real_history"]
                if (
                    no_history
                    and live_raw <= PM_MIN + 1e-12
                    and proposed > PM_MIN + 1e-12
                    and proposed < role_estimate - 1e-12
                ):
                    reason = "exact_floor_no_history_rescue_guard"
                    guarded.append(key)
                    candidate_raw = live_raw
                else:
                    candidate_raw = round(proposed, 4)

        if reason:
            hold_counts[reason] = hold_counts.get(reason, 0) + 1

        candidate_prod[key] = candidate_raw
        rows.append({
            "key": key,
            "sleeper_id": cohort_row.get("sleeper_id"),
            "legacy_model_position": legacy,
            "current_position": current,
            "deployed_raw_prod_mult": live_raw,
            "candidate_raw_prod_mult": candidate_raw,
            "v1_projection": projection,
            "current_position_history": current_hist,
            "legacy_clean_model_prod_mult": legacy_clean,
            "current_clean_model_prod_mult": current_clean,
            "position_lineage_delta_raw": delta,
            "status": "hold" if reason else "candidate",
            "hold_reason": reason,
        })

    candidate_cfg = copy.deepcopy(cfg)
    candidate_cfg["prod_mult"] = candidate_prod
    candidate_values = snapshot_values.compute_all_values(candidate_cfg)

    row_by_key = {r["key"]: r for r in rows}
    invalid = []
    direction_errors = []
    for key in cohort_keys:
        old = current_values[key]
        new = candidate_values[key]
        row = row_by_key[key]
        row["current_fv"] = int(old["value"])
        row["candidate_fv"] = int(new["value"])
        row["fv_delta"] = int(new["value"]) - int(old["value"])
        row["fv_pct_change"] = (
            row["fv_delta"] / old["value"]
            if old["value"] else None
        )

        if not isinstance(new["value"], int) or new["value"] <= 0:
            invalid.append(key)

        raw_old = finite(row["deployed_raw_prod_mult"])
        raw_new = finite(row["candidate_raw_prod_mult"])
        raw_delta = (
            raw_new - raw_old
            if raw_old is not None and raw_new is not None
            else 0.0
        )
        fv_delta = row["fv_delta"]
        if (
            (raw_delta > 1e-12 and fv_delta < 0)
            or (raw_delta < -1e-12 and fv_delta > 0)
        ):
            direction_errors.append({
                "key": key,
                "raw_delta": raw_delta,
                "fv_delta": fv_delta,
            })

    noncohort_changes = []
    offense_changes = []
    for key, old in current_values.items():
        new = candidate_values[key]
        if old["value"] == new["value"]:
            continue
        if key not in cohort_set:
            noncohort_changes.append(key)
        if old["pos"] in {"QB", "RB", "WR", "TE", "K"}:
            offense_changes.append(key)

    changed = [
        key for key in cohort_keys
        if current_values[key]["value"]
        != candidate_values[key]["value"]
    ]

    unguarded = []
    for row in rows:
        key = row["key"]
        old_raw = finite(row["deployed_raw_prod_mult"])
        new_raw = finite(row["candidate_raw_prod_mult"])
        if old_raw is None or new_raw is None:
            continue
        role = cfg["player_db"][key]["role"]
        role_est = float(cfg["role_mult"].get(role, 1.0))
        if (
            key in cfg["no_real_history"]
            and old_raw <= PM_MIN + 1e-12
            and new_raw > PM_MIN + 1e-12
            and new_raw < role_est - 1e-12
        ):
            unguarded.append(key)

    rank_summary = {}
    for pos in sorted(IDP):
        keys = [
            k for k, v in current_values.items()
            if v["pos"] == pos
        ]
        old_rank = ordinal_ranks(current_values, keys)
        new_rank = ordinal_ranks(candidate_values, keys)
        target = [k for k in cohort_keys if current_values[k]["pos"] == pos]
        moves = [
            new_rank[k] - old_rank[k] for k in target
        ]
        rank_summary[pos] = {
            "target_count": len(target),
            "max_abs_rank_move": max(
                (abs(x) for x in moves), default=0
            ),
            "top24_movers_ge5": sum(
                old_rank[k] <= 24
                and abs(new_rank[k] - old_rank[k]) >= 5
                for k in target
            ),
            "top36_movers_ge5": sum(
                old_rank[k] <= 36
                and abs(new_rank[k] - old_rank[k]) >= 5
                for k in target
            ),
        }

    gates = {
        "immutable_release_hashes_match": {
            "pass": not release_hash_errors,
            "errors": release_hash_errors,
        },
        "failed_phase1_artifacts_intact": {
            "pass": (
                phase1["decision"]
                == "STOP_IDP_POSITION_LINEAGE_V1_PHASE1_INTEGRITY_FAILURE"
                and not phase1_hash_errors
            ),
            "phase1_decision": phase1["decision"],
            "hash_errors": phase1_hash_errors,
        },
        "current_core_cohort_nonempty_unique": {
            "pass": (
                len(cohort_keys) > 0
                and len(cohort_keys) == len(set(cohort_keys))
            ),
            "count": len(cohort_keys),
        },
        "current_positions_exact": {
            "pass": not position_errors,
            "errors": position_errors,
        },
        "deployed_raw_matches_frozen_v1": {
            "pass": not deployed_raw_errors,
            "errors": deployed_raw_errors,
        },
        "classification_complete": {
            "pass": len(rows) == len(cohort_keys),
        },
        "no_unguarded_floor_rescue_discontinuity": {
            "pass": not unguarded,
            "keys": unguarded,
        },
        "candidate_values_valid": {
            "pass": not invalid,
            "keys": invalid,
        },
        "prod_direction_fv_monotonic": {
            "pass": not direction_errors,
            "errors": direction_errors,
        },
        "zero_noncohort_fv_changes": {
            "pass": not noncohort_changes,
            "keys": noncohort_changes,
        },
        "zero_offense_fv_changes": {
            "pass": not offense_changes,
            "keys": offense_changes,
        },
    }

    if not all(g["pass"] for g in gates.values()):
        decision = (
            "STOP_IDP_POSITION_LINEAGE_V1_PHASE1B_INTEGRITY_FAILURE"
        )
    elif not changed:
        decision = (
            "STOP_IDP_POSITION_LINEAGE_V1_PHASE1B_NO_MATERIAL_CANDIDATE"
        )
    else:
        decision = (
            "PASS_IDP_POSITION_LINEAGE_V1_PHASE1B_CURRENT_CORE_FREEZE"
        )

    fv_delta = [row_by_key[k]["fv_delta"] for k in cohort_keys]
    pct = [
        row_by_key[k]["fv_pct_change"]
        for k in cohort_keys
        if row_by_key[k]["fv_pct_change"] is not None
    ]
    raw_delta = []
    for k in cohort_keys:
        a = finite(row_by_key[k]["deployed_raw_prod_mult"])
        b = finite(row_by_key[k]["candidate_raw_prod_mult"])
        if a is not None and b is not None:
            raw_delta.append(b - a)

    largest = sorted(
        rows,
        key=lambda r: (-abs(r["fv_delta"]), r["key"]),
    )[:30]

    return {
        "study_id": "idp-position-lineage-v1",
        "phase": "1B",
        "status": "CURRENT_CORE_REBASE_COMPLETE",
        "decision": decision,
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "counts": {
            "current_core_cohort": len(cohort_keys),
            "candidate_rows": sum(
                r["status"] == "candidate" for r in rows
            ),
            "held_rows": sum(
                r["status"] == "hold" for r in rows
            ),
            "changed_fv_rows": len(changed),
            "floor_rescue_guarded": len(guarded),
            "hold_reason_counts": dict(
                sorted(hold_counts.items())
            ),
        },
        "gates": gates,
        "movement": {
            "raw_prod_mult_delta": summarize(raw_delta),
            "fv_delta": summarize(fv_delta),
            "fv_pct_change": summarize(pct),
            "rank_summary_by_current_position": rank_summary,
            "largest_absolute_fv_movers": largest,
        },
        "rows": rows,
        "input_sha256": {
            str(PREREG.relative_to(ROOT)): sha256(PREREG),
            str(COHORT.relative_to(ROOT)): sha256(COHORT),
            str(PHASE1.relative_to(ROOT)): sha256(PHASE1),
            str(PHASE1_MANIFEST.relative_to(ROOT)): sha256(PHASE1_MANIFEST),
            str(FROZEN.relative_to(ROOT)): sha256(FROZEN),
            str(HISTORY.relative_to(ROOT)): sha256(HISTORY),
            str(RELEASE_MANIFEST.relative_to(ROOT)): sha256(RELEASE_MANIFEST),
            str(INDEX.relative_to(ROOT)): sha256(INDEX),
            str(ROSTERS.relative_to(ROOT)): sha256(ROSTERS),
            str(POSITIONS.relative_to(ROOT)): sha256(POSITIONS),
        },
    }

def markdown(r):
    c = r["counts"]
    m = r["movement"]
    lines = [
        "# IDP Position Lineage V1 — Phase 1B Current-Core Rebase",
        "",
        f"**Decision:** `{r['decision']}`",
        "",
        "Production remains unchanged.",
        "",
        "## Cohort",
        "",
        f"- Frozen current-core mismatches: **{c['current_core_cohort']}**",
        f"- Candidate rows: **{c['candidate_rows']}**",
        f"- Held rows: **{c['held_rows']}**",
        f"- Rows with changed FV: **{c['changed_fv_rows']}**",
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
        "## Movement diagnostics",
        "",
        f"- Median raw PROD_MULT delta: **{m['raw_prod_mult_delta'].get('median', 0):+.4f}**",
        f"- Median FV delta: **{m['fv_delta'].get('median', 0):+.1f}**",
        f"- P90 FV delta: **{m['fv_delta'].get('p90', 0):+.1f}**",
        f"- Minimum FV delta: **{m['fv_delta'].get('min', 0):+.1f}**",
        f"- Maximum FV delta: **{m['fv_delta'].get('max', 0):+.1f}**",
        "",
        "### Rank stability",
        "",
        "| Pos | Target N | Max abs move | Top-24 >=5 | Top-36 >=5 |",
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
        "| Player | Legacy | Current | Old FV | Candidate FV | Delta | Status |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in m["largest_absolute_fv_movers"][:20]:
        lines.append(
            f"| {row['key']} | {row['legacy_model_position']} | "
            f"{row['current_position']} | {row['current_fv']} | "
            f"{row['candidate_fv']} | {row['fv_delta']:+d} | "
            f"{row['status']} |"
        )

    lines += [
        "",
        "A PASS freezes the current-core candidate for a separate "
        "shadow/sanity review. It does not authorize deployment.",
        "",
    ]
    return "\n".join(lines)

def write():
    result = build()
    OUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    OUT_MD.write_text(markdown(result) + "\n")

    manifest = {
        "study_id": result["study_id"],
        "phase": "1B",
        "decision": result["decision"],
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": result[
            "repo_commit_sha_evaluated"
        ],
        "output_sha256": {
            str(PREREG.relative_to(ROOT)): sha256(PREREG),
            str(
                (RESEARCH / "phase1b_preregistration.md").relative_to(ROOT)
            ): sha256(RESEARCH / "phase1b_preregistration.md"),
            str(COHORT.relative_to(ROOT)): sha256(COHORT),
            str(SCRIPT.relative_to(ROOT)): sha256(SCRIPT),
            str(OUT_JSON.relative_to(ROOT)): sha256(OUT_JSON),
            str(OUT_MD.relative_to(ROOT)): sha256(OUT_MD),
        },
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({
        "decision": result["decision"],
        "cohort": result["counts"]["current_core_cohort"],
        "candidate_rows": result["counts"]["candidate_rows"],
        "held_rows": result["counts"]["held_rows"],
        "changed_fv_rows": result["counts"]["changed_fv_rows"],
    }, indent=2))

def selftest():
    history = {
        "shrinkage_k_by_position": {"DL": 4.0},
        "position_mean_ppg": {"DL": 8.0},
        "position_median_availability_2025": {"DL": 1.0},
        "own_weight_durability_by_position": {"DL": 0.2},
    }
    rec = recompute_history(
        "DL",
        {"games_played_2025": 17, "true_ppg_2025": 10.0},
        history,
    )
    assert rec is not None
    assert abs(rec["shrunk_ppg"] - ((170 + 32) / 21)) < 1e-12
    assert rec["projected_games"] == 17.0
    assert clamp(2.0, 0.15, 1.55) == 1.55
    print("IDP Position Lineage V1 Phase 1B self-test PASS")

def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    else:
        write()

if __name__ == "__main__":
    main()

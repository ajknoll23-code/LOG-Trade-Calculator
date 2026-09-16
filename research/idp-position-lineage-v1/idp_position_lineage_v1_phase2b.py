#!/usr/bin/env python3
"""IDP Position Lineage V1 Phase 2B age-feedback shadow."""

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

P1B_JSON = RESEARCH / "idp_position_lineage_v1_phase1b.json"
P1B_COHORT = RESEARCH / "phase1b_current_core_cohort.json"
P1B_MANIFEST = RESEARCH / "phase1b_manifest.json"
P2_JSON = RESEARCH / "idp_position_lineage_v1_phase2.json"
P2_MANIFEST = RESEARCH / "phase2_manifest.json"
PREREG = RESEARCH / "phase2b_preregistration.json"

INDEX = ROOT / "index.html"
ROSTERS = ROOT / "data" / "league_rosters.json"
POSITIONS = (
    ROOT / "scripts" / "artifacts" / "generated" / "player_positions.json"
)

OUT_JSON = RESEARCH / "idp_position_lineage_v1_phase2b.json"
OUT_MD = RESEARCH / "idp_position_lineage_v1_phase2b.md"
MANIFEST = RESEARCH / "phase2b_manifest.json"

PM_MIN = 0.15
PM_MAX = 1.55
ROUND_TOL = 0.000051
AGE_TOL = 0.00000051
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

def js_round_positive(x):
    return math.floor(x + 0.5)

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
        "p25": pct(0.25),
        "p75": pct(0.75),
        "p90": pct(0.90),
        "p95": pct(0.95),
        "min": vals[0],
        "max": vals[-1],
    }

def verify_manifest_outputs(manifest):
    errors = []
    for rel, expected in manifest["output_sha256"].items():
        path = ROOT / rel
        actual = sha256(path) if path.exists() else "missing"
        if actual != expected:
            errors.append({
                "path": rel,
                "expected": expected,
                "actual": actual,
            })
    return errors

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

def exact_runtime_components(snapshot_values, cfg, key, raw_prod_map):
    info = cfg["player_db"][key]
    role = info["role"]
    pos = info["pos"]
    age = info["age"]

    effective_prod, raw_prod = snapshot_values.production_multiplier(
        key,
        role,
        raw_prod_map,
        cfg["no_real_history"],
        cfg["role_mult"],
    )
    exact_age = snapshot_values.effective_age_multiplier(
        pos,
        age,
        role,
        key,
        effective_prod,
        raw_prod,
        cfg,
    )
    pw = cfg["position_weight"].get(pos, 1.0)
    fv = js_round_positive(
        100.0 * pw * exact_age * effective_prod * 55.0
    )
    return {
        "effective_prod": float(effective_prod),
        "raw_prod": raw_prod,
        "exact_age_mult": float(exact_age),
        "position_weight": float(pw),
        "fv": int(fv),
    }

def build():
    p1b = read_json(P1B_JSON)
    cohort_doc = read_json(P1B_COHORT)
    p1b_manifest = read_json(P1B_MANIFEST)
    p2 = read_json(P2_JSON)
    p2_manifest = read_json(P2_MANIFEST)
    positions = read_json(POSITIONS)

    snapshot_values, cfg = load_runtime()
    current_values = snapshot_values.compute_all_values(cfg)

    p1b_hash_errors = verify_manifest_outputs(p1b_manifest)
    p2_hash_errors = verify_manifest_outputs(p2_manifest)

    p2_meta_errors = (
        p2["gates"][
            "candidate_metadata_and_age_multiplier_unchanged"
        ]["errors"]
    )
    p2_true_metadata_errors = [
        e for e in p2_meta_errors
        if e.get("field") != "age_mult"
    ]

    cohort = list(cohort_doc["rows"])
    cohort_keys = [r["key"] for r in cohort]
    cohort_set = set(cohort_keys)
    p1b_rows = {r["key"]: r for r in p1b["rows"]}

    candidate_keys = [
        k for k in cohort_keys
        if p1b_rows[k]["status"] == "candidate"
    ]
    held_keys = [
        k for k in cohort_keys
        if p1b_rows[k]["status"] == "hold"
    ]

    identity_errors = []
    deployed_errors = []
    reconstruction_errors = []
    offset_errors = []
    static_metadata_errors = []
    age_formula_errors = []
    post_peak_age_errors = []
    age_direction_errors = []
    decomposition_errors = []
    held_errors = []
    invalid_values = []
    total_direction_errors = []

    candidate_prod = dict(cfg["prod_mult"])

    for row in cohort:
        key = row["key"]
        frozen = p1b_rows[key]
        info = cfg["player_db"].get(key)
        pos = row["current_position"]

        if (
            key not in current_values
            or not info
            or info.get("pos") != pos
            or positions.get(key) != pos
        ):
            identity_errors.append({
                "key": key,
                "cohort_position": pos,
                "live_position": info.get("pos") if info else None,
                "generated_position": positions.get(key),
                "renders": key in current_values,
            })
            continue

        deployed = finite(cfg["prod_mult"].get(key))
        p1b_deployed = finite(frozen["deployed_raw_prod_mult"])
        if (
            deployed is None
            or p1b_deployed is None
            or abs(deployed - p1b_deployed) > 1e-9
        ):
            deployed_errors.append({
                "key": key,
                "current": deployed,
                "phase1b": p1b_deployed,
            })

        if frozen["status"] == "candidate":
            candidate_prod[key] = finite(
                frozen["candidate_raw_prod_mult"]
            )
        else:
            candidate_prod[key] = deployed

    shadow_cfg = copy.deepcopy(cfg)
    shadow_cfg["prod_mult"] = candidate_prod
    shadow_values = snapshot_values.compute_all_values(shadow_cfg)

    rows = []
    for key in cohort_keys:
        frozen = p1b_rows[key]
        info = cfg["player_db"].get(key)
        old = current_values.get(key)
        new = shadow_values.get(key)
        if info is None or old is None or new is None:
            continue

        pos = info["pos"]
        age = info["age"]
        role = info["role"]

        if (
            old["pos"] != new["pos"]
            or old["age"] != new["age"]
            or old["role"] != new["role"]
            or old["no_real_production_history"]
               != new["no_real_production_history"]
            or cfg["position_weight"][pos]
               != shadow_cfg["position_weight"][pos]
            or cfg["age_curve"][pos]
               != shadow_cfg["age_curve"][pos]
        ):
            static_metadata_errors.append({"key": key})

        current_components = exact_runtime_components(
            snapshot_values, cfg, key, cfg["prod_mult"]
        )
        shadow_components = exact_runtime_components(
            snapshot_values, shadow_cfg, key, candidate_prod
        )

        if (
            abs(
                old["age_mult"]
                - round(
                    current_components["exact_age_mult"], 6
                )
            ) > AGE_TOL
        ):
            age_formula_errors.append({
                "key": key,
                "side": "current",
                "snapshot_age_mult": old["age_mult"],
                "formula_age_mult": current_components[
                    "exact_age_mult"
                ],
            })

        if (
            abs(
                new["age_mult"]
                - round(
                    shadow_components["exact_age_mult"], 6
                )
            ) > AGE_TOL
        ):
            age_formula_errors.append({
                "key": key,
                "side": "shadow",
                "snapshot_age_mult": new["age_mult"],
                "formula_age_mult": shadow_components[
                    "exact_age_mult"
                ],
            })

        peak_end = cfg["age_curve"][pos]["peakEnd"]
        age_sensitive = age <= peak_end
        age_delta_exact = (
            shadow_components["exact_age_mult"]
            - current_components["exact_age_mult"]
        )
        eff_prod_delta = (
            shadow_components["effective_prod"]
            - current_components["effective_prod"]
        )

        if (
            not age_sensitive
            and abs(age_delta_exact) > 1e-12
        ):
            post_peak_age_errors.append({
                "key": key,
                "age": age,
                "peak_end": peak_end,
                "age_delta": age_delta_exact,
            })

        if age_sensitive and (
            (eff_prod_delta > 1e-12 and age_delta_exact < -1e-12)
            or (
                eff_prod_delta < -1e-12
                and age_delta_exact > 1e-12
            )
        ):
            age_direction_errors.append({
                "key": key,
                "effective_prod_delta": eff_prod_delta,
                "age_mult_delta": age_delta_exact,
            })

        if frozen["status"] == "candidate":
            deployed = finite(frozen["deployed_raw_prod_mult"])
            candidate = finite(frozen["candidate_raw_prod_mult"])
            legacy_clean = finite(
                frozen["legacy_clean_model_prod_mult"]
            )
            current_clean = finite(
                frozen["current_clean_model_prod_mult"]
            )
            if None in (
                deployed,
                candidate,
                legacy_clean,
                current_clean,
            ):
                reconstruction_errors.append({
                    "key": key,
                    "reason": "missing_numeric_component",
                })
            else:
                raw_unclamped = (
                    deployed + current_clean - legacy_clean
                )
                reconstructed = round(
                    clamp(raw_unclamped, PM_MIN, PM_MAX), 4
                )
                if abs(candidate - reconstructed) > 1e-9:
                    reconstruction_errors.append({
                        "key": key,
                        "candidate": candidate,
                        "reconstructed": reconstructed,
                    })

                clamped = (
                    raw_unclamped < PM_MIN - 1e-12
                    or raw_unclamped > PM_MAX + 1e-12
                )
                old_offset = deployed - legacy_clean
                new_offset = candidate - current_clean
                if (
                    not clamped
                    and abs(new_offset - old_offset) > ROUND_TOL
                ):
                    offset_errors.append({
                        "key": key,
                        "old_offset": old_offset,
                        "new_offset": new_offset,
                        "residual": new_offset - old_offset,
                    })

        direct_prod_only_fv = js_round_positive(
            100.0
            * current_components["position_weight"]
            * current_components["exact_age_mult"]
            * shadow_components["effective_prod"]
            * 55.0
        )
        current_fv = current_components["fv"]
        full_shadow_fv = shadow_components["fv"]
        direct_effect = direct_prod_only_fv - current_fv
        age_feedback_effect = (
            full_shadow_fv - direct_prod_only_fv
        )
        total_effect = full_shadow_fv - current_fv

        if (
            direct_effect
            + age_feedback_effect
            != total_effect
            or full_shadow_fv != int(new["value"])
            or current_fv != int(old["value"])
        ):
            decomposition_errors.append({
                "key": key,
                "current_formula_fv": current_fv,
                "current_snapshot_fv": int(old["value"]),
                "direct_prod_only_fv": direct_prod_only_fv,
                "shadow_formula_fv": full_shadow_fv,
                "shadow_snapshot_fv": int(new["value"]),
                "direct_effect": direct_effect,
                "age_feedback_effect": age_feedback_effect,
                "total_effect": total_effect,
            })

        if frozen["status"] == "hold":
            if int(old["value"]) != int(new["value"]):
                held_errors.append({
                    "key": key,
                    "current_fv": int(old["value"]),
                    "shadow_fv": int(new["value"]),
                })

        if not isinstance(new["value"], int) or new["value"] <= 0:
            invalid_values.append(key)

        raw_old = finite(frozen["deployed_raw_prod_mult"])
        raw_new = finite(frozen["candidate_raw_prod_mult"])
        raw_delta = (
            raw_new - raw_old
            if raw_old is not None and raw_new is not None
            else 0.0
        )
        fv_delta = int(new["value"]) - int(old["value"])
        if (
            (raw_delta > 1e-12 and fv_delta < 0)
            or (raw_delta < -1e-12 and fv_delta > 0)
        ):
            total_direction_errors.append({
                "key": key,
                "raw_delta": raw_delta,
                "fv_delta": fv_delta,
            })

        rows.append({
            "key": key,
            "status": frozen["status"],
            "current_position": pos,
            "age": age,
            "role": role,
            "age_sensitive": age_sensitive,
            "current_effective_prod": current_components[
                "effective_prod"
            ],
            "shadow_effective_prod": shadow_components[
                "effective_prod"
            ],
            "effective_prod_delta": eff_prod_delta,
            "current_exact_age_mult": current_components[
                "exact_age_mult"
            ],
            "shadow_exact_age_mult": shadow_components[
                "exact_age_mult"
            ],
            "age_mult_delta": age_delta_exact,
            "current_fv": int(old["value"]),
            "direct_prod_only_fv": direct_prod_only_fv,
            "shadow_fv": int(new["value"]),
            "direct_production_effect_fv": direct_effect,
            "age_feedback_effect_fv": age_feedback_effect,
            "total_fv_delta": fv_delta,
            "age_feedback_share_of_abs_total": (
                abs(age_feedback_effect) / abs(total_effect)
                if total_effect else 0.0
            ),
        })

    noncohort_changes = []
    offense_changes = []
    for key, old in current_values.items():
        new = shadow_values[key]
        if int(old["value"]) == int(new["value"]):
            continue
        if key not in cohort_set:
            noncohort_changes.append(key)
        if old["pos"] in {"QB", "RB", "WR", "TE", "K"}:
            offense_changes.append(key)

    phase2_other_gates_pass = all(
        gate["pass"]
        for name, gate in p2["gates"].items()
        if name
        != "candidate_metadata_and_age_multiplier_unchanged"
    )

    gates = {
        "phase1b_pass_and_hashes_intact": {
            "pass": (
                p1b["decision"]
                == "PASS_IDP_POSITION_LINEAGE_V1_PHASE1B_CURRENT_CORE_FREEZE"
                and not p1b_hash_errors
            ),
            "hash_errors": p1b_hash_errors,
        },
        "phase2_stop_and_hashes_intact": {
            "pass": (
                p2["decision"]
                == "STOP_IDP_POSITION_LINEAGE_V1_PHASE2_SHADOW_SANITY"
                and not p2_hash_errors
                and phase2_other_gates_pass
            ),
            "phase2_decision": p2["decision"],
            "hash_errors": p2_hash_errors,
            "all_other_phase2_gates_pass": phase2_other_gates_pass,
        },
        "phase2_failure_was_age_output_only": {
            "pass": (
                bool(p2_meta_errors)
                and not p2_true_metadata_errors
            ),
            "phase2_metadata_errors": p2_meta_errors,
            "true_metadata_errors": p2_true_metadata_errors,
        },
        "frozen_cohort_counts_intact": {
            "pass": (
                len(cohort_keys) == 27
                and len(candidate_keys) == 24
                and len(held_keys) == 3
            ),
            "cohort": len(cohort_keys),
            "candidates": len(candidate_keys),
            "holds": len(held_keys),
        },
        "current_core_identity_position_intact": {
            "pass": not identity_errors,
            "errors": identity_errors,
        },
        "deployed_raw_still_matches_phase1b": {
            "pass": not deployed_errors,
            "errors": deployed_errors,
        },
        "transport_reconstruction_exact": {
            "pass": not reconstruction_errors,
            "errors": reconstruction_errors,
        },
        "unclamped_model_offset_preserved": {
            "pass": not offset_errors,
            "errors": offset_errors,
            "tolerance": ROUND_TOL,
        },
        "static_metadata_and_age_formula_inputs_unchanged": {
            "pass": not static_metadata_errors,
            "errors": static_metadata_errors,
        },
        "age_multiplier_recomputes_exactly": {
            "pass": not age_formula_errors,
            "errors": age_formula_errors,
            "tolerance": AGE_TOL,
        },
        "post_peak_age_multiplier_unchanged": {
            "pass": not post_peak_age_errors,
            "errors": post_peak_age_errors,
        },
        "age_feedback_direction_consistent": {
            "pass": not age_direction_errors,
            "errors": age_direction_errors,
        },
        "fv_effect_decomposition_exact": {
            "pass": not decomposition_errors,
            "errors": decomposition_errors,
        },
        "held_rows_unchanged": {
            "pass": not held_errors,
            "errors": held_errors,
        },
        "candidate_values_valid": {
            "pass": not invalid_values,
            "keys": invalid_values,
        },
        "raw_prod_direction_total_fv_monotonic": {
            "pass": not total_direction_errors,
            "errors": total_direction_errors,
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

    decision = (
        "PASS_IDP_POSITION_LINEAGE_V1_PHASE2B_AGE_FEEDBACK_SHADOW"
        if all(g["pass"] for g in gates.values())
        else "STOP_IDP_POSITION_LINEAGE_V1_PHASE2B_AGE_FEEDBACK_SHADOW"
    )

    candidate_rows = [
        r for r in rows if r["status"] == "candidate"
    ]
    age_sensitive_candidates = [
        r for r in candidate_rows if r["age_sensitive"]
    ]

    largest_feedback = sorted(
        candidate_rows,
        key=lambda r: (
            -abs(r["age_feedback_effect_fv"]),
            r["key"],
        ),
    )[:24]

    return {
        "study_id": "idp-position-lineage-v1",
        "phase": "2B",
        "status": "AGE_FEEDBACK_SHADOW_COMPLETE",
        "decision": decision,
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "counts": {
            "frozen_cohort": len(cohort_keys),
            "candidate_rows": len(candidate_keys),
            "held_rows": len(held_keys),
            "age_sensitive_candidate_rows": len(
                age_sensitive_candidates
            ),
            "candidate_rows_with_nonzero_age_feedback": sum(
                r["age_feedback_effect_fv"] != 0
                for r in candidate_rows
            ),
        },
        "gates": gates,
        "diagnostics": {
            "candidate_total_fv_delta": summarize(
                [r["total_fv_delta"] for r in candidate_rows]
            ),
            "direct_production_effect_fv": summarize(
                [
                    r["direct_production_effect_fv"]
                    for r in candidate_rows
                ]
            ),
            "age_feedback_effect_fv": summarize(
                [
                    r["age_feedback_effect_fv"]
                    for r in candidate_rows
                ]
            ),
            "age_feedback_share_of_abs_total": summarize(
                [
                    r["age_feedback_share_of_abs_total"]
                    for r in candidate_rows
                ]
            ),
            "age_mult_delta": summarize(
                [r["age_mult_delta"] for r in candidate_rows]
            ),
            "largest_age_feedback_rows": largest_feedback,
        },
        "rows": rows,
        "next_step_if_pass": (
            "SEPARATE_GUARDED_PRODUCTION_CONFIRMATION"
        ),
        "next_step_if_stop": (
            "CLOSE_OR_REPAIR_WITHOUT_WEAKENING_GATES"
        ),
    }

def markdown(r):
    c = r["counts"]
    d = r["diagnostics"]
    lines = [
        "# IDP Position Lineage V1 — Phase 2B Age-Feedback Shadow",
        "",
        f"**Decision:** `{r['decision']}`",
        "",
        "Production remains unchanged.",
        "",
        "## Cohort",
        "",
        f"- Frozen current-core cohort: **{c['frozen_cohort']}**",
        f"- Candidates: **{c['candidate_rows']}**",
        f"- Holds: **{c['held_rows']}**",
        f"- Production-sensitive-age candidates: **{c['age_sensitive_candidate_rows']}**",
        f"- Candidates with nonzero FV age feedback: **{c['candidate_rows_with_nonzero_age_feedback']}**",
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
        "## FV decomposition diagnostics",
        "",
        f"- Median total FV delta: **{d['candidate_total_fv_delta'].get('median', 0):+.1f}**",
        f"- Median direct-production effect: **{d['direct_production_effect_fv'].get('median', 0):+.1f}**",
        f"- Median age-feedback effect: **{d['age_feedback_effect_fv'].get('median', 0):+.1f}**",
        f"- P90 age-feedback effect: **{d['age_feedback_effect_fv'].get('p90', 0):+.1f}**",
        f"- Median age-feedback share of absolute total: **{d['age_feedback_share_of_abs_total'].get('median', 0):.1%}**",
        "",
        "### Largest age-feedback effects",
        "",
        "| Player | Pos | Age | Total ΔFV | Direct Prod | Age Feedback | Age Mult Δ |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in d["largest_age_feedback_rows"][:20]:
        lines.append(
            f"| {row['key']} | {row['current_position']} | "
            f"{row['age']} | {row['total_fv_delta']:+d} | "
            f"{row['direct_production_effect_fv']:+d} | "
            f"{row['age_feedback_effect_fv']:+d} | "
            f"{row['age_mult_delta']:+.6f} |"
        )

    lines += [
        "",
        "## Decision semantics",
        "",
        "A PASS proves the prior Phase 2 STOP came from an invalid "
        "age-output invariant, while the unchanged production age "
        "formula deterministically explains the feedback. It still "
        "does not authorize deployment.",
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
        "phase": "2B",
        "decision": result["decision"],
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": result[
            "repo_commit_sha_evaluated"
        ],
        "preregistration_sha256": sha256(PREREG),
        "phase1b_manifest_sha256": sha256(P1B_MANIFEST),
        "phase2_manifest_sha256": sha256(P2_MANIFEST),
        "output_sha256": {
            str(PREREG.relative_to(ROOT)): sha256(PREREG),
            str(
                (RESEARCH / "phase2b_preregistration.md").relative_to(ROOT)
            ): sha256(RESEARCH / "phase2b_preregistration.md"),
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
        "candidates": result["counts"]["candidate_rows"],
        "age_sensitive": result["counts"][
            "age_sensitive_candidate_rows"
        ],
        "nonzero_age_feedback": result["counts"][
            "candidate_rows_with_nonzero_age_feedback"
        ],
    }, indent=2))

def selftest():
    # Production-sensitive age output is allowed to change when the
    # unchanged formula consumes a different production multiplier.
    direct = 100
    age_feedback = 25
    total = 125
    assert direct + age_feedback == total
    assert js_round_positive(10.5) == 11
    assert clamp(2.0, PM_MIN, PM_MAX) == PM_MAX
    print("IDP Position Lineage V1 Phase 2B self-test PASS")

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

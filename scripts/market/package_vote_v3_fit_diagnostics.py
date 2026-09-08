#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import package_vote_fit_diagnostics as v1d
import package_vote_v2_pipeline as v2p
import package_vote_v3_pipeline as v3p

V3_CHALLENGES = ROOT / "research" / "package-adjustment-v3" / "package_vote_challenges_v3.json"
V3_RESULTS = ROOT / "research" / "package-adjustment-v3" / "package_vote_v3_results.json"
V2_CHALLENGES = ROOT / "research" / "package-adjustment-v2" / "package_vote_challenges_v2.json"
OUT_JSON = ROOT / "research" / "package-adjustment-v3" / "package_vote_v3_fit_diagnostics.json"
OUT_MD = ROOT / "research" / "package-adjustment-v3" / "package_vote_v3_fit_diagnostics.md"

BOOTSTRAP_REPS = 400
BOOTSTRAP_SEED = 20260908
POOLED_EFFECTIVE_VOTE_CAP = 30.0

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def fit_matrix(X, y, w, names, ridge=1e-6):
    theta, ll, pred = v1d.logistic_irls(X, y, w, ridge=ridge)
    return {
        "coefficients": {n: float(v) for n, v in zip(names, theta)},
        "weighted_log_likelihood": float(ll),
        "aic": float(2 * len(theta) - 2 * ll),
        "parameter_count": int(len(theta)),
        "predictions": [float(x) for x in pred],
    }

def fit_fields(records, fields, ridge=1e-6):
    cols = [np.ones(len(records), dtype=float)]
    names = ["intercept"]
    for field in fields:
        cols.append(np.asarray([float(r[field]) for r in records], dtype=float))
        names.append(field)
    X = np.column_stack(cols)
    y = np.asarray([float(r["y"]) for r in records], dtype=float)
    w = np.asarray([float(r["weight"]) for r in records], dtype=float)
    return fit_matrix(X, y, w, names, ridge=ridge)

def build_v3_records(rows, catalog, voter_weights):
    targets = {}
    for c in catalog.values():
        targets[c["target"]["key"]] = float(c["target_fv"])
    logs = np.asarray([math.log(v) for v in targets.values()], dtype=float)
    log_mean = float(np.mean(logs))
    log_sd = float(np.std(logs))
    if log_sd <= 1e-12:
        log_sd = 1.0

    out = []
    for row in rows:
        c = catalog.get(row["challenge_id"])
        if c is None:
            continue
        voter = row["voter_roster_id"]
        target_fv = float(c["target_fv"])
        target_z = (math.log(target_fv) - log_mean) / log_sd
        log_ratio = math.log(max(float(c["raw_package_to_target_ratio"]), 1e-12))
        out.append({
            "experiment": "v3",
            "challenge_id": c["id"],
            "voter": voter,
            "choice": row["choice"],
            "y": 1.0 if row["choice"] == "P" else 0.0,
            "weight": float(voter_weights[voter]["ballot_weight"]),
            "ratio": float(c["raw_package_to_target_ratio"]),
            "ratio_target": float(c["ratio_target"]),
            "log_ratio": log_ratio,
            "package_size": int(c["package_size"]),
            "size3": 1.0 if int(c["package_size"]) == 3 else 0.0,
            "target_key": c["target"]["key"],
            "target_name": c["target"]["name"],
            "target_pos": c["target"]["pos"],
            "target_tier": c["target_tier"],
            "target_fv": target_fv,
            "target_z": target_z,
            "ratio_x_target_z": log_ratio * target_z,
        })
    return out, {
        "target_log_mean": log_mean,
        "target_log_sd": log_sd,
        "unique_target_values": sorted(targets.values()),
    }

def build_v2_records(rows, catalog):
    out = []
    for row in rows:
        c = catalog.get(row["challenge_id"])
        if c is None:
            continue
        out.append({
            "experiment": "v2",
            "challenge_id": c["id"],
            "voter": row["voter_roster_id"],
            "choice": row["choice"],
            "y": 1.0 if row["choice"] == "P" else 0.0,
            "ratio": float(c["raw_package_to_target_ratio"]),
            "log_ratio": math.log(max(float(c["raw_package_to_target_ratio"]), 1e-12)),
            "package_size": int(c["package_size"]),
            "size3": 1.0 if int(c["package_size"]) == 3 else 0.0,
            "experiment_v3": 0.0,
        })
    return out

def fit_target_fixed_effects(records):
    targets = sorted({r["target_key"] for r in records})
    if len(targets) < 3:
        return {"available": False, "reason": "too_few_targets"}
    ref = targets[0]
    cols = [
        np.ones(len(records), dtype=float),
        np.asarray([r["log_ratio"] for r in records], dtype=float),
        np.asarray([r["size3"] for r in records], dtype=float),
    ]
    names = ["intercept", "log_ratio", "size3"]
    for target in targets[1:]:
        cols.append(np.asarray([1.0 if r["target_key"] == target else 0.0 for r in records], dtype=float))
        names.append(f"target:{target}")
    X = np.column_stack(cols)
    y = np.asarray([r["y"] for r in records], dtype=float)
    w = np.asarray([r["weight"] for r in records], dtype=float)
    fit = fit_matrix(X, y, w, names, ridge=1e-4)
    return {
        "available": True,
        "reference_target": ref,
        "target_count": len(targets),
        "votes": len(records),
        "log_ratio_coefficient": fit["coefficients"]["log_ratio"],
        "size3_coefficient": fit["coefficients"]["size3"],
        "weighted_log_likelihood": fit["weighted_log_likelihood"],
        "note": "target fixed effects absorb target-specific baseline preference; ridge is stabilization only",
    }

def indifference_from_coefficients(coef, target_z=0.0, size3=0.0):
    alpha = float(coef.get("intercept", 0.0))
    gamma = float(coef.get("size3", 0.0))
    delta = float(coef.get("target_z", 0.0))
    beta = float(coef.get("log_ratio", 0.0))
    eta = float(coef.get("ratio_x_target_z", 0.0))
    denom = beta + eta * target_z
    if not math.isfinite(denom) or denom <= 1e-8:
        return None
    log_r = -(alpha + gamma * size3 + delta * target_z) / denom
    if not math.isfinite(log_r):
        return None
    r = math.exp(log_r)
    return float(r) if math.isfinite(r) else None

def target_reference_points(meta):
    vals = np.asarray(meta["unique_target_values"], dtype=float)
    logs = np.log(vals)
    refs = {}
    for label, q in (("p25",25),("median",50),("p75",75),("p90",90)):
        fv = float(np.percentile(vals, q))
        z = (math.log(fv) - meta["target_log_mean"]) / meta["target_log_sd"]
        refs[label] = {"target_fv": fv, "target_z": z}
    return refs

def indifference_table(model, refs, tested_min, tested_max):
    coef = model["coefficients"]
    rows = {}
    uses_target = "target_z" in coef or "ratio_x_target_z" in coef
    for label, ref in refs.items():
        z = ref["target_z"] if uses_target else 0.0
        row = {"target_fv": ref["target_fv"]}
        for size, size3 in ((2,0.0),(3,1.0)):
            r = indifference_from_coefficients(coef, z, size3)
            row[f"size{size}_ratio_50"] = r
            row[f"size{size}_within_tested_range"] = (
                r is not None and tested_min <= r <= tested_max
            )
        rows[label] = row
    return rows

def resample_voters(records, rng):
    by_voter = defaultdict(list)
    for r in records:
        by_voter[r["voter"]].append(r)
    voters = sorted(by_voter)
    sampled = [rng.choice(voters) for _ in voters]
    out = []
    for i, voter in enumerate(sampled):
        for r in by_voter[voter]:
            rr = dict(r)
            rr["voter"] = f"boot_{i}_{voter}"
            out.append(rr)
    return out

def bootstrap(records, tested_min, tested_max):
    rng = random.Random(BOOTSTRAP_SEED)
    ratio_coef, size_coef, interaction_coef = [], [], []
    r2, r3 = [], []
    within2, within3 = 0, 0
    for _ in range(BOOTSTRAP_REPS):
        sample = resample_voters(records, rng)
        m = fit_fields(sample, ["log_ratio", "size3"], ridge=1e-4)
        b = m["coefficients"]
        ratio_coef.append(b["log_ratio"])
        size_coef.append(b["size3"])
        rr2 = indifference_from_coefficients(b, 0.0, 0.0)
        rr3 = indifference_from_coefficients(b, 0.0, 1.0)
        if rr2 is not None:
            r2.append(rr2)
            within2 += int(tested_min <= rr2 <= tested_max)
        if rr3 is not None:
            r3.append(rr3)
            within3 += int(tested_min <= rr3 <= tested_max)

        mi = fit_fields(
            sample,
            ["log_ratio", "size3", "target_z", "ratio_x_target_z"],
            ridge=1e-4,
        )
        interaction_coef.append(mi["coefficients"]["ratio_x_target_z"])

    return {
        "reps": BOOTSTRAP_REPS,
        "seed": BOOTSTRAP_SEED,
        "log_ratio_coefficient": v1d.summarize_distribution(ratio_coef),
        "size3_coefficient": v1d.summarize_distribution(size_coef),
        "target_interaction_coefficient": v1d.summarize_distribution(interaction_coef),
        "ratio_positive_rate_pct": 100.0 * sum(x > 0 for x in ratio_coef) / len(ratio_coef),
        "size3_negative_rate_pct": 100.0 * sum(x < 0 for x in size_coef) / len(size_coef),
        "median_target_size2_indifference_ratio": v1d.summarize_distribution(r2),
        "median_target_size3_indifference_ratio": v1d.summarize_distribution(r3),
        "size2_indifference_within_tested_range_pct": 100.0 * within2 / max(1, len(r2)),
        "size3_indifference_within_tested_range_pct": 100.0 * within3 / max(1, len(r3)),
    }

def pooled_v2_v3_sensitivity(sheet_rows, v3_records):
    v2_doc = read_json(V2_CHALLENGES)
    v2_catalog = {c["id"]: c for c in v2_doc["challenges"]}
    raw_v2 = [v2p.parse_row(r) for r in sheet_rows if v2p.is_package_v2_row(r)]
    raw_v2 = [r for r in raw_v2 if r is not None]
    capped_v2, dropped_v2 = v2p.apply_daily_cap(raw_v2)
    v2_records = build_v2_records(capped_v2, v2_catalog)

    pooled = [dict(r) for r in v2_records]
    for r in v3_records:
        rr = dict(r)
        rr["experiment_v3"] = 1.0
        pooled.append(rr)

    counts = defaultdict(int)
    for r in pooled:
        counts[r["voter"]] += 1
    voter_ballot_weight = {
        voter: min(1.0, POOLED_EFFECTIVE_VOTE_CAP / count)
        for voter, count in counts.items()
    }
    for r in pooled:
        r["weight"] = voter_ballot_weight[r["voter"]]
        r["ratio_x_experiment_v3"] = r["log_ratio"] * float(r["experiment_v3"])

    base = fit_fields(pooled, ["log_ratio", "size3", "experiment_v3"], ridge=1e-5)
    interaction = fit_fields(
        pooled,
        ["log_ratio", "size3", "experiment_v3", "ratio_x_experiment_v3"],
        ridge=1e-5,
    )
    return {
        "status": "secondary_sensitivity_only",
        "v2_votes": len(v2_records),
        "v3_votes": len(v3_records),
        "combined_voters": len(counts),
        "combined_effective_ballot_cap_per_voter": POOLED_EFFECTIVE_VOTE_CAP,
        "v2_daily_cap_dropped": dropped_v2,
        "model_with_experiment_intercept": {
            "aic": base["aic"],
            "coefficients": base["coefficients"],
        },
        "model_with_experiment_slope_interaction": {
            "aic": interaction["aic"],
            "coefficients": interaction["coefficients"],
        },
        "note": (
            "V2 is reused only as a lower-ratio auxiliary dataset. The V3-only "
            "fit remains primary because package construction and tested ratio "
            "range differ by experiment."
        ),
    }

def conclusion(models, boot, summary, selected_name, selected_table):
    warnings = []
    if not summary["diagnostic_data_gates"]["all_passed"]:
        warnings.append("V3 diagnostic collection gates are not all passed")
    if boot["ratio_positive_rate_pct"] < 90.0:
        warnings.append("package acceptance does not rise reliably with raw FV ratio across voter clusters")
    if not summary["empirical_indifference_bracketing"]["fifty_pct_bracketed_by_endpoints"]:
        warnings.append("50% package-choice indifference is not empirically bracketed by the tested ratio endpoints")
    if boot["size3_negative_rate_pct"] < 80.0:
        warnings.append("3-player premium direction is not yet stable across voter clusters")

    selected_rows = selected_table.values()
    if not any(
        row.get("size2_within_tested_range") or row.get("size3_within_tested_range")
        for row in selected_rows
    ):
        warnings.append("selected model's 50% indifference estimate lies outside the tested range")

    return {
        "status": "hold_research" if warnings else "indifference_signal_identified_not_production_ready",
        "production_promotion_allowed": False,
        "warnings": warnings,
        "lowest_aic_model": selected_name,
        "note": (
            "V3 can nominate a shadow package-premium curve only. Live use still "
            "requires a separate package-adjustment implementation, torture tests, "
            "and prospective/OOS validation."
        ),
    }

def write_report(result):
    d = result["diagnostics"]
    data = result["data"]
    c = d["conclusion"]
    lines = [
        "# Package Vote V3 — Indifference Calibration Diagnostics",
        "",
        "**Status: RESEARCH ONLY — no production consumer changed.**",
        "",
        "V3 asks how much raw FV a 2- or 3-player package must contain before voters become indifferent to the concentrated target asset.",
        "",
        f"- Counted V3 votes: `{data['counted_votes']}`",
        f"- Unique V3 voters: `{data['unique_voters']}`",
        f"- Distinct challenges: `{data['distinct_challenges']}`",
        f"- Distinct targets: `{data['distinct_targets']}`",
        "",
        "## Diagnostic conclusion",
        "",
        f"- Status: `{c['status']}`",
        f"- Lowest-AIC V3-only model: `{c['lowest_aic_model']}`",
        "- Production promotion allowed: `False`",
    ]
    if c["warnings"]:
        lines += ["", "Warnings:"]
        lines += [f"- {w}" for w in c["warnings"]]

    lines += [
        "",
        "## V3-only candidate models",
        "",
        "| Model | AIC | coefficients |",
        "|---|---:|---|",
    ]
    for name, model in d["models"].items():
        if "aic" in model:
            lines.append(f"| {name} | {model['aic']:.2f} | `{model['coefficients']}` |")

    lines += [
        "",
        "## Estimated 50% package-choice ratios",
        "",
        "These are shadow estimates, not live adjustments.",
        "",
    ]
    for model_name, table in d["indifference_estimates"].items():
        lines += [
            f"### {model_name}",
            "",
            "| Target reference | Target FV | 2-player ratio | 3-player ratio |",
            "|---|---:|---:|---:|",
        ]
        for label, row in table.items():
            r2 = row["size2_ratio_50"]
            r3 = row["size3_ratio_50"]
            r2s = "n/a" if r2 is None else f"{r2:.3f}"
            r3s = "n/a" if r3 is None else f"{r3:.3f}"
            lines.append(f"| {label} | {row['target_fv']:.0f} | {r2s} | {r3s} |")
        lines.append("")

    b = d["voter_cluster_bootstrap"]
    lines += [
        "## Voter-cluster bootstrap",
        "",
        f"- Reps: `{b['reps']}`",
        f"- raw-ratio coefficient positive: `{b['ratio_positive_rate_pct']:.1f}%`",
        f"- 3-player coefficient negative: `{b['size3_negative_rate_pct']:.1f}%`",
        f"- median-target 2-player indifference median: `{b['median_target_size2_indifference_ratio']['median']}`",
        f"- median-target 2-player 5–95%: `{b['median_target_size2_indifference_ratio']['p05']}`–`{b['median_target_size2_indifference_ratio']['p95']}`",
        f"- median-target 3-player indifference median: `{b['median_target_size3_indifference_ratio']['median']}`",
        f"- median-target 3-player 5–95%: `{b['median_target_size3_indifference_ratio']['p05']}`–`{b['median_target_size3_indifference_ratio']['p95']}`",
        "",
        "## Target fixed-effects sensitivity",
        "",
        f"- Target count: `{d['target_fixed_effects'].get('target_count')}`",
        f"- log-ratio coefficient: `{d['target_fixed_effects'].get('log_ratio_coefficient')}`",
        f"- size3 coefficient: `{d['target_fixed_effects'].get('size3_coefficient')}`",
        "",
        "## V2 + V3 pooled sensitivity",
        "",
        f"- V2 auxiliary votes: `{d['pooled_v2_v3_sensitivity']['v2_votes']}`",
        f"- V3 primary votes: `{d['pooled_v2_v3_sensitivity']['v3_votes']}`",
        f"- Combined voters: `{d['pooled_v2_v3_sensitivity']['combined_voters']}`",
        "- V2 remains a separately labeled lower-ratio auxiliary dataset; it does not replace fresh V3 voting.",
        "",
        "## Guardrails",
        "",
        "- V2 remains frozen.",
        "- V3-only fit is primary.",
        "- V2+V3 pooling is sensitivity analysis only.",
        "- Bootstrap resamples whole voters.",
        "- No diagnostic model changes live player values or trade verdicts.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

def selftest():
    coef = {"intercept": -2.0, "log_ratio": 4.0, "size3": -0.4}
    r2 = indifference_from_coefficients(coef, 0.0, 0.0)
    r3 = indifference_from_coefficients(coef, 0.0, 1.0)
    assert r2 is not None and r3 is not None and r3 > r2 > 1.0
    fake = [
        {"y":0.0,"weight":1.0,"log_ratio":math.log(1.1),"size3":0.0,"target_z":0.0,"ratio_x_target_z":0.0},
        {"y":0.0,"weight":1.0,"log_ratio":math.log(1.2),"size3":1.0,"target_z":0.0,"ratio_x_target_z":0.0},
        {"y":1.0,"weight":1.0,"log_ratio":math.log(1.7),"size3":0.0,"target_z":0.0,"ratio_x_target_z":0.0},
        {"y":1.0,"weight":1.0,"log_ratio":math.log(1.8),"size3":1.0,"target_z":0.0,"ratio_x_target_z":0.0},
    ]
    m = fit_fields(fake, ["log_ratio", "size3"], ridge=1e-3)
    assert "log_ratio" in m["coefficients"]
    print("Package Preference V3 diagnostics self-test passed.")

def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    v3_doc = read_json(V3_CHALLENGES)
    v3_results = read_json(V3_RESULTS)
    gates = v3_results["summary"]["diagnostic_data_gates"]
    if not gates["all_passed"]:
        raise RuntimeError("V3 diagnostic gates are not all passed")

    sheet_rows = v3p.fetch_rows()
    raw_v3 = [v3p.parse_row(r) for r in sheet_rows if v3p.is_package_v3_row(r)]
    raw_v3 = [r for r in raw_v3 if r is not None]
    capped_v3, _dropped = v3p.apply_daily_cap(raw_v3)
    voter_weights = v3p.voter_weights(capped_v3)
    catalog = {c["id"]: c for c in v3_doc["challenges"]}
    records, meta = build_v3_records(capped_v3, catalog, voter_weights)

    models = {
        "ratio_only": fit_fields(records, ["log_ratio"], ridge=1e-5),
        "ratio_plus_size": fit_fields(records, ["log_ratio", "size3"], ridge=1e-5),
        "ratio_plus_size_target": fit_fields(
            records, ["log_ratio", "size3", "target_z"], ridge=1e-5
        ),
        "ratio_plus_size_target_interaction": fit_fields(
            records,
            ["log_ratio", "size3", "target_z", "ratio_x_target_z"],
            ridge=1e-5,
        ),
    }

    best_name = min(models, key=lambda name: models[name]["aic"])
    refs = target_reference_points(meta)
    tested_min = min(float(x) for x in v3_doc["design"]["ratio_targets"])
    tested_max = max(float(x) for x in v3_doc["design"]["ratio_targets"])
    indifference = {
        name: indifference_table(model, refs, tested_min, tested_max)
        for name, model in models.items()
    }

    boot = bootstrap(records, tested_min, tested_max)
    target_fe = fit_target_fixed_effects(records)
    pooled = pooled_v2_v3_sensitivity(sheet_rows, records)
    c = conclusion(
        models,
        boot,
        v3_results["summary"],
        best_name,
        indifference[best_name],
    )

    result = {
        "schema_version": 3,
        "status": "research_only",
        "production_consumer_changed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data": {
            "counted_votes": len(records),
            "unique_voters": len({r["voter"] for r in records}),
            "distinct_challenges": len({r["challenge_id"] for r in records}),
            "distinct_targets": len({r["target_key"] for r in records}),
            "tested_ratio_min": tested_min,
            "tested_ratio_max": tested_max,
        },
        "diagnostic_gates": gates,
        "diagnostics": {
            "models": models,
            "target_reference_points": refs,
            "indifference_estimates": indifference,
            "voter_cluster_bootstrap": boot,
            "target_fixed_effects": target_fe,
            "pooled_v2_v3_sensitivity": pooled,
            "conclusion": c,
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(result)
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    print(f"V3 conclusion: {c['status']} best={best_name}")

if __name__ == "__main__":
    main()

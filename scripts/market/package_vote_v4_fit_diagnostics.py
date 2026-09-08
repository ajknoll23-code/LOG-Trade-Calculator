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
import package_vote_v3_pipeline as v3p
import package_vote_v4_pipeline as v4p

V4_CHALLENGES = ROOT / "research" / "package-adjustment-v4" / "package_vote_challenges_v4.json"
V4_RESULTS = ROOT / "research" / "package-adjustment-v4" / "package_vote_v4_results.json"
V3_CHALLENGES = ROOT / "research" / "package-adjustment-v3" / "package_vote_challenges_v3.json"

OUT_JSON = ROOT / "research" / "package-adjustment-v4" / "package_vote_v4_fit_diagnostics.json"
OUT_MD = ROOT / "research" / "package-adjustment-v4" / "package_vote_v4_fit_diagnostics.md"

BOOTSTRAP_REPS = 400
BOOTSTRAP_SEED = 20260909
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

def build_v4_records(rows, catalog, voter_weights):
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
            "experiment":"v4",
            "challenge_id":c["id"],
            "voter":voter,
            "choice":row["choice"],
            "y":1.0 if row["choice"] == "P" else 0.0,
            "weight":float(voter_weights[voter]["ballot_weight"]),
            "ratio":float(c["raw_package_to_target_ratio"]),
            "ratio_target":float(c["ratio_target"]),
            "log_ratio":log_ratio,
            "target_key":c["target"]["key"],
            "target_name":c["target"]["name"],
            "target_fv":target_fv,
            "target_z":target_z,
            "ratio_x_target_z":log_ratio * target_z,
        })
    return out, {
        "target_log_mean":log_mean,
        "target_log_sd":log_sd,
        "unique_target_values":sorted(targets.values()),
    }

def indifference(coef, target_z=0.0):
    alpha = float(coef.get("intercept", 0.0))
    beta = float(coef.get("log_ratio", 0.0))
    delta = float(coef.get("target_z", 0.0))
    eta = float(coef.get("ratio_x_target_z", 0.0))
    denom = beta + eta * target_z
    if not math.isfinite(denom) or denom <= 1e-8:
        return None
    log_r = -(alpha + delta * target_z) / denom
    if not math.isfinite(log_r):
        return None
    r = math.exp(log_r)
    return float(r) if math.isfinite(r) else None

def target_refs(meta):
    vals = np.asarray(meta["unique_target_values"], dtype=float)
    refs = {}
    for label, q in (("p25",25),("median",50),("p75",75),("p90",90)):
        fv = float(np.percentile(vals, q))
        z = (math.log(fv) - meta["target_log_mean"]) / meta["target_log_sd"]
        refs[label] = {"target_fv":fv, "target_z":z}
    return refs

def table(model, refs, tested_min, tested_max):
    coef = model["coefficients"]
    uses_target = "target_z" in coef or "ratio_x_target_z" in coef
    out = {}
    for label, ref in refs.items():
        z = ref["target_z"] if uses_target else 0.0
        r = indifference(coef, z)
        out[label] = {
            "target_fv":ref["target_fv"],
            "ratio_50":r,
            "within_tested_range":r is not None and tested_min <= r <= tested_max,
        }
    return out

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
    ratio_coef, target_coef, median_ratios = [], [], []
    within = 0
    for _ in range(BOOTSTRAP_REPS):
        sample = resample_voters(records, rng)
        m = fit_fields(sample, ["log_ratio","target_z"], ridge=1e-4)
        b = m["coefficients"]
        ratio_coef.append(b["log_ratio"])
        target_coef.append(b["target_z"])
        r = indifference(b, 0.0)
        if r is not None:
            median_ratios.append(r)
            within += int(tested_min <= r <= tested_max)
    return {
        "reps":BOOTSTRAP_REPS,
        "seed":BOOTSTRAP_SEED,
        "log_ratio_coefficient":v1d.summarize_distribution(ratio_coef),
        "target_z_coefficient":v1d.summarize_distribution(target_coef),
        "ratio_positive_rate_pct":100.0 * sum(x > 0 for x in ratio_coef) / len(ratio_coef),
        "target_z_negative_rate_pct":100.0 * sum(x < 0 for x in target_coef) / len(target_coef),
        "median_target_indifference_ratio":v1d.summarize_distribution(median_ratios),
        "indifference_within_tested_range_pct":100.0 * within / max(1, len(median_ratios)),
    }

def pooled_v3_v4(sheet_rows, v4_records):
    v3_doc = read_json(V3_CHALLENGES)
    v3_catalog = {c["id"]: c for c in v3_doc["challenges"]}

    raw_v3 = [v3p.parse_row(r) for r in sheet_rows if v3p.is_package_v3_row(r)]
    raw_v3 = [r for r in raw_v3 if r is not None]
    capped_v3, dropped_v3 = v3p.apply_daily_cap(raw_v3)

    v3_records = []
    for row in capped_v3:
        c = v3_catalog.get(row["challenge_id"])
        if c is None or int(c["package_size"]) != 3:
            continue
        v3_records.append({
            "experiment":"v3",
            "experiment_v4":0.0,
            "voter":row["voter_roster_id"],
            "y":1.0 if row["choice"] == "P" else 0.0,
            "log_ratio":math.log(max(float(c["raw_package_to_target_ratio"]), 1e-12)),
        })

    pooled = [dict(r) for r in v3_records]
    for r in v4_records:
        pooled.append({
            "experiment":"v4",
            "experiment_v4":1.0,
            "voter":r["voter"],
            "y":r["y"],
            "log_ratio":r["log_ratio"],
        })

    counts = defaultdict(int)
    for r in pooled:
        counts[r["voter"]] += 1
    weights = {
        voter:min(1.0, POOLED_EFFECTIVE_VOTE_CAP / count)
        for voter, count in counts.items()
    }
    for r in pooled:
        r["weight"] = weights[r["voter"]]
        r["ratio_x_experiment_v4"] = r["log_ratio"] * r["experiment_v4"]

    base = fit_fields(pooled, ["log_ratio","experiment_v4"], ridge=1e-5)
    interaction = fit_fields(
        pooled,
        ["log_ratio","experiment_v4","ratio_x_experiment_v4"],
        ridge=1e-5,
    )
    return {
        "status":"secondary_sensitivity_only",
        "v3_three_player_votes":len(v3_records),
        "v4_votes":len(v4_records),
        "combined_voters":len(counts),
        "v3_daily_cap_dropped":dropped_v3,
        "model_with_experiment_intercept":{
            "aic":base["aic"],
            "coefficients":base["coefficients"],
        },
        "model_with_experiment_slope_interaction":{
            "aic":interaction["aic"],
            "coefficients":interaction["coefficients"],
        },
        "note":(
            "V4-only is primary for the high-ratio 3-player extension. "
            "V3 3-player ballots remain frozen lower-ratio auxiliary evidence."
        ),
    }

def conclusion(summary, boot, selected_table):
    warnings = []
    if not summary["diagnostic_data_gates"]["all_passed"]:
        warnings.append("V4 diagnostic collection gates are not all passed")
    if boot["ratio_positive_rate_pct"] < 90.0:
        warnings.append("package acceptance does not rise reliably with ratio across voter clusters")
    if not summary["empirical_indifference_bracketing"]["fifty_pct_bracketed_by_endpoints"]:
        warnings.append("50% package-choice indifference is not empirically bracketed by V4 endpoints")
    if boot["indifference_within_tested_range_pct"] < 80.0:
        warnings.append("bootstrap indifference estimate is not usually inside the V4 tested range")
    if not any(row["within_tested_range"] for row in selected_table.values()):
        warnings.append("selected model indifference estimates lie outside V4 tested range")
    return {
        "status":"hold_research" if warnings else "three_player_indifference_signal_identified_not_production_ready",
        "production_promotion_allowed":False,
        "warnings":warnings,
    }

def write_report(result):
    d = result["diagnostics"]
    lines = [
        "# Package Vote V4 — 3-Player Indifference Diagnostics",
        "",
        "**Status: RESEARCH ONLY — no production consumer changed.**",
        "",
        f"- Counted V4 votes: `{result['data']['counted_votes']}`",
        f"- Unique V4 voters: `{result['data']['unique_voters']}`",
        f"- Distinct challenges: `{result['data']['distinct_challenges']}`",
        f"- Distinct targets: `{result['data']['distinct_targets']}`",
        "",
        "## Candidate models",
        "",
        "| Model | AIC | coefficients |",
        "|---|---:|---|",
    ]
    for name, model in d["models"].items():
        lines.append(f"| {name} | {model['aic']:.2f} | `{model['coefficients']}` |")

    lines += [
        "",
        "## 50% package-choice ratio estimates",
        "",
    ]
    for name, rows in d["indifference_estimates"].items():
        lines += [
            f"### {name}",
            "",
            "| Target reference | Target FV | 3-player ratio | Inside V4 range |",
            "|---|---:|---:|---|",
        ]
        for label, row in rows.items():
            ratio = "n/a" if row["ratio_50"] is None else f"{row['ratio_50']:.3f}"
            lines.append(
                f"| {label} | {row['target_fv']:.0f} | {ratio} | {row['within_tested_range']} |"
            )
        lines.append("")

    b = d["voter_cluster_bootstrap"]
    lines += [
        "## Voter-cluster bootstrap",
        "",
        f"- Reps: `{b['reps']}`",
        f"- raw-ratio coefficient positive: `{b['ratio_positive_rate_pct']:.1f}%`",
        f"- target-value coefficient negative: `{b['target_z_negative_rate_pct']:.1f}%`",
        f"- median-target 3-player indifference median: `{b['median_target_indifference_ratio'].get('median')}`",
        f"- within V4 tested range: `{b['indifference_within_tested_range_pct']:.1f}%`",
        "",
        "## V3 + V4 pooled sensitivity",
        "",
        f"- Frozen V3 3-player auxiliary votes: `{d['v3_v4_pooled_sensitivity']['v3_three_player_votes']}`",
        f"- V4 primary votes: `{d['v3_v4_pooled_sensitivity']['v4_votes']}`",
        "",
        "## Conclusion",
        "",
        f"- Status: `{d['conclusion']['status']}`",
        f"- Production promotion allowed: `{d['conclusion']['production_promotion_allowed']}`",
    ]
    for warning in d["conclusion"]["warnings"]:
        lines.append(f"- Warning: {warning}")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

def selftest():
    fake = {"intercept":-4.0, "log_ratio":6.0, "target_z":-0.4}
    r = indifference(fake, 0.0)
    assert r is not None and 1.0 < r < 3.0
    assert indifference({"intercept":-1.0,"log_ratio":-1.0}, 0.0) is None
    print("Package Preference V4 diagnostics self-test passed.")

def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    result_doc = read_json(V4_RESULTS)
    summary = result_doc["summary"]
    if not summary["diagnostic_data_gates"]["all_passed"]:
        raise RuntimeError("V4 diagnostic gates are not all passed")

    challenge_doc = read_json(V4_CHALLENGES)
    catalog = {c["id"]: c for c in challenge_doc["challenges"]}

    sheet_rows = v4p.fetch_rows()
    raw = [v4p.parse_row(r) for r in sheet_rows if v4p.is_package_v4_row(r)]
    raw = [r for r in raw if r is not None]
    capped, _ = v4p.apply_daily_cap(raw)
    voter_weights = v4p.voter_weights(capped)

    records, meta = build_v4_records(capped, catalog, voter_weights)
    if len(records) != summary["raw_vote_count"]:
        raise RuntimeError("V4 record count mismatch")

    tested_min = min(float(x) for x in challenge_doc["design"]["ratio_targets"])
    tested_max = max(float(x) for x in challenge_doc["design"]["ratio_targets"])

    models = {
        "ratio_only":fit_fields(records, ["log_ratio"], ridge=1e-5),
        "ratio_plus_target":fit_fields(records, ["log_ratio","target_z"], ridge=1e-5),
        "ratio_plus_target_interaction":fit_fields(
            records,
            ["log_ratio","target_z","ratio_x_target_z"],
            ridge=1e-5,
        ),
    }
    refs = target_refs(meta)
    estimates = {
        name:table(model, refs, tested_min, tested_max)
        for name, model in models.items()
    }
    selected = "ratio_plus_target"
    boot = bootstrap(records, tested_min, tested_max)
    pooled = pooled_v3_v4(sheet_rows, records)

    payload = {
        "schema_version":4,
        "status":"research_only",
        "production_consumer_changed":False,
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "data":{
            "counted_votes":len(records),
            "unique_voters":len(voter_weights),
            "distinct_challenges":summary["distinct_challenges"],
            "distinct_targets":summary["distinct_targets"],
            "tested_ratio_min":tested_min,
            "tested_ratio_max":tested_max,
        },
        "diagnostic_gates":summary["diagnostic_data_gates"],
        "diagnostics":{
            "selected_interpretable_model":selected,
            "models":models,
            "indifference_estimates":estimates,
            "voter_cluster_bootstrap":boot,
            "v3_v4_pooled_sensitivity":pooled,
            "conclusion":conclusion(summary, boot, estimates[selected]),
        },
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(payload)
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")

if __name__ == "__main__":
    main()

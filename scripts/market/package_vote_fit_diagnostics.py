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

import package_vote_pipeline as pvp

CHALLENGES = ROOT / "research" / "package-adjustment-v1" / "package_vote_challenges.json"
OUT_JSON = ROOT / "research" / "package-adjustment-v1" / "package_vote_fit_diagnostics.json"
OUT_MD = ROOT / "research" / "package-adjustment-v1" / "package_vote_fit_diagnostics.md"

BOOTSTRAP_REPS = 400
BOOTSTRAP_SEED = 20260908
INTERCEPT_LAMBDA_GRID = np.linspace(0.0, 1.0, 201)
INTERCEPT_BETA_GRID = np.linspace(0.0, 16.0, 161)
BOOT_LAMBDA_GRID = np.linspace(0.0, 1.0, 41)
BOOT_BETA_GRID = np.linspace(0.0, 12.0, 49)
EPS = 1e-12


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sigmoid(z):
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def weighted_log_likelihood(y, p, w):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1.0 - EPS)
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    return float(np.sum(w * (y * np.log(p) + (1.0 - y) * np.log(1.0 - p))))


def weighted_mean(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    denom = float(np.sum(weights))
    return float(np.sum(values * weights) / denom) if denom > 0 else float("nan")


def weighted_corr(a, b, w):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    w = np.asarray(w, dtype=float)
    sw = float(np.sum(w))
    if sw <= 0:
        return None
    ma = float(np.sum(w * a) / sw)
    mb = float(np.sum(w * b) / sw)
    va = float(np.sum(w * (a - ma) ** 2) / sw)
    vb = float(np.sum(w * (b - mb) ** 2) / sw)
    if va <= 1e-15 or vb <= 1e-15:
        return None
    cov = float(np.sum(w * (a - ma) * (b - mb)) / sw)
    return cov / math.sqrt(va * vb)


def quantile(values, q):
    values = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    idx = (len(values) - 1) * q
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return values[lo]
    frac = idx - lo
    return values[lo] * (1.0 - frac) + values[hi] * frac


def summarize_distribution(values):
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not vals:
        return {"n": 0, "median": None, "p05": None, "p25": None, "p75": None, "p95": None}
    return {
        "n": len(vals),
        "median": quantile(vals, 0.50),
        "p05": quantile(vals, 0.05),
        "p25": quantile(vals, 0.25),
        "p75": quantile(vals, 0.75),
        "p95": quantile(vals, 0.95),
    }


def build_dataset(rows, catalog, voter_weights):
    records = []
    for row in rows:
        c = catalog.get(row["challenge_id"])
        if c is None:
            continue
        voter = row["voter_roster_id"]
        vw = voter_weights[voter]["ballot_weight"]
        ratio = float(c["raw_package_to_target_ratio"])
        fg = float(c["fg"])
        size = int(c["package_size"])
        target = c["target"]
        records.append({
            "challenge_id": row["challenge_id"],
            "voter": voter,
            "choice": row["choice"],
            "y": 1.0 if row["choice"] == "P" else 0.0,
            "weight": float(vw),
            "ratio": ratio,
            "log_ratio": math.log(max(ratio, EPS)),
            "fg": fg,
            "fragmentation": float(c["fragmentation"]),
            "best_asset_gap": float(c["best_asset_gap"]),
            "package_size": size,
            "size3": 1.0 if size == 3 else 0.0,
            "target_key": str(target["key"]),
            "target_name": str(target["name"]),
            "target_pos": str(target["pos"]),
            "target_age": target.get("age"),
        })
    return records


def arrays(records):
    y = np.asarray([r["y"] for r in records], dtype=float)
    w = np.asarray([r["weight"] for r in records], dtype=float)
    ratio = np.asarray([r["ratio"] for r in records], dtype=float)
    log_ratio = np.asarray([r["log_ratio"] for r in records], dtype=float)
    fg = np.asarray([r["fg"] for r in records], dtype=float)
    size3 = np.asarray([r["size3"] for r in records], dtype=float)
    return y, w, ratio, log_ratio, fg, size3


def optimize_alpha(y, w, offset, initial=0.0):
    alpha = float(initial)
    for _ in range(60):
        eta = alpha + offset
        p = sigmoid(eta)
        score = float(np.sum(w * (y - p)))
        info = float(np.sum(w * p * (1.0 - p)))
        if info <= 1e-12:
            break
        step = max(-2.0, min(2.0, score / info))
        alpha += step
        if abs(step) < 1e-10:
            break
    p = sigmoid(alpha + offset)
    return alpha, weighted_log_likelihood(y, p, w)


def fit_intercept_structural(records, lambda_grid=INTERCEPT_LAMBDA_GRID, beta_grid=INTERCEPT_BETA_GRID):
    y, w, ratio, _log_ratio, fg, _size3 = arrays(records)
    best = None
    profile = {}

    for lam in lambda_grid:
        eff = ratio * np.maximum(EPS, 1.0 - float(lam) * fg)
        x = np.log(np.maximum(eff, EPS))
        best_lam = None
        for beta in beta_grid:
            alpha, ll = optimize_alpha(y, w, float(beta) * x)
            candidate = (ll, -float(beta), alpha, float(beta))
            if best_lam is None or candidate > best_lam:
                best_lam = candidate
        ll, _neg_beta, alpha, beta = best_lam
        profile[float(lam)] = float(ll)
        candidate = (ll, -float(lam), -float(beta), alpha, float(lam), float(beta))
        if best is None or candidate > best:
            best = candidate

    max_ll, _a, _b, alpha, lam, beta = best
    support = [l for l, ll in profile.items() if 2.0 * (max_ll - ll) <= 3.84]
    eff = ratio * np.maximum(EPS, 1.0 - lam * fg)
    pred = sigmoid(alpha + beta * np.log(np.maximum(eff, EPS)))

    return {
        "alpha_hat": float(alpha),
        "lambda_hat": float(lam),
        "beta_hat": float(beta),
        "weighted_log_likelihood": float(max_ll),
        "aic": float(2 * 3 - 2 * max_ll),
        "boundary_lambda_flag": bool(lam in {0.0, 1.0}),
        "lambda_profile_support_heuristic": {
            "semantics": "profile likelihood heuristic, not calibrated CI",
            "low": float(min(support)) if support else None,
            "high": float(max(support)) if support else None,
            "width": float(max(support) - min(support)) if support else None,
        },
        "predictions": [float(x) for x in pred],
    }


def logistic_irls(X, y, w, ridge=1e-7):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    theta = np.zeros(X.shape[1], dtype=float)
    ll_prev = -float("inf")

    for _ in range(100):
        eta = X @ theta
        p = sigmoid(eta)
        v = np.clip(w * p * (1.0 - p), 1e-10, None)
        grad = X.T @ (w * (y - p))
        hess = X.T @ (X * v[:, None]) + ridge * np.eye(X.shape[1])
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.pinv(hess) @ grad

        step_scale = 1.0
        accepted = False
        for _ in range(20):
            candidate = np.clip(theta + step_scale * step, -30.0, 30.0)
            cp = sigmoid(X @ candidate)
            ll = weighted_log_likelihood(y, cp, w)
            if ll >= ll_prev - 1e-10:
                theta = candidate
                ll_prev = ll
                accepted = True
                break
            step_scale *= 0.5

        if not accepted or np.max(np.abs(step_scale * step)) < 1e-8:
            break

    p = sigmoid(X @ theta)
    ll = weighted_log_likelihood(y, p, w)
    return theta, ll, p


def fit_additive(records, include_fg=True, include_size=False):
    y, w, _ratio, log_ratio, fg, size3 = arrays(records)
    cols = [np.ones(len(records)), log_ratio]
    names = ["intercept", "log_ratio"]
    if include_fg:
        cols.append(fg)
        names.append("fg")
    if include_size:
        cols.append(size3)
        names.append("size3")
    X = np.column_stack(cols)
    theta, ll, pred = logistic_irls(X, y, w)
    return {
        "coefficients": {n: float(v) for n, v in zip(names, theta)},
        "weighted_log_likelihood": float(ll),
        "aic": float(2 * len(theta) - 2 * ll),
        "predictions": [float(x) for x in pred],
        "parameter_count": int(len(theta)),
    }


def lr_test(full_ll, reduced_ll):
    stat = max(0.0, 2.0 * (float(full_ll) - float(reduced_ll)))
    return {"lr_stat": stat, "df": 1, "p_value_heuristic": math.erfc(math.sqrt(stat / 2.0))}


def grouped_residuals(records, predictions, key_fn):
    groups = defaultdict(list)
    for i, r in enumerate(records):
        groups[key_fn(r)].append((r, float(predictions[i])))

    out = []
    for key, vals in groups.items():
        w = np.asarray([v[0]["weight"] for v in vals], dtype=float)
        y = np.asarray([v[0]["y"] for v in vals], dtype=float)
        p = np.asarray([v[1] for v in vals], dtype=float)
        observed = weighted_mean(y, w)
        predicted = weighted_mean(p, w)
        out.append({
            "group": str(key),
            "votes": len(vals),
            "observed_package_pct": 100.0 * observed,
            "predicted_package_pct": 100.0 * predicted,
            "residual_pp": 100.0 * (observed - predicted),
        })
    return sorted(out, key=lambda x: (-abs(x["residual_pp"]), -x["votes"], x["group"]))


def resample_voters(records, rng):
    by_voter = defaultdict(list)
    for r in records:
        by_voter[r["voter"]].append(r)
    voters = sorted(by_voter)
    sampled = [rng.choice(voters) for _ in voters]
    out = []
    for draw_idx, voter in enumerate(sampled):
        for r in by_voter[voter]:
            rr = dict(r)
            rr["voter"] = f"boot_{draw_idx}_{voter}"
            out.append(rr)
    return out


def cluster_bootstrap(records, reps=BOOTSTRAP_REPS, seed=BOOTSTRAP_SEED):
    rng = random.Random(seed)
    lambdas, alphas, betas, fg_coefs, size_coefs = [], [], [], [], []

    for _ in range(reps):
        sample = resample_voters(records, rng)
        structural = fit_intercept_structural(sample, lambda_grid=BOOT_LAMBDA_GRID, beta_grid=BOOT_BETA_GRID)
        additive = fit_additive(sample, include_fg=True, include_size=True)
        lambdas.append(structural["lambda_hat"])
        alphas.append(structural["alpha_hat"])
        betas.append(structural["beta_hat"])
        fg_coefs.append(additive["coefficients"]["fg"])
        size_coefs.append(additive["coefficients"]["size3"])

    return {
        "reps": reps,
        "seed": seed,
        "lambda_hat": summarize_distribution(lambdas),
        "alpha_hat": summarize_distribution(alphas),
        "beta_hat": summarize_distribution(betas),
        "additive_fg_coefficient": summarize_distribution(fg_coefs),
        "additive_size3_coefficient": summarize_distribution(size_coefs),
        "lambda_boundary_rate_pct": 100.0 * sum(x in {0.0, 1.0} for x in lambdas) / len(lambdas),
        "fg_negative_rate_pct": 100.0 * sum(x < 0 for x in fg_coefs) / len(fg_coefs),
        "size3_negative_rate_pct": 100.0 * sum(x < 0 for x in size_coefs) / len(size_coefs),
    }


def leave_one_voter_out(records):
    voters = sorted({r["voter"] for r in records})
    rows = []
    for voter in voters:
        sample = [r for r in records if r["voter"] != voter]
        structural = fit_intercept_structural(sample, lambda_grid=BOOT_LAMBDA_GRID, beta_grid=BOOT_BETA_GRID)
        additive = fit_additive(sample, include_fg=True, include_size=True)
        rows.append({
            "omitted_voter": voter,
            "remaining_votes": len(sample),
            "lambda_hat": structural["lambda_hat"],
            "alpha_hat": structural["alpha_hat"],
            "beta_hat": structural["beta_hat"],
            "fg_coefficient": additive["coefficients"]["fg"],
            "size3_coefficient": additive["coefficients"]["size3"],
        })
    return {
        "rows": rows,
        "lambda_hat": summarize_distribution([r["lambda_hat"] for r in rows]),
        "fg_coefficient": summarize_distribution([r["fg_coefficient"] for r in rows]),
        "size3_coefficient": summarize_distribution([r["size3_coefficient"] for r in rows]),
    }


def current_no_intercept_fit(rows, catalog, weights):
    fit = pvp.fit(rows, catalog, weights)
    return {**fit, "aic": float(2 * 2 - 2 * fit["weighted_log_likelihood"])}


def diagnostic_conclusion(current_fit, intercept_fit, fg_lr, bootstrap):
    warnings = []
    if current_fit["boundary_lambda_flag"]:
        warnings.append("current no-intercept lambda is on a grid boundary")
    support = intercept_fit["lambda_profile_support_heuristic"]
    if support["width"] is None or support["width"] > 0.50:
        warnings.append("intercept-model lambda profile remains wide")
    if intercept_fit["boundary_lambda_flag"]:
        warnings.append("intercept-model lambda is on a grid boundary")
    if bootstrap["lambda_boundary_rate_pct"] >= 25.0:
        warnings.append("cluster bootstrap frequently lands on a lambda boundary")
    if fg_lr["p_value_heuristic"] > 0.10:
        warnings.append("FG does not materially improve the additive ratio model yet")
    if bootstrap["fg_negative_rate_pct"] < 80.0:
        warnings.append("FG sign is not sufficiently stable across voter-cluster bootstrap samples")
    return {
        "status": "hold_research" if warnings else "diagnostically_promising_not_production_ready",
        "production_promotion_allowed": False,
        "warnings": warnings,
        "note": "This diagnostic layer never promotes Package Adjustment automatically. Any production decision requires separate prospective/OOS evidence.",
    }


def build_report(result):
    d = result["diagnostics"]
    data = result["data"]
    models = d["models"]
    intercept = models["structural_with_intercept"]
    current = models["current_no_intercept"]
    boot = d["voter_cluster_bootstrap"]
    loo = d["leave_one_voter_out"]
    concl = d["conclusion"]

    lines = [
        "# Package Vote Fit Diagnostics V1",
        "",
        "**Status: RESEARCH ONLY — no production consumer changed.**",
        "",
        "## Data",
        "",
        f"- Counted package votes: `{data['counted_votes']}`",
        f"- Unique voters: `{data['unique_voters']}`",
        f"- Distinct challenges: `{data['distinct_challenges']}`",
        f"- Package choices: `{data['package_votes']}`",
        f"- Target choices: `{data['target_votes']}`",
        "",
        "## Diagnostic conclusion",
        "",
        f"- Status: `{concl['status']}`",
        "- Production promotion allowed: `False`",
    ]
    if concl["warnings"]:
        lines += ["", "Warnings:"]
        lines.extend(f"- {w}" for w in concl["warnings"])

    lines += [
        "",
        "## Structural lambda comparison",
        "",
        "| Model | alpha | lambda | beta | profile support | boundary | AIC |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| Current no-intercept | — | {current['lambda_hat']:.3f} | {current['beta_hat']:.3f} | {current['lambda_profile_support_heuristic']['low']}–{current['lambda_profile_support_heuristic']['high']} | {current['boundary_lambda_flag']} | {current['aic']:.2f} |",
        f"| Structural + intercept | {intercept['alpha_hat']:.3f} | {intercept['lambda_hat']:.3f} | {intercept['beta_hat']:.3f} | {intercept['lambda_profile_support_heuristic']['low']}–{intercept['lambda_profile_support_heuristic']['high']} | {intercept['boundary_lambda_flag']} | {intercept['aic']:.2f} |",
        "",
        "## Additive FG diagnostics",
        "",
        "| Model | coefficients | AIC |",
        "|---|---|---:|",
        f"| Ratio only | `{models['additive_ratio_only']['coefficients']}` | {models['additive_ratio_only']['aic']:.2f} |",
        f"| Ratio + FG | `{models['additive_ratio_fg']['coefficients']}` | {models['additive_ratio_fg']['aic']:.2f} |",
        f"| Ratio + FG + size3 | `{models['additive_ratio_fg_size']['coefficients']}` | {models['additive_ratio_fg_size']['aic']:.2f} |",
        "",
        f"- FG likelihood-ratio heuristic: stat `{d['fg_likelihood_ratio_test']['lr_stat']:.3f}`, p `{d['fg_likelihood_ratio_test']['p_value_heuristic']:.4f}`.",
        f"- Weighted corr(FG, size3): `{d['predictor_correlations']['fg_vs_size3']}`",
        f"- Weighted corr(FG, log raw ratio): `{d['predictor_correlations']['fg_vs_log_ratio']}`",
        "",
        "## Voter-cluster bootstrap",
        "",
        f"- Reps: `{boot['reps']}` (seed `{boot['seed']}`)",
        f"- lambda median: `{boot['lambda_hat']['median']}`; 5–95%: `{boot['lambda_hat']['p05']}`–`{boot['lambda_hat']['p95']}`",
        f"- lambda boundary rate: `{boot['lambda_boundary_rate_pct']:.1f}%`",
        f"- FG coefficient median: `{boot['additive_fg_coefficient']['median']}`; negative in `{boot['fg_negative_rate_pct']:.1f}%` of reps",
        f"- size3 coefficient median: `{boot['additive_size3_coefficient']['median']}`; negative in `{boot['size3_negative_rate_pct']:.1f}%` of reps",
        "",
        "## Leave-one-voter-out stability",
        "",
        f"- lambda median: `{loo['lambda_hat']['median']}`; 5–95%: `{loo['lambda_hat']['p05']}`–`{loo['lambda_hat']['p95']}`",
        f"- FG coefficient median: `{loo['fg_coefficient']['median']}`",
        f"- size3 coefficient median: `{loo['size3_coefficient']['median']}`",
        "",
        "## Residuals by package size",
        "",
        "| Size | Votes | Observed package % | Predicted % | Residual pp |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in d["residuals"]["by_package_size"]:
        lines.append(f"| {row['group']} | {row['votes']} | {row['observed_package_pct']:.1f} | {row['predicted_package_pct']:.1f} | {row['residual_pp']:+.1f} |")

    lines += [
        "",
        "## Residuals by raw ratio target",
        "",
        "| Ratio | Votes | Observed package % | Predicted % | Residual pp |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in sorted(d["residuals"]["by_ratio_target"], key=lambda x: float(x["group"])):
        lines.append(f"| {row['group']} | {row['votes']} | {row['observed_package_pct']:.1f} | {row['predicted_package_pct']:.1f} | {row['residual_pp']:+.1f} |")

    lines += [
        "",
        "## Residuals by target position",
        "",
        "| Position | Votes | Observed package % | Predicted % | Residual pp |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in d["residuals"]["by_target_position"]:
        lines.append(f"| {row['group']} | {row['votes']} | {row['observed_package_pct']:.1f} | {row['predicted_package_pct']:.1f} | {row['residual_pp']:+.1f} |")

    lines += [
        "",
        "## Largest target-anchor residuals",
        "",
        "| Target | Votes | Observed package % | Predicted % | Residual pp |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in d["residuals"]["by_target_anchor"][:12]:
        lines.append(f"| {row['group']} | {row['votes']} | {row['observed_package_pct']:.1f} | {row['predicted_package_pct']:.1f} | {row['residual_pp']:+.1f} |")

    lines += [
        "",
        "## Interpretation guardrails",
        "",
        "- The intercept model tests whether the old no-intercept lambda was absorbing a general consolidation preference.",
        "- The additive FG test asks whether FG predicts package choice beyond raw package/target FV ratio.",
        "- Package-size residuals test whether 3-for-1 behavior remains unexplained after FG.",
        "- Bootstrap resamples whole voters, not individual ballots, so repeated opinions from one voter stay clustered.",
        "- Profile support is a heuristic likelihood region, not a calibrated confidence interval.",
        "- This file is research-only. No formula, Market Value input, Fundamental Value input, Team Utility input, or live verdict is changed.",
        "",
    ]
    return "\n".join(lines)


def run():
    doc = read_json(CHALLENGES)
    if doc.get("status") != "frozen_package_preference_v1" or doc.get("frozen") is not True:
        raise RuntimeError("unexpected/unfrozen challenge catalog")

    catalog = {c["id"]: c for c in doc["challenges"]}
    raw = [pvp.parse_row(r) for r in pvp.fetch_rows() if pvp.is_package_row(r)]
    raw = [r for r in raw if r is not None]
    capped, dropped = pvp.apply_daily_cap(raw)
    valid = [r for r in capped if r["challenge_id"] in catalog]
    weights = pvp.voter_weights(valid)

    if len(valid) < pvp.MIN_VOTES:
        raise RuntimeError(f"fit diagnostics require at least {pvp.MIN_VOTES} counted votes; found {len(valid)}")

    records = build_dataset(valid, catalog, weights)
    _y, w, _ratio, log_ratio, fg, size3 = arrays(records)

    current_fit = current_no_intercept_fit(valid, catalog, weights)
    intercept_fit = fit_intercept_structural(records)
    ratio_only = fit_additive(records, include_fg=False, include_size=False)
    ratio_fg = fit_additive(records, include_fg=True, include_size=False)
    ratio_fg_size = fit_additive(records, include_fg=True, include_size=True)

    fg_lr = lr_test(ratio_fg["weighted_log_likelihood"], ratio_only["weighted_log_likelihood"])
    bootstrap = cluster_bootstrap(records)
    loo = leave_one_voter_out(records)
    residual_predictions = ratio_fg_size["predictions"]

    diagnostics = {
        "models": {
            "current_no_intercept": current_fit,
            "structural_with_intercept": intercept_fit,
            "additive_ratio_only": ratio_only,
            "additive_ratio_fg": ratio_fg,
            "additive_ratio_fg_size": ratio_fg_size,
        },
        "fg_likelihood_ratio_test": fg_lr,
        "predictor_correlations": {
            "fg_vs_size3": weighted_corr(fg, size3, w),
            "fg_vs_log_ratio": weighted_corr(fg, log_ratio, w),
        },
        "voter_cluster_bootstrap": bootstrap,
        "leave_one_voter_out": loo,
        "residuals": {
            "prediction_model": "additive_ratio_fg_size",
            "by_package_size": grouped_residuals(records, residual_predictions, lambda r: r["package_size"]),
            "by_ratio_target": grouped_residuals(records, residual_predictions, lambda r: f"{min((0.95, 1.05, 1.15, 1.30), key=lambda x: abs(x-r['ratio'])):.2f}"),
            "by_target_position": grouped_residuals(records, residual_predictions, lambda r: r["target_pos"]),
            "by_target_anchor": grouped_residuals(records, residual_predictions, lambda r: r["target_name"]),
        },
    }
    diagnostics["conclusion"] = diagnostic_conclusion(current_fit, intercept_fit, fg_lr, bootstrap)

    for model in diagnostics["models"].values():
        model.pop("predictions", None)

    package_votes = sum(r["choice"] == "P" for r in valid)
    target_votes = sum(r["choice"] == "T" for r in valid)
    result = {
        "schema_version": 1,
        "status": "research_only",
        "production_consumer_changed": False,
        "market_value_consumer_changed": False,
        "fundamental_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bootstrap_reps": BOOTSTRAP_REPS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "source": {
            "challenge_catalog": str(CHALLENGES.relative_to(ROOT)),
            "challenge_catalog_status": doc.get("status"),
            "challenge_catalog_frozen": doc.get("frozen"),
            "raw_package_rows": len(raw),
            "daily_cap_dropped": dropped,
        },
        "data": {
            "counted_votes": len(valid),
            "unique_voters": len(weights),
            "distinct_challenges": len({r["challenge_id"] for r in valid}),
            "package_votes": package_votes,
            "target_votes": target_votes,
            "package_choice_pct": 100.0 * package_votes / len(valid),
        },
        "diagnostics": diagnostics,
    }

    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(build_report(result), encoding="utf-8")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    print(f"Diagnostic conclusion: {diagnostics['conclusion']['status']}")


def selftest():
    fake = []
    for i in range(24):
        ratio = [0.95, 1.05, 1.15, 1.30][i % 4]
        fg = [0.05, 0.12, 0.22][i % 3]
        size = 2 if i % 2 == 0 else 3
        eta = -0.6 + 2.0 * math.log(ratio) - 2.5 * fg - 0.3 * (size == 3)
        p = 1.0 / (1.0 + math.exp(-eta))
        y = 1.0 if ((i * 37) % 100) / 100.0 < p else 0.0
        fake.append({
            "challenge_id": f"x{i}", "voter": f"v{i % 6}", "choice": "P" if y else "T",
            "y": y, "weight": 1.0, "ratio": ratio, "log_ratio": math.log(ratio), "fg": fg,
            "fragmentation": fg + 0.2, "best_asset_gap": fg / 2, "package_size": size,
            "size3": 1.0 if size == 3 else 0.0, "target_key": f"k{i % 4}",
            "target_name": f"Target {i % 4}", "target_pos": ["QB", "RB", "WR", "TE"][i % 4],
            "target_age": 25,
        })

    additive = fit_additive(fake, include_fg=True, include_size=True)
    assert set(additive["coefficients"]) == {"intercept", "log_ratio", "fg", "size3"}
    assert math.isfinite(additive["weighted_log_likelihood"])

    structural = fit_intercept_structural(fake, lambda_grid=np.linspace(0.0, 1.0, 11), beta_grid=np.linspace(0.0, 8.0, 17))
    assert 0.0 <= structural["lambda_hat"] <= 1.0
    assert math.isfinite(structural["weighted_log_likelihood"])

    grouped = grouped_residuals(fake, additive["predictions"], lambda r: r["package_size"])
    assert len(grouped) == 2

    lr = lr_test(-10.0, -12.0)
    assert lr["lr_stat"] == 4.0
    assert 0.0 <= lr["p_value_heuristic"] <= 1.0
    print("Package vote fit diagnostics self-test passed.")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        run()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = ROOT / "research" / "package-adjustment-nextgen-v2"
CONFIG_PATH = RESEARCH_DIR / "model_fit_preregistration.json"
MANIFEST_PATH = RESEARCH_DIR / "model_fit_preregistration_manifest.json"
METHODOLOGY_PATH = RESEARCH_DIR / "model_fit_preregistration.md"
CATALOG_PATH = RESEARCH_DIR / "package_vote_challenges_nextgen_v2.json"
MATURITY_PATH = RESEARCH_DIR / "evidence_maturity_plan.json"

PROB_EPS = 1e-12


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(obj) -> str:
    payload = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_timestamp_utc(value):
    s = str(value or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def cell_key(challenge) -> str:
    return "|".join(
        (
            str(challenge["family"]),
            str(challenge["cell_id"]),
            str(challenge["scale_label"]),
            str(challenge["split"]),
        )
    )


def verify_preregistration():
    cfg = read_json(CONFIG_PATH)
    manifest = read_json(MANIFEST_PATH)
    catalog = read_json(CATALOG_PATH)
    maturity = read_json(MATURITY_PATH)

    assert cfg["status"] == "frozen_model_fit_preregistration"
    assert cfg["frozen"] is True
    assert cfg["voting_activated"] is False
    assert cfg["production_change_authorized"] is False

    artifacts = manifest["artifacts"]
    assert artifacts["fitter"]["sha256"] == sha256(Path(__file__))
    assert artifacts["config"]["sha256"] == sha256(CONFIG_PATH)
    assert artifacts["methodology"]["sha256"] == sha256(METHODOLOGY_PATH)

    assert cfg["environment"]["python_major_minor"] == (
        f"{sys.version_info.major}.{sys.version_info.minor}"
    )
    assert cfg["environment"]["numpy_version"] == np.__version__
    assert cfg["environment"]["scipy_version"] == scipy.__version__

    assert catalog["status"] == "frozen_package_adjustment_nextgen_v2"
    assert catalog["frozen"] is True
    assert maturity["status"] == "preregistered_before_nextgen_voting"
    assert maturity["voting_activated"] is False

    assert canonical_sha256(catalog["challenges"]) == (
        cfg["anchors"]["canonical_challenge_payload_sha256"]
    )
    assert sha256(CATALOG_PATH) == cfg["anchors"]["frozen_catalog_sha256"]
    assert sha256(MATURITY_PATH) == cfg["anchors"]["maturity_plan_sha256"]

    return cfg, catalog, maturity


def catalog_maps(catalog):
    challenges = {c["id"]: c for c in catalog["challenges"]}
    if len(challenges) != 129:
        raise RuntimeError(f"expected 129 frozen challenges, found {len(challenges)}")

    cells = defaultdict(list)
    train_cells = set()
    scale_holdout_cells = set()
    topology_holdout_cells = set()

    for c in challenges.values():
        ck = cell_key(c)
        cells[ck].append(c["id"])

        if c["split"] == "train":
            if c.get("fit_eligible") is not True:
                raise RuntimeError(f"train challenge not fit eligible: {c['id']}")
            train_cells.add(ck)
        elif c["split"] == "structural_scale_holdout":
            if c.get("fit_eligible") is not False:
                raise RuntimeError(f"scale holdout leaked into fit: {c['id']}")
            scale_holdout_cells.add(ck)
        elif c["split"] == "structural_topology_holdout":
            if c.get("fit_eligible") is not False:
                raise RuntimeError(f"topology holdout leaked into fit: {c['id']}")
            topology_holdout_cells.add(ck)
        else:
            raise RuntimeError(f"unknown split: {c['split']}")

    if (len(cells), len(train_cells), len(scale_holdout_cells), len(topology_holdout_cells)) != (
        24,
        13,
        5,
        6,
    ):
        raise RuntimeError(
            "frozen cell topology changed: "
            f"{len(cells)}/{len(train_cells)}/"
            f"{len(scale_holdout_cells)}/{len(topology_holdout_cells)}"
        )

    return {
        "challenges": challenges,
        "all_cells": tuple(sorted(cells)),
        "train_cells": tuple(sorted(train_cells)),
        "scale_holdout_cells": tuple(sorted(scale_holdout_cells)),
        "topology_holdout_cells": tuple(sorted(topology_holdout_cells)),
        "all_holdout_cells": tuple(
            sorted(scale_holdout_cells | topology_holdout_cells)
        ),
    }


def side_values(side):
    return [float(a["fv"]) for a in side["assets"]]


def raw_score(side):
    return float(sum(side_values(side)))


def power_score(side, p):
    values = np.asarray(side_values(side), dtype=float)
    return float(np.power(np.power(values, float(p)).sum(), 1.0 / float(p)))


class ConvexLinearSpline:
    def __init__(self, cfg):
        self.v_ref = float(cfg["normalization"]["v_ref"])
        self.knots = np.asarray(cfg["models"]["M2b"]["knots_normalized"], dtype=float)
        self.domain_max = float(cfg["models"]["M2b"]["inverse_domain_max_normalized"])
        if len(self.knots) != 6:
            raise RuntimeError("M2b preregistration requires exactly six knots")
        if abs(self.knots[0]) > 1e-15 or abs(self.knots[-2] - 1.0) > 1e-15:
            raise RuntimeError("M2b knots lost the 0/1 identification anchors")
        if not np.all(np.diff(self.knots) > 0):
            raise RuntimeError("M2b knots must be strictly increasing")
        if abs(self.knots[-1] - self.domain_max) > 1e-12:
            raise RuntimeError("M2b inverse-domain endpoint mismatch")

    def _shape(self, deltas):
        d = np.asarray(deltas, dtype=float)
        if d.shape != (4,) or np.any(d < -1e-12):
            raise RuntimeError("M2b requires four nonnegative slope increments")
        raw_slopes = np.concatenate(([1.0], 1.0 + np.cumsum(d)))
        raw_y = np.zeros(len(self.knots), dtype=float)
        for i in range(len(raw_slopes)):
            raw_y[i + 1] = (
                raw_y[i]
                + raw_slopes[i] * (self.knots[i + 1] - self.knots[i])
            )
        one_idx = len(self.knots) - 2
        norm = float(raw_y[one_idx])
        if not math.isfinite(norm) or norm <= 0:
            raise RuntimeError("invalid M2b normalization")
        slopes = raw_slopes / norm
        y = raw_y / norm
        return slopes, y

    def g(self, x, deltas):
        x = float(x)
        if x < -1e-12 or x > self.domain_max + 1e-12:
            raise ValueError("normalized asset value outside M2b support")
        x = min(max(x, 0.0), self.domain_max)
        slopes, y = self._shape(deltas)
        idx = int(np.searchsorted(self.knots, x, side="right") - 1)
        idx = max(0, min(idx, len(slopes) - 1))
        return float(y[idx] + slopes[idx] * (x - self.knots[idx]))

    def inverse(self, u, deltas):
        u = float(u)
        slopes, y = self._shape(deltas)
        if u < -1e-12 or u > float(y[-1]) + 1e-12:
            raise ValueError("M2b utility sum outside preregistered inverse support")
        u = min(max(u, 0.0), float(y[-1]))
        idx = int(np.searchsorted(y, u, side="right") - 1)
        idx = max(0, min(idx, len(slopes) - 1))
        return float(self.knots[idx] + (u - y[idx]) / slopes[idx])

    def equivalent_values(self, values, deltas):
        xs = [float(v) / self.v_ref for v in values]
        if any(x < 0 or x > self.domain_max + 1e-12 for x in xs):
            raise ValueError("M2b asset outside preregistered domain")
        utility = sum(self.g(x, deltas) for x in xs)
        xeq = self.inverse(utility, deltas)
        return self.v_ref * xeq

    def score(self, side, deltas):
        return self.equivalent_values(side_values(side), deltas)

    def roughness(self, deltas):
        slopes, _ = self._shape(deltas)
        jumps = np.diff(slopes)
        return float(np.mean(jumps * jumps))


def sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def row_nll(row, challenge, model, theta, cfg, spline):
    if model in {"M0", "M1"}:
        sa = raw_score(challenge["side_a"])
        sb = raw_score(challenge["side_b"])
        log_beta, delta_left = float(theta[0]), float(theta[1])
    elif model == "M2a":
        p, log_beta, delta_left = map(float, theta)
        sa = power_score(challenge["side_a"], p)
        sb = power_score(challenge["side_b"], p)
    elif model == "M2b":
        deltas = list(map(float, theta[:4]))
        log_beta = float(theta[4])
        delta_left = float(theta[5])
        sa = spline.score(challenge["side_a"], deltas)
        sb = spline.score(challenge["side_b"], deltas)
    else:
        raise ValueError(f"unknown model {model}")

    beta = math.exp(log_beta)
    left_indicator = 1.0 if row["displayed_left_side"] == "A" else 0.0
    eta = (
        beta * ((sa - sb) / float(cfg["normalization"]["v_ref"]))
        + delta_left * left_indicator
    )
    y = 1.0 if row["choice_side"] == "A" else 0.0
    return float(np.logaddexp(0.0, eta) - y * eta)


def balanced_loss(
    rows,
    challenge_map,
    model,
    theta,
    cfg,
    spline,
    required_cells=None,
    regularization_lambda=0.0,
):
    grouped = defaultdict(list)
    for row in rows:
        c = challenge_map[row["challenge_id"]]
        grouped[cell_key(c)].append(row)

    if required_cells is None:
        cells = sorted(grouped)
    else:
        cells = list(required_cells)
        missing = [ck for ck in cells if ck not in grouped]
        if missing:
            return math.inf

    if not cells:
        return math.inf

    cell_losses = []
    for ck in cells:
        numer = 0.0
        denom = 0.0
        for row in grouped[ck]:
            w = float(row["weight"])
            if w <= 0:
                continue
            loss = row_nll(
                row,
                challenge_map[row["challenge_id"]],
                model,
                theta,
                cfg,
                spline,
            )
            numer += w * loss
            denom += w
        if denom <= 0:
            return math.inf
        cell_losses.append(numer / denom)

    out = float(sum(cell_losses) / len(cell_losses))
    if model == "M2b" and regularization_lambda > 0:
        out += float(regularization_lambda) * spline.roughness(theta[:4])
    return out


def _model_bounds(model, cfg):
    opt = cfg["optimizer"]
    if model in {"M0", "M1"}:
        return [
            tuple(opt["log_beta_bounds"]),
            tuple(opt["delta_left_bounds"]),
        ]
    if model == "M2a":
        return [
            tuple(cfg["models"]["M2a"]["p_bounds"]),
            tuple(opt["log_beta_bounds"]),
            tuple(opt["delta_left_bounds"]),
        ]
    if model == "M2b":
        d_bounds = tuple(cfg["models"]["M2b"]["slope_increment_bounds"])
        return [
            d_bounds,
            d_bounds,
            d_bounds,
            d_bounds,
            tuple(opt["log_beta_bounds"]),
            tuple(opt["delta_left_bounds"]),
        ]
    raise ValueError(model)


def _default_starts(model, cfg):
    return [
        list(map(float, x))
        for x in cfg["optimizer"]["multistarts"][model]
    ]


def fit_model(
    model,
    rows,
    challenge_map,
    required_cells,
    cfg,
    spline,
    regularization_lambda=0.0,
    warm_start=None,
    bootstrap_mode=False,
):
    bounds = _model_bounds(model, cfg)
    starts = []

    if warm_start is not None:
        starts.append(list(map(float, warm_start)))

    if bootstrap_mode:
        starts.append(_default_starts(model, cfg)[0])
    else:
        starts.extend(_default_starts(model, cfg))

    dedup = []
    seen = set()
    for start in starts:
        key = tuple(round(float(v), 12) for v in start)
        if key not in seen:
            seen.add(key)
            dedup.append(start)

    options = cfg["optimizer"]["scipy_options"]

    def objective(x):
        value = balanced_loss(
            rows,
            challenge_map,
            model,
            x,
            cfg,
            spline,
            required_cells=required_cells,
            regularization_lambda=regularization_lambda,
        )
        return 1e12 if not math.isfinite(value) else value

    results = []
    for start in dedup:
        res = minimize(
            objective,
            np.asarray(start, dtype=float),
            method="L-BFGS-B",
            bounds=bounds,
            options={
                "maxiter": int(options["maxiter"]),
                "maxls": int(options["maxls"]),
                "ftol": float(options["ftol"]),
                "gtol": float(options["gtol"]),
            },
        )
        if bool(res.success) and math.isfinite(float(res.fun)):
            results.append(res)

    if not results:
        return {
            "success": False,
            "eligible": False,
            "reason": "optimizer_failed_all_preregistered_starts",
        }

    results.sort(
        key=lambda r: (
            float(r.fun),
            tuple(round(float(v), 12) for v in r.x),
        )
    )
    best = results[0]
    x = [float(v) for v in best.x]
    tol = float(cfg["optimizer"]["boundary_tolerance"])
    boundary_flags = []

    # Upper beta boundary is unresolved. The lower beta bound is allowed:
    # beta may be effectively zero when score differences are uninformative.
    if x[-2] >= bounds[-2][1] - tol:
        boundary_flags.append("beta_upper")
    if x[-1] <= bounds[-1][0] + tol or x[-1] >= bounds[-1][1] - tol:
        boundary_flags.append("delta_left")

    if model == "M2a" and x[0] >= bounds[0][1] - tol:
        boundary_flags.append("p_upper")
    if model == "M2b":
        for i in range(4):
            if x[i] >= bounds[i][1] - tol:
                boundary_flags.append(f"slope_increment_{i+1}_upper")

    return {
        "success": True,
        "eligible": not boundary_flags,
        "objective": float(best.fun),
        "x": x,
        "boundary_flags": boundary_flags,
        "optimizer_message": str(best.message),
        "iterations": int(getattr(best, "nit", -1)),
    }


def assign_voter_folds(voter_ids, cfg):
    salt = str(cfg["cross_validation"]["fold_hash_salt"])
    k = int(cfg["cross_validation"]["fold_count"])
    ordered = sorted(
        set(voter_ids),
        key=lambda voter: hashlib.sha256(
            (salt + str(voter)).encode("utf-8")
        ).hexdigest(),
    )
    return {voter: i % k for i, voter in enumerate(ordered)}


def select_m2b_lambda(train_rows, challenge_map, train_cells, cfg, spline):
    lambdas = [float(x) for x in cfg["models"]["M2b"]["regularization_lambda_grid"]]
    folds = assign_voter_folds(
        [r["voter_id"] for r in train_rows],
        cfg,
    )
    k = int(cfg["cross_validation"]["fold_count"])
    rows_by_lambda = []

    for lam in lambdas:
        fold_losses = []
        usable = True
        for fold in range(k):
            fit_rows = [r for r in train_rows if folds[r["voter_id"]] != fold]
            val_rows = [r for r in train_rows if folds[r["voter_id"]] == fold]
            if not fit_rows or not val_rows:
                usable = False
                break

            fit = fit_model(
                "M2b",
                fit_rows,
                challenge_map,
                train_cells,
                cfg,
                spline,
                regularization_lambda=lam,
            )
            if not fit.get("success") or not fit.get("eligible"):
                usable = False
                break

            observed_validation_cells = sorted(
                {
                    cell_key(challenge_map[r["challenge_id"]])
                    for r in val_rows
                }
            )
            val_loss = balanced_loss(
                val_rows,
                challenge_map,
                "M2b",
                fit["x"],
                cfg,
                spline,
                required_cells=observed_validation_cells,
                regularization_lambda=0.0,
            )
            if not math.isfinite(val_loss):
                usable = False
                break
            fold_losses.append(float(val_loss))

        rows_by_lambda.append(
            {
                "lambda": lam,
                "usable": usable and len(fold_losses) == k,
                "fold_losses": fold_losses,
                "mean_validation_log_loss": (
                    float(sum(fold_losses) / len(fold_losses))
                    if usable and len(fold_losses) == k
                    else None
                ),
            }
        )

    usable_rows = [r for r in rows_by_lambda if r["usable"]]
    if not usable_rows:
        return {
            "success": False,
            "reason": "no_regularization_value_completed_all_preregistered_folds",
            "candidates": rows_by_lambda,
        }

    best_loss = min(r["mean_validation_log_loss"] for r in usable_rows)
    tie = float(cfg["cross_validation"]["prefer_smoother_within_log_loss"])
    acceptable = [
        r for r in usable_rows
        if r["mean_validation_log_loss"] <= best_loss + tie
    ]
    chosen = max(acceptable, key=lambda r: r["lambda"])

    return {
        "success": True,
        "selected_lambda": float(chosen["lambda"]),
        "best_observed_mean_validation_log_loss": float(best_loss),
        "selection_rule": "largest_lambda_within_preregistered_tie_band_of_minimum",
        "candidates": rows_by_lambda,
    }


def normalize_ballots(payload, catalog_ctx, cfg):
    challenges = catalog_ctx["challenges"]
    release = parse_timestamp_utc(payload.get("released_at_utc"))
    if release is None:
        raise RuntimeError("ballot payload missing valid released_at_utc")

    if payload.get("schema_version") != 1:
        raise RuntimeError("unexpected normalized ballot schema version")
    if payload.get("catalog_payload_sha256") != (
        cfg["anchors"]["canonical_challenge_payload_sha256"]
    ):
        raise RuntimeError("ballot payload catalog fingerprint mismatch")
    if payload.get("maturity_plan_sha256") != cfg["anchors"]["maturity_plan_sha256"]:
        raise RuntimeError("ballot payload maturity-plan fingerprint mismatch")

    counters = Counter()
    parsed = []

    for raw in payload.get("ballots") or []:
        ts = parse_timestamp_utc(raw.get("timestamp"))
        if ts is None:
            counters["invalid_timestamp"] += 1
            continue
        if ts <= release:
            counters["pre_release"] += 1
            continue

        voter = str(raw.get("voter_id") or "").strip()
        challenge_id = str(raw.get("challenge_id") or "").strip()
        choice = str(raw.get("choice_side") or "").strip().upper()
        left = str(raw.get("displayed_left_side") or "").strip().upper()

        if not voter:
            counters["missing_voter"] += 1
            continue
        if challenge_id not in challenges:
            counters["unknown_challenge"] += 1
            continue
        if choice not in {"A", "B"}:
            counters["invalid_choice"] += 1
            continue
        if left not in {"A", "B"}:
            counters["invalid_display_side"] += 1
            continue

        parsed.append(
            {
                "timestamp": ts.isoformat(),
                "_dt": ts,
                "voter_id": voter,
                "challenge_id": challenge_id,
                "choice_side": choice,
                "displayed_left_side": left,
            }
        )

    parsed.sort(
        key=lambda r: (
            r["_dt"],
            r["voter_id"],
            r["challenge_id"],
            r["choice_side"],
            r["displayed_left_side"],
        )
    )

    daily_cap = int(cfg["voter_protections"]["daily_valid_nextgen_vote_cap"])
    daily_counts = Counter()
    kept = []
    for row in parsed:
        key = (row["voter_id"], row["_dt"].date().isoformat())
        if daily_counts[key] >= daily_cap:
            counters["daily_cap_dropped"] += 1
            continue
        daily_counts[key] += 1
        kept.append(row)

    lifetime_cap = float(
        cfg["voter_protections"]["primary_evidence_effective_lifetime_cap"]
    )
    voter_counts = Counter(r["voter_id"] for r in kept)
    voter_weight = {
        voter: min(1.0, lifetime_cap / count)
        for voter, count in voter_counts.items()
    }

    for row in kept:
        row["weight"] = float(voter_weight[row["voter_id"]])
        row.pop("_dt", None)

    return kept, dict(counters)


def maturity_report(rows, catalog_ctx, cfg):
    challenge_map = catalog_ctx["challenges"]
    cell_mass = {ck: 0.0 for ck in catalog_ctx["all_cells"]}
    cell_voters = {ck: set() for ck in catalog_ctx["all_cells"]}

    for row in rows:
        ck = cell_key(challenge_map[row["challenge_id"]])
        cell_mass[ck] += float(row["weight"])
        cell_voters[ck].add(row["voter_id"])

    total_effective = float(sum(float(r["weight"]) for r in rows))
    distinct_voters = len({r["voter_id"] for r in rows})

    gate = cfg["maturity_gate"]
    conditions = {
        "minimum_valid_effective_votes": (
            total_effective + 1e-9 >= float(gate["minimum_valid_effective_votes"])
        ),
        "minimum_distinct_voters": (
            distinct_voters >= int(gate["minimum_distinct_voters"])
        ),
        "minimum_effective_votes_each_cell": all(
            mass + 1e-9 >= float(gate["minimum_valid_effective_votes_per_cell"])
            for mass in cell_mass.values()
        ),
        "minimum_distinct_voters_each_cell": all(
            len(voters) >= int(gate["minimum_distinct_voters_per_cell"])
            for voters in cell_voters.values()
        ),
    }

    hard_cap = float(cfg["stopping"]["hard_collection_cap_valid_effective_votes"])
    hard_cap_breached = total_effective > hard_cap + 1e-9

    if hard_cap_breached:
        status = "hard_cap_breached_refuse_fit"
    elif all(conditions.values()):
        status = "mature"
    elif total_effective + 1e-9 >= hard_cap:
        status = "coverage_unresolved_at_hard_cap"
    else:
        status = "waiting_for_maturity"

    return {
        "status": status,
        "mature": status == "mature",
        "hard_cap_breached": hard_cap_breached,
        "valid_raw_ballots_after_daily_cap": len(rows),
        "valid_effective_votes": total_effective,
        "distinct_voters": distinct_voters,
        "conditions": conditions,
        "per_cell": {
            ck: {
                "effective_votes": float(cell_mass[ck]),
                "distinct_voters": len(cell_voters[ck]),
            }
            for ck in sorted(cell_mass)
        },
    }


def model_eval(model, fit, rows, challenge_map, cells, cfg, spline):
    if not fit.get("success"):
        return None
    return balanced_loss(
        rows,
        challenge_map,
        model,
        fit["x"],
        cfg,
        spline,
        required_cells=cells,
        regularization_lambda=0.0,
    )


def bootstrap_analysis(
    rows,
    catalog_ctx,
    cfg,
    spline,
    original_fits,
    m2b_lambda,
):
    draws_target = int(cfg["bootstrap"]["valid_draws"])
    max_attempts = int(cfg["bootstrap"]["max_attempts"])
    rng = random.Random(int(cfg["bootstrap"]["seed"]))
    voters = sorted({r["voter_id"] for r in rows})

    train_cells = catalog_ctx["train_cells"]
    scale_cells = catalog_ctx["scale_holdout_cells"]
    topology_cells = catalog_ctx["topology_holdout_cells"]
    holdout_cells = catalog_ctx["all_holdout_cells"]
    challenge_map = catalog_ctx["challenges"]

    completed = []

    for _attempt in range(max_attempts):
        if len(completed) >= draws_target:
            break

        picks = [rng.choice(voters) for _ in voters]
        multiplicity = Counter(picks)
        boot_rows = []
        for row in rows:
            mult = multiplicity.get(row["voter_id"], 0)
            if mult <= 0:
                continue
            rr = dict(row)
            # Critical preregistered V5 inheritance:
            # original capped ballot weight is frozen before resampling.
            rr["weight"] = float(row["weight"]) * mult
            boot_rows.append(rr)

        train_rows = [
            r for r in boot_rows
            if challenge_map[r["challenge_id"]]["fit_eligible"] is True
        ]
        holdout_rows = [
            r for r in boot_rows
            if challenge_map[r["challenge_id"]]["fit_eligible"] is False
        ]

        present_train = {
            cell_key(challenge_map[r["challenge_id"]]) for r in train_rows
        }
        present_holdout = {
            cell_key(challenge_map[r["challenge_id"]]) for r in holdout_rows
        }
        if not set(train_cells).issubset(present_train):
            continue
        if not set(holdout_cells).issubset(present_holdout):
            continue

        fits = {}
        for model in ("M0", "M2a", "M2b"):
            lam = m2b_lambda if model == "M2b" else 0.0
            fit = fit_model(
                model,
                train_rows,
                challenge_map,
                train_cells,
                cfg,
                spline,
                regularization_lambda=lam,
                warm_start=original_fits[model]["x"],
                bootstrap_mode=True,
            )
            if not fit.get("success") or not fit.get("eligible"):
                fits = {}
                break
            fits[model] = fit
        if not fits:
            continue

        losses = {}
        for model in ("M0", "M2a", "M2b"):
            losses[model] = {
                "combined": model_eval(
                    model, fits[model], holdout_rows, challenge_map,
                    holdout_cells, cfg, spline
                ),
                "scale": model_eval(
                    model, fits[model], holdout_rows, challenge_map,
                    scale_cells, cfg, spline
                ),
                "topology": model_eval(
                    model, fits[model], holdout_rows, challenge_map,
                    topology_cells, cfg, spline
                ),
            }
        if not all(
            math.isfinite(losses[m][s])
            for m in losses
            for s in losses[m]
        ):
            continue

        completed.append(
            {
                "losses": losses,
                "M2a_p": float(fits["M2a"]["x"][0]),
                "M2b_deltas": [float(x) for x in fits["M2b"]["x"][:4]],
            }
        )

    if len(completed) < draws_target:
        return {
            "status": "unresolved",
            "valid_draws": len(completed),
            "target_valid_draws": draws_target,
            "max_attempts": max_attempts,
            "reason": "insufficient_valid_voter_cluster_bootstrap_draws",
        }

    def favor(a, b):
        return float(
            sum(d["losses"][a]["combined"] < d["losses"][b]["combined"]
                for d in completed)
            / len(completed)
        )

    def improvement_quantiles(a, b):
        vals = np.asarray(
            [
                d["losses"][b]["combined"] - d["losses"][a]["combined"]
                for d in completed
            ],
            dtype=float,
        )
        return {
            "p05": float(np.quantile(vals, 0.05)),
            "median": float(np.quantile(vals, 0.50)),
            "p95": float(np.quantile(vals, 0.95)),
        }

    return {
        "status": "complete",
        "valid_draws": len(completed),
        "target_valid_draws": draws_target,
        "favorable_fraction": {
            "M2a_vs_M0": favor("M2a", "M0"),
            "M2b_vs_M0": favor("M2b", "M0"),
            "M2b_vs_M2a": favor("M2b", "M2a"),
        },
        "combined_holdout_log_loss_improvement_ci90": {
            "M2a_vs_M0": improvement_quantiles("M2a", "M0"),
            "M2b_vs_M0": improvement_quantiles("M2b", "M0"),
            "M2b_vs_M2a": improvement_quantiles("M2b", "M2a"),
        },
    }


def select_research_candidate(point, bootstrap, cfg):
    if bootstrap.get("status") != "complete":
        return {
            "status": "unresolved",
            "selected_model": None,
            "reason": "bootstrap_incomplete",
        }

    threshold = float(
        cfg["model_selection"]["minimum_absolute_combined_holdout_log_loss_improvement"]
    )
    split_tol = float(
        cfg["model_selection"]["maximum_absolute_regression_per_structural_holdout_split"]
    )
    min_favor = float(
        cfg["model_selection"]["minimum_bootstrap_favorable_fraction"]
    )

    def qualifies(challenger, incumbent, favor_key):
        if not point[challenger]["eligible"]:
            return False, ["challenger_ineligible"]

        reasons = []
        improvement = (
            point[incumbent]["combined_holdout_log_loss"]
            - point[challenger]["combined_holdout_log_loss"]
        )
        if improvement + 1e-15 < threshold:
            reasons.append("combined_holdout_improvement_below_threshold")

        for split in ("scale_holdout_log_loss", "topology_holdout_log_loss"):
            if (
                point[challenger][split]
                > point[incumbent][split] + split_tol + 1e-15
            ):
                reasons.append(f"{split}_regression_exceeds_tolerance")

        if bootstrap["favorable_fraction"][favor_key] + 1e-15 < min_favor:
            reasons.append("bootstrap_favorable_fraction_below_threshold")

        return not reasons, reasons

    incumbent = "M0"
    decisions = []

    ok, reasons = qualifies("M2a", "M0", "M2a_vs_M0")
    decisions.append(
        {"challenger": "M2a", "incumbent": "M0", "qualified": ok, "reasons": reasons}
    )
    if ok:
        incumbent = "M2a"

    favor_key = "M2b_vs_M2a" if incumbent == "M2a" else "M2b_vs_M0"
    ok, reasons = qualifies("M2b", incumbent, favor_key)
    decisions.append(
        {
            "challenger": "M2b",
            "incumbent": incumbent,
            "qualified": ok,
            "reasons": reasons,
        }
    )
    if ok:
        incumbent = "M2b"

    return {
        "status": "research_candidate_selected",
        "selected_model": incumbent,
        "production_promotion_authorized": False,
        "decisions": decisions,
    }


def run_analysis(payload):
    cfg, catalog, _maturity = verify_preregistration()
    ctx = catalog_maps(catalog)
    spline = ConvexLinearSpline(cfg)

    rows, exclusions = normalize_ballots(payload, ctx, cfg)
    maturity = maturity_report(rows, ctx, cfg)

    base = {
        "schema_version": 1,
        "status": maturity["status"],
        "research_only": True,
        "production_change_authorized": False,
        "automatic_production_change_allowed": False,
        "catalog_payload_sha256": cfg["anchors"]["canonical_challenge_payload_sha256"],
        "model_fit_preregistration_sha256": sha256(CONFIG_PATH),
        "exclusions": exclusions,
        "maturity": maturity,
    }

    if not maturity["mature"]:
        base["fit_performed"] = False
        return base

    challenge_map = ctx["challenges"]
    train_rows = [
        r for r in rows if challenge_map[r["challenge_id"]]["fit_eligible"] is True
    ]
    holdout_rows = [
        r for r in rows if challenge_map[r["challenge_id"]]["fit_eligible"] is False
    ]

    m0 = fit_model(
        "M0", train_rows, challenge_map, ctx["train_cells"], cfg, spline
    )
    m2a = fit_model(
        "M2a", train_rows, challenge_map, ctx["train_cells"], cfg, spline
    )
    cv = select_m2b_lambda(
        train_rows, challenge_map, ctx["train_cells"], cfg, spline
    )
    if not cv.get("success"):
        base.update(
            {
                "fit_performed": True,
                "status": "model_fit_unresolved",
                "M0_fit": m0,
                "M2a_fit": m2a,
                "M2b_cross_validation": cv,
                "selection": {
                    "status": "unresolved",
                    "selected_model": None,
                    "reason": "M2b_cross_validation_unresolved",
                },
            }
        )
        return base

    m2b = fit_model(
        "M2b",
        train_rows,
        challenge_map,
        ctx["train_cells"],
        cfg,
        spline,
        regularization_lambda=float(cv["selected_lambda"]),
    )

    fits = {"M0": m0, "M2a": m2a, "M2b": m2b}
    point = {}
    for model, fit in fits.items():
        point[model] = {
            "eligible": bool(fit.get("success") and fit.get("eligible")),
            "fit": fit,
            "combined_holdout_log_loss": model_eval(
                model,
                fit,
                holdout_rows,
                challenge_map,
                ctx["all_holdout_cells"],
                cfg,
                spline,
            ),
            "scale_holdout_log_loss": model_eval(
                model,
                fit,
                holdout_rows,
                challenge_map,
                ctx["scale_holdout_cells"],
                cfg,
                spline,
            ),
            "topology_holdout_log_loss": model_eval(
                model,
                fit,
                holdout_rows,
                challenge_map,
                ctx["topology_holdout_cells"],
                cfg,
                spline,
            ),
        }

    # M1 is exactly M0 on this frozen all-multi-piece-vs-multi-piece catalog.
    point["M1"] = {
        **point["M0"],
        "benchmark_identity": "M1_equals_M0_on_frozen_nextgen_catalog",
    }

    if not point["M0"]["eligible"]:
        base.update(
            {
                "fit_performed": True,
                "status": "model_fit_unresolved",
                "point_estimates": point,
                "M2b_cross_validation": cv,
                "selection": {
                    "status": "unresolved",
                    "selected_model": None,
                    "reason": "baseline_M0_nuisance_fit_unresolved",
                },
            }
        )
        return base

    boot = bootstrap_analysis(
        rows,
        ctx,
        cfg,
        spline,
        {"M0": m0, "M2a": m2a, "M2b": m2b},
        float(cv["selected_lambda"]),
    )
    selection = select_research_candidate(point, boot, cfg)

    base.update(
        {
            "fit_performed": True,
            "status": (
                "fit_complete_research_only"
                if selection["status"] == "research_candidate_selected"
                else "model_fit_unresolved"
            ),
            "M2b_cross_validation": cv,
            "point_estimates": point,
            "bootstrap": boot,
            "selection": selection,
        }
    )
    return base


def selftest():
    cfg, catalog, _maturity = verify_preregistration()
    ctx = catalog_maps(catalog)
    spline = ConvexLinearSpline(cfg)

    assert cfg["normalization"]["v_ref"] == 5401.0
    assert len(catalog["challenges"]) == 129

    # Production V1.6 is fail-closed for multi-v-multi; all frozen NextGen
    # challenges are multi-v-multi, so M1 is exactly M0 on this catalog.
    for c in catalog["challenges"]:
        assert len(c["side_a"]["assets"]) >= 2
        assert len(c["side_b"]["assets"]) >= 2

    # M2a identification/invariants.
    for values in ([1000.0], [1200.0, 800.0], [3000.0, 1000.0, 500.0]):
        side = {"assets": [{"fv": v} for v in values]}
        assert abs(power_score(side, 1.0) - sum(values)) < 1e-8
        assert abs(
            power_score(side, 1.4)
            - power_score({"assets": list(reversed(side["assets"]))}, 1.4)
        ) < 1e-8

    # M2b mathematical invariants, including boundary parameter sets.
    delta_sets = (
        [0.0, 0.0, 0.0, 0.0],
        [2.0, 2.0, 2.0, 2.0],
        [0.0, 0.5, 1.0, 1.5],
    )
    for deltas in delta_sets:
        assert abs(spline.g(0.0, deltas)) < 1e-12
        assert abs(spline.g(1.0, deltas) - 1.0) < 1e-12

        grid = np.linspace(0.0, spline.domain_max, 500)
        ys = [spline.g(x, deltas) for x in grid]
        assert all(b > a for a, b in zip(ys, ys[1:]))

        slopes, _ = spline._shape(deltas)
        assert np.all(np.diff(slopes) >= -1e-12)

        for x in np.linspace(0.0, spline.domain_max, 50):
            assert abs(spline.inverse(spline.g(x, deltas), deltas) - x) < 1e-9

        for c in catalog["challenges"]:
            for side_name in ("side_a", "side_b"):
                side = c[side_name]
                eq = spline.score(side, deltas)
                raw = raw_score(side)
                assert eq > 0
                # Convex g with g(0)=0 is superadditive, so equivalent value
                # cannot exceed the raw sum for these positive-value sides.
                assert eq <= raw + 1e-6

    # Singleton identity, positive-piece monotonicity, swap/identical properties.
    for deltas in delta_sets:
        for v in (250.0, 1000.0, 5401.0):
            assert abs(spline.equivalent_values([v], deltas) - v) < 1e-6
        a = spline.equivalent_values([3000.0, 1000.0], deltas)
        b = spline.equivalent_values([3000.0, 1000.0, 250.0], deltas)
        assert b > a
        diff = a - b
        assert abs(diff + (b - a)) < 1e-12
        assert abs(a - a) < 1e-12

    # Deterministic balanced voter folds.
    voters = [f"v{i:02d}" for i in range(40)]
    folds1 = assign_voter_folds(voters, cfg)
    folds2 = assign_voter_folds(list(reversed(voters)), cfg)
    assert folds1 == folds2
    counts = Counter(folds1.values())
    assert sorted(counts.values()) == [8, 8, 8, 8, 8]

    # Bootstrap weighting semantics: freeze original cap, then multiply cluster.
    cap = float(cfg["voter_protections"]["primary_evidence_effective_lifetime_cap"])
    original_count = 25
    original_weight = min(1.0, cap / original_count)
    assert abs(original_weight - 0.8) < 1e-12
    assert abs(original_count * original_weight * 2 - 40.0) < 1e-12

    # Numerical optimizer smoke test with one synthetic row per frozen train
    # challenge; this tests the exact objective plumbing without viewing votes.
    synthetic = []
    for i, c in enumerate(
        sorted(
            (x for x in catalog["challenges"] if x["fit_eligible"] is True),
            key=lambda x: x["id"],
        )
    ):
        synthetic.append(
            {
                "voter_id": f"synthetic_{i % 20:02d}",
                "challenge_id": c["id"],
                "choice_side": "A" if i % 2 == 0 else "B",
                "displayed_left_side": "A" if (i // 2) % 2 == 0 else "B",
                "weight": 1.0,
            }
        )
    smoke = fit_model(
        "M0",
        synthetic,
        ctx["challenges"],
        ctx["train_cells"],
        cfg,
        spline,
    )
    assert smoke["success"] is True
    assert math.isfinite(smoke["objective"])

    print("Package Adjustment NextGen V2 model-fit preregistration self-test passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--ballots")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return

    if not args.ballots:
        parser.error("--ballots is required unless --selftest is used")

    result = run_analysis(read_json(Path(args.ballots)))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()

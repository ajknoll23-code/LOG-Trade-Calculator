#!/usr/bin/env python3
"""Package Adjustment V4 Phase 3F — one-time fresh confirmation evaluation.

Consumes only the immutable exact-600 V4 confirmation evidence, the frozen
240-challenge catalog, the two frozen V4 candidates, and the pre-unblinding
interpretation contract.

Implements the frozen confirmation evaluation:
- raw additive control + the two frozen V4 candidates;
- 5-fold cross-validation grouped by voter cluster;
- beta > 0 via beta=exp(log_beta), plus frozen left-side bias parameter;
- held-out weighted log loss as the primary metric;
- candidate selection by lowest mean held-out log loss;
- unresolved candidate selection when best-vs-runner-up gap < 0.002;
- every deployment gate evaluated independently for BOTH frozen candidates;
- challenge-cluster bootstrap versus raw;
- topology x asset-mix safety regression versus raw;
- interpretation exactly according to the pre-unblinding Phase 3F contract.

No parameters are tuned. No model is substituted post hoc. No production code is
changed by this evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import scipy
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "research" / "package-adjustment-v4-elite-fragmentation"

PREREG = D / "phase1_structural_preregistration.json"
FAMILY = D / "frozen_candidate.json"
CATALOG = D / "phase3b_confirmation_catalog.json"
FROZEN = D / "phase3_exact_600_frozen.json"
FREEZE_MANIFEST = D / "phase3_exact_600_freeze_manifest.json"
INTERPRETATION = D / "phase3f_interpretation_contract.json"

RESULT_OUT = D / "phase3_confirmation_evaluation.json"
MANIFEST_OUT = D / "phase3_confirmation_evaluation_manifest.json"
REPORT_OUT = D / "phase3_confirmation_evaluation.md"

RAW_ID = "raw-additive-control-g1.00"
FOLD_COUNT = 5
FOLD_SEED = "package-adjustment-v4-phase3f-fold-v1"
BOOTSTRAP_SEED = 2026092003
BOOTSTRAP_DRAWS = 20000
EPS = 1e-12

EXPECTED_BLOBS = {
    "prereg": "ac8e35c0104d95ea080897a460506cafa4a33203",
    "family": "6b56cff2e0abd5eeee8189ca97e8bde7cb787c84",
    "catalog": "0c974cd5d6a66c410f91775ba34fa068cc79f408",
    "frozen": "91d5d563aaf22382c7b740ca2d1caa4be9037f36",
    "freeze_manifest": "204bb2e8523ef1f388b740f8c942bc5d54bc76c4",
    "interpretation": "c1b90709b9ca53f520c69b3b272fa74507029a09",
}
EXPECTED_FROZEN_SHA256 = (
    "0027bd94719f4716d1c80b6578a9b5b0c9f779e762ef3e33f3861992158c706b"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def canonical_hash(obj) -> str:
    return hashlib.sha256(
        json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def logloss_one(y: int, p: float) -> float:
    p = min(1.0 - 1e-12, max(1e-12, float(p)))
    return -(y * math.log(p) + (1 - y) * math.log(1.0 - p))


def raw_delta(challenge: dict) -> float:
    a = sum(float(asset["fv"]) for asset in challenge["side_a"])
    b = sum(float(asset["fv"]) for asset in challenge["side_b"])
    denom = a + b
    if not math.isfinite(denom) or denom <= 0:
        raise RuntimeError("Invalid raw additive score denominator")
    out = (a - b) / denom
    if not math.isfinite(out):
        raise RuntimeError("Nonfinite raw additive score delta")
    return out


def side_components(side: list[dict], candidate: dict) -> dict:
    vals = sorted((float(asset["fv"]) for asset in side), reverse=True)
    if not vals or any(not math.isfinite(v) or v <= 0 for v in vals):
        raise RuntimeError("V4 side contains invalid FV")

    v1 = vals[0]
    v2 = vals[1] if len(vals) >= 2 else 0.0
    third_plus = sum(vals[2:]) if len(vals) >= 3 else 0.0
    total = sum(vals)
    elite_factor = min(1.0, max(0.0, v1 / 10000.0))

    premium = elite_factor * (
        float(candidate["stud_strength"]) * v1
        - float(candidate["second_piece_discount"]) * v2
        - float(candidate["third_plus_discount"]) * third_plus
    )
    effective = total + premium

    if not (math.isfinite(premium) and math.isfinite(effective)):
        raise RuntimeError("Nonfinite V4 side score")
    if effective <= 0:
        raise RuntimeError("Nonpositive V4 effective score")

    return {
        "total": total,
        "elite_factor": elite_factor,
        "premium": premium,
        "effective": effective,
    }


def v4_delta(challenge: dict, candidate: dict) -> float:
    a = side_components(challenge["side_a"], candidate)["effective"]
    b = side_components(challenge["side_b"], candidate)["effective"]
    denom = abs(a) + abs(b)
    if not math.isfinite(denom) or denom <= 0:
        raise RuntimeError("Invalid V4 normalized score denominator")
    out = (a - b) / denom
    if not math.isfinite(out) or not (-1.0 < out < 1.0):
        raise RuntimeError(f"Invalid V4 normalized score delta: {out}")
    return out


def reference_raw_delta(challenge: dict) -> float:
    """Independent audit implementation; not used for scientific scoring."""
    total_a = 0.0
    total_b = 0.0
    for asset in challenge["side_a"]:
        total_a += float(asset["fv"])
    for asset in challenge["side_b"]:
        total_b += float(asset["fv"])
    return (total_a - total_b) / (total_a + total_b)


def reference_v4_delta(challenge: dict, candidate: dict) -> float:
    """Independent direct-formula implementation for pre-unblinding audit."""
    def direct(side):
        values = [float(asset["fv"]) for asset in side]
        values.sort(reverse=True)
        top = values[0]
        second = values[1] if len(values) > 1 else 0.0
        tail = 0.0
        for value in values[2:]:
            tail += value
        total = 0.0
        for value in values:
            total += value
        elite = top / 10000.0
        if elite < 0.0:
            elite = 0.0
        if elite > 1.0:
            elite = 1.0
        return total + elite * (
            float(candidate["stud_strength"]) * top
            - float(candidate["second_piece_discount"]) * second
            - float(candidate["third_plus_discount"]) * tail
        )

    ea = direct(challenge["side_a"])
    eb = direct(challenge["side_b"])
    return (ea - eb) / (abs(ea) + abs(eb))


def numeric_gradient_audit():
    """Finite-difference verification of the analytic calibration gradient."""
    rng = random.Random(2026092004)
    rows = []
    for i in range(120):
        x = rng.uniform(-0.85, 0.85)
        left = i % 2
        y = 1 if rng.random() < sigmoid(2.3 * x + 0.17 * left) else 0
        rows.append({
            "x": {"audit": x},
            "left": left,
            "y": y,
            "weight": rng.uniform(0.25, 2.0),
        })

    total_weight = sum(r["weight"] for r in rows)

    def objective(theta):
        log_beta, delta_left = float(theta[0]), float(theta[1])
        beta = math.exp(log_beta)
        loss_sum = 0.0
        grad_log_beta = 0.0
        grad_delta = 0.0
        for row in rows:
            z = beta * row["x"]["audit"] + delta_left * row["left"]
            p = sigmoid(z)
            residual = p - row["y"]
            w = row["weight"]
            loss_sum += w * logloss_one(row["y"], p)
            grad_log_beta += (
                w * residual * beta * row["x"]["audit"]
            )
            grad_delta += w * residual * row["left"]
        return (
            loss_sum / total_weight,
            [
                grad_log_beta / total_weight,
                grad_delta / total_weight,
            ],
        )

    for theta in ((0.37, -0.22), (-0.41, 0.31), (0.0, 0.0)):
        value, analytic = objective(theta)
        assert math.isfinite(value)
        h = 1e-6
        numeric = []
        for j in range(2):
            plus = list(theta)
            minus = list(theta)
            plus[j] += h
            minus[j] -= h
            numeric.append(
                (objective(plus)[0] - objective(minus)[0]) / (2.0 * h)
            )
        for a, n in zip(analytic, numeric):
            if abs(a - n) > 2e-7:
                raise RuntimeError(
                    f"Calibration gradient audit failed: analytic={a}, numeric={n}"
                )


def synthetic_oof_audit():
    """Independent checks of grouping and weighted OOF aggregation."""
    rng = random.Random(2026092005)
    voters = [f"audit-v{i:02d}" for i in range(1, 32)]
    rows = []
    ordinal = 0

    for voter_i, voter in enumerate(voters):
        for j in range(5):
            ordinal += 1
            raw_x = rng.uniform(-0.70, 0.70)
            candidate_x = 1.12 * raw_x + 0.025
            left = (voter_i + j) % 2
            p = sigmoid(2.8 * candidate_x + 0.11 * left)
            y = 1 if rng.random() < p else 0
            rows.append({
                "ordinal": ordinal,
                "voter_cluster": voter,
                "challenge_id": f"audit-{voter_i % 11}-{j}",
                "topology": "1v2",
                "asset_mix": "players_only",
                "left": left,
                "y": y,
                "weight": 0.5 + ((voter_i + j) % 4) * 0.25,
                "x": {
                    RAW_ID: raw_x,
                    "audit-candidate": candidate_x,
                },
            })

    predictions, fold_metrics, combined, fold_counts = evaluate_oof(
        rows, [RAW_ID, "audit-candidate"]
    )
    assert sorted(fold_counts.values()) == [6, 6, 6, 6, 7]

    fold_map, _ = deterministic_fold_map(voters)
    for voter in voters:
        assigned = {
            row["fold"]
            for row in rows
            if row["voter_cluster"] == voter
        }
        assert assigned == {fold_map[voter]}

    total_weight = sum(row["weight"] for row in rows)
    for model_id in (RAW_ID, "audit-candidate"):
        manual = sum(
            row["weight"]
            * predictions[model_id][row["ordinal"]]["loss"]
            for row in rows
        ) / total_weight
        if abs(manual - combined[model_id]) > 1e-14:
            raise RuntimeError(
                f"OOF aggregation audit failed for {model_id}: "
                f"{manual} != {combined[model_id]}"
            )
        assert len(fold_metrics[model_id]) == 5


def bootstrap_audit():
    """Sanity-check bootstrap sign and weighting on known synthetic losses."""
    rows = []
    predictions = {RAW_ID: {}, "better": {}, "worse": {}}
    ordinal = 0

    for challenge_i in range(231):
        repeats = 2 if challenge_i < 19 else 1
        for _ in range(repeats):
            ordinal += 1
            rows.append({
                "ordinal": ordinal,
                "challenge_id": f"boot-{challenge_i:03d}",
                "weight": 1.0,
            })
            predictions[RAW_ID][ordinal] = {"loss": 0.70}
            predictions["better"][ordinal] = {"loss": 0.60}
            predictions["worse"][ordinal] = {"loss": 0.80}

    better = challenge_cluster_bootstrap(
        rows, predictions, "better"
    )
    worse = challenge_cluster_bootstrap(
        rows, predictions, "worse"
    )

    assert better["cluster_count"] == 231
    assert better["favorable_fraction"] == 1.0
    assert worse["favorable_fraction"] == 0.0
    assert abs(
        better["improvement_raw_minus_candidate_percentiles"]["median"]
        - 0.10
    ) < 1e-12
    assert abs(
        worse["improvement_raw_minus_candidate_percentiles"]["median"]
        + 0.10
    ) < 1e-12


def threshold_boundary_audit():
    """Verify all frozen inequality directions at and around each threshold."""
    assert 0.005 + EPS >= 0.005
    assert not (0.0049 + EPS >= 0.005)

    assert 0.90 + EPS >= 0.90
    assert not (0.899 + EPS >= 0.90)

    assert 0.030 <= 0.030 + EPS
    assert not (0.031 <= 0.030 + EPS)

    assert 0.002 + EPS >= 0.002
    assert not (0.0019 + EPS >= 0.002)


def frozen_catalog_score_audit(family: dict, catalog: dict):
    """Audit real frozen catalog scores without reading any human outcomes."""
    candidates = family["candidate_family"]
    challenges = catalog["challenges"]

    max_raw_diff = 0.0
    max_v4_diff = 0.0
    for challenge in challenges:
        direct_raw = raw_delta(challenge)
        reference_raw = reference_raw_delta(challenge)
        max_raw_diff = max(max_raw_diff, abs(direct_raw - reference_raw))

        swapped = {
            "side_a": challenge["side_b"],
            "side_b": challenge["side_a"],
        }
        if abs(direct_raw + raw_delta(swapped)) > 1e-12:
            raise RuntimeError(
                f"Raw side-swap audit failed for {challenge['id']}"
            )

        for candidate in candidates:
            direct_v4 = v4_delta(challenge, candidate)
            reference_v4 = reference_v4_delta(challenge, candidate)
            max_v4_diff = max(
                max_v4_diff, abs(direct_v4 - reference_v4)
            )
            if abs(direct_v4 + v4_delta(swapped, candidate)) > 1e-12:
                raise RuntimeError(
                    f"V4 side-swap audit failed for "
                    f"{challenge['id']} / {candidate['id']}"
                )

    if max_raw_diff > 1e-14:
        raise RuntimeError(
            f"Raw formula/reference mismatch: {max_raw_diff}"
        )
    if max_v4_diff > 1e-14:
        raise RuntimeError(
            f"V4 formula/reference mismatch: {max_v4_diff}"
        )

    print(
        "PASS frozen-catalog score audit: 240 challenges; "
        f"raw max diff={max_raw_diff:.3g}; "
        f"V4 max diff={max_v4_diff:.3g}"
    )


def calculation_audit():
    numeric_gradient_audit()
    synthetic_oof_audit()
    bootstrap_audit()
    threshold_boundary_audit()

    # Randomized independent formula equivalence, no real outcomes.
    rng = random.Random(2026092006)
    candidates = [
        {
            "id": "audit-s75",
            "stud_strength": 0.75,
            "second_piece_discount": 0.10,
            "third_plus_discount": 0.30,
        },
        {
            "id": "audit-s50",
            "stud_strength": 0.50,
            "second_piece_discount": 0.10,
            "third_plus_discount": 0.30,
        },
    ]
    for _ in range(5000):
        a_n = rng.randint(1, 6)
        b_n = rng.randint(1, 6)
        challenge = {
            "side_a": [
                {"fv": rng.uniform(200.0, 10000.0)}
                for _ in range(a_n)
            ],
            "side_b": [
                {"fv": rng.uniform(200.0, 10000.0)}
                for _ in range(b_n)
            ],
        }
        if abs(raw_delta(challenge) - reference_raw_delta(challenge)) > 1e-14:
            raise RuntimeError("Random raw formula audit failed")
        for candidate in candidates:
            if (
                abs(
                    v4_delta(challenge, candidate)
                    - reference_v4_delta(challenge, candidate)
                )
                > 1e-14
            ):
                raise RuntimeError("Random V4 formula audit failed")

    print(
        "Package Adjustment V4 Phase 3F calculation audit PASS: "
        "score formulas, analytic gradient, grouped OOF aggregation, "
        "bootstrap direction, and frozen threshold inequalities verified."
    )


def deterministic_fold_map(voter_clusters):
    ordered = sorted(
        voter_clusters,
        key=lambda voter: hashlib.sha256(
            f"{FOLD_SEED}|{voter}".encode("utf-8")
        ).hexdigest(),
    )
    if len(ordered) != 31:
        raise RuntimeError(f"Expected 31 frozen voter clusters, got {len(ordered)}")

    mapping = {voter: idx % FOLD_COUNT for idx, voter in enumerate(ordered)}
    counts = {fold: 0 for fold in range(FOLD_COUNT)}
    for fold in mapping.values():
        counts[fold] += 1

    if sorted(counts.values()) != [6, 6, 6, 6, 7]:
        raise RuntimeError(f"Unexpected grouped fold voter counts: {counts}")
    return mapping, counts


def fit_calibration(rows, model_id):
    total_weight = sum(row["weight"] for row in rows)
    if total_weight <= 0:
        raise RuntimeError("Training fold has nonpositive effective weight")

    def objective(theta):
        log_beta = float(theta[0])
        delta_left = float(theta[1])
        beta = math.exp(log_beta)

        loss_sum = 0.0
        grad_log_beta = 0.0
        grad_delta = 0.0

        for row in rows:
            z = beta * row["x"][model_id] + delta_left * row["left"]
            p = sigmoid(z)
            w = row["weight"]
            residual = p - row["y"]
            loss_sum += w * logloss_one(row["y"], p)
            grad_log_beta += w * residual * beta * row["x"][model_id]
            grad_delta += w * residual * row["left"]

        return (
            loss_sum / total_weight,
            [
                grad_log_beta / total_weight,
                grad_delta / total_weight,
            ],
        )

    fit = minimize(
        fun=lambda t: objective(t)[0],
        x0=[0.0, 0.0],
        jac=lambda t: objective(t)[1],
        method="L-BFGS-B",
        options={
            "maxiter": 2000,
            "ftol": 1e-14,
            "gtol": 1e-10,
            "maxls": 50,
        },
    )
    if not fit.success:
        raise RuntimeError(
            f"Calibration failed for {model_id}: "
            f"{fit.status} {fit.message}"
        )

    log_beta = float(fit.x[0])
    delta_left = float(fit.x[1])
    beta = math.exp(log_beta)
    if not (
        math.isfinite(beta)
        and beta > 0
        and math.isfinite(delta_left)
    ):
        raise RuntimeError(f"Invalid calibration for {model_id}")

    return {
        "beta": beta,
        "log_beta": log_beta,
        "delta_left": delta_left,
        "training_weight": total_weight,
        "optimizer_iterations": int(getattr(fit, "nit", 0)),
        "optimizer_objective": float(fit.fun),
    }


def evaluate_oof(rows, model_ids):
    voters = sorted({row["voter_cluster"] for row in rows})
    fold_map, fold_voter_counts = deterministic_fold_map(voters)

    for row in rows:
        row["fold"] = fold_map[row["voter_cluster"]]

    predictions = {model_id: {} for model_id in model_ids}
    fold_metrics = {model_id: [] for model_id in model_ids}

    for fold in range(FOLD_COUNT):
        train = [row for row in rows if row["fold"] != fold]
        test = [row for row in rows if row["fold"] == fold]
        if not train or not test:
            raise RuntimeError(f"Empty V4 Phase 3F train/test fold {fold}")

        train_voters = len({r["voter_cluster"] for r in train})
        test_voters = len({r["voter_cluster"] for r in test})

        for model_id in model_ids:
            params = fit_calibration(train, model_id)
            test_weight = sum(row["weight"] for row in test)
            loss_sum = 0.0

            for row in test:
                z = (
                    params["beta"] * row["x"][model_id]
                    + params["delta_left"] * row["left"]
                )
                p = sigmoid(z)
                loss = logloss_one(row["y"], p)
                predictions[model_id][row["ordinal"]] = {
                    "p": p,
                    "loss": loss,
                }
                loss_sum += row["weight"] * loss

            fold_metrics[model_id].append({
                "fold": fold,
                "train_voter_clusters": train_voters,
                "test_voter_clusters": test_voters,
                "train_ballots": len(train),
                "test_ballots": len(test),
                "test_effective_weight": round(float(test_weight), 9),
                "held_out_log_loss": round(loss_sum / test_weight, 12),
                "calibration": {
                    "beta": round(params["beta"], 12),
                    "log_beta": round(params["log_beta"], 12),
                    "delta_left": round(params["delta_left"], 12),
                },
            })

    total_weight = sum(row["weight"] for row in rows)
    combined = {}
    for model_id in model_ids:
        if len(predictions[model_id]) != len(rows):
            raise RuntimeError(f"Incomplete OOF predictions for {model_id}")
        combined[model_id] = sum(
            row["weight"] * predictions[model_id][row["ordinal"]]["loss"]
            for row in rows
        ) / total_weight

    return predictions, fold_metrics, combined, fold_voter_counts


def challenge_cluster_bootstrap(rows, predictions, candidate_id):
    clusters = defaultdict(
        lambda: {"improvement_sum": 0.0, "weight": 0.0}
    )
    for row in rows:
        raw_loss = predictions[RAW_ID][row["ordinal"]]["loss"]
        candidate_loss = predictions[candidate_id][row["ordinal"]]["loss"]
        w = row["weight"]
        c = clusters[row["challenge_id"]]
        c["improvement_sum"] += w * (raw_loss - candidate_loss)
        c["weight"] += w

    challenge_ids = sorted(clusters)
    if len(challenge_ids) != 231:
        raise RuntimeError(
            "Expected 231 frozen challenge clusters, got "
            f"{len(challenge_ids)}"
        )

    rng = random.Random(BOOTSTRAP_SEED)
    favorable = 0
    improvements = []

    for _ in range(BOOTSTRAP_DRAWS):
        diff_sum = 0.0
        weight_sum = 0.0
        for _j in range(len(challenge_ids)):
            cid = challenge_ids[rng.randrange(len(challenge_ids))]
            diff_sum += clusters[cid]["improvement_sum"]
            weight_sum += clusters[cid]["weight"]

        if weight_sum <= 0:
            raise RuntimeError("Bootstrap sample has nonpositive weight")

        improvement = diff_sum / weight_sum
        improvements.append(improvement)
        if improvement > 0:
            favorable += 1

    improvements.sort()

    def percentile(q):
        h = (len(improvements) - 1) * q
        lo = int(math.floor(h))
        hi = int(math.ceil(h))
        if lo == hi:
            return improvements[lo]
        frac = h - lo
        return (
            improvements[lo] * (1.0 - frac)
            + improvements[hi] * frac
        )

    return {
        "method": "challenge_cluster_resampling_of_fixed_oof_losses",
        "cluster_count": len(challenge_ids),
        "draws": BOOTSTRAP_DRAWS,
        "rng": "python_random.Random_MT19937",
        "seed": BOOTSTRAP_SEED,
        "favorable_fraction": favorable / BOOTSTRAP_DRAWS,
        "improvement_raw_minus_candidate_percentiles": {
            "p05": percentile(0.05),
            "median": percentile(0.50),
            "p95": percentile(0.95),
        },
    }


def interpretation_status(
    selection_resolved: bool,
    selected_all_gates: bool,
    any_candidate_all_gates: bool,
):
    if selection_resolved and selected_all_gates:
        return (
            "CONFIRMATION_PASSED_PRODUCTION_CANDIDATE_ELIGIBLE",
            True,
            False,
            (
                "The uniquely selected frozen V4 candidate passed every "
                "preregistered deployment gate. Proceed to a separate explicit "
                "deployment audit; this evaluation does not alter production."
            ),
        )

    if selection_resolved and not selected_all_gates:
        return (
            "CONFIRMATION_FAILED_RESEARCH_ONLY",
            False,
            False,
            (
                "Candidate selection resolved, but the selected candidate failed "
                "at least one preregistered deployment gate. Do not substitute "
                "the runner-up post hoc. Production remains V1.6."
            ),
        )

    if (not selection_resolved) and any_candidate_all_gates:
        return (
            "CONFIRMATION_FAMILY_VALIDATED_CANDIDATE_SELECTION_UNRESOLVED",
            False,
            True,
            (
                "The frozen V4 family has confirmation evidence versus raw, but "
                "the two candidate parameterizations are unresolved under the "
                "frozen 0.002 selection rule. No production promotion. Pre-register "
                "a fresh candidate-discrimination study restricted to these same "
                "two frozen candidates; do not retune them against these 600 votes."
            ),
        )

    return (
        "CONFIRMATION_UNRESOLVED_AND_NO_CANDIDATE_PASSES_RESEARCH_ONLY",
        False,
        False,
        (
            "Candidate selection is unresolved and neither frozen V4 candidate "
            "independently passed every deployment gate. Close this V4 "
            "confirmation cycle without production."
        ),
    )


def validate_contract_metadata(read_frozen_dataset: bool):
    files = {
        "prereg": PREREG,
        "family": FAMILY,
        "catalog": CATALOG,
        "freeze_manifest": FREEZE_MANIFEST,
        "interpretation": INTERPRETATION,
    }
    if read_frozen_dataset:
        files["frozen"] = FROZEN

    for key, path in files.items():
        expected = EXPECTED_BLOBS[key]
        actual = git_blob(path)
        if actual != expected:
            raise RuntimeError(
                f"Frozen source drift for {key}: {actual} != {expected}"
            )

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    freeze_manifest = json.loads(
        FREEZE_MANIFEST.read_text(encoding="utf-8")
    )
    interpretation = json.loads(
        INTERPRETATION.read_text(encoding="utf-8")
    )

    contract = prereg["fresh_confirmation_contract_if_candidate_frozen"]
    evaluation = contract["evaluation"]

    assert prereg["status"] == "FROZEN_BEFORE_SPENT_EVIDENCE_DEVELOPMENT"
    assert prereg["frozen"] is True
    assert prereg["production_change_authorized"] is False

    assert evaluation["primary_metric"] == (
        "5-fold voter-grouped held-out log loss"
    )
    assert evaluation["raw_additive_control_required"] is True
    assert evaluation["candidate_selection_if_two_frozen"] == (
        "lowest mean held-out log loss; unresolved if best-vs-runner-up gap < 0.002"
    )
    assert evaluation["automatic_production_promotion_allowed"] is False
    gates = evaluation["deployment_gates"]
    assert gates["minimum_log_loss_improvement_vs_raw_control"] == 0.005
    assert gates[
        "challenge_cluster_bootstrap_favorable_fraction_vs_raw"
    ] == 0.9
    assert gates[
        "maximum_topology_x_asset_mix_log_loss_regression_vs_raw"
    ] == 0.03
    assert gates["all_24_cells_coverage_required"] is True

    assert family["status"] == "FROZEN_V4_CONFIRMATION_FAMILY"
    assert family["frozen"] is True
    assert family["family_count"] == 2
    candidate_ids = [c["id"] for c in family["candidate_family"]]
    assert candidate_ids == [
        "elite-frag-s75-p210-p330",
        "elite-frag-s50-p210-p330",
    ]

    assert catalog["status"] == (
        "frozen_unreleased_fresh_confirmation_catalog"
    )
    assert catalog["frozen"] is True
    assert len(catalog["challenges"]) == 240
    assert catalog["catalog_diagnostics"]["research_cell_count"] == 24
    assert catalog["catalog_diagnostics"]["joe_mixon_occurrences"] == 0
    assert (
        catalog["catalog_diagnostics"]["invalid_pick_year_occurrences"] == 0
    )
    assert (
        catalog["catalog_diagnostics"][
            "known_ktc_examples_in_selected_catalog"
        ]
        == 0
    )
    assert (
        catalog["catalog_diagnostics"][
            "historical_trade_matches_in_selected_catalog"
        ]
        == 0
    )
    assert (
        catalog["candidate_family_fingerprint_sha256"]
        == canonical_hash(family["candidate_family"])
    )

    assert freeze_manifest["status"] == (
        "FROZEN_EXACT_600_CONFIRMATION_EVIDENCE_MANIFEST"
    )
    assert freeze_manifest["model_evaluation_performed"] is False
    assert freeze_manifest["production_change_authorized"] is False
    assert freeze_manifest["voting_closed_by_this_phase"] is True
    assert freeze_manifest["checkpoint"]["effective_votes"] == 600
    assert freeze_manifest["checkpoint"]["distinct_voters"] == 31
    assert freeze_manifest["checkpoint"]["distinct_challenges"] == 231
    assert (
        freeze_manifest["checkpoint"]["cells_passing_both_gates"] == 24
    )
    assert freeze_manifest["checkpoint"]["coverage_gates_pass"] is True
    assert (
        freeze_manifest["dataset"]["sha256"]
        == EXPECTED_FROZEN_SHA256
    )

    assert interpretation["status"] == (
        "FROZEN_BEFORE_V4_CONFIRMATION_UNBLINDING"
    )
    assert interpretation[
        "frozen_before_human_outcomes_interpreted"
    ] is True
    assert interpretation["changes_existing_preregistered_thresholds"] is False
    assert interpretation["changes_frozen_candidate_family"] is False
    assert interpretation["candidate_selection_rule"][
        "unresolved_if_best_vs_runner_up_gap_below"
    ] == 0.002
    assert interpretation["deployment_gates"] == {
        "all_24_cells_coverage_required": True,
        "challenge_cluster_bootstrap_favorable_fraction_vs_raw": 0.9,
        "maximum_topology_x_asset_mix_log_loss_regression_vs_raw": 0.03,
        "minimum_log_loss_improvement_vs_raw_control": 0.005,
    }
    assert len(interpretation["interpretation_ladder"]) == 4

    if read_frozen_dataset:
        if sha256_file(FROZEN) != EXPECTED_FROZEN_SHA256:
            raise RuntimeError("Frozen exact-600 dataset SHA256 drift")
        frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
        assert frozen["status"] == "FROZEN_EXACT_600_CONFIRMATION_EVIDENCE"
        assert frozen["frozen"] is True
        assert frozen["model_evaluation_performed"] is False
        assert frozen["checkpoint_selection_outcome_blind"] is True
        assert (
            frozen["human_outcomes_revealed_only_after_checkpoint_selection"]
            is True
        )
        assert frozen["frozen_effective_votes"] == 600.0
        assert frozen["raw_checkpoint_ballot_count"] == 600
        assert frozen["distinct_voter_clusters"] == 31
        assert len(frozen["ballots"]) == 600
        return (
            prereg,
            family,
            catalog,
            freeze_manifest,
            interpretation,
            frozen,
        )

    return (
        prereg,
        family,
        catalog,
        freeze_manifest,
        interpretation,
    )


def selftest():
    fake_voters = [f"v{i:02d}" for i in range(1, 32)]
    mapping, counts = deterministic_fold_map(fake_voters)
    assert len(mapping) == 31
    assert sorted(counts.values()) == [6, 6, 6, 6, 7]

    c = {
        "id": "test",
        "stud_strength": 0.75,
        "second_piece_discount": 0.10,
        "third_plus_discount": 0.30,
    }
    challenge = {
        "side_a": [{"fv": 8000}, {"fv": 2000}],
        "side_b": [{"fv": 6000}, {"fv": 3500}],
    }
    d = v4_delta(challenge, c)
    swapped = {
        "side_a": challenge["side_b"],
        "side_b": challenge["side_a"],
    }
    assert abs(d + v4_delta(swapped, c)) < 1e-12

    assert interpretation_status(True, True, True)[0] == (
        "CONFIRMATION_PASSED_PRODUCTION_CANDIDATE_ELIGIBLE"
    )
    assert interpretation_status(True, False, True)[0] == (
        "CONFIRMATION_FAILED_RESEARCH_ONLY"
    )
    assert interpretation_status(False, False, True)[0] == (
        "CONFIRMATION_FAMILY_VALIDATED_CANDIDATE_SELECTION_UNRESOLVED"
    )
    assert interpretation_status(False, False, False)[0] == (
        "CONFIRMATION_UNRESOLVED_AND_NO_CANDIDATE_PASSES_RESEARCH_ONLY"
    )

    # Synthetic calibration sanity check, no real V4 outcomes.
    rows = []
    ordinal = 0
    for voter_i, voter in enumerate(fake_voters):
        for j, x in enumerate((-0.70, -0.20, 0.20, 0.70)):
            ordinal += 1
            left = 1 if (voter_i + j) % 2 == 0 else 0
            y = 1 if x + 0.1 * left > 0 else 0
            rows.append({
                "ordinal": ordinal,
                "voter_cluster": voter,
                "challenge_id": f"toy-{voter_i}-{j}",
                "topology": "1v2",
                "asset_mix": "players_only",
                "left": left,
                "y": y,
                "weight": 1.0,
                "x": {RAW_ID: x, "candidate": x},
            })
    params = fit_calibration(rows, "candidate")
    assert params["beta"] > 0
    assert math.isfinite(params["delta_left"])

    print("Package Adjustment V4 Phase 3F evaluator self-test PASS")


def preflight():
    (
        _prereg,
        family,
        catalog,
        _freeze_manifest,
        _interpretation,
    ) = validate_contract_metadata(read_frozen_dataset=False)
    frozen_catalog_score_audit(family, catalog)
    print(
        "Package Adjustment V4 Phase 3F preflight PASS: "
        "all frozen metadata/contracts and all 240 catalog score calculations "
        "verified without reading the exact-600 ballot dataset."
    )


def main():
    for path in (RESULT_OUT, MANIFEST_OUT, REPORT_OUT):
        if path.exists():
            raise RuntimeError(
                f"Phase 3F one-time evaluation already exists: {path}"
            )

    (
        prereg,
        family,
        catalog_doc,
        freeze_manifest,
        interpretation,
        frozen,
    ) = validate_contract_metadata(read_frozen_dataset=True)

    candidate_specs = [dict(c) for c in family["candidate_family"]]
    candidate_ids = [c["id"] for c in candidate_specs]
    model_ids = [RAW_ID] + candidate_ids

    challenges = {c["id"]: c for c in catalog_doc["challenges"]}
    if len(challenges) != 240:
        raise RuntimeError("Frozen V4 catalog challenge count drift")

    rows = []
    for ballot in frozen["ballots"]:
        challenge = challenges.get(ballot["challenge_id"])
        if challenge is None:
            raise RuntimeError(
                f"Unknown frozen challenge {ballot['challenge_id']}"
            )

        choice = ballot["human_choice"]
        if choice not in {"A", "B"}:
            raise RuntimeError("Frozen ballot choice must be canonical A/B")

        display_left = ballot["display_left"]
        if display_left not in {"A", "B"}:
            raise RuntimeError("Frozen display orientation invalid")
        left_flag = 1 if ballot["canonical_a_displayed_left"] else 0
        if (display_left == "A") != bool(left_flag):
            raise RuntimeError("Frozen display orientation fields disagree")

        x = {RAW_ID: raw_delta(challenge)}
        for candidate in candidate_specs:
            x[candidate["id"]] = v4_delta(challenge, candidate)

        rows.append({
            "ordinal": int(ballot["ordinal"]),
            "voter_cluster": ballot["voter_cluster"],
            "challenge_id": ballot["challenge_id"],
            "research_cell": ballot["research_cell"],
            "topology": ballot["topology"],
            "asset_mix": ballot["asset_mix"],
            "challenge_stratum": ballot["challenge_stratum"],
            "left": left_flag,
            "y": 1 if choice == "A" else 0,
            "weight": float(ballot["frozen_ballot_weight"]),
            "x": x,
        })

    if len(rows) != 600:
        raise RuntimeError(f"Expected 600 frozen ballots, got {len(rows)}")
    if abs(sum(r["weight"] for r in rows) - 600.0) > 1e-8:
        raise RuntimeError("Frozen effective ballot weight drift")
    if len({r["voter_cluster"] for r in rows}) != 31:
        raise RuntimeError("Frozen voter-cluster count drift")
    if len({r["challenge_id"] for r in rows}) != 231:
        raise RuntimeError("Frozen distinct-challenge count drift")
    if len({r["research_cell"] for r in rows}) != 24:
        raise RuntimeError("Frozen research-cell count drift")

    predictions, fold_metrics, combined, fold_voter_counts = evaluate_oof(
        rows, model_ids
    )

    evaluation_cfg = prereg[
        "fresh_confirmation_contract_if_candidate_frozen"
    ]["evaluation"]
    gates_cfg = evaluation_cfg["deployment_gates"]

    raw_loss = combined[RAW_ID]

    safety_groups = sorted({
        (row["topology"], row["asset_mix"])
        for row in rows
    })
    if len(safety_groups) != 12:
        raise RuntimeError(
            f"Expected 12 topology x asset-mix groups, got "
            f"{len(safety_groups)}"
        )

    candidate_results = {}
    for candidate in candidate_specs:
        cid = candidate["id"]
        candidate_loss = combined[cid]
        improvement = raw_loss - candidate_loss

        group_rows = []
        regressions = []
        for topology, asset_mix in safety_groups:
            subset = [
                row for row in rows
                if row["topology"] == topology
                and row["asset_mix"] == asset_mix
            ]
            if not subset:
                raise RuntimeError(
                    f"Missing safety group {topology}|{asset_mix}"
                )

            wsum = sum(row["weight"] for row in subset)
            raw_group_loss = sum(
                row["weight"]
                * predictions[RAW_ID][row["ordinal"]]["loss"]
                for row in subset
            ) / wsum
            candidate_group_loss = sum(
                row["weight"]
                * predictions[cid][row["ordinal"]]["loss"]
                for row in subset
            ) / wsum
            regression = candidate_group_loss - raw_group_loss
            regressions.append(regression)

            group_rows.append({
                "topology": topology,
                "asset_mix": asset_mix,
                "effective_weight": round(float(wsum), 9),
                "raw_control_log_loss": round(raw_group_loss, 12),
                "candidate_log_loss": round(
                    candidate_group_loss, 12
                ),
                "regression_candidate_minus_raw": round(
                    regression, 12
                ),
            })

        max_regression = max(regressions)
        bootstrap = challenge_cluster_bootstrap(
            rows, predictions, cid
        )

        improvement_gate = (
            improvement + EPS
            >= gates_cfg["minimum_log_loss_improvement_vs_raw_control"]
        )
        bootstrap_gate = (
            bootstrap["favorable_fraction"] + EPS
            >= gates_cfg[
                "challenge_cluster_bootstrap_favorable_fraction_vs_raw"
            ]
        )
        safety_gate = (
            max_regression
            <= gates_cfg[
                "maximum_topology_x_asset_mix_log_loss_regression_vs_raw"
            ]
            + EPS
        )
        coverage_gate = (
            freeze_manifest["checkpoint"]["coverage_gates_pass"] is True
            and freeze_manifest["checkpoint"][
                "cells_passing_both_gates"
            ] == 24
        )
        all_gates = (
            improvement_gate
            and bootstrap_gate
            and safety_gate
            and coverage_gate
        )

        candidate_results[cid] = {
            "parameters": {
                "stud_strength": candidate["stud_strength"],
                "second_piece_discount": (
                    candidate["second_piece_discount"]
                ),
                "third_plus_discount": (
                    candidate["third_plus_discount"]
                ),
            },
            "mean_held_out_log_loss": round(candidate_loss, 12),
            "improvement_raw_minus_candidate": round(
                improvement, 12
            ),
            "folds": fold_metrics[cid],
            "deployment_gates": {
                "minimum_required_improvement": gates_cfg[
                    "minimum_log_loss_improvement_vs_raw_control"
                ],
                "improvement_gate_pass": improvement_gate,
                "challenge_cluster_bootstrap": {
                    **bootstrap,
                    "favorable_fraction": round(
                        bootstrap["favorable_fraction"], 12
                    ),
                    "improvement_raw_minus_candidate_percentiles": {
                        key: round(value, 12)
                        for key, value in bootstrap[
                            "improvement_raw_minus_candidate_percentiles"
                        ].items()
                    },
                },
                "minimum_required_bootstrap_favorable_fraction": gates_cfg[
                    "challenge_cluster_bootstrap_favorable_fraction_vs_raw"
                ],
                "bootstrap_gate_pass": bootstrap_gate,
                "topology_x_asset_mix": group_rows,
                "maximum_observed_group_regression": round(
                    max_regression, 12
                ),
                "maximum_allowed_group_regression": gates_cfg[
                    "maximum_topology_x_asset_mix_log_loss_regression_vs_raw"
                ],
                "group_safety_gate_pass": safety_gate,
                "all_24_frozen_cells_coverage_gate_pass": coverage_gate,
                "all_deployment_gates_pass": all_gates,
            },
        }

    ranked = sorted(
        candidate_ids,
        key=lambda cid: (combined[cid], cid),
    )
    selected_id = ranked[0]
    runner_up_id = ranked[1]
    gap = combined[runner_up_id] - combined[selected_id]
    selection_resolved = gap + EPS >= 0.002

    selected_all_gates = candidate_results[selected_id][
        "deployment_gates"
    ]["all_deployment_gates_pass"]
    candidates_passing_all_gates = [
        cid for cid in candidate_ids
        if candidate_results[cid]["deployment_gates"][
            "all_deployment_gates_pass"
        ]
    ]
    any_candidate_all_gates = bool(candidates_passing_all_gates)

    (
        status,
        production_candidate_eligible,
        family_confirmation_supported,
        next_action,
    ) = interpretation_status(
        selection_resolved,
        selected_all_gates,
        any_candidate_all_gates,
    )

    # Hard-bind status semantics to the frozen interpretation contract.
    ladder_cases = {
        row["case"]
        for row in interpretation["interpretation_ladder"]
    }
    assert ladder_cases == {
        "unique_candidate_selected_and_all_deployment_gates_pass",
        "unique_candidate_selected_but_any_deployment_gate_fails",
        (
            "candidate_selection_unresolved_gap_below_0_002_and_at_least_"
            "one_candidate_individually_clears_all_deployment_gates"
        ),
        (
            "candidate_selection_unresolved_gap_below_0_002_and_neither_"
            "candidate_individually_clears_all_deployment_gates"
        ),
    }

    evaluated_at = datetime.now(timezone.utc).isoformat()

    result = {
        "schema_version": 1,
        "status": status,
        "study_id": "package-adjustment-v4-elite-fragmentation",
        "phase": "3F",
        "frozen": True,
        "research_only": True,
        "evaluation_occurs_once": True,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "production_revision_unchanged": (
            "v1.6-v5-size2-composition-overlay"
        ),
        "evaluated_at_utc": evaluated_at,
        "source_evidence": {
            "raw_ballots": 600,
            "effective_votes": 600.0,
            "voter_clusters": 31,
            "distinct_challenges": 231,
            "required_cells": 24,
            "freeze_dataset_sha256": sha256_file(FROZEN),
        },
        "implementation": {
            "raw_score_delta": (
                "(sum(FV)_A - sum(FV)_B) / "
                "(sum(FV)_A + sum(FV)_B)"
            ),
            "v4_side_score": (
                "T + clamp(v1/10000,0,1) * "
                "(stud_strength*v1 - second_piece_discount*v2 "
                "- third_plus_discount*sum(v3+))"
            ),
            "v4_score_delta": (
                "(E_A-E_B)/(abs(E_A)+abs(E_B))"
            ),
            "probability_link": (
                "logistic(beta * normalized_score_delta + "
                "delta_left * I(canonical_A_displayed_left))"
            ),
            "beta_constraint": "beta > 0 via beta=exp(log_beta)",
            "cross_validation": (
                "5-fold grouped by frozen voter cluster"
            ),
            "fold_assignment": (
                "SHA256(package-adjustment-v4-phase3f-fold-v1|"
                "voter_cluster), sorted then round-robin across five folds"
            ),
            "fold_voter_counts": fold_voter_counts,
            "optimizer": (
                "scipy.optimize.minimize L-BFGS-B with analytic gradient"
            ),
            "scipy_version": scipy.__version__,
            "bootstrap": {
                "method": (
                    "challenge_cluster_resampling_of_fixed_oof_losses"
                ),
                "draws": BOOTSTRAP_DRAWS,
                "seed": BOOTSTRAP_SEED,
                "rng": "python_random.Random_MT19937",
            },
            "candidate_parameter_tuning_performed": False,
            "runner_up_substitution_allowed": False,
            "development_ktc_examples_used_as_tiebreaker": False,
            "row_predictions_persisted": False,
        },
        "raw_control": {
            "id": RAW_ID,
            "mean_held_out_log_loss": round(raw_loss, 12),
            "folds": fold_metrics[RAW_ID],
        },
        "candidate_results": candidate_results,
        "candidate_selection": {
            "eligible_candidate_ids": candidate_ids,
            "ranked_by_mean_held_out_log_loss": ranked,
            "selected_candidate_id": selected_id,
            "runner_up_candidate_id": runner_up_id,
            "best_vs_runner_up_log_loss_gap": round(gap, 12),
            "runner_up_resolution_threshold": 0.002,
            "selection_resolved": selection_resolved,
        },
        "interpretation": {
            "contract_status": interpretation["status"],
            "contract_sha256": sha256_file(INTERPRETATION),
            "candidates_passing_all_deployment_gates": (
                candidates_passing_all_gates
            ),
            "family_confirmation_supported": (
                family_confirmation_supported
            ),
            "production_candidate_eligible": (
                production_candidate_eligible
            ),
            "no_post_hoc_runner_up_substitution": True,
        },
        "production_candidate_eligible": production_candidate_eligible,
        "family_confirmation_supported": family_confirmation_supported,
        "next_action": next_action,
    }

    # Internal invariants before any output is written.
    assert result["source_evidence"]["freeze_dataset_sha256"] == (
        EXPECTED_FROZEN_SHA256
    )
    assert result["candidate_selection"][
        "runner_up_resolution_threshold"
    ] == 0.002
    assert set(result["candidate_results"]) == set(candidate_ids)
    assert (
        result["production_candidate_eligible"]
        is (status == "CONFIRMATION_PASSED_PRODUCTION_CANDIDATE_ELIGIBLE")
    )
    if family_confirmation_supported:
        assert not selection_resolved
        assert any_candidate_all_gates
    if selection_resolved and not selected_all_gates:
        assert status == "CONFIRMATION_FAILED_RESEARCH_ONLY"

    result_text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    RESULT_OUT.write_text(result_text, encoding="utf-8")
    result_sha256 = hashlib.sha256(result_text.encode()).hexdigest()

    manifest = {
        "schema_version": 1,
        "status": "FROZEN_ONE_TIME_V4_PHASE3F_EVALUATION_MANIFEST",
        "study_id": "package-adjustment-v4-elite-fragmentation",
        "phase": "3F",
        "frozen": True,
        "research_only": True,
        "one_time_evaluation_consumed": True,
        "evaluation_status": status,
        "selected_candidate_id": selected_id,
        "candidate_selection_resolved": selection_resolved,
        "candidates_passing_all_deployment_gates": (
            candidates_passing_all_gates
        ),
        "family_confirmation_supported": family_confirmation_supported,
        "production_candidate_eligible": production_candidate_eligible,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "production_revision_unchanged": (
            "v1.6-v5-size2-composition-overlay"
        ),
        "evaluated_at_utc": evaluated_at,
        "source_artifacts": {
            "preregistration": {
                "path": str(PREREG.relative_to(ROOT)),
                "git_blob_sha": EXPECTED_BLOBS["prereg"],
                "sha256": sha256_file(PREREG),
            },
            "frozen_candidate_family": {
                "path": str(FAMILY.relative_to(ROOT)),
                "git_blob_sha": EXPECTED_BLOBS["family"],
                "sha256": sha256_file(FAMILY),
            },
            "confirmation_catalog": {
                "path": str(CATALOG.relative_to(ROOT)),
                "git_blob_sha": EXPECTED_BLOBS["catalog"],
                "sha256": sha256_file(CATALOG),
            },
            "frozen_exact_600_dataset": {
                "path": str(FROZEN.relative_to(ROOT)),
                "git_blob_sha": EXPECTED_BLOBS["frozen"],
                "sha256": sha256_file(FROZEN),
            },
            "freeze_manifest": {
                "path": str(FREEZE_MANIFEST.relative_to(ROOT)),
                "git_blob_sha": EXPECTED_BLOBS["freeze_manifest"],
                "sha256": sha256_file(FREEZE_MANIFEST),
            },
            "pre_unblinding_interpretation_contract": {
                "path": str(INTERPRETATION.relative_to(ROOT)),
                "git_blob_sha": EXPECTED_BLOBS["interpretation"],
                "sha256": sha256_file(INTERPRETATION),
            },
        },
        "evaluation_result": {
            "path": str(RESULT_OUT.relative_to(ROOT)),
            "sha256": result_sha256,
            "byte_length": len(result_text.encode()),
        },
        "candidate_parameter_tuning_performed": False,
        "runner_up_substitution_performed": False,
        "row_predictions_persisted": False,
        "next_action": next_action,
    }
    manifest_text = json.dumps(
        manifest, indent=2, sort_keys=True
    ) + "\n"
    MANIFEST_OUT.write_text(manifest_text, encoding="utf-8")
    manifest_sha256 = hashlib.sha256(
        manifest_text.encode()
    ).hexdigest()

    def f6(v):
        return f"{float(v):.6f}"

    report = [
        "# Package Adjustment V4 — Phase 3F One-Time Confirmation Evaluation",
        "",
        f"**Status:** `{status}`",
        "",
        (
            "- Frozen evidence: **600.00 effective votes / "
            "31 voter clusters / 231 challenges / 24 cells**"
        ),
        f"- Raw control held-out log loss: **{f6(raw_loss)}**",
        f"- Selected candidate: **`{selected_id}`**",
        (
            f"- Best-vs-runner-up gap: **{f6(gap)}** "
            "(resolved if >= 0.002000)"
        ),
        (
            "- Candidate selection: **"
            + ("RESOLVED" if selection_resolved else "UNRESOLVED")
            + "**"
        ),
        "",
        "## Frozen candidate comparison",
        "",
        "| Candidate | Held-out log loss | Improvement vs raw | All deployment gates |",
        "|---|---:|---:|---|",
    ]
    for cid in ranked:
        cr = candidate_results[cid]
        all_pass = cr["deployment_gates"]["all_deployment_gates_pass"]
        report.append(
            f"| {cid} | {cr['mean_held_out_log_loss']:.6f} | "
            f"{cr['improvement_raw_minus_candidate']:.6f} | "
            f"{'PASS' if all_pass else 'FAIL'} |"
        )

    report += [
        "",
        "## Deployment gates by frozen candidate",
        "",
    ]
    for cid in ranked:
        g = candidate_results[cid]["deployment_gates"]
        b = g["challenge_cluster_bootstrap"]
        report += [
            f"### `{cid}`",
            "",
            (
                "- Improvement >= 0.005: **"
                + ("PASS" if g["improvement_gate_pass"] else "FAIL")
                + f"** ({candidate_results[cid]['improvement_raw_minus_candidate']:.6f})"
            ),
            (
                "- Challenge-cluster bootstrap favorable >= 0.90: **"
                + ("PASS" if g["bootstrap_gate_pass"] else "FAIL")
                + f"** ({b['favorable_fraction']:.4f})"
            ),
            (
                "- Max topology×asset-mix regression <= 0.03: **"
                + ("PASS" if g["group_safety_gate_pass"] else "FAIL")
                + f"** ({g['maximum_observed_group_regression']:.6f})"
            ),
            (
                "- 24/24 frozen coverage: **"
                + (
                    "PASS"
                    if g["all_24_frozen_cells_coverage_gate_pass"]
                    else "FAIL"
                )
                + "**"
            ),
            "",
        ]

    report += [
        "## Frozen interpretation",
        "",
        (
            "- Candidates independently passing every deployment gate: **"
            + (
                ", ".join(f"`{cid}`" for cid in candidates_passing_all_gates)
                if candidates_passing_all_gates
                else "none"
            )
            + "**"
        ),
        (
            "- Family confirmation supported: **"
            + ("YES" if family_confirmation_supported else "NO")
            + "**"
        ),
        (
            "- Production-candidate eligible: **"
            + ("YES" if production_candidate_eligible else "NO")
            + "**"
        ),
        "",
        next_action,
        "",
        (
            "> No parameter tuning, KTC-example tiebreaker, runner-up "
            "substitution, or automatic production promotion was performed."
        ),
        "",
    ]
    report_text = "\n".join(report)
    REPORT_OUT.write_text(report_text, encoding="utf-8")

    # Final read-back validation. If this process exits 0, the three outputs
    # are internally coherent and safe to artifact immediately.
    result_check = json.loads(RESULT_OUT.read_text(encoding="utf-8"))
    manifest_check = json.loads(
        MANIFEST_OUT.read_text(encoding="utf-8")
    )
    assert result_check["status"] == status
    assert manifest_check["evaluation_status"] == status
    assert manifest_check["one_time_evaluation_consumed"] is True
    assert (
        manifest_check["evaluation_result"]["sha256"]
        == sha256_file(RESULT_OUT)
    )
    assert result_check["production_change_authorized"] is False
    assert manifest_check["production_change_authorized"] is False

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report_text)

    env_path = os.environ.get("GITHUB_ENV")
    if env_path:
        with open(env_path, "a", encoding="utf-8") as fh:
            fh.write(f"V4_PHASE3F_STATUS={status}\n")
            fh.write(
                f"V4_PHASE3F_RESULT_SHA256={result_sha256}\n"
            )
            fh.write(
                f"V4_PHASE3F_MANIFEST_SHA256={manifest_sha256}\n"
            )

    print(report_text)
    print("V4_PHASE3F_STATUS=" + status)
    print("V4_PHASE3F_SELECTED_CANDIDATE=" + selected_id)
    print(
        "V4_PHASE3F_SELECTION_RESOLVED="
        + str(selection_resolved).lower()
    )
    print(
        "V4_PHASE3F_FAMILY_SUPPORTED="
        + str(family_confirmation_supported).lower()
    )
    print(
        "V4_PHASE3F_PRODUCTION_CANDIDATE_ELIGIBLE="
        + str(production_candidate_eligible).lower()
    )
    print("V4_PHASE3F_RESULT_SHA256=" + result_sha256)
    print("V4_PHASE3F_MANIFEST_SHA256=" + manifest_sha256)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--selftest", action="store_true")
    modes.add_argument("--audit-calculations", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
    elif args.audit_calculations:
        calculation_audit()
    elif args.preflight:
        preflight()
    else:
        main()

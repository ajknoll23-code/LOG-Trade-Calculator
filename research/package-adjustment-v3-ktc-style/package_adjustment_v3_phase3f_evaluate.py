#!/usr/bin/env python3
"""Package Adjustment V3 Phase 3F — one-time frozen confirmation evaluation.

Consumes only the immutable Phase 3E exact-600 evidence and the frozen catalog.
Implements the Phase 3A preregistered evaluation exactly once:
- raw additive g=1.00 control + frozen g=2.01/2.15/2.30 candidates;
- 5-fold CV grouped by voter cluster;
- beta > 0 via beta=exp(log_beta), plus delta_left;
- calibration fit only on each training fold;
- held-out weighted log loss as primary metric;
- candidate selection among the three gamma candidates only;
- runner-up unresolved threshold < 0.002;
- deployment gates vs raw control;
- challenge-cluster bootstrap favorable fraction.

This evaluator does not modify production and does not tune gamma.
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
D = ROOT / "research" / "package-adjustment-v3-ktc-style"

PREREG = D / "phase3_confirmation_preregistration.json"
CATALOG = D / "phase3_confirmation_catalog.json"
FROZEN = D / "phase3_exact_600_frozen.json"
FREEZE_MANIFEST = D / "phase3_exact_600_freeze_manifest.json"
PHASE2_FAMILY = D / "phase2_candidate_family.json"

RESULT_OUT = D / "phase3_confirmation_evaluation.json"
MANIFEST_OUT = D / "phase3_confirmation_evaluation_manifest.json"
REPORT_OUT = Path("/tmp/package-adjustment-v3-phase3f-evaluation-report.md")

MODEL_SPECS = [
    ("raw-additive-control-g1.00", 1.00, True),
    ("power-g2.01", 2.01, False),
    ("power-g2.15", 2.15, False),
    ("power-g2.30", 2.30, False),
]
CANDIDATE_IDS = ["power-g2.01", "power-g2.15", "power-g2.30"]

FOLD_COUNT = 5
FOLD_SEED = "package-adjustment-v3-phase3f-fold-v1"
BOOTSTRAP_SEED = 2026091903
BOOTSTRAP_DRAWS = 20000
EPS = 1e-15


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def logloss_one(y: int, p: float) -> float:
    p = min(1.0 - 1e-12, max(1e-12, float(p)))
    return -(y * math.log(p) + (1 - y) * math.log(1.0 - p))


def normalized_score_delta(challenge: dict, gamma: float) -> float:
    # Algebraically identical to Phase 3B's apex-normalized implementation:
    # dividing every fv by the same apex cancels in (score_a-score_b)/(score_a+score_b).
    score_a = sum(float(asset["fv"]) ** gamma for asset in challenge["side_a"])
    score_b = sum(float(asset["fv"]) ** gamma for asset in challenge["side_b"])
    denom = score_a + score_b
    if not math.isfinite(denom) or denom <= 0:
        raise RuntimeError("Nonpositive/nonfinite normalized score denominator")
    out = (score_a - score_b) / denom
    if not math.isfinite(out) or not (-1.0 < out < 1.0):
        raise RuntimeError(f"Invalid normalized score delta: {out}")
    return out


def deterministic_fold_map(voter_clusters):
    ordered = sorted(
        voter_clusters,
        key=lambda voter: hashlib.sha256(
            f"{FOLD_SEED}|{voter}".encode("utf-8")
        ).hexdigest(),
    )
    if len(ordered) != 30:
        raise RuntimeError(f"Expected 30 voter clusters, got {len(ordered)}")
    mapping = {voter: idx % FOLD_COUNT for idx, voter in enumerate(ordered)}
    counts = {fold: 0 for fold in range(FOLD_COUNT)}
    for fold in mapping.values():
        counts[fold] += 1
    if sorted(counts.values()) != [6, 6, 6, 6, 6]:
        raise RuntimeError(f"Unexpected grouped-fold sizes: {counts}")
    return mapping, counts


def fit_calibration(rows, model_id):
    # rows contain x, left, y, weight.
    total_weight = sum(r["weight"] for r in rows)
    if total_weight <= 0:
        raise RuntimeError("Training fold has nonpositive weight")

    def objective(theta):
        log_beta, delta_left = float(theta[0]), float(theta[1])
        beta = math.exp(log_beta)
        loss_sum = 0.0
        grad_log_beta = 0.0
        grad_delta = 0.0

        for row in rows:
            z = beta * row["x"][model_id] + delta_left * row["left"]
            p = sigmoid(z)
            w = row["weight"]
            loss_sum += w * logloss_one(row["y"], p)
            residual = p - row["y"]
            grad_log_beta += w * residual * beta * row["x"][model_id]
            grad_delta += w * residual * row["left"]

        return (
            loss_sum / total_weight,
            [grad_log_beta / total_weight, grad_delta / total_weight],
        )

    # Fixed, outcome-independent initialization. Gamma itself is never optimized.
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
            f"Calibration failed for {model_id}: {fit.status} {fit.message}"
        )

    log_beta = float(fit.x[0])
    delta_left = float(fit.x[1])
    beta = math.exp(log_beta)
    if not (math.isfinite(beta) and beta > 0 and math.isfinite(delta_left)):
        raise RuntimeError(f"Nonfinite calibration for {model_id}")

    return {
        "beta": beta,
        "log_beta": log_beta,
        "delta_left": delta_left,
        "training_weight": total_weight,
        "optimizer_iterations": int(getattr(fit, "nit", 0)),
        "optimizer_objective": float(fit.fun),
    }


def evaluate_oof(rows):
    voter_clusters = sorted({r["voter_cluster"] for r in rows})
    fold_map, fold_voter_counts = deterministic_fold_map(voter_clusters)

    for row in rows:
        row["fold"] = fold_map[row["voter_cluster"]]

    predictions = {model_id: {} for model_id, _, _ in MODEL_SPECS}
    fold_metrics = {model_id: [] for model_id, _, _ in MODEL_SPECS}

    for fold in range(FOLD_COUNT):
        train = [r for r in rows if r["fold"] != fold]
        test = [r for r in rows if r["fold"] == fold]
        if not train or not test:
            raise RuntimeError(f"Empty train/test fold {fold}")

        for model_id, _, _ in MODEL_SPECS:
            params = fit_calibration(train, model_id)
            test_weight = sum(r["weight"] for r in test)
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

            fold_metrics[model_id].append(
                {
                    "fold": fold,
                    "train_voter_clusters": 24,
                    "test_voter_clusters": 6,
                    "train_ballots": len(train),
                    "test_ballots": len(test),
                    "train_effective_weight": round(
                        float(params["training_weight"]), 9
                    ),
                    "test_effective_weight": round(float(test_weight), 9),
                    "held_out_log_loss": round(loss_sum / test_weight, 12),
                    "calibration": {
                        "beta": round(params["beta"], 12),
                        "log_beta": round(params["log_beta"], 12),
                        "delta_left": round(params["delta_left"], 12),
                        "optimizer_iterations": params["optimizer_iterations"],
                    },
                }
            )

    # Every ballot must have exactly one held-out prediction per model.
    ordinals = {r["ordinal"] for r in rows}
    for model_id in predictions:
        if set(predictions[model_id]) != ordinals:
            raise RuntimeError(f"Incomplete OOF predictions for {model_id}")

    combined = {}
    total_weight = sum(r["weight"] for r in rows)
    for model_id, _, _ in MODEL_SPECS:
        weighted = sum(
            r["weight"] * predictions[model_id][r["ordinal"]]["loss"]
            for r in rows
        )
        combined[model_id] = weighted / total_weight

    return predictions, fold_metrics, combined, fold_voter_counts


def bootstrap_challenges(rows, predictions, selected_id, raw_id):
    cluster = defaultdict(lambda: {"improvement_sum": 0.0, "weight": 0.0})
    for row in rows:
        raw_loss = predictions[raw_id][row["ordinal"]]["loss"]
        cand_loss = predictions[selected_id][row["ordinal"]]["loss"]
        w = row["weight"]
        c = cluster[row["challenge_id"]]
        c["improvement_sum"] += w * (raw_loss - cand_loss)
        c["weight"] += w

    challenge_ids = sorted(cluster)
    if len(challenge_ids) != 218:
        raise RuntimeError(
            f"Expected 218 challenge clusters in frozen checkpoint, got {len(challenge_ids)}"
        )

    rng = random.Random(BOOTSTRAP_SEED)
    favorable = 0
    improvements = []

    for _ in range(BOOTSTRAP_DRAWS):
        diff_sum = 0.0
        weight_sum = 0.0
        for _j in range(len(challenge_ids)):
            cid = challenge_ids[rng.randrange(len(challenge_ids))]
            diff_sum += cluster[cid]["improvement_sum"]
            weight_sum += cluster[cid]["weight"]
        if weight_sum <= 0:
            raise RuntimeError("Bootstrap sample has nonpositive weight")
        imp = diff_sum / weight_sum
        improvements.append(imp)
        if imp > 0:
            favorable += 1

    improvements.sort()

    def pct(q):
        if not improvements:
            return None
        h = (len(improvements) - 1) * q
        lo = int(math.floor(h))
        hi = int(math.ceil(h))
        if lo == hi:
            return improvements[lo]
        frac = h - lo
        return improvements[lo] * (1 - frac) + improvements[hi] * frac

    return {
        "method": "challenge_cluster_resampling_of_fixed_oof_losses",
        "cluster_count": len(challenge_ids),
        "draws": BOOTSTRAP_DRAWS,
        "rng": "python_random.Random_MT19937",
        "seed": BOOTSTRAP_SEED,
        "favorable_fraction": favorable / BOOTSTRAP_DRAWS,
        "improvement_raw_minus_candidate_percentiles": {
            "p05": pct(0.05),
            "median": pct(0.50),
            "p95": pct(0.95),
        },
    }


def selftest():
    # Logistic calibration should recover a positive beta on a deterministic
    # toy sample and grouped folds must remain 6 voters each.
    fake_voters = [f"v{i:02d}" for i in range(1, 31)]
    fmap, counts = deterministic_fold_map(fake_voters)
    assert len(fmap) == 30
    assert sorted(counts.values()) == [6, 6, 6, 6, 6]

    rows = []
    ordinal = 0
    for voter_i, voter in enumerate(fake_voters):
        for j in range(4):
            ordinal += 1
            x = (-0.75, -0.25, 0.25, 0.75)[j]
            left = 1 if (voter_i + j) % 2 == 0 else 0
            y = 1 if x + 0.15 * left > 0 else 0
            rows.append(
                {
                    "ordinal": ordinal,
                    "voter_cluster": voter,
                    "challenge_id": f"c{j}",
                    "topology": "1v2",
                    "asset_mix": "players_only",
                    "left": left,
                    "y": y,
                    "weight": 1.0,
                    "x": {
                        "raw-additive-control-g1.00": x,
                        "power-g2.01": x,
                        "power-g2.15": x,
                        "power-g2.30": x,
                    },
                }
            )

    params = fit_calibration(rows, "power-g2.01")
    assert params["beta"] > 0
    assert math.isfinite(params["delta_left"])

    # Score normalization is side-swap antisymmetric.
    challenge = {
        "side_a": [{"fv": 8000}, {"fv": 2000}],
        "side_b": [{"fv": 6000}, {"fv": 3500}],
    }
    d = normalized_score_delta(challenge, 2.15)
    swapped = {
        "side_a": challenge["side_b"],
        "side_b": challenge["side_a"],
    }
    ds = normalized_score_delta(swapped, 2.15)
    assert abs(d + ds) < 1e-12

    print("Package Adjustment V3 Phase 3F evaluator self-test PASS")


def main():
    if RESULT_OUT.exists() or MANIFEST_OUT.exists():
        raise RuntimeError("Phase 3F evaluation already exists; refusing second evaluation")

    cfg = json.loads(PREREG.read_text(encoding="utf-8"))
    catalog_doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    freeze_manifest = json.loads(FREEZE_MANIFEST.read_text(encoding="utf-8"))
    phase2 = json.loads(PHASE2_FAMILY.read_text(encoding="utf-8"))

    assert cfg["status"] == "FROZEN_FRESH_CONFIRMATION_PREREGISTRATION"
    assert cfg["frozen"] is True
    assert cfg["production_change_authorized"] is False
    assert cfg["candidate_family_fingerprint_sha256"] == (
        "c8610b7ac74631ed87cf52490f8368cfd3805034725cdb59fbed0d76a3b885ed"
    )

    plan = cfg["evaluation_plan_after_freeze"]
    assert plan["models_compared"] == [
        "raw-additive-control-g1.00",
        "power-g2.01",
        "power-g2.15",
        "power-g2.30",
    ]
    assert plan["primary_metric"] == "held-out log loss"
    assert plan["cross_validation"] == (
        "5-fold grouped by voter identity; a voter may appear in only one fold"
    )
    assert plan["calibration_parameters_refit_inside_each_training_fold"] is True
    assert plan["beta_constraint"] == "beta > 0 via beta=exp(log_beta)"
    assert plan["left_bias_parameter"] == "delta_left"
    assert plan["raw_additive_control_gamma"] == 1

    gates = plan["deployment_eligibility_gates"]
    assert gates["minimum_log_loss_improvement_vs_raw_additive_control"] == 0.005
    assert gates["challenge_cluster_bootstrap_favorable_fraction_vs_raw_control"] == 0.9
    assert gates["maximum_topology_x_asset_mix_log_loss_regression_vs_raw_control"] == 0.03
    assert gates["all_24_cells_must_have_frozen_coverage_gate_pass"] is True

    assert phase2["decision"] == "PASS_V3_PHASE2_FAMILY_FROZEN_FOR_FRESH_CONFIRMATION"
    assert phase2["fresh_confirmation_family_ids"] == CANDIDATE_IDS
    assert phase2["production_change_authorized"] is False

    assert frozen["status"] == "FROZEN_EXACT_600_CONFIRMATION_EVIDENCE"
    assert frozen["frozen"] is True
    assert frozen["model_evaluation_performed"] is False
    assert frozen["checkpoint_selection_outcome_blind"] is True
    assert frozen["frozen_effective_votes"] == 600.0
    assert frozen["raw_checkpoint_ballot_count"] == 600
    assert frozen["distinct_voter_clusters"] == 30
    assert len(frozen["ballots"]) == 600

    assert freeze_manifest["status"] == "FROZEN_EXACT_600_CONFIRMATION_EVIDENCE_MANIFEST"
    assert freeze_manifest["model_evaluation_performed"] is False
    assert freeze_manifest["production_change_authorized"] is False
    assert freeze_manifest["checkpoint"]["effective_votes"] == 600.0
    assert freeze_manifest["checkpoint"]["distinct_voters"] == 30
    assert freeze_manifest["checkpoint"]["cells_passing_both_gates"] == 24
    assert freeze_manifest["checkpoint"]["coverage_gates_pass"] is True
    assert freeze_manifest["pre_unblinding_provenance_exception"][
        "corrected_five_ktc_all_absent_from_frozen_catalog"
    ] is True

    challenges = {c["id"]: c for c in catalog_doc["challenges"]}
    assert len(challenges) == 240

    rows = []
    for ballot in frozen["ballots"]:
        challenge = challenges.get(ballot["challenge_id"])
        if challenge is None:
            raise RuntimeError(f"Unknown frozen challenge {ballot['challenge_id']}")

        choice = ballot["human_choice"]
        if choice not in {"A", "B"}:
            raise RuntimeError("Frozen ballot choice must be canonical A/B")

        left_flag = 1 if ballot["canonical_a_displayed_left"] else 0
        if ballot["display_left"] not in {"A", "B"}:
            raise RuntimeError("Frozen display orientation invalid")
        if (ballot["display_left"] == "A") != bool(left_flag):
            raise RuntimeError("Frozen orientation fields disagree")

        x_by_model = {}
        for model_id, gamma, _is_control in MODEL_SPECS:
            x_by_model[model_id] = normalized_score_delta(challenge, gamma)

        rows.append(
            {
                "ordinal": int(ballot["ordinal"]),
                "voter_cluster": ballot["voter_cluster"],
                "challenge_id": ballot["challenge_id"],
                "research_cell": ballot["research_cell"],
                "topology": ballot["topology"],
                "asset_mix": ballot["asset_mix"],
                "left": left_flag,
                "y": 1 if choice == "A" else 0,
                "weight": float(ballot["frozen_ballot_weight"]),
                "x": x_by_model,
            }
        )

    assert len(rows) == 600
    assert abs(sum(r["weight"] for r in rows) - 600.0) < 1e-8
    assert len({r["voter_cluster"] for r in rows}) == 30
    assert len({r["challenge_id"] for r in rows}) == 218
    assert len({r["research_cell"] for r in rows}) == 24

    predictions, fold_metrics, combined, fold_voter_counts = evaluate_oof(rows)

    # Candidate selection is preregistered among the three frozen gamma candidates.
    ranked_candidates = sorted(
        CANDIDATE_IDS,
        key=lambda model_id: (combined[model_id], model_id),
    )
    selected_id = ranked_candidates[0]
    runner_up_id = ranked_candidates[1]
    runner_up_gap = combined[runner_up_id] - combined[selected_id]
    gamma_selection_resolved = runner_up_gap + EPS >= 0.002

    raw_id = "raw-additive-control-g1.00"
    improvement = combined[raw_id] - combined[selected_id]

    # Topology x asset-mix safety groups using held-out OOF predictions.
    group_rows = []
    regressions = []
    for topology in sorted({r["topology"] for r in rows}):
        for asset_mix in ("includes_picks", "players_only"):
            subset = [
                r for r in rows
                if r["topology"] == topology and r["asset_mix"] == asset_mix
            ]
            if not subset:
                raise RuntimeError(f"Missing safety group {topology}|{asset_mix}")
            wsum = sum(r["weight"] for r in subset)
            raw_loss = sum(
                r["weight"] * predictions[raw_id][r["ordinal"]]["loss"]
                for r in subset
            ) / wsum
            cand_loss = sum(
                r["weight"] * predictions[selected_id][r["ordinal"]]["loss"]
                for r in subset
            ) / wsum
            regression = cand_loss - raw_loss
            regressions.append(regression)
            group_rows.append(
                {
                    "topology": topology,
                    "asset_mix": asset_mix,
                    "effective_weight": round(wsum, 9),
                    "raw_control_log_loss": round(raw_loss, 12),
                    "selected_candidate_log_loss": round(cand_loss, 12),
                    "regression_candidate_minus_raw": round(regression, 12),
                }
            )

    max_group_regression = max(regressions)

    bootstrap = bootstrap_challenges(
        rows=rows,
        predictions=predictions,
        selected_id=selected_id,
        raw_id=raw_id,
    )

    improvement_gate = (
        improvement + EPS
        >= gates["minimum_log_loss_improvement_vs_raw_additive_control"]
    )
    bootstrap_gate = (
        bootstrap["favorable_fraction"] + EPS
        >= gates["challenge_cluster_bootstrap_favorable_fraction_vs_raw_control"]
    )
    safety_gate = (
        max_group_regression
        <= gates["maximum_topology_x_asset_mix_log_loss_regression_vs_raw_control"] + EPS
    )
    coverage_gate = (
        freeze_manifest["checkpoint"]["cells_passing_both_gates"] == 24
        and freeze_manifest["checkpoint"]["coverage_gates_pass"] is True
    )

    all_deployment_gates = (
        improvement_gate and bootstrap_gate and safety_gate and coverage_gate
    )

    if not gamma_selection_resolved:
        status = "CONFIRMATION_UNRESOLVED_GAMMA_SELECTION_RESEARCH_ONLY"
        production_candidate_eligible = False
        next_action = (
            "Frozen candidate selection is unresolved because the best and runner-up "
            "mean held-out log loss differ by less than 0.002. Production remains V1.6."
        )
    elif all_deployment_gates:
        status = "CONFIRMATION_PASSED_PRODUCTION_CANDIDATE_ELIGIBLE"
        production_candidate_eligible = True
        next_action = (
            "The selected frozen gamma candidate passed every preregistered "
            "confirmation gate. A separate explicit production deployment phase is "
            "required; this workflow does not alter production."
        )
    else:
        status = "CONFIRMATION_FAILED_RESEARCH_ONLY"
        production_candidate_eligible = False
        next_action = (
            "At least one preregistered deployment gate failed. Keep Package "
            "Adjustment V3 research-only and production remains V1.6."
        )

    model_results = []
    for model_id, gamma, is_control in MODEL_SPECS:
        model_results.append(
            {
                "id": model_id,
                "gamma": gamma,
                "role": "raw_additive_control" if is_control else "frozen_candidate",
                "mean_held_out_log_loss": round(combined[model_id], 12),
                "folds": fold_metrics[model_id],
            }
        )

    evaluated_at = datetime.now(timezone.utc).isoformat()

    result = {
        "schema_version": 1,
        "status": status,
        "study_id": "package-adjustment-v3-ktc-style",
        "phase": "3F",
        "frozen": True,
        "research_only": True,
        "evaluation_occurs_once": True,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "production_revision_unchanged": "v1.6-v5-size2-composition-overlay",
        "evaluated_at_utc": evaluated_at,
        "source_evidence": {
            "raw_ballots": 600,
            "effective_votes": 600.0,
            "voter_clusters": 30,
            "distinct_challenges": 218,
            "required_cells": 24,
            "freeze_dataset_sha256": sha256_file(FROZEN),
        },
        "implementation": {
            "score_delta": "(sum(fv**gamma)_A - sum(fv**gamma)_B) / (sum(fv**gamma)_A + sum(fv**gamma)_B)",
            "probability_link": plan["probability_link"],
            "beta_constraint": plan["beta_constraint"],
            "left_bias_parameter": plan["left_bias_parameter"],
            "cross_validation": plan["cross_validation"],
            "fold_assignment": (
                "SHA256(package-adjustment-v3-phase3f-fold-v1|voter_cluster), "
                "sorted then round-robin across five folds; six voters/fold"
            ),
            "fold_voter_counts": fold_voter_counts,
            "optimizer": "scipy.optimize.minimize L-BFGS-B with analytic gradient",
            "scipy_version": scipy.__version__,
            "bootstrap": {
                "method": bootstrap["method"],
                "draws": bootstrap["draws"],
                "cluster_count": bootstrap["cluster_count"],
                "seed": bootstrap["seed"],
                "rng": bootstrap["rng"],
            },
            "gamma_refit_or_tuning_performed": False,
            "row_predictions_persisted": False,
        },
        "models": model_results,
        "candidate_selection": {
            "eligible_candidate_ids": CANDIDATE_IDS,
            "ranked_by_mean_held_out_log_loss": ranked_candidates,
            "selected_candidate_id": selected_id,
            "runner_up_candidate_id": runner_up_id,
            "best_vs_runner_up_log_loss_gap": round(runner_up_gap, 12),
            "runner_up_resolution_threshold": 0.002,
            "gamma_selection_resolved": gamma_selection_resolved,
            "development_ktc_examples_used_as_tiebreaker": False,
        },
        "deployment_gates": {
            "selected_candidate_id": selected_id,
            "raw_control_id": raw_id,
            "raw_control_mean_held_out_log_loss": round(combined[raw_id], 12),
            "selected_candidate_mean_held_out_log_loss": round(
                combined[selected_id], 12
            ),
            "improvement_raw_minus_candidate": round(improvement, 12),
            "minimum_required_improvement": gates[
                "minimum_log_loss_improvement_vs_raw_additive_control"
            ],
            "improvement_gate_pass": improvement_gate,
            "challenge_cluster_bootstrap": {
                **bootstrap,
                "favorable_fraction": round(
                    bootstrap["favorable_fraction"], 12
                ),
                "improvement_raw_minus_candidate_percentiles": {
                    k: round(v, 12)
                    for k, v in bootstrap[
                        "improvement_raw_minus_candidate_percentiles"
                    ].items()
                },
            },
            "minimum_required_bootstrap_favorable_fraction": gates[
                "challenge_cluster_bootstrap_favorable_fraction_vs_raw_control"
            ],
            "bootstrap_gate_pass": bootstrap_gate,
            "topology_x_asset_mix": group_rows,
            "maximum_observed_group_regression": round(max_group_regression, 12),
            "maximum_allowed_group_regression": gates[
                "maximum_topology_x_asset_mix_log_loss_regression_vs_raw_control"
            ],
            "group_safety_gate_pass": safety_gate,
            "all_24_frozen_cells_coverage_gate_pass": coverage_gate,
            "all_deployment_gates_pass": all_deployment_gates,
        },
        "production_candidate_eligible": production_candidate_eligible,
        "pre_unblinding_provenance_exception_carried_forward": (
            freeze_manifest["pre_unblinding_provenance_exception"]
        ),
        "next_action": next_action,
    }

    result_text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    RESULT_OUT.write_text(result_text, encoding="utf-8")
    result_sha256 = hashlib.sha256(result_text.encode("utf-8")).hexdigest()

    manifest = {
        "schema_version": 1,
        "status": "FROZEN_ONE_TIME_PHASE3F_EVALUATION_MANIFEST",
        "study_id": "package-adjustment-v3-ktc-style",
        "phase": "3F",
        "frozen": True,
        "research_only": True,
        "one_time_evaluation_consumed": True,
        "evaluation_status": status,
        "selected_candidate_id": selected_id,
        "production_candidate_eligible": production_candidate_eligible,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "production_revision_unchanged": "v1.6-v5-size2-composition-overlay",
        "evaluated_at_utc": evaluated_at,
        "source_artifacts": {
            "preregistration": {
                "path": str(PREREG.relative_to(ROOT)),
                "git_blob_sha": "19966121899d41bdbc754a6a260758cf175b12e2",
                "sha256": sha256_file(PREREG),
            },
            "catalog": {
                "path": str(CATALOG.relative_to(ROOT)),
                "git_blob_sha": "3d4615e590697341ee8c27785d8b22e16b82ac44",
                "sha256": sha256_file(CATALOG),
            },
            "frozen_exact_600_dataset": {
                "path": str(FROZEN.relative_to(ROOT)),
                "git_blob_sha": "bf4779cadbfefdb694c1d028d876b2bad819ee88",
                "sha256": sha256_file(FROZEN),
            },
            "freeze_manifest": {
                "path": str(FREEZE_MANIFEST.relative_to(ROOT)),
                "git_blob_sha": "99e6cfcde0cfd28e0c7f486eba00b22bc24edef6",
                "sha256": sha256_file(FREEZE_MANIFEST),
            },
            "phase2_candidate_family": {
                "path": str(PHASE2_FAMILY.relative_to(ROOT)),
                "git_blob_sha": "a43f4998a0f2dc80eb50078d9a599c2bea77464c",
                "sha256": sha256_file(PHASE2_FAMILY),
            },
        },
        "evaluation_result": {
            "path": str(RESULT_OUT.relative_to(ROOT)),
            "sha256": result_sha256,
            "byte_length": len(result_text.encode("utf-8")),
        },
        "row_predictions_persisted": False,
        "gamma_refit_or_tuning_performed": False,
        "next_action": next_action,
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    MANIFEST_OUT.write_text(manifest_text, encoding="utf-8")
    manifest_sha256 = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

    def f6(v):
        return f"{float(v):.6f}"

    report = [
        "# Package Adjustment V3 — Phase 3F One-Time Confirmation Evaluation",
        "",
        f"**Status:** `{status}`",
        "",
        f"- Frozen evidence: **600.00 effective votes / 30 voter clusters / 218 challenges**",
        f"- Raw control held-out log loss: **{f6(combined[raw_id])}**",
        f"- Selected candidate: **`{selected_id}`**",
        f"- Selected candidate held-out log loss: **{f6(combined[selected_id])}**",
        f"- Improvement vs raw: **{f6(improvement)}** (required >= 0.005000)",
        f"- Best vs runner-up gap: **{f6(runner_up_gap)}** (resolved if >= 0.002000)",
        "",
        "## Frozen model comparison",
        "",
        "| Model | Gamma | Held-out log loss |",
        "|---|---:|---:|",
    ]
    for model_id, gamma, _ in MODEL_SPECS:
        report.append(
            f"| {model_id} | {gamma:.2f} | {combined[model_id]:.6f} |"
        )

    report += [
        "",
        "## Deployment gates",
        "",
        f"- Gamma selection resolved: **{'PASS' if gamma_selection_resolved else 'FAIL'}**",
        f"- Improvement >= 0.005: **{'PASS' if improvement_gate else 'FAIL'}**",
        f"- Challenge-cluster bootstrap favorable >= 0.90: **{'PASS' if bootstrap_gate else 'FAIL'}** "
        f"({bootstrap['favorable_fraction']:.4f})",
        f"- Max topology×asset-mix regression <= 0.03: **{'PASS' if safety_gate else 'FAIL'}** "
        f"({max_group_regression:.6f})",
        f"- 24/24 frozen coverage: **{'PASS' if coverage_gate else 'FAIL'}**",
        "",
        "## Governance",
        "",
        next_action,
        "",
        "> This evaluation performs no gamma tuning, no model refit outside fold-level "
        "calibration, no use of the five KTC development examples as a tiebreaker, "
        "and no automatic production promotion.",
        "",
    ]
    report_text = "\n".join(report)
    REPORT_OUT.write_text(report_text, encoding="utf-8")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(report_text)

    env_path = os.environ.get("GITHUB_ENV")
    if env_path:
        with open(env_path, "a", encoding="utf-8") as fh:
            fh.write(f"PHASE3F_STATUS={status}\n")
            fh.write(f"PHASE3F_RESULT_SHA256={result_sha256}\n")
            fh.write(f"PHASE3F_MANIFEST_SHA256={manifest_sha256}\n")

    print(report_text)
    print("PHASE3F_STATUS=" + status)
    print("PHASE3F_SELECTED_CANDIDATE=" + selected_id)
    print("PHASE3F_RESULT_SHA256=" + result_sha256)
    print("PHASE3F_MANIFEST_SHA256=" + manifest_sha256)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        main()

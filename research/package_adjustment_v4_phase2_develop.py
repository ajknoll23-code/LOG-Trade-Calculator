#!/usr/bin/env python3
"""Package Adjustment V4 Phase 2 — spent-evidence structural development.

Uses the already-spent V3 exact-600 dataset strictly as development evidence,
after applying the V4 Phase 1 frozen asset-eligibility rules before reading
eligible ballot outcomes.

No production changes. No gamma tuning. No continuous structural-parameter
optimization. At most two preregistered V4 candidates can be frozen for a
future fresh-confirmation cycle.
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
V4 = ROOT / "research" / "package-adjustment-v4-elite-fragmentation"
V3 = ROOT / "research" / "package-adjustment-v3-ktc-style"

PREREG = V4 / "phase1_structural_preregistration.json"
PHASE1_MANIFEST = V4 / "phase1_manifest.json"
CATALOG = V3 / "phase3_confirmation_catalog.json"
FROZEN = V3 / "phase3_exact_600_frozen.json"
V3_CLOSEOUT = V3 / "package_adjustment_v3_research_closeout.json"

RESULT_OUT = V4 / "phase2_development_results.json"
SUMMARY_OUT = V4 / "phase2_development_summary.md"
MANIFEST_OUT = V4 / "phase2_manifest.json"
CANDIDATE_OUT = V4 / "frozen_candidate.json"

RAW_ID = "raw-additive-control-g1.00"
V3_REF_ID = "v3-reference-power-g2.15"

FOLD_COUNT = 5
FOLD_SEED = "package-adjustment-v4-phase2-fold-v1"
STRESS_SEED = 20260919
STRESS_CASES_PER_SHAPE = 500
SHAPES = [
    (1, 2), (1, 3), (2, 2), (2, 3), (3, 3),
    (3, 4), (4, 6), (5, 6), (6, 6), (1, 10),
]
EPS = 1e-12


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


def power_delta(challenge: dict, gamma: float) -> float:
    a = sum(float(x["fv"]) ** gamma for x in challenge["side_a"])
    b = sum(float(x["fv"]) ** gamma for x in challenge["side_b"])
    denom = a + b
    if not math.isfinite(denom) or denom <= 0:
        raise RuntimeError("Invalid power score denominator")
    return (a - b) / denom


def side_components(values, candidate):
    vals = sorted((float(v) for v in values), reverse=True)
    if not vals or any((not math.isfinite(v) or v <= 0) for v in vals):
        raise ValueError("All side values must be finite and positive")

    v1 = vals[0]
    v2 = vals[1] if len(vals) >= 2 else 0.0
    third_plus = sum(vals[2:]) if len(vals) >= 3 else 0.0
    total = sum(vals)
    elite_factor = min(1.0, max(0.0, v1 / 10000.0))

    premium = elite_factor * (
        candidate["stud_strength"] * v1
        - candidate["second_piece_discount"] * v2
        - candidate["third_plus_discount"] * third_plus
    )
    effective = total + premium

    if not (math.isfinite(premium) and math.isfinite(effective)):
        raise RuntimeError("Nonfinite V4 side score")

    return {
        "total": total,
        "elite_factor": elite_factor,
        "premium": premium,
        "effective": effective,
    }


def v4_delta(challenge: dict, candidate: dict) -> float:
    a = side_components([x["fv"] for x in challenge["side_a"]], candidate)
    b = side_components([x["fv"] for x in challenge["side_b"]], candidate)
    denom = abs(a["effective"]) + abs(b["effective"])
    if denom <= 0 or not math.isfinite(denom):
        raise RuntimeError("Invalid V4 normalized score denominator")
    out = (a["effective"] - b["effective"]) / denom
    if not math.isfinite(out):
        raise RuntimeError("Nonfinite V4 normalized score delta")
    return out


def package_adjustment(side_a, side_b, candidate):
    a = [float(v) for v in side_a]
    b = [float(v) for v in side_b]
    if not a or not b:
        raise ValueError("Trade sides must both be nonempty")

    ca = side_components(a, candidate)
    cb = side_components(b, candidate)

    if len(a) == 1 and len(b) == 1:
        return {
            "adjusted_side": None,
            "adjustment": 0.0,
            "score_a": ca["effective"],
            "score_b": cb["effective"],
        }

    delta = ca["effective"] - cb["effective"]
    if abs(delta) <= 1e-15:
        return {
            "adjusted_side": None,
            "adjustment": 0.0,
            "score_a": ca["effective"],
            "score_b": cb["effective"],
        }

    if delta > 0:
        adjusted_side = "A"
        relative_premium = ca["premium"] - cb["premium"]
    else:
        adjusted_side = "B"
        relative_premium = cb["premium"] - ca["premium"]

    adjustment = max(0.0, relative_premium)
    if not math.isfinite(adjustment) or adjustment < 0:
        raise RuntimeError("Invalid V4 package adjustment")

    return {
        "adjusted_side": adjusted_side,
        "adjustment": adjustment,
        "score_a": ca["effective"],
        "score_b": cb["effective"],
    }


def challenge_eligible_for_v4_development(challenge: dict) -> tuple[bool, list[str]]:
    """Frozen structural filter, evaluated without ballot outcomes.

    V3's catalog already required valued/rostered players at catalog generation.
    V4 adds two frozen exclusions that are fully verifiable from the frozen
    challenge itself: Joe Mixon and draft-pick years outside 2027/2028.
    """
    reasons = []
    assets = list(challenge["side_a"]) + list(challenge["side_b"])

    for asset in assets:
        fv = float(asset.get("fv") or 0)
        if not math.isfinite(fv) or fv <= 0:
            reasons.append("nonpositive_or_nonfinite_fv")

        if asset.get("kind") == "player":
            if str(asset.get("name") or "").strip().casefold() == "joe mixon":
                reasons.append("explicitly_excluded_joe_mixon")
            if asset.get("pos") not in {"QB", "RB", "WR", "TE", "DL", "LB", "DB"}:
                reasons.append("position_not_allowed")
        elif asset.get("kind") == "pick":
            year = int(asset.get("year"))
            round_num = int(asset.get("round"))
            slot = str(asset.get("slot"))
            if year not in {2027, 2028}:
                reasons.append("draft_pick_year_not_2027_2028")
            if round_num not in {1, 2, 3, 4}:
                reasons.append("draft_pick_round_not_1_4")
            if slot not in {"early", "mid", "late"}:
                reasons.append("draft_pick_slot_invalid")
        else:
            reasons.append("unknown_asset_kind")

    return (len(reasons) == 0, sorted(set(reasons)))


def deterministic_fold_map(voter_clusters):
    ordered = sorted(
        voter_clusters,
        key=lambda voter: hashlib.sha256(
            f"{FOLD_SEED}|{voter}".encode("utf-8")
        ).hexdigest(),
    )
    if len(ordered) != 30:
        raise RuntimeError(f"Expected all 30 voter clusters after V4 filtering, got {len(ordered)}")

    mapping = {voter: idx % FOLD_COUNT for idx, voter in enumerate(ordered)}
    counts = {fold: 0 for fold in range(FOLD_COUNT)}
    for fold in mapping.values():
        counts[fold] += 1
    if sorted(counts.values()) != [6, 6, 6, 6, 6]:
        raise RuntimeError(f"Unexpected V4 grouped fold sizes: {counts}")
    return mapping, counts


def fit_calibration(rows, model_id):
    total_weight = sum(row["weight"] for row in rows)
    if total_weight <= 0:
        raise RuntimeError("Nonpositive training weight")

    def objective(theta):
        log_beta = float(theta[0])
        delta_left = float(theta[1])
        beta = math.exp(log_beta)

        loss_sum = 0.0
        grad_log_beta = 0.0
        grad_delta = 0.0

        for row in rows:
            x = row["x"][model_id]
            z = beta * x + delta_left * row["left"]
            p = sigmoid(z)
            w = row["weight"]
            loss_sum += w * logloss_one(row["y"], p)
            residual = p - row["y"]
            grad_log_beta += w * residual * beta * x
            grad_delta += w * residual * row["left"]

        return (
            loss_sum / total_weight,
            [grad_log_beta / total_weight, grad_delta / total_weight],
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
            f"Calibration failed for {model_id}: {fit.status} {fit.message}"
        )

    beta = math.exp(float(fit.x[0]))
    delta_left = float(fit.x[1])
    if not (math.isfinite(beta) and beta > 0 and math.isfinite(delta_left)):
        raise RuntimeError(f"Invalid calibration for {model_id}")

    return {
        "beta": beta,
        "log_beta": float(fit.x[0]),
        "delta_left": delta_left,
        "training_weight": total_weight,
    }


def hard_invariants(candidate):
    checks = {
        "one_for_one_package_adjustment_is_zero": True,
        "side_swap_symmetry": True,
        "asset_order_invariance": True,
        "finite_effective_scores": True,
        "finite_nonnegative_display_adjustment": True,
        "positive_effective_score_monotonicity_under_asset_value_increase": True,
        "adding_a_positive_piece_cannot_reduce_effective_side_score": True,
        "tiny_piece_continuity": True,
        "second_piece_effective_weight_remains_positive": True,
        "third_plus_piece_effective_weight_remains_positive": True,
        "draft_picks_supported_as_first_class_assets": True,
        "multi_vs_multi_supported": True,
        "explicit_player_exclusion_policy_enforced": True,
        "draft_pick_year_policy_2027_2028_only_enforced": True,
    }

    # Fixed-top marginal weights are explicitly positive under the frozen grid.
    for elite_factor in (0.0, 0.25, 0.5, 0.75, 1.0):
        if 1.0 - elite_factor * candidate["second_piece_discount"] <= 0:
            checks["second_piece_effective_weight_remains_positive"] = False
        if 1.0 - elite_factor * candidate["third_plus_discount"] <= 0:
            checks["third_plus_piece_effective_weight_remains_positive"] = False

    # Policy probes.
    fake_good = {
        "side_a": [{"kind": "player", "name": "A", "pos": "WR", "fv": 5000}],
        "side_b": [{"kind": "pick", "name": "2027 Mid 1st", "year": 2027, "round": 1, "slot": "mid", "fv": 5800}],
    }
    fake_bad_joe = {
        "side_a": [{"kind": "player", "name": "Joe Mixon", "pos": "RB", "fv": 3000}],
        "side_b": [{"kind": "player", "name": "B", "pos": "WR", "fv": 3000}],
    }
    fake_bad_2029 = {
        "side_a": [{"kind": "pick", "name": "2029 Mid 1st", "year": 2029, "round": 1, "slot": "mid", "fv": 4000}],
        "side_b": [{"kind": "player", "name": "B", "pos": "WR", "fv": 4000}],
    }
    if not challenge_eligible_for_v4_development(fake_good)[0]:
        checks["draft_picks_supported_as_first_class_assets"] = False
    if challenge_eligible_for_v4_development(fake_bad_joe)[0]:
        checks["explicit_player_exclusion_policy_enforced"] = False
    if challenge_eligible_for_v4_development(fake_bad_2029)[0]:
        checks["draft_pick_year_policy_2027_2028_only_enforced"] = False

    # Pure 1v1 adjustment must always be zero.
    for a in (300, 1500, 4500, 8500):
        for b in (250, 2200, 5000, 9000):
            if package_adjustment([a], [b], candidate)["adjustment"] != 0.0:
                checks["one_for_one_package_adjustment_is_zero"] = False

    # Deterministic stress suite.
    rng = random.Random(STRESS_SEED)
    shape_counts = {f"{a}v{b}": 0 for a, b in SHAPES}
    max_adjustment = 0.0

    for a_count, b_count in SHAPES:
        shape = f"{a_count}v{b_count}"
        for _ in range(STRESS_CASES_PER_SHAPE):
            a = [float(rng.randint(212, 9000)) for _ in range(a_count)]
            b = [float(rng.randint(212, 9000)) for _ in range(b_count)]
            shape_counts[shape] += 1

            ra = side_components(a, candidate)
            rb = side_components(b, candidate)
            if not all(
                math.isfinite(v)
                for v in (
                    ra["premium"], ra["effective"],
                    rb["premium"], rb["effective"],
                )
            ):
                checks["finite_effective_scores"] = False

            result = package_adjustment(a, b, candidate)
            if not math.isfinite(result["adjustment"]) or result["adjustment"] < 0:
                checks["finite_nonnegative_display_adjustment"] = False
            max_adjustment = max(max_adjustment, result["adjustment"])

            # Side-swap symmetry.
            swapped = package_adjustment(b, a, candidate)
            if abs(result["adjustment"] - swapped["adjustment"]) > 1e-8:
                checks["side_swap_symmetry"] = False
            if result["adjusted_side"] == "A" and swapped["adjusted_side"] != "B":
                checks["side_swap_symmetry"] = False
            if result["adjusted_side"] == "B" and swapped["adjusted_side"] != "A":
                checks["side_swap_symmetry"] = False

            # Asset order invariance.
            a_rev = list(reversed(a))
            b_rev = list(reversed(b))
            ro = package_adjustment(a_rev, b_rev, candidate)
            if (
                ro["adjusted_side"] != result["adjusted_side"]
                or abs(ro["adjustment"] - result["adjustment"]) > 1e-8
            ):
                checks["asset_order_invariance"] = False

            # Increasing an existing positive asset may not reduce side score.
            idx = rng.randrange(len(a))
            bumped = list(a)
            bumped[idx] += max(1.0, 0.05 * bumped[idx])
            if side_components(bumped, candidate)["effective"] + 1e-9 < ra["effective"]:
                checks[
                    "positive_effective_score_monotonicity_under_asset_value_increase"
                ] = False

            # Adding any positive piece may not reduce side score.
            added = list(a) + [float(rng.randint(1, 3000))]
            if side_components(added, candidate)["effective"] + 1e-9 < ra["effective"]:
                checks["adding_a_positive_piece_cannot_reduce_effective_side_score"] = False

            # Tiny piece should create a tiny, continuous score change.
            tiny = 1e-6
            tiny_score = side_components(list(a) + [tiny], candidate)["effective"]
            delta = tiny_score - ra["effective"]
            if delta < -1e-10 or abs(delta) > 5e-6:
                checks["tiny_piece_continuity"] = False

    if any(v != STRESS_CASES_PER_SHAPE for v in shape_counts.values()):
        checks["multi_vs_multi_supported"] = False

    return {
        "pass": all(checks.values()),
        "checks": checks,
        "stress_seed": STRESS_SEED,
        "cases_per_shape": STRESS_CASES_PER_SHAPE,
        "stress_case_count": sum(shape_counts.values()),
        "stress_shape_counts": shape_counts,
        "max_display_adjustment": round(max_adjustment, 9),
    }


def evaluate_models(rows, model_ids):
    voters = sorted({row["voter_cluster"] for row in rows})
    fold_map, fold_voter_counts = deterministic_fold_map(voters)
    for row in rows:
        row["fold"] = fold_map[row["voter_cluster"]]

    predictions = {model_id: {} for model_id in model_ids}
    fold_metrics = {model_id: [] for model_id in model_ids}

    for fold in range(FOLD_COUNT):
        train = [r for r in rows if r["fold"] != fold]
        test = [r for r in rows if r["fold"] == fold]
        if not train or not test:
            raise RuntimeError(f"Empty V4 train/test fold {fold}")

        for model_id in model_ids:
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
                predictions[model_id][row["ordinal"]] = loss
                loss_sum += row["weight"] * loss

            fold_metrics[model_id].append(
                {
                    "fold": fold,
                    "test_ballots": len(test),
                    "test_effective_weight": round(float(test_weight), 9),
                    "held_out_log_loss": round(loss_sum / test_weight, 12),
                    "calibration": {
                        "beta": round(params["beta"], 12),
                        "log_beta": round(params["log_beta"], 12),
                        "delta_left": round(params["delta_left"], 12),
                    },
                }
            )

    total_weight = sum(r["weight"] for r in rows)
    combined = {}
    for model_id in model_ids:
        if len(predictions[model_id]) != len(rows):
            raise RuntimeError(f"Incomplete OOF predictions for {model_id}")
        combined[model_id] = sum(
            row["weight"] * predictions[model_id][row["ordinal"]]
            for row in rows
        ) / total_weight

    return predictions, fold_metrics, combined, fold_voter_counts


def selftest():
    candidate = {
        "id": "test",
        "stud_strength": 0.5,
        "second_piece_discount": 0.25,
        "third_plus_discount": 0.5,
    }

    a = side_components([8000, 3000, 1000], candidate)
    b = side_components([3000, 1000, 8000], candidate)
    assert abs(a["effective"] - b["effective"]) < 1e-12

    assert package_adjustment([5000], [4000], candidate)["adjustment"] == 0.0

    good = {
        "side_a": [{"kind": "pick", "name": "2028 Early 1st", "year": 2028, "round": 1, "slot": "early", "fv": 6000}],
        "side_b": [{"kind": "player", "name": "Player X", "pos": "WR", "fv": 6000}],
    }
    bad = {
        "side_a": [{"kind": "pick", "name": "2029 Early 1st", "year": 2029, "round": 1, "slot": "early", "fv": 6000}],
        "side_b": [{"kind": "player", "name": "Player X", "pos": "WR", "fv": 6000}],
    }
    assert challenge_eligible_for_v4_development(good)[0] is True
    assert challenge_eligible_for_v4_development(bad)[0] is False

    inv = hard_invariants(candidate)
    assert inv["pass"] is True, inv

    print("Package Adjustment V4 Phase 2 self-test PASS")


def main():
    for path in (RESULT_OUT, SUMMARY_OUT, MANIFEST_OUT, CANDIDATE_OUT):
        if path.exists():
            raise RuntimeError(f"V4 Phase 2 output already exists; refusing rerun: {path}")

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    phase1_manifest = json.loads(PHASE1_MANIFEST.read_text(encoding="utf-8"))
    catalog_doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    closeout = json.loads(V3_CLOSEOUT.read_text(encoding="utf-8"))

    assert prereg["status"] == "FROZEN_BEFORE_SPENT_EVIDENCE_DEVELOPMENT"
    assert prereg["frozen"] is True
    assert prereg["new_independent_research_cycle"] is True
    assert prereg["production_change_authorized"] is False
    assert prereg["production_revision_must_remain"] == "v1.6-v5-size2-composition-overlay"
    assert prereg["candidate_grid"]["candidate_count"] == 24
    assert prereg["candidate_grid"]["no_continuous_parameter_optimization"] is True
    assert prereg["candidate_grid"]["no_gamma_parameter"] is True
    assert prereg["asset_eligibility"]["players"]["explicitly_excluded_players"] == ["Joe Mixon"]
    assert prereg["asset_eligibility"]["draft_picks"]["years_allowed"] == [2027, 2028]
    assert prereg["asset_eligibility"]["draft_picks"]["2029_and_later_allowed"] is False

    plan = prereg["phase2_development_plan"]
    assert plan["evidence"] == "frozen V3 exact-600 ballots, development-only"
    assert plan["cross_validation"] == "5-fold grouped by frozen voter cluster"
    assert plan["candidate_selection"] == (
        "lowest mean held-out log loss among invariant-passing V4 candidates"
    )
    assert plan["near_tie_rule"]["threshold_mean_log_loss"] == 0.0005
    assert plan["near_tie_rule"]["maximum_candidates_frozen"] == 2

    assert phase1_manifest["v3_outcomes_read"] is False
    assert phase1_manifest["candidate_grid_count"] == 24
    assert closeout["status"] == "research_closed_no_successor_candidate"
    assert closeout["confirmation_evidence"]["spent_development_evidence_for_future_cycles"] is True
    assert closeout["confirmation_evidence"]["may_not_be_reused_as_fresh_confirmation"] is True

    challenges = {c["id"]: c for c in catalog_doc["challenges"]}
    if len(challenges) != 240:
        raise RuntimeError("Expected frozen V3 catalog of 240 challenges")

    # Apply V4 eligibility using only frozen challenge metadata. No human-choice
    # field is inspected to decide inclusion/exclusion.
    eligible_ids = set()
    excluded_ids = {}
    for cid, challenge in challenges.items():
        eligible, reasons = challenge_eligible_for_v4_development(challenge)
        if eligible:
            eligible_ids.add(cid)
        else:
            excluded_ids[cid] = reasons

    structural_ballots = [
        ballot for ballot in frozen["ballots"]
        if ballot["challenge_id"] in eligible_ids
    ]
    excluded_ballots = [
        ballot for ballot in frozen["ballots"]
        if ballot["challenge_id"] not in eligible_ids
    ]

    if len(frozen["ballots"]) != 600:
        raise RuntimeError("Expected exact V3 frozen source of 600 ballots")
    if len(structural_ballots) != 428:
        raise RuntimeError(
            f"Frozen V4 eligibility expected 428 development ballots; got {len(structural_ballots)}"
        )
    if len(excluded_ballots) != 172:
        raise RuntimeError("Frozen V4 eligibility exclusion count drift")
    if len({b["voter_cluster"] for b in structural_ballots}) != 30:
        raise RuntimeError("V4 filtering unexpectedly removed a voter cluster")
    if len({b["challenge_id"] for b in structural_ballots}) != 161:
        raise RuntimeError("V4 eligible distinct-challenge count drift")

    exclusion_reason_ballots = defaultdict(int)
    for ballot in excluded_ballots:
        for reason in excluded_ids[ballot["challenge_id"]]:
            exclusion_reason_ballots[reason] += 1

    # Frozen prereg candidate grid + invariant gating, still independent of outcomes.
    candidates = [dict(c) for c in prereg["candidate_grid"]["candidates"]]
    invariant_results = {}
    invariant_passing = []

    for candidate in candidates:
        inv = hard_invariants(candidate)
        invariant_results[candidate["id"]] = inv
        if inv["pass"]:
            invariant_passing.append(candidate)

    if not invariant_passing:
        raise RuntimeError("No V4 candidate passed frozen hard invariants")

    # Only now interpret eligible human responses/orientation.
    rows = []
    for ballot in structural_ballots:
        challenge = challenges[ballot["challenge_id"]]
        choice = ballot["human_choice"]
        if choice not in {"A", "B"}:
            raise RuntimeError("Invalid frozen canonical human choice")
        left = 1 if ballot["canonical_a_displayed_left"] else 0

        x = {
            RAW_ID: power_delta(challenge, 1.0),
            V3_REF_ID: power_delta(challenge, 2.15),
        }
        for candidate in invariant_passing:
            x[candidate["id"]] = v4_delta(challenge, candidate)

        rows.append(
            {
                "ordinal": int(ballot["ordinal"]),
                "voter_cluster": ballot["voter_cluster"],
                "challenge_id": ballot["challenge_id"],
                "topology": challenge["topology"],
                "asset_mix": challenge["asset_mix"],
                "weight": float(ballot["frozen_ballot_weight"]),
                "left": left,
                "y": 1 if choice == "A" else 0,
                "x": x,
            }
        )

    if len(rows) != 428:
        raise RuntimeError("Eligible row construction drift")

    model_ids = [RAW_ID, V3_REF_ID] + [c["id"] for c in invariant_passing]
    predictions, fold_metrics, combined, fold_voter_counts = evaluate_models(
        rows, model_ids
    )

    raw_loss = combined[RAW_ID]
    v3_ref_loss = combined[V3_REF_ID]
    gates_cfg = plan["development_nomination_gates"]

    candidate_results = {}
    eligible_candidates = []

    groups = sorted({
        (row["topology"], row["asset_mix"])
        for row in rows
    })
    if len(groups) != 12:
        raise RuntimeError(f"Expected all 12 topology×asset-mix groups, got {len(groups)}")

    for candidate in invariant_passing:
        cid = candidate["id"]
        candidate_loss = combined[cid]

        positive_folds = sum(
            1
            for cand_fold, raw_fold in zip(fold_metrics[cid], fold_metrics[RAW_ID])
            if cand_fold["held_out_log_loss"] + EPS < raw_fold["held_out_log_loss"]
        )

        group_rows = []
        max_regression = -float("inf")
        for topology, asset_mix in groups:
            subset = [
                row for row in rows
                if row["topology"] == topology and row["asset_mix"] == asset_mix
            ]
            wsum = sum(row["weight"] for row in subset)
            raw_group = sum(
                row["weight"] * predictions[RAW_ID][row["ordinal"]]
                for row in subset
            ) / wsum
            cand_group = sum(
                row["weight"] * predictions[cid][row["ordinal"]]
                for row in subset
            ) / wsum
            regression = cand_group - raw_group
            max_regression = max(max_regression, regression)
            group_rows.append({
                "topology": topology,
                "asset_mix": asset_mix,
                "effective_weight": round(wsum, 9),
                "raw_log_loss": round(raw_group, 12),
                "candidate_log_loss": round(cand_group, 12),
                "regression_candidate_minus_raw": round(regression, 12),
            })

        gate_beat_raw = candidate_loss + EPS < raw_loss
        gate_beat_v3 = candidate_loss + EPS < v3_ref_loss
        gate_positive_folds = (
            positive_folds >= gates_cfg["minimum_positive_folds_vs_raw"]
        )
        gate_group = (
            max_regression
            <= gates_cfg["maximum_topology_x_asset_mix_regression_vs_raw"] + EPS
        )

        eligible = (
            gate_beat_raw
            and gate_beat_v3
            and gate_positive_folds
            and gate_group
        )

        candidate_results[cid] = {
            "parameters": {
                "stud_strength": candidate["stud_strength"],
                "second_piece_discount": candidate["second_piece_discount"],
                "third_plus_discount": candidate["third_plus_discount"],
            },
            "hard_invariants": invariant_results[cid],
            "mean_held_out_log_loss": round(candidate_loss, 12),
            "improvement_vs_raw": round(raw_loss - candidate_loss, 12),
            "improvement_vs_v3_reference": round(v3_ref_loss - candidate_loss, 12),
            "positive_folds_vs_raw": positive_folds,
            "maximum_topology_x_asset_mix_regression_vs_raw": round(
                max_regression, 12
            ),
            "topology_x_asset_mix": group_rows,
            "gates": {
                "beat_raw_control": gate_beat_raw,
                "beat_v3_g2_15_reference": gate_beat_v3,
                "minimum_positive_folds_vs_raw": gate_positive_folds,
                "maximum_group_regression_vs_raw": gate_group,
            },
            "eligible_for_freeze": eligible,
            "folds": fold_metrics[cid],
        }
        if eligible:
            eligible_candidates.append(candidate)

    eligible_candidates.sort(
        key=lambda c: (combined[c["id"]], c["id"])
    )

    frozen_family = []
    if eligible_candidates:
        frozen_family.append(eligible_candidates[0])
        if len(eligible_candidates) >= 2:
            best = eligible_candidates[0]["id"]
            runner = eligible_candidates[1]["id"]
            gap = combined[runner] - combined[best]
            if gap <= plan["near_tie_rule"]["threshold_mean_log_loss"] + EPS:
                frozen_family.append(eligible_candidates[1])

    if len(frozen_family) > 2:
        raise RuntimeError("V4 frozen family exceeded preregistered maximum of two")

    if frozen_family:
        status = "V4_DEVELOPMENT_CANDIDATE_FAMILY_FROZEN_FOR_FRESH_CONFIRMATION"
        next_action = (
            "Generate a new unreleased V4 fresh-confirmation catalog under the "
            "Phase 1 frozen contract. The spent V3 ballots cannot count."
        )
    else:
        status = "V4_DEVELOPMENT_CLOSED_NO_CANDIDATE"
        next_action = (
            "Close V4 without fresh voting. Do not retune the frozen grid against "
            "the same spent V3 outcomes."
        )

    generated = datetime.now(timezone.utc).isoformat()

    result = {
        "schema_version": 1,
        "study_id": "package-adjustment-v4-elite-fragmentation",
        "phase": 2,
        "status": status,
        "generated_at_utc": generated,
        "research_only": True,
        "production_change_authorized": False,
        "production_revision_unchanged": "v1.6-v5-size2-composition-overlay",
        "spent_evidence_filter": {
            "source_frozen_ballots": 600,
            "eligibility_applied_before_outcome_interpretation": True,
            "eligible_ballots": len(rows),
            "excluded_ballots": len(excluded_ballots),
            "eligible_distinct_voters": len({r["voter_cluster"] for r in rows}),
            "eligible_distinct_challenges": len({r["challenge_id"] for r in rows}),
            "excluded_distinct_challenges": len({
                b["challenge_id"] for b in excluded_ballots
            }),
            "exclusion_reason_ballot_counts": dict(
                sorted(exclusion_reason_ballots.items())
            ),
            "joe_mixon_or_invalid_pick_rows_are_not_used_for_model_selection": True,
            "original_frozen_ballot_weights_retained": True,
            "no_reweighting_after_filter": True,
        },
        "controls": {
            RAW_ID: {
                "mean_held_out_log_loss": round(raw_loss, 12),
                "folds": fold_metrics[RAW_ID],
            },
            V3_REF_ID: {
                "mean_held_out_log_loss": round(v3_ref_loss, 12),
                "folds": fold_metrics[V3_REF_ID],
            },
        },
        "hard_invariant_candidate_count": len(invariant_passing),
        "candidate_results": candidate_results,
        "eligible_candidate_ids_ranked": [c["id"] for c in eligible_candidates],
        "frozen_confirmation_family_ids": [c["id"] for c in frozen_family],
        "frozen_confirmation_family_count": len(frozen_family),
        "fresh_confirmation_required": bool(frozen_family),
        "spent_v3_votes_may_count_as_fresh_confirmation": False,
        "continuous_parameter_optimization_performed": False,
        "gamma_tuning_performed": False,
        "fold_voter_counts": fold_voter_counts,
        "next_action": next_action,
    }

    RESULT_OUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if frozen_family:
        frozen_candidate = {
            "schema_version": 1,
            "status": "FROZEN_V4_CONFIRMATION_FAMILY",
            "study_id": "package-adjustment-v4-elite-fragmentation",
            "phase": 2,
            "frozen": True,
            "research_only": True,
            "production_change_authorized": False,
            "production_revision_retained": "v1.6-v5-size2-composition-overlay",
            "frozen_at_utc": generated,
            "candidate_family": [
                {
                    "id": c["id"],
                    "stud_strength": c["stud_strength"],
                    "second_piece_discount": c["second_piece_discount"],
                    "third_plus_discount": c["third_plus_discount"],
                    "development_mean_held_out_log_loss": round(
                        combined[c["id"]], 12
                    ),
                }
                for c in frozen_family
            ],
            "family_count": len(frozen_family),
            "fresh_confirmation_required": True,
            "fresh_vote_namespace_reserved": "__pkgv4c1__",
            "v3_spent_votes_count_for_confirmation": False,
            "asset_eligibility": prereg["asset_eligibility"],
            "next_action": (
                "Generate the fresh V4 confirmation catalog from this frozen family."
            ),
        }
        CANDIDATE_OUT.write_text(
            json.dumps(frozen_candidate, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    best_any = min(
        invariant_passing,
        key=lambda c: (combined[c["id"]], c["id"]),
    )
    best_any_result = candidate_results[best_any["id"]]

    summary_lines = [
        "# Package Adjustment V4 — Phase 2 Spent-Evidence Development",
        "",
        f"**Status:** `{status}`",
        "",
        "## Evidence eligibility",
        "",
        "- V3 spent source ballots: **600**",
        f"- V4-eligible development ballots: **{len(rows)}**",
        f"- Excluded by frozen V4 asset rules: **{len(excluded_ballots)}**",
        f"- Eligible voter clusters: **{len({r['voter_cluster'] for r in rows})} / 30**",
        f"- Eligible distinct challenges: **{len({r['challenge_id'] for r in rows})}**",
        "",
        "Joe Mixon and 2029+ draft-pick challenges were excluded before eligible "
        "ballot outcomes were used for model development.",
        "",
        "## Controls",
        "",
        f"- Raw additive control: **{raw_loss:.6f}**",
        f"- V3 g2.15 reference: **{v3_ref_loss:.6f}**",
        "",
        "## Best V4 structure by held-out log loss",
        "",
        f"- Candidate: **`{best_any['id']}`**",
        f"- Held-out log loss: **{combined[best_any['id']]:.6f}**",
        f"- Improvement vs raw: **{raw_loss - combined[best_any['id']]:.6f}**",
        f"- Improvement vs V3 reference: **{v3_ref_loss - combined[best_any['id']]:.6f}**",
        f"- Positive folds vs raw: **{best_any_result['positive_folds_vs_raw']} / 5**",
        f"- Max topology×asset-mix regression: **{best_any_result['maximum_topology_x_asset_mix_regression_vs_raw']:.6f}**",
        "",
        "## Frozen fresh-confirmation family",
        "",
    ]
    if frozen_family:
        for c in frozen_family:
            summary_lines.append(
                f"- `{c['id']}` — development log loss "
                f"**{combined[c['id']]:.6f}**"
            )
    else:
        summary_lines.append("- **None.** No candidate passed every frozen development gate.")

    summary_lines += [
        "",
        "No production formula changed. These spent V3 votes cannot count toward "
        "V4 confirmation.",
        "",
        next_action,
        "",
    ]
    SUMMARY_OUT.write_text("\n".join(summary_lines), encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "status": "package_adjustment_v4_phase2_development_manifest",
        "generated_at_utc": generated,
        "research_only": True,
        "production_change_authorized": False,
        "production_revision_retained": "v1.6-v5-size2-composition-overlay",
        "source_artifacts": {
            "phase1_preregistration": {
                "path": str(PREREG.relative_to(ROOT)),
                "git_blob_sha": "ac8e35c0104d95ea080897a460506cafa4a33203",
                "sha256": sha256_file(PREREG),
            },
            "phase1_manifest": {
                "path": str(PHASE1_MANIFEST.relative_to(ROOT)),
                "git_blob_sha": "37fff17e89237aad3e40539a4835b5eaf5163781",
                "sha256": sha256_file(PHASE1_MANIFEST),
            },
            "v3_catalog": {
                "path": str(CATALOG.relative_to(ROOT)),
                "git_blob_sha": "3d4615e590697341ee8c27785d8b22e16b82ac44",
                "sha256": sha256_file(CATALOG),
            },
            "v3_exact_600": {
                "path": str(FROZEN.relative_to(ROOT)),
                "git_blob_sha": "bf4779cadbfefdb694c1d028d876b2bad819ee88",
                "sha256": sha256_file(FROZEN),
            },
        },
        "development_status": status,
        "eligible_development_ballots": len(rows),
        "excluded_development_ballots": len(excluded_ballots),
        "frozen_confirmation_family_ids": [c["id"] for c in frozen_family],
        "frozen_confirmation_family_count": len(frozen_family),
        "fresh_confirmation_authorized": bool(frozen_family),
        "continuous_parameter_optimization_performed": False,
        "gamma_tuning_performed": False,
        "outputs": {
            "results": {
                "path": str(RESULT_OUT.relative_to(ROOT)),
                "sha256": sha256_file(RESULT_OUT),
            },
            "summary": {
                "path": str(SUMMARY_OUT.relative_to(ROOT)),
                "sha256": sha256_file(SUMMARY_OUT),
            },
            "frozen_candidate": (
                {
                    "path": str(CANDIDATE_OUT.relative_to(ROOT)),
                    "sha256": sha256_file(CANDIDATE_OUT),
                }
                if CANDIDATE_OUT.exists()
                else None
            ),
        },
        "next_action": next_action,
    }
    MANIFEST_OUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(SUMMARY_OUT.read_text(encoding="utf-8"))

    env_path = os.environ.get("GITHUB_ENV")
    if env_path:
        with open(env_path, "a", encoding="utf-8") as fh:
            fh.write(f"V4_PHASE2_STATUS={status}\n")
            fh.write(
                "V4_PHASE2_FROZEN_FAMILY_COUNT="
                f"{len(frozen_family)}\n"
            )

    print(SUMMARY_OUT.read_text(encoding="utf-8"))
    print("V4_PHASE2_STATUS=" + status)
    print("V4_PHASE2_FROZEN_FAMILY_COUNT=" + str(len(frozen_family)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        main()

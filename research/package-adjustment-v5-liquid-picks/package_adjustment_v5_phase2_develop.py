#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
from datetime import datetime, timezone
from pathlib import Path

import scipy
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[2]
V5 = ROOT / "research" / "package-adjustment-v5-liquid-picks"
V4 = ROOT / "research" / "package-adjustment-v4-elite-fragmentation"

P1 = V5 / "phase1_structural_preregistration.json"
P1A = V5 / "phase1a_predevelopment_clarification.json"
P1B = V5 / "phase1b_predevelopment_architecture_correction.json"
CATALOG = V4 / "phase3b_confirmation_catalog.json"
FROZEN = V4 / "phase3_exact_600_frozen.json"
FREEZE_MANIFEST = V4 / "phase3_exact_600_freeze_manifest.json"
V4_EVAL = V4 / "phase3_confirmation_evaluation.json"
V4_CLOSEOUT = V4 / "package_adjustment_v4_research_closeout.json"

RESULT_OUT = V5 / "phase2_development_results.json"
MANIFEST_OUT = V5 / "phase2_manifest.json"
REPORT_OUT = V5 / "phase2_development.md"
FROZEN_CANDIDATE_OUT = V5 / "frozen_candidate.json"
CLOSEOUT_OUT = V5 / "phase2_closeout.json"

RAW_ID = "raw-additive-control-g1.00"
V4_ID = "v4-selected-elite-frag-s75-p210-p330"
FOLD_COUNT = 5
FOLD_SEED = "package-adjustment-v4-phase3f-fold-v1"
EPS = 1e-12
AUDIT_SEED = 2026092007

EXPECTED_BLOBS = {
    "phase1": "97f4da97d35594c658ce7252fb5a0bf0e7a2a188",
    "phase1a": "e7ba03b32256137a7c3f9bd3a0131ebe0b99a687",
    "phase1b": "0bd740f1ca877d3dd477d4880f893f96922d2500",
    "catalog": "0c974cd5d6a66c410f91775ba34fa068cc79f408",
    "frozen": "91d5d563aaf22382c7b740ca2d1caa4be9037f36",
    "freeze_manifest": "204bb2e8523ef1f388b740f8c942bc5d54bc76c4",
    "v4_eval": "dc293d2e21b1f15e32ded441d64e29e544774251",
    "v4_closeout": "34ee736d4f0a47db2afaa14cc2b0b95cc428a874",
}
EXPECTED_FROZEN_SHA256 = "0027bd94719f4716d1c80b6578a9b5b0c9f779e762ef3e33f3861992158c706b"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def canonical_hash(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
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


def is_pick(asset: dict) -> bool:
    return str(asset.get("kind") or "").lower() == "pick"


def raw_delta(challenge: dict) -> float:
    a = sum(float(x["fv"]) for x in challenge["side_a"])
    b = sum(float(x["fv"]) for x in challenge["side_b"])
    return (a - b) / (a + b)


def v4_side_score(side: list[dict]) -> float:
    vals = sorted((float(x["fv"]) for x in side), reverse=True)
    v1 = vals[0]
    v2 = vals[1] if len(vals) >= 2 else 0.0
    tail = sum(vals[2:]) if len(vals) >= 3 else 0.0
    total = sum(vals)
    elite = min(1.0, max(0.0, v1 / 10000.0))
    score = total + elite * (0.75 * v1 - 0.10 * v2 - 0.30 * tail)
    if not math.isfinite(score) or score <= 0:
        raise RuntimeError("invalid V4 side score")
    return score


def v4_delta(challenge: dict) -> float:
    a = v4_side_score(challenge["side_a"])
    b = v4_side_score(challenge["side_b"])
    return (a - b) / (abs(a) + abs(b))


def v5_side_score(side: list[dict], lam: float) -> float:
    vals = sorted((float(x["fv"]) for x in side), reverse=True)
    v1 = vals[0]
    v2 = vals[1] if len(vals) >= 2 else 0.0
    tail = sum(vals[2:]) if len(vals) >= 3 else 0.0
    total = sum(vals)
    pick_sum = sum(float(x["fv"]) for x in side if is_pick(x))
    elite = min(1.0, max(0.0, v1 / 10000.0))
    score = (
        total
        + elite * (0.75 * v1 - 0.10 * v2 - 0.30 * tail)
        + float(lam) * elite * pick_sum
    )
    if not math.isfinite(score) or score <= 0:
        raise RuntimeError("invalid V5 side score")
    return score


def v5_delta(challenge: dict, lam: float) -> float:
    if len(challenge["side_a"]) == 1 and len(challenge["side_b"]) == 1:
        return raw_delta(challenge)
    a = v5_side_score(challenge["side_a"], lam)
    b = v5_side_score(challenge["side_b"], lam)
    return (a - b) / (abs(a) + abs(b))


def reference_v5_side_score(side: list[dict], lam: float) -> float:
    pairs = sorted(
        [(float(x["fv"]), is_pick(x)) for x in side],
        reverse=True,
    )
    top = pairs[0][0]
    second = pairs[1][0] if len(pairs) >= 2 else 0.0
    tail = sum(v for v, _ in pairs[2:])
    total = sum(v for v, _ in pairs)
    picks = sum(v for v, p in pairs if p)
    elite = max(0.0, min(1.0, top / 10000.0))
    return total + elite * (0.75 * top - 0.10 * second - 0.30 * tail) + lam * elite * picks


def deterministic_fold_map(voters):
    ordered = sorted(
        voters,
        key=lambda v: hashlib.sha256(f"{FOLD_SEED}|{v}".encode()).hexdigest(),
    )
    if len(ordered) != 31:
        raise RuntimeError(f"expected 31 voters, got {len(ordered)}")
    mapping = {v: i % FOLD_COUNT for i, v in enumerate(ordered)}
    counts = {i: 0 for i in range(FOLD_COUNT)}
    for fold in mapping.values():
        counts[fold] += 1
    if sorted(counts.values()) != [6, 6, 6, 6, 7]:
        raise RuntimeError(f"unexpected fold counts {counts}")
    return mapping, counts


def fit_calibration(rows, model_id):
    total_weight = sum(r["weight"] for r in rows)

    def objective(theta):
        log_beta, delta_left = float(theta[0]), float(theta[1])
        beta = math.exp(log_beta)
        loss = g0 = g1 = 0.0
        for r in rows:
            z = beta * r["x"][model_id] + delta_left * r["left"]
            p = sigmoid(z)
            residual = p - r["y"]
            w = r["weight"]
            loss += w * logloss_one(r["y"], p)
            g0 += w * residual * beta * r["x"][model_id]
            g1 += w * residual * r["left"]
        return loss / total_weight, [g0 / total_weight, g1 / total_weight]

    fit = minimize(
        fun=lambda t: objective(t)[0],
        x0=[0.0, 0.0],
        jac=lambda t: objective(t)[1],
        method="L-BFGS-B",
        options={"maxiter": 2000, "ftol": 1e-14, "gtol": 1e-10, "maxls": 50},
    )
    if not fit.success:
        raise RuntimeError(f"calibration failed for {model_id}: {fit.message}")
    beta = math.exp(float(fit.x[0]))
    delta_left = float(fit.x[1])
    if not math.isfinite(beta) or beta <= 0 or not math.isfinite(delta_left):
        raise RuntimeError("invalid calibration")
    return {"beta": beta, "log_beta": float(fit.x[0]), "delta_left": delta_left}


def evaluate_oof(rows, model_ids):
    fmap, fold_counts = deterministic_fold_map({r["voter_cluster"] for r in rows})
    for r in rows:
        r["fold"] = fmap[r["voter_cluster"]]

    predictions = {mid: {} for mid in model_ids}
    folds = {mid: [] for mid in model_ids}

    for fold in range(FOLD_COUNT):
        train = [r for r in rows if r["fold"] != fold]
        test = [r for r in rows if r["fold"] == fold]
        for mid in model_ids:
            params = fit_calibration(train, mid)
            wsum = sum(r["weight"] for r in test)
            loss_sum = 0.0
            for r in test:
                p = sigmoid(params["beta"] * r["x"][mid] + params["delta_left"] * r["left"])
                loss = logloss_one(r["y"], p)
                predictions[mid][r["ordinal"]] = {"loss": loss, "p": p}
                loss_sum += r["weight"] * loss
            folds[mid].append({
                "fold": fold,
                "held_out_log_loss": round(loss_sum / wsum, 12),
                "test_effective_weight": round(wsum, 9),
                "calibration": {
                    "beta": round(params["beta"], 12),
                    "log_beta": round(params["log_beta"], 12),
                    "delta_left": round(params["delta_left"], 12),
                },
            })

    total_weight = sum(r["weight"] for r in rows)
    combined = {}
    for mid in model_ids:
        combined[mid] = sum(
            r["weight"] * predictions[mid][r["ordinal"]]["loss"]
            for r in rows
        ) / total_weight
    return predictions, folds, combined, fold_counts


def validate_contract(read_outcomes=False):
    files = {
        "phase1": P1,
        "phase1a": P1A,
        "phase1b": P1B,
        "catalog": CATALOG,
        "freeze_manifest": FREEZE_MANIFEST,
        "v4_eval": V4_EVAL,
        "v4_closeout": V4_CLOSEOUT,
    }
    if read_outcomes:
        files["frozen"] = FROZEN
    for key, path in files.items():
        if git_blob(path) != EXPECTED_BLOBS[key]:
            raise RuntimeError(f"frozen source drift: {key}")

    p1 = json.loads(P1.read_text())
    p1a = json.loads(P1A.read_text())
    p1b = json.loads(P1B.read_text())
    catalog = json.loads(CATALOG.read_text())
    fm = json.loads(FREEZE_MANIFEST.read_text())
    v4e = json.loads(V4_EVAL.read_text())
    close = json.loads(V4_CLOSEOUT.read_text())

    assert p1["status"] == "FROZEN_BEFORE_SPENT_V4_DEVELOPMENT"
    assert p1a["status"] == "FROZEN_PREDEVELOPMENT_CLARIFICATION"
    assert p1b["status"] == "FROZEN_ALGEBRAIC_CORRECTION_BEFORE_SPENT_EVIDENCE"
    assert p1b["corrected_candidate_grid"]["candidate_count"] == 7
    assert p1b["corrected_candidate_grid"]["pick_liquidity_credit_values"] == [0.05,0.10,0.15,0.20,0.25,0.30,0.40]

    retained = p1b["phase2_development_contract_retained_with_only_candidate_grid_and_formula_superseded"]
    gates = retained["development_nomination_gates"]
    assert gates["minimum_improvement_vs_raw_control"] == 0.005
    assert gates["maximum_overall_log_loss_increase_vs_v4_s75"] == 0.005
    assert gates["minimum_positive_folds_vs_raw"] == 3
    assert gates["maximum_topology_x_asset_mix_regression_vs_raw"] == 0.02
    assert gates["three_v_three_includes_picks_regression_vs_raw_must_be_at_most"] == 0.02
    assert gates["players_only_predictions_must_equal_v4_s75"] is True
    assert retained["near_tie_rule"] == {"maximum_candidates_frozen": 2, "threshold_mean_log_loss": 0.001}

    assert p1a["authoritative_interpretation_for_phase2"]["equivalence_tolerance"] == 1e-12
    assert len(catalog["challenges"]) == 240
    assert fm["checkpoint"]["effective_votes"] == 600
    assert fm["checkpoint"]["distinct_voters"] == 31
    assert fm["checkpoint"]["distinct_challenges"] == 231
    assert fm["checkpoint"]["cells_passing_both_gates"] == 24
    assert v4e["raw_control"]["mean_held_out_log_loss"] == 0.674732487601
    assert v4e["candidate_results"]["elite-frag-s75-p210-p330"]["mean_held_out_log_loss"] == 0.629618180674
    assert close["spent_confirmation_evidence"]["may_not_be_reused_as_fresh_confirmation"] is True

    if read_outcomes:
        if sha256_file(FROZEN) != EXPECTED_FROZEN_SHA256:
            raise RuntimeError("frozen exact-600 sha drift")
        frozen = json.loads(FROZEN.read_text())
        assert len(frozen["ballots"]) == 600
        assert frozen["frozen_effective_votes"] == 600.0
        return p1, p1a, p1b, catalog, fm, v4e, frozen
    return p1, p1a, p1b, catalog, fm, v4e


def random_side(rng, n):
    return [
        {
            "kind": "pick" if rng.random() < 0.35 else "player",
            "fv": rng.uniform(50.0, 10000.0),
        }
        for _ in range(n)
    ]


def invariant_audit(p1b, catalog):
    candidates = p1b["corrected_candidate_grid"]["candidates"]
    rng = random.Random(AUDIT_SEED)
    shapes = [(1,2),(1,3),(2,2),(2,3),(3,3),(3,4),(4,6),(5,6),(6,6),(1,10)]

    for c in candidates:
        lam = float(c["pick_liquidity_credit"])
        for a_n, b_n in shapes:
            for _ in range(200):
                ch = {"side_a": random_side(rng, a_n), "side_b": random_side(rng, b_n)}
                for side in (ch["side_a"], ch["side_b"]):
                    if abs(v5_side_score(side, lam) - reference_v5_side_score(side, lam)) > 1e-10:
                        raise RuntimeError("formula audit mismatch")

                d = v5_delta(ch, lam)
                swapped = {"side_a": ch["side_b"], "side_b": ch["side_a"]}
                if abs(d + v5_delta(swapped, lam)) > 1e-12:
                    raise RuntimeError("side swap failed")

                rev = {"side_a": list(reversed(ch["side_a"])), "side_b": list(reversed(ch["side_b"]))}
                if abs(d - v5_delta(rev, lam)) > 1e-12:
                    raise RuntimeError("order invariance failed")

                side = [dict(x) for x in ch["side_a"]]
                idx = rng.randrange(len(side))
                before = v5_side_score(side, lam)
                side[idx]["fv"] += rng.uniform(0.01, 500.0)
                if v5_side_score(side, lam) + 1e-9 < before:
                    raise RuntimeError("value monotonicity failed")

                base = [dict(x) for x in ch["side_a"]]
                base_score = v5_side_score(base, lam)
                for kind in ("player", "pick"):
                    plus = base + [{"kind": kind, "fv": rng.uniform(0.01, 1500.0)}]
                    if v5_side_score(plus, lam) + 1e-9 < base_score:
                        raise RuntimeError("positive-piece monotonicity failed")

        for ch in catalog["challenges"]:
            if ch["asset_mix"] == "players_only":
                if abs(v5_delta(ch, lam) - v4_delta(ch)) > 1e-12:
                    raise RuntimeError(f"players-only equivalence failed: {c['id']}")

    one = {
        "side_a": [{"kind":"player","fv":9000.0}],
        "side_b": [{"kind":"pick","fv":7000.0}],
    }
    for c in candidates:
        if abs(v5_delta(one, float(c["pick_liquidity_credit"])) - raw_delta(one)) > 1e-12:
            raise RuntimeError("1v1 quiet failed")

    print("PASS V5 invariant audit")


def selftest():
    ch = {
        "side_a":[{"kind":"player","fv":8000.0},{"kind":"pick","fv":2500.0},{"kind":"player","fv":1500.0}],
        "side_b":[{"kind":"player","fv":6500.0},{"kind":"player","fv":4500.0}],
    }
    assert abs(v5_delta(ch, 0.0) - v4_delta(ch)) < 1e-12
    assert v5_side_score(ch["side_a"], 0.20) > v5_side_score(ch["side_a"], 0.0)
    _, counts = deterministic_fold_map({f"v{i:02d}" for i in range(1,32)})
    assert sorted(counts.values()) == [6,6,6,6,7]
    print("Package Adjustment V5 Phase 2 self-test PASS")


def preflight():
    _p1, _p1a, p1b, catalog, _fm, _v4e = validate_contract(False)
    invariant_audit(p1b, catalog)
    print("V5 Phase 2 preflight PASS without reading human outcomes")


def build_rows(frozen, catalog, candidates):
    challenges = {c["id"]: c for c in catalog["challenges"]}
    rows = []
    for b in frozen["ballots"]:
        ch = challenges[b["challenge_id"]]
        x = {RAW_ID: raw_delta(ch), V4_ID: v4_delta(ch)}
        for c in candidates:
            x[c["id"]] = v5_delta(ch, float(c["pick_liquidity_credit"]))
        rows.append({
            "ordinal": int(b["ordinal"]),
            "voter_cluster": b["voter_cluster"],
            "challenge_id": b["challenge_id"],
            "topology": b["topology"],
            "asset_mix": b["asset_mix"],
            "left": 1 if b["canonical_a_displayed_left"] else 0,
            "y": 1 if b["human_choice"] == "A" else 0,
            "weight": float(b["frozen_ballot_weight"]),
            "x": x,
        })
    if len(rows) != 600:
        raise RuntimeError("expected 600 development rows")
    return rows, challenges


def grouped_loss(rows, predictions, model_id, topology, asset_mix):
    subset = [r for r in rows if r["topology"] == topology and r["asset_mix"] == asset_mix]
    w = sum(r["weight"] for r in subset)
    return sum(r["weight"] * predictions[model_id][r["ordinal"]]["loss"] for r in subset) / w, w


def develop():
    for p in (RESULT_OUT, MANIFEST_OUT, REPORT_OUT, FROZEN_CANDIDATE_OUT, CLOSEOUT_OUT):
        if p.exists():
            raise RuntimeError(f"Phase 2 output exists: {p}")

    p1, p1a, p1b, catalog, fm, v4e, frozen = validate_contract(True)
    candidates = [dict(c) for c in p1b["corrected_candidate_grid"]["candidates"]]
    invariant_audit(p1b, catalog)

    rows, challenges = build_rows(frozen, catalog, candidates)
    model_ids = [RAW_ID, V4_ID] + [c["id"] for c in candidates]
    predictions, folds, combined, fold_counts = evaluate_oof(rows, model_ids)

    expected_raw = float(v4e["raw_control"]["mean_held_out_log_loss"])
    expected_v4 = float(v4e["candidate_results"]["elite-frag-s75-p210-p330"]["mean_held_out_log_loss"])
    if abs(combined[RAW_ID] - expected_raw) > 2e-10:
        raise RuntimeError("raw control did not reproduce V4 evaluation")
    if abs(combined[V4_ID] - expected_v4) > 2e-10:
        raise RuntimeError("V4 s75 did not reproduce V4 evaluation")

    retained = p1b["phase2_development_contract_retained_with_only_candidate_grid_and_formula_superseded"]
    gates = retained["development_nomination_gates"]
    eq_tol = float(p1a["authoritative_interpretation_for_phase2"]["equivalence_tolerance"])
    groups = sorted({(r["topology"], r["asset_mix"]) for r in rows})
    if len(groups) != 12:
        raise RuntimeError("expected 12 topology x mix groups")

    results = {}
    passing = []

    for c in candidates:
        cid = c["id"]
        lam = float(c["pick_liquidity_credit"])
        loss = combined[cid]
        improvement = combined[RAW_ID] - loss
        v4_increase = loss - combined[V4_ID]

        positive_folds = sum(
            folds[cid][i]["held_out_log_loss"] < folds[RAW_ID][i]["held_out_log_loss"] - EPS
            for i in range(FOLD_COUNT)
        )

        group_rows = []
        regs = []
        reg_3v3_pick = None
        for topology, mix in groups:
            cand_loss, weight = grouped_loss(rows, predictions, cid, topology, mix)
            raw_loss, _ = grouped_loss(rows, predictions, RAW_ID, topology, mix)
            reg = cand_loss - raw_loss
            regs.append(reg)
            group_rows.append({
                "topology": topology,
                "asset_mix": mix,
                "effective_weight": round(weight, 9),
                "candidate_log_loss": round(cand_loss, 12),
                "raw_control_log_loss": round(raw_loss, 12),
                "regression_candidate_minus_raw": round(reg, 12),
            })
            if topology == "3v3" and mix == "includes_picks":
                reg_3v3_pick = reg

        max_eq = max(
            abs(v5_delta(ch, lam) - v4_delta(ch))
            for ch in challenges.values()
            if ch["asset_mix"] == "players_only"
        )

        gate_improve = improvement + EPS >= gates["minimum_improvement_vs_raw_control"]
        gate_v4 = v4_increase <= gates["maximum_overall_log_loss_increase_vs_v4_s75"] + EPS
        gate_folds = positive_folds >= gates["minimum_positive_folds_vs_raw"]
        max_reg = max(regs)
        gate_groups = max_reg <= gates["maximum_topology_x_asset_mix_regression_vs_raw"] + EPS
        gate_3v3 = reg_3v3_pick <= gates["three_v_three_includes_picks_regression_vs_raw_must_be_at_most"] + EPS
        gate_eq = max_eq <= eq_tol + EPS
        all_pass = all([gate_improve, gate_v4, gate_folds, gate_groups, gate_3v3, gate_eq])

        if all_pass:
            passing.append(cid)

        results[cid] = {
            "pick_liquidity_credit": lam,
            "mean_held_out_log_loss": round(loss, 12),
            "improvement_raw_minus_candidate": round(improvement, 12),
            "log_loss_increase_vs_v4_s75": round(v4_increase, 12),
            "positive_folds_vs_raw": int(positive_folds),
            "folds": folds[cid],
            "topology_x_asset_mix": group_rows,
            "development_nomination_gates": {
                "minimum_improvement_vs_raw_control": 0.005,
                "improvement_gate_pass": gate_improve,
                "maximum_overall_log_loss_increase_vs_v4_s75": 0.005,
                "v4_reference_gate_pass": gate_v4,
                "minimum_positive_folds_vs_raw": 3,
                "positive_folds_gate_pass": gate_folds,
                "maximum_topology_x_asset_mix_regression_vs_raw": 0.02,
                "maximum_observed_topology_x_asset_mix_regression": round(max_reg, 12),
                "topology_x_asset_mix_gate_pass": gate_groups,
                "three_v_three_includes_picks_regression_limit": 0.02,
                "three_v_three_includes_picks_regression": round(reg_3v3_pick, 12),
                "three_v_three_includes_picks_gate_pass": gate_3v3,
                "players_only_structural_equivalence_tolerance": 1e-12,
                "players_only_max_abs_structural_delta_difference_vs_v4_s75": round(max_eq, 15),
                "players_only_equivalence_gate_pass": gate_eq,
                "all_development_nomination_gates_pass": all_pass,
            },
        }

    passing_ranked = sorted(passing, key=lambda cid: (combined[cid], cid))
    frozen_ids = passing_ranked[:1]
    if len(passing_ranked) >= 2:
        gap = combined[passing_ranked[1]] - combined[passing_ranked[0]]
        if gap <= retained["near_tie_rule"]["threshold_mean_log_loss"] + EPS:
            frozen_ids.append(passing_ranked[1])

    now = datetime.now(timezone.utc).isoformat()
    if frozen_ids:
        status = "PASS_V5_PHASE2_FAMILY_FROZEN_FOR_FRESH_CONFIRMATION"
        next_action = "Proceed to fresh V5 signal-feasibility/catalog work. V4 exact-600 remains spent development evidence only."
    else:
        status = "CLOSE_V5_PHASE2_NO_CANDIDATE"
        next_action = "Close V5 without fresh voting. Do not expand the V5 grid against the same spent outcomes."

    result = {
        "schema_version": 1,
        "study_id": "package-adjustment-v5-liquid-picks",
        "phase": 2,
        "status": status,
        "frozen": True,
        "research_only": True,
        "one_time_spent_v4_development_consumed": True,
        "production_change_authorized": False,
        "production_revision_unchanged": "v1.6-v5-size2-composition-overlay",
        "developed_at_utc": now,
        "evidence_role": {
            "dataset": "V4 exact-600 frozen confirmation ballots",
            "effective_votes": 600.0,
            "voter_clusters": 31,
            "distinct_challenges": 231,
            "role_for_v5": "spent development evidence only",
            "may_count_as_v5_fresh_confirmation": False,
        },
        "implementation": {
            "formula": "E = total_FV + elite*(0.75*v1 - 0.10*v2 - 0.30*sum(v3+)) + lambda*elite*sum(pick_FV)",
            "fold_seed": FOLD_SEED,
            "fold_voter_counts": fold_counts,
            "candidate_parameter_tuning_performed": False,
            "candidate_grid_expanded_after_outcomes": False,
            "row_predictions_persisted": False,
            "scipy_version": scipy.__version__,
        },
        "control_reproduction": {
            "raw_control": {
                "mean_held_out_log_loss": round(combined[RAW_ID], 12),
                "committed_v4_value": expected_raw,
                "absolute_difference": round(abs(combined[RAW_ID] - expected_raw), 15),
                "reproduced": True,
            },
            "v4_s75_reference": {
                "mean_held_out_log_loss": round(combined[V4_ID], 12),
                "committed_v4_value": expected_v4,
                "absolute_difference": round(abs(combined[V4_ID] - expected_v4), 15),
                "reproduced": True,
            },
        },
        "raw_control": {
            "id": RAW_ID,
            "mean_held_out_log_loss": round(combined[RAW_ID], 12),
            "folds": folds[RAW_ID],
        },
        "v4_s75_reference": {
            "id": V4_ID,
            "mean_held_out_log_loss": round(combined[V4_ID], 12),
            "folds": folds[V4_ID],
        },
        "candidate_results": results,
        "candidates_passing_all_development_nomination_gates": passing_ranked,
        "frozen_confirmation_family_ids": frozen_ids,
        "near_tie_rule": retained["near_tie_rule"],
        "fresh_confirmation_required": bool(frozen_ids),
        "next_action": next_action,
    }
    RESULT_OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    if frozen_ids:
        by_id = {c["id"]: c for c in candidates}
        frozen_doc = {
            "schema_version": 1,
            "study_id": "package-adjustment-v5-liquid-picks",
            "phase": 2,
            "status": "FROZEN_V5_CONFIRMATION_FAMILY",
            "frozen": True,
            "frozen_at_utc": now,
            "research_only": True,
            "production_change_authorized": False,
            "family_count": len(frozen_ids),
            "candidate_family": [by_id[x] for x in frozen_ids],
            "candidate_family_ids": frozen_ids,
            "candidate_family_fingerprint_sha256": canonical_hash([by_id[x] for x in frozen_ids]),
            "development_evidence_is_spent": True,
            "development_evidence_may_not_confirm_v5": True,
            "fresh_confirmation_required": True,
            "fresh_confirmation_contract": p1b["fresh_confirmation_contract_retained_exactly"],
        }
        FROZEN_CANDIDATE_OUT.write_text(json.dumps(frozen_doc, indent=2, sort_keys=True) + "\n")
    else:
        closeout = {
            "schema_version": 1,
            "study_id": "package-adjustment-v5-liquid-picks",
            "phase": 2,
            "status": "research_closed_no_phase2_candidate",
            "closed": True,
            "closed_at_utc": now,
            "production_change_authorized": False,
            "fresh_v5_voting_authorized": False,
            "candidate_grid_expansion_allowed": False,
            "spent_v4_development_consumed": True,
            "next_action": next_action,
        }
        CLOSEOUT_OUT.write_text(json.dumps(closeout, indent=2, sort_keys=True) + "\n")

    manifest = {
        "schema_version": 1,
        "study_id": "package-adjustment-v5-liquid-picks",
        "phase": 2,
        "status": "FROZEN_V5_PHASE2_DEVELOPMENT_MANIFEST",
        "development_status": status,
        "frozen": True,
        "production_change_authorized": False,
        "one_time_spent_v4_development_consumed": True,
        "source_artifacts": {
            "phase1": {"git_blob_sha": EXPECTED_BLOBS["phase1"], "sha256": sha256_file(P1)},
            "phase1a": {"git_blob_sha": EXPECTED_BLOBS["phase1a"], "sha256": sha256_file(P1A)},
            "phase1b": {"git_blob_sha": EXPECTED_BLOBS["phase1b"], "sha256": sha256_file(P1B)},
            "v4_catalog": {"git_blob_sha": EXPECTED_BLOBS["catalog"], "sha256": sha256_file(CATALOG)},
            "v4_exact_600": {"git_blob_sha": EXPECTED_BLOBS["frozen"], "sha256": sha256_file(FROZEN)},
        },
        "result": {"sha256": sha256_file(RESULT_OUT)},
        "frozen_confirmation_family_ids": frozen_ids,
        "fresh_confirmation_required": bool(frozen_ids),
        "next_action": next_action,
    }
    if frozen_ids:
        manifest["frozen_candidate"] = {"sha256": sha256_file(FROZEN_CANDIDATE_OUT)}
    else:
        manifest["closeout"] = {"sha256": sha256_file(CLOSEOUT_OUT)}
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    report = [
        "# Package Adjustment V5 — Phase 2 Spent-V4 Development",
        "",
        f"**Status:** `{status}`",
        "",
        f"- Raw log loss: **{combined[RAW_ID]:.6f}**",
        f"- V4 s75 log loss: **{combined[V4_ID]:.6f}**",
        "- Passing candidates: **" + (", ".join(f"`{x}`" for x in passing_ranked) if passing_ranked else "none") + "**",
        "- Frozen family: **" + (", ".join(f"`{x}`" for x in frozen_ids) if frozen_ids else "none") + "**",
        "",
        "| Candidate | Log loss | Improvement vs raw | Δ vs V4 | Positive folds | Max group regression | 3v3 picks regression | Gates |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for cid in sorted(results, key=lambda x: results[x]["mean_held_out_log_loss"]):
        r = results[cid]
        g = r["development_nomination_gates"]
        report.append(
            f"| {cid} | {r['mean_held_out_log_loss']:.6f} | "
            f"{r['improvement_raw_minus_candidate']:.6f} | "
            f"{r['log_loss_increase_vs_v4_s75']:.6f} | "
            f"{r['positive_folds_vs_raw']} | "
            f"{g['maximum_observed_topology_x_asset_mix_regression']:.6f} | "
            f"{g['three_v_three_includes_picks_regression']:.6f} | "
            f"{'PASS' if g['all_development_nomination_gates_pass'] else 'FAIL'} |"
        )
    report += ["", next_action, "", "> V4 exact-600 may not count as V5 confirmation.", ""]
    REPORT_OUT.write_text("\n".join(report))

    if os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a") as fh:
            fh.write(f"V5_PHASE2_STATUS={status}\n")
            fh.write("V5_PHASE2_FROZEN_IDS=" + ",".join(frozen_ids) + "\n")

    print("\n".join(report))
    print("V5_PHASE2_STATUS=" + status)
    print("V5_PHASE2_PASSING_COUNT=" + str(len(passing_ranked)))
    print("V5_PHASE2_FROZEN_IDS=" + ",".join(frozen_ids))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--develop", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
    elif args.preflight:
        preflight()
    else:
        develop()

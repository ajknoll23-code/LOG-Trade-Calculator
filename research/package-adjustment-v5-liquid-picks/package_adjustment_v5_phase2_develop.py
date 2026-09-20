#!/usr/bin/env python3
"""Package Adjustment V5 Phase 2 — one-time spent-V4 development."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
V5 = ROOT / "research" / "package-adjustment-v5-liquid-picks"
V4 = ROOT / "research" / "package-adjustment-v4-elite-fragmentation"

PREREG = V5 / "phase1_structural_preregistration.json"
CLAR = V5 / "phase1a_predevelopment_clarification.json"
CORR = V5 / "phase1b_predevelopment_architecture_correction.json"
CATALOG = V4 / "phase3b_confirmation_catalog.json"
FROZEN = V4 / "phase3_exact_600_frozen.json"
V4_EVAL = V4 / "phase3_confirmation_evaluation.json"
V4_CLOSEOUT = V4 / "package_adjustment_v4_research_closeout.json"
V4_CORE = V4 / "package_adjustment_v4_phase3f_evaluate.py"

RESULT = V5 / "phase2_development_results.json"
MANIFEST = V5 / "phase2_manifest.json"
FAMILY = V5 / "frozen_candidate.json"
REPORT = V5 / "phase2_development.md"

RAW = "raw-additive-control-g1.00"
V4S75 = "v4-selected-elite-frag-s75-p210-p330"
EPS = 1e-12

EXPECTED = {
    "prereg": "97f4da97d35594c658ce7252fb5a0bf0e7a2a188",
    "clar": "e7ba03b32256137a7c3f9bd3a0131ebe0b99a687",
    "corr": "0bd740f1ca877d3dd477d4880f893f96922d2500",
    "catalog": "0c974cd5d6a66c410f91775ba34fa068cc79f408",
    "frozen": "91d5d563aaf22382c7b740ca2d1caa4be9037f36",
    "v4_eval": "dc293d2e21b1f15e32ded441d64e29e544774251",
    "v4_closeout": "34ee736d4f0a47db2afaa14cc2b0b95cc428a874",
    "v4_core": "d1541caa59344f3acb841ed5975a560dc27b0b09",
}
FROZEN_SHA = "0027bd94719f4716d1c80b6578a9b5b0c9f779e762ef3e33f3861992158c706b"
V4_RAW_LOSS = 0.674732487601
V4_S75_LOSS = 0.629618180674


def blob(path):
    b = path.read_bytes()
    return hashlib.sha1(f"blob {len(b)}\0".encode() + b).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canon(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_core():
    spec = importlib.util.spec_from_file_location("v4_phase3f_frozen_core", V4_CORE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import frozen V4 evaluator core")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    if mod.FOLD_SEED != "package-adjustment-v4-phase3f-fold-v1":
        raise RuntimeError("V4 fold contract drift")
    return mod


def v4_side(side):
    vals = sorted(float(x["fv"]) for x in side)
    vals.reverse()
    if not vals or any(not math.isfinite(x) or x <= 0 for x in vals):
        raise RuntimeError("invalid asset FV")
    v1 = vals[0]
    v2 = vals[1] if len(vals) > 1 else 0.0
    tail = sum(vals[2:])
    total = sum(vals)
    elite = min(1.0, max(0.0, v1 / 10000.0))
    out = total + elite * (0.75 * v1 - 0.10 * v2 - 0.30 * tail)
    if not math.isfinite(out) or out <= 0:
        raise RuntimeError("invalid V4 side score")
    return out


def delta_from_scores(a, b):
    out = (a - b) / (abs(a) + abs(b))
    if not math.isfinite(out) or not (-1 < out < 1):
        raise RuntimeError("invalid normalized delta")
    return out


def v4_delta(ch):
    return delta_from_scores(v4_side(ch["side_a"]), v4_side(ch["side_b"]))


def v5_side(side, lam):
    base = v4_side(side)
    v1 = max(float(x["fv"]) for x in side)
    elite = min(1.0, max(0.0, v1 / 10000.0))
    picks = sum(
        float(x["fv"]) for x in side
        if str(x.get("kind") or "").lower() == "pick"
    )
    out = base + float(lam) * elite * picks
    if not math.isfinite(out) or out <= 0:
        raise RuntimeError("invalid V5 side score")
    return out


def v5_delta(ch, lam):
    return delta_from_scores(
        v5_side(ch["side_a"], lam),
        v5_side(ch["side_b"], lam),
    )


def validate_sources(read_ballots=False):
    paths = {
        "prereg": PREREG, "clar": CLAR, "corr": CORR,
        "catalog": CATALOG, "v4_eval": V4_EVAL,
        "v4_closeout": V4_CLOSEOUT, "v4_core": V4_CORE,
    }
    if read_ballots:
        paths["frozen"] = FROZEN
    for k, path in paths.items():
        if blob(path) != EXPECTED[k]:
            raise RuntimeError(f"frozen source drift: {k}")

    prereg = json.loads(PREREG.read_text())
    clar = json.loads(CLAR.read_text())
    corr = json.loads(CORR.read_text())
    catalog = json.loads(CATALOG.read_text())
    v4_eval = json.loads(V4_EVAL.read_text())
    closeout = json.loads(V4_CLOSEOUT.read_text())

    assert prereg["status"] == "FROZEN_BEFORE_SPENT_V4_DEVELOPMENT"
    assert clar["status"] == "FROZEN_PREDEVELOPMENT_CLARIFICATION"
    assert corr["status"] == "FROZEN_ALGEBRAIC_CORRECTION_BEFORE_SPENT_EVIDENCE"
    assert corr["corrected_candidate_grid"]["candidate_count"] == 7
    assert corr["corrected_candidate_grid"]["pick_liquidity_credit_values"] == [
        0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40
    ]
    assert corr["governance"]["v4_exact_600_remains_spent_development_evidence_only"] is True
    assert clar["authoritative_interpretation_for_phase2"]["equivalence_tolerance"] == 1e-12

    dev = corr["phase2_development_contract_retained_with_only_candidate_grid_and_formula_superseded"]
    assert dev["development_nomination_gates"] == {
        "maximum_overall_log_loss_increase_vs_v4_s75": 0.005,
        "maximum_topology_x_asset_mix_regression_vs_raw": 0.02,
        "minimum_improvement_vs_raw_control": 0.005,
        "minimum_positive_folds_vs_raw": 3,
        "players_only_predictions_must_equal_v4_s75": True,
        "three_v_three_includes_picks_regression_vs_raw_must_be_at_most": 0.02,
    }
    assert dev["near_tie_rule"] == {
        "maximum_candidates_frozen": 2,
        "threshold_mean_log_loss": 0.001,
    }

    assert len(catalog["challenges"]) == 240
    assert v4_eval["raw_control"]["mean_held_out_log_loss"] == V4_RAW_LOSS
    assert v4_eval["candidate_results"]["elite-frag-s75-p210-p330"]["mean_held_out_log_loss"] == V4_S75_LOSS
    assert closeout["spent_confirmation_evidence"]["may_not_be_reused_as_fresh_confirmation"] is True

    if read_ballots:
        if sha(FROZEN) != FROZEN_SHA:
            raise RuntimeError("V4 exact-600 SHA drift")
        frozen = json.loads(FROZEN.read_text())
        assert frozen["frozen_effective_votes"] == 600.0
        assert frozen["distinct_voter_clusters"] == 31
        assert len(frozen["ballots"]) == 600
        return prereg, clar, corr, catalog, v4_eval, closeout, frozen
    return prereg, clar, corr, catalog, v4_eval, closeout


def stress(candidates):
    rng = random.Random(20260920)
    shapes = [(1,2),(1,3),(2,2),(2,3),(3,3),(3,4),(4,6),(5,6),(6,6),(1,10)]

    def asset():
        return {
            "fv": rng.uniform(50.0, 10000.0),
            "kind": "pick" if rng.random() < 0.35 else "player",
        }

    for c in candidates:
        lam = float(c["pick_liquidity_credit"])
        for na, nb in shapes:
            for _ in range(1000):
                a = [asset() for _ in range(na)]
                b = [asset() for _ in range(nb)]
                ch = {"side_a": a, "side_b": b}
                sw = {"side_a": b, "side_b": a}
                if abs(v5_delta(ch, lam) + v5_delta(sw, lam)) > 1e-12:
                    raise RuntimeError("swap invariant")
                shuffled = list(a)
                rng.shuffle(shuffled)
                if abs(v5_side(a, lam) - v5_side(shuffled, lam)) > 1e-12:
                    raise RuntimeError("order invariant")
                idx = rng.randrange(len(a))
                grown = [dict(x) for x in a]
                grown[idx]["fv"] *= 1.000001
                if v5_side(grown, lam) + 1e-10 < v5_side(a, lam):
                    raise RuntimeError("monotonicity invariant")
                added = [dict(x) for x in a] + [{"fv": rng.uniform(1, 500), "kind": "pick"}]
                if v5_side(added, lam) + 1e-10 < v5_side(a, lam):
                    raise RuntimeError("positive-piece invariant")
                tiny = [dict(x) for x in a] + [{"fv": 1e-6, "kind": "pick"}]
                jump = v5_side(tiny, lam) - v5_side(a, lam)
                if jump < -1e-10 or jump > 1e-3:
                    raise RuntimeError("continuity invariant")

        for _ in range(1000):
            side = [
                {"fv": rng.uniform(50, 10000), "kind": "player"}
                for _ in range(rng.randint(1, 8))
            ]
            if abs(v5_side(side, lam) - v4_side(side)) > 1e-12:
                raise RuntimeError("player-only equivalence")


def selftest():
    candidates = [
        {"id": str(i), "pick_liquidity_credit": x}
        for i, x in enumerate([0.05,0.10,0.15,0.20,0.25,0.30,0.40])
    ]
    stress(candidates)
    print("PASS V5 Phase 2 structural self-test: 70,000 stress cases per frozen contract.")


def preflight():
    _, _, corr, catalog, _, _ = validate_sources(False)
    candidates = corr["corrected_candidate_grid"]["candidates"]
    stress(candidates)
    for ch in catalog["challenges"]:
        if ch["asset_mix"] != "players_only":
            continue
        ref = v4_delta(ch)
        for c in candidates:
            if abs(v5_delta(ch, c["pick_liquidity_credit"]) - ref) > 1e-12:
                raise RuntimeError(f"real-catalog player-only equivalence: {ch['id']}")
    print("PASS V5 Phase 2 outcome-unread preflight.")


def group_losses(rows, preds, model):
    out = {}
    groups = sorted({(r["topology"], r["asset_mix"]) for r in rows})
    if len(groups) != 12:
        raise RuntimeError("expected 12 topology x asset-mix groups")
    for key in groups:
        subset = [r for r in rows if (r["topology"], r["asset_mix"]) == key]
        w = sum(r["weight"] for r in subset)
        out[key] = sum(
            r["weight"] * preds[model][r["ordinal"]]["loss"] for r in subset
        ) / w
    return out


def main():
    for path in (RESULT, MANIFEST, FAMILY, REPORT):
        if path.exists():
            raise RuntimeError(f"Phase 2 output already exists: {path}")

    _, clar, corr, catalog, _, _, frozen = validate_sources(True)
    core = load_core()
    candidates = [dict(x) for x in corr["corrected_candidate_grid"]["candidates"]]
    ids = [x["id"] for x in candidates]
    by_challenge = {x["id"]: x for x in catalog["challenges"]}

    rows = []
    max_equiv = 0.0
    for ballot in frozen["ballots"]:
        ch = by_challenge[ballot["challenge_id"]]
        choice = ballot["human_choice"]
        if choice not in {"A", "B"}:
            raise RuntimeError("invalid spent ballot")
        x = {
            RAW: core.raw_delta(ch),
            V4S75: v4_delta(ch),
        }
        for c in candidates:
            cid = c["id"]
            x[cid] = v5_delta(ch, c["pick_liquidity_credit"])
            if ch["asset_mix"] == "players_only":
                max_equiv = max(max_equiv, abs(x[cid] - x[V4S75]))
        rows.append({
            "ordinal": int(ballot["ordinal"]),
            "voter_cluster": ballot["voter_cluster"],
            "challenge_id": ballot["challenge_id"],
            "topology": ballot["topology"],
            "asset_mix": ballot["asset_mix"],
            "left": 1 if ballot["canonical_a_displayed_left"] else 0,
            "y": 1 if choice == "A" else 0,
            "weight": float(ballot["frozen_ballot_weight"]),
            "x": x,
        })

    assert len(rows) == 600
    assert abs(sum(r["weight"] for r in rows) - 600.0) < 1e-8
    assert len({r["voter_cluster"] for r in rows}) == 31
    assert len({r["challenge_id"] for r in rows}) == 231
    assert max_equiv <= 1e-12

    models = [RAW, V4S75] + ids
    preds, folds, combined, fold_counts = core.evaluate_oof(rows, models)

    if abs(combined[RAW] - V4_RAW_LOSS) > 5e-12:
        raise RuntimeError(f"raw reference mismatch: {combined[RAW]}")
    if abs(combined[V4S75] - V4_S75_LOSS) > 5e-12:
        raise RuntimeError(f"V4 s75 reference mismatch: {combined[V4S75]}")

    dev = corr["phase2_development_contract_retained_with_only_candidate_grid_and_formula_superseded"]
    gates = dev["development_nomination_gates"]
    near = dev["near_tie_rule"]
    raw_groups = group_losses(rows, preds, RAW)

    candidate_results = {}
    for c in candidates:
        cid = c["id"]
        loss = combined[cid]
        improvement = combined[RAW] - loss
        delta_v4 = loss - combined[V4S75]

        positive_folds = sum(
            folds[cid][i]["held_out_log_loss"] + EPS
            < folds[RAW][i]["held_out_log_loss"]
            for i in range(5)
        )

        cg = group_losses(rows, preds, cid)
        group_rows = []
        max_reg = -math.inf
        reg_3v3_picks = None
        for key in sorted(cg):
            reg = cg[key] - raw_groups[key]
            max_reg = max(max_reg, reg)
            if key == ("3v3", "includes_picks"):
                reg_3v3_picks = reg
            group_rows.append({
                "topology": key[0],
                "asset_mix": key[1],
                "candidate_log_loss": round(cg[key], 12),
                "raw_log_loss": round(raw_groups[key], 12),
                "regression_candidate_minus_raw": round(reg, 12),
            })
        if reg_3v3_picks is None:
            raise RuntimeError("missing 3v3/includes_picks group")

        checks = {
            "improvement_vs_raw": {
                "threshold": 0.005,
                "observed": round(improvement, 12),
                "pass": improvement + EPS >= 0.005,
            },
            "increase_vs_v4_s75": {
                "threshold": 0.005,
                "observed": round(delta_v4, 12),
                "pass": delta_v4 <= 0.005 + EPS,
            },
            "positive_folds_vs_raw": {
                "threshold": 3,
                "observed": positive_folds,
                "pass": positive_folds >= 3,
            },
            "max_group_regression_vs_raw": {
                "threshold": 0.02,
                "observed": round(max_reg, 12),
                "pass": max_reg <= 0.02 + EPS,
            },
            "three_v_three_includes_picks_regression_vs_raw": {
                "threshold": 0.02,
                "observed": round(reg_3v3_picks, 12),
                "pass": reg_3v3_picks <= 0.02 + EPS,
            },
            "players_only_structural_equivalence": {
                "threshold": clar["authoritative_interpretation_for_phase2"]["equivalence_tolerance"],
                "observed": round(max_equiv, 15),
                "pass": max_equiv <= 1e-12,
            },
        }

        candidate_results[cid] = {
            "pick_liquidity_credit": c["pick_liquidity_credit"],
            "mean_held_out_log_loss": round(loss, 12),
            "improvement_raw_minus_candidate": round(improvement, 12),
            "increase_candidate_minus_v4_s75": round(delta_v4, 12),
            "positive_folds_vs_raw": positive_folds,
            "max_group_regression_vs_raw": round(max_reg, 12),
            "three_v_three_includes_picks_regression_vs_raw": round(reg_3v3_picks, 12),
            "topology_x_asset_mix": group_rows,
            "nomination_gates": checks,
            "all_nomination_gates_pass": all(x["pass"] for x in checks.values()),
        }

    ranked = sorted(ids, key=lambda cid: (combined[cid], cid))
    passing = [cid for cid in ranked if candidate_results[cid]["all_nomination_gates_pass"]]

    frozen_ids = []
    near_gap = None
    if passing:
        frozen_ids = [passing[0]]
        if len(passing) > 1:
            near_gap = combined[passing[1]] - combined[passing[0]]
            if near_gap <= near["threshold_mean_log_loss"] + EPS:
                frozen_ids.append(passing[1])
    assert len(frozen_ids) <= 2

    status = (
        "PASS_V5_PHASE2_CANDIDATE_FAMILY_FROZEN"
        if frozen_ids else
        "CLOSE_V5_NO_DEVELOPMENT_CANDIDATE"
    )
    now = datetime.now(timezone.utc).isoformat()

    result = {
        "schema_version": 1,
        "study_id": "package-adjustment-v5-liquid-picks",
        "phase": 2,
        "status": status,
        "frozen": True,
        "research_only": True,
        "production_change_authorized": False,
        "fresh_confirmation_authorized": bool(frozen_ids),
        "developed_at_utc": now,
        "source_evidence": {
            "effective_votes": 600.0,
            "voter_clusters": 31,
            "distinct_challenges": 231,
            "v4_exact_600_role": "spent development evidence only",
            "may_count_as_v5_fresh_confirmation": False,
            "dataset_sha256": FROZEN_SHA,
        },
        "reference_reproduction": {
            "raw_control_mean_held_out_log_loss": round(combined[RAW], 12),
            "v4_s75_mean_held_out_log_loss": round(combined[V4S75], 12),
            "matches_committed_v4_evaluation": True,
        },
        "implementation": {
            "candidate_count": 7,
            "candidate_parameter_tuning_performed": False,
            "candidate_grid_expansion_performed": False,
            "cross_validation": "5-fold grouped by frozen voter cluster",
            "fold_seed": core.FOLD_SEED,
            "fold_voter_counts": fold_counts,
            "candidate_specific_calibration_refit_per_training_fold": True,
            "row_predictions_persisted": False,
        },
        "candidate_results": candidate_results,
        "selection": {
            "ranked_all_candidate_ids": ranked,
            "passing_candidate_ids": passing,
            "near_tie_threshold_mean_log_loss": near["threshold_mean_log_loss"],
            "maximum_candidates_frozen": near["maximum_candidates_frozen"],
            "best_vs_second_passing_gap": (
                None if near_gap is None else round(near_gap, 12)
            ),
            "frozen_candidate_ids": frozen_ids,
        },
        "next_action": (
            "Build outcome-blind V5 fresh-confirmation feasibility/catalog work."
            if frozen_ids else
            "Close V5 without fresh voting; do not widen or retune this grid."
        ),
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    frozen_candidates = [
        next(c for c in candidates if c["id"] == cid) for cid in frozen_ids
    ]
    family = {
        "schema_version": 1,
        "study_id": "package-adjustment-v5-liquid-picks",
        "phase": 2,
        "status": (
            "FROZEN_V5_CONFIRMATION_FAMILY"
            if frozen_ids else "NO_V5_CONFIRMATION_FAMILY"
        ),
        "frozen": True,
        "frozen_at_utc": now,
        "research_only": True,
        "production_change_authorized": False,
        "fresh_confirmation_authorized": bool(frozen_ids),
        "family_count": len(frozen_candidates),
        "candidate_family": frozen_candidates,
        "candidate_family_fingerprint_sha256": canon(frozen_candidates),
        "source_development_result_sha256": sha(RESULT),
        "spent_v4_votes_count_for_confirmation": False,
        "candidate_parameter_tuning_after_development": False,
        "next_action": result["next_action"],
    }
    FAMILY.write_text(json.dumps(family, indent=2, sort_keys=True) + "\n")

    manifest = {
        "schema_version": 1,
        "study_id": "package-adjustment-v5-liquid-picks",
        "phase": 2,
        "status": "FROZEN_V5_PHASE2_DEVELOPMENT_MANIFEST",
        "frozen": True,
        "production_change_authorized": False,
        "fresh_confirmation_authorized": bool(frozen_ids),
        "candidate_family_count": len(frozen_candidates),
        "source_blobs": EXPECTED,
        "outputs": {
            "development_results_sha256": sha(RESULT),
            "frozen_candidate_sha256": sha(FAMILY),
        },
        "next_action": result["next_action"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Package Adjustment V5 — Phase 2 Development",
        "",
        f"**Status:** `{status}`",
        "",
        f"- Raw held-out log loss: **{combined[RAW]:.6f}**",
        f"- V4 s75 held-out log loss: **{combined[V4S75]:.6f}**",
        f"- Frozen V5 candidates: **{len(frozen_ids)}**",
        "",
        "| Candidate | λ | Log loss | Improvement vs raw | Δ vs V4 s75 | Max group reg. | 3v3 picks reg. | Gates |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for cid in ranked:
        r = candidate_results[cid]
        lines.append(
            f"| {cid} | {r['pick_liquidity_credit']:.2f} | "
            f"{r['mean_held_out_log_loss']:.6f} | "
            f"{r['improvement_raw_minus_candidate']:.6f} | "
            f"{r['increase_candidate_minus_v4_s75']:.6f} | "
            f"{r['max_group_regression_vs_raw']:.6f} | "
            f"{r['three_v_three_includes_picks_regression_vs_raw']:.6f} | "
            f"{'PASS' if r['all_nomination_gates_pass'] else 'FAIL'} |"
        )
    lines += ["", result["next_action"], ""]
    REPORT.write_text("\n".join(lines))

    print("\n".join(lines))
    print("V5_PHASE2_STATUS=" + status)
    print("V5_PHASE2_FROZEN_IDS=" + (
        ",".join(frozen_ids) if frozen_ids else "NONE"
    ))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--selftest", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--develop", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    elif args.preflight:
        preflight()
    else:
        main()

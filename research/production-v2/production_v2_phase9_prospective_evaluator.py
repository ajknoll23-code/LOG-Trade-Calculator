#!/usr/bin/env python3
"""
Production V2 Phase 9 — prospective 2026 calibration evaluator.

INSTALL NOW, GRADE LATER
------------------------
This evaluator is intentionally created before meaningful 2026 outcomes exist.

On its FIRST successful run it freezes an immutable preseason prediction matrix:
  5 offense FantasyPros weights
x 3 history weights
x 2 replacement-rank families
x 4 affine floors
= 120 V2 variants

It also freezes the currently deployed Fundamental model as the control.

Future Phase-9 runs NEVER rebuild those predictions from current index.html.
They grade the frozen preseason predictions against completed 2026 outcomes
captured by scripts/validation/capture_realized_outcomes.py. This prevents
October/November model edits, role changes, age changes, or source refreshes
from leaking backward into a September preseason backtest.

Existing validation code is reused for:
- exact league scoring target: capture_realized_outcomes.py
- completed-week/leakage rules and metrics: evaluate_model_history.py

PRIMARY CALIBRATION TARGET
--------------------------
effective PROD_MULT vs realized active-game PPG
This isolates the production signal being rebuilt.

SECONDARY GUARDRAILS
--------------------
- Fundamental Value vs future total points
- Fundamental Value vs realized active-game PPG
- position subgroup Spearman
- paired bootstrap vs the frozen deployed model

READINESS
---------
0 weeks: ready / waiting
1-3: collection only
4-7: early diagnostic only
8-11: calibration review eligible
12+: stability review eligible
18: season-complete review

Phase 9 NEVER authorizes production deployment. Phase 10 is a separate,
explicit deployment decision.

OUTPUTS
-------
Immutable once created:
  research/production-v2/production_v2_phase9_preseason_candidates.json

Refreshable:
  research/production-v2/production_v2_phase9_evaluation.json
  research/production-v2/production_v2_phase9_evaluation.md
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import statistics
import sys
from datetime import datetime, timezone
from collections import defaultdict

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"
VALIDATION_DIR = SCRIPTS / "validation"

PHASE1_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase1_audit.json"
PHASE2_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase2_preseason_baseline.json"
PHASE3_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase3_baseline_normalization_audit.json"
PHASE5_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase5_no_history_semantics_audit.json"
PHASE6_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase6_transform_compression_audit.json"
PHASE7_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase7_missing_candidate_fallback_audit.json"
PHASE8_JSON = REPO_ROOT / "research" / "production-v2" / "production_v2_phase8_shadow_model.json"
PHASE8_SCRIPT = REPO_ROOT / "research" / "production-v2" / "production_v2_phase8_shadow_model.py"

INDEX_HTML = REPO_ROOT / "index.html"
SNAPSHOT_VALUES_PATH = VALIDATION_DIR / "snapshot_values.py"
MODEL_EVALUATOR_PATH = VALIDATION_DIR / "evaluate_model_history.py"
OUTCOMES_PATH = REPO_ROOT / "research" / "model-history" / "outcomes" / "2026.json"

FROZEN_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase9_preseason_candidates.json"
OUTPUT_JSON = REPO_ROOT / "research" / "production-v2" / "production_v2_phase9_evaluation.json"
OUTPUT_MD = REPO_ROOT / "research" / "production-v2" / "production_v2_phase9_evaluation.md"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
OFFENSE = {"QB", "RB", "WR", "TE"}

FP_WEIGHTS = (0.00, 0.25, 0.50, 0.75, 1.00)
HISTORY_WEIGHTS = (0.25, 0.45, 0.65)
FLOORS = (0.05, 0.10, 0.15, 0.20)

EXPECTED_TRACKED = 549
EXPECTED_NORMAL = 518
EXPECTED_CONTINUITY = 31
EXPECTED_VARIANTS = 120

REFERENCE_VARIANT = "fp_0.50__history_0.45__evidence_hybrid__floor_0.15"
DEPLOYED_CONTROL = "deployed_current"

BOOTSTRAP_REPS = 300
BOOTSTRAP_SEED = 20260903

PROTOCOL = {
    "protocol_version": "production-v2-phase9-preseason-v1",
    "season": "2026",
    "prediction_freeze": (
        "All candidate predictions are frozen before grading and never rebuilt "
        "from later production state."
    ),
    "completed_week_rules": "reuse scripts/validation/evaluate_model_history.py",
    "primary_target": "effective_prod_mult_vs_realized_active_ppg",
    "secondary_targets": [
        "fundamental_value_vs_future_total_points",
        "fundamental_value_vs_realized_active_ppg",
    ],
    "variant_grid": {
        "fantasypros_weight": list(FP_WEIGHTS),
        "history_weight": list(HISTORY_WEIGHTS),
        "rank_family": ["documented", "evidence_hybrid"],
        "floor": list(FLOORS),
    },
    "readiness": {
        "0": "ready_waiting",
        "1_to_3": "collection_only",
        "4_to_7": "early_diagnostic_only",
        "8_to_11": "calibration_review_eligible",
        "12_to_17": "stability_review_eligible",
        "18": "season_complete_review",
    },
    "deployment_authorized": False,
}
PROTOCOL_SHA256 = hashlib.sha256(
    json.dumps(PROTOCOL, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finite(value):
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def round_numbers(obj, digits=6):
    if isinstance(obj, dict):
        return {k: round_numbers(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_numbers(v, digits) for v in obj]
    if isinstance(obj, float):
        return round(obj, digits) if math.isfinite(obj) else None
    return obj


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path.relative_to(REPO_ROOT)}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def variant_key(fp_weight, history_weight, rank_family, floor):
    return (
        f"fp_{fp_weight:.2f}__history_{history_weight:.2f}__"
        f"{rank_family}__floor_{floor:.2f}"
    )


def offense_forward(rec, fp_weight):
    forward = rec.get("forward") or {}
    fp = finite(forward.get("fantasypros_points"))
    sleeper = finite(forward.get("sleeper_points"))
    if fp is not None and sleeper is not None:
        return fp_weight * fp + (1.0 - fp_weight) * sleeper
    if fp is not None:
        return fp
    if sleeper is not None:
        return sleeper
    return None


def scenario_forward(rec, fp_weight):
    if rec.get("pos") in OFFENSE:
        return offense_forward(rec, fp_weight)
    return finite((rec.get("forward") or {}).get("projection"))


def scenario_players(base_players, fp_weight, history_weight):
    out = {}
    for key, rec in base_players.items():
        row = dict(rec)
        history = finite((rec.get("history") or {}).get("history_component"))
        forward = scenario_forward(rec, fp_weight)

        combined = None
        if rec.get("candidate") is not None:
            if history is None or forward is None:
                raise RuntimeError(
                    f"{key}: Phase-1 candidate exists but scenario inputs are incomplete"
                )
            combined = history_weight * history + (1.0 - history_weight) * forward

        row["phase1_combined_points"] = combined
        out[key] = row
    return out


def validate_preseason_inputs(phase1, phase2, phase3, phase5, phase6, phase7, phase8):
    players = phase1.get("players")
    if not isinstance(players, dict) or len(players) != EXPECTED_TRACKED:
        raise RuntimeError("Phase-1 tracked-player cohort changed")

    normal = sum(1 for r in players.values() if r.get("candidate") is not None)
    if normal != EXPECTED_NORMAL or len(players) - normal != EXPECTED_CONTINUITY:
        raise RuntimeError("Phase-1 normal/continuity cohort changed")

    if phase2.get("status") != "FROZEN_PRESEASON_BASELINE_RESEARCH_ONLY":
        raise RuntimeError("Phase-2A preseason baseline not frozen")
    if phase5.get("decision") != (
        "CARRY_DATA_FIRST_NO_HISTORY_SEMANTICS_FORWARD_FOR_V2_CANDIDATE_COHORT"
    ):
        raise RuntimeError("Phase-5 semantics changed")
    if phase6.get("decision") != (
        "KEEP_TRANSFORM_FLOOR_UNDEPLOYED_PENDING_PROSPECTIVE_CALIBRATION"
    ):
        raise RuntimeError("Phase-6 transform status changed")
    if phase7.get("decision") != (
        "CARRY_CURRENT_VALUE_CONTINUITY_FALLBACK_FOR_MISSING_V2_CANDIDATES"
    ):
        raise RuntimeError("Phase-7 fallback changed")
    if phase8.get("status") != "CONSOLIDATED_SHADOW_MODEL_RESEARCH_ONLY":
        raise RuntimeError("Phase-8 shadow model not complete")

    # Freeze must occur against the exact architecture state Phase 8 used.
    input_hashes = phase8.get("input_sha256") or {}
    expected_index = input_hashes.get("index.html")
    expected_snapshot = input_hashes.get("scripts/validation/snapshot_values.py")
    if expected_index and sha256(INDEX_HTML) != expected_index:
        raise RuntimeError(
            "index.html changed since Phase 8; refusing to create a contaminated "
            "preseason Phase-9 freeze"
        )
    if expected_snapshot and sha256(SNAPSHOT_VALUES_PATH) != expected_snapshot:
        raise RuntimeError(
            "snapshot_values.py changed since Phase 8; refusing Phase-9 freeze"
        )


def freeze_candidates():
    if FROZEN_PATH.exists():
        payload = read_json(FROZEN_PATH)
        validate_frozen(payload)
        print(f"Phase-9 preseason candidate matrix already frozen: {FROZEN_PATH.relative_to(REPO_ROOT)}")
        return payload, False

    phase1 = read_json(PHASE1_PATH)
    phase2 = read_json(PHASE2_PATH)
    phase3 = read_json(PHASE3_PATH)
    phase5 = read_json(PHASE5_PATH)
    phase6 = read_json(PHASE6_PATH)
    phase7 = read_json(PHASE7_PATH)
    phase8_json = read_json(PHASE8_JSON)

    validate_preseason_inputs(
        phase1, phase2, phase3, phase5, phase6, phase7, phase8_json
    )

    phase8 = load_module("production_v2_phase8_shadow_model", PHASE8_SCRIPT)
    snapshot_values = phase8.load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    base_players = phase1["players"]
    normal_keys = sorted(
        key for key, rec in base_players.items() if rec.get("candidate") is not None
    )
    continuity_keys = sorted(
        key for key, rec in base_players.items() if rec.get("candidate") is None
    )

    player_meta = []
    for key in normal_keys:
        rec = base_players[key]
        player_meta.append({
            "key": key,
            "pos": rec["pos"],
            "age": rec["age"],
            "role": rec["role"],
        })

    continuity = []
    for key in continuity_keys:
        rec = base_players[key]
        continuity.append({
            "key": key,
            "pos": rec["pos"],
            "current_value": int(rec["current"]["fundamental_value"]),
        })

    rank_families = {
        "documented": {k: int(v) for k, v in phase3["documented_ranks"].items()},
        "evidence_hybrid": {
            k: int(v) for k, v in phase3["evidence_hybrid_ranks"].items()
        },
    }

    variants = {}
    for fp_weight in FP_WEIGHTS:
        for history_weight in HISTORY_WEIGHTS:
            scenario = scenario_players(
                base_players, fp_weight, history_weight
            )
            for rank_family, ranks in rank_families.items():
                for floor in FLOORS:
                    key = variant_key(
                        fp_weight, history_weight, rank_family, floor
                    )
                    values, baselines = phase8.compute_variant(
                        scenario,
                        ranks,
                        floor,
                        cfg,
                        snapshot_values,
                    )
                    variants[key] = {
                        "fantasypros_weight": fp_weight,
                        "sleeper_weight_when_both": 1.0 - fp_weight,
                        "history_weight": history_weight,
                        "forward_weight": 1.0 - history_weight,
                        "rank_family": rank_family,
                        "floor": floor,
                        "ranks": ranks,
                        "baselines": baselines,
                        "value_vector": [
                            int(values[player]["value"]) for player in normal_keys
                        ],
                        "prod_mult_vector": [
                            float(values[player]["effective_prod_mult"])
                            for player in normal_keys
                        ],
                    }

    if len(variants) != EXPECTED_VARIANTS:
        raise RuntimeError(f"expected {EXPECTED_VARIANTS} variants, got {len(variants)}")
    if REFERENCE_VARIANT not in variants:
        raise RuntimeError("reference variant missing from freeze")

    deployed_value_vector = []
    deployed_pm_vector = []
    for key in normal_keys:
        current = base_players[key]["current"]
        deployed_value_vector.append(int(current["fundamental_value"]))
        deployed_pm_vector.append(float(current["effective_prod_mult"]))

    payload = round_numbers({
        "schema_version": 1,
        "phase": "Production V2 Phase 9",
        "artifact": "immutable_preseason_candidate_matrix",
        "protocol": PROTOCOL,
        "protocol_sha256": PROTOCOL_SHA256,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": "2026",
        "normal_player_count": len(normal_keys),
        "continuity_player_count": len(continuity_keys),
        "variant_count": len(variants),
        "reference_variant": REFERENCE_VARIANT,
        "normal_players": player_meta,
        "continuity_players": continuity,
        "deployed_control": {
            "key": DEPLOYED_CONTROL,
            "value_vector": deployed_value_vector,
            "prod_mult_vector": deployed_pm_vector,
        },
        "variants": variants,
        "source_sha256": {
            str(PHASE1_PATH.relative_to(REPO_ROOT)): sha256(PHASE1_PATH),
            str(PHASE2_PATH.relative_to(REPO_ROOT)): sha256(PHASE2_PATH),
            str(PHASE3_PATH.relative_to(REPO_ROOT)): sha256(PHASE3_PATH),
            str(PHASE5_PATH.relative_to(REPO_ROOT)): sha256(PHASE5_PATH),
            str(PHASE6_PATH.relative_to(REPO_ROOT)): sha256(PHASE6_PATH),
            str(PHASE7_PATH.relative_to(REPO_ROOT)): sha256(PHASE7_PATH),
            str(PHASE8_JSON.relative_to(REPO_ROOT)): sha256(PHASE8_JSON),
            str(PHASE8_SCRIPT.relative_to(REPO_ROOT)): sha256(PHASE8_SCRIPT),
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
            str(SNAPSHOT_VALUES_PATH.relative_to(REPO_ROOT)): sha256(SNAPSHOT_VALUES_PATH),
        },
    })
    validate_frozen(payload)
    FROZEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    FROZEN_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Frozen Phase-9 preseason matrix: {len(normal_keys)} normal players, "
        f"{len(continuity_keys)} continuity players, {len(variants)} variants"
    )
    return payload, True


def validate_frozen(payload):
    if payload.get("schema_version") != 1:
        raise RuntimeError("unexpected Phase-9 freeze schema")
    if payload.get("protocol_sha256") != PROTOCOL_SHA256:
        raise RuntimeError("Phase-9 protocol hash mismatch")
    if payload.get("normal_player_count") != EXPECTED_NORMAL:
        raise RuntimeError("Phase-9 normal player count mismatch")
    if payload.get("continuity_player_count") != EXPECTED_CONTINUITY:
        raise RuntimeError("Phase-9 continuity count mismatch")
    if payload.get("variant_count") != EXPECTED_VARIANTS:
        raise RuntimeError("Phase-9 variant count mismatch")
    players = payload.get("normal_players")
    variants = payload.get("variants")
    if not isinstance(players, list) or len(players) != EXPECTED_NORMAL:
        raise RuntimeError("Phase-9 normal player metadata invalid")
    if not isinstance(variants, dict) or len(variants) != EXPECTED_VARIANTS:
        raise RuntimeError("Phase-9 variants invalid")
    for key, row in variants.items():
        if len(row.get("value_vector") or []) != EXPECTED_NORMAL:
            raise RuntimeError(f"{key}: value vector length mismatch")
        if len(row.get("prod_mult_vector") or []) != EXPECTED_NORMAL:
            raise RuntimeError(f"{key}: PM vector length mismatch")
    control = payload.get("deployed_control") or {}
    if len(control.get("value_vector") or []) != EXPECTED_NORMAL:
        raise RuntimeError("deployed control value vector mismatch")
    if len(control.get("prod_mult_vector") or []) != EXPECTED_NORMAL:
        raise RuntimeError("deployed control PM vector mismatch")
    if payload.get("reference_variant") not in variants:
        raise RuntimeError("Phase-9 reference variant missing")


def completed_prefix(completed_weeks):
    completed = set(int(w) for w in completed_weeks)
    out = []
    week = 1
    while week in completed and week <= 18:
        out.append(week)
        week += 1
    return out


def aggregate_outcomes(outcomes, weeks, model_keys):
    wanted = set(model_keys)
    total = {k: 0.0 for k in model_keys}
    active = {k: 0 for k in model_keys}

    week_map = outcomes.get("weeks") or {}
    for week in weeks:
        block = week_map.get(str(week)) or {}
        for row in block.get("players") or []:
            points = finite(row.get("fantasy_points"))
            if points is None:
                continue
            for key in row.get("model_keys") or []:
                if key in wanted:
                    total[key] += points
                    active[key] += 1

    return {
        key: {
            "total_points": round(total[key], 6),
            "active_games": active[key],
            "active_ppg": (
                round(total[key] / active[key], 6) if active[key] else None
            ),
        }
        for key in model_keys
    }


def window_specs(prefix):
    n = len(prefix)
    if n == 0:
        return []
    specs = []
    if n < 4:
        specs.append((f"weeks_1_to_{n}_early", list(range(1, n + 1))))
        return specs

    specs.append(("weeks_1_to_4", [1, 2, 3, 4]))
    if n >= 8:
        specs.append(("weeks_5_to_8", [5, 6, 7, 8]))
        specs.append(("weeks_1_to_8", list(range(1, 9))))
    if n >= 12:
        specs.append(("weeks_9_to_12", [9, 10, 11, 12]))
        specs.append(("weeks_1_to_12", list(range(1, 13))))
    if n > 12:
        specs.append((f"weeks_1_to_{n}", list(range(1, n + 1))))
    return specs


def score_prediction(evaluator, names, positions, values, pms, realized):
    total_names = []
    total_pred_values = []
    total_outcomes = []

    active_names = []
    active_pred_values = []
    active_pred_pms = []
    active_outcomes = []

    by_position = defaultdict(lambda: {
        "names": [], "pms": [], "ppg": []
    })

    for i, key in enumerate(names):
        row = realized[key]
        total_names.append(key)
        total_pred_values.append(float(values[i]))
        total_outcomes.append(float(row["total_points"]))

        if row["active_games"] > 0:
            ppg = float(row["active_ppg"])
            active_names.append(key)
            active_pred_values.append(float(values[i]))
            active_pred_pms.append(float(pms[i]))
            active_outcomes.append(ppg)

            pos = positions[i]
            by_position[pos]["names"].append(key)
            by_position[pos]["pms"].append(float(pms[i]))
            by_position[pos]["ppg"].append(ppg)

    primary = evaluator.metric_bundle(
        active_names, active_pred_pms, active_outcomes, include_top_n=False
    )
    secondary_total = evaluator.metric_bundle(
        total_names, total_pred_values, total_outcomes, include_top_n=True
    )
    secondary_active = evaluator.metric_bundle(
        active_names, active_pred_values, active_outcomes, include_top_n=False
    )

    position_primary = {}
    for pos in TRACKED_POSITIONS:
        g = by_position[pos]
        position_primary[pos] = evaluator.metric_bundle(
            g["names"], g["pms"], g["ppg"], include_top_n=False
        )

    return {
        "primary_prod_mult_vs_active_ppg": primary,
        "secondary_value_vs_total_points": secondary_total,
        "secondary_value_vs_active_ppg": secondary_active,
        "primary_by_position": position_primary,
    }


def rank_scoreboard(scoreboard):
    def sort_key(item):
        key, row = item
        m = row["primary_prod_mult_vs_active_ppg"]
        sp = m.get("spearman")
        pair = m.get("pairwise_ordering_accuracy")
        mae = m.get("minmax_normalized_mae")
        return (
            -(sp if sp is not None else -999),
            -(pair if pair is not None else -999),
            (mae if mae is not None else 999),
            key,
        )
    return [key for key, _ in sorted(scoreboard.items(), key=sort_key)]


def parameter_profiles(scoreboard, frozen):
    profiles = {
        "fantasypros_weight": defaultdict(list),
        "history_weight": defaultdict(list),
        "rank_family": defaultdict(list),
        "floor": defaultdict(list),
    }

    for key, metrics in scoreboard.items():
        if key == DEPLOYED_CONTROL:
            continue
        sp = (
            metrics.get("primary_prod_mult_vs_active_ppg") or {}
        ).get("spearman")
        if sp is None:
            continue
        v = frozen["variants"][key]
        profiles["fantasypros_weight"][f"{v['fantasypros_weight']:.2f}"].append(sp)
        profiles["history_weight"][f"{v['history_weight']:.2f}"].append(sp)
        profiles["rank_family"][v["rank_family"]].append(sp)
        profiles["floor"][f"{v['floor']:.2f}"].append(sp)

    out = {}
    for param, groups in profiles.items():
        out[param] = {}
        for level, vals in sorted(groups.items()):
            out[param][level] = {
                "variant_count": len(vals),
                "median_primary_spearman": (
                    round(statistics.median(vals), 6) if vals else None
                ),
                "max_primary_spearman": (
                    round(max(vals), 6) if vals else None
                ),
            }
    return out


def paired_bootstrap(evaluator, frozen, realized, candidate_key, reps=BOOTSTRAP_REPS):
    names = [p["key"] for p in frozen["normal_players"]]
    active_indices = [
        i for i, key in enumerate(names)
        if realized[key]["active_games"] > 0
    ]
    if len(active_indices) < 50:
        return {
            "eligible": False,
            "reason": "fewer than 50 active players",
            "n": len(active_indices),
        }

    candidate = frozen["variants"][candidate_key]["prod_mult_vector"]
    control = frozen["deployed_control"]["prod_mult_vector"]
    outcomes = [float(realized[names[i]]["active_ppg"]) for i in active_indices]
    cand = [float(candidate[i]) for i in active_indices]
    ctrl = [float(control[i]) for i in active_indices]

    base_c = evaluator.spearman(cand, outcomes)
    base_d = evaluator.spearman(ctrl, outcomes)
    if base_c is None or base_d is None:
        return {"eligible": False, "reason": "undefined base Spearman"}

    rng = random.Random(BOOTSTRAP_SEED + sum(ord(c) for c in candidate_key))
    diffs = []
    n = len(active_indices)
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        c = [cand[i] for i in idx]
        d = [ctrl[i] for i in idx]
        y = [outcomes[i] for i in idx]
        cs = evaluator.spearman(c, y)
        ds = evaluator.spearman(d, y)
        if cs is not None and ds is not None:
            diffs.append(cs - ds)

    if len(diffs) < reps * 0.9:
        return {"eligible": False, "reason": "too many undefined bootstrap samples"}

    diffs.sort()
    def q(p):
        x = (len(diffs) - 1) * p
        lo = int(math.floor(x))
        hi = int(math.ceil(x))
        if lo == hi:
            return diffs[lo]
        f = x - lo
        return diffs[lo] * (1 - f) + diffs[hi] * f

    return round_numbers({
        "eligible": True,
        "n": n,
        "reps": len(diffs),
        "observed_spearman_delta_vs_deployed": base_c - base_d,
        "bootstrap_median_delta": statistics.median(diffs),
        "ci80": [q(0.10), q(0.90)],
        "ci95": [q(0.025), q(0.975)],
        "share_delta_positive": sum(1 for d in diffs if d > 0) / len(diffs),
    })


def readiness_status(n):
    if n <= 0:
        return "READY_WAITING_FOR_COMPLETED_WEEK_1"
    if n <= 3:
        return "COLLECTING_NO_CALIBRATION"
    if n <= 7:
        return "EARLY_DIAGNOSTIC_ONLY"
    if n <= 11:
        return "CALIBRATION_REVIEW_ELIGIBLE_NOT_DEPLOYMENT"
    if n <= 17:
        return "STABILITY_REVIEW_ELIGIBLE_NOT_AUTO_DEPLOYMENT"
    return "SEASON_COMPLETE_CALIBRATION_REVIEW"


def build_evaluation(frozen):
    validate_frozen(frozen)
    evaluator = load_module("evaluate_model_history_phase9", MODEL_EVALUATOR_PATH)

    base = {
        "schema_version": 1,
        "phase": "Production V2 Phase 9",
        "status": None,
        "protocol": PROTOCOL,
        "protocol_sha256": PROTOCOL_SHA256,
        "production_mutation_authorized": False,
        "deployment_authorized": False,
        "calibration_claim_authorized": False,
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_candidate_sha256": sha256(FROZEN_PATH),
        "reference_variant": REFERENCE_VARIANT,
        "deployed_control": DEPLOYED_CONTROL,
    }

    if not OUTCOMES_PATH.exists():
        base.update({
            "status": "READY_WAITING_FOR_COMPLETED_WEEK_1",
            "outcomes_available": False,
            "completed_weeks": [],
            "completed_prefix_weeks": [],
            "completed_prefix_count": 0,
            "windows": {},
            "interpretation": (
                "Phase 9 is installed and the preseason prediction matrix is "
                "frozen. No realized 2026 outcome file exists yet."
            ),
        })
        return round_numbers(base)

    outcomes = read_json(OUTCOMES_PATH)
    evaluator.validate_outcomes(outcomes)
    completed = evaluator.completed_outcome_weeks(outcomes)
    prefix = completed_prefix(completed)
    n = len(prefix)

    base.update({
        "status": readiness_status(n),
        "outcomes_available": True,
        "outcomes_sha256": sha256(OUTCOMES_PATH),
        "outcomes_refreshed_at_utc": outcomes.get("refreshed_at_utc"),
        "completed_weeks": completed,
        "completed_prefix_weeks": prefix,
        "completed_prefix_count": n,
    })

    names = [p["key"] for p in frozen["normal_players"]]
    positions = [p["pos"] for p in frozen["normal_players"]]

    windows = {}
    for window_name, weeks in window_specs(prefix):
        realized = aggregate_outcomes(outcomes, weeks, names)

        scoreboard = {}
        scoreboard[DEPLOYED_CONTROL] = score_prediction(
            evaluator,
            names,
            positions,
            frozen["deployed_control"]["value_vector"],
            frozen["deployed_control"]["prod_mult_vector"],
            realized,
        )

        for key, variant in frozen["variants"].items():
            scoreboard[key] = score_prediction(
                evaluator,
                names,
                positions,
                variant["value_vector"],
                variant["prod_mult_vector"],
                realized,
            )

        ordered = rank_scoreboard(scoreboard)
        variant_order = [k for k in ordered if k != DEPLOYED_CONTROL]
        top_variants = variant_order[:15]
        deployed_rank = ordered.index(DEPLOYED_CONTROL) + 1
        ref_rank = ordered.index(REFERENCE_VARIANT) + 1

        deployed_primary = (
            scoreboard[DEPLOYED_CONTROL]["primary_prod_mult_vs_active_ppg"].get("spearman")
        )
        ref_primary = (
            scoreboard[REFERENCE_VARIANT]["primary_prod_mult_vs_active_ppg"].get("spearman")
        )

        compact_top = []
        for rank, key in enumerate(top_variants, start=1):
            row = scoreboard[key]
            primary = row["primary_prod_mult_vs_active_ppg"]
            variant = frozen["variants"][key]
            sp = primary.get("spearman")
            compact_top.append({
                "rank": rank,
                "variant": key,
                "fantasypros_weight": variant["fantasypros_weight"],
                "history_weight": variant["history_weight"],
                "rank_family": variant["rank_family"],
                "floor": variant["floor"],
                "primary": primary,
                "secondary_value_vs_total_points": row["secondary_value_vs_total_points"],
                "primary_spearman_delta_vs_deployed": (
                    sp - deployed_primary
                    if sp is not None and deployed_primary is not None else None
                ),
                "primary_spearman_delta_vs_reference": (
                    sp - ref_primary
                    if sp is not None and ref_primary is not None else None
                ),
            })

        # Position diagnostics for the top 5 only.
        top_position = {
            key: scoreboard[key]["primary_by_position"]
            for key in top_variants[:5]
        }

        bootstrap = {}
        if len(weeks) >= 8:
            for key in top_variants[:5]:
                bootstrap[key] = paired_bootstrap(
                    evaluator, frozen, realized, key
                )

        windows[window_name] = {
            "weeks": weeks,
            "active_player_count": sum(
                1 for row in realized.values() if row["active_games"] > 0
            ),
            "deployed_control_rank_among_121": deployed_rank,
            "reference_variant_rank_among_121": ref_rank,
            "deployed_control_metrics": scoreboard[DEPLOYED_CONTROL],
            "reference_variant_metrics": scoreboard[REFERENCE_VARIANT],
            "top_variants": compact_top,
            "parameter_profiles": parameter_profiles(scoreboard, frozen),
            "top5_primary_by_position": top_position,
            "top5_paired_bootstrap_vs_deployed": bootstrap,
        }

    base["windows"] = windows

    # Stability summary once split windows exist.
    stability = {
        "available": False,
        "note": "Requires at least 8 completed consecutive weeks.",
    }
    if n >= 8 and "weeks_1_to_4" in windows and "weeks_5_to_8" in windows:
        w1 = windows["weeks_1_to_4"]["top_variants"]
        w2 = windows["weeks_5_to_8"]["top_variants"]
        w8 = windows["weeks_1_to_8"]["top_variants"]
        stability = {
            "available": True,
            "week1_4_top_variant": w1[0]["variant"] if w1 else None,
            "week5_8_top_variant": w2[0]["variant"] if w2 else None,
            "week1_8_top_variant": w8[0]["variant"] if w8 else None,
            "exact_top_variant_stable_across_1_4_and_5_8": (
                bool(w1 and w2 and w1[0]["variant"] == w2[0]["variant"])
            ),
            "top10_overlap_1_4_vs_5_8": len(
                {r["variant"] for r in w1[:10]}
                & {r["variant"] for r in w2[:10]}
            ),
        }
    base["stability"] = stability

    if n == 0:
        interpretation = (
            "Outcome capture exists, but no completed consecutive 2026 week is "
            "yet eligible under the leakage-safe completion rule."
        )
    elif n < 4:
        interpretation = (
            "Phase 9 is collecting realized evidence. Results are smoke-test "
            "diagnostics only and must not influence coefficients."
        )
    elif n < 8:
        interpretation = (
            "The first 4-week diagnostic is available. It is intentionally too "
            "early to select provider/history/rank/floor settings."
        )
    elif n < 12:
        interpretation = (
            "Phase 9 has enough evidence for calibration review. Compare the "
            "first and second four-week windows, cumulative results, position "
            "guardrails, and paired bootstrap before shortlisting settings."
        )
    else:
        interpretation = (
            "Phase 9 has entered stability review. A Phase-10 deployment review "
            "may be prepared only if improvements are stable across independent "
            "windows and materially beat the frozen deployed control without "
            "position-level regressions."
        )
    base["interpretation"] = interpretation
    return round_numbers(base)


def render_md(result):
    lines = [
        "# Production V2 — Phase 9 Prospective Evaluator",
        "",
        "## Status",
        "",
        f"**{result['status']}**",
        "",
        "- Production files mutated: **0**",
        "- Deployment authorized: **No**",
        f"- Frozen candidate matrix: **120 V2 variants + deployed control**",
        f"- Completed consecutive weeks: **{result.get('completed_prefix_count', 0)}**",
        "",
        "## Frozen protocol",
        "",
        "- Primary: **effective PROD_MULT vs realized active-game PPG**",
        "- Secondary: Fundamental Value vs future total points",
        "- Secondary: Fundamental Value vs realized active-game PPG",
        "- Completed-week and leakage rules are reused from `scripts/validation/evaluate_model_history.py`.",
        "- Predictions are frozen preseason and never rebuilt from later `index.html` state.",
        "",
        "## Readiness ladder",
        "",
        "- Weeks 1–3: collection only",
        "- Weeks 4–7: early diagnostic only",
        "- Weeks 8–11: calibration review eligible",
        "- Weeks 12+: stability review eligible",
        "- Week 18: season-complete review",
        "",
    ]

    if not result.get("outcomes_available"):
        lines += [
            "## Current result",
            "",
            "The evaluator is fully installed and ready. No realized 2026 outcome file exists yet, so there is nothing legitimate to grade.",
            "",
        ]
        return "\n".join(lines).rstrip() + "\n"

    lines += [
        "## Completed outcome state",
        "",
        f"- Outcome refresh: `{result.get('outcomes_refreshed_at_utc')}`",
        f"- Completed weeks recognized: **{result.get('completed_weeks', [])}**",
        f"- Consecutive prefix used: **{result.get('completed_prefix_weeks', [])}**",
        "",
    ]

    windows = result.get("windows") or {}
    for name, window in windows.items():
        lines += [
            f"## {name}",
            "",
            f"Weeks: **{window['weeks']}**  ",
            f"Active normal-candidate players: **{window['active_player_count']}**  ",
            f"Deployed control rank: **{window['deployed_control_rank_among_121']} / 121**  ",
            f"Phase-8 monitoring reference rank: **{window['reference_variant_rank_among_121']} / 121**",
            "",
            "| Rank | Variant | FP wt | History wt | Ranks | Floor | Primary Spearman | Δ vs deployed | Pairwise |",
            "|---:|---|---:|---:|---|---:|---:|---:|---:|",
        ]
        for row in window["top_variants"][:10]:
            p = row["primary"]
            lines.append(
                f"| {row['rank']} | `{row['variant']}` | "
                f"{row['fantasypros_weight']:.0%} | {row['history_weight']:.0%} | "
                f"{row['rank_family']} | {row['floor']:.2f} | "
                f"{p.get('spearman') if p.get('spearman') is not None else '—'} | "
                f"{row.get('primary_spearman_delta_vs_deployed') if row.get('primary_spearman_delta_vs_deployed') is not None else '—'} | "
                f"{p.get('pairwise_ordering_accuracy') if p.get('pairwise_ordering_accuracy') is not None else '—'} |"
            )
        lines.append("")

    stability = result.get("stability") or {}
    lines += [
        "## Stability",
        "",
    ]
    if stability.get("available"):
        lines += [
            f"- Weeks 1–4 top: `{stability.get('week1_4_top_variant')}`",
            f"- Weeks 5–8 top: `{stability.get('week5_8_top_variant')}`",
            f"- Weeks 1–8 top: `{stability.get('week1_8_top_variant')}`",
            f"- Exact top stable across independent 4-week windows: **{stability.get('exact_top_variant_stable_across_1_4_and_5_8')}**",
            f"- Top-10 overlap between Weeks 1–4 and 5–8: **{stability.get('top10_overlap_1_4_vs_5_8')} / 10**",
            "",
        ]
    else:
        lines += [stability.get("note", "Not available yet."), ""]

    lines += [
        "## Interpretation",
        "",
        result.get("interpretation", ""),
        "",
        "Phase 9 never deploys a coefficient automatically. Any eventual winner must survive independent-window stability, position guardrails, bootstrap uncertainty, and comparison against the frozen deployed model before Phase 10.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def semantic_for_check(obj):
    x = copy.deepcopy(obj)
    x["evaluated_at_utc"] = "<normalized>"
    return x


def write_evaluation(result):
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(render_md(result), encoding="utf-8")
    print(
        f"Phase-9 evaluation: {result['status']} | "
        f"completed_prefix={result.get('completed_prefix_count', 0)}"
    )


def check_evaluation():
    if not FROZEN_PATH.exists():
        raise RuntimeError("Phase-9 frozen candidate matrix is missing")
    frozen = read_json(FROZEN_PATH)
    validate_frozen(frozen)
    expected = build_evaluation(frozen)

    if not OUTPUT_JSON.exists() or not OUTPUT_MD.exists():
        raise RuntimeError("Phase-9 evaluation outputs are missing")
    existing = read_json(OUTPUT_JSON)
    if semantic_for_check(existing) != semantic_for_check(expected):
        raise RuntimeError("Phase-9 JSON does not reproduce semantically")
    if OUTPUT_MD.read_text(encoding="utf-8") != render_md(expected):
        raise RuntimeError("Phase-9 Markdown does not reproduce exactly")
    print("PASS Phase-9 semantic-output check.")


def run_selftest():
    assert EXPECTED_VARIANTS == (
        len(FP_WEIGHTS) * len(HISTORY_WEIGHTS) * 2 * len(FLOORS)
    )
    assert variant_key(0.50, 0.45, "evidence_hybrid", 0.15) == REFERENCE_VARIANT

    # Provider blend.
    rec = {
        "pos": "QB",
        "forward": {"fantasypros_points": 120, "sleeper_points": 100}
    }
    assert offense_forward(rec, 0.50) == 110
    assert offense_forward(rec, 1.00) == 120
    assert offense_forward(rec, 0.00) == 100

    # Single-source fallback does not disappear at an edge weight.
    rec = {
        "pos": "WR",
        "forward": {"fantasypros_points": 90, "sleeper_points": None}
    }
    assert offense_forward(rec, 0.00) == 90

    assert completed_prefix([]) == []
    assert completed_prefix([1, 2, 4]) == [1, 2]
    assert completed_prefix([1, 2, 3, 4]) == [1, 2, 3, 4]

    assert readiness_status(0) == "READY_WAITING_FOR_COMPLETED_WEEK_1"
    assert readiness_status(4) == "EARLY_DIAGNOSTIC_ONLY"
    assert readiness_status(8) == "CALIBRATION_REVIEW_ELIGIBLE_NOT_DEPLOYMENT"
    assert readiness_status(12) == "STABILITY_REVIEW_ELIGIBLE_NOT_AUTO_DEPLOYMENT"

    print("PASS Production V2 Phase-9 standalone self-test.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    if not any((args.freeze, args.write, args.check)):
        parser.error("choose --freeze, --write, or --check")

    if args.freeze:
        freeze_candidates()
        return

    if args.write:
        if not FROZEN_PATH.exists():
            raise RuntimeError("run --freeze before --write")
        frozen = read_json(FROZEN_PATH)
        validate_frozen(frozen)
        result = build_evaluation(frozen)
        write_evaluation(result)
        return

    check_evaluation()


if __name__ == "__main__":
    main()

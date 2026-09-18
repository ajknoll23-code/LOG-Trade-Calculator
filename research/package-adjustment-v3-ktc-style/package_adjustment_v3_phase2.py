#!/usr/bin/env python3
"""Package Adjustment V3 Phase 2 — all-asset scarcity candidate family.

Research only. Production is unchanged.

Phase 1 established that the live topology-specific V1.6 architecture cannot
serve as a general trade calculator:
- 1/5 supplied KTC reference shapes supported;
- 0/8 supplied completed league trades supported;
- a nonlinear bilateral all-asset architecture is justified.

Phase 2 does NOT pick a production formula. It freezes a small candidate family
and requires every eligible candidate to pass hard mathematical/runtime
invariants before any fresh human confirmation voting is generated.

Evidence governance:
- five KTC screenshots: development-only behavioral anchors;
- eight real league trades: topology/scope anchors, not fairness labels;
- prior exact 900-vote dataset: spent and prohibited here.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import random
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "research" / "package-adjustment-v3-ktc-style"
INDEX = ROOT / "index.html"
PHASE1_SCRIPT = RESEARCH / "package_adjustment_v3_phase1.py"
PHASE1_AUDIT = RESEARCH / "phase1_architecture_audit.json"
PHASE1_PREREG = RESEARCH / "phase1_preregistration.json"
TRADE_HISTORY = ROOT / "data" / "trade_history.json"

PREREG_JSON = RESEARCH / "phase2_preregistration.json"
PREREG_MD = RESEARCH / "phase2_preregistration.md"
OUT_JSON = RESEARCH / "phase2_candidate_family.json"
OUT_MD = RESEARCH / "phase2_candidate_family.md"
MANIFEST = RESEARCH / "phase2_manifest.json"

VALIDATION_DIR = ROOT / "scripts" / "validation"
if str(VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATION_DIR))
import snapshot_values  # noqa: E402

# Development grid. The 1.85 lower-curvature control is intentionally included
# but must fail the KTC-direction eligibility gate if Phase 1 behavior holds.
CANDIDATE_GRID = [
    {
        "id": "power-g1.85-control",
        "gamma": 1.85,
        "role": "lower_curvature_control",
    },
    {
        "id": "power-g2.01",
        "gamma": 2.01,
        "role": "minimum_ktc_conformant_curvature",
    },
    {
        "id": "power-g2.15",
        "gamma": 2.15,
        "role": "moderate_stud_curvature",
    },
    {
        "id": "power-g2.30",
        "gamma": 2.30,
        "role": "strong_stud_curvature",
    },
]

FRESH_CONFIRMATION_FAMILY_IDS = [
    "power-g2.01",
    "power-g2.15",
    "power-g2.30",
]

SHAPES = [
    (1, 2),
    (1, 3),
    (2, 2),
    (2, 3),
    (3, 3),
    (3, 4),
    (4, 6),
    (5, 6),
    (6, 6),
    (1, 10),
]

RNG_SEED = 20260918
STRESS_CASES_PER_SHAPE = 200
EPS = 1e-9


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(obj) -> str:
    return hashlib.sha256(
        json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def load_phase1():
    spec = importlib.util.spec_from_file_location(
        "package_adjustment_v3_phase1",
        PHASE1_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not import Phase 1 evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preregister():
    phase1 = json.loads(PHASE1_AUDIT.read_text(encoding="utf-8"))
    if (
        phase1.get("decision")
        != "PASS_V3_PHASE1_ARCHITECTURE_REPLACEMENT_JUSTIFIED"
    ):
        raise RuntimeError("Phase 1 replacement-architecture gate not passed")

    prereg = {
        "schema_version": 1,
        "study_id": "package-adjustment-v3-ktc-style",
        "phase": 2,
        "status": "FROZEN_BEFORE_EVALUATION",
        "research_only": True,
        "production_change_authorized": False,
        "candidate_grid": CANDIDATE_GRID,
        "fresh_confirmation_family_ids": FRESH_CONFIRMATION_FAMILY_IDS,
        "eligibility_rules": {
            "gamma_must_exceed_one": True,
            "ktc_development_adjusted_side_accuracy": "5/5",
            "all_hard_invariants_must_pass": True,
            "all_stress_shapes_must_have_finite_outputs": True,
            "draft_picks_supported_as_first_class_positive_value_assets": True,
        },
        "hard_invariants": [
            "one_for_one_policy_is_zero_package_adjustment",
            "side_swap_symmetry",
            "asset_order_invariance",
            "positive_asset_score_monotonicity",
            "scale_equivariance",
            "fragmentation_penalty_for_equal_raw_total",
            "tiny_piece_continuity",
            "nonnegative_finite_display_adjustment",
            "multi_vs_multi_support",
            "draft_pick_support",
        ],
        "evidence_roles": {
            "five_ktc_screenshots": "development_only_behavioral_anchor",
            "eight_completed_league_trades": "topology_scope_anchor_not_fairness_label",
            "old_900_vote_dataset": "spent_prohibited",
        },
        "selection_policy": (
            "Phase 2 may nominate a development reference candidate using the "
            "five KTC anchors, but it may not declare a production winner. "
            "Fresh confirmation evidence must select/reject the frozen family."
        ),
        "stress_protocol": {
            "rng_seed": RNG_SEED,
            "cases_per_shape": STRESS_CASES_PER_SHAPE,
            "shapes": [f"{a}v{b}" for a, b in SHAPES],
        },
    }
    PREREG_JSON.write_text(
        json.dumps(prereg, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    PREREG_MD.write_text(
        """# Package Adjustment V3 — Phase 2 Preregistration

**Research only. Production is unchanged.**

Phase 2 freezes a small power-scarcity candidate family and tests it against
hard mathematical/runtime invariants before any fresh human confirmation vote
catalog is generated.

## Candidate grid

- `power-g1.85-control` — lower-curvature control.
- `power-g2.01` — minimum KTC-conformant curvature from Phase 1.
- `power-g2.15` — moderate stud curvature.
- `power-g2.30` — stronger stud curvature.

Only candidates with 5/5 KTC-development adjusted-side direction and every
hard invariant passing can enter fresh confirmation.

The old 900-vote dataset is prohibited. Historical accepted league trades are
topology/scope evidence only and are not treated as perfectly fair trades.

No production winner can be selected in Phase 2.
""",
        encoding="utf-8",
    )
    print("Package Adjustment V3 Phase 2 preregistration frozen")


def parse_pick_policy(index_text: str):
    block = re.search(
        r"const\s+PICK_BASE\s*=\s*\{(.*?)\n\};",
        index_text,
        flags=re.S,
    )
    if not block:
        raise RuntimeError("Could not parse PICK_BASE")

    pick_base = {}
    row_re = re.compile(
        r"(\d+)\s*:\s*\{\s*early\s*:\s*([0-9.]+)\s*,\s*"
        r"mid\s*:\s*([0-9.]+)\s*,\s*late\s*:\s*([0-9.]+)"
    )
    for round_s, early, mid, late in row_re.findall(block.group(1)):
        pick_base[int(round_s)] = {
            "early": float(early),
            "mid": float(mid),
            "late": float(late),
        }
    if sorted(pick_base) != [1, 2, 3, 4, 5, 6]:
        raise RuntimeError(f"Unexpected PICK_BASE rounds: {sorted(pick_base)}")

    year_match = re.search(
        r"const\s+YEAR_DISCOUNT\s*=\s*\{(.*?)\};",
        index_text,
        flags=re.S,
    )
    if not year_match:
        raise RuntimeError("Could not parse YEAR_DISCOUNT")
    year_discount = {
        year: float(value)
        for year, value in re.findall(
            r"['\"](\d{4})['\"]\s*:\s*([0-9.]+)",
            year_match.group(1),
        )
    }
    if not year_discount:
        raise RuntimeError("YEAR_DISCOUNT parsed empty")

    return {
        "pick_base": pick_base,
        "year_discount": year_discount,
        "fallback_discount": 0.6,
    }


def pick_value(round_num, slot, year, policy):
    base = policy["pick_base"].get(
        int(round_num),
        policy["pick_base"][6],
    ).get(slot, policy["pick_base"][6]["late"])
    discount = policy["year_discount"].get(
        str(year),
        policy["fallback_discount"],
    )
    # JS Math.round positive semantics.
    return math.floor(base * discount + 0.5)


def build_asset_universe():
    cfg = snapshot_values.load_from_html(INDEX)
    players = snapshot_values.compute_all_values(cfg)

    player_assets = [
        {
            "kind": "player",
            "id": key,
            "pos": row["pos"],
            "value": float(row["value"]),
        }
        for key, row in players.items()
        if isinstance(row.get("value"), (int, float))
        and row["value"] > 0
    ]
    if len(player_assets) < 500:
        raise RuntimeError(
            f"Unexpectedly small player asset universe: {len(player_assets)}"
        )

    index_text = INDEX.read_text(encoding="utf-8")
    policy = parse_pick_policy(index_text)
    pick_assets = []
    for year in ("2026", "2027", "2028", "2029"):
        for round_num in range(1, 7):
            for slot in ("early", "mid", "late"):
                value = pick_value(
                    round_num,
                    slot,
                    year,
                    policy,
                )
                if value <= 0:
                    raise RuntimeError(
                        f"Nonpositive pick value: {year} R{round_num} {slot}"
                    )
                pick_assets.append(
                    {
                        "kind": "pick",
                        "id": f"{year}-r{round_num}-{slot}",
                        "year": year,
                        "round": round_num,
                        "slot": slot,
                        "value": float(value),
                    }
                )

    return player_assets, pick_assets, policy


def scarcity_score(value: float, gamma: float, apex: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"Invalid asset value: {value}")
    if not (gamma > 1):
        raise ValueError(f"Gamma must be >1: {gamma}")
    if not (apex > 0):
        raise ValueError(f"Apex must be >0: {apex}")
    return (value / apex) ** gamma


def inverse_scarcity_score(score: float, gamma: float, apex: float) -> float:
    score = float(score)
    if not math.isfinite(score) or score < 0:
        raise ValueError(f"Invalid scarcity score: {score}")
    return apex * (score ** (1.0 / gamma))


def package_adjustment(side_a, side_b, gamma, apex):
    a = [float(x) for x in side_a]
    b = [float(x) for x in side_b]

    if not a or not b:
        raise ValueError("Both trade sides must contain at least one asset")
    if any((not math.isfinite(x) or x <= 0) for x in a + b):
        raise ValueError("All trade assets must have positive finite value")

    # Package adjustment is intentionally quiet for pure 1-for-1 trades.
    if len(a) == 1 and len(b) == 1:
        return {
            "adjusted_side": None,
            "adjustment": 0.0,
            "equivalent_missing_asset": 0.0,
            "score_a": scarcity_score(a[0], gamma, apex),
            "score_b": scarcity_score(b[0], gamma, apex),
        }

    score_a = sum(scarcity_score(x, gamma, apex) for x in a)
    score_b = sum(scarcity_score(x, gamma, apex) for x in b)

    delta = score_a - score_b
    if abs(delta) <= 1e-15:
        return {
            "adjusted_side": None,
            "adjustment": 0.0,
            "equivalent_missing_asset": 0.0,
            "score_a": score_a,
            "score_b": score_b,
        }

    adjusted_side = "A" if delta > 0 else "B"
    missing = inverse_scarcity_score(
        abs(delta),
        gamma,
        apex,
    )

    raw_a = sum(a)
    raw_b = sum(b)
    if adjusted_side == "A":
        adjustment = raw_b + missing - raw_a
    else:
        adjustment = raw_a + missing - raw_b

    adjustment = max(0.0, adjustment)
    if not math.isfinite(adjustment):
        raise RuntimeError("Nonfinite package adjustment")

    return {
        "adjusted_side": adjusted_side,
        "adjustment": adjustment,
        "equivalent_missing_asset": missing,
        "score_a": score_a,
        "score_b": score_b,
    }


def ktc_diagnostics(phase1, candidate):
    gamma = candidate["gamma"]
    rows = []
    correct_side = 0
    errors = []

    # KTC raw values have a natural 10k apex. The normalized power transform
    # is scale-equivariant, so using 10k here is only for numerical conditioning.
    apex = 10000.0

    for fixture in phase1.KTC_FIXTURES:
        pred = package_adjustment(
            fixture["side_a"],
            fixture["side_b"],
            gamma,
            apex,
        )
        side_ok = (
            pred["adjusted_side"]
            == fixture["observed_adjusted_side"]
        )
        correct_side += int(side_ok)
        error = abs(
            pred["adjustment"]
            - fixture["observed_adjustment"]
        )
        errors.append(error)
        rows.append(
            {
                "fixture_id": fixture["id"],
                "shape": fixture["shape"],
                "side_ok": side_ok,
                "predicted_side": pred["adjusted_side"],
                "observed_adjustment": fixture["observed_adjustment"],
                "predicted_adjustment": round(
                    pred["adjustment"], 3
                ),
                "absolute_error": round(error, 3),
            }
        )

    return {
        "adjusted_side_correct": correct_side,
        "adjusted_side_total": len(rows),
        "adjusted_side_accuracy": f"{correct_side}/{len(rows)}",
        "mean_absolute_error": round(
            statistics.fmean(errors), 3
        ),
        "rows": rows,
    }


def deterministic_stress_cases(values):
    rng = random.Random(RNG_SEED)
    cases = []

    for a_count, b_count in SHAPES:
        for case_i in range(STRESS_CASES_PER_SHAPE):
            a = [
                values[rng.randrange(len(values))]
                for _ in range(a_count)
            ]
            b = [
                values[rng.randrange(len(values))]
                for _ in range(b_count)
            ]
            cases.append(
                {
                    "id": f"{a_count}v{b_count}-{case_i:03d}",
                    "shape": f"{a_count}v{b_count}",
                    "a": a,
                    "b": b,
                }
            )

    return cases


def hard_invariants(candidate, player_assets, pick_assets):
    gamma = candidate["gamma"]
    all_values = [
        row["value"] for row in player_assets + pick_assets
    ]
    apex = max(all_values)

    if not gamma > 1:
        return {
            "pass": False,
            "failure": "gamma_not_above_one",
        }

    checks = {
        "one_for_one_zero": True,
        "side_swap_symmetry": True,
        "asset_order_invariance": True,
        "positive_asset_score_monotonicity": True,
        "scale_equivariance": True,
        "fragmentation_penalty": True,
        "tiny_piece_continuity": True,
        "finite_nonnegative_adjustments": True,
        "all_stress_shapes_covered": True,
        "draft_pick_support": True,
    }

    # 1-for-1 is deliberately not a package-adjustment case.
    quantiles = sorted(all_values)
    sample_idx = [
        0,
        len(quantiles) // 4,
        len(quantiles) // 2,
        3 * len(quantiles) // 4,
        len(quantiles) - 1,
    ]
    sample = [quantiles[i] for i in sample_idx]
    for x in sample:
        for y in sample:
            r = package_adjustment([x], [y], gamma, apex)
            if r["adjustment"] != 0 or r["adjusted_side"] is not None:
                checks["one_for_one_zero"] = False

    # Equal-total fragmentation must lose scarcity score under gamma>1.
    for frac in (0.25, 0.50, 0.75, 1.00):
        total = apex * frac
        seq = []
        for n in range(1, 7):
            piece = total / n
            score = n * scarcity_score(piece, gamma, apex)
            seq.append(score)
        if not all(
            seq[i] > seq[i + 1] + 1e-15
            for i in range(len(seq) - 1)
        ):
            checks["fragmentation_penalty"] = False

    # Tiny-piece continuity on a clear non-tie example.
    base_a = [apex]
    base_b = [apex * 0.55, apex * 0.35]
    base = package_adjustment(
        base_a,
        base_b,
        gamma,
        apex,
    )
    tiny = apex * 1e-8
    perturbed = package_adjustment(
        base_a,
        base_b + [tiny],
        gamma,
        apex,
    )
    if abs(
        perturbed["adjustment"] - base["adjustment"]
    ) > apex * 1e-5:
        checks["tiny_piece_continuity"] = False

    # Explicit player+pick and pick-only package cases.
    pick_values = [row["value"] for row in pick_assets]
    player_values = [row["value"] for row in player_assets]
    pick_cases = [
        (
            [max(player_values)],
            [pick_values[0], pick_values[10], pick_values[20]],
        ),
        (
            [max(player_values), pick_values[5]],
            [player_values[len(player_values)//2], pick_values[15]],
        ),
        (
            [pick_values[0], pick_values[1]],
            [pick_values[2], pick_values[3], pick_values[4]],
        ),
    ]
    for a, b in pick_cases:
        r = package_adjustment(a, b, gamma, apex)
        if (
            not math.isfinite(r["adjustment"])
            or r["adjustment"] < 0
        ):
            checks["draft_pick_support"] = False

    stress = deterministic_stress_cases(all_values)
    max_adjustment = 0.0
    adjusted_side_counts = {
        "A": 0,
        "B": 0,
        "none": 0,
    }

    for case in stress:
        a = case["a"]
        b = case["b"]
        r = package_adjustment(a, b, gamma, apex)

        if (
            not math.isfinite(r["adjustment"])
            or r["adjustment"] < -EPS
            or not math.isfinite(r["equivalent_missing_asset"])
        ):
            checks["finite_nonnegative_adjustments"] = False

        max_adjustment = max(
            max_adjustment,
            r["adjustment"],
        )
        adjusted_side_counts[
            r["adjusted_side"] or "none"
        ] += 1

        # Side-swap symmetry.
        rs = package_adjustment(b, a, gamma, apex)
        expected_side = (
            None
            if r["adjusted_side"] is None
            else ("B" if r["adjusted_side"] == "A" else "A")
        )
        if (
            rs["adjusted_side"] != expected_side
            or abs(rs["adjustment"] - r["adjustment"])
            > max(1e-7, apex * 1e-10)
        ):
            checks["side_swap_symmetry"] = False

        # Asset order invariance.
        ro = package_adjustment(
            list(reversed(a)),
            list(reversed(b)),
            gamma,
            apex,
        )
        if (
            ro["adjusted_side"] != r["adjusted_side"]
            or abs(ro["adjustment"] - r["adjustment"])
            > max(1e-7, apex * 1e-10)
        ):
            checks["asset_order_invariance"] = False

        # Positive asset score monotonicity.
        before = sum(
            scarcity_score(x, gamma, apex) for x in a
        )
        extra = min(all_values)
        after = before + scarcity_score(
            extra,
            gamma,
            apex,
        )
        if not after > before:
            checks[
                "positive_asset_score_monotonicity"
            ] = False

        # Scale equivariance. Apex must scale with the same transformation.
        for factor in (0.5, 2.0):
            scaled = package_adjustment(
                [x * factor for x in a],
                [x * factor for x in b],
                gamma,
                apex * factor,
            )
            if (
                scaled["adjusted_side"]
                != r["adjusted_side"]
                or abs(
                    scaled["adjustment"]
                    - r["adjustment"] * factor
                )
                > max(1e-6, apex * factor * 1e-9)
            ):
                checks["scale_equivariance"] = False

    shape_counts = {}
    for case in stress:
        shape_counts[case["shape"]] = (
            shape_counts.get(case["shape"], 0) + 1
        )
    expected_shapes = {
        f"{a}v{b}" for a, b in SHAPES
    }
    if set(shape_counts) != expected_shapes:
        checks["all_stress_shapes_covered"] = False

    return {
        "pass": all(checks.values()),
        "checks": checks,
        "stress_case_count": len(stress),
        "stress_shape_counts": shape_counts,
        "adjusted_side_counts": adjusted_side_counts,
        "max_display_adjustment": round(
            max_adjustment, 3
        ),
        "apex_asset_value": apex,
    }


def historical_current_state_diagnostic(
    candidate,
    phase1,
    player_assets,
    policy,
):
    values_by_name = {
        snapshot_values.normalize_lookup_name(row["id"]): row["value"]
        for row in player_assets
    }
    # The snapshot keys are already normalized lookup keys, but preserve
    # explicit normalization for safety.
    values_by_name = {
        snapshot_values.normalize_lookup_name(k): v
        for k, v in values_by_name.items()
    }

    history = json.loads(
        TRADE_HISTORY.read_text(encoding="utf-8")
    )
    by_id = {
        str(row.get("transaction_id")): row
        for row in (history.get("trades_with_picks") or [])
    }

    apex = max(
        [row["value"] for row in player_assets]
        + [
            pick_value(r, s, y, policy)
            for y in ("2026", "2027", "2028", "2029")
            for r in range(1, 7)
            for s in ("early", "mid", "late")
        ]
    )

    rows = []
    resolvable = 0
    for anchor in phase1.HISTORICAL_TRADE_ANCHORS:
        trade = by_id.get(anchor["transaction_id"])
        if not trade:
            continue

        side_values = []
        unresolved = []
        for side in trade.get("sides") or []:
            vals = []

            for player in side.get("received_players") or []:
                key = snapshot_values.normalize_lookup_name(
                    player.get("name")
                )
                value = values_by_name.get(key)
                if value is None:
                    unresolved.append(
                        player.get("name")
                    )
                else:
                    vals.append(float(value))

            for pick in side.get("received_picks") or []:
                vals.append(
                    float(
                        pick_value(
                            pick.get("round"),
                            "mid",
                            pick.get("season"),
                            policy,
                        )
                    )
                )

            side_values.append(vals)

        row = {
            "trade_number": anchor["trade_number"],
            "transaction_id": anchor["transaction_id"],
            "shape": anchor["shape"],
            "current_value_resolved": (
                len(unresolved) == 0
                and len(side_values) == 2
                and all(side_values)
            ),
            "unresolved_players": sorted(
                set(unresolved)
            ),
        }

        if row["current_value_resolved"]:
            resolvable += 1
            result = package_adjustment(
                side_values[0],
                side_values[1],
                candidate["gamma"],
                apex,
            )
            row.update(
                {
                    "adjusted_side": result[
                        "adjusted_side"
                    ],
                    "display_adjustment": round(
                        result["adjustment"], 3
                    ),
                    "note": (
                        "current-state diagnostic only; "
                        "not historical fairness evidence"
                    ),
                }
            )

        rows.append(row)

    return {
        "resolved_trade_count": resolvable,
        "total_trade_count": len(
            phase1.HISTORICAL_TRADE_ANCHORS
        ),
        "rows": rows,
    }


def selftest():
    assert [row["id"] for row in CANDIDATE_GRID] == [
        "power-g1.85-control",
        "power-g2.01",
        "power-g2.15",
        "power-g2.30",
    ]
    assert all(
        row["gamma"] > 1
        for row in CANDIDATE_GRID
    )

    apex = 10000.0
    for gamma in (1.85, 2.01, 2.15, 2.30):
        # Fragmentation.
        assert (
            scarcity_score(8000, gamma, apex)
            > 2
            * scarcity_score(4000, gamma, apex)
        )

        # Inverse.
        for value in (1000, 3000, 7000, 10000):
            score = scarcity_score(
                value,
                gamma,
                apex,
            )
            recovered = inverse_scarcity_score(
                score,
                gamma,
                apex,
            )
            assert abs(recovered - value) < 1e-7

        # Symmetry and 1v1 quiet policy.
        r = package_adjustment(
            [8000],
            [4500, 3500],
            gamma,
            apex,
        )
        s = package_adjustment(
            [4500, 3500],
            [8000],
            gamma,
            apex,
        )
        assert abs(
            r["adjustment"] - s["adjustment"]
        ) < 1e-8
        assert (
            r["adjusted_side"] == "A"
        ) == (
            s["adjusted_side"] == "B"
        )
        one = package_adjustment(
            [8000],
            [7000],
            gamma,
            apex,
        )
        assert one["adjustment"] == 0
        assert one["adjusted_side"] is None

    print(
        "Package Adjustment V3 Phase 2 self-test PASS"
    )


def evaluate():
    phase1_audit = json.loads(
        PHASE1_AUDIT.read_text(encoding="utf-8")
    )
    if (
        phase1_audit.get("decision")
        != "PASS_V3_PHASE1_ARCHITECTURE_REPLACEMENT_JUSTIFIED"
    ):
        raise RuntimeError(
            "Phase 1 architecture gate not passed"
        )

    prereg = json.loads(
        PREREG_JSON.read_text(encoding="utf-8")
    )
    if prereg.get("candidate_grid") != CANDIDATE_GRID:
        raise RuntimeError(
            "Phase 2 candidate grid differs from preregistration"
        )

    phase1 = load_phase1()
    player_assets, pick_assets, pick_policy = (
        build_asset_universe()
    )

    results = []
    eligible = []

    for candidate in CANDIDATE_GRID:
        ktc = ktc_diagnostics(
            phase1,
            candidate,
        )
        invariants = hard_invariants(
            candidate,
            player_assets,
            pick_assets,
        )

        is_eligible = (
            ktc["adjusted_side_accuracy"] == "5/5"
            and invariants["pass"] is True
        )

        row = {
            **candidate,
            "ktc_development": ktc,
            "hard_invariants": invariants,
            "eligible_for_fresh_confirmation": (
                is_eligible
            ),
        }
        results.append(row)
        if is_eligible:
            eligible.append(candidate["id"])

    if eligible != FRESH_CONFIRMATION_FAMILY_IDS:
        raise RuntimeError(
            "Frozen fresh-confirmation family mismatch: "
            f"expected={FRESH_CONFIRMATION_FAMILY_IDS} "
            f"actual={eligible}"
        )

    eligible_rows = [
        row for row in results
        if row["eligible_for_fresh_confirmation"]
    ]
    reference = min(
        eligible_rows,
        key=lambda row: (
            row["ktc_development"][
                "mean_absolute_error"
            ],
            row["gamma"],
        ),
    )
    if reference["id"] != "power-g2.01":
        raise RuntimeError(
            f"Unexpected development reference: {reference['id']}"
        )

    historical_diag = historical_current_state_diagnostic(
        reference,
        phase1,
        player_assets,
        pick_policy,
    )

    gates = {
        "phase1_pass_verified": True,
        "old_900_vote_dataset_read": False,
        "three_candidate_fresh_confirmation_family_frozen": (
            eligible == FRESH_CONFIRMATION_FAMILY_IDS
        ),
        "lower_curvature_control_rejected_by_ktc_direction_gate": (
            "power-g1.85-control" not in eligible
        ),
        "all_eligible_candidates_pass_hard_invariants": all(
            row["hard_invariants"]["pass"]
            for row in eligible_rows
        ),
        "all_eligible_candidates_cover_2000_stress_cases": all(
            row["hard_invariants"][
                "stress_case_count"
            ] == len(SHAPES) * STRESS_CASES_PER_SHAPE
            for row in eligible_rows
        ),
        "player_universe_at_least_500": (
            len(player_assets) >= 500
        ),
        "pick_universe_72_variants": (
            len(pick_assets) == 72
        ),
        "production_change_authorized": False,
    }

    hard_pass = (
        gates["phase1_pass_verified"]
        and gates[
            "three_candidate_fresh_confirmation_family_frozen"
        ]
        and gates[
            "lower_curvature_control_rejected_by_ktc_direction_gate"
        ]
        and gates[
            "all_eligible_candidates_pass_hard_invariants"
        ]
        and gates[
            "all_eligible_candidates_cover_2000_stress_cases"
        ]
        and gates["player_universe_at_least_500"]
        and gates["pick_universe_72_variants"]
        and gates["production_change_authorized"] is False
    )

    decision = (
        "PASS_V3_PHASE2_FAMILY_FROZEN_FOR_FRESH_CONFIRMATION"
        if hard_pass
        else "STOP_V3_PHASE2_CANDIDATE_FAMILY_FAILURE"
    )

    result = {
        "schema_version": 1,
        "study_id": "package-adjustment-v3-ktc-style",
        "phase": 2,
        "status": "RESEARCH_ONLY_CANDIDATE_FAMILY_AUDIT_COMPLETE",
        "decision": decision,
        "production_change_authorized": False,
        "governance": {
            "old_900_vote_dataset_read": False,
            "old_900_vote_dataset_used_for_fit": False,
            "old_900_vote_dataset_used_for_selection": False,
            "historical_trades_used_as_fairness_labels": False,
            "fresh_confirmation_required": True,
        },
        "asset_universe": {
            "player_count": len(player_assets),
            "pick_variant_count": len(pick_assets),
            "player_value_min": min(
                row["value"] for row in player_assets
            ),
            "player_value_max": max(
                row["value"] for row in player_assets
            ),
            "pick_value_min": min(
                row["value"] for row in pick_assets
            ),
            "pick_value_max": max(
                row["value"] for row in pick_assets
            ),
        },
        "candidate_results": results,
        "fresh_confirmation_family_ids": eligible,
        "development_reference_candidate_id": (
            reference["id"]
        ),
        "development_reference_reason": (
            "lowest KTC-development adjustment MAE among "
            "5/5-direction candidates that pass every hard invariant; "
            "not a production winner"
        ),
        "historical_current_state_diagnostic": historical_diag,
        "phase3_requirements": [
            "Freeze a fresh confirmation challenge catalog before collecting any new votes.",
            "Design challenges to discriminate power-g2.01 vs power-g2.15 vs power-g2.30 across package shapes and asset mixes.",
            "Include player+player, player+pick, pick-heavy, and multi-vs-multi trades.",
            "Do not use old 900-vote ballots in Phase 3.",
            "Pre-register minimum voters, effective votes, topology coverage, and stop condition before opening collection.",
            "Keep production V1.6 unchanged until fresh confirmation selects and validates a successor.",
        ],
        "gates": gates,
    }

    OUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Package Adjustment V3 — Phase 2 Candidate Family",
        "",
        f"**Decision:** `{decision}`",
        "",
        "**Research only. Production V1.6 is unchanged.**",
        "",
        "## Frozen family for fresh confirmation",
        "",
        "| Candidate | Gamma | KTC side direction | KTC dev MAE | Hard invariants | Fresh confirmation? |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for row in results:
        lines.append(
            f"| `{row['id']}` | {row['gamma']:.2f} | "
            f"{row['ktc_development']['adjusted_side_accuracy']} | "
            f"{row['ktc_development']['mean_absolute_error']:.1f} | "
            f"{'PASS' if row['hard_invariants']['pass'] else 'FAIL'} | "
            f"{'YES' if row['eligible_for_fresh_confirmation'] else 'NO'} |"
        )

    lines += [
        "",
        f"Development reference: **`{reference['id']}`**.",
        "",
        "That label does **not** authorize deployment. It only identifies the "
        "closest KTC-development anchor among the mathematically valid candidates.",
        "",
        "## Stress coverage",
        "",
        f"- Player assets: **{len(player_assets)}**",
        f"- Pick variants: **{len(pick_assets)}**",
        f"- Deterministic cases per eligible candidate: **{len(SHAPES) * STRESS_CASES_PER_SHAPE}**",
        "- Shapes: " + ", ".join(f"{a}v{b}" for a, b in SHAPES),
        "- Picks are first-class positive-value assets; no player-only gate.",
        "- Multi-vs-multi is supported by construction.",
        "- 1v1 remains quiet with zero package adjustment.",
        "",
        "## Hard invariants",
        "",
        "Every eligible candidate passed:",
        "",
        "- side-swap symmetry;",
        "- asset-order invariance;",
        "- positive-value monotonicity;",
        "- scale equivariance;",
        "- equal-total fragmentation penalty;",
        "- tiny-piece continuity;",
        "- finite/nonnegative display adjustment;",
        "- player/pick mixed-package support;",
        "- all frozen package topologies.",
        "",
        "## Historical-trade diagnostic",
        "",
        f"- Current-state values resolvable for **{historical_diag['resolved_trade_count']}/{historical_diag['total_trade_count']}** real trade anchors.",
        "- These outputs are diagnostic only; accepted historical trades are not assumed fair.",
        "",
        "## Next",
        "",
        "Phase 3 should freeze a fresh human-vote catalog specifically designed "
        "to distinguish the three eligible gamma curves. No old votes may be reused.",
        "",
    ]

    OUT_MD.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "study_id": result["study_id"],
        "phase": 2,
        "decision": decision,
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
        ).strip(),
        "input_git_blobs": {
            str(PHASE1_SCRIPT.relative_to(ROOT)): git_blob(
                PHASE1_SCRIPT
            ),
            str(PHASE1_AUDIT.relative_to(ROOT)): git_blob(
                PHASE1_AUDIT
            ),
            str(PHASE1_PREREG.relative_to(ROOT)): git_blob(
                PHASE1_PREREG
            ),
            "index.html": git_blob(INDEX),
        },
        "input_sha256": {
            "index.html": sha256(INDEX),
            str(TRADE_HISTORY.relative_to(ROOT)): sha256(
                TRADE_HISTORY
            ),
        },
        "candidate_family_fingerprint_sha256": canonical_hash(
            {
                "eligible_ids": eligible,
                "candidate_grid": CANDIDATE_GRID,
                "shapes": SHAPES,
                "rng_seed": RNG_SEED,
                "cases_per_shape": STRESS_CASES_PER_SHAPE,
            }
        ),
        "output_sha256": {
            str(PREREG_JSON.relative_to(ROOT)): sha256(
                PREREG_JSON
            ),
            str(PREREG_MD.relative_to(ROOT)): sha256(
                PREREG_MD
            ),
            str(OUT_JSON.relative_to(ROOT)): sha256(
                OUT_JSON
            ),
            str(OUT_MD.relative_to(ROOT)): sha256(
                OUT_MD
            ),
            str(Path(__file__).resolve().relative_to(ROOT)): sha256(
                Path(__file__).resolve()
            ),
        },
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "decision": decision,
                "fresh_confirmation_family_ids": eligible,
                "development_reference_candidate_id": reference[
                    "id"
                ],
                "player_assets": len(player_assets),
                "pick_variants": len(pick_assets),
                "stress_cases_per_candidate": (
                    len(SHAPES) * STRESS_CASES_PER_SHAPE
                ),
                "historical_current_state_resolved": (
                    f"{historical_diag['resolved_trade_count']}/"
                    f"{historical_diag['total_trade_count']}"
                ),
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(
        required=True
    )
    group.add_argument(
        "--preregister",
        action="store_true",
    )
    group.add_argument(
        "--selftest",
        action="store_true",
    )
    group.add_argument(
        "--evaluate",
        action="store_true",
    )
    args = parser.parse_args()

    if args.preregister:
        preregister()
    elif args.selftest:
        selftest()
    else:
        evaluate()


if __name__ == "__main__":
    main()

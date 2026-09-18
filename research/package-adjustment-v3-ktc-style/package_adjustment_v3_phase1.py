#!/usr/bin/env python3
"""Package Adjustment V3 Phase 1 — KTC-style architecture audit.

Research only. Production is unchanged.

Evidence roles:
1. Five user-supplied KTC screenshots:
   development-only numerical/behavioral anchors.
2. Eight completed 2025 league trades:
   real-world topology/scope anchors only, NOT "fair trade = zero" labels.
3. Prior exact 900-vote dataset:
   spent evidence; prohibited for V3 fit, selection, or confirmation.

The new model class under study is topology-agnostic:
- transform every asset through a nonlinear scarcity/value function;
- score every asset on both sides;
- compare side totals in transformed space;
- solve backward for the equivalent missing asset;
- express that equivalent asset as a human-readable value adjustment.

No formula is selected for production in Phase 1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "research/package-adjustment-v3-ktc-style"

INDEX = ROOT / "index.html"
LIVE = ROOT / "research/package-adjustment-production-candidate-v1/live_deployment.json"
CLOSEOUT = ROOT / "research/package-adjustment-nextgen-v2/package_adjustment_nextgen_v2_research_closeout_v1.md"
TRADE_HISTORY = ROOT / "data/trade_history.json"

PREREG_JSON = OUTDIR / "phase1_preregistration.json"
PREREG_MD = OUTDIR / "phase1_preregistration.md"
OUT_JSON = OUTDIR / "phase1_architecture_audit.json"
OUT_MD = OUTDIR / "phase1_architecture_audit.md"
MANIFEST = OUTDIR / "phase1_manifest.json"

ANCHOR_MAX_VALUE = 10000.0

KTC_FIXTURES = [
    {
        "id": "gibbs_vs_achane_higgins",
        "side_a": [9998],
        "side_b": [6760, 5049],
        "observed_adjusted_side": "A",
        "observed_adjustment": 6716,
        "shape": "1v2",
    },
    {
        "id": "lamb_laporta_vs_odunze_barkley",
        "side_a": [7106, 4479],
        "side_b": [5079, 5264],
        "observed_adjusted_side": "A",
        "observed_adjustment": 2740,
        "shape": "2v2",
    },
    {
        "id": "pickens_lloyd_vs_likely_flournoy_dowdle",
        "side_a": [6132, 2943],
        "side_b": [3759, 2099, 3028],
        "observed_adjusted_side": "A",
        "observed_adjustment": 3855,
        "shape": "2v3",
    },
    {
        "id": "allen_vs_caleb_barkley",
        "side_a": [9996],
        "side_b": [8112, 5264],
        "observed_adjusted_side": "A",
        "observed_adjustment": 4912,
        "shape": "1v2",
    },
    {
        "id": "pickens_black_vs_reed_washington_brooks",
        "side_a": [6132, 3297],
        "side_b": [3202, 5132, 3461],
        "observed_adjusted_side": "A",
        "observed_adjustment": 1712,
        "shape": "2v3",
    },
]

# Independently matched to data/trade_history.json.
# Counts are side-order independent during verification.
HISTORICAL_TRADE_ANCHORS = [
    {
        "trade_number": 1,
        "transaction_id": "1302060793277190144",
        "created_utc": "2025-12-03T21:39:53.538000+00:00",
        "shape": "3v4",
        "side_counts": [(2, 1), (2, 2)],
    },
    {
        "trade_number": 2,
        "transaction_id": "1286424658563850240",
        "created_utc": "2025-10-21T18:07:28.517000+00:00",
        "shape": "5v6",
        "side_counts": [(3, 2), (3, 3)],
    },
    {
        "trade_number": 3,
        "transaction_id": "1266894062737178624",
        "created_utc": "2025-08-28T20:39:51.612000+00:00",
        "shape": "3v3",
        "side_counts": [(1, 2), (2, 1)],
    },
    {
        "trade_number": 4,
        "transaction_id": "1230727781449474048",
        "created_utc": "2025-05-21T01:27:58.216000+00:00",
        "shape": "2v2",
        "side_counts": [(2, 0), (1, 1)],
    },
    {
        "trade_number": 5,
        "transaction_id": "1279283926803714048",
        "created_utc": "2025-10-02T01:12:45.398000+00:00",
        "shape": "3v3",
        "side_counts": [(2, 1), (2, 1)],
    },
    {
        "trade_number": 6,
        "transaction_id": "1292164704810041344",
        "created_utc": "2025-11-06T14:16:22.188000+00:00",
        "shape": "4v6",
        "side_counts": [(2, 2), (2, 4)],
    },
    {
        "trade_number": 7,
        "transaction_id": "1214337320170311680",
        "created_utc": "2025-04-05T19:58:07.727000+00:00",
        "shape": "3v3",
        "side_counts": [(2, 1), (2, 1)],
    },
    {
        "trade_number": 8,
        "transaction_id": "1277441540758732800",
        "created_utc": "2025-09-26T23:11:46.334000+00:00",
        "shape": "1v2",
        "side_counts": [(1, 0), (0, 2)],
    },
]


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


def preregister():
    OUTDIR.mkdir(parents=True, exist_ok=True)

    prereg = {
        "schema_version": 1,
        "study_id": "package-adjustment-v3-ktc-style",
        "phase": 1,
        "status": "FROZEN_BEFORE_EVALUATION",
        "research_only": True,
        "production_change_authorized": False,
        "hypothesis": (
            "A topology-agnostic nonlinear asset-scarcity transform with bilateral "
            "all-asset scoring and inverse equivalent-asset display can represent "
            "real trade packages more coherently than the current topology-specific "
            "target-multiplier architecture."
        ),
        "evidence_roles": {
            "five_ktc_screenshots": "development_only_numerical_behavioral_anchors",
            "eight_completed_league_trades": "real_world_topology_scope_anchors_not_fairness_labels",
            "old_900_vote_dataset": "spent_prohibited_for_fit_selection_or_confirmation",
        },
        "successor_constraints": [
            "Fundamental Value remains unchanged",
            "Market Value remains unchanged",
            "Team Utility remains unchanged",
            "Package Adjustment remains a trade-verdict layer",
            "Multi-vs-multi must be representable",
            "Draft picks must be first-class supported assets",
            "Package topology transitions must be continuous",
            "Accepted historical trades must not be treated as zero-adjustment truth",
            "Fresh confirmation evidence is required before any future deployment",
        ],
        "ktc_fixture_fingerprint_sha256": canonical_hash(KTC_FIXTURES),
        "historical_trade_anchor_fingerprint_sha256": canonical_hash(
            HISTORICAL_TRADE_ANCHORS
        ),
    }
    PREREG_JSON.write_text(
        json.dumps(prereg, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    PREREG_MD.write_text(
        """# Package Adjustment V3 — Phase 1 Preregistration

This is a new research cycle, not a continuation of the closed NextGen V2 branch.

## New hypothesis

Replace topology-specific package multipliers with a KTC-style architecture:

1. transform every asset through a nonlinear scarcity/value curve;
2. sum transformed scores on both sides;
3. identify the side with greater scarcity-adjusted value;
4. solve for the hypothetical single asset that would equalize transformed value;
5. convert that missing asset back into normal value to produce a human-readable adjustment.

## Evidence roles

- Five supplied KTC screenshots: development-only numerical/behavioral anchors.
- Eight completed league trades: real-world topology/scope anchors only.
- Prior exact 900-vote dataset: spent evidence; prohibited for V3 fitting, selection, or confirmation.

An accepted historical trade is **not** presumed to be objectively fair.

No production change is authorized.
""",
        encoding="utf-8",
    )
    print("Package Adjustment V3 Phase 1 preregistration frozen")


def current_v16_support_for_ktc_fixture(fixture):
    a = list(map(float, fixture["side_a"]))
    b = list(map(float, fixture["side_b"]))

    if len(a) == 1 and len(b) >= 2:
        target, package = a[0], b
    elif len(b) == 1 and len(a) >= 2:
        target, package = b[0], a
    elif len(a) == 1 and len(b) == 1:
        return False, "one_for_one"
    else:
        return False, "multi_vs_multi"

    if any(v >= target for v in package):
        return False, "package_piece_at_or_above_target"

    meaningful = [v for v in package if v >= target * 0.06]
    if len(meaningful) < 2:
        return False, "effective_one_for_one_after_tiny_filter"
    if len(meaningful) > 3:
        return False, "more_than_three_meaningful_players"

    total = sum(meaningful)
    ordered = sorted(meaningful, reverse=True)

    if len(meaningful) == 2:
        largest = ordered[0] / total
        smallest = ordered[1] / total
        in_v3 = (
            0.5044104156375697 - 1e-12
            <= largest
            <= 0.5230278884462152 + 1e-12
            and 0.4769721115537849 - 1e-12
            <= smallest
            <= 0.49558958436243034 + 1e-12
        )
        in_v5 = (
            largest > 0.5230278884462152 + 1e-12
            and largest <= 0.6 + 1e-12
        )
        if not (in_v3 or in_v5):
            return False, "size2_composition_outside_evidence_supported_envelope"
        return True, "supported_size2"

    largest = ordered[0] / total
    middle = ordered[1] / total
    smallest = ordered[2] / total
    in_v4 = (
        0.41991319353657897 - 1e-12
        <= largest
        <= 0.4696171986399035 + 1e-12
        and 0.30827026434134036 - 1e-12
        <= middle
        <= 0.36725409193118236 + 1e-12
        and 0.2120186203977994 - 1e-12
        <= smallest
        <= 0.2247276896617619 + 1e-12
    )
    if not in_v4:
        return False, "size3_composition_outside_frozen_v4_envelope"
    return True, "supported_size3"


def verify_historical_trade_anchors():
    doc = json.loads(TRADE_HISTORY.read_text(encoding="utf-8"))
    by_id = {
        str(row.get("transaction_id")): row
        for row in (doc.get("trades_with_picks") or [])
    }

    rows = []
    for expected in HISTORICAL_TRADE_ANCHORS:
        tid = expected["transaction_id"]
        trade = by_id.get(tid)
        if trade is None:
            raise RuntimeError(f"Historical trade anchor missing: {tid}")

        sides = trade.get("sides") or []
        if len(sides) != 2:
            raise RuntimeError(f"Historical trade {tid} is not two-sided")

        actual_counts = sorted(
            (
                len(side.get("received_players") or []),
                len(side.get("received_picks") or []),
            )
            for side in sides
        )
        if actual_counts != sorted(expected["side_counts"]):
            raise RuntimeError(
                f"Historical trade count mismatch for {tid}: "
                f"expected={sorted(expected['side_counts'])} "
                f"actual={actual_counts}"
            )

        created = datetime.fromtimestamp(
            int(trade["created"]) / 1000.0,
            tz=timezone.utc,
        ).isoformat()
        if created != expected["created_utc"]:
            raise RuntimeError(
                f"Historical trade timestamp mismatch for {tid}: "
                f"expected={expected['created_utc']} actual={created}"
            )

        total_players = sum(
            len(side.get("received_players") or []) for side in sides
        )
        total_picks = sum(
            len(side.get("received_picks") or []) for side in sides
        )

        # Exact live V1.6 rejects the trade immediately if ANY asset is not a player.
        current_v16_supported = total_picks == 0

        rows.append(
            {
                "trade_number": expected["trade_number"],
                "transaction_id": tid,
                "created_utc": created,
                "shape": expected["shape"],
                "total_players": total_players,
                "total_picks": total_picks,
                "current_v16_supported": current_v16_supported,
                "current_v16_reason": (
                    None if current_v16_supported else "player_only_scope"
                ),
            }
        )

    return rows


def power_score(value: float, gamma: float, max_value: float) -> float:
    if not (0 <= value <= max_value):
        raise ValueError("value outside normalized scale")
    return (value / max_value) ** gamma


def inverse_power_score(score: float, gamma: float, max_value: float):
    if score < 0 or score > 1 + 1e-12:
        return None
    return max_value * (min(1.0, score) ** (1.0 / gamma))


def power_equivalent_adjustment(fixture, gamma: float):
    a = list(map(float, fixture["side_a"]))
    b = list(map(float, fixture["side_b"]))

    score_a = sum(
        power_score(value, gamma, ANCHOR_MAX_VALUE) for value in a
    )
    score_b = sum(
        power_score(value, gamma, ANCHOR_MAX_VALUE) for value in b
    )

    if abs(score_a - score_b) <= 1e-15:
        return {
            "adjusted_side": None,
            "predicted_adjustment": 0.0,
            "equivalent_missing_asset": 0.0,
        }

    adjusted_side = "A" if score_a > score_b else "B"
    missing = inverse_power_score(
        abs(score_a - score_b),
        gamma,
        ANCHOR_MAX_VALUE,
    )
    if missing is None:
        return {
            "adjusted_side": adjusted_side,
            "predicted_adjustment": None,
            "equivalent_missing_asset": None,
        }

    if adjusted_side == "A":
        adjustment = sum(b) + missing - sum(a)
    else:
        adjustment = sum(a) + missing - sum(b)

    return {
        "adjusted_side": adjusted_side,
        "predicted_adjustment": max(0.0, adjustment),
        "equivalent_missing_asset": missing,
    }


def fit_power_baseline():
    best = None

    for i in range(1200, 3501):
        gamma = i / 1000.0
        wrong_side = 0
        errors = []
        rows = []

        for fixture in KTC_FIXTURES:
            pred = power_equivalent_adjustment(fixture, gamma)
            if pred["predicted_adjustment"] is None:
                wrong_side += 100
                errors.append(1e9)
                continue

            side_ok = (
                pred["adjusted_side"]
                == fixture["observed_adjusted_side"]
            )
            wrong_side += int(not side_ok)

            error = abs(
                pred["predicted_adjustment"]
                - fixture["observed_adjustment"]
            )
            errors.append(error)
            rows.append((fixture, pred, error, side_ok))

        objective = (wrong_side, statistics.fmean(errors))
        if best is None or objective < best["objective"]:
            best = {
                "objective": objective,
                "gamma": gamma,
                "mae": objective[1],
                "rows": rows,
            }

    return best


def selftest():
    ktc_support = [
        current_v16_support_for_ktc_fixture(row)[0]
        for row in KTC_FIXTURES
    ]
    assert sum(ktc_support) == 1, ktc_support

    assert len(HISTORICAL_TRADE_ANCHORS) == 8
    assert all(
        sum(picks for _players, picks in row["side_counts"]) > 0
        for row in HISTORICAL_TRADE_ANCHORS
    )

    assert (
        power_score(9000, 2.0, 10000)
        > 2 * power_score(4500, 2.0, 10000)
    )

    for value in (1000, 3000, 5000, 7500, 9999):
        score = power_score(value, 2.0, 10000)
        recovered = inverse_power_score(score, 2.0, 10000)
        assert abs(recovered - value) < 1e-8

    print("Package Adjustment V3 Phase 1 self-test PASS")


def evaluate():
    if not PREREG_JSON.exists() or not PREREG_MD.exists():
        raise RuntimeError("Preregistration must be frozen before evaluation")

    index_text = INDEX.read_text(encoding="utf-8")
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    closeout_text = CLOSEOUT.read_text(encoding="utf-8")

    required_live_markers = [
        "function packageAdjustmentAssessment(){",
        "allAssets.some(a => a.type !== 'player')",
        "reason:'multi_vs_multi'",
        "if(meaningful.length > 3){",
        "largestShareMaxInclusive: 0.6",
    ]
    missing = [
        marker for marker in required_live_markers
        if marker not in index_text
    ]
    if missing:
        raise RuntimeError(f"Live V1.6 markers missing: {missing}")

    if (
        live.get("production_revision")
        != "v1.6-v5-size2-composition-overlay"
    ):
        raise RuntimeError(
            f"Unexpected production revision: "
            f"{live.get('production_revision')}"
        )

    if "research_closed_no_successor_candidate" not in closeout_text:
        raise RuntimeError("NextGen V2 closeout marker missing")
    if (
        "exact 900-vote dataset is spent development evidence"
        not in closeout_text
    ):
        raise RuntimeError("Spent-evidence marker missing")

    historical_rows = verify_historical_trade_anchors()

    current_ktc_rows = []
    for fixture in KTC_FIXTURES:
        supported, reason = current_v16_support_for_ktc_fixture(
            fixture
        )
        current_ktc_rows.append(
            {
                "fixture_id": fixture["id"],
                "shape": fixture["shape"],
                "supported": supported,
                "reason": reason,
            }
        )

    current_ktc_supported = sum(
        row["supported"] for row in current_ktc_rows
    )
    current_real_supported = sum(
        row["current_v16_supported"] for row in historical_rows
    )

    fit = fit_power_baseline()
    fitted_rows = []
    correct_side = 0

    for fixture, pred, error, side_ok in fit["rows"]:
        correct_side += int(side_ok)
        observed = float(fixture["observed_adjustment"])
        fitted_rows.append(
            {
                "fixture_id": fixture["id"],
                "shape": fixture["shape"],
                "observed_adjusted_side": (
                    fixture["observed_adjusted_side"]
                ),
                "predicted_adjusted_side": pred["adjusted_side"],
                "observed_adjustment": observed,
                "predicted_adjustment": round(
                    pred["predicted_adjustment"], 3
                ),
                "absolute_error": round(error, 3),
                "absolute_pct_error": round(
                    100.0 * error / observed, 3
                ),
                "equivalent_missing_asset": round(
                    pred["equivalent_missing_asset"], 3
                ),
            }
        )

    gates = {
        "live_v16_revision_verified": True,
        "old_900_vote_branch_closed_and_spent": True,
        "current_v16_ktc_reference_support_is_one_of_five": (
            current_ktc_supported == 1
        ),
        "all_eight_historical_trade_anchors_verified": (
            len(historical_rows) == 8
        ),
        "current_v16_supports_zero_of_eight_real_trades": (
            current_real_supported == 0
        ),
        "new_architecture_covers_all_five_ktc_topologies": (
            len(fitted_rows) == 5
        ),
        "simple_convex_baseline_gets_all_adjustment_sides_correct": (
            correct_side == 5
        ),
        "production_change_authorized": False,
    }

    hard_pass = (
        gates["live_v16_revision_verified"]
        and gates["old_900_vote_branch_closed_and_spent"]
        and gates["current_v16_ktc_reference_support_is_one_of_five"]
        and gates["all_eight_historical_trade_anchors_verified"]
        and gates["current_v16_supports_zero_of_eight_real_trades"]
        and gates["new_architecture_covers_all_five_ktc_topologies"]
        and gates[
            "simple_convex_baseline_gets_all_adjustment_sides_correct"
        ]
        and gates["production_change_authorized"] is False
    )

    decision = (
        "PASS_V3_PHASE1_ARCHITECTURE_REPLACEMENT_JUSTIFIED"
        if hard_pass
        else "STOP_V3_PHASE1_ARCHITECTURE_AUDIT_FAILURE"
    )

    result = {
        "schema_version": 1,
        "study_id": "package-adjustment-v3-ktc-style",
        "phase": 1,
        "status": "RESEARCH_ONLY_ARCHITECTURE_AUDIT_COMPLETE",
        "decision": decision,
        "production_change_authorized": False,
        "production_revision_observed": live["production_revision"],
        "governance": {
            "old_900_votes_used_for_fit": False,
            "old_900_votes_used_for_selection": False,
            "old_900_votes_used_for_confirmation": False,
            "ktc_examples_are_development_only": True,
            "historical_trades_are_fairness_labels": False,
            "fresh_confirmation_required_before_future_deployment": True,
        },
        "current_v16_ktc_reference_coverage": {
            "supported_fixture_count": current_ktc_supported,
            "total_fixture_count": 5,
            "coverage_pct": round(
                100.0 * current_ktc_supported / 5.0, 2
            ),
            "rows": current_ktc_rows,
        },
        "historical_league_trade_anchors": {
            "purpose": (
                "real-world topology and scope validation; "
                "not numeric fairness labels"
            ),
            "verified_trade_count": len(historical_rows),
            "current_v16_supported_trade_count": current_real_supported,
            "rows": historical_rows,
        },
        "prototype_power_baseline": {
            "purpose": (
                "architecture feasibility only; "
                "not a frozen production candidate"
            ),
            "formula": "score=(asset_value/max_value)^gamma",
            "fit_scope": (
                "five supplied KTC numerical/behavioral anchors only"
            ),
            "best_gamma": fit["gamma"],
            "adjusted_side_accuracy": f"{correct_side}/5",
            "mean_absolute_adjustment_error": round(fit["mae"], 3),
            "rows": fitted_rows,
        },
        "successor_architecture_requirements": {
            "asset_level_nonlinear_scarcity_transform": True,
            "bilateral_all_asset_scoring": True,
            "supports_multi_vs_multi": True,
            "supports_arbitrary_piece_counts_by_construction": True,
            "supports_draft_picks_as_first_class_assets": True,
            "inverse_equivalent_asset_for_display_adjustment": True,
            "fundamental_value_unchanged": True,
            "market_value_unchanged": True,
            "team_utility_unchanged": True,
            "trade_verdict_layer_only": True,
        },
        "phase2_requirements": [
            "Build a small normalized LOG/FV scarcity-curve candidate family.",
            "Treat players and picks as first-class assets in the same bilateral scoring architecture.",
            "Stress-test continuity across 1v2, 1v3, 2v2, 2v3, 3v3, 3v4, 4v6, 5v6, and larger packages.",
            "Require monotonicity: adding a positive-value asset cannot make that side worse.",
            "Require split/merge sanity: equivalent fragmentation must not create discontinuous jumps at arbitrary piece-count boundaries.",
            "Do not use the spent 900-vote dataset for fitting, selection, or confirmation.",
            "Do not treat accepted historical trades as perfectly fair without contemporaneous valuation evidence.",
            "Freeze candidate(s) before generating a fresh confirmation-vote catalog.",
        ],
        "gates": gates,
    }

    OUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Package Adjustment V3 — Phase 1 KTC-Style Architecture Audit",
        "",
        f"**Decision:** `{decision}`",
        "",
        "**Research only. Production is unchanged.**",
        "",
        "## Core finding",
        "",
        f"- Current V1.6 supports only **{current_ktc_supported}/5** supplied KTC reference shapes.",
        f"- Current V1.6 supports **{current_real_supported}/8** supplied real completed league trades.",
        "- Every real completed trade anchor contains at least one draft pick, and V1.6 is player-only.",
        "- The real trade set spans 1v2, 2v2, 3v3, 3v4, 4v6, and 5v6 package shapes.",
        "- A topology-agnostic nonlinear all-asset architecture is therefore required if the model is expected to behave like a general trade calculator.",
        "",
        "## KTC behavioral anchors",
        "",
        f"- Development-only best power gamma: **{fit['gamma']:.3f}**.",
        f"- Correct adjusted side: **{correct_side}/5**.",
        f"- Mean absolute displayed-adjustment error: **{fit['mae']:.1f} KTC points**.",
        "",
        "The power curve is a feasibility baseline only. It is **not** the selected V3 production formula.",
        "",
        "| KTC fixture | Shape | V1.6 supported? | Reason |",
        "|---|---:|---:|---|",
    ]

    for row in current_ktc_rows:
        lines.append(
            f"| `{row['fixture_id']}` | {row['shape']} | "
            f"{'YES' if row['supported'] else 'NO'} | "
            f"`{row['reason']}` |"
        )

    lines += [
        "",
        "## Completed league-trade topology anchors",
        "",
        "| Trade | Date | Shape | Players | Picks | V1.6 |",
        "|---:|---|---:|---:|---:|---|",
    ]

    for row in historical_rows:
        lines.append(
            f"| {row['trade_number']} | "
            f"{row['created_utc'][:10]} | "
            f"{row['shape']} | "
            f"{row['total_players']} | "
            f"{row['total_picks']} | "
            f"{'SUPPORTED' if row['current_v16_supported'] else 'UNSUPPORTED'} |"
        )

    lines += [
        "",
        "These completed trades validate real-world scope/topology only. "
        "They are not treated as mathematically fair or used as zero-adjustment targets.",
        "",
        "## Governance",
        "",
        "- Prior exact 900-vote dataset: **not used**.",
        "- Five KTC screenshots: development-only behavior anchors.",
        "- Eight completed league trades: topology/scope anchors only.",
        "- No production change is authorized.",
        "- A future V3 candidate requires fresh preregistered confirmation evidence.",
        "",
    ]

    OUT_MD.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "study_id": result["study_id"],
        "phase": 1,
        "decision": decision,
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
        ).strip(),
        "input_sha256": {
            "index.html": sha256(INDEX),
            str(LIVE.relative_to(ROOT)): sha256(LIVE),
            str(CLOSEOUT.relative_to(ROOT)): sha256(CLOSEOUT),
            str(TRADE_HISTORY.relative_to(ROOT)): sha256(TRADE_HISTORY),
        },
        "output_sha256": {
            str(PREREG_JSON.relative_to(ROOT)): sha256(PREREG_JSON),
            str(PREREG_MD.relative_to(ROOT)): sha256(PREREG_MD),
            str(OUT_JSON.relative_to(ROOT)): sha256(OUT_JSON),
            str(OUT_MD.relative_to(ROOT)): sha256(OUT_MD),
            str(Path(__file__).resolve().relative_to(ROOT)): sha256(
                Path(__file__).resolve()
            ),
        },
    }

    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "decision": decision,
                "ktc_reference_support_v16": f"{current_ktc_supported}/5",
                "historical_trade_support_v16": f"{current_real_supported}/8",
                "power_baseline_gamma": fit["gamma"],
                "power_baseline_adjusted_side_accuracy": f"{correct_side}/5",
                "power_baseline_mae": round(fit["mae"], 3),
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preregister", action="store_true")
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()

    if args.preregister:
        preregister()
    elif args.selftest:
        selftest()
    else:
        evaluate()


if __name__ == "__main__":
    main()

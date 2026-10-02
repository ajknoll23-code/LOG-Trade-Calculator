#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

PRIMARY_CATEGORIES = {
    "ONE_FOR_TWO_PLAYER_ONLY",
    "ONE_FOR_TWO_WITH_PICK",
    "ONE_FOR_THREE_PLAYER_ONLY",
    "ONE_FOR_THREE_WITH_PICK",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_classifier(path: Path):
    spec = importlib.util.spec_from_file_location(
        "package_structural_classifier_b34d", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import frozen structural classifier")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


def category_rollups(primary_rows):
    counts = Counter(x["category"] for x in primary_rows)
    one_for_two = (
        counts["ONE_FOR_TWO_PLAYER_ONLY"]
        + counts["ONE_FOR_TWO_WITH_PICK"]
    )
    one_for_three = (
        counts["ONE_FOR_THREE_PLAYER_ONLY"]
        + counts["ONE_FOR_THREE_WITH_PICK"]
    )
    player_only = (
        counts["ONE_FOR_TWO_PLAYER_ONLY"]
        + counts["ONE_FOR_THREE_PLAYER_ONLY"]
    )
    with_pick = (
        counts["ONE_FOR_TWO_WITH_PICK"]
        + counts["ONE_FOR_THREE_WITH_PICK"]
    )
    targets = {
        (x.get("clean_metrics") or {})
        .get("singleton_target", {})
        .get("key")
        for x in primary_rows
    }
    targets.discard(None)

    return {
        "future_primary_clean_trade_count": len(primary_rows),
        "one_for_two_count": one_for_two,
        "one_for_three_count": one_for_three,
        "player_only_package_count": player_only,
        "with_pick_package_count": with_pick,
        "distinct_singleton_target_players": len(targets),
        "category_counts": dict(sorted(counts.items())),
        "distinct_singleton_target_keys": sorted(targets),
    }


def maturity_checks(rollups, gate):
    checks = {
        "future_primary_clean_trade_count": (
            rollups["future_primary_clean_trade_count"]
            >= gate["future_primary_clean_trade_count_min"]
        ),
        "one_for_two_count": (
            rollups["one_for_two_count"]
            >= gate["one_for_two_count_min"]
        ),
        "one_for_three_count": (
            rollups["one_for_three_count"]
            >= gate["one_for_three_count_min"]
        ),
        "player_only_package_count": (
            rollups["player_only_package_count"]
            >= gate["player_only_package_count_min"]
        ),
        "with_pick_package_count": (
            rollups["with_pick_package_count"]
            >= gate["with_pick_package_count_min"]
        ),
        "distinct_singleton_target_players": (
            rollups["distinct_singleton_target_players"]
            >= gate["distinct_singleton_target_players_min"]
        ),
    }
    return checks


def build_status(evidence, taxonomy, anchor, classifier):
    assert taxonomy["status"] == (
        "PREREGISTERED_FUTURE_STRUCTURAL_TAXONOMY_RESEARCH_ONLY"
    )
    assert anchor["status"] == "FUTURE_STRUCTURAL_TAXONOMY_FREEZE_ANCHORED"
    assert anchor["existing_development_trades_may_count_future"] is False
    assert taxonomy["maturity_review_gate"][
        "existing_six_count_toward_thresholds"
    ] is False

    cutoff = int(anchor["first_freeze_commit_epoch_ms"])
    old_ids = set(anchor["existing_development_trade_ids"])
    assert len(old_ids) == 6

    post_anchor = []
    post_anchor_numeric = []
    post_anchor_excluded = []
    primary_rows = []
    track_only_rows = []

    for tid, trade in sorted(
        evidence["trades"].items(),
        key=lambda kv: kv[1].get("created_epoch_ms") or 0,
    ):
        created = int(trade.get("created_epoch_ms") or 0)

        if tid in old_ids:
            if created > cutoff:
                raise RuntimeError(
                    f"development trade unexpectedly after cutoff: {tid}"
                )
            continue

        if created <= cutoff:
            # Any pre-anchor non-development trade remains outside the future sample.
            continue

        post_anchor.append(tid)

        if not trade.get("eligible_for_numeric_package_research"):
            post_anchor_excluded.append({
                "transaction_id": tid,
                "created_at_utc": trade.get("created_at_utc"),
                "reason": trade.get("exclusion_reason"),
            })
            continue

        pre = trade.get("pretrade_snapshot") or {}
        age = pre.get("age_hours_at_trade")
        if age is None or float(age) <= 0:
            raise RuntimeError(
                f"future eligible trade lacks strictly pre-trade snapshot: {tid}"
            )

        classified = classifier.classify_trade(trade)
        post_anchor_numeric.append(tid)

        if classified["category"] in PRIMARY_CATEGORIES:
            if not classified["primary_clean_consolidation"]:
                raise RuntimeError(
                    f"category/primary disagreement for future trade {tid}"
                )
            primary_rows.append(classified)
        else:
            if classified["primary_clean_consolidation"]:
                raise RuntimeError(
                    f"track-only category marked primary for future trade {tid}"
                )
            track_only_rows.append(classified)

    rollups = category_rollups(primary_rows)
    gate = taxonomy["maturity_review_gate"]
    checks = maturity_checks(rollups, gate)
    mature = all(checks.values())

    progress = {
        "future_primary_clean_trade_count": {
            "current": rollups["future_primary_clean_trade_count"],
            "required": gate["future_primary_clean_trade_count_min"],
        },
        "one_for_two_count": {
            "current": rollups["one_for_two_count"],
            "required": gate["one_for_two_count_min"],
        },
        "one_for_three_count": {
            "current": rollups["one_for_three_count"],
            "required": gate["one_for_three_count_min"],
        },
        "player_only_package_count": {
            "current": rollups["player_only_package_count"],
            "required": gate["player_only_package_count_min"],
        },
        "with_pick_package_count": {
            "current": rollups["with_pick_package_count"],
            "required": gate["with_pick_package_count_min"],
        },
        "distinct_singleton_target_players": {
            "current": rollups["distinct_singleton_target_players"],
            "required": gate["distinct_singleton_target_players_min"],
        },
    }

    return {
        "schema_version": 1,
        "study_id": "package-adjustment-v1",
        "phase": "B34D-future-structural-maturity-monitor",
        "status": (
            "MATURE_ARCHITECTURE_REVIEW_ONLY"
            if mature
            else "WAITING_FOR_FUTURE_CLEAN_TRADES"
        ),
        "governance": {
            "taxonomy_frozen": True,
            "cutover_commit_sha": anchor["first_freeze_commit_sha"],
            "cutover_commit_epoch_ms": cutoff,
            "existing_six_counted": False,
            "lambda_fit_performed": False,
            "conditional_model_fit_performed": False,
            "production_authorized": False,
            "package_formula_change_authorized": False,
            "v8_voting_unchanged": True,
            "shadow_v2_unchanged": True,
        },
        "source_counts": {
            "total_logged_trades": evidence["counts"]["trade_count"],
            "total_numeric_eligible_trades": evidence["counts"][
                "eligible_numeric_trade_count"
            ],
            "post_anchor_trade_count": len(post_anchor),
            "post_anchor_numeric_trade_count": len(post_anchor_numeric),
            "post_anchor_excluded_trade_count": len(post_anchor_excluded),
            "post_anchor_track_only_count": len(track_only_rows),
            "post_anchor_primary_clean_count": len(primary_rows),
        },
        "maturity": {
            "all_requirements_met": mature,
            "checks": checks,
            "progress": progress,
            "passing_gate_authorizes": gate["passing_gate_authorizes"],
        },
        "primary_rollups": rollups,
        "future_primary_trades": primary_rows,
        "future_track_only_trades": track_only_rows,
        "future_excluded_trades": post_anchor_excluded,
        "next": {
            "if_not_mature": (
                "continue prospective capture without fitting or production changes"
            ),
            "if_mature": (
                "architecture/modeling review only; preregister candidate conditional "
                "model and reserve later unopened future trades as holdout before fitting"
            ),
        },
    }


def write_report(status, path: Path):
    m = status["maturity"]
    p = m["progress"]

    lines = [
        "# Package Trade Evidence — Future Structural Maturity Monitor",
        "",
        f"**Status:** `{status['status']}`",
        "",
        "Existing six development trades do not count.",
        "",
        "## Progress",
        "",
    ]

    labels = [
        ("future_primary_clean_trade_count", "Future clean trades"),
        ("one_for_two_count", "1-for-2"),
        ("one_for_three_count", "1-for-3"),
        ("player_only_package_count", "Player-only packages"),
        ("with_pick_package_count", "Pick-containing packages"),
        (
            "distinct_singleton_target_players",
            "Distinct singleton target players",
        ),
    ]
    for key, label in labels:
        row = p[key]
        lines.append(
            f"- {label}: `{row['current']} / {row['required']}`"
        )

    lines += [
        "",
        f"- All maturity requirements met: `{m['all_requirements_met']}`",
        "",
        "## Governance",
        "",
        "- No lambda is fit.",
        "- No conditional package model is fit.",
        "- No production change is authorized.",
        "- V8 voting and Shadow V2 remain unchanged.",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def selftest():
    roll = {
        "future_primary_clean_trade_count": 12,
        "one_for_two_count": 6,
        "one_for_three_count": 6,
        "player_only_package_count": 6,
        "with_pick_package_count": 6,
        "distinct_singleton_target_players": 8,
    }
    gate = {
        "future_primary_clean_trade_count_min": 12,
        "one_for_two_count_min": 3,
        "one_for_three_count_min": 3,
        "player_only_package_count_min": 3,
        "with_pick_package_count_min": 3,
        "distinct_singleton_target_players_min": 6,
    }
    assert all(maturity_checks(roll, gate).values())

    roll["with_pick_package_count"] = 2
    checks = maturity_checks(roll, gate)
    assert checks["with_pick_package_count"] is False
    assert not all(checks.values())

    print("PASS: B34D maturity monitor synthetic selftest")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--evidence")
    ap.add_argument("--taxonomy")
    ap.add_argument("--anchor")
    ap.add_argument("--classifier")
    ap.add_argument("--out")
    ap.add_argument("--report")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    for name in (
        "evidence", "taxonomy", "anchor", "classifier", "out", "report"
    ):
        if getattr(args, name) is None:
            ap.error(f"--{name} is required")

    evidence = load_json(Path(args.evidence))
    taxonomy = load_json(Path(args.taxonomy))
    anchor = load_json(Path(args.anchor))
    classifier = load_classifier(Path(args.classifier))

    assert evidence["status"] == "research_only_prospective_trade_evidence"
    assert evidence["consumer_changed"] is False

    status = build_status(evidence, taxonomy, anchor, classifier)

    Path(args.out).write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(status, Path(args.report))

    print(json.dumps({
        "status": status["status"],
        "source_counts": status["source_counts"],
        "maturity": status["maturity"]["progress"],
        "all_requirements_met": status["maturity"]["all_requirements_met"],
        "production_authorized": False,
        "lambda_fit_performed": False,
    }, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
import ktc_pipeline

CHALLENGES = ROOT / "research/package-adjustment-v5/package_vote_challenges_v5.json"
RELEASE = ROOT / "research/package-adjustment-v5/release_manifest.json"
OUT_JSON = ROOT / "research/package-adjustment-v5/package_vote_v5_results.json"
OUT_MD = ROOT / "research/package-adjustment-v5/package_vote_v5_results.md"

PREFIX = "__pkgv5__|"
META_PREFIX = "__pkgv5_meta__|"
SCHEMA_MARKER = "__pkgv5_schema__|5"

MAX_VOTES_PER_VOTER_PER_DAY = 20
VOTER_EFFECTIVE_LIFETIME_CAP = 30.0

MIN_VOTES = 500
MIN_VOTERS = 12
MIN_CHALLENGES = 180
MIN_TARGETS = 14
MIN_EACH_CHOICE = 75
MIN_VOTES_PER_COMPOSITION = 50
MIN_VOTES_PER_COMPOSITION_RATIO_CELL = 10


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def fetch_rows():
    r = requests.get(ktc_pipeline.SHEET_CSV_URL, timeout=30)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))


def is_package_v5_row(row):
    return str(row.get("keep") or "").startswith(PREFIX)


def parse_row(row):
    parts = str(row.get("keep") or "").split("|")
    if len(parts) != 3 or parts[0] != "__pkgv5__" or parts[2] not in {"T", "P"}:
        return None
    meta = str(row.get("trade") or "")
    left = meta[len(META_PREFIX):] if meta.startswith(META_PREFIX) else None
    if left not in {"T", "P"}:
        left = None
    if str(row.get("cut") or "") != SCHEMA_MARKER:
        return None
    return {
        "timestamp": row.get("timestamp") or "",
        "voter_roster_id": str(row.get("voter_roster_id") or ""),
        "challenge_id": parts[1],
        "choice": parts[2],
        "left_canonical_side": left,
    }


def filter_after_release(rows, release):
    cutoff = parse_timestamp_utc(release["released_at_utc"])
    if cutoff is None:
        raise RuntimeError("invalid V5 release timestamp")
    kept = []
    pre = 0
    invalid = 0
    for row in rows:
        ts = parse_timestamp_utc(row.get("timestamp"))
        if ts is None:
            invalid += 1
            continue
        if ts <= cutoff:
            pre += 1
            continue
        kept.append(row)
    return kept, pre, invalid


def apply_daily_cap(rows):
    rows = sorted(
        rows,
        key=lambda r: (str(r.get("timestamp") or ""), str(r.get("voter_roster_id") or "")),
    )
    counts = defaultdict(int)
    kept = []
    dropped = 0
    for row in rows:
        day = str(row.get("timestamp") or "")[:10]
        voter = str(row.get("voter_roster_id") or "")
        if not day or not voter:
            continue
        key = (voter, day)
        if counts[key] >= MAX_VOTES_PER_VOTER_PER_DAY:
            dropped += 1
            continue
        counts[key] += 1
        kept.append(row)
    return kept, dropped


def voter_weights(rows):
    counts = defaultdict(int)
    for row in rows:
        counts[row["voter_roster_id"]] += 1
    return {
        voter: {
            "raw_votes": count,
            "ballot_weight": min(1.0, VOTER_EFFECTIVE_LIFETIME_CAP / count),
            "effective_votes": min(float(count), VOTER_EFFECTIVE_LIFETIME_CAP),
        }
        for voter, count in counts.items()
    }


def weighted_choice_pct(rows, weights):
    if not rows:
        return None
    package = 0.0
    total = 0.0
    for row in rows:
        w = float(weights[row["voter_roster_id"]]["ballot_weight"])
        total += w
        if row["choice"] == "P":
            package += w
    return None if total <= 0 else 100.0 * package / total


def summarize(rows, doc):
    catalog = {c["id"]: c for c in doc["challenges"]}
    valid = [r for r in rows if r["challenge_id"] in catalog]
    unknown = len(rows) - len(valid)
    weights = voter_weights(valid)

    package_votes = sum(r["choice"] == "P" for r in valid)
    target_votes = sum(r["choice"] == "T" for r in valid)
    distinct_challenges = len({r["challenge_id"] for r in valid})
    distinct_targets = len({
        catalog[r["challenge_id"]]["target"]["key"] for r in valid
    })

    left_known = [r for r in valid if r["left_canonical_side"] in {"T", "P"}]
    left_rate = (
        100.0 * sum(r["choice"] == r["left_canonical_side"] for r in left_known) / len(left_known)
        if left_known else None
    )

    compositions = list(doc["design"]["composition_labels"])
    by_composition = {}
    by_composition_ratio = {}

    for label in compositions:
        ids = {
            c["id"] for c in catalog.values()
            if c["composition_target"]["label"] == label
        }
        sub = [r for r in valid if r["challenge_id"] in ids]
        raw_p = sum(r["choice"] == "P" for r in sub)
        by_composition[label] = {
            "votes": len(sub),
            "package_choice_pct": round(100.0 * raw_p / len(sub), 2) if sub else None,
            "weighted_package_choice_pct": (
                round(weighted_choice_pct(sub, weights), 2) if sub else None
            ),
            "distinct_challenges": len({r["challenge_id"] for r in sub}),
            "distinct_targets": len({
                catalog[r["challenge_id"]]["target"]["key"] for r in sub
            }),
        }

        ratios = sorted({
            float(c["ratio_target"]) for c in catalog.values()
            if c["composition_target"]["label"] == label
        })
        cells = {}
        for ratio in ratios:
            cell_ids = {
                c["id"] for c in catalog.values()
                if c["composition_target"]["label"] == label
                and abs(float(c["ratio_target"]) - ratio) < 1e-9
            }
            cell_rows = [r for r in valid if r["challenge_id"] in cell_ids]
            raw_cp = sum(r["choice"] == "P" for r in cell_rows)
            cells[f"{ratio:.2f}"] = {
                "votes": len(cell_rows),
                "package_choice_pct": (
                    round(100.0 * raw_cp / len(cell_rows), 2) if cell_rows else None
                ),
                "weighted_package_choice_pct": (
                    round(weighted_choice_pct(cell_rows, weights), 2) if cell_rows else None
                ),
                "distinct_targets": len({
                    catalog[r["challenge_id"]]["target"]["key"]
                    for r in cell_rows
                }),
            }
        by_composition_ratio[label] = cells

    composition_coverage = all(
        by_composition[label]["votes"] >= MIN_VOTES_PER_COMPOSITION
        for label in compositions
    )
    cell_coverage = all(
        row["votes"] >= MIN_VOTES_PER_COMPOSITION_RATIO_CELL
        for cells in by_composition_ratio.values()
        for row in cells.values()
    )

    gates = {
        "counted_votes": len(valid) >= MIN_VOTES,
        "unique_voters": len(weights) >= MIN_VOTERS,
        "distinct_challenges": distinct_challenges >= MIN_CHALLENGES,
        "distinct_targets": distinct_targets >= MIN_TARGETS,
        "choice_mix": package_votes >= MIN_EACH_CHOICE and target_votes >= MIN_EACH_CHOICE,
        "composition_coverage": composition_coverage,
        "composition_ratio_cell_coverage": cell_coverage,
    }

    return {
        "raw_vote_count": len(valid),
        "unknown_challenge_rows": unknown,
        "unique_voters": len(weights),
        "distinct_challenges": distinct_challenges,
        "distinct_targets": distinct_targets,
        "package_votes": package_votes,
        "target_votes": target_votes,
        "package_choice_pct": (
            round(100.0 * package_votes / len(valid), 2) if valid else None
        ),
        "weighted_package_choice_pct": (
            round(weighted_choice_pct(valid, weights), 2) if valid else None
        ),
        "display_left_choice_pct": round(left_rate, 2) if left_rate is not None else None,
        "by_composition": by_composition,
        "by_composition_and_ratio": by_composition_ratio,
        "voter_weights": weights,
        "diagnostic_data_gates": {
            "thresholds": {
                "counted_votes": MIN_VOTES,
                "unique_voters": MIN_VOTERS,
                "distinct_challenges": MIN_CHALLENGES,
                "distinct_targets": MIN_TARGETS,
                "minimum_each_choice": MIN_EACH_CHOICE,
                "minimum_votes_per_composition": MIN_VOTES_PER_COMPOSITION,
                "minimum_votes_per_composition_ratio_cell": MIN_VOTES_PER_COMPOSITION_RATIO_CELL,
            },
            "passed": gates,
            "all_passed": all(gates.values()),
        },
    }


def write_report(result):
    s = result["summary"]
    lines = [
        "# Package Preference Voting V5 — Two-Player Composition Expansion",
        "",
        "**Status: RESEARCH ONLY — production V1.5 is unchanged.**",
        "",
        f"- Counted V5 votes: `{s['raw_vote_count']}`",
        f"- Unique V5 voters: `{s['unique_voters']}`",
        f"- Distinct challenges: `{s['distinct_challenges']}`",
        f"- Distinct targets: `{s['distinct_targets']}`",
        f"- Overall package choice rate: `{s['package_choice_pct']}`",
        f"- Voter-capped weighted package choice rate: `{s['weighted_package_choice_pct']}`",
        f"- Display-left choice rate: `{s['display_left_choice_pct']}`",
        "",
        "## By two-player composition",
        "",
        "| Composition | Votes | Package chosen | Weighted package chosen |",
        "|---:|---:|---:|---:|",
    ]
    for label, row in s["by_composition"].items():
        raw = "n/a" if row["package_choice_pct"] is None else f"{row['package_choice_pct']:.1f}%"
        weighted = (
            "n/a" if row["weighted_package_choice_pct"] is None
            else f"{row['weighted_package_choice_pct']:.1f}%"
        )
        lines.append(f"| {label} | {row['votes']} | {raw} | {weighted} |")

    lines += ["", "## Composition × ratio cells", ""]
    for label, cells in s["by_composition_and_ratio"].items():
        lines += [
            f"### {label}",
            "",
            "| Ratio | Votes | Package chosen | Weighted package chosen |",
            "|---:|---:|---:|---:|",
        ]
        for ratio, row in cells.items():
            raw = "n/a" if row["package_choice_pct"] is None else f"{row['package_choice_pct']:.1f}%"
            weighted = (
                "n/a" if row["weighted_package_choice_pct"] is None
                else f"{row['weighted_package_choice_pct']:.1f}%"
            )
            lines.append(f"| {ratio} | {row['votes']} | {raw} | {weighted} |")
        lines.append("")

    lines += [
        "## Diagnostic gates",
        "",
        f"- All passed: `{s['diagnostic_data_gates']['all_passed']}`",
    ]
    for key, passed in s["diagnostic_data_gates"]["passed"].items():
        lines.append(f"- {key}: `{passed}`")

    lines += [
        "",
        "## Isolation",
        "",
        "- V5 is two-player composition research only.",
        "- V3 and V4 remain frozen.",
        "- V5 does not alter Fundamental Value, Market Value, Team Utility, draft-pick values, or the live Package Adjustment formula.",
        "- No automatic production change is allowed from these results.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def selftest():
    assert is_package_v5_row({"keep":"__pkgv5__|abc|P"})
    assert not is_package_v5_row({"keep":"__pkgv4__|abc|P"})
    parsed = parse_row({
        "timestamp":"2026-09-09T00:00:00Z",
        "voter_roster_id":"ext_x",
        "keep":"__pkgv5__|abc|T",
        "trade":"__pkgv5_meta__|P",
        "cut":"__pkgv5_schema__|5",
    })
    assert parsed is not None
    assert parsed["challenge_id"] == "abc"
    assert parsed["choice"] == "T"
    assert parsed["left_canonical_side"] == "P"

    release = {"released_at_utc":"2026-09-09T00:00:00+00:00"}
    rows = [
        {"timestamp":"2026-09-08T23:59:59Z"},
        {"timestamp":"2026-09-09T00:00:00Z"},
        {"timestamp":"2026-09-09T00:00:01Z"},
        {"timestamp":"bad"},
    ]
    kept, pre, invalid = filter_after_release(rows, release)
    assert len(kept) == 1 and pre == 2 and invalid == 1

    caprows = [{
        "timestamp":"2026-09-09T01:00:00Z",
        "voter_roster_id":"ext_x",
        "challenge_id":f"x{i}",
        "choice":"P",
        "left_canonical_side":"P",
    } for i in range(25)]
    capped, dropped = apply_daily_cap(caprows)
    assert len(capped) == 20 and dropped == 5
    print("Package Preference V5 pipeline self-test passed.")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    doc = read_json(CHALLENGES)
    release = read_json(RELEASE)

    if doc.get("status") != "frozen_package_preference_v5" or doc.get("frozen") is not True:
        raise RuntimeError("unexpected/unfrozen V5 challenge catalog")
    if release.get("status") != "package_adjustment_v5_composition_vote_release":
        raise RuntimeError("unexpected V5 release manifest")
    if release.get("frozen") is not True:
        raise RuntimeError("V5 release manifest must be frozen")
    if release.get("production_formula_changed") is not False:
        raise RuntimeError("V5 release manifest must not change production")

    raw = [parse_row(r) for r in fetch_rows() if is_package_v5_row(r)]
    raw = [r for r in raw if r is not None]
    source_raw_package_rows = len(raw)

    post, pre, invalid = filter_after_release(raw, release)
    capped, dropped = apply_daily_cap(post)
    summary = summarize(capped, doc)

    result = {
        "schema_version": 5,
        "status": "research_only",
        "consumer_changed": False,
        "market_value_consumer_changed": False,
        "fundamental_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "trade_verdict_consumer_changed": False,
        "production_formula_enabled": False,
        "automatic_production_change_allowed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "transport": "existing KTC Google Sheet via reserved __pkgv5__ rows",
        "release_id": release["release_id"],
        "released_at_utc": release["released_at_utc"],
        "package_daily_cap_per_voter": MAX_VOTES_PER_VOTER_PER_DAY,
        "voter_effective_lifetime_cap": VOTER_EFFECTIVE_LIFETIME_CAP,
        "source_raw_package_rows": source_raw_package_rows,
        "pre_release_rows_excluded": pre,
        "invalid_timestamp_rows_excluded": invalid,
        "post_release_rows": len(post),
        "daily_cap_dropped": dropped,
        "summary": summary,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(result)

    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    print("V5 votes counted:", summary["raw_vote_count"])
    print("V5 maturity gates:", summary["diagnostic_data_gates"]["all_passed"])


if __name__ == "__main__":
    main()


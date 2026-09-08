#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
import ktc_pipeline

CHALLENGES = ROOT / "research" / "package-adjustment-v2" / "package_vote_challenges_v2.json"
OUT_JSON = ROOT / "research" / "package-adjustment-v2" / "package_vote_v2_results.json"
OUT_MD = ROOT / "research" / "package-adjustment-v2" / "package_vote_v2_results.md"

PREFIX = "__pkgv2__|"
META_PREFIX = "__pkgv2_meta__|"
SCHEMA_PREFIX = "__pkgv2_schema__|"

MAX_VOTES_PER_VOTER_PER_DAY = 10
VOTER_EFFECTIVE_LIFETIME_CAP = 30.0

MIN_VOTES = 120
MIN_VOTERS = 10
MIN_CHALLENGES = 60
MIN_MATCHED_PAIRS_WITH_BOTH_SIZES = 20
MIN_EACH_CHOICE = 20


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_rows():
    r = requests.get(ktc_pipeline.SHEET_CSV_URL, timeout=30)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))


def is_package_v2_row(row):
    return str(row.get("keep") or "").startswith(PREFIX)


def parse_row(row):
    parts = str(row.get("keep") or "").split("|")
    if len(parts) != 3 or parts[0] != "__pkgv2__" or parts[2] not in {"T", "P"}:
        return None
    meta = str(row.get("trade") or "")
    left = meta[len(META_PREFIX):] if meta.startswith(META_PREFIX) else None
    if left not in {"T", "P"}:
        left = None
    if str(row.get("cut") or "") != "__pkgv2_schema__|2":
        return None
    return {
        "timestamp": row.get("timestamp") or "",
        "voter_roster_id": str(row.get("voter_roster_id") or ""),
        "challenge_id": parts[1],
        "choice": parts[2],
        "left_canonical_side": left,
    }


def apply_daily_cap(rows):
    counts = defaultdict(int)
    kept, dropped = [], 0
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


def summarize(rows, doc):
    catalog = {c["id"]: c for c in doc["challenges"]}
    valid = [r for r in rows if r["challenge_id"] in catalog]
    weights = voter_weights(valid)

    package_votes = sum(r["choice"] == "P" for r in valid)
    target_votes = sum(r["choice"] == "T" for r in valid)
    distinct = len({r["challenge_id"] for r in valid})

    left_known = [r for r in valid if r["left_canonical_side"] in {"T", "P"}]
    left_rate = (
        100.0 * sum(r["choice"] == r["left_canonical_side"] for r in left_known) / len(left_known)
        if left_known else None
    )

    by_size = {}
    for size in doc["design"]["package_sizes"]:
        ids = {c["id"] for c in doc["challenges"] if int(c["package_size"]) == int(size)}
        sub = [r for r in valid if r["challenge_id"] in ids]
        p = sum(r["choice"] == "P" for r in sub)
        by_size[str(size)] = {
            "votes": len(sub),
            "package_choice_pct": round(100.0 * p / len(sub), 2) if sub else None,
        }

    by_ratio = {}
    for rt in doc["design"]["ratio_targets"]:
        ids = {
            c["id"] for c in doc["challenges"]
            if abs(float(c["ratio_target"]) - float(rt)) < 1e-9
        }
        sub = [r for r in valid if r["challenge_id"] in ids]
        p = sum(r["choice"] == "P" for r in sub)
        by_ratio[f"{float(rt):.2f}"] = {
            "votes": len(sub),
            "package_choice_pct": round(100.0 * p / len(sub), 2) if sub else None,
        }

    by_position = {}
    for pos in doc["design"]["target_positions"]:
        ids = {c["id"] for c in doc["challenges"] if c["target"]["pos"] == pos}
        sub = [r for r in valid if r["challenge_id"] in ids]
        p = sum(r["choice"] == "P" for r in sub)
        by_position[pos] = {
            "votes": len(sub),
            "package_choice_pct": round(100.0 * p / len(sub), 2) if sub else None,
        }

    challenge_vote_counts = defaultdict(int)
    for r in valid:
        challenge_vote_counts[r["challenge_id"]] += 1

    pair_status = {}
    for pair_id in sorted({c["matched_pair_id"] for c in doc["challenges"]}):
        pair = [c for c in doc["challenges"] if c["matched_pair_id"] == pair_id]
        size_ids = {int(c["package_size"]): c["id"] for c in pair}
        n2 = challenge_vote_counts.get(size_ids.get(2, ""), 0)
        n3 = challenge_vote_counts.get(size_ids.get(3, ""), 0)
        pair_status[pair_id] = {
            "two_player_votes": n2,
            "three_player_votes": n3,
            "both_sizes_observed": n2 > 0 and n3 > 0,
        }

    matched_pairs_both = sum(row["both_sizes_observed"] for row in pair_status.values())

    gates = {
        "counted_votes": len(valid) >= MIN_VOTES,
        "unique_voters": len(weights) >= MIN_VOTERS,
        "distinct_challenges": distinct >= MIN_CHALLENGES,
        "matched_pairs_with_both_sizes": matched_pairs_both >= MIN_MATCHED_PAIRS_WITH_BOTH_SIZES,
        "choice_mix": package_votes >= MIN_EACH_CHOICE and target_votes >= MIN_EACH_CHOICE,
    }

    return {
        "raw_vote_count": len(valid),
        "unique_voters": len(weights),
        "distinct_challenges": distinct,
        "package_votes": package_votes,
        "target_votes": target_votes,
        "package_choice_pct": round(100.0 * package_votes / len(valid), 2) if valid else None,
        "display_left_choice_pct": round(left_rate, 2) if left_rate is not None else None,
        "by_package_size": by_size,
        "by_ratio_target": by_ratio,
        "by_target_position": by_position,
        "matched_pair_coverage": {
            "matched_pairs_total": len(pair_status),
            "matched_pairs_with_both_sizes_observed": matched_pairs_both,
            "pair_status": pair_status,
        },
        "voter_weights": weights,
        "diagnostic_data_gates": {
            "thresholds": {
                "counted_votes": MIN_VOTES,
                "unique_voters": MIN_VOTERS,
                "distinct_challenges": MIN_CHALLENGES,
                "matched_pairs_with_both_sizes": MIN_MATCHED_PAIRS_WITH_BOTH_SIZES,
                "minimum_each_choice": MIN_EACH_CHOICE,
            },
            "passed": gates,
            "all_passed": all(gates.values()),
        },
    }


def write_report(result):
    s = result["summary"]
    lines = [
        "# Package Preference Voting V2",
        "",
        "**Status: RESEARCH ONLY — no production consumer changed.**",
        "",
        "V2 is a frozen matched-secondary-split design: each matched pair compares "
        "`[A, B]` against `[A, C, D]` around the same target and raw FV ratio.",
        "",
        f"- Counted package votes: `{s['raw_vote_count']}`",
        f"- Unique voters: `{s['unique_voters']}`",
        f"- Distinct challenges: `{s['distinct_challenges']}`",
        f"- Package choice rate: `{s['package_choice_pct']}`",
        f"- Display-left choice rate: `{s['display_left_choice_pct']}`",
        f"- Matched pairs with both sizes observed: "
        f"`{s['matched_pair_coverage']['matched_pairs_with_both_sizes_observed']}` / "
        f"`{s['matched_pair_coverage']['matched_pairs_total']}`",
        "",
        "## By package size",
        "",
        "| Size | Votes | Package chosen |",
        "|---:|---:|---:|",
    ]
    for size, row in s["by_package_size"].items():
        pct = "n/a" if row["package_choice_pct"] is None else f"{row['package_choice_pct']:.1f}%"
        lines.append(f"| {size} | {row['votes']} | {pct} |")

    lines += [
        "",
        "## By raw package / target FV ratio",
        "",
        "| Ratio | Votes | Package chosen |",
        "|---:|---:|---:|",
    ]
    for ratio, row in s["by_ratio_target"].items():
        pct = "n/a" if row["package_choice_pct"] is None else f"{row['package_choice_pct']:.1f}%"
        lines.append(f"| {ratio} | {row['votes']} | {pct} |")

    lines += [
        "",
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
        "- V2 rows use reserved `__pkgv2__` transport markers.",
        "- V1 remains frozen and analytically separate.",
        "- V2 package votes do not alter KTC, Market Value, Fundamental Value, Team Utility, or the live trade verdict.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def selftest():
    assert is_package_v2_row({"keep": "__pkgv2__|abc|P"})
    assert not is_package_v2_row({"keep": "__pkgv1__|abc|P"})
    parsed = parse_row({
        "timestamp": "2026-09-08T00:00:00Z",
        "voter_roster_id": "ext_x",
        "keep": "__pkgv2__|abc|T",
        "trade": "__pkgv2_meta__|P",
        "cut": "__pkgv2_schema__|2",
    })
    assert parsed["challenge_id"] == "abc"
    assert parsed["choice"] == "T"
    assert parsed["left_canonical_side"] == "P"

    rows = [{
        "timestamp": "2026-09-08T00:00:00Z",
        "voter_roster_id": "ext_x",
        "challenge_id": f"x{i}",
        "choice": "P",
        "left_canonical_side": "P",
    } for i in range(15)]
    capped, dropped = apply_daily_cap(rows)
    assert len(capped) == 10 and dropped == 5
    print("Package Preference V2 pipeline self-test passed.")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    doc = read_json(CHALLENGES)
    if doc.get("status") != "frozen_package_preference_v2" or doc.get("frozen") is not True:
        raise RuntimeError("unexpected/unfrozen V2 challenge catalog")

    raw = [parse_row(r) for r in fetch_rows() if is_package_v2_row(r)]
    raw = [r for r in raw if r is not None]
    capped, dropped = apply_daily_cap(raw)
    summary = summarize(capped, doc)

    result = {
        "schema_version": 2,
        "status": "research_only",
        "consumer_changed": False,
        "market_value_consumer_changed": False,
        "fundamental_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "transport": "existing KTC Google Sheet via reserved __pkgv2__ rows",
        "package_daily_cap_per_voter": MAX_VOTES_PER_VOTER_PER_DAY,
        "voter_effective_lifetime_cap": VOTER_EFFECTIVE_LIFETIME_CAP,
        "raw_package_rows": len(raw),
        "daily_cap_dropped": dropped,
        "summary": summary,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(result)
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

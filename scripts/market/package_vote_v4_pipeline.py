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
import package_vote_phase

CHALLENGES = ROOT / "research" / "package-adjustment-v4" / "package_vote_challenges_v4.json"
OUT_JSON = ROOT / "research" / "package-adjustment-v4" / "package_vote_v4_results.json"
OUT_MD = ROOT / "research" / "package-adjustment-v4" / "package_vote_v4_results.md"

PREFIX = "__pkgv4__|"
META_PREFIX = "__pkgv4_meta__|"
SCHEMA_MARKER = "__pkgv4_schema__|4"

MAX_VOTES_PER_VOTER_PER_DAY = 20
VOTER_EFFECTIVE_LIFETIME_CAP = 30.0

MIN_VOTES = 200
MIN_VOTERS = 15
MIN_CHALLENGES = 70
MIN_TARGETS = 14
MIN_EACH_CHOICE = 30
MIN_VOTES_PER_RATIO_BUCKET = 25

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def fetch_rows():
    r = requests.get(ktc_pipeline.SHEET_CSV_URL, timeout=30)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))

def is_package_v4_row(row):
    return str(row.get("keep") or "").startswith(PREFIX)

def parse_row(row):
    parts = str(row.get("keep") or "").split("|")
    if len(parts) != 3 or parts[0] != "__pkgv4__" or parts[2] not in {"T", "P"}:
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
    distinct_challenges = len({r["challenge_id"] for r in valid})
    distinct_targets = len({catalog[r["challenge_id"]]["target"]["key"] for r in valid})

    left_known = [r for r in valid if r["left_canonical_side"] in {"T", "P"}]
    left_rate = (
        100.0 * sum(r["choice"] == r["left_canonical_side"] for r in left_known) / len(left_known)
        if left_known else None
    )

    ratios = [float(x) for x in doc["design"]["ratio_targets"]]
    by_ratio = {}
    for ratio in ratios:
        ids = {
            c["id"] for c in catalog.values()
            if abs(float(c["ratio_target"]) - ratio) < 1e-9
        }
        sub = [r for r in valid if r["challenge_id"] in ids]
        p = sum(r["choice"] == "P" for r in sub)
        by_ratio[f"{ratio:.2f}"] = {
            "votes": len(sub),
            "package_choice_pct": round(100.0 * p / len(sub), 2) if sub else None,
        }

    by_tier = {}
    tiers = sorted({str(c.get("target_tier") or "unknown") for c in catalog.values()})
    for tier in tiers:
        ids = {c["id"] for c in catalog.values() if str(c.get("target_tier") or "unknown") == tier}
        sub = [r for r in valid if r["challenge_id"] in ids]
        p = sum(r["choice"] == "P" for r in sub)
        by_tier[tier] = {
            "votes": len(sub),
            "package_choice_pct": round(100.0 * p / len(sub), 2) if sub else None,
        }

    ratio_coverage = all(
        by_ratio[f"{r:.2f}"]["votes"] >= MIN_VOTES_PER_RATIO_BUCKET for r in ratios
    )

    gates = {
        "counted_votes": len(valid) >= MIN_VOTES,
        "unique_voters": len(weights) >= MIN_VOTERS,
        "distinct_challenges": distinct_challenges >= MIN_CHALLENGES,
        "distinct_targets": distinct_targets >= MIN_TARGETS,
        "choice_mix": package_votes >= MIN_EACH_CHOICE and target_votes >= MIN_EACH_CHOICE,
        "ratio_bucket_coverage": ratio_coverage,
    }

    low_key = f"{min(ratios):.2f}"
    high_key = f"{max(ratios):.2f}"
    low_pct = by_ratio[low_key]["package_choice_pct"]
    high_pct = by_ratio[high_key]["package_choice_pct"]

    return {
        "raw_vote_count": len(valid),
        "unique_voters": len(weights),
        "distinct_challenges": distinct_challenges,
        "distinct_targets": distinct_targets,
        "package_votes": package_votes,
        "target_votes": target_votes,
        "package_choice_pct": round(100.0 * package_votes / len(valid), 2) if valid else None,
        "display_left_choice_pct": round(left_rate, 2) if left_rate is not None else None,
        "by_ratio_target": by_ratio,
        "by_target_tier": by_tier,
        "empirical_indifference_bracketing": {
            "lowest_ratio": min(ratios),
            "lowest_ratio_package_choice_pct": low_pct,
            "highest_ratio": max(ratios),
            "highest_ratio_package_choice_pct": high_pct,
            "fifty_pct_bracketed_by_endpoints": (
                low_pct is not None and high_pct is not None
                and low_pct <= 50.0 and high_pct >= 50.0
            ),
        },
        "voter_weights": weights,
        "diagnostic_data_gates": {
            "thresholds": {
                "counted_votes": MIN_VOTES,
                "unique_voters": MIN_VOTERS,
                "distinct_challenges": MIN_CHALLENGES,
                "distinct_targets": MIN_TARGETS,
                "minimum_each_choice": MIN_EACH_CHOICE,
                "minimum_votes_per_ratio_bucket": MIN_VOTES_PER_RATIO_BUCKET,
            },
            "passed": gates,
            "all_passed": all(gates.values()),
        },
    }

def write_report(result):
    s = result["summary"]
    lines = [
        "# Package Preference Voting V4 — 3-Player Indifference Extension",
        "",
        "**Status: RESEARCH ONLY — no production consumer changed.**",
        "",
        f"- Counted V4 votes: `{s['raw_vote_count']}`",
        f"- Unique V4 voters: `{s['unique_voters']}`",
        f"- Distinct challenges: `{s['distinct_challenges']}`",
        f"- Distinct targets: `{s['distinct_targets']}`",
        f"- Overall package choice rate: `{s['package_choice_pct']}`",
        "",
        "## By raw package / target FV ratio",
        "",
        "| Ratio | Votes | Package chosen |",
        "|---:|---:|---:|",
    ]
    for ratio, row in s["by_ratio_target"].items():
        pct = "n/a" if row["package_choice_pct"] is None else f"{row['package_choice_pct']:.1f}%"
        lines.append(f"| {ratio} | {row['votes']} | {pct} |")

    b = s["empirical_indifference_bracketing"]
    lines += [
        "",
        "## Indifference bracketing",
        "",
        f"- Lowest tested ratio `{b['lowest_ratio']}` package choice: `{b['lowest_ratio_package_choice_pct']}`",
        f"- Highest tested ratio `{b['highest_ratio']}` package choice: `{b['highest_ratio_package_choice_pct']}`",
        f"- 50% empirically bracketed by tested endpoints: `{b['fifty_pct_bracketed_by_endpoints']}`",
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
        "- V4 is 3-player package research only.",
        "- V3 remains frozen.",
        "- V4 does not alter KTC, Market Value, Fundamental Value, Team Utility, Package Adjustment Shadow V1, or the live trade verdict.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

def selftest():
    assert is_package_v4_row({"keep":"__pkgv4__|abc|P"})
    assert not is_package_v4_row({"keep":"__pkgv3__|abc|P"})
    parsed = parse_row({
        "timestamp":"2026-09-08T00:00:00Z",
        "voter_roster_id":"ext_x",
        "keep":"__pkgv4__|abc|T",
        "trade":"__pkgv4_meta__|P",
        "cut":"__pkgv4_schema__|4",
    })
    assert parsed["challenge_id"] == "abc"
    assert parsed["choice"] == "T"
    assert parsed["left_canonical_side"] == "P"

    rows = [{
        "timestamp":"2026-09-08T00:00:00Z",
        "voter_roster_id":"ext_x",
        "challenge_id":f"x{i}",
        "choice":"P",
        "left_canonical_side":"P",
    } for i in range(25)]
    capped, dropped = apply_daily_cap(rows)
    assert len(capped) == 20 and dropped == 5
    print("Package Preference V4 pipeline self-test passed.")

def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    doc = read_json(CHALLENGES)
    if doc.get("status") != "frozen_package_preference_v4" or doc.get("frozen") is not True:
        raise RuntimeError("unexpected/unfrozen V4 challenge catalog")

    raw = [parse_row(r) for r in fetch_rows() if is_package_v4_row(r)]
    raw = [r for r in raw if r is not None]
    phase = package_vote_phase.partition_rows(raw, 'v4')
    source_raw_package_rows = len(raw)
    raw = phase['postlaunch_rows']
    capped, dropped = apply_daily_cap(raw)
    summary = summarize(capped, doc)

    result = {
        "schema_version": 4,
        "status": "research_only",
        "consumer_changed": False,
        "market_value_consumer_changed": False,
        "fundamental_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "package_adjustment_shadow_v1_consumer_changed": False,
        "production_formula_enabled": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "transport": "existing KTC Google Sheet via reserved __pkgv4__ rows",
        "package_daily_cap_per_voter": MAX_VOTES_PER_VOTER_PER_DAY,
        "voter_effective_lifetime_cap": VOTER_EFFECTIVE_LIFETIME_CAP,
        "vote_phase": phase["vote_phase"],
        "prelaunch_evidence_excluded": phase["vote_phase"] == "postlaunch_only",
        "prelaunch_cutoff_utc": phase["prelaunch_cutoff_utc"],
        "prelaunch_cutoff_epoch_ms": phase["prelaunch_cutoff_epoch_ms"],
        "canonical_prelaunch_snapshot": phase["canonical_prelaunch_snapshot"],
        "source_raw_package_rows": source_raw_package_rows,
        "prelaunch_rows_excluded": phase["prelaunch_rows_excluded"],
        "invalid_timestamp_rows_excluded": phase["invalid_timestamp_rows_excluded"],
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

#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
import ktc_pipeline

CHALLENGES = ROOT / "research" / "package-adjustment-v1" / "package_vote_challenges.json"
OUT_JSON = ROOT / "research" / "package-adjustment-v1" / "package_vote_results.json"
OUT_MD = ROOT / "research" / "package-adjustment-v1" / "package_vote_results.md"

PREFIX = "__pkgv1__|"
META_PREFIX = "__pkgv1_meta__|"
SCHEMA_PREFIX = "__pkgv1_schema__|"

MAX_VOTES_PER_VOTER_PER_DAY = 10
VOTER_EFFECTIVE_LIFETIME_CAP = 30.0
MIN_VOTES = 80
MIN_VOTERS = 6
MIN_CHALLENGES = 20
MIN_EACH_CHOICE = 15

LAMBDA_GRID = tuple(i / 200 for i in range(201))
BETA_GRID = tuple(i / 4 for i in range(1, 65))

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def fetch_rows():
    r = requests.get(ktc_pipeline.SHEET_CSV_URL, timeout=30)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))

def is_package_row(row):
    return str(row.get("keep") or "").startswith(PREFIX)

def parse_row(row):
    parts = str(row.get("keep") or "").split("|")
    if len(parts) != 3 or parts[0] != "__pkgv1__" or parts[2] not in {"T","P"}:
        return None
    meta = str(row.get("trade") or "")
    left = meta[len(META_PREFIX):] if meta.startswith(META_PREFIX) else None
    if left not in {"T","P"}:
        left = None
    if not str(row.get("cut") or "").startswith(SCHEMA_PREFIX):
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

def logistic(z):
    if z >= 0:
        e = math.exp(-z)
        return 1.0 / (1.0 + e)
    e = math.exp(z)
    return e / (1.0 + e)

def log_likelihood(rows, catalog, weights, lam, beta):
    total = 0.0
    for row in rows:
        c = catalog[row["challenge_id"]]
        ratio = float(c["raw_package_to_target_ratio"])
        fg = float(c["fg"])
        eff_ratio = max(1e-9, ratio * max(1e-9, 1.0 - lam * fg))
        p = min(1 - 1e-12, max(1e-12, logistic(beta * math.log(eff_ratio))))
        y = 1.0 if row["choice"] == "P" else 0.0
        w = weights[row["voter_roster_id"]]["ballot_weight"]
        total += w * (y * math.log(p) + (1.0-y) * math.log(1.0-p))
    return total

def fit(rows, catalog, weights):
    best = None
    profile = {}
    for lam in LAMBDA_GRID:
        best_ll = None
        for beta in BETA_GRID:
            ll = log_likelihood(rows, catalog, weights, lam, beta)
            best_ll = ll if best_ll is None else max(best_ll, ll)
            candidate = (ll, -lam, -beta, lam, beta)
            if best is None or candidate > best:
                best = candidate
        profile[f"{lam:.3f}"] = best_ll
    max_ll, _a, _b, lam, beta = best
    supported = [float(k) for k,ll in profile.items() if 2*(max_ll-ll) <= 3.84]
    return {
        "lambda_hat": lam,
        "beta_hat": beta,
        "weighted_log_likelihood": max_ll,
        "lambda_profile_support_heuristic": {
            "semantics": "profile likelihood heuristic, not calibrated CI",
            "low": min(supported) if supported else None,
            "high": max(supported) if supported else None,
        },
        "boundary_lambda_flag": lam in {0.0, 1.0},
    }

def summarize(rows, doc):
    catalog = {c["id"]: c for c in doc["challenges"]}
    valid = [r for r in rows if r["challenge_id"] in catalog]
    weights = voter_weights(valid)
    package_votes = sum(r["choice"] == "P" for r in valid)
    target_votes = sum(r["choice"] == "T" for r in valid)
    unique_voters = len(weights)
    distinct = len({r["challenge_id"] for r in valid})

    left_known = [r for r in valid if r["left_canonical_side"] in {"T","P"}]
    left_rate = (
        100 * sum(r["choice"] == r["left_canonical_side"] for r in left_known) / len(left_known)
        if left_known else None
    )

    by_ratio = {}
    for rt in doc["design"]["ratio_targets"]:
        ids = {c["id"] for c in doc["challenges"] if abs(float(c["ratio_target"])-float(rt)) < 1e-9}
        sub = [r for r in valid if r["challenge_id"] in ids]
        p = sum(r["choice"] == "P" for r in sub)
        by_ratio[f"{float(rt):.2f}"] = {
            "votes": len(sub),
            "package_choice_pct": round(100*p/len(sub),2) if sub else None,
        }

    by_size = {}
    for size in doc["design"]["package_sizes"]:
        ids = {c["id"] for c in doc["challenges"] if int(c["package_size"]) == int(size)}
        sub = [r for r in valid if r["challenge_id"] in ids]
        p = sum(r["choice"] == "P" for r in sub)
        by_size[str(size)] = {
            "votes": len(sub),
            "package_choice_pct": round(100*p/len(sub),2) if sub else None,
        }

    gates = {
        "counted_votes": len(valid) >= MIN_VOTES,
        "unique_voters": unique_voters >= MIN_VOTERS,
        "distinct_challenges": distinct >= MIN_CHALLENGES,
        "choice_mix": package_votes >= MIN_EACH_CHOICE and target_votes >= MIN_EACH_CHOICE,
    }
    ready = all(gates.values())

    return {
        "voter_weights": weights,
        "raw_vote_count": len(valid),
        "unique_voters": unique_voters,
        "distinct_challenges": distinct,
        "package_votes": package_votes,
        "target_votes": target_votes,
        "package_choice_pct": round(100*package_votes/len(valid),2) if valid else None,
        "display_left_choice_pct": round(left_rate,2) if left_rate is not None else None,
        "by_ratio_target": by_ratio,
        "by_package_size": by_size,
        "promotion_data_gates": {
            "thresholds": {
                "counted_votes": MIN_VOTES,
                "unique_voters": MIN_VOTERS,
                "distinct_challenges": MIN_CHALLENGES,
                "minimum_each_choice": MIN_EACH_CHOICE,
            },
            "passed": gates,
            "all_passed": ready,
        },
        "v0_fit": fit(valid, catalog, weights) if ready else None,
    }

def write_report(result):
    s = result["summary"]
    lines = [
        "# Package Preference Voting V1",
        "",
        "**Status: RESEARCH ONLY — no production consumer changed.**",
        "",
        f"- Counted package votes: `{s['raw_vote_count']}`",
        f"- Unique voters: `{s['unique_voters']}`",
        f"- Distinct challenges: `{s['distinct_challenges']}`",
        f"- Package choice rate: `{s['package_choice_pct']}`",
        f"- Display-left choice rate: `{s['display_left_choice_pct']}`",
        "",
        "## By raw package / target FV ratio",
        "",
        "| Ratio | Votes | Package chosen |",
        "|---:|---:|---:|",
    ]
    for ratio,row in s["by_ratio_target"].items():
        pct = "n/a" if row["package_choice_pct"] is None else f"{row['package_choice_pct']:.1f}%"
        lines.append(f"| {ratio} | {row['votes']} | {pct} |")

    lines += ["", "## V0 lambda fit", ""]
    if s["v0_fit"] is None:
        lines.append("Insufficient data for provisional lambda; collection continues.")
    else:
        f = s["v0_fit"]
        support = f["lambda_profile_support_heuristic"]
        lines += [
            f"- `lambda_hat`: `{f['lambda_hat']:.3f}`",
            f"- `beta_hat`: `{f['beta_hat']:.2f}`",
            f"- Profile support heuristic: `{support['low']}` to `{support['high']}`",
            f"- Boundary flag: `{f['boundary_lambda_flag']}`",
        ]

    lines += [
        "",
        "## Isolation",
        "",
        "- Package rows are removed before normal KTC daily-cap and Bradley-Terry work.",
        "- Package votes do not alter Market Value or the live trade verdict.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

def selftest():
    assert is_package_row({"keep":"__pkgv1__|abc|P"})
    assert not is_package_row({"keep":"alpha"})
    parsed = parse_row({
        "timestamp":"2026-09-07T00:00:00Z",
        "voter_roster_id":"4",
        "keep":"__pkgv1__|abc|P",
        "trade":"__pkgv1_meta__|T",
        "cut":"__pkgv1_schema__|1",
    })
    assert parsed["challenge_id"] == "abc"
    assert parsed["choice"] == "P"
    assert parsed["left_canonical_side"] == "T"
    rows = [{
        "timestamp":"2026-09-07T00:00:00Z",
        "voter_roster_id":"4",
        "challenge_id":f"x{i}",
        "choice":"P",
        "left_canonical_side":"P",
    } for i in range(15)]
    capped,dropped = apply_daily_cap(rows)
    assert len(capped) == 10 and dropped == 5
    print("Package vote pipeline self-test passed.")

def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    doc = read_json(CHALLENGES)
    if doc.get("status") != "frozen_package_preference_v1" or doc.get("frozen") is not True:
        raise RuntimeError("unexpected/unfrozen challenge catalog")

    raw = [parse_row(r) for r in fetch_rows() if is_package_row(r)]
    raw = [r for r in raw if r is not None]
    capped,dropped = apply_daily_cap(raw)
    summary = summarize(capped, doc)

    result = {
        "schema_version": 1,
        "status": "research_only",
        "consumer_changed": False,
        "market_value_consumer_changed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "transport": "existing KTC Google Sheet via reserved __pkgv1__ rows",
        "package_daily_cap_per_voter": MAX_VOTES_PER_VOTER_PER_DAY,
        "voter_effective_lifetime_cap": VOTER_EFFECTIVE_LIFETIME_CAP,
        "raw_package_rows": len(raw),
        "daily_cap_dropped": dropped,
        "summary": summary,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(result)
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")

if __name__ == "__main__":
    main()

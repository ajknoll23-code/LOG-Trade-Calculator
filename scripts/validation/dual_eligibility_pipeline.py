#!/usr/bin/env python3
"""
Dual-eligibility audit.

Identifies players whose Sleeper `fantasy_positions` span more than one Trade
Desk valuation bucket, plus any current Trade Desk position that is no longer
Sleeper-eligible. This script is intentionally an ELIGIBILITY audit only.
It does not recommend whichever position has the highest economic weight.

Canonical convention:
- preserve Sleeper's fantasy_positions order;
- the first unique collapsed bucket is Sleeper's primary bucket;
- an existing Trade Desk valuation position is considered valid only while it
  remains in the player's current eligible buckets;
- dual eligibility is surfaced for review rather than auto-optimized for value.

Output: scripts/dual_eligibility_results.json
"""

import json
import os
import re
import sys
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

POS_BUCKET = {
    "DE": "DL", "DT": "DL", "DL": "DL",
    "OLB": "LB", "ILB": "LB", "LB": "LB",
    "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB",
}


def normalize_name(s):
    return re.sub(r"\s+", " ", re.sub(r"[.'\u2019-]", "", (s or "").strip().lower()))


def eligible_buckets(fantasy_positions):
    buckets = []
    for fp in fantasy_positions or []:
        bucket = POS_BUCKET.get(fp)
        if bucket and bucket not in buckets:
            buckets.append(bucket)
    return buckets


def fetch_player_index():
    print("Fetching Sleeper player index...")
    resp = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=60)
    resp.raise_for_status()
    return resp.json()


def load_trade_desk_positions(index_path=None):
    index_path = index_path or os.path.join(REPO_ROOT, "index.html")
    text = open(index_path, encoding="utf-8").read()
    m = re.search(r"const PLAYER_DB = \{(.*?)\n\};", text, re.S)
    if not m:
        raise RuntimeError("Could not find PLAYER_DB in index.html")
    return {
        key: pos
        for key, pos in re.findall(r"'([^']+)'\s*:\s*\{\s*pos:'([A-Z]+)'", m.group(1))
    }


def analyze_player_index(player_index, trade_desk_positions=None):
    trade_desk_positions = trade_desk_positions or {}
    dual_eligible = []

    # Normalized names are not safe identity keys when multiple Sleeper rows
    # share one name. Only compare a Trade Desk name-keyed position to Sleeper
    # when that normalized name is unique in the player index.
    name_counts = {}
    for p in player_index.values():
        name = (p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}").strip()
        if name:
            key = normalize_name(name)
            name_counts[key] = name_counts.get(key, 0) + 1

    for pid, p in player_index.items():
        fpos = p.get("fantasy_positions") or []
        buckets = eligible_buckets(fpos)

        name = (p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}").strip()
        if not name:
            continue
        key = normalize_name(name)
        name_collision = name_counts.get(key, 0) > 1
        current = None if name_collision else trade_desk_positions.get(key)
        current_is_eligible = (current in buckets) if current and buckets else None

        # Keep genuinely dual-bucket players AND any current Trade Desk row
        # whose curated position is no longer Sleeper-eligible. The latter is
        # an important stale-position integrity case even though the player is
        # not dual-eligible today.
        if len(buckets) < 2 and current_is_eligible is not False:
            continue

        dual_eligible.append({
            "sleeper_id": pid,
            "player": key,
            "team": p.get("team"),
            "name_collision": name_collision,
            "raw_position": p.get("position"),
            "raw_fantasy_positions": fpos,
            "eligible_buckets": buckets,
            "is_dual_eligible": len(buckets) >= 2,
            "sleeper_primary_bucket": buckets[0] if buckets else None,
            "current_trade_desk_position": current,
            "current_position_is_eligible": current_is_eligible,
            "manual_review_recommended": True,
        })

    dual_eligible.sort(key=lambda r: (r["player"], r["sleeper_id"]))
    return dual_eligible


def run_selftest():
    synthetic = {
        "1": {"full_name": "Edge One", "team": "ARI", "position": "DE", "fantasy_positions": ["DE", "LB"]},
        "2": {"full_name": "Edge Two", "team": "BUF", "position": "LB", "fantasy_positions": ["LB", "DE"]},
        "3": {"full_name": "Only DB", "team": "CHI", "position": "CB", "fantasy_positions": ["CB", "S"]},
        "4": {"full_name": "Stale Position", "team": "ATL", "position": "DE", "fantasy_positions": ["DL"]},
    }
    td = {"edge one": "DL", "edge two": "DL", "stale position": "LB"}
    rows = analyze_player_index(synthetic, td)
    assert len(rows) == 3, rows  # CB/S collapses to one DB bucket and is not included
    one = next(r for r in rows if r["sleeper_id"] == "1")
    two = next(r for r in rows if r["sleeper_id"] == "2")
    assert one["eligible_buckets"] == ["DL", "LB"]
    assert one["sleeper_primary_bucket"] == "DL"
    assert one["current_position_is_eligible"] is True
    assert two["eligible_buckets"] == ["LB", "DL"]
    assert two["sleeper_primary_bucket"] == "LB"
    assert two["current_position_is_eligible"] is True
    stale = next(r for r in rows if r["sleeper_id"] == "4")
    assert stale["is_dual_eligible"] is False
    assert stale["current_position_is_eligible"] is False
    print("dual_eligibility_pipeline self-test passed.")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

    player_index = fetch_player_index()
    td_positions = load_trade_desk_positions()
    dual_eligible = analyze_player_index(player_index, td_positions)

    out_path = os.path.join(SCRIPT_DIR, "dual_eligibility_results.json")
    with open(out_path, "w") as f:
        json.dump(dual_eligible, f, indent=2)

    invalid = [r for r in dual_eligible if r["current_position_is_eligible"] is False]
    print(f"\nFound {len(dual_eligible)} genuinely dual-bucket-eligible IDP players.")
    print(f"Trade Desk positions no longer Sleeper-eligible: {len(invalid)}")
    print("First 15:")
    for r in dual_eligible[:15]:
        cur = r["current_trade_desk_position"] or "-"
        print(
            f"  {r['player']:22s} eligible={str(r['eligible_buckets']):16s} "
            f"Sleeper-primary={r['sleeper_primary_bucket']} current={cur}"
        )
    print(f"\nFull audit written to {out_path}")


if __name__ == "__main__":
    main()

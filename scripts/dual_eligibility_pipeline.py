"""
Dual-eligibility pipeline -- identifies which IDP players are genuinely
dual-position-eligible according to Sleeper's own data, and for each one,
says which of their eligible position buckets carries the highest
POSITION_WEIGHT in this league's rules.

WHY THIS EXISTS: a prior session flagged 7 players (Abdul Carter, Brian
Burns, Will Anderson, Joseph Ossai, Akheem Mesidor, James Pearce, Jeremy
Chinn) as "mistagged" in PLAYER_DB because their tag didn't match
Sleeper's single raw `position` field. That was wrong -- those players
were deliberately tagged at their dual-eligible position's higher value
on purpose, and the "fix" got reverted. The bug wasn't the tags; it was
using the single `position` field (which only ever holds one value) to
check for something that's inherently a multi-value question. This
script uses the right field for that question instead:
`fantasy_positions`, which is the actual array Sleeper itself uses to
decide what a player is eligible to be started as, and is present for
every player already (sync_sleeper.py already pulls it, it just wasn't
used for this).

METHOD: fetch the full Sleeper player index once (same endpoint every
other script here uses). For each player, bucket every entry in their
fantasy_positions array using the same DL/LB/DB collapse used everywhere
else in this project. If that produces more than one distinct bucket,
the player is genuinely dual-eligible. Among their eligible buckets, the
"recommended" one is whichever carries the highest POSITION_WEIGHT.

IMPORTANT: this script does NOT modify index.html or PLAYER_DB. It only
produces a real, sourced list. What to do with a player whose current
PLAYER_DB tag doesn't match their highest-value eligible bucket is a
judgment call each time (are they ACTUALLY going to see snaps/production
at the higher-weighted position, or just technically roster-eligible
there) -- that's for a human to decide per player, not something this
script should auto-apply.

USAGE: python3 dual_eligibility_pipeline.py
Requires: requests (pip install requests --break-system-packages)

HONESTY NOTE, same as the other new scripts this session: written and
reasoned through without the ability to execute it end-to-end (no
outbound network in this sandbox). The /v1/players/nfl endpoint and its
fantasy_positions field are the same ones sync_sleeper.py already uses
successfully in production, so this is a known-working data source --
but spot-check a couple of known dual-eligible players against the real
Sleeper app before trusting the full output.
"""

import json
import os
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Mirrors index.html's POSITION_WEIGHT for the three IDP buckets --
# IMPORTANT: if those live weights ever change, update this to match, or
# the "recommended" column here will be computed against stale weights.
POSITION_WEIGHT = {"DL": 0.81, "LB": 1.17, "DB": 1.00}

# Same bucket collapse used everywhere else in this project (sync_sleeper.py,
# durability_pipeline.py) -- kept identical on purpose.
POS_BUCKET = {
    "DE": "DL", "DT": "DL", "DL": "DL",
    "OLB": "LB", "ILB": "LB", "LB": "LB",
    "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB",
}


def fetch_player_index():
    print("Fetching Sleeper player index...")
    resp = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=60)
    resp.raise_for_status()
    return resp.json()


def main():
    player_index = fetch_player_index()

    dual_eligible = []
    for pid, p in player_index.items():
        fpos = p.get("fantasy_positions") or []
        buckets = set()
        for fp in fpos:
            b = POS_BUCKET.get(fp)
            if b:
                buckets.add(b)
        if len(buckets) < 2:
            continue  # single-bucket-eligible (the normal case) or not IDP at all

        name = (p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}").strip()
        if not name:
            continue

        recommended = max(buckets, key=lambda b: POSITION_WEIGHT[b])
        dual_eligible.append({
            "sleeper_id": pid,
            "player": name.lower(),
            "team": p.get("team"),
            "raw_fantasy_positions": fpos,
            "eligible_buckets": sorted(buckets),
            "recommended_bucket": recommended,
            "recommended_weight": POSITION_WEIGHT[recommended],
        })

    dual_eligible.sort(key=lambda r: r["player"])

    with open(os.path.join(SCRIPT_DIR, "dual_eligibility_results.json"), "w") as f:
        json.dump(dual_eligible, f, indent=2)

    print(f"\nFound {len(dual_eligible)} genuinely dual-eligible IDP players "
          f"(per Sleeper's own fantasy_positions field).")
    print("First 15:")
    for r in dual_eligible[:15]:
        print(f"  {r['player']:22s} {str(r['eligible_buckets']):16s} -> recommend {r['recommended_bucket']}")
    print(f"\nFull list written to dual_eligibility_results.json")


if __name__ == "__main__":
    main()

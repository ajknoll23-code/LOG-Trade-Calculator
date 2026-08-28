#!/usr/bin/env python3
"""
scripts/filter_sleeper_idp_only.py

Reads the already-committed sleeper_2026_raw_categories.json (large --
every real player, offense included) and writes a much smaller
companion file containing only real IDP-position players. Exists purely
so the person can share a chat-sized file instead of an 8MB one -- the
full file stays in the repo as the real audit artifact; this is a
convenience view, not a replacement for it.

Does NOT re-fetch anything from Sleeper -- pure local filtering of a
file that already exists, so this runs in seconds.

USAGE: python3 scripts/filter_sleeper_idp_only.py
Add --selftest to verify the position filter against synthetic data
before trusting real output.

OUTPUT: scripts/sleeper_2026_idp_only.json (much smaller, safe to
share directly)
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IN_PATH = os.path.join(SCRIPT_DIR, "sleeper_2026_raw_categories.json")
OUT_PATH = os.path.join(SCRIPT_DIR, "sleeper_2026_idp_only.json")

# Sleeper's own real position labels are more granular than FantasyPros'
# simplified LB/DL/DB buckets (e.g. DE/DT separately, not just "DL";
# CB/S/SS/FS separately, not just "DB") -- cast a wide net here so a
# real IDP player isn't accidentally excluded by assuming FantasyPros'
# simpler bucketing applies to Sleeper's raw data too.
IDP_POSITIONS = {"LB", "OLB", "ILB", "MLB", "DL", "DE", "DT", "NT",
                  "DB", "CB", "S", "SS", "FS", "EDGE"}


def filter_idp(players):
    return [p for p in players if p.get("pos") in IDP_POSITIONS]


def run_selftest():
    print("Running self-test on synthetic data...")
    synthetic = [
        {"player": "real lb", "pos": "LB"},
        {"player": "real edge", "pos": "DE"},
        {"player": "real corner", "pos": "CB"},
        {"player": "real qb", "pos": "QB"},
        {"player": "real wr", "pos": "WR"},
    ]
    filtered = filter_idp(synthetic)
    assert len(filtered) == 3, f"expected 3 real IDP players kept, got {len(filtered)}"
    kept_names = {p["player"] for p in filtered}
    assert kept_names == {"real lb", "real edge", "real corner"}, f"unexpected filter result: {kept_names}"
    print("  IDP position filter correctly keeps real IDP positions and excludes offense -- OK")
    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

    if not os.path.exists(IN_PATH):
        print(f"ERROR: {IN_PATH} doesn't exist yet -- run the Sleeper 2026 Projections workflow first.")
        sys.exit(1)

    with open(IN_PATH) as f:
        players = json.load(f)
    print(f"Loaded {len(players)} total real players from {IN_PATH}")

    idp_only = filter_idp(players)
    print(f"Filtered to {len(idp_only)} real IDP-position players")

    with open(OUT_PATH, "w") as f:
        json.dump(idp_only, f, indent=2)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()

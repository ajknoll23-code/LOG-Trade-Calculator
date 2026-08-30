#!/usr/bin/env python3
"""
scripts/projections/filter_sleeper_idp_only.py

Reads scripts/sleeper_2026_raw_categories.json and writes the smaller
scripts/sleeper_2026_idp_only.json convenience view.

USAGE: python3 scripts/projections/filter_sleeper_idp_only.py
Add --selftest to verify the filter first.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(SCRIPT_DIR)
IN_PATH = os.path.join(SCRIPTS_DIR, "sleeper_2026_raw_categories.json")
OUT_PATH = os.path.join(SCRIPTS_DIR, "sleeper_2026_idp_only.json")

IDP_POSITIONS = {"LB", "OLB", "ILB", "MLB", "DL", "DE", "DT", "NT",
                 "DB", "CB", "S", "SS", "FS", "EDGE"}


def filter_idp(players):
    return [p for p in players if p.get("pos") in IDP_POSITIONS]


def run_selftest():
    synthetic = [
        {"player": "real lb", "pos": "LB"},
        {"player": "real edge", "pos": "DE"},
        {"player": "real corner", "pos": "CB"},
        {"player": "real qb", "pos": "QB"},
        {"player": "real wr", "pos": "WR"},
    ]
    filtered = filter_idp(synthetic)
    assert len(filtered) == 3
    assert {p["player"] for p in filtered} == {"real lb", "real edge", "real corner"}
    print("Self-test passed.")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

    if not os.path.exists(IN_PATH):
        print(f"ERROR: {IN_PATH} doesn't exist yet -- run the Sleeper 2026 Projections workflow first.")
        sys.exit(1)

    with open(IN_PATH) as f:
        players = json.load(f)

    idp_only = filter_idp(players)

    with open(OUT_PATH, "w") as f:
        json.dump(idp_only, f, indent=2)

    print(f"Wrote {OUT_PATH} ({len(idp_only)} players)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
diff_snapshots.py

Compares two value_snapshots produced by snapshot_values.py and produces
the old-vs-new "biggest movers" report: top 25 increases, top 25
decreases, with old value, new value, and % change for each player.

Usage:
    python3 scripts/validation/diff_snapshots.py scripts/value_snapshots/OLD.json scripts/value_snapshots/NEW.json

If run with no arguments, automatically picks the two most recent
snapshots in scripts/value_snapshots/.
"""
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
SNAP_DIR = SCRIPTS_DIR / "value_snapshots"


def load(path):
    return json.loads(Path(path).read_text())


def main():
    if len(sys.argv) == 3:
        old_path, new_path = sys.argv[1], sys.argv[2]
    else:
        files = sorted(SNAP_DIR.glob('*.json'))
        if len(files) < 2:
            print(f"Need at least 2 snapshots in {SNAP_DIR} to diff. "
                  f"Found {len(files)}. Run scripts/validation/snapshot_values.py first "
                  "(and again after your rebuild).")
            sys.exit(1)
        old_path, new_path = files[-2], files[-1]
        print(f"Auto-selected: OLD={old_path.name}  NEW={new_path.name}\n")

    old = load(old_path)
    new = load(new_path)
    old_vals = old['values']
    new_vals = new['values']

    movers = []
    for key, new_info in new_vals.items():
        if key not in old_vals:
            continue  # new player, nothing to diff
        old_val = old_vals[key]['value']
        new_val = new_info['value']
        if old_val == 0:
            continue
        pct_change = (new_val - old_val) / old_val * 100
        movers.append({
            'key': key, 'pos': new_info['pos'],
            'old_value': old_val, 'new_value': new_val,
            'abs_change': new_val - old_val, 'pct_change': round(pct_change, 1),
        })

    increases = sorted(movers, key=lambda x: -x['abs_change'])[:25]
    decreases = sorted(movers, key=lambda x: x['abs_change'])[:25]

    print(f"=== Biggest 25 value INCREASES ({old['timestamp_utc']} -> {new['timestamp_utc']}) ===")
    print(f"{'Player':22s} {'Pos':4s} {'Old':6s} {'New':6s} {'Change':8s} {'%'}")
    for m in increases:
        print(f"{m['key']:22s} {m['pos']:4s} {m['old_value']:<6d} {m['new_value']:<6d} "
              f"+{m['abs_change']:<7d} +{m['pct_change']}%")

    print(f"\n=== Biggest 25 value DECREASES ===")
    print(f"{'Player':22s} {'Pos':4s} {'Old':6s} {'New':6s} {'Change':8s} {'%'}")
    for m in decreases:
        print(f"{m['key']:22s} {m['pos']:4s} {m['old_value']:<6d} {m['new_value']:<6d} "
              f"{m['abs_change']:<8d} {m['pct_change']}%")

    # New/removed players (no diff possible, but worth surfacing)
    new_players = [k for k in new_vals if k not in old_vals]
    removed_players = [k for k in old_vals if k not in new_vals]
    if new_players:
        print(f"\n=== {len(new_players)} players in NEW snapshot only (added since last snapshot) ===")
        print(', '.join(sorted(new_players)[:20]) + (' ...' if len(new_players) > 20 else ''))
    if removed_players:
        print(f"\n=== {len(removed_players)} players in OLD snapshot only (removed since last snapshot) ===")
        print(', '.join(sorted(removed_players)[:20]) + (' ...' if len(removed_players) > 20 else ''))


if __name__ == '__main__':
    main()

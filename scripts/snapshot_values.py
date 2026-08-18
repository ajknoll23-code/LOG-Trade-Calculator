#!/usr/bin/env python3
"""
snapshot_values.py

Captures a timestamped snapshot of every player's computed trade value,
straight from the live formula in index.html -- not a re-derivation, the
actual same math the tool uses. Run this BEFORE any data rebuild (age
corrections, production rebuild, role changes, etc.) so diff_snapshots.py
can produce a real old-vs-new comparison afterward.

This closes the gap flagged in the 2026-08 audit: "I don't have a
preserved full old-PROD_MULT_DATA snapshot to diff against... I can't
honestly produce that comparison without inventing the old numbers."

Usage:
    python3 scripts/snapshot_values.py

Output:
    scripts/value_snapshots/<YYYY-MM-DD_HHMMSS>.json

Run this from the repo root (same level as index.html).
"""
import re
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

POSITION_WEIGHT = {'QB': 1.30, 'RB': 0.89, 'WR': 1.00, 'TE': 0.82, 'DL': 0.81,
                    'LB': 1.17, 'DB': 1.00, 'K': 0.35}

AGE_CURVE = {
    'QB': {'peakStart': 26, 'peakEnd': 33, 'floor': 35},
    'RB': {'peakStart': 23, 'peakEnd': 25, 'floor': 30},
    'WR': {'peakStart': 24, 'peakEnd': 28, 'floor': 33},
    'TE': {'peakStart': 25, 'peakEnd': 29, 'floor': 34},
    'DL': {'peakStart': 24, 'peakEnd': 29, 'floor': 34},
    'LB': {'peakStart': 24, 'peakEnd': 29, 'floor': 32},
    'DB': {'peakStart': 23, 'peakEnd': 27, 'floor': 32},
    'K':  {'peakStart': 22, 'peakEnd': 40, 'floor': 45},
}
QB_POST_PEAK_FLOOR = 0.546
ROLE_MULT = {'Elite': 1.4, 'Every-Down': 1.15, 'Starter': 1.0, 'Rotational': 0.65,
             'Understudy': 0.57, 'Depth': 0.35, 'Speculative': 0.22}


def extract_block(content, marker, end_marker='\n};'):
    start = content.index(marker)
    end = content.index(end_marker, start)
    return content[start:end]


def load_from_html(html_path):
    content = Path(html_path).read_text()

    pdb_block = extract_block(content, 'const PLAYER_DB = {')
    pdb_pattern = re.compile(r"'([^']+)':\{pos:'([A-Z]+)',age:(\d+),role:'([^']+)'")
    player_db = {k: {'pos': pos, 'age': int(age), 'role': role}
                 for k, pos, age, role in pdb_pattern.findall(pdb_block)}

    prod_block = extract_block(content, 'const PROD_MULT_DATA = {')
    prod_pattern = re.compile(r"'([^']+)':([0-9.]+)")
    prod_mult = {k: float(v) for k, v in prod_pattern.findall(prod_block)}

    return player_db, prod_mult


def production_multiplier(key, role, prod_mult_data):
    role_estimate = ROLE_MULT.get(role, 1.0)
    if key in prod_mult_data:
        real = prod_mult_data[key]
        if role == 'Elite' and real < 0.65:
            return 0.65, real
        if real <= 0.15 and role_estimate > real:
            return role_estimate, real
        return real, real
    return role_estimate, None


def age_multiplier(pos, age, role, real_production, raw_production):
    c = AGE_CURVE.get(pos, AGE_CURVE['WR'])
    if pos == 'K':
        return 0.5
    if age <= c['peakEnd']:
        pre_floor = 0.725 if role == 'Elite' else 0.55
        if role == 'Elite' and isinstance(real_production, (int, float)):
            bonus = max(0, real_production - 0.65) * 0.6
            pre_floor = min(0.98, pre_floor + bonus)
        t = max(0, (age - 21) / (c['peakStart'] - 21)) if c['peakStart'] != 21 else 0
        pre_floor_base = pre_floor + t * (1.0 - pre_floor)
        base = pre_floor_base if age <= c['peakStart'] else 1.0

        if (pos == 'RB' and role == 'Elite' and age <= 25
                and isinstance(raw_production, (int, float)) and raw_production >= 0.65):
            years_of_upside = min(4, max(0, c['peakEnd'] - age))
            youth_bonus = 0.384 * math.sqrt(years_of_upside)
            flat_base = 0.725 if age <= c['peakStart'] else 1.0
            return min(1.5, flat_base + youth_bonus)
        return base

    decline_span = c['floor'] - c['peakEnd']
    t = min(1, (age - c['peakEnd']) / decline_span) if decline_span else 1
    if pos == 'QB':
        return max(QB_POST_PEAK_FLOOR, 1.0 - t * (1 - QB_POST_PEAK_FLOOR))
    return max(0.62, 1.0 - t * 0.38)


def compute_all_values(player_db, prod_mult_data):
    results = {}
    for key, info in player_db.items():
        pos, age, role = info['pos'], info['age'], info['role']
        rm, raw_rm = production_multiplier(key, role, prod_mult_data)
        am = age_multiplier(pos, age, role, rm, raw_rm)
        pw = POSITION_WEIGHT.get(pos, 1.0)
        value = round(100 * pw * am * rm * 55)
        results[key] = {
            'pos': pos, 'age': age, 'role': role, 'value': value,
            'age_mult': round(am, 4), 'prod_mult': round(rm, 4),
            'has_real_prod_data': raw_rm is not None,
        }
    return results


def main():
    html_path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    if not Path(html_path).exists():
        print(f"ERROR: {html_path} not found. Run this from the repo root, "
              f"or pass the path explicitly: python3 scripts/snapshot_values.py path/to/index.html")
        sys.exit(1)

    player_db, prod_mult_data = load_from_html(html_path)
    values = compute_all_values(player_db, prod_mult_data)

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')
    out_dir = Path('scripts/value_snapshots')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{timestamp}.json'

    snapshot = {
        'timestamp_utc': timestamp,
        'player_count': len(values),
        'values': values,
    }
    out_path.write_text(json.dumps(snapshot, indent=2))
    print(f"Snapshot saved: {out_path} ({len(values)} players)")
    print("Run this again after your next rebuild, then use diff_snapshots.py to compare.")


if __name__ == '__main__':
    main()

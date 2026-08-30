#!/usr/bin/env python3
"""
snapshot_values.py

Captures a timestamped snapshot of every player's computed Trade Desk value
using the CURRENT valuation constants/data embedded in index.html.

IMPORTANT: index.html is the valuation source of truth today. This script
intentionally parses POSITION_WEIGHT, AGE_CURVE, ROLE_MULT, PROD_MULT_DATA,
NO_REAL_PRODUCTION_HISTORY, PLAYER_DB, QB_POST_PEAK_FLOOR, and
LB_POST_PEAK_DECAY_POWER from that file before applying a Python port of the
live productionMultiplier()/ageMultiplier()/playerValue() math.

A repository regression check compares this Python port against the live JS
functions for every PLAYER_DB row so formula drift is caught before a snapshot
is trusted.

Usage:
    python3 scripts/validation/snapshot_values.py
    python3 scripts/validation/snapshot_values.py path/to/index.html
    python3 scripts/validation/snapshot_values.py --selftest

Output:
    scripts/value_snapshots/<YYYY-MM-DD_HHMMSS>.json
"""

import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def extract_object_body(content, const_name):
    """Return the text inside `const <name> = { ... };` using balanced braces."""
    marker = f"const {const_name} = {{"
    start = content.find(marker)
    if start < 0:
        raise RuntimeError(f"Could not find {marker!r} in index.html")
    brace = content.find("{", start)
    depth = 0
    quote = None
    escaped = False
    for i in range(brace, len(content)):
        ch = content[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return content[brace + 1:i]
    raise RuntimeError(f"Unterminated object for {const_name}")


def extract_scalar(content, const_name):
    m = re.search(rf"const\s+{re.escape(const_name)}\s*=\s*([0-9.]+)\s*;", content)
    if not m:
        raise RuntimeError(f"Could not find scalar const {const_name}")
    return float(m.group(1))


def parse_simple_numeric_object(body):
    pairs = re.findall(r"(?:'([^']+)'|\b([A-Za-z][A-Za-z0-9_-]*))\s*:\s*([0-9.]+)", body)
    out = {}
    for quoted, bare, value in pairs:
        out[quoted or bare] = float(value)
    return out


def load_from_html(html_path):
    content = Path(html_path).read_text(encoding="utf-8")

    player_body = extract_object_body(content, "PLAYER_DB")
    player_pattern = re.compile(
        r"'([^']+)'\s*:\s*\{\s*pos:'([A-Z]+)'\s*,\s*age:(\d+)\s*,\s*role:'([^']+)'"
    )
    player_db = {
        key: {"pos": pos, "age": int(age), "role": role}
        for key, pos, age, role in player_pattern.findall(player_body)
    }
    if not player_db:
        raise RuntimeError("PLAYER_DB parsed as empty")

    prod_mult = parse_simple_numeric_object(extract_object_body(content, "PROD_MULT_DATA"))
    no_history = set(re.findall(r"'([^']+)'\s*:\s*1\b", extract_object_body(content, "NO_REAL_PRODUCTION_HISTORY")))
    position_weight = parse_simple_numeric_object(extract_object_body(content, "POSITION_WEIGHT"))
    role_mult = parse_simple_numeric_object(extract_object_body(content, "ROLE_MULT"))

    age_curve_body = extract_object_body(content, "AGE_CURVE")
    age_curve_pattern = re.compile(
        r"([A-Z]+)\s*:\s*\{\s*peakStart\s*:\s*(\d+)\s*,\s*peakEnd\s*:\s*(\d+)\s*,\s*floor\s*:\s*(\d+)\s*\}"
    )
    age_curve = {
        pos: {"peakStart": int(start), "peakEnd": int(end), "floor": int(floor)}
        for pos, start, end, floor in age_curve_pattern.findall(age_curve_body)
    }
    if not age_curve:
        raise RuntimeError("AGE_CURVE parsed as empty")

    return {
        "player_db": player_db,
        "prod_mult": prod_mult,
        "no_real_history": no_history,
        "position_weight": position_weight,
        "role_mult": role_mult,
        "age_curve": age_curve,
        "qb_post_peak_floor": extract_scalar(content, "QB_POST_PEAK_FLOOR"),
        "lb_post_peak_decay_power": extract_scalar(content, "LB_POST_PEAK_DECAY_POWER"),
    }


def production_multiplier(key, role, prod_mult_data, no_real_history, role_mult):
    role_estimate = role_mult.get(role, 1.0)
    if key in prod_mult_data:
        real = prod_mult_data[key]
        if role == "Elite" and real < 0.65:
            return 0.65, real
        if real <= 0.15 and role_estimate > real and key in no_real_history:
            return role_estimate, real
        return real, real
    return role_estimate, None


def age_multiplier(pos, age, role, real_production, raw_production, cfg):
    age_curve = cfg["age_curve"]
    c = age_curve.get(pos, age_curve["WR"])

    if pos == "K":
        return 0.5

    if age <= c["peakEnd"]:
        if isinstance(real_production, (int, float)):
            lo, hi = 0.15, 1.55
            ratio = max(0.0, min(1.0, (real_production - lo) / (hi - lo)))
            pre_floor = 0.55 + ratio * (0.98 - 0.55)
        else:
            pre_floor = 0.725 if role == "Elite" else 0.55

        denom = c["peakStart"] - 21
        t = max(0.0, (age - 21) / denom) if denom else 0.0
        pre_floor_base = pre_floor + t * (1.0 - pre_floor)
        base = pre_floor_base if age <= c["peakStart"] else 1.0

        if (
            pos == "RB"
            and role == "Elite"
            and age <= 25
            and isinstance(raw_production, (int, float))
            and raw_production >= 0.65
        ):
            years_of_upside = min(4, max(0, c["peakEnd"] - age))
            youth_bonus = 0.384 * math.sqrt(years_of_upside)
            flat_base = 0.725 if age <= c["peakStart"] else 1.0
            return min(1.5, flat_base + youth_bonus)
        return base

    decline_span = c["floor"] - c["peakEnd"]
    t = max(0.0, min(1.0, (age - c["peakEnd"]) / decline_span)) if decline_span else 1.0

    if pos == "QB":
        qb_floor = cfg["qb_post_peak_floor"]
        return max(qb_floor, 1.0 - t * (1.0 - qb_floor))
    if pos == "LB":
        power = cfg["lb_post_peak_decay_power"]
        return max(0.62, 1.0 - 0.38 * math.pow(t, power))
    return max(0.62, 1.0 - t * 0.38)


def compute_all_values(cfg):
    results = {}
    for key, info in cfg["player_db"].items():
        pos, age, role = info["pos"], info["age"], info["role"]
        rm, raw_rm = production_multiplier(
            key,
            role,
            cfg["prod_mult"],
            cfg["no_real_history"],
            cfg["role_mult"],
        )
        am = age_multiplier(pos, age, role, rm, raw_rm, cfg)
        pw = cfg["position_weight"].get(pos, 1.0)
        # JavaScript Math.round() rounds positive .5 ties upward; Python's
        # built-in round() uses bankers rounding. Trade Desk values are
        # positive, so floor(x + 0.5) reproduces the live JS exactly.
        value = math.floor(100 * pw * am * rm * 55 + 0.5)
        results[key] = {
            "pos": pos,
            "age": age,
            "role": role,
            "value": value,
            "age_mult": round(am, 6),
            "prod_mult": round(rm, 6),
            "has_real_prod_data": raw_rm is not None,
            "no_real_production_history": key in cfg["no_real_history"],
        }
    return results


def run_selftest(html_path="index.html"):
    cfg = load_from_html(html_path)

    # Regression checks for the exact live constants that previously drifted.
    assert cfg["position_weight"]["DL"] == 0.93
    assert cfg["position_weight"]["LB"] == 1.12
    assert cfg["position_weight"]["DB"] == 0.87
    assert cfg["lb_post_peak_decay_power"] == 0.5

    # Production-floor rescue must be lineage-gated.
    test_cfg = dict(cfg)
    test_cfg["prod_mult"] = {"with history": 0.15, "without history": 0.15}
    test_cfg["no_real_history"] = {"without history"}
    rm_with, _ = production_multiplier("with history", "Depth", test_cfg["prod_mult"], test_cfg["no_real_history"], cfg["role_mult"])
    rm_without, _ = production_multiplier("without history", "Depth", test_cfg["prod_mult"], test_cfg["no_real_history"], cfg["role_mult"])
    assert rm_with == 0.15, rm_with
    assert rm_without == cfg["role_mult"]["Depth"], rm_without

    values = compute_all_values(cfg)
    assert len(values) == len(cfg["player_db"])
    print(f"snapshot_values self-test passed ({len(values)} PLAYER_DB rows).")


def main():
    args = [a for a in sys.argv[1:] if a != "--selftest"]
    html_path = args[0] if args else "index.html"

    if not Path(html_path).exists():
        print(
            f"ERROR: {html_path} not found. Run this from the repo root, "
            "or pass the path explicitly: python3 scripts/validation/snapshot_values.py path/to/index.html"
        )
        sys.exit(1)

    if "--selftest" in sys.argv:
        run_selftest(html_path)
        return

    cfg = load_from_html(html_path)
    values = compute_all_values(cfg)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    out_dir = Path("scripts/value_snapshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{timestamp}.json"

    snapshot = {
        "timestamp_utc": timestamp,
        "source_html": str(html_path),
        "player_count": len(values),
        "values": values,
    }
    out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"Snapshot saved: {out_path} ({len(values)} players)")
    print("Run this again after your next rebuild, then use scripts/validation/diff_snapshots.py to compare.")


if __name__ == "__main__":
    main()

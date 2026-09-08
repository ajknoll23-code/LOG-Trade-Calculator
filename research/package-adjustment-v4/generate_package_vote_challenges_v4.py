#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALUES = ROOT / "scripts" / "artifacts" / "generated" / "value_uncertainty.json"
ROSTERS = ROOT / "data" / "league_rosters.json"
V3_CATALOG = ROOT / "research" / "package-adjustment-v3" / "package_vote_challenges_v3.json"
OUT = ROOT / "research" / "package-adjustment-v4" / "package_vote_challenges_v4.json"

# V4 is a targeted 3-for-1 extension.  It overlaps V3 at 1.85x, then extends
# only far enough to bracket the V3-implied ~2.0-2.2x 3-player indifference
# while preserving V3's 45/33/22 package composition.
RATIO_TARGETS = (1.75, 1.85, 1.95, 2.05, 2.15)
PACKAGE_SIZE = 3
COMPONENT_WEIGHTS = (0.45, 0.33, 0.22)

MIN_PIECE_TO_TARGET = 0.06
MAX_PIECE_TO_TARGET = 0.995
MAX_RATIO_ERROR = 0.035
MAX_COMPONENT_ERROR_TO_TARGET = 0.10
NEAREST_POOL = 18

MIN_TARGETS = 14
MIN_CHALLENGES = MIN_TARGETS * len(RATIO_TARGETS)

POS_MAP = {
    "QB":"QB","RB":"RB","WR":"WR","TE":"TE","K":"K",
    "DL":"DL","DE":"DL","DT":"DL",
    "LB":"LB","OLB":"LB","ILB":"LB",
    "DB":"DB","CB":"DB","S":"DB","SS":"DB","FS":"DB",
}

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def normalize_name(value):
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def normalize_pos(value):
    return POS_MAP.get(str(value or "").upper())

def finite(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def player_universe():
    values_doc = read_json(VALUES)
    rosters_doc = read_json(ROSTERS)

    value_index = {}
    for name, row in (values_doc.get("players") or {}).items():
        fv = finite(row.get("center_value"))
        pos = normalize_pos(row.get("pos"))
        if fv is None or fv <= 0 or not pos or pos == "K":
            continue
        value_index[normalize_name(name)] = {"fv": float(fv), "pos": pos}

    rostered = {}
    for roster in rosters_doc.get("rosters") or []:
        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for raw in roster.get(slot) or []:
                key = normalize_name(raw.get("name"))
                row = value_index.get(key)
                if not row:
                    continue
                rostered[key] = {
                    "key": key,
                    "name": str(raw.get("name") or key),
                    "pos": row["pos"],
                    "fv": row["fv"],
                    "team": raw.get("team"),
                    "age": raw.get("age"),
                }

    players = sorted(rostered.values(), key=lambda p: (p["fv"], p["key"]))
    if len(players) < 350:
        raise RuntimeError(f"too few rostered valued players: {len(players)}")
    return players, {p["key"]: p for p in players}

def nearest_candidates(players, desired, target_fv, target_key):
    allowed = [
        p for p in players
        if p["key"] != target_key
        and target_fv * MIN_PIECE_TO_TARGET <= float(p["fv"]) < target_fv * MAX_PIECE_TO_TARGET
    ]
    allowed.sort(key=lambda p: (abs(float(p["fv"]) - desired), p["key"]))
    return allowed[:NEAREST_POOL]

def construct_package(anchor, players, ratio_target):
    target_fv = float(anchor["fv"])
    total_goal = target_fv * float(ratio_target)
    desired = [total_goal * w for w in COMPONENT_WEIGHTS]

    pools = [nearest_candidates(players, d, target_fv, anchor["key"]) for d in desired]
    if any(len(pool) < 4 for pool in pools):
        return None

    best = None
    for triple in itertools.product(*pools):
        keys = [p["key"] for p in triple]
        if len(set(keys)) != 3:
            continue
        vals = [float(p["fv"]) for p in triple]
        if any(v >= target_fv for v in vals):
            continue

        ratio = sum(vals) / target_fv
        ratio_err = abs(ratio - float(ratio_target))
        if ratio_err > MAX_RATIO_ERROR:
            continue

        comp_errs = [abs(v - d) / target_fv for v, d in zip(vals, desired)]
        if max(comp_errs) > MAX_COMPONENT_ERROR_TO_TARGET:
            continue

        score = (
            ratio_err,
            sum(comp_errs),
            max(comp_errs),
            tuple(sorted(keys)),
        )
        if best is None or score < best[0]:
            best = (score, list(triple))

    return None if best is None else best[1]

def challenge_record(anchor, package, ratio_target, v3_target_meta):
    target_fv = float(anchor["fv"])
    package_fv = sum(float(p["fv"]) for p in package)
    ratio = package_fv / target_fv
    ratio_code = int(round(float(ratio_target) * 100))
    slug = re.sub(r"[^a-z0-9]+", "_", normalize_name(anchor["name"])).strip("_")
    cid = f"pkgv4_{anchor['pos'].lower()}_{slug}_{ratio_code}_3x"
    return {
        "id": cid,
        "schema_version": 4,
        "experiment": "package_indifference_v4_three_player_extension",
        "target_tier": v3_target_meta.get("tier"),
        "target_rank_within_position": v3_target_meta.get("rank_within_position"),
        "target": {
            "key": anchor["key"],
            "name": anchor["name"],
            "pos": anchor["pos"],
            "team": anchor.get("team"),
            "age": anchor.get("age"),
            "fv": round(target_fv, 3),
        },
        "package": [{
            "key": p["key"],
            "name": p["name"],
            "pos": p["pos"],
            "team": p.get("team"),
            "age": p.get("age"),
            "fv": round(float(p["fv"]), 3),
        } for p in package],
        "package_size": 3,
        "target_fv": round(target_fv, 3),
        "package_fv": round(package_fv, 3),
        "raw_package_to_target_ratio": round(ratio, 6),
        "ratio_target": float(ratio_target),
        "component_profile": {
            "intended_package_shares": list(COMPONENT_WEIGHTS),
            "actual_piece_to_target_shares": [
                round(float(p["fv"]) / target_fv, 6) for p in package
            ],
            "largest_piece_to_target": round(
                max(float(p["fv"]) / target_fv for p in package), 6
            ),
        },
    }

def validate(challenges):
    if len(challenges) < MIN_CHALLENGES:
        raise RuntimeError(f"V4 catalog too small: {len(challenges)}")

    ids = [c["id"] for c in challenges]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate V4 challenge IDs")

    by_target = defaultdict(list)
    for c in challenges:
        by_target[c["target"]["key"]].append(c)
        if c["package_size"] != 3:
            raise RuntimeError("V4 must remain 3-player only")
        if any(float(p["fv"]) >= float(c["target_fv"]) for p in c["package"]):
            raise RuntimeError(f"{c['id']}: package piece >= target FV")
        if abs(float(c["raw_package_to_target_ratio"]) - float(c["ratio_target"])) > MAX_RATIO_ERROR:
            raise RuntimeError(f"{c['id']}: ratio outside tolerance")

    expected = set(float(x) for x in RATIO_TARGETS)
    for target_key, rows in by_target.items():
        got = set(float(c["ratio_target"]) for c in rows)
        if got != expected:
            raise RuntimeError(f"{target_key}: incomplete V4 ratio grid")

    if len(by_target) < MIN_TARGETS:
        raise RuntimeError(f"too few complete V4 targets: {len(by_target)}")

    positions = {c["target"]["pos"] for c in challenges}
    if len(positions) < 6:
        raise RuntimeError(f"insufficient V4 position coverage: {sorted(positions)}")

    return by_target

def selftest():
    fake_target = {"key":"t","name":"Target","pos":"WR","fv":100.0}
    players = [
        {"key":"a","name":"A","pos":"WR","fv":96.0},
        {"key":"b","name":"B","pos":"RB","fv":71.0},
        {"key":"c","name":"C","pos":"TE","fv":48.0},
        {"key":"d","name":"D","pos":"WR","fv":90.0},
        {"key":"e","name":"E","pos":"RB","fv":75.0},
        {"key":"f","name":"F","pos":"TE","fv":50.0},
        {"key":"g","name":"G","pos":"WR","fv":85.0},
        {"key":"h","name":"H","pos":"RB","fv":65.0},
        {"key":"i","name":"I","pos":"TE","fv":45.0},
        {"key":"j","name":"J","pos":"DB","fv":60.0},
        {"key":"k","name":"K","pos":"LB","fv":55.0},
        {"key":"l","name":"L","pos":"DL","fv":40.0},
    ]
    pkg = construct_package(fake_target, players, 2.15)
    assert pkg is not None
    ratio = sum(p["fv"] for p in pkg) / 100.0
    assert abs(ratio - 2.15) <= MAX_RATIO_ERROR
    assert all(p["fv"] < 100.0 for p in pkg)
    print("Package Preference V4 generator self-test passed.")

def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    players, player_index = player_universe()
    v3 = read_json(V3_CATALOG)
    if v3.get("status") != "frozen_package_preference_v3" or v3.get("frozen") is not True:
        raise RuntimeError("V3 catalog must remain frozen before V4 generation")

    v3_targets = v3.get("targets") or []
    if len(v3_targets) < 14:
        raise RuntimeError("V3 target list unexpectedly small")

    challenges = []
    selected_targets = []
    skipped = []

    for meta in v3_targets:
        key = normalize_name(meta.get("name"))
        anchor = player_index.get(key)
        if anchor is None:
            skipped.append({"name": meta.get("name"), "reason": "missing_current_rostered_FV"})
            continue

        cells = []
        ok = True
        for ratio in RATIO_TARGETS:
            pkg = construct_package(anchor, players, ratio)
            if pkg is None:
                ok = False
                skipped.append({
                    "name": anchor["name"],
                    "ratio": ratio,
                    "reason": "could_not_construct_complete_grid",
                })
                break
            cells.append((ratio, pkg))

        if not ok:
            continue

        selected_targets.append({
            "key": anchor["key"],
            "name": anchor["name"],
            "pos": anchor["pos"],
            "tier": meta.get("tier"),
            "rank_within_position": meta.get("rank_within_position"),
            "fv": anchor["fv"],
            "v3_target_fv": meta.get("fv"),
        })
        for ratio, pkg in cells:
            challenges.append(challenge_record(anchor, pkg, ratio, meta))

    by_target = validate(challenges)

    ratio_counts = Counter(f"{float(c['ratio_target']):.2f}" for c in challenges)
    pos_counts = Counter(c["target"]["pos"] for c in challenges)
    tier_counts = Counter(c.get("target_tier") or "unknown" for c in challenges)

    payload = {
        "schema_version": 4,
        "status": "frozen_package_preference_v4",
        "frozen": True,
        "consumer_changed": False,
        "production_formula_enabled": False,
        "purpose": (
            "Targeted 3-player package extension to empirically bracket the "
            "50% indifference point suggested by V3."
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": {
            "value_uncertainty": sha256(VALUES),
            "league_rosters": sha256(ROSTERS),
            "v3_catalog": sha256(V3_CATALOG),
        },
        "design": {
            "package_sizes": [3],
            "ratio_targets": list(RATIO_TARGETS),
            "component_weights": list(COMPONENT_WEIGHTS),
            "v3_overlap_ratio": 1.85,
            "same_v3_targets_requested": True,
            "values_hidden_from_voter": True,
            "display_side_randomized": True,
            "own_roster_exclusion_expected_in_browser": True,
            "v3_reuse_policy": (
                "V3 remains frozen. V4-only is primary for the 3-player extension; "
                "V3 may be reused only as a separately labeled lower-ratio sensitivity."
            ),
        },
        "catalog_diagnostics": {
            "challenge_count": len(challenges),
            "target_count": len(by_target),
            "ratio_counts": dict(sorted(ratio_counts.items())),
            "target_position_counts": dict(sorted(pos_counts.items())),
            "target_tier_counts": dict(sorted(tier_counts.items())),
            "skipped_targets_or_cells": skipped,
        },
        "targets": selected_targets,
        "challenges": challenges,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print("V4 challenges:", len(challenges))
    print("V4 targets:", len(by_target))
    print("Ratio counts:", dict(sorted(ratio_counts.items())))

if __name__ == "__main__":
    main()

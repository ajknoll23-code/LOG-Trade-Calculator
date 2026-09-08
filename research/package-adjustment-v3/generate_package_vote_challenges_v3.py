#!/usr/bin/env python3
from __future__ import annotations

import bisect
import hashlib
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
OUT = ROOT / "research" / "package-adjustment-v3" / "package_vote_challenges_v3.json"

# V3 is an indifference experiment, not another FG test.  The range deliberately
# extends well past V2's 0.95-1.30 window so the package choice curve has a chance
# to cross 50%.
RATIO_TARGETS = (1.10, 1.25, 1.40, 1.60, 1.85)
PACKAGE_SIZES = (2, 3)
TARGET_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
TARGET_TIER_RANKS = {
    "elite": (0, 1, 2),
    "premium": (3, 4, 5, 6, 7),
    "starter": (8, 9, 10, 11, 12, 13, 14, 15),
}
# Target package shapes standardize composition enough to identify ratio and
# package-count effects without pretending composition is irrelevant.
COMPONENT_WEIGHTS = {
    2: (0.51, 0.49),
    3: (0.45, 0.33, 0.22),
}
MIN_PIECE_TO_TARGET = 0.06
MAX_PIECE_TO_TARGET = 0.98
MAX_RATIO_ERROR = 0.035
MAX_COMPONENT_ERROR_TO_TARGET = 0.085
MIN_ANCHORS = 14
MIN_CHALLENGES = 140
MAX_PLAYER_APPEARANCE_SOFT = 14

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

def slug(value):
    s = normalize_name(value)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")

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

def nearest_player(candidates, desired, excluded, appearance_counts):
    vals = [p["fv"] for p in candidates]
    k0 = bisect.bisect_left(vals, desired)
    best = None
    for k in range(max(0, k0 - 18), min(len(candidates), k0 + 19)):
        p = candidates[k]
        if p["key"] in excluded:
            continue
        # Tight value matching dominates; a small reuse penalty improves catalog
        # diversity without breaking the intended package shape.
        score = (
            abs(float(p["fv"]) - desired),
            max(0, appearance_counts[p["key"]] - MAX_PLAYER_APPEARANCE_SOFT) * 0.005 * max(desired, 1.0),
            p["key"],
        )
        if best is None or score < best[0]:
            best = (score, p)
    return None if best is None else best[1]

def construct_package(anchor, players, ratio_target, package_size, appearance_counts):
    target = float(anchor["fv"])
    total_goal = target * float(ratio_target)
    weights = COMPONENT_WEIGHTS[int(package_size)]

    candidates = [
        p for p in players
        if p["key"] != anchor["key"]
        and target * MIN_PIECE_TO_TARGET <= float(p["fv"]) <= target * MAX_PIECE_TO_TARGET
    ]
    candidates.sort(key=lambda p: (float(p["fv"]), p["key"]))
    if len(candidates) < package_size + 4:
        return None

    package = []
    excluded = {anchor["key"]}
    for share in weights:
        desired = total_goal * float(share)
        p = nearest_player(candidates, desired, excluded, appearance_counts)
        if p is None:
            return None
        if abs(float(p["fv"]) - desired) / target > MAX_COMPONENT_ERROR_TO_TARGET:
            return None
        package.append(p)
        excluded.add(p["key"])

    total = sum(float(p["fv"]) for p in package)
    ratio = total / target
    if abs(ratio - ratio_target) > MAX_RATIO_ERROR:
        return None

    # Every piece must remain strictly below the concentrated target.
    if any(float(p["fv"]) >= target for p in package):
        return None

    return package

def target_candidates_by_tier(players, pos):
    pool = [p for p in players if p["pos"] == pos]
    out = {}
    for tier, ranks in TARGET_TIER_RANKS.items():
        out[tier] = [(r, pool[r]) for r in ranks if r < len(pool)]
    return out

def challenge_record(anchor, package, ratio_target, package_size, tier, rank_within_pos):
    target = float(anchor["fv"])
    total = sum(float(p["fv"]) for p in package)
    ratio = total / target
    ratio_code = int(round(float(ratio_target) * 100))
    cid = f"pkgv3_{anchor['pos'].lower()}_{slug(anchor['name'])}_{ratio_code}_{package_size}x"
    component_target_shares = [float(p["fv"]) / target for p in package]
    return {
        "id": cid,
        "schema_version": 3,
        "experiment": "package_indifference_v3",
        "target_tier": tier,
        "target_rank_within_position": int(rank_within_pos),
        "target": {
            "key": anchor["key"],
            "name": anchor["name"],
            "pos": anchor["pos"],
            "team": anchor.get("team"),
            "age": anchor.get("age"),
            "fv": round(target, 3),
        },
        "package": [{
            "key": p["key"],
            "name": p["name"],
            "pos": p["pos"],
            "team": p.get("team"),
            "age": p.get("age"),
            "fv": round(float(p["fv"]), 3),
        } for p in package],
        "package_size": int(package_size),
        "target_fv": round(target, 3),
        "package_fv": round(total, 3),
        "raw_package_to_target_ratio": round(ratio, 6),
        "ratio_target": float(ratio_target),
        "component_profile": {
            "intended_package_shares": list(COMPONENT_WEIGHTS[int(package_size)]),
            "actual_piece_to_target_shares": [round(x, 6) for x in component_target_shares],
            "largest_piece_to_target": round(max(component_target_shares), 6),
        },
    }

def validate_catalog(challenges):
    ids = [c["id"] for c in challenges]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate V3 challenge ids")
    if len(challenges) < MIN_CHALLENGES:
        raise RuntimeError(f"V3 challenge catalog too small: {len(challenges)}")

    targets = {c["target"]["key"] for c in challenges}
    if len(targets) < MIN_ANCHORS:
        raise RuntimeError(f"too few V3 targets: {len(targets)}")

    by_target = defaultdict(list)
    for c in challenges:
        by_target[c["target"]["key"]].append(c)
        if c["package_size"] not in PACKAGE_SIZES:
            raise RuntimeError("unexpected package size")
        if c["ratio_target"] not in RATIO_TARGETS:
            raise RuntimeError("unexpected ratio target")
        if any(float(p["fv"]) >= float(c["target_fv"]) for p in c["package"]):
            raise RuntimeError(f"{c['id']}: package piece is not below target FV")

    # Selected targets should carry the complete 5x2 grid. This lets target-
    # fixed-effect diagnostics compare ratio/package size within the same target.
    expected_cells = {(float(r), int(s)) for r in RATIO_TARGETS for s in PACKAGE_SIZES}
    for target_key, rows in by_target.items():
        cells = {(float(c["ratio_target"]), int(c["package_size"])) for c in rows}
        if cells != expected_cells:
            raise RuntimeError(f"{target_key}: incomplete V3 ratio/size grid")

    pos_counts = Counter(c["target"]["pos"] for c in challenges)
    missing_pos = [p for p in TARGET_POSITIONS if pos_counts[p] < 10]
    if missing_pos:
        raise RuntimeError(f"insufficient position coverage: {missing_pos}")

    tier_counts = Counter(c["target_tier"] for c in challenges)
    missing_tiers = [t for t in TARGET_TIER_RANKS if tier_counts[t] < 20]
    if missing_tiers:
        raise RuntimeError(f"insufficient target-tier coverage: {missing_tiers}")

    return by_target

def selftest():
    fake = {
        "key":"target","name":"Target","pos":"WR","team":"ARI","age":25,"fv":100.0
    }
    p1={"key":"a","name":"A","pos":"WR","fv":71.0}
    p2={"key":"b","name":"B","pos":"RB","fv":69.0}
    c=challenge_record(fake,[p1,p2],1.40,2,"premium",4)
    assert c["schema_version"] == 3
    assert c["package_size"] == 2
    assert abs(c["raw_package_to_target_ratio"] - 1.40) < 1e-9
    assert c["component_profile"]["largest_piece_to_target"] < 1.0
    print("Package Preference V3 generator self-test passed.")

def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    values_doc = read_json(VALUES)
    rosters_doc = read_json(ROSTERS)

    value_index = {}
    for name, row in (values_doc.get("players") or {}).items():
        fv = finite(row.get("center_value"))
        pos = normalize_pos(row.get("pos"))
        if fv is None or fv <= 0 or not pos or pos == "K":
            continue
        value_index[normalize_name(name)] = {"fv": fv, "pos": pos}

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
                    "fv": float(row["fv"]),
                    "team": raw.get("team"),
                    "age": raw.get("age"),
                }

    players = sorted(rostered.values(), key=lambda p: (-p["fv"], p["key"]))
    if len(players) < 350:
        raise RuntimeError(f"too few rostered valued players: {len(players)}")

    appearance_counts = Counter()
    challenges = []
    selected_targets = []

    # One fully constructible target per tier per position.  Each selected target
    # contributes the complete 5 ratio x 2 package-size grid.
    for pos in TARGET_POSITIONS:
        tiers = target_candidates_by_tier(players, pos)
        for tier in ("elite", "premium", "starter"):
            chosen = None
            for rank_within_pos, anchor in tiers[tier]:
                cells = []
                ok = True
                for ratio in RATIO_TARGETS:
                    for size in PACKAGE_SIZES:
                        pkg = construct_package(anchor, players, ratio, size, appearance_counts)
                        if pkg is None:
                            ok = False
                            break
                        cells.append((ratio, size, pkg))
                    if not ok:
                        break
                if ok:
                    chosen = (rank_within_pos, anchor, cells)
                    break
            if chosen is None:
                print(f"  NOTE: no fully constructible V3 target for {pos}/{tier}; skipping cell")
                continue

            rank_within_pos, anchor, cells = chosen
            selected_targets.append({
                "key": anchor["key"],
                "name": anchor["name"],
                "pos": pos,
                "tier": tier,
                "rank_within_position": rank_within_pos,
                "fv": anchor["fv"],
            })
            for ratio, size, pkg in cells:
                ch = challenge_record(anchor, pkg, ratio, size, tier, rank_within_pos)
                challenges.append(ch)
                for p in pkg:
                    appearance_counts[p["key"]] += 1

    by_target = validate_catalog(challenges)

    ratio_counts = Counter(f"{float(c['ratio_target']):.2f}" for c in challenges)
    size_counts = Counter(str(c["package_size"]) for c in challenges)
    pos_counts = Counter(c["target"]["pos"] for c in challenges)
    tier_counts = Counter(c["target_tier"] for c in challenges)

    payload = {
        "schema_version": 3,
        "status": "frozen_package_preference_v3",
        "frozen": True,
        "consumer_changed": False,
        "production_formula_enabled": False,
        "purpose": (
            "Estimate the package/target FV ratio required to reach human trade "
            "indifference, with package-size and target-value sensitivity."
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": {
            "value_uncertainty": sha256(VALUES),
            "league_rosters": sha256(ROSTERS),
        },
        "design": {
            "ratio_targets": list(RATIO_TARGETS),
            "package_sizes": list(PACKAGE_SIZES),
            "target_positions": list(TARGET_POSITIONS),
            "target_tiers": list(TARGET_TIER_RANKS),
            "component_weights": {str(k): list(v) for k, v in COMPONENT_WEIGHTS.items()},
            "values_hidden_from_voter": True,
            "display_side_randomized": True,
            "own_roster_exclusion_expected_in_browser": True,
            "v2_reuse_policy": (
                "V2 remains frozen and may be used only as a separately labeled "
                "lower-ratio sensitivity dataset. V3-only fit is primary."
            ),
        },
        "catalog_diagnostics": {
            "challenge_count": len(challenges),
            "target_count": len(by_target),
            "ratio_counts": dict(sorted(ratio_counts.items())),
            "package_size_counts": dict(sorted(size_counts.items())),
            "target_position_counts": dict(sorted(pos_counts.items())),
            "target_tier_counts": dict(sorted(tier_counts.items())),
            "max_player_package_appearances": max(appearance_counts.values()) if appearance_counts else 0,
        },
        "targets": selected_targets,
        "challenges": challenges,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  challenges={len(challenges)} targets={len(by_target)}")
    print(f"  ratios={dict(sorted(ratio_counts.items()))}")

if __name__ == "__main__":
    main()

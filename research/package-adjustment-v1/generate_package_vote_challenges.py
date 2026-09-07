#!/usr/bin/env python3
from __future__ import annotations

import bisect
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALUES = ROOT / "scripts" / "artifacts" / "generated" / "value_uncertainty.json"
ROSTERS = ROOT / "data" / "league_rosters.json"
OUT = ROOT / "research" / "package-adjustment-v1" / "package_vote_challenges.json"

RATIO_TARGETS = (0.95, 1.05, 1.15, 1.30)
PACKAGE_SIZES = (2, 3)
ANCHORS_PER_POSITION = 2
MAX_PIECE_TO_TARGET = 0.85
MIN_PIECE_TO_TARGET = 0.06
MAX_RATIO_ERROR = 0.025

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

def fragmentation(values):
    total = sum(values)
    if total <= 0:
        return 0.0
    return 1.0 - sum((v / total) ** 2 for v in values)

def nearest_two(candidates, desired, used):
    i, j = 0, len(candidates) - 1
    best = None
    while i < j:
        a, b = candidates[i], candidates[j]
        total = a["fv"] + b["fv"]
        key = tuple(sorted((a["key"], b["key"])))
        if key not in used:
            cand = (abs(total - desired), key, [a, b], total)
            if best is None or cand[:2] < best[:2]:
                best = cand
        if total < desired:
            i += 1
        else:
            j -= 1
    return best

def nearest_three(candidates, desired, used):
    vals = [p["fv"] for p in candidates]
    best = None
    n = len(candidates)
    for i in range(n - 2):
        for j in range(i + 1, n - 1):
            need = desired - candidates[i]["fv"] - candidates[j]["fv"]
            k0 = bisect.bisect_left(vals, need, j + 1)
            for k in (k0 - 1, k0, k0 + 1):
                if k <= j or k >= n:
                    continue
                trio = [candidates[i], candidates[j], candidates[k]]
                key = tuple(sorted(p["key"] for p in trio))
                if key in used:
                    continue
                total = sum(p["fv"] for p in trio)
                cand = (abs(total - desired), key, trio, total)
                if best is None or cand[:2] < best[:2]:
                    best = cand
    return best

def main():
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

    anchors = []
    for pos in ("QB","RB","WR","TE","DL","LB","DB"):
        anchors.extend([p for p in players if p["pos"] == pos][:ANCHORS_PER_POSITION])

    challenges = []
    used_packages = set()

    for anchor in anchors:
        target = anchor["fv"]
        candidates = [
            p for p in players
            if p["key"] != anchor["key"]
            and p["fv"] <= target * MAX_PIECE_TO_TARGET
            and p["fv"] >= target * MIN_PIECE_TO_TARGET
        ]
        candidates.sort(key=lambda p: (p["fv"], p["key"]))

        for size in PACKAGE_SIZES:
            for ratio_target in RATIO_TARGETS:
                desired = target * ratio_target
                found = (
                    nearest_two(candidates, desired, used_packages)
                    if size == 2
                    else nearest_three(candidates, desired, used_packages)
                )
                if not found:
                    continue

                _err, package_key, package, total = found
                actual_ratio = total / target
                if abs(actual_ratio - ratio_target) > MAX_RATIO_ERROR:
                    continue

                used_packages.add(package_key)
                frag = fragmentation([p["fv"] for p in package])
                gap = max(0.0, 1.0 - max(p["fv"] for p in package) / target)
                challenge_id = (
                    f"pkgv1_{anchor['pos'].lower()}_"
                    f"{anchor['key'].replace(' ', '_')}_"
                    f"{size}x_{int(round(ratio_target * 100)):03d}"
                )

                challenges.append({
                    "id": challenge_id,
                    "schema_version": 1,
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
                        "fv": round(p["fv"], 3),
                    } for p in package],
                    "package_size": size,
                    "target_fv": round(target, 3),
                    "package_fv": round(total, 3),
                    "raw_package_to_target_ratio": round(actual_ratio, 6),
                    "ratio_target": ratio_target,
                    "fragmentation": round(frag, 8),
                    "best_asset_gap": round(gap, 8),
                    "fg": round(frag * gap, 8),
                })

    ids = [c["id"] for c in challenges]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate package challenge ids")
    if len(challenges) < 70:
        raise RuntimeError(f"challenge catalog too small: {len(challenges)}")

    by_size, by_pos, by_ratio = {}, {}, {}
    for c in challenges:
        by_size[str(c["package_size"])] = by_size.get(str(c["package_size"]), 0) + 1
        pos = c["target"]["pos"]
        by_pos[pos] = by_pos.get(pos, 0) + 1
        key = f"{c['ratio_target']:.2f}"
        by_ratio[key] = by_ratio.get(key, 0) + 1

    doc = {
        "schema_version": 1,
        "status": "frozen_package_preference_v1",
        "consumer_changed": False,
        "frozen": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "regeneration_policy": "Do not regenerate from vote outcomes; future changes require a versioned V2.",
        "display_policy": "Names/team/position/age only. Fundamental values and geometry stay hidden.",
        "source_sha256": {
            str(VALUES.relative_to(ROOT)): sha256(VALUES),
            str(ROSTERS.relative_to(ROOT)): sha256(ROSTERS),
        },
        "design": {
            "ratio_targets": list(RATIO_TARGETS),
            "package_sizes": list(PACKAGE_SIZES),
            "anchors_per_position": ANCHORS_PER_POSITION,
            "max_piece_to_target": MAX_PIECE_TO_TARGET,
            "min_piece_to_target": MIN_PIECE_TO_TARGET,
            "max_ratio_error": MAX_RATIO_ERROR,
            "pick_assets_included": False,
        },
        "counts": {
            "challenge_count": len(challenges),
            "by_package_size": by_size,
            "by_target_position": by_pos,
            "by_ratio_target": by_ratio,
        },
        "challenges": challenges,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} with {len(challenges)} challenges")

if __name__ == "__main__":
    main()

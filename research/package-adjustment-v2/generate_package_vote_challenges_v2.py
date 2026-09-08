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
OUT = ROOT / "research" / "package-adjustment-v2" / "package_vote_challenges_v2.json"

RATIO_TARGETS = (0.95, 1.05, 1.15, 1.30)
PACKAGE_SIZES = (2, 3)
TARGET_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
ANCHOR_TIER_RANKS = {
    "elite": (0, 1, 2),
    "high": (3, 4, 5, 6),
    "upper_mid": (7, 8, 9, 10, 11, 12),
}
MIN_MATCHED_PAIRS_PER_ANCHOR = 3

MIN_PIECE_TO_TARGET = 0.05
MAX_PIECE_TO_TARGET = 0.80
MIN_SHARED_TO_TARGET = 0.48
MAX_SHARED_TO_TARGET = 0.80
MIN_SPLIT_SOURCE_TO_TARGET = 0.12
MAX_RATIO_ERROR = 0.020
MAX_PAIR_RATIO_GAP = 0.010
MAX_SPLIT_ERROR_TO_TARGET = 0.015
MIN_CHALLENGES = 120
MAX_PLAYER_APPEARANCE_SOFT = 8

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


def geometry(package, target):
    vals = [float(p["fv"]) for p in package]
    frag = fragmentation(vals)
    gap = max(0.0, 1.0 - max(vals) / target)
    return {
        "fragmentation": frag,
        "best_asset_gap": gap,
        "fg": frag * gap,
    }


def nearest_value(candidates, desired, excluded):
    vals = [p["fv"] for p in candidates]
    k0 = bisect.bisect_left(vals, desired)
    best = None
    for k in range(max(0, k0 - 4), min(len(candidates), k0 + 5)):
        p = candidates[k]
        if p["key"] in excluded:
            continue
        cand = (abs(p["fv"] - desired), p["key"], p)
        if best is None or cand < best:
            best = cand
    return None if best is None else best[2]


def nearest_split_pair(candidates, desired, excluded, max_piece_fv):
    vals = [p["fv"] for p in candidates]
    best = None
    n = len(candidates)
    for i in range(n - 1):
        a = candidates[i]
        if a["key"] in excluded or a["fv"] > max_piece_fv:
            continue
        need = desired - a["fv"]
        k0 = bisect.bisect_left(vals, need, i + 1)
        for j in (k0 - 2, k0 - 1, k0, k0 + 1, k0 + 2):
            if j <= i or j >= n:
                continue
            b = candidates[j]
            if b["key"] in excluded or b["fv"] > max_piece_fv:
                continue
            total = a["fv"] + b["fv"]
            cand = (abs(total - desired), tuple(sorted((a["key"], b["key"]))), [a, b], total)
            if best is None or cand[:2] < best[:2]:
                best = cand
    return best


def select_matched_pair(anchor, players, ratio_target, appearance_counts):
    target = float(anchor["fv"])
    desired_total = target * ratio_target

    candidates = [
        p for p in players
        if p["key"] != anchor["key"]
        and target * MIN_PIECE_TO_TARGET <= p["fv"] <= target * MAX_PIECE_TO_TARGET
    ]
    candidates.sort(key=lambda p: (p["fv"], p["key"]))
    if len(candidates) < 8:
        return None

    shared_candidates = [
        p for p in candidates
        if target * MIN_SHARED_TO_TARGET <= p["fv"] <= target * MAX_SHARED_TO_TARGET
    ]

    # Search many possible shared top assets. The matched 3-player challenge is
    # created by splitting only the secondary piece from the 2-player package:
    # [A, B] -> [A, C, D]. This holds the target, ratio, and strongest package
    # asset nearly fixed while changing fragmentation/package count.
    scored = []
    for shared in shared_candidates:
        desired_secondary = desired_total - shared["fv"]
        if desired_secondary < target * MIN_SPLIT_SOURCE_TO_TARGET:
            continue
        if desired_secondary > shared["fv"]:
            # shared asset must remain the strongest piece in both packages
            continue

        secondary = nearest_value(
            candidates,
            desired_secondary,
            {anchor["key"], shared["key"]},
        )
        if secondary is None or secondary["fv"] > shared["fv"]:
            continue
        if secondary["fv"] < target * MIN_SPLIT_SOURCE_TO_TARGET:
            continue

        split = nearest_split_pair(
            candidates,
            secondary["fv"],
            {anchor["key"], shared["key"], secondary["key"]},
            shared["fv"],
        )
        if not split:
            continue

        split_err, split_keys, split_players, split_total = split
        if split_err / target > MAX_SPLIT_ERROR_TO_TARGET:
            continue

        pkg2 = [shared, secondary]
        pkg3 = [shared] + split_players
        total2 = sum(p["fv"] for p in pkg2)
        total3 = sum(p["fv"] for p in pkg3)
        ratio2 = total2 / target
        ratio3 = total3 / target

        if abs(ratio2 - ratio_target) > MAX_RATIO_ERROR:
            continue
        if abs(ratio3 - ratio_target) > MAX_RATIO_ERROR:
            continue
        if abs(ratio2 - ratio3) > MAX_PAIR_RATIO_GAP:
            continue

        g2 = geometry(pkg2, target)
        g3 = geometry(pkg3, target)

        # Lower is better. First prioritize tight matching. A soft appearance
        # penalty spreads package pieces across the catalog without making
        # construction brittle.
        pieces = [p["key"] for p in pkg2 + split_players]
        reuse_penalty = sum(max(0, appearance_counts[k] - MAX_PLAYER_APPEARANCE_SOFT) for k in pieces)
        score = (
            abs(ratio2 - ratio_target)
            + abs(ratio3 - ratio_target)
            + 2.0 * abs(ratio2 - ratio3)
            + split_err / target
            + 0.002 * reuse_penalty
        )

        scored.append((
            score,
            tuple(sorted(p["key"] for p in pkg2)),
            tuple(sorted(p["key"] for p in pkg3)),
            pkg2,
            pkg3,
            ratio2,
            ratio3,
            g2,
            g3,
            secondary,
            split_players,
        ))

    if not scored:
        return None

    scored.sort(key=lambda x: x[:3])
    return scored[0]


def anchor_candidates_by_tier(players, pos):
    pool = [p for p in players if p["pos"] == pos]
    out = {}
    for tier, ranks in ANCHOR_TIER_RANKS.items():
        out[tier] = [pool[r] for r in ranks if r < len(pool)]
    return out



def challenge_record(anchor, package, package_size, ratio_target, pair_id, treatment, shared, secondary, split_players):
    target = float(anchor["fv"])
    total = sum(float(p["fv"]) for p in package)
    geom = geometry(package, target)
    challenge_id = f"{pair_id}_{package_size}x"

    return {
        "id": challenge_id,
        "schema_version": 2,
        "matched_pair_id": pair_id,
        "treatment": treatment,
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
        "package_size": package_size,
        "target_fv": round(target, 3),
        "package_fv": round(total, 3),
        "raw_package_to_target_ratio": round(total / target, 6),
        "ratio_target": ratio_target,
        "fragmentation": round(geom["fragmentation"], 8),
        "best_asset_gap": round(geom["best_asset_gap"], 8),
        "fg": round(geom["fg"], 8),
        # Hidden research metadata; browser rendering continues to show only
        # names/team/position/age.
        "matched_design": {
            "shared_top_asset_key": shared["key"],
            "secondary_split_source_key": secondary["key"],
            "secondary_split_replacement_keys": [p["key"] for p in split_players],
        },
    }


def validate_catalog(challenges):
    ids = [c["id"] for c in challenges]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate V2 challenge ids")
    if len(challenges) < MIN_CHALLENGES:
        raise RuntimeError(f"V2 challenge catalog too small: {len(challenges)}")

    by_pair = defaultdict(list)
    for c in challenges:
        by_pair[c["matched_pair_id"]].append(c)

    for pair_id, pair in by_pair.items():
        if len(pair) != 2:
            raise RuntimeError(f"{pair_id}: expected exactly two matched challenges")
        sizes = {c["package_size"] for c in pair}
        if sizes != {2, 3}:
            raise RuntimeError(f"{pair_id}: expected package sizes 2 and 3")
        targets = {c["target"]["key"] for c in pair}
        if len(targets) != 1:
            raise RuntimeError(f"{pair_id}: target mismatch")
        ratios = [c["raw_package_to_target_ratio"] for c in pair]
        if abs(ratios[0] - ratios[1]) > MAX_PAIR_RATIO_GAP + 1e-9:
            raise RuntimeError(f"{pair_id}: matched ratio gap too large")

        shared = {c["matched_design"]["shared_top_asset_key"] for c in pair}
        if len(shared) != 1:
            raise RuntimeError(f"{pair_id}: shared top asset mismatch")

    pos_counts = Counter(c["target"]["pos"] for c in challenges)
    missing = [pos for pos in TARGET_POSITIONS if pos_counts[pos] < 8]
    if missing:
        raise RuntimeError(f"insufficient V2 target-position coverage: {missing}")

    return by_pair


def selftest():
    assert abs(fragmentation([50, 50]) - 0.5) < 1e-12
    assert fragmentation([100]) == 0.0

    fake_anchor = {"key":"target","name":"Target","pos":"WR","fv":100.0}
    fake_shared = {"key":"a","name":"A","pos":"WR","fv":60.0}
    fake_b = {"key":"b","name":"B","pos":"RB","fv":40.0}
    fake_c = {"key":"c","name":"C","pos":"RB","fv":22.0}
    fake_d = {"key":"d","name":"D","pos":"TE","fv":18.0}
    pair_id = "pkgv2_wr_target_100"
    c2 = challenge_record(fake_anchor,[fake_shared,fake_b],2,1.0,pair_id,"two_player",fake_shared,fake_b,[fake_c,fake_d])
    c3 = challenge_record(fake_anchor,[fake_shared,fake_c,fake_d],3,1.0,pair_id,"secondary_split_three_player",fake_shared,fake_b,[fake_c,fake_d])
    # Override minimum only for this local validation.
    assert c2["matched_pair_id"] == c3["matched_pair_id"]
    assert abs(c2["raw_package_to_target_ratio"] - c3["raw_package_to_target_ratio"]) < 1e-9
    assert c3["fragmentation"] > c2["fragmentation"]
    print("Package Preference V2 generator self-test passed.")


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
    selected_anchors = []

    # Pick one constructible anchor from each value tier in every position.
    # Requiring at least three of four ratio cells per selected anchor avoids
    # filling the catalog with targets that cannot support the matched design.
    for pos in TARGET_POSITIONS:
        tier_candidates = anchor_candidates_by_tier(players, pos)
        for tier in ("elite", "high", "upper_mid"):
            chosen = None
            chosen_rows = None

            for anchor in tier_candidates[tier]:
                candidate_rows = []
                for ratio_target in RATIO_TARGETS:
                    found = select_matched_pair(
                        anchor, players, ratio_target, appearance_counts
                    )
                    if not found:
                        continue
                    candidate_rows.append((ratio_target, found))

                if len(candidate_rows) >= MIN_MATCHED_PAIRS_PER_ANCHOR:
                    chosen = anchor
                    chosen_rows = candidate_rows
                    break

            if chosen is None:
                raise RuntimeError(
                    f"no constructible {tier} anchor for {pos} with "
                    f"{MIN_MATCHED_PAIRS_PER_ANCHOR}+ matched ratio cells"
                )

            selected_anchors.append({
                "key": chosen["key"],
                "name": chosen["name"],
                "pos": chosen["pos"],
                "tier": tier,
            })

            for ratio_target, found in chosen_rows:
                (
                    _score, _key2, _key3, pkg2, pkg3, ratio2, ratio3,
                    _g2, _g3, secondary, split_players
                ) = found
                shared = pkg2[0]
                pair_id = (
                    f"pkgv2_{chosen['pos'].lower()}_"
                    f"{chosen['key'].replace(' ', '_')}_"
                    f"{int(round(ratio_target * 100)):03d}"
                )

                challenges.append(challenge_record(
                    chosen, pkg2, 2, ratio_target, pair_id,
                    "two_player", shared, secondary, split_players
                ))
                challenges.append(challenge_record(
                    chosen, pkg3, 3, ratio_target, pair_id,
                    "secondary_split_three_player", shared, secondary, split_players
                ))

                for p in pkg2 + split_players:
                    appearance_counts[p["key"]] += 1

    by_pair = validate_catalog(challenges)

    by_size = Counter(str(c["package_size"]) for c in challenges)
    by_pos = Counter(c["target"]["pos"] for c in challenges)
    by_ratio = Counter(f"{c['ratio_target']:.2f}" for c in challenges)
    by_anchor = Counter(c["target"]["key"] for c in challenges)

    # Catalog-level predictor collinearity audit.
    mean_fg = sum(c["fg"] for c in challenges) / len(challenges)
    mean_size = sum(1 if c["package_size"] == 3 else 0 for c in challenges) / len(challenges)
    cov = sum((c["fg"]-mean_fg)*((1 if c["package_size"]==3 else 0)-mean_size) for c in challenges) / len(challenges)
    var_fg = sum((c["fg"]-mean_fg)**2 for c in challenges) / len(challenges)
    var_size = sum(((1 if c["package_size"]==3 else 0)-mean_size)**2 for c in challenges) / len(challenges)
    corr = cov / math.sqrt(var_fg * var_size) if var_fg > 0 and var_size > 0 else None

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 2,
        "status": "frozen_package_preference_v2",
        "consumer_changed": False,
        "frozen": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "regeneration_policy": (
            "Freeze after initial generation. Never regenerate from vote outcomes; "
            "future design changes require V3."
        ),
        "display_policy": (
            "Names/team/position/age only. Fundamental values, matched-pair metadata, "
            "and geometry stay hidden from voters."
        ),
        "research_question": (
            "Identify whether package size or FG explains consolidation preference by "
            "matching [A,B] against [A,C,D] around the same target and raw FV ratio."
        ),
        "source_sha256": {
            str(VALUES.relative_to(ROOT)): sha256(VALUES),
            str(ROSTERS.relative_to(ROOT)): sha256(ROSTERS),
        },
        "design": {
            "ratio_targets": list(RATIO_TARGETS),
            "package_sizes": list(PACKAGE_SIZES),
            "target_positions": list(TARGET_POSITIONS),
            "anchor_tier_candidate_ranks": {
                tier: list(ranks) for tier, ranks in ANCHOR_TIER_RANKS.items()
            },
            "minimum_matched_ratio_cells_per_anchor": MIN_MATCHED_PAIRS_PER_ANCHOR,
            "matched_secondary_split": True,
            "matched_pair_ratio_gap_max": MAX_PAIR_RATIO_GAP,
            "max_ratio_error": MAX_RATIO_ERROR,
            "min_piece_to_target": MIN_PIECE_TO_TARGET,
            "max_piece_to_target": MAX_PIECE_TO_TARGET,
            "pick_assets_included": False,
            "candidate_models": [
                "raw_ratio_only",
                "raw_ratio_plus_package_size",
                "raw_ratio_plus_fg",
                "raw_ratio_plus_package_size_plus_fg",
                "matched_pair_fixed_effects",
            ],
        },
        "counts": {
            "challenge_count": len(challenges),
            "matched_pair_count": len(by_pair),
            "anchor_count": len(by_anchor),
            "by_package_size": dict(sorted(by_size.items())),
            "by_target_position": dict(sorted(by_pos.items())),
            "by_ratio_target": dict(sorted(by_ratio.items())),
        },
        "selected_anchors": selected_anchors,
        "catalog_diagnostics": {
            "fg_vs_size3_correlation": corr,
            "max_player_package_appearances": max(appearance_counts.values()) if appearance_counts else 0,
        },
        "challenges": challenges,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Wrote {OUT.relative_to(ROOT)} with {len(challenges)} challenges "
        f"across {len(by_pair)} matched pairs and {len(by_anchor)} anchors"
    )


if __name__ == "__main__":
    main()

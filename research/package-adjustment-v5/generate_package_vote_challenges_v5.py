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
OUT = ROOT / "research" / "package-adjustment-v5" / "package_vote_challenges_v5.json"
OUT_MD = ROOT / "research" / "package-adjustment-v5" / "composition_study_design.md"

# V5 isolates two-player composition instead of package count.
# Composition is defined as share of total package FV, largest piece first.
COMPOSITIONS = (
    (0.50, 0.50),
    (0.55, 0.45),
    (0.60, 0.40),
    (0.65, 0.35),
    (0.70, 0.30),
    (0.75, 0.25),
)

# Broad shared ratio grid. Cells are included only when the intended largest
# package piece remains below the target FV. This produces a natural feasible
# frontier rather than pretending 75/25 can exist at a 1.85x total ratio.
RATIO_GRID = (1.10, 1.20, 1.30, 1.40, 1.50, 1.60, 1.75)

PACKAGE_SIZE = 2
MIN_PIECE_TO_TARGET = 0.06
MAX_PIECE_TO_TARGET = 0.985
MAX_RATIO_ERROR = 0.035
MAX_PACKAGE_SHARE_ERROR = 0.025
NEAREST_POOL = 30

MIN_TARGETS = 14
MIN_CHALLENGES = 250
MIN_TARGETS_PER_COMPOSITION = 10
MIN_CHALLENGES_PER_COMPOSITION = 30

TARGET_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")

POS_MAP = {
    "QB":"QB","RB":"RB","WR":"WR","TE":"TE","K":"K",
    "DL":"DL","DE":"DL","DT":"DL",
    "LB":"LB","OLB":"LB","ILB":"LB",
    "DB":"DB","CB":"DB","S":"DB","SS":"DB","FS":"DB",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def split_code(split):
    return f"{int(round(split[0]*100)):02d}_{int(round(split[1]*100)):02d}"


def feasible_ratios(split):
    largest = float(split[0])
    return tuple(
        r for r in RATIO_GRID
        if largest * float(r) <= MAX_PIECE_TO_TARGET + 1e-12
    )


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

    players = sorted(rostered.values(), key=lambda p: (float(p["fv"]), p["key"]))
    if len(players) < 350:
        raise RuntimeError(f"too few rostered valued players: {len(players)}")
    return players, {p["key"]: p for p in players}


def nearest_candidates(players, desired, target_fv, target_key):
    allowed = [
        p for p in players
        if p["key"] != target_key
        and target_fv * MIN_PIECE_TO_TARGET <= float(p["fv"]) < target_fv
    ]
    allowed.sort(key=lambda p: (abs(float(p["fv"]) - desired), p["key"]))
    return allowed[:NEAREST_POOL]


def construct_package(anchor, players, ratio_target, split):
    target_fv = float(anchor["fv"])
    total_goal = target_fv * float(ratio_target)
    desired = [total_goal * float(w) for w in split]

    if max(desired) > target_fv * MAX_PIECE_TO_TARGET + 1e-9:
        return None

    pools = [
        nearest_candidates(players, d, target_fv, anchor["key"])
        for d in desired
    ]
    if any(len(pool) < 4 for pool in pools):
        return None

    best = None
    for pair in itertools.product(*pools):
        if pair[0]["key"] == pair[1]["key"]:
            continue
        vals = [float(pair[0]["fv"]), float(pair[1]["fv"])]
        if any(v >= target_fv for v in vals):
            continue
        if any(v < target_fv * MIN_PIECE_TO_TARGET for v in vals):
            continue

        total = sum(vals)
        ratio = total / target_fv
        ratio_err = abs(ratio - float(ratio_target))
        if ratio_err > MAX_RATIO_ERROR:
            continue

        ordered = sorted(vals, reverse=True)
        actual_split = [ordered[0] / total, ordered[1] / total]
        share_errs = [
            abs(actual_split[0] - float(split[0])),
            abs(actual_split[1] - float(split[1])),
        ]
        if max(share_errs) > MAX_PACKAGE_SHARE_ERROR:
            continue

        component_err = sum(
            abs(v - d) / target_fv
            for v, d in zip(vals, desired)
        )
        score = (
            ratio_err,
            max(share_errs),
            sum(share_errs),
            component_err,
            tuple(sorted(p["key"] for p in pair)),
        )
        if best is None or score < best[0]:
            best = (score, list(pair))

    if best is None:
        return None

    # Canonicalize package order largest-to-smallest for stable composition fields.
    return sorted(best[1], key=lambda p: (-float(p["fv"]), p["key"]))


def challenge_record(anchor, package, ratio_target, split, target_meta):
    target_fv = float(anchor["fv"])
    vals = [float(p["fv"]) for p in package]
    package_fv = sum(vals)
    ratio = package_fv / target_fv
    actual_split = [v / package_fv for v in vals]
    slug = re.sub(r"[^a-z0-9]+", "_", normalize_name(anchor["name"])).strip("_")
    ratio_code = int(round(float(ratio_target) * 100))
    scode = split_code(split)

    return {
        "id": f"pkgv5_{anchor['pos'].lower()}_{slug}_{scode}_{ratio_code}_2x",
        "schema_version": 5,
        "experiment": "package_indifference_v5_two_player_composition",
        "target_tier": target_meta.get("tier"),
        "target_rank_within_position": target_meta.get("rank_within_position"),
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
        "package_size": 2,
        "target_fv": round(target_fv, 3),
        "package_fv": round(package_fv, 3),
        "raw_package_to_target_ratio": round(ratio, 6),
        "ratio_target": float(ratio_target),
        "composition_target": {
            "largest_package_share": float(split[0]),
            "smallest_package_share": float(split[1]),
            "label": f"{int(round(split[0]*100))}/{int(round(split[1]*100))}",
        },
        "component_profile": {
            "intended_package_shares": list(split),
            "actual_package_shares": [round(x, 6) for x in actual_split],
            "largest_piece_to_target": round(vals[0] / target_fv, 6),
            "smallest_piece_to_target": round(vals[1] / target_fv, 6),
        },
    }


def validate(challenges):
    if len(challenges) < MIN_CHALLENGES:
        raise RuntimeError(f"V5 catalog too small: {len(challenges)}")

    ids = [c["id"] for c in challenges]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate V5 challenge IDs")

    target_keys = {c["target"]["key"] for c in challenges}
    if len(target_keys) < MIN_TARGETS:
        raise RuntimeError(f"too few V5 targets: {len(target_keys)}")

    comp_rows = defaultdict(list)
    comp_targets = defaultdict(set)
    for c in challenges:
        if c["package_size"] != 2:
            raise RuntimeError("V5 must remain 2-player only")
        if c["target"]["pos"] not in TARGET_POSITIONS:
            raise RuntimeError(f"unsupported target position in V5: {c['target']['pos']}")
        if any(float(p["fv"]) >= float(c["target_fv"]) for p in c["package"]):
            raise RuntimeError(f"{c['id']}: package piece >= target FV")
        if abs(float(c["raw_package_to_target_ratio"]) - float(c["ratio_target"])) > MAX_RATIO_ERROR:
            raise RuntimeError(f"{c['id']}: ratio outside tolerance")

        intended = c["component_profile"]["intended_package_shares"]
        actual = c["component_profile"]["actual_package_shares"]
        if max(abs(float(a)-float(b)) for a, b in zip(actual, intended)) > MAX_PACKAGE_SHARE_ERROR + 1e-9:
            raise RuntimeError(f"{c['id']}: composition outside tolerance")

        label = c["composition_target"]["label"]
        comp_rows[label].append(c)
        comp_targets[label].add(c["target"]["key"])

    expected_labels = {
        f"{int(round(s[0]*100))}/{int(round(s[1]*100))}"
        for s in COMPOSITIONS
    }
    if set(comp_rows) != expected_labels:
        raise RuntimeError(f"missing V5 composition bands: {expected_labels - set(comp_rows)}")

    for label in sorted(expected_labels):
        if len(comp_rows[label]) < MIN_CHALLENGES_PER_COMPOSITION:
            raise RuntimeError(f"{label}: too few challenges ({len(comp_rows[label])})")
        if len(comp_targets[label]) < MIN_TARGETS_PER_COMPOSITION:
            raise RuntimeError(f"{label}: too few targets ({len(comp_targets[label])})")

    return target_keys, comp_rows, comp_targets


def selftest():
    assert feasible_ratios((0.50, 0.50)) == RATIO_GRID
    assert 1.60 in feasible_ratios((0.60, 0.40))
    assert 1.75 not in feasible_ratios((0.60, 0.40))
    assert feasible_ratios((0.75, 0.25)) == (1.10, 1.20, 1.30)

    target = {"key":"t","name":"Target","pos":"WR","fv":100.0}
    players = [
        {"key":"a","name":"A","pos":"RB","fv":84.0},
        {"key":"b","name":"B","pos":"WR","fv":56.0},
        {"key":"c","name":"C","pos":"TE","fv":83.0},
        {"key":"d","name":"D","pos":"DB","fv":57.0},
        {"key":"e","name":"E","pos":"LB","fv":80.0},
        {"key":"f","name":"F","pos":"DL","fv":60.0},
        {"key":"g","name":"G","pos":"QB","fv":77.0},
        {"key":"h","name":"H","pos":"WR","fv":63.0},
    ]
    pkg = construct_package(target, players, 1.40, (0.60, 0.40))
    assert pkg is not None
    total = sum(p["fv"] for p in pkg)
    actual = max(p["fv"] for p in pkg) / total
    assert abs(total / 100.0 - 1.40) <= MAX_RATIO_ERROR
    assert abs(actual - 0.60) <= MAX_PACKAGE_SHARE_ERROR
    print("Package Preference V5 composition generator self-test passed.")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    players, player_index = player_universe()
    v3 = read_json(V3_CATALOG)
    if v3.get("status") != "frozen_package_preference_v3" or v3.get("frozen") is not True:
        raise RuntimeError("V3 catalog must remain frozen before V5 generation")

    v3_targets = v3.get("targets") or []
    if len(v3_targets) < 14:
        raise RuntimeError("V3 target list unexpectedly small")

    challenges = []
    selected_targets = {}
    skipped = []

    for meta in v3_targets:
        key = normalize_name(meta.get("name") or meta.get("key"))
        anchor = player_index.get(key)
        if anchor is None:
            skipped.append({
                "target": meta.get("name"),
                "reason": "missing_current_rostered_FV",
            })
            continue

        built_for_target = 0
        for split in COMPOSITIONS:
            for ratio in feasible_ratios(split):
                pkg = construct_package(anchor, players, ratio, split)
                if pkg is None:
                    skipped.append({
                        "target": anchor["name"],
                        "composition": f"{int(split[0]*100)}/{int(split[1]*100)}",
                        "ratio": ratio,
                        "reason": "could_not_construct_cell",
                    })
                    continue
                challenges.append(challenge_record(anchor, pkg, ratio, split, meta))
                built_for_target += 1

        if built_for_target:
            selected_targets[anchor["key"]] = {
                "key": anchor["key"],
                "name": anchor["name"],
                "pos": anchor["pos"],
                "tier": meta.get("tier"),
                "rank_within_position": meta.get("rank_within_position"),
                "fv": anchor["fv"],
                "v3_target_fv": meta.get("fv"),
                "constructed_cells": built_for_target,
            }

    target_keys, comp_rows, comp_targets = validate(challenges)

    ratio_counts = Counter(f"{float(c['ratio_target']):.2f}" for c in challenges)
    composition_counts = Counter(c["composition_target"]["label"] for c in challenges)
    position_counts = Counter(c["target"]["pos"] for c in challenges)
    tier_counts = Counter(str(c.get("target_tier") or "unknown") for c in challenges)

    by_composition_ratio = defaultdict(Counter)
    for c in challenges:
        by_composition_ratio[c["composition_target"]["label"]][
            f"{float(c['ratio_target']):.2f}"
        ] += 1

    payload = {
        "schema_version": 5,
        "status": "frozen_package_preference_v5",
        "frozen": True,
        "consumer_changed": False,
        "market_value_consumer_changed": False,
        "fundamental_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "trade_verdict_consumer_changed": False,
        "production_formula_enabled": False,
        "purpose": (
            "Measure how two-player package composition changes human consolidation "
            "preference and the package/target FV ratio required for indifference."
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": {
            "value_uncertainty": sha256(VALUES),
            "league_rosters": sha256(ROSTERS),
            "frozen_v3_catalog": sha256(V3_CATALOG),
        },
        "design": {
            "package_sizes": [2],
            "composition_targets": [list(x) for x in COMPOSITIONS],
            "composition_labels": [
                f"{int(round(x[0]*100))}/{int(round(x[1]*100))}"
                for x in COMPOSITIONS
            ],
            "ratio_grid": list(RATIO_GRID),
            "feasible_ratio_grid_by_composition": {
                f"{int(round(x[0]*100))}/{int(round(x[1]*100))}":
                    list(feasible_ratios(x))
                for x in COMPOSITIONS
            },
            "max_piece_to_target_for_intended_cell": MAX_PIECE_TO_TARGET,
            "max_actual_package_share_error": MAX_PACKAGE_SHARE_ERROR,
            "values_hidden_from_voter": True,
            "display_side_randomized": True,
            "same_frozen_v3_target_set_requested": True,
            "v3_reuse_policy": (
                "V3 remains frozen and unchanged. V5 is a new composition experiment. "
                "V3 may be used only as separately labeled 51/49 baseline evidence."
            ),
            "production_policy": (
                "Research only. No production envelope widening, multiplier change, "
                "or consumer change is allowed from catalog generation alone."
            ),
        },
        "catalog_diagnostics": {
            "challenge_count": len(challenges),
            "target_count": len(target_keys),
            "composition_counts": dict(sorted(composition_counts.items())),
            "ratio_counts": dict(sorted(ratio_counts.items())),
            "target_position_counts": dict(sorted(position_counts.items())),
            "target_tier_counts": dict(sorted(tier_counts.items())),
            "target_counts_by_composition": {
                label: len(comp_targets[label]) for label in sorted(comp_targets)
            },
            "cell_counts_by_composition_ratio": {
                label: dict(sorted(counter.items()))
                for label, counter in sorted(by_composition_ratio.items())
            },
            "skipped_cell_count": len(skipped),
            "skipped_cells": skipped,
        },
        "targets": sorted(selected_targets.values(), key=lambda x: (x["pos"], x["name"])),
        "challenges": sorted(challenges, key=lambda c: c["id"]),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Package Adjustment V5 — Two-Player Composition Study",
        "",
        "**Status: RESEARCH ONLY — production V1.5 is unchanged.**",
        "",
        "## Question",
        "",
        "How far can a two-player package move away from the frozen V3 ~51/49 shape "
        "before human consolidation preference materially changes?",
        "",
        "## Composition bands",
        "",
    ]
    for split in COMPOSITIONS:
        label = f"{int(round(split[0]*100))}/{int(round(split[1]*100))}"
        ratios = ", ".join(f"{r:.2f}x" for r in feasible_ratios(split))
        lines.append(f"- **{label}** — ratios: {ratios}")

    lines += [
        "",
        "## Design protections",
        "",
        "- Two-player packages only.",
        "- Same frozen V3 target set requested for comparability.",
        "- Every package player remains below the target FV.",
        "- Actual package composition must be within 2.5 percentage points of its intended band.",
        "- Voter never sees FV values.",
        "- Left/right display side is randomized by the browser voting layer.",
        "- V3 and V4 evidence remain frozen and untouched.",
        "- No live formula, Fundamental Value, Market Value, Team Utility, draft-pick value, or trade verdict consumer changes.",
        "",
        "## Generated catalog",
        "",
        f"- Challenges: `{len(challenges)}`",
        f"- Distinct targets: `{len(target_keys)}`",
        f"- Skipped infeasible/unconstructible cells: `{len(skipped)}`",
        "",
        "### Challenges by composition",
        "",
    ]
    for label, count in sorted(composition_counts.items()):
        lines.append(
            f"- {label}: `{count}` challenges across `{len(comp_targets[label])}` targets"
        )

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    print("V5 challenges:", len(challenges))
    print("V5 targets:", len(target_keys))
    print("Composition counts:", dict(sorted(composition_counts.items())))
    print("Skipped cells:", len(skipped))


if __name__ == "__main__":
    main()


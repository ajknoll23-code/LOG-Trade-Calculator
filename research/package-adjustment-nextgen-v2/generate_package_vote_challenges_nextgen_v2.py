#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = ROOT / "research" / "package-adjustment-nextgen-v2"
SPEC = RESEARCH_DIR / "package_adjustment_nextgen_v2_research_spec.md"
VALUES = ROOT / "scripts" / "artifacts" / "generated" / "value_uncertainty.json"
ROSTERS = ROOT / "data" / "league_rosters.json"
PROMOTION = ROOT / "research" / "package-adjustment-v5" / "controlled_live_v1_6_promotion.json"
OUT = RESEARCH_DIR / "package_vote_challenges_nextgen_v2.json"
OUT_MD = RESEARCH_DIR / "challenge_catalog_design.md"

HISTORICAL_FROZEN = (
    ROOT / "research" / "package-adjustment-v3" / "package_vote_challenges_v3.json",
    ROOT / "research" / "package-adjustment-v4" / "package_vote_challenges_v4.json",
    ROOT / "research" / "package-adjustment-v5" / "package_vote_challenges_v5.json",
)

EXPECTED_PRODUCTION_REVISION = "v1.6-v5-size2-composition-overlay"
EXPECTED_FORMULA_SHA256 = "9a1a52f3393a701fe8463fcf2179d1342debb925da1109ce73276b8b2b8cbbc7"

TRANSPORT_MARKERS = (
    "__pkgnv2__|",
    "__pkgnv2_meta__|",
    "__pkgnv2_schema__|1",
)
TARGET_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
POS_MAP = {
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K",
    "DL": "DL", "DE": "DL", "DT": "DL",
    "LB": "LB", "OLB": "LB", "ILB": "LB",
    "DB": "DB", "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB",
}

CORE_PROFILES = (
    ("80_20", (0.80, 0.20)),
    ("70_30", (0.70, 0.30)),
    ("60_40", (0.60, 0.40)),
    ("55_45", (0.55, 0.45)),
    ("50_50_control", (0.50, 0.50)),
)
FLAT_PROFILE = (0.50, 0.50)
FRAGMENTATION_COMPARISONS = (
    ("80_20_vs_80_10_10", (0.80, 0.20), (0.80, 0.10, 0.10)),
    ("80_20_vs_80_05x4", (0.80, 0.20), (0.80, 0.05, 0.05, 0.05, 0.05)),
)
HOLDOUT_3V3_COMPARISONS = (
    ("60_25_15_vs_34_33_33", (0.60, 0.25, 0.15), (0.34, 0.33, 0.33)),
    ("70_20_10_vs_40_35_25", (0.70, 0.20, 0.10), (0.40, 0.35, 0.25)),
)
SCALE_QUANTILES = (("low", 0.25), ("mid", 0.50), ("high", 0.75))
FIT_SCALE_LABELS = {"low", "mid"}
SCALE_HOLDOUT_LABEL = "high"

MAX_SIDE_TARGET_ERROR = 0.025
MAX_PAIR_TOTAL_GAP = 0.025
MAX_COMPONENT_SHARE_ERROR = 0.025
FEASIBLE_8020_SHARE_ERROR = 0.025
NEAREST_POOL = 48
BEAM_WIDTH = 180
SIDE_CANDIDATE_LIMIT = 24
CORE_TARGET_REPS = 6
CORE_MIN_REPS = 4
FRAG_TARGET_REPS = 5
FRAG_MIN_REPS_PER_SUPPORTED_CELL = 2
FRAG_MIN_SUPPORTED_SCALES = 2
HOLDOUT_TARGET_REPS = 4
HOLDOUT_MIN_REPS = 2
MAX_GOAL_CANDIDATES = 90
FRAG_MAX_GOAL_CANDIDATES = 220
MIN_ROSTERED_PLAYERS = 350
APPEARANCE_PENALTY = 0.00035


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def normalize_name(value) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_pos(value):
    return POS_MAP.get(str(value or "").upper())


def nearest_rank(values: Iterable[float], q: float) -> float:
    vals = sorted(float(v) for v in values)
    if not vals:
        raise RuntimeError("nearest_rank requires non-empty values")
    if not 0 < q <= 1:
        raise ValueError("q must be in (0, 1]")
    idx = max(0, min(len(vals) - 1, math.ceil(q * len(vals)) - 1))
    return vals[idx]


def profile_label(shares) -> str:
    return "_".join(str(int(round(100 * float(s)))) for s in shares)


def canonical_actual_shares(assets):
    values = sorted((float(a["fv"]) for a in assets), reverse=True)
    total = sum(values)
    return [v / total for v in values]


def git_output(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def git_metadata(root: Path, require_clean_generator: bool = True):
    head = git_output(root, "rev-parse", "HEAD")
    committed_at = git_output(root, "show", "-s", "--format=%cI", "HEAD")
    rel = Path(__file__).resolve().relative_to(root).as_posix()
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--error-unmatch", rel],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if require_clean_generator and tracked.returncode != 0:
        raise RuntimeError(
            "generator must be committed before catalog generation; run --selftest before commit"
        )
    if require_clean_generator:
        dirty = git_output(root, "status", "--porcelain=v1", "--", rel)
        if dirty:
            raise RuntimeError(
                "generator has uncommitted changes; commit it before catalog generation"
            )
    return head, committed_at


def assert_required_files(root: Path):
    required = [SPEC, VALUES, ROSTERS, PROMOTION, *HISTORICAL_FROZEN]
    missing = [p.relative_to(root).as_posix() for p in required if not p.is_file()]
    if missing:
        raise RuntimeError("missing required repository files: " + ", ".join(missing))


def assert_production_baseline():
    doc = read_json(PROMOTION)
    if doc.get("status") != "controlled_live_v1_6_promotion_validated":
        raise RuntimeError("unexpected controlled-live promotion status")
    if doc.get("production_revision") != EXPECTED_PRODUCTION_REVISION:
        raise RuntimeError(
            f"production revision changed: {doc.get('production_revision')!r}"
        )
    if doc.get("exact_live_formula_sha256") != EXPECTED_FORMULA_SHA256:
        raise RuntimeError("controlled-live Package Adjustment formula SHA changed")
    if doc.get("automatic_future_production_change_allowed") is not False:
        raise RuntimeError("promotion artifact unexpectedly allows automatic future changes")
    return doc


def assert_historical_frozen():
    snapshots = {}
    for path in HISTORICAL_FROZEN:
        doc = read_json(path)
        if doc.get("frozen") is not True:
            raise RuntimeError(f"historical catalog is not frozen: {path}")
        snapshots[path] = sha256(path)
    return snapshots


def assert_transport_namespace_unused(root: Path):
    candidates = [
        root / "index.html",
        root / "scripts" / "market" / "ktc_pipeline.py",
    ]
    workflow_dir = root / ".github" / "workflows"
    if workflow_dir.is_dir():
        candidates.extend(sorted(workflow_dir.glob("*.yml")))
        candidates.extend(sorted(workflow_dir.glob("*.yaml")))

    collisions = []
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in TRANSPORT_MARKERS:
            if marker in text:
                collisions.append((path.relative_to(root).as_posix(), marker))
    if collisions:
        detail = "; ".join(f"{path}: {marker}" for path, marker in collisions)
        raise RuntimeError(f"NextGen transport namespace is already in active use: {detail}")


def build_player_universe(values_doc, rosters_doc, *, min_rostered_players=None, min_position_count=8):
    by_id = {}
    by_name = {}
    duplicate_names = set()

    for name, row in (values_doc.get("players") or {}).items():
        fv = finite(row.get("center_value"))
        pos = normalize_pos(row.get("pos"))
        if fv is None or fv <= 0 or not pos or pos == "K":
            continue
        record = {
            "value_name": str(name),
            "key": normalize_name(name),
            "fv": float(fv),
            "pos": pos,
            "sleeper_id": str(row.get("sleeper_id") or "").strip() or None,
        }
        if record["sleeper_id"]:
            existing = by_id.get(record["sleeper_id"])
            if existing and existing["key"] != record["key"]:
                raise RuntimeError(f"duplicate sleeper_id in FV data: {record['sleeper_id']}")
            by_id[record["sleeper_id"]] = record

        key = record["key"]
        if key in by_name and by_name[key]["sleeper_id"] != record["sleeper_id"]:
            duplicate_names.add(key)
        else:
            by_name[key] = record

    for key in duplicate_names:
        by_name.pop(key, None)

    rostered = {}
    unresolved = []
    for roster in rosters_doc.get("rosters") or []:
        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for raw in roster.get(slot) or []:
                name = str(raw.get("name") or "").strip()
                key = normalize_name(name)
                pid = str(raw.get("player_id") or "").strip() or None
                row = by_id.get(pid) if pid else None
                method = "sleeper_id" if row else None
                if row is None:
                    row = by_name.get(key)
                    method = "normalized_name" if row else None
                if row is None:
                    unresolved.append({"name": name, "player_id": pid, "slot": slot})
                    continue

                stable_key = row["sleeper_id"] or row["key"]
                candidate = {
                    "key": stable_key,
                    "name": name or row["value_name"],
                    "pos": row["pos"],
                    "fv": float(row["fv"]),
                    "team": raw.get("team"),
                    "age": raw.get("age"),
                    "player_id": pid or row["sleeper_id"],
                    "match_method": method,
                }
                existing = rostered.get(stable_key)
                if existing and abs(existing["fv"] - candidate["fv"]) > 1e-12:
                    raise RuntimeError(f"conflicting FV for rostered player {stable_key}")
                rostered[stable_key] = candidate

    players = sorted(rostered.values(), key=lambda p: (-float(p["fv"]), p["key"]))
    floor = MIN_ROSTERED_PLAYERS if min_rostered_players is None else int(min_rostered_players)
    if len(players) < floor:
        raise RuntimeError(f"too few eligible rostered valued players: {len(players)}")

    pos_counts = Counter(p["pos"] for p in players)
    missing_positions = [p for p in TARGET_POSITIONS if pos_counts[p] < int(min_position_count)]
    if missing_positions:
        raise RuntimeError(f"insufficient position coverage: {missing_positions}")

    return players, unresolved, pos_counts


def enumerate_feasible_8020_pairs(players):
    rows = []
    for i, a in enumerate(players):
        av = float(a["fv"])
        for b in players[i + 1:]:
            bv = float(b["fv"])
            total = av + bv
            if total <= 0:
                continue
            share = max(av, bv) / total
            if abs(share - 0.80) <= FEASIBLE_8020_SHARE_ERROR + 1e-12:
                top, low = (a, b) if av >= bv else (b, a)
                rows.append({
                    "total_fv": total,
                    "top_key": top["key"],
                    "low_key": low["key"],
                    "top_share": share,
                })
    if len(rows) < 30:
        raise RuntimeError(f"too few feasible 80/20 pairs for scale derivation: {len(rows)}")
    rows.sort(key=lambda r: (r["total_fv"], r["top_key"], r["low_key"]))
    return rows


def scale_plan(feasible_pairs):
    totals = [r["total_fv"] for r in feasible_pairs]
    anchors = {label: nearest_rank(totals, q) for label, q in SCALE_QUANTILES}
    if not (anchors["low"] < anchors["mid"] < anchors["high"]):
        raise RuntimeError(f"scale anchors are not strictly increasing: {anchors}")

    plans = {}
    for label, _ in SCALE_QUANTILES:
        anchor = anchors[label]
        ranked = sorted(
            feasible_pairs,
            key=lambda r: (
                abs(float(r["total_fv"]) - anchor),
                float(r["total_fv"]),
                r["top_key"],
                r["low_key"],
            ),
        )
        unique = []
        seen_rounded = set()
        for row in ranked:
            code = round(float(row["total_fv"]), 3)
            if code in seen_rounded:
                continue
            seen_rounded.add(code)
            unique.append(float(row["total_fv"]))
            if len(unique) >= MAX_GOAL_CANDIDATES:
                break
        if len(unique) < 12:
            raise RuntimeError(f"too few unique goal totals for scale {label}: {len(unique)}")
        plans[label] = {"anchor_total_fv": float(anchor), "candidate_goal_totals": unique}
    return plans


def component_value_window(total_goal, intended_share):
    """Outer FV window implied by the frozen total/share tolerances.

    This is intentionally only a feasibility prefilter. Exact side-total,
    component-share, and pair-total tolerances are still enforced by the
    existing joint constructor and validator.
    """
    share = float(intended_share)
    low_share = max(0.0, share - MAX_COMPONENT_SHARE_ERROR)
    high_share = share + MAX_COMPONENT_SHARE_ERROR
    low_total = float(total_goal) * (1.0 - MAX_SIDE_TARGET_ERROR)
    high_total = float(total_goal) * (1.0 + MAX_SIDE_TARGET_ERROR)
    return low_total * low_share, high_total * high_share


def component_window_matching_exists(players, total_goal, shares_a, shares_b):
    """Check whether all intended components can use distinct real players.

    The fragmentation family needs up to seven distinct players in one
    comparison. Core 80/20 scale anchors can be too low for 10% or 5% pieces
    even though an 80/20 pair itself is feasible. This matching check filters
    candidate totals using the actual FV grid before defining the
    fragmentation-specific scale bands.
    """
    components = [float(s) for s in shares_a] + [float(s) for s in shares_b]
    candidate_keys = []
    for share in components:
        lo, hi = component_value_window(total_goal, share)
        desired = float(total_goal) * share
        candidates = [
            (abs(float(player["fv"]) - desired), player["key"])
            for player in players
            if lo - 1e-12 <= float(player["fv"]) <= hi + 1e-12
        ]
        candidates.sort()
        if not candidates:
            return False
        candidate_keys.append([key for _err, key in candidates])

    # Standard augmenting-path bipartite matching. Components are processed
    # from sparsest to densest so impossible low-value windows fail quickly.
    order = sorted(range(len(components)), key=lambda i: (len(candidate_keys[i]), i))
    player_to_component = {}

    def augment(component_index, seen):
        for key in candidate_keys[component_index]:
            if key in seen:
                continue
            seen.add(key)
            previous = player_to_component.get(key)
            if previous is None or augment(previous, seen):
                player_to_component[key] = component_index
                return True
        return False

    for component_index in order:
        if not augment(component_index, set()):
            return False
    return True


def fragmentation_scale_plans(players, feasible_pairs):
    """Derive scale bands from totals feasible for each fragmentation design.

    The core scale plan is intentionally based on feasible 80/20 *two-player*
    packages. Reusing those same quartiles for 80/10/10 or 80/5/5/5/5 can
    create structurally impossible low/mid cells because the required 10%/5%
    assets fall below the actual rostered FV grid. That is a scale-design
    mismatch, not evidence that the fragmentation experiment should be
    dropped or that its 2.5% tolerances should be loosened.

    Each comparison therefore gets its own deterministic low/mid/high scale
    bands, still derived from the same frozen real-player 80/20 totals, after
    filtering for enough distinct real players in every component window.
    Exact construction tolerances remain unchanged downstream.
    """
    output = {}
    diagnostics = {}

    for comparison_label, shares_a, shares_b in FRAGMENTATION_COMPARISONS:
        feasible_totals = []
        seen = set()
        for row in feasible_pairs:
            total = float(row["total_fv"])
            code = round(total, 3)
            if code in seen:
                continue
            seen.add(code)
            if component_window_matching_exists(players, total, shares_a, shares_b):
                feasible_totals.append(total)

        feasible_totals.sort()
        if len(feasible_totals) < 12:
            min_fv = min(float(p["fv"]) for p in players)
            max_fv = max(float(p["fv"]) for p in players)
            raise RuntimeError(
                "fragmentation design has too few component-feasible real-player totals: "
                f"{comparison_label}; feasible_unique_totals={len(feasible_totals)}; "
                f"eligible_fv_range=({min_fv:.3f}, {max_fv:.3f}); "
                "tolerances were not loosened"
            )

        anchors = {
            scale_label: nearest_rank(feasible_totals, q)
            for scale_label, q in SCALE_QUANTILES
        }
        if not (anchors["low"] < anchors["mid"] < anchors["high"]):
            raise RuntimeError(
                f"fragmentation scale anchors are not strictly increasing for "
                f"{comparison_label}: {anchors}"
            )

        plans = {}
        for scale_label, _q in SCALE_QUANTILES:
            anchor = anchors[scale_label]
            ranked = sorted(
                feasible_totals,
                key=lambda total: (abs(float(total) - anchor), float(total)),
            )
            goals = ranked[:FRAG_MAX_GOAL_CANDIDATES]
            if len(goals) < 12:
                raise RuntimeError(
                    f"fragmentation scale {comparison_label}/{scale_label} has too few "
                    f"candidate goals: {len(goals)}"
                )
            plans[scale_label] = {
                "anchor_total_fv": float(anchor),
                "candidate_goal_totals": [float(x) for x in goals],
            }

        output[comparison_label] = plans
        diagnostics[comparison_label] = {
            "component_feasible_unique_total_count": len(feasible_totals),
            "min_component_feasible_total_fv": float(feasible_totals[0]),
            "max_component_feasible_total_fv": float(feasible_totals[-1]),
            "scale_anchors": {k: float(v) for k, v in anchors.items()},
        }

    return output, diagnostics


def nearest_candidate_pool(players, desired, excluded, appearance_counts):
    rows = [p for p in players if p["key"] not in excluded]
    rows.sort(
        key=lambda p: (
            abs(float(p["fv"]) - desired),
            appearance_counts[p["key"]],
            p["key"],
        )
    )
    return rows[:NEAREST_POOL]


def construct_side_candidates(players, total_goal, intended_shares, excluded,
                              appearance_counts, limit=SIDE_CANDIDATE_LIMIT):
    """Return multiple high-quality valid side constructions.

    Phase-1 originally returned only the single best side before attempting to
    build the opposite side. On sparse real-player FV grids that can consume a
    scarce near-target asset and make a jointly feasible comparison appear
    impossible. Returning several candidates lets the trade constructor solve
    the two sides jointly without relaxing any preregistered tolerance.
    """
    shares = tuple(sorted((float(s) for s in intended_shares), reverse=True))
    if not shares or abs(sum(shares) - 1.0) > 1e-9:
        raise ValueError(f"invalid intended shares: {intended_shares}")
    desired_values = [total_goal * s for s in shares]

    # state = (running_score, tuple(keys), tuple(players))
    states = [(0.0, tuple(), tuple())]
    for desired in desired_values:
        expanded = []
        for running, keys, chosen in states:
            local_excluded = set(excluded) | set(keys)
            pool = nearest_candidate_pool(players, desired, local_excluded, appearance_counts)
            for player in pool:
                component_error = abs(float(player["fv"]) - desired) / total_goal
                reuse = appearance_counts[player["key"]]
                score = running + component_error + APPEARANCE_PENALTY * reuse
                expanded.append((score, keys + (player["key"],), chosen + (player,)))
        if not expanded:
            return []
        expanded.sort(key=lambda row: (row[0], row[1]))
        states = expanded[:BEAM_WIDTH]

    valid = []
    seen = set()
    for running, keys, chosen in states:
        assets = sorted(chosen, key=lambda p: (-float(p["fv"]), p["key"]))
        key_tuple = tuple(p["key"] for p in assets)
        if key_tuple in seen:
            continue
        seen.add(key_tuple)

        actual_total = sum(float(p["fv"]) for p in assets)
        total_error = abs(actual_total - total_goal) / total_goal
        actual_shares = canonical_actual_shares(assets)
        share_errors = [abs(a - b) for a, b in zip(actual_shares, shares)]
        max_share_error = max(share_errors)
        if total_error > MAX_SIDE_TARGET_ERROR + 1e-12:
            continue
        if max_share_error > MAX_COMPONENT_SHARE_ERROR + 1e-12:
            continue
        score = (
            total_error,
            max_share_error,
            sum(share_errors),
            running,
            key_tuple,
        )
        valid.append((score, assets))

    valid.sort(key=lambda row: row[0])
    return [assets for _score, assets in valid[:int(limit)]]


def construct_side(players, total_goal, intended_shares, excluded, appearance_counts):
    candidates = construct_side_candidates(
        players, total_goal, intended_shares, excluded, appearance_counts, limit=1
    )
    return candidates[0] if candidates else None


def asset_record(player):
    return {
        "key": player["key"],
        "name": player["name"],
        "pos": player["pos"],
        "team": player.get("team"),
        "age": player.get("age"),
        "player_id": player.get("player_id"),
        "fv": round(float(player["fv"]), 3),
    }


def side_record(assets, intended_shares, total_goal):
    total = sum(float(p["fv"]) for p in assets)
    shares = canonical_actual_shares(assets)
    intended = tuple(sorted((float(s) for s in intended_shares), reverse=True))
    return {
        "assets": [asset_record(p) for p in assets],
        "asset_count": len(assets),
        "raw_fv": round(total, 3),
        "target_total_fv": round(float(total_goal), 3),
        "target_total_error_pct": round(abs(total - total_goal) / total_goal, 8),
        "intended_shares": [round(s, 6) for s in intended],
        "actual_shares": [round(s, 6) for s in shares],
        "max_share_error": round(max(abs(a - b) for a, b in zip(shares, intended)), 8),
    }


def make_challenge(*, challenge_id, family, cell_id, scale_label, scale_anchor,
                   total_goal, shares_a, shares_b, assets_a, assets_b,
                   split, fit_eligible, treatment):
    side_a = side_record(assets_a, shares_a, total_goal)
    side_b = side_record(assets_b, shares_b, total_goal)
    mean_total = (float(side_a["raw_fv"]) + float(side_b["raw_fv"])) / 2.0
    pair_gap = abs(float(side_a["raw_fv"]) - float(side_b["raw_fv"])) / mean_total
    return {
        "id": challenge_id,
        "schema_version": 1,
        "experiment": "package_adjustment_nextgen_v2",
        "family": family,
        "cell_id": cell_id,
        "treatment": treatment,
        "scale_label": scale_label,
        "scale_anchor_total_fv": round(float(scale_anchor), 3),
        "goal_total_fv": round(float(total_goal), 3),
        "split": split,
        "fit_eligible": bool(fit_eligible),
        "values_hidden_from_voter": True,
        "side_a": side_a,
        "side_b": side_b,
        "pair_total_gap_pct": round(pair_gap, 8),
    }


def challenge_signature(challenge):
    a = tuple(sorted(x["key"] for x in challenge["side_a"]["assets"]))
    b = tuple(sorted(x["key"] for x in challenge["side_b"]["assets"]))
    # A challenge and an exact side-swapped copy carry the same information.
    # Canonicalize the two sides so both map to one signature.
    sides = tuple(sorted((a, b)))
    return challenge["family"], challenge["cell_id"], sides


def try_build_challenge(players, appearance_counts, used_signatures, *, family,
                        cell_id, scale_label, scale_anchor, total_goal,
                        shares_a, shares_b, split, fit_eligible, treatment,
                        rep_index):
    """Jointly construct both sides instead of greedily locking Side A first.

    This preserves the same 2.5% total/share tolerances while avoiding a false
    "unconstructible" result when the first greedy side consumes a scarce
    player needed for the opposing profile. It is especially important for
    80/20 vs 80/10/10 fragmentation cells on a sparse real-player FV grid.
    """
    candidates_a = construct_side_candidates(
        players, total_goal, shares_a, set(), appearance_counts
    )
    candidates_b = construct_side_candidates(
        players, total_goal, shares_b, set(), appearance_counts
    )
    if not candidates_a or not candidates_b:
        return None

    ranked_pairs = []
    for assets_a in candidates_a:
        keys_a = {p["key"] for p in assets_a}
        total_a = sum(float(p["fv"]) for p in assets_a)
        shares_actual_a = canonical_actual_shares(assets_a)
        intended_a = tuple(sorted((float(s) for s in shares_a), reverse=True))
        err_a = abs(total_a - total_goal) / total_goal
        share_err_a = max(abs(a - b) for a, b in zip(shares_actual_a, intended_a))

        for assets_b in candidates_b:
            keys_b = {p["key"] for p in assets_b}
            if keys_a & keys_b:
                continue

            total_b = sum(float(p["fv"]) for p in assets_b)
            mean_total = (total_a + total_b) / 2.0
            if mean_total <= 0:
                continue
            pair_gap = abs(total_a - total_b) / mean_total
            if pair_gap > MAX_PAIR_TOTAL_GAP + 1e-12:
                continue

            shares_actual_b = canonical_actual_shares(assets_b)
            intended_b = tuple(sorted((float(s) for s in shares_b), reverse=True))
            err_b = abs(total_b - total_goal) / total_goal
            share_err_b = max(abs(a - b) for a, b in zip(shares_actual_b, intended_b))

            a_keys = tuple(sorted(keys_a))
            b_keys = tuple(sorted(keys_b))
            signature = (family, cell_id, tuple(sorted((a_keys, b_keys))))
            if signature in used_signatures:
                continue

            reuse = sum(appearance_counts[k] for k in keys_a | keys_b)
            rank = (
                pair_gap,
                max(err_a, err_b),
                max(share_err_a, share_err_b),
                err_a + err_b,
                share_err_a + share_err_b,
                APPEARANCE_PENALTY * reuse,
                tuple(sorted((a_keys, b_keys))),
            )
            ranked_pairs.append((rank, assets_a, assets_b, signature))

    if not ranked_pairs:
        return None

    ranked_pairs.sort(key=lambda row: row[0])
    _rank, assets_a, assets_b, _signature = ranked_pairs[0]

    challenge_id = (
        f"pkgnv2_{family}_{scale_label}_{cell_id}_r{rep_index:02d}"
        .replace("/", "_")
    )
    return make_challenge(
        challenge_id=challenge_id,
        family=family,
        cell_id=cell_id,
        scale_label=scale_label,
        scale_anchor=scale_anchor,
        total_goal=total_goal,
        shares_a=shares_a,
        shares_b=shares_b,
        assets_a=assets_a,
        assets_b=assets_b,
        split=split,
        fit_eligible=fit_eligible,
        treatment=treatment,
    )


def add_cell(challenges, skipped, players, appearance_counts, used_signatures,
             scale_info, *, family, cell_id, shares_a, shares_b, target_reps,
             split, fit_eligible, treatment):
    built = 0
    scale_label = scale_info["label"]
    anchor = scale_info["anchor_total_fv"]
    for goal in scale_info["candidate_goal_totals"]:
        if built >= target_reps:
            break
        candidate = try_build_challenge(
            players,
            appearance_counts,
            used_signatures,
            family=family,
            cell_id=cell_id,
            scale_label=scale_label,
            scale_anchor=anchor,
            total_goal=goal,
            shares_a=shares_a,
            shares_b=shares_b,
            split=split,
            fit_eligible=fit_eligible,
            treatment=treatment,
            rep_index=built + 1,
        )
        if candidate is None:
            continue
        signature = challenge_signature(candidate)
        used_signatures.add(signature)
        challenges.append(candidate)
        for side in ("side_a", "side_b"):
            for asset in candidate[side]["assets"]:
                appearance_counts[asset["key"]] += 1
        built += 1

    if built < target_reps:
        skipped.append({
            "family": family,
            "cell_id": cell_id,
            "scale_label": scale_label,
            "requested_reps": target_reps,
            "built_reps": built,
            "reason": "insufficient_real_asset_matches_within_frozen_tolerances",
        })
    return built


def generate_challenges(players, plans, fragmentation_plans):
    challenges = []
    skipped = []
    appearance_counts = Counter()
    used_signatures = set()
    cell_counts = {}

    # Core concentration ladder. High scale is a complete structural scale holdout.
    for scale_label, _ in SCALE_QUANTILES:
        info = {"label": scale_label, **plans[scale_label]}
        split = "structural_scale_holdout" if scale_label == SCALE_HOLDOUT_LABEL else "train"
        fit_eligible = scale_label in FIT_SCALE_LABELS
        for label, shares in CORE_PROFILES:
            cell_id = f"core_{label}"
            count = add_cell(
                challenges, skipped, players, appearance_counts, used_signatures, info,
                family="core_concentration_2v2",
                cell_id=cell_id,
                shares_a=shares,
                shares_b=FLAT_PROFILE,
                target_reps=CORE_TARGET_REPS,
                split=split,
                fit_eligible=fit_eligible,
                treatment=f"{profile_label(shares)}_vs_{profile_label(FLAT_PROFILE)}",
            )
            cell_counts[("core_concentration_2v2", scale_label, cell_id)] = count

    # Fragmentation/filler identifying cells. These use comparison-specific
    # feasible scale bands because 10%/5% pieces can be impossible at the core
    # 80/20 quartile totals even though the core comparison itself is feasible.
    # Scientific construction tolerances remain exactly the same.
    for label, shares_a, shares_b in FRAGMENTATION_COMPARISONS:
        comparison_plans = fragmentation_plans[label]
        for scale_label, _ in SCALE_QUANTILES:
            info = {"label": scale_label, **comparison_plans[scale_label]}
            cell_id = f"frag_{label}"
            count = add_cell(
                challenges, skipped, players, appearance_counts, used_signatures, info,
                family="fragmentation_filler",
                cell_id=cell_id,
                shares_a=shares_a,
                shares_b=shares_b,
                target_reps=FRAG_TARGET_REPS,
                split="train",
                fit_eligible=True,
                treatment=f"{profile_label(shares_a)}_vs_{profile_label(shares_b)}",
            )
            cell_counts[("fragmentation_filler", scale_label, cell_id)] = count

    # Entire 3v3 topology is withheld from fitting.
    for scale_label, _ in SCALE_QUANTILES:
        info = {"label": scale_label, **plans[scale_label]}
        for label, shares_a, shares_b in HOLDOUT_3V3_COMPARISONS:
            cell_id = f"holdout_{label}"
            count = add_cell(
                challenges, skipped, players, appearance_counts, used_signatures, info,
                family="structural_topology_3v3",
                cell_id=cell_id,
                shares_a=shares_a,
                shares_b=shares_b,
                target_reps=HOLDOUT_TARGET_REPS,
                split="structural_topology_holdout",
                fit_eligible=False,
                treatment=f"{profile_label(shares_a)}_vs_{profile_label(shares_b)}",
            )
            cell_counts[("structural_topology_3v3", scale_label, cell_id)] = count

    validate_challenges(challenges, cell_counts)
    return challenges, skipped, appearance_counts, cell_counts


def validate_side(challenge_id, side_name, side):
    assets = side.get("assets") or []
    if len(assets) != int(side.get("asset_count", -1)):
        raise RuntimeError(f"{challenge_id} {side_name}: asset_count mismatch")
    if not assets:
        raise RuntimeError(f"{challenge_id} {side_name}: empty side")
    keys = [a["key"] for a in assets]
    if len(keys) != len(set(keys)):
        raise RuntimeError(f"{challenge_id} {side_name}: duplicate asset")
    if any(a.get("pos") not in TARGET_POSITIONS for a in assets):
        raise RuntimeError(f"{challenge_id} {side_name}: unsupported position")
    if any(finite(a.get("fv")) is None or float(a["fv"]) <= 0 for a in assets):
        raise RuntimeError(f"{challenge_id} {side_name}: non-positive FV")
    total = sum(float(a["fv"]) for a in assets)
    if abs(total - float(side["raw_fv"])) > 0.01:
        raise RuntimeError(f"{challenge_id} {side_name}: raw FV mismatch")
    if float(side["target_total_error_pct"]) > MAX_SIDE_TARGET_ERROR + 1e-8:
        raise RuntimeError(f"{challenge_id} {side_name}: total target error too large")
    if float(side["max_share_error"]) > MAX_COMPONENT_SHARE_ERROR + 1e-8:
        raise RuntimeError(f"{challenge_id} {side_name}: share error too large")


def validate_challenges(challenges, cell_counts):
    ids = [c["id"] for c in challenges]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate NextGen challenge IDs")

    signatures = [challenge_signature(c) for c in challenges]
    if len(signatures) != len(set(signatures)):
        raise RuntimeError("duplicate NextGen challenge signatures")

    for c in challenges:
        if c.get("schema_version") != 1:
            raise RuntimeError(f"{c['id']}: wrong schema version")
        if c.get("experiment") != "package_adjustment_nextgen_v2":
            raise RuntimeError(f"{c['id']}: wrong experiment name")
        if c.get("values_hidden_from_voter") is not True:
            raise RuntimeError(f"{c['id']}: values_hidden_from_voter must be true")
        validate_side(c["id"], "side_a", c["side_a"])
        validate_side(c["id"], "side_b", c["side_b"])
        a_keys = {a["key"] for a in c["side_a"]["assets"]}
        b_keys = {a["key"] for a in c["side_b"]["assets"]}
        if a_keys & b_keys:
            raise RuntimeError(f"{c['id']}: same asset appears on both sides")
        if float(c["pair_total_gap_pct"]) > MAX_PAIR_TOTAL_GAP + 1e-8:
            raise RuntimeError(f"{c['id']}: side-to-side total gap too large")
        if c["split"] == "train" and c.get("fit_eligible") is not True:
            raise RuntimeError(f"{c['id']}: training row is not fit-eligible")
        if c["split"] != "train" and c.get("fit_eligible") is not False:
            raise RuntimeError(f"{c['id']}: holdout leakage via fit_eligible")

    # Core coverage is mandatory in every scale/profile cell.
    for scale_label, _ in SCALE_QUANTILES:
        for label, _shares in CORE_PROFILES:
            key = ("core_concentration_2v2", scale_label, f"core_{label}")
            if cell_counts.get(key, 0) < CORE_MIN_REPS:
                raise RuntimeError(f"core cell below minimum coverage: {key} -> {cell_counts.get(key, 0)}")

    # Each fragmentation comparison must be supported in at least two scales.
    for label, _a, _b in FRAGMENTATION_COMPARISONS:
        supported = 0
        scale_coverage = {}
        for scale_label, _ in SCALE_QUANTILES:
            key = ("fragmentation_filler", scale_label, f"frag_{label}")
            count = int(cell_counts.get(key, 0))
            scale_coverage[scale_label] = count
            if count >= FRAG_MIN_REPS_PER_SUPPORTED_CELL:
                supported += 1
        if supported < FRAG_MIN_SUPPORTED_SCALES:
            raise RuntimeError(
                "fragmentation comparison lacks scale coverage: "
                f"{label}; counts={scale_coverage}; "
                f"need >= {FRAG_MIN_REPS_PER_SUPPORTED_CELL} reps in "
                f">= {FRAG_MIN_SUPPORTED_SCALES} scales"
            )

    # Structural 3v3 holdout must exist in every scale/profile cell.
    for scale_label, _ in SCALE_QUANTILES:
        for label, _a, _b in HOLDOUT_3V3_COMPARISONS:
            key = ("structural_topology_3v3", scale_label, f"holdout_{label}")
            if cell_counts.get(key, 0) < HOLDOUT_MIN_REPS:
                raise RuntimeError(f"3v3 holdout cell below minimum coverage: {key}")

    # Entire high core scale must be withheld; all 3v3 rows must be withheld.
    for c in challenges:
        if c["family"] == "core_concentration_2v2" and c["scale_label"] == SCALE_HOLDOUT_LABEL:
            if c["split"] != "structural_scale_holdout" or c["fit_eligible"] is not False:
                raise RuntimeError(f"{c['id']}: high-scale holdout leakage")
        if c["family"] == "structural_topology_3v3":
            if c["split"] != "structural_topology_holdout" or c["fit_eligible"] is not False:
                raise RuntimeError(f"{c['id']}: 3v3 holdout leakage")


def validate_fv_lookup(challenges, players):
    lookup = {p["key"]: float(p["fv"]) for p in players}
    for c in challenges:
        for side_name in ("side_a", "side_b"):
            for asset in c[side_name]["assets"]:
                expected = lookup.get(asset["key"])
                if expected is None:
                    raise RuntimeError(f"{c['id']}: asset absent from frozen FV universe: {asset['key']}")
                if abs(expected - float(asset["fv"])) > 0.001:
                    raise RuntimeError(f"{c['id']}: FV lookup mismatch for {asset['key']}")


def counter_to_dict(counter):
    return {str(k): int(v) for k, v in sorted(counter.items(), key=lambda kv: str(kv[0]))}


def build_catalog_document(root: Path, players, unresolved, pos_counts, v_ref,
                           feasible_pairs, plans, fragmentation_plans, fragmentation_diagnostics,
                           challenges, skipped, appearance_counts, cell_counts, head,
                           committed_at, frozen_before):
    values_doc = read_json(VALUES)
    family_counts = Counter(c["family"] for c in challenges)
    split_counts = Counter(c["split"] for c in challenges)
    scale_counts = Counter(c["scale_label"] for c in challenges)

    cells = []
    for (family, scale, cell_id), count in sorted(cell_counts.items()):
        cells.append({
            "family": family,
            "scale_label": scale,
            "cell_id": cell_id,
            "challenge_count": int(count),
        })

    return {
        "schema_version": 1,
        "status": "generated_research_catalog_unreleased",
        "research_only": True,
        "frozen": False,
        "production_formula_enabled": False,
        "automatic_production_change_allowed": False,
        "production_revision_at_generation": EXPECTED_PRODUCTION_REVISION,
        "exact_live_formula_sha256_at_generation": EXPECTED_FORMULA_SHA256,
        "generated_at_utc": committed_at,
        "generator_commit_sha": head,
        "generator_path": Path(__file__).resolve().relative_to(root).as_posix(),
        "generator_sha256": sha256(Path(__file__).resolve()),
        "research_spec": {
            "path": SPEC.relative_to(root).as_posix(),
            "sha256": sha256(SPEC),
        },
        "inputs": {
            "player_fv": {
                "path": VALUES.relative_to(root).as_posix(),
                "sha256": sha256(VALUES),
                "source_generated_at_utc": values_doc.get("generated_at_utc"),
            },
            "league_rosters": {
                "path": ROSTERS.relative_to(root).as_posix(),
                "sha256": sha256(ROSTERS),
            },
            "controlled_live_promotion": {
                "path": PROMOTION.relative_to(root).as_posix(),
                "sha256": sha256(PROMOTION),
            },
            "historical_frozen_catalogs": {
                p.relative_to(root).as_posix(): digest for p, digest in frozen_before.items()
            },
        },
        "transport_reserved_not_activated": {
            "vote_prefix": TRANSPORT_MARKERS[0],
            "meta_prefix": TRANSPORT_MARKERS[1],
            "schema_marker": TRANSPORT_MARKERS[2],
        },
        "v_ref": {
            "definition": "nearest-rank 95th percentile of positive FV among eligible rostered non-kicker players",
            "quantile": 0.95,
            "value": round(float(v_ref), 6),
            "eligible_player_count": len(players),
        },
        "pick_cells": {
            "active": False,
            "reason": "production draft-pick FV source not verified in Phase 1",
        },
        "design": {
            "eligible_positions": list(TARGET_POSITIONS),
            "kicker_excluded": True,
            "values_hidden_from_voter": True,
            "display_side_randomization_required_at_activation": True,
            "max_side_target_error": MAX_SIDE_TARGET_ERROR,
            "max_pair_total_gap": MAX_PAIR_TOTAL_GAP,
            "max_component_share_error": MAX_COMPONENT_SHARE_ERROR,
            "scale_quantiles": {label: q for label, q in SCALE_QUANTILES},
            "scale_anchors": {label: round(plans[label]["anchor_total_fv"], 3) for label, _ in SCALE_QUANTILES},
            "fragmentation_scale_basis": "comparison-specific feasible real-player totals under frozen component windows",
            "fragmentation_scale_anchors": {
                comparison: {
                    scale: round(info["anchor_total_fv"], 3)
                    for scale, info in comparison_plans.items()
                }
                for comparison, comparison_plans in fragmentation_plans.items()
            },
            "core_profiles": {label: list(shares) for label, shares in CORE_PROFILES},
            "fragmentation_comparisons": [
                {"label": label, "side_a": list(a), "side_b": list(b)}
                for label, a, b in FRAGMENTATION_COMPARISONS
            ],
            "structural_holdout_comparisons": [
                {"label": label, "side_a": list(a), "side_b": list(b)}
                for label, a, b in HOLDOUT_3V3_COMPARISONS
            ],
            "high_scale_reserved_from_fit": True,
            "all_3v3_reserved_from_fit": True,
            "prospective_time_holdout_required_later": True,
        },
        "catalog_diagnostics": {
            "challenge_count": len(challenges),
            "family_counts": counter_to_dict(family_counts),
            "split_counts": counter_to_dict(split_counts),
            "scale_counts": counter_to_dict(scale_counts),
            "position_counts_in_universe": counter_to_dict(pos_counts),
            "unresolved_roster_entries": len(unresolved),
            "feasible_80_20_pair_count": len(feasible_pairs),
            "fragmentation_scale_diagnostics": fragmentation_diagnostics,
            "cell_counts": cells,
            "skipped_or_underfilled_cells": skipped,
            "max_asset_appearance_count": max(appearance_counts.values()) if appearance_counts else 0,
        },
        "challenges": challenges,
    }


def design_markdown(catalog):
    d = catalog["catalog_diagnostics"]
    vref = catalog["v_ref"]
    lines = [
        "# Package Adjustment NextGen V2 — Generated Challenge Catalog Design",
        "",
        "**Status: GENERATED / UNRELEASED — RESEARCH ONLY. Production V1.6 is unchanged.**",
        "",
        "## Frozen inputs",
        "",
        f"- Generator commit: `{catalog['generator_commit_sha']}`",
        f"- Generator SHA-256: `{catalog['generator_sha256']}`",
        f"- Research spec SHA-256: `{catalog['research_spec']['sha256']}`",
        f"- Player FV SHA-256: `{catalog['inputs']['player_fv']['sha256']}`",
        f"- League rosters SHA-256: `{catalog['inputs']['league_rosters']['sha256']}`",
        f"- Controlled-live formula SHA-256: `{catalog['exact_live_formula_sha256_at_generation']}`",
        "",
        "## Normalization",
        "",
        f"- Eligible rostered players: `{vref['eligible_player_count']}`",
        f"- V_REF (nearest-rank 95th percentile): `{vref['value']}`",
        "",
        "## Catalog",
        "",
        f"- Challenges: `{d['challenge_count']}`",
        f"- Feasible real-player 80/20 pairs used for scale derivation: `{d['feasible_80_20_pair_count']}`",
        f"- Pick cells active: `{catalog['pick_cells']['active']}`",
        "- Core high-value scale is reserved from fitting.",
        "- All 3v3 structural-topology challenges are reserved from fitting.",
        "- FV values must remain hidden from voters when activated.",
        "- Left/right display must be randomized by the future browser activation layer.",
        "",
        "### Challenges by family",
        "",
    ]
    for family, count in d["family_counts"].items():
        lines.append(f"- {family}: `{count}`")
    lines.extend(["", "### Challenges by split", ""])
    for split, count in d["split_counts"].items():
        lines.append(f"- {split}: `{count}`")
    lines.extend([
        "",
        "## Isolation",
        "",
        "This generator creates only NextGen research catalog/design outputs. It does not modify production FV, Market Value, Team Utility, draft-pick values, the controlled-live Package Adjustment formula, Trade Verdict consumers, historical V3/V4/V5 catalogs, or workflow files.",
        "",
        "A separate reviewed step is required before browser voting activation.",
        "",
    ])
    return "\n".join(lines)


def write_if_safe(path: Path, content: str, force: bool):
    if path.exists() and not force:
        old = path.read_text(encoding="utf-8")
        if old == content:
            return "unchanged"
        raise RuntimeError(
            f"refusing to overwrite existing {path.relative_to(ROOT)}; "
            "review existing catalog or rerun with --force only before any release/freeze"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "written"


def snapshot_protected_files():
    paths = [SPEC, VALUES, ROSTERS, PROMOTION, *HISTORICAL_FROZEN]
    workflow_dir = ROOT / ".github" / "workflows"
    if workflow_dir.is_dir():
        paths.extend(sorted(workflow_dir.glob("*.yml")))
        paths.extend(sorted(workflow_dir.glob("*.yaml")))
    paths.extend([
        ROOT / "index.html",
        ROOT / "scripts" / "market" / "ktc_pipeline.py",
    ])
    return {p: sha256(p) for p in paths if p.is_file()}


def assert_snapshot_unchanged(before):
    changed = []
    for path, digest in before.items():
        if not path.is_file() or sha256(path) != digest:
            changed.append(path.relative_to(ROOT).as_posix())
    if changed:
        raise RuntimeError("protected files changed during generation: " + ", ".join(changed))


def run_generation(force=False, dry_run=False):
    assert_required_files(ROOT)
    assert_production_baseline()
    frozen_before = assert_historical_frozen()
    assert_transport_namespace_unused(ROOT)
    protected_before = snapshot_protected_files()
    head, committed_at = git_metadata(ROOT, require_clean_generator=True)

    values_doc = read_json(VALUES)
    rosters_doc = read_json(ROSTERS)
    players, unresolved, pos_counts = build_player_universe(values_doc, rosters_doc)
    v_ref = nearest_rank([p["fv"] for p in players], 0.95)
    feasible_pairs = enumerate_feasible_8020_pairs(players)
    plans = scale_plan(feasible_pairs)
    fragmentation_plans, fragmentation_diagnostics = fragmentation_scale_plans(
        players, feasible_pairs
    )
    challenges, skipped, appearance_counts, cell_counts = generate_challenges(
        players, plans, fragmentation_plans
    )
    validate_fv_lookup(challenges, players)

    catalog = build_catalog_document(
        ROOT, players, unresolved, pos_counts, v_ref, feasible_pairs, plans,
        fragmentation_plans, fragmentation_diagnostics, challenges, skipped,
        appearance_counts, cell_counts, head, committed_at, frozen_before,
    )
    json_text = json.dumps(catalog, indent=2, sort_keys=True) + "\n"
    md_text = design_markdown(catalog)

    if dry_run:
        assert_snapshot_unchanged(protected_before)
        print(json.dumps({
            "status": "dry_run_passed",
            "challenge_count": len(challenges),
            "v_ref": v_ref,
            "scale_anchors": {k: round(v["anchor_total_fv"], 3) for k, v in plans.items()},
            "fragmentation_scale_anchors": {
                comparison: {
                    scale: round(info["anchor_total_fv"], 3)
                    for scale, info in comparison_plans.items()
                }
                for comparison, comparison_plans in fragmentation_plans.items()
            },
            "fragmentation_scale_diagnostics": fragmentation_diagnostics,
            "family_counts": counter_to_dict(Counter(c["family"] for c in challenges)),
            "split_counts": counter_to_dict(Counter(c["split"] for c in challenges)),
            "skipped_or_underfilled_cells": len(skipped),
        }, indent=2, sort_keys=True))
        return

    out_status = write_if_safe(OUT, json_text, force)
    md_status = write_if_safe(OUT_MD, md_text, force)
    assert_snapshot_unchanged(protected_before)

    # Re-read and validate the exact bytes handed to later stages.
    loaded = read_json(OUT)
    if loaded != catalog:
        raise RuntimeError("written catalog does not round-trip exactly")
    validate_challenges(loaded["challenges"], cell_counts)
    validate_fv_lookup(loaded["challenges"], players)

    print(f"NextGen V2 catalog {out_status}: {OUT.relative_to(ROOT)}")
    print(f"NextGen V2 design {md_status}: {OUT_MD.relative_to(ROOT)}")
    print(f"Challenges: {len(challenges)}")
    print(f"V_REF: {v_ref:.3f}")
    print("Production V1.6 unchanged; catalog remains unreleased research.")


def synthetic_players(n=490):
    positions = TARGET_POSITIONS
    # Dense deterministic value ladder from ~150 to ~12,000. A nonlinear spacing
    # provides many low-value pieces while retaining elite coverage.
    vals = []
    for i in range(n):
        t = i / (n - 1)
        value = 150.0 + (12000.0 - 150.0) * (t ** 1.65)
        vals.append(value)
    vals.sort(reverse=True)
    players = []
    for i, value in enumerate(vals):
        players.append({
            "key": f"p{i:04d}",
            "name": f"Player {i:04d}",
            "pos": positions[i % len(positions)],
            "fv": round(value, 3),
            "team": f"T{i % 32:02d}",
            "age": 21 + (i % 14),
            "player_id": str(100000 + i),
            "match_method": "sleeper_id",
        })
    return players


def selftest():
    assert normalize_name("A.J. Brown") == "aj brown"
    assert normalize_name("D'Andre Swift") == "dandre swift"
    assert normalize_pos("DE") == "DL"
    assert normalize_pos("CB") == "DB"
    assert nearest_rank([1, 2, 3, 4], 0.50) == 2
    assert nearest_rank([1, 2, 3, 4], 0.95) == 4
    assert profile_label((0.80, 0.10, 0.10)) == "80_10_10"

    # Exercise the exact live input shapes: value_uncertainty.json uses a
    # players mapping with center_value/pos/sleeper_id, while league_rosters
    # stores player_id/name under roster slot arrays. ID match is preferred;
    # normalized-name fallback remains available for rows without an ID.
    mini_values = {
        "players": {
            "a.j. test": {"center_value": 5000, "pos": "WR", "sleeper_id": "101"},
            "fallback runner": {"center_value": 2500, "pos": "RB", "sleeper_id": None},
            "test kicker": {"center_value": 4000, "pos": "K", "sleeper_id": "999"},
        }
    }
    mini_rosters = {
        "rosters": [{
            "starters": [
                {"name": "A.J. Test", "player_id": "101", "team": "AAA", "age": 24},
                {"name": "Fallback Runner", "player_id": None, "team": "BBB", "age": 25},
                {"name": "Test Kicker", "player_id": "999", "team": "CCC", "age": 30},
            ],
            "bench": [], "taxi": [], "reserve_ir": [],
        }]
    }
    mini_players, mini_unresolved, _ = build_player_universe(
        mini_values, mini_rosters, min_rostered_players=1, min_position_count=0
    )
    assert len(mini_players) == 2
    assert len(mini_unresolved) == 1 and mini_unresolved[0]["name"] == "Test Kicker"
    assert {p["match_method"] for p in mini_players} == {"sleeper_id", "normalized_name"}
    assert all(p["pos"] != "K" for p in mini_players)

    # Sparse-grid regression: jointly choose disjoint sides instead of greedily
    # consuming the only useful near-80% asset on the first side.
    sparse = [
        {"key":"t1","name":"Top 1","pos":"WR","fv":8000.0,"team":"A","age":24,"player_id":"t1","match_method":"sleeper_id"},
        {"key":"t2","name":"Top 2","pos":"WR","fv":7920.0,"team":"B","age":24,"player_id":"t2","match_method":"sleeper_id"},
        {"key":"m1","name":"Mid 1","pos":"RB","fv":2010.0,"team":"C","age":25,"player_id":"m1","match_method":"sleeper_id"},
        {"key":"m2","name":"Mid 2","pos":"RB","fv":1960.0,"team":"D","age":25,"player_id":"m2","match_method":"sleeper_id"},
        {"key":"s1","name":"Small 1","pos":"TE","fv":1020.0,"team":"E","age":25,"player_id":"s1","match_method":"sleeper_id"},
        {"key":"s2","name":"Small 2","pos":"LB","fv":990.0,"team":"F","age":25,"player_id":"s2","match_method":"sleeper_id"},
        {"key":"s3","name":"Small 3","pos":"DB","fv":970.0,"team":"G","age":25,"player_id":"s3","match_method":"sleeper_id"},
    ]
    sparse_counts = Counter()
    sparse_challenge = try_build_challenge(
        sparse, sparse_counts, set(),
        family="fragmentation_filler",
        cell_id="frag_sparse_regression",
        scale_label="mid",
        scale_anchor=10000.0,
        total_goal=10000.0,
        shares_a=(0.80, 0.20),
        shares_b=(0.80, 0.10, 0.10),
        split="train",
        fit_eligible=True,
        treatment="80_20_vs_80_10_10",
        rep_index=1,
    )
    assert sparse_challenge is not None
    assert sparse_challenge["pair_total_gap_pct"] <= MAX_PAIR_TOTAL_GAP
    assert sparse_challenge["side_a"]["max_share_error"] <= MAX_COMPONENT_SHARE_ERROR
    assert sparse_challenge["side_b"]["max_share_error"] <= MAX_COMPONENT_SHARE_ERROR
    assert not (
        {a["key"] for a in sparse_challenge["side_a"]["assets"]}
        & {a["key"] for a in sparse_challenge["side_b"]["assets"]}
    )

    players = synthetic_players()
    v_ref = nearest_rank([p["fv"] for p in players], 0.95)
    assert v_ref > 0
    pairs = enumerate_feasible_8020_pairs(players)
    plans = scale_plan(pairs)
    frag_plans, frag_diagnostics = fragmentation_scale_plans(players, pairs)
    challenges, skipped, appearances, cells = generate_challenges(players, plans, frag_plans)
    validate_challenges(challenges, cells)
    validate_fv_lookup(challenges, players)

    assert any(c["family"] == "core_concentration_2v2" for c in challenges)
    assert any(c["family"] == "fragmentation_filler" for c in challenges)
    assert any(c["family"] == "structural_topology_3v3" for c in challenges)
    assert all(
        c["fit_eligible"] is False
        for c in challenges
        if c["family"] == "structural_topology_3v3"
    )
    assert all(
        c["fit_eligible"] is False
        for c in challenges
        if c["family"] == "core_concentration_2v2" and c["scale_label"] == "high"
    )
    assert not any(
        c["split"] != "train" and c["fit_eligible"]
        for c in challenges
    )
    assert max(appearances.values()) > 0
    assert set(frag_plans) == {label for label, _a, _b in FRAGMENTATION_COMPARISONS}
    for comparison, comparison_plans in frag_plans.items():
        anchors = [comparison_plans[label]["anchor_total_fv"] for label, _q in SCALE_QUANTILES]
        assert anchors[0] < anchors[1] < anchors[2], comparison
        assert frag_diagnostics[comparison]["component_feasible_unique_total_count"] >= 12

    # Regression for the live-data failure mode: a rostered-value floor can
    # make global core low/mid anchors invalid for 10%/5% filler pieces. The
    # fragmentation planner must derive its own feasible anchors instead of
    # weakening the 2.5% construction tolerances.
    floored_players = [p for p in synthetic_players(560) if float(p["fv"]) >= 700.0]
    floored_pairs = enumerate_feasible_8020_pairs(floored_players)
    floored_core = scale_plan(floored_pairs)
    floored_frag, floored_diag = fragmentation_scale_plans(floored_players, floored_pairs)
    assert floored_frag["80_20_vs_80_10_10"]["low"]["anchor_total_fv"] >= floored_core["low"]["anchor_total_fv"]
    assert floored_diag["80_20_vs_80_05x4"]["component_feasible_unique_total_count"] >= 12

    # Differential identity from the preregistered model definition.
    raw_a, raw_b = 8041.0, 7411.0
    eq_a, eq_b = 9100.0, 7700.0
    package_diff = (eq_a - eq_b) - (raw_a - raw_b)
    adj_a, adj_b = max(package_diff, 0.0), max(-package_diff, 0.0)
    assert abs(((raw_a + adj_a) - (raw_b + adj_b)) - (eq_a - eq_b)) < 1e-12

    # Homogeneous power example: concentrated package must have the higher
    # equivalent despite both equivalent values lying below the raw 10,000 sum.
    p = 1.2
    e_conc = (9000.0 ** p + 1000.0 ** p) ** (1.0 / p)
    e_flat = (5000.0 ** p + 5000.0 ** p) ** (1.0 / p)
    assert e_conc > e_flat
    assert e_conc < 10000.0 and e_flat < 10000.0

    print("Package Adjustment NextGen V2 generator self-test passed.")
    print(f"Synthetic challenges: {len(challenges)}")
    print(f"Synthetic feasible 80/20 pairs: {len(pairs)}")
    print(f"Synthetic V_REF: {v_ref:.3f}")
    print(f"Synthetic skipped/underfilled cells: {len(skipped)}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate the Package Adjustment NextGen V2 research challenge catalog."
    )
    parser.add_argument("--selftest", action="store_true", help="run deterministic synthetic tests only")
    parser.add_argument("--dry-run", action="store_true", help="build and validate against repo inputs without writing outputs")
    parser.add_argument("--force", action="store_true", help="overwrite unreleased outputs; never use after freeze/release")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.selftest:
        selftest()
        return
    run_generation(force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

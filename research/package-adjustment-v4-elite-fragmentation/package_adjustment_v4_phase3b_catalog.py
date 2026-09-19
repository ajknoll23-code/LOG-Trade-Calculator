#!/usr/bin/env python3
"""Package Adjustment V4 Phase 3B — frozen unreleased fresh-confirmation catalog.

Outcome-blind. Generates exactly 240 trade challenges:
6 topologies × 2 asset mixes × 2 strata × 10 challenges.

Strata:
- candidate_vs_raw_disagreement
- balanced_broad

No human vote outcomes are read. No voting is activated.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "research" / "package-adjustment-v4-elite-fragmentation"
V3 = ROOT / "research" / "package-adjustment-v3-ktc-style"

INDEX = ROOT / "index.html"
ROSTERS = ROOT / "data" / "league_rosters.json"
TRADE_HISTORY = ROOT / "data" / "trade_history.json"

PREREG = D / "phase1_structural_preregistration.json"
FAMILY = D / "frozen_candidate.json"
PHASE2_MANIFEST = D / "phase2_manifest.json"
FEASIBILITY = D / "phase3a_signal_feasibility.json"
FEASIBILITY_MANIFEST = D / "phase3a_signal_feasibility_manifest.json"

V3_PICK_UTILITY = V3 / "package_adjustment_v3_phase2.py"
V3_PHASE1 = V3 / "package_adjustment_v3_phase1.py"

OUT = D / "phase3b_confirmation_catalog.json"
OUT_MD = D / "phase3b_confirmation_catalog.md"
OUT_MANIFEST = D / "phase3b_confirmation_catalog_manifest.json"

VALIDATION_DIR = ROOT / "scripts" / "validation"
if str(VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATION_DIR))
import snapshot_values  # noqa: E402

RNG_SEED = 202609195
MAX_ATTEMPTS_PER_GROUP = 250_000
POOL_TARGET_TARGETED = 250
POOL_TARGET_BROAD = 800
CHALLENGES_PER_CELL = 10
RAW_RATIO_MIN = 0.80
RAW_RATIO_MAX = 1.25
MIN_SIGN_MARGIN = 0.005
EPS = 1e-12

TOPOLOGIES = {
    "1v2": (1, 2),
    "1v3": (1, 3),
    "2v2": (2, 2),
    "2v3": (2, 3),
    "3v3": (3, 3),
    "3v4": (3, 4),
}
ASSET_MIXES = ("players_only", "includes_picks")
STRATA = ("candidate_vs_raw_disagreement", "balanced_broad")

CORRECT_KTC_EXAMPLES = [
    (frozenset(["jahmyr gibbs"]), frozenset(["devon achane", "tee higgins"])),
    (frozenset(["ceedee lamb", "sam laporta"]), frozenset(["rome odunze", "saquon barkley"])),
    (frozenset(["george pickens", "marshawn lloyd"]), frozenset(["isaiah likely", "ryan flournoy", "rico dowdle"])),
    (frozenset(["josh allen"]), frozenset(["caleb williams", "saquon barkley"])),
    (frozenset(["george pickens", "kaelon black"]), frozenset(["jayden reed", "parker washington", "jonathon brooks"])),
]


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def normalize_name(value) -> str:
    return snapshot_values.normalize_lookup_name(value)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ordinal(round_num: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(round_num, f"{round_num}th")


def build_asset_universe():
    cfg = snapshot_values.load_from_html(INDEX)
    values = snapshot_values.compute_all_values(cfg)
    rosters = json.loads(ROSTERS.read_text(encoding="utf-8"))

    roster_display = {}
    for roster in rosters.get("rosters") or []:
        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for raw in roster.get(slot) or []:
                key = normalize_name(raw.get("name"))
                if not key:
                    continue
                roster_display.setdefault(
                    key,
                    {
                        "name": str(raw.get("name") or key.title()),
                        "team": raw.get("team"),
                        "age": raw.get("age"),
                    },
                )

    players = []
    for key in sorted(roster_display):
        if key == "joe mixon":
            continue
        row = values.get(key)
        if not row or row["pos"] not in {"QB", "RB", "WR", "TE", "DL", "LB", "DB"}:
            continue
        fv = float(row["value"])
        if not math.isfinite(fv) or fv <= 0:
            continue
        display = roster_display[key]
        players.append({
            "id": f"player:{key}",
            "kind": "player",
            "key": key,
            "name": display["name"],
            "pos": row["pos"],
            "team": display.get("team"),
            "age": display.get("age"),
            "fv": fv,
        })

    if len(players) < 300:
        raise RuntimeError(f"Too few eligible V4 players: {len(players)}")
    if any(normalize_name(p["name"]) == "joe mixon" for p in players):
        raise RuntimeError("Joe Mixon leaked into V4 catalog universe")

    phase2 = load_module(V3_PICK_UTILITY, "v3_pick_utility_for_v4_catalog")
    policy = phase2.parse_pick_policy(INDEX.read_text(encoding="utf-8"))

    picks = []
    for year in ("2027", "2028"):
        for round_num in range(1, 5):
            for slot in ("early", "mid", "late"):
                fv = float(phase2.pick_value(round_num, slot, year, policy))
                picks.append({
                    "id": f"pick:{year}:r{round_num}:{slot}",
                    "kind": "pick",
                    "key": f"{year}-r{round_num}-{slot}",
                    "name": f"{year} {slot.capitalize()} {ordinal(round_num)}",
                    "pos": "PICK",
                    "team": None,
                    "age": None,
                    "year": int(year),
                    "round": round_num,
                    "slot": slot,
                    "fv": fv,
                })

    if len(picks) != 24:
        raise RuntimeError(f"Expected 24 pick assets, got {len(picks)}")
    return players, picks


def side_key(side):
    return tuple(sorted(a["id"] for a in side))


def trade_signature(side_a, side_b):
    return tuple(sorted((side_key(side_a), side_key(side_b))))


def player_name_signature(side):
    return frozenset(
        normalize_name(a["name"]) for a in side if a["kind"] == "player"
    )


def is_known_ktc_example(side_a, side_b):
    if any(a["kind"] != "player" for a in side_a + side_b):
        return False
    a = player_name_signature(side_a)
    b = player_name_signature(side_b)
    return any((a == x and b == y) or (a == y and b == x) for x, y in CORRECT_KTC_EXAMPLES)


def generic_historical_signature(side_a, side_b):
    def describe(side):
        out = []
        for a in side:
            if a["kind"] == "player":
                out.append("player:" + normalize_name(a["name"]))
            else:
                out.append(f"pick:{a['year']}:r{int(a['round'])}:*")
        return tuple(sorted(out))
    return tuple(sorted((describe(side_a), describe(side_b))))


def historical_forbidden_signatures():
    phase1 = load_module(V3_PHASE1, "v3_phase1_trade_anchors_for_v4")
    doc = json.loads(TRADE_HISTORY.read_text(encoding="utf-8"))
    by_id = {
        str(row.get("transaction_id")): row
        for row in (doc.get("trades_with_picks") or [])
    }
    forbidden = set()
    for anchor in phase1.HISTORICAL_TRADE_ANCHORS:
        trade = by_id.get(anchor["transaction_id"])
        if not trade:
            raise RuntimeError(f"Missing historical trade {anchor['transaction_id']}")
        sides = []
        for side in trade.get("sides") or []:
            desc = []
            for p in side.get("received_players") or []:
                desc.append("player:" + normalize_name(p.get("name")))
            for pick in side.get("received_picks") or []:
                desc.append(
                    "pick:"
                    + str(pick.get("season"))
                    + ":r"
                    + str(int(pick.get("round")))
                    + ":*"
                )
            sides.append(tuple(sorted(desc)))
        forbidden.add(tuple(sorted(sides)))
    if len(forbidden) != 8:
        raise RuntimeError(f"Expected 8 historical exclusions, got {len(forbidden)}")
    return forbidden


def sample_unique(rng, pool, n):
    ordered = sorted(pool, key=lambda a: (-float(a["fv"]), a["id"]))
    chosen, used = [], set()
    while len(chosen) < n:
        idx = min(len(ordered) - 1, int((rng.random() ** 1.6) * len(ordered)))
        asset = ordered[idx]
        if asset["id"] in used:
            continue
        used.add(asset["id"])
        chosen.append(asset)
    return chosen


def sample_trade(rng, a_count, b_count, mix, players, picks):
    total = a_count + b_count
    if mix == "players_only":
        assets = sample_unique(rng, players, total)
    else:
        pick_count = rng.randint(1, min(total - 1, 4))
        assets = (
            sample_unique(rng, players, total - pick_count)
            + sample_unique(rng, picks, pick_count)
        )
        rng.shuffle(assets)
    if len({a["id"] for a in assets}) != total:
        raise RuntimeError("Duplicate asset within challenge")
    return assets[:a_count], assets[a_count:]


def sign(v):
    return 1 if v > EPS else (-1 if v < -EPS else 0)


def raw_delta(side_a, side_b):
    a = sum(float(x["fv"]) for x in side_a)
    b = sum(float(x["fv"]) for x in side_b)
    return (a - b) / (a + b)


def effective_score(side, candidate):
    vals = sorted((float(x["fv"]) for x in side), reverse=True)
    v1 = vals[0]
    v2 = vals[1] if len(vals) >= 2 else 0.0
    third = sum(vals[2:]) if len(vals) >= 3 else 0.0
    total = sum(vals)
    elite = min(1.0, max(0.0, v1 / 10000.0))
    premium = elite * (
        float(candidate["stud_strength"]) * v1
        - float(candidate["second_piece_discount"]) * v2
        - float(candidate["third_plus_discount"]) * third
    )
    return total + premium


def candidate_delta(side_a, side_b, candidate):
    a = effective_score(side_a, candidate)
    b = effective_score(side_b, candidate)
    return (a - b) / (abs(a) + abs(b))


def hash_rank(prefix, signature):
    return hashlib.sha256(
        (prefix + "|" + json.dumps(signature, sort_keys=True)).encode()
    ).hexdigest()


def public_asset(a):
    keep = {
        "kind": a["kind"],
        "name": a["name"],
        "pos": a["pos"],
        "team": a.get("team"),
        "age": a.get("age"),
        "fv": int(round(float(a["fv"]))),
    }
    if a["kind"] == "pick":
        keep.update(
            year=int(a["year"]),
            round=int(a["round"]),
            slot=a["slot"],
        )
    return keep


def choose_diverse(pool, n, appearance_counts, used_signatures, rank_key):
    available = [r for r in pool if r["signature"] not in used_signatures]
    chosen = []
    while len(chosen) < n:
        if not available:
            raise RuntimeError("Pool exhausted during diverse selection")

        def score(row):
            assets = row["side_a"] + row["side_b"]
            counts_after = [appearance_counts[a["id"]] + 1 for a in assets]
            return (
                max(counts_after),
                sum(counts_after),
                rank_key(row),
                hash_rank(row["cell"], row["signature"]),
            )

        best = min(available, key=score)
        chosen.append(best)
        used_signatures.add(best["signature"])
        for a in best["side_a"] + best["side_b"]:
            appearance_counts[a["id"]] += 1
        available = [r for r in available if r["signature"] != best["signature"]]
    return chosen


def selftest():
    c = {"stud_strength": 0.75, "second_piece_discount": 0.10, "third_plus_discount": 0.30}
    a = [{"fv": 8000}, {"fv": 1000}]
    b = [{"fv": 5000}, {"fv": 4200}]
    assert math.isfinite(raw_delta(a, b))
    assert math.isfinite(candidate_delta(a, b, c))
    fake1 = [
        {"kind": "player", "name": "George Pickens"},
        {"kind": "player", "name": "Kaelon Black"},
    ]
    fake2 = [
        {"kind": "player", "name": "Jayden Reed"},
        {"kind": "player", "name": "Parker Washington"},
        {"kind": "player", "name": "Jonathon Brooks"},
    ]
    assert is_known_ktc_example(fake1, fake2)
    print("Package Adjustment V4 Phase 3B catalog self-test PASS")


def generate():
    for path in (OUT, OUT_MD, OUT_MANIFEST):
        if path.exists():
            raise RuntimeError(f"V4 Phase 3B output already exists: {path}")

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    phase2 = json.loads(PHASE2_MANIFEST.read_text(encoding="utf-8"))
    feasibility = json.loads(FEASIBILITY.read_text(encoding="utf-8"))
    feasibility_manifest = json.loads(FEASIBILITY_MANIFEST.read_text(encoding="utf-8"))

    assert prereg["status"] == "FROZEN_BEFORE_SPENT_EVIDENCE_DEVELOPMENT"
    contract = prereg["fresh_confirmation_contract_if_candidate_frozen"]
    assert contract["challenge_count"] == 240
    assert contract["challenges_per_cell"] == 10
    assert contract["challenge_strata"] == [
        "candidate_vs_raw_disagreement", "balanced_broad"
    ]
    assert contract["known_five_ktc_examples_excluded_exactly"] is True
    assert contract["known_eight_historical_trades_excluded_exactly"] is True

    assert family["status"] == "FROZEN_V4_CONFIRMATION_FAMILY"
    assert family["family_count"] == 2
    assert family["fresh_vote_namespace_reserved"] == "__pkgv4c1__"
    assert phase2["fresh_confirmation_authorized"] is True
    assert feasibility["status"] == "V4_FRESH_CONFIRMATION_SIGNAL_FEASIBLE"
    assert feasibility["human_vote_outcomes_read"] is False
    assert feasibility_manifest["human_vote_outcomes_read"] is False

    candidates = family["candidate_family"]
    players, picks = build_asset_universe()
    forbidden_history = historical_forbidden_signatures()

    rng = random.Random(RNG_SEED)
    pools = {}

    for topology, (a_count, b_count) in TOPOLOGIES.items():
        for mix in ASSET_MIXES:
            targeted = {}
            broad = {}

            for _ in range(MAX_ATTEMPTS_PER_GROUP):
                side_a, side_b = sample_trade(
                    rng, a_count, b_count, mix, players, picks
                )
                sig = trade_signature(side_a, side_b)
                if sig in targeted or sig in broad:
                    continue
                if is_known_ktc_example(side_a, side_b):
                    continue
                if generic_historical_signature(side_a, side_b) in forbidden_history:
                    continue

                raw_a = sum(float(x["fv"]) for x in side_a)
                raw_b = sum(float(x["fv"]) for x in side_b)
                ratio = raw_a / raw_b
                if not (RAW_RATIO_MIN <= ratio <= RAW_RATIO_MAX):
                    continue

                d0 = raw_delta(side_a, side_b)
                d1 = candidate_delta(side_a, side_b, candidates[0])
                d2 = candidate_delta(side_a, side_b, candidates[1])
                row = {
                    "topology": topology,
                    "asset_mix": mix,
                    "side_a": side_a,
                    "side_b": side_b,
                    "signature": sig,
                    "raw_ratio": ratio,
                    "raw_imbalance": abs(math.log(ratio)),
                    "raw_delta_abs": abs(d0),
                    "candidate_1_delta_abs": abs(d1),
                    "candidate_2_delta_abs": abs(d2),
                }

                broad.setdefault(sig, row)

                s0, s1, s2 = sign(d0), sign(d1), sign(d2)
                if 0 not in (s0, s1, s2) and s1 == s2 and s0 != s1:
                    margin = min(abs(d0), abs(d1), abs(d2))
                    if margin >= MIN_SIGN_MARGIN:
                        targeted.setdefault(
                            sig, {**row, "disagreement_margin": margin}
                        )

                if len(targeted) >= POOL_TARGET_TARGETED and len(broad) >= POOL_TARGET_BROAD:
                    break

            if len(targeted) < POOL_TARGET_TARGETED:
                raise RuntimeError(
                    f"Insufficient targeted pool {topology}/{mix}: {len(targeted)}"
                )
            if len(broad) < POOL_TARGET_BROAD:
                raise RuntimeError(
                    f"Insufficient broad pool {topology}/{mix}: {len(broad)}"
                )

            pools[(topology, mix, "candidate_vs_raw_disagreement")] = list(targeted.values())
            pools[(topology, mix, "balanced_broad")] = list(broad.values())

    appearance_counts = Counter()
    used_signatures = set()
    selected = []

    # Select targeted first by meaningful margin, with diversity dominating.
    for topology in TOPOLOGIES:
        for mix in ASSET_MIXES:
            key = (topology, mix, "candidate_vs_raw_disagreement")
            for row in pools[key]:
                row["cell"] = "|".join(key)
            chosen = choose_diverse(
                pools[key],
                CHALLENGES_PER_CELL,
                appearance_counts,
                used_signatures,
                rank_key=lambda r: -r["disagreement_margin"],
            )
            selected.extend({**r, "stratum": key[2]} for r in chosen)

    # Broad stratum: selection does NOT require disagreement. Rank only by raw
    # balance and deterministic hash, after the same diversity objective.
    for topology in TOPOLOGIES:
        for mix in ASSET_MIXES:
            key = (topology, mix, "balanced_broad")
            for row in pools[key]:
                row["cell"] = "|".join(key)
            chosen = choose_diverse(
                pools[key],
                CHALLENGES_PER_CELL,
                appearance_counts,
                used_signatures,
                rank_key=lambda r: r["raw_imbalance"],
            )
            selected.extend({**r, "stratum": key[2]} for r in chosen)

    if len(selected) != 240:
        raise RuntimeError(f"Expected 240 selected challenges, got {len(selected)}")
    if len({r["signature"] for r in selected}) != 240:
        raise RuntimeError("Duplicate selected trade signature")

    cell_counts = Counter(
        f"{r['topology']}|{r['asset_mix']}|{r['stratum']}" for r in selected
    )
    if len(cell_counts) != 24 or any(v != 10 for v in cell_counts.values()):
        raise RuntimeError(f"Invalid 24-cell balance: {dict(cell_counts)}")

    topology_counts = Counter(r["topology"] for r in selected)
    mix_counts = Counter(r["asset_mix"] for r in selected)
    stratum_counts = Counter(r["stratum"] for r in selected)
    if any(v != 40 for v in topology_counts.values()) or len(topology_counts) != 6:
        raise RuntimeError("Topology balance failure")
    if mix_counts != Counter({"players_only": 120, "includes_picks": 120}):
        raise RuntimeError("Asset-mix balance failure")
    if stratum_counts != Counter({
        "candidate_vs_raw_disagreement": 120,
        "balanced_broad": 120,
    }):
        raise RuntimeError("Stratum balance failure")

    known_matches = sum(
        1 for r in selected if is_known_ktc_example(r["side_a"], r["side_b"])
    )
    historical_matches = sum(
        1 for r in selected
        if generic_historical_signature(r["side_a"], r["side_b"]) in forbidden_history
    )
    joe_count = sum(
        1 for r in selected
        for a in (r["side_a"] + r["side_b"])
        if a["kind"] == "player" and normalize_name(a["name"]) == "joe mixon"
    )
    invalid_pick_count = sum(
        1 for r in selected
        for a in (r["side_a"] + r["side_b"])
        if a["kind"] == "pick" and int(a["year"]) not in {2027, 2028}
    )
    if known_matches or historical_matches or joe_count or invalid_pick_count:
        raise RuntimeError(
            "Forbidden V4 catalog content: "
            f"ktc={known_matches} history={historical_matches} "
            f"joe={joe_count} invalid_pick={invalid_pick_count}"
        )

    # Stable challenge IDs within each cell.
    by_cell = defaultdict(list)
    for row in selected:
        by_cell[
            (row["topology"], row["asset_mix"], row["stratum"])
        ].append(row)

    challenges = []
    for cell in sorted(by_cell):
        rows = sorted(
            by_cell[cell],
            key=lambda r: hash_rank("|".join(cell), r["signature"]),
        )
        topology, mix, stratum = cell
        for idx, row in enumerate(rows, 1):
            challenge_id = (
                "pkgv4c1_"
                + topology
                + "_"
                + mix
                + "_"
                + ("targeted" if stratum == "candidate_vs_raw_disagreement" else "broad")
                + f"_{idx:02d}"
            )
            challenges.append({
                "schema_version": 1,
                "experiment": "package_adjustment_v4_fresh_confirmation",
                "id": challenge_id,
                "research_cell": f"{topology}|{mix}|{stratum}",
                "topology": topology,
                "asset_mix": mix,
                "challenge_stratum": stratum,
                "side_a_count": len(row["side_a"]),
                "side_b_count": len(row["side_b"]),
                "side_a": [public_asset(a) for a in row["side_a"]],
                "side_b": [public_asset(a) for a in row["side_b"]],
                "raw_side_total_ratio": round(row["raw_ratio"], 12),
            })

    distinct_players = {
        normalize_name(a["name"])
        for c in challenges
        for a in c["side_a"] + c["side_b"]
        if a["kind"] == "player"
    }
    distinct_picks = {
        a["name"]
        for c in challenges
        for a in c["side_a"] + c["side_b"]
        if a["kind"] == "pick"
    }
    appearance = Counter(
        a["name"]
        for c in challenges
        for a in c["side_a"] + c["side_b"]
    )

    doc = {
        "schema_version": 1,
        "study_id": "package-adjustment-v4-elite-fragmentation",
        "phase": "3B",
        "status": "frozen_unreleased_fresh_confirmation_catalog",
        "frozen": True,
        "released": False,
        "voting_activated": False,
        "research_only": True,
        "consumer_changed": False,
        "production_formula_enabled": False,
        "production_revision_retained": "v1.6-v5-size2-composition-overlay",
        "vote_namespace_reserved": "__pkgv4c1__",
        "human_vote_outcomes_read": False,
        "old_v3_600_vote_dataset_read": False,
        "old_nextgen_900_vote_dataset_read": False,
        "candidate_family_fingerprint_sha256": canonical_hash(
            family["candidate_family"]
        ),
        "catalog_diagnostics": {
            "challenge_count": 240,
            "research_cell_count": 24,
            "challenges_per_cell": 10,
            "topology_counts": dict(sorted(topology_counts.items())),
            "asset_mix_counts": dict(sorted(mix_counts.items())),
            "stratum_counts": dict(sorted(stratum_counts.items())),
            "known_ktc_examples_in_selected_catalog": known_matches,
            "historical_trade_matches_in_selected_catalog": historical_matches,
            "joe_mixon_occurrences": joe_count,
            "invalid_pick_year_occurrences": invalid_pick_count,
            "distinct_player_assets": len(distinct_players),
            "distinct_pick_assets": len(distinct_picks),
            "max_asset_appearance_count": max(appearance.values()),
            "median_asset_appearance_count": sorted(appearance.values())[len(appearance)//2],
        },
        "selection_contract": {
            "rng_seed": RNG_SEED,
            "raw_ratio_range": [RAW_RATIO_MIN, RAW_RATIO_MAX],
            "targeted_minimum_sign_margin": MIN_SIGN_MARGIN,
            "targeted_definition": (
                "both frozen V4 candidates agree on trade direction, raw addition "
                "points the opposite direction, and every normalized score has "
                "absolute margin >= 0.005"
            ),
            "balanced_broad_definition": (
                "realistic raw-balanced trade; no model-disagreement requirement"
            ),
            "known_five_ktc_examples_excluded": True,
            "known_eight_historical_trades_excluded": True,
            "joe_mixon_excluded": True,
            "pick_years_allowed": [2027, 2028],
        },
        "challenges": challenges,
    }

    OUT.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Package Adjustment V4 — Phase 3B Confirmation Catalog",
        "",
        "**Status:** `frozen_unreleased_fresh_confirmation_catalog`",
        "",
        "- Challenges: **240**",
        "- Research cells: **24**",
        "- Challenges per cell: **10**",
        "- Targeted candidate-vs-raw: **120**",
        "- Broad-balanced: **120**",
        "- Players-only: **120**",
        "- Includes picks: **120**",
        "- Joe Mixon occurrences: **0**",
        "- 2029+ pick occurrences: **0**",
        "- Known KTC example matches: **0**",
        "- Historical real-trade matches: **0**",
        f"- Distinct player assets: **{len(distinct_players)}**",
        f"- Distinct pick assets: **{len(distinct_picks)}**",
        f"- Max asset appearances: **{max(appearance.values())}**",
        "",
        "Voting is not activated. Human vote outcomes were not read.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "status": "package_adjustment_v4_phase3b_confirmation_catalog_manifest",
        "frozen": True,
        "released": False,
        "voting_activated": False,
        "production_change_authorized": False,
        "production_revision_retained": "v1.6-v5-size2-composition-overlay",
        "human_vote_outcomes_read": False,
        "source_artifacts": {
            "phase1_preregistration": {
                "path": str(PREREG.relative_to(ROOT)),
                "git_blob_sha": git_blob(PREREG),
                "sha256": sha256(PREREG),
            },
            "frozen_candidate_family": {
                "path": str(FAMILY.relative_to(ROOT)),
                "git_blob_sha": git_blob(FAMILY),
                "sha256": sha256(FAMILY),
            },
            "phase2_manifest": {
                "path": str(PHASE2_MANIFEST.relative_to(ROOT)),
                "git_blob_sha": git_blob(PHASE2_MANIFEST),
                "sha256": sha256(PHASE2_MANIFEST),
            },
            "phase3a_feasibility": {
                "path": str(FEASIBILITY.relative_to(ROOT)),
                "git_blob_sha": git_blob(FEASIBILITY),
                "sha256": sha256(FEASIBILITY),
            },
            "phase3a_feasibility_manifest": {
                "path": str(FEASIBILITY_MANIFEST.relative_to(ROOT)),
                "git_blob_sha": git_blob(FEASIBILITY_MANIFEST),
                "sha256": sha256(FEASIBILITY_MANIFEST),
            },
            "index_html": {"git_blob_sha": git_blob(INDEX)},
            "league_rosters": {"git_blob_sha": git_blob(ROSTERS)},
            "trade_history": {"git_blob_sha": git_blob(TRADE_HISTORY)},
            "generator": {"git_blob_sha": git_blob(Path(__file__).resolve())},
        },
        "outputs": {
            "catalog": {
                "path": str(OUT.relative_to(ROOT)),
                "sha256": sha256(OUT),
            },
            "summary": {
                "path": str(OUT_MD.relative_to(ROOT)),
                "sha256": sha256(OUT_MD),
            },
        },
        "catalog_diagnostics": doc["catalog_diagnostics"],
        "next_action": (
            "Audit the frozen catalog, then activate fresh V4 confirmation voting "
            "under namespace __pkgv4c1__."
        ),
    }
    OUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(doc["catalog_diagnostics"], indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        generate()


if __name__ == "__main__":
    main()

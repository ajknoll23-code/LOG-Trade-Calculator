#!/usr/bin/env python3
"""Package Adjustment V3 Phase 3B — frozen fresh-confirmation catalog.

Research only. This generator does not activate voting and does not read any
human vote outcomes.

Fresh namespace reserved by Phase 3A: __pkgv3c1__
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import importlib.util
import json
import math
import random
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "research" / "package-adjustment-v3-ktc-style"
INDEX = ROOT / "index.html"
ROSTERS = ROOT / "data" / "league_rosters.json"
TRADE_HISTORY = ROOT / "data" / "trade_history.json"

PREREG = D / "phase3_confirmation_preregistration.json"
PREREG_MANIFEST = D / "phase3_confirmation_preregistration_manifest.json"
PHASE2_SCRIPT = D / "package_adjustment_v3_phase2.py"
PHASE1_SCRIPT = D / "package_adjustment_v3_phase1.py"

OUT = D / "phase3_confirmation_catalog.json"
OUT_MD = D / "phase3_confirmation_catalog.md"
OUT_MANIFEST = D / "phase3_confirmation_catalog_manifest.json"

VALIDATION_DIR = ROOT / "scripts" / "validation"
if str(VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATION_DIR))
import snapshot_values  # noqa: E402

RNG_SEED = 202609183
MAX_ATTEMPTS_PER_TOPOLOGY_MIX = 900_000
POOL_TARGET_PER_BAND = 60
TARGETED_1V3_ATTEMPTS_PER_BAND = 500_000
TARGETED_1V3_Z_NEIGHBORS = 10
EPS = 1e-12

KNOWN_KTC_NAME_SIGNATURES = [
    (
        frozenset(["jahmyr gibbs"]),
        frozenset(["devon achane", "tee higgins"]),
    ),
    (
        frozenset(["ceedee lamb", "sam laporta"]),
        frozenset(["rome odunze", "saquon barkley"]),
    ),
    (
        frozenset(["george pickens", "marshawn lloyd"]),
        frozenset(["isaiah likely", "ryan flournoy", "rico dowdle"]),
    ),
    (
        frozenset(["josh allen"]),
        frozenset(["caleb williams", "saquon barkley"]),
    ),
    (
        frozenset(["george pickens", "kaelon black"]),
        frozenset(["jayden reed", "mike washington", "jonathon brooks"]),
    ),
]


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(
        f"blob {len(data)}\0".encode("utf-8") + data
    ).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(obj) -> str:
    return hashlib.sha256(
        json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def normalize_name(value) -> str:
    return snapshot_values.normalize_lookup_name(value)


def title_from_key(key: str) -> str:
    return " ".join(piece.capitalize() for piece in key.split())


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ordinal(round_num: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(
        round_num, f"{round_num}th"
    )


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
                        "name": str(
                            raw.get("name") or title_from_key(key)
                        ),
                        "team": raw.get("team"),
                        "age": raw.get("age"),
                    },
                )

    players = []
    for key in sorted(roster_display):
        row = values.get(key)
        if not row or row["pos"] == "K":
            continue
        value = float(row["value"])
        if not math.isfinite(value) or value <= 0:
            continue
        display = roster_display[key]
        players.append(
            {
                "id": f"player:{key}",
                "kind": "player",
                "key": key,
                "name": display["name"],
                "pos": row["pos"],
                "team": display.get("team"),
                "age": display.get("age"),
                "fv": value,
            }
        )

    if len(players) < 300:
        raise RuntimeError(
            f"Too few currently rostered valued players: {len(players)}"
        )

    phase2 = load_module(
        PHASE2_SCRIPT, "package_adjustment_v3_phase2"
    )
    policy = phase2.parse_pick_policy(
        INDEX.read_text(encoding="utf-8")
    )

    picks = []
    for year in ("2027", "2028", "2029"):
        for round_num in range(1, 5):
            for slot in ("early", "mid", "late"):
                value = float(
                    phase2.pick_value(
                        round_num, slot, year, policy
                    )
                )
                picks.append(
                    {
                        "id": (
                            f"pick:{year}:r{round_num}:{slot}"
                        ),
                        "kind": "pick",
                        "key": (
                            f"{year}-r{round_num}-{slot}"
                        ),
                        "name": (
                            f"{year} {slot.capitalize()} "
                            f"{ordinal(round_num)}"
                        ),
                        "pos": "PICK",
                        "team": None,
                        "age": None,
                        "year": year,
                        "round": round_num,
                        "slot": slot,
                        "fv": value,
                    }
                )

    assert len(picks) == 36
    return players, picks


def side_key(side):
    return tuple(sorted(asset["id"] for asset in side))


def trade_signature(side_a, side_b):
    return tuple(sorted((side_key(side_a), side_key(side_b))))


def player_name_signature(side):
    return frozenset(
        normalize_name(asset["name"])
        for asset in side
        if asset["kind"] == "player"
    )


def is_known_ktc_trade(side_a, side_b):
    if any(
        asset["kind"] != "player"
        for asset in side_a + side_b
    ):
        return False

    a = player_name_signature(side_a)
    b = player_name_signature(side_b)
    return any(
        (a == left and b == right)
        or (a == right and b == left)
        for left, right in KNOWN_KTC_NAME_SIGNATURES
    )


def historical_forbidden_signatures():
    phase1 = load_module(
        PHASE1_SCRIPT, "package_adjustment_v3_phase1"
    )
    history = json.loads(
        TRADE_HISTORY.read_text(encoding="utf-8")
    )
    by_id = {
        str(row.get("transaction_id")): row
        for row in (history.get("trades_with_picks") or [])
    }

    forbidden = set()
    for anchor in phase1.HISTORICAL_TRADE_ANCHORS:
        trade = by_id.get(anchor["transaction_id"])
        if not trade:
            raise RuntimeError(
                "Missing historical trade "
                f"{anchor['transaction_id']}"
            )

        sides = []
        for side in trade.get("sides") or []:
            desc = []
            for player in side.get("received_players") or []:
                desc.append(
                    "player:"
                    + normalize_name(player.get("name"))
                )
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

    return forbidden


def generic_historical_signature(side_a, side_b):
    def describe(side):
        out = []
        for asset in side:
            if asset["kind"] == "player":
                out.append(
                    "player:"
                    + normalize_name(asset["name"])
                )
            else:
                out.append(
                    "pick:"
                    + str(asset["year"])
                    + ":r"
                    + str(int(asset["round"]))
                    + ":*"
                )
        return tuple(sorted(out))

    return tuple(
        sorted((describe(side_a), describe(side_b)))
    )


def sample_unique(rng, pool, n):
    if len(pool) < n:
        raise RuntimeError("Insufficient unique assets")

    ordered = sorted(
        pool,
        key=lambda a: (-float(a["fv"]), a["id"]),
    )
    chosen = []
    used = set()

    while len(chosen) < n:
        # Broad rank-biased draw: useful for creating concentration
        # differences without turning every ballot into elite-only assets.
        idx = min(
            len(ordered) - 1,
            int((rng.random() ** 1.6) * len(ordered)),
        )
        asset = ordered[idx]
        if asset["id"] in used:
            continue
        used.add(asset["id"])
        chosen.append(asset)

    return chosen


def sample_trade(
    rng, a_count, b_count, asset_mix, players, picks
):
    total = a_count + b_count

    if asset_mix == "players_only":
        assets = sample_unique(rng, players, total)
    elif asset_mix == "includes_picks":
        # At least one pick and one player across the trade.
        pick_count = rng.randint(
            1, min(total - 1, 4)
        )
        player_count = total - pick_count
        assets = (
            sample_unique(rng, players, player_count)
            + sample_unique(rng, picks, pick_count)
        )
        rng.shuffle(assets)
    else:
        raise ValueError(asset_mix)

    if len({a["id"] for a in assets}) != total:
        raise RuntimeError(
            "Duplicate asset generated within trade"
        )

    return assets[:a_count], assets[a_count:]


def normalized_score_delta(
    side_a, side_b, gamma, apex
):
    score_a = sum(
        (float(asset["fv"]) / apex) ** gamma
        for asset in side_a
    )
    score_b = sum(
        (float(asset["fv"]) / apex) ** gamma
        for asset in side_b
    )
    denom = score_a + score_b
    if denom <= 0:
        raise RuntimeError("Nonpositive score denominator")
    return (score_a - score_b) / denom


def sign(value):
    if value > EPS:
        return 1
    if value < -EPS:
        return -1
    return 0


def disagreement_band(d201, d215, d230):
    s201, s215, s230 = (
        sign(d201),
        sign(d215),
        sign(d230),
    )
    if 0 in (s201, s215, s230):
        return None
    if s201 != s215 and s215 == s230:
        return "g201_vs_g215"
    if s201 == s215 and s215 != s230:
        return "g215_vs_g230"
    return None


def candidate_record(
    topology, asset_mix, side_a, side_b, apex
):
    raw_a = sum(float(a["fv"]) for a in side_a)
    raw_b = sum(float(a["fv"]) for a in side_b)
    ratio = raw_a / raw_b

    if not (0.80 <= ratio <= 1.25):
        return None

    d201 = normalized_score_delta(
        side_a, side_b, 2.01, apex
    )
    d215 = normalized_score_delta(
        side_a, side_b, 2.15, apex
    )
    d230 = normalized_score_delta(
        side_a, side_b, 2.30, apex
    )
    band = disagreement_band(d201, d215, d230)
    if band is None:
        return None

    if band == "g201_vs_g215":
        margin = min(abs(d201), abs(d215))
    else:
        margin = min(abs(d215), abs(d230))

    return {
        "topology": topology,
        "asset_mix": asset_mix,
        "band": band,
        "side_a": side_a,
        "side_b": side_b,
        "raw_a": raw_a,
        "raw_b": raw_b,
        "raw_ratio": ratio,
        "raw_imbalance": abs(math.log(ratio)),
        "disagreement_margin": margin,
        "trade_signature": trade_signature(
            side_a, side_b
        ),
    }



def third_asset_boundary_value(a_value, x_value, y_value, gamma):
    remaining = (
        float(a_value) ** gamma
        - float(x_value) ** gamma
        - float(y_value) ** gamma
    )
    if remaining <= 0:
        return None
    return remaining ** (1.0 / gamma)


def targeted_1v3_fill(
    *,
    asset_mix,
    band,
    players,
    picks,
    apex,
    forbidden_history,
    cell_candidates,
    rng,
):
    """Construct rare 1v3 crossings without changing the frozen cell contract."""
    cell = f"1v3|{asset_mix}|{band}"
    if len(cell_candidates[cell]) >= POOL_TARGET_PER_BAND:
        return {
            "attempts": 0,
            "accepted": 0,
            "final_pool_size": len(cell_candidates[cell]),
        }

    if asset_mix == "players_only":
        universe = list(players)
        z_pool = list(players)
    elif asset_mix == "includes_picks":
        universe = list(players) + list(picks)
        z_pool = list(players) + list(picks)
    else:
        raise ValueError(asset_mix)

    a_pool = sorted(
        universe,
        key=lambda asset: (-float(asset["fv"]), asset["id"]),
    )
    a_pool = a_pool[: max(80, int(len(a_pool) * 0.60))]

    z_sorted = sorted(
        z_pool,
        key=lambda asset: (float(asset["fv"]), asset["id"]),
    )
    z_values = [float(asset["fv"]) for asset in z_sorted]

    accepted = 0
    attempts = 0

    for attempts in range(1, TARGETED_1V3_ATTEMPTS_PER_BAND + 1):
        if len(cell_candidates[cell]) >= POOL_TARGET_PER_BAND:
            break

        a = a_pool[rng.randrange(len(a_pool))]
        a_value = float(a["fv"])

        pair_pool = [
            asset
            for asset in universe
            if asset["id"] != a["id"]
            and float(asset["fv"]) < a_value * 0.98
            and float(asset["fv"]) > a_value * 0.08
        ]
        if len(pair_pool) < 2:
            continue

        if asset_mix == "includes_picks" and attempts % 2 == 0:
            pick_pair = [x for x in pair_pool if x["kind"] == "pick"]
            player_pair = [x for x in pair_pool if x["kind"] == "player"]
            if not pick_pair or not player_pair:
                continue
            x = pick_pair[rng.randrange(len(pick_pair))]
            y = player_pair[rng.randrange(len(player_pair))]
        else:
            x, y = rng.sample(pair_pool, 2)

        if len({a["id"], x["id"], y["id"]}) != 3:
            continue

        if band == "g201_vs_g215":
            low_gamma, high_gamma = 2.01, 2.15
        elif band == "g215_vs_g230":
            low_gamma, high_gamma = 2.15, 2.30
        else:
            raise ValueError(band)

        z_low = third_asset_boundary_value(
            a_value, float(x["fv"]), float(y["fv"]), low_gamma
        )
        z_high = third_asset_boundary_value(
            a_value, float(x["fv"]), float(y["fv"]), high_gamma
        )
        if z_low is None or z_high is None:
            continue

        lo = min(z_low, z_high)
        hi = max(z_low, z_high)
        if not (hi > lo + EPS):
            continue

        start = bisect.bisect_right(z_values, lo + EPS)
        if start >= len(z_sorted):
            continue

        for idx in range(
            start,
            min(len(z_sorted), start + TARGETED_1V3_Z_NEIGHBORS),
        ):
            z = z_sorted[idx]
            z_value = float(z["fv"])
            if z_value >= hi - EPS:
                break
            if z["id"] in {a["id"], x["id"], y["id"]}:
                continue

            side_a = [a]
            side_b = [x, y, z]

            if asset_mix == "players_only":
                if any(asset["kind"] != "player" for asset in side_a + side_b):
                    continue
            else:
                kinds = {asset["kind"] for asset in side_a + side_b}
                if kinds != {"player", "pick"}:
                    continue

            if is_known_ktc_trade(side_a, side_b):
                continue
            if generic_historical_signature(side_a, side_b) in forbidden_history:
                continue

            candidate = candidate_record(
                "1v3", asset_mix, side_a, side_b, apex
            )
            if candidate is None or candidate["band"] != band:
                continue

            sig = repr(candidate["trade_signature"])
            old = cell_candidates[cell].get(sig)
            if old is None or candidate["disagreement_margin"] > old["disagreement_margin"]:
                if old is None:
                    accepted += 1
                cell_candidates[cell][sig] = candidate

    return {
        "attempts": attempts,
        "accepted": accepted,
        "final_pool_size": len(cell_candidates[cell]),
    }


def asset_public(asset):
    row = {
        "id": asset["id"],
        "kind": asset["kind"],
        "key": asset["key"],
        "name": asset["name"],
        "pos": asset["pos"],
        "team": asset.get("team"),
        "age": asset.get("age"),
        "fv": round(float(asset["fv"]), 3),
    }
    if asset["kind"] == "pick":
        row.update(
            {
                "year": asset["year"],
                "round": int(asset["round"]),
                "slot": asset["slot"],
            }
        )
    return row


def selftest():
    def fake(name, value):
        return {
            "id": f"player:{name}",
            "kind": "player",
            "key": name,
            "name": title_from_key(name),
            "pos": "WR",
            "team": "ARI",
            "age": 25,
            "fv": float(value),
        }

    a = [fake("josh allen", 9996)]
    b = [
        fake("caleb williams", 8112),
        fake("saquon barkley", 5264),
    ]
    assert is_known_ktc_trade(a, b)
    assert trade_signature(a, b) == trade_signature(
        b, a
    )
    assert (
        normalize_name("De'Von Achane")
        == "devon achane"
    )

    target_value = 10000.0
    x_value = 6000.0
    y_value = 3500.0
    z201 = third_asset_boundary_value(
        target_value, x_value, y_value, 2.01
    )
    z215 = third_asset_boundary_value(
        target_value, x_value, y_value, 2.15
    )
    assert z201 is not None and z215 is not None
    assert abs(z201 - z215) > EPS

    apex = 10000.0
    for gamma in (2.01, 2.15, 2.30):
        d = normalized_score_delta(
            a, b, gamma, apex
        )
        assert math.isfinite(d)

    print(
        "Package Adjustment V3 Phase 3B "
        "catalog generator self-test PASS"
    )


def generate():
    prereg = json.loads(
        PREREG.read_text(encoding="utf-8")
    )
    prereg_manifest = json.loads(
        PREREG_MANIFEST.read_text(encoding="utf-8")
    )

    assert (
        prereg["status"]
        == "FROZEN_FRESH_CONFIRMATION_PREREGISTRATION"
    )
    assert prereg["frozen"] is True
    assert prereg["production_change_authorized"] is False
    assert (
        prereg["catalog_design"]["research_cell_count"]
        == 24
    )
    assert (
        prereg["catalog_design"]["challenge_count"]
        == 240
    )
    assert (
        prereg["catalog_design"][
            "challenges_per_cell"
        ]
        == 10
    )
    assert (
        prereg["catalog_design"]["new_vote_namespace"]
        == "__pkgv3c1__"
    )
    assert prereg_manifest["catalog_generated"] is False
    assert prereg_manifest["voting_activated"] is False
    assert (
        prereg_manifest["human_vote_outcomes_read"]
        is False
    )
    assert (
        prereg_manifest["old_900_vote_dataset_read"]
        is False
    )

    players, picks = build_asset_universe()
    all_assets = players + picks
    apex = max(float(a["fv"]) for a in all_assets)

    forbidden_history = (
        historical_forbidden_signatures()
    )

    rng = random.Random(RNG_SEED)
    cell_candidates = defaultdict(dict)
    attempts_by_group = {}
    ktc_exclusions = 0
    historical_exclusions = 0

    for topology in prereg["catalog_design"][
        "topologies"
    ]:
        a_count, b_count = map(
            int, topology.split("v")
        )

        for asset_mix in prereg["catalog_design"][
            "asset_mix_groups"
        ]:
            group = f"{topology}|{asset_mix}"
            attempts = 0

            random_attempt_limit = (
                min(MAX_ATTEMPTS_PER_TOPOLOGY_MIX, 100_000)
                if topology == "1v3"
                else MAX_ATTEMPTS_PER_TOPOLOGY_MIX
            )

            while attempts < random_attempt_limit:
                attempts += 1

                side_a, side_b = sample_trade(
                    rng,
                    a_count,
                    b_count,
                    asset_mix,
                    players,
                    picks,
                )

                if is_known_ktc_trade(
                    side_a, side_b
                ):
                    ktc_exclusions += 1
                    continue

                if (
                    generic_historical_signature(
                        side_a, side_b
                    )
                    in forbidden_history
                ):
                    historical_exclusions += 1
                    continue

                c = candidate_record(
                    topology,
                    asset_mix,
                    side_a,
                    side_b,
                    apex,
                )
                if c is None:
                    continue

                cell = (
                    f"{topology}|{asset_mix}|"
                    f"{c['band']}"
                )
                sig = repr(c["trade_signature"])
                old = cell_candidates[cell].get(sig)
                if (
                    old is None
                    or c["disagreement_margin"]
                    > old["disagreement_margin"]
                ):
                    cell_candidates[cell][sig] = c

                ready = all(
                    len(
                        cell_candidates[
                            f"{topology}|{asset_mix}|{band}"
                        ]
                    )
                    >= POOL_TARGET_PER_BAND
                    for band in prereg[
                        "catalog_design"
                    ]["disagreement_bands"]
                )
                if ready:
                    break

            attempts_by_group[group] = attempts

    targeted_1v3_diagnostics = {}
    for asset_mix in prereg["catalog_design"]["asset_mix_groups"]:
        for band in prereg["catalog_design"]["disagreement_bands"]:
            key = f"1v3|{asset_mix}|{band}"
            targeted_1v3_diagnostics[key] = targeted_1v3_fill(
                asset_mix=asset_mix,
                band=band,
                players=players,
                picks=picks,
                apex=apex,
                forbidden_history=forbidden_history,
                cell_candidates=cell_candidates,
                rng=rng,
            )

    expected_cells = set(
        prereg["catalog_design"]["research_cells"]
    )
    missing = expected_cells - set(cell_candidates)
    extra = set(cell_candidates) - expected_cells
    if missing or extra:
        raise RuntimeError(
            "Research cell mismatch "
            f"missing={sorted(missing)} "
            f"extra={sorted(extra)}"
        )

    short = {
        cell: len(cell_candidates[cell])
        for cell in sorted(expected_cells)
        if len(cell_candidates[cell]) < 10
    }
    if short:
        raise RuntimeError(
            "Underfilled frozen disagreement cells: "
            f"{short}"
        )

    appearance = Counter()
    selected = []
    selected_signatures = set()

    for cell in sorted(expected_cells):
        pool = list(cell_candidates[cell].values())

        for i in range(10):
            available = [
                c
                for c in pool
                if c["trade_signature"]
                not in selected_signatures
            ]
            if not available:
                raise RuntimeError(
                    f"No unique candidate left for {cell}"
                )

            available.sort(
                key=lambda c: (
                    -round(
                        c["disagreement_margin"],
                        12,
                    ),
                    round(c["raw_imbalance"], 12),
                    sum(
                        appearance[a["id"]]
                        for a in (
                            c["side_a"]
                            + c["side_b"]
                        )
                    ),
                    repr(c["trade_signature"]),
                )
            )
            chosen = available[0]
            selected_signatures.add(
                chosen["trade_signature"]
            )

            for asset in (
                chosen["side_a"]
                + chosen["side_b"]
            ):
                appearance[asset["id"]] += 1

            topology, asset_mix, band = (
                cell.split("|")
            )
            cid = (
                f"pkgv3c1_{topology}_"
                f"{asset_mix}_{band}_{i+1:02d}"
            )

            selected.append(
                {
                    "id": cid,
                    "schema_version": 1,
                    "experiment":
                        "package_adjustment_v3_fresh_confirmation",
                    "research_cell": cell,
                    "topology": topology,
                    "asset_mix": asset_mix,
                    "disagreement_band": band,
                    "side_a": [
                        asset_public(a)
                        for a in chosen["side_a"]
                    ],
                    "side_b": [
                        asset_public(a)
                        for a in chosen["side_b"]
                    ],
                    "side_a_count": len(
                        chosen["side_a"]
                    ),
                    "side_b_count": len(
                        chosen["side_b"]
                    ),
                    "side_a_raw_fv": round(
                        chosen["raw_a"], 3
                    ),
                    "side_b_raw_fv": round(
                        chosen["raw_b"], 3
                    ),
                    "raw_side_total_ratio": round(
                        chosen["raw_ratio"], 9
                    ),
                    "selection_diagnostics": {
                        "disagreement_margin": round(
                            chosen[
                                "disagreement_margin"
                            ],
                            12,
                        ),
                        "raw_total_log_imbalance":
                            round(
                                chosen[
                                    "raw_imbalance"
                                ],
                                12,
                            ),
                    },
                }
            )

    if len(selected) != 240:
        raise RuntimeError(
            f"Expected 240 challenges, "
            f"got {len(selected)}"
        )

    if len({c["id"] for c in selected}) != 240:
        raise RuntimeError(
            "Duplicate challenge IDs"
        )
    if len(selected_signatures) != 240:
        raise RuntimeError(
            "Duplicate trade signatures"
        )

    by_cell = Counter(
        c["research_cell"] for c in selected
    )
    if (
        set(by_cell) != expected_cells
        or set(by_cell.values()) != {10}
    ):
        raise RuntimeError(
            "Catalog is not exactly 10/cell"
        )

    # Final frozen-prediction and exclusion verification.
    for row in selected:
        side_a = row["side_a"]
        side_b = row["side_b"]

        d201 = normalized_score_delta(
            side_a, side_b, 2.01, apex
        )
        d215 = normalized_score_delta(
            side_a, side_b, 2.15, apex
        )
        d230 = normalized_score_delta(
            side_a, side_b, 2.30, apex
        )
        got_band = disagreement_band(
            d201, d215, d230
        )
        if got_band != row["disagreement_band"]:
            raise RuntimeError(
                f"{row['id']}: disagreement drift"
            )

        if is_known_ktc_trade(
            side_a, side_b
        ):
            raise RuntimeError(
                f"{row['id']}: KTC example leaked"
            )

        if (
            generic_historical_signature(
                side_a, side_b
            )
            in forbidden_history
        ):
            raise RuntimeError(
                f"{row['id']}: historical trade leaked"
            )

    topology_counts = Counter(
        c["topology"] for c in selected
    )
    mix_counts = Counter(
        c["asset_mix"] for c in selected
    )
    band_counts = Counter(
        c["disagreement_band"] for c in selected
    )

    distinct_players = {
        asset["id"]
        for c in selected
        for asset in c["side_a"] + c["side_b"]
        if asset["kind"] == "player"
    }
    distinct_picks = {
        asset["id"]
        for c in selected
        for asset in c["side_a"] + c["side_b"]
        if asset["kind"] == "pick"
    }

    appearances = sorted(appearance.values())

    doc = {
        "schema_version": 1,
        "study_id":
            "package-adjustment-v3-ktc-style",
        "phase": "3B",
        "status":
            "frozen_unreleased_fresh_confirmation_catalog",
        "frozen": True,
        "released": False,
        "voting_activated": False,
        "research_only": True,
        "consumer_changed": False,
        "production_formula_enabled": False,
        "production_revision_retained":
            "v1.6-v5-size2-composition-overlay",
        "vote_namespace_reserved": "__pkgv3c1__",
        "old_900_vote_dataset_read": False,
        "human_vote_outcomes_read": False,
        "candidate_family_fingerprint_sha256":
            prereg[
                "candidate_family_fingerprint_sha256"
            ],
        "preregistration_git_blob":
            git_blob(PREREG),
        "catalog_design": {
            "research_cell_count": 24,
            "challenges_per_cell": 10,
            "challenge_count": 240,
            "selection_based_on_frozen_candidate_disagreement":
                True,
            "values_hidden_from_future_voter_ui":
                True,
            "candidate_predictions_hidden_from_future_voter_ui":
                True,
            "display_side_randomization_required_at_activation":
                True,
        },
        "catalog_diagnostics": {
            "challenge_count": 240,
            "research_cell_count": 24,
            "research_cell_counts":
                dict(sorted(by_cell.items())),
            "topology_counts":
                dict(sorted(topology_counts.items())),
            "asset_mix_counts":
                dict(sorted(mix_counts.items())),
            "disagreement_band_counts":
                dict(sorted(band_counts.items())),
            "distinct_player_assets":
                len(distinct_players),
            "distinct_pick_assets":
                len(distinct_picks),
            "max_asset_appearance_count":
                max(appearances),
            "median_asset_appearance_count":
                appearances[
                    len(appearances) // 2
                ],
            "known_ktc_examples_in_selected_catalog":
                0,
            "historical_trade_matches_in_selected_catalog":
                0,
            "known_ktc_search_exclusions":
                ktc_exclusions,
            "historical_trade_search_exclusions":
                historical_exclusions,
            "search_attempts_by_topology_asset_mix":
                dict(sorted(
                    attempts_by_group.items()
                )),
            "candidate_pool_sizes_by_cell": {
                cell: len(cell_candidates[cell])
                for cell in sorted(
                    expected_cells
                )
            },
            "targeted_1v3_boundary_search":
                targeted_1v3_diagnostics,
        },
        "challenges": selected,
    }

    OUT.write_text(
        json.dumps(
            doc, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Package Adjustment V3 — Phase 3B Fresh Confirmation Catalog",
        "",
        "**Status:** `frozen_unreleased_fresh_confirmation_catalog`",
        "",
        "**Voting is NOT activated. Production remains V1.6.**",
        "",
        "- Challenges: **240**",
        "- Research cells: **24**",
        "- Challenges per cell: **10**",
        f"- Distinct player assets: **{len(distinct_players)}**",
        f"- Distinct pick assets: **{len(distinct_picks)}**",
        f"- Maximum asset appearances: **{max(appearances)}**",
        "",
        "## Coverage",
        "",
        "- Every topology has 40 challenges.",
        "- Players-only: 120.",
        "- Includes picks: 120.",
        "- g2.01-vs-g2.15 disagreement: 120.",
        "- g2.15-vs-g2.30 disagreement: 120.",
        "",
        "The five development KTC examples and eight known completed league trades are excluded.",
        "",
        "No old package-vote row, human outcome, or spent 900-vote evidence was read.",
        "",
        "Next: separate voting activation with a new valid-after cutoff.",
        "",
    ]
    OUT_MD.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    manifest_out = {
        "schema_version": 1,
        "study_id": doc["study_id"],
        "phase": "3B",
        "status": doc["status"],
        "catalog_generated": True,
        "voting_activated": False,
        "production_change_authorized": False,
        "old_900_vote_dataset_read": False,
        "human_vote_outcomes_read": False,
        "repo_commit_sha_evaluated":
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
            ).strip(),
        "catalog_sha256": sha256(OUT),
        "catalog_md_sha256": sha256(OUT_MD),
        "catalog_fingerprint_sha256":
            canonical_hash(
                {
                    "challenge_ids": [
                        c["id"]
                        for c in selected
                    ],
                    "research_cell_counts":
                        dict(sorted(
                            by_cell.items()
                        )),
                    "candidate_family_fingerprint_sha256":
                        doc[
                            "candidate_family_fingerprint_sha256"
                        ],
                }
            ),
        "source_git_blobs": {
            "phase3_confirmation_preregistration.json":
                git_blob(PREREG),
            "phase3_confirmation_preregistration_manifest.json":
                git_blob(PREREG_MANIFEST),
            "package_adjustment_v3_phase2.py":
                git_blob(PHASE2_SCRIPT),
            "index.html": git_blob(INDEX),
            "data/league_rosters.json":
                git_blob(ROSTERS),
            "data/trade_history.json":
                git_blob(TRADE_HISTORY),
            "generator":
                git_blob(
                    Path(__file__).resolve()
                ),
        },
    }
    OUT_MANIFEST.write_text(
        json.dumps(
            manifest_out,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": doc["status"],
                "challenge_count": 240,
                "research_cell_count": 24,
                "topology_counts":
                    dict(sorted(
                        topology_counts.items()
                    )),
                "asset_mix_counts":
                    dict(sorted(
                        mix_counts.items()
                    )),
                "band_counts":
                    dict(sorted(
                        band_counts.items()
                    )),
                "distinct_player_assets":
                    len(distinct_players),
                "distinct_pick_assets":
                    len(distinct_picks),
                "max_asset_appearance_count":
                    max(appearances),
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(
        required=True
    )
    group.add_argument(
        "--selftest", action="store_true"
    )
    group.add_argument(
        "--generate", action="store_true"
    )
    args = parser.parse_args()

    if args.selftest:
        selftest()
    else:
        generate()


if __name__ == "__main__":
    main()

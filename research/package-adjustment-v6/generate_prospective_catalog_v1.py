#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "research/package-adjustment-v6"

PREREG = D / "prospective_preregistration_v1.json"
DEV_CATALOG = D / "package_vote_challenges_v6.json"
VALUES = ROOT / "scripts/artifacts/generated/value_uncertainty.json"
ROSTERS = ROOT / "data/league_rosters.json"

SNAPSHOT = D / "prospective_source_fv_snapshot_v1.json"
OUT = D / "package_vote_challenges_v6_prospective_v1.json"
MANIFEST = D / "prospective_catalog_freeze_manifest_v1.json"

TARGET_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
TARGET_ANCHOR_RANKS = (2, 8, 16)
NEAREST_POOL = 28
MAX_RATIO_ERROR = 0.035
MAX_PACKAGE_SHARE_ERROR = 0.040
MAX_PLAYER_APPEARANCE_SOFT = 22
GENERATION_SALT = "pkgv6p1-catalog-v1|20260921"

POS_MAP = {
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K",
    "DL": "DL", "DE": "DL", "DT": "DL",
    "LB": "LB", "OLB": "LB", "ILB": "LB",
    "DB": "DB", "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB",
}

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical_json_sha256(obj) -> str:
    b = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(b).hexdigest()

def normalize_name(value) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def slug(value) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_name(value)).strip("_")

def normalize_pos(value):
    return POS_MAP.get(str(value or "").upper())

def finite(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def player_universe():
    values_doc = read_json(VALUES)
    rosters_doc = read_json(ROSTERS)

    value_index = {}
    for name, row in (values_doc.get("players") or {}).items():
        fv = finite(row.get("center_value"))
        pos = normalize_pos(row.get("pos"))
        if fv is None or fv <= 0 or not pos or pos == "K":
            continue
        value_index[normalize_name(name)] = {
            "fv": float(fv),
            "pos": pos,
        }

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

    players = sorted(
        rostered.values(),
        key=lambda p: (-float(p["fv"]), p["key"]),
    )
    if len(players) < 350:
        raise RuntimeError(f"too few rostered valued players: {len(players)}")
    return players

def freeze_source_snapshot(players, prereg, development_targets):
    payload = {
        "schema_version": 1,
        "status": "frozen_v6p1_prospective_source_fv_snapshot",
        "frozen": True,
        "research_only": True,
        "production_change_authorized": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "preregistration_git_blob_sha": (
            "d0000c9f42c7be11a8d49d0029993a28fabebc73"
        ),
        "preregistration_sha256": sha256(PREREG),
        "value_uncertainty_sha256": sha256(VALUES),
        "league_rosters_sha256": sha256(ROSTERS),
        "development_target_keys_excluded": sorted(development_targets),
        "player_count": len(players),
        "players": players,
    }
    SNAPSHOT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload

def nearest_candidates(players, desired, target_fv, target_key):
    allowed = [
        p for p in players
        if p["key"] != target_key and float(p["fv"]) < target_fv
    ]
    allowed.sort(
        key=lambda p: (
            abs(float(p["fv"]) - desired),
            hashlib.sha256(
                (GENERATION_SALT + "|pkg|" + p["key"]).encode()
            ).hexdigest(),
            p["key"],
        )
    )
    return allowed[:NEAREST_POOL]

def construct_package(anchor, players, shares, apex_level, appearance_counts):
    target_fv = float(anchor["fv"])
    top_share = float(shares[0])
    ratio_target = float(apex_level) / top_share
    total_goal = target_fv * ratio_target
    desired = [total_goal * float(s) for s in shares]

    pools = [
        nearest_candidates(players, d, target_fv, anchor["key"])
        for d in desired
    ]
    if any(len(pool) < 4 for pool in pools):
        return None

    best = None
    for triple in itertools.product(*pools):
        keys = [p["key"] for p in triple]
        if len(set(keys)) != 3:
            continue

        vals = [float(p["fv"]) for p in triple]
        if not (vals[0] >= vals[1] >= vals[2]):
            continue
        if any(v >= target_fv for v in vals):
            continue

        total = sum(vals)
        ratio = total / target_fv
        ratio_err = abs(ratio - ratio_target)
        if ratio_err > MAX_RATIO_ERROR:
            continue

        actual_shares = [v / total for v in vals]
        share_errs = [
            abs(actual_shares[i] - float(shares[i]))
            for i in range(3)
        ]
        if max(share_errs) > MAX_PACKAGE_SHARE_ERROR:
            continue

        reuse_penalty = sum(
            max(
                0,
                appearance_counts[p["key"]] - MAX_PLAYER_APPEARANCE_SOFT,
            )
            for p in triple
        )

        signature = "|".join(sorted(keys))
        deterministic_tie = hashlib.sha256(
            (
                GENERATION_SALT
                + "|"
                + anchor["key"]
                + "|"
                + signature
            ).encode()
        ).hexdigest()

        score = (
            ratio_err,
            max(share_errs),
            sum(share_errs),
            reuse_penalty,
            deterministic_tie,
            tuple(keys),
        )
        if best is None or score < best[0]:
            best = (score, list(triple))

    return None if best is None else best[1]

def challenge_record(anchor, package, profile, apex_level, target_rank):
    target_fv = float(anchor["fv"])
    package_fv = sum(float(p["fv"]) for p in package)
    ratio = package_fv / target_fv
    vals = [float(p["fv"]) for p in package]
    actual_shares = [v / package_fv for v in vals]
    hhi = sum(s * s for s in actual_shares)
    phi = 1.0 - hhi

    expected_ratio = float(apex_level) / float(profile["shares"][0])
    profile_code = profile["label"].replace("/", "_")
    apex_code = int(round(float(apex_level) * 100))

    cid = (
        f"pkgv6p1_{anchor['pos'].lower()}_{slug(anchor['name'])}_"
        f"{profile_code}_a{apex_code}"
    )

    return {
        "id": cid,
        "schema_version": 1,
        "experiment": (
            "package_adjustment_v6_fresh_prospective_confirmation"
        ),
        "research_cell": (
            f"{profile['label']}|apex_{apex_level:.2f}"
        ),
        "target_rank_within_position": int(target_rank),
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
        "ratio_target": round(expected_ratio, 9),
        "apex_piece_to_target_target": float(apex_level),
        "component_profile": {
            "label": profile["label"],
            "intended_package_shares": [
                float(x) for x in profile["shares"]
            ],
            "intended_hhi": float(profile["hhi"]),
            "intended_phi": float(profile["phi"]),
            "actual_package_shares": [
                round(x, 6) for x in actual_shares
            ],
            "actual_piece_to_target_shares": [
                round(v / target_fv, 6) for v in vals
            ],
            "actual_hhi": round(hhi, 9),
            "actual_phi": round(phi, 9),
            "largest_piece_to_target": round(
                max(vals) / target_fv, 6
            ),
        },
    }

def trade_signature(challenge):
    return (
        challenge["target"]["key"],
        tuple(sorted(p["key"] for p in challenge["package"])),
    )

def build_catalog(players, prereg, dev_catalog):
    contract = prereg["fresh_prospective_catalog_contract"]

    labels = contract["composition_profiles"]
    profile_map = {
        "45/33/22": [0.45, 0.33, 0.22],
        "50/30/20": [0.50, 0.30, 0.20],
        "50/25/25": [0.50, 0.25, 0.25],
        "55/30/15": [0.55, 0.30, 0.15],
        "60/25/15": [0.60, 0.25, 0.15],
        "60/20/20": [0.60, 0.20, 0.20],
    }
    profiles = []
    for label in labels:
        shares = profile_map[label]
        hhi = sum(s * s for s in shares)
        profiles.append({
            "label": label,
            "shares": shares,
            "hhi": hhi,
            "phi": 1.0 - hhi,
        })

    apex_levels = [
        float(x) for x in contract["apex_target_levels"]
    ]
    assert len(profiles) == 6
    assert len(apex_levels) == 4

    development_targets = {
        c["target"]["key"] for c in dev_catalog["challenges"]
    }
    development_signatures = {
        trade_signature(c) for c in dev_catalog["challenges"]
    }
    assert len(development_targets) == 21

    by_pos = {
        pos: [p for p in players if p["pos"] == pos]
        for pos in TARGET_POSITIONS
    }

    appearance_counts = Counter()
    selected_targets = []
    challenges = []
    used_target_keys = set()

    # Three fresh targets per position. Each slot has a deterministic
    # rank anchor; candidates are searched by distance from that anchor.
    # Development targets are excluded entirely, making prospective
    # target identity fresh in addition to exact trade-signature freshness.
    for pos in TARGET_POSITIONS:
        pool = by_pos[pos]
        if len(pool) < 20:
            raise RuntimeError(
                f"insufficient {pos} player pool for fresh target search: "
                f"{len(pool)}"
            )

        for slot_index, anchor_rank in enumerate(TARGET_ANCHOR_RANKS):
            candidates = [
                (rank, p)
                for rank, p in enumerate(pool[:40])
                if p["key"] not in development_targets
                and p["key"] not in used_target_keys
            ]
            candidates.sort(
                key=lambda rp: (
                    abs(rp[0] - anchor_rank),
                    rp[0],
                    hashlib.sha256(
                        (
                            GENERATION_SALT
                            + "|target|"
                            + pos
                            + "|"
                            + str(slot_index)
                            + "|"
                            + rp[1]["key"]
                        ).encode()
                    ).hexdigest(),
                    rp[1]["key"],
                )
            )

            chosen = None
            for rank, anchor in candidates:
                local_appearance = Counter(appearance_counts)
                cell_rows = []
                ok = True

                for profile in profiles:
                    for apex in apex_levels:
                        pkg = construct_package(
                            anchor,
                            players,
                            profile["shares"],
                            apex,
                            local_appearance,
                        )
                        if pkg is None:
                            ok = False
                            break

                        row = challenge_record(
                            anchor,
                            pkg,
                            profile,
                            apex,
                            rank,
                        )
                        if trade_signature(row) in development_signatures:
                            ok = False
                            break

                        cell_rows.append(row)
                        for p in pkg:
                            local_appearance[p["key"]] += 1

                    if not ok:
                        break

                if ok and len(cell_rows) == 24:
                    chosen = (
                        rank,
                        anchor,
                        cell_rows,
                        local_appearance,
                    )
                    break

            if chosen is None:
                raise RuntimeError(
                    f"no fresh fully constructible target for "
                    f"{pos} slot {slot_index} near rank {anchor_rank}"
                )

            rank, anchor, cell_rows, appearance_counts = chosen
            used_target_keys.add(anchor["key"])
            selected_targets.append({
                "key": anchor["key"],
                "name": anchor["name"],
                "pos": pos,
                "rank_within_position": int(rank),
                "selection_slot": int(slot_index),
                "selection_anchor_rank": int(anchor_rank),
                "fv": float(anchor["fv"]),
            })
            challenges.extend(cell_rows)

    assert len(selected_targets) == 21
    assert len(challenges) == 504

    # Full frozen validation.
    ids = [c["id"] for c in challenges]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate prospective challenge IDs")

    signatures = [trade_signature(c) for c in challenges]
    if len(signatures) != len(set(signatures)):
        raise RuntimeError("duplicate prospective trade signatures")

    overlap = set(signatures) & development_signatures
    if overlap:
        raise RuntimeError(
            f"development trade signatures leaked: {len(overlap)}"
        )

    prospective_target_keys = {
        c["target"]["key"] for c in challenges
    }
    target_overlap = prospective_target_keys & development_targets
    if target_overlap:
        raise RuntimeError(
            "development targets leaked into fresh catalog: "
            + repr(sorted(target_overlap))
        )

    expected_cells = {
        f"{p['label']}|apex_{a:.2f}"
        for p in profiles
        for a in apex_levels
    }
    by_cell = defaultdict(list)
    by_target = defaultdict(list)

    for c in challenges:
        by_cell[c["research_cell"]].append(c)
        by_target[c["target"]["key"]].append(c)

        if c["package_size"] != 3 or len(c["package"]) != 3:
            raise RuntimeError(
                f"{c['id']}: not exact 1-vs-3"
            )
        if any(
            float(p["fv"]) >= float(c["target_fv"])
            for p in c["package"]
        ):
            raise RuntimeError(
                f"{c['id']}: package piece >= target FV"
            )

        ratio_err = abs(
            float(c["raw_package_to_target_ratio"])
            - float(c["ratio_target"])
        )
        if ratio_err > MAX_RATIO_ERROR + 1e-12:
            raise RuntimeError(
                f"{c['id']}: ratio outside tolerance"
            )

        intended = c["component_profile"][
            "intended_package_shares"
        ]
        actual = c["component_profile"][
            "actual_package_shares"
        ]
        if max(
            abs(float(a) - float(b))
            for a, b in zip(actual, intended)
        ) > MAX_PACKAGE_SHARE_ERROR + 1e-12:
            raise RuntimeError(
                f"{c['id']}: composition outside tolerance"
            )

    if set(by_cell) != expected_cells:
        raise RuntimeError("prospective 24-cell set mismatch")
    if any(len(v) != 21 for v in by_cell.values()):
        raise RuntimeError(
            "every prospective cell must contain all 21 targets"
        )
    if any(
        {x["research_cell"] for x in v} != expected_cells
        for v in by_target.values()
    ):
        raise RuntimeError(
            "every prospective target must cover all 24 cells"
        )

    positions = {
        c["target"]["pos"] for c in challenges
    }
    if positions != set(TARGET_POSITIONS):
        raise RuntimeError(
            f"prospective target positions mismatch: {positions}"
        )

    # Candidate formula is allowed only here as a post-generation
    # finite-value validation. It does not rank/select/retain challenges.
    q = float(prereg["candidate"]["q"])
    for c in challenges:
        v = [
            float(p["fv"]) for p in c["package"]
        ]
        c2_score = sum(x ** q for x in v) ** (1.0 / q)
        if not math.isfinite(c2_score) or c2_score <= 0:
            raise RuntimeError(
                f"{c['id']}: invalid C2 numerical score"
            )

    return {
        "profiles": profiles,
        "apex_levels": apex_levels,
        "development_targets": development_targets,
        "selected_targets": selected_targets,
        "challenges": challenges,
        "appearance_counts": appearance_counts,
        "by_cell": by_cell,
        "by_target": by_target,
    }

def main():
    prereg = read_json(PREREG)
    dev_catalog = read_json(DEV_CATALOG)

    assert prereg["status"] == "frozen_v6_prospective_preregistration"
    assert prereg["frozen"] is True
    assert prereg["fresh_prospective_catalog_contract"][
        "required_cell_count"
    ] == 24
    assert prereg["fresh_prospective_catalog_contract"][
        "minimum_fresh_target_count"
    ] == 21

    players = player_universe()

    # Build twice before writing outputs to prove deterministic selection.
    a = build_catalog(players, prereg, dev_catalog)
    b = build_catalog(players, prereg, dev_catalog)
    if canonical_json_sha256(a["selected_targets"]) != \
       canonical_json_sha256(b["selected_targets"]):
        raise RuntimeError("target selection is not deterministic")
    if canonical_json_sha256(a["challenges"]) != \
       canonical_json_sha256(b["challenges"]):
        raise RuntimeError("challenge selection is not deterministic")

    freeze_source_snapshot(
        players,
        prereg,
        a["development_targets"],
    )

    profile_counts = Counter(
        c["component_profile"]["label"]
        for c in a["challenges"]
    )
    apex_counts = Counter(
        f"{float(c['apex_piece_to_target_target']):.2f}"
        for c in a["challenges"]
    )
    position_counts = Counter(
        c["target"]["pos"] for c in a["challenges"]
    )
    cell_counts = Counter(
        c["research_cell"] for c in a["challenges"]
    )
    ratio_errors = [
        abs(
            float(c["raw_package_to_target_ratio"])
            - float(c["ratio_target"])
        )
        for c in a["challenges"]
    ]
    share_errors = [
        max(
            abs(float(x) - float(y))
            for x, y in zip(
                c["component_profile"][
                    "actual_package_shares"
                ],
                c["component_profile"][
                    "intended_package_shares"
                ],
            )
        )
        for c in a["challenges"]
    ]

    generated = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": 1,
        "status": "frozen_v6p1_prospective_catalog",
        "frozen": True,
        "released": False,
        "voting_activated": False,
        "research_only": True,
        "production_change_authorized": False,
        "production_revision_retained": (
            "v1.6-v5-size2-composition-overlay"
        ),
        "generated_at_utc": generated,
        "catalog_id": (
            "package-adjustment-v6-prospective-catalog-v1"
        ),
        "purpose": (
            "Fresh independent one-vs-three player-only prospective "
            "confirmation catalog for frozen V6 C2 versus frozen C1."
        ),
        "candidate_predictions_used_for_catalog_selection": False,
        "development_vote_outcomes_read": False,
        "prospective_vote_outcomes_read": False,
        "development_target_reuse_count": 0,
        "development_trade_signature_overlap_count": 0,
        "source_sha256": {
            "prospective_preregistration": sha256(PREREG),
            "development_catalog": sha256(DEV_CATALOG),
            "source_fv_snapshot": sha256(SNAPSHOT),
            "value_uncertainty": sha256(VALUES),
            "league_rosters": sha256(ROSTERS),
            "generator": sha256(Path(__file__)),
        },
        "design": {
            "generation_salt": GENERATION_SALT,
            "target_positions": list(TARGET_POSITIONS),
            "target_anchor_ranks": list(TARGET_ANCHOR_RANKS),
            "fresh_targets_per_position": 3,
            "composition_profiles": a["profiles"],
            "apex_piece_to_target_levels": a["apex_levels"],
            "cell_count": 24,
            "target_count": 21,
            "challenge_count": 504,
            "max_ratio_error": MAX_RATIO_ERROR,
            "max_package_share_error": (
                MAX_PACKAGE_SHARE_ERROR
            ),
            "candidate_blind_selection": True,
            "development_targets_excluded_entirely": True,
        },
        "targets": a["selected_targets"],
        "challenges": a["challenges"],
        "catalog_diagnostics": {
            "challenge_count": 504,
            "target_count": 21,
            "research_cell_count": 24,
            "expected_challenges_per_cell": 21,
            "profile_counts": dict(
                sorted(profile_counts.items())
            ),
            "apex_counts": dict(
                sorted(apex_counts.items())
            ),
            "target_position_counts": dict(
                sorted(position_counts.items())
            ),
            "research_cell_counts": dict(
                sorted(cell_counts.items())
            ),
            "max_abs_ratio_error": max(ratio_errors),
            "max_abs_package_share_error": max(share_errors),
            "max_package_player_appearance_count": max(
                a["appearance_counts"].values()
            ),
            "development_target_overlap_count": 0,
            "development_trade_signature_overlap_count": 0,
            "candidate_formula_post_generation_numeric_validation_only": True,
        },
    }

    OUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "status": "frozen_v6p1_prospective_catalog_manifest",
        "frozen": True,
        "research_only": True,
        "generated_at_utc": generated,
        "production_change_authorized": False,
        "production_revision_retained": (
            "v1.6-v5-size2-composition-overlay"
        ),
        "preregistration_git_blob_sha": (
            "d0000c9f42c7be11a8d49d0029993a28fabebc73"
        ),
        "preregistration_sha256": sha256(PREREG),
        "development_catalog_sha256": sha256(DEV_CATALOG),
        "source_fv_snapshot_sha256": sha256(SNAPSHOT),
        "generator_sha256": sha256(Path(__file__)),
        "catalog_sha256": sha256(OUT),
        "challenge_count": 504,
        "target_count": 21,
        "research_cell_count": 24,
        "development_target_overlap_count": 0,
        "development_trade_signature_overlap_count": 0,
        "candidate_predictions_used_for_selection": False,
        "development_vote_outcomes_read": False,
        "prospective_vote_outcomes_read": False,
        "released": False,
        "voting_activated": False,
        "model_evaluation_performed": False,
        "prospective_votes_collected": False,
        "next_action": (
            "Validate the frozen V6P1 catalog and then activate the "
            "separate V6P1 transport/sampler in a later workflow."
        ),
    }

    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "PASS: frozen V6P1 catalog generated with "
        "504 challenges, 21 entirely fresh targets, and 24 cells."
    )
    print("Catalog SHA256:", manifest["catalog_sha256"])

if __name__ == "__main__":
    main()

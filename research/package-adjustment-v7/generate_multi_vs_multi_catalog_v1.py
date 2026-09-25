#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "research" / "package-adjustment-v7"

PHASE1 = D / "phase1_multi_vs_multi_preregistration_v1.json"
PHASE1_MAN = D / "phase1_multi_vs_multi_preregistration_manifest_v1.json"
V6_DEV = ROOT / "research/package-adjustment-v6/development_candidate_v1.json"
V6_PROS = ROOT / "research/package-adjustment-v6/prospective_evaluation_v1.json"
VALUES = ROOT / "scripts/artifacts/generated/value_uncertainty.json"
ROSTERS = ROOT / "data/league_rosters.json"
INDEX = ROOT / "index.html"
SNAPSHOT_VALUES = ROOT / "scripts/validation/snapshot_values.py"

OUT_SNAPSHOT = D / "phase1a_player_fv_snapshot_v1.json"
OUT_POWER = D / "phase1a_power_analysis_v1.json"
OUT_CATALOG = D / "package_vote_challenges_v7_development_v1.json"
OUT_SUMMARY = D / "phase1a_power_and_catalog_v1.md"
OUT_MANIFEST = D / "phase1a_power_and_catalog_manifest_v1.json"

SCHEMA = 1
STUDY_ID = "package-adjustment-v7-multi-v-multi"
STATUS = "FROZEN_PRE_VOTE_POWER_AND_CATALOG"
DECISION = "FREEZE_V7_PHASE1A_AT_40_VOTER_FIRST_CHECKPOINT"

POSITIONS = ("QB","RB","WR","TE","DL","LB","DB")
POS_MAP = {
    "QB":"QB","RB":"RB","WR":"WR","TE":"TE",
    "DL":"DL","DE":"DL","DT":"DL",
    "LB":"LB","OLB":"LB","ILB":"LB",
    "DB":"DB","CB":"DB","S":"DB","SS":"DB","FS":"DB",
}
PROFILES = {
    2: ((0.50,0.50),(0.60,0.40),(0.70,0.30),(0.80,0.20)),
    3: ((0.34,0.33,0.33),(0.45,0.33,0.22),(0.55,0.30,0.15),(0.65,0.20,0.15)),
    4: ((0.25,0.25,0.25,0.25),(0.35,0.28,0.22,0.15),(0.45,0.25,0.18,0.12),(0.55,0.18,0.15,0.12)),
}
DESIGN = {
    "2v2": ("A_low","B_low","A_moderate","B_moderate","A_high","B_high"),
    "2v3": ("A_high","A_high","B_high","A_moderate","B_moderate","A_low","B_low","B_low"),
    "2v4": ("A_high","A_high","A_moderate","B_moderate","A_low","B_low"),
    "3v3": ("A_low","B_low","A_moderate","B_moderate","A_high","B_high"),
    "3v4": ("A_high","B_high","B_high","A_moderate","B_moderate","A_low","B_low","B_low"),
    "4v4": ("A_low","B_low","A_moderate","B_moderate","A_high","B_high"),
}
BAND_TARGET = {"low":0.035,"moderate":0.085,"high":0.16}
BAND_RANGE = {"low":(0.012,0.060),"moderate":(0.050,0.120),"high":(0.100,0.300)}

MOTIVATING_PLAYERS = frozenset({
    "jacob rodriguez","abdul carter","sam darnold",
    "kyler murray","jamien sherwood","marvin harrison",
})

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical_sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode()
    ).hexdigest()

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def norm(value) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def finite(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def load_snapshot_module():
    spec = importlib.util.spec_from_file_location("snapshot_values_v7", SNAPSHOT_VALUES)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

def player_universe():
    snapmod = load_snapshot_module()
    cfg = snapmod.load_from_html(INDEX)
    live = snapmod.compute_all_values(cfg)
    vu = read_json(VALUES)
    roster = read_json(ROSTERS)

    vu_idx = {}
    for raw_name, row in (vu.get("players") or {}).items():
        key = norm(raw_name)
        val = finite(row.get("center_value"))
        pos = POS_MAP.get(str(row.get("pos") or "").upper())
        if val is not None and val > 0 and pos in POSITIONS:
            vu_idx[key] = {"fv": int(round(val)), "pos": pos}

    players = {}
    mismatches = []
    for team in roster.get("rosters") or []:
        for slot in ("starters","bench","taxi","reserve_ir"):
            for raw in team.get(slot) or []:
                key = norm(raw.get("name"))
                if key not in live or key not in vu_idx:
                    continue
                live_val = int(live[key]["value"])
                vu_val = int(vu_idx[key]["fv"])
                if live_val != vu_val:
                    mismatches.append((key, live_val, vu_val))
                    continue
                pos = POS_MAP.get(str(live[key]["pos"]).upper())
                if pos not in POSITIONS:
                    continue
                players[key] = {
                    "key": key,
                    "name": str(raw.get("name") or key),
                    "pos": pos,
                    "fv": live_val,
                    "team": raw.get("team"),
                    "age": raw.get("age"),
                }
    if mismatches:
        raise RuntimeError(f"value_uncertainty/live FV mismatch examples={mismatches[:10]}")
    out = sorted(players.values(), key=lambda p: (-p["fv"], p["key"]))
    if len(out) < 350:
        raise RuntimeError(f"too few frozen rostered players: {len(out)}")
    counts = Counter(p["pos"] for p in out)
    if any(counts[p] < 20 for p in POSITIONS):
        raise RuntimeError(f"insufficient position coverage: {dict(counts)}")
    return out, dict(sorted(counts.items()))

def nearest_players(players_asc, desired, used, limit=10):
    # deterministic O(n) ranking over only 472-ish players; simple and auditable
    pool = [p for p in players_asc if p["key"] not in used]
    pool.sort(key=lambda p: (abs(float(p["fv"]) - desired), p["key"]))
    return pool[:limit]

def side_key(players):
    return "|".join(sorted(p["key"] for p in players))

def build_side_pool(players, size):
    players_asc = sorted(players, key=lambda p: (p["fv"], p["key"]))
    out = {}
    for anchor in players_asc:
        for profile in PROFILES[size]:
            total_goal = float(anchor["fv"]) / float(profile[0])
            for variant in range(4):
                chosen = [anchor]
                used = {anchor["key"]}
                ok = True
                for i in range(1, size):
                    pool = nearest_players(
                        players_asc, total_goal * float(profile[i]), used, limit=10
                    )
                    if not pool:
                        ok = False
                        break
                    pick = pool[(variant + i * 2) % len(pool)]
                    chosen.append(pick)
                    used.add(pick["key"])
                if not ok or len(chosen) != size:
                    continue
                total = sum(float(p["fv"]) for p in chosen)
                shares = sorted((float(p["fv"]) / total for p in chosen), reverse=True)
                if min(shares) < 0.10 - 1e-12:
                    continue
                key = side_key(chosen)
                if key in out:
                    continue
                out[key] = {
                    "players": chosen,
                    "sum": total,
                    "top_share": shares[0],
                    "hhi": sum(s*s for s in shares),
                    "key": key,
                }
    rows = list(out.values())
    rows.sort(key=lambda s: (s["sum"], s["key"]))
    if len(rows) < 500:
        raise RuntimeError(f"side pool too small for size {size}: {len(rows)}")
    return rows

def lower_bound_sum(rows, target):
    lo, hi = 0, len(rows)
    while lo < hi:
        mid = (lo + hi) // 2
        if rows[mid]["sum"] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo

def overlaps(a, b):
    aa = {p["key"] for p in a["players"]}
    return any(p["key"] in aa for p in b["players"])

def in_band(diff, band):
    lo, hi = BAND_RANGE[band]
    x = abs(float(diff))
    return x >= lo - 1e-12 and x <= hi + 1e-12

def slot_plan():
    slots = []
    idx = 0
    for topology, cells in DESIGN.items():
        a_size, b_size = [int(x) for x in topology.split("v")]
        for cell in cells:
            direction, band = cell.split("_", 1)
            slots.append({
                "design_index": idx,
                "topology": topology,
                "a_size": a_size,
                "b_size": b_size,
                "direction": direction,
                "band": band,
            })
            idx += 1
    assert len(slots) == 40
    # Rare 2v4 B-moderate first; preserve original design_index for output ordering.
    return sorted(
        slots,
        key=lambda s: (
            0 if (s["topology"]=="2v4" and s["direction"]=="B" and s["band"]=="moderate") else
            1 if (s["topology"]=="2v4" and s["direction"]=="B") else
            2,
            s["design_index"],
        )
    )

def choose_catalog(players):
    side_pools = {n: build_side_pool(players, n) for n in (2,3,4)}
    appearance = Counter()
    pos_coverage = Counter()
    used_pairs = set()
    selected = []

    for slot in slot_plan():
        A_pool = side_pools[slot["a_size"]]
        B_pool = side_pools[slot["b_size"]]
        best = None

        for A in A_pool:
            if any(appearance[p["key"]] >= 4 for p in A["players"]):
                continue
            center = lower_bound_sum(B_pool, A["sum"])
            lo = max(0, center - 150)
            hi = min(len(B_pool), center + 151)

            for B in B_pool[lo:hi]:
                if any(appearance[p["key"]] >= 4 for p in B["players"]):
                    continue
                if overlaps(A, B):
                    continue
                pair_key = A["key"] + "||" + B["key"]
                if pair_key in used_pairs:
                    continue

                raw_ratio = min(A["sum"], B["sum"]) / max(A["sum"], B["sum"])
                if raw_ratio < 0.92 - 1e-12:
                    continue

                diff = A["top_share"] - B["top_share"]
                if slot["direction"] == "A" and diff <= 0:
                    continue
                if slot["direction"] == "B" and diff >= 0:
                    continue
                if not in_band(diff, slot["band"]):
                    continue

                all_players = A["players"] + B["players"]
                poses = {p["pos"] for p in all_players}
                deficit_cover = sum(1 for p in poses if pos_coverage[p] < 6)
                max_app = max(appearance[p["key"]] for p in all_players)
                reuse = sum(appearance[p["key"]] for p in all_players)

                score = (
                    -deficit_cover,
                    max_app,
                    reuse,
                    abs(abs(diff) - BAND_TARGET[slot["band"]]),
                    abs(raw_ratio - 0.97),
                    pair_key,
                )
                if best is None or score < best[0]:
                    best = (score, A, B, raw_ratio, diff, pair_key)

        if best is None:
            raise RuntimeError(f"could not construct frozen design slot: {slot}")

        _, A, B, raw_ratio, diff, pair_key = best
        used_pairs.add(pair_key)
        for p in A["players"] + B["players"]:
            appearance[p["key"]] += 1
        for p in {x["pos"] for x in A["players"] + B["players"]}:
            pos_coverage[p] += 1

        selected.append({
            **slot,
            "A": A,
            "B": B,
            "raw_ratio": raw_ratio,
            "top_share_diff_A_minus_B": diff,
        })

    selected.sort(key=lambda x: x["design_index"])
    return selected, side_pools, appearance, pos_coverage

def asset_record(p):
    return {
        "key": p["key"], "name": p["name"], "pos": p["pos"],
        "team": p.get("team"), "age": p.get("age"), "fv": int(p["fv"]),
    }

def challenge_record(i, row):
    A, B = row["A"], row["B"]
    all_names = {p["key"] for p in A["players"] + B["players"]}
    if all_names == MOTIVATING_PLAYERS:
        raise RuntimeError("motivating trade player-only shadow leaked into development catalog")
    cid = f"pkgv7dev_{i:03d}"
    def side(s):
        total = float(s["sum"])
        return {
            "assets": [asset_record(p) for p in s["players"]],
            "asset_count": len(s["players"]),
            "raw_fv": int(round(total)),
            "top_asset_share": round(float(s["top_share"]), 9),
            "hhi": round(float(s["hhi"]), 9),
            "minimum_asset_share": round(min(float(p["fv"])/total for p in s["players"]), 9),
        }
    return {
        "id": cid,
        "schema_version": 1,
        "experiment": "package_adjustment_v7_multi_vs_multi_development",
        "topology": row["topology"],
        "primary_contrast_band": row["band"],
        "primary_concentration_direction_by_top_share": row["direction"],
        "raw_sum_ratio_min_over_max": round(float(row["raw_ratio"]), 9),
        "top_asset_share_difference_A_minus_B": round(float(row["top_share_diff_A_minus_B"]), 9),
        "side_A": side(A),
        "side_B": side(B),
        "fv_visible_to_voter": False,
        "candidate_prediction_used_for_selection": False,
    }

def validate_catalog(challenges, prereg):
    if len(challenges) != 40:
        raise RuntimeError(f"expected 40 challenges, got {len(challenges)}")
    ids = [c["id"] for c in challenges]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate challenge ids")

    expected_topology = prereg["development_catalog_preregistration"]["topology_counts"]
    got_topology = Counter(c["topology"] for c in challenges)
    if dict(got_topology) != dict(expected_topology):
        raise RuntimeError(f"topology count mismatch {got_topology} vs {expected_topology}")

    dirs = Counter(c["primary_concentration_direction_by_top_share"] for c in challenges)
    if dirs != Counter({"A":20,"B":20}):
        raise RuntimeError(f"direction balance mismatch: {dirs}")

    bands = Counter(c["primary_contrast_band"] for c in challenges)
    if set(bands) != {"low","moderate","high"}:
        raise RuntimeError(f"missing contrast band: {bands}")

    appearance = Counter()
    position_challenges = Counter()
    signatures = set()

    for c in challenges:
        if c["fv_visible_to_voter"] is not False:
            raise RuntimeError(f"{c['id']}: FV visibility leak")
        if c["candidate_prediction_used_for_selection"] is not False:
            raise RuntimeError(f"{c['id']}: candidate-selection leak")

        sides = [c["side_A"], c["side_B"]]
        side_keys = []
        for side in sides:
            if side["asset_count"] not in (2,3,4):
                raise RuntimeError(f"{c['id']}: bad side size")
            keys = [a["key"] for a in side["assets"]]
            if len(keys) != len(set(keys)):
                raise RuntimeError(f"{c['id']}: duplicate within side")
            if min(float(a["fv"]) / float(side["raw_fv"]) for a in side["assets"]) < 0.10 - 0.002:
                raise RuntimeError(f"{c['id']}: primary tiny-piece rule failed")
            side_keys.append(set(keys))
            for a in side["assets"]:
                appearance[a["key"]] += 1
                if a["pos"] not in POSITIONS:
                    raise RuntimeError(f"{c['id']}: unsupported position {a['pos']}")
        if side_keys[0] & side_keys[1]:
            raise RuntimeError(f"{c['id']}: same player on both sides")

        ratio = min(c["side_A"]["raw_fv"], c["side_B"]["raw_fv"]) / max(
            c["side_A"]["raw_fv"], c["side_B"]["raw_fv"]
        )
        if ratio < 0.92 - 0.002:
            raise RuntimeError(f"{c['id']}: raw sum ratio below design floor")

        for pos in set(a["pos"] for s in sides for a in s["assets"]):
            position_challenges[pos] += 1

        sig = (
            tuple(sorted(a["key"] for a in c["side_A"]["assets"])),
            tuple(sorted(a["key"] for a in c["side_B"]["assets"])),
        )
        if sig in signatures:
            raise RuntimeError(f"{c['id']}: duplicate trade signature")
        signatures.add(sig)

    if max(appearance.values()) > 4:
        raise RuntimeError(f"player appearance cap exceeded: {max(appearance.values())}")
    if any(position_challenges[p] < 6 for p in POSITIONS):
        raise RuntimeError(f"position challenge coverage failed: {dict(position_challenges)}")
    return {
        "topology_counts": dict(sorted(got_topology.items())),
        "direction_counts": dict(sorted(dirs.items())),
        "contrast_band_counts": dict(sorted(bands.items())),
        "max_player_appearances": max(appearance.values()),
        "unique_players": len(appearance),
        "position_challenge_counts": dict(sorted(position_challenges.items())),
    }

def normal_power(true_d, se, practical=0.005, z=1.6448536269514722):
    # pass requires point D <= -practical AND one-sided 95% UCB < 0
    threshold = min(-practical, -z * se)
    return NormalDist().cdf((threshold - true_d) / se), threshold

def build_power():
    prereg = read_json(PHASE1)
    dev = read_json(V6_DEV)
    pros = read_json(V6_PROS)
    checkpoints = prereg["mock_vote_transport"]["candidate_checkpoint_voter_counts"]
    target = float(prereg["mock_vote_transport"]["power_target"])
    practical = float(
        prereg["mock_vote_transport"]["minimum_worthwhile_equal_topology_macro_log_loss_improvement"]
    )

    sources = [
        {
            "name":"v6_development_crossed_bootstrap",
            "voters": int(dev["development_evidence"]["distinct_voter_clusters"]),
            "D": float(dev["crossed_cluster_uncertainty"]["point_difference_candidate_minus_C1"]),
            "sd": float(dev["crossed_cluster_uncertainty"]["bootstrap_sd"]),
            "source_sha256": sha256(V6_DEV),
        },
        {
            "name":"v6_prospective_crossed_bootstrap",
            "voters": int(pros["evidence"]["distinct_voter_clusters"]),
            "D": float(pros["primary_confirmation"]["D_overall_C2_minus_C1"]),
            "sd": float(pros["primary_confirmation"]["crossed_cluster_uncertainty"]["bootstrap_sd"]),
            "source_sha256": sha256(V6_PROS),
        },
    ]

    rows = []
    for n in checkpoints:
        src_rows = []
        for src in sources:
            se = src["sd"] * math.sqrt(src["voters"] / float(n))
            p, threshold = normal_power(src["D"], se, practical=practical)
            src_rows.append({
                "source": src["name"],
                "projected_se": se,
                "assumed_true_D": src["D"],
                "joint_primary_gate_threshold_Dhat": threshold,
                "approximate_power": p,
            })
        conservative = min(r["approximate_power"] for r in src_rows)
        rows.append({
            "distinct_voter_checkpoint": int(n),
            "source_projections": src_rows,
            "conservative_power": conservative,
            "passes_target": conservative >= target,
        })

    eligible = [r for r in rows if r["passes_target"]]
    if not eligible:
        selected = None
        decision = "NO_ALLOWED_CHECKPOINT_REACHES_POWER_TARGET"
    else:
        selected = eligible[0]["distinct_voter_checkpoint"]
        decision = "SELECT_FIRST_ALLOWED_CHECKPOINT_MEETING_POWER_TARGET"

    if selected != 40:
        raise RuntimeError(f"preregistered allowed checkpoint resolution changed: selected={selected}")

    return {
        "schema_version":1,
        "study_id":STUDY_ID,
        "stage":"phase1a_pre_vote_power_analysis",
        "status":"FROZEN_PRE_VOTE_POWER",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "method":"conservative normal planning approximation using two independent pre-existing V6 crossed-cluster SD/effect sources; voter-cluster SE scaled by sqrt(N_source/N_target)",
        "planning_only_not_v7_result":True,
        "v7_votes_read":False,
        "power_target":target,
        "minimum_worthwhile_improvement":practical,
        "one_sided_z":1.6448536269514722,
        "checkpoints":rows,
        "selected_first_checkpoint_distinct_voters":selected,
        "coverage_gate_at_or_after_first_checkpoint":{
            "minimum_distinct_voters_total":selected,
            "minimum_distinct_voters_per_challenge":32,
            "reason":"32/40 retains >0.80 conservative prospective-source planning power while allowing partial-session attrition.",
            "if_total_40_reached_without_per_challenge_coverage":"continue outcome-blind collection only until all 40 challenges reach 32 distinct voters or 50 total distinct voters, whichever occurs first",
        },
        "hard_cap_distinct_voters":50,
        "decision":decision,
        "source_inputs":sources,
        "candidate_scores_or_v7_vote_outcomes_used":False,
    }

def render_summary(snapshot, power, catalog):
    d = catalog["diagnostics"]
    p40 = next(x for x in power["checkpoints"] if x["distinct_voter_checkpoint"] == 40)
    p30 = next(x for x in power["checkpoints"] if x["distinct_voter_checkpoint"] == 30)
    return "\n".join([
        "# Package Adjustment V7 Phase 1A — Power + 40-Trade Catalog Freeze",
        "",
        f"**Decision:** `{DECISION}`",
        "",
        "No V7 vote has been collected or read. Production remains unchanged.",
        "",
        "## Power",
        "",
        f"- 30 voters conservative planning power: {p30['conservative_power']:.4f} — below 0.80.",
        f"- 40 voters conservative planning power: {p40['conservative_power']:.4f} — passes.",
        "- 50 voters remains the hard cap, not the primary target.",
        "- First maturity checkpoint: 40 distinct voters.",
        "- Coverage gate: at least 32 distinct voters on every one of the 40 challenges.",
        "",
        "## Frozen development catalog",
        "",
        f"- Frozen rostered player universe: {snapshot['player_count']} players.",
        "- Exactly 40 player-only challenges.",
        "- Topologies: 2v2=6, 2v3=8, 2v4=6, 3v3=6, 3v4=8, 4v4=6.",
        f"- Direction balance by top-asset share: {d['direction_counts']}.",
        f"- Contrast bands: {d['contrast_band_counts']}.",
        f"- Unique players used: {d['unique_players']}.",
        f"- Maximum appearances by one player: {d['max_player_appearances']}.",
        f"- Position challenge coverage: {d['position_challenge_counts']}.",
        "",
        "Primary concentration direction is defined by top-asset share. HHI is frozen as a secondary "
        "descriptor because raw HHI is mechanically affected by 2-vs-3-vs-4 asset count; topology "
        "already captures cardinality.",
        "",
        "Draft picks remain excluded until the independent pick/player FV bridge is frozen.",
        "",
        "## Next",
        "",
        "Build a separate voting-activation workflow/UI using this exact catalog. Do not regenerate the catalog after votes begin.",
        "",
    ]) + "\n"

def build_outputs():
    prereg = read_json(PHASE1)
    assert prereg["status"] == "FROZEN_PRE_VOTE_PRE_CATALOG_PRE_FIT"
    assert prereg["development_catalog_preregistration"]["challenge_count"] == 40
    assert prereg["mock_vote_transport"]["distinct_voter_hard_cap"] == 50
    assert prereg["new_mock_trade_votes_exist_or_were_read"] is False

    players, pos_counts = player_universe()
    generated = datetime.now(timezone.utc).isoformat()
    snapshot = {
        "schema_version":1,
        "study_id":STUDY_ID,
        "stage":"phase1a_frozen_player_fv_snapshot",
        "status":"FROZEN_PRE_VOTE_PLAYER_FV_SNAPSHOT",
        "generated_at_utc":generated,
        "player_count":len(players),
        "position_counts":pos_counts,
        "players":players,
        "source_sha256":{
            "index_html":sha256(INDEX),
            "value_uncertainty":sha256(VALUES),
            "league_rosters":sha256(ROSTERS),
            "snapshot_values_py":sha256(SNAPSHOT_VALUES),
            "phase1_preregistration":sha256(PHASE1),
        },
        "market_values_used":False,
        "draft_picks_included":False,
        "v7_votes_read":False,
    }

    power = build_power()
    selected, side_pools, appearance, pos_cov = choose_catalog(players)
    challenges = [challenge_record(i+1, row) for i,row in enumerate(selected)]
    diagnostics = validate_catalog(challenges, prereg)

    catalog = {
        "schema_version":1,
        "study_id":STUDY_ID,
        "stage":"phase1a_development_catalog",
        "status":"FROZEN_PRE_VOTE_DEVELOPMENT_CATALOG",
        "generated_at_utc":generated,
        "frozen":True,
        "released":False,
        "voting_activated":False,
        "v7_votes_read":False,
        "candidate_fit_performed":False,
        "candidate_predictions_used_for_catalog_selection":False,
        "fv_visible_to_voter":False,
        "challenge_count":40,
        "primary_concentration_operationalization":{
            "direction_metric":"top_asset_share",
            "band_metric":"absolute top_asset_share difference",
            "bands":{k:list(v) for k,v in BAND_RANGE.items()},
            "hhi_role":"secondary frozen descriptor; not required to share direction across unequal-size topologies because raw HHI depends on asset count",
        },
        "design":{
            "topology_counts":prereg["development_catalog_preregistration"]["topology_counts"],
            "raw_sum_ratio_minimum":0.92,
            "minimum_asset_share_of_own_side_raw_sum":0.10,
            "max_player_appearances":4,
            "minimum_challenges_containing_each_position":6,
            "display_side_randomization_required":True,
            "challenge_order_randomization_required":True,
            "exact_motivating_trade_excluded":True,
        },
        "diagnostics":diagnostics,
        "side_pool_counts":{str(k):len(v) for k,v in side_pools.items()},
        "source_sha256":{
            "phase1_preregistration":sha256(PHASE1),
            "player_snapshot":None,
        },
        "challenges":challenges,
    }

    return snapshot, power, catalog

def write():
    for p in (OUT_SNAPSHOT,OUT_POWER,OUT_CATALOG,OUT_SUMMARY,OUT_MANIFEST):
        if p.exists():
            raise RuntimeError(f"output already exists: {p}")

    snapshot,power,catalog = build_outputs()
    OUT_SNAPSHOT.write_text(json.dumps(snapshot,indent=2,sort_keys=True)+"\n")
    catalog["source_sha256"]["player_snapshot"] = sha256(OUT_SNAPSHOT)
    OUT_POWER.write_text(json.dumps(power,indent=2,sort_keys=True)+"\n")
    OUT_CATALOG.write_text(json.dumps(catalog,indent=2,sort_keys=True)+"\n")
    OUT_SUMMARY.write_text(render_summary(snapshot,power,catalog))

    manifest = {
        "schema_version":1,
        "study_id":STUDY_ID,
        "stage":"phase1a_power_and_catalog_freeze",
        "status":STATUS,
        "decision":DECISION,
        "generated_at_utc":snapshot["generated_at_utc"],
        "research_only":True,
        "v7_votes_read":False,
        "voting_activated":False,
        "candidate_fit_performed":False,
        "production_change_authorized":False,
        "selected_first_checkpoint_distinct_voters":power["selected_first_checkpoint_distinct_voters"],
        "hard_cap_distinct_voters":power["hard_cap_distinct_voters"],
        "challenge_count":catalog["challenge_count"],
        "output_sha256":{
            OUT_SNAPSHOT.name:sha256(OUT_SNAPSHOT),
            OUT_POWER.name:sha256(OUT_POWER),
            OUT_CATALOG.name:sha256(OUT_CATALOG),
            OUT_SUMMARY.name:sha256(OUT_SUMMARY),
            Path(__file__).name:sha256(Path(__file__)),
        },
        "canonical_sha256":{
            "snapshot":canonical_sha(snapshot),
            "power":canonical_sha(power),
            "catalog":canonical_sha(catalog),
        },
        "next_stage":"package-adjustment-v7-development-voting-activation",
    }
    OUT_MANIFEST.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")

    print(json.dumps({
        "decision":DECISION,
        "player_count":snapshot["player_count"],
        "challenge_count":catalog["challenge_count"],
        "selected_first_checkpoint":power["selected_first_checkpoint_distinct_voters"],
        "hard_cap":power["hard_cap_distinct_voters"],
        "catalog_diagnostics":catalog["diagnostics"],
        "v7_votes_read":False,
        "voting_activated":False,
        "production_change_authorized":False,
    },indent=2))

def check():
    prereg = read_json(PHASE1)
    snap = read_json(OUT_SNAPSHOT)
    power = read_json(OUT_POWER)
    catalog = read_json(OUT_CATALOG)
    man = read_json(OUT_MANIFEST)

    assert snap["player_count"] >= 350
    assert snap["v7_votes_read"] is False
    assert power["selected_first_checkpoint_distinct_voters"] == 40
    assert power["hard_cap_distinct_voters"] == 50
    assert power["v7_votes_read"] is False
    assert catalog["challenge_count"] == 40
    assert catalog["voting_activated"] is False
    assert catalog["candidate_fit_performed"] is False
    assert catalog["candidate_predictions_used_for_catalog_selection"] is False
    diag = validate_catalog(catalog["challenges"], prereg)
    assert diag == catalog["diagnostics"]
    assert man["decision"] == DECISION
    assert man["v7_votes_read"] is False
    assert man["voting_activated"] is False
    assert man["production_change_authorized"] is False
    for name,h in man["output_sha256"].items():
        p = D / name if name != Path(__file__).name else Path(__file__)
        assert sha256(p) == h, (name,sha256(p),h)
    assert catalog["source_sha256"]["player_snapshot"] == sha256(OUT_SNAPSHOT)
    print("PASS: Package Adjustment V7 Phase 1A outputs revalidated.")

def selftest():
    # Power checkpoint resolution is intentionally exact and deterministic.
    dev_d,dev_sd,dev_n = -0.07822179237598825,0.025655953446444925,34
    pros_d,pros_sd,pros_n = -0.056642594682942526,0.018619304491449096,45
    vals=[]
    for n in (30,40,50):
        ps=[]
        for d,sd,n0 in ((dev_d,dev_sd,dev_n),(pros_d,pros_sd,pros_n)):
            se=sd*math.sqrt(n0/n)
            p,_=normal_power(d,se)
            ps.append(p)
        vals.append((n,min(ps)))
    assert vals[0][1] < 0.80
    assert vals[1][1] >= 0.80
    assert vals[2][1] >= vals[1][1]
    assert sum(len(v) for v in DESIGN.values()) == 40
    assert sum(1 for cells in DESIGN.values() for c in cells if c.startswith("A_")) == 20
    assert sum(1 for cells in DESIGN.values() for c in cells if c.startswith("B_")) == 20
    print("PASS: V7 Phase 1A generator self-test.")

def main():
    ap=argparse.ArgumentParser()
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest",action="store_true")
    g.add_argument("--write",action="store_true")
    g.add_argument("--check",action="store_true")
    a=ap.parse_args()
    if a.selftest: selftest()
    elif a.write: write()
    else: check()

if __name__ == "__main__":
    main()

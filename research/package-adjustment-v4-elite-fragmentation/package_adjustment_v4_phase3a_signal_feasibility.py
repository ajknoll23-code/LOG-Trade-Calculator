#!/usr/bin/env python3
"""Package Adjustment V4 Phase 3A — outcome-blind signal feasibility.

Verifies that the already-frozen V4 family can produce an informative fresh
confirmation catalog before any new human votes are collected.

No human vote outcomes are read. No fitting or tuning is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "research" / "package-adjustment-v4-elite-fragmentation"
V3 = ROOT / "research" / "package-adjustment-v3-ktc-style"

INDEX = ROOT / "index.html"
ROSTERS = ROOT / "data" / "league_rosters.json"
PREREG = V4 / "phase1_structural_preregistration.json"
FAMILY = V4 / "frozen_candidate.json"
PHASE2_MANIFEST = V4 / "phase2_manifest.json"
V3_PICK_UTILITY = V3 / "package_adjustment_v3_phase2.py"

OUT = V4 / "phase3a_signal_feasibility.json"
OUT_MD = V4 / "phase3a_signal_feasibility.md"
OUT_MANIFEST = V4 / "phase3a_signal_feasibility_manifest.json"

RNG_SEED = 202609194
MAX_ATTEMPTS_PER_GROUP = 250_000
MIN_TARGETED_POOL_PER_GROUP = 30
MIN_BROAD_POOL_PER_GROUP = 100
RAW_RATIO_MIN = 0.80
RAW_RATIO_MAX = 1.25
MIN_SIGN_MARGIN = 0.005
CANDIDATE_SEPARATION_MARGIN = 0.002
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

CORRECT_KTC_EXAMPLES = [
    (frozenset(["jahmyr gibbs"]), frozenset(["devon achane", "tee higgins"])),
    (frozenset(["ceedee lamb", "sam laporta"]), frozenset(["rome odunze", "saquon barkley"])),
    (frozenset(["george pickens", "marshawn lloyd"]), frozenset(["isaiah likely", "ryan flournoy", "rico dowdle"])),
    (frozenset(["josh allen"]), frozenset(["caleb williams", "saquon barkley"])),
    (frozenset(["george pickens", "kaelon black"]), frozenset(["jayden reed", "parker washington", "jonathon brooks"])),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def normalize_name(value) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


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
    validation_dir = ROOT / "scripts" / "validation"
    if str(validation_dir) not in sys.path:
        sys.path.insert(0, str(validation_dir))
    import snapshot_values

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
        raise RuntimeError("Joe Mixon leaked into V4 player universe")

    phase2 = load_module(V3_PICK_UTILITY, "v3_pick_utility")
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
        raise RuntimeError(f"Expected 24 V4 pick assets, got {len(picks)}")
    if any(p["year"] not in {2027, 2028} for p in picks):
        raise RuntimeError("2029+ pick leaked into V4 pick universe")

    return players, picks


def side_key(side):
    return tuple(sorted(a["id"] for a in side))


def trade_signature(side_a, side_b):
    return tuple(sorted((side_key(side_a), side_key(side_b))))


def is_known_ktc_example(side_a, side_b):
    if any(a["kind"] != "player" for a in side_a + side_b):
        return False
    a = frozenset(normalize_name(x["name"]) for x in side_a)
    b = frozenset(normalize_name(x["name"]) for x in side_b)
    return any((a == x and b == y) or (a == y and b == x) for x, y in CORRECT_KTC_EXAMPLES)


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


def sample_trade(rng, a_count, b_count, asset_mix, players, picks):
    total = a_count + b_count
    if asset_mix == "players_only":
        assets = sample_unique(rng, players, total)
    else:
        pick_count = rng.randint(1, min(total - 1, 4))
        assets = sample_unique(rng, players, total - pick_count) + sample_unique(rng, picks, pick_count)
        rng.shuffle(assets)
        if {a["kind"] for a in assets} != {"player", "pick"}:
            raise RuntimeError("Mixed-asset challenge construction failed")
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
    third_plus = sum(vals[2:]) if len(vals) >= 3 else 0.0
    total = sum(vals)
    elite = min(1.0, max(0.0, v1 / 10000.0))
    premium = elite * (
        float(candidate["stud_strength"]) * v1
        - float(candidate["second_piece_discount"]) * v2
        - float(candidate["third_plus_discount"]) * third_plus
    )
    return total + premium


def candidate_delta(side_a, side_b, candidate):
    a = effective_score(side_a, candidate)
    b = effective_score(side_b, candidate)
    return (a - b) / (abs(a) + abs(b))


def percentile(values, q):
    if not values:
        return None
    xs = sorted(values)
    h = (len(xs) - 1) * q
    lo, hi = int(math.floor(h)), int(math.ceil(h))
    if lo == hi:
        return xs[lo]
    f = h - lo
    return xs[lo] * (1 - f) + xs[hi] * f


def selftest():
    c = {
        "stud_strength": 0.75,
        "second_piece_discount": 0.10,
        "third_plus_discount": 0.30,
    }
    a = [{"fv": 8000}, {"fv": 1500}]
    b = [{"fv": 5200}, {"fv": 4200}]
    assert math.isfinite(raw_delta(a, b))
    assert math.isfinite(candidate_delta(a, b, c))

    x = [{"kind": "player", "name": "George Pickens"}, {"kind": "player", "name": "Kaelon Black"}]
    y = [
        {"kind": "player", "name": "Jayden Reed"},
        {"kind": "player", "name": "Parker Washington"},
        {"kind": "player", "name": "Jonathon Brooks"},
    ]
    assert is_known_ktc_example(x, y)
    print("Package Adjustment V4 Phase 3A self-test PASS")


def main():
    for path in (OUT, OUT_MD, OUT_MANIFEST):
        if path.exists():
            raise RuntimeError(f"Phase 3A output already exists: {path}")

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    phase2 = json.loads(PHASE2_MANIFEST.read_text(encoding="utf-8"))

    assert prereg["status"] == "FROZEN_BEFORE_SPENT_EVIDENCE_DEVELOPMENT"
    assert prereg["asset_eligibility"]["draft_picks"]["years_allowed"] == [2027, 2028]
    assert prereg["asset_eligibility"]["players"]["explicitly_excluded_players"] == ["Joe Mixon"]
    assert prereg["fresh_confirmation_contract_if_candidate_frozen"]["challenge_strata"] == [
        "candidate_vs_raw_disagreement", "balanced_broad"
    ]
    assert family["status"] == "FROZEN_V4_CONFIRMATION_FAMILY"
    assert family["family_count"] == 2
    assert phase2["fresh_confirmation_authorized"] is True

    candidates = family["candidate_family"]
    players, picks = build_asset_universe()
    rng = random.Random(RNG_SEED)

    group_rows = []
    total_targeted = 0
    total_broad = 0
    total_candidate_split = 0
    split_groups = 0

    for topology, (a_count, b_count) in TOPOLOGIES.items():
        for mix in ASSET_MIXES:
            targeted = {}
            broad = {}
            split = {}
            target_margins = []
            split_margins = []
            seen = set()

            for attempt in range(1, MAX_ATTEMPTS_PER_GROUP + 1):
                side_a, side_b = sample_trade(rng, a_count, b_count, mix, players, picks)
                sig = trade_signature(side_a, side_b)
                if sig in seen or is_known_ktc_example(side_a, side_b):
                    continue
                seen.add(sig)

                raw_a = sum(float(x["fv"]) for x in side_a)
                raw_b = sum(float(x["fv"]) for x in side_b)
                ratio = raw_a / raw_b
                if not (RAW_RATIO_MIN <= ratio <= RAW_RATIO_MAX):
                    continue

                d0 = raw_delta(side_a, side_b)
                d1 = candidate_delta(side_a, side_b, candidates[0])
                d2 = candidate_delta(side_a, side_b, candidates[1])

                broad[sig] = abs(d0)

                s0, s1, s2 = sign(d0), sign(d1), sign(d2)
                if 0 not in (s0, s1, s2) and s1 == s2 and s0 != s1:
                    margin = min(abs(d0), abs(d1), abs(d2))
                    if margin >= MIN_SIGN_MARGIN:
                        targeted[sig] = margin
                        target_margins.append(margin)

                if s1 and s2 and s1 != s2:
                    margin = min(abs(d1), abs(d2))
                    if margin >= CANDIDATE_SEPARATION_MARGIN:
                        split[sig] = margin
                        split_margins.append(margin)

                if (
                    len(targeted) >= MIN_TARGETED_POOL_PER_GROUP
                    and len(broad) >= MIN_BROAD_POOL_PER_GROUP
                    and attempt >= 25_000
                ):
                    break
            else:
                attempt = MAX_ATTEMPTS_PER_GROUP

            passed = (
                len(targeted) >= MIN_TARGETED_POOL_PER_GROUP
                and len(broad) >= MIN_BROAD_POOL_PER_GROUP
            )
            if split:
                split_groups += 1
                total_candidate_split += len(split)

            total_targeted += len(targeted)
            total_broad += len(broad)

            group_rows.append({
                "topology": topology,
                "asset_mix": mix,
                "attempts": attempt,
                "targeted_family_vs_raw_pool": len(targeted),
                "balanced_broad_pool": len(broad),
                "candidate_vs_candidate_sign_disagreement_pool": len(split),
                "targeted_margin_p10": percentile(target_margins, 0.10),
                "targeted_margin_median": percentile(target_margins, 0.50),
                "targeted_margin_p90": percentile(target_margins, 0.90),
                "candidate_separation_margin_median": percentile(split_margins, 0.50),
                "operational_feasibility_pass": passed,
            })

    all_pass = all(r["operational_feasibility_pass"] for r in group_rows)
    status = (
        "V4_FRESH_CONFIRMATION_SIGNAL_FEASIBLE"
        if all_pass
        else "V4_FRESH_CONFIRMATION_NOT_FEASIBLE_UNDER_FROZEN_ARCHITECTURE"
    )
    generated = datetime.now(timezone.utc).isoformat()

    result = {
        "schema_version": 1,
        "study_id": "package-adjustment-v4-elite-fragmentation",
        "phase": "3A",
        "status": status,
        "generated_at_utc": generated,
        "research_only": True,
        "outcome_blind": True,
        "human_vote_outcomes_read": False,
        "model_fitting_performed": False,
        "candidate_family_changed": False,
        "production_change_authorized": False,
        "production_revision_unchanged": "v1.6-v5-size2-composition-overlay",
        "frozen_candidate_ids": [c["id"] for c in candidates],
        "asset_universe": {
            "eligible_players": len(players),
            "pick_assets": len(picks),
            "joe_mixon_present": False,
            "pick_years": [2027, 2028],
        },
        "feasibility_contract": {
            "raw_ratio_range": [RAW_RATIO_MIN, RAW_RATIO_MAX],
            "minimum_meaningful_sign_margin": MIN_SIGN_MARGIN,
            "minimum_targeted_pool_per_topology_x_mix": MIN_TARGETED_POOL_PER_GROUP,
            "minimum_balanced_broad_pool_per_topology_x_mix": MIN_BROAD_POOL_PER_GROUP,
            "candidate_separation_margin": CANDIDATE_SEPARATION_MARGIN,
            "candidate_separation_is_diagnostic_not_a_pass_gate": True,
            "max_attempts_per_group": MAX_ATTEMPTS_PER_GROUP,
            "rng_seed": RNG_SEED,
        },
        "groups": group_rows,
        "all_12_groups_operationally_feasible": all_pass,
        "totals": {
            "targeted_family_vs_raw_pool": total_targeted,
            "balanced_broad_pool": total_broad,
            "candidate_vs_candidate_sign_disagreement_pool": total_candidate_split,
            "groups_with_candidate_vs_candidate_sign_disagreement": split_groups,
        },
        "development_signal_warning": {
            "phase2_best_improvement_vs_raw": 0.000000009673,
            "phase2_advantage_was_numerically_tiny": True,
        },
        "next_action": (
            "Generate and freeze the unreleased 240-challenge V4 fresh-confirmation catalog."
            if all_pass else
            "Close V4 without fresh voting; do not loosen this feasibility gate post hoc."
        ),
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Package Adjustment V4 — Phase 3A Signal Feasibility",
        "",
        f"**Status:** `{status}`",
        "",
        "Outcome-blind operational gate; no human vote outcomes were read.",
        "",
        f"- Eligible players: **{len(players)}**",
        f"- Picks: **{len(picks)}** (2027/2028 only)",
        "- Joe Mixon: **excluded**",
        f"- All 12 topology×mix groups feasible: **{'YES' if all_pass else 'NO'}**",
        f"- Meaningful family-vs-raw challenge pool: **{total_targeted}**",
        f"- Broad-balanced pool: **{total_broad}**",
        f"- Candidate-vs-candidate sign splits: **{total_candidate_split}** across **{split_groups}/12** groups",
        "",
        "| Topology | Mix | Targeted | Broad | Candidate split | Pass |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in group_rows:
        lines.append(
            f"| {r['topology']} | {r['asset_mix']} | "
            f"{r['targeted_family_vs_raw_pool']} | {r['balanced_broad_pool']} | "
            f"{r['candidate_vs_candidate_sign_disagreement_pool']} | "
            f"{'PASS' if r['operational_feasibility_pass'] else 'FAIL'} |"
        )
    lines += [
        "",
        "Phase 2's development advantage was microscopic, so fresh voting is only justified if this step demonstrates real structural disagreement.",
        "",
        result["next_action"],
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "status": "package_adjustment_v4_phase3a_signal_feasibility_manifest",
        "generated_at_utc": generated,
        "outcome_blind": True,
        "human_vote_outcomes_read": False,
        "production_change_authorized": False,
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
            "index_html": {"git_blob_sha": git_blob(INDEX)},
            "league_rosters": {"git_blob_sha": git_blob(ROSTERS)},
        },
        "outputs": {
            "result": {"path": str(OUT.relative_to(ROOT)), "sha256": sha256(OUT)},
            "summary": {"path": str(OUT_MD.relative_to(ROOT)), "sha256": sha256(OUT_MD)},
        },
        "next_action": result["next_action"],
    }
    OUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(OUT_MD.read_text(encoding="utf-8"))
    if os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as fh:
            fh.write(f"V4_PHASE3A_STATUS={status}\n")

    print(OUT_MD.read_text(encoding="utf-8"))
    print("V4_PHASE3A_STATUS=" + status)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        main()

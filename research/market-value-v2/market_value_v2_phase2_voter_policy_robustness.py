#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
OUTDIR = SCRIPT.parent

PREREG = OUTDIR / "market_value_v2_phase2_preregistration.json"
SNAPSHOT = OUTDIR / "market_value_v2_phase2_vote_snapshot.json"
OUTJSON = OUTDIR / "market_value_v2_phase2_voter_policy_robustness.json"
OUTMD = OUTDIR / "market_value_v2_phase2_voter_policy_robustness.md"
MANIFEST = OUTDIR / "market_value_v2_phase2_manifest.json"

KTC_PIPELINE = ROOT / "scripts" / "market" / "ktc_pipeline.py"
POSITIONS = ROOT / "scripts" / "artifacts" / "generated" / "player_positions.json"

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_ktc():
    spec = importlib.util.spec_from_file_location("ktc_pipeline_phase2", KTC_PIPELINE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load KTC pipeline")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def normalize_vote_row(row):
    return {
        "timestamp": str(row.get("timestamp") or ""),
        "voter_roster_id": str(row.get("voter_roster_id") or ""),
        "keep": str(row.get("keep") or ""),
        "trade": str(row.get("trade") or ""),
        "cut": str(row.get("cut") or "")
    }

def freeze_snapshot():
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if prereg["status"] != "PREREGISTERED_BEFORE_LIVE_VOTE_FETCH":
        raise RuntimeError("preregistration state mismatch")

    mod = load_ktc()

    response = requests.get(mod.SHEET_CSV_URL, timeout=30)
    response.raise_for_status()
    all_rows = list(csv.DictReader(io.StringIO(response.text)))

    non_package = [
        r for r in all_rows
        if not mod.is_package_vote_row(r)
    ]
    counted = mod.apply_daily_cap(non_package)
    counted = [normalize_vote_row(r) for r in counted]

    league = [
        r for r in counted
        if mod.is_league_voter(r["voter_roster_id"])
    ]
    guests = [
        r for r in counted
        if not mod.is_league_voter(r["voter_roster_id"])
    ]

    voters = sorted({r["voter_roster_id"] for r in counted})

    snapshot = {
        "schema_version": 1,
        "study_id": "market-value-v2-phase2-voter-policy-robustness",
        "frozen_at_utc":
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sheet_url": mod.SHEET_CSV_URL,
        "raw_sheet_row_count": len(all_rows),
        "package_rows_excluded": len(all_rows) - len(non_package),
        "counted_after_daily_cap": len(counted),
        "league_counted_rows": len(league),
        "guest_counted_rows": len(guests),
        "distinct_voter_count": len(voters),
        "rows": counted
    }
    SNAPSHOT.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )

def voter_base_weights(rows, cap):
    counts = defaultdict(int)
    for row in rows:
        counts[row["voter_roster_id"]] += 1
    weights = {}
    for voter, count in counts.items():
        weights[voter] = min(1.0, cap / float(count))
    return weights, counts

def weighted_rank(rows, guest_multiplier, cap, voter_override=None):
    mod = load_ktc()
    base_weights, counts = voter_base_weights(rows, cap)
    weighted_pairs = []
    effective_votes = defaultdict(float)

    for row in rows:
        voter = row["voter_roster_id"]
        effective_voter = (
            voter_override.get(voter, voter)
            if voter_override else voter
        )
        # If voter_override is used only to rename, caller should
        # pre-transform rows so caps are recomputed by synthetic identity.
        is_league = mod.is_league_voter(effective_voter)
        group_mult = 1.0 if is_league else guest_multiplier
        w = base_weights[voter] * group_mult

        if w <= 0:
            continue

        effective_votes[effective_voter] += w
        keep, trade, cut = row["keep"], row["trade"], row["cut"]
        if not (keep and trade and cut):
            continue
        weighted_pairs.extend([
            (keep, trade, w),
            (keep, cut, w),
            (trade, cut, w)
        ])

    strengths = mod.weighted_bradley_terry(weighted_pairs)
    ordered = [
        player for player, _ in
        sorted(strengths.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    ranks = {player: i + 1 for i, player in enumerate(ordered)}
    return {
        "strengths": strengths,
        "ranks": ranks,
        "ordered": ordered,
        "effective_votes_by_voter": dict(effective_votes),
        "raw_votes_by_voter": dict(counts)
    }

def spearman_from_ranks(a, b):
    common = sorted(set(a) & set(b))
    n = len(common)
    if n < 2:
        return None
    # Pearson correlation of rank vectors on common players.
    xa = [float(a[p]) for p in common]
    xb = [float(b[p]) for p in common]
    ma = sum(xa) / n
    mb = sum(xb) / n
    num = sum((x-ma)*(y-mb) for x, y in zip(xa, xb))
    da = math.sqrt(sum((x-ma)**2 for x in xa))
    db = math.sqrt(sum((y-mb)**2 for y in xb))
    if da == 0 or db == 0:
        return None
    return num / (da * db)

def top_overlap(a_order, b_order, n=50):
    aa = set(a_order[:n])
    bb = set(b_order[:n])
    return len(aa & bb) / float(n)

def split_guest_identities(rows):
    mod = load_ktc()
    by_voter = defaultdict(list)
    for row in rows:
        by_voter[row["voter_roster_id"]].append(dict(row))

    transformed = []
    split_voters = []
    for voter, voter_rows in sorted(by_voter.items()):
        voter_rows.sort(
            key=lambda r: (
                r["timestamp"], r["keep"], r["trade"], r["cut"]
            )
        )
        if mod.is_league_voter(voter) or len(voter_rows) <= 15:
            transformed.extend(voter_rows)
            continue

        split_voters.append(voter)
        for idx, row in enumerate(voter_rows):
            row = dict(row)
            row["voter_roster_id"] = (
                f"{voter}__split_{idx % 2}"
            )
            transformed.append(row)

    return transformed, split_voters

def run_analysis():
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    rows = snap["rows"]

    cap = float(
        prereg["candidate_policy"][
            "per_voter_lifetime_effective_vote_cap"
        ]
    )
    primary_weight = float(
        prereg["candidate_policy"]["guest_voter_multiplier"]
    )
    gates_cfg = prereg["primary_unseen_robustness_gates"]

    full = weighted_rank(rows, primary_weight, cap)

    # Candidate concentration.
    effective = full["effective_votes_by_voter"]
    total_effective = sum(effective.values())
    largest_share = (
        100.0 * max(effective.values()) / total_effective
        if total_effective and effective else 0.0
    )

    distinct_voters = len(full["raw_votes_by_voter"])

    # Leave-one-voter-out stability.
    voters = sorted(full["raw_votes_by_voter"])
    lovo = []
    for voter in voters:
        reduced = [
            r for r in rows
            if r["voter_roster_id"] != voter
        ]
        alt = weighted_rank(reduced, primary_weight, cap)
        rho = spearman_from_ranks(full["ranks"], alt["ranks"])
        overlap = top_overlap(full["ordered"], alt["ordered"], 50)
        lovo.append({
            "voter_roster_id": voter,
            "raw_votes_removed": full["raw_votes_by_voter"][voter],
            "spearman": rho,
            "top50_overlap": overlap
        })

    valid_rhos = [x["spearman"] for x in lovo if x["spearman"] is not None]
    lovo_median = statistics.median(valid_rhos) if valid_rhos else None
    lovo_worst = min(valid_rhos) if valid_rhos else None
    lovo_worst_top50 = min(
        x["top50_overlap"] for x in lovo
    ) if lovo else None

    # Guest identity reset/split stress.
    split_rows, split_voters = split_guest_identities(rows)
    split_rank = weighted_rank(split_rows, primary_weight, cap)
    split_rho = spearman_from_ranks(
        full["ranks"], split_rank["ranks"]
    )
    split_top50 = top_overlap(
        full["ordered"], split_rank["ordered"], 50
    )

    # Descriptive guest-weight sensitivity.
    sensitivity = {}
    for weight in prereg["diagnostic_guest_weights"]:
        weight = float(weight)
        alt = weighted_rank(rows, weight, cap)
        sensitivity[str(weight)] = {
            "resolved_players": len(alt["ranks"]),
            "spearman_vs_0_50": spearman_from_ranks(
                full["ranks"], alt["ranks"]
            ),
            "top50_overlap_vs_0_50": top_overlap(
                full["ordered"], alt["ordered"], 50
            ),
            "effective_vote_mass": round(
                sum(alt["effective_votes_by_voter"].values()), 6
            )
        }

    gates = {
        "minimum_distinct_voters": (
            distinct_voters >=
            int(gates_cfg["minimum_distinct_voters"])
        ),
        "maximum_single_voter_effective_share_pct": (
            largest_share <=
            float(gates_cfg["maximum_single_voter_effective_share_pct"])
        ),
        "leave_one_voter_out_median_spearman": (
            lovo_median is not None and
            lovo_median >=
            float(gates_cfg["leave_one_voter_out_median_spearman_min"])
        ),
        "leave_one_voter_out_worst_spearman": (
            lovo_worst is not None and
            lovo_worst >=
            float(gates_cfg["leave_one_voter_out_worst_spearman_min"])
        ),
        "leave_one_voter_out_worst_top50_overlap": (
            lovo_worst_top50 is not None and
            lovo_worst_top50 >=
            float(gates_cfg["leave_one_voter_out_worst_top50_overlap_min"])
        ),
        "guest_identity_split_stress_spearman": (
            split_rho is not None and
            split_rho >=
            float(gates_cfg["guest_identity_split_stress_spearman_min"])
        ),
        "guest_identity_split_stress_top50_overlap": (
            split_top50 >=
            float(gates_cfg["guest_identity_split_stress_top50_overlap_min"])
        )
    }

    all_pass = all(gates.values())
    decision = (
        "ACTIONABLE_FOR_PROMOTION_SHADOW"
        if all_pass
        else "HOLD_MARKET_VALUE_V2_POLICY_ROBUSTNESS_FAILED"
    )

    # Sort most influential LOOVO removals first.
    lovo_sorted = sorted(
        lovo,
        key=lambda x: (
            x["spearman"] if x["spearman"] is not None else -1,
            x["top50_overlap"]
        )
    )

    result = {
        "schema_version": 1,
        "study_id": "market-value-v2-phase2-voter-policy-robustness",
        "status": "ROBUSTNESS_EVALUATED_ON_FROZEN_LIVE_SNAPSHOT",
        "decision": decision,
        "generated_at_utc":
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "research_only": True,
        "production_change_authorized": False,
        "promotion_authorized": False,
        "snapshot_summary": {
            k: snap[k]
            for k in (
                "frozen_at_utc",
                "raw_sheet_row_count",
                "package_rows_excluded",
                "counted_after_daily_cap",
                "league_counted_rows",
                "guest_counted_rows",
                "distinct_voter_count"
            )
        },
        "primary_candidate": {
            "guest_weight": primary_weight,
            "resolved_players": len(full["ranks"]),
            "distinct_voters": distinct_voters,
            "total_effective_vote_mass": round(total_effective, 6),
            "largest_single_voter_effective_share_pct":
                round(largest_share, 4)
        },
        "leave_one_voter_out": {
            "runs": len(lovo),
            "median_spearman": lovo_median,
            "worst_spearman": lovo_worst,
            "worst_top50_overlap": lovo_worst_top50,
            "most_influential_voter_removals": lovo_sorted[:10]
        },
        "guest_identity_split_stress": {
            "guest_voters_split": split_voters,
            "guest_voters_split_count": len(split_voters),
            "spearman_vs_primary": split_rho,
            "top50_overlap_vs_primary": split_top50,
            "resolved_players": len(split_rank["ranks"])
        },
        "weight_sensitivity": sensitivity,
        "hard_gates": gates,
        "all_primary_gates_pass": all_pass,
        "next_step_rule": (
            "If ACTIONABLE_FOR_PROMOTION_SHADOW, build a separate "
            "Market Value V2 production-candidate shadow that changes "
            "only the Market Value consumer and proves exact downstream "
            "scope. If any primary gate fails, do not promote 0.50; "
            "diagnose the failed robustness dimension without tuning "
            "against this frozen snapshot."
        )
    }

    OUTJSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )
    return result

def render(result):
    p = result["primary_candidate"]
    l = result["leave_one_voter_out"]
    s = result["guest_identity_split_stress"]

    lines = [
        "# Market Value V2 Phase 2 — Voter-Policy Robustness",
        "",
        f"**Decision:** `{result['decision']}`",
        "",
        "**RESEARCH ONLY. Market Value V1 remains deployed.**",
        "",
        "## Frozen snapshot",
        "",
        f"- Counted ballots after daily cap: **{result['snapshot_summary']['counted_after_daily_cap']}**",
        f"- League ballots: **{result['snapshot_summary']['league_counted_rows']}**",
        f"- Guest ballots: **{result['snapshot_summary']['guest_counted_rows']}**",
        f"- Distinct voters: **{result['snapshot_summary']['distinct_voter_count']}**",
        "",
        "## Primary 0.50 guest-weight candidate",
        "",
        f"- Resolved players: **{p['resolved_players']}**",
        f"- Effective vote mass: **{p['total_effective_vote_mass']}**",
        f"- Largest single-voter effective share: **{p['largest_single_voter_effective_share_pct']:.2f}%**",
        "",
        "## Leave-one-voter-out robustness",
        "",
        f"- Runs: **{l['runs']}**",
        f"- Median Spearman: **{l['median_spearman']:.6f}**",
        f"- Worst Spearman: **{l['worst_spearman']:.6f}**",
        f"- Worst Top-50 overlap: **{100*l['worst_top50_overlap']:.1f}%**",
        "",
        "## Guest identity-reset stress",
        "",
        f"- Guest identities split: **{s['guest_voters_split_count']}**",
        f"- Spearman vs primary: **{s['spearman_vs_primary']:.6f}**",
        f"- Top-50 overlap vs primary: **{100*s['top50_overlap_vs_primary']:.1f}%**",
        "",
        "## Hard gates",
        ""
    ]
    for gate, passed in result["hard_gates"].items():
        lines.append(f"- `{gate}`: **{'PASS' if passed else 'FAIL'}**")

    lines += [
        "",
        "## Guest-weight sensitivity",
        "",
        "| Guest weight | Resolved | Spearman vs 0.50 | Top-50 overlap | Effective vote mass |",
        "|---:|---:|---:|---:|---:|"
    ]
    for weight, row in sorted(
        result["weight_sensitivity"].items(),
        key=lambda kv: float(kv[0])
    ):
        rho = row["spearman_vs_0_50"]
        rho_txt = f"{rho:.6f}" if rho is not None else "—"
        lines.append(
            f"| {weight} | {row['resolved_players']} | {rho_txt} | "
            f"{100*row['top50_overlap_vs_0_50']:.1f}% | "
            f"{row['effective_vote_mass']} |"
        )

    lines += [
        "",
        "## Governance",
        "",
        "- The 0.50 guest multiplier was not re-fit in this phase.",
        "- Weight sensitivity is descriptive and cannot rescue a failed primary robustness gate.",
        "- The guest split stress specifically targets browser-local identity reset risk.",
        "- Market Value V1, Fundamental Value, Team Utility, and live trade verdicts are unchanged.",
        "- This phase cannot deploy itself.",
        "",
        "## Next-step rule",
        "",
        result["next_step_rule"],
        ""
    ]
    return "\n".join(lines)

def write():
    freeze_snapshot()
    result = run_analysis()
    OUTMD.write_text(
        render(result).rstrip() + "\n",
        encoding="utf-8"
    )

    manifest = {
        "schema_version": 1,
        "study_id": result["study_id"],
        "decision": result["decision"],
        "production_change_authorized": False,
        "promotion_authorized": False,
        "preregistration_sha256": sha256(PREREG),
        "vote_snapshot_sha256": sha256(SNAPSHOT),
        "ktc_pipeline_sha256": sha256(KTC_PIPELINE),
        "player_positions_sha256": sha256(POSITIONS),
        "output_json_sha256": sha256(OUTJSON),
        "output_md_sha256": sha256(OUTMD),
        "evaluator_sha256": sha256(SCRIPT)
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )

    print(json.dumps({
        "decision": result["decision"],
        "resolved_players": result["primary_candidate"]["resolved_players"],
        "distinct_voters": result["primary_candidate"]["distinct_voters"],
        "largest_voter_share_pct":
            result["primary_candidate"][
                "largest_single_voter_effective_share_pct"
            ],
        "lovo_median_spearman":
            result["leave_one_voter_out"]["median_spearman"],
        "lovo_worst_spearman":
            result["leave_one_voter_out"]["worst_spearman"],
        "guest_split_spearman":
            result["guest_identity_split_stress"]["spearman_vs_primary"],
        "all_primary_gates_pass":
            result["all_primary_gates_pass"]
    }, indent=2))

def check():
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    result = json.loads(OUTJSON.read_text(encoding="utf-8"))
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    if result["production_change_authorized"] is not False:
        raise RuntimeError("production change illegally authorized")
    if result["promotion_authorized"] is not False:
        raise RuntimeError("promotion illegally authorized")
    if snap["counted_after_daily_cap"] != len(snap["rows"]):
        raise RuntimeError("snapshot row-count mismatch")
    if result["primary_candidate"]["distinct_voters"] < 1:
        raise RuntimeError("no voters evaluated")
    if result["decision"] == "ACTIONABLE_FOR_PROMOTION_SHADOW":
        if not result["all_primary_gates_pass"]:
            raise RuntimeError("actionable decision with failed gate")
    elif result["decision"] == "HOLD_MARKET_VALUE_V2_POLICY_ROBUSTNESS_FAILED":
        if result["all_primary_gates_pass"]:
            raise RuntimeError("hold decision despite all gates passing")
    else:
        raise RuntimeError(f"unexpected decision: {result['decision']}")

    if prereg["candidate_policy"]["guest_voter_multiplier"] != 0.5:
        raise RuntimeError("candidate guest weight drifted")

    print("Market Value V2 Phase 2 output checks PASS")

def selftest():
    # Rank metrics.
    a = {"a": 1, "b": 2, "c": 3}
    b = {"a": 1, "b": 2, "c": 3}
    assert abs(spearman_from_ranks(a, b) - 1.0) < 1e-12
    assert top_overlap(["a", "b"], ["b", "a"], 2) == 1.0

    # Guest split preserves all ballots while changing identities only.
    rows = [
        {
            "timestamp": f"2026-01-{1 + i//10:02d}T00:00:00Z",
            "voter_roster_id": "ext_test",
            "keep": "a",
            "trade": "b",
            "cut": "c"
        }
        for i in range(40)
    ]
    split, voters = split_guest_identities(rows)
    assert len(split) == len(rows)
    assert voters == ["ext_test"]
    assert {
        r["voter_roster_id"] for r in split
    } == {"ext_test__split_0", "ext_test__split_1"}

    print("Market Value V2 Phase 2 self-test PASS")

def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
    elif args.write:
        write()
    else:
        check()

if __name__ == "__main__":
    main()

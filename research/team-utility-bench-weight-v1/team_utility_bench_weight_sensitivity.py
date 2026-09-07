#!/usr/bin/env python3
"""
Team Utility bench-weight sensitivity V1.

RESEARCH ONLY. This script does not modify TU_BENCH_WEIGHT, Fundamental
Value, Market Value, Package Adjustment, trade totals, or live verdicts.

Purpose:
- quantify how sensitive legal-roster Team Utility is to the currently
  unvalidated bench-weight constant;
- identify how often quantity-vs-concentration conclusions change over
  a reasonable weight grid;
- create a clean baseline before Package Adjustment V0 is calibrated.

This is NOT a calibration study because no accepted/rejected trade or
package-preference labels are used. It can show instability/confounding,
but it cannot prove that any tested weight is "correct".
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
ROSTERS = ROOT / "data" / "league_rosters.json"
VALUES = ROOT / "scripts" / "artifacts" / "generated" / "value_uncertainty.json"
PROJECTIONS = ROOT / "scripts" / "artifacts" / "generated" / "team_utility_lineup_projections.json"

OUT_JSON = ROOT / "research" / "team-utility-bench-weight-v1" / "bench_weight_sensitivity.json"
OUT_MD = ROOT / "research" / "team-utility-bench-weight-v1" / "bench_weight_sensitivity.md"

WEIGHTS = (0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
RAW_BALANCE_LOW = 0.90
RAW_BALANCE_HIGH = 1.10
MAX_PIECE_TO_TARGET = 0.85
TARGET_PERCENTILE = 0.60

DEDICATED = (
    ("QB", 1), ("RB", 2), ("WR", 2), ("TE", 1),
    ("DL", 2), ("LB", 2), ("DB", 2), ("K", 1),
)
FLEXES = (
    ("FLEX", {"RB", "WR", "TE"}, 1),
    ("SUPER_FLEX", {"QB", "RB", "WR", "TE"}, 1),
    ("IDP_FLEX", {"DL", "LB", "DB"}, 2),
)

POS_MAP = {
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K",
    "DL": "DL", "DE": "DL", "DT": "DL",
    "LB": "LB", "OLB": "LB", "ILB": "LB",
    "DB": "DB", "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB",
}


@dataclass(frozen=True)
class Player:
    sid: str
    name: str
    pos: str
    fv: float
    projection: float | None


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_name(value) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_pos(value) -> str | None:
    if not value:
        return None
    return POS_MAP.get(str(value).upper())


def raw_position(raw) -> str | None:
    for value in raw.get("fantasy_positions") or []:
        pos = normalize_pos(value)
        if pos:
            return pos
    return normalize_pos(raw.get("position"))


def finite(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def percentile(values, q):
    xs = sorted(float(x) for x in values)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    idx = (len(xs) - 1) * q
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return xs[lo]
    frac = idx - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def parse_deployed_constants():
    text = INDEX.read_text(encoding="utf-8")
    wm = re.search(r"const\s+TU_BENCH_WEIGHT\s*=\s*([0-9.]+)\s*;", text)
    lm = re.search(r"const\s+TU_ACTIVE_ROSTER_LIMIT\s*=\s*(\d+)\s*;", text)
    if not wm:
        raise RuntimeError("could not find deployed TU_BENCH_WEIGHT in index.html")
    if not lm:
        raise RuntimeError(
            "legal-roster Team Utility fix is missing: "
            "TU_ACTIVE_ROSTER_LIMIT not found"
        )
    return float(wm.group(1)), int(lm.group(1))


def build_value_index():
    doc = read_json(VALUES)
    rows = doc.get("players")
    if not isinstance(rows, dict) or len(rows) < 500:
        raise RuntimeError("value_uncertainty.json missing expected full FV universe")
    result = {}
    for name, row in rows.items():
        fv = finite(row.get("center_value"))
        pos = normalize_pos(row.get("pos"))
        if fv is None or fv <= 0 or not pos:
            continue
        result[normalize_name(name)] = {
            "fv": fv,
            "pos": pos,
        }
    return result, doc


def build_projection_index():
    doc = read_json(PROJECTIONS)
    if doc.get("purpose") != "Team Utility starter selection only; never Fundamental Value":
        raise RuntimeError("unexpected Team Utility projection artifact purpose")
    rows = doc.get("players")
    if not isinstance(rows, dict) or len(rows) < 400:
        raise RuntimeError("Team Utility projection artifact unexpectedly small")
    result = {}
    for sid, row in rows.items():
        projection = finite(row.get("projection"))
        if projection is not None:
            result[str(sid)] = projection
    return result, doc


def build_rosters(value_index, projection_index):
    doc = read_json(ROSTERS)
    raw_rosters = doc.get("rosters")
    if not isinstance(raw_rosters, list) or len(raw_rosters) < 10:
        raise RuntimeError("league_rosters.json missing expected league rosters")

    rosters = {}
    missing_fv = []
    seen_players = 0

    for roster in raw_rosters:
        rid = str(roster.get("roster_id"))
        active = []
        for slot in ("starters", "bench"):
            for raw in roster.get(slot, []) or []:
                seen_players += 1
                sid = str(raw.get("player_id") or "")
                name = str(raw.get("name") or sid)
                key = normalize_name(name)
                value_row = value_index.get(key)
                if value_row is None:
                    missing_fv.append({
                        "roster_id": rid,
                        "team_name": roster.get("team_name"),
                        "sleeper_id": sid,
                        "player": name,
                    })
                    continue

                pos = value_row["pos"] or raw_position(raw)
                if not sid or not pos:
                    continue

                active.append(Player(
                    sid=sid,
                    name=name,
                    pos=pos,
                    fv=float(value_row["fv"]),
                    projection=projection_index.get(sid),
                ))

        # Deduplicate by stable Sleeper ID and retain first live row.
        unique = {}
        for p in active:
            unique.setdefault(p.sid, p)

        rosters[rid] = {
            "team_name": roster.get("team_name")
                or roster.get("owner_username")
                or f"Roster {rid}",
            "players": list(unique.values()),
        }

    coverage = 100.0 * (seen_players - len(missing_fv)) / seen_players if seen_players else 0.0
    if coverage < 95.0:
        raise RuntimeError(
            f"active-roster Fundamental Value coverage too low: {coverage:.2f}%"
        )
    return rosters, missing_fv, coverage


def selector_key(player: Player):
    # Canonical projection artifact chooses starters. K has no canonical
    # projection source, so Fundamental Value remains its explicit
    # selection fallback. Missing non-K projections sort behind known
    # projections, with FV only breaking missing-data ties.
    if player.pos == "K":
        return (1, player.fv, player.sid)
    if player.projection is None:
        return (0, player.fv, player.sid)
    return (1, player.projection, player.sid)


def optimize_lineup(players):
    remaining = list(players)
    starters = []

    def pop_best(eligible, count):
        nonlocal remaining
        for _ in range(count):
            candidates = [p for p in remaining if p.pos in eligible]
            if not candidates:
                break
            best = max(candidates, key=selector_key)
            remaining.remove(best)
            starters.append(best)

    for pos, count in DEDICATED:
        pop_best({pos}, count)
    for _label, eligible, count in FLEXES:
        pop_best(eligible, count)

    return starters, remaining


def optimize_legal(players, limit):
    # Stable-ID deduplication protects synthetic trade pools from
    # accidentally counting a player twice.
    by_sid = {}
    for p in players:
        by_sid[p.sid] = p
    unique = list(by_sid.values())

    starters, remaining = optimize_lineup(unique)
    bench_capacity = max(0, limit - len(starters))
    bench_sorted = sorted(remaining, key=lambda p: (p.fv, p.sid), reverse=True)
    bench = bench_sorted[:bench_capacity]
    cuts = bench_sorted[bench_capacity:]
    return {
        "starters": starters,
        "bench": bench,
        "cuts": cuts,
        "roster_size": len(starters) + len(bench),
    }


def sums(optimized):
    return (
        sum(p.fv for p in optimized["starters"]),
        sum(p.fv for p in optimized["bench"]),
    )


def utility_parts(before_players, after_players, limit):
    pre = optimize_legal(before_players, limit)
    post = optimize_legal(after_players, limit)
    pre_lineup, pre_bench = sums(pre)
    post_lineup, post_bench = sums(post)
    return {
        "lineup_delta": post_lineup - pre_lineup,
        "bench_delta": post_bench - pre_bench,
        "cuts": [p.name for p in post["cuts"]],
    }


def score(parts, weight):
    l = parts["lineup_delta"]
    b = parts["bench_delta"]
    return (1.0 - weight) * l + weight * b


def sign(value, eps=0.5):
    if value > eps:
        return 1
    if value < -eps:
        return -1
    return 0


def break_even(parts):
    # TU(w) = L + w(B-L). Solve TU(w)=0.
    l = parts["lineup_delta"]
    b = parts["bench_delta"]
    denom = b - l
    if abs(denom) < 1e-12:
        return None
    w = -l / denom
    return w if math.isfinite(w) else None


def remove_sids(players, sids):
    remove = set(sids)
    return [p for p in players if p.sid not in remove]


def best_fragmented_package(pool, target_fv, size):
    # Package pieces must each be materially weaker than the target,
    # and the package raw FV must land within ±10% of target FV.
    candidates = [
        p for p in pool
        if p.pos != "K"
        and p.fv > 0
        and p.fv <= target_fv * MAX_PIECE_TO_TARGET
    ]
    if len(candidates) < size:
        return None

    best = None
    best_err = math.inf
    for combo in itertools.combinations(candidates, size):
        total = sum(p.fv for p in combo)
        ratio = total / target_fv if target_fv > 0 else 0
        if ratio < RAW_BALANCE_LOW or ratio > RAW_BALANCE_HIGH:
            continue
        err = abs(1.0 - ratio)
        tie = tuple(sorted((p.sid for p in combo)))
        candidate = (err, tie, combo, total, ratio)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
            best_err = err
            if best_err < 1e-9:
                break

    if best is None:
        return None
    _err, _tie, combo, total, ratio = best
    return list(combo), total, ratio


def generate_scenarios(rosters, limit):
    all_fv = [
        p.fv
        for r in rosters.values()
        for p in r["players"]
        if p.pos != "K"
    ]
    target_floor = percentile(all_fv, TARGET_PERCENTILE)
    if target_floor is None:
        raise RuntimeError("could not compute target FV percentile")

    optimized = {
        rid: optimize_legal(r["players"], limit)
        for rid, r in rosters.items()
    }

    scenarios = []
    roster_ids = sorted(rosters)

    for rid_a in roster_ids:
        team_a = rosters[rid_a]
        # Only current optimized starters and only upper-value starters:
        # this intentionally targets concentration-vs-depth situations.
        targets = [
            p for p in optimized[rid_a]["starters"]
            if p.pos != "K" and p.fv >= target_floor
        ]

        for rid_b in roster_ids:
            if rid_b == rid_a:
                continue
            team_b = rosters[rid_b]

            for target in targets:
                for package_size in (2, 3):
                    found = best_fragmented_package(
                        team_b["players"],
                        target.fv,
                        package_size,
                    )
                    if not found:
                        continue

                    package, package_total, ratio = found
                    package_sids = [p.sid for p in package]

                    after_a = (
                        remove_sids(team_a["players"], [target.sid])
                        + package
                    )
                    after_b = (
                        remove_sids(team_b["players"], package_sids)
                        + [target]
                    )

                    parts_a = utility_parts(team_a["players"], after_a, limit)
                    parts_b = utility_parts(team_b["players"], after_b, limit)

                    scenarios.append({
                        "type": f"1_for_{package_size}",
                        "fragmented_receiver_roster_id": rid_a,
                        "fragmented_receiver_team": team_a["team_name"],
                        "consolidator_roster_id": rid_b,
                        "consolidator_team": team_b["team_name"],
                        "target": {
                            "sleeper_id": target.sid,
                            "player": target.name,
                            "pos": target.pos,
                            "fv": round(target.fv, 3),
                        },
                        "package": [
                            {
                                "sleeper_id": p.sid,
                                "player": p.name,
                                "pos": p.pos,
                                "fv": round(p.fv, 3),
                            }
                            for p in package
                        ],
                        "raw_package_fv": round(package_total, 3),
                        "raw_package_to_target_ratio": round(ratio, 6),
                        "fragmented_receiver": {
                            "lineup_delta": round(parts_a["lineup_delta"], 3),
                            "bench_delta": round(parts_a["bench_delta"], 3),
                            "implied_cuts": parts_a["cuts"],
                            "break_even_weight": break_even(parts_a),
                        },
                        "consolidator": {
                            "lineup_delta": round(parts_b["lineup_delta"], 3),
                            "bench_delta": round(parts_b["bench_delta"], 3),
                            "implied_cuts": parts_b["cuts"],
                            "break_even_weight": break_even(parts_b),
                        },
                    })

    return scenarios, target_floor


def summarize_side(scenarios, side_key):
    summary = {}
    for w in WEIGHTS:
        vals = [score(s[side_key], w) for s in scenarios]
        positives = sum(1 for v in vals if sign(v) > 0)
        negatives = sum(1 for v in vals if sign(v) < 0)
        zeros = len(vals) - positives - negatives
        summary[f"{w:.2f}"] = {
            "scenario_count": len(vals),
            "positive_pct": round(100 * positives / len(vals), 2) if vals else None,
            "negative_pct": round(100 * negatives / len(vals), 2) if vals else None,
            "neutral_pct": round(100 * zeros / len(vals), 2) if vals else None,
            "median_team_utility": round(statistics.median(vals), 3) if vals else None,
            "mean_team_utility": round(statistics.fmean(vals), 3) if vals else None,
        }
    return summary


def stability_summary(scenarios, side_key):
    any_flip = 0
    core_flip = 0
    current_flip_vs_edges = 0
    break_evens = []

    for s in scenarios:
        parts = s[side_key]
        signs = [sign(score(parts, w)) for w in WEIGHTS]
        nonzero = {x for x in signs if x != 0}
        if len(nonzero) > 1:
            any_flip += 1

        core_signs = {
            sign(score(parts, w))
            for w in (0.10, 0.15, 0.20)
            if sign(score(parts, w)) != 0
        }
        if len(core_signs) > 1:
            core_flip += 1

        current = sign(score(parts, 0.15))
        edge_signs = {sign(score(parts, 0.05)), sign(score(parts, 0.30))}
        if current != 0 and any(x != 0 and x != current for x in edge_signs):
            current_flip_vs_edges += 1

        be = parts.get("break_even_weight")
        if be is not None and 0.0 <= be <= 0.50:
            break_evens.append(float(be))

    n = len(scenarios)
    return {
        "scenario_count": n,
        "sign_flip_anywhere_0_to_0_30_count": any_flip,
        "sign_flip_anywhere_0_to_0_30_pct": round(100 * any_flip / n, 2) if n else None,
        "sign_flip_core_0_10_to_0_20_count": core_flip,
        "sign_flip_core_0_10_to_0_20_pct": round(100 * core_flip / n, 2) if n else None,
        "current_0_15_disagrees_with_0_05_or_0_30_count": current_flip_vs_edges,
        "current_0_15_disagrees_with_0_05_or_0_30_pct": round(
            100 * current_flip_vs_edges / n, 2
        ) if n else None,
        "break_even_weight_in_0_to_0_50_count": len(break_evens),
        "break_even_weight_p10": round(percentile(break_evens, 0.10), 4)
            if break_evens else None,
        "break_even_weight_median": round(percentile(break_evens, 0.50), 4)
            if break_evens else None,
        "break_even_weight_p90": round(percentile(break_evens, 0.90), 4)
            if break_evens else None,
    }


def write_report(result):
    fw = result["weight_summary"]["fragmented_receiver"]
    cw = result["weight_summary"]["consolidator"]
    fs = result["stability"]["fragmented_receiver"]
    cs = result["stability"]["consolidator"]

    lines = [
        "# Team Utility Bench-Weight Sensitivity V1",
        "",
        "**Status: RESEARCH ONLY — no production consumer changed.**",
        "",
        "This study does **not** choose a new bench weight. It measures how much "
        "the Team Utility conclusion moves when the unvalidated bench coefficient "
        "is varied while legal-roster enforcement stays fixed.",
        "",
        "## Inputs and guardrails",
        "",
        f"- Deployed bench weight: `{result['deployed_bench_weight']:.2f}` (unchanged)",
        f"- Legal active-roster limit: `{result['active_roster_limit']}`",
        f"- Tested weights: {', '.join(f'`{w:.2f}`' for w in WEIGHTS)}",
        f"- Current active-roster FV coverage: `{result['coverage']['active_fv_coverage_pct']:.2f}%`",
        f"- Teams: `{result['coverage']['team_count']}`",
        f"- Synthetic raw-balanced scenarios: `{result['scenario_count']}`",
        f"- 1-for-2 scenarios: `{result['scenario_counts_by_type'].get('1_for_2', 0)}`",
        f"- 1-for-3 scenarios: `{result['scenario_counts_by_type'].get('1_for_3', 0)}`",
        f"- Concentrated target minimum FV (league active FV p60): `{result['target_fv_floor']:.0f}`",
        "",
        "Synthetic scenarios intentionally pair a current optimized starter with "
        "2 or 3 individually weaker players from another real roster whose raw "
        "Fundamental Value sum is within ±10% of the starter. This isolates "
        "lineup concentration vs. legal-roster depth without using Package Adjustment.",
        "",
        "## Fragmented receiver sensitivity",
        "",
        "| Bench weight | Positive TU | Negative TU | Median TU |",
        "|---:|---:|---:|---:|",
    ]
    for w in WEIGHTS:
        row = fw[f"{w:.2f}"]
        lines.append(
            f"| {w:.2f} | {row['positive_pct']:.1f}% | "
            f"{row['negative_pct']:.1f}% | {row['median_team_utility']:.0f} |"
        )

    lines += [
        "",
        f"- Sign flips anywhere from 0.00–0.30: "
        f"**{fs['sign_flip_anywhere_0_to_0_30_pct']:.1f}%**",
        f"- Sign flips inside the core 0.10–0.20 band: "
        f"**{fs['sign_flip_core_0_10_to_0_20_pct']:.1f}%**",
        f"- Current 0.15 disagrees with either 0.05 or 0.30: "
        f"**{fs['current_0_15_disagrees_with_0_05_or_0_30_pct']:.1f}%**",
        "",
        "## Consolidator sensitivity",
        "",
        "| Bench weight | Positive TU | Negative TU | Median TU |",
        "|---:|---:|---:|---:|",
    ]
    for w in WEIGHTS:
        row = cw[f"{w:.2f}"]
        lines.append(
            f"| {w:.2f} | {row['positive_pct']:.1f}% | "
            f"{row['negative_pct']:.1f}% | {row['median_team_utility']:.0f} |"
        )

    lines += [
        "",
        f"- Sign flips anywhere from 0.00–0.30: "
        f"**{cs['sign_flip_anywhere_0_to_0_30_pct']:.1f}%**",
        f"- Sign flips inside the core 0.10–0.20 band: "
        f"**{cs['sign_flip_core_0_10_to_0_20_pct']:.1f}%**",
        "",
        "## Interpretation rule",
        "",
        "There is deliberately **no `recommended_weight` field**. Without package "
        "preference or prospective trade labels, choosing the weight that makes "
        "one side win more often would be circular. The correct use of this report "
        "is to determine whether `0.15` is a stable placeholder and how strongly "
        "future Package Adjustment research must control for Team Utility weight.",
        "",
        "## Production impact",
        "",
        "- `TU_BENCH_WEIGHT` changed: **NO**",
        "- Fundamental Value changed: **NO**",
        "- Market Value changed: **NO**",
        "- Trade verdict changed by this research job: **NO**",
        "- Package Adjustment deployed: **NO**",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def run_selftest():
    assert sign(10) == 1
    assert sign(-10) == -1
    assert sign(0) == 0

    # L=-100, B=100 => -100 + w(200) = 0 at w=.5
    parts = {"lineup_delta": -100.0, "bench_delta": 100.0}
    assert abs(break_even(parts) - 0.5) < 1e-12
    assert score(parts, 0.0) == -100
    assert score(parts, 0.5) == 0

    # Fragmented package search must enforce raw-balance and piece gap.
    pool = [
        Player("1", "A", "WR", 60, 1),
        Player("2", "B", "RB", 40, 1),
        Player("3", "C", "TE", 10, 1),
    ]
    found = best_fragmented_package(pool, 100, 2)
    assert found is not None
    package, total, ratio = found
    assert {p.sid for p in package} == {"1", "2"}
    assert total == 100
    assert ratio == 1.0

    print("Team Utility bench-weight sensitivity self-test passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    deployed_weight, active_limit = parse_deployed_constants()
    value_index, value_doc = build_value_index()
    projection_index, projection_doc = build_projection_index()
    rosters, missing_fv, fv_coverage = build_rosters(
        value_index,
        projection_index,
    )

    scenarios, target_floor = generate_scenarios(rosters, active_limit)
    if len(scenarios) < 100:
        raise RuntimeError(
            f"too few sensitivity scenarios generated: {len(scenarios)}"
        )

    by_type = {}
    for s in scenarios:
        by_type[s["type"]] = by_type.get(s["type"], 0) + 1

    result = {
        "schema_version": 1,
        "status": "research_only",
        "consumer_changed": False,
        "bench_weight_changed": False,
        "package_adjustment_deployed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "legal_roster_raw_balanced_stud_for_depth_sensitivity_v1",
        "deployed_bench_weight": deployed_weight,
        "active_roster_limit": active_limit,
        "tested_weights": list(WEIGHTS),
        "scenario_generation": {
            "raw_package_to_target_min": RAW_BALANCE_LOW,
            "raw_package_to_target_max": RAW_BALANCE_HIGH,
            "max_individual_piece_to_target": MAX_PIECE_TO_TARGET,
            "target_active_fv_percentile_floor": TARGET_PERCENTILE,
            "uses_current_optimized_starters_as_targets": True,
            "package_sizes": [2, 3],
            "uses_real_current_roster_players": True,
            "uses_outcome_labels": False,
        },
        "coverage": {
            "team_count": len(rosters),
            "active_fv_coverage_pct": round(fv_coverage, 3),
            "active_missing_fv": missing_fv,
            "fundamental_universe_player_count": int(
                value_doc.get("counts", {}).get("player_count", 0)
            ),
            "lineup_projection_player_count": int(
                projection_doc.get("player_count", len(projection_index))
            ),
        },
        "target_fv_floor": round(target_floor, 3),
        "scenario_count": len(scenarios),
        "scenario_counts_by_type": by_type,
        "weight_summary": {
            "fragmented_receiver": summarize_side(
                scenarios, "fragmented_receiver"
            ),
            "consolidator": summarize_side(
                scenarios, "consolidator"
            ),
        },
        "stability": {
            "fragmented_receiver": stability_summary(
                scenarios, "fragmented_receiver"
            ),
            "consolidator": stability_summary(
                scenarios, "consolidator"
            ),
        },
        # Keep a bounded audit sample instead of bloating the artifact
        # with every generated scenario.
        "audit_sample": scenarios[:100],
        "conclusion_policy": (
            "Descriptive sensitivity only. No weight is recommended "
            "without external preference/prospective trade labels."
        ),
    }

    if args.write:
        OUT_JSON.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_report(result)
        print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
        print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

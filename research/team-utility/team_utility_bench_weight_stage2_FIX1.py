#!/usr/bin/env python3
"""Team Utility bench-weight calibration audit, Stage 2.

Research-only 2026 roster + decision-sensitivity audit.

Stage 1 found that the deployed global bench weight (0.15) nearly exactly
matches this league's 2024-2025 empirical four-week active-bench future-start
share (15.25%; clustered 95% band 14.42%-16.14%). Stage 2 does NOT replace
that empirical anchor. It asks whether the 2026 roster architecture is
decision-sensitive enough that a modest change around 0.15 would materially
alter Team Utility recommendations.

Why this is not a historical trade backtest
-------------------------------------------
data/trade_history.json was intentionally built for pick-value calibration:
it contains only pick-involving completed trades and does not preserve exact
pre-trade rosters or taxi/reserve slot state. This audit therefore does not
pretend those records can identify the historically "correct" Team Utility
coefficient.

Instead Stage 2 uses:
* all 12 current 2026 league rosters;
* real current starters / bench / taxi / reserve_ir slot status;
* production-parity Fundamental Values, including live-roster merge rows;
* refreshed stable-Sleeper-ID Team Utility lineup projections;
* the exact production starter-selection rule:
    projection first for non-K,
    projected > missing,
    FV tie/fallback,
    K by FV,
    taxi/reserve_ir not starter eligible;
* incoming assets default to active bench / starter eligible.

Decision-sensitivity tests
--------------------------
A) Marginal acquisition universe:
   Every rostered player is hypothetically added to each of the other 11
   rosters. For each recipient, compare acquisition rankings at each candidate
   w against production w=0.15.

B) FV-balanced one-for-one swap universe:
   For every pair of real teams, test real-player swaps whose Fundamental
   Values are reasonably close. Evaluate Team Utility for BOTH sides and
   measure how often the sign pattern changes relative to w=0.15.

No production files are changed.

Outputs
-------
research/team-utility/team_utility_bench_weight_stage2.json
research/team-utility/team_utility_bench_weight_stage2.md

Usage
-----
python3 research/team-utility/team_utility_bench_weight_stage2.py --selftest
python3 research/team-utility/team_utility_bench_weight_stage2.py --write
python3 research/team-utility/team_utility_bench_weight_stage2.py --check
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
ROSTERS = ROOT / "data" / "league_rosters.json"
PROJECTION_ARTIFACT = (
    ROOT / "scripts" / "artifacts" / "generated" / "team_utility_lineup_projections.json"
)
STAGE1 = ROOT / "research" / "team-utility" / "team_utility_bench_weight_audit.json"
OUT_JSON = ROOT / "research" / "team-utility" / "team_utility_bench_weight_stage2.json"
OUT_MD = ROOT / "research" / "team-utility" / "team_utility_bench_weight_stage2.md"

CANDIDATE_WEIGHTS = (0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50)
BASELINE_W = 0.15
TOP_K = (10, 25)
BALANCED_FV_RATIO_MAX = 1.15
BALANCED_FV_ABS_MAX = 1200.0
EXPECTED_TEAMS = 12
EXPECTED_STARTERS = 17

# Repo-only helpers are loaded lazily. This keeps --selftest fully standalone,
# so the downloadable script can be syntax/self-tested outside the repository.
_HELPERS = None

def get_repo_helpers():
    global _HELPERS
    if _HELPERS is not None:
        return _HELPERS

    sys.path.insert(0, str(ROOT / "research" / "team-utility"))
    sys.path.insert(0, str(ROOT / "scripts" / "validation"))
    starter_audit = importlib.import_module("team_utility_starter_objective_audit")
    snapshot_values = importlib.import_module("snapshot_values")
    _HELPERS = (starter_audit, snapshot_values)
    return _HELPERS


@dataclass(frozen=True)
class Player:
    player_id: str
    key: str
    name: str
    pos: str
    roster_slot: str
    fundamental: float
    projection: float | None

    @property
    def starter_eligible(self) -> bool:
        return self.roster_slot not in {"taxi", "reserve_ir"}


def round_js(x: float) -> int:
    # Team Utility deltas can be negative. JS Math.round() behavior for
    # negative halves differs from Python round(). floor(x + 0.5) matches JS
    # for finite numbers in this audit.
    return math.floor(x + 0.5)


def utility_from_deltas(lineup_delta: float, bench_delta: float, w: float) -> int:
    return round_js((1.0 - w) * lineup_delta + w * bench_delta)


def lineup_compare_key(p: Player) -> tuple:
    if p.pos == "K":
        return (0, 0.0, -p.fundamental, p.key)

    has = p.projection is not None and math.isfinite(p.projection)
    if has:
        # sorted ascending: projected rows first, highest projection first,
        # then higher FV, then stable key.
        return (0, -float(p.projection), -p.fundamental, p.key)

    # Missing projection is behind any projected non-K player. FV fallback
    # orders missing-vs-missing.
    return (1, 0.0, -p.fundamental, p.key)


def optimize_lineup(players: list[Player]) -> dict[str, list[Player]]:
    remaining = sorted(list(players), key=lineup_compare_key)
    starters: list[Player] = []

    dedicated = (
        ("QB", 1), ("RB", 2), ("WR", 2), ("TE", 1), ("K", 1),
        ("DL", 2), ("LB", 2), ("DB", 2),
    )
    flexes = (
        ({"RB", "WR", "TE"}, 1),
        ({"QB", "RB", "WR", "TE"}, 1),
        ({"DL", "LB", "DB"}, 2),
    )

    def pop_first(predicate) -> bool:
        nonlocal remaining
        for idx, player in enumerate(remaining):
            if player.starter_eligible and predicate(player):
                starters.append(player)
                remaining.pop(idx)
                return True
        return False

    for pos, count in dedicated:
        for _ in range(count):
            if not pop_first(lambda p, pos=pos: p.pos == pos):
                break

    for eligible, count in flexes:
        for _ in range(count):
            if not pop_first(lambda p, eligible=eligible: p.pos in eligible):
                break

    return {"starters": starters, "bench": remaining}


def sum_fv(players: list[Player]) -> float:
    return sum(p.fundamental for p in players)


def calculate_deltas(pre: list[Player], post: list[Player]) -> tuple[float, float]:
    pre_opt = optimize_lineup(pre)
    post_opt = optimize_lineup(post)
    lineup_delta = sum_fv(post_opt["starters"]) - sum_fv(pre_opt["starters"])
    bench_delta = sum_fv(post_opt["bench"]) - sum_fv(pre_opt["bench"])
    return lineup_delta, bench_delta


def rank_values(values: list[float]) -> list[float]:
    """Average ranks for ties, ascending values -> ascending ranks."""
    indexed = sorted(enumerate(values), key=lambda t: t[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j - 1) / 2.0 + 1.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denom = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    if denom == 0:
        return None
    return sum(x*y for x, y in zip(dx, dy)) / denom


def spearman(xs: list[float], ys: list[float]) -> float | None:
    return pearson(rank_values(xs), rank_values(ys))


def overlap_fraction(a: list[str], b: list[str], k: int) -> float:
    sa = set(a[:k])
    sb = set(b[:k])
    if not sa:
        return 1.0
    return len(sa & sb) / len(sa)


def sign_bucket(value: int) -> int:
    return 1 if value > 0 else (-1 if value < 0 else 0)


def normalize_name(value: str) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'\u2019-]", "", s)
    return re.sub(r"\s+", " ", s)


def load_inputs():
    starter_audit, snapshot_values = get_repo_helpers()

    for path in (INDEX, ROSTERS, PROJECTION_ARTIFACT, STAGE1):
        if not path.exists():
            raise RuntimeError(f"missing required input: {path.relative_to(ROOT)}")

    roster_doc = json.loads(ROSTERS.read_text(encoding="utf-8"))
    projection_doc = json.loads(PROJECTION_ARTIFACT.read_text(encoding="utf-8"))
    stage1 = json.loads(STAGE1.read_text(encoding="utf-8"))

    if projection_doc.get("schema_version") != 1:
        raise RuntimeError("unexpected Team Utility projection schema")
    if int(projection_doc.get("season") or 0) != 2026:
        raise RuntimeError("unexpected Team Utility projection season")
    if int(projection_doc.get("player_count") or 0) < 400:
        raise RuntimeError("projection artifact coverage unexpectedly small")

    index_text = INDEX.read_text(encoding="utf-8")
    m = re.search(r"const\s+TU_BENCH_WEIGHT\s*=\s*([0-9.]+)\s*;", index_text)
    if not m:
        raise RuntimeError("could not parse TU_BENCH_WEIGHT")
    current_w = float(m.group(1))
    if abs(current_w - BASELINE_W) > 1e-12:
        raise RuntimeError(
            f"Stage 2 expected production bench weight {BASELINE_W}, found {current_w}"
        )

    if stage1.get("status") != "PASS":
        raise RuntimeError("Stage 1 bench-weight audit is not PASS")
    if abs(float(stage1.get("current_production_bench_weight")) - BASELINE_W) > 1e-12:
        raise RuntimeError("Stage 1 was not calibrated against production 0.15")

    base_cfg = snapshot_values.load_from_html(INDEX)
    cfg = starter_audit.merge_live_league_into_cfg(base_cfg, roster_doc)
    fundamental_by_key = snapshot_values.compute_all_values(cfg)

    projections_by_id = {
        str(pid): float(row["projection"])
        for pid, row in (projection_doc.get("players") or {}).items()
        if isinstance(row, dict)
        and isinstance(row.get("projection"), (int, float))
        and math.isfinite(float(row["projection"]))
    }

    return roster_doc, cfg, fundamental_by_key, projections_by_id, stage1


def build_league_players(
    roster_doc: dict,
    cfg: dict,
    fundamental_by_key: dict,
    projections_by_id: dict[str, float],
) -> tuple[dict[int, list[Player]], list[dict]]:
    starter_audit, _ = get_repo_helpers()
    player_db = cfg["player_db"]
    out: dict[int, list[Player]] = {}
    unresolved: list[dict] = []
    seen_ids: dict[str, int] = {}

    for roster in roster_doc.get("rosters", []):
        rid = int(roster["roster_id"])
        players: list[Player] = []

        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for raw in roster.get(slot, []) or []:
                pid = str(raw.get("player_id") or "")
                raw_key = normalize_name(raw.get("name", ""))
                key = starter_audit.resolve_existing_key(
                    raw_key,
                    player_db,
                    cfg.get("aliases", {}),
                    cfg.get("aliases_reverse", {}),
                )
                info = player_db.get(key)
                fv_row = fundamental_by_key.get(key)

                if not info or not fv_row:
                    unresolved.append({
                        "roster_id": rid,
                        "player_id": pid,
                        "player": raw.get("name"),
                        "slot": slot,
                        "reason": "missing production-parity FV row",
                    })
                    continue

                if pid in seen_ids and seen_ids[pid] != rid:
                    raise RuntimeError(
                        f"player_id {pid} appears on multiple rosters: "
                        f"{seen_ids[pid]} and {rid}"
                    )
                seen_ids[pid] = rid

                pos = str(info["pos"])
                projection = None if pos == "K" else projections_by_id.get(pid)

                players.append(Player(
                    player_id=pid,
                    key=key,
                    name=raw.get("name") or key,
                    pos=pos,
                    roster_slot=slot,
                    fundamental=float(fv_row["value"]),
                    projection=projection,
                ))

        out[rid] = players

    return out, unresolved


def validate_lineups(league: dict[int, list[Player]]) -> dict[str, Any]:
    if len(league) != EXPECTED_TEAMS:
        raise RuntimeError(f"expected {EXPECTED_TEAMS} teams, found {len(league)}")

    rows = []
    for rid, players in sorted(league.items()):
        optimized = optimize_lineup(players)
        starters = optimized["starters"]
        missing_non_k = sum(
            1 for p in starters
            if p.pos != "K" and p.projection is None
        )
        taxi_starters = sum(
            1 for p in starters if p.roster_slot in {"taxi", "reserve_ir"}
        )

        if len(starters) != EXPECTED_STARTERS:
            raise RuntimeError(
                f"roster {rid}: expected {EXPECTED_STARTERS} starters, "
                f"got {len(starters)}"
            )
        if missing_non_k != 0:
            raise RuntimeError(
                f"roster {rid}: projection-selected lineup has "
                f"{missing_non_k} missing non-K projection(s)"
            )
        if taxi_starters != 0:
            raise RuntimeError(
                f"roster {rid}: taxi/reserve player selected as starter"
            )

        rows.append({
            "roster_id": rid,
            "roster_player_count": len(players),
            "starter_count": len(starters),
            "missing_non_k_projection_starters": missing_non_k,
            "taxi_or_reserve_starters": taxi_starters,
        })

    return {"teams": rows}


def acquisition_scenarios(
    league: dict[int, list[Player]],
) -> list[dict[str, Any]]:
    all_players = [
        (source_rid, p)
        for source_rid, players in league.items()
        for p in players
    ]

    rows = []
    for recipient_rid, recipient_players in sorted(league.items()):
        for source_rid, asset in all_players:
            if source_rid == recipient_rid:
                continue

            incoming = Player(
                player_id=asset.player_id,
                key=asset.key,
                name=asset.name,
                pos=asset.pos,
                roster_slot="bench",  # production policy for incoming assets
                fundamental=asset.fundamental,
                projection=asset.projection,
            )
            lineup_delta, bench_delta = calculate_deltas(
                recipient_players,
                recipient_players + [incoming],
            )

            rows.append({
                "recipient_roster_id": recipient_rid,
                "source_roster_id": source_rid,
                "player_id": asset.player_id,
                "player": asset.name,
                "pos": asset.pos,
                "fv": asset.fundamental,
                "lineup_delta": lineup_delta,
                "bench_delta": bench_delta,
            })

    return rows


def acquisition_sensitivity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_team: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_team.setdefault(row["recipient_roster_id"], []).append(row)

    baseline_rankings: dict[int, list[str]] = {}
    baseline_values: dict[int, dict[str, int]] = {}

    for rid, team_rows in by_team.items():
        vals = {
            r["player_id"]: utility_from_deltas(
                r["lineup_delta"], r["bench_delta"], BASELINE_W
            )
            for r in team_rows
        }
        baseline_values[rid] = vals
        baseline_rankings[rid] = [
            r["player_id"]
            for r in sorted(
                team_rows,
                key=lambda r: (
                    -vals[r["player_id"]],
                    -r["fv"],
                    r["player_id"],
                ),
            )
        ]

    result = {}
    for w in CANDIDATE_WEIGHTS:
        per_team = []
        for rid, team_rows in sorted(by_team.items()):
            current_vals = [
                utility_from_deltas(r["lineup_delta"], r["bench_delta"], w)
                for r in team_rows
            ]
            baseline_vals = [
                baseline_values[rid][r["player_id"]]
                for r in team_rows
            ]
            rho = spearman(current_vals, baseline_vals)

            ranking = [
                r["player_id"]
                for r in sorted(
                    team_rows,
                    key=lambda r: (
                        -utility_from_deltas(
                            r["lineup_delta"], r["bench_delta"], w
                        ),
                        -r["fv"],
                        r["player_id"],
                    ),
                )
            ]

            row = {
                "roster_id": rid,
                "spearman_vs_0_15": rho,
            }
            for k in TOP_K:
                row[f"top_{k}_overlap_vs_0_15"] = overlap_fraction(
                    baseline_rankings[rid], ranking, k
                )
            per_team.append(row)

        result[f"{w:.2f}"] = {
            "median_spearman_vs_0_15": statistics.median(
                r["spearman_vs_0_15"] for r in per_team
                if r["spearman_vs_0_15"] is not None
            ),
            "min_spearman_vs_0_15": min(
                r["spearman_vs_0_15"] for r in per_team
                if r["spearman_vs_0_15"] is not None
            ),
            "median_top_10_overlap_vs_0_15": statistics.median(
                r["top_10_overlap_vs_0_15"] for r in per_team
            ),
            "min_top_10_overlap_vs_0_15": min(
                r["top_10_overlap_vs_0_15"] for r in per_team
            ),
            "median_top_25_overlap_vs_0_15": statistics.median(
                r["top_25_overlap_vs_0_15"] for r in per_team
            ),
            "min_top_25_overlap_vs_0_15": min(
                r["top_25_overlap_vs_0_15"] for r in per_team
            ),
            "per_team": per_team,
        }

    return result


def balanced_swap_scenarios(
    league: dict[int, list[Player]],
) -> list[dict[str, Any]]:
    team_ids = sorted(league)
    rows = []

    for i, rid_a in enumerate(team_ids):
        for rid_b in team_ids[i + 1:]:
            roster_a = league[rid_a]
            roster_b = league[rid_b]

            for a in roster_a:
                for b in roster_b:
                    lo = min(a.fundamental, b.fundamental)
                    hi = max(a.fundamental, b.fundamental)
                    if lo <= 0:
                        continue
                    ratio = hi / lo
                    abs_diff = hi - lo
                    if (
                        ratio > BALANCED_FV_RATIO_MAX
                        or abs_diff > BALANCED_FV_ABS_MAX
                    ):
                        continue

                    incoming_b = Player(
                        player_id=b.player_id,
                        key=b.key,
                        name=b.name,
                        pos=b.pos,
                        roster_slot="bench",
                        fundamental=b.fundamental,
                        projection=b.projection,
                    )
                    incoming_a = Player(
                        player_id=a.player_id,
                        key=a.key,
                        name=a.name,
                        pos=a.pos,
                        roster_slot="bench",
                        fundamental=a.fundamental,
                        projection=a.projection,
                    )

                    post_a = [p for p in roster_a if p.player_id != a.player_id]
                    post_a.append(incoming_b)
                    post_b = [p for p in roster_b if p.player_id != b.player_id]
                    post_b.append(incoming_a)

                    la, ba = calculate_deltas(roster_a, post_a)
                    lb, bb = calculate_deltas(roster_b, post_b)

                    rows.append({
                        "roster_a": rid_a,
                        "roster_b": rid_b,
                        "asset_a_id": a.player_id,
                        "asset_a": a.name,
                        "asset_a_fv": a.fundamental,
                        "asset_b_id": b.player_id,
                        "asset_b": b.name,
                        "asset_b_fv": b.fundamental,
                        "fv_ratio": ratio,
                        "fv_abs_diff": abs_diff,
                        "a_lineup_delta": la,
                        "a_bench_delta": ba,
                        "b_lineup_delta": lb,
                        "b_bench_delta": bb,
                    })

    if len(rows) < 1000:
        raise RuntimeError(
            f"balanced-swap universe unexpectedly small: {len(rows)}"
        )
    return rows


def swap_sensitivity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline_patterns = []
    for r in rows:
        ua = utility_from_deltas(
            r["a_lineup_delta"], r["a_bench_delta"], BASELINE_W
        )
        ub = utility_from_deltas(
            r["b_lineup_delta"], r["b_bench_delta"], BASELINE_W
        )
        baseline_patterns.append((sign_bucket(ua), sign_bucket(ub)))

    result = {}
    for w in CANDIDATE_WEIGHTS:
        changed = 0
        side_flips = 0
        mutual_positive = 0
        mutual_negative = 0
        split = 0
        zero_involved = 0

        for idx, r in enumerate(rows):
            ua = utility_from_deltas(
                r["a_lineup_delta"], r["a_bench_delta"], w
            )
            ub = utility_from_deltas(
                r["b_lineup_delta"], r["b_bench_delta"], w
            )
            pattern = (sign_bucket(ua), sign_bucket(ub))
            base = baseline_patterns[idx]

            if pattern != base:
                changed += 1
            side_flips += int(pattern[0] != base[0])
            side_flips += int(pattern[1] != base[1])

            if 0 in pattern:
                zero_involved += 1
            elif pattern == (1, 1):
                mutual_positive += 1
            elif pattern == (-1, -1):
                mutual_negative += 1
            else:
                split += 1

        n = len(rows)
        result[f"{w:.2f}"] = {
            "scenario_count": n,
            "sign_pattern_change_vs_0_15_count": changed,
            "sign_pattern_change_vs_0_15_pct": 100.0 * changed / n,
            "side_sign_flip_vs_0_15_count": side_flips,
            "side_sign_flip_vs_0_15_pct_of_sides": 100.0 * side_flips / (2 * n),
            "mutual_positive_pct": 100.0 * mutual_positive / n,
            "mutual_negative_pct": 100.0 * mutual_negative / n,
            "split_sign_pct": 100.0 * split / n,
            "zero_involved_pct": 100.0 * zero_involved / n,
        }

    return result


def bench_capital_profile(league: dict[int, list[Player]]) -> dict[str, Any]:
    rows = []
    for rid, players in sorted(league.items()):
        starter_opt = optimize_lineup(players)
        starter_ids = {p.player_id for p in starter_opt["starters"]}

        active_bench_fv = sum(
            p.fundamental for p in players
            if p.player_id not in starter_ids and p.roster_slot in {"starters", "bench"}
        )
        taxi_fv = sum(
            p.fundamental for p in players if p.roster_slot == "taxi"
        )
        reserve_fv = sum(
            p.fundamental for p in players if p.roster_slot == "reserve_ir"
        )
        total_nonstarter_fv = active_bench_fv + taxi_fv + reserve_fv

        rows.append({
            "roster_id": rid,
            "active_bench_fv": active_bench_fv,
            "taxi_fv": taxi_fv,
            "reserve_ir_fv": reserve_fv,
            "total_nonstarter_fv": total_nonstarter_fv,
            "taxi_reserve_share_of_nonstarter_fv": (
                (taxi_fv + reserve_fv) / total_nonstarter_fv
                if total_nonstarter_fv else 0.0
            ),
        })

    return {
        "per_team": rows,
        "median_taxi_reserve_share_of_nonstarter_fv": statistics.median(
            r["taxi_reserve_share_of_nonstarter_fv"] for r in rows
        ),
        "max_taxi_reserve_share_of_nonstarter_fv": max(
            r["taxi_reserve_share_of_nonstarter_fv"] for r in rows
        ),
    }


def decision(stage1: dict, acq: dict, swaps: dict) -> dict[str, Any]:
    stage1_target = float(
        stage1["stage1_interpretation"]["primary_empirical_target"]
    )
    stage1_ci = stage1["horizons"]["4"]["bootstrap_team_season_clustered"][
        "unconditional_future_start_share"
    ]

    anchor_supported = (
        float(stage1_ci["p025"]) <= BASELINE_W <= float(stage1_ci["p975"])
    )

    local_weights = ("0.10", "0.20")
    local_top10 = min(
        acq[w]["median_top_10_overlap_vs_0_15"] for w in local_weights
    )
    local_rho = min(
        acq[w]["median_spearman_vs_0_15"] for w in local_weights
    )
    local_swap_flip = max(
        swaps[w]["sign_pattern_change_vs_0_15_pct"] for w in local_weights
    )

    # Conservative rule:
    # - Stage 1 must empirically support 0.15.
    # - Acquisition rankings must remain strongly similar at +/-0.05.
    # - Less than 10% of balanced swap sign-patterns may change at +/-0.05.
    locally_stable = (
        local_top10 >= 0.80
        and local_rho >= 0.95
        and local_swap_flip < 10.0
    )

    if anchor_supported and locally_stable:
        recommendation = "KEEP_0_15"
        rationale = (
            "Stage 1 empirically anchors the coefficient near 0.15 and "
            "Stage 2 shows 2026 Team Utility decisions are locally robust "
            "to +/-0.05 changes. There is no evidence-based reason to move "
            "the global coefficient."
        )
    elif anchor_supported:
        recommendation = "KEEP_0_15_FLAG_CONTEXTUAL_WEIGHT_RESEARCH"
        rationale = (
            "Stage 1 empirically supports 0.15, but 2026 decision sensitivity "
            "is high enough that a single global bench coefficient may be too "
            "coarse. Keep 0.15 rather than moving it, and research context- or "
            "slot-specific weighting before any production change."
        )
    else:
        recommendation = "NO_CHANGE_INCONCLUSIVE"
        rationale = (
            "The Stage-1 empirical anchor no longer cleanly supports 0.15. "
            "Do not change production from sensitivity evidence alone."
        )

    return {
        "recommendation": recommendation,
        "production_change_authorized": False,
        "stage1_primary_target": stage1_target,
        "stage1_95pct_band": [
            float(stage1_ci["p025"]),
            float(stage1_ci["p975"]),
        ],
        "stage1_anchor_supports_0_15": anchor_supported,
        "local_0_10_0_20_min_median_top10_overlap": local_top10,
        "local_0_10_0_20_min_median_spearman": local_rho,
        "local_0_10_0_20_max_swap_sign_pattern_flip_pct": local_swap_flip,
        "local_stability_rule_passed": locally_stable,
        "rationale": rationale,
    }


def round_recursive(obj: Any) -> Any:
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, list):
        return [round_recursive(x) for x in obj]
    if isinstance(obj, dict):
        return {k: round_recursive(v) for k, v in obj.items()}
    return obj


def build_result() -> dict[str, Any]:
    roster_doc, cfg, fv, projections, stage1 = load_inputs()
    league, unresolved = build_league_players(
        roster_doc, cfg, fv, projections
    )

    if unresolved:
        sample = unresolved[:10]
        raise RuntimeError(
            "current roster valuation universe has unresolved rows: "
            f"{len(unresolved)}; sample={sample}"
        )

    lineup_validation = validate_lineups(league)

    acquisitions = acquisition_scenarios(league)
    acquisition_results = acquisition_sensitivity(acquisitions)

    swaps = balanced_swap_scenarios(league)
    swap_results = swap_sensitivity(swaps)

    profile = bench_capital_profile(league)
    recommendation = decision(stage1, acquisition_results, swap_results)

    result = {
        "schema_version": 1,
        "audit": "team_utility_bench_weight_stage2",
        "status": "PASS",
        "production_bench_weight": BASELINE_W,
        "candidate_weights": list(CANDIDATE_WEIGHTS),
        "methodology": {
            "historical_trade_backtest_used": False,
            "historical_trade_backtest_reason": (
                "data/trade_history.json is pick-calibration data and does "
                "not preserve exact pre-trade roster/taxi/reserve states"
            ),
            "acquisition_universe": (
                "every current rostered player hypothetically added as active "
                "bench to each of the other 11 current 2026 rosters"
            ),
            "balanced_swap_universe": {
                "description": (
                    "one-for-one current-player swaps between real teams, "
                    "filtered to similar Fundamental Value"
                ),
                "max_fv_ratio": BALANCED_FV_RATIO_MAX,
                "max_fv_absolute_difference": BALANCED_FV_ABS_MAX,
            },
            "starter_objective": (
                "2026 Team Utility production rule: non-K projection first; "
                "projected over missing; FV fallback/tie; K by FV"
            ),
            "accounting_units": "lineupDelta and benchDelta remain Fundamental Value",
            "incoming_slot_policy": "incoming asset defaults to active bench/startable",
            "taxi_reserve_policy": "retained as bench economics; never starter eligible",
        },
        "data_quality": {
            "team_count": len(league),
            "league_player_count": sum(len(v) for v in league.values()),
            "projection_artifact_player_count": len(projections),
            "live_merge_stats": cfg.get("live_merge_stats"),
            "unresolved_current_roster_rows": len(unresolved),
            "lineup_validation": lineup_validation,
        },
        "bench_capital_profile": profile,
        "acquisition_scenarios": {
            "scenario_count": len(acquisitions),
            "sensitivity": acquisition_results,
        },
        "balanced_swap_scenarios": {
            "scenario_count": len(swaps),
            "sensitivity": swap_results,
        },
        "stage1_anchor": {
            "current_weight": stage1["current_production_bench_weight"],
            "primary_4_week_target": stage1[
                "stage1_interpretation"
            ]["primary_empirical_target"],
            "bootstrap_95pct": stage1["horizons"]["4"][
                "bootstrap_team_season_clustered"
            ]["unconditional_future_start_share"],
        },
        "decision": recommendation,
    }

    return round_recursive(result)


def pct(x: float) -> str:
    return f"{100*x:.1f}%"


def render_markdown(result: dict[str, Any]) -> str:
    d = result["decision"]
    acq = result["acquisition_scenarios"]["sensitivity"]
    swaps = result["balanced_swap_scenarios"]["sensitivity"]
    profile = result["bench_capital_profile"]

    lines = [
        "# Team Utility Bench-Weight Audit — Stage 2",
        "",
        "## Decision",
        "",
        f"**Recommendation: `{d['recommendation']}`**",
        "",
        f"- Production coefficient: **{result['production_bench_weight']:.2f}**",
        f"- Stage-1 empirical 4-week target: **{pct(d['stage1_primary_target'])}**",
        (
            "- Stage-1 clustered 95% band: "
            f"**{pct(d['stage1_95pct_band'][0])} to "
            f"{pct(d['stage1_95pct_band'][1])}**"
        ),
        f"- Stage-1 anchor supports 0.15: **{d['stage1_anchor_supports_0_15']}**",
        (
            "- Local 0.10/0.20 minimum median acquisition top-10 overlap "
            f"vs 0.15: **{pct(d['local_0_10_0_20_min_median_top10_overlap'])}**"
        ),
        (
            "- Local 0.10/0.20 minimum median acquisition Spearman "
            f"vs 0.15: **{d['local_0_10_0_20_min_median_spearman']:.4f}**"
        ),
        (
            "- Local 0.10/0.20 maximum balanced-swap sign-pattern flip rate: "
            f"**{d['local_0_10_0_20_max_swap_sign_pattern_flip_pct']:.2f}%**"
        ),
        f"- Local stability rule passed: **{d['local_stability_rule_passed']}**",
        "",
        d["rationale"],
        "",
        "**This audit does not authorize an automatic production change.**",
        "",
        "## Data quality",
        "",
        f"- Current teams: **{result['data_quality']['team_count']}**",
        f"- Current rostered players evaluated: **{result['data_quality']['league_player_count']}**",
        f"- Projection artifact rows available: **{result['data_quality']['projection_artifact_player_count']}**",
        f"- Current unresolved roster rows: **{result['data_quality']['unresolved_current_roster_rows']}**",
        f"- Marginal acquisition scenarios: **{result['acquisition_scenarios']['scenario_count']}**",
        f"- FV-balanced one-for-one swap scenarios: **{result['balanced_swap_scenarios']['scenario_count']}**",
        "",
        "Every current team filled all 17 legal starter slots with zero taxi/reserve starters and zero missing non-K projections.",
        "",
        "## Acquisition-ranking sensitivity",
        "",
        "| w | Median Spearman vs .15 | Min Spearman | Median top-10 overlap | Min top-10 | Median top-25 overlap |",
        "|---:|---:|---:|---:|---:|---:|",
    ]

    for w in CANDIDATE_WEIGHTS:
        r = acq[f"{w:.2f}"]
        lines.append(
            f"| {w:.2f} | {r['median_spearman_vs_0_15']:.4f} | "
            f"{r['min_spearman_vs_0_15']:.4f} | "
            f"{pct(r['median_top_10_overlap_vs_0_15'])} | "
            f"{pct(r['min_top_10_overlap_vs_0_15'])} | "
            f"{pct(r['median_top_25_overlap_vs_0_15'])} |"
        )

    lines += [
        "",
        "## Balanced one-for-one swap sensitivity",
        "",
        "| w | Sign-pattern changes vs .15 | Side sign flips | Mutual positive | Mutual negative | Split-sign |",
        "|---:|---:|---:|---:|---:|---:|",
    ]

    for w in CANDIDATE_WEIGHTS:
        r = swaps[f"{w:.2f}"]
        lines.append(
            f"| {w:.2f} | {r['sign_pattern_change_vs_0_15_pct']:.2f}% | "
            f"{r['side_sign_flip_vs_0_15_pct_of_sides']:.2f}% | "
            f"{r['mutual_positive_pct']:.2f}% | "
            f"{r['mutual_negative_pct']:.2f}% | "
            f"{r['split_sign_pct']:.2f}% |"
        )

    lines += [
        "",
        "## Taxi / reserve contribution to current bench capital",
        "",
        (
            "- Median taxi+reserve share of nonstarter FV across teams: "
            f"**{pct(profile['median_taxi_reserve_share_of_nonstarter_fv'])}**"
        ),
        (
            "- Maximum team taxi+reserve share of nonstarter FV: "
            f"**{pct(profile['max_taxi_reserve_share_of_nonstarter_fv'])}**"
        ),
        "",
        "This matters because Stage 1 empirically measured active-bench utilization only; historical Sleeper matchup rosters excluded taxi/IR.",
        "",
        "## Interpretation",
        "",
        "- Stage 1 answers **where the empirical bench coefficient is centered**.",
        "- Stage 2 answers **whether moving that coefficient changes real 2026 roster-fit decisions**.",
        "- The historical trade file is deliberately **not** used as a fake outcome backtest because it does not preserve exact pre-trade roster and slot state.",
        "- Fundamental Value remains the accounting unit. Projections only choose who starts.",
        "- Incoming players are treated exactly like production: active bench and immediately starter-eligible.",
        "- `TU_BENCH_WEIGHT` remains **0.15** after this research run unless a later explicit production deployment changes it.",
        "",
    ]

    if d["recommendation"] == "KEEP_0_15":
        lines += [
            "## Recommended close",
            "",
            "Lock **`TU_BENCH_WEIGHT = 0.15`** as the validated V1 global bench coefficient.",
            "",
            "Do not reopen the coefficient until one of these conditions occurs:",
            "1. enough 2026 regular-season lineup history accumulates under the new 2-RB/2-LB ruleset;",
            "2. a trustworthy exact pre/post trade-roster history is built;",
            "3. evidence justifies separate active-bench vs taxi/reserve weighting.",
            "",
        ]
    else:
        lines += [
            "## Recommended next research",
            "",
            "Keep production at **0.15** and investigate whether the sensitivity is caused by active-bench vs taxi/reserve treatment or by specific roster contexts before considering any new coefficient.",
            "",
        ]

    return "\n".join(lines)


def write_outputs(result: dict[str, Any]) -> None:
    OUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUT_MD.write_text(render_markdown(result), encoding="utf-8")


def check_outputs(result: dict[str, Any]) -> None:
    expected_json = json.dumps(result, indent=2, sort_keys=True) + "\n"
    expected_md = render_markdown(result)

    if not OUT_JSON.exists() or not OUT_MD.exists():
        raise RuntimeError("Stage-2 outputs missing; run --write")
    if OUT_JSON.read_text(encoding="utf-8") != expected_json:
        raise RuntimeError("Stage-2 JSON output is stale")
    if OUT_MD.read_text(encoding="utf-8") != expected_md:
        raise RuntimeError("Stage-2 Markdown output is stale")

    print("PASS Team Utility bench-weight Stage-2 outputs are current.")


def selftest() -> None:
    # Comparator: projection beats FV.
    a = Player("a", "a", "A", "QB", "bench", 9000, 100)
    b = Player("b", "b", "B", "QB", "bench", 3000, 300)
    lineup = optimize_lineup([a, b])
    assert lineup["starters"][0].player_id == "b"

    # Missing projection loses to known projection, including known 0.
    c = Player("c", "c", "C", "WR", "bench", 10000, None)
    d = Player("d", "d", "D", "WR", "bench", 1000, 0.0)
    assert sorted([c, d], key=lineup_compare_key)[0].player_id == "d"

    # Taxi cannot start.
    taxi = Player("t", "t", "Taxi", "QB", "taxi", 20000, 999)
    active = Player("q", "q", "Active", "QB", "bench", 1000, 1)
    lineup = optimize_lineup([taxi, active])
    assert lineup["starters"][0].player_id == "q"
    assert any(p.player_id == "t" for p in lineup["bench"])

    # Name normalization parity: preserve ordinary letters (especially "u")
    # while removing punctuation/apostrophes exactly as production does.
    assert normalize_name("Justin Jefferson") == "justin jefferson"
    assert normalize_name("D'Andre Swift") == "dandre swift"
    assert normalize_name("Henry To'oTo'o") == "henry tootoo"

    # Utility algebra.
    assert utility_from_deltas(100, 0, 0.15) == 85
    assert utility_from_deltas(0, 100, 0.15) == 15
    assert utility_from_deltas(-100, 0, 0.15) == -85

    # Ranking helpers.
    assert abs(spearman([1, 2, 3], [1, 2, 3]) - 1.0) < 1e-12
    assert overlap_fraction(["a", "b"], ["b", "a"], 2) == 1.0

    print("PASS Team Utility bench-weight Stage-2 synthetic self-test.")


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--selftest", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return

    result = build_result()

    if args.write:
        write_outputs(result)
        print(json.dumps({
            "status": result["status"],
            "recommendation": result["decision"]["recommendation"],
            "production_bench_weight": result["production_bench_weight"],
            "acquisition_scenarios": result["acquisition_scenarios"]["scenario_count"],
            "balanced_swap_scenarios": result["balanced_swap_scenarios"]["scenario_count"],
            "production_change_authorized": result["decision"]["production_change_authorized"],
        }, indent=2))
        print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
        print(f"Wrote {OUT_MD.relative_to(ROOT)}")
        return

    check_outputs(result)


if __name__ == "__main__":
    main()

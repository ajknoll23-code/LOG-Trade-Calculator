#!/usr/bin/env python3
"""Team Utility bench-weight calibration audit, Stage 1.

Purpose
-------
Calibrate the *order of magnitude* of Team Utility's global bench coefficient
using real historical roster decisions from this league, without changing
production.

Production formula:
    TeamUtility = (1 - w) * lineupDelta_FV + w * benchDelta_FV

The deployed w=0.15 is currently an unvalidated assumption.

This audit asks a narrower empirical question:
    When a player is on an active roster but benched in week t, how much of the
    next 1/2/4 weeks does that same player actually spend in the starting lineup
    for that same team?

That future-start share is a direct, unit-free proxy for the fraction of
near-term lineup utility carried by active bench capital. It is not claimed to
capture every dynasty reason bench assets retain value (future years, trade
market, development, etc.), so this is a calibration anchor, not an automatic
production change.

Important scope caveats
-----------------------
* Historical lineup reconstruction covers 2024-2025, when this league used
  1 dedicated RB and 1 dedicated LB. Production 2026 uses 2 RB and 2 LB.
  We do NOT rewrite history to simulate 2026 rules in this Stage-1 audit.
* historical_lineup_demand.json's "benched" pool is active-roster only;
  Sleeper matchup `players` excludes taxi/IR. Production bench economics also
  retain taxi/reserve_ir capital, so one global coefficient is structurally
  coarser than the historical target.
* No model value, projection, or current player rating is used to label the
  historical outcome. This avoids leaking today's player quality backward.

Outputs
-------
research/team-utility/team_utility_bench_weight_audit.json
research/team-utility/team_utility_bench_weight_audit.md

Usage
-----
python3 research/team-utility/team_utility_bench_weight_audit.py --selftest
python3 research/team-utility/team_utility_bench_weight_audit.py --write
python3 research/team-utility/team_utility_bench_weight_audit.py --check
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
import re
from statistics import mean, median
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
HIST = ROOT / "research" / "roster-economics" / "historical_lineup_demand.json"
INDEX = ROOT / "index.html"
RUNTIME = ROOT / "scripts" / "team_utility_projection_runtime.js"
OUT_JSON = ROOT / "research" / "team-utility" / "team_utility_bench_weight_audit.json"
OUT_MD = ROOT / "research" / "team-utility" / "team_utility_bench_weight_audit.md"

EXPECTED_SEASONS = ("2024", "2025")
HORIZONS = (1, 2, 4)
CANDIDATE_WEIGHTS = (0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50)
BOOTSTRAP_REPS = 2000
BOOTSTRAP_SEED = 20260902


@dataclass(frozen=True)
class PlayerWeek:
    season: str
    week: int
    roster_id: int
    player_id: str
    pos: str | None
    started: bool


def qtile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("qtile() requires at least one value")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    idx = (len(xs) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return xs[lo]
    frac = idx - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def load_inputs() -> tuple[dict[str, Any], float]:
    if not HIST.exists():
        raise RuntimeError(f"missing historical lineup data: {HIST}")
    if not INDEX.exists():
        raise RuntimeError(f"missing production index: {INDEX}")
    if not RUNTIME.exists():
        raise RuntimeError(f"missing Team Utility runtime: {RUNTIME}")

    hist = json.loads(HIST.read_text(encoding="utf-8"))

    index_text = INDEX.read_text(encoding="utf-8")
    match = re.search(r"const\s+TU_BENCH_WEIGHT\s*=\s*([0-9.]+)\s*;", index_text)
    if not match:
        raise RuntimeError("could not find TU_BENCH_WEIGHT in index.html")
    current_weight = float(match.group(1))

    runtime_text = RUNTIME.read_text(encoding="utf-8")
    required_runtime_tokens = (
        "TEAM_UTILITY_PROJECTION_RUNTIME_V1",
        "lineupDelta",
        "benchDelta",
        "starterEligible: slot !== 'taxi' && slot !== 'reserve_ir'",
    )
    for token in required_runtime_tokens:
        if token not in runtime_text:
            raise RuntimeError(f"production runtime missing expected token: {token}")

    return hist, current_weight


def normalize_records(hist: dict[str, Any]) -> tuple[list[PlayerWeek], dict[str, dict[str, Any]]]:
    seasons = hist.get("seasons")
    if not isinstance(seasons, dict):
        raise RuntimeError("historical lineup data missing seasons object")

    normalized: list[PlayerWeek] = []
    season_meta: dict[str, dict[str, Any]] = {}

    for season in EXPECTED_SEASONS:
        payload = seasons.get(season)
        if not isinstance(payload, dict):
            raise RuntimeError(f"historical lineup data missing season {season}")

        records = payload.get("records")
        if not isinstance(records, list):
            raise RuntimeError(f"season {season} missing records list")

        roster_positions = payload.get("roster_positions") or []
        weeks_with_data = int(payload.get("weeks_with_data") or 0)

        teams = set()
        weeks = set()
        benched = 0
        started = 0

        for raw in records:
            if not isinstance(raw, dict):
                continue
            try:
                week = int(raw["week"])
                roster_id = int(raw["roster_id"])
                player_id = str(raw["player_id"])
            except (KeyError, TypeError, ValueError):
                continue

            start_type = raw.get("start_type")
            if start_type not in {"dedicated", "flex", "benched"}:
                continue

            is_started = start_type in {"dedicated", "flex"}
            pos = raw.get("pos_bucket")
            pos = str(pos) if pos is not None else None

            normalized.append(
                PlayerWeek(
                    season=season,
                    week=week,
                    roster_id=roster_id,
                    player_id=player_id,
                    pos=pos,
                    started=is_started,
                )
            )
            teams.add(roster_id)
            weeks.add(week)
            if is_started:
                started += 1
            else:
                benched += 1

        season_meta[season] = {
            "weeks_with_data": weeks_with_data,
            "observed_week_min": min(weeks) if weeks else None,
            "observed_week_max": max(weeks) if weeks else None,
            "team_count": len(teams),
            "record_count": len([r for r in normalized if r.season == season]),
            "started_record_count": started,
            "benched_record_count": benched,
            "starter_slot_count": sum(1 for p in roster_positions if p != "BN"),
            "dedicated_rb_slots": sum(1 for p in roster_positions if p == "RB"),
            "dedicated_lb_slots": sum(1 for p in roster_positions if p == "LB"),
            "roster_positions": roster_positions,
        }

    if len(normalized) < 10_000:
        raise RuntimeError(
            f"historical lineup sample unexpectedly small: {len(normalized)} records"
        )

    for season, meta in season_meta.items():
        if meta["team_count"] != 12:
            raise RuntimeError(
                f"{season}: expected 12 teams, found {meta['team_count']}"
            )
        if meta["weeks_with_data"] < 16:
            raise RuntimeError(
                f"{season}: expected at least 16 weeks, found {meta['weeks_with_data']}"
            )
        if meta["benched_record_count"] < 1_000:
            raise RuntimeError(
                f"{season}: benched sample unexpectedly small: "
                f"{meta['benched_record_count']}"
            )

    return normalized, season_meta


def build_state_index(records: list[PlayerWeek]) -> dict[tuple[str, int, int, str], PlayerWeek]:
    index: dict[tuple[str, int, int, str], PlayerWeek] = {}
    for rec in records:
        key = (rec.season, rec.week, rec.roster_id, rec.player_id)
        prior = index.get(key)
        if prior is not None:
            # A player should have one state per team-week. If duplicates ever
            # appear, a started state dominates a benched state; two identical
            # states are harmless.
            if prior.started == rec.started:
                continue
            if prior.started:
                continue
        index[key] = rec
    return index


def eligible_bench_observations(
    records: list[PlayerWeek],
    season_meta: dict[str, dict[str, Any]],
    horizon: int,
) -> list[PlayerWeek]:
    out = []
    for rec in records:
        if rec.started:
            continue
        max_week = season_meta[rec.season]["observed_week_max"]
        if max_week is None:
            continue
        # Avoid right-censoring: every included week has a complete calendar
        # horizon available in the historical season.
        if rec.week + horizon <= max_week:
            out.append(rec)
    return out


def evaluate_horizon(
    records: list[PlayerWeek],
    state_index: dict[tuple[str, int, int, str], PlayerWeek],
    season_meta: dict[str, dict[str, Any]],
    horizon: int,
) -> dict[str, Any]:
    obs = eligible_bench_observations(records, season_meta, horizon)

    rows = []
    for rec in obs:
        future_starts = 0
        future_present = 0

        for future_week in range(rec.week + 1, rec.week + horizon + 1):
            future = state_index.get(
                (rec.season, future_week, rec.roster_id, rec.player_id)
            )
            if future is not None:
                future_present += 1
                if future.started:
                    future_starts += 1

        rows.append(
            {
                "season": rec.season,
                "roster_id": rec.roster_id,
                "pos": rec.pos or "UNKNOWN",
                "future_starts": future_starts,
                "future_present": future_present,
                "future_slots": horizon,
                "any_start": 1 if future_starts > 0 else 0,
            }
        )

    if not rows:
        raise RuntimeError(f"horizon {horizon}: no eligible bench observations")

    total_slots = sum(r["future_slots"] for r in rows)
    total_starts = sum(r["future_starts"] for r in rows)
    total_present = sum(r["future_present"] for r in rows)

    pooled = {
        "bench_player_week_observations": len(rows),
        "unconditional_future_start_share": total_starts / total_slots,
        "any_future_start_probability": sum(r["any_start"] for r in rows) / len(rows),
        "same_team_roster_retention_share": total_present / total_slots,
        "conditional_start_share_when_present": (
            total_starts / total_present if total_present else None
        ),
    }

    by_season = {}
    for season in EXPECTED_SEASONS:
        sub = [r for r in rows if r["season"] == season]
        slots = sum(r["future_slots"] for r in sub)
        starts = sum(r["future_starts"] for r in sub)
        present = sum(r["future_present"] for r in sub)
        by_season[season] = {
            "bench_player_week_observations": len(sub),
            "unconditional_future_start_share": starts / slots if slots else None,
            "any_future_start_probability": (
                sum(r["any_start"] for r in sub) / len(sub) if sub else None
            ),
            "same_team_roster_retention_share": present / slots if slots else None,
            "conditional_start_share_when_present": (
                starts / present if present else None
            ),
        }

    by_position = {}
    positions = sorted({r["pos"] for r in rows})
    for pos in positions:
        sub = [r for r in rows if r["pos"] == pos]
        if len(sub) < 25:
            continue
        slots = sum(r["future_slots"] for r in sub)
        starts = sum(r["future_starts"] for r in sub)
        present = sum(r["future_present"] for r in sub)
        by_position[pos] = {
            "bench_player_week_observations": len(sub),
            "unconditional_future_start_share": starts / slots if slots else None,
            "any_future_start_probability": (
                sum(r["any_start"] for r in sub) / len(sub)
            ),
            "same_team_roster_retention_share": present / slots if slots else None,
            "conditional_start_share_when_present": (
                starts / present if present else None
            ),
        }

    # Clustered bootstrap at the team-season level. This respects the fact
    # that weekly observations from the same real roster are not independent.
    clusters: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        clusters[(row["season"], row["roster_id"])].append(row)

    cluster_items = list(clusters.items())
    rng = random.Random(BOOTSTRAP_SEED + horizon)

    start_share_samples = []
    any_start_samples = []

    for _ in range(BOOTSTRAP_REPS):
        sampled = [rng.choice(cluster_items)[1] for _ in range(len(cluster_items))]
        sampled_rows = [row for cluster in sampled for row in cluster]
        slots = sum(r["future_slots"] for r in sampled_rows)
        starts = sum(r["future_starts"] for r in sampled_rows)
        start_share_samples.append(starts / slots)
        any_start_samples.append(
            sum(r["any_start"] for r in sampled_rows) / len(sampled_rows)
        )

    bootstrap = {
        "cluster_count": len(cluster_items),
        "replicates": BOOTSTRAP_REPS,
        "unconditional_future_start_share": {
            "p10": qtile(start_share_samples, 0.10),
            "p50": qtile(start_share_samples, 0.50),
            "p90": qtile(start_share_samples, 0.90),
            "p025": qtile(start_share_samples, 0.025),
            "p975": qtile(start_share_samples, 0.975),
        },
        "any_future_start_probability": {
            "p10": qtile(any_start_samples, 0.10),
            "p50": qtile(any_start_samples, 0.50),
            "p90": qtile(any_start_samples, 0.90),
            "p025": qtile(any_start_samples, 0.025),
            "p975": qtile(any_start_samples, 0.975),
        },
    }

    return {
        "horizon_weeks": horizon,
        "pooled": pooled,
        "by_season": by_season,
        "by_position": by_position,
        "bootstrap_team_season_clustered": bootstrap,
    }


def candidate_grid(primary_target: float, current_weight: float) -> list[dict[str, Any]]:
    out = []
    for w in CANDIDATE_WEIGHTS:
        out.append(
            {
                "weight": w,
                "absolute_distance_to_primary_target": abs(w - primary_target),
                "distance_vs_current_0_15": abs(w - primary_target)
                - abs(current_weight - primary_target),
            }
        )
    out.sort(key=lambda row: (row["absolute_distance_to_primary_target"], row["weight"]))
    return out


def format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{100 * value:.2f}%"


def round_recursive(obj: Any) -> Any:
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, list):
        return [round_recursive(x) for x in obj]
    if isinstance(obj, dict):
        return {k: round_recursive(v) for k, v in obj.items()}
    return obj


def build_result() -> dict[str, Any]:
    hist, current_weight = load_inputs()
    records, season_meta = normalize_records(hist)
    state_index = build_state_index(records)

    horizon_results = {
        str(h): evaluate_horizon(records, state_index, season_meta, h)
        for h in HORIZONS
    }

    primary = horizon_results["4"]["pooled"]["unconditional_future_start_share"]
    bootstrap4 = horizon_results["4"]["bootstrap_team_season_clustered"][
        "unconditional_future_start_share"
    ]
    grid = candidate_grid(primary, current_weight)
    nearest = grid[0]["weight"]

    season_targets = [
        horizon_results["4"]["by_season"][season][
            "unconditional_future_start_share"
        ]
        for season in EXPECTED_SEASONS
    ]
    season_spread = max(season_targets) - min(season_targets)

    current_inside_80 = bootstrap4["p10"] <= current_weight <= bootstrap4["p90"]
    current_inside_95 = bootstrap4["p025"] <= current_weight <= bootstrap4["p975"]

    # Stage-1 intentionally does not authorize production changes because the
    # historical ruleset differs from 2026 and taxi/IR are outside the source
    # bench pool. It only identifies which candidates deserve Stage-2 testing.
    stage1_interpretation = {
        "primary_empirical_target": primary,
        "nearest_0_05_candidate": nearest,
        "current_weight": current_weight,
        "current_weight_inside_bootstrap_80pct_band": current_inside_80,
        "current_weight_inside_bootstrap_95pct_band": current_inside_95,
        "season_to_season_target_spread": season_spread,
        "production_change_authorized": False,
        "reason_no_automatic_deployment": (
            "Stage-1 uses 2024-2025 active-bench utilization under the old "
            "1-RB/1-LB ruleset and does not observe taxi/IR utilization. "
            "Use this as an empirical anchor, then run a 2026-roster and "
            "trade-sensitivity audit before changing the global coefficient."
        ),
    }

    result = {
        "schema_version": 1,
        "audit": "team_utility_bench_weight_stage1",
        "status": "PASS",
        "production_formula": (
            "TeamUtility = (1-w)*lineupDelta_FV + w*benchDelta_FV"
        ),
        "current_production_bench_weight": current_weight,
        "source_scope": {
            "historical_seasons": list(EXPECTED_SEASONS),
            "historical_source": str(HIST.relative_to(ROOT)),
            "historical_bench_definition": (
                "rostered-but-not-started active matchup players; taxi/IR excluded"
            ),
            "current_2026_ruleset_difference": (
                "2024-2025 had 1 dedicated RB and 1 dedicated LB; "
                "2026 has 2 dedicated RB and 2 dedicated LB"
            ),
        },
        "season_data_quality": season_meta,
        "horizons": horizon_results,
        "candidate_grid_against_4_week_start_share": grid,
        "stage1_interpretation": stage1_interpretation,
        "methodology_notes": [
            (
                "Primary target is the unconditional fraction of the next 4 "
                "calendar weeks that a currently benched player starts for "
                "the same team. Leaving the roster counts as zero future "
                "lineup use, which matches Team Utility's roster-fit purpose."
            ),
            (
                "Any-start probability is reported as an upper-bound style "
                "usage metric; it gives full credit if the player starts at "
                "least once and therefore should not be substituted directly "
                "for w."
            ),
            (
                "Conditional start share when still present is diagnostic "
                "only because conditioning away cuts/trades overstates the "
                "team's retained utility from the original bench asset."
            ),
            (
                "Bootstrap resamples whole team-season clusters, not individual "
                "player-weeks, to preserve within-roster dependence."
            ),
        ],
    }

    return round_recursive(result)


def render_markdown(result: dict[str, Any]) -> str:
    s = result["stage1_interpretation"]
    lines = [
        "# Team Utility Bench-Weight Audit — Stage 1",
        "",
        "## Decision",
        "",
        "**Research only — no production coefficient change is authorized by this audit.**",
        "",
        f"- Current production `TU_BENCH_WEIGHT`: **{result['current_production_bench_weight']:.2f}**",
        f"- Primary empirical target (4-week future-start share): **{format_pct(s['primary_empirical_target'])}**",
        f"- Nearest 0.05 candidate: **{s['nearest_0_05_candidate']:.2f}**",
        f"- Current 0.15 inside clustered-bootstrap 80% band: **{s['current_weight_inside_bootstrap_80pct_band']}**",
        f"- Current 0.15 inside clustered-bootstrap 95% band: **{s['current_weight_inside_bootstrap_95pct_band']}**",
        f"- 2024 vs 2025 target spread: **{format_pct(s['season_to_season_target_spread'])}**",
        "",
        "Why no automatic deployment: "
        + s["reason_no_automatic_deployment"],
        "",
        "## Historical sample quality",
        "",
        "| Season | Teams | Weeks | Records | Started | Benched | Starter slots | RB dedicated | LB dedicated |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for season in EXPECTED_SEASONS:
        m = result["season_data_quality"][season]
        lines.append(
            f"| {season} | {m['team_count']} | {m['weeks_with_data']} | "
            f"{m['record_count']} | {m['started_record_count']} | "
            f"{m['benched_record_count']} | {m['starter_slot_count']} | "
            f"{m['dedicated_rb_slots']} | {m['dedicated_lb_slots']} |"
        )

    lines += [
        "",
        "## Bench utilization by horizon",
        "",
        "| Horizon | Bench player-weeks | Future start share | Any future start | Same-team retention | Start share if retained |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for horizon in HORIZONS:
        p = result["horizons"][str(horizon)]["pooled"]
        lines.append(
            f"| {horizon} week{'s' if horizon != 1 else ''} | "
            f"{p['bench_player_week_observations']} | "
            f"{format_pct(p['unconditional_future_start_share'])} | "
            f"{format_pct(p['any_future_start_probability'])} | "
            f"{format_pct(p['same_team_roster_retention_share'])} | "
            f"{format_pct(p['conditional_start_share_when_present'])} |"
        )

    h4 = result["horizons"]["4"]
    b = h4["bootstrap_team_season_clustered"]["unconditional_future_start_share"]

    lines += [
        "",
        "## Four-week primary target by season",
        "",
        "| Season | Bench player-weeks | Future start share | Any future start | Retention |",
        "|---|---:|---:|---:|---:|",
    ]

    for season in EXPECTED_SEASONS:
        p = h4["by_season"][season]
        lines.append(
            f"| {season} | {p['bench_player_week_observations']} | "
            f"{format_pct(p['unconditional_future_start_share'])} | "
            f"{format_pct(p['any_future_start_probability'])} | "
            f"{format_pct(p['same_team_roster_retention_share'])} |"
        )

    lines += [
        "",
        "## Four-week target by position",
        "",
        "| Position | Bench player-weeks | Future start share | Any future start | Retention |",
        "|---|---:|---:|---:|---:|",
    ]

    for pos, p in sorted(h4["by_position"].items()):
        lines.append(
            f"| {pos} | {p['bench_player_week_observations']} | "
            f"{format_pct(p['unconditional_future_start_share'])} | "
            f"{format_pct(p['any_future_start_probability'])} | "
            f"{format_pct(p['same_team_roster_retention_share'])} |"
        )

    lines += [
        "",
        "## Clustered bootstrap",
        "",
        f"- Team-season clusters: **{h4['bootstrap_team_season_clustered']['cluster_count']}**",
        f"- Replicates: **{h4['bootstrap_team_season_clustered']['replicates']}**",
        f"- 80% band for 4-week future-start share: **{format_pct(b['p10'])} to {format_pct(b['p90'])}**",
        f"- 95% band: **{format_pct(b['p025'])} to {format_pct(b['p975'])}**",
        "",
        "## Candidate coefficient grid",
        "",
        "| Candidate w | Distance to empirical target | Improvement vs current 0.15 |",
        "|---:|---:|---:|",
    ]

    for row in result["candidate_grid_against_4_week_start_share"]:
        lines.append(
            f"| {row['weight']:.2f} | "
            f"{format_pct(row['absolute_distance_to_primary_target'])} | "
            f"{format_pct(-row['distance_vs_current_0_15'])} |"
        )

    lines += [
        "",
        "## Interpretation guardrails",
        "",
        "- This is a **utilization calibration anchor**, not a proof that bench dynasty assets are worth only their short-horizon start probability.",
        "- 2024–25 were played with **1 dedicated RB and 1 dedicated LB**; production 2026 uses **2 RB and 2 LB**.",
        "- Historical `benched` observations exclude taxi/IR. Production currently keeps taxi/reserve-IR assets in bench economics while preventing them from starting.",
        "- A single global `w` may therefore be too coarse. Stage 2 should test 2026 roster sensitivity and whether active bench vs taxi/IR need separate treatment.",
        "- `TU_BENCH_WEIGHT` remains unchanged at **0.15** after this audit.",
        "",
        "## Next test",
        "",
        "Use this empirical range to run a **2026 roster + real-trade sensitivity audit** across `w = 0.00–0.50`. That second audit should determine whether changing 0.15 materially improves decision quality or merely changes score magnitude.",
        "",
    ]

    return "\n".join(lines)


def write_outputs(result: dict[str, Any]) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUT_MD.write_text(render_markdown(result), encoding="utf-8")


def check_outputs(result: dict[str, Any]) -> None:
    expected_json = json.dumps(result, indent=2, sort_keys=True) + "\n"
    expected_md = render_markdown(result)

    if not OUT_JSON.exists() or not OUT_MD.exists():
        raise RuntimeError("audit outputs are missing; run --write")

    actual_json = OUT_JSON.read_text(encoding="utf-8")
    actual_md = OUT_MD.read_text(encoding="utf-8")

    if actual_json != expected_json:
        raise RuntimeError("team_utility_bench_weight_audit.json is stale")
    if actual_md != expected_md:
        raise RuntimeError("team_utility_bench_weight_audit.md is stale")

    print("PASS Team Utility bench-weight audit outputs are current.")


def selftest() -> None:
    # Quantile interpolation.
    assert qtile([0.0, 1.0], 0.5) == 0.5

    # Candidate nearest-target behavior.
    grid = candidate_grid(0.17, 0.15)
    assert grid[0]["weight"] == 0.15
    grid = candidate_grid(0.19, 0.15)
    assert grid[0]["weight"] == 0.20

    # Tiny synthetic future-start example:
    records = [
        PlayerWeek("2024", 1, 1, "A", "RB", False),
        PlayerWeek("2024", 2, 1, "A", "RB", True),
        PlayerWeek("2024", 3, 1, "A", "RB", False),
        PlayerWeek("2024", 1, 1, "B", "WR", False),
        PlayerWeek("2024", 2, 1, "B", "WR", False),
        PlayerWeek("2024", 3, 1, "B", "WR", False),
    ]
    meta = {
        "2024": {"observed_week_max": 3},
        "2025": {"observed_week_max": 3},
    }
    idx = build_state_index(records)
    obs = eligible_bench_observations(records, meta, 1)
    assert len(obs) == 3

    # For week-1 bench A, next week is a start.
    a = [r for r in obs if r.player_id == "A" and r.week == 1][0]
    future = idx[("2024", 2, 1, "A")]
    assert future.started is True

    print("PASS Team Utility bench-weight Stage-1 synthetic self-test.")


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
            "current_weight": result["current_production_bench_weight"],
            "primary_4_week_target": result["stage1_interpretation"]["primary_empirical_target"],
            "nearest_0_05_candidate": result["stage1_interpretation"]["nearest_0_05_candidate"],
            "production_change_authorized": result["stage1_interpretation"]["production_change_authorized"],
        }, indent=2))
        print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
        print(f"Wrote {OUT_MD.relative_to(ROOT)}")
        return

    check_outputs(result)


if __name__ == "__main__":
    main()

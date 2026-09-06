#!/usr/bin/env python3
"""
Position Weight / Cross-Position Economics V2 — Phase 2 ruleset simulation.

Research only. No POSITION_WEIGHT change is authorized.

Historical 2024-2025 lineup demand was observed under the old ruleset.
The 2026 league added dedicated RB/LB capacity, so this phase does not
retroactively reinterpret old manager behavior.

Instead it:
1. validates a league-wide structural lineup allocator against the real
   2024/2025 starts under each season's actual roster_positions;
2. fetches the current 2026 Sleeper roster_positions;
3. reruns the same 2024/2025 weekly scoring samples under the current rules.

The allocator is a structural supply/demand model: it fills dedicated slots,
then assigns FLEX/SUPER_FLEX/IDP_FLEX capacity to the best remaining eligible
position pools for that realized week. It intentionally ignores individual
team ownership constraints, so validation error is reported rather than hidden.

No new position weights are produced here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
from typing import Any

import requests

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]

CONFIG_JSON = REPO_ROOT / "config.json"
PHASE1_JSON = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase1_architecture_audit.json"
)
WEEKLY_POINTS_JSON = (
    REPO_ROOT / "research" / "roster-economics"
    / "weekly_points_by_season.json"
)
HISTORICAL_LINEUP_JSON = (
    REPO_ROOT / "research" / "roster-economics"
    / "historical_lineup_demand.json"
)

OUTPUT_JSON = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase2_ruleset_simulation.json"
)
OUTPUT_MD = (
    REPO_ROOT / "research" / "position-weight-v2"
    / "position_weight_v2_phase2_ruleset_simulation.md"
)

METHOD_VERSION = "position-weight-v2-phase2-ruleset-simulation-v1"
PHASE1_METHOD = "position-weight-v2-phase1-architecture-audit-v1"
SLEEPER_BASE = "https://api.sleeper.app/v1"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
OFFENSE = ("QB", "RB", "WR", "TE")
IDP = ("DL", "LB", "DB")
SEASONS = ("2024", "2025")
REGULAR_SEASON_MAX_WEEK = 18

FLEX_ELIGIBLE = {
    "FLEX": ("RB", "WR", "TE"),
    "SUPER_FLEX": ("QB", "RB", "WR", "TE"),
    "IDP_FLEX": ("DL", "LB", "DB"),
    "REC_FLEX": ("WR", "TE"),
    "WRRB_FLEX": ("WR", "RB"),
}


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def round_numbers(obj, digits=6):
    if isinstance(obj, dict):
        return {k: round_numbers(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_numbers(v, digits) for v in obj]
    if isinstance(obj, float):
        return round(obj, digits) if math.isfinite(obj) else None
    return obj


def mean(values):
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return statistics.fmean(vals) if vals else None


def median(values):
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return statistics.median(vals) if vals else None


def percentile(values, q):
    vals = sorted(
        float(v) for v in values
        if v is not None and math.isfinite(float(v))
    )
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    idx = (len(vals) - 1) * max(0.0, min(1.0, float(q)))
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    frac = idx - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def fetch_current_league(league_id: str) -> dict[str, Any]:
    url = f"{SLEEPER_BASE}/league/{league_id}"
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("Sleeper league response is not an object")
            return payload
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed to fetch current Sleeper league: {last_error}")


def slot_structure(roster_positions: list[str], teams: int) -> dict[str, Any]:
    if not roster_positions or teams <= 0:
        raise RuntimeError("invalid roster structure")

    per_team = {}
    for slot in roster_positions:
        slot = str(slot)
        if slot == "BN":
            continue
        per_team[slot] = per_team.get(slot, 0) + 1

    unsupported = sorted(
        slot for slot in per_team
        if slot not in TRACKED_POSITIONS
        and slot not in FLEX_ELIGIBLE
        and slot not in {"K", "DEF"}
    )
    if unsupported:
        raise RuntimeError(f"unsupported starter slots: {unsupported}")

    dedicated_per_team = {
        pos: int(per_team.get(pos, 0))
        for pos in TRACKED_POSITIONS
    }
    flex_per_team = {
        slot: int(per_team.get(slot, 0))
        for slot in FLEX_ELIGIBLE
        if int(per_team.get(slot, 0)) > 0
    }

    return {
        "teams": int(teams),
        "roster_positions": list(roster_positions),
        "dedicated_per_team": dedicated_per_team,
        "flex_per_team": flex_per_team,
        "dedicated_league": {
            pos: dedicated_per_team[pos] * teams
            for pos in TRACKED_POSITIONS
        },
        "flex_league": {
            slot: count * teams
            for slot, count in flex_per_team.items()
        },
    }


def weekly_scores(points_data, season, week):
    players = (points_data.get("seasons") or {}).get(season)
    if not isinstance(players, dict):
        raise RuntimeError(f"weekly points missing {season}")

    out = {pos: [] for pos in TRACKED_POSITIONS}
    for pid, rec in players.items():
        pos = str(rec.get("pos_bucket") or "").upper()
        if pos not in out:
            continue
        weekly = rec.get("weekly_points")
        if not isinstance(weekly, dict):
            continue
        raw = weekly.get(str(week))
        if raw is None:
            raw = weekly.get(week)
        if raw is None:
            continue
        try:
            pts = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(pts):
            out[pos].append((str(pid), pts))

    for pos in TRACKED_POSITIONS:
        out[pos].sort(key=lambda row: (-row[1], row[0]))
    return out


def distribute_flex_slots(
    positions,
    dedicated,
    score_lists,
    flex_counts,
):
    """
    Exact DP over position-count increments after dedicated slots are filled.
    """
    positions = tuple(positions)
    idx = {pos: i for i, pos in enumerate(positions)}
    zero = tuple(0 for _ in positions)

    dedicated_score = 0.0
    for pos in positions:
        need = int(dedicated.get(pos, 0))
        if len(score_lists[pos]) < need:
            raise RuntimeError(
                f"{pos}: {len(score_lists[pos])} weekly scores for {need} dedicated slots"
            )
        dedicated_score += sum(v for _, v in score_lists[pos][:need])

    dp = {zero: 0.0}

    slot_instances = []
    for slot, count in sorted(flex_counts.items()):
        eligible = tuple(p for p in FLEX_ELIGIBLE[slot] if p in idx)
        for _ in range(int(count)):
            slot_instances.append((slot, eligible))

    for slot, eligible in slot_instances:
        nxt = {}
        for state, flex_score in dp.items():
            for pos in eligible:
                i = idx[pos]
                player_index = int(dedicated[pos]) + int(state[i])
                if player_index >= len(score_lists[pos]):
                    continue
                value = float(score_lists[pos][player_index][1])
                new_state = list(state)
                new_state[i] += 1
                new_state = tuple(new_state)
                new_score = flex_score + value
                if new_state not in nxt or new_score > nxt[new_state]:
                    nxt[new_state] = new_score
        if not nxt:
            raise RuntimeError(f"no feasible assignment for {slot}")
        dp = nxt

    best_state, best_flex = max(dp.items(), key=lambda kv: kv[1])
    starts = {
        pos: int(dedicated[pos]) + int(best_state[idx[pos]])
        for pos in positions
    }
    return starts, dedicated_score + best_flex


def simulate_week(score_lists, structure):
    dedicated = structure["dedicated_league"]
    flex = structure["flex_league"]

    offense_flex = {
        slot: count for slot, count in flex.items()
        if set(FLEX_ELIGIBLE[slot]).issubset(set(OFFENSE))
    }
    idp_flex = {
        slot: count for slot, count in flex.items()
        if set(FLEX_ELIGIBLE[slot]).issubset(set(IDP))
    }

    offense_starts, offense_points = distribute_flex_slots(
        OFFENSE, dedicated, score_lists, offense_flex
    )
    idp_starts, idp_points = distribute_flex_slots(
        IDP, dedicated, score_lists, idp_flex
    )
    starts = {**offense_starts, **idp_starts}

    pos_out = {}
    for pos in TRACKED_POSITIONS:
        n = int(starts[pos])
        rows = score_lists[pos]
        if len(rows) < n:
            raise RuntimeError(f"{pos}: insufficient score rows for simulated starts")
        marginal = float(rows[n - 1][1]) if n > 0 else None
        first_bench = float(rows[n][1]) if len(rows) > n else None
        avg_started = (
            statistics.fmean(v for _, v in rows[:n])
            if n > 0 else None
        )
        pos_out[pos] = {
            "simulated_starts": n,
            "marginal_started_points": marginal,
            "first_bench_points": first_bench,
            "marginal_gap_to_first_bench": (
                marginal - first_bench
                if marginal is not None and first_bench is not None
                else None
            ),
            "average_started_points": avg_started,
            "available_scored_players": len(rows),
        }

    return {
        "positions": pos_out,
        "optimal_tracked_starter_points": offense_points + idp_points,
    }


def season_weeks(points_data, season):
    players = points_data["seasons"][season]
    weeks = set()
    for rec in players.values():
        weekly = rec.get("weekly_points")
        if not isinstance(weekly, dict):
            continue
        for raw in weekly:
            try:
                week = int(raw)
            except (TypeError, ValueError):
                continue
            if 1 <= week <= REGULAR_SEASON_MAX_WEEK:
                weeks.add(week)
    return sorted(weeks)


def simulate_ruleset(points_data, season, structure):
    weeks = season_weeks(points_data, season)
    weekly_results = []
    for week in weeks:
        result = simulate_week(
            weekly_scores(points_data, season, week),
            structure,
        )
        result["week"] = week
        weekly_results.append(result)

    teams = int(structure["teams"])
    positions = {}
    for pos in TRACKED_POSITIONS:
        starts = [
            row["positions"][pos]["simulated_starts"] / teams
            for row in weekly_results
        ]
        marginal = [
            row["positions"][pos]["marginal_started_points"]
            for row in weekly_results
        ]
        avg_started = [
            row["positions"][pos]["average_started_points"]
            for row in weekly_results
        ]
        gap = [
            row["positions"][pos]["marginal_gap_to_first_bench"]
            for row in weekly_results
        ]
        positions[pos] = {
            "mean_simulated_starters_per_team_week": mean(starts),
            "median_simulated_starters_per_team_week": median(starts),
            "median_marginal_started_points": median(marginal),
            "p25_marginal_started_points": percentile(marginal, 0.25),
            "p75_marginal_started_points": percentile(marginal, 0.75),
            "median_average_started_points": median(avg_started),
            "median_gap_to_first_bench": median(gap),
        }

    return {
        "season": season,
        "weeks_simulated": weeks,
        "week_count": len(weeks),
        "structure": structure,
        "positions": positions,
        "weekly": weekly_results,
    }


def historical_teams(season_payload):
    weeks = int(season_payload.get("weeks_with_data") or 0)
    team_weeks = int(((season_payload.get("summary") or {}).get("team_weeks")) or 0)
    if weeks <= 0 or team_weeks <= 0:
        raise RuntimeError("historical team/week metadata missing")
    teams = team_weeks / weeks
    rounded = int(round(teams))
    if abs(teams - rounded) > 1e-9:
        raise RuntimeError("historical team count is not integral")
    return rounded


def validation_against_observed(simulated, observed_season):
    observed = (
        (observed_season.get("summary") or {})
        .get("effective_starters_per_team_week")
        or {}
    )
    positions = {}
    abs_errors = []
    for pos in TRACKED_POSITIONS:
        obs = float(observed.get(pos) or 0.0)
        sim = float(
            simulated["positions"][pos][
                "mean_simulated_starters_per_team_week"
            ]
        )
        err = sim - obs
        positions[pos] = {
            "observed_effective_starters_per_team_week": obs,
            "simulated_starters_per_team_week": sim,
            "error": err,
            "absolute_error": abs(err),
        }
        abs_errors.append(abs(err))

    return {
        "positions": positions,
        "mean_absolute_error_starters_per_team_week": mean(abs_errors),
        "max_absolute_error_starters_per_team_week": max(abs_errors),
    }


def validate_phase1(phase1):
    if phase1.get("method_version") != PHASE1_METHOD:
        raise RuntimeError("unexpected Position Weight V2 Phase-1 method")
    for field in (
        "deployment_authorized",
        "position_weight_change_authorized",
        "replacement_rank_change_authorized",
        "production_v2_change_authorized",
        "transform_change_authorized",
        "scale_change_authorized",
    ):
        if phase1.get(field) is not False:
            raise RuntimeError(f"Phase 1 guardrail changed: {field}")
    if phase1.get("frozen_prospective_experiments_touched") is not False:
        raise RuntimeError("Phase 1 says frozen experiments were touched")


def build_result(fetch_current: bool):
    phase1 = read_json(PHASE1_JSON)
    validate_phase1(phase1)
    points_data = read_json(WEEKLY_POINTS_JSON)
    historical = read_json(HISTORICAL_LINEUP_JSON)
    config = read_json(CONFIG_JSON)

    hist_seasons = historical.get("seasons")
    if not isinstance(hist_seasons, dict):
        raise RuntimeError("historical lineup seasons missing")

    historical_replays = {}
    validation = {}
    for season in SEASONS:
        h = hist_seasons.get(season)
        if not isinstance(h, dict):
            raise RuntimeError(f"historical lineup data missing {season}")
        structure = slot_structure(
            h["roster_positions"],
            historical_teams(h),
        )
        sim = simulate_ruleset(points_data, season, structure)
        historical_replays[season] = sim
        validation[season] = validation_against_observed(sim, h)

    existing = read_json(OUTPUT_JSON) if (not fetch_current and OUTPUT_JSON.exists()) else None

    if fetch_current:
        league_id = str(config.get("league_id") or "")
        if not league_id:
            raise RuntimeError("config.json missing league_id")
        league = fetch_current_league(league_id)
        roster_positions = league.get("roster_positions")
        teams = int(league.get("total_rosters") or 0)
        if not isinstance(roster_positions, list) or not roster_positions:
            raise RuntimeError("current Sleeper league missing roster_positions")
        if teams <= 0:
            raise RuntimeError("current Sleeper league missing total_rosters")
        current_source = {
            "league_id": league_id,
            "season": str(league.get("season") or config.get("season") or ""),
            "total_rosters": teams,
            "roster_positions": list(roster_positions),
            "fetched_at_epoch": time.time(),
        }
    else:
        if not existing:
            raise RuntimeError("--check requires existing Phase-2 output")
        current_source = existing.get("current_2026_ruleset_source")
        if not isinstance(current_source, dict):
            raise RuntimeError("stored current ruleset source missing")
        roster_positions = current_source.get("roster_positions")
        teams = int(current_source.get("total_rosters") or 0)
        if not isinstance(roster_positions, list) or teams <= 0:
            raise RuntimeError("stored current ruleset source malformed")

    current_structure = slot_structure(list(roster_positions), teams)
    current_rules = {
        season: simulate_ruleset(points_data, season, current_structure)
        for season in SEASONS
    }

    current_summary = {}
    ruleset_change = {}
    for pos in TRACKED_POSITIONS:
        demand_values = [
            current_rules[s]["positions"][pos][
                "mean_simulated_starters_per_team_week"
            ]
            for s in SEASONS
        ]
        marginal_values = [
            current_rules[s]["positions"][pos][
                "median_marginal_started_points"
            ]
            for s in SEASONS
        ]
        starter_values = [
            current_rules[s]["positions"][pos][
                "median_average_started_points"
            ]
            for s in SEASONS
        ]
        current_summary[pos] = {
            "mean_structural_starters_per_team_week_2026_rules": mean(demand_values),
            "median_marginal_started_points_2026_rules": median(marginal_values),
            "median_average_started_points_2026_rules": median(starter_values),
            "by_scoring_sample_season": {
                s: current_rules[s]["positions"][pos]
                for s in SEASONS
            },
        }

        old_values = [
            float(
                (((hist_seasons[s].get("summary") or {})
                  .get("effective_starters_per_team_week") or {})
                 .get(pos) or 0.0)
            )
            for s in SEASONS
        ]
        old_mean = mean(old_values)
        new_mean = current_summary[pos][
            "mean_structural_starters_per_team_week_2026_rules"
        ]
        ruleset_change[pos] = {
            "historical_observed_old_rules_mean": old_mean,
            "simulated_2026_rules_mean": new_mean,
            "delta_starters_per_team_week": new_mean - old_mean,
            "pct_change_vs_old_observed": (
                (new_mean - old_mean) / old_mean
                if old_mean not in (None, 0) else None
            ),
        }

    validation_maes = [
        validation[s]["mean_absolute_error_starters_per_team_week"]
        for s in SEASONS
    ]

    return round_numbers({
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_CURRENT_RULESET_STRUCTURAL_SIMULATION",
        "deployment_authorized": False,
        "position_weight_change_authorized": False,
        "replacement_rank_change_authorized": False,
        "production_v2_change_authorized": False,
        "transform_change_authorized": False,
        "scale_change_authorized": False,
        "frozen_prospective_experiments_touched": False,
        "allocator_scope": {
            "historical_scoring_sample_seasons": list(SEASONS),
            "league_wide_structural_allocator": True,
            "post_week_optimal_points": True,
            "individual_team_roster_constraints_modeled": False,
            "purpose": (
                "estimate structural slot demand under a specified ruleset, "
                "not reproduce exact manager-feasible lineups"
            ),
        },
        "historical_validation": {
            "by_season": validation,
            "mean_of_season_mae_starters_per_team_week": mean(validation_maes),
        },
        "current_2026_ruleset_source": current_source,
        "current_2026_structure": current_structure,
        "current_rules_on_historical_scoring_samples": current_rules,
        "current_2026_structural_summary": current_summary,
        "ruleset_change_vs_historical_observed": ruleset_change,
        "phase3_handoff": {
            "position_weight_candidates_authorized": False,
            "use_current_rules_structural_demand": True,
            "use_current_rules_marginal_scoring": True,
            "retain_historical_observed_demand_as_validation_only": True,
            "replacement_rank_families_remain_frozen": True,
        },
        "input_sha256": {
            str(CONFIG_JSON.relative_to(REPO_ROOT)): sha256(CONFIG_JSON),
            str(PHASE1_JSON.relative_to(REPO_ROOT)): sha256(PHASE1_JSON),
            str(WEEKLY_POINTS_JSON.relative_to(REPO_ROOT)): sha256(WEEKLY_POINTS_JSON),
            str(HISTORICAL_LINEUP_JSON.relative_to(REPO_ROOT)): sha256(HISTORICAL_LINEUP_JSON),
        },
    })


def fmt(value, digits=3):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def pct(value):
    if value is None:
        return "—"
    return f"{100.0 * float(value):+.1f}%"


def render_md(result):
    current = result["current_2026_ruleset_source"]
    lines = [
        "# Position Weight / Cross-Position Economics V2 — Phase 2 Ruleset Simulation",
        "",
        "**Research only. No POSITION_WEIGHT change is authorized.**",
        "",
        f"Method: `{result['method_version']}`",
        "",
        "## Current ruleset snapshot",
        "",
        f"- Sleeper season: **{current.get('season')}**",
        f"- Teams: **{current.get('total_rosters')}**",
        f"- `roster_positions`: `{current.get('roster_positions')}`",
        "",
        "## Historical allocator validation",
        "",
        "| Season | Mean abs error starters/team-week | Max abs error |",
        "|---|---:|---:|",
    ]

    for season in SEASONS:
        v = result["historical_validation"]["by_season"][season]
        lines.append(
            f"| {season} | {fmt(v['mean_absolute_error_starters_per_team_week'])} | "
            f"{fmt(v['max_absolute_error_starters_per_team_week'])} |"
        )

    lines += [
        "",
        "| Pos | 2024 observed/sim | 2025 observed/sim |",
        "|---|---|---|",
    ]
    for pos in TRACKED_POSITIONS:
        cells = []
        for season in SEASONS:
            row = result["historical_validation"]["by_season"][season]["positions"][pos]
            cells.append(
                f"{fmt(row['observed_effective_starters_per_team_week'])}/"
                f"{fmt(row['simulated_starters_per_team_week'])}"
            )
        lines.append(f"| {pos} | {cells[0]} | {cells[1]} |")

    lines += [
        "",
        "## 2026-rules structural demand",
        "",
        "| Pos | Structural starters/team-week | Median marginal-start pts | Median avg starter pts | Old observed demand | Ruleset Δ |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for pos in TRACKED_POSITIONS:
        cur = result["current_2026_structural_summary"][pos]
        delta = result["ruleset_change_vs_historical_observed"][pos]
        lines.append(
            f"| {pos} | "
            f"{fmt(cur['mean_structural_starters_per_team_week_2026_rules'])} | "
            f"{fmt(cur['median_marginal_started_points_2026_rules'])} | "
            f"{fmt(cur['median_average_started_points_2026_rules'])} | "
            f"{fmt(delta['historical_observed_old_rules_mean'])} | "
            f"{fmt(delta['delta_starters_per_team_week'])} "
            f"({pct(delta['pct_change_vs_old_observed'])}) |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "Historical validation measures how closely the league-wide optimal structural allocator "
        "resembles real manager starts under the same old rules. It is not expected to be perfect "
        "because ownership constraints and manager decisions are intentionally omitted.",
        "",
        "The 2026-rules simulation then holds the player-performance samples fixed and changes only "
        "the slot structure, so the resulting positional demand movement is attributable to today's rules.",
        "",
        "This phase still does **not** create candidate POSITION_WEIGHT values.",
        "",
        "## Guardrails",
        "",
        "- deployment_authorized: **false**",
        "- position_weight_change_authorized: **false**",
        "- replacement_rank_change_authorized: **false**",
        "- production_v2_change_authorized: **false**",
        "- transform_change_authorized: **false**",
        "- scale_change_authorized: **false**",
        "- frozen prospective experiments touched: **false**",
        "",
    ]
    return "\n".join(lines)


def run_selftest():
    scores = {pos: [] for pos in TRACKED_POSITIONS}
    scores["QB"] = [("q1", 30.0), ("q2", 25.0), ("q3", 5.0)]
    scores["RB"] = [("r1", 20.0), ("r2", 15.0), ("r3", 14.0)]
    scores["WR"] = [("w1", 18.0), ("w2", 17.0), ("w3", 16.0)]
    scores["TE"] = [("t1", 12.0), ("t2", 8.0), ("t3", 7.0)]
    scores["DL"] = [("d1", 10.0), ("d2", 9.0)]
    scores["LB"] = [("l1", 11.0), ("l2", 10.0)]
    scores["DB"] = [("b1", 8.0), ("b2", 7.0)]

    starts, total = distribute_flex_slots(
        OFFENSE,
        {p: 1 for p in OFFENSE},
        scores,
        {"FLEX": 1, "SUPER_FLEX": 1},
    )
    assert starts["QB"] == 2
    assert starts["WR"] == 2
    assert starts["RB"] == 1
    assert starts["TE"] == 1
    assert abs(total - 122.0) < 1e-12

    structure = slot_structure(
        ["QB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX",
         "DL", "LB", "DB", "IDP_FLEX", "BN"],
        1,
    )
    assert structure["dedicated_league"]["QB"] == 1
    assert structure["flex_league"]["SUPER_FLEX"] == 1
    print("PASS Position Weight V2 Phase 2 self-test.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    if args.check:
        result = build_result(fetch_current=False)
        rendered_json = json.dumps(result, indent=2, sort_keys=True) + "\n"
        rendered_md = render_md(result).rstrip() + "\n"
        if not OUTPUT_JSON.exists() or not OUTPUT_MD.exists():
            raise RuntimeError("Phase 2 outputs missing")
        if OUTPUT_JSON.read_text(encoding="utf-8") != rendered_json:
            raise RuntimeError("Phase 2 JSON is stale or non-deterministic")
        if OUTPUT_MD.read_text(encoding="utf-8") != rendered_md:
            raise RuntimeError("Phase 2 Markdown is stale or non-deterministic")
        for field in (
            "deployment_authorized",
            "position_weight_change_authorized",
            "replacement_rank_change_authorized",
            "production_v2_change_authorized",
            "transform_change_authorized",
            "scale_change_authorized",
        ):
            if result.get(field) is not False:
                raise RuntimeError(f"guardrail failed: {field}")
        if result.get("frozen_prospective_experiments_touched") is not False:
            raise RuntimeError("frozen prospective guardrail failed")
        print("PASS Position Weight V2 Phase 2 checks.")
        return

    result = build_result(fetch_current=True)
    rendered_json = json.dumps(result, indent=2, sort_keys=True) + "\n"
    rendered_md = render_md(result).rstrip() + "\n"

    if args.write:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(rendered_json, encoding="utf-8")
        OUTPUT_MD.write_text(rendered_md, encoding="utf-8")
        print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
        print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")
    else:
        print(rendered_md)


if __name__ == "__main__":
    main()

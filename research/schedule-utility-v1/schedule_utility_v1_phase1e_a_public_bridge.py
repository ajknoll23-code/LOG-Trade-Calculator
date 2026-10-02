#!/usr/bin/env python3
"""
Schedule Utility V1 — Phase 1E-A public LOG-SAPA implementation audit.

Reads public nflverse 2026 weekly player stats and schedules.
Strictly limits predictor stats to regular-season Weeks 1-3.
Does NOT read the private 4for4 bundle.
Does NOT read Week-4 player outcome rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

SEASON = 2026
TARGET_WEEK = 4
ALLOWED_STAT_WEEKS = {1, 2, 3}

TEAM_ALIAS = {
    "ARZ": "ARI",
    "BLT": "BAL",
    "CLV": "CLE",
    "HST": "HOU",
    "JAC": "JAX",
    "LA": "LAR",
    "LAR": "LAR",
    "LV": "LV",
    "OAK": "LV",
    "SD": "LAC",
    "LAC": "LAC",
    "STL": "LAR",
    "WSH": "WAS",
}


def canon_team(value: object) -> str:
    s = str(value or "").strip().upper()
    if not s:
        raise ValueError("blank team")
    return TEAM_ALIAS.get(s, s)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_frozen(path: Path):
    spec = importlib.util.spec_from_file_location("log_sapa_v1_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen implementation: {path}")
    mod = importlib.util.module_from_spec(spec)
    # Python 3.13 dataclasses resolves annotations through sys.modules
    # while the module body executes. Register before exec_module.
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_schedule_edges(rows: list[dict[str, str]]) -> tuple[dict[tuple[int, int, str], str], dict]:
    required = {"season", "week", "away_team", "home_team"}
    if not rows:
        raise ValueError("empty schedule")
    missing = required - set(rows[0])
    if missing:
        raise KeyError(f"schedule missing fields: {sorted(missing)}")

    edges: dict[tuple[int, int, str], str] = {}
    games = 0
    for row in rows:
        try:
            season = int(row["season"])
            week = int(row["week"])
        except (TypeError, ValueError):
            continue
        if season != SEASON or week not in ALLOWED_STAT_WEEKS:
            continue

        game_type = str(row.get("game_type") or row.get("season_type") or "REG").upper()
        if game_type not in {"REG", "REGULAR"}:
            continue

        away = canon_team(row["away_team"])
        home = canon_team(row["home_team"])
        if away == home:
            raise ValueError(f"invalid same-team game: {away}")

        for off, deff in ((away, home), (home, away)):
            key = (season, week, off)
            if key in edges and edges[key] != deff:
                raise ValueError(f"conflicting schedule edge: {key}")
            edges[key] = deff
        games += 1

    # Weeks 1-3 should contain 16 NFL games each in 2026.
    if games != 48 or len(edges) != 96:
        raise ValueError(f"unexpected Weeks 1-3 schedule coverage: games={games}, edges={len(edges)}")

    teams = sorted({k[2] for k in edges})
    opps = sorted(set(edges.values()))
    if len(set(teams) | set(opps)) != 32:
        raise ValueError("expected 32 NFL teams in schedule")

    return edges, {
        "regular_season_games_weeks_1_3": games,
        "offense_schedule_edges_weeks_1_3": len(edges),
        "distinct_teams": 32,
    }


def adapt_player_rows(rows: list[dict[str, str]], frozen) -> tuple[list[dict], dict]:
    if not rows:
        raise ValueError("empty player stats")
    fields = set(rows[0])
    context_required = {"season", "week", "season_type", "position"}
    missing_context = context_required - fields
    if missing_context:
        raise KeyError(f"weekly stats missing context fields: {sorted(missing_context)}")

    # nflverse's current player-stats schema uses `team`; the frozen
    # LOG-SAPA implementation expects `recent_team`. This is a source
    # schema adapter only, not a predictor-parameter change.
    has_recent_team = "recent_team" in fields
    has_team = "team" in fields
    if not has_recent_team and not has_team:
        raise KeyError(
            "weekly stats missing team identity: expected `team` or `recent_team`"
        )

    missing_stats = set(frozen.STAT_FIELDS) - fields
    if missing_stats:
        raise KeyError(f"weekly stats missing frozen stat fields: {sorted(missing_stats)}")

    kept: list[dict] = []
    source_rows_2026 = 0
    future_or_target_rows_seen_but_not_admitted = 0
    nonreg_rows_excluded = 0

    for row in rows:
        try:
            season = int(row["season"])
            week = int(row["week"])
        except (TypeError, ValueError):
            continue
        if season != SEASON:
            continue
        source_rows_2026 += 1

        st = str(row.get("season_type", "")).upper()
        if st not in {"REG", "REGULAR"}:
            nonreg_rows_excluded += 1
            continue

        if week not in ALLOWED_STAT_WEEKS:
            future_or_target_rows_seen_but_not_admitted += 1
            continue

        out = dict(row)
        out["season"] = season
        out["week"] = week
        out["season_type"] = "REG"

        recent_team_raw = row.get("recent_team")
        team_raw = row.get("team")
        if recent_team_raw not in (None, "") and team_raw not in (None, ""):
            recent_team_c = canon_team(recent_team_raw)
            team_c = canon_team(team_raw)
            if recent_team_c != team_c:
                raise ValueError(
                    f"conflicting team identity: recent_team={recent_team_c}, "
                    f"team={team_c}"
                )
            out["recent_team"] = recent_team_c
        elif recent_team_raw not in (None, ""):
            out["recent_team"] = canon_team(recent_team_raw)
        elif team_raw not in (None, ""):
            out["recent_team"] = canon_team(team_raw)
        else:
            raise ValueError("blank team identity in eligible player row")

        # position_group is optional in the frozen function; preserve if supplied.
        if "position_group" not in out:
            out["position_group"] = ""
        kept.append(out)

    if not kept:
        raise ValueError("no eligible Weeks 1-3 player rows")
    max_admitted_week = max(int(r["week"]) for r in kept)
    min_admitted_week = min(int(r["week"]) for r in kept)
    if min_admitted_week != 1 or max_admitted_week != 3:
        raise ValueError(
            f"predictor firewall failed: admitted weeks {min_admitted_week}..{max_admitted_week}"
        )

    return kept, {
        "source_rows_2026_seen": source_rows_2026,
        "predictor_rows_admitted_weeks_1_3": len(kept),
        "target_or_later_rows_seen_but_not_admitted": future_or_target_rows_seen_but_not_admitted,
        "nonregular_rows_excluded": nonreg_rows_excluded,
        "min_admitted_week": min_admitted_week,
        "max_admitted_week": max_admitted_week,
        "team_identity_source_adapter": (
            "recent_team_direct"
            if has_recent_team and not has_team
            else "team_to_recent_team"
            if has_team and not has_recent_team
            else "recent_team_and_team_conflict_checked"
        ),
    }


def compute_cells(frozen, player_rows: list[dict], edges: dict) -> dict:
    cell_defs = [
        ("QB_HALF", "QB", "HALF_PPR"),
        ("RB_HALF", "RB", "HALF_PPR"),
        ("WR_HALF", "WR", "HALF_PPR"),
        ("TE_HALF", "TE", "HALF_PPR"),
        ("RB_PPR", "RB", "PPR"),
        ("WR_PPR", "WR", "PPR"),
        ("TE_PPR", "TE", "PPR"),
    ]

    by_mode = {}
    out = {}

    for cell, position, mode in cell_defs:
        if mode not in by_mode:
            by_mode[mode] = frozen.aggregate_player_rows(player_rows, edges, mode)
        game_rows = by_mode[mode]
        raw = frozen.compute_log_sapa(
            game_rows,
            season=SEASON,
            target_week=TARGET_WEEK,
            position=position,
            scoring_mode=mode,
        )
        values = {team: d.get("log_sapa") for team, d in raw.items()}
        scores = frozen.rank_to_matchup_score(values)

        available = sorted(team for team, value in values.items() if value is not None)
        if len(available) != 32:
            raise ValueError(f"{cell}: expected 32 available defenses, got {len(available)}")
        if set(available) != set(scores):
            raise ValueError(f"{cell}: rank output team set mismatch")
        if any(scores[t] is None for t in available):
            raise ValueError(f"{cell}: missing normalized score despite raw availability")

        # Public data -> public derived team-level predictor is allowed.
        out[cell] = {
            "position": position,
            "scoring_mode": mode,
            "target_week": TARGET_WEEK,
            "defense_count": len(available),
            "raw_log_sapa_by_defense": {
                team: round(float(values[team]), 12) for team in sorted(values)
            },
            "normalized_matchup_score_by_defense": {
                team: round(float(scores[team]), 12) for team in sorted(scores)
            },
            "min_log_sapa": round(min(float(values[t]) for t in available), 12),
            "max_log_sapa": round(max(float(values[t]) for t in available), 12),
        }

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True)
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--frozen", required=True)
    ap.add_argument("--expected-frozen-sha256", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    stats_path = Path(args.stats)
    schedule_path = Path(args.schedule)
    frozen_path = Path(args.frozen)

    observed_frozen_sha = sha256(frozen_path)
    if observed_frozen_sha != args.expected_frozen_sha256:
        raise RuntimeError(
            f"frozen implementation SHA mismatch: {observed_frozen_sha} != "
            f"{args.expected_frozen_sha256}"
        )

    frozen = load_frozen(frozen_path)
    if frozen.METRIC_ID != "LOG-SAPA-V1":
        raise RuntimeError("unexpected frozen metric ID")

    schedule_rows = read_csv(schedule_path)
    edges, schedule_audit = build_schedule_edges(schedule_rows)

    source_player_rows = read_csv(stats_path)
    admitted_player_rows, row_audit = adapt_player_rows(source_player_rows, frozen)

    cells = compute_cells(frozen, admitted_player_rows, edges)

    result = {
        "schema_version": 1,
        "study_id": "schedule-utility-v1",
        "phase": "1E-A",
        "status": "PASS_PUBLIC_IMPLEMENTATION_READY_PRIVATE_BRIDGE_PENDING",
        "metric_id": "LOG-SAPA-V1",
        "season": SEASON,
        "target_week": TARGET_WEEK,
        "predictor_stat_weeks": [1, 2, 3],
        "outcome_data_read": False,
        "target_week_player_rows_admitted": False,
        "historical_target_outcomes_opened": False,
        "private_4for4_rows_read_in_github": False,
        "production_change_authorized": False,
        "phase2_outcome_test_authorized": False,
        "frozen_implementation": {
            "path": str(frozen_path),
            "sha256": observed_frozen_sha,
            "parameters_changed": False,
        },
        "public_source_files": {
            "stats_player_week_2026_csv": {
                "sha256": sha256(stats_path),
                "url": (
                    "https://github.com/nflverse/nflverse-data/releases/download/"
                    "stats_player/stats_player_week_2026.csv"
                ),
            },
            "games_csv": {
                "sha256": sha256(schedule_path),
                "url": (
                    "https://github.com/nflverse/nflverse-data/releases/download/"
                    "schedules/games.csv"
                ),
            },
        },
        "schedule_audit": schedule_audit,
        "player_row_firewall": row_audit,
        "cells": cells,
        "private_bridge": {
            "status": "PENDING_PRIVATE_PHASE_1E_B",
            "provider": "4for4",
            "provider_rows_committed": False,
            "expected_source_hashes": {
                "afpa_half": "57c1a228ae849496092ac8404be33072d974a6eb0c251646e58b579b0892b430",
                "qb_half": "d054b074162cfe748e22c4ce00dd3bf07aee97f3eaf04cd4c737be46c5d18b47",
                "rb_half": "1f54c87762ddfff9a47e7219c1e6ea48f4905507f37e119dfaf55c3b49b22f75",
                "wr_half": "c3ae5f0af52beaa3a258785b4dbbf63ca21dcf73847a067f1daa9391db9279e4",
                "te_half": "cfae6b10a1eb6dc428004c2a599f85f4d5ab86499d3585e40e260adc03ddd325",
                "rb_ppr": "cda98824bc3a1f79ccc016a93e31da80c6c477eac1e5281536acc005979856b3",
                "wr_ppr": "ef323c774adcc680944ee2db8414f598eb96b714d09ec44263ba3a49309c8d4d",
                "te_ppr": "cdab088a1a128305acfd7820edf2c19241135a24be1a0f852dd9b8a7cdc1894f",
            },
            "frozen_pass_rule": {
                "median_spearman_at_least": 0.60,
                "cells_at_or_above_0_50_at_least": 6,
                "no_cell_below": 0.30,
            },
        },
        "next_phase": {
            "phase": "1E-B",
            "name": "private 4for4 source bridge freeze",
            "historical_target_outcomes_may_be_opened": False,
        },
    }

    Path(args.out).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "decision": result["status"],
        "cells": {k: v["defense_count"] for k, v in cells.items()},
        "max_predictor_stat_week": row_audit["max_admitted_week"],
        "private_bridge": result["private_bridge"]["status"],
        "outcomes_opened": False,
    }, indent=2))


if __name__ == "__main__":
    main()

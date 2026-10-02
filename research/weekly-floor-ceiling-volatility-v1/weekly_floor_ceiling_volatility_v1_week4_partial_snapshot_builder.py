#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import weekly_floor_ceiling_volatility_v1_snapshot_builder as frozen

SEASON = 2026
ORIGIN_WEEK = 4
EXCLUDED_TEAMS = {"PIT", "CLE"}
POSITIONS = ("QB", "RB", "WR", "TE")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_schedule_state(schedule_path, now):
    rows = frozen.read_csv(schedule_path)
    games = []
    for row in rows:
        try:
            season = int(row.get("season"))
            week = int(row.get("week"))
        except (TypeError, ValueError):
            continue
        if season != SEASON or week != ORIGIN_WEEK:
            continue
        if frozen.norm(row.get("game_type")).upper() != "REG":
            continue
        games.append({
            "game_id": frozen.norm(row.get("game_id")),
            "away_team": frozen.canon_team(row.get("away_team")),
            "home_team": frozen.canon_team(row.get("home_team")),
            "kickoff_utc": frozen.parse_kickoff_utc(
                row.get("gameday"), row.get("gametime")
            ),
        })

    if len(games) != 16:
        raise RuntimeError(f"EXPECTED_16_WEEK4_GAMES_FOUND_{len(games)}")

    started = [g for g in games if g["kickoff_utc"] <= now]
    remaining = [g for g in games if g["kickoff_utc"] > now]

    if len(started) != 1 or len(remaining) != 15:
        raise RuntimeError(
            "WEEK4_PARTIAL_SALVAGE_WINDOW_CLOSED_OR_UNEXPECTED "
            f"started={len(started)} remaining={len(remaining)}"
        )

    missed = started[0]
    if {missed["away_team"], missed["home_team"]} != EXCLUDED_TEAMS:
        raise RuntimeError(
            f"UNEXPECTED_STARTED_GAME {missed['away_team']}-{missed['home_team']}"
        )

    cutoff = min(g["kickoff_utc"] for g in remaining)
    if not now < cutoff:
        raise RuntimeError(
            f"PARTIAL_FREEZE_DEADLINE_MISSED now={now.isoformat()} "
            f"cutoff={cutoff.isoformat()}"
        )

    return missed, remaining, cutoff


def build(html_path, schedule_path, protocol_path, amendment_path, out_path, manifest_path):
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    amendment = json.loads(Path(amendment_path).read_text(encoding="utf-8"))

    assert protocol["status"] == "PREREGISTERED_PROSPECTIVE_ONLY_VALIDATION"
    assert protocol["season"] == SEASON
    assert protocol["first_candidate_origin_week"] == ORIGIN_WEEK

    assert amendment["status"] == (
        "PREREGISTERED_AMENDMENT_BEFORE_REMAINING_WEEK4_GAMES"
    )
    assert amendment["week4_only_origin_amendment"]["excluded_teams"] == [
        "CLE", "PIT"
    ]
    assert amendment["governance"]["outcome_association_opened"] is False

    now = datetime.now(timezone.utc)
    missed, remaining, cutoff = load_schedule_state(schedule_path, now)

    raw = Path(html_path).read_bytes()
    soup = BeautifulSoup(raw, "html.parser")
    text = frozen.norm(soup.get_text(" ", strip=True))
    lower = text.lower()

    if "logged-out mode uses half-ppr" not in lower:
        raise RuntimeError("HALF_PPR_PUBLIC_MODE_NOT_VERIFIED_AT_FREEZE")

    snap = frozen.extract_snapshot_meta(text)
    if snap["season"] != SEASON or snap["week"] != ORIGIN_WEEK:
        raise RuntimeError(
            f"NEXTDYNE_WRONG_ORIGIN current={snap['season']}-W{snap['week']}"
        )

    _, headers, resolved, trs = frozen.resolve_table(soup)

    raw_rows = []
    seen = set()
    duplicate_count = 0
    excluded_player_rows = 0

    for tr in trs:
        cells = [
            frozen.norm(x.get_text(" ", strip=True))
            for x in tr.find_all(["th", "td"])
        ]
        if len(cells) < len(headers):
            continue

        def cell(key):
            idx = resolved[key]
            return cells[idx] if idx is not None and idx < len(cells) else None

        pos = frozen.norm(cell("pos")).upper()
        if pos not in POSITIONS:
            continue

        name = frozen.norm(cell("player"))
        team = frozen.canon_team(cell("team"))

        if team in EXCLUDED_TEAMS:
            excluded_player_rows += 1
            continue

        floor = frozen.safe_float(cell("floor"))
        proj = frozen.safe_float(cell("proj"))
        ceiling = frozen.safe_float(cell("ceiling"))

        if not name or not team:
            continue
        if floor is None or proj is None or ceiling is None:
            continue
        if ceiling < floor or proj < floor or proj > ceiling:
            continue

        key = f"{frozen.norm_name(name)}|{team}|{pos}"
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)

        width = ceiling - floor
        commitment_payload = json.dumps(
            [name, team, pos, floor, proj, ceiling],
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        raw_rows.append({
            "stable_key": key,
            "player_name": name,
            "team": team,
            "position": pos,
            "floor": floor,
            "projection": proj,
            "ceiling": ceiling,
            "width": width,
            "source_row_commitment_sha256": frozen.sha256_bytes(
                commitment_payload
            ),
        })

    if len(raw_rows) < 140:
        raise RuntimeError(f"IMPLAUSIBLY_FEW_VALID_REMAINING_ROWS {len(raw_rows)}")

    if any(r["team"] in EXCLUDED_TEAMS for r in raw_rows):
        raise RuntimeError("EXCLUDED_GAME_PLAYER_LEAK")

    by_pos = defaultdict(list)
    for row in raw_rows:
        by_pos[row["position"]].append(row)

    output_rows = []
    counts = {}

    for pos in POSITIONS:
        rows = by_pos[pos]
        if len(rows) < 12:
            raise RuntimeError(
                f"INSUFFICIENT_REMAINING_ROWS_FOR_POSITION {pos} {len(rows)}"
            )
        counts[pos] = len(rows)

        pct_floor = frozen.midrank_percentiles(
            [(r["stable_key"], r["floor"]) for r in rows]
        )
        pct_proj = frozen.midrank_percentiles(
            [(r["stable_key"], r["projection"]) for r in rows]
        )
        pct_ceil = frozen.midrank_percentiles(
            [(r["stable_key"], r["ceiling"]) for r in rows]
        )
        pct_width = frozen.midrank_percentiles(
            [(r["stable_key"], r["width"]) for r in rows]
        )

        for r in sorted(rows, key=lambda x: x["stable_key"]):
            k = r["stable_key"]
            output_rows.append({
                "stable_key": k,
                "player_name": r["player_name"],
                "team": r["team"],
                "position": r["position"],
                "projection_strength_pct": round(pct_proj[k], 9),
                "floor_strength_pct": round(pct_floor[k], 9),
                "ceiling_strength_pct": round(pct_ceil[k], 9),
                "volatility_width_pct": round(pct_width[k], 9),
                "floor_resilience": round(
                    pct_floor[k] - pct_proj[k], 9
                ),
                "ceiling_upside": round(
                    pct_ceil[k] - pct_proj[k], 9
                ),
                "source_row_commitment_sha256": r[
                    "source_row_commitment_sha256"
                ],
            })

    snapshot = {
        "schema_version": 1,
        "study_id": "weekly-floor-ceiling-volatility-v1",
        "phase": "prospective-predictor-snapshot",
        "status": "FROZEN_PREKICKOFF_PARTIAL_ORIGIN_SNAPSHOT",
        "season": SEASON,
        "origin_week": ORIGIN_WEEK,
        "origin_label": "PARTIAL_ORIGIN_15_OF_16_GAMES",
        "counts_as_one_origin_under_amended_contract": True,
        "freeze_runtime_utc": now.isoformat(),
        "earliest_remaining_kickoff_utc": cutoff.isoformat(),
        "excluded_completed_game": {
            "game_id": missed["game_id"],
            "away_team": missed["away_team"],
            "home_team": missed["home_team"],
            "kickoff_utc": missed["kickoff_utc"].isoformat(),
        },
        "remaining_game_ids": sorted(g["game_id"] for g in remaining),
        "source": {
            "provider": "NextDyne",
            "url": "https://www.nextdyne.io/tools/dynasty-weekly-projections",
            "response_sha256": sha256(html_path),
            "model_version": snap["model_version"],
            "source_snapshot_display": snap["snapshot_display"],
            "scoring_mode": "logged-out Half-PPR",
        },
        "predictor_contract": {
            "raw_floor_projection_ceiling_values_persisted": False,
            "within_position_midrank_percentiles": True,
            "percentile_universe": (
                "Week 4 players from the 15 not-yet-started games only"
            ),
            "excluded_teams": ["CLE", "PIT"],
            "floor_resilience_definition": (
                "floor_strength_pct - projection_strength_pct"
            ),
            "ceiling_upside_definition": (
                "ceiling_strength_pct - projection_strength_pct"
            ),
            "volatility_width_definition": (
                "within-position percentile of (ceiling - floor)"
            ),
            "overall_score_authorized": False,
        },
        "coverage": {
            "week_game_count": 16,
            "included_game_count": 15,
            "excluded_game_count": 1,
            "row_count": len(output_rows),
            "by_position": counts,
            "excluded_player_rows": excluded_player_rows,
            "duplicate_rows_dropped": duplicate_count,
        },
        "rows": output_rows,
        "governance": {
            "realized_outcomes_read": False,
            "outcome_association_opened": False,
            "production_change_authorized": False,
            "user_facing_display_authorized": False,
            "fundamental_value_effect_authorized": False,
            "package_adjustment_effect_authorized": False,
            "team_utility_effect_authorized": False,
            "trade_value_effect_authorized": False,
            "trade_verdict_effect_authorized": False,
            "projection_adjustment_authorized": False,
        },
    }

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "study_id": "weekly-floor-ceiling-volatility-v1",
        "origin": "2026-W04",
        "origin_label": "PARTIAL_ORIGIN_15_OF_16_GAMES",
        "status": "PASS_PREKICKOFF_PARTIAL_ORIGIN_FREEZE",
        "counts_as_one_origin_under_amended_contract": True,
        "original_protocol_sha256": sha256(protocol_path),
        "amendment_sha256": sha256(amendment_path),
        "partial_snapshot_builder_sha256": sha256(Path(__file__)),
        "snapshot_sha256": sha256(out),
        "source_html_sha256": sha256(html_path),
        "schedule_sha256": sha256(schedule_path),
        "excluded_completed_game": snapshot["excluded_completed_game"],
        "earliest_remaining_kickoff_utc": cutoff.isoformat(),
        "remaining_game_ids": snapshot["remaining_game_ids"],
        "freeze_runtime_utc": now.isoformat(),
        "raw_provider_values_persisted": False,
        "realized_outcomes_read": False,
        "production_change_authorized": False,
        "leave_week4_out_sensitivity_required": True,
    }

    Path(manifest_path).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": snapshot["status"],
        "origin": "2026-W04",
        "origin_label": snapshot["origin_label"],
        "included_games": 15,
        "excluded_game": "PIT-CLE",
        "row_count": len(output_rows),
        "by_position": counts,
        "counts_as_one_origin": True,
        "outcomes_read": False,
        "production_authorized": False,
    }, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--amendment", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()

    build(
        args.html,
        args.schedule,
        args.protocol,
        args.amendment,
        args.out,
        args.manifest,
    )


if __name__ == "__main__":
    main()

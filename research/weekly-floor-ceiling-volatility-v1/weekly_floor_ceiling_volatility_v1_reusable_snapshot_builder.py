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

POSITIONS = ("QB", "RB", "WR", "TE")
ALLOWED_ORIGIN_WEEKS = tuple(range(5, 18))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def week_cutoff(schedule_path, season, origin_week):
    rows = frozen.read_csv(schedule_path)
    games = []
    for row in rows:
        try:
            row_season = int(row.get("season"))
            row_week = int(row.get("week"))
        except (TypeError, ValueError):
            continue
        if row_season != season:
            continue
        if frozen.norm(row.get("game_type")).upper() != "REG":
            continue
        if row_week != origin_week:
            continue
        games.append(
            (
                frozen.parse_kickoff_utc(
                    row.get("gameday"), row.get("gametime")
                ),
                frozen.norm(row.get("game_id")),
            )
        )

    if not games:
        raise RuntimeError(
            f"NO_{season}_WEEK{origin_week}_REG_GAMES_IN_SCHEDULE"
        )
    games.sort()
    return games[0][0], [g[1] for g in games]


def build(
    html_path,
    schedule_path,
    protocol_path,
    bridge_path,
    season,
    origin_week,
    out_path,
    manifest_path,
):
    if origin_week not in ALLOWED_ORIGIN_WEEKS:
        raise RuntimeError(
            f"ORIGIN_WEEK_OUTSIDE_B39_SCOPE week={origin_week}"
        )

    protocol = json.loads(
        Path(protocol_path).read_text(encoding="utf-8")
    )
    bridge = json.loads(
        Path(bridge_path).read_text(encoding="utf-8")
    )

    assert protocol["status"] == "PREREGISTERED_PROSPECTIVE_ONLY_VALIDATION"
    assert protocol["season"] == season
    assert protocol["first_candidate_origin_week"] == 4
    assert protocol["prospective_origin_contract"][
        "primary_origin_count_required"
    ] == 8
    assert protocol["prospective_origin_contract"]["no_backfill"] is True

    assert bridge["status"] == (
        "PREREGISTERED_OPERATIONAL_GENERALIZATION_BEFORE_WEEK5_CAPTURE"
    )
    assert bridge["full_week_capture_contract"]["allowed_origin_weeks"] == list(
        ALLOWED_ORIGIN_WEEKS
    )
    assert bridge["full_week_capture_contract"][
        "persistent_team_exclusions"
    ] == []
    assert bridge["week4_exception_propagates_forward"] is False

    now = datetime.now(timezone.utc)
    cutoff, game_ids = week_cutoff(
        schedule_path, season, origin_week
    )
    if not now < cutoff:
        raise RuntimeError(
            f"FREEZE_DEADLINE_MISSED_NO_BACKFILL "
            f"season={season} week={origin_week} "
            f"now={now.isoformat()} cutoff={cutoff.isoformat()}"
        )

    raw = Path(html_path).read_bytes()
    soup = BeautifulSoup(raw, "html.parser")
    text = frozen.norm(soup.get_text(" ", strip=True))
    lower = text.lower()

    if "logged-out mode uses half-ppr" not in lower:
        raise RuntimeError(
            "HALF_PPR_PUBLIC_MODE_NOT_VERIFIED_AT_FREEZE"
        )

    snap = frozen.extract_snapshot_meta(text)
    if snap["season"] != season or snap["week"] != origin_week:
        raise RuntimeError(
            f"NEXTDYNE_WRONG_ORIGIN "
            f"expected={season}-W{origin_week} "
            f"current={snap['season']}-W{snap['week']}"
        )

    _, headers, resolved, trs = frozen.resolve_table(soup)

    raw_rows = []
    seen = set()
    duplicate_count = 0

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
        floor = frozen.safe_float(cell("floor"))
        proj = frozen.safe_float(cell("proj"))
        ceiling = frozen.safe_float(cell("ceiling"))

        if not name or not team:
            continue
        if floor is None or proj is None or ceiling is None:
            continue
        if ceiling < floor or proj < floor or proj > ceiling:
            continue

        # IMPORTANT: no team is excluded in the reusable Week 5+ path.
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

    if len(raw_rows) < 150:
        raise RuntimeError(
            f"IMPLAUSIBLY_FEW_VALID_ROWS {len(raw_rows)}"
        )

    by_pos = defaultdict(list)
    for row in raw_rows:
        by_pos[row["position"]].append(row)

    output_rows = []
    counts = {}

    for pos in POSITIONS:
        rows = by_pos[pos]
        if not rows:
            raise RuntimeError(f"NO_ROWS_FOR_POSITION {pos}")
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
        "status": "FROZEN_PREKICKOFF_PREDICTOR_SNAPSHOT",
        "season": season,
        "origin_week": origin_week,
        "freeze_runtime_utc": now.isoformat(),
        "first_actual_kickoff_utc": cutoff.isoformat(),
        "source": {
            "provider": "NextDyne",
            "url": (
                "https://www.nextdyne.io/tools/"
                "dynasty-weekly-projections"
            ),
            "response_sha256": sha256(html_path),
            "model_version": snap["model_version"],
            "source_snapshot_display": snap["snapshot_display"],
            "scoring_mode": "logged-out Half-PPR",
        },
        "predictor_contract": {
            "raw_floor_projection_ceiling_values_persisted": False,
            "within_position_midrank_percentiles": True,
            "persistent_team_exclusions": [],
            "week4_partial_origin_exception_propagated": False,
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
            "row_count": len(output_rows),
            "by_position": counts,
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
        "origin": f"{season}-W{origin_week:02d}",
        "status": "PASS_PREKICKOFF_FREEZE",
        "protocol_sha256": sha256(protocol_path),
        "operational_bridge_sha256": sha256(bridge_path),
        "reusable_builder_sha256": sha256(Path(__file__)),
        "snapshot_sha256": sha256(out),
        "source_html_sha256": sha256(html_path),
        "schedule_sha256": sha256(schedule_path),
        "first_actual_kickoff_utc": cutoff.isoformat(),
        "week_game_ids": game_ids,
        "freeze_runtime_utc": now.isoformat(),
        "persistent_team_exclusions": [],
        "week4_exception_propagated": False,
        "raw_provider_values_persisted": False,
        "realized_outcomes_read": False,
        "production_change_authorized": False,
    }
    Path(manifest_path).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": snapshot["status"],
        "origin": f"{season}-W{origin_week:02d}",
        "first_actual_kickoff_utc": cutoff.isoformat(),
        "row_count": len(output_rows),
        "by_position": counts,
        "persistent_team_exclusions": [],
        "week4_exception_propagated": False,
        "raw_provider_values_persisted": False,
        "outcomes_read": False,
        "production_authorized": False,
    }, indent=2))


def selftest():
    vals = [("a", 1.0), ("b", 2.0), ("c", 2.0), ("d", 4.0)]
    expected = frozen.midrank_percentiles(vals)
    assert expected["a"] == 0.0
    assert abs(expected["b"] - 0.5) < 1e-12
    assert abs(expected["c"] - 0.5) < 1e-12
    assert expected["d"] == 1.0
    assert 5 in ALLOWED_ORIGIN_WEEKS
    assert 17 in ALLOWED_ORIGIN_WEEKS
    assert 4 not in ALLOWED_ORIGIN_WEEKS
    print("SELFTEST PASS")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html")
    ap.add_argument("--schedule")
    ap.add_argument("--protocol")
    ap.add_argument("--bridge")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--origin-week", type=int)
    ap.add_argument("--out")
    ap.add_argument("--manifest")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    required = {
        "html": args.html,
        "schedule": args.schedule,
        "protocol": args.protocol,
        "bridge": args.bridge,
        "origin_week": args.origin_week,
        "out": args.out,
        "manifest": args.manifest,
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        raise SystemExit(f"missing required args: {missing}")

    build(
        args.html,
        args.schedule,
        args.protocol,
        args.bridge,
        args.season,
        args.origin_week,
        args.out,
        args.manifest,
    )


if __name__ == "__main__":
    main()

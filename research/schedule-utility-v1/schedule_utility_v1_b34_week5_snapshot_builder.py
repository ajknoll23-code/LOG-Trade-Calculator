#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
from zoneinfo import ZoneInfo

SEASON = 2026
ORIGIN_WEEK = 5
HISTORY_WEEKS = (1, 2, 3, 4)
POSITIONS = ("QB", "RB", "WR", "TE")
SCORING_MODE = "HALF_PPR"
EXPECTED_CUTOFF_UTC = datetime.fromisoformat("2026-10-09T00:15:00+00:00")
EASTERN = ZoneInfo("America/New_York")

TEAM_ALIAS = {
    "ARZ": "ARI", "ARI": "ARI",
    "BLT": "BAL", "BAL": "BAL",
    "CLV": "CLE", "CLE": "CLE",
    "HST": "HOU", "HOU": "HOU",
    "JAC": "JAX", "JAX": "JAX",
    "LA": "LAR", "LAR": "LAR", "STL": "LAR",
    "OAK": "LV", "LV": "LV",
    "SD": "LAC", "LAC": "LAC",
    "WSH": "WAS", "WAS": "WAS",
}

POSITION_ALIAS = {
    "QB": "QB", "RB": "RB", "FB": "RB", "HB": "RB",
    "WR": "WR", "TE": "TE",
}


@dataclass(frozen=True)
class Game:
    game_id: str
    season: int
    week: int
    kickoff_utc: datetime
    away_team: str
    home_team: str
    completed: bool

    def opponent(self, team: str) -> str:
        if team == self.away_team:
            return self.home_team
        if team == self.home_team:
            return self.away_team
        raise KeyError(team)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def is_blank(v) -> bool:
    return v is None or str(v).strip() == ""


def canon_team(v) -> str:
    s = str(v or "").strip().upper()
    if not s:
        raise ValueError("blank team")
    return TEAM_ALIAS.get(s, s)


def canon_position(v):
    s = str(v or "").strip().upper()
    if not s:
        return None
    return POSITION_ALIAS.get(s)


def parse_kickoff_utc(gameday, gametime) -> datetime:
    d = str(gameday or "").strip()
    t = str(gametime or "").strip()
    if not d or not t:
        raise ValueError(f"missing gameday/gametime: {d!r} {t!r}")
    local = datetime.fromisoformat(f"{d}T{t}:00").replace(tzinfo=EASTERN)
    return local.astimezone(timezone.utc)


def load_frozen(path: Path):
    spec = importlib.util.spec_from_file_location("log_sapa_v1_b34", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import frozen LOG-SAPA")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


def load_2026_schedule(path: Path):
    rows = read_csv(path)
    if not rows:
        raise ValueError("empty schedule source")
    required = {
        "game_id", "season", "game_type", "week", "gameday", "gametime",
        "away_team", "home_team", "away_score", "home_score",
    }
    missing = required - set(rows[0])
    if missing:
        raise KeyError(f"schedule missing columns: {sorted(missing)}")

    games = {}
    for row in rows:
        try:
            season = int(row["season"])
            week = int(row["week"])
        except (TypeError, ValueError):
            continue
        if season != SEASON or str(row["game_type"]).upper() != "REG":
            continue

        gid = str(row["game_id"]).strip()
        if not gid:
            raise ValueError("blank 2026 REG game_id")
        if gid in games:
            raise ValueError(f"duplicate game_id: {gid}")

        away = canon_team(row["away_team"])
        home = canon_team(row["home_team"])
        if away == home:
            raise ValueError(f"same-team game: {gid}")

        games[gid] = Game(
            game_id=gid,
            season=season,
            week=week,
            kickoff_utc=parse_kickoff_utc(row["gameday"], row["gametime"]),
            away_team=away,
            home_team=home,
            completed=(
                not is_blank(row["away_score"])
                and not is_blank(row["home_score"])
            ),
        )

    if len(games) < 250:
        raise ValueError(f"implausibly few 2026 REG schedule games: {len(games)}")

    return games


def source_readiness(games):
    week4 = sorted(
        [g for g in games.values() if g.week == 4],
        key=lambda g: (g.kickoff_utc, g.game_id),
    )
    week5 = sorted(
        [g for g in games.values() if g.week == 5],
        key=lambda g: (g.kickoff_utc, g.game_id),
    )
    if not week4 or not week5:
        raise ValueError("missing Week 4 or Week 5 schedule rows")

    incomplete_w4 = [g.game_id for g in week4 if not g.completed]
    if incomplete_w4:
        raise RuntimeError(
            "WEEK4_NOT_COMPLETE_DO_NOT_FREEZE: "
            + ",".join(incomplete_w4)
        )

    cutoff = week5[0].kickoff_utc
    if cutoff != EXPECTED_CUTOFF_UTC:
        raise RuntimeError(
            f"WEEK5_CUTOFF_CHANGED: current={cutoff.isoformat()} "
            f"frozen={EXPECTED_CUTOFF_UTC.isoformat()}"
        )

    completed_w5 = [g.game_id for g in week5 if g.completed]
    if completed_w5:
        raise RuntimeError(
            "WEEK5_OUTCOME_ALREADY_PRESENT_NO_BACKFILL: "
            + ",".join(completed_w5)
        )

    now = datetime.now(timezone.utc)
    if not now < cutoff:
        raise RuntimeError(
            f"WEEK5_FREEZE_DEADLINE_MISSED: now={now.isoformat()} "
            f"cutoff={cutoff.isoformat()}"
        )

    return {
        "week4_scheduled_games": len(week4),
        "week4_completed_games": len(week4),
        "week5_scheduled_games": len(week5),
        "week5_completed_games_at_freeze": 0,
        "week5_cutoff_utc": cutoff.isoformat(),
        "freeze_runtime_utc": now.isoformat(),
    }


def parse_numeric_fields(row, fields):
    for field in fields:
        value = row.get(field)
        if is_blank(value):
            continue
        try:
            x = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"non-numeric frozen scoring field {field}={value!r}"
            ) from exc
        if not math.isfinite(x):
            raise ValueError(f"non-finite frozen scoring field {field}")


def adapt_stats(path: Path, games, frozen):
    rows = read_csv(path)
    if not rows:
        raise ValueError("empty 2026 weekly stats source")

    fields = set(rows[0])
    required = {
        "player_id", "game_id", "season", "week", "season_type", "position",
    }
    missing = required - fields
    if missing:
        raise KeyError(f"2026 stats missing context fields: {sorted(missing)}")
    if "team" not in fields and "recent_team" not in fields:
        raise KeyError("2026 stats missing team/recent_team")
    missing_scoring = set(frozen.STAT_FIELDS) - fields
    if missing_scoring:
        raise KeyError(
            f"2026 stats missing frozen scoring fields: {sorted(missing_scoring)}"
        )

    adapted = []
    duplicate_guard = set()
    audit = defaultdict(int)

    for row in rows:
        try:
            season = int(row["season"])
            week = int(row["week"])
        except (TypeError, ValueError):
            continue
        if season != SEASON:
            continue
        audit["source_rows_seen_2026"] += 1

        if str(row["season_type"]).upper() not in {"REG", "REGULAR"}:
            audit["nonregular_rows_skipped"] += 1
            continue

        # Origin Week 5 can use only Weeks 1-4 and only games before cutoff.
        if week >= ORIGIN_WEEK:
            audit["week5_plus_rows_physically_excluded"] += 1
            continue

        gid = str(row["game_id"]).strip()
        game = games.get(gid)
        if game is None:
            raise KeyError(f"stats game_id absent from schedule: {gid}")
        if game.week != week or game.season != SEASON:
            raise ValueError(f"stats/schedule season-week mismatch: {gid}")
        if not game.completed:
            raise ValueError(
                f"stats row exists for schedule-uncompleted game: {gid}"
            )
        if game.kickoff_utc >= EXPECTED_CUTOFF_UTC:
            raise ValueError(f"post-cutoff game entered origin history: {gid}")

        recent = row.get("recent_team")
        team_raw = row.get("team")
        if not is_blank(recent) and not is_blank(team_raw):
            a = canon_team(recent)
            b = canon_team(team_raw)
            if a != b:
                raise ValueError(
                    f"conflicting recent_team/team in {gid}: {a} vs {b}"
                )
            team = a
        elif not is_blank(recent):
            team = canon_team(recent)
        elif not is_blank(team_raw):
            team = canon_team(team_raw)
        else:
            raise ValueError(f"blank team identity: {gid}")

        if team not in {game.away_team, game.home_team}:
            raise ValueError(
                f"player team {team} not in scheduled game {gid}"
            )

        if "opponent_team" in fields and not is_blank(row.get("opponent_team")):
            opp = canon_team(row["opponent_team"])
            if opp != game.opponent(team):
                raise ValueError(
                    f"opponent mismatch {gid}: row={opp} "
                    f"schedule={game.opponent(team)}"
                )
            audit["opponent_schedule_checks"] += 1

        pg = canon_position(row.get("position_group"))
        p = canon_position(row.get("position"))
        if pg is not None and p is not None and pg != p:
            raise ValueError(
                f"canonical position conflict {gid}: {pg} vs {p}"
            )
        pos = pg or p

        parse_numeric_fields(row, frozen.STAT_FIELDS)

        player_id = str(row.get("player_id") or "").strip()
        if not player_id:
            audit["blank_player_id_rows_seen"] += 1
            if pos in POSITIONS:
                raise ValueError(
                    f"blank player_id on canonical {pos} row in {gid}"
                )
            audit["blank_player_id_noncanonical_excluded"] += 1
            continue

        dup = (gid, team, player_id)
        if dup in duplicate_guard:
            raise ValueError(f"duplicate player-game-team row: {dup}")
        duplicate_guard.add(dup)

        out = dict(row)
        out["season"] = SEASON
        out["week"] = week
        out["season_type"] = "REG"
        out["recent_team"] = team
        out["_canonical_position"] = pos
        adapted.append(out)
        audit["rows_admitted_weeks_1_4"] += 1

    if not adapted:
        raise ValueError("no admitted Weeks 1-4 predictor rows")

    return adapted, dict(audit)


def aggregate_history(player_rows, games, frozen):
    by_team_game = defaultdict(list)
    totals = defaultdict(float)
    counts = defaultdict(int)

    for row in player_rows:
        gid = str(row["game_id"])
        team = str(row["recent_team"])
        by_team_game[(gid, team)].append(row)
        pos = row["_canonical_position"]
        if pos in POSITIONS:
            key = (gid, team, pos)
            totals[key] += frozen.score_player_row(row, SCORING_MODE)
            counts[key] += 1

    history_games = sorted(
        [
            g for g in games.values()
            if g.completed
            and g.week in HISTORY_WEEKS
            and g.kickoff_utc < EXPECTED_CUTOFF_UTC
        ],
        key=lambda g: (g.week, g.kickoff_utc, g.game_id),
    )

    source_failures = []
    zero_fills = defaultdict(int)
    out = []

    for game in history_games:
        for offense, defense in (
            (game.away_team, game.home_team),
            (game.home_team, game.away_team),
        ):
            team_rows = by_team_game.get((game.game_id, offense), [])
            if not team_rows:
                source_failures.append({
                    "game_id": game.game_id,
                    "team": offense,
                    "reason": "NO_WEEKLY_PLAYER_STAT_ROWS",
                })
                continue

            for pos in POSITIONS:
                key = (game.game_id, offense, pos)
                if counts.get(key, 0) == 0:
                    points = 0.0
                    zero_fills[pos] += 1
                else:
                    points = totals[key]

                out.append(
                    frozen.GamePositionPoints(
                        season=SEASON,
                        week=game.week,
                        offense_team=offense,
                        defense_team=defense,
                        position=pos,
                        scoring_mode=SCORING_MODE,
                        points=points,
                    )
                )

    if source_failures:
        raise RuntimeError(
            "WEEKLY_STATS_NOT_READY_FOR_ALL_COMPLETED_HISTORY_GAMES: "
            + json.dumps(source_failures[:20], sort_keys=True)
        )

    expected = len(history_games) * 2 * len(POSITIONS)
    if len(out) != expected:
        raise RuntimeError(
            f"history aggregate mismatch: {len(out)} != {expected}"
        )

    return out, {
        "history_games_weeks_1_4": len(history_games),
        "team_position_history_rows": len(out),
        "zero_fills": dict(sorted(zero_fills.items())),
        "source_completeness_failures": 0,
    }


def offense_baselines(game_rows, position):
    by_offense = defaultdict(list)
    for r in game_rows:
        if r.position == position and r.scoring_mode == SCORING_MODE:
            by_offense[r.offense_team].append(float(r.points))

    out = {}
    for team, values in sorted(by_offense.items()):
        out[team] = {
            "status": (
                "AVAILABLE" if len(values) >= 2
                else "UNAVAILABLE_LT2_GAMES"
            ),
            "eligible_games": len(values),
            "baseline_points": (
                statistics.fmean(values) if len(values) >= 2 else None
            ),
        }
    return out


def future_schedule_at_origin(games):
    future = sorted(
        [
            g for g in games.values()
            if ORIGIN_WEEK <= g.week <= 17
            and g.kickoff_utc >= EXPECTED_CUTOFF_UTC
        ],
        key=lambda g: (g.kickoff_utc, g.game_id),
    )

    per_team = defaultdict(list)
    for game in future:
        per_team[game.away_team].append(
            (game, game.home_team)
        )
        per_team[game.home_team].append(
            (game, game.away_team)
        )

    team_h = {}
    for team, entries in per_team.items():
        entries = sorted(entries, key=lambda x: (x[0].kickoff_utc, x[0].game_id))
        for i, (game, opponent) in enumerate(entries, start=1):
            team_h[(game.game_id, team)] = i

    rows = []
    for game in future:
        for offense, defense in (
            (game.away_team, game.home_team),
            (game.home_team, game.away_team),
        ):
            rows.append({
                "game_id": game.game_id,
                "scheduled_week_at_origin": game.week,
                "scheduled_kickoff_utc_at_origin": game.kickoff_utc.isoformat(),
                "offense_team": offense,
                "defense_team": defense,
                "planned_h_at_origin": team_h[(game.game_id, offense)],
            })

    return rows


def build_snapshot(schedule_path, stats_path, frozen_path, b33_path):
    b33 = json.loads(Path(b33_path).read_text(encoding="utf-8"))
    if b33["status"] != "PREREGISTERED_ORDINAL_PROSPECTIVE_SHADOW":
        raise RuntimeError("B33 is not frozen preregistered")
    if b33["prospective_origin_contract"]["first_candidate_origin_week"] != 5:
        raise RuntimeError("B33 first origin is not Week 5")
    if b33["prospective_origin_contract"][
        "2026_week_5_first_kickoff_utc"
    ] != "2026-10-09T00:15:00Z":
        raise RuntimeError("B33 Week 5 cutoff mismatch")

    frozen = load_frozen(Path(frozen_path))
    if frozen.METRIC_ID != "LOG-SAPA-V1":
        raise RuntimeError("wrong frozen metric")
    if frozen.LOOKBACK_WEEKS != 10:
        raise RuntimeError("frozen lookback changed")
    if frozen.MIN_OPPONENT_COMPARISON_GAMES != 2:
        raise RuntimeError("frozen opponent minimum changed")
    if frozen.MIN_DEFENSE_ADJUSTED_GAMES != 3:
        raise RuntimeError("frozen defense minimum changed")

    games = load_2026_schedule(Path(schedule_path))
    readiness = source_readiness(games)
    player_rows, stats_audit = adapt_stats(
        Path(stats_path), games, frozen
    )
    game_rows, aggregate_audit = aggregate_history(
        player_rows, games, frozen
    )

    position_payload = {}
    for pos in POSITIONS:
        baselines = offense_baselines(game_rows, pos)
        defense_snapshot = frozen.compute_log_sapa(
            game_rows,
            season=SEASON,
            target_week=ORIGIN_WEEK,
            position=pos,
            scoring_mode=SCORING_MODE,
        )

        position_payload[pos] = {
            "offense_baselines": baselines,
            "defense_snapshot": defense_snapshot,
            "available_offense_baselines": sum(
                x["status"] == "AVAILABLE" for x in baselines.values()
            ),
            "available_defense_effects": sum(
                x.get("status") == "AVAILABLE"
                for x in defense_snapshot.values()
            ),
        }

    future_rows = future_schedule_at_origin(games)

    # Audit planned h=1 predictor availability at freeze. This is descriptive;
    # the preregistered gate is evaluated only after 10 eligible origin weeks.
    h1 = [r for r in future_rows if r["planned_h_at_origin"] == 1]
    h1_availability = {}
    for pos in POSITIONS:
        available = 0
        missing = []
        payload = position_payload[pos]
        for r in h1:
            base = payload["offense_baselines"].get(r["offense_team"], {})
            deff = payload["defense_snapshot"].get(r["defense_team"], {})
            ok = (
                base.get("status") == "AVAILABLE"
                and deff.get("status") == "AVAILABLE"
                and deff.get("defense_effect") is not None
            )
            if ok:
                available += 1
            else:
                missing.append({
                    "game_id": r["game_id"],
                    "offense_team": r["offense_team"],
                    "defense_team": r["defense_team"],
                    "baseline_status": base.get("status", "MISSING"),
                    "defense_status": deff.get("status", "MISSING"),
                })
        h1_availability[pos] = {
            "expected_directional_rows": len(h1),
            "predictor_available_rows": available,
            "availability_fraction": (
                available / len(h1) if h1 else None
            ),
            "missing": missing,
        }

    return {
        "schema_version": 1,
        "study_id": "schedule-utility-v1",
        "phase": "B34-weekly-prospective-origin-snapshot",
        "status": "FROZEN_PROSPECTIVE_ORIGIN_SNAPSHOT",
        "season": SEASON,
        "origin_week": ORIGIN_WEEK,
        "origin_cutoff_utc": EXPECTED_CUTOFF_UTC.isoformat(),
        "scoring_mode": SCORING_MODE,
        "visibility": "NON_USER_VISIBLE",
        "outcome_evaluation_performed": False,
        "production_authorized": False,
        "quantitative_v1_stop_remains_binding": True,
        "source_snapshot": {
            "schedule_sha256": sha256(Path(schedule_path)),
            "stats_player_week_2026_sha256": sha256(Path(stats_path)),
            "log_sapa_sha256": sha256(Path(frozen_path)),
            "b33_prereg_sha256": sha256(Path(b33_path)),
        },
        "readiness": readiness,
        "stats_ingestion_audit": stats_audit,
        "history_aggregation_audit": aggregate_audit,
        "position_snapshots": position_payload,
        "future_schedule_at_origin": future_rows,
        "planned_h1_predictor_availability": h1_availability,
        "governance": {
            "snapshot_created_before_origin_cutoff": True,
            "week4_complete_before_snapshot": True,
            "week5_outcomes_present_at_snapshot": False,
            "no_backfill": True,
            "baseline_and_defense_effect_frozen_for_future_targets": True,
            "may_recompute_predictor_after_outcomes": False,
            "may_change_tiers_or_thresholds": False,
            "user_facing_display_authorized": False,
            "fv_or_trade_integration_authorized": False,
        },
    }


def selftest():
    assert canon_team("JAC") == "JAX"
    assert canon_team("WSH") == "WAS"
    assert canon_position("FB") == "RB"
    assert canon_position("K") is None

    dt = parse_kickoff_utc("2026-10-08", "20:15")
    assert dt == EXPECTED_CUTOFF_UTC

    print("PASS: B34 snapshot builder synthetic selftest")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--schedule")
    ap.add_argument("--stats")
    ap.add_argument("--frozen")
    ap.add_argument("--b33")
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    for name in ("schedule", "stats", "frozen", "b33", "out"):
        if getattr(args, name) is None:
            ap.error(f"--{name} is required")

    result = build_snapshot(
        args.schedule, args.stats, args.frozen, args.b33
    )
    out = Path(args.out)
    out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": result["status"],
        "origin_week": result["origin_week"],
        "freeze_runtime_utc": result["readiness"]["freeze_runtime_utc"],
        "week4_completed_games":
            result["readiness"]["week4_completed_games"],
        "week5_completed_games_at_freeze":
            result["readiness"]["week5_completed_games_at_freeze"],
        "history_games":
            result["history_aggregation_audit"]["history_games_weeks_1_4"],
        "h1_availability": {
            p: result["planned_h1_predictor_availability"][p][
                "availability_fraction"
            ]
            for p in POSITIONS
        },
        "production_authorized": False,
        "outcome_evaluation_performed": False,
    }, indent=2))


if __name__ == "__main__":
    main()

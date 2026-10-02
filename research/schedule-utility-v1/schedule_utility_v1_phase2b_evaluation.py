#!/usr/bin/env python3
"""
Schedule Utility V1 — Phase 2B frozen retrospective predictive evaluation.

This is the first workflow authorized to evaluate the 2015-2025 target outcomes.
It MUST NOT change the frozen LOG-SAPA predictor, primary estimand, weights,
coverage rule, inference, or decision thresholds.

Primary analysis is delegated to the exact B29-frozen
schedule_utility_v1_phase2a_analysis_v2.py module.

Only aggregate results are emitted. Raw historical player rows and row-level
evaluation records are never persisted to the repository.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import statistics
import sys
from typing import Mapping

SEASONS = tuple(range(2015, 2026))
TARGET_WEEKS = tuple(range(4, 18))
POSITIONS = ("QB", "RB", "WR", "TE")
CELL_DEFS = (
    ("QB_HALF", "QB", "HALF_PPR"),
    ("RB_HALF", "RB", "HALF_PPR"),
    ("WR_HALF", "WR", "HALF_PPR"),
    ("TE_HALF", "TE", "HALF_PPR"),
    ("RB_PPR", "RB", "PPR"),
    ("WR_PPR", "WR", "PPR"),
    ("TE_PPR", "TE", "PPR"),
)
WEEK_BUCKETS = (
    ("W4_7", 4, 7),
    ("W8_11", 8, 11),
    ("W12_17", 12, 17),
)
PLACEBO_REPS = 256
PLACEBO_SEED = 20261002

EXPECTED_LOG_SAPA_SHA256 = (
    "9ab4ec5b21ef9ef57e476e861a7293dbc886b9bc9d7cc5f0bd5cc982cc729ee6"
)
EXPECTED_ANALYSIS_SHA256 = (
    "2b35cd60082385add312b24c676b72e2b89c4e636e1fa94010fcffb0c675b9c5"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {name}: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


def verify_frozen_sources(
    *,
    preflight_json: Path,
    drift_audit_json: Path,
    schedule_path: Path,
    stats_dir: Path,
) -> tuple[dict, dict]:
    pre = json.loads(preflight_json.read_text(encoding="utf-8"))
    drift = json.loads(drift_audit_json.read_text(encoding="utf-8"))
    if pre["status"] != "PASS_PREDICTOR_ONLY_PREFLIGHT_READY_TO_UNSEAL_PHASE2_TARGETS":
        raise RuntimeError("B30 preflight is not PASS")
    if pre["target_outcome_evaluation_performed"] is not False:
        raise RuntimeError("B30 outcome firewall violated")
    if pre["phase2_primary_pass_stop_computed"] is not False:
        raise RuntimeError("B30 unexpectedly computed primary verdict")
    if pre["next_phase"]["may_open_target_outcomes_for_frozen_evaluation"] is not True:
        raise RuntimeError("B30 does not authorize target opening")
    if pre["next_phase"]["may_change_predictor_or_primary_gate"] is not False:
        raise RuntimeError("B30 governance mismatch")
    if pre["predictor_availability_failures"]:
        raise RuntimeError("B30 predictor availability failures are non-empty")

    if drift["status"] != (
        "PASS_SCHEDULE_CONTAINER_DRIFT_SEMANTICALLY_EQUIVALENT"
    ):
        raise RuntimeError("B31A source drift audit is not PASS")
    if drift["historical_target_outcomes_opened"] is not False:
        raise RuntimeError("B31A outcome firewall violated")
    if drift["target_outcome_evaluation_performed"] is not False:
        raise RuntimeError("B31A unexpectedly evaluated outcomes")
    if drift["predictor_or_primary_gate_changed"] is not False:
        raise RuntimeError("B31A governance mismatch")
    if drift["all_11_player_stat_files_byte_identical"] is not True:
        raise RuntimeError("B31A player-stat source identity gate failed")
    if drift["semantic_mismatches"]:
        raise RuntimeError("B31A semantic mismatch list is non-empty")
    if drift["next_phase"]["authorized"] is not True:
        raise RuntimeError("B31A does not authorize B31 V2")
    if drift["next_phase"]["may_change_predictor_or_primary_gate"] is not False:
        raise RuntimeError("B31A next-phase governance mismatch")

    frozen = pre["source_snapshot_sha256"]
    observed = {
        "games_csv": sha256(schedule_path),
        "stats_player_week": {},
    }

    authorized_games_sha = drift["next_phase"]["required_games_sha256"]
    if observed["games_csv"] != authorized_games_sha:
        raise RuntimeError(
            f"schedule source hash drift after B31A authorization: "
            f"{observed['games_csv']} != {authorized_games_sha}"
        )

    # Player-stat bytes remain pinned to the ORIGINAL B30 snapshot.
    authorized_stats = drift["next_phase"]["required_player_stat_sha256"]
    if authorized_stats != frozen["stats_player_week"]:
        raise RuntimeError("B31A authorized player-stat map differs from B30")

    for season in SEASONS:
        path = stats_dir / f"stats_player_week_{season}.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        got = sha256(path)
        expected = frozen["stats_player_week"][str(season)]
        observed["stats_player_week"][str(season)] = got
        if got != expected:
            raise RuntimeError(
                f"{season} stats source hash drift: {got} != {expected}"
            )

    return pre, observed


def adapt_full_eval_stats(
    path: Path,
    *,
    season: int,
    games: Mapping[str, object],
    frozen,
    b30,
) -> tuple[list[dict], dict]:
    """
    Same source/identity/scoring contract as B30, but Week 17 is retained
    because B31 is now authorized to evaluate target outcomes through Week 17.
    Weeks >17 are physically excluded.
    """
    rows = b30.read_csv(path)
    if not rows:
        raise ValueError(f"empty player stats file for {season}")

    fields = set(rows[0])
    required_context = {
        "player_id", "game_id", "season", "week", "season_type", "position",
    }
    missing = required_context - fields
    if missing:
        raise KeyError(
            f"{season} player stats missing context fields: {sorted(missing)}"
        )
    if "team" not in fields and "recent_team" not in fields:
        raise KeyError(f"{season} player stats missing team/recent_team")

    missing_stats = set(frozen.STAT_FIELDS) - fields
    if missing_stats:
        raise KeyError(
            f"{season} player stats missing frozen scoring fields: "
            f"{sorted(missing_stats)}"
        )

    adapted = []
    duplicate_guard = set()
    audit = defaultdict(int)

    for row in rows:
        try:
            row_season = int(row["season"])
            week = int(row["week"])
        except (TypeError, ValueError):
            continue
        if row_season != season:
            continue

        audit["source_rows_seen"] += 1

        if str(row["season_type"]).upper() not in {"REG", "REGULAR"}:
            audit["nonregular_rows_skipped"] += 1
            continue

        if week > 17:
            audit["week18_plus_rows_physically_skipped"] += 1
            continue

        game_id = str(row["game_id"]).strip()
        game = games.get(game_id)
        if game is None:
            raise KeyError(
                f"{season}: player row game_id absent from schedule: {game_id}"
            )
        if game.season != season or game.week != week:
            raise ValueError(
                f"{season}: player/schedule season-week mismatch for {game_id}"
            )
        if not game.completed:
            continue

        recent_raw = row.get("recent_team")
        team_raw = row.get("team")
        if not b30.is_blank(recent_raw) and not b30.is_blank(team_raw):
            a = b30.canon_team(recent_raw)
            b = b30.canon_team(team_raw)
            if a != b:
                raise ValueError(
                    f"{season}: conflicting recent_team/team in {game_id}: {a} vs {b}"
                )
            team = a
        elif not b30.is_blank(recent_raw):
            team = b30.canon_team(recent_raw)
        elif not b30.is_blank(team_raw):
            team = b30.canon_team(team_raw)
        else:
            raise ValueError(f"{season}: blank team identity in {game_id}")

        if team not in {game.away_team, game.home_team}:
            raise ValueError(
                f"{season}: player team {team} not in scheduled game {game_id}"
            )

        if "opponent_team" in fields and not b30.is_blank(row.get("opponent_team")):
            audit["opponent_schedule_checks"] += 1
            opp = b30.canon_team(row["opponent_team"])
            if opp != game.opponent(team):
                raise ValueError(
                    f"{season}: opponent mismatch {game_id}: "
                    f"row={opp}, schedule={game.opponent(team)}"
                )

        pg = b30.canon_position(row.get("position_group"))
        p = b30.canon_position(row.get("position"))
        if pg is not None and p is not None and pg != p:
            raise ValueError(
                f"{season}: canonical position conflict in {game_id}: "
                f"position_group={pg}, position={p}"
            )
        pos = pg or p

        b30._parse_numeric_columns(row, frozen.STAT_FIELDS)

        player_id = str(row["player_id"] or "").strip()
        if not player_id:
            audit["blank_player_id_rows_seen"] += 1
            if pos in POSITIONS:
                raise ValueError(
                    f"{season}: blank player_id on canonical position row "
                    f"in {game_id}: team={team}, position={pos}"
                )
            audit["blank_player_id_noncanonical_rows_excluded"] += 1
            continue

        dup_key = (game_id, team, player_id)
        if dup_key in duplicate_guard:
            raise ValueError(
                f"{season}: duplicate player-game-team row: {dup_key}"
            )
        duplicate_guard.add(dup_key)

        if pos is None:
            audit["noncanonical_position_rows"] += 1

        out = dict(row)
        out["season"] = season
        out["week"] = week
        out["season_type"] = "REG"
        out["recent_team"] = team
        out["position"] = pos or str(row.get("position") or "")
        out["position_group"] = pos or ""
        out["_canonical_position"] = pos
        adapted.append(out)
        audit["rows_admitted_weeks_1_17"] += 1

    if not adapted:
        raise ValueError(f"{season}: no admitted evaluation-source rows")

    return adapted, dict(audit)


def build_actual_map(
    *,
    season: int,
    player_rows: list[dict],
    games: Mapping[str, object],
    frozen,
    scoring_mode: str,
) -> tuple[dict[tuple[str, str, str], float], dict]:
    by_team_game: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in player_rows:
        by_team_game[(str(row["game_id"]), str(row["recent_team"]))].append(row)

    totals: dict[tuple[str, str, str], float] = defaultdict(float)
    counts: dict[tuple[str, str, str], int] = defaultdict(int)

    for (game_id, team), rows in by_team_game.items():
        for row in rows:
            pos = row["_canonical_position"]
            if pos not in POSITIONS:
                continue
            totals[(game_id, team, pos)] += frozen.score_player_row(
                row, scoring_mode
            )
            counts[(game_id, team, pos)] += 1

    out: dict[tuple[str, str, str], float] = {}
    zero_fills = defaultdict(int)
    source_failures = []

    target_games = [
        g for g in games.values()
        if g.season == season and g.completed and 4 <= g.week <= 17
    ]

    for game in sorted(target_games, key=lambda g: (g.week, g.kickoff, g.game_id)):
        for offense in (game.away_team, game.home_team):
            team_game_rows = by_team_game.get((game.game_id, offense), [])
            if not team_game_rows:
                source_failures.append({
                    "game_id": game.game_id,
                    "team": offense,
                    "reason": "NO_WEEKLY_PLAYER_STAT_ROWS_FOR_COMPLETED_TARGET_TEAM_GAME",
                })
                continue

            for pos in POSITIONS:
                key = (game.game_id, offense, pos)
                if counts.get(key, 0) == 0:
                    out[key] = 0.0
                    zero_fills[pos] += 1
                else:
                    out[key] = totals[key]

    if source_failures:
        raise ValueError(
            f"{season}: target team-game source completeness failures: "
            f"{source_failures[:20]} total={len(source_failures)}"
        )

    expected = len(target_games) * 2 * len(POSITIONS)
    if len(out) != expected:
        raise ValueError(
            f"{season} {scoring_mode}: target aggregate row mismatch "
            f"{len(out)} != {expected}"
        )

    return out, {
        "completed_target_games_weeks_4_17": len(target_games),
        "team_position_target_rows": len(out),
        "zero_fills": dict(sorted(zero_fills.items())),
        "source_completeness_failures": 0,
    }


def rel_mae(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "relative_mae_improvement": None}
    base = statistics.fmean(
        abs(float(r["baseline_forecast"]) - float(r["actual"]))
        for r in rows
    )
    adj = statistics.fmean(
        abs(float(r["adjusted_forecast"]) - float(r["actual"]))
        for r in rows
    )
    return {
        "n": len(rows),
        "baseline_mae": base,
        "adjusted_mae": adj,
        "relative_mae_improvement": (
            (base - adj) / base if base > 0 else None
        ),
    }


def week_bucket(week: int) -> str:
    for name, lo, hi in WEEK_BUCKETS:
        if lo <= week <= hi:
            return name
    raise ValueError(week)


def run_placebo(rows: list[dict]) -> dict:
    """
    Non-gating deterministic diagnostic.

    Defense effects are permuted across directional target rows within the
    same season-week-cell. Baseline forecasts and actual outcomes remain fixed.
    """
    groups = defaultdict(list)
    for r in rows:
        groups[(r["season"], r["week"], r["cell"])].append(r)

    observed = rel_mae(rows)["relative_mae_improvement"]
    rng = random.Random(PLACEBO_SEED)
    permuted = []

    for _ in range(PLACEBO_REPS):
        base_abs = []
        adj_abs = []
        for key in sorted(groups):
            g = groups[key]
            effects = [float(r["defense_effect"]) for r in g]
            shuffled = list(effects)
            rng.shuffle(shuffled)
            for r, eff in zip(g, shuffled):
                actual = float(r["actual"])
                base = float(r["baseline_forecast"])
                base_abs.append(abs(base - actual))
                adj_abs.append(abs((base + eff) - actual))
        base_mae = statistics.fmean(base_abs)
        adj_mae = statistics.fmean(adj_abs)
        permuted.append((base_mae - adj_mae) / base_mae)

    count_ge = sum(x >= observed - 1e-15 for x in permuted)
    return {
        "non_gating": True,
        "repetitions": PLACEBO_REPS,
        "seed": PLACEBO_SEED,
        "permutation_unit": "defense_effect across directional rows within season-week-cell",
        "observed_row_pooled_relative_mae_improvement": observed,
        "permutation_mean_relative_mae_improvement": statistics.fmean(permuted),
        "permutation_p_ge_observed_plus1": (count_ge + 1) / (PLACEBO_REPS + 1),
    }


def run(
    *,
    schedule_path: Path,
    stats_dir: Path,
    log_sapa_path: Path,
    b30_module_path: Path,
    analysis_path: Path,
    preflight_json: Path,
    drift_audit_json: Path,
) -> dict:
    if sha256(log_sapa_path) != EXPECTED_LOG_SAPA_SHA256:
        raise RuntimeError("frozen LOG-SAPA SHA mismatch")
    if sha256(analysis_path) != EXPECTED_ANALYSIS_SHA256:
        raise RuntimeError("frozen Phase 2A analysis SHA mismatch")

    b30 = load_module("b30_frozen_preflight", b30_module_path)
    frozen = load_module("log_sapa_frozen_b31", log_sapa_path)
    analysis = load_module("phase2a_analysis_frozen_b31", analysis_path)

    preflight, observed_hashes = verify_frozen_sources(
        preflight_json=preflight_json,
        drift_audit_json=drift_audit_json,
        schedule_path=schedule_path,
        stats_dir=stats_dir,
    )

    # Sanity-check the exact B29 primary rules before target construction.
    assert analysis.PRIMARY_MIN_MEAN_RELATIVE_MAE_IMPROVEMENT == 0.01
    assert analysis.PRIMARY_MAX_ONE_SIDED_SIGNFLIP_P == 0.05
    assert analysis.PRIMARY_MIN_POSITIVE_CELLS == 5
    assert analysis.PRIMARY_MIN_WORST_CELL_RELATIVE_MAE_IMPROVEMENT == -0.02
    assert analysis.MIN_COVERAGE_FRACTION_PER_SEASON_CELL == 0.95

    games, schedule_audit = b30.load_schedule(schedule_path)
    week_cutoffs = schedule_audit.pop("week_cutoffs")
    expected_by_season = (
        schedule_audit["schedule_derived_expected_directional_rows_weeks_4_17"]
    )

    eval_rows: list[dict] = []
    itt_rows: list[dict] = []
    missingness = defaultdict(int)
    source_audit = {}
    actual_audit = {}
    predictor_consistency = {}

    for season in SEASONS:
        stats_path = stats_dir / f"stats_player_week_{season}.csv"

        # Predictor rows use the exact B30 adapter/aggregator, including its
        # physical Week-17+ exclusion.
        predictor_source_rows, pre_audit = b30.adapt_historical_stats(
            stats_path,
            season=season,
            games=games,
            frozen=frozen,
        )
        source_audit[f"{season}_predictor"] = pre_audit

        # Target source retains Week 17 because B31 is now outcome-authorized.
        full_rows, full_audit = adapt_full_eval_stats(
            stats_path,
            season=season,
            games=games,
            frozen=frozen,
            b30=b30,
        )
        source_audit[f"{season}_evaluation"] = full_audit

        for mode in ("HALF_PPR", "PPR"):
            predictor_rows, pred_audit = b30.build_team_game_position_rows(
                season=season,
                player_rows=predictor_source_rows,
                games=games,
                frozen=frozen,
                scoring_mode=mode,
            )
            predictor_consistency[f"{season}_{mode}"] = pred_audit

            actual_map, act_audit = build_actual_map(
                season=season,
                player_rows=full_rows,
                games=games,
                frozen=frozen,
                scoring_mode=mode,
            )
            actual_audit[f"{season}_{mode}"] = act_audit

            for cell, position, cell_mode in CELL_DEFS:
                if cell_mode != mode:
                    continue

                all_game_rows = [
                    r for r in predictor_rows
                    if r.position == position
                ]

                identity_to_game_id = {}
                for g in games.values():
                    if g.season != season:
                        continue
                    identity_to_game_id[
                        (g.season, g.week, g.away_team, g.home_team)
                    ] = g.game_id
                    identity_to_game_id[
                        (g.season, g.week, g.home_team, g.away_team)
                    ] = g.game_id

                for week in TARGET_WEEKS:
                    cutoff = week_cutoffs[(season, week)]
                    candidate_ids, _excluded = b30.candidate_game_ids(
                        games,
                        season=season,
                        target_week=week,
                        week_cutoff=cutoff,
                    )

                    hist = []
                    for r in all_game_rows:
                        gid = identity_to_game_id.get(
                            (r.season, r.week, r.offense_team, r.defense_team)
                        )
                        if gid is None:
                            raise ValueError(
                                f"cannot recover predictor game identity "
                                f"{r.season} W{r.week} "
                                f"{r.offense_team}-{r.defense_team}"
                            )
                        if gid in candidate_ids:
                            hist.append(r)

                    try:
                        defense_snapshot = frozen.compute_log_sapa(
                            hist,
                            season=season,
                            target_week=week,
                            position=position,
                            scoring_mode=mode,
                        )
                    except ValueError as exc:
                        if "no eligible historical game rows" in str(exc):
                            defense_snapshot = {}
                        else:
                            raise

                    offense_points = defaultdict(list)
                    for r in hist:
                        offense_points[r.offense_team].append(float(r.points))

                    targets = b30.target_directional_matchups(
                        games, season=season, week=week
                    )

                    for game_id, offense, defense in targets:
                        actual_key = (game_id, offense, position)
                        actual_exists = actual_key in actual_map
                        baseline_values = offense_points.get(offense, [])
                        baseline_ok = len(baseline_values) >= 2
                        defense_payload = defense_snapshot.get(defense, {})
                        defense_ok = (
                            defense_payload.get("status") == "AVAILABLE"
                            and defense_payload.get("defense_effect") is not None
                        )

                        reasons = []
                        if not actual_exists:
                            reasons.append("TARGET_ACTUAL_UNAVAILABLE")
                        if not baseline_ok:
                            reasons.append("BASELINE_UNAVAILABLE_LT2_GAMES")
                        if not defense_ok:
                            reasons.append("DEFENSE_EFFECT_UNAVAILABLE")

                        if reasons:
                            for reason in reasons:
                                missingness[
                                    (season, cell, week_bucket(week), reason)
                                ] += 1

                        if actual_exists and baseline_ok:
                            actual = float(actual_map[actual_key])
                            baseline = statistics.fmean(baseline_values)
                            if defense_ok:
                                defense_effect = float(
                                    defense_payload["defense_effect"]
                                )
                                adjusted = baseline + defense_effect
                            else:
                                defense_effect = 0.0
                                adjusted = baseline
                            itt_rows.append({
                                "season": season,
                                "week": week,
                                "game_id": game_id,
                                "offense_team": offense,
                                "defense_team": defense,
                                "cell": cell,
                                "actual": actual,
                                "baseline_forecast": baseline,
                                "defense_effect": defense_effect,
                                "adjusted_forecast": adjusted,
                                "defense_effect_available": defense_ok,
                            })

                        if not (actual_exists and baseline_ok and defense_ok):
                            continue

                        actual = float(actual_map[actual_key])
                        baseline = statistics.fmean(baseline_values)
                        defense_effect = float(defense_payload["defense_effect"])
                        adjusted = baseline + defense_effect

                        # Rematch definition is frozen before outcome metrics:
                        # same offense/defense pair has a candidate-history game.
                        rematch = any(
                            r.offense_team == offense
                            and r.defense_team == defense
                            for r in hist
                        )

                        eval_rows.append({
                            "season": season,
                            "week": week,
                            "game_id": game_id,
                            "offense_team": offense,
                            "defense_team": defense,
                            "cell": cell,
                            "actual": actual,
                            "baseline_forecast": baseline,
                            "defense_effect": defense_effect,
                            "adjusted_forecast": adjusted,
                            "_week_bucket": week_bucket(week),
                            "_era": (
                                "2015_2020" if season <= 2020 else "2021_2025"
                            ),
                            "_rematch": rematch,
                        })

    # Strip diagnostic-only private keys before passing to frozen evaluator.
    primary_rows = [
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in eval_rows
    ]

    primary = analysis.evaluate(primary_rows, expected_by_season)

    diagnostics = {}

    diagnostics["week_buckets"] = {
        name: rel_mae([r for r in eval_rows if r["_week_bucket"] == name])
        for name, _, _ in WEEK_BUCKETS
    }
    diagnostics["era_split"] = {
        era: rel_mae([r for r in eval_rows if r["_era"] == era])
        for era in ("2015_2020", "2021_2025")
    }
    diagnostics["rematch_split"] = {
        "rematch": rel_mae([r for r in eval_rows if r["_rematch"]]),
        "non_rematch": rel_mae([r for r in eval_rows if not r["_rematch"]]),
        "definition": (
            "same offense-defense directional pair appeared in the "
            "information-eligible candidate history before target cutoff"
        ),
    }
    diagnostics["intention_to_treat_defense_unavailable_equals_baseline"] = {
        **rel_mae(itt_rows),
        "non_gating": True,
        "rows_with_defense_effect_unavailable": sum(
            not r["defense_effect_available"] for r in itt_rows
        ),
    }
    diagnostics["placebo_permutation"] = run_placebo(eval_rows)
    diagnostics["missingness"] = [
        {
            "season": season,
            "cell": cell,
            "week_bucket": bucket,
            "reason": reason,
            "count": count,
        }
        for (season, cell, bucket, reason), count in sorted(missingness.items())
    ]
    diagnostics["b30_structural_centering"] = {
        "source": "schedule_utility_v1_phase2b_preflight.json",
        "descriptive_only_not_gate": True,
        "retained_without_reinterpretation": True,
    }

    decision = primary["primary"]["decision"]
    passed = primary["primary"]["pass"]

    return {
        "schema_version": 1,
        "study_id": "schedule-utility-v1",
        "phase": "2B-evaluation",
        "status": decision,
        "target_outcomes_opened": True,
        "target_outcome_evaluation_performed": True,
        "production_change_authorized": False,
        "phase3_shadow_authorized": bool(passed),
        "retuning_after_outcomes_authorized": False,
        "frozen_inputs": {
            "log_sapa_sha256": sha256(log_sapa_path),
            "analysis_v2_sha256": sha256(analysis_path),
            "b30_player_stat_snapshot_sha256_match": True,
            "b31a_authorized_schedule_snapshot_sha256_match": True,
            "observed_source_snapshot_sha256": observed_hashes,
        },
        "primary_evaluation": primary,
        "secondary_diagnostics_non_gating": diagnostics,
        "source_ingestion_audit": source_audit,
        "target_aggregation_audit": actual_audit,
        "predictor_aggregation_consistency_audit": predictor_consistency,
        "governance": {
            "if_pass": (
                "Phase 3 prospective shadow may be preregistered; "
                "production remains unauthorized."
            ),
            "if_stop": (
                "2015-2025 are consumed for this frozen construction. "
                "Do not retune on these outcomes; any redesigned construction "
                "requires previously unopened validation data."
            ),
        },
    }


def selftest() -> None:
    assert week_bucket(4) == "W4_7"
    assert week_bucket(8) == "W8_11"
    assert week_bucket(17) == "W12_17"

    rows = [
        {
            "actual": 10.0,
            "baseline_forecast": 8.0,
            "adjusted_forecast": 9.0,
        },
        {
            "actual": 20.0,
            "baseline_forecast": 18.0,
            "adjusted_forecast": 19.0,
        },
    ]
    x = rel_mae(rows)
    assert x["n"] == 2
    assert abs(x["baseline_mae"] - 2.0) < 1e-15
    assert abs(x["adjusted_mae"] - 1.0) < 1e-15
    assert abs(x["relative_mae_improvement"] - 0.5) < 1e-15

    assert PLACEBO_REPS == 256
    assert PLACEBO_SEED == 20261002
    print("PASS: B31 frozen evaluation synthetic selftest")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--schedule")
    ap.add_argument("--stats-dir")
    ap.add_argument("--log-sapa")
    ap.add_argument("--b30-module")
    ap.add_argument("--analysis")
    ap.add_argument("--preflight-json")
    ap.add_argument("--drift-audit-json")
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    required = [
        args.schedule, args.stats_dir, args.log_sapa, args.b30_module,
        args.analysis, args.preflight_json, args.drift_audit_json, args.out,
    ]
    if any(x is None for x in required):
        ap.error("all source/module/output arguments are required")

    result = run(
        schedule_path=Path(args.schedule),
        stats_dir=Path(args.stats_dir),
        log_sapa_path=Path(args.log_sapa),
        b30_module_path=Path(args.b30_module),
        analysis_path=Path(args.analysis),
        preflight_json=Path(args.preflight_json),
        drift_audit_json=Path(args.drift_audit_json),
    )

    Path(args.out).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": result["status"],
        "primary": result["primary_evaluation"]["primary"],
        "phase3_shadow_authorized": result["phase3_shadow_authorized"],
        "production_change_authorized": False,
    }, indent=2))


if __name__ == "__main__":
    main()

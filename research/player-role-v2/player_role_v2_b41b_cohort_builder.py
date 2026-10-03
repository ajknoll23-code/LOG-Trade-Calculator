#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any

DEV_SEASONS = (2019, 2020, 2021, 2022, 2023, 2024)
HOLDOUT_SEASON = 2025
ORIGIN_WEEKS = tuple(range(4, 15))
POSITIONS = ("QB", "RB", "WR", "TE", "K", "DL", "LB", "DB")

# Historical projection features are intentionally absent.
FORBIDDEN_FEATURE_TOKENS = (
    "projection",
    "projected",
    "fantasypros",
    "sleeper_projection",
    "owner_id",
    "roster_id",
    "dynasty_team",
    "username",
)

POSITION_MAP = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "WR": "WR",
    "TE": "TE",
    "K": "K",
    "PK": "K",
    "DE": "DL",
    "DT": "DL",
    "NT": "DL",
    "DL": "DL",
    "EDGE": "DL",
    "LB": "LB",
    "ILB": "LB",
    "MLB": "LB",
    "OLB": "LB",
    "CB": "DB",
    "S": "DB",
    "SS": "DB",
    "FS": "DB",
    "DB": "DB",
}

# These are raw observed fields only. No fantasy scoring formula is
# applied in B41B. B41C must freeze the scorer before model fitting.
SCORING_COMPONENTS = (
    "attempts",
    "passing_yards",
    "passing_tds",
    "passing_interceptions",
    "passing_2pt_conversions",
    "carries",
    "rushing_yards",
    "rushing_tds",
    "rushing_2pt_conversions",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "receiving_2pt_conversions",
    "fumbles_lost_total",
    "fumble_recovery_tds",
    "special_teams_tds",
    "def_tackles_solo",
    "def_tackle_assists",
    "def_tackles_for_loss",
    "def_sacks",
    "def_qb_hits",
    "def_interceptions",
    "def_pass_defended",
    "def_fumbles_forced",
    "fumble_recovery_opp",
    "def_safeties",
    "def_punt_blocks",
    "def_pat_blocks",
    "def_fg_blocks",
    "def_tds",
    "fg_att",
    "fg_made",
    "pat_att",
    "pat_made",
)

OPPORTUNITY_BY_POSITION = {
    "QB": ("attempts", "carries"),
    "RB": ("carries", "targets", "target_share"),
    "WR": ("targets", "target_share", "air_yards_share", "receiving_air_yards"),
    "TE": ("targets", "target_share", "air_yards_share", "receiving_air_yards"),
    "K": ("fg_att", "pat_att"),
    "DL": (
        "def_tackles_solo",
        "def_tackle_assists",
        "def_tackles_for_loss",
        "def_sacks",
        "def_qb_hits",
    ),
    "LB": (
        "def_tackles_solo",
        "def_tackle_assists",
        "def_tackles_for_loss",
        "def_sacks",
        "def_qb_hits",
    ),
    "DB": (
        "def_tackles_solo",
        "def_tackle_assists",
        "def_interceptions",
        "def_pass_defended",
    ),
}

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def norm_name(value: Any) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()

def finite_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default

def parse_pct(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.endswith("%"):
        text = text[:-1]
        try:
            return float(text) / 100.0
        except ValueError:
            return None
    try:
        x = float(text)
    except ValueError:
        return None
    if not math.isfinite(x) or x < 0:
        return None
    if x <= 1.000001:
        return x
    if x <= 100.000001:
        return x / 100.0
    return None

def canon_pos(value: Any) -> str | None:
    return POSITION_MAP.get(str(value or "").strip().upper())

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def mean_or_none(values):
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return statistics.fmean(vals) if vals else None

def trend_or_none(values):
    vals = [v for v in values if v is not None]
    if len(vals) < 6:
        return None
    return statistics.fmean(vals[-3:]) - statistics.fmean(vals[-6:-3])

def snap_share(row: dict[str, Any], pos: str) -> float | None:
    if pos in {"QB", "RB", "WR", "TE"}:
        return row.get("offense_pct")
    if pos in {"DL", "LB", "DB"}:
        return row.get("defense_pct")
    if pos == "K":
        return row.get("st_pct")
    return None

def raw_components(stats: dict[str, Any]) -> dict[str, float]:
    return {
        field: round(finite_float(stats.get(field), 0.0), 6)
        for field in SCORING_COMPONENTS
    }

def has_any_stat_signal(stats: dict[str, Any]) -> bool:
    fields = set(SCORING_COMPONENTS) | {
        "targets",
        "target_share",
        "air_yards_share",
        "receiving_air_yards",
    }
    return any(abs(finite_float(stats.get(k), 0.0)) > 0 for k in fields)

def is_active(row: dict[str, Any]) -> bool:
    snap_total = (
        finite_float(row.get("offense_snaps"), 0.0)
        + finite_float(row.get("defense_snaps"), 0.0)
        + finite_float(row.get("st_snaps"), 0.0)
    )
    return snap_total > 0 or has_any_stat_signal(row.get("stats", {}))

def load_players(path: Path):
    rows = read_csv(path)
    headers = set(rows[0]) if rows else set()
    required = {"gsis_id", "pfr_id", "position"}
    if not required.issubset(headers):
        raise RuntimeError(
            f"players.csv missing required ID fields: {sorted(required - headers)}"
        )

    gsis_meta = {}
    pfr_to_gsis = {}
    duplicate_pfr = set()

    for r in rows:
        gsis = str(r.get("gsis_id") or "").strip()
        pfr = str(r.get("pfr_id") or "").strip()
        if gsis:
            gsis_meta[gsis] = {
                "position": canon_pos(r.get("position")),
                "display_name": (
                    r.get("display_name")
                    or r.get("full_name")
                    or r.get("football_name")
                    or ""
                ),
            }
        if gsis and pfr:
            if pfr in pfr_to_gsis and pfr_to_gsis[pfr] != gsis:
                duplicate_pfr.add(pfr)
            pfr_to_gsis[pfr] = gsis

    if duplicate_pfr:
        raise RuntimeError(
            f"ambiguous PFR IDs in players crosswalk: {len(duplicate_pfr)}"
        )
    return gsis_meta, pfr_to_gsis

def load_season(stats_path: Path, snaps_path: Path, gsis_meta, pfr_to_gsis):
    stats_rows = read_csv(stats_path)
    snap_rows = read_csv(snaps_path)

    by_key = {}
    stats_relevant = 0

    for s in stats_rows:
        if str(s.get("season_type") or "").upper() != "REG":
            continue
        gsis = str(s.get("player_id") or "").strip()
        if not gsis:
            continue
        season = int(s["season"])
        week = int(s["week"])
        pos = canon_pos(s.get("position")) or (gsis_meta.get(gsis) or {}).get("position")
        if pos not in POSITIONS:
            continue
        stats_relevant += 1
        key = (season, week, gsis)
        if key in by_key and by_key[key].get("stats"):
            raise RuntimeError(f"duplicate stats key: {key}")
        by_key[key] = {
            "season": season,
            "week": week,
            "gsis_id": gsis,
            "player_name": s.get("player_display_name") or s.get("player_name") or "",
            "team": str(s.get("team") or "").strip().upper(),
            "position": pos,
            "stats": s,
            "offense_snaps": 0.0,
            "offense_pct": None,
            "defense_snaps": 0.0,
            "defense_pct": None,
            "st_snaps": 0.0,
            "st_pct": None,
            "has_stats_row": True,
            "has_snap_row": False,
        }

    snap_relevant = 0
    snap_mapped = 0
    snap_joined_to_stats = 0
    snap_unmapped_samples = []

    for s in snap_rows:
        if str(s.get("game_type") or "").upper() != "REG":
            continue
        pfr = str(s.get("pfr_player_id") or "").strip()
        if not pfr:
            continue
        pos_from_snap = canon_pos(s.get("position"))
        gsis = pfr_to_gsis.get(pfr)
        pos_from_player = (gsis_meta.get(gsis) or {}).get("position") if gsis else None
        pos = pos_from_player or pos_from_snap
        if pos not in POSITIONS:
            continue
        snap_relevant += 1
        if not gsis:
            if len(snap_unmapped_samples) < 25:
                snap_unmapped_samples.append({
                    "player": s.get("player"),
                    "pfr_player_id": pfr,
                    "position": s.get("position"),
                    "season": s.get("season"),
                    "week": s.get("week"),
                })
            continue
        snap_mapped += 1
        season = int(s["season"])
        week = int(s["week"])
        key = (season, week, gsis)
        existed = key in by_key
        if not existed:
            by_key[key] = {
                "season": season,
                "week": week,
                "gsis_id": gsis,
                "player_name": s.get("player") or (gsis_meta.get(gsis) or {}).get("display_name") or "",
                "team": str(s.get("team") or "").strip().upper(),
                "position": pos,
                "stats": {},
                "has_stats_row": False,
                "has_snap_row": True,
            }
        else:
            by_key[key]["has_snap_row"] = True
            snap_joined_to_stats += 1

        row = by_key[key]
        row["offense_snaps"] = finite_float(s.get("offense_snaps"), 0.0)
        row["offense_pct"] = parse_pct(s.get("offense_pct"))
        row["defense_snaps"] = finite_float(s.get("defense_snaps"), 0.0)
        row["defense_pct"] = parse_pct(s.get("defense_pct"))
        row["st_snaps"] = finite_float(s.get("st_snaps"), 0.0)
        row["st_pct"] = parse_pct(s.get("st_pct"))

    mapped_rate = snap_mapped / snap_relevant if snap_relevant else 0.0
    if snap_relevant < 1000:
        raise RuntimeError(f"implausibly few relevant snap rows: {snap_relevant}")
    if mapped_rate < 0.90:
        raise RuntimeError(
            f"snap PFR->GSIS identity mapping below QC floor: {mapped_rate:.4f}"
        )

    rows = list(by_key.values())
    for r in rows:
        r["active"] = is_active(r)
        r["snap_share"] = snap_share(r, r["position"])

    return rows, {
        "stats_relevant_rows": stats_relevant,
        "snap_relevant_rows": snap_relevant,
        "snap_mapped_rows": snap_mapped,
        "snap_mapping_rate": mapped_rate,
        "snap_joined_to_stats_rows": snap_joined_to_stats,
        "snap_unmapped_samples": snap_unmapped_samples,
    }

def opportunity_features(history, pos):
    fields = OPPORTUNITY_BY_POSITION[pos]
    out = {}
    for field in fields:
        vals = [
            finite_float(r.get("stats", {}).get(field), 0.0)
            for r in history
        ]
        out[f"{field}__last3_active_mean"] = mean_or_none(vals[-3:])
        out[f"{field}__season_to_date_active_mean"] = mean_or_none(vals)
        out[f"{field}__last3_minus_prior3"] = trend_or_none(vals)
    return out

def build_origins(all_rows):
    by_player_season = defaultdict(list)
    for r in all_rows:
        if r["season"] not in DEV_SEASONS:
            raise RuntimeError(f"holdout or unsupported season entered builder: {r['season']}")
        if r["position"] not in POSITIONS:
            continue
        by_player_season[(r["season"], r["gsis_id"])].append(r)

    cohort = []
    excluded = Counter()

    for (season, gsis), rows in by_player_season.items():
        rows.sort(key=lambda x: x["week"])
        for origin in ORIGIN_WEEKS:
            history = [r for r in rows if r["week"] <= origin and r["active"]]
            future = [r for r in rows if r["week"] > origin and r["active"]]

            if not history:
                excluded["no_prior_active_game"] += 1
                continue
            if len(future) < 2:
                excluded["fewer_than_2_future_active_games"] += 1
                continue

            pos = history[-1]["position"]
            # Require the current position assignment to be internally stable
            # within the historical player-season at the origin.
            hist_positions = {r["position"] for r in history[-3:]}
            if len(hist_positions) != 1:
                excluded["recent_position_instability"] += 1
                continue

            target_games = future[:4]
            feature_max_week = max(r["week"] for r in history)
            target_min_week = min(r["week"] for r in target_games)
            if feature_max_week > origin:
                raise RuntimeError("future leakage in feature window")
            if target_min_week <= origin:
                raise RuntimeError("target does not occur strictly after origin")

            snaps = [r["snap_share"] for r in history]
            row = {
                "season": season,
                "origin_week": origin,
                "gsis_id": gsis,
                "player_name": history[-1]["player_name"],
                "position": pos,
                "team_at_origin": history[-1]["team"],
                "prior_active_games": len(history),
                "feature_max_week": feature_max_week,
                "target_min_week": target_min_week,
                "target_active_game_count": len(target_games),
                "snap_share__latest_active": snaps[-1],
                "snap_share__last3_active_mean": mean_or_none(snaps[-3:]),
                "snap_share__season_to_date_active_mean": mean_or_none(snaps),
                "snap_share__last3_minus_prior3": trend_or_none(snaps),
                "history_last3_scoring_components_json": json.dumps(
                    [
                        {
                            "week": r["week"],
                            "components": raw_components(r.get("stats", {})),
                        }
                        for r in history[-3:]
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "history_season_to_date_scoring_components_json": json.dumps(
                    [
                        {
                            "week": r["week"],
                            "components": raw_components(r.get("stats", {})),
                        }
                        for r in history
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "target_next4_active_games_json": json.dumps(
                    [
                        {
                            "week": r["week"],
                            "team": r["team"],
                            "snap_share": r["snap_share"],
                            "components": raw_components(r.get("stats", {})),
                        }
                        for r in target_games
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            }
            row.update(opportunity_features(history, pos))
            cohort.append(row)

    return cohort, excluded

def write_csv_gz(path: Path, rows):
    if not rows:
        raise RuntimeError("empty cohort")
    fields = list(rows[0].keys())
    for row in rows:
        if list(row.keys()) != fields:
            raise RuntimeError("inconsistent cohort schema")
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", required=True)
    ap.add_argument("--players", required=True)
    ap.add_argument("--out-cohort", required=True)
    ap.add_argument("--out-audit", required=True)
    ap.add_argument("--out-manifest", required=True)
    args = ap.parse_args()

    source = Path(args.source_dir)
    players_path = Path(args.players)
    gsis_meta, pfr_to_gsis = load_players(players_path)

    all_rows = []
    season_audits = {}
    source_hashes = {
        "players.csv": sha256(players_path),
    }

    for season in DEV_SEASONS:
        stats = source / f"stats_player_week_{season}.csv"
        snaps = source / f"snap_counts_{season}.csv"
        if not stats.exists() or not snaps.exists():
            raise RuntimeError(f"missing development source files for {season}")

        source_hashes[stats.name] = sha256(stats)
        source_hashes[snaps.name] = sha256(snaps)

        rows, audit = load_season(stats, snaps, gsis_meta, pfr_to_gsis)
        all_rows.extend(rows)
        season_audits[str(season)] = audit

    if any(r["season"] == HOLDOUT_SEASON for r in all_rows):
        raise RuntimeError("2025 holdout was opened in B41B")

    cohort, excluded = build_origins(all_rows)
    cohort.sort(key=lambda r: (r["season"], r["origin_week"], r["position"], r["gsis_id"]))

    columns = list(cohort[0].keys()) if cohort else []
    lowered = " ".join(columns).lower()
    for token in FORBIDDEN_FEATURE_TOKENS:
        if token in lowered:
            raise RuntimeError(f"forbidden feature/identity token in cohort schema: {token}")

    leakage_bad = [
        r for r in cohort
        if int(r["feature_max_week"]) > int(r["origin_week"])
        or int(r["target_min_week"]) <= int(r["origin_week"])
    ]
    if leakage_bad:
        raise RuntimeError(f"leakage audit failed for {len(leakage_bad)} rows")

    by_season_pos = Counter((r["season"], r["position"]) for r in cohort)
    by_position = Counter(r["position"] for r in cohort)
    by_season = Counter(r["season"] for r in cohort)

    # Structural cohort-quality floors. These are not role thresholds
    # and do not use target performance.
    for season in DEV_SEASONS:
        for pos in POSITIONS:
            n = by_season_pos[(season, pos)]
            floor = 40 if pos == "K" else 100
            if n < floor:
                raise RuntimeError(
                    f"insufficient development cohort size season={season} pos={pos} n={n}"
                )

    cohort_path = Path(args.out_cohort)
    write_csv_gz(cohort_path, cohort)

    audit = {
        "schema_version": 1,
        "study_id": "player-role-v2",
        "phase": "B41B-historical-cohort-construction-and-leakage-audit",
        "development_seasons": list(DEV_SEASONS),
        "untouched_holdout_season": HOLDOUT_SEASON,
        "holdout_rows_read": 0,
        "historical_projection_features_used": False,
        "model_fit_performed": False,
        "predictor_target_association_computed": False,
        "role_weights_derived": False,
        "role_thresholds_derived": False,
        "production_change_authorized": False,
        "cohort_row_count": len(cohort),
        "row_counts_by_season": {str(k): v for k, v in sorted(by_season.items())},
        "row_counts_by_position": dict(sorted(by_position.items())),
        "row_counts_by_season_position": {
            f"{season}:{pos}": by_season_pos[(season, pos)]
            for season in DEV_SEASONS
            for pos in POSITIONS
        },
        "exclusions": dict(excluded),
        "identity_and_source_audit_by_season": season_audits,
        "leakage_checks": {
            "feature_window_never_after_origin": True,
            "target_window_strictly_after_origin": True,
            "owner_identity_absent": True,
            "dynasty_roster_identity_absent": True,
            "2025_holdout_absent": True,
            "projection_features_absent": True,
        },
        "target_status": {
            "future_raw_components_constructed": True,
            "future_league_scored_target_computed": False,
            "reason": (
                "B41B intentionally preserves raw future game components only. "
                "The exact target scorer must be frozen in the next phase before "
                "any model fitting or predictor-target association."
            ),
        },
    }
    Path(args.out_audit).write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "study_id": "player-role-v2",
        "phase": "B41B-development-cohort-manifest",
        "builder_sha256": sha256(Path(__file__)),
        "source_sha256": source_hashes,
        "cohort_sha256": sha256(cohort_path),
        "cohort_row_count": len(cohort),
        "cohort_columns": columns,
        "development_seasons": list(DEV_SEASONS),
        "holdout_season": HOLDOUT_SEASON,
        "holdout_opened": False,
        "model_fit_performed": False,
        "production_change_authorized": False,
    }
    Path(args.out_manifest).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "cohort_row_count": len(cohort),
        "rows_by_position": dict(sorted(by_position.items())),
        "holdout_opened": False,
        "projection_features_used": False,
        "model_fit_performed": False,
        "target_scored": False,
        "production_authorized": False,
    }, indent=2))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Continuous Opportunity / Role Signal V2 — Phase 1 coverage + structure audit.

RESEARCH ONLY. No deployed ROLE_MULT, PROD_MULT_DATA, AGE_CURVE, Production V2,
Market Value, or player value is changed.

Purpose
-------
The deployed calculator still contains a coarse role label / ROLE_MULT layer,
while current Sleeper data exposes continuous depth-chart order and nflverse
provides historical game-level snap participation.

This phase does NOT create an opportunity coefficient. It answers:

1. Can historical offensive / defensive snap participation be attached cleanly
   to tracked fantasy positions?
2. Can snap-count PFR identities be linked to nflverse GSIS identities for a
   future leakage-safe scoring evaluation?
3. What does continuous historical opportunity look like by position?
4. How stable is opportunity from one season to the next?
5. For current tracked players, how much 2025 opportunity and current Sleeper
   depth-chart coverage exists?
6. How coarse are deployed role labels relative to the continuous signal?

Primary historical opportunity signal
-------------------------------------
For QB/RB/WR/TE:
    sum(game offense_pct) / scheduled_team_games

For DL/LB/DB:
    sum(game defense_pct) / scheduled_team_games

Missing games therefore contribute zero. This intentionally captures both role
and availability / lost participation, which is dynasty-relevant.

Secondary signal:
    average snap share in games where the player recorded primary-unit snaps

That isolates role intensity when active.

No coefficient is selected here. Phase 2 must test lagged opportunity
out-of-sample against future realized custom-scored production.

Sources
-------
nflverse player metadata:
https://github.com/nflverse/nflverse-data/releases/download/players/players.csv

nflverse snap counts:
https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_<YEAR>.csv

Sleeper players:
https://api.sleeper.app/v1/players/nfl

Outputs
-------
research/opportunity-v2/opportunity_v2_phase1_coverage_audit.json
research/opportunity-v2/opportunity_v2_phase1_coverage_audit.md

Usage
-----
python3 research/opportunity-v2/opportunity_v2_phase1_coverage_audit.py --selftest
python3 research/opportunity-v2/opportunity_v2_phase1_coverage_audit.py --write
python3 research/opportunity-v2/opportunity_v2_phase1_coverage_audit.py --check
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

INDEX_HTML = REPO_ROOT / "index.html"
IDENTITY_PATH = SCRIPTS / "identity_crosswalk.json"

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "opportunity-v2"
    / "opportunity_v2_phase1_coverage_audit.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "opportunity-v2"
    / "opportunity_v2_phase1_coverage_audit.md"
)

NFLVERSE_PLAYERS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"
)
NFLVERSE_SNAP_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "snap_counts/snap_counts_{season}.csv"
)
SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"

METHOD_VERSION = "opportunity-v2-phase1-coverage-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
HISTORICAL_SEASONS = tuple(range(2015, 2026))
CURRENT_REFERENCE_SEASON = 2025
HTTP_TIMEOUT_SECONDS = 90


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON: {path.relative_to(REPO_ROOT)}: {exc}"
        ) from exc


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\.?\b", "", text)
    text = re.sub(r"[.'’`\-]", "", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def integer_or_none(value: Any) -> int | None:
    x = finite_number(value)
    if x is None:
        return None
    rounded = int(round(x))
    if abs(x - rounded) > 1e-9:
        return None
    return rounded


def scheduled_games(season: int) -> int:
    return 16 if season <= 2020 else 17


def normalize_pct(value: Any) -> float | None:
    x = finite_number(value)
    if x is None:
        return None
    if x > 1.5:
        x /= 100.0
    return max(0.0, min(1.0, x))


def normalize_position(
    position: Any = None,
    position_group: Any = None,
) -> str | None:
    pos = str(position or "").strip().upper()
    group = str(position_group or "").strip().upper()

    for value in (pos, group):
        if value in {"QB", "RB", "WR", "TE"}:
            return value
        if value in {"CB", "DB", "FS", "SS", "S"}:
            return "DB"
        if value in {"LB", "ILB", "OLB"}:
            return "LB"
        if value in {"DL", "DE", "DT", "NT", "EDGE", "ED"}:
            return "DL"

    return None


def fetch_csv_rows(
    url: str,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    sess = session or requests.Session()
    response = sess.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    reader = csv.DictReader(io.StringIO(response.text))
    return [dict(row) for row in reader]


def fetch_sleeper_players(
    session: requests.Session | None = None,
) -> dict[str, dict[str, Any]]:
    sess = session or requests.Session()
    response = sess.get(SLEEPER_PLAYERS_URL, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, dict) or len(payload) < 1000:
        raise RuntimeError("Sleeper player index is malformed or unexpectedly sparse")

    return {
        str(player_id): row
        for player_id, row in payload.items()
        if isinstance(row, dict)
    }


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def build_identity_name_map(rows: Any) -> dict[str, str]:
    if not isinstance(rows, list):
        raise RuntimeError("identity_crosswalk.json must contain a JSON list")

    buckets: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("requires_manual_review") is True:
            continue

        sleeper_id = str(row.get("sleeper_id") or "").strip()
        if not sleeper_id:
            continue

        for field in ("name", "normalized_name"):
            norm = normalize_name(row.get(field))
            if norm:
                buckets[norm].add(sleeper_id)

    return {
        name: next(iter(ids))
        for name, ids in buckets.items()
        if len(ids) == 1
    }


def build_nflverse_player_maps(
    rows: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
]:
    by_pfr: dict[str, dict[str, Any]] = {}
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        pfr_id = str(row.get("pfr_id") or "").strip()
        gsis_id = str(row.get("gsis_id") or "").strip() or None
        display_name = str(
            row.get("display_name")
            or row.get("full_name")
            or row.get("football_name")
            or ""
        ).strip()
        pos = normalize_position(
            row.get("position"),
            row.get("position_group"),
        )

        compact = {
            "pfr_id": pfr_id or None,
            "gsis_id": gsis_id,
            "display_name": display_name or None,
            "pos": pos,
            "birth_date": str(row.get("birth_date") or "").strip() or None,
        }

        if pfr_id:
            by_pfr[pfr_id] = compact

        norm = normalize_name(display_name)
        if norm:
            by_name[norm].append(compact)

    if len(by_pfr) < 1000:
        raise RuntimeError(
            f"nflverse player metadata PFR coverage unexpectedly sparse: {len(by_pfr)}"
        )

    return by_pfr, by_name


def resolve_current_nflverse_player(
    player_key: str,
    pos: str,
    by_name: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str]:
    norm = normalize_name(player_key)
    candidates = by_name.get(norm, [])

    compatible = [
        row for row in candidates
        if row.get("pos") == pos
    ]

    if len(compatible) == 1:
        return compatible[0], "unique_name_position"

    if len(candidates) == 1:
        return candidates[0], "unique_name_only"

    if candidates:
        return None, "ambiguous"

    return None, "unresolved"


def primary_pct_and_snaps(
    pos: str,
    row: dict[str, Any],
) -> tuple[float | None, float]:
    if pos in {"QB", "RB", "WR", "TE"}:
        pct = normalize_pct(row.get("offense_pct"))
        snaps = finite_number(row.get("offense_snaps")) or 0.0
    else:
        pct = normalize_pct(row.get("defense_pct"))
        snaps = finite_number(row.get("defense_snaps")) or 0.0
    return pct, max(0.0, snaps)


def build_historical_player_seasons(
    snap_rows_by_season: dict[int, list[dict[str, Any]]],
    nflverse_by_pfr: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    # Aggregate at game level first to protect against duplicate rows.
    games: dict[
        tuple[int, str, str],
        dict[str, Any],
    ] = {}

    for season, rows in snap_rows_by_season.items():
        for row in rows:
            game_type = str(row.get("game_type") or "").strip().upper()
            if game_type and game_type != "REG":
                continue

            pfr_id = str(row.get("pfr_player_id") or "").strip()
            game_id = str(
                row.get("game_id")
                or row.get("pfr_game_id")
                or ""
            ).strip()
            if not pfr_id or not game_id:
                continue

            metadata = nflverse_by_pfr.get(pfr_id)
            pos = (
                metadata.get("pos")
                if metadata
                else normalize_position(row.get("position"))
            )
            if pos not in TRACKED_POSITIONS:
                continue

            pct, snaps = primary_pct_and_snaps(pos, row)
            if pct is None and snaps <= 0:
                continue

            key = (season, pfr_id, game_id)
            payload = games.setdefault(
                key,
                {
                    "season": season,
                    "pfr_id": pfr_id,
                    "game_id": game_id,
                    "player": (
                        (metadata or {}).get("display_name")
                        or str(row.get("player") or "").strip()
                        or pfr_id
                    ),
                    "gsis_id": (metadata or {}).get("gsis_id"),
                    "pos": pos,
                    "pct": 0.0,
                    "snaps": 0.0,
                },
            )
            payload["pct"] = max(float(payload["pct"]), float(pct or 0.0))
            payload["snaps"] = max(float(payload["snaps"]), float(snaps))

    season_groups: dict[
        tuple[int, str],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for payload in games.values():
        season_groups[(payload["season"], payload["pfr_id"])].append(payload)

    out = []
    for (season, pfr_id), rows in season_groups.items():
        rows = sorted(rows, key=lambda r: r["game_id"])
        first = rows[0]
        scheduled = scheduled_games(season)

        primary_games = [r for r in rows if float(r["snaps"]) > 0.0]
        pct_sum = sum(float(r["pct"]) for r in rows)

        active_pct = [
            float(r["pct"])
            for r in primary_games
            if r["pct"] is not None
        ]

        out.append(
            {
                "season": season,
                "pfr_id": pfr_id,
                "gsis_id": first.get("gsis_id"),
                "player": first["player"],
                "pos": first["pos"],
                "scheduled_games": scheduled,
                "snap_row_games": len(rows),
                "primary_snap_games": len(primary_games),
                "total_primary_snaps": sum(
                    float(r["snaps"]) for r in rows
                ),
                "season_opportunity_share": pct_sum / scheduled,
                "active_game_snap_share": (
                    statistics.fmean(active_pct)
                    if active_pct else 0.0
                ),
                "primary_game_availability_share": (
                    len(primary_games) / scheduled
                ),
            }
        )

    out.sort(
        key=lambda r: (
            r["season"],
            r["pos"],
            r["player"],
            r["pfr_id"],
        )
    )

    if len(out) < 5000:
        raise RuntimeError(
            f"Historical snap player-season sample unexpectedly sparse: {len(out)}"
        )

    return out


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(float(v) for v in values)
    if len(vals) == 1:
        return vals[0]
    q = max(0.0, min(1.0, q))
    idx = (len(vals) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    t = idx - lo
    return vals[lo] * (1.0 - t) + vals[hi] * t


def rankdata(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda x: (x[1], x[0]))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg
        i = j
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    if den <= 0:
        return None
    return sum(a*b for a, b in zip(dx, dy)) / den


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    return pearson(rankdata(xs), rankdata(ys))


def summarize_historical(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    by_pos = {}
    for pos in TRACKED_POSITIONS:
        cohort = [r for r in rows if r["pos"] == pos]
        opp = [float(r["season_opportunity_share"]) for r in cohort]
        active = [float(r["active_game_snap_share"]) for r in cohort]

        by_pos[pos] = {
            "player_seasons": len(cohort),
            "with_gsis_id": sum(1 for r in cohort if r.get("gsis_id")),
            "gsis_identity_coverage_pct": (
                100.0 * sum(1 for r in cohort if r.get("gsis_id")) / len(cohort)
                if cohort else 0.0
            ),
            "season_opportunity_share_quantiles": {
                "p10": percentile(opp, 0.10),
                "p25": percentile(opp, 0.25),
                "p50": percentile(opp, 0.50),
                "p75": percentile(opp, 0.75),
                "p90": percentile(opp, 0.90),
            },
            "active_game_snap_share_quantiles": {
                "p10": percentile(active, 0.10),
                "p25": percentile(active, 0.25),
                "p50": percentile(active, 0.50),
                "p75": percentile(active, 0.75),
                "p90": percentile(active, 0.90),
            },
        }

    return {
        "player_seasons": len(rows),
        "with_gsis_id": sum(1 for r in rows if r.get("gsis_id")),
        "gsis_identity_coverage_pct": (
            100.0 * sum(1 for r in rows if r.get("gsis_id")) / len(rows)
            if rows else 0.0
        ),
        "by_position": by_pos,
    }


def year_over_year_stability(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    lookup = {
        (r["pfr_id"], int(r["season"])): r
        for r in rows
    }

    out = {}
    for pos in TRACKED_POSITIONS:
        current = []
        nxt = []

        for row in rows:
            if row["pos"] != pos:
                continue
            next_row = lookup.get(
                (row["pfr_id"], int(row["season"]) + 1)
            )
            if next_row is None or next_row["pos"] != pos:
                continue
            current.append(float(row["season_opportunity_share"]))
            nxt.append(float(next_row["season_opportunity_share"]))

        out[pos] = {
            "paired_player_seasons": len(current),
            "spearman_y_to_y_plus_1": spearman(current, nxt),
            "pearson_y_to_y_plus_1": pearson(current, nxt),
        }

    return out


def build_current_rows(
    cfg: dict[str, Any],
    historical_rows: list[dict[str, Any]],
    nflverse_by_name: dict[str, list[dict[str, Any]]],
    sleeper_players: dict[str, dict[str, Any]],
    identity_rows: Any,
) -> list[dict[str, Any]]:
    identity_map = build_identity_name_map(identity_rows)

    prior_lookup = {
        (r["pfr_id"], int(r["season"])): r
        for r in historical_rows
        if int(r["season"]) == CURRENT_REFERENCE_SEASON
    }

    out = []

    for player in sorted(cfg["player_db"]):
        info = cfg["player_db"][player]
        pos = info["pos"]
        if pos not in TRACKED_POSITIONS:
            continue

        nflverse_row, nflverse_resolution = resolve_current_nflverse_player(
            player,
            pos,
            nflverse_by_name,
        )

        pfr_id = nflverse_row.get("pfr_id") if nflverse_row else None
        gsis_id = nflverse_row.get("gsis_id") if nflverse_row else None
        prior = (
            prior_lookup.get((pfr_id, CURRENT_REFERENCE_SEASON))
            if pfr_id else None
        )

        sleeper_id = identity_map.get(normalize_name(player))
        sleeper_row = sleeper_players.get(sleeper_id) if sleeper_id else None

        depth_chart_order = (
            integer_or_none(sleeper_row.get("depth_chart_order"))
            if sleeper_row else None
        )
        depth_chart_position = (
            str(sleeper_row.get("depth_chart_position") or "").strip() or None
            if sleeper_row else None
        )
        sleeper_team = (
            str(sleeper_row.get("team") or "").strip() or None
            if sleeper_row else None
        )

        role = info.get("role")
        role_mult = finite_number(cfg["role_mult"].get(role))

        out.append(
            {
                "player": player,
                "pos": pos,
                "age": info.get("age"),
                "role": role,
                "role_mult": role_mult,
                "no_real_production_history": player in cfg["no_real_history"],
                "nflverse": {
                    "resolution": nflverse_resolution,
                    "pfr_id": pfr_id,
                    "gsis_id": gsis_id,
                },
                "sleeper": {
                    "sleeper_id": sleeper_id,
                    "team": sleeper_team,
                    "depth_chart_position": depth_chart_position,
                    "depth_chart_order": depth_chart_order,
                },
                "reference_2025": {
                    "season_opportunity_share": (
                        prior.get("season_opportunity_share")
                        if prior else None
                    ),
                    "active_game_snap_share": (
                        prior.get("active_game_snap_share")
                        if prior else None
                    ),
                    "primary_game_availability_share": (
                        prior.get("primary_game_availability_share")
                        if prior else None
                    ),
                    "primary_snap_games": (
                        prior.get("primary_snap_games")
                        if prior else None
                    ),
                },
            }
        )

    if len(out) < 500:
        raise RuntimeError(
            f"Current tracked opportunity cohort unexpectedly small: {len(out)}"
        )

    return out


def summarize_current(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    by_position = {}
    by_role = {}

    for pos in TRACKED_POSITIONS:
        cohort = [r for r in rows if r["pos"] == pos]
        opp = [
            float(r["reference_2025"]["season_opportunity_share"])
            for r in cohort
            if r["reference_2025"]["season_opportunity_share"] is not None
        ]

        role_x = []
        role_y = []
        depth_x = []
        depth_y = []

        for row in cohort:
            y = row["reference_2025"]["season_opportunity_share"]
            if y is None:
                continue

            if row["role_mult"] is not None:
                role_x.append(float(row["role_mult"]))
                role_y.append(float(y))

            depth = row["sleeper"]["depth_chart_order"]
            if depth is not None:
                # Smaller order = more opportunity, so negate for positive direction.
                depth_x.append(-float(depth))
                depth_y.append(float(y))

        by_position[pos] = {
            "tracked": len(cohort),
            "with_2025_opportunity": len(opp),
            "with_sleeper_depth_order": sum(
                1 for r in cohort
                if r["sleeper"]["depth_chart_order"] is not None
            ),
            "with_pfr_id": sum(
                1 for r in cohort if r["nflverse"]["pfr_id"]
            ),
            "with_gsis_id": sum(
                1 for r in cohort if r["nflverse"]["gsis_id"]
            ),
            "median_2025_opportunity_share": (
                statistics.median(opp) if opp else None
            ),
            "role_mult_vs_2025_opportunity_spearman": spearman(
                role_x,
                role_y,
            ),
            "inverse_depth_order_vs_2025_opportunity_spearman": spearman(
                depth_x,
                depth_y,
            ),
        }

    roles = sorted(
        {str(r["role"]) for r in rows if r.get("role")},
        key=lambda role: (
            -(finite_number(
                next(
                    (r["role_mult"] for r in rows if r["role"] == role),
                    None,
                )
            ) or 0.0),
            role,
        ),
    )

    for role in roles:
        cohort = [r for r in rows if r["role"] == role]
        opp = [
            float(r["reference_2025"]["season_opportunity_share"])
            for r in cohort
            if r["reference_2025"]["season_opportunity_share"] is not None
        ]
        role_mult = next(
            (r["role_mult"] for r in cohort if r["role_mult"] is not None),
            None,
        )
        by_role[role] = {
            "role_mult": role_mult,
            "tracked": len(cohort),
            "with_2025_opportunity": len(opp),
            "median_2025_opportunity_share": (
                statistics.median(opp) if opp else None
            ),
            "p25_2025_opportunity_share": percentile(opp, 0.25),
            "p75_2025_opportunity_share": percentile(opp, 0.75),
        }

    return {
        "tracked_players": len(rows),
        "with_2025_opportunity": sum(
            1 for r in rows
            if r["reference_2025"]["season_opportunity_share"] is not None
        ),
        "with_sleeper_depth_order": sum(
            1 for r in rows
            if r["sleeper"]["depth_chart_order"] is not None
        ),
        "with_pfr_id": sum(
            1 for r in rows if r["nflverse"]["pfr_id"]
        ),
        "with_gsis_id": sum(
            1 for r in rows if r["nflverse"]["gsis_id"]
        ),
        "no_history_players": sum(
            1 for r in rows if r["no_real_production_history"]
        ),
        "by_position": by_position,
        "by_role": by_role,
    }


def largest_role_opportunity_disagreements(
    rows: list[dict[str, Any]],
    limit: int = 40,
) -> list[dict[str, Any]]:
    eligible = [
        r for r in rows
        if r["role_mult"] is not None
        and r["reference_2025"]["season_opportunity_share"] is not None
    ]
    if not eligible:
        return []

    # Compare within-position percentiles so role/opportunity scales remain comparable.
    out = []

    for pos in TRACKED_POSITIONS:
        cohort = [r for r in eligible if r["pos"] == pos]
        if len(cohort) < 5:
            continue

        role_values = [float(r["role_mult"]) for r in cohort]
        opp_values = [
            float(r["reference_2025"]["season_opportunity_share"])
            for r in cohort
        ]
        role_ranks = rankdata(role_values)
        opp_ranks = rankdata(opp_values)

        denom = max(1.0, len(cohort) - 1.0)

        for row, rr, oo in zip(cohort, role_ranks, opp_ranks):
            role_pct = (rr - 1.0) / denom
            opp_pct = (oo - 1.0) / denom
            out.append(
                {
                    "player": row["player"],
                    "pos": pos,
                    "role": row["role"],
                    "role_mult": row["role_mult"],
                    "season_opportunity_share_2025": row[
                        "reference_2025"
                    ]["season_opportunity_share"],
                    "active_game_snap_share_2025": row[
                        "reference_2025"
                    ]["active_game_snap_share"],
                    "role_percentile_within_position": role_pct,
                    "opportunity_percentile_within_position": opp_pct,
                    "absolute_percentile_gap": abs(role_pct - opp_pct),
                    "sleeper_depth_chart_order": row[
                        "sleeper"
                    ]["depth_chart_order"],
                }
            )

    out.sort(
        key=lambda r: (
            -float(r["absolute_percentile_gap"]),
            r["pos"],
            r["player"],
        )
    )
    return out[:limit]


def build_result(
    session: requests.Session | None = None,
) -> dict[str, Any]:
    sess = session or requests.Session()

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)
    identity_rows = read_json(IDENTITY_PATH)

    print("Downloading nflverse player metadata...")
    nflverse_players = fetch_csv_rows(
        NFLVERSE_PLAYERS_URL,
        session=sess,
    )
    nflverse_by_pfr, nflverse_by_name = build_nflverse_player_maps(
        nflverse_players
    )

    snap_rows_by_season = {}
    for season in HISTORICAL_SEASONS:
        print(f"Downloading nflverse snap counts {season}...")
        snap_rows_by_season[season] = fetch_csv_rows(
            NFLVERSE_SNAP_URL.format(season=season),
            session=sess,
        )

    print("Downloading current Sleeper player index...")
    sleeper_players = fetch_sleeper_players(session=sess)

    historical_rows = build_historical_player_seasons(
        snap_rows_by_season,
        nflverse_by_pfr,
    )
    historical_summary = summarize_historical(historical_rows)
    stability = year_over_year_stability(historical_rows)

    current_rows = build_current_rows(
        cfg,
        historical_rows,
        nflverse_by_name,
        sleeper_players,
        identity_rows,
    )
    current_summary = summarize_current(current_rows)
    disagreements = largest_role_opportunity_disagreements(current_rows)

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": "RESEARCH_ONLY_CONTINUOUS_OPPORTUNITY_COVERAGE_AUDIT",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "role_mult_change_authorized": False,
        "opportunity_formula_authorized": False,
        "scope": {
            "historical_seasons": list(HISTORICAL_SEASONS),
            "tracked_positions": list(TRACKED_POSITIONS),
            "current_reference_season": CURRENT_REFERENCE_SEASON,
            "primary_signal": (
                "sum primary-unit game snap share divided by scheduled team games; "
                "missing games contribute zero"
            ),
            "secondary_signal": (
                "mean primary-unit snap share in games with primary-unit snaps"
            ),
            "offense_primary_unit": "offense_pct for QB/RB/WR/TE",
            "idp_primary_unit": "defense_pct for DL/LB/DB",
        },
        "sources": {
            "deployed_role_source": "index.html",
            "identity_crosswalk": str(IDENTITY_PATH.relative_to(REPO_ROOT)),
            "nflverse_players_url": NFLVERSE_PLAYERS_URL,
            "nflverse_snap_url_template": NFLVERSE_SNAP_URL,
            "sleeper_players_url": SLEEPER_PLAYERS_URL,
        },
        "historical_summary": historical_summary,
        "year_over_year_opportunity_stability": stability,
        "current_summary": current_summary,
        "largest_current_role_opportunity_disagreements": disagreements,
        "historical_player_seasons": historical_rows,
        "current_players": current_rows,
        "phase2_handoff": (
            "Use only lagged/preseason-available opportunity features and test "
            "out-of-sample by historical base season whether continuous opportunity "
            "adds predictive value beyond current production alone. Do not use "
            "same-season future snap information. Candidate families should begin "
            "with position-normalized season opportunity share, active-game snap "
            "share, and year-over-year change; depth-chart order should remain a "
            "current/preseason diagnostic until historical depth snapshots are "
            "available."
        ),
    }


def pct(value: Any) -> str:
    if value is None:
        return "—"
    return f"{100.0 * float(value):.1f}%"


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def render_markdown(result: dict[str, Any]) -> str:
    hist = result["historical_summary"]
    cur = result["current_summary"]

    lines = [
        "# Continuous Opportunity / Role Signal V2 — Phase 1 Coverage Audit",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No deployed ROLE_MULT or player value is changed.**",
        "",
        "## Signal definition",
        "",
        "Primary opportunity signal:",
        "",
        "`sum(primary-unit game snap share) / scheduled team games`",
        "",
        "For QB/RB/WR/TE the primary unit is offense. For DL/LB/DB it is defense.",
        "Missing games contribute zero, so the signal includes both role and availability.",
        "",
        "Secondary signal: average primary-unit snap share in games where the player",
        "recorded primary-unit snaps.",
        "",
        "## Historical coverage",
        "",
        f"- Historical seasons: **{result['scope']['historical_seasons'][0]}–"
        f"{result['scope']['historical_seasons'][-1]}**",
        f"- Player-seasons: **{hist['player_seasons']}**",
        f"- GSIS-linkable player-seasons: **{hist['with_gsis_id']} "
        f"({hist['gsis_identity_coverage_pct']:.1f}%)**",
        "",
        "| Pos | Player-seasons | GSIS coverage | Opp P25 | Opp P50 | Opp P75 | "
        "Active snap P50 | Y→Y+1 Spearman |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for pos in TRACKED_POSITIONS:
        row = hist["by_position"][pos]
        q = row["season_opportunity_share_quantiles"]
        aq = row["active_game_snap_share_quantiles"]
        stab = result["year_over_year_opportunity_stability"][pos]
        lines.append(
            f"| {pos} | {row['player_seasons']} | "
            f"{row['gsis_identity_coverage_pct']:.1f}% | "
            f"{pct(q['p25'])} | {pct(q['p50'])} | {pct(q['p75'])} | "
            f"{pct(aq['p50'])} | {fmt(stab['spearman_y_to_y_plus_1'])} |"
        )

    lines.extend(
        [
            "",
            "## Current tracked-player coverage",
            "",
            f"- Tracked players: **{cur['tracked_players']}**",
            f"- With 2025 opportunity: **{cur['with_2025_opportunity']}**",
            f"- With current Sleeper depth-chart order: "
            f"**{cur['with_sleeper_depth_order']}**",
            f"- With PFR ID: **{cur['with_pfr_id']}**",
            f"- With GSIS ID: **{cur['with_gsis_id']}**",
            f"- No-history players: **{cur['no_history_players']}**",
            "",
            "| Pos | Tracked | 2025 opp | Depth order | Median 2025 opp | "
            "Role vs opp ρ | Inverse depth vs opp ρ |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for pos in TRACKED_POSITIONS:
        row = cur["by_position"][pos]
        lines.append(
            f"| {pos} | {row['tracked']} | {row['with_2025_opportunity']} | "
            f"{row['with_sleeper_depth_order']} | "
            f"{pct(row['median_2025_opportunity_share'])} | "
            f"{fmt(row['role_mult_vs_2025_opportunity_spearman'])} | "
            f"{fmt(row['inverse_depth_order_vs_2025_opportunity_spearman'])} |"
        )

    lines.extend(
        [
            "",
            "## Deployed role labels vs 2025 opportunity",
            "",
            "| Role | ROLE_MULT | Tracked | With 2025 opp | Opp P25 | Opp median | Opp P75 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for role, row in cur["by_role"].items():
        lines.append(
            f"| {role} | {fmt(row['role_mult'])} | {row['tracked']} | "
            f"{row['with_2025_opportunity']} | "
            f"{pct(row['p25_2025_opportunity_share'])} | "
            f"{pct(row['median_2025_opportunity_share'])} | "
            f"{pct(row['p75_2025_opportunity_share'])} |"
        )

    lines.extend(
        [
            "",
            "## Largest role/opportunity disagreements",
            "",
            "These are descriptive only. Current 2026 role/depth labels are not assumed",
            "to be wrong merely because they differ from 2025 opportunity.",
            "",
            "| Player | Pos | Role | 2025 opp | Active snap | Depth order | Percentile gap |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )

    for row in result["largest_current_role_opportunity_disagreements"][:25]:
        lines.append(
            f"| {row['player']} | {row['pos']} | {row['role']} | "
            f"{pct(row['season_opportunity_share_2025'])} | "
            f"{pct(row['active_game_snap_share_2025'])} | "
            f"{row['sleeper_depth_chart_order'] if row['sleeper_depth_chart_order'] is not None else '—'} | "
            f"{pct(row['absolute_percentile_gap'])} |"
        )

    lines.extend(
        [
            "",
            "## Phase 2",
            "",
            result["phase2_handoff"],
            "",
        ]
    )

    return "\n".join(lines)


def write_outputs(result: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(render_markdown(result), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


def check_outputs() -> None:
    result = read_json(OUTPUT_JSON)

    if result.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Opportunity V2 Phase-1 method_version mismatch")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Opportunity Phase 1 lost production mutation guardrail")
    if result.get("deployment_authorized") is not False:
        raise RuntimeError("Opportunity Phase 1 unexpectedly authorizes deployment")
    if result.get("role_mult_change_authorized") is not False:
        raise RuntimeError("Opportunity Phase 1 unexpectedly authorizes ROLE_MULT change")
    if result.get("opportunity_formula_authorized") is not False:
        raise RuntimeError("Opportunity Phase 1 unexpectedly authorizes formula")

    hist = result.get("historical_summary") or {}
    if int(hist.get("player_seasons") or 0) < 5000:
        raise RuntimeError("Opportunity historical sample unexpectedly small")
    if float(hist.get("gsis_identity_coverage_pct") or 0.0) < 85.0:
        raise RuntimeError(
            "Opportunity historical GSIS linkage below 85%; Phase 2 handoff unsafe"
        )

    cur = result.get("current_summary") or {}
    if int(cur.get("tracked_players") or 0) < 500:
        raise RuntimeError("Opportunity current tracked cohort unexpectedly small")
    if int(cur.get("with_pfr_id") or 0) < 400:
        raise RuntimeError("Opportunity current PFR identity coverage unexpectedly low")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Opportunity Phase-1 markdown missing")

    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Historical coverage",
        "Current tracked-player coverage",
        "Deployed role labels vs 2025 opportunity",
        "Phase 2",
    ):
        if marker not in text:
            raise RuntimeError(
                f"Opportunity Phase-1 markdown missing marker: {marker}"
            )

    print("Continuous Opportunity V2 Phase-1 outputs passed guardrails.")


def run_selftest() -> None:
    assert scheduled_games(2020) == 16
    assert scheduled_games(2021) == 17
    assert abs(normalize_pct("75") - 0.75) < 1e-9
    assert abs(normalize_pct("0.75") - 0.75) < 1e-9
    assert normalize_position("EDGE") == "DL"
    assert normalize_position("CB") == "DB"
    assert normalize_position("ILB") == "LB"

    expected = (0.80 + 0.60) / 17.0
    assert abs(expected - 0.08235294117647059) < 1e-9
    assert abs(spearman([1, 2, 3], [10, 20, 30]) - 1.0) < 1e-9

    print(
        "Continuous Opportunity V2 Phase-1 self-test passed: season length, "
        "percentage normalization, position mapping, opportunity math, and ranking."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    if args.check:
        check_outputs()
        return

    result = build_result()

    if args.write:
        write_outputs(result)
    else:
        print(render_markdown(result))


if __name__ == "__main__":
    main()

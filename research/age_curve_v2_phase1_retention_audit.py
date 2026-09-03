#!/usr/bin/env python3
"""
Age Curve V2 — Phase 1 historical retention audit.

RESEARCH ONLY. No deployed age multiplier or player value is changed.

Purpose
-------
The deployed dynasty model currently uses hand-set AGE_CURVE peak/floor ages
plus special QB/LB decline rules. Before changing those constants, this audit
measures what actually happened historically under this league's scoring:

- How much current-season production survives into Year +1?
- How much survives into Year +2?
- How does that differ by position, age, and current production tier?
- At what ages does forward retention materially deteriorate?

Critical target choice
----------------------
The primary retention target is future custom-scored points per scheduled team
game, with a missing future player-season treated as ZERO. That intentionally
captures both performance decline and loss of role / league exit, which are
both relevant to dynasty value.

This is not an active-game-only aging curve.

Data
----
nflverse player metadata
nflverse weekly player stats, 2015-2025

The exact same historical nflverse scoring proxy already used by
No-History / Rookie V2 Phase 2 is imported rather than reimplemented.

Outputs
-------
research/age-curve-v2/age_curve_v2_phase1_retention_audit.json
research/age-curve-v2/age_curve_v2_phase1_retention_audit.md

Usage
-----
python3 research/age-curve-v2/age_curve_v2_phase1_retention_audit.py --selftest
python3 research/age-curve-v2/age_curve_v2_phase1_retention_audit.py --write
python3 research/age-curve-v2/age_curve_v2_phase1_retention_audit.py --check
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

INDEX_HTML = REPO_ROOT / "index.html"
PHASE2_PROSPECT_SCRIPT = (
    REPO_ROOT
    / "research"
    / "no-history-v2"
    / "no_history_v2_phase2_prospect_prior.py"
)

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase1_retention_audit.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase1_retention_audit.md"
)

NFLVERSE_PLAYERS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "players/players.csv"
)
NFLVERSE_WEEKLY_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{season}.csv"
)

METHOD_VERSION = "age-curve-v2-phase1-retention-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
STAT_YEARS = tuple(range(2015, 2026))
BASE_YEARS = tuple(range(2015, 2024))  # requires both +1 and +2 within data
MIN_AGE = 20
MAX_AGE = 39
MIN_POSITION_AGE_N = 15
MIN_TIER_AGE_N = 8
HTTP_TIMEOUT_SECONDS = 90

# Production-tier cut points within each position-season, based on the current
# season's custom points per scheduled team game.
TIER_NAMES = ("elite", "starter", "rotation", "depth")


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


def finite_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def int_or_none(value: Any) -> int | None:
    x = finite_or_none(value)
    if x is None:
        return None
    n = int(round(x))
    if abs(x - n) > 1e-9:
        return None
    return n


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(float(v) for v in values)
    if len(vals) == 1:
        return vals[0]
    q = max(0.0, min(1.0, float(q)))
    idx = (len(vals) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    t = idx - lo
    return vals[lo] * (1.0 - t) + vals[hi] * t


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def scheduled_games(season: int) -> int:
    return 16 if season <= 2020 else 17


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def load_phase2_module():
    if not PHASE2_PROSPECT_SCRIPT.exists():
        raise RuntimeError(
            f"Missing scoring source: {PHASE2_PROSPECT_SCRIPT.relative_to(REPO_ROOT)}"
        )
    spec = importlib.util.spec_from_file_location(
        "no_history_v2_phase2_prospect_prior",
        PHASE2_PROSPECT_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not import Phase-2 historical scoring proxy")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch_csv_rows(
    url: str,
    session: requests.Session,
) -> list[dict[str, str]]:
    response = session.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.text)))
    if not rows:
        raise RuntimeError(f"No CSV rows returned from {url}")
    return rows


def normalize_position_group(
    position: Any,
    position_group: Any,
) -> str | None:
    pos = str(position or "").upper().strip()
    group = str(position_group or "").upper().strip()

    if group in {"QB", "RB", "WR", "TE"}:
        return group
    if pos in {"QB", "RB", "WR", "TE"}:
        return pos

    if group == "DL" or pos in {"DE", "DT", "NT", "DL"}:
        return "DL"
    if group == "LB" or pos in {"LB", "ILB", "OLB", "EDGE"}:
        return "LB"
    if group == "DB" or pos in {"CB", "DB", "FS", "SS", "S"}:
        return "DB"

    return None


def parse_birth_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def season_age(birth: date | None, season: int) -> int | None:
    if birth is None:
        return None
    as_of = date(season, 9, 1)
    age = as_of.year - birth.year - (
        (as_of.month, as_of.day) < (birth.month, birth.day)
    )
    if MIN_AGE <= age <= MAX_AGE:
        return age
    return None


def build_player_metadata(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out = {}
    for row in rows:
        player_id = str(row.get("gsis_id") or "").strip()
        if not player_id:
            continue
        pos = normalize_position_group(
            row.get("position"),
            row.get("position_group"),
        )
        if pos not in TRACKED_POSITIONS:
            continue
        birth = parse_birth_date(row.get("birth_date"))
        if birth is None:
            continue
        out[player_id] = {
            "player_id": player_id,
            "player": str(row.get("display_name") or "").strip() or player_id,
            "pos": pos,
            "birth_date": birth,
        }
    return out


def build_player_seasons(
    metadata: dict[str, dict[str, Any]],
    stats_by_season: dict[int, list[dict[str, Any]]],
    scorer,
) -> dict[tuple[str, int], dict[str, Any]]:
    point_totals: dict[tuple[str, int], float] = defaultdict(float)
    stat_rows: dict[tuple[str, int], int] = defaultdict(int)

    for season, rows in stats_by_season.items():
        for row in rows:
            player_id = str(row.get("player_id") or "").strip()
            meta = metadata.get(player_id)
            if meta is None:
                continue
            key = (player_id, season)
            point_totals[key] += float(scorer(row))
            stat_rows[key] += 1

    seasons = {}
    for player_id, meta in metadata.items():
        for season in STAT_YEARS:
            age = season_age(meta["birth_date"], season)
            if age is None:
                continue
            key = (player_id, season)
            points = float(point_totals.get(key, 0.0))
            rows = int(stat_rows.get(key, 0))
            seasons[key] = {
                "player_id": player_id,
                "player": meta["player"],
                "pos": meta["pos"],
                "season": season,
                "age": age,
                "total_points": points,
                "stat_rows": rows,
                "points_per_team_game": points / scheduled_games(season),
                "points_per_stat_row": points / rows if rows > 0 else 0.0,
            }

    return seasons


def assign_tiers(
    seasons: dict[tuple[str, int], dict[str, Any]],
) -> None:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in seasons.values():
        if row["season"] not in BASE_YEARS:
            continue
        if row["stat_rows"] <= 0:
            continue
        grouped[(row["pos"], row["season"])].append(row)

    for cohort in grouped.values():
        vals = [float(r["points_per_team_game"]) for r in cohort]
        q90 = percentile(vals, 0.90)
        q60 = percentile(vals, 0.60)
        q30 = percentile(vals, 0.30)
        assert q90 is not None and q60 is not None and q30 is not None

        for row in cohort:
            value = float(row["points_per_team_game"])
            if value >= q90:
                tier = "elite"
            elif value >= q60:
                tier = "starter"
            elif value >= q30:
                tier = "rotation"
            else:
                tier = "depth"
            row["production_tier"] = tier


def build_retention_rows(
    seasons: dict[tuple[str, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    out = []

    for (player_id, season), current in seasons.items():
        if season not in BASE_YEARS:
            continue
        if current.get("stat_rows", 0) <= 0:
            continue
        tier = current.get("production_tier")
        if tier not in TIER_NAMES:
            continue

        next1 = seasons.get((player_id, season + 1))
        next2 = seasons.get((player_id, season + 2))
        if next1 is None or next2 is None:
            continue

        cur = float(current["points_per_team_game"])
        y1 = float(next1["points_per_team_game"])
        y2 = float(next2["points_per_team_game"])

        out.append(
            {
                "player_id": player_id,
                "player": current["player"],
                "pos": current["pos"],
                "season": season,
                "age": int(current["age"]),
                "production_tier": tier,
                "current_points_per_team_game": cur,
                "year1_points_per_team_game": y1,
                "year2_points_per_team_game": y2,
                "year1_any_stats": bool(next1["stat_rows"] > 0),
                "year2_any_stats": bool(next2["stat_rows"] > 0),
                "year1_retention_ratio": y1 / cur if cur > 0 else None,
                "year2_retention_ratio": y2 / cur if cur > 0 else None,
            }
        )

    return out


def retention_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}

    current = [float(r["current_points_per_team_game"]) for r in rows]
    y1 = [float(r["year1_points_per_team_game"]) for r in rows]
    y2 = [float(r["year2_points_per_team_game"]) for r in rows]

    current_sum = sum(current)
    y1_sum = sum(y1)
    y2_sum = sum(y2)

    ratio1 = [
        min(3.0, float(r["year1_retention_ratio"]))
        for r in rows
        if r.get("year1_retention_ratio") is not None
    ]
    ratio2 = [
        min(3.0, float(r["year2_retention_ratio"]))
        for r in rows
        if r.get("year2_retention_ratio") is not None
    ]

    return {
        "n": len(rows),
        "median_current_points_per_team_game": median(current),
        "aggregate_year1_retention": (
            y1_sum / current_sum if current_sum > 0 else None
        ),
        "aggregate_year2_retention": (
            y2_sum / current_sum if current_sum > 0 else None
        ),
        "median_individual_year1_retention_capped_3x": median(ratio1),
        "median_individual_year2_retention_capped_3x": median(ratio2),
        "year1_any_stats_share": sum(
            1 for r in rows if r["year1_any_stats"]
        ) / len(rows),
        "year2_any_stats_share": sum(
            1 for r in rows if r["year2_any_stats"]
        ) / len(rows),
        "year1_at_least_half_current_share": sum(
            1
            for r in rows
            if float(r["year1_points_per_team_game"])
            >= 0.5 * float(r["current_points_per_team_game"])
        )
        / len(rows),
        "year2_at_least_half_current_share": sum(
            1
            for r in rows
            if float(r["year2_points_per_team_game"])
            >= 0.5 * float(r["current_points_per_team_game"])
        )
        / len(rows),
    }


def summarize_by_position_age(
    retention_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    out = {}

    for pos in TRACKED_POSITIONS:
        pos_rows = [r for r in retention_rows if r["pos"] == pos]
        ages = sorted({int(r["age"]) for r in pos_rows})
        age_rows = {}

        for age in ages:
            cohort = [r for r in pos_rows if int(r["age"]) == age]
            if len(cohort) < MIN_POSITION_AGE_N:
                continue
            age_rows[str(age)] = retention_summary(cohort)

        out[pos] = {
            "all_ages": retention_summary(pos_rows),
            "by_age": age_rows,
        }

    return out


def summarize_by_position_tier_age(
    retention_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    out = {}

    for pos in TRACKED_POSITIONS:
        out[pos] = {}
        for tier in TIER_NAMES:
            tier_rows = [
                r
                for r in retention_rows
                if r["pos"] == pos and r["production_tier"] == tier
            ]
            ages = sorted({int(r["age"]) for r in tier_rows})
            age_map = {}
            for age in ages:
                cohort = [r for r in tier_rows if int(r["age"]) == age]
                if len(cohort) < MIN_TIER_AGE_N:
                    continue
                age_map[str(age)] = retention_summary(cohort)
            out[pos][tier] = {
                "all_ages": retention_summary(tier_rows),
                "by_age": age_map,
            }

    return out


def derive_empirical_peak_and_cliff(
    by_position_age: dict[str, Any],
) -> dict[str, Any]:
    """
    Descriptive only:
    - best retention age = age with highest aggregate Year+1 retention,
      requiring an emitted age cohort.
    - first material decline = first age at/after 24 where Y+1 retention falls
      below 75% and remains below 80% at the next emitted age.
    """
    out = {}

    for pos in TRACKED_POSITIONS:
        age_map = by_position_age[pos]["by_age"]
        rows = []
        for age_text, summary in age_map.items():
            ret = summary.get("aggregate_year1_retention")
            if ret is None:
                continue
            rows.append((int(age_text), float(ret), int(summary["n"])))
        rows.sort()

        if not rows:
            out[pos] = {
                "best_observed_retention_age": None,
                "first_material_retention_cliff_age": None,
            }
            continue

        best = max(rows, key=lambda x: (x[1], x[2], -x[0]))
        cliff = None
        for i, (age, ret, _) in enumerate(rows):
            if age < 24 or ret >= 0.75:
                continue
            next_ret = rows[i + 1][1] if i + 1 < len(rows) else None
            if next_ret is None or next_ret < 0.80:
                cliff = age
                break

        out[pos] = {
            "best_observed_retention_age": best[0],
            "best_observed_year1_retention": best[1],
            "first_material_retention_cliff_age": cliff,
        }

    return out


def deployed_age_policy(cfg: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for pos in TRACKED_POSITIONS:
        curve = cfg["age_curve"].get(pos) or cfg["age_curve"].get("WR")
        out[pos] = {
            "peak_start": int(curve["peakStart"]),
            "peak_end": int(curve["peakEnd"]),
            "floor_age": int(curve["floor"]),
        }
    out["special_rules"] = {
        "qb_post_peak_floor": cfg["qb_post_peak_floor"],
        "lb_post_peak_decay_power": cfg["lb_post_peak_decay_power"],
        "rb_fractional_age_active": True,
    }
    return out


def build_result(
    session: requests.Session | None = None,
) -> dict[str, Any]:
    sess = session or requests.Session()
    phase2 = load_phase2_module()
    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    print("Downloading nflverse player metadata...")
    players_rows = fetch_csv_rows(NFLVERSE_PLAYERS_URL, sess)

    stats_by_season = {}
    for season in STAT_YEARS:
        print(f"Downloading nflverse weekly player stats {season}...")
        stats_by_season[season] = fetch_csv_rows(
            NFLVERSE_WEEKLY_URL.format(season=season),
            sess,
        )

    metadata = build_player_metadata(players_rows)
    if len(metadata) < 5000:
        raise RuntimeError(
            f"Player metadata unexpectedly sparse: {len(metadata)}"
        )

    seasons = build_player_seasons(
        metadata,
        stats_by_season,
        phase2.score_nflverse_week,
    )
    assign_tiers(seasons)
    retention_rows = build_retention_rows(seasons)

    if len(retention_rows) < 3000:
        raise RuntimeError(
            f"Historical retention cohort unexpectedly sparse: {len(retention_rows)}"
        )

    by_position_age = summarize_by_position_age(retention_rows)
    by_position_tier_age = summarize_by_position_tier_age(retention_rows)

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": "RESEARCH_ONLY_HISTORICAL_AGE_RETENTION_AUDIT",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "age_curve_change_authorized": False,
        "target_definition": {
            "primary": (
                "future custom-scored points per scheduled team game; missing "
                "future player-season = zero"
            ),
            "secondary": "future points per nflverse stat row",
            "why": (
                "Dynasty age value should reflect performance, role retention, "
                "and league exit rather than active-game performance alone."
            ),
        },
        "historical_window": {
            "weekly_stat_years": list(STAT_YEARS),
            "base_years_with_two_future_seasons": list(BASE_YEARS),
            "retention_row_count": len(retention_rows),
        },
        "production_tiers": {
            "method": (
                "within each position-season: elite >= P90, starter P60-P90, "
                "rotation P30-P60, depth < P30 by current points/team-game"
            ),
            "names": list(TIER_NAMES),
        },
        "deployed_age_policy": deployed_age_policy(cfg),
        "by_position_age": by_position_age,
        "by_position_tier_age": by_position_tier_age,
        "descriptive_retention_landmarks": derive_empirical_peak_and_cliff(
            by_position_age
        ),
        "guardrail": (
            "This phase measures historical retention only. It does not fit or "
            "select replacement AGE_CURVE coefficients."
        ),
        "phase2_handoff": (
            "If historical retention cohorts are sufficiently populated, fit "
            "candidate age-value curves to future Year+1/Year+2 retention and "
            "compare them against the deployed age policy out of sample."
        ),
        "sources": {
            "nflverse_players": NFLVERSE_PLAYERS_URL,
            "nflverse_weekly_template": NFLVERSE_WEEKLY_URL,
            "historical_scoring_proxy": str(
                PHASE2_PROSPECT_SCRIPT.relative_to(REPO_ROOT)
            )
            + "::score_nflverse_week",
            "deployed_age_policy_source": "index.html",
        },
    }


def pct(value: Any) -> str:
    if value is None:
        return "—"
    return f"{100.0 * float(value):.1f}%"


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def render_markdown(result: dict[str, Any]) -> str:
    hist = result["historical_window"]
    policy = result["deployed_age_policy"]
    landmarks = result["descriptive_retention_landmarks"]

    lines = [
        "# Age Curve V2 — Phase 1 Historical Retention Audit",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No deployed age multiplier or player value is changed.**",
        "",
        result["guardrail"],
        "",
        "## Historical evidence",
        "",
        f"- Weekly stat seasons: **{hist['weekly_stat_years'][0]}–{hist['weekly_stat_years'][-1]}**",
        f"- Base seasons with full Year +1 and +2 targets: "
        f"**{hist['base_years_with_two_future_seasons'][0]}–"
        f"{hist['base_years_with_two_future_seasons'][-1]}**",
        f"- Player-season retention rows: **{hist['retention_row_count']}**",
        "",
        "Primary retention target treats a missing future season as **zero**. "
        "That makes the curve dynasty-relevant: decline, lost role, retirement, "
        "and league exit all count.",
        "",
        "## Current deployed age policy vs descriptive historical landmarks",
        "",
        "| Pos | Current peak | Current floor age | Best observed Y+1 retention age | "
        "First material retention cliff |",
        "|---|---:|---:|---:|---:|",
    ]

    for pos in TRACKED_POSITIONS:
        p = policy[pos]
        l = landmarks[pos]
        current_peak = f"{p['peak_start']}–{p['peak_end']}"
        lines.append(
            f"| {pos} | {current_peak} | {p['floor_age']} | "
            f"{l['best_observed_retention_age'] if l['best_observed_retention_age'] is not None else '—'} | "
            f"{l['first_material_retention_cliff_age'] if l['first_material_retention_cliff_age'] is not None else '—'} |"
        )

    lines.extend(
        [
            "",
            "These landmarks are descriptive only; they are **not replacement "
            "coefficients**.",
            "",
            "## Position-age Year +1 retention",
            "",
        ]
    )

    for pos in TRACKED_POSITIONS:
        lines.extend(
            [
                f"### {pos}",
                "",
                "| Age | N | Aggregate Y+1 retention | Aggregate Y+2 retention | "
                "Y+1 any-stat survival | Y+1 >= 50% current |",
                "|---:|---:|---:|---:|---:|---:|",
            ]
        )
        age_map = result["by_position_age"][pos]["by_age"]
        for age_text in sorted(age_map, key=int):
            row = age_map[age_text]
            lines.append(
                f"| {age_text} | {row['n']} | "
                f"{pct(row['aggregate_year1_retention'])} | "
                f"{pct(row['aggregate_year2_retention'])} | "
                f"{pct(row['year1_any_stats_share'])} | "
                f"{pct(row['year1_at_least_half_current_share'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Tier-sensitive retention",
            "",
            "The same age can behave differently for an elite player and a depth "
            "player. The table below summarizes all ages within each current "
            "production tier before Phase 2 fits any age interaction.",
            "",
            "| Pos | Tier | N | Y+1 retention | Y+2 retention | Y+1 any-stat survival |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )

    for pos in TRACKED_POSITIONS:
        for tier in TIER_NAMES:
            row = result["by_position_tier_age"][pos][tier]["all_ages"]
            lines.append(
                f"| {pos} | {tier} | {row.get('n', 0)} | "
                f"{pct(row.get('aggregate_year1_retention'))} | "
                f"{pct(row.get('aggregate_year2_retention'))} | "
                f"{pct(row.get('year1_any_stats_share'))} |"
            )

    lines.extend(
        [
            "",
            "## Next step",
            "",
            result["phase2_handoff"],
            "",
            "Phase 2 should test candidate curves out of sample by historical season "
            "rather than choosing ages because they visually fit this report.",
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
        raise RuntimeError("Age Curve V2 Phase-1 method_version mismatch")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Age audit lost production mutation guardrail")
    if result.get("deployment_authorized") is not False:
        raise RuntimeError("Age audit unexpectedly authorizes deployment")
    if result.get("age_curve_change_authorized") is not False:
        raise RuntimeError("Age audit unexpectedly authorizes age-curve changes")

    hist = result.get("historical_window") or {}
    if int(hist.get("retention_row_count") or 0) < 3000:
        raise RuntimeError("Historical age retention sample is implausibly small")

    by_position = result.get("by_position_age") or {}
    if set(by_position) != set(TRACKED_POSITIONS):
        raise RuntimeError("Age audit position coverage is incomplete")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Age audit markdown report missing")

    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Position-age Year +1 retention",
        "Tier-sensitive retention",
        "Next step",
    ):
        if marker not in text:
            raise RuntimeError(f"Age audit markdown missing marker: {marker}")

    print("Age Curve V2 Phase-1 outputs passed guardrails.")


def run_selftest() -> None:
    assert scheduled_games(2020) == 16
    assert scheduled_games(2021) == 17

    dob = date(2000, 10, 1)
    assert season_age(dob, 2025) == 24

    synthetic = [
        {
            "current_points_per_team_game": 10.0,
            "year1_points_per_team_game": 8.0,
            "year2_points_per_team_game": 6.0,
            "year1_any_stats": True,
            "year2_any_stats": True,
            "year1_retention_ratio": 0.8,
            "year2_retention_ratio": 0.6,
        },
        {
            "current_points_per_team_game": 10.0,
            "year1_points_per_team_game": 0.0,
            "year2_points_per_team_game": 0.0,
            "year1_any_stats": False,
            "year2_any_stats": False,
            "year1_retention_ratio": 0.0,
            "year2_retention_ratio": 0.0,
        },
    ]
    summary = retention_summary(synthetic)
    assert abs(summary["aggregate_year1_retention"] - 0.4) < 1e-9
    assert abs(summary["aggregate_year2_retention"] - 0.3) < 1e-9
    assert abs(summary["year1_any_stats_share"] - 0.5) < 1e-9
    assert abs(summary["year1_at_least_half_current_share"] - 0.5) < 1e-9

    print(
        "Age Curve V2 Phase-1 self-test passed: season age, scheduled-game "
        "denominator, zero-future retention, and survival metrics."
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

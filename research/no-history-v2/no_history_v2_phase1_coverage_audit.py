#!/usr/bin/env python3
"""
No-History / Rookie Value V2 — Phase 1 coverage audit.

RESEARCH ONLY. This script does not mutate index.html, PROD_MULT_DATA,
Market Value, Production V2, or any deployed player value.

Purpose
-------
Production V2 already builds normal forward/history candidates for most players.
This audit isolates the part still missing from the dynasty model: a prospect
prior for rookies and very young players with little/no real NFL history.

Phase 1 does NOT create a new value formula. It only answers:
1. Which tracked players are truly no-history?
2. Which of them are rookies / second-year players versus veterans?
3. Can we attach stable Sleeper identity + years experience + depth-chart data?
4. Can we attach NFL draft year / round / overall pick from nflverse?
5. Which players already have a normal Production V2 candidate?
6. Which players would actually be eligible for a future prospect-prior test?

External research sources
-------------------------
Sleeper players:
  https://api.sleeper.app/v1/players/nfl

nflverse draft picks:
  https://github.com/nflverse/nflverse-data/releases/download/draft_picks/draft_picks.csv

Outputs
-------
research/no-history-v2/no_history_v2_phase1_coverage_audit.json
research/no-history-v2/no_history_v2_phase1_coverage_audit.md

Usage
-----
python3 research/no-history-v2/no_history_v2_phase1_coverage_audit.py --selftest
python3 research/no-history-v2/no_history_v2_phase1_coverage_audit.py --write
python3 research/no-history-v2/no_history_v2_phase1_coverage_audit.py --check
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
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
PHASE1_PATH = (
    REPO_ROOT
    / "research"
    / "production-v2"
    / "production_v2_phase1_audit.json"
)
IDENTITY_PATH = SCRIPTS / "identity_crosswalk.json"

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "no-history-v2"
    / "no_history_v2_phase1_coverage_audit.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "no-history-v2"
    / "no_history_v2_phase1_coverage_audit.md"
)

SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"
NFLVERSE_DRAFT_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "draft_picks/draft_picks.csv"
)

METHOD_VERSION = "no-history-rookie-v2-phase1-coverage-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
RECENT_DRAFT_YEARS = {2025, 2026}
PROSPECT_MAX_YEARS_EXP = 1
HTTP_TIMEOUT_SECONDS = 60


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


def load_snapshot_values_module():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def valid_sleeper_id(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"none", "null", "na", "nan"}:
        return None
    return text


def build_identity_name_map(rows: Any) -> dict[str, str]:
    if not isinstance(rows, list):
        raise RuntimeError("identity_crosswalk.json must contain a JSON list")

    buckets: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        if not isinstance(row, dict):
            continue

        sleeper_id = valid_sleeper_id(row.get("sleeper_id"))
        if sleeper_id is None:
            continue

        if row.get("requires_manual_review") is True:
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


def fetch_sleeper_players(
    session: requests.Session | None = None,
) -> dict[str, dict[str, Any]]:
    sess = session or requests.Session()
    response = sess.get(SLEEPER_PLAYERS_URL, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, dict) or len(payload) < 1000:
        raise RuntimeError(
            "Sleeper players response is malformed or unexpectedly sparse"
        )

    out: dict[str, dict[str, Any]] = {}
    for sleeper_id, row in payload.items():
        if isinstance(row, dict):
            out[str(sleeper_id)] = row
    return out


def sleeper_display_name(row: dict[str, Any]) -> str:
    full = str(row.get("full_name") or "").strip()
    if full:
        return full
    first = str(row.get("first_name") or "").strip()
    last = str(row.get("last_name") or "").strip()
    return f"{first} {last}".strip()


def compatible_position(
    trade_desk_pos: str,
    source_pos: Any = None,
    source_category: Any = None,
) -> bool:
    pos = str(source_pos or "").strip().upper()
    category = str(source_category or "").strip().upper()

    if trade_desk_pos in {"QB", "RB", "WR", "TE"}:
        return trade_desk_pos in {pos, category}

    if trade_desk_pos == "DB":
        return (
            category == "DB"
            or pos in {"CB", "DB", "FS", "SS", "S"}
        )

    if trade_desk_pos == "LB":
        return (
            category in {"LB", "ED"}
            or pos in {"LB", "ILB", "OLB", "EDGE"}
        )

    if trade_desk_pos == "DL":
        return (
            category in {"DL", "ED"}
            or pos in {
                "DL",
                "DE",
                "DT",
                "NT",
                "EDGE",
            }
        )

    return False


def build_sleeper_name_index(
    sleeper_players: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for sleeper_id, row in sleeper_players.items():
        norm = normalize_name(sleeper_display_name(row))
        if norm:
            out[norm].append(sleeper_id)
    return out


def resolve_sleeper_player(
    player_key: str,
    trade_desk_pos: str,
    identity_name_map: dict[str, str],
    sleeper_players: dict[str, dict[str, Any]],
    sleeper_name_index: dict[str, list[str]],
) -> tuple[str | None, dict[str, Any] | None, str]:
    norm = normalize_name(player_key)

    direct_id = identity_name_map.get(norm)
    if direct_id and direct_id in sleeper_players:
        return direct_id, sleeper_players[direct_id], "identity_crosswalk"

    candidates = []
    for sleeper_id in sleeper_name_index.get(norm, []):
        row = sleeper_players[sleeper_id]
        if compatible_position(
            trade_desk_pos,
            row.get("position"),
            row.get("fantasy_positions"),
        ):
            candidates.append(sleeper_id)

    if len(candidates) == 1:
        sleeper_id = candidates[0]
        return sleeper_id, sleeper_players[sleeper_id], "unique_name_position"

    # Last-resort exact-name match is allowed only when globally unique.
    all_name_matches = sleeper_name_index.get(norm, [])
    if len(all_name_matches) == 1:
        sleeper_id = all_name_matches[0]
        return sleeper_id, sleeper_players[sleeper_id], "unique_name_only"

    if len(all_name_matches) > 1:
        return None, None, "ambiguous_name"

    return None, None, "unresolved"


def fetch_nflverse_draft_rows(
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    sess = session or requests.Session()
    response = sess.get(NFLVERSE_DRAFT_URL, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()

    text = response.text
    reader = csv.DictReader(io.StringIO(text))
    rows = []

    for row in reader:
        if not isinstance(row, dict):
            continue

        season = integer_or_none(row.get("season"))
        draft_round = integer_or_none(row.get("round"))
        pick = integer_or_none(row.get("pick"))
        full_name = str(
            row.get("full_name")
            or row.get("pfr_player_name")
            or row.get("name")
            or ""
        ).strip()

        if season is None or not full_name:
            continue

        rows.append(
            {
                "season": season,
                "round": draft_round,
                "pick": pick,
                "team": str(row.get("team") or "").strip() or None,
                "full_name": full_name,
                "position": str(row.get("position") or "").strip() or None,
                "category": str(row.get("category") or "").strip() or None,
                "college": str(row.get("college") or "").strip() or None,
                "age": finite_number(row.get("age")),
            }
        )

    if len(rows) < 10000:
        raise RuntimeError(
            f"nflverse draft data is unexpectedly sparse: {len(rows)} rows"
        )

    return rows


def build_draft_name_index(
    rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        norm = normalize_name(row.get("full_name"))
        if norm:
            out[norm].append(row)
    return out


def resolve_draft_row(
    player_key: str,
    trade_desk_pos: str,
    draft_name_index: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str]:
    norm = normalize_name(player_key)
    candidates = draft_name_index.get(norm, [])

    if not candidates:
        return None, "unresolved"

    compatible = [
        row
        for row in candidates
        if compatible_position(
            trade_desk_pos,
            row.get("position"),
            row.get("category"),
        )
    ]

    pool = compatible or candidates

    # Prefer the most recent draft season when a historical name collision exists.
    pool = sorted(
        pool,
        key=lambda r: (
            -(r.get("season") or 0),
            r.get("pick") if r.get("pick") is not None else 9999,
        ),
    )

    if not pool:
        return None, "unresolved"

    top = pool[0]

    if len(pool) == 1:
        return top, "unique_name_position" if compatible else "unique_name_only"

    if compatible:
        latest_season = top.get("season")
        same_latest = [
            r
            for r in pool
            if r.get("season") == latest_season
        ]
        if len(same_latest) == 1:
            return top, "latest_unique_position"

    return None, "ambiguous"


def classify_experience(
    years_exp: int | None,
    draft_season: int | None,
) -> str:
    if years_exp == 0:
        return "rookie"
    if years_exp == 1:
        return "second_year"
    if years_exp is not None and years_exp >= 2:
        return "veteran"

    if draft_season == 2026:
        return "rookie_inferred_from_draft"
    if draft_season == 2025:
        return "second_year_inferred_from_draft"

    return "unknown"


def prospect_prior_eligible(
    no_real_history: bool,
    years_exp: int | None,
    draft_season: int | None,
) -> bool:
    if not no_real_history:
        return False
    if years_exp is not None and years_exp <= PROSPECT_MAX_YEARS_EXP:
        return True
    return draft_season in RECENT_DRAFT_YEARS


def clean_phase1_candidate(candidate: Any) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None

    # Preserve only compact, diagnostic fields when present. The full Phase-1
    # object remains the source of truth and is not duplicated into this audit.
    keys = (
        "forward_points",
        "history_points",
        "combined_points",
        "fantasypros_points",
        "sleeper_points",
        "source",
        "status",
    )
    out = {k: candidate.get(k) for k in keys if k in candidate}
    return out or {"present": True}


def build_rows(
    cfg: dict[str, Any],
    phase1: dict[str, Any],
    identity_rows: Any,
    sleeper_players: dict[str, dict[str, Any]],
    draft_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    players = phase1.get("players")
    if not isinstance(players, dict) or len(players) < 500:
        raise RuntimeError("Production V2 Phase-1 player matrix is missing or sparse")

    identity_map = build_identity_name_map(identity_rows)
    sleeper_name_index = build_sleeper_name_index(sleeper_players)
    draft_name_index = build_draft_name_index(draft_rows)

    out = []

    for key in sorted(players):
        phase1_row = players[key]
        if not isinstance(phase1_row, dict):
            continue

        pos = str(phase1_row.get("pos") or "").strip().upper()
        if pos not in TRACKED_POSITIONS:
            continue

        player_cfg = cfg["player_db"].get(key) or {}
        role = player_cfg.get("role") or phase1_row.get("role")
        age = player_cfg.get("age") or phase1_row.get("age")
        no_real_history = key in cfg["no_real_history"]

        sleeper_id, sleeper_row, sleeper_resolution = resolve_sleeper_player(
            key,
            pos,
            identity_map,
            sleeper_players,
            sleeper_name_index,
        )

        years_exp = None
        sleeper_team = None
        sleeper_status = None
        depth_chart_order = None
        sleeper_birth_date = None

        if sleeper_row is not None:
            years_exp = integer_or_none(sleeper_row.get("years_exp"))
            sleeper_team = str(sleeper_row.get("team") or "").strip() or None
            sleeper_status = str(sleeper_row.get("status") or "").strip() or None
            depth_chart_order = integer_or_none(
                sleeper_row.get("depth_chart_order")
            )
            sleeper_birth_date = (
                str(sleeper_row.get("birth_date") or "").strip() or None
            )

        draft_row, draft_resolution = resolve_draft_row(
            key,
            pos,
            draft_name_index,
        )
        draft_season = draft_row.get("season") if draft_row else None
        draft_round = draft_row.get("round") if draft_row else None
        draft_pick = draft_row.get("pick") if draft_row else None

        current = phase1_row.get("current") or {}
        current_value = current.get("fundamental_value")
        if current_value is None:
            # Fallback to the exact deployed snapshot math if the Phase-1 compact
            # row ever changes its current-value field name.
            current_values = cfg.get("_current_values") or {}
            current_value = (current_values.get(key) or {}).get("value")

        candidate = phase1_row.get("candidate")
        candidate_present = isinstance(candidate, dict)
        phase1_combined_points = finite_number(
            phase1_row.get("phase1_combined_points")
        )

        if phase1_combined_points is None and isinstance(candidate, dict):
            for field in ("combined_points", "phase1_combined_points"):
                phase1_combined_points = finite_number(candidate.get(field))
                if phase1_combined_points is not None:
                    break

        experience_class = classify_experience(years_exp, draft_season)
        eligible = prospect_prior_eligible(
            no_real_history,
            years_exp,
            draft_season,
        )

        out.append(
            {
                "player": key,
                "pos": pos,
                "age": age,
                "role": role,
                "current_fundamental_value": current_value,
                "no_real_production_history": no_real_history,
                "experience_class": experience_class,
                "prospect_prior_eligible": eligible,
                "production_v2_candidate_present": candidate_present,
                "phase1_combined_points": phase1_combined_points,
                "phase1_candidate_compact": clean_phase1_candidate(candidate),
                "sleeper": {
                    "sleeper_id": sleeper_id,
                    "resolution": sleeper_resolution,
                    "years_exp": years_exp,
                    "team": sleeper_team,
                    "status": sleeper_status,
                    "depth_chart_order": depth_chart_order,
                    "birth_date": sleeper_birth_date,
                },
                "draft": {
                    "resolution": draft_resolution,
                    "season": draft_season,
                    "round": draft_round,
                    "pick": draft_pick,
                    "team": draft_row.get("team") if draft_row else None,
                    "position": draft_row.get("position") if draft_row else None,
                    "category": draft_row.get("category") if draft_row else None,
                    "college": draft_row.get("college") if draft_row else None,
                    "draft_age": draft_row.get("age") if draft_row else None,
                },
            }
        )

    if len(out) < 500:
        raise RuntimeError(f"Coverage audit produced too few tracked players: {len(out)}")

    return out


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    no_history = [r for r in rows if r["no_real_production_history"]]
    eligible = [r for r in rows if r["prospect_prior_eligible"]]
    eligible_missing_candidate = [
        r
        for r in eligible
        if not r["production_v2_candidate_present"]
    ]

    by_position = {}
    for pos in TRACKED_POSITIONS:
        cohort = [r for r in rows if r["pos"] == pos]
        nh = [r for r in cohort if r["no_real_production_history"]]
        pe = [r for r in cohort if r["prospect_prior_eligible"]]
        by_position[pos] = {
            "tracked": len(cohort),
            "no_real_history": len(nh),
            "prospect_prior_eligible": len(pe),
            "eligible_with_v2_candidate": sum(
                1 for r in pe if r["production_v2_candidate_present"]
            ),
            "eligible_missing_v2_candidate": sum(
                1 for r in pe if not r["production_v2_candidate_present"]
            ),
            "eligible_with_sleeper_id": sum(
                1 for r in pe if r["sleeper"]["sleeper_id"]
            ),
            "eligible_with_years_exp": sum(
                1 for r in pe if r["sleeper"]["years_exp"] is not None
            ),
            "eligible_with_draft_pick": sum(
                1 for r in pe if r["draft"]["pick"] is not None
            ),
            "eligible_with_depth_chart_order": sum(
                1 for r in pe
                if r["sleeper"]["depth_chart_order"] is not None
            ),
        }

    experience_counts = Counter(r["experience_class"] for r in no_history)

    return {
        "tracked_players": len(rows),
        "no_real_history_players": len(no_history),
        "prospect_prior_eligible_players": len(eligible),
        "eligible_with_v2_candidate": sum(
            1 for r in eligible if r["production_v2_candidate_present"]
        ),
        "eligible_missing_v2_candidate": len(eligible_missing_candidate),
        "eligible_with_sleeper_id": sum(
            1 for r in eligible if r["sleeper"]["sleeper_id"]
        ),
        "eligible_with_years_exp": sum(
            1 for r in eligible if r["sleeper"]["years_exp"] is not None
        ),
        "eligible_with_draft_pick": sum(
            1 for r in eligible if r["draft"]["pick"] is not None
        ),
        "eligible_with_depth_chart_order": sum(
            1 for r in eligible
            if r["sleeper"]["depth_chart_order"] is not None
        ),
        "no_history_experience_classes": dict(sorted(experience_counts.items())),
        "by_position": by_position,
    }


def build_result(
    session: requests.Session | None = None,
) -> dict[str, Any]:
    snapshot_values = load_snapshot_values_module()
    cfg = snapshot_values.load_from_html(INDEX_HTML)
    cfg["_current_values"] = snapshot_values.compute_all_values(cfg)

    phase1 = read_json(PHASE1_PATH)
    identity_rows = read_json(IDENTITY_PATH)

    sleeper_players = fetch_sleeper_players(session=session)
    draft_rows = fetch_nflverse_draft_rows(session=session)

    rows = build_rows(
        cfg,
        phase1,
        identity_rows,
        sleeper_players,
        draft_rows,
    )
    summary = summarize_rows(rows)

    eligible_rows = [
        row for row in rows if row["prospect_prior_eligible"]
    ]
    eligible_rows.sort(
        key=lambda r: (
            not r["production_v2_candidate_present"],
            r["pos"],
            -(r["draft"]["pick"] is not None),
            r["draft"]["pick"] if r["draft"]["pick"] is not None else 9999,
            r["player"],
        )
    )

    missing_candidate_rows = [
        row
        for row in eligible_rows
        if not row["production_v2_candidate_present"]
    ]

    return {
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": "RESEARCH_ONLY_COVERAGE_AUDIT_NO_VALUE_CHANGES",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "future_formula_authorized": False,
        "scope": {
            "purpose": (
                "Establish reliable rookie/young no-history evidence coverage "
                "before testing any prospect-prior value formula."
            ),
            "prospect_prior_eligibility": (
                "NO_REAL_PRODUCTION_HISTORY and (Sleeper years_exp <= 1 "
                "or nflverse draft season in 2025/2026)."
            ),
            "tracked_positions": list(TRACKED_POSITIONS),
            "production_v2_relationship": (
                "Production V2 remains the forward/history engine. A future "
                "prospect prior may only be tested as an additional research "
                "signal for eligible players."
            ),
        },
        "sources": {
            "deployed_value_source": "index.html",
            "production_v2_phase1": str(PHASE1_PATH.relative_to(REPO_ROOT)),
            "identity_crosswalk": str(IDENTITY_PATH.relative_to(REPO_ROOT)),
            "sleeper_players_url": SLEEPER_PLAYERS_URL,
            "nflverse_draft_url": NFLVERSE_DRAFT_URL,
        },
        "summary": summary,
        "prospect_prior_eligible_players": eligible_rows,
        "eligible_missing_v2_candidate_players": missing_candidate_rows,
    }


def pct(n: int, d: int) -> str:
    if d <= 0:
        return "—"
    return f"{100.0 * n / d:.1f}%"


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    eligible = summary["prospect_prior_eligible_players"]

    lines = [
        "# No-History / Rookie Value V2 — Phase 1 Coverage Audit",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No player value, Production V2 coefficient, Market Value, "
        "or `index.html` production constant is changed by this audit.**",
        "",
        "Production V2 already handles forward/history estimation for most players. "
        "This phase only identifies the young/no-history cohort that could justify "
        "a separate prospect prior later.",
        "",
        "## Coverage summary",
        "",
        f"- Tracked players: **{summary['tracked_players']}**",
        f"- No-real-history players: **{summary['no_real_history_players']}**",
        f"- Prospect-prior eligible: **{eligible}**",
        f"- Eligible with normal Production V2 candidate: "
        f"**{summary['eligible_with_v2_candidate']}**",
        f"- Eligible missing Production V2 candidate: "
        f"**{summary['eligible_missing_v2_candidate']}**",
        f"- Eligible with Sleeper ID: **{summary['eligible_with_sleeper_id']} "
        f"({pct(summary['eligible_with_sleeper_id'], eligible)})**",
        f"- Eligible with years experience: **{summary['eligible_with_years_exp']} "
        f"({pct(summary['eligible_with_years_exp'], eligible)})**",
        f"- Eligible with nflverse draft pick: **{summary['eligible_with_draft_pick']} "
        f"({pct(summary['eligible_with_draft_pick'], eligible)})**",
        f"- Eligible with Sleeper depth-chart order: "
        f"**{summary['eligible_with_depth_chart_order']} "
        f"({pct(summary['eligible_with_depth_chart_order'], eligible)})**",
        "",
        "### No-history experience classes",
        "",
    ]

    for key, value in summary["no_history_experience_classes"].items():
        lines.append(f"- `{key}`: **{value}**")

    lines.extend(
        [
            "",
            "## By position",
            "",
            "| Pos | Tracked | No history | Eligible | V2 candidate | Missing V2 | "
            "Sleeper ID | Draft pick | Depth order |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for pos in TRACKED_POSITIONS:
        row = summary["by_position"][pos]
        lines.append(
            f"| {pos} | {row['tracked']} | {row['no_real_history']} | "
            f"{row['prospect_prior_eligible']} | "
            f"{row['eligible_with_v2_candidate']} | "
            f"{row['eligible_missing_v2_candidate']} | "
            f"{row['eligible_with_sleeper_id']} | "
            f"{row['eligible_with_draft_pick']} | "
            f"{row['eligible_with_depth_chart_order']} |"
        )

    lines.extend(
        [
            "",
            "## Prospect-prior eligible players",
            "",
            "| Player | Pos | Age | Exp | Draft | Pick | Current FV | V2 candidate | "
            "Depth | Sleeper resolution |",
            "|---|---|---:|---|---:|---:|---:|---|---:|---|",
        ]
    )

    for row in result["prospect_prior_eligible_players"]:
        draft = row["draft"]
        sleeper = row["sleeper"]
        lines.append(
            f"| {row['player']} | {row['pos']} | {row['age'] if row['age'] is not None else '—'} | "
            f"{row['experience_class']} | "
            f"{draft['season'] if draft['season'] is not None else '—'} | "
            f"{draft['pick'] if draft['pick'] is not None else '—'} | "
            f"{row['current_fundamental_value'] if row['current_fundamental_value'] is not None else '—'} | "
            f"{'yes' if row['production_v2_candidate_present'] else 'NO'} | "
            f"{sleeper['depth_chart_order'] if sleeper['depth_chart_order'] is not None else '—'} | "
            f"{sleeper['resolution']} |"
        )

    lines.extend(
        [
            "",
            "## Phase 1 decision rule",
            "",
            "Do **not** design the prospect-value blend until this audit shows that the "
            "eligible cohort has enough reliable identity, experience, draft, and "
            "forward-candidate coverage to avoid replacing one coarse fallback with "
            "another.",
            "",
            "If coverage is strong, Phase 2 should test **draft capital + age + "
            "Production V2 forward strength** as a research-only prospect prior. "
            "It should compare multiple blend strengths rather than selecting a "
            "hand-tuned coefficient.",
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
        raise RuntimeError("Phase-1 audit method_version mismatch")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Phase-1 audit lost production-mutation guardrail")
    if result.get("deployment_authorized") is not False:
        raise RuntimeError("Phase-1 audit unexpectedly authorizes deployment")
    if result.get("future_formula_authorized") is not False:
        raise RuntimeError("Phase-1 audit unexpectedly authorizes a formula")

    summary = result.get("summary") or {}
    if int(summary.get("tracked_players") or 0) < 500:
        raise RuntimeError("Phase-1 audit tracked-player count is implausibly low")
    if int(summary.get("no_real_history_players") or 0) <= 0:
        raise RuntimeError("Phase-1 audit found no no-history players")
    if not OUTPUT_MD.exists():
        raise RuntimeError("Phase-1 markdown report is missing")

    markdown = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Coverage summary",
        "Phase 1 decision rule",
    ):
        if marker not in markdown:
            raise RuntimeError(f"Phase-1 markdown missing marker: {marker}")

    print("No-History / Rookie V2 Phase-1 audit outputs passed guardrails.")


def run_selftest() -> None:
    assert normalize_name("Marvin Harrison Jr.") == "marvin harrison"
    assert normalize_name("D'Andre Swift") == "dandre swift"
    assert classify_experience(0, 2026) == "rookie"
    assert classify_experience(1, 2025) == "second_year"
    assert classify_experience(None, 2026) == "rookie_inferred_from_draft"
    assert prospect_prior_eligible(True, 0, None) is True
    assert prospect_prior_eligible(True, 1, None) is True
    assert prospect_prior_eligible(True, 2, 2024) is False
    assert prospect_prior_eligible(False, 0, 2026) is False

    assert compatible_position("QB", "QB", "QB")
    assert compatible_position("DL", "DE", "ED")
    assert compatible_position("LB", "OLB", "ED")
    assert compatible_position("DB", "CB", "DB")
    assert not compatible_position("WR", "RB", "RB")

    identity = [
        {"name": "Player A", "sleeper_id": "1", "requires_manual_review": False},
        {"name": "Player B", "sleeper_id": "2", "requires_manual_review": True},
        {"name": "Player A", "sleeper_id": "1", "requires_manual_review": False},
    ]
    mapping = build_identity_name_map(identity)
    assert mapping["player a"] == "1"
    assert "player b" not in mapping

    print(
        "No-History / Rookie V2 Phase-1 self-test passed: normalization, "
        "eligibility, position compatibility, and identity guardrails."
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

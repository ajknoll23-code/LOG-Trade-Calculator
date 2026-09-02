#!/usr/bin/env python3
"""Build the refreshed Team Utility lineup-projection artifact.

This is a projection-selection data product, NOT a player-value model.

Architecture:
- QB/RB/WR/TE: use Trade Desk's league-scored Sleeper 2026 projection.
- If an offensive player is missing from Sleeper but has a resolved
  FantasyPros identity, use Trade Desk's normalized FantasyPros projection
  as an explicit fallback.
- LB/DL/DB: use the canonical validated IDP V1 category-level ensemble from
  scripts/model/idp_v1_projection.py.
- K: deliberately omitted. The current canonical projection pipelines do not
  model this league's kicker scoring, so Team Utility must keep using
  Fundamental Value to choose among kickers until a real K projection source
  is validated.
- Identity: artifact is keyed by stable Sleeper player_id, never by display
  name.

The output is intended ONLY to decide who occupies starting slots inside Team
Utility. Fundamental Value remains the accounting unit used for lineupDelta,
benchDelta, and the final Team Utility number.

Usage:
  python3 scripts/projections/build_team_utility_lineup_projections.py --selftest
  python3 scripts/projections/build_team_utility_lineup_projections.py --write
  python3 scripts/projections/build_team_utility_lineup_projections.py --check
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent

sys.path.insert(0, str(SCRIPTS_DIR))
from model import idp_v1_projection  # noqa: E402

SEASON = 2026

SLEEPER_TOTALS = SCRIPTS_DIR / "sleeper_2026_projections.json"
SLEEPER_RAW = SCRIPTS_DIR / "artifacts" / "generated" / "sleeper_2026_raw_categories.json"
FP_NORMALIZED = SCRIPTS_DIR / "fantasypros_api_normalized_2026.json"
IDENTITY = SCRIPTS_DIR / "identity_crosswalk.json"
PLAYER_POSITIONS = SCRIPTS_DIR / "artifacts" / "generated" / "player_positions.json"
LEAGUE_ROSTERS = REPO_ROOT / "data" / "league_rosters.json"

OUTPUT = SCRIPTS_DIR / "artifacts" / "generated" / "team_utility_lineup_projections.json"
REPORT = SCRIPTS_DIR / "artifacts" / "reports" / "team_utility_lineup_projection_report.md"

OFFENSE = {"QB", "RB", "WR", "TE"}
IDP = {"DL", "LB", "DB"}

DEDICATED = (
    ("QB", 1),
    ("RB", 2),
    ("WR", 2),
    ("TE", 1),
    ("DL", 2),
    ("LB", 2),
    ("DB", 2),
    ("K", 1),
)
FLEXES = (
    ("FLEX", {"RB", "WR", "TE"}, 1),
    ("SUPER_FLEX", {"QB", "RB", "WR", "TE"}, 1),
    ("IDP_FLEX", {"DL", "LB", "DB"}, 2),
)
EXPECTED_STARTERS = sum(n for _, n in DEDICATED) + sum(n for _, _, n in FLEXES)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_name(value) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_pos(value) -> str | None:
    if not value:
        return None
    raw = str(value).upper()
    mapping = {
        "QB": "QB",
        "RB": "RB",
        "WR": "WR",
        "TE": "TE",
        "K": "K",
        "DL": "DL",
        "DE": "DL",
        "DT": "DL",
        "LB": "LB",
        "OLB": "LB",
        "ILB": "LB",
        "DB": "DB",
        "CB": "DB",
        "S": "DB",
        "SS": "DB",
        "FS": "DB",
    }
    return mapping.get(raw)


def first_valid_pos(*values) -> str | None:
    for value in values:
        if isinstance(value, (list, tuple)):
            for item in value:
                pos = normalize_pos(item)
                if pos:
                    return pos
        else:
            pos = normalize_pos(value)
            if pos:
                return pos
    return None


def finite_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def load_sources():
    required = (
        SLEEPER_TOTALS,
        SLEEPER_RAW,
        FP_NORMALIZED,
        IDENTITY,
        PLAYER_POSITIONS,
        LEAGUE_ROSTERS,
    )
    for path in required:
        if not path.exists():
            raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")

    sleeper_total_rows = read_json(SLEEPER_TOTALS)
    sleeper_raw_rows = read_json(SLEEPER_RAW)
    fp_doc = read_json(FP_NORMALIZED)
    crosswalk = read_json(IDENTITY)
    player_positions = read_json(PLAYER_POSITIONS)
    league_rosters = read_json(LEAGUE_ROSTERS)

    if not isinstance(sleeper_total_rows, list):
        raise RuntimeError("sleeper_2026_projections.json must be a list")
    if not isinstance(sleeper_raw_rows, list):
        raise RuntimeError("sleeper raw categories must be a list")
    if not isinstance(fp_doc, dict) or not isinstance(fp_doc.get("players"), list):
        raise RuntimeError("fantasypros_api_normalized_2026.json missing players list")
    if not isinstance(crosswalk, list):
        raise RuntimeError("identity_crosswalk.json must be a list")
    if not isinstance(player_positions, dict):
        raise RuntimeError("player_positions.json must be an object")
    if not isinstance(league_rosters, dict) or not isinstance(league_rosters.get("rosters"), list):
        raise RuntimeError("league_rosters.json missing rosters list")

    return (
        sleeper_total_rows,
        sleeper_raw_rows,
        fp_doc["players"],
        crosswalk,
        player_positions,
        league_rosters,
    )


def index_by_unique(rows, key_name, label):
    out = {}
    for row in rows:
        raw = row.get(key_name)
        if raw is None:
            continue
        key = str(raw)
        if key in out:
            raise RuntimeError(f"{label}: duplicate {key_name}={key}")
        out[key] = row
    return out


def build_fp_by_sleeper(fp_rows, crosswalk):
    fp_by_id = index_by_unique(fp_rows, "fantasypros_id", "FantasyPros normalized")
    mapped = {}
    method_counts = Counter()
    skipped_manual = 0
    missing_fp_row = 0

    for link in crosswalk:
        sid = link.get("sleeper_id")
        fpid = link.get("fantasypros_id")
        if sid is None or fpid is None:
            continue
        if link.get("requires_manual_review"):
            skipped_manual += 1
            continue

        sid = str(sid)
        fpid = str(fpid)
        fp_row = fp_by_id.get(fpid)
        if fp_row is None:
            missing_fp_row += 1
            continue

        if sid in mapped and str(mapped[sid]["fantasypros_id"]) != fpid:
            raise RuntimeError(
                f"identity crosswalk maps Sleeper {sid} to multiple FantasyPros IDs: "
                f"{mapped[sid]['fantasypros_id']} and {fpid}"
            )

        mapped[sid] = fp_row
        method_counts[str(link.get("match_method") or "unknown")] += 1

    return mapped, {
        "mapped_sleeper_ids": len(mapped),
        "manual_review_rows_skipped": skipped_manual,
        "crosswalk_rows_missing_fp_output": missing_fp_row,
        "match_method_counts": dict(sorted(method_counts.items())),
    }


def choose_position(sid, sleeper_total, sleeper_raw, fp_row, crosswalk_by_sid):
    total = sleeper_total.get(sid) or {}
    raw = sleeper_raw.get(sid) or {}
    fp = fp_row.get(sid) or {}
    link = crosswalk_by_sid.get(sid) or {}

    return first_valid_pos(
        total.get("pos"),
        raw.get("fantasy_positions"),
        raw.get("pos"),
        link.get("sleeper_fantasy_positions"),
        link.get("sleeper_pos"),
        fp.get("source_position"),
    )


def build_artifact():
    (
        sleeper_total_rows,
        sleeper_raw_rows,
        fp_rows,
        crosswalk,
        player_positions,
        league_rosters,
    ) = load_sources()

    sleeper_total = index_by_unique(sleeper_total_rows, "sleeper_id", "Sleeper totals")
    sleeper_raw = index_by_unique(sleeper_raw_rows, "sleeper_id", "Sleeper raw")

    crosswalk_by_sid = {}
    for row in crosswalk:
        sid = row.get("sleeper_id")
        if sid is None or row.get("requires_manual_review"):
            continue
        crosswalk_by_sid.setdefault(str(sid), row)

    fp_by_sleeper, identity_stats = build_fp_by_sleeper(fp_rows, crosswalk)

    source_counts = Counter()
    position_counts = Counter()
    players = {}

    candidate_ids = set(sleeper_total) | set(sleeper_raw) | set(fp_by_sleeper)

    for sid in sorted(candidate_ids, key=lambda x: (len(x), x)):
        total_row = sleeper_total.get(sid) or {}
        raw_row = sleeper_raw.get(sid) or {}
        fp_row = fp_by_sleeper.get(sid) or {}

        pos = choose_position(
            sid,
            sleeper_total,
            sleeper_raw,
            fp_by_sleeper,
            crosswalk_by_sid,
        )
        if pos == "K":
            # Intentional: no canonical kicker projection model yet.
            continue
        if pos not in OFFENSE | IDP:
            continue

        sleeper_total_value = finite_number(total_row.get("sleeper_2026_proj_total"))
        fp_total_value = finite_number(fp_row.get("trade_desk_normalized_points"))

        projection = None
        source = None
        source_detail = {}

        if pos in OFFENSE:
            if sleeper_total_value is not None:
                projection = sleeper_total_value
                source = "sleeper_league_scored"
            elif fp_total_value is not None:
                projection = fp_total_value
                source = "fantasypros_normalized_fallback"
            else:
                continue

        else:
            sleeper_stats = raw_row.get("raw_category_season_totals")
            if not isinstance(sleeper_stats, dict):
                sleeper_stats = None

            fp_stats = fp_row.get("raw_stats_used")
            if not isinstance(fp_stats, dict):
                fp_stats = None

            result = idp_v1_projection.compute_v1_projection(
                fp_stats,
                sleeper_stats,
                old_proj=sleeper_total_value,
            )
            projection = finite_number(result.get("projection"))
            if projection is None:
                continue

            cohort = str(result.get("source_cohort") or "unknown")
            source = f"idp_v1_{cohort}"
            source_detail = {
                "fp_active": bool(result.get("fp_active")),
                "sleeper_active": bool(result.get("sleeper_active")),
                "fp_tackle_active": bool(result.get("fp_tackle_active")),
                "sleeper_tackle_active": bool(result.get("sleeper_tackle_active")),
            }

        if projection is None:
            continue

        name = (
            total_row.get("player")
            or raw_row.get("player")
            or fp_row.get("normalized_name")
            or fp_row.get("name")
            or sid
        )
        team = total_row.get("team") or raw_row.get("team") or fp_row.get("team")
        weeks = total_row.get("weeks_with_projection_data")
        if weeks is None:
            weeks = raw_row.get("weeks_with_projection_data")

        row = {
            "sleeper_id": sid,
            "player": str(name),
            "pos": pos,
            "projection": round(float(projection), 3),
            "source": source,
        }
        if team:
            row["team"] = team
        if isinstance(weeks, int):
            row["weeks_with_projection_data"] = weeks
        if fp_row.get("fantasypros_id") is not None:
            row["fantasypros_id"] = fp_row["fantasypros_id"]
        if source_detail:
            row["source_detail"] = source_detail

        players[sid] = row
        source_counts[source] += 1
        position_counts[pos] += 1

    artifact = {
        "schema_version": 1,
        "season": SEASON,
        "purpose": "Team Utility starter selection only; never Fundamental Value",
        "identity": "stable Sleeper player_id",
        "kicker_policy": (
            "K omitted: canonical projection pipelines do not model this league's "
            "kicker scoring; Team Utility must use Fundamental Value for K selection."
        ),
        "projection_policy": {
            "QB_RB_WR_TE": (
                "Sleeper league-scored 2026 projection; FantasyPros normalized "
                "projection only when Sleeper is unavailable."
            ),
            "DL_LB_DB": (
                "Canonical validated IDP V1 category-level ensemble via "
                "scripts/model/idp_v1_projection.py."
            ),
            "missing_projection": (
                "Missing is missing, never zero; browser must use an explicit fallback."
            ),
        },
        "input_sha256": {
            str(SLEEPER_TOTALS.relative_to(REPO_ROOT)): sha256(SLEEPER_TOTALS),
            str(SLEEPER_RAW.relative_to(REPO_ROOT)): sha256(SLEEPER_RAW),
            str(FP_NORMALIZED.relative_to(REPO_ROOT)): sha256(FP_NORMALIZED),
            str(IDENTITY.relative_to(REPO_ROOT)): sha256(IDENTITY),
        },
        "identity_stats": identity_stats,
        "source_counts": dict(sorted(source_counts.items())),
        "position_counts": dict(sorted(position_counts.items())),
        "player_count": len(players),
        "players": players,
    }

    validation = validate_current_league(
        artifact,
        league_rosters,
        player_positions,
    )
    artifact["current_league_validation"] = validation
    return artifact


@dataclass(frozen=True)
class RosterPlayer:
    sleeper_id: str
    name: str
    pos: str
    projection: float | None


def roster_position(raw, player_positions):
    key = normalize_name(raw.get("name"))
    canonical = normalize_pos(player_positions.get(key))
    if canonical:
        return canonical
    return first_valid_pos(
        raw.get("fantasy_positions"),
        raw.get("position"),
    )


def optimize_projection_lineup(players):
    remaining = list(players)
    starters = []

    def rank_tuple(player):
        # Known projection always beats missing. K is the explicit exception:
        # no canonical K projection exists, so all kickers are equivalent for
        # this coverage validation and a K slot may be filled without one.
        if player.pos == "K":
            return (1, 0.0, player.sleeper_id)
        if player.projection is None:
            return (0, -math.inf, player.sleeper_id)
        return (1, player.projection, player.sleeper_id)

    def pop_best(eligible, label, count):
        nonlocal remaining
        for _ in range(count):
            candidates = [p for p in remaining if p.pos in eligible]
            if not candidates:
                break
            best = max(candidates, key=rank_tuple)
            remaining.remove(best)
            starters.append((label, best))

    for pos, count in DEDICATED:
        pop_best({pos}, pos, count)
    for label, eligible, count in FLEXES:
        pop_best(eligible, label, count)

    return starters, remaining


def validate_current_league(artifact, league_rosters, player_positions):
    projections = {
        sid: finite_number(row.get("projection"))
        for sid, row in artifact["players"].items()
    }

    team_rows = []
    all_active_non_k = 0
    all_active_non_k_projected = 0
    missing_selected = []

    for roster in league_rosters.get("rosters", []):
        active = []
        for slot in ("starters", "bench"):
            for raw in roster.get(slot, []) or []:
                sid = str(raw.get("player_id") or "")
                pos = roster_position(raw, player_positions)
                if not sid or not pos:
                    continue
                active.append(
                    RosterPlayer(
                        sleeper_id=sid,
                        name=str(raw.get("name") or sid),
                        pos=pos,
                        projection=projections.get(sid),
                    )
                )

        non_k = [p for p in active if p.pos != "K"]
        projected_non_k = [p for p in non_k if p.projection is not None]
        all_active_non_k += len(non_k)
        all_active_non_k_projected += len(projected_non_k)

        starters, _ = optimize_projection_lineup(active)
        missing = [
            p
            for _, p in starters
            if p.pos != "K" and p.projection is None
        ]
        for p in missing:
            missing_selected.append(
                {
                    "roster_id": roster.get("roster_id"),
                    "team_name": roster.get("team_name")
                    or roster.get("owner_username"),
                    "sleeper_id": p.sleeper_id,
                    "player": p.name,
                    "pos": p.pos,
                }
            )

        team_rows.append(
            {
                "roster_id": roster.get("roster_id"),
                "team_name": roster.get("team_name")
                or roster.get("owner_username")
                or f"Roster {roster.get('roster_id')}",
                "active_player_count": len(active),
                "active_non_k_count": len(non_k),
                "active_non_k_projection_count": len(projected_non_k),
                "active_non_k_projection_coverage_pct": round(
                    100.0 * len(projected_non_k) / len(non_k), 1
                )
                if non_k
                else 100.0,
                "legal_starter_count": len(starters),
                "selected_non_k_missing_projection_count": len(missing),
            }
        )

    team_rows.sort(key=lambda r: r["roster_id"] or 0)
    return {
        "team_count": len(team_rows),
        "expected_starters_per_team": EXPECTED_STARTERS,
        "teams_with_full_17_slot_lineup": sum(
            1 for r in team_rows if r["legal_starter_count"] == EXPECTED_STARTERS
        ),
        "teams_with_projection_complete_non_k_lineup": sum(
            1
            for r in team_rows
            if r["legal_starter_count"] == EXPECTED_STARTERS
            and r["selected_non_k_missing_projection_count"] == 0
        ),
        "active_non_k_projection_coverage_pct": round(
            100.0 * all_active_non_k_projected / all_active_non_k, 2
        )
        if all_active_non_k
        else 100.0,
        "selected_non_k_missing_projection": missing_selected,
        "teams": team_rows,
    }


def validate_artifact(artifact):
    if artifact.get("schema_version") != 1:
        raise RuntimeError("unexpected Team Utility projection schema version")
    if artifact.get("season") != SEASON:
        raise RuntimeError(f"unexpected season: {artifact.get('season')}")
    players = artifact.get("players")
    if not isinstance(players, dict):
        raise RuntimeError("players must be an object keyed by Sleeper ID")
    if len(players) < 400:
        raise RuntimeError(f"projection artifact unexpectedly small: {len(players)}")

    position_counts = artifact.get("position_counts") or {}
    for pos in ("QB", "RB", "WR", "TE", "DL", "LB", "DB"):
        if int(position_counts.get(pos, 0)) < 10:
            raise RuntimeError(f"projection artifact has implausibly low {pos} coverage")

    for sid, row in players.items():
        if str(row.get("sleeper_id")) != str(sid):
            raise RuntimeError(f"Sleeper ID key/row mismatch: {sid}")
        projection = finite_number(row.get("projection"))
        if projection is None:
            raise RuntimeError(f"non-finite projection: {sid}")
        if row.get("pos") == "K":
            raise RuntimeError("K should not be present in the canonical artifact")

    v = artifact.get("current_league_validation") or {}
    team_count = int(v.get("team_count", 0))
    if team_count < 10:
        raise RuntimeError(f"current league validation saw only {team_count} teams")
    if int(v.get("teams_with_full_17_slot_lineup", 0)) != team_count:
        raise RuntimeError(
            "at least one current roster cannot fill the legal 17-slot lineup"
        )
    if int(v.get("teams_with_projection_complete_non_k_lineup", 0)) != team_count:
        missing = v.get("selected_non_k_missing_projection") or []
        raise RuntimeError(
            "at least one current roster needs a missing non-K projection to "
            f"fill its optimal lineup: {missing[:10]}"
        )
    if float(v.get("active_non_k_projection_coverage_pct", 0)) < 85.0:
        raise RuntimeError(
            "current active non-K projection coverage below 85%: "
            f"{v.get('active_non_k_projection_coverage_pct')}%"
        )

    return {
        "status": "PASS",
        "player_count": len(players),
        "team_count": team_count,
        "active_non_k_projection_coverage_pct": v.get(
            "active_non_k_projection_coverage_pct"
        ),
        "projection_complete_lineup_teams": v.get(
            "teams_with_projection_complete_non_k_lineup"
        ),
    }


def render_report(artifact):
    v = artifact["current_league_validation"]
    lines = [
        "# Team Utility Lineup Projection Artifact",
        "",
        "## Status",
        "",
        "**Generated projection-selection data only. Fundamental Value is unchanged.**",
        "",
        "## Architecture",
        "",
        "- QB/RB/WR/TE: Trade Desk league-scored Sleeper 2026 projections.",
        "- Offensive fallback: normalized FantasyPros projection only when Sleeper is missing.",
        "- DL/LB/DB: canonical validated IDP V1 category-level ensemble.",
        "- Identity: stable Sleeper player ID.",
        "- K: intentionally omitted; Team Utility must use Fundamental Value for the dedicated kicker slot until a validated kicker projection pipeline exists.",
        "- Missing projection is never interpreted as zero.",
        "",
        "## Artifact coverage",
        "",
        f"- Total projected players: **{artifact['player_count']}**",
        f"- Position counts: **{json.dumps(artifact['position_counts'], sort_keys=True)}**",
        f"- Source counts: **{json.dumps(artifact['source_counts'], sort_keys=True)}**",
        "",
        "## Current league validation",
        "",
        f"- Teams checked: **{v['team_count']}**",
        f"- Teams with all 17 legal slots fillable: **{v['teams_with_full_17_slot_lineup']} / {v['team_count']}**",
        f"- Teams with a projection-complete non-K starting lineup: **{v['teams_with_projection_complete_non_k_lineup']} / {v['team_count']}**",
        f"- Active non-K roster projection coverage: **{v['active_non_k_projection_coverage_pct']}%**",
        f"- Selected non-K players needing fallback: **{len(v['selected_non_k_missing_projection'])}**",
        "",
        "## Team detail",
        "",
        "| Team | Active non-K coverage | Legal starters | Missing projected starters |",
        "|---|---:|---:|---:|",
    ]

    for r in v["teams"]:
        lines.append(
            f"| {r['team_name']} | {r['active_non_k_projection_coverage_pct']:.1f}% | "
            f"{r['legal_starter_count']}/{EXPECTED_STARTERS} | "
            f"{r['selected_non_k_missing_projection_count']} |"
        )

    if v["selected_non_k_missing_projection"]:
        lines += ["", "## Missing projections required by a current lineup", ""]
        for row in v["selected_non_k_missing_projection"]:
            lines.append(
                f"- {row['team_name']}: {row['player']} "
                f"({row['pos']}, Sleeper {row['sleeper_id']})"
            )

    lines += [
        "",
        "## Identity / provenance",
        "",
        f"- FantasyPros IDs mapped to Sleeper IDs: **{artifact['identity_stats']['mapped_sleeper_ids']}**",
        f"- Manual-review identity rows skipped: **{artifact['identity_stats']['manual_review_rows_skipped']}**",
        "",
        "The artifact is deterministic: its input file SHA-256 hashes are stored in the JSON, and no wall-clock timestamp is embedded.",
        "",
    ]
    return "\n".join(lines)


def run_selftest():
    # Position normalization.
    assert normalize_pos("DE") == "DL"
    assert normalize_pos("DT") == "DL"
    assert normalize_pos("OLB") == "LB"
    assert normalize_pos("CB") == "DB"
    assert normalize_pos("QB") == "QB"
    assert normalize_pos("P") is None

    # Canonical IDP module itself must remain healthy.
    idp_v1_projection.run_selftest()

    # A synthetic roster with exactly the legal shape should fill all 17 slots.
    synthetic = []
    counter = 0
    for pos, count in (
        ("QB", 2),
        ("RB", 3),
        ("WR", 3),
        ("TE", 2),
        ("K", 1),
        ("DL", 4),
        ("LB", 4),
        ("DB", 4),
    ):
        for i in range(count):
            counter += 1
            synthetic.append(
                RosterPlayer(
                    sleeper_id=str(counter),
                    name=f"{pos}{i}",
                    pos=pos,
                    projection=None if pos == "K" else float(100 - i),
                )
            )
    starters, _ = optimize_projection_lineup(synthetic)
    assert len(starters) == EXPECTED_STARTERS
    assert all(p.projection is not None for _, p in starters if p.pos != "K")

    # Missing projection must rank behind a real zero projection, because
    # missing is unknown, not equivalent to zero.
    a = RosterPlayer("a", "known zero", "WR", 0.0)
    b = RosterPlayer("b", "missing", "WR", None)
    starters, _ = optimize_projection_lineup([a, b])
    assert starters[0][1].sleeper_id == "a"

    print("team_utility_lineup_projection builder self-test passed.")


def write():
    artifact = build_artifact()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(render_report(artifact) + "\n", encoding="utf-8")
    result = validate_artifact(artifact)
    print(json.dumps(result, indent=2))
    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)}")
    print(f"Wrote {REPORT.relative_to(REPO_ROOT)}")


def check():
    if not OUTPUT.exists():
        raise RuntimeError(f"missing generated artifact: {OUTPUT.relative_to(REPO_ROOT)}")
    stored = read_json(OUTPUT)
    result = validate_artifact(stored)

    rebuilt = build_artifact()
    if stored != rebuilt:
        raise RuntimeError(
            "team_utility_lineup_projections.json is stale relative to its "
            "committed projection/identity inputs; rebuild it"
        )

    print(json.dumps(result, indent=2))
    print("PASS Team Utility lineup projection artifact is current and valid.")


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--selftest", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
    elif args.write:
        write()
    else:
        check()


if __name__ == "__main__":
    main()

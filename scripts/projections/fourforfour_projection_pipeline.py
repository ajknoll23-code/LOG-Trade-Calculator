#!/usr/bin/env python3
"""
Research-only 4for4 IDP projection ingestion/audit pipeline.

Purpose
-------
Ingest three user-downloaded 4for4 2026 IDP CSV exports (DL/LB/DB), validate
schema and stat semantics, resolve each row to the project's canonical Sleeper
identity, and score the raw projection categories under this league's own IDP
scoring rules.

This is intentionally NOT a production model/deployment pipeline.

Privacy / licensing guard
-------------------------
The LOG-Trade-Calculator repository is public, while 4for4's terms restrict
reproduction/redistribution of its content/output. Therefore this script:
  * refuses, by default, to read 4for4 CSVs stored inside the repository;
  * refuses, by default, to write detailed row-level output inside the repo;
  * writes only to a user-selected private/local output directory;
  * provides a separate aggregate-only public summary that contains no
    row-level 4for4 projections.

No 4for4 CSV or normalized row-level projection should be committed to the
public repository without explicit permission from the data provider.

Stat semantics
--------------
The 2026 4for4 IDP projection table exposes separate `Tackles` and `Assists`
columns, and 4for4's 2026 IDP methodology discusses tackles and assists as
separate modeled categories. This pipeline therefore maps:
    Tackles -> solo tackles
    Assists -> assisted tackles

Scoring coverage
----------------
Season-total 4for4 exports cannot reconstruct this league's per-game IDP
milestone bonuses (10+ combined tackles, 2+ sacks, 3+ passes defended), and the
export does not expose blocked kicks. The pipeline scores every available raw
category exactly and flags those structural omissions. It never applies a
per-game threshold to a season total.

Usage
-----
  python3 scripts/projections/fourforfour_projection_pipeline.py --selftest

  python3 scripts/projections/fourforfour_projection_pipeline.py \
      --dl /private/path/4for4-dl.csv \
      --lb /private/path/4for4-lb.csv \
      --db /private/path/4for4-db.csv \
      --output-dir ~/.local/share/log-trade-calculator/4for4-idp-v1

Optional aggregate-only summary safe for a public repo:
  --public-summary /path/to/aggregate_summary.json

The detailed output directory receives:
  fourforfour_2026_idp_normalized_private.json
  fourforfour_2026_idp_identity_audit_private.json
  fourforfour_2026_idp_audit_private.md

None of those detailed files should be committed to the public repository.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import sys
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
# Installed path: <repo>/scripts/projections/fourforfour_projection_pipeline.py
REPO_ROOT = SCRIPT_PATH.parents[2]
SEASON = 2026
PIPELINE_VERSION = "fourforfour-idp-v1-phase1"
SEMANTICS_VERSION = "4for4-2026-tackles-as-solo-v1"

EXPECTED_COLUMNS = (
    "Player",
    "Team",
    "Bye",
    "Position",
    "FF Pts",
    "Snap %",
    "Tackles",
    "Assists",
    "Sacks",
    "TFL",
    "QBH",
    "INT",
    "PD",
    "FFum",
    "FR",
    "Safety",
    "DefTD",
)

NUMERIC_COLUMNS = (
    "FF Pts",
    "Snap %",
    "Tackles",
    "Assists",
    "Sacks",
    "TFL",
    "QBH",
    "INT",
    "PD",
    "FFum",
    "FR",
    "Safety",
    "DefTD",
)

# Provider position -> Trade Desk/Sleeper bucket.
POSITION_BUCKET = {
    "DE": "DL",
    "DT": "DL",
    "NT": "DL",
    "DL": "DL",
    "LB": "LB",
    "ILB": "LB",
    "MLB": "LB",
    "OLB": "LB",
    "DB": "DB",
    "CB": "DB",
    "S": "DB",
    "SS": "DB",
    "FS": "DB",
    # EDGE can legitimately resolve to Sleeper DL or LB eligibility.
    "EDGE": "EDGE",
}

# Common provider/team aliases. The existing FantasyPros/Sleeper resolver also
# carries JAC -> JAX; the historical aliases below are harmless compatibility
# guards for stale exports and never override a contradictory current team.
TEAM_ALIASES = {
    "JAC": "JAX",
    "WSH": "WAS",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
}

MISSING_SCORING_CATEGORIES = (
    "blk_kick",
    "weekly_idp_milestone_bonuses",
)

DETAIL_NORMALIZED_NAME = "fourforfour_2026_idp_normalized_private.json"
DETAIL_AUDIT_NAME = "fourforfour_2026_idp_identity_audit_private.json"
DETAIL_REPORT_NAME = "fourforfour_2026_idp_audit_private.md"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_bytes(payload.encode("utf-8"))


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def normalize_team(value: Any) -> str | None:
    if value in (None, ""):
        return None
    team = str(value).strip().upper()
    if not team or team == "FA":
        return None
    return TEAM_ALIASES.get(team, team)


def normalize_name(value: Any) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_position(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return POSITION_BUCKET.get(str(value).strip().upper())


def parse_finite_number(value: Any, *, field: str, row_number: int, path: Path) -> float:
    text = str(value if value is not None else "").strip()
    if field == "Snap %" and text.endswith("%"):
        text = text[:-1].strip()
    if text == "":
        raise RuntimeError(f"{path.name}: row {row_number}: blank numeric field {field!r}")
    try:
        x = float(text)
    except ValueError as exc:
        raise RuntimeError(
            f"{path.name}: row {row_number}: malformed numeric field {field!r}={value!r}"
        ) from exc
    if not math.isfinite(x):
        raise RuntimeError(f"{path.name}: row {row_number}: non-finite {field!r}={value!r}")
    return x


def score_idp_season_base(stats: dict[str, float]) -> float:
    """Score all 4for4-exported IDP categories under the league's exact rates.

    Deliberately excludes per-game threshold bonuses because these are season
    totals, not weekly projections. Also cannot score blocked kicks because the
    4for4 export does not expose them.
    """
    return (
        stats["idp_tkl_solo"] * 1.5
        + stats["idp_tkl_ast"] * 0.75
        + stats["idp_sack"] * 3.0
        + stats["idp_tkl_loss"] * 2.0
        + stats["idp_qb_hit"] * 2.0
        + stats["idp_int"] * 6.0
        + stats["idp_pass_def"] * 3.0
        + stats["idp_ff"] * 3.0
        + stats["idp_fum_rec"] * 4.0
        + stats["idp_safety"] * 3.0
        + stats["idp_td"] * 6.0
    )


def row_to_stats(numeric: dict[str, float]) -> dict[str, float]:
    # 4for4 `Tackles` is mapped to SOLO tackles; `Assists` is separate.
    return {
        "idp_tkl_solo": numeric["Tackles"],
        "idp_tkl_ast": numeric["Assists"],
        "idp_sack": numeric["Sacks"],
        "idp_tkl_loss": numeric["TFL"],
        "idp_qb_hit": numeric["QBH"],
        "idp_int": numeric["INT"],
        "idp_pass_def": numeric["PD"],
        "idp_ff": numeric["FFum"],
        "idp_fum_rec": numeric["FR"],
        "idp_safety": numeric["Safety"],
        "idp_td": numeric["DefTD"],
    }


def validate_bucket_position(source_bucket: str, canonical_position: str, raw_position: str, path: Path, row_number: int) -> None:
    if source_bucket == "DL" and canonical_position not in {"DL", "EDGE"}:
        raise RuntimeError(
            f"{path.name}: row {row_number}: DL export contains incompatible Position={raw_position!r}"
        )
    if source_bucket == "LB" and canonical_position not in {"LB", "EDGE"}:
        raise RuntimeError(
            f"{path.name}: row {row_number}: LB export contains incompatible Position={raw_position!r}"
        )
    if source_bucket == "DB" and canonical_position != "DB":
        raise RuntimeError(
            f"{path.name}: row {row_number}: DB export contains incompatible Position={raw_position!r}"
        )


def load_csv(path: Path, source_bucket: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_bytes = path.read_bytes()
    text = raw_bytes.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    headers = tuple(reader.fieldnames or ())
    missing = [c for c in EXPECTED_COLUMNS if c not in headers]
    if missing:
        raise RuntimeError(f"{path.name}: missing expected columns: {missing}; got={list(headers)}")

    rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(reader, start=2):
        player = str(row.get("Player") or "").strip()
        team = normalize_team(row.get("Team"))
        raw_position = str(row.get("Position") or "").strip().upper()
        canonical_position = normalize_position(raw_position)
        if not player:
            raise RuntimeError(f"{path.name}: row {row_number}: blank Player")
        if canonical_position is None:
            raise RuntimeError(
                f"{path.name}: row {row_number}: unsupported Position={raw_position!r}"
            )
        validate_bucket_position(source_bucket, canonical_position, raw_position, path, row_number)

        numeric = {
            field: parse_finite_number(row.get(field), field=field, row_number=row_number, path=path)
            for field in NUMERIC_COLUMNS
        }
        if not (0 <= numeric["Snap %"] <= 100):
            raise RuntimeError(
                f"{path.name}: row {row_number}: Snap % out of range: {numeric['Snap %']}"
            )
        for field in NUMERIC_COLUMNS:
            if field not in {"FF Pts", "Snap %"} and numeric[field] < 0:
                raise RuntimeError(
                    f"{path.name}: row {row_number}: negative defensive projection {field}={numeric[field]}"
                )

        stats = row_to_stats(numeric)
        base_points = score_idp_season_base(stats)
        source_identity = {
            "player": player,
            "team": team,
            "position": raw_position,
            "source_bucket": source_bucket,
            "stats": stats,
            "snap_pct": numeric["Snap %"],
            "provider_ff_pts": numeric["FF Pts"],
        }
        rows.append({
            "source_bucket": source_bucket,
            "source_row_number": row_number,
            "source_file": path.name,
            "source_file_sha256": sha256_bytes(raw_bytes),
            "source_row_sha256": canonical_json_hash(source_identity),
            "player": player,
            "normalized_name": normalize_name(player),
            "team": team,
            "source_position": raw_position,
            "canonical_position": canonical_position,
            "provider_ff_pts": numeric["FF Pts"],
            "snap_pct": numeric["Snap %"],
            "raw_stats": stats,
            "log_base_points": round(base_points, 6),
            "missing_scoring_categories": list(MISSING_SCORING_CATEGORIES),
        })

    meta = {
        "source_bucket": source_bucket,
        "file_name": path.name,
        "sha256": sha256_bytes(raw_bytes),
        "row_count": len(rows),
        "headers": list(headers),
    }
    return rows, meta


def load_existing_resolver_module():
    resolver_path = REPO_ROOT / "scripts" / "projections" / "resolve_fantasypros_sleeper_identity.py"
    if not resolver_path.exists():
        raise RuntimeError(f"missing existing identity resolver: {resolver_path}")
    spec = importlib.util.spec_from_file_location("trade_desk_identity_resolver", resolver_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load identity resolver: {resolver_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"missing required repo input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_identity_context() -> dict[str, Any]:
    resolver = load_existing_resolver_module()
    total_rows = read_json(REPO_ROOT / "scripts" / "sleeper_2026_projections.json")
    raw_rows = read_json(
        REPO_ROOT / "scripts" / "artifacts" / "generated" / "sleeper_2026_raw_categories.json"
    )
    team_refresh_path = REPO_ROOT / "scripts" / "artifacts" / "generated" / "player_team_refresh.json"
    team_refresh = read_json(team_refresh_path) if team_refresh_path.exists() else {}
    crosswalk = read_json(REPO_ROOT / "scripts" / "identity_crosswalk.json")

    sleeper_by_sid, sleeper_by_name = resolver.build_sleeper_universe(
        total_rows, raw_rows, team_refresh
    )
    return {
        "resolver": resolver,
        "sleeper_by_sid": sleeper_by_sid,
        "sleeper_by_name": sleeper_by_name,
        "crosswalk": crosswalk,
    }


def row_position_compatible(canonical_position: str, sleeper_row: dict[str, Any]) -> bool:
    labels = set(sleeper_row.get("positions") or ())
    if canonical_position == "EDGE":
        return bool(labels & {"DL", "LB", "EDGE"})
    return canonical_position in labels or (canonical_position in {"DL", "LB"} and "EDGE" in labels)


def crosswalk_position_compatible(canonical_position: str, cw: dict[str, Any]) -> bool:
    fp_pos = str(cw.get("fp_position") or "").upper()
    sleeper_positions = set(cw.get("sleeper_fantasy_positions") or [])
    sleeper_pos = str(cw.get("sleeper_pos") or "").upper()
    labels = {fp_pos, sleeper_pos, *sleeper_positions}
    if canonical_position == "EDGE":
        return bool(labels & {"DL", "LB", "EDGE", "DE", "OLB"})
    return canonical_position in labels


def candidate_public_view(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "sleeper_id": candidate.get("sleeper_id"),
        "player": candidate.get("player"),
        "team": candidate.get("team"),
        "positions": sorted(candidate.get("positions") or ()),
        "has_projection_signal": bool(candidate.get("has_projection_signal")),
    }


def resolve_identity(row: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    resolver = context["resolver"]
    sleeper_by_sid = context["sleeper_by_sid"]
    sleeper_by_name = context["sleeper_by_name"]
    crosswalk = context["crosswalk"]

    name = row["normalized_name"]
    team = row["team"]
    canonical_position = row["canonical_position"]

    name_candidates = list(sleeper_by_name.get(name, ()))
    position_candidates = [c for c in name_candidates if row_position_compatible(canonical_position, c)]
    team_candidates = [
        c for c in position_candidates
        if team and normalize_team(c.get("team")) == team
    ]

    result = {
        "resolved": False,
        "sleeper_id": None,
        "sleeper_team": None,
        "sleeper_positions": None,
        "sleeper_has_projection_signal": None,
        "match_method": None,
        "match_confidence": "none",
        "requires_manual_review": True,
        "name_candidate_count": len(name_candidates),
        "position_candidate_count": len(position_candidates),
        "team_position_candidate_count": len(team_candidates),
        "crosswalk_corroborated": False,
        "candidate_sleeper_ids": sorted({str(c.get("sleeper_id")) for c in position_candidates}),
    }

    def assign(candidate: dict[str, Any], method: str, *, crosswalk_corroborated: bool) -> dict[str, Any]:
        out = dict(result)
        out.update({
            "resolved": True,
            "sleeper_id": str(candidate["sleeper_id"]),
            "sleeper_team": candidate.get("team"),
            "sleeper_positions": sorted(candidate.get("positions") or ()),
            "sleeper_has_projection_signal": bool(candidate.get("has_projection_signal")),
            "match_method": method,
            "match_confidence": "high",
            "requires_manual_review": False,
            "crosswalk_corroborated": crosswalk_corroborated,
        })
        return out

    # First choice: strict current name + compatible position + current team.
    if len(team_candidates) == 1:
        candidate = team_candidates[0]
        sid = str(candidate["sleeper_id"])
        corroborating = [
            cw for cw in crosswalk
            if cw.get("sleeper_id") not in (None, "")
            and str(cw.get("sleeper_id")) == sid
            and crosswalk_position_compatible(canonical_position, cw)
        ]
        # A same-name/team/position authoritative crosswalk pointing to a
        # different SID is a hard contradiction, not something to guess past.
        contradictions = [
            cw for cw in crosswalk
            if cw.get("sleeper_id") not in (None, "")
            and resolver.stable_authoritative_name_equivalent(row["player"], cw.get("name"))
            and normalize_team(cw.get("sleeper_team") or cw.get("fp_team")) == team
            and crosswalk_position_compatible(canonical_position, cw)
            and str(cw.get("sleeper_id")) != sid
        ]
        if contradictions:
            raise RuntimeError(
                f"authoritative identity contradiction for {row['player']} {team} "
                f"{row['source_position']}: direct Sleeper={sid}, crosswalk="
                f"{sorted({str(c['sleeper_id']) for c in contradictions})}"
            )
        method = (
            "name_position_team_confirmed_crosswalk_corroborated"
            if corroborating
            else "name_position_team_confirmed"
        )
        return assign(candidate, method, crosswalk_corroborated=bool(corroborating))

    if len(team_candidates) > 1:
        result["match_method"] = "multiple_name_position_team_candidates"
        return result

    # Second choice: existing authoritative crosswalk can bridge harmless
    # provider display-name suffix differences, but it must independently match
    # team + compatible position and resolve to the same person in Sleeper.
    cw_candidates = []
    for cw in crosswalk:
        sid = cw.get("sleeper_id")
        if sid in (None, ""):
            continue
        if not resolver.stable_authoritative_name_equivalent(row["player"], cw.get("name")):
            continue
        if team and normalize_team(cw.get("sleeper_team") or cw.get("fp_team")) != team:
            continue
        if not crosswalk_position_compatible(canonical_position, cw):
            continue
        sleeper_candidate = sleeper_by_sid.get(str(sid))
        if not sleeper_candidate:
            continue
        if not resolver.stable_authoritative_name_equivalent(row["player"], sleeper_candidate.get("player")):
            continue
        if not row_position_compatible(canonical_position, sleeper_candidate):
            continue
        cw_candidates.append(sleeper_candidate)

    unique_cw = {str(c["sleeper_id"]): c for c in cw_candidates}
    if len(unique_cw) == 1:
        candidate = next(iter(unique_cw.values()))
        return assign(
            candidate,
            "existing_authoritative_crosswalk_name_team_position",
            crosswalk_corroborated=True,
        )
    if len(unique_cw) > 1:
        result["match_method"] = "multiple_authoritative_crosswalk_candidates"
        result["candidate_sleeper_ids"] = sorted(unique_cw)
        return result

    if not name_candidates:
        result["match_method"] = "no_sleeper_name_candidate"
    elif not position_candidates:
        result["match_method"] = "name_found_position_incompatible"
    elif len(position_candidates) == 1:
        candidate = position_candidates[0]
        result["candidate_sleeper_ids"] = [str(candidate["sleeper_id"])]
        if team and candidate.get("team"):
            result["match_method"] = "unique_name_position_team_mismatch"
        else:
            result["match_method"] = "unique_name_position_team_unavailable"
    else:
        result["match_method"] = "unresolved_name_position_collision"
    return result


def collapse_exact_same_sid_duplicates(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collapse exact duplicate provider rows that resolve to the same Sleeper ID.

    Divergent rows for the same Sleeper ID are retained and reported as a hard
    identity/data collision in the audit; this function never chooses between
    conflicting provider rows.
    """
    by_sid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unresolved: list[dict[str, Any]] = []
    for row in rows:
        sid = row["identity"].get("sleeper_id")
        if sid:
            by_sid[str(sid)].append(row)
        else:
            unresolved.append(row)

    collapsed: list[dict[str, Any]] = []
    collisions: list[dict[str, Any]] = []
    for sid, group in by_sid.items():
        if len(group) == 1:
            collapsed.append(group[0])
            continue

        signatures = {
            canonical_json_hash({
                "team": r["team"],
                "canonical_position": r["canonical_position"],
                "provider_ff_pts": r["provider_ff_pts"],
                "snap_pct": r["snap_pct"],
                "raw_stats": r["raw_stats"],
            })
            for r in group
        }
        if len(signatures) == 1:
            keeper = dict(group[0])
            keeper["duplicate_source_rows_collapsed"] = [
                {
                    "source_bucket": r["source_bucket"],
                    "source_file": r["source_file"],
                    "source_row_number": r["source_row_number"],
                    "source_row_sha256": r["source_row_sha256"],
                }
                for r in group[1:]
            ]
            collapsed.append(keeper)
        else:
            collisions.append({
                "sleeper_id": sid,
                "players": sorted({r["player"] for r in group}),
                "rows": [
                    {
                        "source_bucket": r["source_bucket"],
                        "source_file": r["source_file"],
                        "source_row_number": r["source_row_number"],
                        "source_row_sha256": r["source_row_sha256"],
                    }
                    for r in group
                ],
            })
            # Keep all rows in the detailed audit but do not place any of them
            # into the clean normalized resolved set.
            unresolved.extend(group)

    return collapsed + unresolved, collisions


def make_normalized_row(row: dict[str, Any]) -> dict[str, Any]:
    identity = row["identity"]
    return {
        "provider": "4for4",
        "season": SEASON,
        "pipeline_version": PIPELINE_VERSION,
        "semantics_version": SEMANTICS_VERSION,
        "source_bucket": row["source_bucket"],
        "source_file": row["source_file"],
        "source_file_sha256": row["source_file_sha256"],
        "source_row_number": row["source_row_number"],
        "source_row_sha256": row["source_row_sha256"],
        "source_player_name": row["player"],
        "source_team": row["team"],
        "source_position": row["source_position"],
        "canonical_position": row["canonical_position"],
        "sleeper_id": identity.get("sleeper_id"),
        "identity": identity,
        "snap_pct": row["snap_pct"],
        "provider_ff_pts_reference_only": row["provider_ff_pts"],
        "raw_category_season_totals": row["raw_stats"],
        "log_base_points_excluding_weekly_bonuses_and_blocked_kicks": row["log_base_points"],
        "missing_scoring_categories": list(MISSING_SCORING_CATEGORIES),
        "production_authorized": False,
    }


def aggregate_summary(all_rows: list[dict[str, Any]], file_meta: list[dict[str, Any]], collisions: list[dict[str, Any]]) -> dict[str, Any]:
    resolved_rows = [r for r in all_rows if r["identity"].get("resolved")]
    unresolved_rows = [r for r in all_rows if not r["identity"].get("resolved")]
    duplicate_names = Counter(r["normalized_name"] for r in all_rows)
    duplicated_name_count = sum(1 for count in duplicate_names.values() if count > 1)
    method_counts = Counter(r["identity"].get("match_method") for r in all_rows)
    bucket_counts = Counter(r["source_bucket"] for r in all_rows)
    resolved_bucket_counts = Counter(r["source_bucket"] for r in resolved_rows)

    points = [r["log_base_points"] for r in resolved_rows]
    # Aggregate distribution only; no individual player projection is exposed.
    points_summary = None
    if points:
        points_summary = {
            "count": len(points),
            "mean": round(statistics.mean(points), 6),
            "median": round(statistics.median(points), 6),
            "min": round(min(points), 6),
            "max": round(max(points), 6),
        }

    return {
        "schema_version": 1,
        "pipeline_version": PIPELINE_VERSION,
        "season": SEASON,
        "status": "phase1_audit_complete" if not collisions else "phase1_audit_has_same_identity_collisions",
        "research_only": True,
        "production_changes": False,
        "source_distribution_restricted": True,
        "row_level_provider_data_written_to_public_repo": False,
        "semantics": {
            "tackles_field": "solo_tackles",
            "assists_field": "assisted_tackles",
            "semantics_version": SEMANTICS_VERSION,
            "season_total_scoring_excludes_weekly_threshold_bonuses": True,
            "missing_scoring_categories": list(MISSING_SCORING_CATEGORIES),
        },
        "inputs": {
            "files": [
                {
                    "source_bucket": m["source_bucket"],
                    "sha256": m["sha256"],
                    "row_count": m["row_count"],
                    "schema_exact_required_columns_present": True,
                }
                for m in file_meta
            ],
            "total_rows": len(all_rows),
            "rows_by_bucket": dict(sorted(bucket_counts.items())),
        },
        "identity": {
            "resolved_rows": len(resolved_rows),
            "unresolved_rows": len(unresolved_rows),
            "resolved_rate": round(len(resolved_rows) / len(all_rows), 6) if all_rows else 0.0,
            "resolved_by_bucket": dict(sorted(resolved_bucket_counts.items())),
            "match_method_counts": dict(sorted(method_counts.items(), key=lambda kv: str(kv[0]))),
            "duplicate_normalized_name_groups": duplicated_name_count,
            "same_sleeper_id_divergent_row_collisions": len(collisions),
        },
        "log_base_points_aggregate_only": points_summary,
    }


def build_private_audit(all_rows: list[dict[str, Any]], file_meta: list[dict[str, Any]], collisions: list[dict[str, Any]]) -> dict[str, Any]:
    unresolved = []
    for row in all_rows:
        if row["identity"].get("resolved"):
            continue
        unresolved.append({
            "player": row["player"],
            "team": row["team"],
            "source_position": row["source_position"],
            "source_bucket": row["source_bucket"],
            "source_file": row["source_file"],
            "source_row_number": row["source_row_number"],
            "source_row_sha256": row["source_row_sha256"],
            "identity": row["identity"],
        })

    duplicate_name_groups = []
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        by_name[row["normalized_name"]].append(row)
    for name, group in sorted(by_name.items()):
        if len(group) <= 1:
            continue
        duplicate_name_groups.append({
            "normalized_name": name,
            "rows": [
                {
                    "player": r["player"],
                    "team": r["team"],
                    "source_position": r["source_position"],
                    "source_bucket": r["source_bucket"],
                    "sleeper_id": r["identity"].get("sleeper_id"),
                    "match_method": r["identity"].get("match_method"),
                }
                for r in group
            ],
        })

    return {
        "schema_version": 1,
        "pipeline_version": PIPELINE_VERSION,
        "research_only": True,
        "production_authorized": False,
        "semantics_version": SEMANTICS_VERSION,
        "source_files": file_meta,
        "unresolved_rows": unresolved,
        "duplicate_name_groups": duplicate_name_groups,
        "same_sleeper_id_divergent_row_collisions": collisions,
    }


def render_private_report(summary: dict[str, Any], audit: dict[str, Any]) -> str:
    ident = summary["identity"]
    lines = [
        "# 4for4 IDP V1 — Phase 1 Private Audit",
        "",
        "**Research only. No Fundamental Value or production values are changed.**",
        "",
        "This report contains provider-derived row-level identity diagnostics and is",
        "intended to remain private/local. Do not commit it to the public repository.",
        "",
        "## Input / schema",
        "",
    ]
    for f in summary["inputs"]["files"]:
        lines.append(f"- {f['source_bucket']}: {f['row_count']} rows; SHA-256 `{f['sha256']}`")
    lines.extend([
        "",
        f"Total rows: **{summary['inputs']['total_rows']}**",
        "",
        "## Stat semantics / scoring",
        "",
        "- `Tackles` -> solo tackles",
        "- `Assists` -> assisted tackles",
        "- Provider `FF Pts` is reference-only and never used as Trade Desk scoring input",
        "- Available raw categories are rescored under league rates",
        "- Weekly 10+ tackle / 2+ sack / 3+ PD bonuses are not reconstructible from season totals",
        "- Blocked kicks are absent from the export",
        "",
        "## Identity coverage",
        "",
        f"Resolved: **{ident['resolved_rows']} / {summary['inputs']['total_rows']}** "
        f"({ident['resolved_rate']:.2%})",
        f"Unresolved: **{ident['unresolved_rows']}**",
        f"Duplicate-name groups: **{ident['duplicate_normalized_name_groups']}**",
        f"Divergent rows resolving to the same Sleeper ID: **{ident['same_sleeper_id_divergent_row_collisions']}**",
        "",
        "### Match methods",
        "",
    ])
    for method, count in ident["match_method_counts"].items():
        lines.append(f"- `{method}`: {count}")

    lines.extend(["", "## Unresolved rows", ""])
    if not audit["unresolved_rows"]:
        lines.append("None.")
    else:
        for r in audit["unresolved_rows"]:
            lines.append(
                f"- {r['player']} ({r['team'] or 'FA'}, {r['source_position']}, {r['source_bucket']}): "
                f"`{r['identity'].get('match_method')}` candidates={r['identity'].get('candidate_sleeper_ids')}"
            )

    lines.extend(["", "## Duplicate provider names", ""])
    if not audit["duplicate_name_groups"]:
        lines.append("None.")
    else:
        for g in audit["duplicate_name_groups"]:
            parts = []
            for r in g["rows"]:
                parts.append(
                    f"{r['team'] or 'FA'}/{r['source_position']} -> {r['sleeper_id'] or 'UNRESOLVED'}"
                )
            lines.append(f"- `{g['normalized_name']}`: " + "; ".join(parts))

    lines.extend(["", "## Same-Sleeper-ID divergent row collisions", ""])
    if not audit["same_sleeper_id_divergent_row_collisions"]:
        lines.append("None.")
    else:
        for c in audit["same_sleeper_id_divergent_row_collisions"]:
            lines.append(f"- Sleeper `{c['sleeper_id']}`: {len(c['rows'])} divergent provider rows")

    lines.extend([
        "",
        "## Production isolation",
        "",
        "- Fundamental Value changed: **No**",
        "- PROD_MULT changed: **No**",
        "- Team Utility changed: **No**",
        "- Package Adjustment changed: **No**",
        "- This pipeline only creates private research artifacts plus an optional aggregate-only summary.",
        "",
    ])
    return "\n".join(lines)


def enforce_private_paths(input_paths: list[Path], output_dir: Path, *, allow_repo_private_input: bool) -> None:
    repo = REPO_ROOT.resolve()
    for path in input_paths:
        rp = path.resolve()
        if is_relative_to(rp, repo):
            # Narrow escape hatch for an explicitly private/ignored working area.
            rel = rp.relative_to(repo)
            has_private_component = any(part.startswith(".private") for part in rel.parts)
            if not (allow_repo_private_input and has_private_component):
                raise RuntimeError(
                    f"refusing to read provider CSV from public repo tree: {rel}. "
                    "Keep paid 4for4 exports outside the repo. If you intentionally use a "
                    "gitignored .private* directory, pass --allow-repo-private-input."
                )

    out = output_dir.resolve()
    if is_relative_to(out, repo):
        raise RuntimeError(
            f"refusing to write detailed provider-derived output inside public repo: "
            f"{out.relative_to(repo)}. Choose a private/local --output-dir outside the repo."
        )


def run_selftest() -> None:
    print("Running 4for4 IDP V1 Phase 1 self-test...")

    # Exact scoring-rate regression. No weekly threshold bonus is added.
    stats = {
        "idp_tkl_solo": 80.0,
        "idp_tkl_ast": 40.0,
        "idp_sack": 5.0,
        "idp_tkl_loss": 10.0,
        "idp_qb_hit": 8.0,
        "idp_int": 2.0,
        "idp_pass_def": 6.0,
        "idp_ff": 2.0,
        "idp_fum_rec": 1.0,
        "idp_safety": 0.0,
        "idp_td": 1.0,
    }
    expected = 80*1.5 + 40*.75 + 5*3 + 10*2 + 8*2 + 2*6 + 6*3 + 2*3 + 1*4 + 1*6
    actual = score_idp_season_base(stats)
    assert abs(actual - expected) < 1e-9, (actual, expected)
    assert actual == 247.0
    print("  scoring rates + season-total no-threshold-bonus rule: OK")

    # Tackles semantics regression: mapping is explicitly solo, not combined.
    numeric = {
        "Tackles": 90.0, "Assists": 70.0, "Sacks": 0.0, "TFL": 0.0,
        "QBH": 0.0, "INT": 0.0, "PD": 0.0, "FFum": 0.0, "FR": 0.0,
        "Safety": 0.0, "DefTD": 0.0,
    }
    mapped = row_to_stats(numeric)
    assert mapped["idp_tkl_solo"] == 90.0
    assert mapped["idp_tkl_ast"] == 70.0
    print("  Tackles->solo / Assists->assisted semantics: OK")

    class ResolverStub:
        @staticmethod
        def stable_authoritative_name_equivalent(a, b):
            def split(value):
                n = normalize_name(value)
                p = n.split()
                if p and p[-1] in {"jr", "sr", "ii", "iii", "iv", "v"}:
                    return " ".join(p[:-1]), p[-1]
                return n, None
            aa, asuf = split(a)
            bb, bsuf = split(b)
            if normalize_name(a) == normalize_name(b):
                return True
            if aa != bb:
                return False
            if asuf and bsuf:
                return asuf == bsuf
            return bool(asuf or bsuf)

    # Synthetic duplicate-name universe: distinct players must resolve by
    # name + compatible position + team, not name alone.
    by_sid = {
        "10917": {"sleeper_id":"10917", "player":"byron young", "team":"LAR", "positions":{"DL","LB"}, "has_projection_signal":True},
        "10925": {"sleeper_id":"10925", "player":"byron young", "team":"PHI", "positions":{"DL"}, "has_projection_signal":True},
        "11052": {"sleeper_id":"11052", "player":"jaylon jones", "team":"IND", "positions":{"DB"}, "has_projection_signal":True},
        "8702": {"sleeper_id":"8702", "player":"jaylon jones", "team":"CHI", "positions":{"DB"}, "has_projection_signal":True},
        "1": {"sleeper_id":"1", "player":"ernest jones", "team":"SEA", "positions":{"LB"}, "has_projection_signal":True},
    }
    by_name = defaultdict(list)
    for c in by_sid.values():
        by_name[c["player"]].append(c)
    crosswalk = [
        {"name":"Byron Young", "sleeper_id":"10917", "fp_position":"DL", "sleeper_team":"LAR", "sleeper_positions":["DL","LB"], "sleeper_pos":"LB"},
        {"name":"Byron Young", "sleeper_id":"10925", "fp_position":"DL", "sleeper_team":"PHI", "sleeper_positions":["DL"], "sleeper_pos":"DL"},
        {"name":"Jaylon Jones", "sleeper_id":"11052", "fp_position":"DB", "sleeper_team":"IND", "sleeper_positions":["DB"], "sleeper_pos":"DB"},
        {"name":"Jaylon Jones", "sleeper_id":"8702", "fp_position":"DB", "sleeper_team":"CHI", "sleeper_positions":["DB"], "sleeper_pos":"DB"},
        {"name":"Ernest Jones IV", "sleeper_id":"1", "fp_position":"LB", "sleeper_team":"SEA", "sleeper_positions":["LB"], "sleeper_pos":"LB"},
    ]
    ctx = {"resolver": ResolverStub(), "sleeper_by_sid": by_sid, "sleeper_by_name": by_name, "crosswalk": crosswalk}

    def test_row(player, team, pos):
        return {"player":player, "normalized_name":normalize_name(player), "team":team, "source_position":pos, "canonical_position":normalize_position(pos)}

    assert resolve_identity(test_row("Byron Young", "LAR", "DE"), ctx)["sleeper_id"] == "10917"
    assert resolve_identity(test_row("Byron Young", "PHI", "DT"), ctx)["sleeper_id"] == "10925"
    assert resolve_identity(test_row("Jaylon Jones", "IND", "CB"), ctx)["sleeper_id"] == "11052"
    assert resolve_identity(test_row("Jaylon Jones", "CHI", "CB"), ctx)["sleeper_id"] == "8702"
    print("  real duplicate-name pattern (Byron Young / Jaylon Jones) resolves by team+position: OK")

    # Stable authoritative crosswalk may bridge a suffix difference; raw name
    # guessing may not.
    suffix = resolve_identity(test_row("Ernest Jones IV", "SEA", "LB"), ctx)
    assert suffix["sleeper_id"] == "1"
    assert suffix["crosswalk_corroborated"] is True
    print("  stable crosswalk suffix bridge: OK")

    mismatch = resolve_identity(test_row("Byron Young", "SEA", "DE"), ctx)
    assert mismatch["resolved"] is False
    assert mismatch["match_method"] in {"unresolved_name_position_collision", "multiple_authoritative_crosswalk_candidates"}
    print("  team mismatch/collision fails closed: OK")

    print("Self-test passed.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only 4for4 IDP 2026 ingestion/audit")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--dl", type=Path)
    p.add_argument("--lb", type=Path)
    p.add_argument("--db", type=Path)
    p.add_argument("--output-dir", type=Path)
    p.add_argument("--public-summary", type=Path)
    p.add_argument(
        "--allow-repo-private-input",
        action="store_true",
        help="Allow inputs under an explicitly .private* directory in repo (must remain gitignored).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.selftest:
        run_selftest()
        return

    if not (args.dl and args.lb and args.db and args.output_dir):
        raise SystemExit("full audit requires --dl, --lb, --db, and --output-dir")

    input_paths = [args.dl, args.lb, args.db]
    for path in input_paths:
        if not path.exists():
            raise RuntimeError(f"input does not exist: {path}")
        if not path.is_file():
            raise RuntimeError(f"input is not a file: {path}")

    enforce_private_paths(
        input_paths,
        args.output_dir,
        allow_repo_private_input=args.allow_repo_private_input,
    )

    all_rows: list[dict[str, Any]] = []
    file_meta: list[dict[str, Any]] = []
    for bucket, path in (("DL", args.dl), ("LB", args.lb), ("DB", args.db)):
        rows, meta = load_csv(path, bucket)
        all_rows.extend(rows)
        file_meta.append(meta)

    # Input-level exact duplicate row hash is always suspicious; keep the audit
    # explicit rather than silently deduplicating raw input lines.
    row_hash_counts = Counter(r["source_row_sha256"] for r in all_rows)
    exact_duplicate_hashes = [h for h, n in row_hash_counts.items() if n > 1]

    context = build_identity_context()
    for row in all_rows:
        row["identity"] = resolve_identity(row, context)

    processed_rows, collisions = collapse_exact_same_sid_duplicates(all_rows)
    # The collapse helper retains unresolved rows; normalized output remains one
    # record per original unresolved row and one per clean resolved Sleeper ID.
    normalized = [make_normalized_row(r) for r in processed_rows]

    summary = aggregate_summary(all_rows, file_meta, collisions)
    summary["inputs"]["exact_duplicate_row_hash_groups"] = len(exact_duplicate_hashes)
    audit = build_private_audit(all_rows, file_meta, collisions)
    audit["exact_duplicate_row_hashes"] = exact_duplicate_hashes

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / DETAIL_NORMALIZED_NAME).write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / DETAIL_AUDIT_NAME).write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / DETAIL_REPORT_NAME).write_text(
        render_private_report(summary, audit), encoding="utf-8"
    )

    if args.public_summary:
        public_path = args.public_summary.expanduser().resolve()
        # Aggregate-only summary may be written in the repo because it contains
        # no row-level provider projections or player-level source output.
        public_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"\nPrivate detailed outputs: {output_dir}")
    if args.public_summary:
        print(f"Aggregate-only public summary: {args.public_summary.expanduser().resolve()}")


if __name__ == "__main__":
    main()

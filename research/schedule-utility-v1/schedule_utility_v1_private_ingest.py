#!/usr/bin/env python3
"""
Schedule Utility V1 private 4for4 ingestion/audit helper.

This tool is intentionally source-private:
  * raw 4for4 CSV rows must remain outside the public repository;
  * the tool accepts private local paths;
  * only aggregate validation metadata and source hashes may be written
    to the public summary.

Phase 1A validates source structure and schedule/aFPA consistency only.
It does not read fantasy outcomes and does not authorize production use.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_AFP_HEADERS = [
    "Team", "#", "QB", "#.1", "RB-HALF", "#.2", "WR-HALF",
    "#.3", "TE-HALF", "#.4", "K", "#.5", "OFF-HALF", "#.6", "DEF",
]
EXPECTED_HOT_HEADERS = [
    "Wk", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "10", "11", "12", "13", "14", "15", "16", "17", "18",
    "PO2", "PO3", "ROS",
]
HALF_MASTER_COLUMN = {
    "qb_half": "QB",
    "rb_half": "RB-HALF",
    "wr_half": "WR-HALF",
    "te_half": "TE-HALF",
}
HOT_KEYS = (
    "qb_half", "rb_half", "wr_half", "te_half",
    "rb_ppr", "wr_ppr", "te_ppr",
)
CELL_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)(@?)([A-Z]{2,3})$")

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    headers = list(reader.fieldnames or [])
    return headers, list(reader)

def parse_matchup(value: Any):
    s = str(value or "").strip()
    if not s or s.upper() == "BYE":
        return None
    m = CELL_RE.fullmatch(s)
    if not m:
        raise ValueError(f"invalid Hot Spots weekly cell: {s!r}")
    return {
        "value": float(m.group(1)),
        "away": bool(m.group(2)),
        "opponent": m.group(3),
    }

def schedule_map(rows: list[dict[str, str]]):
    out = {}
    for row in rows:
        team = row["Wk"].strip().upper()
        for week in range(1, 19):
            parsed = parse_matchup(row[str(week)])
            out[(team, week)] = None if parsed is None else (
                parsed["opponent"], parsed["away"]
            )
    return out

def validate_source_bundle(paths: dict[str, Path], capture_utc: str, as_of_week: int):
    if not capture_utc:
        raise ValueError("source_capture_utc is required; CSV does not embed it")
    if not (1 <= as_of_week <= 18):
        raise ValueError("as_of_week must be 1..18")

    af_headers, af_rows = read_csv(paths["afpa_half"])
    if af_headers != EXPECTED_AFP_HEADERS:
        raise ValueError(f"unexpected aFPA headers: {af_headers}")
    if len(af_rows) != 32:
        raise ValueError(f"aFPA must contain 32 teams; got {len(af_rows)}")

    af_by_team = {r["Team"].strip().upper(): r for r in af_rows}
    if len(af_by_team) != 32:
        raise ValueError("aFPA Team keys are not unique")

    hot_rows = {}
    file_meta = {
        "afpa_half": {
            "sha256": sha256_file(paths["afpa_half"]),
            "rows": len(af_rows),
            "columns": len(af_headers),
        }
    }

    for key in HOT_KEYS:
        headers, rows = read_csv(paths[key])
        if headers != EXPECTED_HOT_HEADERS:
            raise ValueError(f"{key}: unexpected Hot Spots headers")
        if len(rows) != 32:
            raise ValueError(f"{key}: expected 32 teams; got {len(rows)}")
        teams = [r["Wk"].strip().upper() for r in rows]
        if len(set(teams)) != 32:
            raise ValueError(f"{key}: team keys are not unique")
        if set(teams) != set(af_by_team):
            raise ValueError(f"{key}: team universe differs from aFPA")
        hot_rows[key] = rows
        file_meta[key] = {
            "sha256": sha256_file(paths[key]),
            "rows": len(rows),
            "columns": len(headers),
        }

    # Parse every weekly cell and enforce exactly one bye per team.
    parsed_nonbye = {}
    bye_counts = {}
    for key, rows in hot_rows.items():
        nonbye = 0
        byes = 0
        for row in rows:
            row_byes = 0
            for week in range(1, 19):
                p = parse_matchup(row[str(week)])
                if p is None:
                    byes += 1
                    row_byes += 1
                else:
                    nonbye += 1
            if row_byes != 1:
                raise ValueError(
                    f"{key}: {row['Wk']} has {row_byes} bye cells; expected 1"
                )
        parsed_nonbye[key] = nonbye
        bye_counts[key] = byes
        if nonbye != 544 or byes != 32:
            raise ValueError(
                f"{key}: expected 544 non-bye and 32 bye cells; "
                f"got {nonbye}/{byes}"
            )

    # Every Hot Spots export must encode the exact same NFL schedule.
    base_schedule = schedule_map(hot_rows["qb_half"])
    schedule_identity_mismatches = 0
    for key in HOT_KEYS:
        sm = schedule_map(hot_rows[key])
        schedule_identity_mismatches += sum(
            1 for k, v in base_schedule.items() if sm[k] != v
        )
    if schedule_identity_mismatches:
        raise ValueError(
            f"Hot Spots schedule mismatch count={schedule_identity_mismatches}"
        )

    # Schedule must be reciprocal: if A is at B, B is home vs A in same week.
    reciprocity_mismatches = 0
    for (team, week), item in base_schedule.items():
        if item is None:
            continue
        opp, away = item
        other = base_schedule.get((opp, week))
        if other is None or other[0] != team or other[1] == away:
            reciprocity_mismatches += 1
    if reciprocity_mismatches:
        raise ValueError(
            f"schedule reciprocity mismatch count={reciprocity_mismatches}"
        )

    # Half-PPR Hot Spots values must reproduce opponent aFPA exactly.
    half_exact_checks = 0
    half_value_mismatches = 0
    for key, master_col in HALF_MASTER_COLUMN.items():
        for row in hot_rows[key]:
            for week in range(1, 19):
                p = parse_matchup(row[str(week)])
                if p is None:
                    continue
                expected = float(af_by_team[p["opponent"]][master_col])
                half_exact_checks += 1
                if abs(p["value"] - expected) > 1e-12:
                    half_value_mismatches += 1
    if half_value_mismatches:
        raise ValueError(
            f"Half-PPR Hot Spots/aFPA mismatch count={half_value_mismatches}"
        )

    # PPR schedule files must preserve the same matchup identity.
    ppr_vs_half_schedule_mismatches = 0
    for pos in ("rb", "wr", "te"):
        a = schedule_map(hot_rows[f"{pos}_half"])
        b = schedule_map(hot_rows[f"{pos}_ppr"])
        ppr_vs_half_schedule_mismatches += sum(
            1 for k, v in a.items() if b[k] != v
        )
    if ppr_vs_half_schedule_mismatches:
        raise ValueError(
            f"PPR/Half schedule mismatch count={ppr_vs_half_schedule_mismatches}"
        )

    # Provider playoff summary semantics can be inferred from displayed
    # weekly values only to rounding tolerance. They are audit evidence,
    # not V1 production inputs.
    po2_max_abs_display_rounding_error = 0.0
    po3_max_abs_display_rounding_error = 0.0
    for key, rows in hot_rows.items():
        for row in rows:
            v16 = parse_matchup(row["16"])["value"]
            v17 = parse_matchup(row["17"])["value"]
            v15 = parse_matchup(row["15"])["value"]
            po2_err = abs(((v16 + v17) / 2.0) - float(row["PO2"]))
            po3_err = abs(((v15 + v16 + v17) / 3.0) - float(row["PO3"]))
            po2_max_abs_display_rounding_error = max(
                po2_max_abs_display_rounding_error, po2_err
            )
            po3_max_abs_display_rounding_error = max(
                po3_max_abs_display_rounding_error, po3_err
            )

    return {
        "schema_version": 1,
        "study_id": "schedule-utility-v1",
        "phase": "1A",
        "status": "PASS_PRIVATE_SOURCE_INGESTION_FEASIBILITY",
        "source_capture_utc": capture_utc,
        "source_as_of_week": as_of_week,
        "outcome_data_read": False,
        "production_change_authorized": False,
        "raw_provider_rows_persisted_publicly": False,
        "row_level_provider_output_persisted_publicly": False,
        "source_file_count": len(paths),
        "source_files": file_meta,
        "coverage": {
            "team_count": 32,
            "hot_spots_table_count": 7,
            "hot_spots_nonbye_weekly_cells_per_table": 544,
            "hot_spots_bye_cells_per_table": 32,
            "hot_spots_total_nonbye_weekly_cells": sum(parsed_nonbye.values()),
            "hot_spots_total_bye_cells": sum(bye_counts.values()),
            "half_ppr_positions": ["QB", "RB", "WR", "TE"],
            "ppr_positions_with_separate_export": ["RB", "WR", "TE"],
            "qb_master_column_has_reception_scoring_suffix": False,
        },
        "validation": {
            "schedule_identity_mismatches": schedule_identity_mismatches,
            "schedule_reciprocity_mismatches": reciprocity_mismatches,
            "half_ppr_afpa_exact_checks": half_exact_checks,
            "half_ppr_afpa_value_mismatches": half_value_mismatches,
            "ppr_vs_half_schedule_mismatches": ppr_vs_half_schedule_mismatches,
            "po2_consistent_with_weeks_16_17_with_display_rounding": (
                po2_max_abs_display_rounding_error <= 0.051
            ),
            "po3_consistent_with_weeks_15_17_with_display_rounding": (
                po3_max_abs_display_rounding_error <= 0.067
            ),
            "po2_max_abs_display_rounding_error": round(
                po2_max_abs_display_rounding_error, 9
            ),
            "po3_max_abs_display_rounding_error": round(
                po3_max_abs_display_rounding_error, 9
            ),
        },
        "v1_window_policy": {
            "use_provider_ros_summary_as_primary_window": False,
            "use_provider_po2_po3_summary_as_primary_window": False,
            "derive_windows_from_weekly_matchup_cells": True,
            "near_term_definition": "next 3 scheduled non-bye games",
            "ros_definition": (
                "remaining fantasy-regular-season games excluding configured "
                "league playoff weeks"
            ),
            "playoff_definition": "configured league playoff weeks only",
        },
        "metadata_contract": {
            "csv_embeds_capture_timestamp": False,
            "csv_embeds_as_of_week": False,
            "capture_timestamp_must_be_supplied_externally": True,
            "as_of_week_must_be_supplied_externally": True,
            "fail_closed_if_missing": True,
        },
    }

def selftest():
    assert parse_matchup("10.9@LAC") == {
        "value": 10.9, "away": True, "opponent": "LAC"
    }
    assert parse_matchup("13.4SEA") == {
        "value": 13.4, "away": False, "opponent": "SEA"
    }
    assert parse_matchup("BYE") is None
    try:
        parse_matchup("not-a-cell")
    except ValueError:
        pass
    else:
        raise AssertionError("malformed matchup should fail closed")
    print("PASS: schedule utility private-ingestion selftest")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--afpa-half")
    ap.add_argument("--qb-half")
    ap.add_argument("--rb-half")
    ap.add_argument("--wr-half")
    ap.add_argument("--te-half")
    ap.add_argument("--rb-ppr")
    ap.add_argument("--wr-ppr")
    ap.add_argument("--te-ppr")
    ap.add_argument("--source-capture-utc")
    ap.add_argument("--as-of-week", type=int)
    ap.add_argument("--public-summary")
    ns = ap.parse_args()

    if ns.selftest:
        selftest()
        return

    required = {
        "afpa_half": ns.afpa_half,
        "qb_half": ns.qb_half,
        "rb_half": ns.rb_half,
        "wr_half": ns.wr_half,
        "te_half": ns.te_half,
        "rb_ppr": ns.rb_ppr,
        "wr_ppr": ns.wr_ppr,
        "te_ppr": ns.te_ppr,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise SystemExit(f"missing private source arguments: {missing}")
    if not ns.public_summary:
        raise SystemExit("--public-summary is required")

    paths = {k: Path(v).expanduser().resolve() for k, v in required.items()}
    for key, path in paths.items():
        if not path.exists():
            raise SystemExit(f"{key}: private source does not exist: {path}")

    result = validate_source_bundle(
        paths,
        capture_utc=ns.source_capture_utc,
        as_of_week=ns.as_of_week,
    )
    out = Path(ns.public_summary)
    out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "decision": result["status"],
        "public_summary": str(out),
        "raw_provider_rows_persisted_publicly": False,
    }, indent=2))

if __name__ == "__main__":
    main()

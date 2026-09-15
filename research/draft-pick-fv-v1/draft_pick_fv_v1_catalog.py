#!/usr/bin/env python3
"""
Draft Pick FV V1 — historical rookie-draft catalog.

This script is deliberately a CATALOG / FEASIBILITY step only.

It may read:
  * this league's Sleeper predecessor-league chain,
  * completed Sleeper draft metadata and draft picks,
  * Sleeper's player index for identity/position fallback,
  * DynastyProcess's Sleeper<->GSIS ID crosswalk,
  * nflverse players.csv for DOB and NFL identity metadata.

It MUST NOT read:
  * weekly or season fantasy outcomes,
  * 2026 realized player outcomes,
  * KTC or any dynasty market values,
  * package-adjustment votes,
  * candidate predictions.

No model is fit here. No candidate is scored here. No production file is
changed here. The output freezes which historical rookie draft classes and
pick records are eligible BEFORE outcome data are attached.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
RESEARCH = ROOT / "research" / "draft-pick-fv-v1"
CONFIG = ROOT / "config.json"
PREREG = RESEARCH / "preregistration_v1.json"
PREREG_MANIFEST = RESEARCH / "preregistration_manifest_v1.json"

OUT_JSON = RESEARCH / "historical_draft_catalog_v1.json"
OUT_MD = RESEARCH / "historical_draft_catalog_v1.md"
OUT_MANIFEST = RESEARCH / "historical_draft_catalog_manifest_v1.json"

SLEEPER_BASE = "https://api.sleeper.app/v1"
NFLVERSE_PLAYERS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "players/players.csv"
)
DYNASTYPROCESS_IDS_URL = (
    "https://raw.githubusercontent.com/dynastyprocess/data/master/"
    "files/db_playerids.csv"
)

TRACKED = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
EXCLUDED_KNOWN = {
    "K", "P", "LS", "OL", "OT", "OG", "C", "G", "T", "FB", "DEF",
    "DST",
}
POS_BUCKET = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "WR": "WR",
    "TE": "TE",
    "DE": "DL",
    "DT": "DL",
    "NT": "DL",
    "DL": "DL",
    "EDGE": "DL",
    "OLB": "LB",
    "ILB": "LB",
    "MLB": "LB",
    "LB": "LB",
    "CB": "DB",
    "S": "DB",
    "SS": "DB",
    "FS": "DB",
    "DB": "DB",
}

EXPECTED_PREREG_SHA = (
    "34ef4798b9f12769da54a4a267c81bc07ad09151a38eaaf06b3abb3ca3614108"
)

class CatalogError(RuntimeError):
    pass

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical_sha(obj: Any) -> str:
    data = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(data)

def fetch_json(session: requests.Session, url: str, retries: int = 4) -> Any:
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=45)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise CatalogError(f"Failed JSON fetch {url}: {last}")

def fetch_bytes(session: requests.Session, url: str, retries: int = 4) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=60)
            r.raise_for_status()
            return r.content
        except requests.RequestException as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise CatalogError(f"Failed byte fetch {url}: {last}")

def normalize_id(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"na", "nan", "none", "null"}:
        return None
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s

def normalize_name(value: Any) -> str:
    s = str(value or "").lower().strip()
    s = re.sub(r"[\.'’`\-]", "", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()

def bucket_position(raw: Any) -> tuple[str | None, str]:
    if raw is None:
        return None, "unresolved"
    p = str(raw).upper().strip()
    if not p:
        return None, "unresolved"
    if p in POS_BUCKET:
        return POS_BUCKET[p], "tracked"
    if p in EXCLUDED_KNOWN:
        return p, "known_excluded"
    return None, "unresolved"

def slot_tier(slot: int) -> str:
    if not 1 <= slot <= 12:
        raise CatalogError(f"draft_slot outside 1..12: {slot}")
    if slot <= 4:
        return "early"
    if slot <= 8:
        return "mid"
    return "late"

def pick_position_metadata(pick: dict[str, Any]) -> str | None:
    meta = pick.get("metadata") or {}
    for key in ("position", "pos"):
        val = meta.get(key)
        if val:
            return str(val)
    return None

def pick_name_metadata(pick: dict[str, Any]) -> str | None:
    meta = pick.get("metadata") or {}
    for key in ("first_name", "last_name"):
        if meta.get(key):
            first = str(meta.get("first_name") or "").strip()
            last = str(meta.get("last_name") or "").strip()
            full = f"{first} {last}".strip()
            if full:
                return full
    for key in ("player_name", "full_name"):
        if meta.get(key):
            return str(meta[key]).strip()
    return None

def csv_rows(raw: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fields = list(reader.fieldnames or [])
    return fields, [dict(row) for row in reader]

def find_column(fields: list[str], candidates: tuple[str, ...]) -> str | None:
    lower = {f.lower(): f for f in fields}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None

def build_id_crosswalk(raw: bytes) -> tuple[dict[str, str], dict[str, Any]]:
    fields, rows = csv_rows(raw)
    sleeper_col = find_column(
        fields,
        ("sleeper_id", "sleeper", "sleeper_player_id"),
    )
    gsis_col = find_column(
        fields,
        ("gsis_id", "gsis", "nfl_id"),
    )
    if not sleeper_col or not gsis_col:
        raise CatalogError(
            "DynastyProcess crosswalk missing sleeper/gsis columns. "
            f"Fields={fields}"
        )

    out: dict[str, str] = {}
    collisions: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        sid = normalize_id(row.get(sleeper_col))
        gid = normalize_id(row.get(gsis_col))
        if not sid or not gid:
            continue
        collisions[sid].add(gid)

    ambiguous = {
        sid: sorted(gids)
        for sid, gids in collisions.items()
        if len(gids) > 1
    }
    for sid, gids in collisions.items():
        if len(gids) == 1:
            out[sid] = next(iter(gids))

    return out, {
        "row_count": len(rows),
        "usable_sleeper_to_gsis": len(out),
        "ambiguous_sleeper_ids": ambiguous,
        "columns": fields,
    }

def build_nflverse_index(raw: bytes) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    fields, rows = csv_rows(raw)
    gsis_col = find_column(fields, ("gsis_id",))
    birth_col = find_column(fields, ("birth_date", "birthdate"))
    name_col = find_column(fields, ("display_name", "full_name", "name"))
    pos_col = find_column(fields, ("position", "position_group"))
    rookie_col = find_column(fields, ("rookie_season", "entry_year"))
    if not gsis_col or not birth_col:
        raise CatalogError(
            "nflverse players.csv missing gsis_id/birth_date. "
            f"Fields={fields}"
        )

    out = {}
    duplicate_gsis = 0
    for row in rows:
        gid = normalize_id(row.get(gsis_col))
        if not gid:
            continue
        if gid in out:
            duplicate_gsis += 1
            continue
        out[gid] = {
            "birth_date": (row.get(birth_col) or "").strip() or None,
            "name": (row.get(name_col) or "").strip() if name_col else None,
            "position": (row.get(pos_col) or "").strip() if pos_col else None,
            "rookie_season": normalize_id(row.get(rookie_col)) if rookie_col else None,
        }
    return out, {
        "row_count": len(rows),
        "gsis_index_count": len(out),
        "duplicate_gsis_rows_ignored": duplicate_gsis,
        "columns": fields,
    }

def validate_birth_date(value: Any) -> str | None:
    s = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return None
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None
    return s

def walk_league_chain(
    session: requests.Session,
    start_league_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chain = []
    source_hashes = []
    seen = set()
    current = str(start_league_id)

    for _ in range(30):
        if not current or current == "0":
            break
        if current in seen:
            raise CatalogError(f"Sleeper previous_league_id cycle at {current}")
        seen.add(current)

        url = f"{SLEEPER_BASE}/league/{current}"
        league = fetch_json(session, url)
        if not isinstance(league, dict) or not league.get("league_id"):
            raise CatalogError(f"Malformed Sleeper league response for {current}")

        chain.append(league)
        source_hashes.append({
            "kind": "sleeper_league",
            "league_id": current,
            "season": str(league.get("season")),
            "canonical_sha256": canonical_sha(league),
        })

        prev = normalize_id(league.get("previous_league_id"))
        if not prev:
            break
        current = prev

    if len(chain) == 30 and normalize_id(chain[-1].get("previous_league_id")):
        raise CatalogError("Sleeper league chain exceeded safety limit 30")
    return chain, source_hashes

def plausible_rookie_draft(
    draft: dict[str, Any],
    league: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons = []
    status = str(draft.get("status") or "").lower()
    draft_type = str(draft.get("type") or "").lower()
    settings = draft.get("settings") or {}

    try:
        rounds = int(settings.get("rounds"))
    except (TypeError, ValueError):
        rounds = None

    try:
        teams = int(draft.get("settings", {}).get("teams") or league.get("total_rosters"))
    except (TypeError, ValueError):
        teams = None

    if status != "complete":
        reasons.append("not_complete")
    if draft_type == "snake":
        reasons.append("snake_startup_or_nonrookie")
    if draft_type not in {"linear", ""}:
        reasons.append(f"unsupported_draft_type:{draft_type}")
    if rounds is None or not (4 <= rounds <= 8):
        reasons.append(f"rounds_outside_4_8:{rounds}")
    if teams != 12:
        reasons.append(f"not_12_team:{teams}")

    draft_season = str(draft.get("season") or "")
    league_season = str(league.get("season") or "")
    if draft_season and league_season and draft_season != league_season:
        reasons.append(
            f"draft_season_mismatch:{draft_season}!={league_season}"
        )

    return not reasons, reasons

def choose_drafts(
    session: requests.Session,
    chain: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    selected = []
    season_audit = []
    source_hashes = []

    for league in chain:
        league_id = str(league["league_id"])
        season = str(league.get("season"))
        url = f"{SLEEPER_BASE}/league/{league_id}/drafts"
        drafts = fetch_json(session, url)
        if not isinstance(drafts, list):
            raise CatalogError(f"Malformed drafts response for {league_id}")

        source_hashes.append({
            "kind": "sleeper_league_drafts",
            "league_id": league_id,
            "season": season,
            "canonical_sha256": canonical_sha(drafts),
        })

        assessed = []
        plausible = []
        for d in drafts:
            ok, reasons = plausible_rookie_draft(d, league)
            row = {
                "draft_id": str(d.get("draft_id")),
                "season": str(d.get("season")),
                "status": d.get("status"),
                "type": d.get("type"),
                "rounds": (d.get("settings") or {}).get("rounds"),
                "plausible": ok,
                "reasons_if_not_plausible": reasons,
            }
            assessed.append(row)
            if ok:
                plausible.append(d)

        if len(plausible) == 1:
            d = plausible[0]
            selected.append({
                "league": league,
                "draft": d,
            })
            selection = "selected_unique_plausible_rookie_draft"
        elif len(plausible) == 0:
            selection = "no_plausible_rookie_draft"
        else:
            selection = "ambiguous_multiple_plausible_drafts"

        season_audit.append({
            "season": season,
            "league_id": league_id,
            "league_total_rosters": league.get("total_rosters"),
            "draft_count": len(drafts),
            "plausible_count": len(plausible),
            "selection": selection,
            "drafts": assessed,
        })

    return selected, season_audit, source_hashes

def resolve_pick(
    pick: dict[str, Any],
    sleeper_players: dict[str, Any],
    id_crosswalk: dict[str, str],
    nflverse: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sid = normalize_id(pick.get("player_id"))
    sleeper = sleeper_players.get(sid, {}) if sid else {}
    gid = id_crosswalk.get(sid) if sid else None
    nflp = nflverse.get(gid, {}) if gid else {}

    raw_pos_sources = [
        ("draft_metadata", pick_position_metadata(pick)),
        ("sleeper_player_index", sleeper.get("position")),
        ("nflverse", nflp.get("position")),
    ]
    resolved_pos = None
    pos_status = "unresolved"
    pos_source = None
    raw_pos = None
    for source, candidate in raw_pos_sources:
        bucket, status = bucket_position(candidate)
        if status != "unresolved":
            resolved_pos = bucket
            pos_status = status
            pos_source = source
            raw_pos = str(candidate).upper().strip()
            break

    name = (
        pick_name_metadata(pick)
        or sleeper.get("full_name")
        or nflp.get("name")
        or None
    )

    nflverse_birth = validate_birth_date(nflp.get("birth_date"))
    sleeper_birth = validate_birth_date(
        sleeper.get("birth_date") or sleeper.get("birthdate")
    )
    sleeper_dob_consistent = (
        nflverse_birth is not None
        and sleeper_birth is not None
        and nflverse_birth == sleeper_birth
    )

    return {
        "sleeper_player_id": sid,
        "gsis_id": gid,
        "player_name": name,
        "position_bucket": resolved_pos if pos_status == "tracked" else None,
        "position_resolution_status": pos_status,
        "raw_position": raw_pos,
        "position_source": pos_source,
        "nflverse_birth_date": nflverse_birth,
        "dob_source": "nflverse_players" if nflverse_birth else None,
        "sleeper_birth_date_for_consistency_only": sleeper_birth,
        "sleeper_dob_matches_nflverse": sleeper_dob_consistent,
        "identity_crosswalk_status": (
            "sleeper_to_gsis_unique"
            if gid
            else "no_unique_sleeper_to_gsis"
        ),
    }

def build_catalog() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if sha256_path(PREREG) != EXPECTED_PREREG_SHA:
        raise CatalogError("Frozen preregistration SHA changed")

    current_league_id = normalize_id(config.get("league_id"))
    current_season = int(config.get("season"))
    if not current_league_id:
        raise CatalogError("config.json league_id missing")

    gates = prereg["maturity_and_feasibility_gates"]
    latest_primary = int(gates["primary_latest_eligible_draft_year"])
    min_classes = int(
        gates["minimum_complete_draft_classes_for_model_selection"]
    )
    min_cell = int(
        gates["minimum_players_per_round_tier_cell_across_primary_sample"]
    )
    min_dob = float(gates["minimum_absolute_bridge_dob_coverage"])
    min_pos = float(gates["minimum_position_resolution_coverage"])

    session = requests.Session()
    session.headers.update({
        "User-Agent": "LOG-Trade-Calculator-Draft-Pick-FV-V1-Catalog/1.0"
    })

    chain, source_hashes = walk_league_chain(
        session, current_league_id
    )

    selected, season_audit, draft_hashes = choose_drafts(session, chain)
    source_hashes.extend(draft_hashes)

    sleeper_players_url = f"{SLEEPER_BASE}/players/nfl"
    sleeper_players = fetch_json(session, sleeper_players_url)
    if not isinstance(sleeper_players, dict):
        raise CatalogError("Malformed Sleeper player index")
    source_hashes.append({
        "kind": "sleeper_players_nfl",
        "canonical_sha256": canonical_sha(sleeper_players),
    })

    id_bytes = fetch_bytes(session, DYNASTYPROCESS_IDS_URL)
    id_crosswalk, crosswalk_meta = build_id_crosswalk(id_bytes)
    source_hashes.append({
        "kind": "dynastyprocess_db_playerids_csv",
        "url": DYNASTYPROCESS_IDS_URL,
        "sha256": sha256_bytes(id_bytes),
    })

    nfl_bytes = fetch_bytes(session, NFLVERSE_PLAYERS_URL)
    nflverse, nfl_meta = build_nflverse_index(nfl_bytes)
    source_hashes.append({
        "kind": "nflverse_players_csv",
        "url": NFLVERSE_PLAYERS_URL,
        "sha256": sha256_bytes(nfl_bytes),
    })

    classes = []
    all_pick_rows = []
    for item in selected:
        league = item["league"]
        draft = item["draft"]
        draft_id = str(draft["draft_id"])
        season = int(draft.get("season") or league.get("season"))
        rounds = int((draft.get("settings") or {}).get("rounds"))

        picks_url = f"{SLEEPER_BASE}/draft/{draft_id}/picks"
        picks = fetch_json(session, picks_url)
        if not isinstance(picks, list):
            raise CatalogError(f"Malformed draft picks response {draft_id}")

        source_hashes.append({
            "kind": "sleeper_draft_picks",
            "draft_id": draft_id,
            "season": season,
            "canonical_sha256": canonical_sha(picks),
        })

        pick_rows = []
        duplicate_round_slot = []
        seen_round_slot = set()
        for p in picks:
            try:
                rnd = int(p.get("round"))
                slot = int(p.get("draft_slot"))
            except (TypeError, ValueError):
                continue
            if not 1 <= rnd <= 6 or not 1 <= slot <= 12:
                continue

            key = (rnd, slot)
            if key in seen_round_slot:
                duplicate_round_slot.append(
                    {"round": rnd, "slot": slot}
                )
            seen_round_slot.add(key)

            resolved = resolve_pick(
                p,
                sleeper_players=sleeper_players,
                id_crosswalk=id_crosswalk,
                nflverse=nflverse,
            )
            row = {
                "draft_year": season,
                "league_id": str(league["league_id"]),
                "draft_id": draft_id,
                "draft_rounds_configured": rounds,
                "round": rnd,
                "draft_slot": slot,
                "overall_pick_no": p.get("pick_no"),
                "tier": slot_tier(slot),
                "roster_id": p.get("roster_id"),
                "picked_by": p.get("picked_by"),
                **resolved,
            }
            pick_rows.append(row)
            all_pick_rows.append(row)

        class_row = {
            "draft_year": season,
            "league_id": str(league["league_id"]),
            "draft_id": draft_id,
            "draft_type": draft.get("type"),
            "draft_status": draft.get("status"),
            "configured_rounds": rounds,
            "rounds_1_6_selected_pick_count": len(pick_rows),
            "unique_round_slot_count": len(seen_round_slot),
            "duplicate_round_slot_records": duplicate_round_slot,
            "complete_72_round_slot_grid": (
                len(seen_round_slot) == 72
                and not duplicate_round_slot
                and all(
                    (r, s) in seen_round_slot
                    for r in range(1, 7)
                    for s in range(1, 13)
                )
            ),
            "primary_mature": season <= latest_primary,
            "picks": sorted(
                pick_rows,
                key=lambda x: (x["round"], x["draft_slot"]),
            ),
        }
        classes.append(class_row)

    classes.sort(key=lambda x: x["draft_year"])
    primary_classes = [
        c for c in classes if c["primary_mature"]
    ]

    primary_rows = [
        p
        for c in primary_classes
        for p in c["picks"]
    ]

    cell_counts = {
        f"R{rnd}_{tier}": 0
        for rnd in range(1, 7)
        for tier in ("early", "mid", "late")
    }
    exact_slot_counts = {
        f"R{rnd}_S{slot:02d}": 0
        for rnd in range(1, 7)
        for slot in range(1, 13)
    }

    tracked_rows = []
    position_resolved = 0
    known_excluded = 0
    unresolved_position = 0

    for row in primary_rows:
        status = row["position_resolution_status"]
        if status == "tracked":
            position_resolved += 1
            tracked_rows.append(row)
            cell_counts[f"R{row['round']}_{row['tier']}"] += 1
            exact_slot_counts[
                f"R{row['round']}_S{row['draft_slot']:02d}"
            ] += 1
        elif status == "known_excluded":
            position_resolved += 1
            known_excluded += 1
        else:
            unresolved_position += 1

    pos_coverage = (
        position_resolved / len(primary_rows)
        if primary_rows else 0.0
    )
    dob_resolved = sum(
        1 for row in tracked_rows if row["nflverse_birth_date"]
    )
    dob_coverage = (
        dob_resolved / len(tracked_rows)
        if tracked_rows else 0.0
    )

    complete_primary_years = [
        c["draft_year"]
        for c in primary_classes
        if c["draft_status"] == "complete"
    ]
    complete_primary_years = sorted(set(complete_primary_years))

    validation_years = (
        complete_primary_years[-2:]
        if len(complete_primary_years) >= 2
        else complete_primary_years[:]
    )
    development_years = [
        y for y in complete_primary_years
        if y not in validation_years
    ]

    gates_result = {
        "at_least_six_primary_mature_classes": {
            "required": min_classes,
            "observed": len(complete_primary_years),
            "pass": len(complete_primary_years) >= min_classes,
        },
        "minimum_tracked_players_per_round_tier_cell": {
            "required": min_cell,
            "observed_minimum": (
                min(cell_counts.values()) if cell_counts else 0
            ),
            "pass": (
                bool(cell_counts)
                and min(cell_counts.values()) >= min_cell
            ),
        },
        "position_resolution_coverage": {
            "required": min_pos,
            "observed": pos_coverage,
            "pass": pos_coverage >= min_pos,
            "definition": (
                "Share of selected picks in rounds 1-6 whose position "
                "resolves either to a tracked bucket or to a known excluded "
                "position such as K/OL/P. Unknown is unresolved."
            ),
        },
        "absolute_bridge_nflverse_dob_coverage": {
            "required": min_dob,
            "observed": dob_coverage,
            "pass": dob_coverage >= min_dob,
            "denominator": len(tracked_rows),
            "resolved": dob_resolved,
        },
    }

    all_pass = all(g["pass"] for g in gates_result.values())
    status = (
        "CATALOG_FROZEN_READY_FOR_OUTCOME_INGESTION"
        if all_pass
        else "INSUFFICIENT_HISTORICAL_EVIDENCE"
    )

    catalog = {
        "schema_version": 1,
        "catalog_id": "draft-pick-fv-v1-historical-draft-catalog",
        "study_id": prereg["study_id"],
        "status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "candidate_fit_performed": False,
        "candidate_scores_computed": False,
        "historical_weekly_outcomes_read": False,
        "2026_realized_outcomes_read": False,
        "ktc_or_market_data_read": False,
        "package_vote_data_read": False,
        "production_change_authorized": False,
        "preregistration_sha256": sha256_path(PREREG),
        "current_config": {
            "league_id": current_league_id,
            "season": current_season,
        },
        "source_contract": {
            "sleeper_league_chain": True,
            "sleeper_completed_drafts": True,
            "sleeper_draft_picks": True,
            "sleeper_player_index_identity_only": True,
            "dynastyprocess_id_crosswalk": True,
            "nflverse_players_for_dob": True,
            "weekly_stats_endpoint_used": False,
        },
        "league_chain": [
            {
                "league_id": str(l.get("league_id")),
                "season": str(l.get("season")),
                "total_rosters": l.get("total_rosters"),
                "previous_league_id": normalize_id(
                    l.get("previous_league_id")
                ),
            }
            for l in chain
        ],
        "season_draft_selection_audit": season_audit,
        "identity_source_metadata": {
            "dynastyprocess_crosswalk": crosswalk_meta,
            "nflverse_players": nfl_meta,
        },
        "source_hashes": source_hashes,
        "draft_classes": classes,
        "primary_mature_class_years": complete_primary_years,
        "frozen_development_class_years": development_years,
        "frozen_locked_validation_class_years": validation_years,
        "coverage": {
            "primary_selected_pick_rows_rounds_1_6": len(primary_rows),
            "tracked_position_pick_rows": len(tracked_rows),
            "known_excluded_position_pick_rows": known_excluded,
            "unresolved_position_pick_rows": unresolved_position,
            "position_resolution_coverage": pos_coverage,
            "tracked_nflverse_dob_resolved": dob_resolved,
            "tracked_nflverse_dob_coverage": dob_coverage,
            "round_tier_cell_counts": cell_counts,
            "exact_round_slot_tracked_counts": exact_slot_counts,
        },
        "maturity_and_feasibility_gates": gates_result,
        "next_step": (
            "Outcome ingestion/evaluation may be built under the frozen "
            "preregistration and this frozen catalog."
            if all_pass
            else
            "Stop Draft Pick FV V1. Do not ingest outcomes for model "
            "selection and do not fit a replacement curve."
        ),
    }
    return catalog

def write_outputs(catalog: dict[str, Any]) -> None:
    OUT_JSON.write_text(
        json.dumps(catalog, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    gates = catalog["maturity_and_feasibility_gates"]
    years = catalog["primary_mature_class_years"]
    dev = catalog["frozen_development_class_years"]
    val = catalog["frozen_locked_validation_class_years"]
    cov = catalog["coverage"]

    lines = [
        "# Draft Pick FV V1 — Historical Draft Catalog",
        "",
        f"**Status:** `{catalog['status']}`",
        "",
        "This catalog freezes historical rookie-draft identities and "
        "feasibility before any player outcome data are attached. No "
        "candidate was fit or scored.",
        "",
        "## League chain / mature classes",
        "",
        f"- Sleeper predecessor leagues found: **{len(catalog['league_chain'])}**",
        f"- Primary-mature rookie draft classes: **{', '.join(map(str, years)) or 'none'}**",
        f"- Frozen development years: **{', '.join(map(str, dev)) or 'none'}**",
        f"- Frozen locked validation years: **{', '.join(map(str, val)) or 'none'}**",
        "",
        "## Feasibility gates",
        "",
        "| Gate | Required | Observed | Pass |",
        "|---|---:|---:|:---:|",
    ]
    for name, g in gates.items():
        observed = g.get("observed", g.get("observed_minimum"))
        if isinstance(observed, float):
            obs_text = f"{observed:.4f}"
        else:
            obs_text = str(observed)
        req = g["required"]
        req_text = f"{req:.4f}" if isinstance(req, float) else str(req)
        lines.append(
            f"| {name} | {req_text} | {obs_text} | "
            f"{'PASS' if g['pass'] else 'FAIL'} |"
        )

    lines += [
        "",
        "## Coverage",
        "",
        f"- Primary selected pick rows (rounds 1-6): **{cov['primary_selected_pick_rows_rounds_1_6']}**",
        f"- Tracked QB/RB/WR/TE/DL/LB/DB rows: **{cov['tracked_position_pick_rows']}**",
        f"- Known excluded-position rows: **{cov['known_excluded_position_pick_rows']}**",
        f"- Unresolved-position rows: **{cov['unresolved_position_pick_rows']}**",
        f"- Position resolution coverage: **{cov['position_resolution_coverage']:.2%}**",
        f"- nflverse DOB coverage among tracked rows: **{cov['tracked_nflverse_dob_coverage']:.2%}**",
        "",
        "## Round × tier tracked counts",
        "",
        "| Cell | N |",
        "|---|---:|",
    ]
    for cell, n in sorted(cov["round_tier_cell_counts"].items()):
        lines.append(f"| {cell} | {n} |")

    lines += [
        "",
        "## Draft-season selection audit",
        "",
        "| Season | League | Drafts | Plausible | Decision |",
        "|---:|---|---:|---:|---|",
    ]
    for row in sorted(
        catalog["season_draft_selection_audit"],
        key=lambda x: int(x["season"]) if str(x["season"]).isdigit() else -1,
    ):
        lines.append(
            f"| {row['season']} | {row['league_id']} | "
            f"{row['draft_count']} | {row['plausible_count']} | "
            f"{row['selection']} |"
        )

    lines += [
        "",
        "## Guardrail",
        "",
        "No weekly/season fantasy outcomes were read. No KTC/market values "
        "were read. No candidate was fit or scored. A Green workflow only "
        "means the catalog was generated correctly; scientific readiness is "
        "the status and gate table above.",
        "",
        f"**Next step:** {catalog['next_step']}",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "catalog_id": catalog["catalog_id"],
        "study_id": catalog["study_id"],
        "status": "frozen_catalog",
        "scientific_status": catalog["status"],
        "files": {
            str(OUT_JSON.relative_to(ROOT)): {
                "sha256": sha256_path(OUT_JSON)
            },
            str(OUT_MD.relative_to(ROOT)): {
                "sha256": sha256_path(OUT_MD)
            },
        },
        "historical_weekly_outcomes_read": False,
        "candidate_fit_performed": False,
        "production_change_authorized": False,
    }
    OUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

def selftest() -> None:
    assert slot_tier(1) == "early"
    assert slot_tier(4) == "early"
    assert slot_tier(5) == "mid"
    assert slot_tier(8) == "mid"
    assert slot_tier(9) == "late"
    assert slot_tier(12) == "late"

    for raw, expected in [
        ("DE", "DL"),
        ("DT", "DL"),
        ("OLB", "LB"),
        ("ILB", "LB"),
        ("CB", "DB"),
        ("FS", "DB"),
        ("QB", "QB"),
    ]:
        bucket, status = bucket_position(raw)
        assert status == "tracked"
        assert bucket == expected

    bucket, status = bucket_position("K")
    assert status == "known_excluded"
    assert bucket == "K"
    assert normalize_id("123.0") == "123"
    assert normalize_name("John Doe Jr.") == "john doe"

    synthetic = {
        "status": "complete",
        "type": "linear",
        "season": "2020",
        "settings": {"rounds": 6, "teams": 12},
    }
    league = {"season": "2020", "total_rosters": 12}
    ok, reasons = plausible_rookie_draft(synthetic, league)
    assert ok and not reasons

    snake = dict(synthetic)
    snake["type"] = "snake"
    ok, reasons = plausible_rookie_draft(snake, league)
    assert not ok
    assert "snake_startup_or_nonrookie" in reasons

    print("PASS: Draft Pick FV V1 catalog self-test")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return

    if args.check:
        if not OUT_JSON.exists() or not OUT_MANIFEST.exists():
            raise CatalogError("Catalog outputs do not exist")
        catalog = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        manifest = json.loads(
            OUT_MANIFEST.read_text(encoding="utf-8")
        )
        assert catalog["candidate_fit_performed"] is False
        assert catalog["historical_weekly_outcomes_read"] is False
        assert catalog["2026_realized_outcomes_read"] is False
        assert catalog["ktc_or_market_data_read"] is False
        assert catalog["production_change_authorized"] is False
        assert manifest["candidate_fit_performed"] is False
        assert manifest["historical_weekly_outcomes_read"] is False
        assert manifest["production_change_authorized"] is False
        for rel, rec in manifest["files"].items():
            assert sha256_path(ROOT / rel) == rec["sha256"]
        print(
            "PASS: frozen historical draft catalog contract verified; "
            f"scientific status={catalog['status']}"
        )
        return

    catalog = build_catalog()
    write_outputs(catalog)
    print(json.dumps({
        "status": catalog["status"],
        "primary_mature_class_years": catalog["primary_mature_class_years"],
        "development_years": catalog["frozen_development_class_years"],
        "validation_years": catalog["frozen_locked_validation_class_years"],
        "gates": catalog["maturity_and_feasibility_gates"],
    }, indent=2))

if __name__ == "__main__":
    main()

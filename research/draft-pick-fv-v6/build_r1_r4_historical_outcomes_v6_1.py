#!/usr/bin/env python3
"""Draft Pick FV V6.1 Phase 3 historical outcome harvest.

This stage may read 2018-2025 league-wide NFL calendar-season stats because
those seasons are required by the preregistered H2/H3/H4 development horizons
for the 2018-2023 draft classes. It MUST NOT read the frozen 2024 rookie
holdout pick corpus, join any 2024 rookie-pick identities, fit candidates,
score candidates, or authorize production.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import re
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path.cwd()
V5 = ROOT / "research" / "draft-pick-fv-v5"
V6 = ROOT / "research" / "draft-pick-fv-v6"

PRE = V6 / "structural_continuity_preregistration_v6.json"
AMEND = V6 / "structural_continuity_preoutcome_amendment_v6_1.json"
PICKS = V6 / "r1_r4_development_pick_identity_v6_1.jsonl"
P2_SUM = V6 / "r1_r4_source_identity_summary_v6_1.json"
P2_MAN = V6 / "r1_r4_source_identity_manifest_v6_1.json"
V5_PRE = V5 / "r1_r2_bridge_preregistration_v5.json"

SCORE_PATH = ROOT / "research/roster-economics/historical_weekly_points_pipeline.py"
AGE_PATH = ROOT / "scripts/validation/snapshot_values.py"

OUT_SCRIPT = V6 / "build_r1_r4_historical_outcomes_v6_1.py"
OUT_SOURCE = V6 / "r1_r4_historical_source_manifest_v6_1.json"
OUT_LINEAGE = V6 / "r1_r4_historical_position_dob_lineage_v6_1.jsonl"
OUT_UNIVERSE = V6 / "r1_r4_historical_scored_universe_v6_1.jsonl"
OUT_DEV = V6 / "r1_r4_development_outcomes_v6_1.jsonl"
OUT_SUM = V6 / "r1_r4_historical_outcome_summary_v6_1.json"
OUT_MD = V6 / "r1_r4_historical_outcome_summary_v6_1.md"
OUT_MAN = V6 / "r1_r4_historical_outcome_manifest_v6_1.json"

BASE = "https://api.sleeper.app/v1"
DRAFT_YEARS = (2018, 2019, 2020, 2021, 2022, 2023)
SEASONS = tuple(range(2018, 2026))
WEEKS = tuple(range(1, 19))
POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
CELLS = tuple(
    f"r{rnd}_{tier}"
    for rnd in range(1, 5)
    for tier in ("early", "mid", "late")
)
MIN_READY = 0.95

POS_MAP = {
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

PLAYER_SHA256 = "4dd70f328f31b0bb7cbf043412298d5a325863e27b8f2eeea22c9e925c808dee"
DP_SHA256 = "0174ea890e71d33fa0afc1b846ce1c92273542278a287b6bd52c3a4aa5edce73"

ROSTER_ASSET_CONTRACT = {
    2018: {"id": 125773963, "size": 997735, "updated_at": "2023-09-13T00:54:20Z"},
    2019: {"id": 125774522, "size": 1001234, "updated_at": "2023-09-13T00:59:44Z"},
    2020: {"id": 125775504, "size": 988000, "updated_at": "2023-09-13T01:04:58Z"},
    2021: {"id": 125776019, "size": 953822, "updated_at": "2023-09-13T01:10:36Z"},
    2022: {"id": 125776585, "size": 980115, "updated_at": "2023-09-13T01:16:11Z"},
    2023: {"id": 156614734, "size": 967354, "updated_at": "2024-03-14T07:18:12Z"},
    2024: {"id": 237398176, "size": 1005701, "updated_at": "2025-03-14T07:16:10Z"},
    2025: {
        "id": 373640814,
        "size": 1010039,
        "updated_at": "2026-03-14T07:33:08Z",
        "digest": "sha256:531ee5de386037bb17de3e3e3d50f7b4ed08789526bbaae9876fdd3dfb4d04ad",
    },
}

class GateError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bsha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha(obj: Any) -> str:
    raw = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateError(f"{path}:{n}: invalid JSONL: {exc}") from exc
            if not isinstance(obj, dict):
                raise GateError(f"{path}:{n}: non-object row")
            rows.append(obj)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(
                json.dumps(row, sort_keys=True, separators=(",", ":"))
                + "\n"
            )


def import_file(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise GateError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def stable_id(v: Any) -> str | None:
    s = str(v or "").strip()
    if not s or s.upper() in {"NA", "N/A", "NULL", "NONE", "NAN", "0", "0000"}:
        return None
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def safe_int(v: Any) -> int | None:
    try:
        s = str(v or "").strip()
    except Exception:
        return None
    if not re.fullmatch(r"[+-]?\d+", s):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def norm_pos(v: Any) -> str | None:
    s = str(v or "").strip().upper()
    return POS_MAP.get(s)


def valid_dob(v: Any) -> str | None:
    s = str(v or "").strip()
    if not s:
        return None
    try:
        d = date.fromisoformat(s[:10])
    except ValueError:
        return None
    if not 1940 <= d.year <= 2010:
        return None
    return d.isoformat()


def age_sep1(birth: str, season: int) -> int:
    d = date.fromisoformat(birth)
    a = date(season, 9, 1)
    age = a.year - d.year - ((a.month, a.day) < (d.month, d.day))
    if not 18 <= age <= 50:
        raise GateError(f"implausible age {age}: {birth} in {season}")
    return age


def sched_games(season: int) -> int:
    return 17 if season >= 2021 else 16


def required_weeks(season: int) -> set[int]:
    return set(range(1, 19 if season >= 2021 else 18))


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def request_json(
    session: requests.Session,
    url: str,
    *,
    allow_old_week18: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    waits = (2, 4, 8, 15, 30, 45, 60, 90)
    last: Exception | None = None
    for attempt, wait_default in enumerate(waits):
        try:
            r = session.get(url, timeout=60)
            if allow_old_week18 and r.status_code == 404:
                raw = b"{}"
                return {}, {
                    "url": url,
                    "status": 404,
                    "sha256": bsha(raw),
                    "bytes": len(raw),
                    "top_level_n": 0,
                }
            if r.status_code == 429:
                try:
                    retry_after = float(r.headers.get("Retry-After") or 0)
                except ValueError:
                    retry_after = 0.0
                wait = max(retry_after, float(wait_default))
                last = GateError(f"HTTP 429 cooldown {wait}s")
                if attempt + 1 == len(waits):
                    break
                time.sleep(wait)
                continue
            r.raise_for_status()
            raw = r.content
            obj = json.loads(raw.decode("utf-8"))
            if not isinstance(obj, dict):
                raise GateError("non-object JSON")
            return obj, {
                "url": url,
                "status": r.status_code,
                "sha256": bsha(raw),
                "bytes": len(raw),
                "top_level_n": len(obj),
            }
        except (
            requests.RequestException,
            UnicodeDecodeError,
            json.JSONDecodeError,
            GateError,
        ) as exc:
            last = exc
            if attempt + 1 < len(waits):
                time.sleep(wait_default)
    raise GateError(
        f"transport failure for {url}: {type(last).__name__}: {last}"
    )


def guard_contract() -> dict[str, Any]:
    pre = load(PRE)
    amend = load(AMEND)
    p2s = load(P2_SUM)
    p2m = load(P2_MAN)
    v5pre = load(V5_PRE)

    if pre["status"] != "FROZEN_PRE_V6_R3_R4_OUTCOME_ACCESS":
        raise GateError("V6 preregistration status drift")
    if amend["decision"] != (
        "PASS_V6_1_CLEAN_SOURCE_AMENDMENT_FROZEN_PHASE2_AUTHORIZED"
    ):
        raise GateError("V6.1 source amendment drift")
    if p2m["decision"] != (
        "PASS_V6_1_PHASE2_R1_R4_SOURCE_IDENTITY_FREEZE_"
        "HISTORICAL_OUTCOME_HARVEST_AUTHORIZED_NEXT_STAGE"
    ):
        raise GateError("Phase 2 authorization drift")
    if p2m["outcome_ingestion_authorized_next_stage"] is not True:
        raise GateError("Phase 2 did not authorize historical outcomes")
    if p2m["holdout_2024_outcome_ingestion_authorized"] is not False:
        raise GateError("2024 holdout outcome firewall drift")
    if p2s["development_source_gate"]["clean_league_n"] != 378:
        raise GateError("development clean league count drift")
    if p2s["development_source_gate"]["retained_occurrence_n"] != 17915:
        raise GateError("development occurrence count drift")
    if p2s["temporal_holdout_2024_source_gate"]["outcomes_sealed"] is not True:
        raise GateError("2024 holdout source no longer sealed")
    if p2s["next_stage"] != (
        "draft-pick-fv-v6-phase3-r1-r4-historical-outcome-harvest"
    ):
        raise GateError("Phase 2 next stage drift")
    for obj in (p2s, p2m):
        for key in (
            "candidate_fit_performed",
            "candidate_selection_performed",
            "production_change_authorized",
        ):
            if obj[key] is not False:
                raise GateError(f"Phase 2 firewall drift: {key}")

    hist = pre["historical_outcome_contract"]
    if hist["provider"] != "Sleeper historical weekly NFL stats":
        raise GateError("historical provider drift")
    if hist["weeks"] != list(range(1, 19)):
        raise GateError("historical week contract drift")
    if hist["replacement_pool_position_lineage_hardening"][
        "full_nfl_replacement_pool_position"
    ] != (
        "season-appropriate nflverse roster position mapped by stable "
        "player ID; do not classify historical replacement pools from "
        "a current 2026 Sleeper position snapshot"
    ):
        raise GateError("position-lineage hardening drift")

    # V6 freezes the V5 O2 definition but did not duplicate the numeric
    # age-curve constants. Pull those constants only from the already-frozen
    # pre-outcome V5 preregistration; no post-outcome source is consulted.
    if v5pre["status"] != "FROZEN_PRE_OUTCOME":
        raise GateError("V5 frozen age-curve source drift")
    bridge = v5pre["frozen_scale_bridge"]
    if float(bridge["base_scale"]) != float(hist["O2_scale"]["base_scale"]):
        raise GateError("base scale mismatch between V5 and V6")
    if bridge["position_weight"] != hist["frozen_position_weights"]:
        raise GateError("position-weight mismatch between V5 and V6")
    if v5pre["frozen_replacement_ranks"] != hist["frozen_replacement_ranks"]:
        raise GateError("replacement-rank mismatch between V5 and V6")

    return {
        "pre": pre,
        "amend": amend,
        "p2s": p2s,
        "p2m": p2m,
        "v5pre": v5pre,
    }


def load_players_master(path: Path) -> dict[str, Any]:
    """Load nflverse Players V2 stable metadata.

    Players V2 intentionally does not include Sleeper IDs.  We use it for
    GSIS-keyed name/position/DOB metadata only; Sleeper linkage comes from
    season rosters, with pinned DynastyProcess GSIS->Sleeper as fallback.
    """
    if sha256(path) != PLAYER_SHA256:
        raise GateError("players.csv hash drift")
    by_gsis = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {
            "gsis_id", "display_name", "position", "birth_date"
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise GateError(
                f"players.csv missing V2 columns: {sorted(missing)}"
            )
        for row in reader:
            gsis = stable_id(row.get("gsis_id"))
            if not gsis:
                continue
            by_gsis[gsis] = {
                "gsis_id": gsis,
                "name": stable_id(row.get("display_name")),
                "position": norm_pos(row.get("position")),
                "birth_date": valid_dob(row.get("birth_date")),
            }
    if not by_gsis:
        raise GateError("players.csv produced empty GSIS index")
    return {"by_gsis": by_gsis}


def load_dp_sleeper_crosswalk(path: Path) -> dict[str, str]:
    if sha256(path) != DP_SHA256:
        raise GateError("DynastyProcess player-ID hash drift")
    candidates = defaultdict(set)
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"gsis_id", "sleeper_id"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise GateError(
                f"DynastyProcess missing columns: {sorted(missing)}"
            )
        for row in reader:
            gsis = stable_id(row.get("gsis_id"))
            sid = stable_id(row.get("sleeper_id"))
            if gsis and sid:
                candidates[gsis].add(sid)
    out = {}
    for gsis, ids in candidates.items():
        if len(ids) == 1:
            out[gsis] = next(iter(ids))
    if not out:
        raise GateError("DynastyProcess GSIS->Sleeper crosswalk empty")
    return out

def load_roster_lineage(
    roster_path: Path,
    season: int,
    master: dict[str, Any],
    dp_sleeper_by_gsis: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates = defaultdict(list)
    raw_n = 0
    supported_n = 0
    with roster_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {
            "season", "position", "full_name", "birth_date",
            "gsis_id", "sleeper_id",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise GateError(
                f"{roster_path.name} missing columns: {sorted(missing)}"
            )
        for row in reader:
            raw_n += 1
            row_season = safe_int(row.get("season"))
            if row_season != season:
                continue
            pos = norm_pos(row.get("position"))
            if pos not in POSITIONS:
                continue
            supported_n += 1
            gsis = stable_id(row.get("gsis_id"))
            sid = stable_id(row.get("sleeper_id"))
            if not sid and gsis:
                sid = dp_sleeper_by_gsis.get(gsis)
            if not sid:
                continue
            candidates[sid].append({
                "season": season,
                "sleeper_id": sid,
                "gsis_id": gsis,
                "position": pos,
                "raw_position": stable_id(row.get("position")),
                "name": stable_id(row.get("full_name")),
                "birth_date": valid_dob(row.get("birth_date")),
            })

    selected = {}
    lineage_rows = []
    conflict_n = 0
    for sid, rows in candidates.items():
        counts = Counter(r["position"] for r in rows)
        ranking = counts.most_common()
        if not ranking:
            continue
        if len(ranking) > 1 and ranking[0][1] == ranking[1][1]:
            conflict_n += 1
            continue
        pos = ranking[0][0]
        same = [r for r in rows if r["position"] == pos]
        gsis_values = {r["gsis_id"] for r in same if r["gsis_id"]}
        dob_values = {r["birth_date"] for r in same if r["birth_date"]}
        name_values = [r["name"] for r in same if r["name"]]
        rec = {
            "season": season,
            "sleeper_id": sid,
            "gsis_id": next(iter(gsis_values)) if len(gsis_values) == 1 else None,
            "position": pos,
            "name": name_values[0] if name_values else None,
            "birth_date": next(iter(dob_values)) if len(dob_values) == 1 else None,
            "source": f"nflverse_roster_{season}",
            "source_row_n": len(rows),
            "position_candidate_counts": dict(sorted(counts.items())),
            "position_conflict_resolved_by_strict_majority": len(counts) > 1,
        }
        selected[sid] = rec
        lineage_rows.append(rec)

    lineage_rows.sort(key=lambda x: x["sleeper_id"])
    return selected, lineage_rows, {
        "raw_row_n": raw_n,
        "supported_position_row_n": supported_n,
        "candidate_sleeper_id_n": len(candidates),
        "selected_sleeper_id_n": len(selected),
        "unresolved_position_tie_n": conflict_n,
    }


def score_season(
    season: int,
    lineage_dir: Path,
    out_path: Path,
) -> None:
    if season not in SEASONS:
        raise GateError(f"unsupported season: {season}")
    guard_contract()
    assets = load(lineage_dir / "lineage_assets_manifest.json")
    players_path = lineage_dir / "players.csv"
    dp_path = lineage_dir / "db_playerids.csv"
    roster_path = lineage_dir / f"roster_{season}.csv"

    if assets["players"]["sha256"] != sha256(players_path):
        raise GateError("players.csv lineage manifest hash mismatch")
    if assets["dynastyprocess"]["sha256"] != sha256(dp_path):
        raise GateError("DynastyProcess lineage manifest hash mismatch")
    roster_asset = assets["rosters"][str(season)]
    if roster_asset["sha256"] != sha256(roster_path):
        raise GateError(f"roster_{season}.csv lineage manifest hash mismatch")
    expected = ROSTER_ASSET_CONTRACT[season]
    for key in ("id", "size", "updated_at"):
        if roster_asset[key] != expected[key]:
            raise GateError(f"roster {season} asset contract drift: {key}")

    master = load_players_master(players_path)
    dp_sleeper_by_gsis = load_dp_sleeper_crosswalk(dp_path)
    roster_map, lineage_rows, lineage_diag = load_roster_lineage(
        roster_path, season, master, dp_sleeper_by_gsis
    )

    scoring = import_file(SCORE_PATH, f"v6_scoring_{season}")
    session = requests.Session()
    session.headers["User-Agent"] = (
        f"LOG-Trade-Calculator-Draft-Pick-FV-V6-Phase3-{season}/1.0"
    )

    totals = {}
    endpoint_meta = []
    nonempty_weeks = set()
    for week in WEEKS:
        obj, meta = request_json(
            session,
            f"{BASE}/stats/nfl/regular/{season}/{week}",
            allow_old_week18=(season <= 2020 and week == 18),
        )
        if obj:
            nonempty_weeks.add(week)
        active_n = 0
        mapped_n = 0
        for pid, stats in obj.items():
            if not isinstance(stats, dict):
                continue
            try:
                active = float(stats.get("gp") or 0) >= 1
            except (TypeError, ValueError):
                active = False
            if not active:
                continue
            sid = str(pid)
            pts = float(scoring.score_week(stats))
            rec = totals.setdefault(
                sid, {"games": 0, "season_total": 0.0}
            )
            rec["games"] += 1
            rec["season_total"] += pts
            active_n += 1
            if sid in roster_map:
                mapped_n += 1
        meta.update({
            "season": season,
            "week": week,
            "nonempty": bool(obj),
            "active_player_n": active_n,
            "season_position_mapped_active_n": mapped_n,
        })
        endpoint_meta.append(meta)
        print(
            f"{season} week {week}: raw={len(obj)} "
            f"active={active_n} mapped={mapped_n}",
            flush=True,
        )
        time.sleep(0.10)

    players = {}
    mapped_active_n = 0
    for sid, stat in totals.items():
        lineage = roster_map.get(sid)
        lineage_gsis = lineage.get("gsis_id") if lineage else None
        master_rec = (
            master["by_gsis"].get(lineage_gsis, {})
            if lineage_gsis else {}
        )
        if lineage:
            mapped_active_n += 1
        players[sid] = {
            "games": int(stat["games"]),
            "season_total": round(float(stat["season_total"]), 8),
            "season_position": lineage.get("position") if lineage else None,
            "season_position_source": (
                lineage.get("source") if lineage else None
            ),
            "gsis_id": (
                lineage.get("gsis_id") if lineage
                else master_rec.get("gsis_id")
            ),
            "name": (
                lineage.get("name") if lineage
                else master_rec.get("name")
            ),
            "birth_date": (
                master_rec.get("birth_date")
                or (lineage.get("birth_date") if lineage else None)
            ),
        }

    missing = sorted(required_weeks(season) - nonempty_weeks)
    payload = {
        "schema_version": 1,
        "stage": "phase3_calendar_season_score",
        "season": season,
        "generated_at_utc": now(),
        "research_only": True,
        "historical_player_outcomes_read": True,
        "calendar_season_stats_read": True,
        "holdout_2024_pick_identity_file_read": False,
        "holdout_2024_rookie_outcomes_scored": False,
        "candidate_fit_performed": False,
        "candidate_scores_computed": False,
        "candidate_selection_performed": False,
        "production_change_authorized": False,
        "required_week_n": len(required_weeks(season)),
        "nonempty_required_week_n": len(
            required_weeks(season) & nonempty_weeks
        ),
        "missing_required_weeks": missing,
        "availability_pass": not missing and bool(players),
        "active_player_n": len(players),
        "season_position_mapped_active_n": mapped_active_n,
        "season_position_mapping_coverage": (
            mapped_active_n / len(players) if players else 0.0
        ),
        "players": players,
        "lineage_rows": lineage_rows,
        "lineage_diagnostics": lineage_diag,
        "weekly_endpoints": endpoint_meta,
        "input_hashes": {
            "players.csv": sha256(players_path),
            "db_playerids.csv": sha256(dp_path),
            f"roster_{season}.csv": sha256(roster_path),
            SCORE_PATH.name: sha256(SCORE_PATH),
        },
    }
    write_json(out_path, payload)


def replacement_baselines(
    season_artifacts: dict[int, dict[str, Any]],
    ranks: dict[str, int],
) -> tuple[dict[int, Any], list[dict[str, Any]]]:
    baselines = {}
    universe = []
    for season in SEASONS:
        art = season_artifacts[season]
        by_pos = defaultdict(list)
        for sid, rec in art["players"].items():
            pos = rec.get("season_position")
            games = int(rec["games"])
            total = float(rec["season_total"])
            if pos not in POSITIONS:
                continue
            ppg = total / games if games else 0.0
            row = {
                "season": season,
                "sleeper_id": sid,
                "gsis_id": rec.get("gsis_id"),
                "name": rec.get("name"),
                "position": pos,
                "games": games,
                "season_total": round(total, 8),
                "ppg": round(ppg, 8),
                "position_source": rec.get("season_position_source"),
            }
            universe.append(row)
            if games >= 3:
                by_pos[pos].append(row)

        baselines[season] = {}
        for pos in POSITIONS:
            eligible = sorted(
                by_pos[pos],
                key=lambda x: (-x["ppg"], x["sleeper_id"]),
            )
            rank = int(ranks[pos])
            if len(eligible) < rank:
                raise GateError(
                    f"{season} {pos}: only {len(eligible)} eligible "
                    f"players for frozen replacement rank {rank}"
                )
            anchor = eligible[rank - 1]
            baselines[season][pos] = {
                "rank": rank,
                "replacement_ppg": float(anchor["ppg"]),
                "anchor_sleeper_id": anchor["sleeper_id"],
                "anchor_gsis_id": anchor.get("gsis_id"),
                "anchor_name": anchor.get("name"),
                "eligible_player_n": len(eligible),
                "position_lineage":
                    f"nflverse season roster {season}",
            }
    universe.sort(
        key=lambda x: (
            x["season"], x["position"], -x["ppg"], x["sleeper_id"]
        )
    )
    return baselines, universe


def build_target_metadata(
    picks: list[dict[str, Any]],
    master: dict[str, Any],
    season_artifacts: dict[int, dict[str, Any]],
) -> dict[tuple[int, str], dict[str, Any]]:
    targets = {}
    for row in picks:
        sid = stable_id(row.get("sleeper_id"))
        if not sid:
            continue
        y = int(row["draft_year"])
        key = (y, sid)

        draft_pos = norm_pos(row.get("draft_position"))
        pos_source = "frozen_phase2_draft_position" if draft_pos else None
        if not draft_pos:
            season_rec = season_artifacts[y]["players"].get(sid, {})
            draft_pos = season_rec.get("season_position")
            if draft_pos:
                pos_source = f"nflverse_roster_{y}_fallback"

        gsis = stable_id(row.get("gsis_id"))
        if not gsis:
            season_rec = season_artifacts[y]["players"].get(sid, {})
            gsis = stable_id(season_rec.get("gsis_id"))
        master_rec = master["by_gsis"].get(gsis, {}) if gsis else {}

        birth = master_rec.get("birth_date")
        dob_source = "pinned_nflverse_players" if birth else None
        if not birth:
            for season in SEASONS:
                srec = season_artifacts[season]["players"].get(sid, {})
                if srec.get("birth_date"):
                    birth = srec["birth_date"]
                    dob_source = f"nflverse_roster_{season}"
                    break

        candidate = {
            "sleeper_id": sid,
            "gsis_id": gsis or master_rec.get("gsis_id"),
            "name": row.get("name") or master_rec.get("name"),
            "position": draft_pos,
            "position_source": pos_source,
            "birth_date": birth,
            "birth_date_source": dob_source,
        }
        if key not in targets:
            targets[key] = candidate
        else:
            prev = targets[key]
            for f in ("position", "birth_date", "gsis_id"):
                a, b = prev.get(f), candidate.get(f)
                if a and b and a != b:
                    raise GateError(f"target metadata conflict {key} {f}")
                if not a and b:
                    prev[f] = b
            for f in ("position_source", "birth_date_source", "name"):
                if not prev.get(f) and candidate.get(f):
                    prev[f] = candidate[f]
    return targets


def score_targets(
    targets_meta: dict[tuple[int, str], dict[str, Any]],
    season_artifacts: dict[int, dict[str, Any]],
    baselines: dict[int, Any],
    hist: dict[str, Any],
    v5pre: dict[str, Any],
) -> dict[tuple[int, str], dict[str, Any]]:
    age_mod = import_file(AGE_PATH, "v6_age")
    bridge = v5pre["frozen_scale_bridge"]
    age_cfg = {
        "age_curve": bridge["age_curve"],
        "qb_post_peak_floor": float(bridge["qb_post_peak_floor"]),
        "lb_post_peak_decay_power":
            float(bridge["lb_post_peak_decay_power"]),
    }
    position_weight = {
        k: float(v)
        for k, v in hist["frozen_position_weights"].items()
    }
    prod = bridge["production_transform"]
    if {
        "zero_games_override", "intercept", "slope", "floor", "ceiling"
    } - set(prod):
        raise GateError("V5 production-transform contract incomplete")

    targets = {}
    for (draft_year, sid), meta in sorted(targets_meta.items()):
        pos = meta.get("position")
        birth = meta.get("birth_date")
        flags = []
        if pos not in POSITIONS:
            flags.append("missing_supported_draft_position")
        if not birth:
            flags.append("missing_birth_date")

        annual = []
        for season in range(draft_year, min(draft_year + 4, 2026)):
            if season not in season_artifacts:
                continue
            if pos not in POSITIONS:
                annual.append({
                    "season": season,
                    "status": "position_unavailable",
                })
                continue
            repl = baselines[season][pos]
            rec = season_artifacts[season]["players"].get(sid)
            games = int(rec["games"]) if rec else 0
            total = float(rec["season_total"]) if rec else 0.0
            denom = (
                float(repl["replacement_ppg"]) * sched_games(season)
            )
            if denom <= 0:
                raise GateError(
                    f"{season} {pos}: nonpositive replacement denominator"
                )
            realized = (
                float(prod["zero_games_override"])
                if games == 0
                else clamp(
                    float(prod["intercept"])
                    + float(prod["slope"]) * (total / denom),
                    float(prod["floor"]),
                    float(prod["ceiling"]),
                )
            )
            age = age_mult = annual_fv = None
            if birth:
                age = age_sep1(birth, season)
                age_mult = float(age_mod.age_multiplier(
                    pos, age, "Starter", realized, realized, age_cfg
                ))
                annual_fv = (
                    float(hist["O2_scale"]["base_scale"])
                    * position_weight[pos]
                    * age_mult
                    * realized
                )
            annual.append({
                "season": season,
                "games": games,
                "season_total": round(total, 8),
                "replacement_rank": repl["rank"],
                "replacement_ppg":
                    round(float(repl["replacement_ppg"]), 8),
                "scheduled_games": sched_games(season),
                "annual_surplus_o1":
                    round(max(0.0, total - denom), 8),
                "realized_prod_mult": round(realized, 10),
                "age_on_sep1": age,
                "age_multiplier":
                    round(age_mult, 10) if age_mult is not None else None,
                "annual_player_equivalent_fv":
                    round(annual_fv, 8)
                    if annual_fv is not None else None,
            })

        def horizon(n: int) -> dict[str, Any]:
            required = list(range(draft_year, draft_year + n))
            rows = [
                x for x in annual
                if int(x["season"]) in required
            ]
            mature = all(s in SEASONS for s in required)
            if not mature or len(rows) != n:
                return {
                    "horizon_years": n,
                    "required_seasons": required,
                    "mature": False,
                    "O1": None,
                    "O2": None,
                }
            o1_ready = all(
                x.get("annual_surplus_o1") is not None for x in rows
            )
            o2_ready = all(
                x.get("annual_player_equivalent_fv") is not None
                for x in rows
            )
            return {
                "horizon_years": n,
                "required_seasons": required,
                "mature": True,
                "O1": (
                    round(sum(x["annual_surplus_o1"] for x in rows), 8)
                    if o1_ready else None
                ),
                "O2": (
                    round(
                        sum(x["annual_player_equivalent_fv"] for x in rows)
                        / n,
                        8,
                    )
                    if o2_ready else None
                ),
            }

        h2, h3, h4 = horizon(2), horizon(3), horizon(4)
        targets[(draft_year, sid)] = {
            **meta,
            "draft_year": draft_year,
            "status_flags": flags,
            "annual": annual,
            "H2": h2,
            "H3": h3,
            "H4": h4,
            "primary_o1_ready":
                h3["mature"] and h3["O1"] is not None,
            "primary_o2_ready":
                h3["mature"] and not flags and h3["O2"] is not None,
        }
    return targets


def aggregate(
    season_dir: Path,
    lineage_dir: Path,
) -> None:
    state = guard_contract()
    picks = read_jsonl(PICKS)
    if len(picks) != 17915:
        raise GateError(f"development pick corpus drift: {len(picks)}")
    if state["p2m"]["output_hashes"][PICKS.name] != sha256(PICKS):
        raise GateError("development pick corpus hash drift")

    # The 2024 holdout pick corpus is intentionally not named or opened here.
    # Calendar-season 2024/2025 league-wide NFL stats are needed for the
    # preregistered H3/H4 outcomes of the 2022/2023 development classes.
    season_artifacts = {}
    for season in SEASONS:
        path = season_dir / f"season_{season}.json"
        if not path.exists():
            raise GateError(f"missing season artifact: {path}")
        art = load(path)
        if int(art["season"]) != season:
            raise GateError(f"wrong season artifact: {path}")
        if art["availability_pass"] is not True:
            raise GateError(
                f"season {season} availability failed: "
                f"{art['missing_required_weeks']}"
            )
        if art["holdout_2024_pick_identity_file_read"] is not False:
            raise GateError("2024 holdout pick identity firewall violated")
        if art["holdout_2024_rookie_outcomes_scored"] is not False:
            raise GateError("2024 holdout rookie outcomes were scored")
        if art["candidate_fit_performed"] is not False:
            raise GateError("candidate fitting occurred in season worker")
        season_artifacts[season] = art

    assets = load(lineage_dir / "lineage_assets_manifest.json")
    if assets["players"]["sha256"] != sha256(lineage_dir / "players.csv"):
        raise GateError("players lineage hash mismatch at aggregate")
    if assets["dynastyprocess"]["sha256"] != sha256(
        lineage_dir / "db_playerids.csv"
    ):
        raise GateError("DynastyProcess lineage hash mismatch at aggregate")
    for season in SEASONS:
        if assets["rosters"][str(season)]["sha256"] != sha256(
            lineage_dir / f"roster_{season}.csv"
        ):
            raise GateError(f"roster {season} lineage hash mismatch")

    master = load_players_master(lineage_dir / "players.csv")
    dp_sleeper_by_gsis = load_dp_sleeper_crosswalk(
        lineage_dir / "db_playerids.csv"
    )

    # Build exact season position lineage used for replacement pools.
    season_lineage_rows = []
    lineage_diagnostics = {}
    for season in SEASONS:
        _, rows, diag = load_roster_lineage(
            lineage_dir / f"roster_{season}.csv",
            season,
            master,
            dp_sleeper_by_gsis,
        )
        for row in rows:
            season_lineage_rows.append({
                "record_type": "replacement_pool_season_lineage",
                **row,
            })
        lineage_diagnostics[str(season)] = diag

    hist = state["pre"]["historical_outcome_contract"]
    ranks = {
        k: int(v) for k, v in hist["frozen_replacement_ranks"].items()
    }
    if set(ranks) != set(POSITIONS):
        raise GateError("replacement rank positions drift")

    baselines, universe = replacement_baselines(season_artifacts, ranks)
    write_jsonl(OUT_UNIVERSE, universe)

    target_meta = build_target_metadata(
        picks, master, season_artifacts
    )

    # Freeze the exact target draft-position and DOB choices too.  This makes
    # the complete player-metadata lineage independently auditable instead of
    # leaving DOB provenance implicit inside the scored occurrence rows.
    target_lineage_rows = [
        {
            "record_type": "target_draft_identity",
            "draft_year": draft_year,
            **meta,
        }
        for (draft_year, _sid), meta in sorted(target_meta.items())
    ]
    lineage_rows = season_lineage_rows + target_lineage_rows
    lineage_rows.sort(
        key=lambda x: (
            x["record_type"],
            int(x.get("season") or x.get("draft_year") or 0),
            str(x.get("sleeper_id") or ""),
        )
    )
    write_jsonl(OUT_LINEAGE, lineage_rows)

    targets = score_targets(
        target_meta,
        season_artifacts,
        baselines,
        hist,
        state["v5pre"],
    )

    out_rows = []
    by_year_cell = defaultdict(
        lambda: {"n": 0, "sid": 0, "o1": 0, "o2": 0, "h4": 0}
    )
    by_year = defaultdict(
        lambda: {"n": 0, "sid": 0, "o1": 0, "o2": 0, "h4": 0}
    )

    for row in picks:
        y = int(row["draft_year"])
        sid = stable_id(row.get("sleeper_id"))
        out = targets.get((y, sid)) if sid else None
        cell = row["cell"]
        o1 = bool(out and out["primary_o1_ready"])
        o2 = bool(out and out["primary_o2_ready"])
        h4 = bool(
            out and out["H4"]["mature"] and out["H4"]["O2"] is not None
        )

        for bucket in (by_year_cell[(y, cell)], by_year[y]):
            bucket["n"] += 1
            if sid:
                bucket["sid"] += 1
            if o1:
                bucket["o1"] += 1
            if o2:
                bucket["o2"] += 1
            if h4:
                bucket["h4"] += 1

        rec = {
            "draft_year": y,
            "league_id": str(row["league_id"]),
            "league_idp": bool(row.get("league_idp", False)),
            "source_origin": row.get("source_origin"),
            "overall_slot": int(row["overall_slot"]),
            "round": int(row["round"]),
            "within_round_pick": int(row["within_round_pick"]),
            "tier": row["tier"],
            "cell": cell,
            "split": "development",
            "mfl_player_id": row.get("mfl_player_id"),
            "gsis_id": row.get("gsis_id"),
            "sleeper_id": sid,
            "stable_player_key": row.get("stable_player_key"),
            "name": row.get("name"),
            "position": out.get("position") if out else None,
            "position_source": (
                out.get("position_source") if out else None
            ),
            "cell_weight_v6_1": row["cell_weight_v6_1"],
            "source_weight_r1_r4_v6_1":
                row["source_weight_r1_r4_v6_1"],
            "primary_o1_ready": o1,
            "primary_o2_ready": o2,
            "birth_date": out.get("birth_date") if out else None,
            "birth_date_source":
                out.get("birth_date_source") if out else None,
            "status_flags": (
                out.get("status_flags")
                if out else ["missing_sleeper_identity"]
            ),
            "H2": out.get("H2") if out else None,
            "H3": out.get("H3") if out else None,
            "H4": out.get("H4") if out else None,
            "annual": out.get("annual") if out else None,
        }
        out_rows.append(rec)

    out_rows.sort(
        key=lambda x: (
            x["draft_year"], int(x["league_id"]), x["overall_slot"]
        )
    )
    write_jsonl(OUT_DEV, out_rows)

    class_availability = {}
    all_h3_classes = True
    for y in DRAFT_YEARS:
        req = [y, y + 1, y + 2]
        passed = all(
            season_artifacts[s]["availability_pass"] for s in req
        )
        class_availability[str(y)] = {
            "required_H3_seasons": req,
            "pass": passed,
        }
        all_h3_classes = all_h3_classes and passed

    cell_diag = {}
    gate = all_h3_classes
    for y in DRAFT_YEARS:
        for cell in CELLS:
            d = by_year_cell[(y, cell)]
            o1_cov = d["o1"] / d["n"] if d["n"] else 0.0
            o2_cov = d["o2"] / d["n"] if d["n"] else 0.0
            passed = o2_cov >= MIN_READY
            gate = gate and passed
            cell_diag[f"{y}:{cell}"] = {
                "retained_occurrence_n": d["n"],
                "sleeper_identity_ready_n": d["sid"],
                "primary_o1_ready_n": d["o1"],
                "primary_o2_ready_n": d["o2"],
                "mature_h4_o2_ready_n": d["h4"],
                "primary_o1_ready_coverage": o1_cov,
                "primary_o2_ready_coverage": o2_cov,
                "minimum_required": MIN_READY,
                "pass": passed,
            }

    year_diag = {}
    for y in DRAFT_YEARS:
        d = by_year[y]
        year_diag[str(y)] = {
            "retained_occurrence_n": d["n"],
            "sleeper_identity_coverage": d["sid"] / d["n"],
            "primary_o1_ready_coverage": d["o1"] / d["n"],
            "primary_o2_ready_coverage": d["o2"] / d["n"],
            "mature_h4_o2_ready_coverage": d["h4"] / d["n"],
            "H4_mature_for_class": y <= 2022,
        }

    overall_o2 = (
        sum(d["o2"] for d in by_year.values()) / len(out_rows)
        if out_rows else 0.0
    )
    gate = gate and overall_o2 >= MIN_READY

    decision = (
        "PASS_V6_1_PHASE3_R1_R4_HISTORICAL_OUTCOME_HARVEST_"
        "DEVELOPMENT_SELECTION_AUTHORIZED_NEXT_STAGE"
        if gate
        else
        "STOP_V6_1_PHASE3_OUTCOME_AVAILABILITY_OR_COMPLETENESS_GATE"
    )
    generated = now()

    source_manifest = {
        "schema_version": 1,
        "stage": "phase3_r1_r4_historical_outcome_harvest",
        "generated_at_utc": generated,
        "provider": "Sleeper historical weekly NFL stats",
        "calendar_seasons_read": list(SEASONS),
        "calendar_2024_2025_leaguewide_stats_read": True,
        "calendar_2024_2025_reason": (
            "Required by preregistered H3/H4 development horizons for "
            "2022 and 2023 draft classes and by season-specific "
            "replacement baselines."
        ),
        "holdout_2024_pick_identity_file_read": False,
        "holdout_2024_rookie_outcomes_scored": False,
        "holdout_2024_pick_outcomes_remain_sealed": True,
        "season_availability": {
            str(s): {
                "availability_pass": season_artifacts[s]["availability_pass"],
                "missing_required_weeks":
                    season_artifacts[s]["missing_required_weeks"],
                "active_player_n": season_artifacts[s]["active_player_n"],
                "season_position_mapped_active_n":
                    season_artifacts[s][
                        "season_position_mapped_active_n"
                    ],
                "season_position_mapping_coverage":
                    season_artifacts[s][
                        "season_position_mapping_coverage"
                    ],
            }
            for s in SEASONS
        },
        "weekly_endpoints": [
            m
            for s in SEASONS
            for m in season_artifacts[s]["weekly_endpoints"]
        ],
        "nflverse_lineage_assets": assets,
        "season_position_lineage_diagnostics": lineage_diagnostics,
        "frozen_lineage_record_counts": {
            "replacement_pool_season_lineage":
                len(season_lineage_rows),
            "target_draft_identity":
                len(target_lineage_rows),
            "total": len(lineage_rows),
        },
        "replacement_baselines": {
            str(s): baselines[s] for s in SEASONS
        },
        "position_lineage_rule": (
            "Replacement pool position is season-appropriate nflverse "
            "roster position mapped to Sleeper ID. Current Sleeper "
            "position is never used for historical replacement pools."
        ),
        "target_position_rule": (
            "Prefer frozen Phase-2 draft position; if absent, use "
            "nflverse roster position from the rookie's draft year only."
        ),
        "dob_rule": (
            "Pinned nflverse players.csv birth date first; historical "
            "nflverse roster birth date only as fallback."
        ),
        "scoring_source": str(SCORE_PATH.relative_to(ROOT)),
        "scoring_source_sha256": sha256(SCORE_PATH),
        "age_multiplier_source": str(AGE_PATH.relative_to(ROOT)),
        "age_multiplier_source_sha256": sha256(AGE_PATH),
        "age_curve_contract_source": str(V5_PRE.relative_to(ROOT)),
        "age_curve_contract_source_sha256": sha256(V5_PRE),
        "candidate_fit_performed": False,
        "candidate_scores_computed": False,
        "candidate_selection_performed": False,
        "production_change_authorized": False,
    }
    write_json(OUT_SOURCE, source_manifest)

    summary = {
        "schema_version": 1,
        "study_id":
            "draft-pick-fv-v6-r1-r4-structural-continuity",
        "stage": "phase3_r1_r4_historical_outcome_harvest",
        "status": (
            "HISTORICAL_OUTCOME_HARVEST_PASS"
            if gate else "HISTORICAL_OUTCOME_HARVEST_STOP"
        ),
        "generated_at_utc": generated,
        "decision": decision,
        "research_only": True,
        "historical_player_outcomes_read": True,
        "historical_outcomes_harvested": True,
        "calendar_2024_2025_leaguewide_stats_read": True,
        "holdout_2024_pick_identity_file_read": False,
        "holdout_2024_rookie_outcomes_scored": False,
        "holdout_2024_pick_outcomes_remain_sealed": True,
        "candidate_fit_performed": False,
        "candidate_scores_computed": False,
        "candidate_selection_performed": False,
        "market_or_ktc_values_read": False,
        "package_vote_data_read": False,
        "production_change_authorized": False,
        "source_population_changed": False,
        "source_search_performed": False,
        "retained_pick_occurrence_n": len(picks),
        "development_outcome_occurrence_n": len(out_rows),
        "unique_outcome_identity_n": len(targets),
        "all_six_H3_classes_available": all_h3_classes,
        "class_availability": class_availability,
        "outcome_readiness_gate": {
            "pass": gate,
            "minimum_primary_o2_occurrence_coverage": MIN_READY,
            "overall_primary_o2_ready_coverage": overall_o2,
            "by_year_cell": cell_diag,
            "by_year": year_diag,
        },
        "position_lineage_hardening": {
            "season_specific_replacement_positions": True,
            "current_sleeper_position_used_for_replacement_pool": False,
            "lineage_artifact": OUT_LINEAGE.name,
            "lineage_artifact_sha256": sha256(OUT_LINEAGE),
        },
        "development_firewall": {
            "development_outcomes_file": OUT_DEV.name,
            "2024_holdout_pick_file_read": False,
            "2024_holdout_outcomes_scored": False,
            "next_development_selection_workflow_may_read":
                OUT_DEV.name,
        },
        "next_stage_authorized": gate,
        "next_stage": (
            "draft-pick-fv-v6-phase4-loyo-development-selection"
            if gate else None
        ),
        "input_hashes": {
            PRE.name: sha256(PRE),
            AMEND.name: sha256(AMEND),
            PICKS.name: sha256(PICKS),
            P2_SUM.name: sha256(P2_SUM),
            P2_MAN.name: sha256(P2_MAN),
            V5_PRE.name: sha256(V5_PRE),
            SCORE_PATH.name: sha256(SCORE_PATH),
            AGE_PATH.name: sha256(AGE_PATH),
            "lineage_assets_manifest.json":
                sha256(lineage_dir / "lineage_assets_manifest.json"),
        },
        "source_manifest_sha256": sha256(OUT_SOURCE),
    }
    write_json(OUT_SUM, summary)

    md = [
        "# Draft Pick FV V6.1 — Phase 3 R1–R4 Historical Outcome Harvest",
        "",
        f"**Decision:** `{decision}`",
        "",
        f"- Development occurrences: **{len(out_rows)}**",
        f"- Unique outcome identities: **{len(targets)}**",
        f"- Overall H3 O2-ready coverage: **{overall_o2:.2%}**",
        f"- All six draft classes H3-available: "
        f"**{'Yes' if all_h3_classes else 'No'}**",
        "",
        "## Position-lineage hardening",
        "",
        "- Replacement pools use season-specific nflverse roster positions: **Yes**",
        "- Current 2026 Sleeper position used for historical replacement pools: **No**",
        "- Exact position/DOB lineage frozen as a separate artifact: **Yes**",
        "",
        "## 2024 holdout firewall",
        "",
        "- 2024 rookie holdout pick corpus read: **No**",
        "- 2024 rookie holdout outcomes scored: **No**",
        "- 2024/2025 league-wide calendar stats read: **Yes**, only because "
        "they are required for the already-preregistered 2022/2023 "
        "development horizons and replacement baselines.",
        "",
        "## Other firewalls",
        "",
        "- Candidate fitting performed: **No**",
        "- Candidate scoring performed: **No**",
        "- KTC/market values read: **No**",
        "- Package-vote evidence read: **No**",
        "- Production change authorized: **No**",
        "",
        "## Next step",
        "",
        (
            "Run preregistered leave-one-draft-year-out development "
            "selection using only the frozen development outcome file."
            if gate else
            "Stop before candidate fitting/selection and diagnose the "
            "outcome readiness failure."
        ),
        "",
    ]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "study_id": summary["study_id"],
        "stage": summary["stage"],
        "status": summary["status"],
        "generated_at_utc": generated,
        "decision": decision,
        "historical_player_outcomes_read": True,
        "holdout_2024_pick_identity_file_read": False,
        "holdout_2024_rookie_outcomes_scored": False,
        "holdout_2024_pick_outcomes_remain_sealed": True,
        "candidate_fit_performed": False,
        "candidate_scores_computed": False,
        "candidate_selection_performed": False,
        "production_change_authorized": False,
        "outcome_readiness_gate_pass": gate,
        "development_selection_authorized_next_stage": gate,
        "input_hashes": summary["input_hashes"],
        "output_hashes": {
            OUT_SOURCE.name: sha256(OUT_SOURCE),
            OUT_LINEAGE.name: sha256(OUT_LINEAGE),
            OUT_UNIVERSE.name: sha256(OUT_UNIVERSE),
            OUT_DEV.name: sha256(OUT_DEV),
            OUT_SUM.name: sha256(OUT_SUM),
            OUT_MD.name: sha256(OUT_MD),
        },
        "canonical_summary_sha256": canonical_sha(summary),
        "next_stage": summary["next_stage"],
    }
    write_json(OUT_MAN, manifest)

    print(f"DECISION={decision}")
    print(f"development_occurrences={len(out_rows)}")
    print(f"unique_outcome_identities={len(targets)}")
    print(f"overall_H3_O2_ready={overall_o2:.6f}")
    print("2024_HOLDOUT_PICK_OUTCOMES_REMAIN_SEALED=true")


def selftest() -> None:
    assert norm_pos("DE") == "DL"
    assert norm_pos("CB") == "DB"
    assert norm_pos("FB") == "RB"
    assert norm_pos("K") is None
    assert sched_games(2020) == 16
    assert sched_games(2021) == 17
    assert required_weeks(2020) == set(range(1, 18))
    assert required_weeks(2021) == set(range(1, 19))
    assert valid_dob("2000-02-29") == "2000-02-29"
    assert age_sep1("2000-09-02", 2024) == 23
    assert clamp(2.0, 0.15, 1.55) == 1.55

    # Synthetic replacement ranking.
    arts = {}
    for season in SEASONS:
        players = {}
        for pos_i, pos in enumerate(POSITIONS):
            for n in range(1, 40):
                sid = f"{season}-{pos}-{n}"
                players[sid] = {
                    "games": 10,
                    "season_total": float(1000 - n - pos_i),
                    "season_position": pos,
                    "season_position_source":
                        f"nflverse_roster_{season}",
                    "gsis_id": f"G-{sid}",
                    "name": sid,
                    "birth_date": "1995-01-01",
                }
        arts[season] = {"players": players}
    ranks = {"QB":29,"RB":25,"WR":28,"TE":11,"DL":16,"LB":28,"DB":22}
    baselines, universe = replacement_baselines(arts, ranks)
    assert len(universe) == len(SEASONS) * len(POSITIONS) * 39
    assert baselines[2018]["QB"]["rank"] == 29
    assert baselines[2025]["TE"]["rank"] == 11

    # H3/H4 maturation boundary is intentional: 2022 has H4 through 2025,
    # 2023 does not because partial 2026 is forbidden.
    assert all(s in SEASONS for s in (2022, 2023, 2024, 2025))
    assert not all(s in SEASONS for s in (2023, 2024, 2025, 2026))
    print("PASS: V6.1 Phase 3 historical-outcome self-test")


def guard_only() -> None:
    state = guard_contract()
    if state["p2m"]["outcome_ingestion_authorized_next_stage"] is not True:
        raise GateError("historical outcomes not authorized")
    print("PASS: V6.1 Phase 3 live predecessor contract guard")
    print("DEVELOPMENT_OCCURRENCES=17915")
    print("2024_HOLDOUT_OUTCOME_AUTHORIZED=false")


def check_outputs() -> None:
    s = load(OUT_SUM)
    m = load(OUT_MAN)
    allowed = {
        "PASS_V6_1_PHASE3_R1_R4_HISTORICAL_OUTCOME_HARVEST_"
        "DEVELOPMENT_SELECTION_AUTHORIZED_NEXT_STAGE",
        "STOP_V6_1_PHASE3_OUTCOME_AVAILABILITY_OR_COMPLETENESS_GATE",
    }
    if s["decision"] not in allowed:
        raise GateError("unexpected Phase 3 decision")
    if m["decision"] != s["decision"]:
        raise GateError("manifest decision mismatch")
    if s["retained_pick_occurrence_n"] != 17915:
        raise GateError("retained occurrence count mismatch")
    if s["development_outcome_occurrence_n"] != 17915:
        raise GateError("development output count mismatch")
    if s["holdout_2024_pick_identity_file_read"] is not False:
        raise GateError("2024 holdout pick corpus was read")
    if s["holdout_2024_rookie_outcomes_scored"] is not False:
        raise GateError("2024 holdout rookie outcomes were scored")
    if s["position_lineage_hardening"][
        "current_sleeper_position_used_for_replacement_pool"
    ] is not False:
        raise GateError("current Sleeper position contaminated replacement pools")
    for obj in (s, m):
        for key in (
            "candidate_fit_performed",
            "candidate_scores_computed",
            "candidate_selection_performed",
            "production_change_authorized",
        ):
            if obj[key] is not False:
                raise GateError(f"output firewall violation: {key}")
    for name, expected in m["output_hashes"].items():
        path = V6 / name
        if sha256(path) != expected:
            raise GateError(f"output hash mismatch: {name}")
    print("PASS: V6.1 Phase 3 frozen outputs validated")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--guard", action="store_true")
    ap.add_argument("--season", type=int)
    ap.add_argument("--lineage-dir")
    ap.add_argument("--season-dir")
    ap.add_argument("--out")
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if args.guard:
        guard_only()
        return
    if args.season is not None:
        if not args.lineage_dir or not args.out:
            raise SystemExit("--season requires --lineage-dir and --out")
        score_season(
            args.season,
            Path(args.lineage_dir),
            Path(args.out),
        )
        return
    if args.aggregate:
        if not args.lineage_dir or not args.season_dir:
            raise SystemExit(
                "--aggregate requires --lineage-dir and --season-dir"
            )
        aggregate(
            Path(args.season_dir),
            Path(args.lineage_dir),
        )
        return
    if args.check:
        check_outputs()
        return
    raise SystemExit(
        "choose --selftest, --guard, --season, --aggregate, or --check"
    )


if __name__ == "__main__":
    main()

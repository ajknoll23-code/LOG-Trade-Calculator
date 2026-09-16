#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

ROOT = Path.cwd()
V3 = ROOT / "research" / "draft-pick-fv-v3"
V4 = ROOT / "research" / "draft-pick-fv-v4"

PREREG = V4 / "source_recovery_preregistration_v4.json"
PREREG_MAN = V4 / "source_recovery_manifest_v4.json"
V3_CLOSURE = V3 / "v3_closure.json"
V3_CONTAM = V3 / "rookie_scope_contamination_audit_v3.json"

SCRIPT_OUT = V4 / "draft_pick_fv_v4_clean_source_recovery.py"
JSON_OUT = V4 / "clean_source_recovery_v4.json"
MD_OUT = V4 / "clean_source_recovery_v4.md"
MAN_OUT = V4 / "clean_source_recovery_manifest_v4.json"

YEARS = [2018, 2019, 2020, 2021, 2022, 2023]
BASE = "https://api.myfantasyleague.com"

DP_SHA256 = "0174ea890e71d33fa0afc1b846ce1c92273542278a287b6bd52c3a4aa5edce73"
NFLVERSE_SHA256 = "507f8cf03ffc8a82b841212582000163eb713ced15c9f83f851afb42da0af259"

DP_COLUMNS = [
    "mfl_id", "gsis_id", "sleeper_id", "name",
    "merge_name", "position", "draft_year",
]
NFLVERSE_COLUMNS = [
    "gsis_id", "display_name", "position", "rookie_season",
]

SENTINELS = {"", "----", "0000", "0", "NA", "N/A", "NULL", "NONE", "NAN"}

class RecoveryError(RuntimeError):
    pass

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def as_list(x: Any) -> list[Any]:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]

def safe_int(x: Any) -> int | None:
    try:
        s = str(x).strip()
    except Exception:
        return None
    if not re.fullmatch(r"[+-]?\d+", s):
        return None
    try:
        return int(s)
    except ValueError:
        return None

def stable_id(x: Any) -> str | None:
    s = str(x or "").strip()
    if not s or s.upper() in SENTINELS:
        return None
    return s

def norm(x: Any) -> str:
    return re.sub(r"\s+", " ", str(x or "").strip()).lower()

def clean_name(x: Any) -> str:
    s = str(x or "").strip()
    if "," in s:
        bits = [z.strip() for z in s.split(",", 1)]
        if len(bits) == 2 and bits[0] and bits[1]:
            s = bits[1] + " " + bits[0]
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", " ", s)
    s = s.replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def norm_position(x: Any) -> str:
    s = str(x or "").strip().upper()
    aliases = {
        "DE": "DL", "DT": "DL", "NT": "DL", "EDGE": "DL",
        "ILB": "LB", "OLB": "LB",
        "CB": "DB", "S": "DB", "FS": "DB", "SS": "DB",
    }
    return aliases.get(s, s)

def explicit_devy_marker(name: Any) -> bool:
    n = norm(name)
    return bool(
        re.search(r"\bdevy\b", n)
        or re.search(r"\bdevy pick\b", n)
        or re.search(r"\bdevy placeholder\b", n)
        or re.search(r"\bplaceholder devy\b", n)
    )

def api_url(year: int, endpoint: str, **params: Any) -> str:
    q = {"TYPE": endpoint, "JSON": 1}
    q.update({k: v for k, v in params.items() if v is not None})
    return f"{BASE}/{year}/export?" + urlencode(q)

def get_json(
    session: requests.Session,
    url: str,
    retries: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=45)
            r.raise_for_status()
            obj = r.json()
            if not isinstance(obj, dict):
                raise RecoveryError("non-object JSON")
            time.sleep(sleep_seconds)
            return obj
        except (
            requests.exceptions.RequestException,
            ValueError,
            RecoveryError,
        ) as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(min(20.0, 2.0 * (attempt + 1)))
    raise RecoveryError(f"{url}: {type(last).__name__}: {last}")

def search_ids(data: dict[str, Any]) -> list[str]:
    leagues = data.get("leagues")
    if not isinstance(leagues, dict):
        return []
    out = []
    for row in as_list(leagues.get("league")):
        if not isinstance(row, dict):
            continue
        lid = row.get("id") or row.get("league_id") or row.get("leagueId")
        if lid is not None:
            out.append(str(lid))
    return out

def league_obj(data: dict[str, Any]) -> dict[str, Any] | None:
    x = data.get("league")
    return x if isinstance(x, dict) else None

def franchise_count(lg: dict[str, Any]) -> int | None:
    f = lg.get("franchises")
    return safe_int(f.get("count")) if isinstance(f, dict) else None

def qb_limit(lg: dict[str, Any]) -> str | None:
    starters = lg.get("starters")
    if not isinstance(starters, dict):
        return None
    for row in as_list(starters.get("position")):
        if (
            isinstance(row, dict)
            and str(row.get("name", "")).upper() == "QB"
        ):
            v = str(row.get("limit", "")).strip()
            return v or None
    return None

def keeper_state(lg: dict[str, Any]) -> str:
    if (
        "keeperType" not in lg
        or lg.get("keeperType") is None
        or norm(lg.get("keeperType")) == ""
    ):
        return "missing"
    v = norm(lg.get("keeperType"))
    if v == "dynasty":
        return "dynasty"
    if v == "keeper":
        return "keeper"
    if v in {"none", "redraft"}:
        return "none"
    return f"other:{v}"

def rookie_pool(lg: dict[str, Any]) -> bool:
    return norm(lg.get("draftPlayerPool")).startswith("rook")

def is_idp(lg: dict[str, Any]) -> bool:
    starters = lg.get("starters")
    if not isinstance(starters, dict):
        return False
    x = starters.get("idp_starters")
    if isinstance(x, str):
        return bool(x.strip())
    return bool(x)

def qualifier(lg: dict[str, Any]) -> tuple[bool, str]:
    if franchise_count(lg) != 12:
        return False, "not_12_team"
    if qb_limit(lg) not in {"1-2", "2"}:
        return False, "not_superflex"
    if not rookie_pool(lg):
        return False, "not_rookie_pool"
    ks = keeper_state(lg)
    if ks == "dynasty":
        return True, "explicit_dynasty"
    if ks == "missing":
        return True, "validated_missing_keeper_proxy"
    return False, f"observed_non_dynasty:{ks}"

def obvious_mock_name(name: Any) -> bool:
    n = norm(name)
    return any(tok in n for tok in ("mock", "draft master", "draftmasters"))

def draft_units(data: dict[str, Any]) -> list[list[dict[str, Any]]]:
    root = data.get("draftResults")
    if not isinstance(root, dict):
        return []
    units = []
    for unit in as_list(root.get("draftUnit")):
        if not isinstance(unit, dict):
            continue
        picks = [
            x for x in as_list(unit.get("draftPick"))
            if isinstance(x, dict)
        ]
        if picks:
            units.append(picks)
    return units

def canonical_pick_rows(units: list[list[dict[str, Any]]]) -> dict[str, Any]:
    # V4 conservatively audits every returned draft unit. This prevents
    # a league from hiding startup/devy selections in a second unit.
    rows = []
    duplicate_slots = 0
    seen_slots = set()
    invalid_pick_number = 0
    blank_player = 0

    for unit_index, picks in enumerate(units):
        for p in picks:
            rnd = safe_int(p.get("round"))
            pick = safe_int(p.get("pick"))
            pid = stable_id(p.get("player"))
            if rnd is None or pick is None or rnd < 1 or rnd > 6:
                continue
            if pick < 1 or pick > 12:
                invalid_pick_number += 1
                continue
            if pid is None:
                blank_player += 1
                continue
            slot = (rnd - 1) * 12 + pick
            slot_key = (rnd, pick)
            if slot_key in seen_slots:
                duplicate_slots += 1
            else:
                seen_slots.add(slot_key)
            rows.append({
                "unit_index": unit_index,
                "round": rnd,
                "pick": pick,
                "overall_slot": slot,
                "mfl_player_id": pid,
            })

    # Completeness is based on the union of canonical nonblank slots
    # returned by the league's draftResults. Any duplicate unit cannot
    # manufacture a missing slot because completeness uses unique slots.
    filled_by_round = {
        str(r): sum((r, p) in seen_slots for p in range(1, 13))
        for r in range(1, 7)
    }

    def full(n: int) -> bool:
        return all(filled_by_round[str(r)] == 12 for r in range(1, n + 1))

    return {
        "rows": rows,
        "filled_by_round": filled_by_round,
        "full4": full(4),
        "full5": full(5),
        "full6": full(6),
        "draft_unit_n": len(units),
        "duplicate_slot_occurrence_n": duplicate_slots,
        "invalid_pick_number_n": invalid_pick_number,
        "blank_player_occurrence_n": blank_player,
    }

def parse_players(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    root = data.get("players")
    if not isinstance(root, dict):
        return {}
    out = {}
    for row in as_list(root.get("player")):
        if not isinstance(row, dict):
            continue
        pid = stable_id(row.get("id") or row.get("player_id"))
        if not pid:
            continue
        out[pid] = {
            "mfl_player_id": pid,
            "name": stable_id(row.get("name")),
            "position": stable_id(row.get("position")),
            "draft_year": safe_int(row.get("draft_year")),
            "team": stable_id(row.get("team")),
            "status": stable_id(row.get("status")),
        }
    return out

def league_scoped_players(
    session: requests.Session,
    year: int,
    league_id: str,
    player_ids: list[str],
    retries: int,
    sleep_seconds: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    ids = sorted(set(player_ids), key=lambda x: (len(x), x))
    found: dict[str, dict[str, Any]] = {}
    targeted_error = None
    full_error = None

    # Chunk targeted queries so URLs remain bounded.
    for start in range(0, len(ids), 100):
        chunk = ids[start:start + 100]
        try:
            data = get_json(
                session,
                api_url(
                    year, "players",
                    L=league_id,
                    DETAILS=1,
                    PLAYERS=",".join(chunk),
                ),
                retries,
                sleep_seconds,
            )
            found.update(parse_players(data))
        except RecoveryError as exc:
            targeted_error = str(exc)
            break

    missing = [pid for pid in ids if pid not in found]
    if missing:
        try:
            data = get_json(
                session,
                api_url(year, "players", L=league_id, DETAILS=1),
                retries,
                sleep_seconds,
            )
            full = parse_players(data)
            for pid in missing:
                if pid in full:
                    found[pid] = full[pid]
        except RecoveryError as exc:
            full_error = str(exc)

    return found, {
        "requested_id_n": len(ids),
        "found_id_n": sum(pid in found for pid in ids),
        "missing_id_n": sum(pid not in found for pid in ids),
        "targeted_error": targeted_error,
        "full_error": full_error,
    }

def load_identity_index(
    dp_path: Path,
    nv_path: Path,
) -> dict[str, Any]:
    if sha256(dp_path) != DP_SHA256:
        raise RecoveryError("DynastyProcess identity source hash mismatch")
    if sha256(nv_path) != NFLVERSE_SHA256:
        raise RecoveryError("nflverse identity source hash mismatch")

    by_name_pos: dict[tuple[str, str], set[int]] = defaultdict(set)

    with dp_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {c: i for i, c in enumerate(header)}
        missing = [c for c in DP_COLUMNS if c not in idx]
        if missing:
            raise RecoveryError(f"DP missing identity columns: {missing}")
        for raw in reader:
            if len(raw) < len(header):
                raw += [""] * (len(header) - len(raw))
            name = raw[idx["merge_name"]] or raw[idx["name"]]
            pos = raw[idx["position"]]
            dy = safe_int(raw[idx["draft_year"]])
            nm = clean_name(name)
            np = norm_position(pos)
            if nm and np and dy is not None:
                by_name_pos[(nm, np)].add(int(dy))

    with nv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {c: i for i, c in enumerate(header)}
        missing = [c for c in NFLVERSE_COLUMNS if c not in idx]
        if missing:
            raise RecoveryError(f"nflverse missing identity columns: {missing}")
        for raw in reader:
            if len(raw) < len(header):
                raw += [""] * (len(header) - len(raw))
            nm = clean_name(raw[idx["display_name"]])
            np = norm_position(raw[idx["position"]])
            dy = safe_int(raw[idx["rookie_season"]])
            gsis = stable_id(raw[idx["gsis_id"]])
            if gsis and nm and np and dy is not None:
                by_name_pos[(nm, np)].add(int(dy))

    return {
        "candidate_years_by_name_pos": by_name_pos,
        "dynastyprocess_sha256": sha256(dp_path),
        "nflverse_sha256": sha256(nv_path),
    }

def classify_contamination(
    draft_year: int,
    pick_rows: list[dict[str, Any]],
    player_meta: dict[str, dict[str, Any]],
    identity: dict[str, Any],
) -> dict[str, Any]:
    evidence = []
    unknown = []
    same_year = 0
    meta_missing = 0
    status = Counter()

    by_name_pos = identity["candidate_years_by_name_pos"]

    for p in pick_rows:
        pid = p["mfl_player_id"]
        meta = player_meta.get(pid)
        if meta is None:
            meta_missing += 1
            unknown.append({
                "overall_slot": p["overall_slot"],
                "mfl_player_id": pid,
                "kind": "league_scoped_player_metadata_missing",
            })
            status["league_scoped_player_metadata_missing"] += 1
            continue

        name = meta.get("name")
        pos = norm_position(meta.get("position"))
        nm = clean_name(name)

        if explicit_devy_marker(name):
            evidence.append({
                "overall_slot": p["overall_slot"],
                "mfl_player_id": pid,
                "kind": "explicit_devy_custom_player",
                "name": name,
                "position": meta.get("position"),
            })
            status["explicit_devy_custom_player"] += 1
            continue

        years = sorted(by_name_pos.get((nm, pos), set())) if nm and pos else []

        if len(years) == 1:
            identity_year = years[0]
            if identity_year < draft_year:
                evidence.append({
                    "overall_slot": p["overall_slot"],
                    "mfl_player_id": pid,
                    "kind": "resolved_past_nfl_class",
                    "name": name,
                    "position": meta.get("position"),
                    "identity_draft_class": identity_year,
                })
                status["resolved_past_nfl_class"] += 1
            elif identity_year > draft_year:
                evidence.append({
                    "overall_slot": p["overall_slot"],
                    "mfl_player_id": pid,
                    "kind": "resolved_future_nfl_class",
                    "name": name,
                    "position": meta.get("position"),
                    "identity_draft_class": identity_year,
                })
                status["resolved_future_nfl_class"] += 1
            else:
                same_year += 1
                status["resolved_same_year"] += 1
        elif len(years) > 1:
            unknown.append({
                "overall_slot": p["overall_slot"],
                "mfl_player_id": pid,
                "kind": "ambiguous_name_position_multiple_draft_classes",
                "name": name,
                "position": meta.get("position"),
                "candidate_draft_years": years,
            })
            status["ambiguous_name_position_multiple_draft_classes"] += 1
        else:
            # MFL's own draft_year is useful diagnostic metadata, but
            # it is not used alone to create positive evidence because
            # the frozen V4 rule requires an unambiguous identity.
            unknown.append({
                "overall_slot": p["overall_slot"],
                "mfl_player_id": pid,
                "kind": "no_external_same_identity_draft_class",
                "name": name,
                "position": meta.get("position"),
                "mfl_metadata_draft_year": meta.get("draft_year"),
            })
            status["no_external_same_identity_draft_class"] += 1

    return {
        "positive_contamination": bool(evidence),
        "positive_evidence_n": len(evidence),
        "positive_evidence": evidence,
        "diagnostic_unknown_n": len(unknown),
        "diagnostic_unknown": unknown,
        "resolved_same_year_n": same_year,
        "league_metadata_missing_n": meta_missing,
        "identity_status_counts": dict(status),
    }

def guard_contract() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    p = load(PREREG)
    c = load(V3_CLOSURE)
    ca = load(V3_CONTAM)

    if p["status"] != "FROZEN_PRE_SEARCH_PRE_OUTCOME":
        raise RecoveryError("V4 preregistration status drift")
    if c["status"] != "CLOSED_PRE_OUTCOME":
        raise RecoveryError("V3 closure status drift")
    if c["decision"] != "STOP_V3_SOURCE_SCOPE_CONTAMINATION_CLEAN_SUBSET_INSUFFICIENT":
        raise RecoveryError("V3 closure decision drift")
    if ca["audit_counts"]["clean_league_n"] != 172:
        raise RecoveryError("V3 clean seed count drift")

    for obj in (p, c, ca):
        if obj["historical_player_outcomes_read"] is not False:
            raise RecoveryError("historical outcomes already read")
        if obj["candidate_fit_performed"] is not False:
            raise RecoveryError("candidate fit already performed")
        if obj["validation_scored"] is not False:
            raise RecoveryError("validation already scored")
        if obj["production_change_authorized"] is not False:
            raise RecoveryError("production already authorized")

    return p, c, ca

def seed_rows_for_year(
    year: int,
    contam: dict[str, Any],
) -> tuple[list[dict[str, Any]], set[str]]:
    clean = []
    all_known = set()
    for row in contam["league_audit"]:
        if int(row["draft_year"]) != year:
            continue
        lid = str(row["league_id"])
        all_known.add(lid)
        if row["positive_rookie_scope_contamination"]:
            continue
        scope = row["scope"]
        clean.append({
            "draft_year": year,
            "league_id": lid,
            "league_name": row.get("league_name"),
            "source": "v3_clean_seed",
            "qualifier_kind": "v3_frozen_qualifier_preserved",
            "idp": bool(row.get("idp")),
            "full4": bool(scope.get("primary_r1_r4")),
            "full5": bool(scope.get("primary_r5")),
            "full6": bool(scope.get("primary_r6") or scope.get("idp_sensitivity_r6")),
            "primary_r1_r4": bool(scope.get("primary_r1_r4")),
            "primary_r5": bool(scope.get("primary_r5")),
            "primary_r6": bool(scope.get("primary_r6")),
            "idp_r6_sensitivity": bool(scope.get("idp_sensitivity_r6")),
            "positive_contamination": False,
            "positive_evidence_n": 0,
            "diagnostic_unknown_n": int(row.get("diagnostic_unknown_n", 0)),
            "carried_forward_from_v3": True,
        })
    return clean, all_known

def discover(
    session: requests.Session,
    year: int,
    prereg: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    terms = prereg["search_universe"]["search_terms"]
    cap = int(prereg["search_universe"]["max_results_per_term"])
    year_cap = int(prereg["search_universe"]["max_unique_candidates_per_year"])
    retries = int(prereg["search_universe"]["transport_retries"])
    sleep_seconds = float(prereg["search_universe"]["request_sleep_seconds"])

    all_ids = set()
    term_counts = {}
    term_unique_before_cap = {}
    errors = {}

    for term in terms:
        try:
            raw = search_ids(
                get_json(
                    session,
                    api_url(year, "leagueSearch", SEARCH=term),
                    retries,
                    sleep_seconds,
                )
            )
        except RecoveryError as exc:
            errors[term] = str(exc)
            continue

        unique = sorted(
            set(raw),
            key=lambda lid: stable_hash(f"{year}|{term}|{lid}"),
        )
        term_unique_before_cap[term] = len(unique)
        selected = unique[:cap]
        term_counts[term] = len(selected)
        all_ids.update(selected)

    # A search endpoint failure changes the frozen discovery frame.
    if errors:
        raise RecoveryError(
            f"{year}: leagueSearch failures redefine discovery frame: "
            f"{sorted(errors)}"
        )

    ordered = sorted(
        all_ids,
        key=lambda lid: stable_hash(f"{year}|candidate|{lid}"),
    )
    selected_year = ordered[:year_cap]

    return selected_year, {
        "search_terms": terms,
        "max_results_per_term": cap,
        "max_unique_candidates_per_year": year_cap,
        "term_unique_before_cap": term_unique_before_cap,
        "term_selected_counts": term_counts,
        "bounded_union_before_year_cap_n": len(ordered),
        "selected_after_year_cap_n": len(selected_year),
        "year_cap_binding": len(ordered) > year_cap,
        "search_errors": {},
    }

def probe_year(
    year: int,
    out_path: Path,
    dp_path: Path,
    nv_path: Path,
) -> None:
    if year not in YEARS:
        raise RecoveryError(f"unsupported year {year}")

    prereg, _, contam = guard_contract()
    identity = load_identity_index(dp_path, nv_path)
    seed_rows, known_ids = seed_rows_for_year(year, contam)

    retries = int(prereg["search_universe"]["transport_retries"])
    sleep_seconds = float(prereg["search_universe"]["request_sleep_seconds"])

    session = requests.Session()
    session.headers.update({
        "User-Agent": f"LOG-Trade-Calculator-V4-Clean-Source-Recovery-{year}/1.0"
    })

    discovered, discovery = discover(session, year, prereg)
    unseen = [lid for lid in discovered if lid not in known_ids]

    counts = Counter()
    qualifier_rejects = Counter()
    transport = Counter()
    rows = []

    print(
        f"{year}: clean seed={len(seed_rows)} known_v3={len(known_ids)} "
        f"discovered={len(discovered)} unseen={len(unseen)}",
        flush=True,
    )

    for idx, lid in enumerate(unseen, start=1):
        counts["unseen_candidates_probed"] += 1

        try:
            lg = league_obj(
                get_json(
                    session,
                    api_url(year, "league", L=lid),
                    retries,
                    sleep_seconds,
                )
            )
        except RecoveryError:
            transport["league_fetch_failed"] += 1
            continue

        if not lg:
            transport["league_missing"] += 1
            continue

        ok, qkind = qualifier(lg)
        if not ok:
            qualifier_rejects[qkind] += 1
            continue

        counts["base_eligible"] += 1
        idp = is_idp(lg)
        mock = obvious_mock_name(lg.get("name"))
        if mock:
            counts["obvious_mock_rejected"] += 1
            continue

        try:
            units = draft_units(
                get_json(
                    session,
                    api_url(year, "draftResults", L=lid),
                    retries,
                    sleep_seconds,
                )
            )
        except RecoveryError:
            transport["draft_fetch_failed"] += 1
            continue

        d = canonical_pick_rows(units)
        if not d["full4"]:
            counts["eligible_but_not_full4"] += 1
            continue

        pick_rows = d["rows"]

        try:
            meta, meta_diag = league_scoped_players(
                session,
                year,
                lid,
                [x["mfl_player_id"] for x in pick_rows],
                retries,
                sleep_seconds,
            )
        except RecoveryError:
            transport["players_fetch_failed"] += 1
            continue

        contamination = classify_contamination(
            year, pick_rows, meta, identity
        )

        if contamination["positive_contamination"]:
            counts["positive_contamination_rejected"] += 1
        else:
            counts["new_clean_full4"] += 1

        primary_r1_r4 = not contamination["positive_contamination"] and d["full4"]
        primary_r5 = (
            not contamination["positive_contamination"]
            and not idp
            and d["full5"]
        )
        primary_r6 = (
            not contamination["positive_contamination"]
            and not idp
            and d["full6"]
        )
        idp_r6 = (
            not contamination["positive_contamination"]
            and idp
            and d["full6"]
        )

        rows.append({
            "draft_year": year,
            "league_id": lid,
            "league_name": lg.get("name"),
            "source": "v4_expanded_search",
            "qualifier_kind": qkind,
            "keeper_state": keeper_state(lg),
            "qb_limit": qb_limit(lg),
            "draft_player_pool": lg.get("draftPlayerPool"),
            "idp": idp,
            "obvious_mock_name": False,
            "full4": d["full4"],
            "full5": d["full5"],
            "full6": d["full6"],
            "filled_by_round": d["filled_by_round"],
            "draft_unit_n": d["draft_unit_n"],
            "duplicate_slot_occurrence_n": d["duplicate_slot_occurrence_n"],
            "invalid_pick_number_n": d["invalid_pick_number_n"],
            "blank_player_occurrence_n": d["blank_player_occurrence_n"],
            "primary_r1_r4": primary_r1_r4,
            "primary_r5": primary_r5,
            "primary_r6": primary_r6,
            "idp_r6_sensitivity": idp_r6,
            "positive_contamination": contamination["positive_contamination"],
            "positive_evidence_n": contamination["positive_evidence_n"],
            "positive_evidence": contamination["positive_evidence"],
            "diagnostic_unknown_n": contamination["diagnostic_unknown_n"],
            "diagnostic_unknown": contamination["diagnostic_unknown"],
            "resolved_same_year_n": contamination["resolved_same_year_n"],
            "identity_status_counts": contamination["identity_status_counts"],
            "league_scoped_player_metadata": meta_diag,
            "carried_forward_from_v3": False,
        })

        if idx % 100 == 0 or idx == len(unseen):
            print(
                f"{year}: {idx}/{len(unseen)} unseen; "
                f"base_eligible={counts['base_eligible']} "
                f"new_clean_full4={counts['new_clean_full4']} "
                f"contaminated={counts['positive_contamination_rejected']}",
                flush=True,
            )

    all_clean = seed_rows + [
        r for r in rows if not r["positive_contamination"]
    ]

    scope_counts = {
        "primary_r1_r4": sum(r["primary_r1_r4"] for r in all_clean),
        "primary_r5": sum(r["primary_r5"] for r in all_clean),
        "primary_r6": sum(r["primary_r6"] for r in all_clean),
        "idp_r6_sensitivity": sum(
            r["idp_r6_sensitivity"] for r in all_clean
        ),
    }
    seed_scope_counts = {
        "primary_r1_r4": sum(r["primary_r1_r4"] for r in seed_rows),
        "primary_r5": sum(r["primary_r5"] for r in seed_rows),
        "primary_r6": sum(r["primary_r6"] for r in seed_rows),
        "idp_r6_sensitivity": sum(
            r["idp_r6_sensitivity"] for r in seed_rows
        ),
    }

    payload = {
        "schema_version": 1,
        "stage": "v4_clean_source_recovery_year",
        "draft_year": year,
        "generated_at_utc": now(),
        "research_only": True,
        "historical_player_outcomes_read": False,
        "market_or_ktc_values_read": False,
        "package_vote_data_read": False,
        "candidate_fit_performed": False,
        "candidate_scores_computed": False,
        "validation_scored": False,
        "production_change_authorized": False,
        "authorizes_outcome_ingestion": False,
        "discovery": discovery,
        "known_v3_league_id_n": len(known_ids),
        "v3_clean_seed_league_n": len(seed_rows),
        "unseen_discovered_candidate_n": len(unseen),
        "probe_counts": dict(counts),
        "qualifier_reject_counts": dict(qualifier_rejects),
        "transport_counts": dict(transport),
        "seed_scope_counts": seed_scope_counts,
        "combined_clean_scope_counts": scope_counts,
        "new_candidate_rows": rows,
        "source_hashes": {
            PREREG.name: sha256(PREREG),
            V3_CLOSURE.name: sha256(V3_CLOSURE),
            V3_CONTAM.name: sha256(V3_CONTAM),
            "dynastyprocess_db_playerids.csv": identity["dynastyprocess_sha256"],
            "nflverse_players.csv": identity["nflverse_sha256"],
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )

    print(json.dumps({
        "year": year,
        "seed_leagues": len(seed_rows),
        "discovered_candidates": len(discovered),
        "unseen_candidates": len(unseen),
        "combined_clean_scope_counts": scope_counts,
        "new_clean_full4": counts["new_clean_full4"],
        "positive_contamination_rejected": counts["positive_contamination_rejected"],
        "transport_counts": dict(transport),
    }, indent=2, sort_keys=True))

def effective_years(counts: list[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    shares = [c / total for c in counts if c > 0]
    hhi = sum(s * s for s in shares)
    return 1.0 / hhi if hhi else 0.0

def aggregate(partial_dir: Path) -> None:
    prereg, _, _ = guard_contract()
    parts = []
    for year in YEARS:
        path = partial_dir / f"year_{year}.json"
        if not path.exists():
            raise RecoveryError(f"missing year result {path}")
        d = load(path)
        if int(d["draft_year"]) != year:
            raise RecoveryError(f"wrong year in {path}")
        if d["source_hashes"][PREREG.name] != sha256(PREREG):
            raise RecoveryError("preregistration hash mismatch across matrix")
        for key in (
            "historical_player_outcomes_read",
            "candidate_fit_performed",
            "candidate_scores_computed",
            "validation_scored",
            "production_change_authorized",
            "authorizes_outcome_ingestion",
        ):
            if d[key] is not False:
                raise RecoveryError(f"firewall violation: {key}")
        parts.append(d)

    clean_r1r4 = [
        int(d["combined_clean_scope_counts"]["primary_r1_r4"])
        for d in parts
    ]
    clean_r5 = [
        int(d["combined_clean_scope_counts"]["primary_r5"])
        for d in parts
    ]
    clean_r6 = [
        int(d["combined_clean_scope_counts"]["primary_r6"])
        for d in parts
    ]
    idp_r6 = [
        int(d["combined_clean_scope_counts"]["idp_r6_sensitivity"])
        for d in parts
    ]

    total_r1r4 = sum(clean_r1r4)
    total_r5 = sum(clean_r5)
    total_r6 = sum(clean_r6)
    total_idp_r6 = sum(idp_r6)
    r6_eff = effective_years(clean_r6)
    r6_max_share = (
        max(clean_r6) / total_r6 if total_r6 else 1.0
    )
    idp_years = sum(x > 0 for x in idp_r6)

    g = prereg["source_sufficiency_gates"]

    primary_gates = {
        "r1_r4_nonmock_total": {
            "value": total_r1r4,
            "threshold": g["r1_r4_nonmock_total_min"],
            "pass": total_r1r4 >= g["r1_r4_nonmock_total_min"],
        },
        "r5_nonidp_nonmock_total": {
            "value": total_r5,
            "threshold": g["r5_nonidp_nonmock_total_min"],
            "pass": total_r5 >= g["r5_nonidp_nonmock_total_min"],
        },
        "r6_nonidp_nonmock_total": {
            "value": total_r6,
            "threshold": g["r6_nonidp_nonmock_total_min"],
            "pass": total_r6 >= g["r6_nonidp_nonmock_total_min"],
        },
        "r6_nonidp_min_per_year": {
            "value": min(clean_r6),
            "threshold": g["r6_nonidp_nonmock_min_each_year"],
            "pass": min(clean_r6) >= g["r6_nonidp_nonmock_min_each_year"],
        },
        "r6_nonidp_hhi_effective_years": {
            "value": r6_eff,
            "threshold": g["r6_nonidp_effective_years_min"],
            "pass": r6_eff >= g["r6_nonidp_effective_years_min"],
        },
        "r6_nonidp_max_year_share": {
            "value": r6_max_share,
            "threshold": g["r6_nonidp_nonmock_max_year_share"],
            "pass": r6_max_share <= g["r6_nonidp_nonmock_max_year_share"],
        },
    }

    sensitivity_gates = {
        "idp_r6_nonmock_total": {
            "value": total_idp_r6,
            "threshold": g["r6_idp_nonmock_total_min_for_sensitivity_only"],
            "pass": (
                total_idp_r6
                >= g["r6_idp_nonmock_total_min_for_sensitivity_only"]
            ),
        },
        "idp_r6_years_represented": {
            "value": idp_years,
            "threshold": g["r6_idp_nonmock_min_years_represented"],
            "pass": (
                idp_years
                >= g["r6_idp_nonmock_min_years_represented"]
            ),
        },
    }

    primary_pass = all(x["pass"] for x in primary_gates.values())
    decision = (
        prereg["decision_rule"]["pass"]
        if primary_pass
        else prereg["decision_rule"]["fail"]
    )

    candidate_rows = [
        row for d in parts for row in d["new_candidate_rows"]
    ]
    new_clean_rows = [
        row for row in candidate_rows
        if not row["positive_contamination"]
    ]
    contaminated_rows = [
        row for row in candidate_rows
        if row["positive_contamination"]
    ]

    seed_by_year = {
        str(d["draft_year"]): d["seed_scope_counts"]
        for d in parts
    }
    combined_by_year = {
        str(d["draft_year"]): d["combined_clean_scope_counts"]
        for d in parts
    }

    source_recovery = {
        "schema_version": 1,
        "study_id": prereg["study_id"],
        "stage": "clean_source_recovery",
        "generated_at_utc": now(),
        "status": (
            "SOURCE_RECOVERY_PASS"
            if primary_pass
            else "SOURCE_RECOVERY_STOP"
        ),
        "decision": decision,
        "historical_player_outcomes_read": False,
        "market_or_ktc_values_read": False,
        "package_vote_data_read": False,
        "candidate_fit_performed": False,
        "candidate_scores_computed": False,
        "validation_scored": False,
        "production_change_authorized": False,
        "authorizes_outcome_ingestion": False,
        "authorizes_source_catalog_freeze": False,
        "authorizes_next_stage": (
            "V4_CATALOG_AND_FULL_PREREGISTRATION_FREEZE_ONLY"
            if primary_pass
            else None
        ),
        "scientific_interpretation": (
            "The frozen contamination-aware MFL source recovery produced "
            "enough clean source evidence to proceed to a separate V4 "
            "catalog/full-preregistration freeze. It does not authorize "
            "historical outcome ingestion."
            if primary_pass
            else
            "The frozen contamination-aware MFL source recovery did not "
            "satisfy all inherited primary source-sufficiency gates. "
            "The MFL V4 recovery path stops before outcomes."
        ),
        "primary_gate_pass": primary_pass,
        "primary_gates": primary_gates,
        "idp_sensitivity_gates": sensitivity_gates,
        "idp_sensitivity_gate_is_nonblocking": True,
        "clean_counts_by_year": {
            str(year): {
                "primary_r1_r4": clean_r1r4[i],
                "primary_r5": clean_r5[i],
                "primary_r6": clean_r6[i],
                "idp_r6_sensitivity": idp_r6[i],
            }
            for i, year in enumerate(YEARS)
        },
        "clean_totals": {
            "primary_r1_r4": total_r1r4,
            "primary_r5": total_r5,
            "primary_r6": total_r6,
            "idp_r6_sensitivity": total_idp_r6,
        },
        "v3_clean_seed_scope_counts_by_year": seed_by_year,
        "combined_clean_scope_counts_by_year": combined_by_year,
        "search_diagnostics_by_year": {
            str(d["draft_year"]): d["discovery"]
            for d in parts
        },
        "probe_diagnostics_by_year": {
            str(d["draft_year"]): {
                "known_v3_league_id_n": d["known_v3_league_id_n"],
                "v3_clean_seed_league_n": d["v3_clean_seed_league_n"],
                "unseen_discovered_candidate_n": d["unseen_discovered_candidate_n"],
                "probe_counts": d["probe_counts"],
                "qualifier_reject_counts": d["qualifier_reject_counts"],
                "transport_counts": d["transport_counts"],
            }
            for d in parts
        },
        "new_source_evidence": {
            "audited_full4_candidate_league_n": len(candidate_rows),
            "new_clean_full4_league_n": len(new_clean_rows),
            "new_positive_contaminated_league_n": len(contaminated_rows),
            "rows": candidate_rows,
        },
        "frozen_search_contract": prereg["search_universe"],
        "frozen_contamination_contract": prereg["contamination_screen"],
        "frozen_source_sufficiency_gates": prereg["source_sufficiency_gates"],
        "source_hashes": {
            PREREG.name: sha256(PREREG),
            PREREG_MAN.name: sha256(PREREG_MAN),
            V3_CLOSURE.name: sha256(V3_CLOSURE),
            V3_CONTAM.name: sha256(V3_CONTAM),
            "dynastyprocess_db_playerids.csv": parts[0]["source_hashes"]["dynastyprocess_db_playerids.csv"],
            "nflverse_players.csv": parts[0]["source_hashes"]["nflverse_players.csv"],
        },
    }

    JSON_OUT.write_text(
        json.dumps(source_recovery, indent=2, sort_keys=True) + "\n"
    )

    lines = [
        "# Draft Pick FV V4 — Clean Source Recovery",
        "",
        f"**Decision:** `{decision}`",
        "",
        "This stage remains completely pre-outcome. Passing source recovery "
        "only authorizes a separate V4 catalog/full-preregistration freeze.",
        "",
        "## Clean source counts",
        "",
        "| Year | R1–R4 | R5 non-IDP | R6 non-IDP | IDP R6 sensitivity |",
        "|---:|---:|---:|---:|---:|",
    ]
    for i, year in enumerate(YEARS):
        lines.append(
            f"| {year} | {clean_r1r4[i]} | {clean_r5[i]} | "
            f"{clean_r6[i]} | {idp_r6[i]} |"
        )

    lines += [
        f"| **Total** | **{total_r1r4}** | **{total_r5}** | "
        f"**{total_r6}** | **{total_idp_r6}** |",
        "",
        "## Primary frozen gates",
        "",
    ]
    for name, gate in primary_gates.items():
        comparator = "≤" if name == "r6_nonidp_max_year_share" else "≥"
        lines.append(
            f"- `{name}`: **{gate['value']}** {comparator} "
            f"**{gate['threshold']}** — "
            f"**{'PASS' if gate['pass'] else 'FAIL'}**"
        )

    lines += [
        "",
        "## IDP sensitivity-only gates",
        "",
    ]
    for name, gate in sensitivity_gates.items():
        lines.append(
            f"- `{name}`: **{gate['value']}** ≥ **{gate['threshold']}** — "
            f"**{'PASS' if gate['pass'] else 'FAIL'}**"
        )

    lines += [
        "",
        "The IDP gates are explicitly nonblocking in the frozen V4 recovery "
        "decision rule.",
        "",
        "## Recovery diagnostics",
        "",
        f"- New audited full-R4 candidates: **{len(candidate_rows)}**",
        f"- New clean full-R4 leagues: **{len(new_clean_rows)}**",
        f"- New positively contaminated leagues: **{len(contaminated_rows)}**",
        "",
        "## Firewall",
        "",
        "- Historical player outcomes read: **No**",
        "- Candidate fit performed: **No**",
        "- Locked validation scored: **No**",
        "- Production change authorized: **No**",
        "",
        "## Next step",
        "",
        (
            "Freeze the recovered V4 clean source catalog and full V4 "
            "scientific preregistration. Outcomes remain sealed."
            if primary_pass
            else
            "Stop the MFL historical-draft recovery path. Do not ingest outcomes."
        ),
    ]
    MD_OUT.write_text("\n".join(lines) + "\n")

    manifest = {
        "schema_version": 1,
        "study_id": source_recovery["study_id"],
        "stage": source_recovery["stage"],
        "generated_at_utc": source_recovery["generated_at_utc"],
        "decision": decision,
        "primary_gate_pass": primary_pass,
        "historical_player_outcomes_read": False,
        "candidate_fit_performed": False,
        "candidate_scores_computed": False,
        "validation_scored": False,
        "production_change_authorized": False,
        "authorizes_outcome_ingestion": False,
        "authorizes_source_catalog_freeze": False,
        "authorizes_next_stage": source_recovery["authorizes_next_stage"],
        "source_hashes": source_recovery["source_hashes"],
        "output_hashes": {
            JSON_OUT.name: sha256(JSON_OUT),
            MD_OUT.name: sha256(MD_OUT),
        },
    }
    MAN_OUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )

    print(json.dumps({
        "decision": decision,
        "primary_gate_pass": primary_pass,
        "clean_counts_by_year": source_recovery["clean_counts_by_year"],
        "clean_totals": source_recovery["clean_totals"],
        "primary_gates": primary_gates,
        "idp_sensitivity_gates": sensitivity_gates,
        "new_clean_full4": len(new_clean_rows),
        "new_contaminated": len(contaminated_rows),
    }, indent=2, sort_keys=True))

def check_outputs() -> None:
    prereg, _, _ = guard_contract()
    d = load(JSON_OUT)
    m = load(MAN_OUT)

    if d["decision"] not in {
        prereg["decision_rule"]["pass"],
        prereg["decision_rule"]["fail"],
    }:
        raise RecoveryError("unexpected decision")
    if m["decision"] != d["decision"]:
        raise RecoveryError("manifest decision mismatch")

    for obj in (d, m):
        for key in (
            "historical_player_outcomes_read",
            "candidate_fit_performed",
            "candidate_scores_computed",
            "validation_scored",
            "production_change_authorized",
            "authorizes_outcome_ingestion",
            "authorizes_source_catalog_freeze",
        ):
            if obj[key] is not False:
                raise RecoveryError(f"firewall violation in output: {key}")

    if d["idp_sensitivity_gate_is_nonblocking"] is not True:
        raise RecoveryError("IDP sensitivity gate accidentally blocking")
    if d["primary_gate_pass"] != all(
        x["pass"] for x in d["primary_gates"].values()
    ):
        raise RecoveryError("primary gate aggregation mismatch")

    if d["primary_gate_pass"]:
        if d["decision"] != prereg["decision_rule"]["pass"]:
            raise RecoveryError("pass decision mismatch")
        if (
            d["authorizes_next_stage"]
            != "V4_CATALOG_AND_FULL_PREREGISTRATION_FREEZE_ONLY"
        ):
            raise RecoveryError("pass next-stage authorization mismatch")
    else:
        if d["decision"] != prereg["decision_rule"]["fail"]:
            raise RecoveryError("fail decision mismatch")
        if d["authorizes_next_stage"] is not None:
            raise RecoveryError("failed recovery authorized a next stage")

    if m["output_hashes"][JSON_OUT.name] != sha256(JSON_OUT):
        raise RecoveryError("JSON hash mismatch")
    if m["output_hashes"][MD_OUT.name] != sha256(MD_OUT):
        raise RecoveryError("MD hash mismatch")

    print("PASS: V4 clean-source recovery outputs validated.")

def selftest() -> None:
    assert clean_name("Odell Beckham Jr.") == "odell beckham"
    assert norm_position("CB") == "DB"
    assert stable_id("0000") is None
    assert explicit_devy_marker("Devy Pick 1")

    units = [[
        {"round": str(r), "pick": str(p), "player": f"{r}{p:02d}"}
        for r in range(1, 7)
        for p in range(1, 13)
    ]]
    d = canonical_pick_rows(units)
    assert d["full4"] and d["full5"] and d["full6"]
    assert d["filled_by_round"]["6"] == 12

    identity = {
        "candidate_years_by_name_pos": {
            ("same rookie", "WR"): {2020},
            ("old veteran", "RB"): {2015},
            ("future prospect", "QB"): {2022},
        }
    }
    picks = [
        {"overall_slot": 1, "mfl_player_id": "1"},
        {"overall_slot": 2, "mfl_player_id": "2"},
        {"overall_slot": 3, "mfl_player_id": "3"},
    ]
    meta = {
        "1": {"name": "Same Rookie", "position": "WR", "draft_year": 2020},
        "2": {"name": "Old Veteran", "position": "RB", "draft_year": 2015},
        "3": {"name": "Future Prospect", "position": "QB", "draft_year": 2022},
    }
    c = classify_contamination(2020, picks, meta, identity)
    assert c["positive_contamination"] is True
    kinds = {x["kind"] for x in c["positive_evidence"]}
    assert "resolved_past_nfl_class" in kinds
    assert "resolved_future_nfl_class" in kinds

    assert abs(effective_years([3, 3, 3, 3, 3, 3]) - 6.0) < 1e-12
    print("PASS: V4 clean-source recovery self-test")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--year", type=int)
    ap.add_argument("--out")
    ap.add_argument("--dynastyprocess-csv")
    ap.add_argument("--nflverse-csv")
    ap.add_argument("--aggregate-dir")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    if args.year is not None:
        if (
            args.year not in YEARS
            or not args.out
            or not args.dynastyprocess_csv
            or not args.nflverse_csv
        ):
            raise SystemExit(
                "--year, --out, --dynastyprocess-csv and "
                "--nflverse-csv required"
            )
        probe_year(
            args.year,
            Path(args.out),
            Path(args.dynastyprocess_csv),
            Path(args.nflverse_csv),
        )
        return

    if args.aggregate_dir:
        aggregate(Path(args.aggregate_dir))
        check_outputs()
        return

    if args.check:
        check_outputs()
        return

    raise SystemExit(
        "choose --selftest, --year, --aggregate-dir or --check"
    )

if __name__ == "__main__":
    main()

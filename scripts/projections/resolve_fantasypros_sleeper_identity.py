#!/usr/bin/env python3
"""
Unified production FantasyPros <-> Sleeper identity resolver.

Covers QB/RB/WR/TE/DL/LB/DB using the matching core validated by the
Unified Identity V2 research audit. New authoritative matches require
name + compatible position + current team corroboration; ambiguous or
mismatched candidates are never guessed. Existing authoritative stable
FPID<->Sleeper-ID pairs remain sticky across later team/FA changes when
the same Sleeper ID still resolves to the same person and compatible
position. Any stable-ID contradiction hard-fails.

Outputs preserve the existing scripts/identity_crosswalk.json contract used
by Team Utility and scheduled refresh.

Usage:
  python3 scripts/projections/resolve_fantasypros_sleeper_identity.py --selftest
  python3 scripts/projections/resolve_fantasypros_sleeper_identity.py
"""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import sys

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]

FP_PATH = REPO_ROOT / "scripts" / "fantasypros_api_normalized_2026.json"
SLEEPER_TOTAL_PATH = REPO_ROOT / "scripts" / "sleeper_2026_projections.json"
SLEEPER_RAW_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "sleeper_2026_raw_categories.json"
TEAM_REFRESH_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "player_team_refresh.json"
V1_CROSSWALK_PATH = REPO_ROOT / "scripts" / "identity_crosswalk.json"

OUTPUT_JSON = REPO_ROOT / "scripts" / "identity_crosswalk.json"
OUTPUT_MD = REPO_ROOT / "scripts" / "artifacts" / "reports" / "identity_collision_report.md"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
OFFENSE = {"QB", "RB", "WR", "TE"}
IDP = {"DL", "LB", "DB"}

TEAM_ALIASES = {
    "JAC": "JAX",  # confirmed provider difference in the existing IDP resolver
}

POSITION_MAP = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "WR": "WR",
    "TE": "TE",
    "DL": "DL",
    "DE": "DL",
    "DT": "DL",
    "NT": "DL",
    "LB": "LB",
    "OLB": "LB",
    "ILB": "LB",
    "MLB": "LB",
    "EDGE": "EDGE",
    "DB": "DB",
    "CB": "DB",
    "S": "DB",
    "SS": "DB",
    "FS": "DB",
}

# EDGE is deliberately compatible with both DL and LB. FantasyPros' normalized
# feed itself uses DL/LB/DB, while Sleeper can expose granular/dual eligibility.
FP_COMPATIBLE_SLEEPER = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "DL": {"DL", "EDGE"},
    "LB": {"LB", "EDGE"},
    "DB": {"DB"},
}


def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_name(value) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_team(value):
    if value in (None, ""):
        return None
    team = str(value).strip().upper()
    if team == "FA":
        return None
    return TEAM_ALIASES.get(team, team)


def normalize_position(value):
    if value in (None, ""):
        return None
    return POSITION_MAP.get(str(value).strip().upper())


def finite_number(value):
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def sleeper_position_labels(row) -> set[str]:
    labels = set()
    raw = row.get("fantasy_positions")
    if isinstance(raw, list):
        for item in raw:
            pos = normalize_position(item)
            if pos:
                labels.add(pos)
    pos = normalize_position(row.get("pos"))
    if pos:
        labels.add(pos)
    return labels


def sleeper_has_signal(row) -> bool:
    total = finite_number(row.get("sleeper_2026_proj_total"))
    if total is not None and total > 0:
        return True
    cats = row.get("raw_category_season_totals")
    if isinstance(cats, dict):
        for value in cats.values():
            x = finite_number(value)
            if x is not None and abs(x) > 1e-12:
                return True
    return False


def build_sleeper_universe(total_rows, raw_rows, team_refresh):
    """Merge current Sleeper projection identity by stable sleeper_id.

    Raw categories supply the broader population. Positive-point totals supply
    additional projection signal. player_team_refresh is used as the freshest
    team corroboration when it has a non-null team for the stable ID.
    """
    teams_by_sid = {}
    if isinstance(team_refresh, dict):
        raw_teams = team_refresh.get("teams_by_sleeper_id")
        if isinstance(raw_teams, dict):
            teams_by_sid = {str(k): normalize_team(v) for k, v in raw_teams.items()}

    by_sid = {}

    def absorb(row, source):
        sid = row.get("sleeper_id")
        if sid in (None, ""):
            raise RuntimeError(f"Sleeper {source} row missing sleeper_id: {row.get('player')!r}")
        sid = str(sid)
        name = normalize_name(row.get("player"))
        if not name:
            raise RuntimeError(f"Sleeper {source} row {sid} has empty player name")

        positions = sleeper_position_labels(row)
        team = normalize_team(row.get("team"))
        signal = sleeper_has_signal(row)

        if sid not in by_sid:
            by_sid[sid] = {
                "sleeper_id": sid,
                "player": name,
                "positions": set(positions),
                "team": team,
                "has_projection_signal": signal,
                "sources": {source},
            }
            return

        current = by_sid[sid]
        if current["player"] != name:
            raise RuntimeError(
                f"Sleeper stable ID {sid} has conflicting names: "
                f"{current['player']!r} vs {name!r}"
            )
        current["positions"].update(positions)
        current["has_projection_signal"] = current["has_projection_signal"] or signal
        current["sources"].add(source)

        if current["team"] and team and current["team"] != team:
            # Do not guess which projection file is fresher. The dedicated team
            # refresh below is allowed to resolve the disagreement.
            current["team"] = None
        elif not current["team"] and team:
            current["team"] = team

    for row in raw_rows:
        absorb(row, "raw_categories")
    for row in total_rows:
        absorb(row, "scored_totals")

    for sid, row in by_sid.items():
        refreshed = teams_by_sid.get(sid)
        if refreshed:
            row["team"] = refreshed

    by_name = defaultdict(list)
    for row in by_sid.values():
        by_name[row["player"]].append(row)

    return by_sid, by_name


def fp_position(row):
    pos = normalize_position(row.get("source_position"))
    # FantasyPros normalized IDP rows should already be DL/LB/DB, and offense
    # rows should already be exact QB/RB/WR/TE. EDGE is not a valid final FP
    # source bucket in this pipeline.
    return pos if pos in TRACKED_POSITIONS else None


def validate_fp_rows(fp_rows):
    seen = {}
    out = []
    for row in fp_rows:
        fpid = row.get("fantasypros_id")
        if fpid in (None, ""):
            raise RuntimeError(f"FantasyPros row missing fantasypros_id: {row.get('name')!r}")
        fpid = str(fpid)
        if fpid in seen:
            raise RuntimeError(f"FantasyPros normalized output contains duplicate fantasypros_id={fpid}")

        recomputed = normalize_name(row.get("name"))
        stored = normalize_name(row.get("normalized_name"))
        if not recomputed:
            raise RuntimeError(f"FantasyPros {fpid} has empty name")
        if stored and stored != recomputed:
            raise RuntimeError(
                f"FantasyPros name-normalization mismatch for {row.get('name')!r}: "
                f"stored={stored!r}, recomputed={recomputed!r}"
            )

        pos = fp_position(row)
        if pos is None:
            continue

        clean = dict(row)
        clean["_fpid"] = fpid
        clean["_name"] = recomputed
        clean["_pos"] = pos
        clean["_team"] = normalize_team(row.get("team"))
        seen[fpid] = clean
        out.append(clean)
    return out


def is_position_compatible(fp_pos: str, sleeper_row) -> bool:
    allowed = FP_COMPATIBLE_SLEEPER[fp_pos]
    labels = set(sleeper_row.get("positions") or ())
    return bool(labels & allowed)


def make_base_entry(fp):
    return {
        "fantasypros_id": fp["_fpid"],
        "name": fp.get("name"),
        "normalized_name": fp["_name"],
        "fp_position": fp["_pos"],
        "fp_team": fp["_team"],
        "sleeper_id": None,
        "candidate_sleeper_id": None,
        "sleeper_team": None,
        "sleeper_positions": None,
        "sleeper_has_projection_signal": None,
        "match_method": None,
        "match_confidence": "none",
        "requires_manual_review": False,
        "name_candidate_count": 0,
        "position_candidate_count": 0,
    }


def fill_candidate(entry, candidate, method, confidence, authoritative):
    entry["candidate_sleeper_id"] = candidate["sleeper_id"]
    entry["sleeper_id"] = candidate["sleeper_id"] if authoritative else None
    entry["sleeper_team"] = candidate.get("team")
    entry["sleeper_positions"] = sorted(candidate.get("positions") or ())
    entry["sleeper_has_projection_signal"] = bool(candidate.get("has_projection_signal"))
    entry["match_method"] = method
    entry["match_confidence"] = confidence
    entry["requires_manual_review"] = not authoritative


def resolve_one(fp, sleeper_by_name):
    entry = make_base_entry(fp)
    name_candidates = list(sleeper_by_name.get(fp["_name"], ()))
    entry["name_candidate_count"] = len(name_candidates)

    if not name_candidates:
        entry["match_method"] = "no_sleeper_name_candidate"
        return entry

    position_candidates = [
        c for c in name_candidates
        if is_position_compatible(fp["_pos"], c)
    ]
    entry["position_candidate_count"] = len(position_candidates)

    if not position_candidates:
        entry["match_method"] = "name_found_position_incompatible"
        entry["requires_manual_review"] = True
        return entry

    fp_team = fp["_team"]
    team_matches = []
    if fp_team:
        team_matches = [
            c for c in position_candidates
            if c.get("team") and normalize_team(c.get("team")) == fp_team
        ]

    if len(team_matches) == 1:
        candidate = team_matches[0]
        method = (
            "name_position_team_confirmed"
            if len(position_candidates) == 1
            else "name_collision_resolved_by_position_team"
        )
        fill_candidate(entry, candidate, method, "high", authoritative=True)
        return entry

    if len(team_matches) > 1:
        entry["match_method"] = "multiple_position_team_matches"
        entry["requires_manual_review"] = True
        return entry

    if len(position_candidates) == 1:
        candidate = position_candidates[0]
        if fp_team and candidate.get("team"):
            fill_candidate(
                entry,
                candidate,
                "unique_name_position_team_mismatch",
                "medium",
                authoritative=False,
            )
        else:
            fill_candidate(
                entry,
                candidate,
                "unique_name_position_team_unavailable",
                "medium",
                authoritative=False,
            )
        return entry

    entry["match_method"] = "unresolved_name_position_collision"
    entry["requires_manual_review"] = True
    return entry


def enforce_one_to_one(rows):
    """Clear every authoritative assignment involved in a SID collision."""
    by_sid = defaultdict(list)
    for row in rows:
        sid = row.get("sleeper_id")
        if sid:
            by_sid[str(sid)].append(row)

    duplicate_sids = {sid: group for sid, group in by_sid.items() if len(group) > 1}
    for sid, group in duplicate_sids.items():
        for row in group:
            row["candidate_sleeper_id"] = sid
            row["sleeper_id"] = None
            row["requires_manual_review"] = True
            row["match_confidence"] = "none"
            row["match_method"] = "duplicate_authoritative_sleeper_assignment"
    return duplicate_sids

# ---------------------------------------------------------------------------
# Production wrapper around the audited V2 matching core.
# ---------------------------------------------------------------------------

def previous_authoritative_by_fpid(previous_rows):
    out = {}
    if not isinstance(previous_rows, list):
        return out
    for row in previous_rows:
        fpid = row.get("fantasypros_id")
        sid = row.get("sleeper_id")
        if fpid in (None, "") or sid in (None, ""):
            continue
        if row.get("requires_manual_review"):
            continue
        fpid = str(fpid)
        sid = str(sid)
        if fpid in out and out[fpid] != sid:
            raise RuntimeError(
                f"Previous crosswalk maps FantasyPros {fpid} to multiple "
                f"authoritative Sleeper IDs: {out[fpid]} and {sid}"
            )
        out[fpid] = sid
    return out


def preserve_previous_authoritative(fp, fresh, prior_sid, sleeper_by_sid):
    """Keep a previously-established stable provider pairing when still valid.

    Team membership is volatile; provider IDs are not. We therefore preserve a
    prior authoritative FPID<->SID mapping when the same SID still resolves to
    the same normalized name and a compatible position. A contradiction is a
    data-integrity failure and hard-fails rather than silently remapping.
    """
    if not prior_sid:
        return fresh

    prior_sid = str(prior_sid)
    current = sleeper_by_sid.get(prior_sid)
    if current is None:
        # Do not preserve an ID that vanished from the current Sleeper universe.
        return fresh

    if current["player"] != fp["_name"]:
        raise RuntimeError(
            f"Stable identity contradiction for FantasyPros {fp['_fpid']} "
            f"({fp['_name']}): prior Sleeper {prior_sid} now resolves to "
            f"{current['player']!r}"
        )
    # Position is mutable even when provider IDs identify the same person.
    # Example: a TE can later be rostered/listed as an FB (normalized to RB).
    # New identity matches still require position compatibility; this exception
    # applies only to a previously authoritative stable FPID<->Sleeper-ID pair
    # whose Sleeper ID still resolves to the exact same normalized person.
    position_changed = not is_position_compatible(fp["_pos"], current)

    fresh_sid = fresh.get("sleeper_id")
    if fresh_sid is not None and str(fresh_sid) != prior_sid:
        raise RuntimeError(
            f"Stable identity contradiction for FantasyPros {fp['_fpid']} "
            f"({fp['_name']}): prior authoritative Sleeper {prior_sid}, fresh "
            f"authoritative resolver produced {fresh_sid}"
        )

    if fresh_sid is not None:
        return fresh

    kept = dict(fresh)
    kept["sleeper_id"] = prior_sid
    kept["candidate_sleeper_id"] = prior_sid
    kept["sleeper_team"] = current.get("team")
    kept["sleeper_positions"] = sorted(current.get("positions") or ())
    kept["sleeper_has_projection_signal"] = bool(current.get("has_projection_signal"))
    kept["match_method"] = (
        "previous_authoritative_stable_id_preserved_position_changed"
        if position_changed
        else "previous_authoritative_stable_id_preserved"
    )
    kept["match_confidence"] = "high"
    kept["requires_manual_review"] = False
    return kept


def build_sleeper_metadata(total_rows, raw_rows, team_refresh):
    """Metadata needed to preserve the legacy crosswalk output contract."""
    meta = {}
    for rows in (raw_rows, total_rows):
        for row in rows:
            sid = row.get("sleeper_id")
            if sid in (None, ""):
                continue
            sid = str(sid)
            m = meta.setdefault(sid, {
                "sleeper_pos": None,
                "sleeper_fantasy_positions": None,
                "sleeper_team": None,
            })
            if m["sleeper_pos"] in (None, "") and row.get("pos") not in (None, ""):
                m["sleeper_pos"] = row.get("pos")
            fps = row.get("fantasy_positions")
            if m["sleeper_fantasy_positions"] is None and isinstance(fps, list):
                m["sleeper_fantasy_positions"] = fps
            team = normalize_team(row.get("team"))
            if m["sleeper_team"] is None and team:
                m["sleeper_team"] = team

    if isinstance(team_refresh, dict):
        teams = team_refresh.get("teams_by_sleeper_id")
        if isinstance(teams, dict):
            for sid, team in teams.items():
                sid = str(sid)
                team = normalize_team(team)
                if team:
                    meta.setdefault(sid, {
                        "sleeper_pos": None,
                        "sleeper_fantasy_positions": None,
                        "sleeper_team": None,
                    })["sleeper_team"] = team
    return meta


def productionize_row(row, sleeper_meta):
    sid_for_metadata = row.get("sleeper_id") or row.get("candidate_sleeper_id")
    meta = sleeper_meta.get(str(sid_for_metadata), {}) if sid_for_metadata else {}
    fpid = row.get("fantasypros_id")
    if isinstance(fpid, str) and fpid.isdigit():
        fpid = int(fpid)

    return {
        "fantasypros_id": fpid,
        "name": row.get("name"),
        "fp_team": row.get("fp_team"),
        "fp_position": row.get("fp_position"),
        "sleeper_id": row.get("sleeper_id"),
        "sleeper_team": meta.get("sleeper_team") or row.get("sleeper_team"),
        "sleeper_pos": meta.get("sleeper_pos"),
        "sleeper_fantasy_positions": meta.get("sleeper_fantasy_positions"),
        "sleeper_has_signal": row.get("sleeper_has_projection_signal"),
        "match_method": row.get("match_method"),
        "match_confidence": row.get("match_confidence"),
        "had_name_collision": bool(row.get("name_candidate_count", 0) > 1),
        "requires_manual_review": bool(row.get("requires_manual_review")),
        "candidate_sleeper_id": row.get("candidate_sleeper_id"),
        # Backwards-compatible diagnostics; consumers may ignore these.
        "name_candidate_count": row.get("name_candidate_count", 0),
        "position_candidate_count": row.get("position_candidate_count", 0),
    }


def build_production_crosswalk(fp_doc, sleeper_totals, sleeper_raw, team_refresh, previous_rows):
    if not isinstance(fp_doc, dict) or not isinstance(fp_doc.get("players"), list):
        raise RuntimeError("FantasyPros normalized document missing players list")
    if not isinstance(sleeper_totals, list):
        raise RuntimeError("Sleeper totals must be a list")
    if not isinstance(sleeper_raw, list):
        raise RuntimeError("Sleeper raw categories must be a list")
    if not isinstance(previous_rows, list):
        raise RuntimeError("Existing identity_crosswalk.json must be a list")

    fp_rows = validate_fp_rows(fp_doc["players"])
    sleeper_by_sid, sleeper_by_name = build_sleeper_universe(
        sleeper_totals, sleeper_raw, team_refresh
    )
    prior = previous_authoritative_by_fpid(previous_rows)

    rows = []
    for fp in fp_rows:
        fresh = resolve_one(fp, sleeper_by_name)
        rows.append(
            preserve_previous_authoritative(
                fp, fresh, prior.get(fp["_fpid"]), sleeper_by_sid
            )
        )

    duplicates = enforce_one_to_one(rows)
    if duplicates:
        raise RuntimeError(
            "Unified identity produced duplicate authoritative Sleeper "
            f"assignments; refusing production write. Sample={sorted(duplicates)[:10]}"
        )

    meta = build_sleeper_metadata(sleeper_totals, sleeper_raw, team_refresh)
    return [productionize_row(row, meta) for row in rows]


def build_production_report(rows):
    by_pos = {p: Counter() for p in TRACKED_POSITIONS}
    methods = Counter()
    manual = []

    for row in rows:
        pos = row.get("fp_position")
        if pos in by_pos:
            c = by_pos[pos]
            c["fp"] += 1
            if row.get("sleeper_id"):
                c["authoritative"] += 1
            if row.get("candidate_sleeper_id"):
                c["candidate"] += 1
            if row.get("requires_manual_review"):
                c["manual"] += 1
        methods[str(row.get("match_method") or "unknown")] += 1
        if row.get("requires_manual_review"):
            manual.append(row)

    authoritative = sum(1 for row in rows if row.get("sleeper_id"))
    lines = [
        "# FantasyPros ↔ Sleeper Unified Identity Report",
        "",
        "Production resolver covering QB / RB / WR / TE / DL / LB / DB.",
        "",
        f"- FantasyPros tracked rows: **{len(rows)}**",
        f"- Authoritative stable-ID matches: **{authoritative}**",
        f"- Manual-review rows: **{len(manual)}**",
        "",
        "## Coverage by position",
        "",
        "| Pos | FP rows | Authoritative | Match rate | Candidate | Manual review |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for pos in TRACKED_POSITIONS:
        c = by_pos[pos]
        n = c["fp"]
        rate = (100.0 * c["authoritative"] / n) if n else 0.0
        lines.append(
            f"| {pos} | {n} | {c['authoritative']} | {rate:.1f}% | "
            f"{c['candidate']} | {c['manual']} |"
        )

    lines += ["", "## Match methods", ""]
    for method, count in sorted(methods.items()):
        lines.append(f"- `{method}`: **{count}**")

    if manual:
        lines += [
            "",
            "## Manual-review rows",
            "",
            "These remain deliberately unresolved; downstream consumers must "
            "use existing fallback behavior rather than guess identity.",
            "",
            "| Player | Pos | FP team | Candidate SID | Sleeper team | Method |",
            "|---|---|---|---|---|---|",
        ]
        for row in manual:
            lines.append(
                f"| {row.get('name') or ''} | {row.get('fp_position') or ''} | "
                f"{row.get('fp_team') or ''} | {row.get('candidate_sleeper_id') or ''} | "
                f"{row.get('sleeper_team') or ''} | {row.get('match_method') or ''} |"
            )

    return "\n".join(lines).rstrip() + "\n"


def run_production_selftest():
    fp_doc = {"players": [
        {"fantasypros_id": 1, "name": "Trevor Lawrence", "normalized_name": "trevor lawrence",
         "source_position": "QB", "team": "JAC"},
        {"fantasypros_id": 2, "name": "A.J. Green", "normalized_name": "aj green",
         "source_position": "WR", "team": "ARI"},
        {"fantasypros_id": 3, "name": "Byron Murphy", "normalized_name": "byron murphy",
         "source_position": "DL", "team": "SEA"},
        {"fantasypros_id": 4, "name": "No Team", "normalized_name": "no team",
         "source_position": "TE", "team": "FA"},
    ]}
    raw = [
        {"sleeper_id": "100", "player": "trevor lawrence", "pos": "QB", "team": "JAX",
         "fantasy_positions": ["QB"], "raw_category_season_totals": {"pass_yd": 4000}},
        {"sleeper_id": "200", "player": "a.j. green", "pos": "WR", "team": "ARI",
         "fantasy_positions": ["WR"], "raw_category_season_totals": {"rec_yd": 1000}},
        {"sleeper_id": "201", "player": "a.j. green", "pos": "CB", "team": "MIA",
         "fantasy_positions": ["DB"], "raw_category_season_totals": {"idp_tkl_solo": 10}},
        {"sleeper_id": "300", "player": "byron murphy", "pos": "DT", "team": "SEA",
         "fantasy_positions": ["DL"], "raw_category_season_totals": {"sack": 5}},
        {"sleeper_id": "301", "player": "byron murphy", "pos": "DE", "team": "MIN",
         "fantasy_positions": ["DL"], "raw_category_season_totals": {"sack": 2}},
        {"sleeper_id": "400", "player": "no team", "pos": "TE", "team": None,
         "fantasy_positions": ["TE"], "raw_category_season_totals": {"rec_yd": 300}},
    ]
    refresh = {"teams_by_sleeper_id": {}}

    rows = build_production_crosswalk(fp_doc, [], raw, refresh, [])
    by_fpid = {str(r["fantasypros_id"]): r for r in rows}
    assert by_fpid["1"]["sleeper_id"] == "100"  # JAC/JAX alias
    assert by_fpid["2"]["sleeper_id"] == "200"  # same name separated by position
    assert by_fpid["3"]["sleeper_id"] == "300"  # collision resolved by team
    assert by_fpid["4"]["sleeper_id"] is None
    assert by_fpid["4"]["candidate_sleeper_id"] == "400"

    required = {
        "fantasypros_id", "name", "fp_team", "fp_position", "sleeper_id",
        "sleeper_team", "sleeper_pos", "sleeper_fantasy_positions",
        "sleeper_has_signal", "match_method", "match_confidence",
        "had_name_collision", "requires_manual_review", "candidate_sleeper_id",
    }
    assert required <= set(rows[0])

    # Sticky stable-ID continuity for a player who later loses team evidence.
    previous = [{
        "fantasypros_id": 4,
        "name": "No Team",
        "fp_position": "TE",
        "sleeper_id": "400",
        "requires_manual_review": False,
    }]
    sticky = build_production_crosswalk(fp_doc, [], raw, refresh, previous)
    sticky_by = {str(r["fantasypros_id"]): r for r in sticky}
    assert sticky_by["4"]["sleeper_id"] == "400"
    assert sticky_by["4"]["match_method"] == "previous_authoritative_stable_id_preserved"

    # Legitimate position changes must preserve a previously authoritative
    # stable identity, but must NOT make TE/RB generally compatible for new
    # matches. This mirrors players such as Connor Heyward moving TE -> FB.
    transition_fp = {"players": [{
        "fantasypros_id": 5,
        "name": "Position Change",
        "normalized_name": "position change",
        "source_position": "TE",
        "team": "LV",
    }]}
    transition_raw = [{
        "sleeper_id": "500",
        "player": "position change",
        "pos": "FB",
        "team": "LV",
        "fantasy_positions": ["RB"],
        "raw_category_season_totals": {"rush_yd": 10},
    }]

    # No prior pairing: TE -> FB/RB is still incompatible and unresolved.
    untrusted_transition = build_production_crosswalk(
        transition_fp, [], transition_raw, refresh, []
    )
    assert untrusted_transition[0]["sleeper_id"] is None
    assert untrusted_transition[0]["requires_manual_review"] is True
    assert (
        untrusted_transition[0]["match_method"]
        == "name_found_position_incompatible"
    )

    # Prior authoritative stable IDs: same person survives the position change.
    transition_previous = [{
        "fantasypros_id": 5,
        "name": "Position Change",
        "fp_position": "TE",
        "sleeper_id": "500",
        "requires_manual_review": False,
    }]
    trusted_transition = build_production_crosswalk(
        transition_fp, [], transition_raw, refresh, transition_previous
    )
    assert trusted_transition[0]["sleeper_id"] == "500"
    assert trusted_transition[0]["requires_manual_review"] is False
    assert (
        trusted_transition[0]["match_method"]
        == "previous_authoritative_stable_id_preserved_position_changed"
    )

    # A previous stable mapping to the wrong current person must hard-fail.
    bad_previous = [{"fantasypros_id": 1, "sleeper_id": "200", "requires_manual_review": False}]
    try:
        build_production_crosswalk(fp_doc, [], raw, refresh, bad_previous)
        raise AssertionError("expected stable identity contradiction to fail")
    except RuntimeError as exc:
        assert "Stable identity contradiction" in str(exc)

    bad_fp = {"players": [{
        "fantasypros_id": 99, "name": "Player One", "normalized_name": "wrong name",
        "source_position": "QB", "team": "KC",
    }]}
    try:
        build_production_crosswalk(bad_fp, [], [], refresh, [])
        raise AssertionError("expected FantasyPros normalization mismatch to fail")
    except RuntimeError as exc:
        assert "normalization mismatch" in str(exc)

    report = build_production_report(rows)
    assert report.endswith("\n") and not report.endswith("\n\n")
    print("PASS unified production FantasyPros-Sleeper identity self-test.")


def production_main():
    if "--selftest" in sys.argv:
        run_production_selftest()
        return

    fp_doc = read_json(FP_PATH)
    sleeper_totals = read_json(SLEEPER_TOTAL_PATH)
    sleeper_raw = read_json(SLEEPER_RAW_PATH)
    team_refresh = read_json(TEAM_REFRESH_PATH)
    previous_rows = read_json(V1_CROSSWALK_PATH) if V1_CROSSWALK_PATH.exists() else []

    rows = build_production_crosswalk(
        fp_doc, sleeper_totals, sleeper_raw, team_refresh, previous_rows
    )

    OUTPUT_JSON.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(build_production_report(rows), encoding="utf-8")

    authoritative = sum(1 for row in rows if row.get("sleeper_id"))
    manual = sum(1 for row in rows if row.get("requires_manual_review"))
    print(
        f"Wrote {len(rows)} unified FantasyPros rows: "
        f"{authoritative} authoritative, {manual} manual review."
    )
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    production_main()

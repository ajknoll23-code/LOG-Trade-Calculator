#!/usr/bin/env python3
"""
Unified FantasyPros <-> Sleeper Identity V2 research audit.

PURPOSE
-------
Build a deterministic, research-only identity crosswalk covering every
Trade Desk position currently present in the FantasyPros normalized feed:

    QB / RB / WR / TE / DL / LB / DB

This DOES NOT replace scripts/identity_crosswalk.json. The current production
crosswalk remains untouched until this audit's coverage/collision report is
reviewed and explicitly promoted.

INPUTS
------
- scripts/fantasypros_api_normalized_2026.json
- scripts/sleeper_2026_projections.json
- scripts/artifacts/generated/sleeper_2026_raw_categories.json
- scripts/artifacts/generated/player_team_refresh.json
- scripts/identity_crosswalk.json   (comparison only; existing validated IDP V1)

OUTPUTS
-------
- research/identity-v2/unified_fantasypros_sleeper_identity_v2.json
- research/identity-v2/unified_fantasypros_sleeper_identity_v2.md

IDENTITY POLICY
---------------
1. FantasyPros fpid and Sleeper sleeper_id remain the stable provider keys.
2. Name alone is NEVER authoritative.
3. Candidate players must have compatible positions.
4. An authoritative match requires explicit current team corroboration.
5. Team aliases are centralized (currently confirmed: JAC == JAX).
6. Ambiguity/mismatch is surfaced for review, never silently guessed.
7. No two FantasyPros IDs may be authoritatively assigned to one Sleeper ID.
8. Existing authoritative IDP V1 mappings are compared for regression/conflict.

Run:
    python3 research/identity-v2/unified_fantasypros_sleeper_identity_v2.py --selftest
    python3 research/identity-v2/unified_fantasypros_sleeper_identity_v2.py
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

OUTPUT_JSON = REPO_ROOT / "research" / "identity-v2" / "unified_fantasypros_sleeper_identity_v2.json"
OUTPUT_MD = REPO_ROOT / "research" / "identity-v2" / "unified_fantasypros_sleeper_identity_v2.md"

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


def compare_existing_idp_v1(rows, v1_rows):
    v2 = {str(r["fantasypros_id"]): r for r in rows}
    summary = Counter()
    details = []

    for old in v1_rows:
        old_sid = old.get("sleeper_id")
        fpid = old.get("fantasypros_id")
        if old_sid in (None, "") or fpid in (None, ""):
            continue
        if old.get("requires_manual_review"):
            continue

        fpid = str(fpid)
        old_sid = str(old_sid)
        new = v2.get(fpid)

        if new is None:
            status = "v1_authoritative_fpid_absent_from_v2"
        elif new.get("sleeper_id") == old_sid:
            status = "v1_authoritative_preserved"
        elif new.get("sleeper_id") is None and new.get("candidate_sleeper_id") == old_sid:
            status = "v1_authoritative_now_manual_same_candidate"
        elif new.get("sleeper_id") is None:
            status = "v1_authoritative_now_unresolved"
        else:
            status = "v1_authoritative_conflict"

        summary[status] += 1
        if status != "v1_authoritative_preserved":
            details.append({
                "fantasypros_id": fpid,
                "name": old.get("name"),
                "old_sleeper_id": old_sid,
                "new_sleeper_id": (new or {}).get("sleeper_id"),
                "new_candidate_sleeper_id": (new or {}).get("candidate_sleeper_id"),
                "new_match_method": (new or {}).get("match_method"),
                "status": status,
            })

    return dict(sorted(summary.items())), details


def build_summary(rows):
    by_pos = {p: Counter() for p in TRACKED_POSITIONS}
    methods = Counter()
    manual = []
    for row in rows:
        pos = row["fp_position"]
        c = by_pos[pos]
        c["fantasypros_rows"] += 1
        if row.get("sleeper_id"):
            c["authoritative_matches"] += 1
        if row.get("candidate_sleeper_id"):
            c["candidate_identified"] += 1
        if row.get("requires_manual_review"):
            c["manual_review"] += 1
            manual.append(row)
        if row.get("sleeper_has_projection_signal"):
            c["matched_candidate_has_signal"] += 1
        methods[str(row.get("match_method") or "unknown")] += 1

    result = {}
    for pos, c in by_pos.items():
        n = c["fantasypros_rows"]
        result[pos] = {
            **dict(c),
            "authoritative_match_rate": (c["authoritative_matches"] / n) if n else None,
        }
    return result, dict(sorted(methods.items())), manual


def build_audit(fp_doc, sleeper_totals, sleeper_raw, team_refresh, v1_rows):
    if not isinstance(fp_doc, dict) or not isinstance(fp_doc.get("players"), list):
        raise RuntimeError("FantasyPros normalized document missing players list")
    if not isinstance(sleeper_totals, list):
        raise RuntimeError("Sleeper totals must be a list")
    if not isinstance(sleeper_raw, list):
        raise RuntimeError("Sleeper raw categories must be a list")
    if not isinstance(v1_rows, list):
        raise RuntimeError("Existing identity_crosswalk.json must be a list")

    fp_rows = validate_fp_rows(fp_doc["players"])
    sleeper_by_sid, sleeper_by_name = build_sleeper_universe(
        sleeper_totals,
        sleeper_raw,
        team_refresh,
    )

    rows = [resolve_one(fp, sleeper_by_name) for fp in fp_rows]
    duplicate_assignments = enforce_one_to_one(rows)

    coverage, method_counts, manual_rows = build_summary(rows)
    v1_summary, v1_details = compare_existing_idp_v1(rows, v1_rows)

    structural = {
        "fantasypros_tracked_rows": len(fp_rows),
        "sleeper_stable_ids_in_universe": len(sleeper_by_sid),
        "authoritative_matches": sum(1 for r in rows if r.get("sleeper_id")),
        "manual_review_rows": sum(1 for r in rows if r.get("requires_manual_review")),
        "duplicate_authoritative_sleeper_assignment_groups": len(duplicate_assignments),
        "existing_idp_v1_authoritative_conflicts": v1_summary.get("v1_authoritative_conflict", 0),
    }

    promotion_ready = (
        structural["duplicate_authoritative_sleeper_assignment_groups"] == 0
        and structural["existing_idp_v1_authoritative_conflicts"] == 0
        and all(coverage[p].get("fantasypros_rows", 0) > 0 for p in TRACKED_POSITIONS)
    )

    decision = (
        "STRUCTURALLY_CLEAN_REVIEW_COVERAGE_BEFORE_PROMOTION"
        if promotion_ready
        else "NOT_READY_FOR_PROMOTION"
    )

    return {
        "schema_version": 1,
        "purpose": "research-only unified FantasyPros-to-Sleeper identity audit",
        "production_crosswalk_mutated": False,
        "decision": decision,
        "identity_policy": {
            "stable_keys": "FantasyPros fantasypros_id <-> Sleeper sleeper_id",
            "name_alone_authoritative": False,
            "position_compatibility_required": True,
            "team_corroboration_required_for_authoritative_match": True,
            "ambiguous_matches_guessed": False,
            "team_aliases": TEAM_ALIASES,
        },
        "structural_summary": structural,
        "coverage_by_position": coverage,
        "match_method_counts": method_counts,
        "existing_idp_v1_comparison": {
            "summary": v1_summary,
            "non_preserved_details": v1_details,
        },
        "manual_review_rows": manual_rows,
        "rows": rows,
    }


def pct(value):
    if value is None:
        return "—"
    return f"{100.0 * value:.1f}%"


def render_report(result):
    s = result["structural_summary"]
    lines = [
        "# Unified FantasyPros ↔ Sleeper Identity V2 Audit",
        "",
        "## Decision",
        "",
        f"**{result['decision']}**",
        "",
        "**RESEARCH ONLY. `scripts/identity_crosswalk.json` was not changed by this audit.**",
        "",
        "## Structural summary",
        "",
        f"- FantasyPros tracked rows: **{s['fantasypros_tracked_rows']}**",
        f"- Sleeper stable IDs in current projection universe: **{s['sleeper_stable_ids_in_universe']}**",
        f"- Authoritative matches: **{s['authoritative_matches']}**",
        f"- Manual-review rows: **{s['manual_review_rows']}**",
        f"- Duplicate authoritative Sleeper assignment groups: **{s['duplicate_authoritative_sleeper_assignment_groups']}**",
        f"- Existing IDP V1 authoritative conflicts: **{s['existing_idp_v1_authoritative_conflicts']}**",
        "",
        "## Coverage by position",
        "",
        "| Pos | FantasyPros rows | Authoritative | Match rate | Candidate identified | Manual review |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for pos in TRACKED_POSITIONS:
        c = result["coverage_by_position"][pos]
        lines.append(
            f"| {pos} | {c.get('fantasypros_rows', 0)} | "
            f"{c.get('authoritative_matches', 0)} | "
            f"{pct(c.get('authoritative_match_rate'))} | "
            f"{c.get('candidate_identified', 0)} | "
            f"{c.get('manual_review', 0)} |"
        )

    lines += [
        "",
        "## Match methods",
        "",
    ]
    for method, count in result["match_method_counts"].items():
        lines.append(f"- `{method}`: **{count}**")

    lines += [
        "",
        "## Existing IDP V1 comparison",
        "",
    ]
    for status, count in result["existing_idp_v1_comparison"]["summary"].items():
        lines.append(f"- `{status}`: **{count}**")

    details = result["existing_idp_v1_comparison"]["non_preserved_details"]
    if details:
        lines += [
            "",
            "### Existing authoritative IDP mappings not identically preserved",
            "",
            "| Player | FPID | Old SID | New SID | Candidate SID | Status | Method |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in details:
            lines.append(
                f"| {row.get('name') or ''} | {row.get('fantasypros_id') or ''} | "
                f"{row.get('old_sleeper_id') or ''} | {row.get('new_sleeper_id') or ''} | "
                f"{row.get('new_candidate_sleeper_id') or ''} | {row.get('status') or ''} | "
                f"{row.get('new_match_method') or ''} |"
            )

    manual = result["manual_review_rows"]
    if manual:
        lines += [
            "",
            "## Manual-review rows",
            "",
            "These are deliberately unresolved. The audit never silently guesses them.",
            "",
            "| Player | Pos | FP team | Candidate SID | Sleeper team | Method | Name cand. | Pos cand. |",
            "|---|---|---|---|---|---|---:|---:|",
        ]
        for row in manual:
            lines.append(
                f"| {row.get('name') or ''} | {row.get('fp_position') or ''} | "
                f"{row.get('fp_team') or ''} | {row.get('candidate_sleeper_id') or ''} | "
                f"{row.get('sleeper_team') or ''} | {row.get('match_method') or ''} | "
                f"{row.get('name_candidate_count', 0)} | {row.get('position_candidate_count', 0)} |"
            )

    lines += [
        "",
        "## Promotion rule",
        "",
        "This audit does **not** promote anything automatically. After reviewing coverage and every unresolved/conflicting row,",
        "the validated matching logic can be moved into the production resolver and only then replace the IDP-only crosswalk.",
        "",
    ]
    return "\n".join(lines)


def run_selftest():
    fp = {
        "players": [
            {"fantasypros_id": 1, "name": "Trevor Lawrence", "normalized_name": "trevor lawrence",
             "source_position": "QB", "team": "JAC"},
            {"fantasypros_id": 2, "name": "A.J. Green", "normalized_name": "aj green",
             "source_position": "WR", "team": "ARI"},
            {"fantasypros_id": 3, "name": "Byron Murphy", "normalized_name": "byron murphy",
             "source_position": "DL", "team": "SEA"},
            {"fantasypros_id": 4, "name": "Unique Mismatch", "normalized_name": "unique mismatch",
             "source_position": "RB", "team": "BUF"},
            {"fantasypros_id": 5, "name": "No Team", "normalized_name": "no team",
             "source_position": "TE", "team": None},
        ]
    }

    raw = [
        {"sleeper_id": "100", "player": "trevor lawrence", "pos": "QB", "team": "JAX",
         "fantasy_positions": ["QB"], "raw_category_season_totals": {"pass_yd": 4000}},
        # Same normalized name, different positions: position must separate them.
        {"sleeper_id": "200", "player": "a.j. green", "pos": "WR", "team": "ARI",
         "fantasy_positions": ["WR"], "raw_category_season_totals": {"rec_yd": 100}},
        {"sleeper_id": "201", "player": "a.j. green", "pos": "CB", "team": "MIA",
         "fantasy_positions": ["DB"], "raw_category_season_totals": {"idp_tkl_solo": 10}},
        # Same name and compatible DL position; team must resolve the collision.
        {"sleeper_id": "300", "player": "byron murphy", "pos": "DT", "team": "SEA",
         "fantasy_positions": ["DL"], "raw_category_season_totals": {"sack": 5}},
        {"sleeper_id": "301", "player": "byron murphy", "pos": "DE", "team": "MIN",
         "fantasy_positions": ["DL"], "raw_category_season_totals": {"sack": 2}},
        {"sleeper_id": "400", "player": "unique mismatch", "pos": "RB", "team": "KC",
         "fantasy_positions": ["RB"], "raw_category_season_totals": {"rush_yd": 500}},
        {"sleeper_id": "500", "player": "no team", "pos": "TE", "team": None,
         "fantasy_positions": ["TE"], "raw_category_season_totals": {"rec_yd": 300}},
    ]

    totals = []
    refresh = {"teams_by_sleeper_id": {}}
    old = []

    result = build_audit(fp, totals, raw, refresh, old)
    rows = {r["fantasypros_id"]: r for r in result["rows"]}

    assert rows["1"]["sleeper_id"] == "100"  # JAC/JAX alias
    assert rows["1"]["match_method"] == "name_position_team_confirmed"
    assert rows["2"]["sleeper_id"] == "200"  # position disambiguation
    assert rows["3"]["sleeper_id"] == "300"  # same-pos collision resolved by team
    assert rows["3"]["match_method"] == "name_collision_resolved_by_position_team"
    assert rows["4"]["sleeper_id"] is None
    assert rows["4"]["candidate_sleeper_id"] == "400"
    assert rows["4"]["match_method"] == "unique_name_position_team_mismatch"
    assert rows["5"]["sleeper_id"] is None
    assert rows["5"]["match_method"] == "unique_name_position_team_unavailable"

    # Normalization mismatch must hard-fail.
    bad_fp = {"players": [
        {"fantasypros_id": 10, "name": "Player One", "normalized_name": "wrong",
         "source_position": "QB", "team": "KC"}
    ]}
    try:
        build_audit(bad_fp, [], [], refresh, [])
        raise AssertionError("expected FantasyPros normalization mismatch to fail")
    except RuntimeError as exc:
        assert "normalization mismatch" in str(exc)

    # Duplicate authoritative SID assignment must be cleared, never silently kept.
    fp_dup = {"players": [
        {"fantasypros_id": 11, "name": "Same Guy", "normalized_name": "same guy",
         "source_position": "DL", "team": "KC"},
        {"fantasypros_id": 12, "name": "Same Guy", "normalized_name": "same guy",
         "source_position": "LB", "team": "KC"},
    ]}
    sleeper_dup = [{
        "sleeper_id": "900", "player": "same guy", "pos": "EDGE", "team": "KC",
        "fantasy_positions": ["EDGE"], "raw_category_season_totals": {"sack": 8}
    }]
    dup_result = build_audit(fp_dup, [], sleeper_dup, refresh, [])
    assert dup_result["structural_summary"]["duplicate_authoritative_sleeper_assignment_groups"] == 1
    assert all(r["sleeper_id"] is None for r in dup_result["rows"])

    print("PASS Unified FantasyPros-Sleeper Identity V2 standalone self-test.")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

    fp_doc = read_json(FP_PATH)
    sleeper_totals = read_json(SLEEPER_TOTAL_PATH)
    sleeper_raw = read_json(SLEEPER_RAW_PATH)
    team_refresh = read_json(TEAM_REFRESH_PATH)
    v1_rows = read_json(V1_CROSSWALK_PATH)

    result = build_audit(
        fp_doc,
        sleeper_totals,
        sleeper_raw,
        team_refresh,
        v1_rows,
    )

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Normalize report EOF so `git diff --check` never sees an added blank
    # line at EOF. Exactly one trailing newline is intentional.
    OUTPUT_MD.write_text(render_report(result).rstrip() + "\n", encoding="utf-8")

    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")
    print(json.dumps(result["structural_summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

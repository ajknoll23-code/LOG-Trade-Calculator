#!/usr/bin/env python3
"""
capture_realized_outcomes.py

Capture realized 2026 NFL weekly outcomes for longitudinal Trade Desk backtesting.

This is the TARGET side of #2:
  - capture_model_history.py preserves what the model/source evidence said.
  - this file preserves what players actually did afterward.

Critical design rule:
    Do NOT create a second fantasy scoring implementation. This script imports
    score_week() from scripts/model/ppg_pipeline.py, the existing weekly scorer
    for this league's exact custom rules.

Identity:
    Current model keys/positions come from index.html through snapshot_values.py.
    Sleeper IDs come from the refreshed Sleeper raw-category file, which already
    carries Sleeper IDs, names, and fantasy_positions. Existing PPG aliases and
    manual Sleeper-ID overrides are reused for audited edge cases.

Output:
    research/model-history/outcomes/2026.json

The output is refreshed on Tuesday/full maintenance passes. Old completed weeks
are re-fetched intentionally so official Sleeper stat corrections can converge
this target file toward final outcomes rather than freezing an early mistake.

Usage:
    python3 scripts/validation/capture_realized_outcomes.py
    python3 scripts/validation/capture_realized_outcomes.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = REPO_ROOT / "scripts" / "validation"
MODEL_DIR = REPO_ROOT / "scripts" / "model"

sys.path.insert(0, str(VALIDATION_DIR))
sys.path.insert(0, str(MODEL_DIR))
import snapshot_values  # noqa: E402
import ppg_pipeline  # noqa: E402

SEASON = "2026"
INDEX_PATH = REPO_ROOT / "index.html"
SLEEPER_IDENTITY_PATH = (
    REPO_ROOT / "scripts" / "artifacts" / "generated" / "sleeper_2026_raw_categories.json"
)
OUTPUT_PATH = REPO_ROOT / "research" / "model-history" / "outcomes" / f"{SEASON}.json"
SCORING_SOURCE_PATH = REPO_ROOT / "scripts" / "model" / "ppg_pipeline.py"

STATE_URL = "https://api.sleeper.app/v1/state/nfl"
STATS_URL = "https://api.sleeper.app/v1/stats/nfl/regular/{season}/{week}"

# Fields that can affect ppg_pipeline.score_week(), plus active-game markers.
SCORING_FIELDS = (
    "gp", "gms_active",
    "pass_yd", "pass_td", "pass_2pt", "pass_int",
    "rush_att", "rush_yd", "rush_td", "rush_2pt",
    "rec", "rec_yd", "rec_td", "rec_2pt",
    "fum_lost", "fum_rec_td",
    "idp_tkl_solo", "idp_tkl_ast", "idp_tkl_loss",
    "idp_sack", "sack", "idp_qb_hit",
    "idp_int", "int", "idp_fum_rec", "idp_ff", "idp_safety",
    "blk_kick", "idp_td", "idp_pass_def",
    "st_td", "st_ff", "st_fum_rec",
)

# Current PLAYER_DB display keys that intentionally differ from Sleeper's
# canonical player names. These are outcome-layer identity aliases only; they
# do not change production valuation names or the historical PPG pipeline.
OUTCOME_ALIASES = {
    "michael penix jr": "michael penix",
    "bam knight": "zonovan knight",
    "harold perkins jr": "harold perkins",
}

# Audited same-name collisions where name + fantasy position are insufficient.
# These IDs were verified against the refreshed Sleeper pool and the intended
# PLAYER_DB players:
#   Jaylon Jones (IND) -> 11052
#   Byron Young (LAR) -> 10917
OUTCOME_ID_OVERRIDES = {
    "jaylon jones": "11052",
    "byron young": "10917",
}


def normalize_name(value: str) -> str:
    value = (value or "").strip().lower()
    for ch in (".", "'", "\u2019", "-"):
        value = value.replace(ch, "")
    return " ".join(value.split())


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Required file does not exist: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}") from exc


def build_sleeper_identity_index(rows: Any, minimum_ids: int = 500):
    if not isinstance(rows, list):
        raise RuntimeError("Sleeper raw-category identity source must be a JSON list")

    by_name = defaultdict(list)
    by_id = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("sleeper_id") or "").strip()
        name = normalize_name(str(row.get("player") or ""))
        if not sid or not name:
            continue
        compact = {
            "sleeper_id": sid,
            "player": name,
            "pos": row.get("pos"),
            "team": row.get("team"),
            "fantasy_positions": [str(x) for x in (row.get("fantasy_positions") or [])],
        }
        by_name[name].append(compact)
        by_id[sid] = compact

    if len(by_id) < minimum_ids:
        raise RuntimeError(
            f"Sleeper identity source is unexpectedly small: {len(by_id)} IDs "
            f"(minimum required: {minimum_ids})"
        )
    return dict(by_name), by_id


def resolve_model_identities(player_db, by_name, by_id):
    resolved = {}
    unresolved = []

    for model_key, info in player_db.items():
        model_pos = str(info.get("pos") or "")
        model_team = str(info.get("team") or "").upper()
        key = normalize_name(model_key)

        override = OUTCOME_ID_OVERRIDES.get(key) or ppg_pipeline.MANUAL_ID_OVERRIDES.get(key)
        if override and str(override) in by_id:
            row = by_id[str(override)]
            resolved[model_key] = {
                **row,
                "model_key": model_key,
                "model_pos": model_pos,
                "model_team": model_team,
                "match_method": (
                    "outcome_manual_sleeper_id_override"
                    if key in OUTCOME_ID_OVERRIDES
                    else "ppg_manual_sleeper_id_override"
                ),
            }
            continue

        # Prefer the model key itself, then outcome-specific aliases, then the
        # broader historical PPG aliases. Keeping this ordered makes the audit
        # trail deterministic and prevents an alias from overriding an exact
        # canonical Sleeper name.
        search_names = [key]
        for alias in (OUTCOME_ALIASES.get(key), ppg_pipeline.ALIASES.get(key)):
            if alias:
                alias = normalize_name(alias)
                if alias not in search_names:
                    search_names.append(alias)

        chosen = None
        chosen_method = None
        reason = None

        for i, search_name in enumerate(search_names):
            candidates = by_name.get(search_name, [])
            if not candidates:
                continue

            name_method = (
                "exact_name"
                if i == 0
                else ("outcome_alias" if OUTCOME_ALIASES.get(key) == search_name else "ppg_alias")
            )

            if len(candidates) == 1:
                chosen = candidates[0]
                chosen_method = name_method
                break

            # First collision-breaker: model fantasy position.
            pos_matches = [
                c for c in candidates
                if model_pos in (c.get("fantasy_positions") or [])
                or model_pos == c.get("pos")
            ]
            if len(pos_matches) == 1:
                chosen = pos_matches[0]
                chosen_method = f"{name_method}_position_disambiguated"
                break

            # Second collision-breaker: current PLAYER_DB team. This resolves
            # legitimate same-name/same-fantasy-position cases such as:
            #   Jaylon Jones IND vs Jaylon Jones CHI
            #   Byron Young LAR vs Byron Young PHI
            # without hard-coding those player IDs into this script.
            team_pool = pos_matches if pos_matches else candidates
            if model_team:
                team_matches = [
                    c for c in team_pool
                    if str(c.get("team") or "").upper() == model_team
                ]
                if len(team_matches) == 1:
                    chosen = team_matches[0]
                    chosen_method = f"{name_method}_team_disambiguated"
                    break
            else:
                team_matches = []

            reason = (
                f"{len(candidates)} candidates for {search_name!r}; "
                f"{len(pos_matches)} matched model position {model_pos!r}; "
                f"{len(team_matches)} matched model team {model_team!r}"
            )

        if chosen:
            resolved[model_key] = {
                **chosen,
                "model_key": model_key,
                "model_pos": model_pos,
                "model_team": model_team,
                "match_method": chosen_method,
            }
        else:
            unresolved.append({
                "model_key": model_key,
                "model_pos": model_pos,
                "model_team": model_team,
                "reason": reason or "no Sleeper identity candidate",
            })

    coverage = len(resolved) / max(1, len(player_db))
    if coverage < 0.95:
        raise RuntimeError(
            f"Only {len(resolved)}/{len(player_db)} model keys resolved to Sleeper IDs "
            f"({coverage:.1%}); refusing to capture a materially incomplete outcome target."
        )
    return resolved, unresolved


def compact_scoring_stats(stats):
    out = {}
    for field in SCORING_FIELDS:
        value = stats.get(field)
        if value not in (None, "", 0, 0.0, False):
            out[field] = value
    return out


def get_json_with_retries(url: str):
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 404:
                return {}
            response.raise_for_status()
            payload = response.json()
            if payload is None:
                return {}
            if not isinstance(payload, dict):
                raise RuntimeError(f"Expected JSON object from {url}")
            return payload
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed after 3 attempts: {url}: {last_error}")


def fetch_state():
    return get_json_with_retries(STATE_URL)


def fetch_week(week: int):
    return get_json_with_retries(STATS_URL.format(season=SEASON, week=week))


def build_week_rows(week_data, resolved):
    id_groups = {}
    for model_key, identity in resolved.items():
        sid = identity["sleeper_id"]
        group = id_groups.setdefault(sid, {
            "sleeper_id": sid,
            "player": identity.get("player"),
            "team": identity.get("team"),
            "model_keys": [],
            "model_positions": [],
        })
        group["model_keys"].append(model_key)
        if identity["model_pos"] not in group["model_positions"]:
            group["model_positions"].append(identity["model_pos"])

    rows = []
    for sid, group in id_groups.items():
        stats = week_data.get(sid)
        if not isinstance(stats, dict):
            continue
        # Same active-game convention as the proven PPG pipeline.
        if (stats.get("gp") or 0) < 1:
            continue
        rows.append({
            "sleeper_id": sid,
            "player": group["player"],
            "team": group["team"],
            "model_keys": sorted(group["model_keys"]),
            "model_positions": sorted(group["model_positions"]),
            "fantasy_points": round(ppg_pipeline.score_week(stats), 2),
            "raw_stats_used": compact_scoring_stats(stats),
        })

    rows.sort(key=lambda r: (r["model_positions"], r["player"] or "", r["sleeper_id"]))
    return rows


def build_outcomes(state_fetcher=fetch_state, week_fetcher=fetch_week):
    cfg = snapshot_values.load_from_html(INDEX_PATH)
    player_db = cfg["player_db"]

    identity_rows = load_json(SLEEPER_IDENTITY_PATH)
    by_name, by_id = build_sleeper_identity_index(identity_rows)
    resolved, unresolved = resolve_model_identities(player_db, by_name, by_id)

    grouped_ids = defaultdict(list)
    for model_key, identity in resolved.items():
        grouped_ids[identity["sleeper_id"]].append(model_key)
    duplicate_groups = {
        sid: sorted(keys) for sid, keys in grouped_ids.items() if len(keys) > 1
    }

    state = state_fetcher() or {}
    state_season = str(state.get("season") or SEASON)
    state_week = int(state.get("week") or 1)
    max_week_to_check = min(18, max(1, state_week)) if state_season == SEASON else 18

    weeks = {}
    for week in range(1, max_week_to_check + 1):
        rows = build_week_rows(week_fetcher(week), resolved)
        if rows:
            weeks[str(week)] = {
                "player_count": len(rows),
                "total_fantasy_points": round(sum(r["fantasy_points"] for r in rows), 2),
                "players": rows,
            }

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": 1,
        "season": SEASON,
        "refreshed_at_utc": now,
        "sleeper_state_at_refresh": state,
        "source": "Sleeper regular-season weekly stats",
        "source_url_template": STATS_URL,
        "scoring_source": "scripts/model/ppg_pipeline.py::score_week",
        "scoring_source_sha256": sha256_file(SCORING_SOURCE_PATH),
        "identity_source": str(SLEEPER_IDENTITY_PATH.relative_to(REPO_ROOT)),
        "model_source": "index.html::PLAYER_DB",
        "model_key_count": len(player_db),
        "resolved_model_key_count": len(resolved),
        "identity_coverage_pct": round(100 * len(resolved) / max(1, len(player_db)), 2),
        "unique_resolved_sleeper_ids": len(grouped_ids),
        "duplicate_model_key_identity_groups": duplicate_groups,
        "unresolved_model_keys": unresolved,
        "weeks_with_realized_data": sorted(int(w) for w in weeks),
        "weeks": weeks,
    }


def write_outcomes(payload):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Realized outcomes saved: {OUTPUT_PATH.relative_to(REPO_ROOT)} | "
        f"identity={payload['resolved_model_key_count']}/{payload['model_key_count']} "
        f"({payload['identity_coverage_pct']}%) | "
        f"weeks={payload['weeks_with_realized_data']}"
    )
    if payload["unresolved_model_keys"]:
        print(
            f"WARNING: {len(payload['unresolved_model_keys'])} model keys were unresolved; "
            "details are preserved in the output audit section."
        )


def run_selftest():
    offense = {
        "gp": 1,
        "pass_yd": 325,
        "pass_td": 2,
        "pass_int": 1,
        "rush_att": 5,
        "rush_yd": 25,
    }
    expected_offense = ppg_pipeline.score_week(offense)
    assert expected_offense == 24.5, expected_offense

    idp = {
        "gp": 1,
        "idp_tkl_solo": 8,
        "idp_tkl_ast": 4,
        "idp_tkl_loss": 2,
        "idp_sack": 2,
        "idp_qb_hit": 3,
        "idp_pass_def": 3,
    }
    expected_idp = ppg_pipeline.score_week(idp)
    assert expected_idp == 46.0, expected_idp

    synthetic_resolved = {
        "test qb": {
            "sleeper_id": "1", "player": "test qb", "team": "TST",
            "model_key": "test qb", "model_pos": "QB", "match_method": "synthetic",
        },
        "test lb": {
            "sleeper_id": "2", "player": "test lb", "team": "TST",
            "model_key": "test lb", "model_pos": "LB", "match_method": "synthetic",
        },
    }
    # Identity regression: aliases + same-name/team disambiguation that were
    # found by the first real 565-player outcome capture.
    synthetic_player_db = {
        "michael penix jr": {"pos": "QB", "team": "ATL"},
        "bam knight": {"pos": "RB", "team": "ARI"},
        "harold perkins jr": {"pos": "LB", "team": "ATL"},
        "jaylon jones": {"pos": "DB", "team": "IND"},
        "byron young": {"pos": "DL", "team": "LAR"},
    }
    synthetic_identity_rows = [
        {"sleeper_id": "11559", "player": "michael penix", "pos": "QB", "team": "ATL", "fantasy_positions": ["QB"]},
        {"sleeper_id": "8122", "player": "zonovan knight", "pos": "RB", "team": "ARI", "fantasy_positions": ["RB"]},
        {"sleeper_id": "13555", "player": "harold perkins", "pos": "LB", "team": "ATL", "fantasy_positions": ["LB"]},
        {"sleeper_id": "11052", "player": "jaylon jones", "pos": "DB", "team": "IND", "fantasy_positions": ["DB"]},
        {"sleeper_id": "8702", "player": "jaylon jones", "pos": "CB", "team": "CHI", "fantasy_positions": ["DB"]},
        {"sleeper_id": "10917", "player": "byron young", "pos": "LB", "team": "LAR", "fantasy_positions": ["DL", "LB"]},
        {"sleeper_id": "10925", "player": "byron young", "pos": "DL", "team": "PHI", "fantasy_positions": ["DL"]},
    ]
    syn_by_name, syn_by_id = build_sleeper_identity_index(
        synthetic_identity_rows, minimum_ids=1
    )
    syn_resolved, syn_unresolved = resolve_model_identities(
        synthetic_player_db, syn_by_name, syn_by_id
    )
    assert not syn_unresolved, syn_unresolved
    assert syn_resolved["michael penix jr"]["sleeper_id"] == "11559"
    assert syn_resolved["bam knight"]["sleeper_id"] == "8122"
    assert syn_resolved["harold perkins jr"]["sleeper_id"] == "13555"
    assert OUTCOME_ID_OVERRIDES["jaylon jones"] == "11052"
    assert OUTCOME_ID_OVERRIDES["byron young"] == "10917"
    assert syn_resolved["jaylon jones"]["sleeper_id"] == "11052"
    assert syn_resolved["byron young"]["sleeper_id"] == "10917"

    rows = build_week_rows({"1": offense, "2": idp, "3": {"gp": 0, "rec": 10}}, synthetic_resolved)
    assert len(rows) == 2
    by_sid = {r["sleeper_id"]: r for r in rows}
    assert by_sid["1"]["fantasy_points"] == expected_offense
    assert by_sid["2"]["fantasy_points"] == expected_idp
    assert "pass_yd" in by_sid["1"]["raw_stats_used"]
    assert "gp" in by_sid["1"]["raw_stats_used"]

    print(
        "capture_realized_outcomes self-test passed: reused ppg_pipeline.score_week "
        "for offense + IDP and excluded gp=0 rows."
    )


def main():
    parser = argparse.ArgumentParser(description="Capture realized Sleeper outcomes for backtesting.")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        run_selftest()
        return
    write_outcomes(build_outcomes())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
scripts/maintenance/team_field_refresh_pipeline.py

Fixes item #6 from the four-AI-review priority list: the `team` field in
PLAYER_DB is permanently stale. Root cause, confirmed by reading
mergeLiveRoster()/mergeLeagueRosters() in index.html directly: the live
Sleeper ROSTER sync payload those functions consume has no `team` field
at all to refresh FROM, so `team` gets explicitly carried forward from
whatever was last hand-baked into PLAYER_DB, forever, no matter how
stale it gets. That carry-forward was itself a real, deliberate fix
(2026-08-20) for a worse bug (team silently wiped to nothing on every
page load) -- so the right fix here is not to remove the carry-forward,
it's to give it something genuinely fresh to carry forward INSTEAD OF
the old hand-baked value.

This script fetches Sleeper's live full player pool (same endpoint,
same 20-hour cache convention as sync_sleeper.py -- Sleeper asks that
the ~5MB /players/nfl dump be called at most once per day, so this
reuses data/players_cache.json if it's fresh rather than hitting the
API again) and extracts a clean {normalized_name: team_abbr} lookup for
every player with a real current team, ready to bake into index.html as
a new PLAYER_TEAM constant -- matching the same baked-table convention
already used for PROD_MULT_DATA, ROLE_MULT, etc.

INTENDED FLOW (matches this project's established pattern -- Claude
performs the actual index.html edit in-session, not an autonomous
script): run this via the matching GitHub Actions workflow, which
commits scripts/player_team_refresh.json. Upload that file back for the
PLAYER_TEAM constant to be baked in and mergeLiveRoster()/
mergeLeagueRosters() updated to use it as the primary team source
(existing.team remains the fallback for any player this fresh pull
doesn't cover, same safety net as before -- just no longer the ONLY
source).

REQUIRES NETWORK ACCESS (fetches live Sleeper data, or reuses a fresh
cache in data/players_cache.json if one already exists from another
pipeline's recent run).

USAGE: python3 scripts/maintenance/team_field_refresh_pipeline.py
Add --selftest to sanity-check the name-normalization and pool-parsing
logic against synthetic data before trusting real output.

OUTPUT: scripts/player_team_refresh.json
  {generated_at, source, n_players, teams_by_sleeper_id, teams, name_collisions}

`teams_by_sleeper_id` is canonical. `teams` is a collision-safe normalized-name
fallback retained for the current manual bake workflow.
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

BASE = "https://api.sleeper.app/v1"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(SCRIPT_DIR)
ROOT = os.path.dirname(SCRIPTS_DIR)
DATA_DIR = os.path.join(ROOT, "data")
OUT_PATH = os.path.join(SCRIPTS_DIR, "player_team_refresh.json")

PLAYERS_CACHE_MAX_AGE_SECONDS = 20 * 60 * 60  # 20 hours -- same as sync_sleeper.py


def normalize_name(s):
    """Identical to index.html's normalizeName() and every other
    Python pipeline's normalize_name() in this project -- kept in sync
    manually across files, same convention throughout."""
    return re.sub(r"\s+", " ", re.sub(r"[.'\u2019-]", "", s.strip().lower()))


def fetch_json(url, retries=3, backoff=2):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "trade-desk-team-refresh/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")


def load_players_cache():
    """Identical logic to sync_sleeper.py's load_players_cache() -- reused
    so this script doesn't force a redundant ~5MB fetch if sync_sleeper.py
    (or this script, on a prior run) already pulled a fresh pool today."""
    path = os.path.join(DATA_DIR, "players_cache.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            cache = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    fetched_at = cache.get("_fetched_at", 0)
    if time.time() - fetched_at > PLAYERS_CACHE_MAX_AGE_SECONDS:
        return None
    return cache


def load_or_fetch_full_pool():
    cache = load_players_cache()
    if cache is not None:
        print("Reusing existing fresh player-pool cache (<20h old).")
        return cache["players"]
    print("Players cache stale or missing -- pulling full /players/nfl dump (~5MB)...")
    pool = fetch_json(f"{BASE}/players/nfl")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "players_cache.json"), "w") as f:
        json.dump({"_fetched_at": time.time(), "players": pool}, f)
    print(f"Cached {len(pool)} players.")
    return pool


def extract_team_maps(pool):
    """Build collision-safe team mappings from Sleeper's stable player IDs.

    Primary output is `teams_by_sleeper_id`; names are only a convenience
    fallback. A normalized name is included in `teams_by_name` ONLY when all
    active rows carrying that name agree on one team. Ambiguous names are
    emitted separately in `name_collisions` and are never silently overwritten.
    """
    teams_by_sleeper_id = {}
    name_rows = {}
    skipped_no_team = 0

    for pid, p in pool.items():
        team = p.get("team")
        if not team:
            skipped_no_team += 1
            continue
        first = p.get("first_name") or ""
        last = p.get("last_name") or ""
        name = (first + " " + last).strip() or p.get("full_name")
        if not name:
            continue
        key = normalize_name(name)
        teams_by_sleeper_id[str(pid)] = team
        name_rows.setdefault(key, []).append({
            "sleeper_id": str(pid),
            "team": team,
            "position": p.get("position"),
            "fantasy_positions": p.get("fantasy_positions") or [],
        })

    teams_by_name = {}
    name_collisions = {}
    for key, rows in name_rows.items():
        distinct_teams = sorted({r["team"] for r in rows})
        if len(rows) == 1 or len(distinct_teams) == 1:
            teams_by_name[key] = distinct_teams[0]
        else:
            name_collisions[key] = rows

    print(
        f"  {len(teams_by_sleeper_id)} active Sleeper-ID team rows, "
        f"{len(teams_by_name)} collision-safe name fallbacks, "
        f"{len(name_collisions)} ambiguous names, "
        f"{skipped_no_team} without a current team."
    )
    return teams_by_sleeper_id, teams_by_name, name_collisions


def run_selftest():
    print("Running self-test on synthetic data...")

    synthetic_pool = {
        "1": {"first_name": "Josh", "last_name": "Allen", "team": "BUF", "position": "QB"},
        "2": {"first_name": "Free", "last_name": "Agent", "team": None, "position": "WR"},
        "3": {"first_name": "D'Andre", "last_name": "Swift-Jones", "team": "CHI", "position": "RB"},
        "4": {"first_name": "Byron", "last_name": "Murphy", "team": "MIN", "position": "CB"},
        "5": {"first_name": "Byron", "last_name": "Murphy", "team": "SEA", "position": "DT"},
    }
    by_id, by_name, collisions = extract_team_maps(synthetic_pool)
    assert by_id["1"] == "BUF"
    assert "2" not in by_id
    assert by_name.get("dandre swiftjones") == "CHI"
    assert "byron murphy" not in by_name, "ambiguous name must never be silently overwritten"
    assert len(collisions["byron murphy"]) == 2
    print("  Stable-ID mapping and collision-safe name fallback -- OK")
    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

    pool = load_or_fetch_full_pool()
    print(f"Full pool size: {len(pool)} players.")

    teams_by_id, teams_by_name, name_collisions = extract_team_maps(pool)

    output = {
        "generated_at": time.time(),
        "source": "sleeper_live_pool",
        "n_players": len(teams_by_id),
        "teams_by_sleeper_id": dict(sorted(teams_by_id.items())),
        "teams": dict(sorted(teams_by_name.items())),
        "name_collisions": dict(sorted(name_collisions.items())),
    }
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
scripts/team_field_refresh_pipeline.py

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

USAGE: python3 scripts/team_field_refresh_pipeline.py
Add --selftest to sanity-check the name-normalization and pool-parsing
logic against synthetic data before trusting real output.

OUTPUT: scripts/player_team_refresh.json
  {generated_at, source: "sleeper_live_pool", n_players, teams: {name: team}}
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
ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(ROOT, "data")
OUT_PATH = os.path.join(SCRIPT_DIR, "player_team_refresh.json")

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


def extract_team_lookup(pool):
    """Returns {normalized_name: team_abbr} for every player with a real
    current team. Players with no current team (free agents, retired,
    practice-squad-only) are simply omitted -- their PLAYER_DB entry
    keeps whatever it already had (the existing fallback), which is
    correct: this script asserts positive fresh facts, it doesn't assert
    "definitely no team" for anyone."""
    lookup = {}
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
        lookup[normalize_name(name)] = team
    print(f"  {len(lookup)} players with a real current team, {skipped_no_team} without one (skipped, not zeroed out).")
    return lookup


def run_selftest():
    print("Running self-test on synthetic data...")

    synthetic_pool = {
        "1": {"first_name": "Josh", "last_name": "Allen", "team": "BUF"},
        "2": {"first_name": "Free", "last_name": "Agent", "team": None},
        "3": {"first_name": "D'Andre", "last_name": "Swift-Jones", "team": "CHI"},  # tests apostrophe/hyphen normalization
    }
    lookup = extract_team_lookup(synthetic_pool)
    assert lookup.get("josh allen") == "BUF", f"expected josh allen -> BUF, got {lookup.get('josh allen')}"
    assert "free agent" not in lookup, "expected a player with no team to be omitted, not zeroed out"
    assert lookup.get("dandre swiftjones") == "CHI", \
        f"expected apostrophe/hyphen-stripped normalization to match index.html's convention, got {lookup}"
    print("  Team extraction and name normalization behave correctly on synthetic data -- OK")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()

    pool = load_or_fetch_full_pool()
    print(f"Full pool size: {len(pool)} players.")

    lookup = extract_team_lookup(pool)

    output = {
        "generated_at": time.time(),
        "source": "sleeper_live_pool",
        "n_players": len(lookup),
        "teams": dict(sorted(lookup.items())),
    }
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

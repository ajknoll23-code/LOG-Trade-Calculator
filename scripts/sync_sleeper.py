#!/usr/bin/env python3
"""
Pulls live league data from Sleeper's public read-only API and writes
resolved (player-ID -> name) JSON files into /data for the trade desk
tool (and Claude, via a pasted raw.githubusercontent.com URL) to consume.

Sleeper API notes (see https://docs.sleeper.com/):
- No auth required, but the full /players/nfl dump is ~5MB and Sleeper
  asks that it be called at most once per day. We cache it in
  data/players_cache.json and only refetch if that cache is missing,
  malformed, or older than 20 hours.
- Rosters/users/traded_picks are small and cheap to call every run.
"""
import json
import os
import time
import urllib.request
import urllib.error

BASE = "https://api.sleeper.app/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(ROOT, "data")
CONFIG_PATH = os.path.join(ROOT, "config.json")

PLAYERS_CACHE_MAX_AGE_SECONDS = 20 * 60 * 60  # 20 hours


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def fetch_json(url, retries=3, backoff=2):
    """GET a URL and parse JSON, with basic retry on transient failures."""
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "loyal-dynasty-sync/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")


def load_players_cache():
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


def build_players_index(needed_ids):
    """
    Return {player_id: {name, position, team, age}} for exactly the IDs we
    need (every player who appears in any roster, taxi, or reserve slot this
    run). Reuses the cached full dump if it's fresh enough; otherwise pulls
    the full /players/nfl dump once and re-caches it.
    """
    cache = load_players_cache()
    if cache is not None:
        pool = cache["players"]
    else:
        print("Players cache stale or missing — pulling full /players/nfl dump (~5MB)...")
        pool = fetch_json(f"{BASE}/players/nfl")
        with open(os.path.join(DATA_DIR, "players_cache.json"), "w") as f:
            json.dump({"_fetched_at": time.time(), "players": pool}, f)
        print(f"Cached {len(pool)} players.")

    index = {}
    missing = []
    for pid in needed_ids:
        p = pool.get(pid)
        if not p:
            missing.append(pid)
            continue
        first = p.get("first_name") or ""
        last = p.get("last_name") or ""
        name = (first + " " + last).strip() or p.get("full_name") or f"Player {pid}"
        index[pid] = {
            "name": name,
            "position": p.get("position"),
            "team": p.get("team"),
            "age": p.get("age"),
            "status": p.get("status"),
            "injury_status": p.get("injury_status"),
        }

    if missing:
        for pid in missing:
            if pid.isalpha() and len(pid) <= 3:
                index[pid] = {"name": f"{pid} DEF", "position": "DEF", "team": pid,
                               "age": None, "status": None, "injury_status": None}
            else:
                print(f"WARNING: player_id {pid} not found in players pool")
                index[pid] = {"name": f"Unknown ({pid})", "position": None, "team": None,
                               "age": None, "status": None, "injury_status": None}

    return index


def resolve_roster(roster, players_index):
    def resolve_list(ids):
        return [players_index.get(pid, {"name": f"Unknown ({pid})"}) | {"player_id": pid}
                for pid in (ids or [])]

    starters = set(roster.get("starters") or [])
    all_players = set(roster.get("players") or [])
    taxi = set(roster.get("taxi") or [])
    reserve = set(roster.get("reserve") or [])
    bench = all_players - starters - taxi - reserve

    return {
        "roster_id": roster["roster_id"],
        "owner_id": roster.get("owner_id"),
        "starters": resolve_list(roster.get("starters")),
        "bench": resolve_list(sorted(bench)),
        "taxi": resolve_list(sorted(taxi)),
        "reserve_ir": resolve_list(sorted(reserve)),
        "settings": roster.get("settings"),
    }


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    config = load_config()
    league_id = config["league_id"]

    print(f"Syncing league {league_id}...")

    users = fetch_json(f"{BASE}/league/{league_id}/users")
    rosters_raw = fetch_json(f"{BASE}/league/{league_id}/rosters")
    traded_picks = fetch_json(f"{BASE}/league/{league_id}/traded_picks")

    owner_map = {
        u["user_id"]: {
            "username": u.get("display_name"),
            "team_name": (u.get("metadata") or {}).get("team_name") or u.get("display_name"),
        }
        for u in users
    }

    needed_ids = set()
    for r in rosters_raw:
        needed_ids.update(r.get("players") or [])
    players_index = build_players_index(needed_ids)

    resolved_rosters = []
    my_roster = None
    for r in rosters_raw:
        resolved = resolve_roster(r, players_index)
        owner = owner_map.get(resolved["owner_id"], {})
        resolved["owner_username"] = owner.get("username")
        resolved["team_name"] = owner.get("team_name")
        resolved_rosters.append(resolved)
        if owner.get("username") == config.get("my_username"):
            my_roster = resolved

    with open(os.path.join(DATA_DIR, "league_rosters.json"), "w") as f:
        json.dump({"synced_at": time.time(), "league_id": league_id,
                    "rosters": resolved_rosters}, f, indent=2)

    if my_roster is not None:
        with open(os.path.join(DATA_DIR, "my_roster.json"), "w") as f:
            json.dump({"synced_at": time.time(), "team_name": my_roster["team_name"],
                        **my_roster}, f, indent=2)
        print(f"Wrote my_roster.json for '{my_roster['team_name']}' "
              f"({len(my_roster['starters']) + len(my_roster['bench']) + len(my_roster['taxi'])} players)")
    else:
        print(f"WARNING: could not find a roster owned by '{config.get('my_username')}' "
              f"— check config.json")

    with open(os.path.join(DATA_DIR, "draft_picks.json"), "w") as f:
        json.dump({"synced_at": time.time(), "traded_picks": traded_picks}, f, indent=2)

    with open(os.path.join(DATA_DIR, "last_synced.json"), "w") as f:
        json.dump({"synced_at": time.time(),
                    "synced_at_readable": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}, f, indent=2)

    print("Sync complete.")


if __name__ == "__main__":
    main()

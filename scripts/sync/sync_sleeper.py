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

Canonical implementation:
    python3 scripts/sync/sync_sleeper.py
"""
import json
import os
import time
import urllib.request
import urllib.error
import sys

BASE = "https://api.sleeper.app/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS_DIR)
DATA_DIR = os.path.join(ROOT, "data")
CONFIG_PATH = os.path.join(ROOT, "config.json")

PLAYERS_CACHE_MAX_AGE_SECONDS = 20 * 60 * 60  # 20 hours

# Sleeper occasionally carries obviously corrupt DOB/age rows in its global
# player dump. Keep overrides stable-ID based and explicit rather than guessing
# from names. Anquin Barnes Jr. (NYG, Sleeper 13869) is age 23 for the 2026
# season; Sleeper currently reports age 3 / birth_date 2022-10-21.
PLAYER_AGE_OVERRIDES = {
    "13869": 23,
}


def safe_player_age(player_id, player):
    """Return a plausible age, an explicit stable-ID override, or None.

    None is allowed for genuinely missing age data and lets the UI use its
    documented fallback. A non-null but implausible source age is treated as
    corrupt rather than trusted.
    """
    pid = str(player_id)
    if pid in PLAYER_AGE_OVERRIDES:
        return PLAYER_AGE_OVERRIDES[pid]
    age = player.get("age")
    if age is None:
        return None
    try:
        age = int(age)
    except (TypeError, ValueError):
        return None
    return age if 18 <= age <= 45 else None


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


def load_or_fetch_full_pool():
    """Return the full Sleeper /players/nfl dump (thousands of players),
    using the 20h cache if fresh, else pulling fresh and re-caching."""
    cache = load_players_cache()
    if cache is not None:
        return cache["players"]
    print("Players cache stale or missing — pulling full /players/nfl dump (~5MB)...")
    pool = fetch_json(f"{BASE}/players/nfl")
    with open(os.path.join(DATA_DIR, "players_cache.json"), "w") as f:
        json.dump({"_fetched_at": time.time(), "players": pool}, f)
    print(f"Cached {len(pool)} players.")
    return pool


def build_players_index(needed_ids, pool):
    """
    Return {player_id: {name, position, team, age}} for exactly the IDs we
    need (every player who appears in any roster, taxi, or reserve slot this
    run), given an already-loaded full player pool.
    """
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
            "fantasy_positions": p.get("fantasy_positions") or [],
            "team": p.get("team"),
            "age": safe_player_age(pid, p),
            "status": p.get("status"),
            "injury_status": p.get("injury_status"),
        }

    if missing:
        # DEF/team-defense entries use team abbreviations (e.g. "DET") as
        # their "player_id" instead of a numeric ID, and aren't in the
        # players dump the same way. Handle those, log anything else.
        for pid in missing:
            if pid.isalpha() and len(pid) <= 3:
                index[pid] = {"name": f"{pid} DEF", "position": "DEF", "fantasy_positions": ["DEF"],
                               "team": pid, "age": None, "status": None, "injury_status": None}
            else:
                print(f"WARNING: player_id {pid} not found in players pool")
                index[pid] = {"name": f"Unknown ({pid})", "position": None, "fantasy_positions": [],
                               "team": None, "age": None, "status": None, "injury_status": None}

    return index


# Sleeper's fine-grained position labels, collapsed to the buckets this
# tool's scoring model actually uses (mirrors normalizePos() in the JS
# tool, kept in sync manually since this is a separate Python script).
POS_BUCKET = {
    "DE": "DL", "DT": "DL", "DL": "DL", "OLB": "LB", "ILB": "LB", "LB": "LB",
    "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB",
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE",
}
def eligible_buckets(fantasy_positions):
    """Collapse Sleeper eligibility to Trade Desk buckets while preserving
    Sleeper's original order. The first unique bucket is the canonical
    primary-position convention used by index.html.
    """
    eligible = []
    for fp in fantasy_positions or []:
        bucket = POS_BUCKET.get(fp)
        if bucket and bucket not in eligible:
            eligible.append(bucket)
    return eligible


def pick_best_position(fantasy_positions, fallback_raw_pos):
    """Python port of the CURRENT pickBestPosition() rule in index.html.

    For dual-eligible players, Sleeper's first-listed fantasy position wins.
    We deliberately do NOT choose whichever eligible bucket has the highest
    Trade Desk POSITION_WEIGHT; that retired rule silently changed valuation
    position based on economics rather than football eligibility/primacy.
    """
    eligible = eligible_buckets(fantasy_positions)
    if not eligible:
        return POS_BUCKET.get(fallback_raw_pos)
    return eligible[0]


def compute_free_agents(pool, rostered_ids):
    """
    Full player pool minus everyone rostered on any of the 12 teams,
    filtered to fantasy-relevant positions with a real current NFL team
    (excludes retired/out-of-league players, kickers, team defenses, and
    anyone Sleeper doesn't have an active NFL team on file for). Computed
    server-side here rather than shipping the full ~5MB raw dump to a
    browser and filtering client-side — this file stays a few hundred
    entries, not thousands.
    """
    free_agents = []
    for pid, p in pool.items():
        if pid in rostered_ids:
            continue
        if not p.get("team"):
            continue
        # Sleeper's global dump contains legacy/duplicate rows that can still
        # retain a team/status even when explicitly marked inactive. These are
        # not current waiver-wire players and previously leaked names such as
        # Dwayne Haskins, Keith Butler, and several "Duplicate Player" rows
        # into the free-agent board.
        if p.get("active") is False:
            continue
        age = safe_player_age(pid, p)
        # Missing age is common for legitimate rookies and remains allowed; an
        # explicitly present but impossible age is a source-data corruption.
        # Exclude it unless a stable-ID override above has been verified.
        if p.get("age") is not None and age is None:
            continue
        raw_pos = p.get("position")
        bucket = pick_best_position(p.get("fantasy_positions"), raw_pos)
        if not bucket:
            continue
        first = p.get("first_name") or ""
        last = p.get("last_name") or ""
        name = (first + " " + last).strip() or p.get("full_name") or f"Player {pid}"
        free_agents.append({
            "player_id": pid,
            "name": name,
            "pos": bucket,
            "raw_position": raw_pos,
            "fantasy_positions": p.get("fantasy_positions") or [],
            "eligible_buckets": eligible_buckets(p.get("fantasy_positions")),
            "team": p.get("team"),
            "age": age,
            "status": p.get("status"),
            "injury_status": p.get("injury_status"),
        })
    return free_agents


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


def compute_roster_changes(data_dir, new_rosters):
    """
    Diff the new roster pull against whatever league_rosters.json already
    exists on disk from the previous sync, to catch real mid-cycle trades/
    adds without needing a dedicated historical database — just compares
    today's pull to yesterday's. Returns [] on a true first run (nothing
    to diff against yet) rather than flagging every single player as
    "new," which would be noise, not signal.
    """
    old_path = os.path.join(data_dir, "league_rosters.json")
    if not os.path.exists(old_path):
        return []
    try:
        with open(old_path) as f:
            old_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    def flatten(rosters):
        mapping = {}
        for r in rosters:
            for slot in ("starters", "bench", "taxi", "reserve_ir"):
                for p in r.get(slot) or []:
                    mapping[p["player_id"]] = {"roster_id": r["roster_id"], "team_name": r.get("team_name"), "name": p.get("name")}
        return mapping

    old_map = flatten(old_data.get("rosters") or [])
    new_map = flatten(new_rosters)

    changes = []
    for pid, new_info in new_map.items():
        old_info = old_map.get(pid)
        if old_info is None:
            continue
        if old_info["roster_id"] != new_info["roster_id"]:
            changes.append({
                "player_id": pid, "name": new_info["name"],
                "old_team": old_info["team_name"], "new_team": new_info["team_name"],
            })
    return changes


def run_selftest():
    assert pick_best_position(["DE", "LB"], "DE") == "DL"
    assert pick_best_position(["LB", "DE"], "DE") == "LB"
    assert pick_best_position(["CB", "S"], "CB") == "DB"
    assert pick_best_position([], "DT") == "DL"

    pool = {
        "1": {
            "first_name": "Dual", "last_name": "Edge", "team": "ARI",
            "position": "DE", "fantasy_positions": ["DE", "LB"],
            "age": 24, "status": "Active", "active": True, "injury_status": None,
        },
        "2": {
            "first_name": "Rostered", "last_name": "Player", "team": "BUF",
            "position": "LB", "fantasy_positions": ["LB"], "active": True,
        },
        "3": {
            "first_name": "Legacy", "last_name": "Ghost", "team": "SEA",
            "position": "LB", "fantasy_positions": ["LB"],
            "age": 62, "status": "Active", "active": False,
        },
        "4": {
            "first_name": "Bad", "last_name": "Age", "team": "HOU",
            "position": "S", "fantasy_positions": ["DB"],
            "age": 52, "status": "Active", "active": True,
        },
        "13869": {
            "first_name": "Anquin", "last_name": "Barnes", "team": "NYG",
            "position": "DT", "fantasy_positions": ["DL"],
            "age": 3, "status": "Active", "active": True,
        },
        "5": {
            "first_name": "Unknown", "last_name": "Age", "team": "GB",
            "position": "WR", "fantasy_positions": ["WR"],
            "age": None, "status": "Active", "active": True,
        },
    }
    rows = compute_free_agents(pool, {"2"})
    by_id = {r["player_id"]: r for r in rows}
    assert set(by_id) == {"1", "13869", "5"}, by_id
    assert by_id["1"]["pos"] == "DL"
    assert by_id["1"]["fantasy_positions"] == ["DE", "LB"]
    assert by_id["1"]["eligible_buckets"] == ["DL", "LB"]
    assert by_id["13869"]["age"] == 23
    assert by_id["5"]["age"] is None
    assert safe_player_age("4", pool["4"]) is None
    print("sync_sleeper self-test passed.")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

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
    full_pool = load_or_fetch_full_pool()
    players_index = build_players_index(needed_ids, full_pool)

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

    free_agents = compute_free_agents(full_pool, needed_ids)
    with open(os.path.join(DATA_DIR, "free_agents.json"), "w") as f:
        json.dump({"synced_at": time.time(), "league_id": league_id,
                    "count": len(free_agents), "free_agents": free_agents}, f, indent=2)
    print(f"Wrote free_agents.json ({len(free_agents)} unrostered fantasy-relevant players)")

    roster_changes = compute_roster_changes(DATA_DIR, resolved_rosters)
    if roster_changes:
        print(f"Detected {len(roster_changes)} mid-cycle roster change(s) since the last sync:")
        for c in roster_changes:
            print(f"  {c['name']}: {c['old_team']} -> {c['new_team']}")

    with open(os.path.join(DATA_DIR, "league_rosters.json"), "w") as f:
        json.dump({"synced_at": time.time(), "league_id": league_id,
                    "rosters": resolved_rosters, "recent_changes": roster_changes}, f, indent=2)

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

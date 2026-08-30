#!/usr/bin/env python3
"""
Walks the league's dynasty history (via previous_league_id) back as far as
it goes, and pulls every completed trade from every season — specifically
ones that included at least one draft pick — into a single file. That's the
raw material for calibrating PICK_BASE / YEAR_DISCOUNT in the trade desk
tool against how picks have actually traded in this league, instead of a
made-up curve.

Each season's scoring_settings and roster_positions get recorded alongside
its trades, since this league's IDP scoring and starting-lineup size have
both changed across seasons (see README note below) — a trade from a season
with different scarcity/scoring isn't directly comparable to one from today
without that context.
"""
import json
import os
import time
import urllib.request
import urllib.error

BASE = "https://api.sleeper.app/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS_DIR)
DATA_DIR = os.path.join(ROOT, "data")
CONFIG_PATH = os.path.join(ROOT, "config.json")

MAX_WEEK = 18

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def fetch_json(url, retries=3, backoff=2, allow_404=False):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "loyal-dynasty-sync/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if allow_404 and e.code == 404:
                return None
            last_err = e
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
        if attempt < retries - 1:
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")

def walk_season_chain(start_league_id):
    seasons = []
    league_id = start_league_id
    seen = set()
    while league_id and league_id not in seen:
        seen.add(league_id)
        info = fetch_json(f"{BASE}/league/{league_id}")
        seasons.append((league_id, info))
        league_id = info.get("previous_league_id")
    seasons.reverse()
    return seasons

def load_players_cache():
    path = os.path.join(DATA_DIR, "players_cache.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f).get("players", {})
    except (json.JSONDecodeError, OSError):
        return {}

def resolve_player_name(pid, players_pool):
    p = players_pool.get(pid)
    if not p:
        if pid and pid.isalpha() and len(pid) <= 3:
            return f"{pid} DEF"
        return f"Unknown ({pid})"
    name = (f"{p.get('first_name','')} {p.get('last_name','')}").strip()
    return name or p.get("full_name") or f"Player {pid}"

def pull_season_trades(league_id, season, players_pool, owner_map):
    trades = []
    for week in range(1, MAX_WEEK + 1):
        txns = fetch_json(f"{BASE}/league/{league_id}/transactions/{week}", allow_404=True)
        if not txns:
            continue
        for t in txns:
            if t.get("type") != "trade" or t.get("status") != "complete":
                continue
            picks = t.get("draft_picks") or []
            if not picks:
                continue

            adds = t.get("adds") or {}
            roster_ids = t.get("roster_ids") or []
            players_by_roster = {rid: [] for rid in roster_ids}
            for pid, rid in adds.items():
                if rid in players_by_roster:
                    players_by_roster[rid].append({
                        "player_id": pid,
                        "name": resolve_player_name(pid, players_pool),
                    })

            picks_by_roster = {rid: [] for rid in roster_ids}
            for pk in picks:
                receiving_roster = pk.get("owner_id")
                if receiving_roster in picks_by_roster:
                    picks_by_roster[receiving_roster].append({
                        "season": pk.get("season"),
                        "round": pk.get("round"),
                        "original_roster_id": pk.get("roster_id"),
                    })

            trades.append({
                "transaction_id": t.get("transaction_id"),
                "league_season": season,
                "week": week,
                "created": t.get("created"),
                "sides": [
                    {
                        "roster_id": rid,
                        "team_name": owner_map.get(rid, {}).get("team_name"),
                        "received_players": players_by_roster.get(rid, []),
                        "received_picks": picks_by_roster.get(rid, []),
                    }
                    for rid in roster_ids
                ],
            })
    return trades

def build_owner_map(league_id):
    users = fetch_json(f"{BASE}/league/{league_id}/users")
    rosters = fetch_json(f"{BASE}/league/{league_id}/rosters")
    user_by_id = {u["user_id"]: u for u in users}
    owner_map = {}
    for r in rosters:
        u = user_by_id.get(r.get("owner_id"), {})
        owner_map[r["roster_id"]] = {
            "owner_username": u.get("display_name"),
            "team_name": (u.get("metadata") or {}).get("team_name") or u.get("display_name"),
        }
    return owner_map

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    config = load_config()
    players_pool = load_players_cache()

    print("Walking season history chain...")
    seasons = walk_season_chain(config["league_id"])
    print(f"Found {len(seasons)} season(s): " +
          ", ".join(f"{info.get('season')} ({lid})" for lid, info in seasons))

    all_trades = []
    season_meta = []
    for league_id, info in seasons:
        season = info.get("season")
        print(f"Pulling trades for {season} ({league_id})...")
        owner_map = build_owner_map(league_id)
        trades = pull_season_trades(league_id, season, players_pool, owner_map)
        print(f"  {len(trades)} pick-involving trade(s) found")
        all_trades.extend(trades)
        season_meta.append({
            "season": season,
            "league_id": league_id,
            "scoring_settings": info.get("scoring_settings"),
            "roster_positions": info.get("roster_positions"),
        })

    output = {
        "synced_at": time.time(),
        "seasons": season_meta,
        "trades_with_picks": all_trades,
        "note": ("Scoring settings and roster_positions differ across seasons — "
                 "see the 'seasons' array for each trade's league_season before "
                 "comparing pick values across years."),
    }

    with open(os.path.join(DATA_DIR, "trade_history.json"), "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote trade_history.json — {len(all_trades)} total pick-involving trades "
          f"across {len(seasons)} season(s).")

if __name__ == "__main__":
    main()

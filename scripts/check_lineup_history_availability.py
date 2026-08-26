"""
check_lineup_history_availability.py -- cheap feasibility check, NOT an
analysis tool.

WHY THIS EXISTS: before investing time designing a roster-economics
analysis (does real FLEX/SUPER_FLEX/IDP_FLEX slot competition explain the
DL/RB/WR baseline deviations found in the prod_mult reconstruction audit),
first answer a much cheaper question: can this league's historical weekly
starting lineups actually be retrieved at all?

This script does NOT reconstruct anything. It only:
  1. Walks this league's previous_league_id chain to find how many past
     seasons are reachable.
  2. For each reachable season, confirms /league/<id> returns real
     roster_positions (needed to know which slot each starter occupies).
  3. Pulls ONE sample week's matchups for each reachable season and
     confirms real starters/players/points data comes back, well-formed.
  4. Reports whether roster_positions is IDENTICAL across all reachable
     seasons or varies -- this matters because a real analysis would need
     to handle season-specific slot definitions if it varies.

REQUIRES REAL INTERNET ACCESS TO RUN. Written and reasoned through against
Sleeper's public API documentation, but not executed end-to-end -- this is
a first real run, same disclosure as every other pipeline script in this
project. Spot-check the printed output against what you know is true
before trusting it (e.g. does the reported season count match how many
years this league has actually existed under this dynasty format).

USAGE: python3 check_lineup_history_availability.py
Requires: requests (pip install requests --break-system-packages)
Reads league_id from config.json in the repo root.
"""

import json
import os
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
BASE = "https://api.sleeper.app/v1"

SAMPLE_WEEK = 5  # arbitrary mid-season week, just needs to have real games played


def get_league(league_id):
    resp = requests.get(f"{BASE}/league/{league_id}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_matchups(league_id, week):
    resp = requests.get(f"{BASE}/league/{league_id}/matchups/{week}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    config_path = os.path.join(REPO_ROOT, "config.json")
    with open(config_path) as f:
        config = json.load(f)
    current_league_id = config["league_id"]

    print(f"Starting from current league_id: {current_league_id}")
    print()

    seasons = []  # list of (league_id, season, roster_positions)
    league_id = current_league_id
    seen = set()

    while league_id and league_id not in seen and league_id != "0":
        seen.add(league_id)
        try:
            league = get_league(league_id)
        except Exception as e:
            print(f"  STOPPED: could not fetch league {league_id} -- {e}")
            break

        season = league.get("season")
        roster_positions = league.get("roster_positions")
        seasons.append((league_id, season, roster_positions))
        print(f"  Season {season}: league_id={league_id}, "
              f"roster_positions has {len(roster_positions) if roster_positions else 0} slots")

        league_id = league.get("previous_league_id")

    print()
    print(f"=== Total seasons reachable via previous_league_id chain: {len(seasons)} ===")
    print()

    if not seasons:
        print("No seasons reachable -- STOP. Historical lineup data is not accessible this way.")
        return

    # Check whether roster_positions is identical across all reachable seasons
    positions_by_season = {s: tuple(rp) if rp else None for _, s, rp in seasons}
    unique_configs = set(positions_by_season.values())
    if len(unique_configs) == 1:
        print("roster_positions is IDENTICAL across every reachable season.")
        print("A historical analysis can use one fixed slot definition.")
    else:
        print(f"roster_positions VARIES across seasons ({len(unique_configs)} distinct configs found).")
        print("A historical analysis will need to use each season's own roster_positions,")
        print("not assume the current league's structure applied in prior years.")
    print()

    # Sample one week's matchups from each reachable season to confirm real data comes back
    print(f"=== Sampling week {SAMPLE_WEEK} matchups from each reachable season ===")
    for league_id, season, roster_positions in seasons:
        try:
            matchups = get_matchups(league_id, SAMPLE_WEEK)
        except Exception as e:
            print(f"  Season {season}: FAILED to fetch matchups -- {e}")
            continue

        if not matchups:
            print(f"  Season {season}: matchups endpoint returned empty -- no data for week {SAMPLE_WEEK} "
                  f"(may be off-season, preseason, or this week hasn't happened in that season)")
            continue

        sample = matchups[0]
        has_starters = bool(sample.get("starters"))
        has_players = bool(sample.get("players"))
        has_points = sample.get("points") is not None
        n_teams = len(matchups)

        ok = has_starters and has_players and has_points
        status = "OK -- well-formed" if ok else "INCOMPLETE -- missing expected fields"
        print(f"  Season {season}: {n_teams} teams returned, sample team has "
              f"starters={has_starters} players={has_players} points={has_points}  [{status}]")

    print()
    print("If every reachable season shows 'OK -- well-formed' above, historical weekly")
    print("lineup reconstruction is feasible. Next real step (not part of this script) would be")
    print("pulling all weeks x all seasons, not just one sample week per season.")


if __name__ == "__main__":
    main()

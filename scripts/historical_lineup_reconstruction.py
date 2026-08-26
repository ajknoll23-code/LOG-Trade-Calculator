#!/usr/bin/env python3
"""
scripts/historical_lineup_reconstruction.py

Roster-economics hypothesis -- Stage 1, steps 1-2 of the recommended
sequence (see prod-mult-reconstruction-audit.md and the follow-up
"historical lineup data & roster-economics" recommendation): reconstruct
every actual weekly starting lineup for the 2024 and 2025 seasons directly
from Sleeper's real matchup data, and tally dedicated-slot vs. flex-slot
starts by position.

WHY THIS EXISTS: the rank-sensitivity sweep on PROD_MULT_DATA found that
DL behaves as though replacement level sits shallower (~22-24) and RB/WR
behave as though it sits deeper (~37-44) than the documented rank-32/36
baselines. One hypothesis for why: real competition for shared FLEX /
SUPER_FLEX / IDP_FLEX roster slots, not an arbitrary historical accident.
This script builds the real weekly demand data needed to test that.

RULESET SCOPE -- READ BEFORE CHANGING SEASONS_TO_ANALYZE:
This league changed dedicated RB slots 1->2 and dedicated LB slots 1->2
for the 2026 season. 2024 and 2025 were both played under the OLD
ruleset (1 RB, 1 LB dedicated). Per the explicit recommendation this
workstream is following: do NOT reweight or adjust 2024-2025 data to
pretend it was played under 2026's rules -- managers made real lineup
decisions under the ruleset that actually existed that year. This script
preserves each season exactly as played and deliberately excludes 2026,
which belongs to a separate later stage (comparing the two rulesets
against each other, once more of the 2026 season has been played out).
Each season's own real `roster_positions` (fetched fresh, not assumed)
is the authority on which slots were dedicated vs. flex that year.

WHAT THIS DOES NOT DO YET (later steps, not this script):
- No start-rate curves by positional rank (needs pre-week, not
  end-of-season, player rank -- leakage risk flagged in the audit).
- No cross-season comparison of flex market share (needs 2026 data to
  accumulate first).
- No conclusion about whether the roster-economics hypothesis is TRUE --
  this script only produces the real counts; interpretation is a
  separate step once DL/WR (the unchanged "control" positions) can be
  checked against the empirically reconstructed replacement zones.

REQUIRES REAL INTERNET ACCESS. Written and reasoned through without the
ability to run it end-to-end in this sandboxed environment (no network
egress here) -- follows the same fetch/retry/position-resolution
conventions already proven out in sync_sleeper.py and ppg_pipeline.py.
Treat first real output with the same scrutiny those got: spot-check a
couple of weeks against the Sleeper app by hand (does Week 3's starters
list for your own team match what Sleeper shows you started?) before
trusting the full run.

USAGE: python3 scripts/historical_lineup_reconstruction.py
Requires: requests (pip install requests --break-system-packages)

OUTPUT: scripts/historical_lineup_demand.json
  - per-season: real roster_positions, real starter-slot order, every
    individual weekly start record (season/week/roster/slot/player/
    pos_bucket/dedicated-or-flex), and a summary (dedicated starters per
    team-week by position, flex market share by slot).
"""

import json
import os
import time
import requests

BASE = "https://api.sleeper.app/v1"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(ROOT, "config.json")
OUT_PATH = os.path.join(SCRIPT_DIR, "historical_lineup_demand.json")

# Ruleset A only -- see module docstring. 2026 is intentionally excluded.
SEASONS_TO_ANALYZE = {"2024", "2025"}

MAX_WEEKS = 18  # stop probing past this even if matchups somehow returned something

# Same position-bucket collapse used elsewhere in this project
# (sync_sleeper.py, index.html's normalizePos()) -- kept in sync manually.
# Deliberately using Sleeper's raw primary `position` field here, NOT the
# weight-maximizing "recommended_bucket" from dual_eligibility_results.json
# that the tool uses for VALUATION. Those are different questions: this
# script asks "which position pool does this start count toward," which
# wants a player's real primary position, not whichever bucket scores him
# highest. Worth a joint spot-check against player_positions.json later if
# a specific dual-eligible player's classification looks off.
POS_BUCKET = {
    "DE": "DL", "DT": "DL", "DL": "DL", "OLB": "LB", "ILB": "LB", "LB": "LB",
    "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB",
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "DEF": "DEF",
}

# Which real position bucket(s) each flex-type slot can absorb -- used to
# attribute a flex start to the player's ACTUAL position, not the slot
# label. Includes a couple of flex variants this league doesn't use
# (REC_FLEX, WRRB_FLEX) so the script doesn't silently mis-tally if that
# ever changes -- harmless if unused.
FLEX_ELIGIBLE = {
    "FLEX": {"RB", "WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "IDP_FLEX": {"DL", "LB", "DB"},
    "REC_FLEX": {"WR", "TE"},
    "WRRB_FLEX": {"RB", "WR"},
}


def fetch_json(url, retries=3, backoff=2):
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def walk_league_chain(start_league_id):
    """
    Follow previous_league_id backwards from the current league, returning
    {season: league_object}. Mirrors the chain-walk already proven out by
    check_lineup_history_availability.py.
    """
    seasons = {}
    league_id = start_league_id
    seen = set()
    while league_id and league_id not in seen:
        seen.add(league_id)
        league = fetch_json(f"{BASE}/league/{league_id}")
        season = league.get("season")
        seasons[season] = league
        league_id = league.get("previous_league_id")
    return seasons


def load_player_position_index():
    """
    Real primary position for every player_id, from Sleeper's full player
    dump. NOTE: this resolves historical (2024/2025) starts against TODAY's
    position data -- a real, small, and accepted limitation. A player who
    has since switched position would be bucketed by his CURRENT position,
    not necessarily what he was in 2024/2025. Not expected to move the
    aggregate demand numbers meaningfully, but worth remembering if a
    single player's classification looks surprising.
    """
    print("Fetching full Sleeper player index for position resolution...")
    pool = fetch_json(f"{BASE}/players/nfl")
    index = {}
    for pid, p in pool.items():
        raw_pos = p.get("position")
        index[pid] = {
            "name": p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "pos_bucket": POS_BUCKET.get(raw_pos, raw_pos),
        }
    return index


def starter_slot_order(roster_positions):
    """
    Sleeper's per-matchup `starters` array is ordered to match the
    non-'BN' entries of roster_positions, in order. Taxi/IR slots aren't
    part of roster_positions at all, so no separate filtering needed there.
    """
    return [s for s in roster_positions if s != "BN"]


def reconstruct_season(season, league, player_index):
    league_id = league["league_id"]
    roster_positions = league.get("roster_positions") or []
    starter_slots = starter_slot_order(roster_positions)

    rosters = fetch_json(f"{BASE}/league/{league_id}/rosters")
    users = fetch_json(f"{BASE}/league/{league_id}/users")
    owner_names = {
        u["user_id"]: (u.get("metadata") or {}).get("team_name") or u.get("display_name")
        for u in users
    }
    roster_id_to_team = {
        r["roster_id"]: owner_names.get(r.get("owner_id"), f"Roster {r['roster_id']}")
        for r in rosters
    }

    records = []
    weeks_with_data = 0
    for week in range(1, MAX_WEEKS + 1):
        try:
            matchups = fetch_json(f"{BASE}/league/{league_id}/matchups/{week}")
        except RuntimeError as e:
            print(f"  week {week}: fetch failed ({e}) -- stopping season here")
            break
        if not matchups:
            continue  # week not played (past real season length, or bye-week gap)
        weeks_with_data += 1
        for entry in matchups:
            roster_id = entry.get("roster_id")
            starters = entry.get("starters") or []
            if not starters or all(s in (None, "0") for s in starters):
                continue  # roster had no real lineup set this week
            team_name = roster_id_to_team.get(roster_id, f"Roster {roster_id}")
            for slot, pid in zip(starter_slots, starters):
                if pid in (None, "0"):
                    continue
                pinfo = player_index.get(pid, {"name": f"Unknown ({pid})", "pos_bucket": None})
                is_flex = slot in FLEX_ELIGIBLE
                records.append({
                    "season": season,
                    "week": week,
                    "roster_id": roster_id,
                    "team_name": team_name,
                    "slot": slot,
                    "player_id": pid,
                    "player_name": pinfo["name"],
                    "pos_bucket": pinfo["pos_bucket"],
                    "start_type": "flex" if is_flex else "dedicated",
                })
        time.sleep(0.2)  # be polite to the API

    return {
        "season": season,
        "league_id": league_id,
        "roster_positions": roster_positions,
        "starter_slots": starter_slots,
        "weeks_with_data": weeks_with_data,
        "records": records,
    }


def summarize(season_data):
    records = season_data["records"]
    weeks = season_data["weeks_with_data"]
    teams = len({r["roster_id"] for r in records}) or 12
    team_weeks = weeks * teams

    dedicated_counts = {}
    flex_counts = {}  # (slot, pos_bucket) -> count
    for r in records:
        if r["start_type"] == "dedicated":
            # BUG FIX (found 2026-08-26 against real output): a dedicated
            # slot's position is defined by the SLOT itself, not by the
            # real player's own primary position bucket. Dual DL/LB-
            # eligible players (real EDGE defenders -- the same class
            # already flagged elsewhere in this project) legitimately fill
            # a "DL" or "LB" dedicated slot depending on which one Sleeper
            # let them occupy that week. Keying this off pos_bucket instead
            # of slot silently misattributed ~130 real DL-slot starts to
            # "LB" and ~19 real LB-slot starts to "DL" in the first run --
            # caught because the resulting LB dedicated count (321) was
            # mathematically impossible given only 1 dedicated LB slot
            # exists per roster. Confirmed against the raw per-team-week
            # slot counts (exactly 1 LB, 2 DL, 2 DB every team-week) before
            # applying this fix.
            dedicated_counts[r["slot"]] = dedicated_counts.get(r["slot"], 0) + 1
        else:
            pb = r["pos_bucket"] or "UNKNOWN"
            key = (r["slot"], pb)
            flex_counts[key] = flex_counts.get(key, 0) + 1

    dedicated_starters_per_team_week = {
        pb: round(count / team_weeks, 3) if team_weeks else None
        for pb, count in dedicated_counts.items()
    }

    flex_by_slot = {}
    for (slot, pb), count in flex_counts.items():
        flex_by_slot.setdefault(slot, {})[pb] = count
    flex_market_share = {}
    for slot, by_pos in flex_by_slot.items():
        total = sum(by_pos.values()) or 1
        flex_market_share[slot] = {
            pb: {"count": c, "share_pct": round(100 * c / total, 1)}
            for pb, c in sorted(by_pos.items(), key=lambda kv: -kv[1])
        }

    # Effective demand = dedicated + this position's share of every flex
    # pool it's eligible for. Reported per team-week so it's directly
    # comparable to "how many roster spots does this position effectively
    # command," independent of raw counts.
    effective_starters_per_team_week = dict(dedicated_starters_per_team_week)
    for slot, by_pos in flex_by_slot.items():
        for pb, count in by_pos.items():
            per_team_week = round(count / team_weeks, 3) if team_weeks else 0
            effective_starters_per_team_week[pb] = round(
                effective_starters_per_team_week.get(pb, 0) + per_team_week, 3
            )

    return {
        "team_weeks": team_weeks,
        "dedicated_starts_by_position": dedicated_counts,
        "dedicated_starters_per_team_week": dedicated_starters_per_team_week,
        "flex_market_share": flex_market_share,
        "effective_starters_per_team_week": effective_starters_per_team_week,
    }


def main():
    config = load_config()
    print(f"Walking league chain from {config['league_id']}...")
    seasons = walk_league_chain(config["league_id"])
    print(f"Reachable seasons: {sorted(seasons.keys())}")

    player_index = load_player_position_index()

    out = {"generated_at": time.time(), "seasons": {}}
    for season, league in seasons.items():
        if season not in SEASONS_TO_ANALYZE:
            continue
        print(f"\n=== Reconstructing {season} (league_id={league['league_id']}) ===")
        season_data = reconstruct_season(season, league, player_index)
        summary = summarize(season_data)
        out["seasons"][season] = {
            "league_id": season_data["league_id"],
            "roster_positions": season_data["roster_positions"],
            "starter_slots": season_data["starter_slots"],
            "weeks_with_data": season_data["weeks_with_data"],
            "summary": summary,
            "records": season_data["records"],
        }
        print(f"  weeks_with_data={season_data['weeks_with_data']}  records={len(season_data['records'])}")
        print(f"  dedicated starts by position: {summary['dedicated_starts_by_position']}")
        print(f"  dedicated starters/team-week: {summary['dedicated_starters_per_team_week']}")
        print(f"  effective starters/team-week (dedicated + flex share): {summary['effective_starters_per_team_week']}")
        for slot, by_pos in summary["flex_market_share"].items():
            shares = {pb: v["share_pct"] for pb, v in by_pos.items()}
            print(f"  {slot} market share: {shares}")

    missing = SEASONS_TO_ANALYZE - set(out["seasons"].keys())
    if missing:
        print(f"\nWARNING: could not reach season(s) {sorted(missing)} via the league chain.")

    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

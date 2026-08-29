#!/usr/bin/env python3
"""
scripts/historical_weekly_points_pipeline.py

Roster-economics hypothesis -- data prerequisite for steps 5-6 (start-rate
curves by positional rank). Computes REAL weekly fantasy points, scored
under this league's exact rules, for 2024 and 2025, across the FULL NFL
positional universe -- not just players who happened to be rostered in
this 12-team league.

WHY THE FULL NFL UNIVERSE, NOT JUST THIS LEAGUE'S ROSTERED PLAYERS:
the replacement-level baselines this whole workstream is testing against
(documented QB18/RB32/WR36/TE15/DL32/LB32/DB32, and the empirically
reconstructed LEGACY_EMPIRICAL_BASELINE) are LEAGUE-WIDE NFL positional
ranks -- "the 32nd-best DL in the NFL," not "the 32nd-best DL among
players someone in this 12-team league happened to roster." Ranking
within only this league's ~250-300 rostered players would systematically
compress the tail and produce a rank scale that isn't comparable to those
baselines at all. Sleeper's weekly stats endpoint already returns EVERY
player with a recorded stat line that week (several hundred per week,
independent of fantasy roster status), so the full universe is available
for free -- no separate real all_players.json name-matching required.

WHY NO NAME-MATCHING (unlike ppg_pipeline.py): this pipeline scores
whatever player_id Sleeper's own stats dump reports, and separately
whatever player_id Sleeper's own matchups reported in
historical_lineup_demand.json -- both come from the same source of truth
(Sleeper's real numeric player IDs), so there's no name-collision or
alias risk to manage here. That headache was specific to matching
loosely-formatted human-typed names against Sleeper's index; it doesn't
apply when everything is already ID-keyed.

REQUIRES REAL INTERNET ACCESS. Reuses score_week() verbatim from
ppg_pipeline.py (already verified against real box scores -- see that
file's history) -- do not hand-edit the scoring logic here without also
updating ppg_pipeline.py, or the two pipelines will silently diverge.

USAGE: python3 scripts/historical_weekly_points_pipeline.py
Requires: requests (pip install requests --break-system-packages)

OUTPUT: scripts/weekly_points_by_season.json
  {season: {player_id: {name, pos_bucket, weekly_points: {week: pts}}}}
  weekly_points only includes weeks the player actually played (gp>=1),
  same "gp is the trustworthy signal, gms_active is not" rule already
  established in ppg_pipeline.py.
"""

import json
import os
import time
import requests

BASE = "https://api.sleeper.app/v1"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(SCRIPT_DIR, "weekly_points_by_season.json")

SEASONS = ["2024", "2025"]
WEEKS = range(1, 19)  # regular season is 18 weeks -- see ppg_pipeline.py's
                       # comment on the real range(1,18) bug this project
                       # already found and fixed once; don't reintroduce it.

# Kept identical to historical_lineup_reconstruction.py's POS_BUCKET --
# these two scripts must agree on position bucketing or a player's rank
# computed here won't line up with his pos_bucket recorded there.
POS_BUCKET = {
    "DE": "DL", "DT": "DL", "DL": "DL", "OLB": "LB", "ILB": "LB", "LB": "LB",
    "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB",
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "DEF": "DEF",
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


# ---- Verbatim from ppg_pipeline.py -- see that file for the real
# box-score verification history behind every line. Do not diverge. ----
def score_week(stats):
    pts = 0.0

    pass_yd = stats.get("pass_yd", 0)
    pts += pass_yd * 0.04
    pts += stats.get("pass_td", 0) * 4.0
    pts += stats.get("pass_2pt", 0) * 2.0
    pts += stats.get("pass_int", 0) * -2.0
    if pass_yd >= 400:
        pts += 3.0
    elif pass_yd >= 300:
        pts += 2.0

    rush_yd = stats.get("rush_yd", 0)
    pts += stats.get("rush_att", 0) * 0.2
    pts += rush_yd * 0.1
    pts += stats.get("rush_td", 0) * 6.0
    pts += stats.get("rush_2pt", 0) * 2.0
    if rush_yd >= 200:
        pts += 3.0
    elif rush_yd >= 100:
        pts += 2.0

    rec_yd = stats.get("rec_yd", 0)
    pts += stats.get("rec", 0) * 0.5
    pts += rec_yd * 0.1
    pts += stats.get("rec_td", 0) * 6.0
    pts += stats.get("rec_2pt", 0) * 2.0
    if rec_yd >= 200:
        pts += 3.0
    elif rec_yd >= 100:
        pts += 2.0

    pts += stats.get("fum_lost", 0) * -2.0
    pts += stats.get("fum_rec_td", 0) * 6.0

    solo = stats.get("idp_tkl_solo", 0)
    ast = stats.get("idp_tkl_ast", 0)
    pts += solo * 1.5
    pts += ast * 0.75
    pts += stats.get("idp_tkl_loss", 0) * 2.0

    sacks = stats.get("idp_sack", stats.get("sack", 0))
    pts += sacks * 3.0
    pts += stats.get("idp_qb_hit", 0) * 2.0

    ints = stats.get("idp_int", stats.get("int", 0))
    pts += ints * 6.0
    pts += stats.get("idp_fum_rec", 0) * 4.0
    pts += stats.get("idp_ff", 0) * 3.0
    pts += stats.get("idp_safety", 0) * 3.0
    pts += stats.get("blk_kick", 0) * 6.0
    pts += stats.get("idp_td", 0) * 6.0

    pd = stats.get("idp_pass_def", 0)
    pts += pd * 3.0

    if (solo + ast) >= 10:
        pts += 2.0
    if sacks >= 2:
        pts += 2.0
    if pd >= 3:
        pts += 2.0

    pts += stats.get("st_td", 0) * 6.0
    pts += stats.get("st_ff", 0) * 3.0
    pts += stats.get("st_fum_rec", 0) * 3.0

    return pts
# ---- End verbatim block ----


def load_player_position_index():
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


def process_season(season, player_index):
    by_player = {}
    for week in WEEKS:
        print(f"  {season} week {week}...")
        week_stats = fetch_json(f"{BASE}/stats/nfl/regular/{season}/{week}")
        for pid, stats in week_stats.items():
            was_active = stats and (stats.get("gp") or 0) >= 1
            if not was_active:
                continue  # same "gp is trustworthy, gms_active is not" rule as ppg_pipeline.py
            pinfo = player_index.get(pid)
            if not pinfo or not pinfo.get("pos_bucket"):
                continue  # not a fantasy-relevant position (e.g. long snapper) or unresolvable
            pts = score_week(stats)
            entry = by_player.setdefault(pid, {
                "name": pinfo["name"], "pos_bucket": pinfo["pos_bucket"], "weekly_points": {}
            })
            entry["weekly_points"][str(week)] = round(pts, 2)
        time.sleep(0.3)
    return by_player


def main():
    player_index = load_player_position_index()

    out = {"generated_at": time.time(), "seasons": {}}
    for season in SEASONS:
        print(f"\n=== Scoring {season} (full NFL positional universe) ===")
        by_player = process_season(season, player_index)
        out["seasons"][season] = by_player
        print(f"  Scored {len(by_player)} players with >=1 real game in {season}.")

    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

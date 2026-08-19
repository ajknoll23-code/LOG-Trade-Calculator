"""
Durability correlation pipeline -- derives a real R^2 for "how well does a
player's games-played rate in one season predict the next season's rate,"
broken out by position.

WHY THIS EXISTS: index.html's productionMultiplier methodology currently
blends projected 2026 durability as 65% the player's own 2025 games-played
rate + 35% their position's median games-played rate. That 65/35 split was
a judgment call ("meaningful but softened penalty") -- never derived from
data, because deriving it properly needs multiple seasons of real
games-played history, and the project only had one season (2025, via
ppg_pipeline.py) when that number was chosen.

This script is unrelated to ppg_pipeline.py's k=3 shrinkage question --
that one is about within-season week-to-week score variance (needs
weekly_points, added to ppg_pipeline.py in the same pass as this file).
This one is about between-season durability persistence and needs multiple
YEARS of data instead, which is why it's a separate script fetching
multiple past seasons rather than an extension of the single-season
pipeline.

METHOD: for six real completed seasons (2019-2024), compute each player's
games-played fraction of that season (games_played / season_max_games,
NOT a fixed /17 -- see SEASON_MAX_GAMES below, since 2019-2020 were
16-game seasons and 2021+ are 17-game seasons; mixing them without
normalizing would bias the correlation). Then, per position, pair every
player's season-N availability with their own season-(N+1) availability
(only when they have real data in both years) and compute the real
Pearson R^2 across all such pairs. That R^2 is exactly the number the
model's open question (section 8.2 of the technical breakdown) asks for:
"a principled way to set this ratio... from real data."

IMPORTANT SCOPE NOTE: this deliberately does NOT limit itself to this
league's ~553 tracked players. The durability question is a league-wide
NFL question ("how consistent is games-played year to year for RBs in
general"), not specific to which players are in this league's database --
using the full Sleeper player pool for every season gives a much larger,
more representative sample than the ~553-player subset would. Because of
this, there's no alias table or name-collision handling needed here at
all -- everything stays keyed by Sleeper's own player_id, never by name,
so the whole class of matching bugs ppg_pipeline.py has to deal with
doesn't apply to this script.

REQUIRES REAL INTERNET ACCESS TO RUN, same as ppg_pipeline.py. Written and
reasoned through without the ability to execute it end-to-end -- the
Sleeper stats endpoint shape is the same one ppg_pipeline.py already uses
successfully in production, so the per-week fetch logic is a known-working
pattern, but the multi-season loop and the final R^2 computation have not
been run against real data by Claude directly. Sanity-check the printed
summary against a couple of players you know the real history of (e.g. a
guy who missed most of a season to injury should show a real dip) before
trusting the derived ratio.

USAGE: python3 durability_pipeline.py
Requires: requests (pip install requests --break-system-packages)
Takes longer than ppg_pipeline.py -- six seasons of weekly fetches instead
of one, so expect several minutes, not one or two.
"""

import json
import os
import time
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Six real completed seasons. Chosen to match doc recommendation of
# "5-10 years" while stopping at a length that's still a reasonable single
# CI job. 2025 (already scored by ppg_pipeline.py) is deliberately
# EXCLUDED from the fetch here to avoid doing the same work twice -- it's
# stitched back in from the existing ppg_results.json instead (see
# load_2025_from_existing_results below), so this script still produces a
# full 2019->2025 chain (6 year-over-year pairs) without re-fetching 2025.
HISTORICAL_SEASONS = [2019, 2020, 2021, 2022, 2023, 2024]

# Real NFL schedule lengths -- 2019 and 2020 were 16-game/17-week seasons,
# 2021 onward are 17-game/18-week seasons. Using a flat /17 everywhere
# (like the single-season pipeline correctly does for 2025-onward-only)
# would silently understate every pre-2021 player's real availability and
# bias the whole correlation. This is the exact same class of bug the
# range(1,18) week-count issue was in ppg_pipeline.py, just for a
# different set of seasons.
SEASON_WEEKS = {2019: 17, 2020: 17, 2021: 18, 2022: 18, 2023: 18, 2024: 18}
SEASON_MAX_GAMES = {2019: 16, 2020: 16, 2021: 17, 2022: 17, 2023: 17, 2024: 17}

# Same bucket collapse as sync_sleeper.py's POS_BUCKET -- kept identical on
# purpose so DL/LB/DB groupings here match what the live tool actually
# uses. This script does NOT need the finer DT/DE split; the open question
# it's answering (65/35 durability) is asked at the DL/LB/DB level, not
# the DT/EDGE level.
POS_BUCKET = {
    "DE": "DL", "DT": "DL", "DL": "DL", "OLB": "LB", "ILB": "LB", "LB": "LB",
    "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB",
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE",
}


def fetch_player_index():
    print("Fetching Sleeper player index...")
    resp = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_season_games_played(season, weeks_count):
    """
    Returns {player_id: games_played_int} for one season, using the exact
    same "gp field, not gms_active" logic ppg_pipeline.py already validated
    against real ground truth (see that script's comment on Blake Cashman).
    Does not compute or need fantasy points here at all -- this script only
    cares about whether a game counted as played, not how well they played
    in it -- so no score_week() call, unlike ppg_pipeline.py.
    """
    games_played = {}
    for week in range(1, weeks_count + 1):
        print(f"  {season} week {week}...")
        resp = requests.get(
            f"https://api.sleeper.app/v1/stats/nfl/regular/{season}/{week}",
            timeout=30,
        )
        resp.raise_for_status()
        week_data = resp.json()
        for pid, stats in week_data.items():
            if stats and (stats.get("gp") or 0) >= 1:
                games_played[pid] = games_played.get(pid, 0) + 1
        time.sleep(0.3)
    return games_played


def load_2025_from_existing_results():
    """
    Reuses the already-fetched, already-validated 2025 games_played numbers
    from ppg_results.json instead of re-fetching -- that file's games_played
    field was computed with the same gp-field logic and has already been
    through real ground-truth checking this project did earlier. Requires
    ppg_pipeline.py to have been run first (normal repo state -- it already
    has been). Returns {sleeper_id: games_played_int}, keyed the same way
    as fetch_season_games_played's output so the two can be mixed freely.
    """
    path = os.path.join(SCRIPT_DIR, "ppg_results.json")
    if not os.path.exists(path):
        print("WARNING: ppg_results.json not found -- 2025 will be skipped, "
              "reducing this run to 5 seasons (2019-2024) instead of 6.")
        return {}
    with open(path) as f:
        results = json.load(f)
    return {r["sleeper_id"]: r["games_played"] for r in results if r.get("sleeper_id")}


def pearson_r2(pairs):
    """
    pairs: list of (x, y) tuples. Plain Pearson correlation, squared -- no
    external stats library needed for this. Returns None if fewer than 5
    pairs (not enough to mean anything) or if either series has zero
    variance (all-identical values -- correlation is undefined, not 0).
    """
    n = len(pairs)
    if n < 5:
        return None, n
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None, n
    r = cov / (var_x ** 0.5 * var_y ** 0.5)
    return r ** 2, n


def main():
    player_index = fetch_player_index()
    pos_by_id = {}
    for pid, p in player_index.items():
        raw_pos = p.get("position")
        bucket = POS_BUCKET.get(raw_pos)
        if bucket:
            pos_by_id[pid] = bucket

    # season -> {player_id: games_played}
    season_games = {}
    for season in HISTORICAL_SEASONS:
        print(f"=== Fetching {season} ({SEASON_WEEKS[season]} weeks) ===")
        season_games[season] = fetch_season_games_played(season, SEASON_WEEKS[season])

    season_games[2025] = load_2025_from_existing_results()
    if season_games[2025]:
        SEASON_MAX_GAMES[2025] = 17  # matches ppg_pipeline.py's WEEKS = range(1,19)
        all_seasons = HISTORICAL_SEASONS + [2025]
    else:
        all_seasons = HISTORICAL_SEASONS

    # Build (availability_N, availability_N+1) pairs per position across
    # every consecutive season boundary in the fetched range.
    pairs_by_pos = {}
    for i in range(len(all_seasons) - 1):
        s1, s2 = all_seasons[i], all_seasons[i + 1]
        g1, g2 = season_games[s1], season_games[s2]
        shared_ids = set(g1.keys()) & set(g2.keys())
        for pid in shared_ids:
            pos = pos_by_id.get(pid)
            if not pos:
                continue
            avail_1 = g1[pid] / SEASON_MAX_GAMES[s1]
            avail_2 = g2[pid] / SEASON_MAX_GAMES[s2]
            # Clip at 1.0 -- a player who was on an active roster for every
            # game of a season should read as fully available (1.0), not
            # slightly over from a data quirk. Real games_played should
            # never exceed SEASON_MAX_GAMES, but this guards against it
            # anyway rather than letting a bad data point skew the fit.
            avail_1 = min(1.0, avail_1)
            avail_2 = min(1.0, avail_2)
            pairs_by_pos.setdefault(pos, []).append((avail_1, avail_2))

    results = {}
    for pos, pairs in sorted(pairs_by_pos.items()):
        r2, n = pearson_r2(pairs)
        results[pos] = {
            "r_squared": round(r2, 4) if r2 is not None else None,
            "n_pairs": n,
            "seasons_used": all_seasons,
        }

    with open(os.path.join(SCRIPT_DIR, "durability_results.json"), "w") as f:
        json.dump(results, f, indent=2)

    print()
    print("=== Real year-over-year games-played R^2 by position ===")
    print(f"{'Pos':4s} {'R^2':6s} {'N pairs':8s}")
    for pos, r in sorted(results.items(), key=lambda kv: -(kv[1]['r_squared'] or 0)):
        r2_str = f"{r['r_squared']:.4f}" if r['r_squared'] is not None else "n/a"
        print(f"{pos:4s} {r2_str:6s} {r['n_pairs']:<8d}")

    print()
    print("Interpretation: R^2 close to 1.0 means a player's own recent")
    print("games-played rate is a strong predictor of next season's rate")
    print("(own-history weight should lean HIGH). R^2 close to 0 means own")
    print("history barely predicts next season at all (position-median")
    print("weight should lean HIGH instead). This directly answers the")
    print("65/35 open question -- e.g. if DL comes back at R^2=0.30, that")
    print("suggests roughly 30% own-history / 70% position-median for DL,")
    print("not the current flat 65/35 applied to every position the same way.")
    print()
    print("Full pair-count and per-position detail written to durability_results.json.")


if __name__ == "__main__":
    main()

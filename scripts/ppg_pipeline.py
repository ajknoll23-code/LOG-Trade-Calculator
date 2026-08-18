"""
True PPG pipeline -- proof of concept for the top 30 players.

WHY THIS EXISTS: the tool's production data has always been season-total
based (or, for the original bulk import, whatever FantasyPros' own season
totals were). That conflates "missed games" with "bad performance" -- a
player who's elite for 15 games and hurt for 2 looks identical to a player
who was mediocre for all 17. Real dynasty valuation practice (Footballguys,
confirmed via research) uses points-per-game while active, not season
totals, specifically to avoid this. Sleeper's OWN player-page PPG already
does this correctly (confirmed 2026-08-17 against a real discrepancy the
league owner noticed on Brian Burns' page) -- this script reconstructs that
same true PPG from raw weekly data, but scored under THIS LEAGUE'S exact
custom rules, not Sleeper's generic PPR/half-PPR/standard defaults.

REQUIRES REAL INTERNET ACCESS TO RUN. This was written and reasoned through
without the ability to test it end-to-end -- the field names below are
confirmed real (from an actual API response pasted back during development),
but the full aggregation across 17 weeks has not been run or validated by
Claude directly. Treat first real output with appropriate scrutiny, cross-
check a couple of players against Sleeper's own displayed PPG by hand
before trusting the full batch.

USAGE: python3 ppg_pipeline.py
Requires: requests (pip install requests --break-system-packages)
"""

import json
import os
import time
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Ported directly from the main tool's real ALIASES map (trade-desk.html) --
# found the hard way 2026-08-18: ALIASES only ever got consulted in ONE
# code path (live-roster-sync merging), so every new piece of code that
# does its own name matching has to remember to reuse it, or aliased names
# silently fail. This script didn't, on the first pass -- fixed now rather
# than patching just the specific names that happened to get caught this
# time. Only the entries actually relevant to real NFL free-agent/rostered
# players are needed here (not every alias in the main file matters for
# this lookup), but keeping the same source of truth rather than a
# separately-maintained list.
ALIASES = {
    'a st brown': 'amonra st brown',
    'jsmithnjigba': 'jaxon smithnjigba',
    'jeremiah love': 'jeremiyah love',
}

SEASON = "2025"
WEEKS = range(1, 18)  # regular season, weeks 1-17

# ---- This league's EXACT scoring rules ----
# Confirmed explicitly this session: half-PPR, 0.2/rush attempt, 6pt
# rush/rec TDs, 4pt passing TDs, IDP (solo 1.5, asst 0.75, sack 3, TFL 2,
# INT 6, PD 3). Passing/rushing/receiving YARDAGE point rates and
# turnover penalties were NOT explicitly re-confirmed this session --
# using standard, clearly-labeled conventional defaults below. If this
# league's real settings differ (e.g. a different passing-yards-per-point
# rate), these specific lines are the ones to correct, everything else
# is confirmed.
def score_week(stats):
    pts = 0.0
    # Passing (standard convention -- NOT explicitly reconfirmed this session)
    pts += stats.get("pass_yd", 0) * 0.04       # 1 pt / 25 yards
    pts += stats.get("pass_td", 0) * 4.0          # confirmed: 4pt passing TDs
    pts += stats.get("pass_int", 0) * -2.0        # standard convention, not reconfirmed
    # Rushing (confirmed: 0.2/attempt bonus + 6pt rush TDs)
    pts += stats.get("rush_att", 0) * 0.2
    pts += stats.get("rush_yd", 0) * 0.1          # 1 pt / 10 yards, standard convention
    pts += stats.get("rush_td", 0) * 6.0
    # Receiving (confirmed: half-PPR + 6pt rec TDs)
    pts += stats.get("rec", 0) * 0.5
    pts += stats.get("rec_yd", 0) * 0.1
    pts += stats.get("rec_td", 0) * 6.0
    # Fumbles (standard convention, not reconfirmed)
    pts += stats.get("fum_lost", 0) * -2.0
    # IDP (all confirmed explicitly this session)
    pts += stats.get("idp_tkl_solo", 0) * 1.5
    pts += stats.get("idp_tkl_ast", 0) * 0.75
    pts += stats.get("idp_sack", stats.get("sack", 0)) * 3.0
    pts += stats.get("idp_tkl_loss", 0) * 2.0     # TFL
    pts += stats.get("idp_int", stats.get("int", 0)) * 6.0
    pts += stats.get("idp_pass_def", 0) * 3.0     # PD
    return pts


def fetch_player_index():
    print("Fetching Sleeper player index (this is a large file, may take a moment)...")
    resp = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=60)
    resp.raise_for_status()
    return resp.json()


def build_name_to_id_map(player_index):
    """
    Returns name -> LIST of (pid, position) candidates, not a single ID.
    A single-ID last-write-wins mapping is exactly the bug already found
    and fixed once in this project (the free-agent board's Justin
    Jefferson/Devonta Smith collision) -- rebuilt here after Lamar Jackson
    silently resolved to zero games despite genuinely playing 13, almost
    certainly because Sleeper's full player index (which includes
    thousands of historical/practice-squad/inactive players, not just
    current rosters) has another real person sharing his exact name, and
    the old version took whichever came last in iteration order with no
    way to tell they were different people.
    """
    def normalize(s):
        s = s.strip().lower()
        for ch in [".", "'", "-"]:
            s = s.replace(ch, "")
        return " ".join(s.split())

    mapping = {}
    for pid, p in player_index.items():
        full_name = p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}"
        key = normalize(full_name)
        mapping.setdefault(key, []).append((pid, p.get("position")))
    return mapping


def resolve_player_id(name, known_pos, name_to_candidates):
    """
    Position-verified resolution -- picks the candidate whose Sleeper
    position matches what we already know about this player, rather than
    trusting a bare name match. Returns (pid, warning) -- warning is None
    on a clean single match, or a string explaining what happened
    otherwise, so collisions get surfaced instead of silently guessed at.
    """
    candidates = name_to_candidates.get(name)
    if not candidates:
        return None, None  # genuinely no match -- handled by the existing unmatched-name path
    if len(candidates) == 1:
        return candidates[0][0], None
    position_matches = [c for c in candidates if c[1] == known_pos]
    if len(position_matches) == 1:
        return position_matches[0][0], f"'{name}' had {len(candidates)} Sleeper entries sharing this name -- resolved via position match ({known_pos})"
    if len(position_matches) == 0:
        return None, f"'{name}' had {len(candidates)} Sleeper entries, none at the expected position ({known_pos}) -- could not safely resolve, treating as unmatched"
    return None, f"'{name}' had {len(position_matches)} Sleeper entries at the SAME position ({known_pos}) -- ambiguous, could not safely resolve"


def fetch_all_weeks():
    all_weeks = {}
    for week in WEEKS:
        print(f"Fetching week {week}...")
        resp = requests.get(f"https://api.sleeper.app/v1/stats/nfl/regular/{SEASON}/{week}", timeout=30)
        resp.raise_for_status()
        all_weeks[week] = resp.json()
        time.sleep(0.3)  # be polite to the API
    return all_weeks


def main():
    with open(os.path.join(SCRIPT_DIR, "top30_players.json")) as f:
        top30 = json.load(f)

    player_index = fetch_player_index()
    name_to_candidates = build_name_to_id_map(player_index)

    unmatched = []
    for p in top30:
        key = p["key"]
        if key not in name_to_candidates:
            aliased = ALIASES.get(key)
            if aliased and aliased in name_to_candidates:
                key = aliased
                p["key"] = aliased  # resolve in place so downstream lookups use the working name
        pid, warning = resolve_player_id(key, p["pos"], name_to_candidates)
        if warning:
            print(f"NOTE: {warning}")
        if pid:
            p["sleeper_id"] = pid
        else:
            unmatched.append(p["key"])
    if unmatched:
        print(f"WARNING: {len(unmatched)} of 30 names could not be safely resolved to a Sleeper ID: {unmatched}")
        print("Either a genuinely new alias is needed, or a real name collision that position")
        print("matching alone couldn't disambiguate -- check the NOTE lines above for which.")

    all_weeks = fetch_all_weeks()

    results = []
    for p in top30:
        pid = p.get("sleeper_id")
        if not pid:
            continue
        weekly_scores = []
        weeks_played = []
        weeks_excluded = []  # diagnostic: weeks with SOME stats entry but not counted as played
        games_played = 0
        for week, week_data in all_weeks.items():
            stats = week_data.get(pid)
            if stats and stats.get("gp", 0) >= 1:
                games_played += 1
                weeks_played.append(week)
                weekly_scores.append(score_week(stats))
            elif stats:
                # has SOME real stats entry for this week, just didn't clear the
                # gp>=1 bar -- worth knowing about specifically, since this is
                # exactly the kind of case that could silently undercount a real
                # game (e.g. Lamar Jackson: confirmed 13 real games, script found
                # 12 on the first pass -- this diagnostic exists specifically to
                # find which single week that was, instead of guessing)
                weeks_excluded.append({"week": week, "gp_value": stats.get("gp"), "gms_active_value": stats.get("gms_active")})
        if games_played == 0:
            continue
        total = sum(weekly_scores)
        true_ppg = total / games_played
        season_total_ppg = total / 17  # the OLD, diluted-by-missed-games way
        results.append({
            "player": p["key"], "pos": p["pos"], "sleeper_id": pid,
            "games_played": games_played, "total_points": round(total, 1),
            "true_ppg": round(true_ppg, 2), "season_total_ppg": round(season_total_ppg, 2),
            "dilution_pct": round((1 - season_total_ppg / true_ppg) * 100, 1) if true_ppg else 0,
            "weeks_played": weeks_played,
            "weeks_with_data_but_excluded": weeks_excluded,
        })

    results.sort(key=lambda r: -r["true_ppg"])
    with open(os.path.join(SCRIPT_DIR, "ppg_results.json"), "w") as f:
        json.dump(results, f, indent=2)

    # Print the diagnostic detail specifically for anyone with an excluded-but-
    # present week, so a mismatch like the Lamar Jackson one shows up directly
    # in the log instead of needing a follow-up round of manual checking.
    flagged = [r for r in results if r["weeks_with_data_but_excluded"]]
    if flagged:
        print()
        print("=== Players with a week that had SOME stats data but wasn't counted as played ===")
        for r in flagged:
            print(f"{r['player']}: played weeks {r['weeks_played']}")
            for w in r["weeks_with_data_but_excluded"]:
                print(f"    week {w['week']}: gp={w['gp_value']}, gms_active={w['gms_active_value']} -- has a stats entry but gp check excluded it")

    print()
    print(f"{'Player':20s} {'Pos':4s} {'GP':3s} {'True PPG':9s} {'Season/17 PPG':14s} {'Dilution'}")
    for r in results:
        print(f"{r['player']:20s} {r['pos']:4s} {r['games_played']:<3d} {r['true_ppg']:<9.2f} {r['season_total_ppg']:<14.2f} {r['dilution_pct']:.1f}%")


if __name__ == "__main__":
    main()

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

USAGE: python3 scripts/model/ppg_pipeline.py
Requires: requests (pip install requests --break-system-packages)

2026-08-19 UPDATE: now also writes each player's individual weekly point
totals (weekly_points, parallel to weeks_played) to ppg_results.json, not
just the season aggregate. This doesn't change any existing field or any
player's true_ppg/games_played -- purely additive. It exists to support
deriving the k=3 shrinkage constant (see index.html's productionMultiplier
methodology) from real within-player vs. between-player variance instead
of the current chosen-by-inspection value.
"""

import json
import os
import time
import requests

# Keep canonical inputs/outputs in the scripts/ root after moving this
# implementation into scripts/model/.
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
# Ported directly from the main tool's real ALIASES map -- the FULL
# list this time, not just the 3 entries that happened to matter for the
# original 30-player test. Expanding to the full player database means
# many more of these could plausibly come up.
ALIASES = {
    'j greenard': 'jonathan greenard',
    'k thibodeaux': 'kayvon thibodeaux',
    'k mckinstry': 'koolaid mckinstry',
    'c gardnerjohnson': 'cj gardnerjohnson',
    't stevenson': 'tyrique stevenson',
    'c gonzalez': 'christian gonzalez',
    't henderson': 'treveyon henderson',
    'w robinson': 'wandale robinson',
    'm fitzpatrick': 'minkah fitzpatrick',
    'd overshown': 'demarvion overshown',
    'a st brown': 'amonra st brown',
    'c schwesinger': 'carson schwesinger',
    'a van ginkel': 'andrew van ginkel',
    'd ezeiruaku': 'donovan ezeiruaku',
    'r stevenson': 'rhamondre stevenson',
    't mcmillan': 'tetairoa mcmillan',
    'd witherspoon': 'devon witherspoon',
    'n singleton': 'nicholas singleton',
    'd stribling': 'dezhaun stribling',
    'j croskeymerritt': 'jacory croskeymerritt',
    'c rozeboom': 'christian rozeboom',
    't ferguson': 'terrance ferguson',
    'jsmithnjigba': 'jaxon smithnjigba',
    'matthew hibner': 'matt hibner',
    'jeremiah love': 'jeremiyah love',

    # Added 2026-08-18 after the full 553-player run flagged these 9 as
    # unresolved. 5 of the 9 were genuine alias gaps (below) -- the other 4
    # (kyle williams, myles murphy, chris jones, chris johnson) are real
    # name collisions this can't safely disambiguate and are NOT handled
    # here; see the separate rostered-player cross-reference fix for those.
    'kylavon chaisson': 'klavon chaisson',
    'k lambertsmith': 'keandre lambertsmith',
    'j owusukoramoah': 'jeremiah owusukoramoah',
    'g nussmeier': 'garrett nussmeier',
    'e mcneilwarren': 'emmanuel mcneilwarren',
}

SEASON = "2025"
WEEKS = range(1, 19)


def score_week(stats):
    """
    Rewritten 2026-08-19 against the league's complete, real scoring sheet.
    """
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


def fetch_player_index():
    print("Fetching Sleeper player index (this is a large file, may take a moment)...")
    resp = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=60)
    resp.raise_for_status()
    return resp.json()


def build_name_to_id_map(player_index):
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
    candidates = name_to_candidates.get(name)
    if not candidates:
        return None, None
    if len(candidates) == 1:
        return candidates[0][0], None
    position_matches = [c for c in candidates if c[1] == known_pos]
    if len(position_matches) == 1:
        return position_matches[0][0], f"'{name}' had {len(candidates)} Sleeper entries sharing this name -- resolved via position match ({known_pos})"
    if len(position_matches) == 0:
        return None, f"'{name}' had {len(candidates)} Sleeper entries, none at the expected position ({known_pos}) -- could not safely resolve, treating as unmatched"
    return None, f"'{name}' had {len(position_matches)} Sleeper entries at the SAME position ({known_pos}) -- ambiguous, could not safely resolve"


MANUAL_ID_OVERRIDES = {
    'kyle williams': '12547',
    'myles murphy': '10875',
    'chris jones': '3558',
    'chris johnson': '13370',
}


def fetch_all_weeks():
    all_weeks = {}
    for week in WEEKS:
        print(f"Fetching week {week}...")
        resp = requests.get(f"https://api.sleeper.app/v1/stats/nfl/regular/{SEASON}/{week}", timeout=30)
        resp.raise_for_status()
        all_weeks[week] = resp.json()
        time.sleep(0.3)
    return all_weeks


def main():
    with open(os.path.join(SCRIPT_DIR, "all_players.json")) as f:
        all_players = json.load(f)

    player_index = fetch_player_index()
    name_to_candidates = build_name_to_id_map(player_index)

    unmatched = []
    for p in all_players:
        key = p["key"]
        if key in MANUAL_ID_OVERRIDES:
            p["sleeper_id"] = MANUAL_ID_OVERRIDES[key]
            continue
        if key not in name_to_candidates:
            aliased = ALIASES.get(key)
            if aliased and aliased in name_to_candidates:
                key = aliased
                p["key"] = aliased
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
    zero_game_players = []
    for p in all_players:
        pid = p.get("sleeper_id")
        if not pid:
            continue
        weekly_scores = []
        weeks_played = []
        weeks_excluded = []
        games_played = 0
        for week, week_data in all_weeks.items():
            stats = week_data.get(pid)
            was_active = stats and (stats.get("gp") or 0) >= 1
            if was_active:
                games_played += 1
                weeks_played.append(week)
                weekly_scores.append(score_week(stats))
            elif stats:
                weeks_excluded.append({
                    "week": week,
                    "gp_value": stats.get("gp"),
                    "gms_active_value": stats.get("gms_active"),
                })
        if games_played == 0:
            zero_game_players.append({
                "player": p["key"], "pos": p["pos"], "sleeper_id": pid,
                "had_any_data": bool(weeks_excluded),
            })
            continue
        total = sum(weekly_scores)
        true_ppg = total / games_played
        season_total_ppg = total / 17
        results.append({
            "player": p["key"], "pos": p["pos"], "sleeper_id": pid,
            "games_played": games_played, "total_points": round(total, 1),
            "true_ppg": round(true_ppg, 2), "season_total_ppg": round(season_total_ppg, 2),
            "dilution_pct": round((1 - season_total_ppg / true_ppg) * 100, 1) if true_ppg else 0,
            "weeks_played": weeks_played,
            "weekly_points": [round(s, 2) for s in weekly_scores],
            "weeks_with_data_but_excluded": weeks_excluded,
        })

    results.sort(key=lambda r: -r["true_ppg"])
    with open(os.path.join(SCRIPT_DIR, "ppg_results.json"), "w") as f:
        json.dump(results, f, indent=2)

    flagged = [r for r in results if r["weeks_with_data_but_excluded"]]
    if flagged:
        print()
        print("=== Players with a week that had SOME stats data but wasn't counted as played ===")
        for r in flagged:
            print(f"{r['player']}: played weeks {r['weeks_played']}")
            for w in r["weeks_with_data_but_excluded"]:
                print(f"    week {w['week']}: gp={w['gp_value']}, gms_active={w['gms_active_value']} -- has a stats entry but gp check excluded it")

    if zero_game_players:
        with_data = [z for z in zero_game_players if z["had_any_data"]]
        without_data = [z for z in zero_game_players if not z["had_any_data"]]
        print()
        print(f"=== {len(zero_game_players)} players resolved to a real Sleeper ID but showed ZERO played games this season ===")
        print(f"--- {len(with_data)} of these HAD some Sleeper data this season ---")
        for z in sorted(with_data, key=lambda x: x["player"]):
            print(f"  {z['player']:25s} {z['pos']:4s} sleeper_id={z['sleeper_id']}")
        print(f"--- {len(without_data)} of these had NO Sleeper data at all this season ---")
        for z in sorted(without_data, key=lambda x: x["player"]):
            print(f"  {z['player']:25s} {z['pos']:4s} sleeper_id={z['sleeper_id']}")

    print()
    print(f"Total players scored: {len(results)} of {len(all_players)} in the input list")
    unmatched_count = len(all_players) - len(results)
    if unmatched_count:
        print(f"({unmatched_count} did not resolve or had zero recorded games -- see WARNING/NOTE lines above)")

    print()
    print("=== Top 15 by dilution % (biggest gap between true PPG and the old season-total method) ===")
    by_dilution = sorted(results, key=lambda r: -r["dilution_pct"])[:15]
    print(f"{'Player':20s} {'Pos':4s} {'GP':3s} {'True PPG':9s} {'Season/17 PPG':14s} {'Dilution'}")
    for r in by_dilution:
        print(f"{r['player']:20s} {r['pos']:4s} {r['games_played']:<3d} {r['true_ppg']:<9.2f} {r['season_total_ppg']:<14.2f} {r['dilution_pct']:.1f}%")

    print()
    print("=== Top 15 by true PPG (highest real per-game production, position-agnostic) ===")
    by_ppg = sorted(results, key=lambda r: -r["true_ppg"])[:15]
    print(f"{'Player':20s} {'Pos':4s} {'GP':3s} {'True PPG':9s} {'Season/17 PPG':14s} {'Dilution'}")
    for r in by_ppg:
        print(f"{r['player']:20s} {r['pos']:4s} {r['games_played']:<3d} {r['true_ppg']:<9.2f} {r['season_total_ppg']:<14.2f} {r['dilution_pct']:.1f}%")

    print()
    print("Full results for all players written to ppg_results.json in the repo.")


if __name__ == "__main__":
    main()

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
    'kylavon chaisson': 'klavon chaisson',  # PLAYER_DB/all_players.json spell
        # this "kylavon" (with a Y) -- PROD_MULT_DATA's real production
        # entry and Sleeper's own name field both use "klavon" (no Y).
        # Verified directly against PLAYER_DB/PROD_MULT_DATA, not guessed.
    'k lambertsmith': 'keandre lambertsmith',  # KeAndre Lambert-Smith, WR, Chargers
    'j owusukoramoah': 'jeremiah owusukoramoah',  # Jeremiah Owusu-Koramoah
    'g nussmeier': 'garrett nussmeier',
    'e mcneilwarren': 'emmanuel mcneilwarren',  # Emmanuel McNeil-Warren, S,
        # Browns -- 2026 draft rookie (college during the 2025 season this
        # pipeline scores), so this alias won't unlock any 2025 stats for
        # him. Adding it now anyway so next season's run resolves cleanly.
}

SEASON = "2025"
WEEKS = range(1, 19)  # regular season is 18 WEEKS (17 games + 1 bye per team) --
                        # range(1,18) was a real bug that silently undercounted
                        # every player whose bye fell earlier in the season,
                        # found 2026-08-18 via 5 of 7 manually-verified players
                        # coming back exactly 1 game short, including two who'd
                        # never been flagged by any other diagnostic at all.

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
    """
    Rewritten 2026-08-19 against the league's complete, real scoring sheet
    (every row confirmed directly from the person's Sleeper league settings
    screenshots -- not assumed/standard-convention like the previous
    version). This fixes a confirmed real bug: the old version scored
    Aidan Hutchinson's real 2025 season at 154 pts; Sleeper's own leaders
    page shows his real 2025 total as 246. The categories added below
    account for the gap.

    FIELD NAME CONFIDENCE: the field names for pass_yd/pass_td/pass_int/
    rush_att/rush_yd/rush_td/rec/rec_yd/rec_td/fum_lost/idp_tkl_solo/
    idp_tkl_ast/idp_sack/idp_tkl_loss/idp_int/idp_pass_def were already
    live in the pipeline and producing real, verified output (Hutchinson's
    144 pts from JUST those categories checks out against his real box
    score), so those are trusted as-is. The NEWLY ADDED field names below
    (idp_qb_hit, idp_ff, idp_fum_rec, idp_td, idp_safety, blk_kick,
    pass_2pt/rush_2pt/rec_2pt, fum_rec_td, st_td/st_ff/st_fum_rec) are
    Sleeper's standard naming convention for these stat types but have NOT
    been individually verified against a real box score the way the
    original fields were -- these are common enough field names across
    Sleeper's API that they're very likely right, but this is the kind of
    thing that's worth a real spot-check (same as everything else new in
    this file) after the first real run, not assumed correct just because
    it's now in the code.

    MILESTONE BONUSES: these aren't separate raw stat fields Sleeper
    returns -- they're derived here by checking the already-fetched yardage
    totals against the sheet's thresholds. Tiers are exclusive (a 250-yard
    rushing game gets the 200+ bonus only, not both).
    """
    pts = 0.0

    # ---- Passing ----
    pass_yd = stats.get("pass_yd", 0)
    pts += pass_yd * 0.04                          # 1 pt / 25 yards
    pts += stats.get("pass_td", 0) * 4.0
    pts += stats.get("pass_2pt", 0) * 2.0           # ADDED -- was missing entirely
    pts += stats.get("pass_int", 0) * -2.0
    if pass_yd >= 400:
        pts += 3.0                                  # ADDED -- milestone bonus
    elif pass_yd >= 300:
        pts += 2.0                                  # ADDED -- milestone bonus

    # ---- Rushing ----
    rush_yd = stats.get("rush_yd", 0)
    pts += stats.get("rush_att", 0) * 0.2
    pts += rush_yd * 0.1                            # 1 pt / 10 yards
    pts += stats.get("rush_td", 0) * 6.0
    pts += stats.get("rush_2pt", 0) * 2.0           # ADDED -- was missing entirely
    if rush_yd >= 200:
        pts += 3.0                                  # ADDED -- milestone bonus
    elif rush_yd >= 100:
        pts += 2.0                                  # ADDED -- milestone bonus

    # ---- Receiving ----
    rec_yd = stats.get("rec_yd", 0)
    pts += stats.get("rec", 0) * 0.5
    pts += rec_yd * 0.1
    pts += stats.get("rec_td", 0) * 6.0
    pts += stats.get("rec_2pt", 0) * 2.0            # ADDED -- was missing entirely
    if rec_yd >= 200:
        pts += 3.0                                  # ADDED -- milestone bonus
    elif rec_yd >= 100:
        pts += 2.0                                  # ADDED -- milestone bonus

    # ---- Fumbles (offense) ----
    pts += stats.get("fum_lost", 0) * -2.0
    pts += stats.get("fum_rec_td", 0) * 6.0         # ADDED -- was missing entirely

    # ---- IDP: Tackles ----
    solo = stats.get("idp_tkl_solo", 0)
    ast = stats.get("idp_tkl_ast", 0)
    pts += solo * 1.5
    pts += ast * 0.75
    pts += stats.get("idp_tkl_loss", 0) * 2.0       # TFL

    # ---- IDP: Pressure ----
    sacks = stats.get("idp_sack", stats.get("sack", 0))
    pts += sacks * 3.0
    pts += stats.get("idp_qb_hit", 0) * 2.0         # ADDED -- was missing entirely

    # ---- IDP: Turnovers / scoring ----
    ints = stats.get("idp_int", stats.get("int", 0))
    pts += ints * 6.0
    pts += stats.get("idp_fum_rec", 0) * 4.0        # ADDED -- was missing entirely
    pts += stats.get("idp_ff", 0) * 3.0             # ADDED -- was missing entirely
    pts += stats.get("idp_safety", 0) * 3.0         # ADDED -- rare, likely near-zero impact
    pts += stats.get("blk_kick", 0) * 6.0           # ADDED -- rare, likely near-zero impact
    pts += stats.get("idp_td", 0) * 6.0             # ADDED -- rare, likely near-zero impact

    # ---- IDP: Coverage ----
    pd = stats.get("idp_pass_def", 0)
    pts += pd * 3.0

    # ---- IDP: per-game bonus thresholds (ADDED -- were missing entirely) ----
    if (solo + ast) >= 10:
        pts += 2.0
    if sacks >= 2:
        pts += 2.0
    if pd >= 3:
        pts += 2.0

    # ---- Special teams (ADDED -- rare, likely near-zero impact) ----
    pts += stats.get("st_td", 0) * 6.0
    pts += stats.get("st_ff", 0) * 3.0
    pts += stats.get("st_fum_rec", 0) * 3.0         # different value than IDP fum rec (3 vs 4)

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


# Real name collisions that position-matching alone can never safely
# resolve (multiple real people, same normalized name, same expected
# position). Found via the full 553-player run, then disambiguated
# 2026-08-19 using a one-off diagnostic (since removed) that printed each
# Sleeper candidate's team/status/years_exp -- picked whichever candidate's
# real-world details (current team, experience matching a known active
# player) actually matched the real person, verified against outside
# sources, not guessed from the name alone.
#
# 'chris jones' is worth a special note: the real Chris Jones (Chiefs DT)
# was in Sleeper's index tagged specifically as position "DT", not the
# generic "DL" this tool expects -- that's WHY position-matching missed
# him even though he was right there in the candidate list. This is a
# live instance of the "DL sub-position bias" issue already flagged as an
# open item (DT vs DE/EDGE potentially needing separate handling) -- worth
# revisiting when that gets addressed generally, since this hardcoded
# override is a workaround for this one player, not a fix for the
# underlying position-bucket gap.
#
# 'chris johnson' -> 13370 is a 2026 draft rookie (Dolphins CB), same
# situation as e-mcneilwarren above: the ID is now correct, but he was in
# college during the 2025 season this pipeline scores, so he'll still
# show zero games for this run. Not a bug.
MANUAL_ID_OVERRIDES = {
    'kyle williams': '12547',      # WR, Patriots
    'myles murphy': '10875',       # DL, Bengals
    'chris jones': '3558',         # DT, Chiefs
    'chris johnson': '13370',      # DB, Dolphins (2026 rookie, 0 games expected this run)
}


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
    with open(os.path.join(SCRIPT_DIR, "all_players.json")) as f:
        all_players = json.load(f)

    player_index = fetch_player_index()
    name_to_candidates = build_name_to_id_map(player_index)

    unmatched = []
    for p in all_players:
        key = p["key"]
        # Manual overrides take priority -- these are known name collisions
        # that position-matching can never safely resolve on its own, so
        # don't even attempt the normal path for them.
        if key in MANUAL_ID_OVERRIDES:
            p["sleeper_id"] = MANUAL_ID_OVERRIDES[key]
            continue
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
    zero_game_players = []  # captured instead of silently dropped -- this is
        # the list that needs a human look, same as Fred Warner and the
        # collisions did. "had_any_data" distinguishes two very different
        # cases: True means Sleeper had SOME weekly entry for this player
        # this season (worth checking why none of it counted as "played"),
        # False means Sleeper had literally nothing all season (much more
        # likely a genuine case -- true rookie who hadn't debuted, or
        # someone who spent the whole year on IR/practice squad).
    for p in all_players:
        pid = p.get("sleeper_id")
        if not pid:
            continue
        weekly_scores = []  # parallel to weeks_played -- weekly_scores[i] is
            # the real score for weeks_played[i]. Added 2026-08-19 to support
            # deriving the k shrinkage constant from real within-player vs.
            # between-player variance (sigma^2_within / sigma^2_between)
            # instead of the k=3 chosen-by-inspection value -- that
            # computation needs each week's individual score, not just the
            # season total, and previously only the total was kept.
        weeks_played = []
        weeks_excluded = []  # diagnostic: weeks with SOME stats entry but not counted as played
        games_played = 0
        for week, week_data in all_weeks.items():
            stats = week_data.get(pid)
            # REVERTED 2026-08-18: the gms_active OR-logic below was a real
            # mistake, not a minor tweak -- confirmed wrong by real ground
            # truth (Blake Cashman genuinely did NOT play weeks 2-5, despite
            # gms_active=1 on all four). gms_active does not reliably mean
            # "played" -- more likely "was on the active roster that week"
            # (dressed/eligible), which can be true even with zero real snaps
            # (healthy scratch, working back from injury, etc.). gp -- actual
            # recorded participation -- is the trustworthy signal. Went back
            # to trusting it alone rather than assuming a theory was correct
            # without verifying it against reality first.
            was_active = stats and (stats.get("gp") or 0) >= 1
            if was_active:
                games_played += 1
                weeks_played.append(week)
                weekly_scores.append(score_week(stats))
            elif stats:
                # Informational only -- do NOT assume these weeks should
                # count. gms_active=1 here does not prove the player
                # actually played (see the note above); this is worth a
                # human look, not an automatic correction. Confirmed real
                # cases where a human check said "no, he genuinely didn't
                # play" despite this flag firing.
                weeks_excluded.append({"week": week, "gp_value": stats.get("gp"), "gms_active_value": stats.get("gms_active")})
        if games_played == 0:
            zero_game_players.append({
                "player": p["key"], "pos": p["pos"], "sleeper_id": pid,
                "had_any_data": bool(weeks_excluded),
            })
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
            "weekly_points": [round(s, 2) for s in weekly_scores],  # parallel
                # array to weeks_played -- see the comment above weekly_scores
                # for why this is now captured.
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

    # NEW: the zero-game list itself, split by whether Sleeper had ANY data
    # for the player this season. "had_any_data=True" is the more suspicious
    # bucket -- something showed up in the weekly stats but never counted as
    # a played game, worth a closer look same as Fred Warner/the collisions
    # got. "had_any_data=False" is more likely genuine (true rookie who
    # hadn't debuted yet in 2025, or someone who spent the whole season on
    # IR/practice squad) but still worth a skim, not assumed clean.
    if zero_game_players:
        with_data = [z for z in zero_game_players if z["had_any_data"]]
        without_data = [z for z in zero_game_players if not z["had_any_data"]]
        print()
        print(f"=== {len(zero_game_players)} players resolved to a real Sleeper ID but showed ZERO played games this season ===")
        print(f"--- {len(with_data)} of these HAD some Sleeper data this season (worth a closer look -- see the flagged section above for why none of it counted) ---")
        for z in sorted(with_data, key=lambda x: x["player"]):
            print(f"  {z['player']:25s} {z['pos']:4s} sleeper_id={z['sleeper_id']}")
        print(f"--- {len(without_data)} of these had NO Sleeper data at all this season (more likely genuine -- true rookie or full-season IR/practice squad) ---")
        for z in sorted(without_data, key=lambda x: x["player"]):
            print(f"  {z['player']:25s} {z['pos']:4s} sleeper_id={z['sleeper_id']}")

    # 553 players is too much for a full table to be scannable in a log --
    # summarize instead of dumping everything. Full detail is still in
    # ppg_results.json for anyone who wants to look up a specific player.
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

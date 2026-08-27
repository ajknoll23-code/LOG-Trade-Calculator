#!/usr/bin/env python3
"""
scripts/draft_slot_projection_pipeline.py

Fixes a real, previously-flagged known limitation: every draft pick was
always valued at the "mid" slot regardless of the actual team's real
performance, understating real variance (a true 1st overall is worth
more than this; a true late 1st, less). Confirmed against KeepTradeCut's
own FAQ before building this: real dynasty pick markets DO differentiate
early/mid/late once real signal exists, but explicitly default ALL
future picks to "Mid" before the season that determines them has
started -- this pipeline matches that same real, stated convention, not
an invented one.

METHODOLOGY:
- Fetches real current Sleeper league standings (wins/losses/ties, real
  points-for as the tiebreaker -- Sleeper's own default tiebreaker
  convention).
- Reverses standings to get REAL draft order: worst record picks first,
  same as the real NFL draft and standard dynasty-league convention
  (confirmed directly with the person before building this -- getting
  the direction backwards would have silently corrupted every pick
  value).
- Splits the resulting 12-team order into three even tiers: ranks 1-4 =
  early, 5-8 = mid, 9-12 = late.
- Per the person's explicit choice (not the more conservative default
  this pipeline's author would have picked): reacts to real standings
  starting week 1, with no minimum-games buffer against early-season
  noise. A team's tier can and will move as their real record changes
  throughout the season.

SCOPING, IMPORTANT: this projection is only meaningful for the picks in
the NEXT upcoming rookie draft -- the one tied to the CURRENTLY IN-
PROGRESS real NFL season, which is the only season with any real
standings signal at all. A draft two seasons out depends on a season
that hasn't even started, so those picks have no real basis for
differentiation and must stay "mid" regardless of what this pipeline
outputs -- enforced in index.html's lookup function, not here, but
documented here too so this scoping isn't only implicit in the consuming
code.

REQUIRES NETWORK ACCESS (fetches live Sleeper league data).

USAGE: python3 scripts/draft_slot_projection_pipeline.py
Add --selftest to sanity-check the standings/reversal/tiering logic
against synthetic data before trusting real output.

OUTPUT: scripts/draft_slot_projection.json
  {generated_at, applies_to_season, standings: [...], tiers: {roster_id: tier}}
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = "https://api.sleeper.app/v1"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(ROOT, "config.json")
OUT_PATH = os.path.join(SCRIPT_DIR, "draft_slot_projection.json")

# The season whose real in-progress standings determine the NEXT rookie
# draft's slots. Needs manual updating once a year, same convention
# already established for PICK_SEASONS in index.html (see that list's
# own comment about 2026 being removed once that draft completed).
DETERMINING_SEASON = "2026"
APPLIES_TO_DRAFT_SEASON = "2027"

TIER_BOUNDARIES = [(1, 4, "early"), (5, 8, "mid"), (9, 12, "late")]

# NOT independently verified against this league's real commissioner-
# configured draft-order tiebreak rule -- per external review, "Sleeper
# default" is an assumption, not a confirmed fact, and this pipeline is
# predicting the league's REAL rookie draft order, which isn't
# guaranteed to be the same rule Sleeper uses for its own standings/
# playoff-seeding display. Coarse 4-team tiers don't make this
# irrelevant: a tiebreaker deciding a rank-4-vs-rank-5 boundary directly
# flips a pick between Early and Mid. Confirm the real rule with the
# league commissioner/settings before fully trusting output near a tier
# boundary. Current order (record pct -> points for -> points against ->
# roster_id) is a defensible default, not a confirmed one.
TIEBREAK_VERIFIED = False


def fetch_json(url, retries=3, backoff=2):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "trade-desk-draft-slot/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")


def load_league_id():
    with open(CONFIG_PATH) as f:
        return json.load(f)["league_id"]


# BACKLOG, per external review -- do not forget this before playoffs:
# this pipeline only ever reverses REGULAR-SEASON cumulative record. It
# has no concept of playoff results. That's fine for a projection only
# ever consulted mid-regular-season (which is all that's happened so
# far), but once this league's real playoffs begin determining actual
# final draft position, this pipeline can't keep pretending regular-
# season win-loss is the complete ordering mechanism -- IF this league's
# real draft-order rule treats playoff participants differently (e.g.
# reverse order of playoff finish, rather than just continuing the
# regular-season table). Two real phases needed eventually:
#   regular season -> current standings-based projection (this script)
#   after real final placement exists -> the league's actual real
#     draft-order rule, whatever that turns out to be once confirmed.
# Confirm the real rule with the league commissioner/settings well
# before the season ends, not after.
#
# ALSO A BACKLOG ITEM: DRAFT_SLOT_APPLIES_TO_SEASON / DETERMINING_SEASON
# need manual updating once a year (matches PICK_SEASONS' own existing
# manual-update convention). When the 2027 season begins: 2027 becomes
# the determining season for 2028 picks, and 2029 becomes the new
# default-'mid' season. Easy to let this quietly stay "2027" a year too
# long if nobody remembers -- worth a real calendar reminder, not just
# this comment.
def compute_standings(rosters):
    """
    Real standings: overall record percentage (accounting for ties, not
    just wins) descending, then real points-for, then real points-
    against, then roster_id as a final deterministic tiebreaker so sort
    order is never ambiguous.

    2026-08-26 FIX, per external review: the original version sorted by
    (wins desc, points_for desc) alone -- wrong whenever a tie exists,
    since Sleeper allows regular-season ties and two teams can have the
    same win count with very different overall records (3-1-1 vs.
    3-2-0). A tied game counts as half a win for ranking purposes, same
    convention as standard record-percentage calculations elsewhere in
    sports. This may go a full season without ever mattering in a league
    with few or no ties, but it's cheap to get right now rather than
    leave a real correctness gap sitting in the sort key.
    """
    standings = []
    for r in rosters:
        settings = r.get("settings", {})
        wins = settings.get("wins", 0)
        losses = settings.get("losses", 0)
        ties = settings.get("ties", 0)
        games = wins + losses + ties
        record_pct = (wins + 0.5 * ties) / games if games else 0.0
        fpts = settings.get("fpts", 0) + settings.get("fpts_decimal", 0) / 100.0
        fpts_against = settings.get("fpts_against", 0) + settings.get("fpts_against_decimal", 0) / 100.0
        standings.append({
            "roster_id": r["roster_id"], "wins": wins, "losses": losses,
            "ties": ties, "record_pct": round(record_pct, 4),
            "points_for": round(fpts, 2), "points_against": round(fpts_against, 2),
        })
    standings.sort(key=lambda s: (-s["record_pct"], -s["points_for"], -s["points_against"], s["roster_id"]))
    return standings


def assign_tiers(standings):
    """
    Reverses real standings into real draft order (worst record picks
    first), then splits into three even tiers. Returns {roster_id: tier}.
    """
    draft_order = list(reversed(standings))  # worst record first
    tiers = {}
    for i, team in enumerate(draft_order):
        draft_position = i + 1
        for lo, hi, tier_name in TIER_BOUNDARIES:
            if lo <= draft_position <= hi:
                tiers[team["roster_id"]] = tier_name
                break
    return tiers, draft_order


def run_selftest():
    print("Running self-test on synthetic data...")

    # 12 synthetic rosters with a known, unambiguous win-loss spread --
    # roster_id 1 is worst (0 wins), roster_id 12 is best (11 wins).
    synthetic_rosters = []
    for i in range(1, 13):
        synthetic_rosters.append({
            "roster_id": i,
            "settings": {"wins": i - 1, "losses": 12 - i, "ties": 0, "fpts": 1000 + i, "fpts_decimal": 0},
        })

    standings = compute_standings(synthetic_rosters)
    assert standings[0]["roster_id"] == 12, f"expected roster 12 (most wins) to rank 1st, got {standings[0]}"
    assert standings[-1]["roster_id"] == 1, f"expected roster 1 (fewest wins) to rank last, got {standings[-1]}"
    print("  Standings correctly ordered by real wins (descending) -- OK")

    tiers, draft_order = assign_tiers(standings)
    # worst record (roster_id=1) should pick FIRST -> early tier
    assert tiers[1] == "early", f"expected worst-record team to be 'early' draft tier, got {tiers[1]}"
    # best record (roster_id=12) should pick LAST -> late tier
    assert tiers[12] == "late", f"expected best-record team to be 'late' draft tier, got {tiers[12]}"
    print("  Worst record -> early pick, best record -> late pick (correct direction, verified) -- OK")

    tier_counts = {"early": 0, "mid": 0, "late": 0}
    for t in tiers.values():
        tier_counts[t] += 1
    assert tier_counts == {"early": 4, "mid": 4, "late": 4}, f"expected an even 4/4/4 split, got {tier_counts}"
    print("  Even 4/4/4 tier split -- OK")

    # points-for tiebreaker: two teams with identical wins, different fpts
    tied_rosters = [
        {"roster_id": 100, "settings": {"wins": 5, "losses": 5, "ties": 0, "fpts": 900, "fpts_decimal": 0}},
        {"roster_id": 101, "settings": {"wins": 5, "losses": 5, "ties": 0, "fpts": 950, "fpts_decimal": 0}},
    ]
    tied_standings = compute_standings(tied_rosters)
    assert tied_standings[0]["roster_id"] == 101, f"expected higher points-for to break the tie and rank first, got {tied_standings}"
    print("  Points-for tiebreaker on equal records -- OK")

    # REGRESSION TEST, per external review: a team with a tied GAME
    # (record-percentage credit for the tie) must rank above a team with
    # the same win count but no ties, even if the no-tie team has more
    # raw points-for. This is exactly the bug the original (wins, then
    # PF) sort had -- verifying it's actually fixed, not just that PF
    # breaks ties when wins are equal.
    real_record_rosters = [
        # Team A: 3-1-1 -> record_pct = (3 + 0.5)/5 = 0.70
        {"roster_id": 200, "settings": {"wins": 3, "losses": 1, "ties": 1, "fpts": 800, "fpts_decimal": 0}},
        # Team B: 3-2-0 -> record_pct = 3/5 = 0.60, but MORE raw points-for
        {"roster_id": 201, "settings": {"wins": 3, "losses": 2, "ties": 0, "fpts": 950, "fpts_decimal": 0}},
    ]
    real_record_standings = compute_standings(real_record_rosters)
    assert real_record_standings[0]["roster_id"] == 200, \
        (f"expected the team with the better real record (3-1-1, credit for the tie) to rank first "
         f"despite lower points-for, got {real_record_standings}")
    print("  Team with a tied game correctly outranks a team with more raw wins-count-equal points "
          "but a worse overall record -- OK (this is the exact bug the original wins-only sort had)")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()

    league_id = load_league_id()
    print(f"Fetching real rosters for league {league_id}...")
    rosters = fetch_json(f"{BASE}/league/{league_id}/rosters")
    print(f"  {len(rosters)} rosters fetched.")

    if not TIEBREAK_VERIFIED:
        print("\nWARNING: the draft-order tiebreak rule (record pct -> points for -> "
              "points against -> roster_id) has NOT been confirmed against this league's "
              "real commissioner-configured rookie draft-order rule -- it's a defensible "
              "default, not a verified fact. This matters most right at a tier boundary "
              "(e.g. rank 4 vs rank 5, Early vs Mid). Confirm the real rule, then set "
              "TIEBREAK_VERIFIED = True at the top of this script.")

    standings = compute_standings(rosters)
    tiers, draft_order = assign_tiers(standings)

    print(f"\nReal current standings (best record first):")
    for i, s in enumerate(standings):
        print(f"  {i+1}. roster_id={s['roster_id']}  {s['wins']}-{s['losses']}-{s['ties']}  "
              f"record_pct={s['record_pct']}  pts_for={s['points_for']}  pts_against={s['points_against']}")

    print(f"\nProjected {APPLIES_TO_DRAFT_SEASON} draft order (worst record picks first) and tiers:")
    for i, team in enumerate(draft_order):
        print(f"  pick {i+1}: roster_id={team['roster_id']}  ({tiers[team['roster_id']]})")

    output = {
        "generated_at": time.time(),
        "determining_season": DETERMINING_SEASON,
        "applies_to_draft_season": APPLIES_TO_DRAFT_SEASON,
        "tiebreak_verified": TIEBREAK_VERIFIED,
        "standings": standings,
        "tiers": tiers,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

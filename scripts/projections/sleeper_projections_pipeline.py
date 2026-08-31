"""
Sleeper 2026 projections pipeline -- fetches Sleeper's own forward-looking
2026 season projections (NOT actual game stats -- the season hasn't
started yet) and scores them under this league's exact custom rules, the
same way ppg_pipeline.py scores real games.

WHY A SEPARATE SCRIPT rather than extending ppg_pipeline.py: that script
hits Sleeper's STATS endpoint (/v1/stats/nfl/regular/{season}/{week}),
which only has real data for games already played. This hits Sleeper's
PROJECTIONS endpoint (/v1/projections/nfl/regular/{season}/{week}) --
same per-week/all-players response shape, so the fetch loop is nearly
identical, but it's forward-looking data for a season that hasn't
happened yet. Keeping this separate avoids overloading one script with
two conceptually different data sources and two different SEASON
constants that would be easy to mix up.

This is the "Sleeper half" of the technical breakdown's section 6e
2026 projections blend (proj_2026 = 0.5 * sleeper_projection + 0.5 *
fantasypros_projection). The FantasyPros half was extracted separately
from the uploaded roster screenshots, not fetched here.

HONESTY NOTE, same as durability_pipeline.py: the /v1/projections/
endpoint's existence and per-week shape is confirmed real (documented in
multiple third-party Sleeper API references), but this exact endpoint has
not been hit and verified against real output in this session -- I could
not run it myself (no outbound network in this sandbox). Before trusting
the output, sanity-check a couple of well-known players (e.g. a clear #1
projected player at a position) against what you'd expect.

RAW-CATEGORY OUTPUT ADDED (2026-08-27), per external review of the
FantasyPros API pipeline: this script always computed real per-player
season point totals by summing score_week() across 18 real weekly
projections, but only ever persisted the final total, never the raw
per-category sums that fed it. That blocked a real, needed analysis --
comparing Sleeper's and FantasyPros' raw stat-level projections
category-by-category (solo tackles, sacks, etc.) rather than inferring
disagreement from already-blended final point totals, which conflate
scoring-category coverage differences with genuine forecast/role
disagreements in a way that's hard to untangle after the fact (a real,
concrete example -- Maxx Crosby vs. Myles Murphy -- showed exactly this
problem: two real pass-rushers missing the identical categories, but
showing opposite disagreement directions with FantasyPros, because their
final-total ratio was picking up more than one real effect at once).
Now accumulates and persists real per-category season sums (same
summing convention as the existing point-total logic) to a SEPARATE
output file, kept apart from the existing sleeper_2026_projections.json
on purpose -- if a future run's values look different, this separation
lets you tell whether Sleeper's real projections changed or something in
this script's own logic changed, without that separation you can't tell
the difference after the fact.

USAGE: python3 scripts/projections/sleeper_projections_pipeline.py
Add --selftest to verify the scoring formula and the new raw-category
accumulation logic against synthetic multi-week data before trusting
real output.
Requires: requests (pip install requests --break-system-packages)
"""

import json
import os
import sys
import time
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(SCRIPT_DIR)
SEASON = 2026
# Same 18-week season-length fix already validated in ppg_pipeline.py --
# using 17 here would silently drop week 18 the same way the original
# bug did for actual stats.
WEEKS = range(1, 19)

# Every raw field score_week() actually reads, kept as one explicit list
# so the raw-category accumulator can't silently drift out of sync with
# the scoring formula if either one is edited later without the other.
# Where score_week() uses a fallback (idp_sack vs sack; idp_int vs int),
# the SAME fallback resolution is used here, accumulating one combined
# "sack"/"int" raw total rather than two separately-named, possibly
# double-counted fields.
RAW_CATEGORY_FIELDS = [
    "pass_yd", "pass_td", "pass_2pt", "pass_int",
    "rush_att", "rush_yd", "rush_td", "rush_2pt",
    "rec", "rec_yd", "rec_td", "rec_2pt",
    "fum_lost", "fum_rec_td",
    "idp_tkl_solo", "idp_tkl_ast", "idp_tkl_loss", "idp_qb_hit",
    "idp_fum_rec", "idp_ff", "idp_safety", "blk_kick", "idp_td", "idp_pass_def",
    "st_td", "st_ff", "st_fum_rec",
]


def score_week(stats):
    """
    Identical to ppg_pipeline.py's score_week (rewritten 2026-08-19 against
    the league's complete real scoring sheet -- see that file's version for
    the full explanation of what was added and why). Copied rather than
    imported so this script has no dependency on that file and can be
    dropped into scripts/projections/ standalone. Any change to league
    scoring rules needs to be made in both places; that's an accepted
    tradeoff for keeping the two pipelines independently runnable.
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
    print("Fetching Sleeper player index...")
    resp = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_week_projections(week):
    print(f"Fetching {SEASON} week {week} projections...")
    resp = requests.get(
        f"https://api.sleeper.app/v1/projections/nfl/regular/{SEASON}/{week}",
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def accumulate_raw_categories(running_totals, pid, stats):
    """
    Adds one week's raw stats into a player's running per-category season
    sum. Uses the SAME fallback resolution as score_week() for the two
    fields that have alternate names (idp_sack/sack, idp_int/int), storing
    them under one canonical key each rather than two separately-tracked,
    possibly-double-counted fields.
    """
    if pid not in running_totals:
        running_totals[pid] = {f: 0.0 for f in RAW_CATEGORY_FIELDS}
        running_totals[pid]["sack"] = 0.0
        running_totals[pid]["int"] = 0.0
    for field in RAW_CATEGORY_FIELDS:
        running_totals[pid][field] += stats.get(field, 0) or 0
    running_totals[pid]["sack"] += stats.get("idp_sack", stats.get("sack", 0)) or 0
    running_totals[pid]["int"] += stats.get("idp_int", stats.get("int", 0)) or 0


def run_selftest():
    print("Running self-test: scoring formula and raw-category accumulation...")

    week_stats = {"idp_tkl_solo": 6, "idp_tkl_ast": 2, "idp_sack": 1, "idp_pass_def": 1}
    pts = score_week(week_stats)
    expected = 6*1.5 + 2*0.75 + 1*3.0 + 1*3.0
    assert abs(pts - expected) < 0.01, f"expected {expected}, got {pts}"
    print(f"  score_week() matches a real hand-computed IDP stat line ({pts:.2f}) -- OK")

    running = {}
    accumulate_raw_categories(running, "test_pid", {"idp_sack": 1.5, "idp_tkl_solo": 4, "rush_yd": 20})
    accumulate_raw_categories(running, "test_pid", {"idp_sack": 0.5, "idp_tkl_solo": 6, "rush_yd": 15})
    assert running["test_pid"]["sack"] == 2.0, f"expected summed sacks 2.0, got {running['test_pid']['sack']}"
    assert running["test_pid"]["idp_tkl_solo"] == 10, f"expected summed solo tackles 10, got {running['test_pid']['idp_tkl_solo']}"
    assert running["test_pid"]["rush_yd"] == 35, f"expected summed rush yards 35, got {running['test_pid']['rush_yd']}"
    print("  Raw-category accumulation correctly sums across multiple weeks (2.0 sacks, 10 solo tackles, "
          "35 rush yards from 2 synthetic weeks) -- OK")

    running2 = {}
    accumulate_raw_categories(running2, "test_pid2", {"idp_sack": 1.0})
    accumulate_raw_categories(running2, "test_pid2", {"sack": 1.0})
    assert running2["test_pid2"]["sack"] == 2.0, \
        f"expected the idp_sack/sack fallback to resolve to one combined total (2.0), got {running2['test_pid2']['sack']}"
    print("  idp_sack/sack fallback resolves to one combined raw total across DIFFERENT weeks, matching "
          "score_week()'s own fallback logic -- OK")

    running3 = {}
    accumulate_raw_categories(running3, "test_pid3", {"idp_sack": 1.0, "sack": 1.0})
    assert running3["test_pid3"]["sack"] == 1.0, \
        (f"expected idp_sack and sack in the SAME week to resolve to ONE value (1.0), matching "
         f"score_week()'s own dict.get(a, dict.get(b)) fallback -- NOT sum to 2.0 -- got "
         f"{running3['test_pid3']['sack']}")
    running4 = {}
    accumulate_raw_categories(running4, "test_pid4", {"idp_int": 1.0, "int": 1.0})
    assert running4["test_pid4"]["int"] == 1.0, \
        f"expected idp_int/int same-week fallback to resolve to 1.0, not double-count, got {running4['test_pid4']['int']}"
    print("  idp_sack/sack AND idp_int/int correctly resolve to ONE value when BOTH real field names "
          "appear in the SAME week -- OK (this specific case wasn't actually tested before, only claimed "
          "in the comment)")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

    player_index = fetch_player_index()

    season_totals = {}
    weeks_with_data = {}
    raw_category_totals = {}
    raw_weekly_snapshot = {}

    for week in WEEKS:
        week_data = fetch_week_projections(week)
        raw_weekly_snapshot[str(week)] = week_data
        for pid, stats in week_data.items():
            if not stats:
                continue
            pts = score_week(stats)
            season_totals[pid] = season_totals.get(pid, 0.0) + pts
            weeks_with_data[pid] = weeks_with_data.get(pid, 0) + 1
            accumulate_raw_categories(raw_category_totals, pid, stats)
        time.sleep(0.3)

    results = []
    raw_results = []
    for pid, total in season_totals.items():
        p = player_index.get(pid, {})
        name = (p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}").strip().lower()
        pos = p.get("position")
        results.append({
            "sleeper_id": pid,
            "player": name,
            "pos": pos,
            "team": p.get("team"),
            "sleeper_2026_proj_total": round(total, 1),
            "weeks_with_projection_data": weeks_with_data[pid],
        })
        raw_results.append({
            "sleeper_id": pid,
            "player": name,
            "pos": pos,
            "team": p.get("team"),
            "fantasy_positions": p.get("fantasy_positions"),
            "weeks_with_projection_data": weeks_with_data[pid],
            "raw_category_season_totals": {k: round(v, 3) for k, v in raw_category_totals.get(pid, {}).items()},
        })

    final_keep_pids = {r["sleeper_id"] for r in results if r["player"].strip() and r["sleeper_2026_proj_total"] > 0}
    results = [r for r in results if r["sleeper_id"] in final_keep_pids]
    results.sort(key=lambda r: -r["sleeper_2026_proj_total"])

    raw_keep_pids = {r["sleeper_id"] for r in raw_results if r["player"].strip() and r["weeks_with_projection_data"] > 0}
    raw_results = [r for r in raw_results if r["sleeper_id"] in raw_keep_pids]
    raw_results.sort(key=lambda r: r["player"])

    with open(os.path.join(SCRIPTS_DIR, "sleeper_2026_projections.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {len(results)} players with real projection data to sleeper_2026_projections.json")

    with open(os.path.join(SCRIPTS_DIR, "artifacts", "generated", "sleeper_2026_raw_categories.json"), "w") as f:
        json.dump(raw_results, f, indent=2)
    print(f"Wrote {len(raw_results)} players' raw per-category season totals to scripts/artifacts/generated/sleeper_2026_raw_categories.json "
          f"(broader audit universe than the production list -- {len(raw_results) - len(results)} more players "
          f"than sleeper_2026_projections.json, since this one isn't filtered by final point total)")

    with open(os.path.join(SCRIPTS_DIR, "artifacts", "generated", "sleeper_2026_raw_weekly.json"), "w") as f:
        json.dump(raw_weekly_snapshot, f)
    print(f"Wrote real unprocessed weekly source data (18 weeks) to scripts/artifacts/generated/sleeper_2026_raw_weekly.json -- "
          f"this file will be large; that's expected for a true immutable snapshot, not an error.")

    print("\nTop 10 by projected total:")
    for r in results[:10]:
        print(f"  {r['player']:25s} {r['pos']:3s} {r['sleeper_2026_proj_total']:6.1f}")


if __name__ == "__main__":
    main()

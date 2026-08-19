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

USAGE: python3 sleeper_projections_pipeline.py
Requires: requests (pip install requests --break-system-packages)
"""

import json
import os
import time
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SEASON = 2026
# Same 18-week season-length fix already validated in ppg_pipeline.py --
# using 17 here would silently drop week 18 the same way the original
# bug did for actual stats.
WEEKS = range(1, 19)


def score_week(stats):
    """
    Identical to ppg_pipeline.py's score_week -- copied rather than
    imported so this script has no dependency on that file and can be
    dropped into scripts/ standalone. Any change to league scoring rules
    needs to be made in both places; that's an accepted tradeoff for
    keeping the two pipelines independently runnable.
    """
    pts = 0.0
    pts += stats.get("pass_yd", 0) * 0.04
    pts += stats.get("pass_td", 0) * 4.0
    pts += stats.get("pass_int", 0) * -2.0
    pts += stats.get("rush_att", 0) * 0.2
    pts += stats.get("rush_yd", 0) * 0.1
    pts += stats.get("rush_td", 0) * 6.0
    pts += stats.get("rec", 0) * 0.5
    pts += stats.get("rec_yd", 0) * 0.1
    pts += stats.get("rec_td", 0) * 6.0
    pts += stats.get("fum_lost", 0) * -2.0
    pts += stats.get("idp_tkl_solo", 0) * 1.5
    pts += stats.get("idp_tkl_ast", 0) * 0.75
    pts += stats.get("idp_sack", stats.get("sack", 0)) * 3.0
    pts += stats.get("idp_tkl_loss", 0) * 2.0
    pts += stats.get("idp_int", stats.get("int", 0)) * 6.0
    pts += stats.get("idp_pass_def", 0) * 3.0
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


def main():
    player_index = fetch_player_index()

    # player_id -> summed projected points across all 18 weeks. Summing
    # weekly projections (rather than looking for a single season-total
    # projection field) matches exactly how ppg_pipeline.py derives real
    # season totals from weekly data, so both halves of the eventual
    # blend are built the same way.
    season_totals = {}
    weeks_with_data = {}  # player_id -> count of weeks that had a projection at all

    for week in WEEKS:
        week_data = fetch_week_projections(week)
        for pid, stats in week_data.items():
            if not stats:
                continue
            pts = score_week(stats)
            season_totals[pid] = season_totals.get(pid, 0.0) + pts
            weeks_with_data[pid] = weeks_with_data.get(pid, 0) + 1
        time.sleep(0.3)

    results = []
    for pid, total in season_totals.items():
        p = player_index.get(pid, {})
        results.append({
            "sleeper_id": pid,
            "player": (p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}").strip().lower(),
            "pos": p.get("position"),
            "team": p.get("team"),
            "sleeper_2026_proj_total": round(total, 1),
            "weeks_with_projection_data": weeks_with_data[pid],
        })

    # Only keep players who actually have a name and some real projection
    # signal -- Sleeper's projections endpoint, like stats, includes a lot
    # of noise entries (inactive/practice-squad players with all-zero
    # weeks) that would just be dead weight in the output.
    results = [r for r in results if r["player"].strip() and r["sleeper_2026_proj_total"] > 0]
    results.sort(key=lambda r: -r["sleeper_2026_proj_total"])

    with open(os.path.join(SCRIPT_DIR, "sleeper_2026_projections.json"), "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nWrote {len(results)} players with real projection data to sleeper_2026_projections.json")
    print("Top 10 by projected total:")
    for r in results[:10]:
        print(f"  {r['player']:25s} {r['pos']:3s} {r['sleeper_2026_proj_total']:6.1f}")


if __name__ == "__main__":
    main()

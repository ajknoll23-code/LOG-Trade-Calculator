#!/usr/bin/env python3
"""
scripts/fantasypros_offense_pipeline.py

Replaces the manually-transcribed FantasyPros offensive projection totals
with a real, automated pipeline -- fetches FantasyPros' live projection
pages (which expose real raw stat categories, not just a final total) and
scores them under this league's exact, already-validated formula (the
same score_week() logic verified in ppg_pipeline.py), instead of trusting
FantasyPros' own precomputed FPTS.

WHY THIS EXISTS: confirmed directly, via real fetches of FantasyPros' own
live pages, that their displayed FPTS is explicitly labeled "based on
Standard Scoring" -- and Standard Scoring does not include this league's
real 0.2-points-per-rush-attempt bonus. Verified the real, quantified gap
this creates by comparing FantasyPros' own live totals against this
league's real formula applied to the same visible raw stats:
  Saquon Barkley (295.8 att): +59.2 pts missing (24.3% understatement)
  Lamar Jackson (118.7 att):  +23.7 pts missing (7.3% understatement)
  Jalen Hurts (111.8 att):    +22.4 pts missing (7.0% understatement)
  CeeDee Lamb / Justin Jefferson (minimal rush volume): negligible gap,
    confirming rushing volume is A real, major driver of this gap for
    RBs and rushing QBs -- NOT the sole explanation. Also confirmed
    directly against FantasyPros' own dedicated scoring-settings page
    (fantasypros.com/scoring-settings/, corrected from an earlier,
    wrong reading of a 2025 contributor blog post): FantasyPros scores
    a thrown interception at -1, this league at -2 -- a second, separate
    real contributor to the QB-specific gap, alongside the missing
    rush-attempt bonus. Both are real; neither is "the" whole story on
    its own.

WHAT THIS DOES NOT FIX: FantasyPros' projection pages give SEASON
TOTALS, not per-game splits, so this league's real per-game milestone
bonuses (300+/400+ pass yards, 100+/200+ rush or rec yards in a single
game) cannot be reconstructed from a season aggregate -- same
fundamental limitation already documented for IDP per-game bonuses
(10+ tackles, 2+ sacks, 3+ PD in one game). This pipeline computes
everything EXCEPT those milestone bonuses, and says so explicitly in
its output rather than silently omitting them.

REQUIRES NETWORK ACCESS (fetches live FantasyPros pages).

USAGE: python3 scripts/fantasypros_offense_pipeline.py
Add --selftest to sanity-check the parsing and scoring logic against
synthetic data matching FantasyPros' real observed table structure,
before trusting real output.

OUTPUT: scripts/fantasypros_offense_pipeline_output.json
  {generated_at, players: {name: {raw stats, trade_desk_proj, fantasypros_stated_proj, gap}}}
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(SCRIPT_DIR, "fantasypros_offense_pipeline_output.json")

PAGES = {
    "QB": "https://www.fantasypros.com/nfl/projections/qb.php?week=draft",
    "RB": "https://www.fantasypros.com/nfl/projections/rb.php?week=draft",
    "WR": "https://www.fantasypros.com/nfl/projections/wr.php?week=draft",
    "TE": "https://www.fantasypros.com/nfl/projections/te.php?week=draft",
}


def fetch_html(url, retries=3, backoff=2):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (trade-desk-fp-offense/1.0)"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")


def parse_number(s):
    """FantasyPros formats big numbers with commas (e.g. '1,382.5') --
    strip those and coerce to float. Returns 0.0 for anything unparseable
    (dashes, empty cells) rather than raising, since a missing category
    for a given player (e.g. a pure receiver with no passing stats) is
    expected, not an error."""
    if s is None:
        return 0.0
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def score_offense(pass_yd=0, pass_td=0, pass_int=0, rush_att=0, rush_yd=0, rush_td=0,
                   rec=0, rec_yd=0, rec_td=0, fum_lost=0):
    """
    This league's real offensive formula, copied verbatim from the
    already-validated score_week() in ppg_pipeline.py -- NOT re-derived
    or approximated. Deliberately excludes the per-game milestone bonuses
    (300+/400+ pass yards, 100+/200+ rush or rec yards) since those can't
    be reconstructed from a season-total projection -- see module
    docstring.

    HONEST SCOPE NOTE, per external review: the gap this produces vs.
    FantasyPros' own stated total is NOT purely a rushing-attempt-bonus
    effect for QBs. Confirmed directly against FantasyPros' own real,
    dedicated scoring-settings page (fantasypros.com/scoring-settings/,
    the actual source their "Standard Scoring" footnote links to -- more
    authoritative than a contributor blog post that gave since-corrected
    numbers, a real mistake caught and fixed this same session): this
    league scores a thrown interception at -2, FantasyPros' Standard
    Scoring uses -1. For a QB, that's a second, separate real contributor
    to the gap alongside the missing rush-attempt bonus -- both are real,
    neither should be described as "the" explanation on its own.
    """
    pts = 0.0
    pts += pass_yd * 0.04
    pts += pass_td * 4.0
    pts += pass_int * -2.0
    pts += rush_att * 0.2
    pts += rush_yd * 0.1
    pts += rush_td * 6.0
    pts += rec * 0.5
    pts += rec_yd * 0.1
    pts += rec_td * 6.0
    pts += fum_lost * -2.0
    return pts


def parse_fantasypros_table(html, position):
    """
    Parses the real FantasyPros projection table structure -- confirmed
    via direct fetch for ALL FOUR positions (QB/RB/WR/TE), including a
    real, embarrassing correction: TE was originally assumed identical
    to WR without being independently checked, and that assumption was
    wrong -- FantasyPros' real TE table has no rushing columns at all
    (REC,YDS,TDS,FL,FPTS -- 5 fields, not 7), so the original code's
    `if len(nums) < 7: continue` silently dropped every single TE. Caught
    by external review, verified directly against the real live page
    before fixing, not just taken on faith.
      QB: ATT,CMP,YDS,TDS,INTS (passing) | ATT,YDS,TDS (rushing) | FL | FPTS
      RB: ATT,YDS,TDS (rushing) | REC,YDS,TDS (receiving) | FL | FPTS
      WR: REC,YDS,TDS (receiving) | ATT,YDS,TDS (rushing) | FL | FPTS
      TE: REC,YDS,TDS (receiving) | FL | FPTS -- no rushing columns

    SECOND REAL BUG FIXED HERE, also caught by external review: the
    original cell-extraction regex only matched numeric-looking content
    (`[\\d,\\.]+`), which meant a dash ("-", FantasyPros' real notation
    for a zero/not-applicable cell) simply vanished from the sequence
    instead of being captured as zero -- silently shifting every
    subsequent value left by one position for that row. A row with even
    one dash could produce a fully wrong-but-plausible-looking set of
    stats without any error being raised. Now extracts EVERY <td> cell
    in order (dashes included) and lets parse_number() -- which already
    correctly handles dashes -- convert each one, instead of dropping
    non-numeric cells before parse_number() ever sees them.
    """
    players = {}
    row_blocks = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S)
    for block in row_blocks:
        name_match = re.search(r'/nfl/projections/[a-z0-9-]+\.php"[^>]*>([^<]+)<', block)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        # Extract EVERY <td> cell's raw inner content, dashes included --
        # NOT just numeric-looking ones. This is the fix for the silent
        # column-shift bug described above.
        raw_cells = re.findall(r'<td[^>]*>\s*([^<]*?)\s*</td>', block)
        if len(raw_cells) < 5:
            continue
        nums = [parse_number(c) for c in raw_cells]

        if position == "QB":
            if len(nums) < 9:
                continue
            pass_att, pass_cmp, pass_yd, pass_td, pass_int, rush_att, rush_yd, rush_td, fl = nums[:9]
            fpts = nums[9] if len(nums) > 9 else None
            players[name.lower()] = {
                "pass_att": pass_att, "pass_cmp": pass_cmp, "pass_yd": pass_yd,
                "pass_td": pass_td, "pass_int": pass_int, "rush_att": rush_att,
                "rush_yd": rush_yd, "rush_td": rush_td, "fum_lost": fl,
                "fantasypros_stated_fpts": fpts,
            }
        elif position == "RB":
            if len(nums) < 7:
                continue
            rush_att, rush_yd, rush_td, rec, rec_yd, rec_td, fl = nums[:7]
            fpts = nums[7] if len(nums) > 7 else None
            players[name.lower()] = {
                "rush_att": rush_att, "rush_yd": rush_yd, "rush_td": rush_td,
                "rec": rec, "rec_yd": rec_yd, "rec_td": rec_td, "fum_lost": fl,
                "fantasypros_stated_fpts": fpts,
            }
        elif position == "WR":
            if len(nums) < 7:
                continue
            rec, rec_yd, rec_td, rush_att, rush_yd, rush_td, fl = nums[:7]
            fpts = nums[7] if len(nums) > 7 else None
            players[name.lower()] = {
                "rec": rec, "rec_yd": rec_yd, "rec_td": rec_td, "rush_att": rush_att,
                "rush_yd": rush_yd, "rush_td": rush_td, "fum_lost": fl,
                "fantasypros_stated_fpts": fpts,
            }
        elif position == "TE":
            # Real schema, verified 2026-08-27: REC,YDS,TDS,FL,FPTS only --
            # no rushing columns at all, unlike WR. This is the fix for
            # the bug described in this function's docstring.
            if len(nums) < 4:
                continue
            rec, rec_yd, rec_td, fl = nums[:4]
            fpts = nums[4] if len(nums) > 4 else None
            players[name.lower()] = {
                "rec": rec, "rec_yd": rec_yd, "rec_td": rec_td,
                "rush_att": 0.0, "rush_yd": 0.0, "rush_td": 0.0,  # TE table has no rushing columns to read
                "fum_lost": fl, "fantasypros_stated_fpts": fpts,
            }
    return players


def run_selftest():
    print("Running self-test on synthetic data matching FantasyPros' real observed table structure...")

    # Synthetic HTML matching the REAL structure confirmed via direct
    # fetch (simplified but structurally faithful: name link, then
    # numeric <td> cells in the real observed column order).
    synthetic_qb_html = """
    <table><tr>
    <td><a href="/nfl/projections/test-qb.php">Test Passer</a></td>
    <td>500.0</td><td>330.0</td><td>4000.0</td><td>28.0</td><td>10.0</td>
    <td>100.0</td><td>500.0</td><td>5.0</td><td>3.0</td><td>300.0</td>
    </tr></table>
    """
    parsed = parse_fantasypros_table(synthetic_qb_html, "QB")
    assert "test passer" in parsed, f"expected to parse a QB row, got {parsed}"
    p = parsed["test passer"]
    assert p["pass_yd"] == 4000.0 and p["rush_att"] == 100.0 and p["fum_lost"] == 3.0, \
        f"expected correct field mapping, got {p}"
    print("  QB row parsing matches real observed column order -- OK")

    # REGRESSION TEST for the real dash-handling bug caught by external
    # review: a "-" cell (FantasyPros' real notation for zero/no data)
    # must NOT vanish from the extracted sequence -- if it does, every
    # value after it silently shifts left, producing a plausible-looking
    # but WRONG row instead of an obvious failure. Same QB row as above,
    # but with fumbles lost shown as "-" instead of "3.0".
    synthetic_qb_html_with_dash = """
    <table><tr>
    <td><a href="/nfl/projections/test-qb2.php">Dash Test Passer</a></td>
    <td>500.0</td><td>330.0</td><td>4000.0</td><td>28.0</td><td>10.0</td>
    <td>100.0</td><td>500.0</td><td>5.0</td><td>-</td><td>300.0</td>
    </tr></table>
    """
    parsed_dash = parse_fantasypros_table(synthetic_qb_html_with_dash, "QB")
    assert "dash test passer" in parsed_dash, f"expected to parse a row with a dash cell, got {parsed_dash}"
    pd_row = parsed_dash["dash test passer"]
    assert pd_row["fum_lost"] == 0.0, \
        f"expected the dash cell to parse as fum_lost=0, got {pd_row['fum_lost']}"
    assert pd_row["fantasypros_stated_fpts"] == 300.0, \
        (f"expected FPTS to still be correctly read as the LAST cell (300.0) -- if the dash had "
         f"caused a silent column shift, this would be wrong instead, got {pd_row['fantasypros_stated_fpts']}")
    print("  Dash ('-') cell correctly parses as 0 without shifting subsequent columns -- OK "
          "(this is the exact silent-corruption bug caught by external review)")

    # TE-specific schema test -- the real bug: TE has NO rushing columns,
    # unlike WR. Confirmed directly against FantasyPros' real live TE
    # page before fixing (REC,YDS,TDS,FL,FPTS -- 5 fields, not 7).
    synthetic_te_html = """
    <table><tr>
    <td><a href="/nfl/projections/test-te.php">Test Tight End</a></td>
    <td>70.0</td><td>800.0</td><td>6.0</td><td>0.2</td><td>150.0</td>
    </tr></table>
    """
    parsed_te = parse_fantasypros_table(synthetic_te_html, "TE")
    assert "test tight end" in parsed_te, f"expected to parse a TE row with the real 5-field schema, got {parsed_te}"
    te_row = parsed_te["test tight end"]
    assert te_row["rec"] == 70.0 and te_row["rec_yd"] == 800.0 and te_row["fantasypros_stated_fpts"] == 150.0, \
        f"expected correct TE field mapping (no rushing columns), got {te_row}"
    print("  TE row parsing uses the REAL 5-field schema (no rushing columns) -- OK "
          "(this is the exact bug that silently dropped every TE, caught by external review)")

    # Scoring sanity: known inputs, known real-formula output
    score = score_offense(pass_yd=4000, pass_td=28, pass_int=10, rush_att=100, rush_yd=500, rush_td=5, fum_lost=3)
    expected = 4000*0.04 + 28*4 - 10*2 + 100*0.2 + 500*0.1 + 5*6 - 3*2
    assert abs(score - expected) < 0.01, f"expected {expected}, got {score}"
    print(f"  score_offense() matches hand-computed real formula ({score:.1f}) -- OK")

    # Real-world regression check: the exact Saquon Barkley numbers found
    # via direct live fetch -- confirms this script would have caught the
    # real, already-verified gap.
    saquon_score = score_offense(rush_att=295.8, rush_yd=1299.1, rush_td=8.2, rec=41.7, rec_yd=330.4, rec_td=2.1, fum_lost=1.0)
    fantasypros_stated = 243.8
    gap = saquon_score - fantasypros_stated
    assert gap > 50, f"expected the real, already-confirmed ~59pt gap for Saquon Barkley, got {gap:.1f}"
    print(f"  Real regression check (Saquon Barkley): computed {saquon_score:.1f} vs. FantasyPros' stated "
          f"{fantasypros_stated} -- gap of {gap:.1f}pts matches the already-verified real finding -- OK")

    # Comma-formatted number parsing (real pages format e.g. "1,382.5")
    assert parse_number("1,382.5") == 1382.5, "expected comma-stripping to work"
    assert parse_number("-") == 0.0, "expected a dash (no data) to parse as 0, not raise"
    print("  Comma-formatted numbers and empty/dash cells parse correctly -- OK")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

    all_players = {}
    for position, url in PAGES.items():
        print(f"Fetching {position} projections from {url}...")
        html = fetch_html(url)
        parsed = parse_fantasypros_table(html, position)
        print(f"  Parsed {len(parsed)} {position} players.")
        # Safety net: this parses real HTML, not a stable API -- if
        # FantasyPros changes their page structure, silently getting 0
        # or 1 players back would be worse than a loud failure, since a
        # near-empty result could get committed and treated as real data.
        if len(parsed) < 20:
            print(f"ERROR: only parsed {len(parsed)} {position} players (expected 50+). "
                  f"FantasyPros likely changed their page structure -- the parser needs "
                  f"updating, not blind trust in this output.")
            sys.exit(1)
        for name, stats in parsed.items():
            trade_desk_proj = score_offense(
                pass_yd=stats.get("pass_yd", 0), pass_td=stats.get("pass_td", 0),
                pass_int=stats.get("pass_int", 0), rush_att=stats.get("rush_att", 0),
                rush_yd=stats.get("rush_yd", 0), rush_td=stats.get("rush_td", 0),
                rec=stats.get("rec", 0), rec_yd=stats.get("rec_yd", 0),
                rec_td=stats.get("rec_td", 0), fum_lost=stats.get("fum_lost", 0),
            )
            fp_stated = stats.get("fantasypros_stated_fpts")
            all_players[name] = {
                "position": position,
                **stats,
                "trade_desk_proj_excl_milestone_bonuses": round(trade_desk_proj, 1),
                "gap_vs_fantasypros_stated": round(trade_desk_proj - fp_stated, 1) if fp_stated is not None else None,
            }

    output = {
        "generated_at": time.time(),
        "note": "trade_desk_proj_excl_milestone_bonuses does NOT include this league's real per-game "
                "milestone bonuses (300+/400+ pass yards, 100+/200+ rush or rec yards in a single game) -- "
                "season-total projections can't reconstruct per-game splits. Treat as a floor, not the "
                "final number.",
        "players": all_players,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {OUT_PATH} ({len(all_players)} total players across {len(PAGES)} positions)")


if __name__ == "__main__":
    main()

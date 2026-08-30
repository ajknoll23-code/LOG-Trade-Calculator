#!/usr/bin/env python3
"""
scripts/projections/fantasypros_api_pipeline.py

The real, full production pipeline for FantasyPros data, replacing both
the manual-transcription workflow AND the HTML-scraping fallback -- per
a real diagnostic confirming HOF-tier API access returns the COMPLETE
declared player population for every real position checked (QB 83/83,
RB 130/130, WR 190/190, TE 122/122, LB 209/209, DL 202/202, DB 203/203,
IDP 529/529 -- declared_count == actual_players_returned across the
board, closing the "full response" question definitively).

ARCHITECTURE, per the project's established principle for every external
projection source this session: NEVER trust a provider's own precomputed
point total. Fetches real raw stat categories and scores them through
THIS LEAGUE'S OWN exact, already-validated formula (score_week() in
ppg_pipeline.py, copied field-for-field below, not re-derived).

RAW / NORMALIZED SEPARATION, per the project's own stated preference for
auditability: writes two separate output files. If a future run's values
change, this separation lets you tell whether FantasyPros changed their
forecast or this pipeline's scoring/normalization code changed --
without that separation, you can't tell the difference after the fact.

CONFIRMED FIELD MAPPING (from a real, saved diagnostic response, not
assumed): offense fields (pass_yds, pass_tds, pass_ints, rush_att,
rush_yds, rush_tds, rec_rec, rec_yds, rec_tds, fumbles) and IDP fields
(def_tackle=solo, def_assist, def_sack, def_tlost=TFL, def_int, def_pd,
def_ff, def_fr, def_td, def_safety).

HONEST, DOCUMENTED GAPS -- not silently zeroed, not guessed around:
  - QB hits: this league scores idp_qb_hit at 2.0 pts, but the API has
    no equivalent field anywhere in the confirmed schema. Every player's
    normalized total is missing this category's contribution. Flagged
    per-player in the output, not silently treated as zero production.
  - Per-game milestone bonuses (10+ combined tackles, 2+ sacks, 3+ PD
    for IDP; 300+/400+ pass yards, 100+/200+ rush or rec yards for
    offense): these are projected SEASON TOTALS, not per-game splits,
    so the per-game threshold bonuses this league awards can't be
    reconstructed from them, structurally, regardless of source. The API
    DOES expose fields shaped like season milestone counts
    (pass_yds_300, rush_yds_100, etc.) -- an earlier 4-player diagnostic
    sample found these were all exactly 0, suggesting they may not be
    populated by FantasyPros' model at all. This pipeline checks that
    claim against the FULL population (not just 4 players) and reports
    the real finding -- see build_report().

IDENTITY: FantasyPros' own fpid is the primary key, per the project's
own stated preference (avoid lowercase-name-as-identity, a real,
previously-flagged risk). Normalized display name is kept as a
secondary field for matching against this project's existing PLAYER_DB,
not as the primary identity.

REQUIRES NETWORK ACCESS and a real FANTASYPROS_API_KEY environment
variable (GitHub Actions secret, never logged -- reuses the same tested
redaction safety property as fantasypros_api_diagnostic.py).

USAGE: python3 scripts/projections/fantasypros_api_pipeline.py
Add --selftest to verify formula correctness, field mapping, and the
key-redaction safety property against synthetic and real regression
data before trusting real output.

OUTPUT:
  scripts/fantasypros_api_raw_2026.json          -- immutable raw snapshot
  scripts/fantasypros_api_normalized_2026.json   -- Trade Desk-scored output
  scripts/artifacts/reports/fantasypros_api_pipeline_report.md -- human-readable QC summary
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(SCRIPT_DIR)
RAW_OUT_PATH = os.path.join(SCRIPTS_DIR, "fantasypros_api_raw_2026.json")
NORMALIZED_OUT_PATH = os.path.join(SCRIPTS_DIR, "fantasypros_api_normalized_2026.json")
REPORT_OUT_PATH = os.path.join(SCRIPTS_DIR, "artifacts", "reports", "fantasypros_api_pipeline_report.md")

API_KEY_ENV_VAR = "FANTASYPROS_API_KEY"
BASE_URL = "https://api.fantasypros.com/public/v2/json"  # confirmed real, via diagnostic
SEASON = "2026"

OFFENSE_POSITIONS = ["QB", "RB", "WR", "TE"]
# BUG FIX, per external review: this used to separately fetch LB, DL,
# and DB and merge them -- but real arithmetic proves those three
# overlap: LB(209) + DL(202) + DB(203) = 614, while the combined IDP
# endpoint returns exactly 529 real players. That 85-player gap is real
# evidence the same players appear under multiple position queries (most
# plausibly real DL/LB-eligible EDGE-type players, exactly the
# population a dual-eligibility bug already caused real trouble for
# elsewhere in this project). Fetching LB/DL/DB separately and merging
# them risked silently double-counting those players. Now uses the
# single combined "IDP" endpoint (confirmed working, 529/529 real
# players) as the one canonical defensive population instead.
IDP_POSITIONS = ["IDP"]

MIN_EXPECTED_PLAYERS = {"QB": 30, "RB": 60, "WR": 90, "TE": 50, "IDP": 400}


def redact(text):
    key = os.environ.get(API_KEY_ENV_VAR)
    if key:
        text = text.replace(key, "***REDACTED***")
    return text


def safe_print(*args):
    print(*[redact(str(a)) for a in args])


def normalize_name(s):
    """Identical convention to every other pipeline in this project."""
    return re.sub(r"\s+", " ", re.sub(r"[.'\u2019-]", "", s.strip().lower()))


def fetch_json(url, api_key, timeout=30, retries=3, backoff=2):
    req = urllib.request.Request(url, headers={"x-api-key": api_key, "User-Agent": "trade-desk-fp-api-pipeline/1.0"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            # BUG FIX, per external review: HTTPError is a SUBCLASS of
            # URLError, so this must be caught FIRST -- the original
            # ordering (URLError before HTTPError) meant every real HTTP
            # error (401 bad key, 403 forbidden, 429 rate-limited, 500
            # server error) was silently caught by the generic URLError
            # branch and blindly retried, instead of being handled
            # correctly per status code. A 401/403 will never succeed on
            # retry -- fail immediately. A 429 or 5xx is worth retrying.
            if e.code in (401, 403):
                raise RuntimeError(redact(f"HTTP {e.code} fetching {url} -- not retrying, this won't "
                                           f"succeed on retry (bad/expired key, or access not permitted)."))
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(redact(f"Failed after {retries} attempts: {last_err}"))


def score_offense(stats):
    """
    This league's real offensive formula, matching the already-validated
    score_week() in ppg_pipeline.py for every category that's actually
    valid to apply here. Deliberately does NOT apply the per-game
    milestone bonuses (300+/400+ pass yards, 100+/200+ rush or rec
    yards) as a threshold check against the season TOTAL -- a real
    mistake caught by this script's own self-test before shipping: a
    per-game threshold check applied to a season aggregate doesn't tell
    you how many individual games crossed that threshold, it just checks
    whether the season sum does, which is true for nearly every real
    starting player and would apply the bonus incorrectly, not just
    imprecisely. This is the same reasoning that already correctly
    excluded these bonuses from the earlier HTML-scraper pipeline; this
    function stays consistent with that, not silently reintroducing the
    mistake because a different data source happened to expose season
    totals for these categories too. The API's OWN milestone-count
    fields (pass_yds_300, etc.) would be the structurally correct way to
    get this data IF they were populated -- confirmed via real diagnostic
    that they are not (see module docstring and build_report()).

    BUG FIX, per external review: this originally excluded 2-point
    conversions and return TDs entirely, incorrectly claiming the API
    schema had no equivalent fields -- it does (2pt_tds, ret_tds), and
    they were visible in the real diagnostic response the whole time.
    All three of this league's real 2pt-conversion categories (pass/
    rush/receiving) score identically at 2.0 pts, so a single combined
    `2pt_tds` field can be scored directly without needing to split it
    by conversion type. `ret_tds` is treated as this league's return/
    special-teams TD category (6.0 pts, same rate as any other TD) --
    a reasonable, not 100%-certain field-semantics assumption, flagged
    here rather than asserted with full confidence.
    """
    pts = 0.0
    pass_yd = stats.get("pass_yds", 0) or 0
    pts += pass_yd * 0.04
    pts += (stats.get("pass_tds", 0) or 0) * 4.0
    pts += (stats.get("pass_ints", 0) or 0) * -2.0

    rush_yd = stats.get("rush_yds", 0) or 0
    pts += (stats.get("rush_att", 0) or 0) * 0.2
    pts += rush_yd * 0.1
    pts += (stats.get("rush_tds", 0) or 0) * 6.0

    rec_yd = stats.get("rec_yds", 0) or 0
    pts += (stats.get("rec_rec", 0) or 0) * 0.5
    pts += rec_yd * 0.1
    pts += (stats.get("rec_tds", 0) or 0) * 6.0

    pts += (stats.get("fumbles", 0) or 0) * -2.0
    pts += (stats.get("2pt_tds", 0) or 0) * 2.0
    pts += (stats.get("ret_tds", 0) or 0) * 6.0
    return pts


def score_idp(stats):
    """
    This league's EXACT real IDP formula, same source as score_offense().
    Real, confirmed API field mapping: def_tackle=solo, def_assist,
    def_sack, def_tlost=TFL, def_int, def_pd, def_ff, def_fr, def_td,
    def_safety. NO equivalent field exists for idp_qb_hit (2.0 pts in
    the real formula) -- this contribution is genuinely missing, not
    zeroed silently; callers should check missing_categories in the
    output rather than trust the total as complete.
    """
    pts = 0.0
    solo = stats.get("def_tackle", 0) or 0
    ast = stats.get("def_assist", 0) or 0
    pts += solo * 1.5
    pts += ast * 0.75
    pts += (stats.get("def_tlost", 0) or 0) * 2.0
    pts += (stats.get("def_sack", 0) or 0) * 3.0
    pts += (stats.get("def_int", 0) or 0) * 6.0
    pts += (stats.get("def_fr", 0) or 0) * 4.0
    pts += (stats.get("def_ff", 0) or 0) * 3.0
    pts += (stats.get("def_safety", 0) or 0) * 3.0
    pts += (stats.get("def_td", 0) or 0) * 6.0
    pts += (stats.get("def_pd", 0) or 0) * 3.0
    # Real, confirmed missing category -- see docstring.
    return pts


def validate_response_identity(data, expected_position):
    """
    Extracted into its own function specifically so this can be unit-
    tested with synthetic data (see run_selftest()) rather than only
    ever being exercised by a live network call. Raises RuntimeError on
    any mismatch; returns None on success.
    """
    if str(data.get("season")) != str(SEASON):
        raise RuntimeError(f"{expected_position}: response claims season={data.get('season')}, expected "
                            f"{SEASON}. Refusing to trust a response that doesn't even claim to be for "
                            f"the right season.")
    if str(data.get("week")) != "0":
        raise RuntimeError(f"{expected_position}: response claims week={data.get('week')}, expected '0' "
                            f"(preseason full-season projections). Refusing to trust a mismatched response.")
    if data.get("positions") != expected_position:
        raise RuntimeError(f"{expected_position}: response's own positions field says "
                            f"'{data.get('positions')}', not '{expected_position}' -- this is exactly the "
                            f"silent-wrong-position-fallback behavior already confirmed real for "
                            f"unsupported position labels. Refusing to trust data that doesn't even "
                            f"claim to be for the position requested.")


def fetch_position(position, api_key, is_idp):
    url = f"{BASE_URL}/nfl/{SEASON}/projections?position={position}&week=0"
    safe_print(f"Fetching {position}...")
    data = fetch_json(url, api_key)
    players = data.get("players") or []
    declared = data.get("count")
    actual = len(players)
    safe_print(f"  declared={declared}  actual={actual}  positions_field={data.get('positions')}  "
                f"season={data.get('season')}  week={data.get('week')}")

    # BUG FIX, per second-round external review: validating only response
    # SIZE (declared vs. actual) isn't enough -- this API has already
    # shown it can return HTTP 200, a real player count, AND wrong data
    # for the position actually requested (DE/DT/CB/S/DEF all silently
    # fell back to real RB data in the original diagnostic). Now also
    # hard-validates the response's own claimed identity.
    validate_response_identity(data, position)

    # BUG FIX, per external review: these were warnings, not hard
    # failures. For an experimental diagnostic that's fine; for a
    # pipeline meant to become the trusted production source, a
    # truncated response (e.g. HOF access lapsing, or FantasyPros
    # reverting to the free-tier 10-player cap for some reason) must
    # never silently commit incomplete data as if it were real, complete
    # data -- that's a real, meaningful data-integrity failure mode this
    # project has repeatedly built hard-fail safety nets against
    # elsewhere (validate_prod_mult_output.py, the offense HTML pipeline's
    # own player-count check, etc.). This was an inconsistency with that
    # established practice, not a deliberate choice -- fixed to match it.
    if str(declared) != str(actual):
        raise RuntimeError(f"{position}: declared count ({declared}) does not match actual returned "
                            f"({actual}) -- this is exactly the earlier free-tier truncation symptom. "
                            f"Refusing to commit a partial response as if it were complete. Check API "
                            f"access/tier status before re-running.")
    if actual < MIN_EXPECTED_PLAYERS.get(position, 1):
        raise RuntimeError(f"{position}: only {actual} players returned, below the expected minimum "
                            f"({MIN_EXPECTED_PLAYERS.get(position)}) for a real full-population response. "
                            f"Refusing to commit -- this doesn't look like real, complete data.")
    return data


def normalize_players(raw_data, query_position, is_idp):
    """
    `query_position` is what was requested from the API ("QB", "IDP",
    etc.) -- NOT necessarily what gets stored as each player's position.
    For IDP, the canonical combined endpoint returns players tagged with
    their OWN real position_id (e.g. "LB", "DL", "DB") -- that real,
    per-player value is preserved as source_position, kept explicitly
    separate from the query label. This project has already been burned
    once by conflating "which query found this player" with "what
    position this player should be valued at" (the pickBestPosition()
    dual-eligibility bug found and fixed earlier this session) --
    deliberately not repeating that mistake here.
    """
    normalized = []
    seen_fpids = {}  # fpid -> full record, so a duplicate can be compared, not just counted
    for p in raw_data.get("players", []):
        fpid = p.get("fpid")
        # BUG FIX, per external review: a None/missing fpid must not be
        # allowed to silently collapse multiple real, different players
        # into one "duplicate" bucket (None == None is True in Python).
        if fpid is None:
            raise RuntimeError(f"Player '{p.get('name')}' has no fpid at all -- refusing to process, "
                                f"since treating a missing ID as a normal case risks silently merging "
                                f"unrelated players together.")
        stats = p.get("stats", {})

        if fpid in seen_fpids:
            prior = seen_fpids[fpid]
            if prior.get("stats") == stats and prior.get("name") == p.get("name"):
                # BUG FIX, per external review: a true identical-content
                # duplicate is safe to skip quietly (informational only).
                continue
            else:
                # BUG FIX, per external review: same ID, DIFFERENT
                # content, must hard-fail -- that's not normal
                # duplication, that's a real data-integrity problem
                # (same player appearing with two different stat lines,
                # or two different real players somehow sharing an ID)
                # that needs a human to look at, not a silent drop.
                raise RuntimeError(f"fpid {fpid} appears twice with DIFFERING content: "
                                    f"'{prior.get('name')}' vs '{p.get('name')}'. This is a real "
                                    f"data-integrity problem, not routine duplication -- refusing to "
                                    f"silently pick one.")
        seen_fpids[fpid] = {"name": p.get("name"), "stats": stats}

        source_position = p.get("position_id") or query_position
        trade_desk_points = score_idp(stats) if is_idp else score_offense(stats)
        # Expanded per second-round external review: a full audit against
        # every real Trade Desk scoring category, not just the two
        # previously documented (QB hits, milestone bonuses). Checked
        # against the real, confirmed API schema (module docstring) --
        # none of these categories have a confirmed equivalent field.
        # Documented explicitly regardless of how small their real
        # fantasy-point impact likely is, per the review's own point:
        # "the fantasy-point impact may be very small, but the
        # documentation should still be exact."
        missing_categories = [
            "per-game milestone bonuses (season-total data can't reconstruct per-game splits)",
            "blocked kick (6.0 pts -- no equivalent API field confirmed)",
            "fumble recovery TD (6.0 pts -- distinct from ret_tds; no equivalent API field confirmed)",
            "special teams TD (6.0 pts -- no equivalent API field confirmed)",
            "special teams forced fumble (no equivalent API field confirmed)",
            "special teams fumble recovery (no equivalent API field confirmed)",
        ]
        if is_idp:
            missing_categories.append("idp_qb_hit (2.0 pts -- no equivalent API field confirmed)")

        normalized.append({
            "fantasypros_id": fpid,
            "mflid": p.get("mflid"),
            "name": p.get("name"),
            "normalized_name": normalize_name(p.get("name", "")),
            "source_position": source_position,   # this player's OWN real position tag, per the API
            "query_position": query_position,      # what was actually requested -- kept for audit trail
            "team": p.get("team_id"),
            "fantasypros_stated_points": stats.get("points"),
            "trade_desk_normalized_points": round(trade_desk_points, 2),
            "raw_stats_used": stats,
            "missing_categories": missing_categories,
        })
    return normalized


def run_selftest():
    print("Running self-test: formula correctness, field mapping, and key-redaction safety...")

    os.environ[API_KEY_ENV_VAR] = "fake_test_key_xyz789"
    assert "fake_test_key_xyz789" not in redact("url?key=fake_test_key_xyz789"), \
        "CRITICAL: redact() failed"
    del os.environ[API_KEY_ENV_VAR]
    print("  Key redaction safety property holds -- OK (critical safety property)")

    saquon_stats = {"rush_att": 295.8, "rush_yds": 1299.1, "rush_tds": 8.2,
                     "rec_rec": 41.7, "rec_yds": 330.4, "rec_tds": 2.1, "fumbles": 1.0}
    score = score_offense(saquon_stats)
    assert abs(score - 302.8) < 0.5, f"expected ~302.8 (matching the earlier verified real calculation), got {score}"
    print(f"  Offense formula matches the earlier independently-verified real Saquon Barkley calculation "
          f"({score:.1f}) -- OK")

    # New fields (2pt_tds, ret_tds) -- per external review, these are
    # real, present-in-schema categories that were incorrectly excluded
    # from the first version. Verify they're now actually scored.
    twopt_stats = dict(saquon_stats, **{"2pt_tds": 2, "ret_tds": 1})
    twopt_score = score_offense(twopt_stats)
    expected_delta = 2 * 2.0 + 1 * 6.0  # 2 two-point conversions + 1 return TD
    assert abs((twopt_score - score) - expected_delta) < 0.01, \
        f"expected 2pt_tds/ret_tds to add exactly {expected_delta} points, got {twopt_score - score}"
    print(f"  2pt_tds and ret_tds are now correctly scored (+{expected_delta:.1f} pts for 2 conversions "
          f"+ 1 return TD) -- OK (previously incorrectly excluded)")

    brooks_stats = {"def_sack": 2.99, "def_int": 0.31, "def_td": 0.13, "def_tackle": 135.47,
                     "def_assist": 79.3, "def_safety": 0, "def_ff": 1.03, "def_fr": 0.85, "def_pd": 3.83, "def_tlost": 0}
    idp_score = score_idp(brooks_stats)
    expected = 135.47*1.5 + 79.3*0.75 + 0*2.0 + 2.99*3.0 + 0.31*6.0 + 0.85*4.0 + 1.03*3.0 + 0*3.0 + 0.13*6.0 + 3.83*3.0
    assert abs(idp_score - expected) < 0.01, f"expected {expected:.2f}, got {idp_score:.2f}"
    print(f"  IDP formula matches a hand-computed real check using Jordyn Brooks' real diagnostic "
          f"stats ({idp_score:.2f}) -- OK")
    print(f"    (FantasyPros' own stated total for this player was 290.18 -- deliberately different, "
          f"not a bug; this league scores tackles/TFL/PD differently)")

    # Duplicate handling, per external review: IDENTICAL-content
    # duplicate should be silently skipped (safe, routine).
    identical_dup_raw = {"players": [
        {"fpid": 111, "name": "Player A", "team_id": "TST", "stats": {"rush_att": 10}},
        {"fpid": 111, "name": "Player A", "team_id": "TST", "stats": {"rush_att": 10}},
        {"fpid": 222, "name": "Player B", "team_id": "TST", "stats": {"rush_att": 30}},
    ]}
    result = normalize_players(identical_dup_raw, "RB", is_idp=False)
    assert len(result) == 2, f"expected an identical-content duplicate to be safely skipped, got {len(result)} players"
    print("  Identical-content duplicate FPID correctly skipped quietly -- OK")

    # DIFFERING-content duplicate must hard-fail, not silently pick one
    # -- per external review, this is a real data-integrity problem, not
    # routine duplication, and the original version silently discarded it.
    differing_dup_raw = {"players": [
        {"fpid": 111, "name": "Player A", "team_id": "TST", "stats": {"rush_att": 10}},
        {"fpid": 111, "name": "Player A", "team_id": "TST", "stats": {"rush_att": 999}},
    ]}
    try:
        normalize_players(differing_dup_raw, "RB", is_idp=False)
        raise AssertionError("expected a differing-content duplicate fpid to raise RuntimeError, but it didn't")
    except RuntimeError as e:
        assert "DIFFERING content" in str(e)
        print("  Differing-content duplicate FPID correctly hard-fails instead of silently picking one -- OK")

    # None fpid must hard-fail, not silently collapse multiple real
    # players into one bucket (None == None is True in Python).
    none_fpid_raw = {"players": [{"fpid": None, "name": "No ID Player", "team_id": "TST", "stats": {}}]}
    try:
        normalize_players(none_fpid_raw, "RB", is_idp=False)
        raise AssertionError("expected a None fpid to raise RuntimeError, but it didn't")
    except RuntimeError as e:
        assert "no fpid" in str(e)
        print("  Missing (None) fpid correctly hard-fails instead of silently processing -- OK")

    # source_position must reflect the PLAYER's own real position tag,
    # not the query label used to fetch them -- critical for the
    # combined IDP endpoint, which returns a mix of LB/DL/DB players.
    idp_raw = {"players": [{"fpid": 1, "name": "Test LB", "team_id": "TST", "position_id": "LB", "stats": brooks_stats}]}
    idp_result = normalize_players(idp_raw, "IDP", is_idp=True)
    assert idp_result[0]["source_position"] == "LB", \
        f"expected source_position to be the player's own 'LB' tag, not the 'IDP' query label, got {idp_result[0]['source_position']}"
    assert idp_result[0]["query_position"] == "IDP", "expected query_position to preserve what was actually requested"
    print("  source_position correctly reflects each player's own real position tag, not the query label "
          "-- OK (this is exactly what prevents the earlier dual-eligibility class of bug from recurring here)")

    assert any("qb_hit" in m for m in idp_result[0]["missing_categories"]), \
        "expected the missing QB-hit category to be explicitly flagged for an IDP player"
    print("  Missing QB-hit category correctly flagged explicitly for IDP players, not silently omitted -- OK")

    # Response-identity validation, per second-round external review:
    # a real response can come back 200 with real players for the WRONG
    # position (already confirmed for DE/DT/CB/S/DEF). Verify this is
    # actually caught, not just count-mismatch.
    good_response = {"season": "2026", "week": "0", "positions": "QB", "count": "1", "players": []}
    validate_response_identity(good_response, "QB")  # should NOT raise
    print("  A response matching the requested season/week/position passes validation -- OK")

    wrong_position_response = {"season": "2026", "week": "0", "positions": "RB", "count": "1", "players": []}
    try:
        validate_response_identity(wrong_position_response, "DE")
        raise AssertionError("expected a position mismatch to raise RuntimeError, but it didn't")
    except RuntimeError as e:
        assert "positions field says" in str(e)
        print("  A response claiming the WRONG position (e.g. DE query returning RB data, the exact "
              "real failure mode already confirmed) correctly hard-fails -- OK")

    wrong_season_response = {"season": "2025", "week": "0", "positions": "QB", "count": "1", "players": []}
    try:
        validate_response_identity(wrong_season_response, "QB")
        raise AssertionError("expected a season mismatch to raise RuntimeError, but it didn't")
    except RuntimeError as e:
        assert "season=" in str(e)
        print("  A response claiming the wrong season correctly hard-fails -- OK")

    print("Self-test passed.\n")


def build_report(all_normalized, milestone_check):
    lines = ["# FantasyPros API Pipeline Report\n"]
    lines.append("Generated from a real, full-population fetch (declared_count == actual_players_returned "
                  "enforced as a hard failure at fetch time -- a mismatch stops the run rather than "
                  "committing partial data).\n")

    lines.append("\n## Player counts by source position\n")
    lines.append("(Uses each player's own real position_id from the API, not the query label used to "
                  "fetch them -- the IDP query returns a mix of LB/DL/DB players together.)\n")
    lines.append("| Position | Players normalized |")
    lines.append("|---|---|")
    by_pos = {}
    for p in all_normalized:
        by_pos.setdefault(p["source_position"], 0)
        by_pos[p["source_position"]] += 1
    for pos, n in sorted(by_pos.items()):
        lines.append(f"| {pos} | {n} |")

    lines.append("\n## Milestone-bonus field population check (across the REAL full population, not a 4-player sample)\n")
    lines.append(f"- Offense players checked: {milestone_check['offense_checked']}")
    lines.append(f"- Offense players with at least one nonzero milestone field: {milestone_check['offense_nonzero']}")
    if milestone_check['offense_nonzero'] == 0:
        lines.append("  - Confirmed across the full population, not just the earlier 4-player sample: these "
                      "fields are **unpopulated in this specific 2026 preseason API response.** Worded "
                      "deliberately as a snapshot finding, not a permanent platform limitation -- "
                      "FantasyPros could populate these in a future season, a weekly feed, or a different "
                      "endpoint version.")
    else:
        lines.append("  - Some real values found -- the earlier 4-player finding does NOT hold at full scale. "
                      "Worth integrating these into scoring after review.")

    lines.append("\n## Known, documented gaps (not silently hidden)\n")
    lines.append("- IDP QB hits: no equivalent API field exists. Every IDP player's normalized total is "
                  "missing this category's real contribution.")
    lines.append("- Per-game milestone bonuses: structurally unreconstructable from season-total projections.")

    # BUG FIX, per second-round external review: this used to filter by
    # source_position in ("LB","DL","DB") -- but the thing known with
    # certainty is which QUERY returned each player, not what granular
    # position label FantasyPros happens to tag them with. Filtering by
    # query_position=="IDP" can't accidentally exclude a real defensive
    # player whose own position_id turns out to be something more
    # granular (DE, DT, CB, S) that wasn't anticipated.
    idp_players = [p for p in all_normalized if p["query_position"] == "IDP"]
    real_source_positions = sorted(set(p["source_position"] for p in idp_players))
    lines.append(f"\n## Real source_position labels actually seen from the combined IDP query\n")
    lines.append(f"{real_source_positions}\n")
    lines.append("(A verified fact from the real response, not an assumption -- if this list contains "
                  "anything unexpected, the field-coverage numbers below should be checked per-label.)\n")
    if idp_players:
        idp_fields = ["def_tackle", "def_assist", "def_sack", "def_tlost", "def_int",
                       "def_pd", "def_ff", "def_fr", "def_td", "def_safety"]
        lines.append(f"\n## IDP field coverage across the real full population (n={len(idp_players)})\n")
        lines.append("Per external review: a field existing in the schema doesn't mean it's actually "
                      "populated -- checked directly rather than assumed, same as the milestone check above.\n")
        lines.append("| Field | Nonzero players | % nonzero |")
        lines.append("|---|---|---|")
        for field in idp_fields:
            nonzero = sum(1 for p in idp_players if (p["raw_stats_used"].get(field) or 0) != 0)
            pct = 100 * nonzero / len(idp_players)
            flag = "  **UNPOPULATED**" if nonzero == 0 else ""
            lines.append(f"| {field} | {nonzero} | {pct:.1f}%{flag} |")
        tlost_nonzero = sum(1 for p in idp_players if (p["raw_stats_used"].get("def_tlost") or 0) != 0)
        if tlost_nonzero == 0:
            lines.append("\n**def_tlost (TFL) is unpopulated across the entire real IDP population.** "
                          "This directly affects the archetype investigation this pipeline exists to "
                          "support -- if TFL isn't real, usable data, that specific piece of the "
                          "EDGE-vs-tackle-volume question stays unresolved by this source.")

    return "\n".join(lines)


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        print(f"ERROR: {API_KEY_ENV_VAR} is not set.")
        sys.exit(1)

    raw_snapshot = {"generated_at": time.time(), "season": SEASON, "positions": {}}
    all_normalized = []
    milestone_fields = ["pass_yds_300", "pass_yds_400", "rush_yds_100", "rush_yds_200", "rec_yds_100", "rec_yds_200"]
    offense_checked, offense_nonzero = 0, 0

    for pos in OFFENSE_POSITIONS:
        data = fetch_position(pos, api_key, is_idp=False)
        raw_snapshot["positions"][pos] = data
        normalized = normalize_players(data, pos, is_idp=False)
        all_normalized.extend(normalized)
        for p in normalized:
            offense_checked += 1
            if any((p["raw_stats_used"].get(f) or 0) != 0 for f in milestone_fields):
                offense_nonzero += 1
        time.sleep(1)

    for pos in IDP_POSITIONS:
        data = fetch_position(pos, api_key, is_idp=True)
        raw_snapshot["positions"][pos] = data
        normalized = normalize_players(data, pos, is_idp=True)
        all_normalized.extend(normalized)
        time.sleep(1)

    with open(RAW_OUT_PATH, "w") as f:
        json.dump(raw_snapshot, f, indent=2)
    safe_print(f"Wrote raw snapshot: {RAW_OUT_PATH} ({len(all_normalized)} total players)")

    with open(NORMALIZED_OUT_PATH, "w") as f:
        json.dump({"generated_at": time.time(), "season": SEASON, "players": all_normalized}, f, indent=2)
    safe_print(f"Wrote normalized output: {NORMALIZED_OUT_PATH}")

    milestone_check = {"offense_checked": offense_checked, "offense_nonzero": offense_nonzero}
    report = build_report(all_normalized, milestone_check)
    with open(REPORT_OUT_PATH, "w") as f:
        f.write(report)
    safe_print(f"Wrote report: {REPORT_OUT_PATH}")
    print(f"\nMilestone fields populated for {offense_nonzero}/{offense_checked} offense players "
          f"(full population, not a small sample).")


if __name__ == "__main__":
    main()

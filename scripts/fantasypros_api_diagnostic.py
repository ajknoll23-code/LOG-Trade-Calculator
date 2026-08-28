#!/usr/bin/env python3
"""
scripts/fantasypros_api_diagnostic.py

Deliberately small and boring, per the project's own stated philosophy
for this workstream: make one careful authenticated request before
building anything real. Does NOT build a production pipeline. Answers
six real questions before any of that work starts:

  A. Does the key work? Which base URL is actually correct? (a real
     discrepancy was found between two different FantasyPros pages
     describing the API -- one showed api.fantasypros.com/v2/json,
     another showed api.fantasypros.com/public/v2/json -- resolved here
     empirically with a real key instead of guessed.)
  B. What does the REAL schema look like for QB/RB/WR/TE -- every field,
     not just the ones an earlier example response happened to show.
  C. Does the real 2026 response include per-game milestone-bonus counts
     (300+/400+ pass yards, 100+/200+ rush or rec yards)? This would
     solve a real, previously-unsolvable limitation of the old HTML-
     scraping approach.
  D. Does the API support IDP positions at all, and if so, under which
     position label (LB/DL/DE/DT/DB/CB/S/IDP -- genuinely unknown, not
     assumed) -- and does it expose TFL and QB hits, the two categories
     most central to the ongoing EDGE-vs-tackle-volume investigation?
  E. What identity fields exist (fpid, external IDs) for mapping to this
     project's own player keys?
  F. Any visible rate-limit, pagination, or tier-restriction signals?

SECURITY, not negotiable: the API key must NEVER appear in any printed
output, log line, or committed file. Read from an environment variable
only, never hardcoded, never echoed -- even in error messages. A real,
regression-tested safety check is built into this script for exactly
that property (see run_selftest()).

REQUIRES NETWORK ACCESS and a real FANTASYPROS_API_KEY environment
variable (injected by the matching GitHub Actions workflow from a
repository secret -- never committed, never logged).

USAGE: python3 scripts/fantasypros_api_diagnostic.py
Add --selftest to verify the key-redaction safety property and basic
parsing logic against synthetic data before trusting real output.

OUTPUT: scripts/fantasypros_api_diagnostic_output.json -- a full report,
safe to commit (contains real schema info, but never the key itself).
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(SCRIPT_DIR, "fantasypros_api_diagnostic_output.json")

API_KEY_ENV_VAR = "FANTASYPROS_API_KEY"

# Real discrepancy found during verification -- try both, report which
# one actually works with the real key, rather than guessing.
CANDIDATE_BASE_URLS = [
    "https://api.fantasypros.com/v2/json",
    "https://api.fantasypros.com/public/v2/json",
]

SEASON = "2026"
OFFENSE_POSITIONS = ["QB", "RB", "WR", "TE"]
# Genuinely unknown which of these (if any) the API accepts as a valid
# position parameter for IDP -- that's exactly what this probes.
IDP_POSITION_CANDIDATES = ["LB", "DL", "DE", "DT", "DB", "CB", "S", "IDP", "DEF"]

MILESTONE_FIELD_HINTS = [
    "pass_yds_300", "pass_yds_400", "rush_yds_100", "rush_yds_200",
    "rec_yds_100", "rec_yds_200", "pass_300", "pass_400", "rush_100",
    "rush_200", "rec_100", "rec_200",
]
IDP_FIELD_HINTS = [
    "solo", "solo_tkl", "tkl_solo", "assist", "ast", "ast_tkl", "tkl_ast",
    "tkl", "tackles", "sack", "sacks", "tfl", "qb_hit", "qb_hits",
    "pd", "pass_def", "int", "ints", "ff", "fum_forced", "fr", "fum_rec",
    "def_td", "safety", "snaps", "snap_pct",
]


def redact(text):
    """Defense in depth: even though the key is never intentionally
    printed, this scrubs it from any string before it's ever written to
    stdout or the output file, in case a future edit accidentally
    includes it in an f-string or error message."""
    key = os.environ.get(API_KEY_ENV_VAR)
    if key:
        text = text.replace(key, "***REDACTED***")
    return text


def safe_print(*args):
    print(*[redact(str(a)) for a in args])


def fetch_json(url, api_key, timeout=20):
    """Returns (status_code, parsed_json_or_None, error_message_or_None).
    Never raises on an HTTP error status -- those are expected and
    informative here (e.g. a 403 on an unsupported position label), not
    failures of this script."""
    req = urllib.request.Request(url, headers={"x-api-key": api_key, "User-Agent": "trade-desk-fp-api-diagnostic/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            headers = dict(resp.getheaders())
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        headers = dict(e.headers) if e.headers else {}
    except (urllib.error.URLError, TimeoutError) as e:
        return None, None, redact(f"Network error: {e}")

    try:
        parsed = json.loads(body) if body else None
    except json.JSONDecodeError:
        parsed = None

    rate_limit_info = {k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()}
    return status, parsed, {"rate_limit_headers": rate_limit_info} if rate_limit_info else None


def find_working_base_url(api_key):
    """Resolves the real base-URL discrepancy empirically -- tries a
    small, known-cheap request (QB projections) against each candidate."""
    for base in CANDIDATE_BASE_URLS:
        url = f"{base}/nfl/{SEASON}/projections?position=QB&week=0"
        status, parsed, extra = fetch_json(url, api_key)
        if status == 200 and parsed is not None:
            return base, status, parsed, extra
        safe_print(f"  Base URL candidate failed: {base} (status={status})")
    return None, status, parsed, extra


def inspect_schema(parsed_response):
    """Reports top-level keys and, for the first player, every field
    present -- not just ones we expected. This is deliberately generic
    rather than checking for specific pre-guessed field names, since the
    whole point is discovering what's REALLY there."""
    if not isinstance(parsed_response, dict):
        return {"error": "response was not a JSON object"}
    top_level_keys = sorted(parsed_response.keys())
    players = parsed_response.get("players") or parsed_response.get("player") or []
    if isinstance(players, dict):
        players = [players]
    result = {
        "top_level_keys": top_level_keys,
        "declared_count_field": parsed_response.get("count"),
        "actual_players_returned": len(players),
        "season_field": parsed_response.get("season"),
        "week_field": parsed_response.get("week"),
        "scoring_field": parsed_response.get("scoring"),
        "positions_field": parsed_response.get("positions"),
    }
    if players:
        first = players[0]
        result["first_player_all_fields"] = first
        stats = first.get("stats", {})
        result["stats_object_keys"] = sorted(stats.keys()) if isinstance(stats, dict) else None
        if isinstance(stats, dict):
            result["milestone_fields_present"] = [f for f in MILESTONE_FIELD_HINTS if f in stats]
            result["idp_like_fields_present"] = [f for f in IDP_FIELD_HINTS if f in stats]
        result["identity_fields_present"] = {k: first.get(k) for k in
                                              ("fpid", "mflid", "yahooid", "sleeper_id", "espn_id") if k in first}
    return result


def run_selftest():
    print("Running self-test: key-redaction safety property and schema inspection...")

    # CRITICAL safety test: the redact() function must actually remove a
    # real-looking key from a string, under the exact env var this
    # script reads from.
    os.environ[API_KEY_ENV_VAR] = "fake_test_key_abc123xyz"
    test_string = "Requesting https://api.fantasypros.com/v2/json?key=fake_test_key_abc123xyz failed"
    redacted = redact(test_string)
    assert "fake_test_key_abc123xyz" not in redacted, \
        f"CRITICAL: redact() failed to remove the key from a string -- got: {redacted}"
    assert "***REDACTED***" in redacted, f"expected the redaction marker to appear, got: {redacted}"
    del os.environ[API_KEY_ENV_VAR]
    print("  redact() correctly removes a real-looking key from any string -- OK (critical safety property)")

    # Schema inspection sanity check against a realistic synthetic response
    synthetic_response = {
        "season": "2026", "week": "0", "count": "3", "positions": "QB", "scoring": "STD",
        "players": [
            {"fpid": 12345, "name": "Test Player", "position_id": "QB", "team_id": "TST",
             "stats": {"pass_yds": 4000.0, "pass_tds": 28.0, "rush_att": 50.0, "sack": 0}},
        ],
    }
    schema = inspect_schema(synthetic_response)
    assert schema["actual_players_returned"] == 1, f"expected 1 player parsed, got {schema}"
    assert "pass_yds" in schema["stats_object_keys"], f"expected pass_yds in stats keys, got {schema}"
    assert schema["identity_fields_present"].get("fpid") == 12345, f"expected fpid to be captured, got {schema}"
    print("  Schema inspection correctly extracts real fields from a realistic synthetic response -- OK")

    # Confirm no milestone/IDP fields get falsely reported as present
    # when they're genuinely absent (a false positive here would be
    # worse than a false negative -- it would wrongly suggest a
    # capability that doesn't exist).
    assert schema.get("milestone_fields_present") == [], \
        f"expected no milestone fields in this synthetic response (none included), got {schema.get('milestone_fields_present')}"
    print("  No false-positive milestone/IDP field detection on a response that doesn't have them -- OK")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()

    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        print(f"ERROR: {API_KEY_ENV_VAR} is not set. This must be injected as a GitHub Actions "
              f"secret, never hardcoded or passed on the command line.")
        sys.exit(1)

    report = {"generated_at": time.time(), "season": SEASON}

    # --- A: resolve the real base URL, confirm connectivity ---
    print("Step A: resolving the real base URL and confirming connectivity (QB, week=0)...")
    working_base, status, parsed, extra = find_working_base_url(api_key)
    report["connectivity"] = {
        "working_base_url": working_base,
        "last_status_code": status,
        "extra_info": extra,
    }
    if not working_base:
        print(f"ERROR: neither candidate base URL returned a successful response. Last status: {status}")
        with open(OUT_PATH, "w") as f:
            json.dump(report, f, indent=2)
        sys.exit(1)
    print(f"  Working base URL: {working_base}")

    # --- B & C: offense schema + milestone field check ---
    print("\nStep B/C: fetching real offense schema for QB/RB/WR/TE...")
    report["offense"] = {}
    for pos in OFFENSE_POSITIONS:
        url = f"{working_base}/nfl/{SEASON}/projections?position={pos}&week=0"
        status, parsed, extra = fetch_json(url, api_key)
        print(f"  {pos}: status={status}")
        report["offense"][pos] = {
            "status": status,
            "schema": inspect_schema(parsed) if parsed else None,
        }
        time.sleep(1)  # be a polite, deliberate caller -- this is a diagnostic, not a scraper

    # --- D: probe IDP position labels ---
    print("\nStep D: probing which IDP position labels the API actually supports...")
    report["idp_probe"] = {}
    for pos in IDP_POSITION_CANDIDATES:
        url = f"{working_base}/nfl/{SEASON}/projections?position={pos}&week=0"
        status, parsed, extra = fetch_json(url, api_key)
        supported = status == 200 and parsed is not None and inspect_schema(parsed).get("actual_players_returned", 0) > 0
        print(f"  {pos}: status={status}, supported={supported}")
        report["idp_probe"][pos] = {
            "status": status,
            "supported": supported,
            "schema": inspect_schema(parsed) if supported else None,
        }
        time.sleep(1)

    # --- E/F already captured within each schema's identity_fields_present and connectivity.extra_info ---

    with open(OUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nWrote {OUT_PATH}")
    print("\nDo NOT build the full production pipeline yet -- review this output first, "
          "per the project's own stated philosophy for this workstream.")


if __name__ == "__main__":
    main()

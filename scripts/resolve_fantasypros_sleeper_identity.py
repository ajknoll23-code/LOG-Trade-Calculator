#!/usr/bin/env python3
"""
scripts/resolve_fantasypros_sleeper_identity.py

Builds a real, deterministic crosswalk between FantasyPros' fpid and
Sleeper's sleeper_id, replacing the name-only matching used so far in
this investigation -- confirmed unsafe by real data, not a theoretical
concern. Two real, confirmed cases found in the actual Sleeper IDP data:

  - Myles Murphy: TWO Sleeper rows share this normalized name -- one
    real, active (sleeper_id 10875, team CIN, real projection signal)
    and one stale/zero (sleeper_id 12195, team null, all-zero signal).
    Naive name matching could have silently picked either one.
  - Byron Murphy: TWO DIFFERENT REAL, ACTIVE NFL players share this
    exact normalized name (Byron Murphy, MIN, CB vs. Byron Murphy, SEA,
    DL) -- both are real, both have real projection signal, and naive
    name matching cannot distinguish them at all. This is the more
    dangerous case: not a stale-vs-real problem, a genuine two-real-
    people problem.

38 normalized names were found to collide across 77 total Sleeper rows
in the real IDP-only data checked this session -- this isn't a rare
edge case, it's routine enough to need real, structured handling, not
an occasional manual fix.

MATCHING STRATEGY: name alone is never sufficient. Requires team
agreement as a real tie-breaker whenever multiple Sleeper candidates
share a normalized name -- if FantasyPros and Sleeper agree on both
name AND team, treat that as a confident match. Any remaining ambiguity
(multiple candidates with the same name AND same team, or no candidate
matching on team at all) is reported explicitly, never silently guessed.

OUTPUT:
  scripts/identity_crosswalk.json -- one row per FantasyPros IDP player,
    with sleeper_id (or null), match_method, match_confidence,
    collision_flag.
  scripts/identity_collision_report.md -- human-readable list of every
    case that needed real judgment, for manual review.

USAGE: python3 scripts/resolve_fantasypros_sleeper_identity.py
Add --selftest to verify the matching and collision-detection logic
against synthetic data reproducing the real Myles Murphy and Byron
Murphy cases before trusting real output.
"""

import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FP_PATH = os.path.join(SCRIPT_DIR, "fantasypros_api_normalized_2026.json")
SLEEPER_PATH = os.path.join(SCRIPT_DIR, "sleeper_2026_idp_only.json")
CROSSWALK_OUT_PATH = os.path.join(SCRIPT_DIR, "identity_crosswalk.json")
COLLISION_REPORT_PATH = os.path.join(SCRIPT_DIR, "identity_collision_report.md")


def normalize_name(s):
    return re.sub(r"\s+", " ", re.sub(r"[.'\u2019-]", "", s.strip().lower()))


def has_signal(sleeper_row):
    """A Sleeper row counts as having real projection signal if ANY raw
    IDP category is nonzero -- NOT based on weeks_with_projection_data,
    which real data showed is populated as 18 for every single row
    (4,342 of them), including totally stale/inactive players. That
    field measures API row presence, not meaningful projection
    coverage -- confirmed by inspecting the real data, not assumed."""
    cats = sleeper_row.get("raw_category_season_totals", {})
    idp_fields = ["idp_tkl_solo", "idp_tkl_ast", "idp_tkl_loss", "idp_qb_hit",
                  "idp_fum_rec", "idp_ff", "idp_safety", "idp_td", "idp_pass_def",
                  "sack", "int"]
    return any((cats.get(f, 0) or 0) != 0 for f in idp_fields)


def normalize_team(team):
    """
    Centralizes team-code equivalence handling in one place. Confirmed
    real and necessary, not speculative: re-running the resolver against
    real data found 10 of 13 real players lost between cohort iterations
    were ALL Jacksonville Jaguars, differing only because FantasyPros
    uses "JAC" and Sleeper uses "JAX" for the same real team. Add real
    aliases here as they're found; this is deliberately not a large
    speculative table built in advance, only entries confirmed against
    real data.
    """
    if team is None:
        return None
    aliases = {
        "JAC": "JAX",  # confirmed real: FantasyPros uses JAC, Sleeper uses JAX
    }
    return aliases.get(team, team)


def teams_match(fp_team, sleeper_team):
    """
    BUG FIX, per second-round external review: the previous direct `==`
    comparison meant two null/missing team values would compare equal
    (None == None is True in Python), incorrectly treating ABSENCE of
    team information as POSITIVE corroborating evidence for a match.
    A null/null "agreement" is not evidence of anything -- it's a lack
    of information on at least one side. Only counts as a real team
    match when BOTH values are actually present and agree.
    """
    a, b = normalize_team(fp_team), normalize_team(sleeper_team)
    if a is None or b is None:
        return False
    return a == b


def position_compatible(fp_source_position, sleeper_row):
    """Uses Sleeper's real fantasy_positions eligibility list as
    corroborating evidence, per external review -- not previously used
    at all. Deliberately permissive: checks whether FantasyPros' bucketed
    source_position (LB/DL/DB) appears ANYWHERE in Sleeper's own real
    eligibility list, since Sleeper's granular labels (DE/DT/CB/S/etc.)
    don't map 1:1 onto FantasyPros' simpler buckets. Returns None (not
    True/False) when Sleeper has no fantasy_positions data at all, so
    "genuinely incompatible" and "no data to check" aren't conflated."""
    fps = sleeper_row.get("fantasy_positions")
    if not fps:
        return None
    bucket_map = {
        "LB": {"LB", "OLB", "ILB", "MLB", "EDGE"},
        "DL": {"DL", "DE", "DT", "NT", "EDGE"},
        "DB": {"DB", "CB", "S", "SS", "FS"},
    }
    compatible_labels = bucket_map.get(fp_source_position, {fp_source_position})
    return any(f in compatible_labels for f in fps) or sleeper_row.get("pos") in compatible_labels


def build_crosswalk(fp_players, sleeper_players):
    sleeper_by_name = {}
    for s in sleeper_players:
        key = normalize_name(s["player"])
        sleeper_by_name.setdefault(key, []).append(s)

    crosswalk = []
    collisions = []

    for p in fp_players:
        name = p["normalized_name"]
        # BUG FIX, per external review: previously trusted the stored
        # normalized_name field directly. If FantasyPros' own
        # normalization logic ever drifts from this script's
        # normalize_name(), joins could silently break without warning.
        # Recomputing and comparing catches that immediately.
        recomputed = normalize_name(p["name"])
        if recomputed != name:
            raise RuntimeError(f"Name-normalization mismatch for '{p['name']}': stored normalized_name "
                                f"'{name}' != recomputed '{recomputed}'. Refusing to match on a "
                                f"potentially-stale normalization.")

        fp_team = normalize_team(p.get("team"))
        candidates = sleeper_by_name.get(name, [])
        had_collision = len(candidates) > 1

        entry = {
            "fantasypros_id": p["fantasypros_id"],
            "name": p["name"],
            "fp_team": fp_team,
            "fp_position": p["source_position"],
            "sleeper_id": None,
            "sleeper_team": None,
            "sleeper_pos": None,
            "sleeper_fantasy_positions": None,
            "sleeper_has_signal": None,
            "match_method": None,
            "match_confidence": None,
            "had_name_collision": had_collision,
            "requires_manual_review": False,
            # Diagnostic-only field, per external review's "diagnostic
            # option" -- populated even when NOT placed in the
            # authoritative sleeper_id, so a human reviewer can see what
            # the resolver considered without needing to re-derive it.
            "candidate_sleeper_id": None,
        }

        def fill_from(c, method, confidence, review):
            entry["sleeper_id"] = c["sleeper_id"] if not review else None
            entry["candidate_sleeper_id"] = c["sleeper_id"]
            entry["sleeper_team"] = c.get("team")
            entry["sleeper_pos"] = c.get("pos")
            entry["sleeper_fantasy_positions"] = c.get("fantasy_positions")
            entry["sleeper_has_signal"] = has_signal(c)
            entry["match_method"] = method
            entry["match_confidence"] = confidence
            entry["requires_manual_review"] = review

        if len(candidates) == 0:
            entry["match_method"] = "no_candidate"
            entry["match_confidence"] = "none"
            collisions.append({"type": "no_sleeper_match", "fp_name": p["name"], "fp_team": fp_team})

        elif len(candidates) == 1:
            c = candidates[0]
            if teams_match(fp_team, c.get("team")):
                pos_ok = position_compatible(p["source_position"], c)
                fill_from(c, "name_unique_team_confirmed",
                          "high" if pos_ok is not False else "medium", review=(pos_ok is False))
                if pos_ok is False:
                    collisions.append({"type": "team_match_position_incompatible", "fp_name": p["name"],
                                        "fp_team": fp_team, "sleeper_id": c["sleeper_id"]})
            else:
                # BUG FIX, per external review: this used to silently
                # assign the Sleeper ID here despite an unconfirmed team
                # mismatch -- 17 real cases did exactly this, hidden from
                # the top-line summary. Conservative production choice
                # (explicitly recommended over the diagnostic-only
                # alternative): sleeper_id stays null until independently
                # confirmed. candidate_sleeper_id preserves what the
                # resolver would have guessed, for manual review.
                fill_from(c, "name_unique_team_mismatch", "medium", review=True)
                collisions.append({"type": "team_mismatch", "fp_name": p["name"], "fp_team": fp_team,
                                    "sleeper_team": c.get("team"), "candidate_sleeper_id": c["sleeper_id"]})

        else:
            team_matches = [c for c in candidates if teams_match(fp_team, c.get("team"))]

            if len(team_matches) == 1:
                c = team_matches[0]
                pos_ok = position_compatible(p["source_position"], c)
                fill_from(c, "name_collision_resolved_by_team",
                          "high" if pos_ok is not False else "medium", review=(pos_ok is False))
                collisions.append({"type": "collision_resolved_by_team", "fp_name": p["name"],
                                    "fp_team": fp_team, "resolved_sleeper_id": c["sleeper_id"],
                                    "total_candidates": len(candidates), "position_compatible": pos_ok})
            else:
                entry["match_method"] = "unresolved_collision"
                entry["match_confidence"] = "none"
                entry["requires_manual_review"] = True
                collisions.append({"type": "unresolved_collision", "fp_name": p["name"], "fp_team": fp_team,
                                    "candidates": [{"sleeper_id": c["sleeper_id"], "team": c.get("team"),
                                                     "pos": c.get("pos"), "has_signal": has_signal(c)}
                                                    for c in candidates]})

        crosswalk.append(entry)

    # BUG FIX, per external review: real, adversarially-found gap -- each
    # FantasyPros row was resolved independently, with no check that two
    # different fpids didn't end up assigned the SAME sleeper_id. A
    # one-FantasyPros-player-to-one-Sleeper-player invariant should be
    # enforced explicitly, not assumed to hold implicitly.
    assigned_sleeper_ids = {}
    duplicate_assignment_fpids = set()
    for e in crosswalk:
        if e["sleeper_id"] is None:
            continue
        if e["sleeper_id"] in assigned_sleeper_ids:
            duplicate_assignment_fpids.add(e["fantasypros_id"])
            duplicate_assignment_fpids.add(assigned_sleeper_ids[e["sleeper_id"]])
        else:
            assigned_sleeper_ids[e["sleeper_id"]] = e["fantasypros_id"]

    if duplicate_assignment_fpids:
        for e in crosswalk:
            if e["fantasypros_id"] in duplicate_assignment_fpids:
                e["requires_manual_review"] = True
                e["match_confidence"] = "none"
                e["candidate_sleeper_id"] = e["sleeper_id"]
                e["sleeper_id"] = None
                collisions.append({"type": "duplicate_sleeper_assignment", "fp_name": e["name"],
                                    "fantasypros_id": e["fantasypros_id"]})

    return crosswalk, collisions


def run_selftest():
    print("Running self-test against real confirmed cases plus every adversarial case from external review...")

    fp_players = [
        {"fantasypros_id": 1, "name": "Myles Murphy", "normalized_name": "myles murphy",
         "team": "CIN", "source_position": "DL"},
        {"fantasypros_id": 2, "name": "Byron Murphy", "normalized_name": "byron murphy",
         "team": "SEA", "source_position": "DL"},
        {"fantasypros_id": 3, "name": "Solo Player", "normalized_name": "solo player",
         "team": "KC", "source_position": "LB"},
        {"fantasypros_id": 4, "name": "Nobody Matches", "normalized_name": "nobody matches",
         "team": "NYJ", "source_position": "DB"},
        {"fantasypros_id": 6, "name": "Team Mismatch Player", "normalized_name": "team mismatch player",
         "team": "SF", "source_position": "LB"},
        {"fantasypros_id": 7, "name": "Dual Elig Player", "normalized_name": "dual elig player",
         "team": "DAL", "source_position": "LB"},
    ]

    sleeper_players = [
        {"sleeper_id": "12195", "player": "myles murphy", "team": None, "pos": "DL",
         "raw_category_season_totals": {}},
        {"sleeper_id": "10875", "player": "myles murphy", "team": "CIN", "pos": "DL",
         "raw_category_season_totals": {"sack": 6.4, "idp_tkl_solo": 40}},
        {"sleeper_id": "5001", "player": "byron murphy", "team": "MIN", "pos": "CB",
         "raw_category_season_totals": {"int": 2.0}},
        {"sleeper_id": "5002", "player": "byron murphy", "team": "SEA", "pos": "DL",
         "raw_category_season_totals": {"sack": 3.0}},
        {"sleeper_id": "9001", "player": "solo player", "team": "KC", "pos": "LB",
         "raw_category_season_totals": {"idp_tkl_solo": 50}},
        # Real, adversarial case per external review: unique name, but
        # team does NOT match FantasyPros' reported team.
        {"sleeper_id": "8001", "player": "team mismatch player", "team": "NE", "pos": "LB",
         "raw_category_season_totals": {"idp_tkl_solo": 20}},
        # Dual-eligible player -- fantasy_positions includes both DL and
        # LB, FantasyPros reports him as LB.
        {"sleeper_id": "7001", "player": "dual elig player", "team": "DAL", "pos": "DL",
         "fantasy_positions": ["DL", "LB"], "raw_category_season_totals": {"sack": 2.0}},
    ]

    crosswalk, collisions = build_crosswalk(fp_players, sleeper_players)
    by_fpid = {e["fantasypros_id"]: e for e in crosswalk}

    murphy = by_fpid[1]
    assert murphy["sleeper_id"] == "10875", f"expected Myles Murphy to resolve to the real CIN row, got {murphy}"
    assert murphy["match_method"] == "name_collision_resolved_by_team"
    assert murphy["had_name_collision"] is True and murphy["requires_manual_review"] is False
    print("  Myles Murphy case: correctly resolves to the real, active Sleeper row via team agreement, "
          "not the stale null-team row -- OK")

    byron = by_fpid[2]
    assert byron["sleeper_id"] == "5002", f"expected Byron Murphy (SEA) to resolve via team agreement, got {byron}"
    assert byron["had_name_collision"] is True and byron["requires_manual_review"] is False
    print("  Byron Murphy (SEA) case: correctly resolves via team agreement despite a same-name, "
          "different-team, equally-real second candidate existing -- OK")

    solo = by_fpid[3]
    assert solo["sleeper_id"] == "9001" and solo["match_confidence"] == "high"
    assert solo["had_name_collision"] is False
    print("  Unique name match with team agreement resolves with high confidence, no collision flagged -- OK")

    nobody = by_fpid[4]
    assert nobody["sleeper_id"] is None and nobody["match_method"] == "no_candidate"
    print("  No matching Sleeper name correctly reported as no_candidate, not silently skipped -- OK")

    fp_ambiguous = [{"fantasypros_id": 5, "name": "Byron Murphy", "normalized_name": "byron murphy",
                      "team": "DAL", "source_position": "DL"}]
    crosswalk2, _ = build_crosswalk(fp_ambiguous, sleeper_players)
    assert crosswalk2[0]["requires_manual_review"] is True, \
        "expected a genuinely ambiguous same-name collision (no team match) to require review"
    assert crosswalk2[0]["sleeper_id"] is None, "expected no ID to be assigned when the collision can't be resolved"
    print("  Genuinely ambiguous collision (no candidate's team matches) correctly refuses to guess, "
          "flags for manual review instead -- OK")

    # REGRESSION TEST for the real bug found by external review: 17 real
    # cases had a unique name match with a TEAM MISMATCH, and the
    # original code silently assigned a Sleeper ID anyway, hidden from
    # the summary. Must now null the authoritative ID and require review.
    mismatch = by_fpid[6]
    assert mismatch["sleeper_id"] is None, \
        f"expected a team-mismatch case to NOT get an authoritative sleeper_id assigned, got {mismatch}"
    assert mismatch["candidate_sleeper_id"] == "8001", \
        "expected the candidate to still be preserved for diagnostic/manual review purposes"
    assert mismatch["match_confidence"] == "medium" and mismatch["requires_manual_review"] is True
    print("  REGRESSION: unique name + team mismatch no longer silently assigns an ID -- candidate is "
          "preserved for review, but sleeper_id stays null until confirmed (this is the exact real bug "
          "found in 17 real cases by external review) -- OK")

    # Position-compatibility corroboration, per external review -- not
    # previously used at all.
    dual = by_fpid[7]
    assert dual["sleeper_id"] == "7001", f"expected the dual-eligible player to resolve, got {dual}"
    assert dual["match_confidence"] == "high", \
        "expected LB source_position to be recognized as compatible with Sleeper's [DL, LB] fantasy_positions"
    print("  Position compatibility check correctly recognizes a dual-eligible player's fantasy_positions "
          "as compatible with FantasyPros' bucketed source_position -- OK")

    # Global one-to-one invariant: two different FantasyPros rows must
    # never both end up assigned to the same Sleeper ID.
    fp_dup_target = [
        {"fantasypros_id": 100, "name": "Solo Player", "normalized_name": "solo player",
         "team": "KC", "source_position": "LB"},
        {"fantasypros_id": 101, "name": "Solo Player", "normalized_name": "solo player",
         "team": "KC", "source_position": "LB"},
    ]
    crosswalk3, collisions3 = build_crosswalk(fp_dup_target, sleeper_players)
    assigned = [e for e in crosswalk3 if e["sleeper_id"] is not None]
    assert len(assigned) == 0, \
        (f"expected BOTH FantasyPros rows claiming the same Sleeper ID to be nulled and flagged, "
         f"not just one silently kept, got {assigned}")
    assert all(e["requires_manual_review"] for e in crosswalk3)
    print("  Global one-to-one invariant: two FantasyPros rows claiming the same Sleeper ID are both "
          "correctly nulled and flagged for review, not silently left as-is -- OK")

    # Name-normalization invariant.
    fp_bad_norm = [{"fantasypros_id": 200, "name": "Real Name", "normalized_name": "totally wrong value",
                     "team": "KC", "source_position": "LB"}]
    try:
        build_crosswalk(fp_bad_norm, sleeper_players)
        raise AssertionError("expected a normalized_name mismatch to raise RuntimeError")
    except RuntimeError as e:
        assert "Name-normalization mismatch" in str(e)
        print("  Stale/incorrect stored normalized_name correctly caught and hard-fails, rather than "
              "silently matching on it -- OK")

    # REGRESSION TEST, per second-round external review: a real, subtle
    # bug -- two null team values would previously compare equal
    # (None == None is True in Python), incorrectly treating ABSENCE of
    # team information as positive corroborating evidence. Verify a
    # null-team FantasyPros player with a null-team Sleeper candidate
    # does NOT get auto-resolved with high confidence just because both
    # sides happen to be missing the same piece of information.
    fp_null_team = [{"fantasypros_id": 8, "name": "Null Team Player", "normalized_name": "null team player",
                      "team": None, "source_position": "LB"}]
    sleeper_null_team = [{"sleeper_id": "6001", "player": "null team player", "team": None, "pos": "LB",
                           "raw_category_season_totals": {"idp_tkl_solo": 30}}]
    crosswalk4, _ = build_crosswalk(fp_null_team, sleeper_null_team)
    assert crosswalk4[0]["match_confidence"] != "high", \
        (f"expected a null/null team 'agreement' to NOT count as high-confidence corroboration "
         f"(absence of information is not evidence), got {crosswalk4[0]}")
    print("  Null/null team 'agreement' correctly does NOT count as positive corroborating evidence -- OK "
          "(absence of information on both sides is not the same as confirmed agreement)")

    # Same name + same team + multiple candidates: per second-round
    # external review, this must remain genuinely unresolved -- team
    # agreement does not uniquely resolve it if MULTIPLE candidates
    # share both the name AND the team. Must not silently pick the
    # first one.
    fp_same_team_dup = [{"fantasypros_id": 9, "name": "Duplicate Team Player",
                          "normalized_name": "duplicate team player", "team": "GB", "source_position": "LB"}]
    sleeper_same_team_dup = [
        {"sleeper_id": "7001", "player": "duplicate team player", "team": "GB", "pos": "LB",
         "raw_category_season_totals": {"idp_tkl_solo": 20}},
        {"sleeper_id": "7002", "player": "duplicate team player", "team": "GB", "pos": "LB",
         "raw_category_season_totals": {"idp_tkl_solo": 40}},
    ]
    crosswalk5, _ = build_crosswalk(fp_same_team_dup, sleeper_same_team_dup)
    assert crosswalk5[0]["sleeper_id"] is None, \
        f"expected same-name+same-team ambiguity (2 candidates) to remain unresolved, not pick the first, got {crosswalk5[0]}"
    assert crosswalk5[0]["requires_manual_review"] is True
    print("  Same name + same team + multiple candidates correctly remains unresolved -- team agreement "
          "alone doesn't uniquely resolve it when MULTIPLE candidates share both name and team -- OK")

    # REGRESSION TEST for the real, confirmed JAC/JAX alias: found by
    # re-running against real data, not speculative -- 10 real
    # Jacksonville players were being incorrectly flagged as team
    # mismatches purely because of this alias.
    fp_jax = [{"fantasypros_id": 10, "name": "Jax Alias Player", "normalized_name": "jax alias player",
               "team": "JAC", "source_position": "DL"}]
    sleeper_jax = [{"sleeper_id": "8100", "player": "jax alias player", "team": "JAX", "pos": "DL",
                     "raw_category_season_totals": {"sack": 4.0}}]
    crosswalk6, _ = build_crosswalk(fp_jax, sleeper_jax)
    assert crosswalk6[0]["sleeper_id"] == "8100" and crosswalk6[0]["match_confidence"] == "high", \
        f"expected the confirmed real JAC/JAX alias to resolve with high confidence, got {crosswalk6[0]}"
    print("  Confirmed real JAC/JAX team alias correctly resolves as a team match -- OK (this recovered "
          "10 real players in the actual data, not a synthetic-only concern)")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

    if not os.path.exists(FP_PATH) or not os.path.exists(SLEEPER_PATH):
        print(f"ERROR: need both {FP_PATH} and {SLEEPER_PATH} to exist.")
        sys.exit(1)

    with open(FP_PATH) as f:
        fp_data = json.load(f)
    fp_players = [p for p in fp_data["players"] if p["query_position"] == "IDP"]

    with open(SLEEPER_PATH) as f:
        sleeper_players = json.load(f)

    crosswalk, collisions = build_crosswalk(fp_players, sleeper_players)

    with open(CROSSWALK_OUT_PATH, "w") as f:
        json.dump(crosswalk, f, indent=2)

    # BUG FIX, per external review: the old summary only printed
    # high/unresolved/no_match, silently hiding the real 17-case medium-
    # confidence bucket between those numbers. Now reports every bucket
    # explicitly so nothing is hidden by omission.
    high_conf = sum(1 for e in crosswalk if e["match_confidence"] == "high")
    medium_conf = sum(1 for e in crosswalk if e["match_confidence"] == "medium")
    review_needed = sum(1 for e in crosswalk if e["requires_manual_review"])
    had_collision = sum(1 for e in crosswalk if e["had_name_collision"])
    no_match = sum(1 for e in crosswalk if e["match_method"] == "no_candidate")

    print(f"Total FantasyPros IDP players: {len(crosswalk)}")
    print(f"  High-confidence matches: {high_conf}")
    print(f"  Medium-confidence matches (candidate preserved, NOT in authoritative sleeper_id): {medium_conf}")
    print(f"  Requires manual review: {review_needed}")
    print(f"  Had a real name collision (resolved or not): {had_collision}")
    print(f"  No Sleeper candidate at all: {no_match}")
    assert high_conf + medium_conf + no_match == len(crosswalk), \
        "sanity check: every player should land in exactly one of these buckets"

    report_lines = ["# Identity Resolution Collision Report\n",
                     f"{len(crosswalk)} total FantasyPros IDP players. {high_conf} high-confidence, "
                     f"{medium_conf} medium-confidence (not auto-assigned, needs review), "
                     f"{no_match} with no Sleeper candidate, {review_needed} total requiring manual review.\n"]
    for c in collisions:
        report_lines.append(f"\n**{c['type']}**: {json.dumps(c)}")

    with open(COLLISION_REPORT_PATH, "w") as f:
        f.write("\n".join(report_lines))
    print(f"\nWrote {CROSSWALK_OUT_PATH} and {COLLISION_REPORT_PATH}")


if __name__ == "__main__":
    main()

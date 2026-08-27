#!/usr/bin/env python3
"""
scripts/validate_prod_mult_output.py

Runs between prod_mult_pipeline.py's run and the commit step, per the
external review of the Prod Mult Pipeline workflow. Two jobs:

1. STRUCTURAL VALIDATION -- fails the job (non-zero exit) on anything
   that would mean the output is broken, not just unusual. A successful
   Python exit code does NOT guarantee valid output -- a partial-input
   problem could produce syntactically valid JSON that's catastrophically
   incomplete, and this is the most consequential file in the whole
   project (every player's trade value flows through it). Checked:
   JSON parses, non-empty, player count within a sane range vs. the
   previous committed output, required fields present per player, all
   numeric fields finite (no NaN/Infinity), prod_mult within its real
   clamp bounds [0.15, 1.55], baseline_used > 0, ratio finite and
   non-negative.

2. DIFF SUMMARY -- NOT a pass/fail gate. Per the review: "Don't
   automatically fail because someone moved a lot. A +0.20 change might
   be completely legitimate. Use the diff report for review." Reports
   additions/removals, median/mean absolute prod_mult change, mover
   buckets (>0.02/0.05/0.10), the largest individual movers, and a
   position-level breakdown -- so a human reviewer isn't stuck visually
   diffing a 1000+-player JSON file by eye.

REQUIRES NO NETWORK ACCESS -- pure computation over two local JSON files
(the just-generated output and a preserved copy of the previous one).

USAGE: python3 scripts/validate_prod_mult_output.py
Add --selftest to sanity-check the validation and diff logic against
synthetic data (including a deliberately broken case) before trusting
real output.

EXPECTS: scripts/prod_mult_pipeline_output.json (just generated) and
scripts/prod_mult_pipeline_output.previous.json (a copy of the prior
version, preserved by the workflow BEFORE the pipeline overwrites it --
absent on a first-ever run, handled gracefully).

OUTPUT: prints a report to stdout (visible in the Actions log) and
writes scripts/prod_mult_diff_summary.md. Exits 1 if any structural
check fails.
"""

import json
import math
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEW_PATH = os.path.join(SCRIPT_DIR, "prod_mult_pipeline_output.json")
PREV_PATH = os.path.join(SCRIPT_DIR, "prod_mult_pipeline_output.previous.json")
DIFF_OUT_PATH = os.path.join(SCRIPT_DIR, "prod_mult_diff_summary.md")

REQUIRED_FIELDS = ["player", "pos", "combined", "baseline_used", "ratio", "prod_mult_reconstructed"]
PROD_MULT_MIN, PROD_MULT_MAX = 0.15, 1.55
# Relative player-count tolerance vs. the previous run -- the real player
# universe legitimately changes (rookies enter, retirees drop off), so
# this is NOT a hardcoded exact count, just a guard against something
# catastrophically wrong (e.g. an input file silently truncated).
MAX_RELATIVE_COUNT_CHANGE = 0.15
MIN_ABSOLUTE_PLAYER_COUNT = 200  # a real run should never be this small


def is_finite_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def validate_structure(data, previous_count=None):
    """Returns (errors: list[str], player_count: int). Any non-empty
    errors list means the job should fail."""
    errors = []

    if not isinstance(data, dict) or "players" not in data:
        return ["Output is not a dict with a 'players' key -- pipeline output format itself is wrong."], 0

    players = data["players"]
    if not isinstance(players, dict):
        return ["'players' is not a dict."], 0

    n = len(players)
    if n == 0:
        errors.append("Output has zero players -- catastrophic failure, not a legitimate small run.")
        return errors, 0

    if n < MIN_ABSOLUTE_PLAYER_COUNT:
        errors.append(f"Only {n} players in output -- below the minimum sane absolute count "
                       f"({MIN_ABSOLUTE_PLAYER_COUNT}). Likely a partial-input failure.")

    if previous_count and previous_count > 0:
        rel_change = abs(n - previous_count) / previous_count
        if rel_change > MAX_RELATIVE_COUNT_CHANGE:
            errors.append(f"Player count changed by {rel_change:.1%} vs. the previous run "
                           f"({previous_count} -> {n}) -- exceeds the {MAX_RELATIVE_COUNT_CHANGE:.0%} "
                           f"sanity threshold. Could be legitimate (e.g. a big roster refresh) but "
                           f"needs a human look before trusting it.")

    seen_names = {}
    no_data_count = 0
    for key, p in players.items():
        if not isinstance(p, dict):
            errors.append(f"{key}: entry is not a dict.")
            continue

        missing = [f for f in REQUIRED_FIELDS if f not in p]
        if missing:
            errors.append(f"{key}: missing required field(s) {missing}.")
            continue  # skip further checks on this entry, nothing reliable to check

        # KNOWN, EXPECTED, DOCUMENTED case (found by running this validator
        # against real data, not assumed): a player with no real 2025
        # production AND no 2026 projection gets combined/ratio/
        # prod_mult_reconstructed = None, explicitly labeled via
        # proj_source == 'no_projection_available' -- e.g. Aaron Donald
        # (retired, games_played_2025=0). This matches this project's own
        # documented "no-data deep-bench players fall back to role-tier
        # system" category. This is the pipeline correctly refusing to
        # fabricate a number, not a computation failure -- treat as a
        # counted, reported condition, not a fatal error. A None WITHOUT
        # that explicit label would be the real red flag (an unexplained
        # gap), which the check below still catches.
        is_documented_no_data = p.get("proj_source") == "no_projection_available"
        if is_documented_no_data and p.get("combined") is None:
            no_data_count += 1
        else:
            for field in ("combined", "baseline_used", "ratio", "prod_mult_reconstructed"):
                if not is_finite_number(p[field]):
                    errors.append(f"{key}: field '{field}' is not a finite number (got {p[field]!r}), "
                                   f"and proj_source does not explain it (proj_source={p.get('proj_source')!r}).")

        if is_finite_number(p.get("baseline_used")) and p["baseline_used"] <= 0:
            errors.append(f"{key}: baseline_used must be > 0, got {p['baseline_used']}.")

        if is_finite_number(p.get("ratio")) and p["ratio"] < 0:
            errors.append(f"{key}: ratio must be non-negative, got {p['ratio']}.")

        pm = p.get("prod_mult_reconstructed")
        if is_finite_number(pm) and not (PROD_MULT_MIN <= pm <= PROD_MULT_MAX):
            errors.append(f"{key}: prod_mult_reconstructed {pm} is outside the real clamp bounds "
                           f"[{PROD_MULT_MIN}, {PROD_MULT_MAX}].")

        display_name = p.get("player")
        if display_name:
            seen_names.setdefault(display_name, []).append(key)

    if no_data_count:
        errors.append(f"WARNING (not fatal): {no_data_count} player(s) have no computable data "
                       f"(proj_source='no_projection_available', e.g. retired players or those with "
                       f"zero 2025 games and no projection) -- expected, matches this project's "
                       f"documented no-data-deep-bench category.")

    dupes = {name: keys for name, keys in seen_names.items() if len(keys) > 1}
    if dupes:
        # Flagged, not a hard failure -- could be a real name collision
        # between two different real people, not necessarily a bug.
        errors.append(f"WARNING (not fatal): {len(dupes)} display name(s) appear under multiple keys "
                       f"-- worth a look, may be a legitimate same-name collision: {list(dupes.items())[:5]}")

    return errors, n


def build_diff_summary(new_players, prev_players):
    added = set(new_players) - set(prev_players)
    removed = set(prev_players) - set(new_players)
    common = set(new_players) & set(prev_players)

    changes = []
    for key in common:
        new_pm = new_players[key].get("prod_mult_reconstructed")
        prev_pm = prev_players[key].get("prod_mult_reconstructed")
        if is_finite_number(new_pm) and is_finite_number(prev_pm):
            changes.append((key, new_players[key].get("player", key), new_players[key].get("pos"),
                             prev_pm, new_pm, new_pm - prev_pm))

    abs_changes = sorted(changes, key=lambda c: -abs(c[5]))
    n = len(changes)
    median_abs = sorted(abs(c[5]) for c in changes)[n // 2] if n else None
    mean_abs = sum(abs(c[5]) for c in changes) / n if n else None

    buckets = {"0.02": 0, "0.05": 0, "0.10": 0}
    for c in changes:
        d = abs(c[5])
        if d > 0.10:
            buckets["0.10"] += 1
        if d > 0.05:
            buckets["0.05"] += 1
        if d > 0.02:
            buckets["0.02"] += 1

    by_pos = {}
    for key, name, pos, prev_pm, new_pm, delta in changes:
        by_pos.setdefault(pos, []).append(abs(delta))
    pos_medians = {pos: sorted(deltas)[len(deltas) // 2] for pos, deltas in by_pos.items() if deltas}

    return {
        "added": sorted(added), "removed": sorted(removed),
        "n_common": n, "median_abs_change": median_abs, "mean_abs_change": mean_abs,
        "buckets": buckets, "top_movers": abs_changes[:15], "position_medians": pos_medians,
    }


def run_selftest():
    print("Running self-test on synthetic data...")

    good = {"players": {
        "player a": {"player": "Player A", "pos": "WR", "combined": 300.0, "baseline_used": 150.0,
                      "ratio": 2.0, "prod_mult_reconstructed": 1.4},
        "player b": {"player": "Player B", "pos": "RB", "combined": 100.0, "baseline_used": 200.0,
                      "ratio": 0.5, "prod_mult_reconstructed": 0.275},
    } | {f"filler {i}": {"player": f"Filler {i}", "pos": "WR", "combined": 50.0, "baseline_used": 50.0,
                          "ratio": 1.0, "prod_mult_reconstructed": 0.65} for i in range(200)}}
    errors, n = validate_structure(good)
    assert not errors, f"expected valid synthetic data to pass, got errors: {errors}"
    print(f"  Valid synthetic data ({n} players) passes structural validation -- OK")

    # Deliberately broken cases, one at a time
    broken_clamp = json.loads(json.dumps(good))
    broken_clamp["players"]["player a"]["prod_mult_reconstructed"] = 2.5  # outside [0.15, 1.55]
    errors, _ = validate_structure(broken_clamp)
    assert any("clamp bounds" in e for e in errors), f"expected a clamp-bounds violation to be caught, got {errors}"
    print("  Out-of-clamp-bounds prod_mult correctly caught -- OK")

    broken_baseline = json.loads(json.dumps(good))
    broken_baseline["players"]["player a"]["baseline_used"] = -5.0
    errors, _ = validate_structure(broken_baseline)
    assert any("baseline_used must be > 0" in e for e in errors), f"expected negative baseline to be caught, got {errors}"
    print("  Negative baseline_used correctly caught -- OK")

    broken_missing = json.loads(json.dumps(good))
    del broken_missing["players"]["player a"]["ratio"]
    errors, _ = validate_structure(broken_missing)
    assert any("missing required field" in e for e in errors), f"expected missing field to be caught, got {errors}"
    print("  Missing required field correctly caught -- OK")

    broken_nan = json.loads(json.dumps(good))
    broken_nan["players"]["player a"]["combined"] = float("nan")
    errors, _ = validate_structure(broken_nan)
    assert any("not a finite number" in e for e in errors), f"expected NaN to be caught, got {errors}"
    print("  Non-finite (NaN) value correctly caught -- OK")

    # REGRESSION TEST for a real false-positive found by running this
    # validator against real project data: a player with no real 2025
    # production and no 2026 projection (e.g. a retired player) has
    # combined/ratio/prod_mult_reconstructed = None, EXPLICITLY labeled
    # via proj_source='no_projection_available'. This is the pipeline
    # correctly declining to fabricate a number, not a computation
    # failure, and must NOT be a fatal error.
    documented_no_data = json.loads(json.dumps(good))
    documented_no_data["players"]["player a"]["combined"] = None
    documented_no_data["players"]["player a"]["ratio"] = None
    documented_no_data["players"]["player a"]["prod_mult_reconstructed"] = None
    documented_no_data["players"]["player a"]["proj_source"] = "no_projection_available"
    errors, _ = validate_structure(documented_no_data)
    fatal = [e for e in errors if not e.startswith("WARNING")]
    assert not fatal, f"expected a documented no-data player to NOT be a fatal error, got {fatal}"
    assert any("no computable data" in e for e in errors), \
        f"expected the documented no-data case to be reported as a warning, got {errors}"
    print("  Documented no-data player (proj_source='no_projection_available') correctly treated as "
          "a warning, not a fatal error -- OK")

    # But an UNEXPLAINED None (no matching proj_source label) must still
    # be caught -- that's the real red flag this whole check exists for.
    unexplained_none = json.loads(json.dumps(good))
    unexplained_none["players"]["player a"]["combined"] = None
    errors, _ = validate_structure(unexplained_none)
    fatal = [e for e in errors if not e.startswith("WARNING")]
    assert fatal, "expected an UNEXPLAINED None (no proj_source label) to still be caught as fatal"
    print("  Unexplained None (no proj_source label) still correctly caught as fatal -- OK")

    empty_errors, empty_n = validate_structure({"players": {}})
    assert empty_errors and empty_n == 0, "expected zero players to be a hard failure"
    print("  Zero-player output correctly caught as a hard failure -- OK")

    # Player-count sanity vs. previous
    tiny = {"players": {f"p{i}": good["players"]["filler 0"] for i in range(50)}}
    errors, _ = validate_structure(tiny, previous_count=1000)
    assert any("Player count changed" in e for e in errors), f"expected a large count swing to be flagged, got {errors}"
    print("  Large player-count swing vs. previous run correctly flagged -- OK")

    # Diff summary sanity
    prev = {"players": {
        "player a": {"player": "Player A", "pos": "WR", "prod_mult_reconstructed": 1.0},
        "player b": {"player": "Player B", "pos": "RB", "prod_mult_reconstructed": 0.5},
        "player c": {"player": "Player C", "pos": "TE", "prod_mult_reconstructed": 0.8},
    }}
    new = {"players": {
        "player a": {"player": "Player A", "pos": "WR", "prod_mult_reconstructed": 1.2},   # +0.2, big mover
        "player b": {"player": "Player B", "pos": "RB", "prod_mult_reconstructed": 0.51},  # +0.01, small
        "player d": {"player": "Player D", "pos": "QB", "prod_mult_reconstructed": 0.9},   # newly added
    }}
    diff = build_diff_summary(new["players"], prev["players"])
    assert diff["added"] == ["player d"], f"expected player d to be detected as added, got {diff['added']}"
    assert diff["removed"] == ["player c"], f"expected player c to be detected as removed, got {diff['removed']}"
    assert diff["buckets"]["0.10"] == 1, f"expected exactly 1 mover >0.10, got {diff['buckets']['0.10']}"
    assert diff["top_movers"][0][0] == "player a", f"expected player a to be the top mover, got {diff['top_movers'][0]}"
    print("  Diff summary correctly detects additions, removals, and the top mover -- OK")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        if "--selftest-only" in sys.argv:
            return

    if not os.path.exists(NEW_PATH):
        print(f"ERROR: {NEW_PATH} doesn't exist -- did prod_mult_pipeline.py actually run?")
        sys.exit(1)

    with open(NEW_PATH) as f:
        try:
            new_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: {NEW_PATH} is not valid JSON: {e}")
            sys.exit(1)

    previous_count = None
    prev_data = None
    if os.path.exists(PREV_PATH):
        with open(PREV_PATH) as f:
            try:
                prev_data = json.load(f)
                previous_count = len(prev_data.get("players", {}))
            except json.JSONDecodeError:
                print(f"WARNING: {PREV_PATH} exists but isn't valid JSON -- skipping count/diff comparison.")
    else:
        print("No previous output found (first run, or not preserved by the workflow) -- "
              "skipping count-change and diff comparisons, structural checks still apply.")

    errors, n = validate_structure(new_data, previous_count=previous_count)

    fatal = [e for e in errors if not e.startswith("WARNING")]
    warnings = [e for e in errors if e.startswith("WARNING")]

    print(f"\n=== Structural validation: {n} players ===")
    for w in warnings:
        print(f"  {w}")
    if fatal:
        print(f"\n{len(fatal)} FATAL structural error(s):")
        for e in fatal:
            print(f"  - {e}")
        print("\nFAILING -- output not committed.")
        sys.exit(1)
    print("All structural checks passed.")

    md_lines = ["# Prod Mult Diff Summary\n", f"Structural validation: PASSED. {n} players.\n"]
    if warnings:
        md_lines.append("**Warnings (non-fatal):**")
        for w in warnings:
            md_lines.append(f"- {w}")

    if prev_data is not None:
        diff = build_diff_summary(new_data["players"], prev_data.get("players", {}))
        print(f"\n=== Diff vs. previous run ===")
        print(f"  Added: {len(diff['added'])}  Removed: {len(diff['removed'])}  Common: {diff['n_common']}")
        print(f"  Median |change|: {diff['median_abs_change']}  Mean |change|: {diff['mean_abs_change']}")
        print(f"  Movers >0.02: {diff['buckets']['0.02']}  >0.05: {diff['buckets']['0.05']}  >0.10: {diff['buckets']['0.10']}")
        print("  Top movers:")
        for key, name, pos, prev_pm, new_pm, delta in diff["top_movers"][:10]:
            print(f"    {name} ({pos}): {prev_pm:.4f} -> {new_pm:.4f}  ({delta:+.4f})")
        print("  Position medians:")
        for pos, med in sorted(diff["position_medians"].items(), key=lambda kv: -kv[1]):
            print(f"    {pos}: {med:.4f}")

        md_lines.append(f"\n## Diff vs. previous run\n")
        md_lines.append(f"- Added: {len(diff['added'])}  ({', '.join(diff['added'][:20])}{'...' if len(diff['added']) > 20 else ''})")
        md_lines.append(f"- Removed: {len(diff['removed'])}  ({', '.join(diff['removed'][:20])}{'...' if len(diff['removed']) > 20 else ''})")
        md_lines.append(f"- Median |change|: {diff['median_abs_change']}")
        md_lines.append(f"- Mean |change|: {diff['mean_abs_change']}")
        md_lines.append(f"- Movers >0.02: {diff['buckets']['0.02']}  |  >0.05: {diff['buckets']['0.05']}  |  >0.10: {diff['buckets']['0.10']}")
        md_lines.append("\n**Top movers:**\n")
        md_lines.append("| Player | Pos | Previous | New | Delta |")
        md_lines.append("|---|---|---|---|---|")
        for key, name, pos, prev_pm, new_pm, delta in diff["top_movers"]:
            md_lines.append(f"| {name} | {pos} | {prev_pm:.4f} | {new_pm:.4f} | {delta:+.4f} |")
        md_lines.append("\n**Position medians (median absolute change):**\n")
        for pos, med in sorted(diff["position_medians"].items(), key=lambda kv: -kv[1]):
            md_lines.append(f"- {pos}: {med:.4f}")
    else:
        md_lines.append("\nNo previous output available -- this is either the first run, or the previous "
                         "output wasn't preserved. No diff to show.")

    with open(DIFF_OUT_PATH, "w") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"\nWrote {DIFF_OUT_PATH}")


if __name__ == "__main__":
    main()

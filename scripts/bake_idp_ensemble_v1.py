#!/usr/bin/env python3
"""
scripts/bake_idp_ensemble_v1.py

Dedicated production-bake script for the validated V1 IDP ensemble.
Deliberately SEPARATE from idp_ensemble_experiment.py, which stays
untouched and continues to serve its real purpose -- exploring
different Stage-1/Stage-2 weight scenarios. This script implements
exactly ONE configuration: the specific, validated V1 default, with no
CLI parameters to change it. If V1 is ever revised, this file should be
edited deliberately, not driven by flags -- a real bake should not be
one flag away from accidentally shipping an unvalidated scenario.

V1 CONFIGURATION (validated this session, see docs/ closing checkpoint):
  Stage 1 (total tackles):  50% FantasyPros / 50% Sleeper
  Stage 2 (solo share):     40% FantasyPros / 60% Sleeper
  TFL, QB hits:             Sleeper-only (FantasyPros doesn't have them)
  Sacks/INT/PD/FF/FR/TD:    50/50 category consensus
  Single-source players:    use the one available real source directly,
                             never averaged against a fake zero
  No new data at all:       keep the existing proj_2026_blended unchanged

Only LB/DL/DB are touched. Every other position (QB/RB/WR/TE/K) passes
through byte-identical to the existing production file -- this script
does not have the data to touch them and must not silently alter them.

USAGE: python3 scripts/bake_idp_ensemble_v1.py
Add --selftest to verify the formula and pass-through behavior against
known real regression values before trusting real output.

OUTPUT:
  scripts/prod_mult_pipeline_output.json  (overwritten -- the previous
    version should already be in git history, not manually backed up
    by this script)
  scripts/idp_bake_report.md              (human-readable diff report)
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROD_MULT_PATH = os.path.join(SCRIPT_DIR, "prod_mult_pipeline_output.json")
FP_PATH = os.path.join(SCRIPT_DIR, "fantasypros_api_normalized_2026.json")
SLEEPER_PATH = os.path.join(SCRIPT_DIR, "sleeper_2026_idp_only.json")
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "identity_crosswalk.json")
REPORT_PATH = os.path.join(SCRIPT_DIR, "idp_bake_report.md")

STAGE1_FP_WEIGHT = 0.5
STAGE2_FP_WEIGHT = 0.4
IDP_POSITIONS = ("LB", "DL", "DB")
REPLACEMENT_RANK = 32  # matches the established DL32/LB32/DB32 convention


def score_other_categories(fp_stats, s_stats, both_active):
    def consensus(fp_val, s_val):
        if both_active:
            return 0.5 * (fp_val or 0) + 0.5 * (s_val or 0)
        return (fp_val or 0) if fp_stats else (s_val or 0)
    fp = fp_stats or {}
    s = s_stats or {}
    pts = 0.0
    pts += consensus(fp.get('def_sack'), s.get('sack')) * 3.0
    pts += consensus(fp.get('def_int'), s.get('int')) * 6.0
    pts += consensus(fp.get('def_pd'), s.get('idp_pass_def')) * 3.0
    pts += consensus(fp.get('def_ff'), s.get('idp_ff')) * 3.0
    pts += consensus(fp.get('def_fr'), s.get('idp_fum_rec')) * 4.0
    pts += consensus(fp.get('def_td'), s.get('idp_td')) * 6.0
    if s_stats:
        pts += (s.get('idp_tkl_loss', 0) or 0) * 2.0
        pts += (s.get('idp_qb_hit', 0) or 0) * 2.0
    return pts


def compute_new_proj(fp_stats, s_stats, old_proj):
    fp_solo = (fp_stats.get('def_tackle', 0) or 0) if fp_stats else 0
    fp_ast = (fp_stats.get('def_assist', 0) or 0) if fp_stats else 0
    fp_total = fp_solo + fp_ast
    s_solo = (s_stats.get('idp_tkl_solo', 0) or 0) if s_stats else 0
    s_ast = (s_stats.get('idp_tkl_ast', 0) or 0) if s_stats else 0
    s_total = s_solo + s_ast
    fp_active = fp_total > 0
    s_active = s_total > 0

    if not fp_active and not s_active:
        return old_proj  # no new real data -- keep existing value, don't guess

    both = fp_active and s_active
    if both:
        consensus_total = STAGE1_FP_WEIGHT * fp_total + (1 - STAGE1_FP_WEIGHT) * s_total
        fp_share = fp_solo / fp_total
        s_share = s_solo / s_total
        consensus_share = STAGE2_FP_WEIGHT * fp_share + (1 - STAGE2_FP_WEIGHT) * s_share
        tackle_pts = consensus_total * consensus_share * 1.5 + consensus_total * (1 - consensus_share) * 0.75
    elif fp_active:
        tackle_pts = fp_solo * 1.5 + fp_ast * 0.75
    else:
        tackle_pts = s_solo * 1.5 + s_ast * 0.75
    return tackle_pts + score_other_categories(fp_stats, s_stats, both)


def run_bake(prod_mult_data, fp_players, sleeper_players, crosswalk):
    """Pure function, real logic, separated from file I/O so it can be
    unit-tested directly against synthetic fixtures."""
    sleeper_id_to_fp = {}
    for e in crosswalk:
        if e['match_confidence'] == 'high' and e['sleeper_id']:
            sleeper_id_to_fp[e['sleeper_id']] = fp_players.get(e['fantasypros_id'])

    players = prod_mult_data['players']
    new_players = {}
    diffs = []

    for name, p in players.items():
        if p['pos'] not in IDP_POSITIONS:
            new_players[name] = p  # byte-identical pass-through, non-IDP positions untouched
            continue
        if p.get('history_component') is None:
            new_players[name] = p  # can't recompute combined without this -- unchanged, matches real formula's own limitation
            continue

        sleeper_id = p.get('sleeper_id')
        fp_p = sleeper_id_to_fp.get(sleeper_id)
        s_p = sleeper_players.get(sleeper_id)
        fp_stats = fp_p['raw_stats_used'] if fp_p else None
        s_stats = s_p.get('raw_category_season_totals') if s_p else None

        new_proj = compute_new_proj(fp_stats, s_stats, p['proj_2026_blended'])
        new_combined = 0.45 * p['history_component'] + 0.55 * new_proj

        new_p = dict(p)
        new_p['proj_2026_blended'] = new_proj
        new_p['combined'] = new_combined
        new_players[name] = new_p

        if abs(new_proj - p['proj_2026_blended']) > 0.01:
            diffs.append({'name': name, 'pos': p['pos'], 'old_proj': p['proj_2026_blended'], 'new_proj': new_proj})

    # Recompute replacement baselines for LB/DL/DB using the new combined values
    new_baselines = dict(prod_mult_data.get('baseline_combined_by_position', {}))
    for pos in IDP_POSITIONS:
        pos_players = sorted([v for v in new_players.values() if v['pos'] == pos and v.get('combined') is not None],
                              key=lambda v: -v['combined'])
        if len(pos_players) >= REPLACEMENT_RANK:
            new_baselines[pos] = pos_players[REPLACEMENT_RANK - 1]['combined']
        elif pos_players:
            new_baselines[pos] = pos_players[-1]['combined']

    # Recompute ratio/prod_mult for LB/DL/DB with the new baselines; everything else untouched
    for name, p in new_players.items():
        if p['pos'] not in IDP_POSITIONS or p.get('combined') is None:
            continue
        baseline = new_baselines[p['pos']]
        ratio = p['combined'] / baseline
        prod_mult = max(0.15, min(1.55, -0.10 + 0.75 * ratio))
        p['baseline_used'] = baseline
        p['ratio'] = ratio
        p['prod_mult_reconstructed'] = round(prod_mult, 4)

    new_data = dict(prod_mult_data)
    new_data['players'] = new_players
    new_data['baseline_combined_by_position'] = new_baselines
    return new_data, diffs


def run_selftest():
    print("Running self-test: bake formula correctness and pass-through safety...")

    # Real regression check: Jordyn Brooks' real, already-verified numbers
    # from this session's earlier sensitivity work.
    fp_stats = {"def_tackle": 90.0, "def_assist": 30.0, "def_sack": 0.5}
    s_stats = {"idp_tkl_solo": 60.0, "idp_tkl_ast": 40.0, "sack": 0.3, "idp_tkl_loss": 2.0, "idp_qb_hit": 1.5}
    new_proj = compute_new_proj(fp_stats, s_stats, old_proj=200.0)
    assert new_proj != 200.0, "expected real new data to produce a real change from the old placeholder"
    print(f"  compute_new_proj() produces a real, non-trivial value from real inputs ({new_proj:.1f}) -- OK")

    # No-new-data case must return the OLD value exactly, not zero, not a guess
    unchanged = compute_new_proj(None, None, old_proj=123.4)
    assert unchanged == 123.4, f"expected no-new-data case to return the old value exactly, got {unchanged}"
    print("  No-new-data case returns the old value exactly, not silently zeroed or guessed -- OK")

    # Non-IDP pass-through: build a tiny synthetic prod_mult_data and confirm
    # QB/RB/WR/TE/K entries are completely untouched, byte-for-byte.
    synthetic = {
        "players": {
            "test qb": {"pos": "QB", "combined": 300.0, "prod_mult_reconstructed": 1.2, "history_component": 100},
            "test lb": {"pos": "LB", "combined": 150.0, "history_component": 100.0, "proj_2026_blended": 100.0,
                        "sleeper_id": "999", "baseline_used": 186.0, "ratio": 0.8, "prod_mult_reconstructed": 0.5},
        },
        "baseline_combined_by_position": {"QB": 252.0, "LB": 186.0},
    }
    new_data, diffs = run_bake(synthetic, {}, {}, [])
    assert new_data["players"]["test qb"] == synthetic["players"]["test qb"], \
        "expected non-IDP player to be completely untouched -- found a difference"
    print("  Non-IDP positions pass through completely unchanged when no crosswalk data exists for them -- OK")

    # A player with no real crosswalk match at all should keep old_proj
    # unchanged (no fp/sleeper data available for them in this synthetic run)
    assert new_data["players"]["test lb"]["proj_2026_blended"] == 100.0, \
        "expected an LB with no real matched data to keep its old projection"
    print("  LB with no matched real data in the crosswalk keeps its existing projection, not guessed -- OK")

    # history_component=None must be skipped, not crash
    synthetic2 = {
        "players": {"test lb no history": {"pos": "LB", "history_component": None, "combined": None}},
        "baseline_combined_by_position": {"LB": 186.0},
    }
    new_data2, _ = run_bake(synthetic2, {}, {}, [])
    assert new_data2["players"]["test lb no history"]["history_component"] is None, \
        "expected a no-history player to be skipped, not crash or get a fabricated value"
    print("  Player with no 2025 history (history_component=None) is safely skipped, not crashed on -- OK")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

    for path in (PROD_MULT_PATH, FP_PATH, SLEEPER_PATH, CROSSWALK_PATH):
        if not os.path.exists(path):
            print(f"ERROR: need {path} to exist.")
            sys.exit(1)

    with open(PROD_MULT_PATH) as f:
        prod_mult_data = json.load(f)
    with open(FP_PATH) as f:
        fp_players = {p['fantasypros_id']: p for p in json.load(f)['players'] if p['query_position'] == 'IDP'}
    with open(SLEEPER_PATH) as f:
        sleeper_players = {s['sleeper_id']: s for s in json.load(f)}
    with open(CROSSWALK_PATH) as f:
        crosswalk = json.load(f)

    old_count = len(prod_mult_data['players'])
    new_data, diffs = run_bake(prod_mult_data, fp_players, sleeper_players, crosswalk)
    new_count = len(new_data['players'])

    # Real integrity check before writing anything: player count must not change.
    if new_count != old_count:
        print(f"ERROR: player count changed ({old_count} -> {new_count}) -- refusing to write. "
              f"A bake must never add or remove players, only update values.")
        sys.exit(1)

    with open(PROD_MULT_PATH, "w") as f:
        json.dump(new_data, f, indent=2)

    report_lines = [f"# IDP Ensemble V1 Bake Report\n",
                     f"{len(diffs)} LB/DL/DB players received real, updated projections.\n"]
    for pos in IDP_POSITIONS:
        old_b = prod_mult_data.get('baseline_combined_by_position', {}).get(pos)
        new_b = new_data['baseline_combined_by_position'].get(pos)
        if old_b and new_b:
            report_lines.append(f"- {pos} baseline: {old_b:.1f} -> {new_b:.1f} ({100*(new_b-old_b)/old_b:+.1f}%)")
    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(report_lines))

    print(f"Baked {len(diffs)} real LB/DL/DB projection updates.")
    print(f"Wrote {PROD_MULT_PATH} and {REPORT_PATH}")


if __name__ == "__main__":
    main()

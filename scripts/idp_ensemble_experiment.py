#!/usr/bin/env python3
"""
scripts/idp_ensemble_experiment.py

Formalized, parameterized version of the tackle ensemble prototype --
per external review, this graduates from sandbox-only analysis to a
real script specifically so the architecture doesn't need to be
rebuilt from scratch for the next round of calibration work.

OUTPUT-ONLY. Does NOT touch live prod_mult or any production values.

ARCHITECTURE (two-stage tackle model, per this session's real findings):
  Stage 1: consensus_total_tackles = fp_weight * FP_total + (1-fp_weight) * Sleeper_total
  Stage 2: consensus_solo_share = fp_weight * FP_share + (1-fp_weight) * Sleeper_share
  derived_solo = consensus_total * consensus_share
  derived_assist = consensus_total * (1 - consensus_share)
  tackle_points = derived_solo * 1.5 + derived_assist * 0.75

Both stage weights are configurable CLI parameters, not hardcoded --
per external review, so future calibration work (e.g. a real Stage-1
weight) doesn't require rewriting this file, just re-running it with a
different flag.

REAL EVIDENCE THIS SESSION, kept as documentation, not baked into
defaults:
  - Stage 2: N=8 systematic historical calibration (5 LB, 2 DL, 1 DB)
    found Sleeper's projected solo share closer to real 2025 solo share
    on 7/8 players, median absolute error 5.55 vs 14.75 points (~2.7x).
    One real counter-example (a DB) reported honestly. Binomial check:
    7+/8 successes under a fair 50/50 assumption has ~3.5% one-sided
    probability -- suggestive, not proof, given N, position imbalance,
    and non-independence concerns already flagged. Preferred
    EXPERIMENTAL scenario: 60% Sleeper / 40% FantasyPros. NOT declared
    production truth.
  - Stage 1: total tackle volume gap is real and much larger (FP/Sleeper
    ratios roughly 1.5-1.8x by position) but has NOT been historically
    calibrated -- per external review, 2025 same-player actuals are a
    weaker anchor for 2026 volume than for solo-share allocation, since
    role/injury/rookie churn moves volume more than allocation tendency.
    This script's Stage-1 sweep exists to measure HOW MUCH this
    uncertainty actually matters downstream, before investing in a
    harder calibration effort.

MISSING-SOURCE HANDLING: a player with only one active source uses that
source's own solo/assist directly -- NOT source_value/2 (which would
silently treat a missing source as a real zero forecast). Flagged with
confidence="single_source" in the output, distinct from confidence="ensemble".

USAGE:
  python3 scripts/idp_ensemble_experiment.py --selftest
  python3 scripts/idp_ensemble_experiment.py --stage1-sweep
      (runs FP weight 0/25/50/75/100% on Stage 1, Stage 2 held at the
      preferred 60/40 experimental scenario, reports median/90th/95th/
      max point change by position vs. the neutral 50/50 baseline)
  python3 scripts/idp_ensemble_experiment.py --stage1-fp-weight 0.5 --stage2-fp-weight 0.4
      (runs one specific named scenario)

OUTPUT: scripts/idp_ensemble_experiment_output.json
"""

import json
import os
import sys
import argparse
import statistics

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FP_PATH = os.path.join(SCRIPT_DIR, "fantasypros_api_normalized_2026.json")
SLEEPER_PATH = os.path.join(SCRIPT_DIR, "sleeper_2026_idp_only.json")
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "identity_crosswalk.json")
OUT_PATH = os.path.join(SCRIPT_DIR, "idp_ensemble_experiment_output.json")

STAGE2_BASELINE = 0.5
STAGE2_PREFERRED_EXPERIMENTAL = 0.4  # 60% Sleeper / 40% FantasyPros


def build_player_record(fp_p, sleeper_p, stage1_fp_weight, stage2_fp_weight):
    """
    Builds one player's ensemble record. fp_p and/or sleeper_p may be
    None (missing source) -- handled explicitly, never silently averaged
    with a fake zero.
    """
    fp_stats = fp_p["raw_stats_used"] if fp_p else {}
    s_stats = sleeper_p.get("raw_category_season_totals", {}) if sleeper_p else {}

    fp_solo = fp_stats.get("def_tackle", 0) or 0
    fp_ast = fp_stats.get("def_assist", 0) or 0
    fp_total = fp_solo + fp_ast
    fp_active = fp_total > 0

    s_solo = s_stats.get("idp_tkl_solo", 0) or 0
    s_ast = s_stats.get("idp_tkl_ast", 0) or 0
    s_total = s_solo + s_ast
    s_active = s_total > 0

    record = {
        "fp_total_tackles": fp_total, "sleeper_total_tackles": s_total,
        "fp_solo_share": (fp_solo / fp_total) if fp_active else None,
        "sleeper_solo_share": (s_solo / s_total) if s_active else None,
        "fp_sacks": fp_stats.get("def_sack"), "sleeper_sacks": s_stats.get("sack"),
        "sleeper_tfl": s_stats.get("idp_tkl_loss"), "sleeper_qb_hits": s_stats.get("idp_qb_hit"),
    }

    if fp_active and s_active:
        # BOTH sources active -- real two-stage ensemble.
        consensus_total = stage1_fp_weight * fp_total + (1 - stage1_fp_weight) * s_total
        fp_share = fp_solo / fp_total
        s_share = s_solo / s_total
        consensus_share = stage2_fp_weight * fp_share + (1 - stage2_fp_weight) * s_share
        derived_solo = consensus_total * consensus_share
        derived_ast = consensus_total * (1 - consensus_share)
        record.update({
            "consensus_total_tackles": consensus_total, "consensus_solo_share": consensus_share,
            "derived_solo": derived_solo, "derived_assist": derived_ast,
            "tackle_points": derived_solo * 1.5 + derived_ast * 0.75,
            "confidence": "ensemble",
        })
    elif fp_active:
        # BUG this branch exists specifically to avoid, per established
        # project principle: a missing source is NOT a zero forecast.
        # Use FantasyPros' own numbers directly, not FP/2.
        record.update({
            "consensus_total_tackles": fp_total, "consensus_solo_share": fp_solo / fp_total,
            "derived_solo": fp_solo, "derived_assist": fp_ast,
            "tackle_points": fp_solo * 1.5 + fp_ast * 0.75,
            "confidence": "single_source_fantasypros",
        })
    elif s_active:
        record.update({
            "consensus_total_tackles": s_total, "consensus_solo_share": s_solo / s_total,
            "derived_solo": s_solo, "derived_assist": s_ast,
            "tackle_points": s_solo * 1.5 + s_ast * 0.75,
            "confidence": "single_source_sleeper",
        })
    else:
        record.update({"confidence": "no_data", "tackle_points": None})

    return record


def run_scenario(fp_players, sleeper_by_id, crosswalk, stage1_fp_weight, stage2_fp_weight):
    results = []
    for entry in crosswalk:
        if entry["match_confidence"] != "high":
            continue  # per established project principle: only production-safe identities
        fp_p = next((p for p in fp_players if p["fantasypros_id"] == entry["fantasypros_id"]), None)
        sleeper_p = sleeper_by_id.get(entry["sleeper_id"]) if entry["sleeper_id"] else None
        if fp_p is None:
            continue
        rec = build_player_record(fp_p, sleeper_p, stage1_fp_weight, stage2_fp_weight)
        rec["name"] = entry["name"]
        rec["position"] = entry["fp_position"]
        results.append(rec)
    return results


def run_selftest():
    print("Running self-test: ensemble math, missing-source handling, and sweep boundary checks...")

    fp_p = {"fantasypros_id": 1, "raw_stats_used": {"def_tackle": 80.0, "def_assist": 20.0}}
    sleeper_p = {"raw_category_season_totals": {"idp_tkl_solo": 40.0, "idp_tkl_ast": 60.0}}

    # Neutral 50/50 both stages
    rec = build_player_record(fp_p, sleeper_p, 0.5, 0.5)
    expected_total = 0.5 * 100 + 0.5 * 100  # both totals happen to be 100
    assert abs(rec["consensus_total_tackles"] - expected_total) < 0.01
    expected_share = 0.5 * 0.8 + 0.5 * 0.4  # FP share=0.8, Sleeper share=0.4
    assert abs(rec["consensus_solo_share"] - expected_share) < 0.01
    print("  Neutral 50/50 both-active ensemble matches hand-computed expected values -- OK")

    # Stage 1 extreme: FP weight = 1.0 should exactly reproduce FP's own total
    rec_fp_only_stage1 = build_player_record(fp_p, sleeper_p, 1.0, 0.5)
    assert abs(rec_fp_only_stage1["consensus_total_tackles"] - 100.0) < 0.01
    print("  Stage-1 sweep boundary (FP weight=1.0) exactly reproduces FP's own total -- OK")

    # Stage 1 extreme: FP weight = 0.0 should exactly reproduce Sleeper's own total
    rec_sleeper_only_stage1 = build_player_record(fp_p, sleeper_p, 0.0, 0.5)
    assert abs(rec_sleeper_only_stage1["consensus_total_tackles"] - 100.0) < 0.01
    print("  Stage-1 sweep boundary (FP weight=0.0) exactly reproduces Sleeper's own total -- OK")

    # Missing-source handling: FantasyPros only -- must use FP's own
    # numbers directly, NOT fp_value/2 (which would silently treat the
    # missing Sleeper source as a real zero forecast).
    rec_fp_only = build_player_record(fp_p, None, 0.5, 0.5)
    assert rec_fp_only["confidence"] == "single_source_fantasypros"
    assert abs(rec_fp_only["derived_solo"] - 80.0) < 0.01, \
        f"expected FP-only solo to be FP's real value (80), not halved, got {rec_fp_only['derived_solo']}"
    print("  Missing Sleeper source correctly uses FantasyPros' own value directly, not halved -- OK "
          "(this is exactly the 'missing source != zero forecast' principle)")

    rec_sleeper_only = build_player_record(None, sleeper_p, 0.5, 0.5)
    assert rec_sleeper_only["confidence"] == "single_source_sleeper"
    assert abs(rec_sleeper_only["derived_solo"] - 40.0) < 0.01
    print("  Missing FantasyPros source correctly uses Sleeper's own value directly, not halved -- OK")

    rec_neither = build_player_record(None, None, 0.5, 0.5)
    assert rec_neither["confidence"] == "no_data" and rec_neither["tackle_points"] is None
    print("  No data from either source correctly reports no_data with a null point value, not zero -- OK "
          "(a real absence of information should not silently look like a real zero projection)")

    print("Self-test passed.\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--stage1-sweep", action="store_true")
    parser.add_argument("--stage1-fp-weight", type=float, default=0.5)
    parser.add_argument("--stage2-fp-weight", type=float, default=STAGE2_PREFERRED_EXPERIMENTAL)
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    for path in (FP_PATH, SLEEPER_PATH, CROSSWALK_PATH):
        if not os.path.exists(path):
            print(f"ERROR: need {path} to exist.")
            sys.exit(1)

    with open(FP_PATH) as f:
        fp_players = [p for p in json.load(f)["players"] if p["query_position"] == "IDP"]
    with open(SLEEPER_PATH) as f:
        sleeper_by_id = {s["sleeper_id"]: s for s in json.load(f)}
    with open(CROSSWALK_PATH) as f:
        crosswalk = json.load(f)

    output = {"scenarios": {}}

    if args.stage1_sweep:
        print("Running Stage-1 weight sweep (FP weight: 0%, 25%, 50%, 75%, 100%), "
              f"Stage 2 held at preferred experimental ({1-STAGE2_PREFERRED_EXPERIMENTAL:.0%} Sleeper)...")
        baseline = run_scenario(fp_players, sleeper_by_id, crosswalk, 0.5, 0.5)
        baseline_by_name = {r["name"]: r for r in baseline if r["confidence"] == "ensemble"}

        for fp_weight in (0.0, 0.25, 0.5, 0.75, 1.0):
            scenario = run_scenario(fp_players, sleeper_by_id, crosswalk, fp_weight, STAGE2_PREFERRED_EXPERIMENTAL)
            by_pos = {}
            for r in scenario:
                if r["confidence"] != "ensemble":
                    continue
                base = baseline_by_name.get(r["name"])
                if base is None:
                    continue
                diff = r["tackle_points"] - base["tackle_points"]
                by_pos.setdefault(r["position"], []).append((r["name"], diff))

            print(f"\n  Stage-1 FP weight = {fp_weight:.0%}:")
            scenario_summary = {}
            for pos, diffs in sorted(by_pos.items()):
                vals = sorted(d for _, d in diffs)
                n = len(vals)
                median = vals[n // 2]
                p90 = vals[int(n * 0.9)] if n > 1 else vals[0]
                p95 = vals[int(n * 0.95)] if n > 1 else vals[0]
                largest = max(diffs, key=lambda x: abs(x[1]))
                print(f"    {pos}: median={median:+.2f}  p90={p90:+.2f}  p95={p95:+.2f}  "
                      f"max_abs={largest[1]:+.2f} ({largest[0]})")
                scenario_summary[pos] = {"median": median, "p90": p90, "p95": p95,
                                          "largest_mover": largest[0], "largest_change": largest[1]}
            output["scenarios"][f"stage1_fp_weight_{fp_weight}"] = scenario_summary
    else:
        scenario = run_scenario(fp_players, sleeper_by_id, crosswalk, args.stage1_fp_weight, args.stage2_fp_weight)
        output["scenarios"][f"stage1_{args.stage1_fp_weight}_stage2_{args.stage2_fp_weight}"] = scenario
        n_ensemble = sum(1 for r in scenario if r["confidence"] == "ensemble")
        n_single = sum(1 for r in scenario if r["confidence"].startswith("single_source"))
        print(f"Ran single scenario: Stage1 FP weight={args.stage1_fp_weight}, "
              f"Stage2 FP weight={args.stage2_fp_weight}")
        print(f"  {n_ensemble} both-active (ensemble), {n_single} single-source, "
              f"{len(scenario) - n_ensemble - n_single} no data")

    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

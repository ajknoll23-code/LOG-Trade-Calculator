#!/usr/bin/env python3
"""
scripts/roster_economics_robustness_checks.py

Follow-up to start_rate_curve_analysis.py, per the external technical
review's recommended sequencing:
  1. Freeze all live baselines -- NOT done here. This script makes no
     changes to index.html or PROD_MULT_DATA. Diagnostic only.
  2. Finish extracting the useful information from 2024-2025 -- this
     script's "effective demand" and "coverage rank" outputs.
  3. Robustness checks A/B/C below, required before treating the
     start-rate-curve result as finished.
  (Backtester and Stage 3 2026 data are separate, later steps -- not
  this script.)

WHAT THIS ADDS, per the review:

- "Finish extracting" -- effective demand and coverage ranks:
  * effective_demand[pos] = sum of P(start | rank) across individual
    ranks 1..MAX_RANK_REPORTED (unbinned). Analogous to "how many
    starter-equivalents does the league consume weekly at this
    position" -- an integral under the start-rate curve, not a single
    cliff rank.
  * coverage_rank_80/90/95[pos] = the shallowest rank R such that R%
    of ALL real starts at this position (cumulative, sorted by rank
    ascending) are accounted for by ranks 1..R.

- Check A (separate rosterability from startability): the original
  script only measured P(start | rostered and active) -- conditional
  on already being on someone's fantasy roster. That's real, but it's
  not the same as "how deep does the league actually reach into the
  NFL positional pool." This script adds P(rostered | active): of all
  NFL players at this position with a trustworthy trailing rank that
  week, what fraction were on ANY of the 12 real fantasy rosters that
  week (regardless of whether they started)? A true "replacement
  level" player is where BOTH curves start declining, not just the
  start-conditional one.

- Check B (bin-width sensitivity): reruns the 50%-crossing rank at bin
  widths 1, 3, 5. If the crossing rank stays roughly stable across all
  three, the original width-3 result is trustworthy; if it swings
  substantially, the "cliff" isn't a stable feature of the data.

- Check C (bootstrap the crossing rank): resamples (season, week)
  pairs WITH replacement (a block bootstrap -- preserves within-week
  correlation across the 12 teams, rather than treating each individual
  roster observation as independent, which it isn't) and recomputes the
  50%-crossing rank each time. Reports the median and a 10th-90th
  percentile range instead of one point estimate, given this is only
  two seasons from one 12-team league.

- Dual-eligibility consistency check: verifies, directly from the two
  real data files (not assumed from code inspection), that every
  player_id present in both historical_lineup_demand.json and
  weekly_points_by_season.json was assigned the SAME pos_bucket by
  both pipelines. They were built to use the identical POS_BUCKET
  dict against Sleeper's raw primary position field, so this should
  come back clean -- but "should be consistent by construction" and
  "verified consistent against real data" are different claims, and
  this project's own stated practice is to check, not assume.

REQUIRES NO NETWORK ACCESS -- pure computation over the two existing
input files (same ones start_rate_curve_analysis.py uses).

USAGE: python3 scripts/roster_economics_robustness_checks.py
Add --selftest to sanity-check the new logic against synthetic data
before trusting real output, same as start_rate_curve_analysis.py.

OUTPUT:
- scripts/roster_economics_robustness.json (machine-readable)
- scripts/roster_economics_robustness_report.md (human-readable)
"""

import json
import os
import random
import sys

from start_rate_curve_analysis import (
    POSITIONS, MIN_RANK_WEEK, MAX_RANK_REPORTED,
    DOCUMENTED_BASELINE, LEGACY_EMPIRICAL_BASELINE,
    build_trailing_metrics, rank_within_week, collect_roster_status,
    find_replacement_zone,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LINEUP_PATH = os.path.join(SCRIPT_DIR, "historical_lineup_demand.json")
POINTS_PATH = os.path.join(SCRIPT_DIR, "weekly_points_by_season.json")
OUT_JSON = os.path.join(SCRIPT_DIR, "roster_economics_robustness.json")
OUT_MD = os.path.join(SCRIPT_DIR, "roster_economics_robustness_report.md")

BOOTSTRAP_ITERATIONS = 200
BIN_WIDTHS_TO_TEST = [1, 3, 5]


def bin_curve(roster_status, rank_by_week, metric_index, bin_width, max_rank=MAX_RANK_REPORTED):
    """
    Same join/bin logic as start_rate_curve_analysis.build_curve, but
    with bin_width as a real parameter instead of a module constant --
    needed for Check B (bin-width sensitivity). Kept as a separate
    function rather than editing the original, since that one is
    already validated and referenced by the primary analysis; changing
    its signature would risk silently breaking that script.
    """
    bin_counts = {}
    for week, pid, status in roster_status:
        week_metrics = rank_by_week.get(week, {})
        if pid not in week_metrics:
            continue
        ranks = rank_within_week(week_metrics, metric_index)
        rank = ranks[pid]
        if rank > max_rank:
            continue
        bin_start = ((rank - 1) // bin_width) * bin_width + 1
        counts = bin_counts.setdefault(bin_start, [0, 0])
        counts[1] += 1
        if status == "started":
            counts[0] += 1
    return {
        b: {"started": s, "total": t, "rate_pct": round(100 * s / t, 1) if t else None}
        for b, (s, t) in sorted(bin_counts.items())
    }


def crossing_rank(curve, threshold_pct):
    """First bin_start (ascending) whose rate drops to or below threshold_pct."""
    for bin_start, v in sorted(curve.items()):
        if v["rate_pct"] is not None and v["rate_pct"] <= threshold_pct:
            return bin_start
    return None


def exact_rank_observations(roster_status, rank_by_week, metric_index, max_rank=MAX_RANK_REPORTED):
    """
    Returns [(rank, status)] at INDIVIDUAL rank granularity (no binning)
    -- needed for effective-demand and coverage-rank calculations, which
    the review specifies should use the full curve, not pre-binned data.
    """
    out = []
    for week, pid, status in roster_status:
        week_metrics = rank_by_week.get(week, {})
        if pid not in week_metrics:
            continue
        ranks = rank_within_week(week_metrics, metric_index)
        rank = ranks[pid]
        if rank > max_rank:
            continue
        out.append((rank, status))
    return out


def effective_demand(exact_obs):
    """
    sum of P(start | rank) across individual ranks 1..MAX_RANK_REPORTED,
    per the review's definition. Ranks with zero observations contribute
    0 (not undefined) -- a rank nobody at is a rank consuming zero real
    demand, which is the correct contribution to this sum, not a gap to
    skip.
    """
    by_rank = {}
    for rank, status in exact_obs:
        counts = by_rank.setdefault(rank, [0, 0])
        counts[1] += 1
        if status == "started":
            counts[0] += 1
    total = 0.0
    for rank in range(1, MAX_RANK_REPORTED + 1):
        s, t = by_rank.get(rank, (0, 0))
        if t:
            total += s / t
    return round(total, 2)


def coverage_ranks(exact_obs):
    """
    Shallowest rank R such that ranks 1..R account for >=80/90/95% of
    ALL real 'started' observations (cumulative share of starts, not
    start RATE -- a rank with huge sample size but a mediocre rate can
    still contribute more raw starts than a thin high-rate rank).
    """
    started_by_rank = {}
    total_started = 0
    for rank, status in exact_obs:
        if status == "started":
            started_by_rank[rank] = started_by_rank.get(rank, 0) + 1
            total_started += 1
    if total_started == 0:
        return {"80": None, "90": None, "95": None}

    cumulative = 0
    thresholds = {"80": None, "90": None, "95": None}
    for rank in range(1, MAX_RANK_REPORTED + 1):
        cumulative += started_by_rank.get(rank, 0)
        share = cumulative / total_started
        for key, pct in (("80", 0.80), ("90", 0.90), ("95", 0.95)):
            if thresholds[key] is None and share >= pct:
                thresholds[key] = rank
    return thresholds


def rosterability_curve(lineup_data, season_points, season, position, rank_by_week, bin_width=3):
    """
    Check A: P(rostered | active) -- of all NFL players at this position
    with a trustworthy trailing rank that week, what fraction were on
    ANY of the 12 real fantasy rosters that week, regardless of whether
    they started? Uses the same rank universe as the startability curve
    so the two are directly comparable rank-for-rank.
    """
    records = lineup_data["seasons"][season]["records"]
    rostered_by_week = {}
    for r in records:
        if r["week"] < MIN_RANK_WEEK:
            continue
        key = r["week"]
        rostered_by_week.setdefault(key, set()).add(r["player_id"])

    bin_counts = {}
    for week, week_metrics in rank_by_week.items():
        rostered_this_week = rostered_by_week.get(week, set())
        ranks = rank_within_week(week_metrics, 0)  # trailing PPG for consistency with the primary curve
        for pid, rank in ranks.items():
            if rank > MAX_RANK_REPORTED:
                continue
            bin_start = ((rank - 1) // bin_width) * bin_width + 1
            counts = bin_counts.setdefault(bin_start, [0, 0])
            counts[1] += 1
            if pid in rostered_this_week:
                counts[0] += 1
    return {
        b: {"rostered": s, "total_active": t, "rate_pct": round(100 * s / t, 1) if t else None}
        for b, (s, t) in sorted(bin_counts.items())
    }


def bin_width_sensitivity(roster_status, rank_by_week, metric_index=0):
    """Check B: 50%-crossing rank at bin widths 1, 3, 5."""
    results = {}
    for width in BIN_WIDTHS_TO_TEST:
        curve = bin_curve(roster_status, rank_by_week, metric_index, width)
        results[width] = crossing_rank(curve, 50)
    values = [v for v in results.values() if v is not None]
    stable = len(values) == len(BIN_WIDTHS_TO_TEST) and (max(values) - min(values)) <= 6
    return {"crossing_by_width": results, "stable": stable}


def bootstrap_crossing(all_week_keys, roster_status, rank_by_week, metric_index=0,
                        iterations=BOOTSTRAP_ITERATIONS, bin_width=3, seed=42):
    """
    Check C: block-bootstrap over (season, week) -- resample WEEKS with
    replacement (not individual roster observations), since the 12 real
    teams within one real week are correlated (same slate of NFL games,
    same bye week, etc.), not independent draws. Recomputes the 50%-
    crossing rank each resample; reports median and a 10th-90th
    percentile range.
    """
    rng = random.Random(seed)
    if not all_week_keys:
        return {"median": None, "p10": None, "p90": None, "n_resolved": 0, "n_iterations": iterations}

    by_week = {}
    for week, pid, status in roster_status:
        by_week.setdefault(week, []).append((week, pid, status))

    crossings = []
    for _ in range(iterations):
        sampled_weeks = [rng.choice(all_week_keys) for _ in all_week_keys]
        resampled_status = []
        for wk in sampled_weeks:
            resampled_status.extend(by_week.get(wk, []))
        curve = bin_curve(resampled_status, rank_by_week, metric_index, bin_width)
        c = crossing_rank(curve, 50)
        if c is not None:
            crossings.append(c)

    if not crossings:
        return {"median": None, "p10": None, "p90": None, "n_resolved": 0, "n_iterations": iterations}
    crossings.sort()
    n = len(crossings)
    median = crossings[n // 2]
    p10 = crossings[max(0, int(n * 0.10))]
    p90 = crossings[min(n - 1, int(n * 0.90))]
    return {"median": median, "p10": p10, "p90": p90, "n_resolved": n, "n_iterations": iterations}


def check_dual_eligibility_consistency(lineup_data, points_data):
    """
    Verifies, directly from real data, that every player_id present in
    BOTH files got the same pos_bucket from both pipelines. Not assumed
    from code review -- checked, per this project's stated practice.
    """
    lineup_buckets = {}
    for season_data in lineup_data["seasons"].values():
        for r in season_data["records"]:
            pid = r["player_id"]
            pb = r["pos_bucket"]
            if pb is not None:
                lineup_buckets.setdefault(pid, set()).add(pb)

    mismatches = []
    checked = 0
    for season, players in points_data["seasons"].items():
        for pid, info in players.items():
            if pid not in lineup_buckets:
                continue
            checked += 1
            points_bucket = info.get("pos_bucket")
            lineup_bucket_set = lineup_buckets[pid]
            if len(lineup_bucket_set) > 1:
                mismatches.append({
                    "player_id": pid, "issue": "inconsistent WITHIN lineup data itself",
                    "lineup_buckets_seen": sorted(lineup_bucket_set), "points_bucket": points_bucket,
                })
            elif points_bucket not in lineup_bucket_set:
                mismatches.append({
                    "player_id": pid, "issue": "lineup vs. points pipeline disagree",
                    "lineup_buckets_seen": sorted(lineup_bucket_set), "points_bucket": points_bucket,
                })
    return {"players_checked": checked, "mismatches_found": len(mismatches), "mismatches": mismatches[:25]}


def run_selftest():
    print("Running self-test on synthetic data...")

    # effective_demand / coverage_ranks: known synthetic curve where
    # ranks 1-5 always start, 6-10 start half the time, rest never.
    exact_obs = []
    for rank in range(1, 5 + 1):
        exact_obs += [(rank, "started")] * 10
    for rank in range(6, 10 + 1):
        exact_obs += [(rank, "started")] * 5 + [(rank, "benched")] * 5
    for rank in range(11, 20 + 1):
        exact_obs += [(rank, "benched")] * 10

    ed = effective_demand(exact_obs)
    # expected: 5*1.0 + 5*0.5 + rest*0 = 7.5 (MAX_RANK_REPORTED beyond 20 contributes 0 since no data there)
    assert abs(ed - 7.5) < 0.01, f"expected effective_demand ~7.5, got {ed}"
    print(f"  effective_demand on synthetic curve = {ed} -- OK")

    cov = coverage_ranks(exact_obs)
    # total started = 5*10 + 5*5 = 75. 80% of 75 = 60 -> reached partway through rank 6-10 band (10/rank)
    assert cov["80"] is not None and 5 <= cov["80"] <= 10, f"expected 80% coverage rank in 5-10, got {cov}"
    print(f"  coverage_ranks on synthetic curve = {cov} -- OK")

    # dual-eligibility check: build a deliberate mismatch and confirm it's caught
    fake_lineup = {"seasons": {"2099": {"records": [
        {"player_id": "x1", "pos_bucket": "DL"},
        {"player_id": "x2", "pos_bucket": "LB"},
    ]}}}
    fake_points = {"seasons": {"2099": {
        "x1": {"pos_bucket": "DL"},   # consistent
        "x2": {"pos_bucket": "DB"},   # deliberately inconsistent
    }}}
    result = check_dual_eligibility_consistency(fake_lineup, fake_points)
    assert result["mismatches_found"] == 1, f"expected exactly 1 synthetic mismatch, got {result}"
    assert result["mismatches"][0]["player_id"] == "x2"
    print("  dual-eligibility consistency check correctly catches a deliberate mismatch -- OK")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()

    if not os.path.exists(LINEUP_PATH) or not os.path.exists(POINTS_PATH):
        print(f"ERROR: need both {LINEUP_PATH} and {POINTS_PATH} to exist.")
        sys.exit(1)

    with open(LINEUP_PATH) as f:
        lineup_data = json.load(f)
    with open(POINTS_PATH) as f:
        points_data = json.load(f)

    seasons = [s for s in ("2024", "2025") if s in lineup_data["seasons"] and s in points_data["seasons"]]
    print(f"Seasons available: {seasons}")

    dual_elig = check_dual_eligibility_consistency(lineup_data, points_data)
    print(f"\nDual-eligibility consistency: checked {dual_elig['players_checked']} players, "
          f"{dual_elig['mismatches_found']} mismatch(es) found.")
    if dual_elig["mismatches_found"]:
        print("  MISMATCHES FOUND -- the lineup and points pipelines disagree on at least one "
              "player's position bucket. This can make the rank curves and the dedicated/flex "
              "demand counts disagree for purely bookkeeping reasons. See the output file for "
              "the full list.")

    results = {"positions": {}, "dual_eligibility_check": dual_elig}
    md_lines = ["# Roster-Economics Robustness Checks\n",
                f"Dual-eligibility consistency: {dual_elig['players_checked']} players checked, "
                f"**{dual_elig['mismatches_found']} mismatches**.\n"]

    for position in POSITIONS:
        print(f"\n=== {position} ===")
        pooled_roster_status = []
        pooled_rank_by_week = {}  # week -> metrics, per season kept separate by prefixing week key
        all_week_keys = []
        rosterability_by_season = {}

        for season in seasons:
            season_points = points_data["seasons"][season]
            rank_by_week = build_trailing_metrics(season_points, position)
            roster_status = collect_roster_status(lineup_data, season_points, season, position)

            rosterability_by_season[season] = rosterability_curve(
                lineup_data, season_points, season, position, rank_by_week
            )

            # Namespace week keys by season so pooling doesn't collide
            # week 5 of 2024 with week 5 of 2025 in the bootstrap/pooled
            # rank lookups below.
            for week, metrics in rank_by_week.items():
                pooled_rank_by_week[(season, week)] = metrics
            for week, pid, status in roster_status:
                pooled_roster_status.append(((season, week), pid, status))
                all_week_keys.append((season, week))

        pooled_roster_status = list(dict.fromkeys(pooled_roster_status))  # de-dup defensively
        all_week_keys = sorted(set(all_week_keys))

        exact_obs = exact_rank_observations(pooled_roster_status, pooled_rank_by_week, 0)
        ed = effective_demand(exact_obs)
        cov = coverage_ranks(exact_obs)
        sensitivity = bin_width_sensitivity(pooled_roster_status, pooled_rank_by_week, 0)
        bootstrap = bootstrap_crossing(all_week_keys, pooled_roster_status, pooled_rank_by_week, 0)

        print(f"  effective_demand: {ed}")
        print(f"  coverage ranks (80/90/95% of real starts): {cov}")
        print(f"  bin-width sensitivity (50%-crossing by width): {sensitivity}")
        print(f"  bootstrap 50%-crossing: median={bootstrap['median']} "
              f"p10={bootstrap['p10']} p90={bootstrap['p90']} "
              f"(resolved {bootstrap['n_resolved']}/{bootstrap['n_iterations']} resamples)")

        results["positions"][position] = {
            "effective_demand": ed,
            "coverage_ranks": cov,
            "bin_width_sensitivity": sensitivity,
            "bootstrap_50pct_crossing": bootstrap,
            "rosterability_by_season": rosterability_by_season,
            "documented_baseline": DOCUMENTED_BASELINE.get(position),
            "empirical_baseline": LEGACY_EMPIRICAL_BASELINE.get(position),
        }

        md_lines.append(f"\n## {position}\n")
        md_lines.append(f"- Effective demand (integral under start-rate curve): **{ed}**")
        md_lines.append(f"- Coverage ranks (80% / 90% / 95% of real starts): "
                         f"**{cov['80']} / {cov['90']} / {cov['95']}**")
        md_lines.append(f"- 50%-crossing by bin width -- 1: {sensitivity['crossing_by_width'].get(1)}, "
                         f"3: {sensitivity['crossing_by_width'].get(3)}, "
                         f"5: {sensitivity['crossing_by_width'].get(5)} "
                         f"(stable: **{sensitivity['stable']}**)")
        md_lines.append(f"- Bootstrap 50%-crossing: median **{bootstrap['median']}**, "
                         f"10th-90th percentile **[{bootstrap['p10']}, {bootstrap['p90']}]** "
                         f"({bootstrap['n_resolved']}/{bootstrap['n_iterations']} resamples resolved)")
        md_lines.append(f"- Documented baseline: {DOCUMENTED_BASELINE.get(position)}  |  "
                         f"Empirical baseline: {LEGACY_EMPIRICAL_BASELINE.get(position)}")

    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
scripts/start_rate_curve_analysis.py

Roster-economics hypothesis -- steps 5-6: build start-rate curves by
real, point-in-time positional rank, and identify the replacement-zone
"cliff" for each position. This is the step that actually tests the
rank-sensitivity sweep's finding (DL behaves shallower than documented,
RB/WR behave deeper) against real lineup behavior.

METHODOLOGY -- exactly as specified and approved:
- PRIMARY metric: trailing PPG through week N-1 (mean points/game over
  all weeks < N where the player recorded a real game).
- ROBUSTNESS CHECK: trailing cumulative points through week N-1 (sum,
  not mean, over the same window). Rewards proven volume over rate --
  a genuinely different ranking in some cases (e.g. a low-snap but
  efficient rotational DL vs. a full-time average one), which is exactly
  why it's useful as a check, not redundant with PPG.
- Weeks 1-3 EXCLUDED from both rank curves (1-2 games of trailing data
  is close to meaningless as a rank signal) but NOT excluded from the
  raw usage/market-share numbers already reported by
  historical_lineup_reconstruction.py -- that exclusion is scoped to
  this script only.
- Rank is computed WITHIN the player's own scored position bucket
  (pos_bucket, e.g. "DL"), against the FULL NFL universe at that
  position (see historical_weekly_points_pipeline.py's docstring for
  why the full universe, not just this league's rostered players).
- Curves built separately for 2024 and 2025 first, then pooled. This
  surfaces season-to-season noise (see the DL IDP_FLEX share swing
  already found: 4.2% in 2024 -> 18.4% in 2025) before it gets averaged
  away and hidden inside a single pooled number.
- Replacement "zone," not a single optimized rank -- reported as
  (last rank with start rate >= 80%, first rank with start rate <= 20%).
  A true instant cliff gives a narrow zone; a gradual falloff gives a
  wide one, and the width itself is informative, not just the location.
- No preseason/hybrid ranking system built here -- only triggered if
  PPG-rank and cumulative-rank curves disagree enough to matter. That
  comparison is reported explicitly so the decision is a real one, not
  assumed.

INPUTS (must already exist in scripts/, both from real Sleeper pulls):
- historical_lineup_demand.json -- MUST be a run of the CURRENT
  historical_lineup_reconstruction.py (2026-08-26 update or later) that
  includes "benched" records. A pre-bench-capture file will silently
  produce a rostered-player universe of starters only, which inflates
  every start rate toward 100% and makes the whole curve meaningless --
  this script checks for at least one "benched" record and aborts with
  a clear error if none are found, rather than producing a bad result
  quietly.
- weekly_points_by_season.json -- from historical_weekly_points_pipeline.py.

REQUIRES NO NETWORK ACCESS -- pure computation over the two input files.

USAGE: python3 scripts/start_rate_curve_analysis.py
Add --selftest to run a synthetic-data sanity check of the ranking/
binning/zone-detection logic BEFORE trusting real output -- cheap,
catches a logic bug before it costs a real interpretation mistake, same
spirit as the manual ground-truth checks used elsewhere in this project.

OUTPUT:
- scripts/start_rate_curves.json (full machine-readable curves + zones)
- scripts/start_rate_curve_report.md (human-readable summary + baseline
  comparison table)
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LINEUP_PATH = os.path.join(SCRIPT_DIR, "historical_lineup_demand.json")
POINTS_PATH = os.path.join(SCRIPT_DIR, "weekly_points_by_season.json")
OUT_JSON = os.path.join(SCRIPT_DIR, "start_rate_curves.json")
OUT_MD = os.path.join(SCRIPT_DIR, "start_rate_curve_report.md")

POSITIONS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]
MIN_RANK_WEEK = 4          # weeks 1-3 excluded from rank curves (see docstring)
BIN_WIDTH = 3               # rank bins for the start-rate curve
MAX_RANK_REPORTED = 60      # curves beyond this are noise for a 12-team league

DOCUMENTED_BASELINE = {"QB": 18, "RB": 32, "WR": 36, "TE": 15, "DL": 32, "LB": 32, "DB": 32}
LEGACY_EMPIRICAL_BASELINE = {"QB": 18, "RB": 37, "WR": 43, "TE": 16, "DL": 23, "LB": 32, "DB": 30}


def build_trailing_metrics(season_points, position):
    """
    Returns {week: {pid: (trailing_ppg, trailing_cumulative)}} for every
    week >= MIN_RANK_WEEK, computed strictly from weeks < that week, for
    every player at this position with >=1 real game in that trailing
    window. season_points is weekly_points_by_season.json's per-season
    dict: {pid: {pos_bucket, weekly_points: {week_str: pts}}}.
    """
    players = {pid: p for pid, p in season_points.items() if p.get("pos_bucket") == position}
    # Determine the real max week present in the data for this season.
    max_week = 0
    for p in players.values():
        for wk in p["weekly_points"]:
            max_week = max(max_week, int(wk))

    by_week = {}
    for week in range(MIN_RANK_WEEK, max_week + 1):
        week_metrics = {}
        for pid, p in players.items():
            prior_scores = [pts for wk, pts in p["weekly_points"].items() if int(wk) < week]
            if not prior_scores:
                continue  # no trailing data yet -- can't rank (e.g. rookie debut)
            trailing_ppg = sum(prior_scores) / len(prior_scores)
            trailing_cum = sum(prior_scores)
            week_metrics[pid] = (trailing_ppg, trailing_cum)
        by_week[week] = week_metrics
    return by_week


def rank_within_week(week_metrics, metric_index):
    """Returns {pid: rank} for one week, rank 1 = highest value, ties broken by pid for determinism."""
    ordered = sorted(week_metrics.items(), key=lambda kv: (-kv[1][metric_index], kv[0]))
    return {pid: i + 1 for i, (pid, _) in enumerate(ordered)}


def collect_roster_status(lineup_data, season, position):
    """
    Returns [(week, pid, status)] for every ROSTERED player (started or
    benched) at this position, week >= MIN_RANK_WEEK, from the lineup
    reconstruction's real records. status is 'started' or 'benched'.
    """
    records = lineup_data["seasons"][season]["records"]
    out = []
    for r in records:
        if r["week"] < MIN_RANK_WEEK:
            continue
        if r["pos_bucket"] != position:
            continue
        if r["start_type"] in ("dedicated", "flex"):
            out.append((r["week"], r["player_id"], "started"))
        elif r["start_type"] == "benched":
            out.append((r["week"], r["player_id"], "benched"))
    return out


def build_curve(roster_status, rank_by_week, metric_index):
    """
    Joins roster status with the precomputed rank-by-week for one metric,
    bins by rank, and returns {bin_start: {'started': n, 'total': n, 'rate': pct}}.
    """
    bin_counts = {}  # bin_start -> [started, total]
    unranked_skipped = 0
    for week, pid, status in roster_status:
        week_metrics = rank_by_week.get(week, {})
        pid_metrics = week_metrics.get(pid)
        if pid_metrics is None:
            unranked_skipped += 1
            continue  # no trailing data for this player yet this week
        ranks = rank_within_week(week_metrics, metric_index)
        rank = ranks[pid]
        if rank > MAX_RANK_REPORTED:
            continue
        bin_start = ((rank - 1) // BIN_WIDTH) * BIN_WIDTH + 1
        counts = bin_counts.setdefault(bin_start, [0, 0])
        counts[1] += 1
        if status == "started":
            counts[0] += 1

    curve = {}
    for bin_start, (started, total) in sorted(bin_counts.items()):
        curve[bin_start] = {
            "started": started, "total": total,
            "rate_pct": round(100 * started / total, 1) if total else None,
        }
    return curve, unranked_skipped


def find_replacement_zone(curve):
    """
    zone = (last rank-bin-start with rate >= 80%, first rank-bin-start
    with rate <= 20%, at or after that point). Returns (None, None) if
    the curve never clearly crosses both thresholds (e.g. too sparse).
    """
    sorted_bins = sorted(curve.items())
    upper = None
    lower = None
    for bin_start, v in sorted_bins:
        if v["rate_pct"] is None:
            continue
        if v["rate_pct"] >= 80:
            upper = bin_start  # keep updating -- want the LAST bin still >=80%
    crossed_upper = False
    for bin_start, v in sorted_bins:
        if v["rate_pct"] is None:
            continue
        if upper is not None and bin_start >= upper:
            crossed_upper = True
        if crossed_upper and v["rate_pct"] <= 20:
            lower = bin_start
            break
    return upper, lower


def compare_to_baselines(zone, position):
    upper, lower = zone
    doc = DOCUMENTED_BASELINE.get(position)
    emp = LEGACY_EMPIRICAL_BASELINE.get(position)

    def locate(value):
        if value is None or upper is None or lower is None:
            return "n/a (zone not resolved)"
        if value < upper:
            return f"ABOVE the zone (shallower than observed cliff) -- rank {value} still had a high real start rate"
        if value > lower:
            return f"BELOW the zone (deeper than observed cliff) -- rank {value} already had a low real start rate"
        return f"INSIDE the observed zone (rank {value} is within the real falloff range)"

    return {
        "documented_baseline": doc, "documented_vs_zone": locate(doc),
        "empirical_baseline": emp, "empirical_vs_zone": locate(emp),
    }


def run_selftest():
    """
    Synthetic sanity check -- NOT real football data. Verifies the
    ranking/binning/zone math is internally correct before spending a
    real API pull + real interpretation time on it. Builds a fake
    position with a clean, known cliff at rank 10 and checks the
    pipeline recovers it.
    """
    print("Running self-test on synthetic data (rank/bin/zone logic only)...")
    fake_points = {}
    for i in range(1, 41):
        pid = f"fake{i}"
        # descending trailing PPG by construction: rank i player has PPG (41-i)
        weekly = {str(wk): float(41 - i) for wk in range(1, 6)}
        fake_points[pid] = {"pos_bucket": "DL", "weekly_points": weekly}

    by_week = build_trailing_metrics(fake_points, "DL")
    assert 4 in by_week and 5 in by_week, "expected weeks 4-5 to have trailing data"
    ranks_wk5 = rank_within_week(by_week[5], 0)
    assert ranks_wk5["fake1"] == 1, f"expected fake1 (highest PPG) to rank 1, got {ranks_wk5['fake1']}"
    assert ranks_wk5["fake40"] == 40, f"expected fake40 (lowest PPG) to rank 40, got {ranks_wk5['fake40']}"

    # synthetic roster status: everyone ranked <=10 always started, >10 never started
    roster_status = []
    for wk in (4, 5):
        for i in range(1, 41):
            status = "started" if i <= 10 else "benched"
            roster_status.append((wk, f"fake{i}", status))

    curve, skipped = build_curve(roster_status, by_week, 0)
    zone = find_replacement_zone(curve)
    upper, lower = zone
    assert upper is not None and lower is not None, "expected a clean zone on a synthetic hard cliff"
    assert upper <= 10 <= lower, f"expected the known cliff (rank 10) inside zone {zone}, got upper={upper} lower={lower}"
    print(f"  Synthetic hard-cliff-at-rank-10 recovered as zone {zone} -- OK")
    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()

    if not os.path.exists(LINEUP_PATH) or not os.path.exists(POINTS_PATH):
        print(f"ERROR: need both {LINEUP_PATH} and {POINTS_PATH} to exist. Run "
              f"historical_lineup_reconstruction.py and historical_weekly_points_pipeline.py first.")
        sys.exit(1)

    with open(LINEUP_PATH) as f:
        lineup_data = json.load(f)
    with open(POINTS_PATH) as f:
        points_data = json.load(f)

    any_benched = any(
        r["start_type"] == "benched"
        for season_data in lineup_data["seasons"].values()
        for r in season_data["records"]
    )
    if not any_benched:
        print("ERROR: historical_lineup_demand.json has no 'benched' records. This file predates "
              "the 2026-08-26 bench-capture update -- re-run historical_lineup_reconstruction.py "
              "before running this script, or every start rate will be meaningless (denominator "
              "will only ever be starters).")
        sys.exit(1)

    seasons = [s for s in ("2024", "2025") if s in lineup_data["seasons"] and s in points_data["seasons"]]
    print(f"Seasons available in both inputs: {seasons}")

    results = {"positions": {}}
    md_lines = ["# Start-Rate Curve Analysis\n",
                "Trailing-PPG rank is primary; trailing-cumulative rank is the robustness check. "
                "Weeks 1-3 excluded. Zone = (last rank with real start rate >=80%, first rank at/after "
                "that point with start rate <=20%).\n"]

    for position in POSITIONS:
        print(f"\n=== {position} ===")
        results["positions"][position] = {"by_season": {}, "pooled": {}}
        pooled_roster_status_ppg = []
        pooled_roster_status_cum = []
        pooled_rank_by_week_ppg = {}
        pooled_rank_by_week_cum = {}

        for season in seasons:
            season_points = points_data["seasons"][season]
            rank_by_week_metrics = build_trailing_metrics(season_points, position)
            roster_status = collect_roster_status(lineup_data, season, position)

            curve_ppg, skipped_ppg = build_curve(roster_status, rank_by_week_metrics, 0)
            curve_cum, skipped_cum = build_curve(roster_status, rank_by_week_metrics, 1)
            zone_ppg = find_replacement_zone(curve_ppg)
            zone_cum = find_replacement_zone(curve_cum)

            results["positions"][position]["by_season"][season] = {
                "curve_trailing_ppg": curve_ppg, "zone_trailing_ppg": zone_ppg,
                "curve_trailing_cumulative": curve_cum, "zone_trailing_cumulative": zone_cum,
                "unranked_skipped_ppg": skipped_ppg,
                "baseline_comparison_ppg": compare_to_baselines(zone_ppg, position),
            }
            print(f"  {season}: PPG-rank zone={zone_ppg}  cumulative-rank zone={zone_cum}  "
                  f"(skipped {skipped_ppg} unranked observations)")

            # accumulate for pooled curve -- re-rank per-season-per-week
            # metrics stay season-local (a 2024 week-6 rank isn't compared
            # to a 2025 week-6 rank directly), but the (week,pid,status)
            # roster observations and their already-computed ranks pool
            # cleanly since "rank" is the shared currency across seasons.
            for week, pid, status in roster_status:
                wm = rank_by_week_metrics.get(week, {})
                if pid not in wm:
                    continue
                ranks_ppg = rank_within_week(wm, 0)
                ranks_cum = rank_within_week(wm, 1)
                pooled_roster_status_ppg.append((ranks_ppg[pid], status))
                pooled_roster_status_cum.append((ranks_cum[pid], status))

        # Pooled curve: bin directly on the already-computed pooled ranks
        # (season-local ranks, pooled as observations) rather than re-
        # deriving from scratch -- equivalent to build_curve's binning
        # step but working from (rank, status) pairs already assembled.
        def bin_pooled(pairs):
            bin_counts = {}
            for rank, status in pairs:
                if rank > MAX_RANK_REPORTED:
                    continue
                bin_start = ((rank - 1) // BIN_WIDTH) * BIN_WIDTH + 1
                counts = bin_counts.setdefault(bin_start, [0, 0])
                counts[1] += 1
                if status == "started":
                    counts[0] += 1
            return {
                b: {"started": s, "total": t, "rate_pct": round(100 * s / t, 1) if t else None}
                for b, (s, t) in sorted(bin_counts.items())
            }

        pooled_curve_ppg = bin_pooled(pooled_roster_status_ppg)
        pooled_curve_cum = bin_pooled(pooled_roster_status_cum)
        pooled_zone_ppg = find_replacement_zone(pooled_curve_ppg)
        pooled_zone_cum = find_replacement_zone(pooled_curve_cum)
        pooled_baseline_cmp = compare_to_baselines(pooled_zone_ppg, position)

        agree = (
            pooled_zone_ppg[0] is not None and pooled_zone_cum[0] is not None
            and abs(pooled_zone_ppg[0] - pooled_zone_cum[0]) <= BIN_WIDTH * 2
            and abs((pooled_zone_ppg[1] or 0) - (pooled_zone_cum[1] or 0)) <= BIN_WIDTH * 2
        )

        results["positions"][position]["pooled"] = {
            "curve_trailing_ppg": pooled_curve_ppg, "zone_trailing_ppg": pooled_zone_ppg,
            "curve_trailing_cumulative": pooled_curve_cum, "zone_trailing_cumulative": pooled_zone_cum,
            "ppg_vs_cumulative_agree": agree,
            "baseline_comparison": pooled_baseline_cmp,
        }

        print(f"  POOLED: PPG-rank zone={pooled_zone_ppg}  cumulative-rank zone={pooled_zone_cum}  "
              f"agree={agree}")
        print(f"  documented baseline ({DOCUMENTED_BASELINE.get(position)}): "
              f"{pooled_baseline_cmp['documented_vs_zone']}")
        print(f"  empirical baseline ({LEGACY_EMPIRICAL_BASELINE.get(position)}): "
              f"{pooled_baseline_cmp['empirical_vs_zone']}")

        md_lines.append(f"\n## {position}\n")
        md_lines.append(f"- Pooled PPG-rank zone: **{pooled_zone_ppg}**")
        md_lines.append(f"- Pooled cumulative-rank zone: **{pooled_zone_cum}**")
        md_lines.append(f"- PPG vs. cumulative agree (within {BIN_WIDTH * 2} ranks): **{agree}**")
        md_lines.append(f"- Documented baseline ({DOCUMENTED_BASELINE.get(position)}): {pooled_baseline_cmp['documented_vs_zone']}")
        md_lines.append(f"- Empirical baseline ({LEGACY_EMPIRICAL_BASELINE.get(position)}): {pooled_baseline_cmp['empirical_vs_zone']}")

    any_disagree = any(
        not results["positions"][p]["pooled"]["ppg_vs_cumulative_agree"]
        for p in POSITIONS
    )
    md_lines.append("\n## Overall stability check\n")
    if any_disagree:
        md_lines.append(
            "PPG-rank and cumulative-rank zones diverge for at least one position -- "
            "per the agreed plan, this is the trigger to consider building the preseason/"
            "hybrid ranking system. Check the per-position sections above for which one(s)."
        )
    else:
        md_lines.append(
            "PPG-rank and cumulative-rank zones agree across all positions with usable data -- "
            "per the agreed plan, no need to build the preseason/hybrid ranking system yet."
        )

    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()

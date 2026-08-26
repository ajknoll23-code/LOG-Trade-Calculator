#!/usr/bin/env python3
"""
scripts/dl_future_split_stability_check.py

One bounded, targeted follow-up, per the external methodology review of
the real backtest results. DL23 (legacy_empirical) beat documented (32)
by 10.6% MAE in Test 3, stable across all three forward-window sizes,
won all 15 folds. Before treating that as anything more than "the
strongest candidate so far," the review flagged a real gap: Test 3's
future-only target is itself an SSE-reduction split on FUTURE production
-- which finds a real production tier break, but a production tier break
is not automatically the same thing as an economic replacement level.
That target has never been inspected directly for stability, especially
for an IDP position with known high week-to-week scoring variance.

THE QUESTION THIS ANSWERS: does future DL production repeatedly produce
a real boundary in roughly the low-to-mid 20s (which would make DL23 a
strong, trustworthy future-production calibration candidate), or does
the future split rank bounce around wildly across folds/windows/resamples
while the MEDIAN just happens to land near 23 (which would make the
10.6% MAE win much less persuasive, since Test 3's target itself would
be unstable)?

WHAT THIS COMPUTES, DL ONLY:
- The future-derived optimal split rank for every fold, individually.
- The same, separately for 2-, 4-, and 6-week forward windows.
- Median, IQR (25th/75th), 10th-90th percentile, and full min/max range
  of those future split ranks.
- A frequency table (histogram) of the future split ranks.
- The future baseline PPG value at each split (not just the rank -- the
  review specifically asked for this so the actual value, not just the
  index, is inspectable).
- A block bootstrap over folds (resample folds with replacement, same
  block-level resampling logic already used and validated in this
  project's DB bootstrap sanity check) to see how stable the MEDIAN
  future split rank is under resampling of which folds happened to be
  observed.

REQUIRES NO NETWORK ACCESS -- reuses baseline_backtester.py's
build_folds() and find_best_split(), both already self-tested there.

USAGE: python3 scripts/dl_future_split_stability_check.py
OUTPUT: scripts/dl_future_split_stability_report.md (written as a real
file, not just console output -- this project's workflows have no
interactive terminal to read stdout from directly).
"""

import json
import os
import random
import sys

from baseline_backtester import build_folds, find_best_split, MAX_RANK_FOR_BASELINE

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
POINTS_PATH = os.path.join(SCRIPT_DIR, "weekly_points_by_season.json")
OUT_PATH = os.path.join(SCRIPT_DIR, "dl_future_split_stability_report.md")

POSITION = "DL"
WINDOWS = [2, 4, 6]
BOOTSTRAP_ITERATIONS = 200

_LOG_LINES = []


def log(msg=""):
    print(msg)
    _LOG_LINES.append(msg)


def percentile(sorted_vals, pct):
    if not sorted_vals:
        return None
    idx = min(len(sorted_vals) - 1, max(0, int(round(pct / 100 * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def find_future_splits_for_window(points_data, window):
    """
    For every fold at this forward window, find the future-derived
    optimal split (rank + PPG value at that rank), for DL only. This is
    the exact same computation baseline_backtester.run_test3() does
    internally, pulled out here as its own inspectable step rather than
    immediately being consumed into an MAE number.
    """
    folds = build_folds(points_data, window)
    results = []
    for fold in folds:
        pos_train = {pid: v for pid, v in fold["train"].items() if v["pos_bucket"] == POSITION}
        pos_target = {pid: v for pid, v in fold["target"].items()
                       if pid in fold["train"] and fold["train"][pid]["pos_bucket"] == POSITION}
        if len(pos_target) < 15:
            continue
        future_ranked = sorted(pos_target.items(), key=lambda kv: -kv[1])[:MAX_RANK_FOR_BASELINE]
        future_values_in_order = [v for _, v in future_ranked]
        split = find_best_split(future_values_in_order)
        if split is None:
            continue
        split_ppg = future_values_in_order[split - 1]
        results.append({
            "fold": fold["name"], "window": window, "split_rank": split,
            "split_ppg": round(split_ppg, 2), "n_players": len(pos_target),
        })
    return results


def block_bootstrap_median(split_ranks, iterations=BOOTSTRAP_ITERATIONS, seed=42):
    """Resample folds' split ranks with replacement -- same block-bootstrap
    logic already validated in db_bootstrap_sanity_check.py -- and report
    how stable the MEDIAN is under resampling."""
    rng = random.Random(seed)
    n = len(split_ranks)
    if n == 0:
        return {"median": None, "p10": None, "p90": None}
    medians = []
    for _ in range(iterations):
        sample = [rng.choice(split_ranks) for _ in range(n)]
        sample.sort()
        medians.append(sample[len(sample) // 2])
    medians.sort()
    return {
        "median": medians[len(medians) // 2],
        "p10": percentile(medians, 10),
        "p90": percentile(medians, 90),
        "min": medians[0], "max": medians[-1],
    }


def main():
    if not os.path.exists(POINTS_PATH):
        log(f"ERROR: need {POINTS_PATH} to exist.")
        sys.exit(1)

    with open(POINTS_PATH) as f:
        points_data = json.load(f)

    log("# DL Future-Split Stability Check\n")
    log("Question: does future DL production repeatedly produce a real boundary in the "
        "low-to-mid 20s, or does the future split rank bounce around while the median "
        "happens to land near 23?\n")

    all_results = []
    for window in WINDOWS:
        window_results = find_future_splits_for_window(points_data, window)
        all_results.extend(window_results)
        splits = sorted(r["split_rank"] for r in window_results)
        ppgs = [r["split_ppg"] for r in window_results]

        log(f"## Window = {window} weeks ({len(window_results)} folds)\n")
        log("| Fold | Split rank | Split PPG | N players |")
        log("|---|---|---|---|")
        for r in window_results:
            log(f"| {r['fold']} | {r['split_rank']} | {r['split_ppg']} | {r['n_players']} |")

        if splits:
            q1 = percentile(splits, 25)
            q3 = percentile(splits, 75)
            log(f"\nMedian: **{splits[len(splits)//2]}**  |  IQR: [{q1}, {q3}]  |  "
                f"10th-90th pctile: [{percentile(splits,10)}, {percentile(splits,90)}]  |  "
                f"Range: [{splits[0]}, {splits[-1]}]")
            log(f"Median split PPG value: {sorted(ppgs)[len(ppgs)//2]}\n")
        else:
            log("\nNo folds resolved at this window.\n")

    log("\n## Combined across all windows\n")
    all_splits = sorted(r["split_rank"] for r in all_results)
    if all_splits:
        log("Frequency table (rank bucket : count):")
        buckets = {}
        for s in all_splits:
            b = (s // 5) * 5
            buckets[b] = buckets.get(b, 0) + 1
        for b in sorted(buckets):
            log(f"  {b:>3}-{b+4:<3}: {buckets[b]:>3}  {'#' * buckets[b]}")

        q1 = percentile(all_splits, 25)
        q3 = percentile(all_splits, 75)
        log(f"\nMedian (all windows combined): **{all_splits[len(all_splits)//2]}**  |  "
            f"IQR: [{q1}, {q3}]  |  10th-90th: [{percentile(all_splits,10)}, {percentile(all_splits,90)}]  |  "
            f"Range: [{all_splits[0]}, {all_splits[-1]}]  |  n={len(all_splits)}")

        boot = block_bootstrap_median(all_splits)
        log(f"\nBlock bootstrap of the median split rank ({BOOTSTRAP_ITERATIONS} resamples): "
            f"median={boot['median']}, 10th-90th=[{boot['p10']}, {boot['p90']}], "
            f"range=[{boot['min']}, {boot['max']}]")

        log("\n## Interpretation guide (not an automatic verdict)\n")
        log("- If most individual-fold split ranks cluster roughly in the low-to-mid 20s "
            "(say, 18-28) and the bootstrap 10th-90th interval is reasonably tight around "
            "the median: the future production boundary is real and stable -- DL23 is a "
            "strong, trustworthy future-production calibration candidate.")
        log("- If individual-fold splits are scattered widely (e.g. some folds in the "
            "teens, some past 40) even though the median lands near 23: the apparent DL23 "
            "advantage is likely being driven by a target that itself isn't stable, and "
            "the 10.6% MAE win should be treated with much more caution.")
    else:
        log("No folds resolved at all -- cannot assess stability.")

    with open(OUT_PATH, "w") as f:
        f.write("\n".join(_LOG_LINES) + "\n")
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

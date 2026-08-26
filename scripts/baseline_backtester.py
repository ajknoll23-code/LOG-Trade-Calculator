#!/usr/bin/env python3
"""
scripts/baseline_backtester.py

The actual backtester, per ChatGPT's "co-equal priority #2" and the final
closeout of the roster-economics workstream: "Which baseline choices
would have produced better predictions of subsequent fantasy
production?" -- not which reproduces the old baked table, not which
matches real lineup behavior. Those were both explored already
(prod-mult-reconstruction-audit.md, roster-economics-closing-summary.md)
and both explicitly flagged as NOT the same question as this one.

WHAT THIS TESTS: three candidate replacement-baseline rank sets, run
through the REAL live formula's exact transform (verified against
prod-mult-reconstruction-audit.md, not guessed):
    ratio = combined / baseline[pos]
    prod_mult = clamp(-0.10 + 0.75 * ratio, 0.15, 1.55)

SCOPE LIMITATION, STATED UP FRONT: the real live formula's "combined"
input blends 0.45x trailing shrunk PPG with 0.55x an external 2026
projection (FantasyPros/Sleeper). This backtester cannot reconstruct
historical external projections for arbitrary past weeks -- those were
one-time snapshots collected by hand, not a queryable time series. This
backtester therefore uses TRAILING PPG ALONE as "combined," which
isolates and tests the one specific thing actually in dispute across
this whole investigation (the baseline/denominator), while deliberately
NOT re-litigating the 45/55 blend weight or projection-data quality --
those are separate, already-settled design choices. If this backtester
ever gets extended to test the blend weights too, that needs real
historical projection snapshots, which don't currently exist.

THREE CANDIDATE BASELINE SETS:
- documented:      QB18 RB32 WR36 TE15 DL32 LB32 DB32 (the tool's live values)
- legacy_empirical: QB18 RB37 WR43 TE16 DL23 LB32 DB30 (what the OLD baked
  table's behavior implied -- already shown NOT to be supported by real
  lineup economics; included here because "doesn't match lineup behavior"
  and "doesn't predict future production" are different claims, and this
  is the test that actually distinguishes them)
- roster_economics_informed: built from this session's real start-rate-
  curve/coverage-rank findings where they were resolved and stable, and
  left at the documented value everywhere the earlier work found the
  signal unresolved or too noisy to act on (QB, LB, DB) -- RB26/WR34/DL32
  are the only three changed from documented, per the actual closing
  summary's per-position verdicts.

TWO TESTS, BOTH RUN:
1. WALK-FORWARD PREDICTIVE VALIDITY (the main event): for each fold,
   position, and baseline candidate, compute each player's prod_mult
   using ONLY data available before the fold's cutoff, then correlate
   (Pearson AND Spearman) against his REAL subsequent production. Higher
   correlation = a baseline choice whose resulting values better predict
   what actually happens next -- the literal question this backtester
   exists to answer.
2. DATA-DRIVEN OPTIMAL SPLIT (a bonus, assumption-free check): independent
   of all three named candidates, sweeps candidate ranks and finds the one
   that maximizes explained variance in SUBSEQUENT production (same
   variance-reduction criterion regression trees use to pick a split) --
   letting the data nominate its own best answer, then reporting where
   that lands relative to the three named candidates.

FOLDS: within-season rolling folds (predict a 4-week forward window from
trailing data through the prior week, several times per season) PLUS one
cross-season fold (train on all of 2024, predict all of 2025) -- multiple
folds specifically because two seasons is thin and a single point
estimate would repeat the exact mistake already caught and fixed once in
this project's history (see the roster-economics workstream's bootstrap
work).

REQUIRES NO NETWORK ACCESS -- uses only weekly_points_by_season.json,
already produced by historical_weekly_points_pipeline.py.

USAGE: python3 scripts/baseline_backtester.py
Add --selftest to sanity-check the correlation/split-finding logic
against synthetic data with a KNOWN true relationship before trusting
real output.

OUTPUT:
- scripts/baseline_backtest_results.json
- scripts/baseline_backtest_report.md
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
POINTS_PATH = os.path.join(SCRIPT_DIR, "weekly_points_by_season.json")
OUT_JSON = os.path.join(SCRIPT_DIR, "baseline_backtest_results.json")
OUT_MD = os.path.join(SCRIPT_DIR, "baseline_backtest_report.md")

POSITIONS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]
MIN_TRAILING_GAMES = 3   # consistent with the roster-economics workstream
FORWARD_WINDOW = 4       # weeks
MAX_RANK_FOR_BASELINE = 60

BASELINE_CANDIDATES = {
    "documented": {"QB": 18, "RB": 32, "WR": 36, "TE": 15, "DL": 32, "LB": 32, "DB": 32},
    "legacy_empirical": {"QB": 18, "RB": 37, "WR": 43, "TE": 16, "DL": 23, "LB": 32, "DB": 30},
    # Only RB/WR/DL changed from documented -- QB/LB/DB were explicitly
    # left unresolved or too noisy to act on in roster-economics-closing-
    # summary.md, so they stay at the documented value here rather than
    # inventing a number the earlier work didn't actually support.
    "roster_economics_informed": {"QB": 18, "RB": 26, "WR": 34, "TE": 15, "DL": 32, "LB": 32, "DB": 32},
}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def prod_mult(combined, baseline_score):
    if not baseline_score:
        return 0.15
    ratio = combined / baseline_score
    return clamp(-0.10 + 0.75 * ratio, 0.15, 1.55)


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / (vx ** 0.5 * vy ** 0.5)


def spearman(xs, ys):
    def rank(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                ranks[order[k]] = avg_rank
            i = j + 1
        return ranks
    return pearson(rank(xs), rank(ys))


def build_folds(points_data):
    """
    Returns a list of fold dicts: {name, train: {pid: {pos_bucket, ppg}},
    target: {pid: ppg}}. train's ppg is trailing mean PPG (>=MIN_TRAILING_
    GAMES real games); target's ppg is forward mean PPG (>=1 real game in
    the forward window).
    """
    folds = []
    seasons = points_data["seasons"]

    for season in ("2024", "2025"):
        if season not in seasons:
            continue
        players = seasons[season]
        max_week = 0
        for p in players.values():
            for wk in p["weekly_points"]:
                max_week = max(max_week, int(wk))

        for predict_week in range(9, 16):
            if predict_week + FORWARD_WINDOW - 1 > max_week:
                continue
            train, target = {}, {}
            for pid, p in players.items():
                trailing = [pts for wk, pts in p["weekly_points"].items() if int(wk) < predict_week]
                if len(trailing) >= MIN_TRAILING_GAMES:
                    train[pid] = {"pos_bucket": p["pos_bucket"], "ppg": sum(trailing) / len(trailing)}
                forward = [pts for wk, pts in p["weekly_points"].items()
                           if predict_week <= int(wk) < predict_week + FORWARD_WINDOW]
                if forward:
                    target[pid] = sum(forward) / len(forward)
            folds.append({"name": f"{season}_wk{predict_week}", "train": train, "target": target})

    # Cross-season fold: full 2024 trailing -> full 2025 forward.
    if "2024" in seasons and "2025" in seasons:
        train = {}
        for pid, p in seasons["2024"].items():
            games = list(p["weekly_points"].values())
            if len(games) >= MIN_TRAILING_GAMES:
                train[pid] = {"pos_bucket": p["pos_bucket"], "ppg": sum(games) / len(games)}
        target = {}
        for pid, p in seasons["2025"].items():
            games = list(p["weekly_points"].values())
            if games:
                target[pid] = sum(games) / len(games)
        folds.append({"name": "2024_full_to_2025_full", "train": train, "target": target})

    return folds


def baseline_score_for_rank(ranked_ppgs, rank):
    if not ranked_ppgs:
        return None
    idx = min(rank - 1, len(ranked_ppgs) - 1)
    return ranked_ppgs[idx]


def run_predictive_validity(folds):
    """Test 1: correlation between candidate-baseline prod_mult and real subsequent PPG."""
    results = {}
    for position in POSITIONS:
        results[position] = {name: {"pearson": [], "spearman": [], "n_folds": 0} for name in BASELINE_CANDIDATES}
        for fold in folds:
            pos_train = {pid: v for pid, v in fold["train"].items() if v["pos_bucket"] == position}
            if len(pos_train) < 10:
                continue
            ranked_ppgs = sorted((v["ppg"] for v in pos_train.values()), reverse=True)[:MAX_RANK_FOR_BASELINE]

            for cand_name, cand_ranks in BASELINE_CANDIDATES.items():
                baseline_rank = cand_ranks.get(position)
                baseline_score = baseline_score_for_rank(ranked_ppgs, baseline_rank)
                if not baseline_score:
                    continue
                xs, ys = [], []
                for pid, v in pos_train.items():
                    if pid not in fold["target"]:
                        continue
                    mult = prod_mult(v["ppg"], baseline_score)
                    xs.append(mult)
                    ys.append(fold["target"][pid])
                if len(xs) < 10:
                    continue
                p = pearson(xs, ys)
                s = spearman(xs, ys)
                if p is not None:
                    results[position][cand_name]["pearson"].append(round(p, 4))
                if s is not None:
                    results[position][cand_name]["spearman"].append(round(s, 4))
                results[position][cand_name]["n_folds"] += 1
    return results


def sse_reduction_for_split(ppgs_sorted_desc, targets_sorted_by_same_order, split_rank):
    """
    Variance-reduction criterion (same idea CART regression trees use to
    pick a split): how much of the total sum-of-squared-error in the
    FUTURE production target is explained by splitting players into
    (rank <= split_rank) vs. (rank > split_rank), based on trailing rank.
    Higher reduction = a cleaner real discontinuity in subsequent
    production at that rank.
    """
    n = len(targets_sorted_by_same_order)
    if split_rank < 1 or split_rank >= n:
        return None
    group_a = targets_sorted_by_same_order[:split_rank]
    group_b = targets_sorted_by_same_order[split_rank:]
    mean_all = sum(targets_sorted_by_same_order) / n
    sse_before = sum((y - mean_all) ** 2 for y in targets_sorted_by_same_order)
    mean_a = sum(group_a) / len(group_a)
    mean_b = sum(group_b) / len(group_b)
    sse_after = sum((y - mean_a) ** 2 for y in group_a) + sum((y - mean_b) ** 2 for y in group_b)
    return sse_before - sse_after


def run_optimal_split(folds):
    """Test 2: data-driven best split rank, independent of the 3 named candidates."""
    results = {position: [] for position in POSITIONS}
    for position in POSITIONS:
        for fold in folds:
            pos_train = {pid: v for pid, v in fold["train"].items() if v["pos_bucket"] == position}
            ranked = sorted(pos_train.items(), key=lambda kv: -kv[1]["ppg"])[:MAX_RANK_FOR_BASELINE]
            pids_in_rank_order = [pid for pid, _ in ranked]
            targets_in_rank_order = []
            valid_pids = []
            for pid in pids_in_rank_order:
                if pid in fold["target"]:
                    targets_in_rank_order.append(fold["target"][pid])
                    valid_pids.append(pid)
            n = len(targets_in_rank_order)
            if n < 15:
                continue

            best_split, best_reduction = None, -1
            for split_rank in range(5, n - 5):
                reduction = sse_reduction_for_split(None, targets_in_rank_order, split_rank)
                if reduction is not None and reduction > best_reduction:
                    best_reduction, best_split = reduction, split_rank
            if best_split is not None:
                results[position].append(best_split)
    return results


def run_selftest():
    print("Running self-test on synthetic data with a KNOWN true relationship...")

    # pearson/spearman sanity: perfect positive linear relationship
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [2.0, 4.0, 6.0, 8.0, 10.0]
    p = pearson(xs, ys)
    assert p is not None and abs(p - 1.0) < 1e-9, f"expected pearson=1.0 for perfect linear data, got {p}"
    s = spearman(xs, ys)
    assert s is not None and abs(s - 1.0) < 1e-9, f"expected spearman=1.0 for perfect monotonic data, got {s}"
    print(f"  pearson/spearman on perfect linear data = {p}/{s} -- OK")

    # prod_mult clamp sanity
    assert prod_mult(0, 10) == 0.15, "ratio=0 should hit the floor"
    assert prod_mult(1000, 10) == 1.55, "huge ratio should hit the ceiling"
    assert abs(prod_mult(10, 10) - 0.65) < 1e-9, "ratio=1.0 should give -0.10+0.75=0.65"
    print("  prod_mult clamp behavior (floor/ceiling/ratio=1.0) -- OK")

    # optimal-split sanity: a KNOWN hard cliff at rank 10 (targets 10.0 for
    # ranks 1-10, 2.0 for ranks 11-30) should be found by the SSE-reduction
    # search, same synthetic-cliff pattern used elsewhere in this project.
    targets = [10.0] * 10 + [2.0] * 20
    best_split, best_reduction = None, -1
    for split_rank in range(5, len(targets) - 5):
        r = sse_reduction_for_split(None, targets, split_rank)
        if r is not None and r > best_reduction:
            best_reduction, best_split = r, split_rank
    assert best_split == 10, f"expected the known cliff at rank 10 to be found exactly, got {best_split}"
    print(f"  SSE-reduction split-finder recovers a known hard cliff at rank 10 exactly -- OK")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()

    if not os.path.exists(POINTS_PATH):
        print(f"ERROR: need {POINTS_PATH} to exist. Run historical_weekly_points_pipeline.py first.")
        sys.exit(1)

    with open(POINTS_PATH) as f:
        points_data = json.load(f)

    folds = build_folds(points_data)
    print(f"Built {len(folds)} folds: {[f['name'] for f in folds]}\n")

    predictive = run_predictive_validity(folds)
    splits = run_optimal_split(folds)

    md_lines = ["# Baseline Backtest Report\n",
                f"{len(folds)} folds: {', '.join(f['name'] for f in folds)}\n",
                "Test 1 -- median Pearson / Spearman correlation between each candidate "
                "baseline's resulting prod_mult and REAL subsequent PPG, across all folds. "
                "Higher = that baseline choice better predicts what actually happens next.\n"]

    results_out = {"folds": [f["name"] for f in folds], "positions": {}}

    for position in POSITIONS:
        print(f"=== {position} ===")
        pos_result = {"predictive_validity": {}, "optimal_splits": splits[position]}
        md_lines.append(f"\n## {position}\n")
        md_lines.append("| Baseline candidate | Median Pearson | Median Spearman | Folds used |")
        md_lines.append("|---|---|---|---|")

        best_cand, best_score = None, -2
        for cand_name in BASELINE_CANDIDATES:
            r = predictive[position][cand_name]
            pearsons = sorted(r["pearson"])
            spearmans = sorted(r["spearman"])
            med_p = pearsons[len(pearsons) // 2] if pearsons else None
            med_s = spearmans[len(spearmans) // 2] if spearmans else None
            pos_result["predictive_validity"][cand_name] = {
                "median_pearson": med_p, "median_spearman": med_s,
                "n_folds": r["n_folds"], "all_pearson": r["pearson"], "all_spearman": r["spearman"],
            }
            print(f"  {cand_name:28s} median_pearson={med_p}  median_spearman={med_s}  (n={r['n_folds']} folds)")
            md_lines.append(f"| {cand_name} | {med_p} | {med_s} | {r['n_folds']} |")
            if med_p is not None and med_p > best_score:
                best_score, best_cand = med_p, cand_name

        splits_this_pos = sorted(splits[position])
        median_split = splits_this_pos[len(splits_this_pos) // 2] if splits_this_pos else None
        print(f"  Data-driven optimal split (median across {len(splits_this_pos)} folds): rank {median_split}")
        print(f"  Best predictive candidate by median Pearson: {best_cand}\n")

        md_lines.append(f"\nData-driven optimal split (median across {len(splits_this_pos)} folds, "
                         f"independent of the 3 named candidates): **rank {median_split}**")
        md_lines.append(f"\nAll optimal splits found: {splits_this_pos}")
        md_lines.append(f"\n**Best predictive candidate for {position}: {best_cand}**")

        pos_result["best_predictive_candidate"] = best_cand
        pos_result["median_optimal_split"] = median_split
        results_out["positions"][position] = pos_result

    with open(OUT_JSON, "w") as f:
        json.dump(results_out, f, indent=2)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()

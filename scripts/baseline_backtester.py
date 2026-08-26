#!/usr/bin/env python3
"""
scripts/baseline_backtester.py

REVISION 2 (2026-08-27) -- rebuilt after an external methodology review
found a real mathematical flaw in the original Test 1: within one
position, changing only the baseline is (pre-clamp) a positive affine
transform of trailing PPG. Pearson is invariant to positive affine
transforms; Spearman is invariant to ANY monotonic transform. So Test 1's
correlation with future PPG could not mathematically distinguish baseline
quality except through clamp-induced tie compression -- confirmed
empirically before this rewrite (three baselines run against the same
synthetic combined/future data produced different correlations purely
because of how many players got floored to 0.15 at each baseline, not
from any real signal about which baseline is "right"). The mental model
that survived the review: the numerator (combined/trailing production)
is predictive; the denominator (baseline) is economic. Test 1 was asking
the denominator to answer a predictive question it mathematically can't.

WHAT THIS TESTS, NOW THREE TESTS WITH THREE DIFFERENT JOBS:

- TEST 1, renamed "predictive preservation / clamp sensitivity"
  (DIAGNOSTIC, NOT a winner-picker): correlation (Pearson, Spearman)
  between each candidate's prod_mult and real subsequent PPG, PLUS
  floor/ceiling hit rates so the clamp-compression mechanism is visible,
  not hidden behind a single correlation number. Useful for catching a
  baseline that's so aggressive it floors/ceilings an unreasonable share
  of a position -- not useful for picking "the best" baseline.

- TEST 2, renamed "future-production tier-break diagnostic" (SUPPORTING
  EVIDENCE, NOT ground truth): the data-driven SSE-reduction split search
  from REVISION 1, unchanged. Still shares core information with Test 1
  (past rank -> future production), so agreement with Test 3 is
  supportive, not two fully independent data sources. A statistical
  production cliff found here is not automatically a replacement-level
  rank -- it's where the reality of subsequent production happens to
  separate most sharply, which can differ from a defensible economic
  replacement definition.

- TEST 3, NEW, the actual decision criterion: a non-circular calibration
  test against real future relative-production structure. For each fold:
    1. Rank players by ACTUAL FUTURE production (not trailing -- this is
       the key move that avoids circularity) and find that future
       period's OWN natural production break via the same SSE-reduction
       method as Test 2, applied entirely within the future data. This
       gives a replacement rank that does not reference ANY of the 3
       named candidates at all.
    2. future_ratio[player] = future_ppg[player] / future_ppg-at-that-
       future-derived-rank -- the REAL relative-value structure that
       materialized, independent of anyone's prior beliefs.
    3. predicted_ratio[player, candidate] = trailing_ppg[player] /
       training-time baseline_score[candidate] -- each candidate's own
       forecast of relative value, using only pre-fold information.
    4. MAE and RMSE between predicted_ratio and future_ratio, per
       candidate. Lower error = that candidate's baseline choice better
       anticipated the real relative-value structure that actually
       happened next. This measures MAGNITUDE, not just ordering --
       exactly what Test 1 structurally could not measure.

SCOPE LIMITATION, STATED UP FRONT (unchanged from revision 1): the live
formula's real "combined" blends 0.45x trailing shrunk PPG with 0.55x an
external 2026 projection. Historical projection snapshots for arbitrary
past weeks don't exist (one-time hand-collected snapshots, not a
queryable time series), so this uses trailing PPG alone as "combined" --
a defensible isolation of the baseline question, but NOT a perfect
reconstruction of live behavior. If blended-combined reshuffles players
around a given rank differently than trailing-PPG-alone does, the
"player occupying rank 32" may not be quite the same type of player in
the live tool as in this backtest. Labeled, not solved.

ALSO NEW IN THIS REVISION, per the same review:
- Per-fold breakdown, not just an aggregate median: separate 2024-only,
  2025-only, and cross-season results, plus a simple "folds won" count
  per candidate. Two seasons of heavily-overlapping rolling windows is
  much thinner independent evidence than 15 folds sounds like -- a
  candidate that wins by 0.002 median is not the same finding as a
  candidate that wins across both seasons, the cross-season fold, AND
  most individual weekly folds.
- Forward-window robustness: Test 3 is re-run at 2-week, 4-week, and
  6-week forward windows. If the winning candidate changes across window
  sizes, that's reported explicitly as an instability, not smoothed over.
- A concrete real-data sanity table per position (candidate baseline
  rank, the actual player occupying it, his PPG, eligible player count,
  floor/ceiling percentages) so the clamp-compression mechanism is
  directly inspectable, not just summarized.

THREE CANDIDATE BASELINE SETS (unchanged from revision 1 -- reviewed and
confirmed fair: comparing position-by-position, not scoring "5 of 7
positions won," so leaving 4 positions identical to documented does not
structurally bias the comparison):
- documented:      QB18 RB32 WR36 TE15 DL32 LB32 DB32
- legacy_empirical: QB18 RB37 WR43 TE16 DL23 LB32 DB30
- roster_economics_informed: QB18 RB26 WR34 TE15 DL32 LB32 DB32

REQUIRES NO NETWORK ACCESS -- uses only weekly_points_by_season.json.

USAGE: python3 scripts/baseline_backtester.py
Add --selftest to sanity-check the logic against synthetic data with a
KNOWN true relationship, including a new targeted test confirming Test 3
can actually discriminate a correct baseline from a wrong one on a
controlled synthetic case -- the original revision's self-tests confirmed
the implementation behaved as intended, but never confirmed the primary
test could actually tell a right answer from a wrong one, which turned
out to be exactly the blind spot the external review caught.

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
MIN_TRAILING_GAMES = 3
FORWARD_WINDOWS = [2, 4, 6]   # robustness sweep; 4 remains the primary/reported window
PRIMARY_WINDOW = 4
MAX_RANK_FOR_BASELINE = 60

BASELINE_CANDIDATES = {
    "documented": {"QB": 18, "RB": 32, "WR": 36, "TE": 15, "DL": 32, "LB": 32, "DB": 32},
    "legacy_empirical": {"QB": 18, "RB": 37, "WR": 43, "TE": 16, "DL": 23, "LB": 32, "DB": 30},
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


def build_folds(points_data, forward_window):
    """Same fold design as revision 1, parametrized on forward_window for the robustness sweep."""
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
            if predict_week + forward_window - 1 > max_week:
                continue
            train, target = {}, {}
            for pid, p in players.items():
                trailing = [pts for wk, pts in p["weekly_points"].items() if int(wk) < predict_week]
                if len(trailing) >= MIN_TRAILING_GAMES:
                    train[pid] = {"pos_bucket": p["pos_bucket"], "name": p.get("name", pid),
                                  "ppg": sum(trailing) / len(trailing)}
                forward = [pts for wk, pts in p["weekly_points"].items()
                           if predict_week <= int(wk) < predict_week + forward_window]
                if forward:
                    target[pid] = sum(forward) / len(forward)
            folds.append({"name": f"{season}_wk{predict_week}", "season": season,
                          "train": train, "target": target})

    if "2024" in seasons and "2025" in seasons:
        train = {}
        for pid, p in seasons["2024"].items():
            games = list(p["weekly_points"].values())
            if len(games) >= MIN_TRAILING_GAMES:
                train[pid] = {"pos_bucket": p["pos_bucket"], "name": p.get("name", pid),
                              "ppg": sum(games) / len(games)}
        target = {}
        for pid, p in seasons["2025"].items():
            games = list(p["weekly_points"].values())
            if games:
                target[pid] = sum(games) / len(games)
        folds.append({"name": "2024_full_to_2025_full", "season": "cross",
                      "train": train, "target": target})

    return folds


def baseline_score_for_rank(ranked_ppgs, rank):
    if not ranked_ppgs:
        return None
    idx = min(rank - 1, len(ranked_ppgs) - 1)
    return ranked_ppgs[idx]


def sse_reduction_for_split(targets_sorted_by_rank, split_rank):
    n = len(targets_sorted_by_rank)
    if split_rank < 1 or split_rank >= n:
        return None
    group_a = targets_sorted_by_rank[:split_rank]
    group_b = targets_sorted_by_rank[split_rank:]
    mean_all = sum(targets_sorted_by_rank) / n
    sse_before = sum((y - mean_all) ** 2 for y in targets_sorted_by_rank)
    mean_a = sum(group_a) / len(group_a)
    mean_b = sum(group_b) / len(group_b)
    sse_after = sum((y - mean_a) ** 2 for y in group_a) + sum((y - mean_b) ** 2 for y in group_b)
    return sse_before - sse_after


def find_best_split(values_sorted_by_rank, min_group=5):
    n = len(values_sorted_by_rank)
    best_split, best_reduction = None, -1
    for split_rank in range(min_group, n - min_group):
        r = sse_reduction_for_split(values_sorted_by_rank, split_rank)
        if r is not None and r > best_reduction:
            best_reduction, best_split = r, split_rank
    return best_split


def run_test1_and_2(folds, position):
    """Diagnostic tests, kept from revision 1, reframed as non-decisive."""
    test1 = {name: {"pearson": [], "spearman": [], "floor_pct": [], "ceiling_pct": []}
             for name in BASELINE_CANDIDATES}
    test2_splits = []

    for fold in folds:
        pos_train = {pid: v for pid, v in fold["train"].items() if v["pos_bucket"] == position}
        if len(pos_train) < 15:
            continue
        ranked_ppgs = sorted((v["ppg"] for v in pos_train.values()), reverse=True)[:MAX_RANK_FOR_BASELINE]

        for cand_name, cand_ranks in BASELINE_CANDIDATES.items():
            baseline_rank = cand_ranks.get(position)
            baseline_score = baseline_score_for_rank(ranked_ppgs, baseline_rank)
            if not baseline_score:
                continue
            xs, ys = [], []
            floor_n, ceiling_n = 0, 0
            for pid, v in pos_train.items():
                if pid not in fold["target"]:
                    continue
                mult = prod_mult(v["ppg"], baseline_score)
                xs.append(mult)
                ys.append(fold["target"][pid])
                if mult <= 0.15:
                    floor_n += 1
                if mult >= 1.55:
                    ceiling_n += 1
            if len(xs) < 10:
                continue
            p = pearson(xs, ys)
            s = spearman(xs, ys)
            if p is not None:
                test1[cand_name]["pearson"].append(round(p, 4))
            if s is not None:
                test1[cand_name]["spearman"].append(round(s, 4))
            test1[cand_name]["floor_pct"].append(round(100 * floor_n / len(xs), 1))
            test1[cand_name]["ceiling_pct"].append(round(100 * ceiling_n / len(xs), 1))

        # Test 2: trailing-rank -> future-ppg split search (unchanged logic)
        ranked_pids = sorted(pos_train.items(), key=lambda kv: -kv[1]["ppg"])[:MAX_RANK_FOR_BASELINE]
        targets_in_order = [fold["target"][pid] for pid, _ in ranked_pids if pid in fold["target"]]
        if len(targets_in_order) >= 15:
            split = find_best_split(targets_in_order)
            if split is not None:
                test2_splits.append(split)

    return test1, test2_splits


def run_test3(folds, position):
    """
    The real decision criterion. For each fold: derive a future-only
    replacement rank (no candidate involved), compute future_ratio from
    it, compute each candidate's predicted_ratio from training-time data
    only, and score by MAE/RMSE between the two.
    """
    per_candidate = {name: {"mae": [], "rmse": [], "fold_names": []} for name in BASELINE_CANDIDATES}

    for fold in folds:
        pos_train = {pid: v for pid, v in fold["train"].items() if v["pos_bucket"] == position}
        pos_target = {pid: v for pid, v in fold["target"].items() if pid in fold["train"] and
                       fold["train"][pid]["pos_bucket"] == position}
        if len(pos_target) < 15:
            continue

        # Non-circular future replacement rank: rank by FUTURE production,
        # find where the FUTURE data itself naturally breaks.
        future_ranked = sorted(pos_target.items(), key=lambda kv: -kv[1])[:MAX_RANK_FOR_BASELINE]
        future_values_in_order = [v for _, v in future_ranked]
        future_split = find_best_split(future_values_in_order)
        if future_split is None:
            continue
        future_replacement_ppg = future_values_in_order[future_split - 1]
        if future_replacement_ppg <= 0:
            continue

        future_ratio = {pid: v / future_replacement_ppg for pid, v in pos_target.items()}

        ranked_ppgs = sorted((v["ppg"] for v in pos_train.values()), reverse=True)[:MAX_RANK_FOR_BASELINE]
        for cand_name, cand_ranks in BASELINE_CANDIDATES.items():
            baseline_rank = cand_ranks.get(position)
            baseline_score = baseline_score_for_rank(ranked_ppgs, baseline_rank)
            if not baseline_score:
                continue
            errors = []
            for pid in pos_target:
                predicted_ratio = pos_train[pid]["ppg"] / baseline_score
                errors.append(predicted_ratio - future_ratio[pid])
            if len(errors) < 10:
                continue
            mae = sum(abs(e) for e in errors) / len(errors)
            rmse = (sum(e ** 2 for e in errors) / len(errors)) ** 0.5
            per_candidate[cand_name]["mae"].append(round(mae, 4))
            per_candidate[cand_name]["rmse"].append(round(rmse, 4))
            per_candidate[cand_name]["fold_names"].append(fold["name"])

    return per_candidate


def build_sanity_table(folds, position):
    """One concrete fold (the cross-season fold, most complete) showing
    exactly which player sits at each candidate's baseline rank and how
    much clamp compression results -- makes the Test 1 mechanism directly
    inspectable rather than summarized away."""
    cross_fold = next((f for f in folds if f["season"] == "cross"), folds[-1] if folds else None)
    if not cross_fold:
        return {}
    pos_train = {pid: v for pid, v in cross_fold["train"].items() if v["pos_bucket"] == position}
    ranked = sorted(pos_train.items(), key=lambda kv: -kv[1]["ppg"])
    table = {}
    for cand_name, cand_ranks in BASELINE_CANDIDATES.items():
        rank = cand_ranks.get(position)
        idx = min(rank - 1, len(ranked) - 1) if ranked else None
        if idx is None:
            continue
        pid, info = ranked[idx]
        baseline_score = info["ppg"]
        floor_n = sum(1 for _, v in pos_train.items() if prod_mult(v["ppg"], baseline_score) <= 0.15)
        ceiling_n = sum(1 for _, v in pos_train.items() if prod_mult(v["ppg"], baseline_score) >= 1.55)
        table[cand_name] = {
            "candidate_rank": rank, "player_at_rank": info["name"],
            "baseline_ppg": round(baseline_score, 2), "eligible_players": len(pos_train),
            "floor_pct": round(100 * floor_n / len(pos_train), 1),
            "ceiling_pct": round(100 * ceiling_n / len(pos_train), 1),
        }
    return table


def summarize_folds_won(test3_by_window):
    """Given per-window Test 3 results, count how many folds each candidate 'won' (lowest MAE)."""
    wins = {name: 0 for name in BASELINE_CANDIDATES}
    fold_names = test3_by_window[PRIMARY_WINDOW]["documented"]["fold_names"] if test3_by_window.get(PRIMARY_WINDOW) else []
    for i in range(len(fold_names)):
        maes = {}
        for cand in BASELINE_CANDIDATES:
            cand_data = test3_by_window[PRIMARY_WINDOW].get(cand, {})
            if i < len(cand_data.get("mae", [])):
                maes[cand] = cand_data["mae"][i]
        if maes:
            winner = min(maes, key=maes.get)
            wins[winner] += 1
    return wins


def median(vals):
    if not vals:
        return None
    s = sorted(vals)
    return s[len(s) // 2]


def run_selftest():
    print("Running self-test on synthetic data with a KNOWN true relationship...")

    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [2.0, 4.0, 6.0, 8.0, 10.0]
    assert abs(pearson(xs, ys) - 1.0) < 1e-9
    assert abs(spearman(xs, ys) - 1.0) < 1e-9
    print("  pearson/spearman on perfect linear data -- OK")

    assert prod_mult(0, 10) == 0.15
    assert prod_mult(1000, 10) == 1.55
    assert abs(prod_mult(10, 10) - 0.65) < 1e-9
    print("  prod_mult clamp behavior (floor/ceiling/ratio=1.0) -- OK")

    targets = [10.0] * 10 + [2.0] * 20
    assert find_best_split(targets) == 10
    print("  SSE-reduction split-finder recovers a known hard cliff at rank 10 exactly -- OK")

    # NEW: targeted test that Test 3 can actually discriminate a correct
    # baseline from a wrong one -- the original revision never tested
    # this, which is exactly the blind spot the external review caught.
    # Construct: trailing_ppg == true_skill exactly (perfect predictor),
    # future_ppg == true_skill exactly too (perfect persistence), with a
    # real cliff at rank 20 (top 20 players worth 2x the rest). A
    # candidate whose baseline rank is 20 should have ~0 MAE; a candidate
    # whose baseline rank is way off (e.g. 5 or 50) should have much
    # higher MAE.
    n = 60
    true_skill = {}
    for i in range(1, n + 1):
        # Real gradient within the top tier (30 down to ~24.3) so that
        # different ranks WITHIN 1-20 have genuinely different values --
        # a flat plateau there (first version of this test) made rank 5
        # and rank 20 look up the identical value and trivially tie,
        # which is a flaw in the TEST's construction, not the backtester.
        # Bottom tier stays flat/low; only used to test a badly-wrong
        # baseline (rank 50), which doesn't need internal gradient.
        if i <= 20:
            true_skill[f"s{i}"] = 30.0 - (i - 1) * 0.3
        else:
            true_skill[f"s{i}"] = 10.0

    fake_train = {pid: {"pos_bucket": "DL", "name": pid, "ppg": val} for pid, val in true_skill.items()}
    fake_target = {pid: val for pid, val in true_skill.items()}
    fake_fold = {"name": "synthetic", "season": "cross", "train": fake_train, "target": fake_target}

    candidates_to_test = {"correct_rank_20": {"DL": 20}, "wrong_rank_5": {"DL": 5}, "wrong_rank_50": {"DL": 50}}
    global BASELINE_CANDIDATES
    original_candidates = BASELINE_CANDIDATES
    BASELINE_CANDIDATES = candidates_to_test
    result = run_test3([fake_fold], "DL")
    BASELINE_CANDIDATES = original_candidates

    mae_correct = result["correct_rank_20"]["mae"][0] if result["correct_rank_20"]["mae"] else None
    mae_wrong_5 = result["wrong_rank_5"]["mae"][0] if result["wrong_rank_5"]["mae"] else None
    mae_wrong_50 = result["wrong_rank_50"]["mae"][0] if result["wrong_rank_50"]["mae"] else None
    assert mae_correct is not None and mae_wrong_5 is not None and mae_wrong_50 is not None, \
        f"expected all three candidates to resolve, got {result}"
    assert mae_correct < mae_wrong_5, f"expected correct baseline (rank 20) to beat wrong rank 5, got {mae_correct} vs {mae_wrong_5}"
    assert mae_correct < mae_wrong_50, f"expected correct baseline (rank 20) to beat wrong rank 50, got {mae_correct} vs {mae_wrong_50}"
    print(f"  Test 3 correctly discriminates a known-correct baseline (MAE={mae_correct}) from "
          f"known-wrong ones (MAE={mae_wrong_5}, {mae_wrong_50}) on a controlled synthetic cliff -- OK")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()

    if not os.path.exists(POINTS_PATH):
        print(f"ERROR: need {POINTS_PATH} to exist.")
        sys.exit(1)

    with open(POINTS_PATH) as f:
        points_data = json.load(f)

    results_out = {"positions": {}}
    md_lines = ["# Baseline Backtest Report (Revision 2)\n",
                "**Test 3 is the decision criterion.** Test 1 and Test 2 are diagnostics "
                "kept for context, per the methodology review that found Test 1's original "
                "correlation-based design could not mathematically distinguish baseline "
                "quality within a position (see script docstring).\n"]

    for position in POSITIONS:
        print(f"\n=== {position} ===")
        folds_primary = build_folds(points_data, PRIMARY_WINDOW)
        test1, test2_splits = run_test1_and_2(folds_primary, position)
        sanity_table = build_sanity_table(folds_primary, position)

        test3_by_window = {}
        for window in FORWARD_WINDOWS:
            folds_w = build_folds(points_data, window)
            test3_by_window[window] = run_test3(folds_w, position)

        wins = summarize_folds_won(test3_by_window)

        md_lines.append(f"\n## {position}\n")
        md_lines.append("### Test 3 (decision criterion) -- MAE against non-circular future relative-production target\n")
        md_lines.append("| Candidate | Median MAE (4wk) | Folds won (4wk) | MAE @2wk | MAE @4wk | MAE @6wk |")
        md_lines.append("|---|---|---|---|---|---|")

        best_cand, best_mae = None, float("inf")
        for cand_name in BASELINE_CANDIDATES:
            mae_4wk = test3_by_window[4][cand_name]["mae"]
            mae_2wk = test3_by_window[2][cand_name]["mae"]
            mae_6wk = test3_by_window[6][cand_name]["mae"]
            med_4 = median(mae_4wk)
            med_2 = median(mae_2wk)
            med_6 = median(mae_6wk)
            print(f"  {cand_name:28s} median_MAE(4wk)={med_4}  folds_won={wins[cand_name]}  "
                  f"MAE@2wk={med_2}  MAE@6wk={med_6}")
            md_lines.append(f"| {cand_name} | {med_4} | {wins[cand_name]} | {med_2} | {med_4} | {med_6} |")
            if med_4 is not None and med_4 < best_mae:
                best_mae, best_cand = med_4, cand_name

        stable = True
        window_winners = {}
        for window in FORWARD_WINDOWS:
            window_maes = {name: median(test3_by_window[window][name]["mae"]) for name in BASELINE_CANDIDATES}
            valid = {k: v for k, v in window_maes.items() if v is not None}
            window_winner = min(valid, key=valid.get) if valid else None
            window_winners[window] = window_winner
        if len(set(window_winners.values())) > 1:
            stable = False

        print(f"  BEST (Test 3, primary 4wk window): {best_cand}")
        print(f"  Stable across 2/4/6-week windows: {stable}  (winners: {window_winners})")

        md_lines.append(f"\n**Best by Test 3: {best_cand}**  |  Stable across forward-window sizes: **{stable}** "
                         f"(per-window winners: {window_winners})")

        md_lines.append("\n### Test 1 (diagnostic -- clamp sensitivity, NOT a winner-picker)\n")
        md_lines.append("| Candidate | Median Pearson | Median Spearman | Median floor% | Median ceiling% |")
        md_lines.append("|---|---|---|---|---|")
        for cand_name in BASELINE_CANDIDATES:
            t1 = test1[cand_name]
            md_lines.append(f"| {cand_name} | {median(t1['pearson'])} | {median(t1['spearman'])} | "
                             f"{median(t1['floor_pct'])} | {median(t1['ceiling_pct'])} |")

        md_lines.append("\n### Test 2 (diagnostic -- future-production tier-break, NOT ground truth)\n")
        md_lines.append(f"Median optimal split (independent of named candidates): "
                         f"**rank {median(test2_splits)}** across {len(test2_splits)} folds")

        md_lines.append("\n### Real-data sanity table (cross-season fold)\n")
        md_lines.append("| Candidate | Rank | Player at rank | Baseline PPG | Eligible players | Floor% | Ceiling% |")
        md_lines.append("|---|---|---|---|---|---|---|")
        for cand_name, row in sanity_table.items():
            md_lines.append(f"| {cand_name} | {row['candidate_rank']} | {row['player_at_rank']} | "
                             f"{row['baseline_ppg']} | {row['eligible_players']} | "
                             f"{row['floor_pct']} | {row['ceiling_pct']} |")

        results_out["positions"][position] = {
            "test3_by_window": test3_by_window, "test3_folds_won": wins,
            "test3_best": best_cand, "test3_stable_across_windows": stable,
            "test1": {name: {k: v for k, v in test1[name].items()} for name in BASELINE_CANDIDATES},
            "test2_median_split": median(test2_splits),
            "sanity_table": sanity_table,
        }

    with open(OUT_JSON, "w") as f:
        json.dump(results_out, f, indent=2)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()

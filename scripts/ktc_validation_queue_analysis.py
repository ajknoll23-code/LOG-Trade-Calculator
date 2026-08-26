#!/usr/bin/env python3
"""
scripts/ktc_validation_queue_analysis.py

Consumes real votes and scores ratio vs. differential scarcity formulas
against them -- the actual decision step this whole detour exists to
support. Companion to ktc_validation_queue_generator.py (which built the
frozen triad pool) and the index.html widget change (which surfaces ~15%
of votes from that pool).

HOW VALIDATION-QUEUE VOTES ARE IDENTIFIED: no backend schema change was
made to tag provenance. Instead, a real vote's 3 players are checked
against the frozen ktc_validation_queue.json triads by set membership
(regardless of order) -- matching all 3 of a specific ~37-entry list by
chance is astronomically unlikely, so a match is treated as certain
provenance from the queue.

METHODOLOGY, per the external review's guidance on the original (now-
superseded) offense-only attempt:

- Primary metric: log loss under a logistic mapping, NOT raw pairwise
  winner accuracy. Winner accuracy treats "formula barely preferred the
  winner" and "formula was extremely confident" identically -- log loss
  penalizes confident wrong answers and rewards well-calibrated
  confidence, which is what actually distinguishes a good scarcity
  formula from a lucky one.
- P(A beats B) = logistic(scale * (value_A - value_B)), separately for
  ratio-based values and differential-based values. A scale/temperature
  parameter is fit per formula (simple 1-D maximum-likelihood logistic
  regression) because ratio and differential live on completely
  different raw numeric scales -- comparing raw value differences
  directly would unfairly favor whichever formula happens to produce
  larger numbers.
- Leave-one-voter-out cross-validation, not a single train/test split --
  with only ~12 real league voters, this is the only validation scheme
  that gives an honest answer to "does this formula generalize to a
  voter it wasn't fit against," which is the real question. Fit the
  scale parameter on all voters except one, evaluate log loss on the
  held-out voter's votes, repeat for every voter.
- Reports both per-voter and pooled results, plus how many DECOY picks
  were unexpected (voter chose to keep/trade the decoy instead of
  cutting it) -- a real, if rare, signal that a "decoy" wasn't actually
  weak in that voter's eyes, worth surfacing rather than silently
  ignoring.

REQUIRES NETWORK ACCESS by default (fetches votes live from the same
Google Sheet published-CSV URL ktc_pipeline.py uses -- no manual export
needed). A local file path can still be passed explicitly for offline
testing against a saved export, but the normal path needs no argument at
all, matching how the aggregator already works. Also needs
prod_mult_pipeline_output.json to already exist locally.

USAGE: python3 scripts/ktc_validation_queue_analysis.py
       (fetches votes live from the Sheet)
   or: python3 scripts/ktc_validation_queue_analysis.py <path_to_local_export>
       (offline testing against a saved xlsx/CSV export)
Add --selftest to sanity-check the logistic fitting and leave-one-voter-
out logic against synthetic data with a KNOWN better formula before
trusting real output.
"""

import csv
import io
import json
import math
import os
import sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_PATH = os.path.join(SCRIPT_DIR, "ktc_validation_queue.json")
LINEAGE_PATH = os.path.join(SCRIPT_DIR, "prod_mult_pipeline_output.json")
OUT_PATH = os.path.join(SCRIPT_DIR, "ktc_validation_analysis_report.md")

# Same Sheet, same URL, same daily cap as ktc_pipeline.py -- kept
# identical on purpose so both scripts see the same real vote population,
# just processed for different questions.
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTuKORGumlKJmUmBdeNWPstkj8VRjPoVkylbqHv1KqwoyziJYOUlkZUKRsSxzB3qHXmyjjLpGpH6W03/pub?gid=458294959&single=true&output=csv"
MAX_VOTES_PER_VOTER_PER_DAY = 20


def fetch_votes_live():
    import requests
    print("Fetching votes live from the Sheet (same source as ktc_pipeline.py)...")
    resp = requests.get(SHEET_CSV_URL, timeout=30)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    print(f"  {len(rows)} raw vote rows fetched")
    return rows


def apply_daily_cap(rows):
    """Identical logic to ktc_pipeline.py's apply_daily_cap() -- kept as
    its own copy here rather than importing from that module, since this
    script needs to run standalone in a workflow step without assuming
    ktc_pipeline.py is importable from the same working directory."""
    counts = defaultdict(int)
    kept = []
    dropped = 0
    for row in rows:
        try:
            day = row["timestamp"][:10]
        except (KeyError, TypeError):
            continue
        key = (row.get("voter_roster_id", ""), day)
        if counts[key] >= MAX_VOTES_PER_VOTER_PER_DAY:
            dropped += 1
            continue
        counts[key] += 1
        kept.append(row)
    if dropped:
        print(f"  Dropped {dropped} votes exceeding the per-voter daily cap")
    return kept


def logistic(x):
    if x > 30:
        return 1.0
    if x < -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def fit_scale(diffs_and_outcomes, iterations=200, lr=0.05):
    """
    1-D logistic regression: fit `scale` maximizing likelihood of real
    outcomes given value differences, via simple gradient ascent (no
    external numerical libraries -- this project keeps dependencies
    minimal throughout, and a 1-parameter fit doesn't need more).
    diffs_and_outcomes: [(value_diff, a_won: bool)]

    CONSTRAINED NON-NEGATIVE, found via a real self-test failure
    (2026-08-27): an unconstrained fit lets scale go negative, which
    silently FLIPS a formula's sign convention -- a formula that is
    perfectly ANTI-correlated with real outcomes gets "rescued" to a
    perfect log loss by fitting a large negative scale, rather than being
    correctly punished for pointing the wrong direction. Caught this by
    deliberately building an adversarial synthetic test (votes that
    always agree with ratio, on triads specifically selected because
    ratio and differential DISAGREE) and finding differential scored a
    perfect 0.0 log loss when it should have scored badly. Since every
    triad in this validation queue is a disagreement case by
    construction, this isn't a contrived edge case -- it's the exact
    situation this whole script runs in. Clamping scale >= 0 forces an
    anti-correlated formula toward scale=0 (uninformative, ~ln(2) log
    loss) instead of rewarding it for pointing backwards.
    """
    scale = 0.1
    n = len(diffs_and_outcomes)
    if n == 0:
        return 0.0
    for _ in range(iterations):
        grad = 0.0
        for d, a_won in diffs_and_outcomes:
            p = logistic(scale * d)
            y = 1.0 if a_won else 0.0
            grad += (y - p) * d
        scale += lr * grad / n
        scale = max(scale, 0.0)
    return scale


def log_loss(diffs_and_outcomes, scale):
    if not diffs_and_outcomes:
        return None
    total = 0.0
    for d, a_won in diffs_and_outcomes:
        p = logistic(scale * d)
        p = min(max(p, 1e-9), 1 - 1e-9)
        y = 1.0 if a_won else 0.0
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(diffs_and_outcomes)


def brier_score(diffs_and_outcomes, scale):
    if not diffs_and_outcomes:
        return None
    total = 0.0
    for d, a_won in diffs_and_outcomes:
        p = logistic(scale * d)
        y = 1.0 if a_won else 0.0
        total += (p - y) ** 2
    return total / len(diffs_and_outcomes)


def accuracy(diffs_and_outcomes, scale):
    if not diffs_and_outcomes:
        return None
    correct = 0
    for d, a_won in diffs_and_outcomes:
        predicted_a = (scale * d) > 0
        if predicted_a == a_won:
            correct += 1
    return correct / len(diffs_and_outcomes)


def raw_directional_accuracy(diffs_and_outcomes):
    """
    Scale-independent diagnostic, per external review point 1: the
    constrained (non-negative) log-loss scoring correctly treats an
    anti-correlated formula as merely "uninformative" (scale converges
    to 0), but that flattens away a real, separate finding worth
    surfacing on its own -- a formula whose RAW natural direction
    (higher value = predicted winner, no fitting at all) is actively
    backwards more often than not. This reports plain accuracy using
    only the formula's own sign, independent of any fitted parameter, so
    "uninformative" and "actively reversed" don't get conflated.
    """
    if not diffs_and_outcomes:
        return None
    correct = 0
    decided = 0
    for d, a_won in diffs_and_outcomes:
        if d == 0:
            continue  # true tie under this formula -- no directional claim to score
        decided += 1
        predicted_a = d > 0
        if predicted_a == a_won:
            correct += 1
    return correct / decided if decided else None


def leave_one_triad_out(by_triad):
    """
    Robustness check per external review point 2: leave-one-voter-out
    alone can't distinguish "generalizes to a new person" from
    "generalizes to a new matchup," since the same triad answered by
    several voters lets the model see that exact matchup's outcomes
    during training even when a different voter is held out. This
    instead holds out an entire TRIAD (all votes on that specific
    matchup, from every voter), fits on every other triad's votes
    pooled together, and evaluates on the held-out triad. Ratio and
    differential should ideally agree under BOTH schemes -- agreement is
    a much stronger signal than either alone.
    by_triad: {triad_id: [(value_diff, a_won)]}
    """
    triad_ids = list(by_triad.keys())
    results = {}
    for held_out in triad_ids:
        train = [obs for t in triad_ids if t != held_out for obs in by_triad[t]]
        test = by_triad[held_out]
        if not train or not test:
            continue
        scale = fit_scale(train)
        results[held_out] = {
            "log_loss": log_loss(test, scale),
            "brier": brier_score(test, scale),
            "accuracy": accuracy(test, scale),
            "n": len(test),
        }
    all_ll = [r["log_loss"] for r in results.values() if r["log_loss"] is not None]
    all_brier = [r["brier"] for r in results.values() if r["brier"] is not None]
    pooled = {
        "mean_log_loss": round(sum(all_ll) / len(all_ll), 4) if all_ll else None,
        "mean_brier": round(sum(all_brier) / len(all_brier), 4) if all_brier else None,
        "n_triads": len(results),
        "n_total_observations": sum(r["n"] for r in results.values()),
    }
    return results, pooled


def leave_one_voter_out(by_voter):
    """
    by_voter: {voter_id: [(value_diff, a_won)]}. For each voter, fit
    scale on everyone else, evaluate on the held-out voter. Returns
    {voter_id: {log_loss, brier, accuracy, n}} plus pooled results.
    """
    voters = list(by_voter.keys())
    results = {}
    pooled_holdout = []
    for held_out in voters:
        train = [obs for v in voters if v != held_out for obs in by_voter[v]]
        test = by_voter[held_out]
        if not train or not test:
            continue
        scale = fit_scale(train)
        results[held_out] = {
            "log_loss": log_loss(test, scale),
            "brier": brier_score(test, scale),
            "accuracy": accuracy(test, scale),
            "n": len(test),
            "scale_fit": round(scale, 4),
        }
        pooled_holdout.extend(test)

    # pooled: average scale across folds applied conceptually via the
    # per-fold held-out predictions already computed above (avoids the
    # circularity of fitting on all data including the very set being
    # scored).
    all_ll = [r["log_loss"] for r in results.values() if r["log_loss"] is not None]
    all_brier = [r["brier"] for r in results.values() if r["brier"] is not None]
    all_acc = [r["accuracy"] for r in results.values() if r["accuracy"] is not None]
    pooled = {
        "mean_log_loss": round(sum(all_ll) / len(all_ll), 4) if all_ll else None,
        "mean_brier": round(sum(all_brier) / len(all_brier), 4) if all_brier else None,
        "mean_accuracy": round(sum(all_acc) / len(all_acc), 4) if all_acc else None,
        "n_voters": len(results),
        "n_total_observations": sum(r["n"] for r in results.values()),
    }
    return results, pooled


def load_queue():
    with open(QUEUE_PATH) as f:
        data = json.load(f)
    triads = data["triads"] if isinstance(data, dict) and "triads" in data else data
    # index by frozenset of the 3 keys for fast lookup regardless of order
    by_triad = {}
    for entry in triads:
        key = frozenset([entry["player_a_key"], entry["player_b_key"], entry["decoy_key"]])
        by_triad[key] = entry
    return by_triad, data.get("queue_version") if isinstance(data, dict) else None


def load_lineage():
    with open(LINEAGE_PATH) as f:
        return json.load(f)["players"]


def normalize_name(s):
    import re
    return re.sub(r"\s+", " ", re.sub(r"[.'\u2019-]", "", s.strip().lower()))


def parse_votes(path):
    """Reads either a CSV or an xlsx export -- same raw shape ktc_pipeline.py consumes."""
    if path.endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(path)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        header = rows[0]
        return [dict(zip(header, r)) for r in rows[1:]]
    else:
        with open(path) as f:
            return list(csv.DictReader(f))


def analyze(votes, queue_by_triad, lineage):
    by_voter_ratio, by_voter_diff = {}, {}
    by_triad_ratio, by_triad_diff = {}, {}
    matched = 0

    # Rich decoy-failure QC, per external review point 3: don't just
    # count failures, break them down by decoy player / triad / voter /
    # position so a systemic problem (one decoy that keeps getting
    # picked, one voter who never cuts decoys, decoy logic broken for a
    # specific position) is visible rather than buried in one number.
    decoy_failures = []
    decoy_failure_by_player = {}
    decoy_failure_by_triad = {}
    decoy_failure_by_voter = {}
    decoy_failure_by_position = {}

    for row in votes:
        keep, trade, cut = row.get("keep"), row.get("trade"), row.get("cut")
        if not (keep and trade and cut):
            continue
        keys = [normalize_name(x) for x in (keep, trade, cut)]
        triad_key = frozenset(keys)
        entry = queue_by_triad.get(triad_key)
        if not entry:
            continue
        matched += 1

        a, b, decoy = entry["player_a_key"], entry["player_b_key"], entry["decoy_key"]
        queue_id = entry.get("queue_id", triad_key)
        keep_n, trade_n, cut_n = normalize_name(keep), normalize_name(trade), normalize_name(cut)
        voter = str(row.get("voter_roster_id", "unknown"))

        if cut_n != decoy:
            decoy_failures.append({"queue_id": queue_id, "decoy": decoy, "voter": voter,
                                    "actual_cut": cut_n})
            decoy_failure_by_player[decoy] = decoy_failure_by_player.get(decoy, 0) + 1
            decoy_failure_by_triad[queue_id] = decoy_failure_by_triad.get(queue_id, 0) + 1
            decoy_failure_by_voter[voter] = decoy_failure_by_voter.get(voter, 0) + 1
            decoy_pos = lineage.get(decoy, {}).get("pos", "unknown")
            decoy_failure_by_position[decoy_pos] = decoy_failure_by_position.get(decoy_pos, 0) + 1
            continue  # decoy wasn't actually cut -- this vote's a/b signal is contaminated, exclude from scoring

        # a_won means "a" was preferred over "b" -- keep beats trade beats
        # cut, so whichever of a/b is 'keep' won.
        a_won = (keep_n == a)

        pa, pb = lineage.get(a), lineage.get(b)
        if not pa or not pb or pa.get("combined") is None or pb.get("combined") is None:
            continue
        if not pa.get("baseline_used") or not pb.get("baseline_used"):
            continue

        ratio_a = pa["combined"] / pa["baseline_used"]
        ratio_b = pb["combined"] / pb["baseline_used"]
        diff_a = pa["combined"] - pa["baseline_used"]
        diff_b = pb["combined"] - pb["baseline_used"]

        by_voter_ratio.setdefault(voter, []).append((ratio_a - ratio_b, a_won))
        by_voter_diff.setdefault(voter, []).append((diff_a - diff_b, a_won))
        by_triad_ratio.setdefault(queue_id, []).append((ratio_a - ratio_b, a_won))
        by_triad_diff.setdefault(queue_id, []).append((diff_a - diff_b, a_won))

    qc = {
        "total_decoy_failures": len(decoy_failures),
        "by_player": dict(sorted(decoy_failure_by_player.items(), key=lambda kv: -kv[1])),
        "by_triad": dict(sorted(decoy_failure_by_triad.items(), key=lambda kv: -kv[1])),
        "by_voter": dict(sorted(decoy_failure_by_voter.items(), key=lambda kv: -kv[1])),
        "by_position": dict(sorted(decoy_failure_by_position.items(), key=lambda kv: -kv[1])),
        "raw_failures": decoy_failures,
    }
    return by_voter_ratio, by_voter_diff, by_triad_ratio, by_triad_diff, matched, qc


def run_selftest():
    print("Running self-test on synthetic data with a KNOWN better formula...")

    # Construct synthetic voters whose real choices follow "ratio" value
    # differences closely (small noise), while "differential" differences
    # are scrambled (near-random relative to real outcomes) -- ratio
    # SHOULD win decisively on log loss.
    import random
    rng = random.Random(7)
    by_voter_ratio = {}
    by_voter_diff = {}
    for voter in range(1, 9):
        obs_r, obs_d = [], []
        for _ in range(15):
            true_ratio_diff = rng.uniform(-2, 2)
            a_won = (true_ratio_diff + rng.gauss(0, 0.3)) > 0  # noisy but real signal
            obs_r.append((true_ratio_diff, a_won))
            obs_d.append((rng.uniform(-2, 2), a_won))  # unrelated to outcome
        by_voter_ratio[voter] = obs_r
        by_voter_diff[voter] = obs_d

    results_r, pooled_r = leave_one_voter_out(by_voter_ratio)
    results_d, pooled_d = leave_one_voter_out(by_voter_diff)

    print(f"  synthetic ratio (real signal) mean log loss: {pooled_r['mean_log_loss']}")
    print(f"  synthetic differential (noise) mean log loss: {pooled_d['mean_log_loss']}")
    assert pooled_r["mean_log_loss"] < pooled_d["mean_log_loss"], \
        f"expected the real-signal formula to win on log loss, got ratio={pooled_r['mean_log_loss']} vs diff={pooled_d['mean_log_loss']}"
    print("  Leave-one-voter-out correctly identifies the formula with real predictive signal -- OK")

    # logistic/log_loss sanity: perfect separation should give near-zero loss
    perfect = [(5.0, True), (-5.0, False), (5.0, True), (-5.0, False)]
    scale = fit_scale(perfect)
    ll = log_loss(perfect, scale)
    assert ll < 0.1, f"expected near-zero log loss on perfectly-separable synthetic data, got {ll}"
    print(f"  Perfectly-separable synthetic data gives near-zero log loss ({ll:.4f}) -- OK")

    # REGRESSION TEST for the 2026-08-27 sign-flip bug: a formula that is
    # PERFECTLY ANTI-correlated with real outcomes (real winner always has
    # the LOWER value under this formula) must be punished with a bad log
    # loss, not rewarded by silently flipping its sign via a negative
    # scale. This is exactly the failure an unconstrained fit produced on
    # real disagreement-queue data before the fix.
    anti_correlated = [(5.0, False), (-5.0, True), (5.0, False), (-5.0, True),
                        (3.0, False), (-3.0, True), (4.0, False), (-4.0, True)]
    scale_anti = fit_scale(anti_correlated)
    ll_anti = log_loss(anti_correlated, scale_anti)
    assert scale_anti == 0.0, f"expected an anti-correlated formula to fit scale=0 (uninformative), got {scale_anti}"
    assert ll_anti > 0.6, f"expected an anti-correlated formula to be punished with log loss near ln(2)=0.693, got {ll_anti}"
    print(f"  Anti-correlated formula correctly punished (scale={scale_anti}, log_loss={ll_anti:.4f}), "
          f"not rescued by a sign flip -- OK")

    # NEW: raw_directional_accuracy should correctly report a formula
    # that's actively backwards (not just uninformative) as <50%.
    raw_acc = raw_directional_accuracy(anti_correlated)
    assert raw_acc is not None and raw_acc < 0.1, \
        f"expected raw directional accuracy near 0 for a perfectly anti-correlated formula, got {raw_acc}"
    print(f"  raw_directional_accuracy correctly reports 'actively backwards' ({raw_acc:.2f}), "
          f"distinct from the flattened scale=0 result -- OK")

    # NEW: leave_one_triad_out should, like leave_one_voter_out, identify
    # a formula with real signal over one that's pure noise, when the
    # SAME triad's votes never leak into its own held-out test fold.
    rng2 = random.Random(11)
    by_triad_signal = {}
    by_triad_noise = {}
    for triad_id in range(1, 11):
        obs_signal, obs_noise = [], []
        for _ in range(5):
            true_diff = rng2.uniform(-2, 2)
            a_won = (true_diff + rng2.gauss(0, 0.3)) > 0
            obs_signal.append((true_diff, a_won))
            obs_noise.append((rng2.uniform(-2, 2), a_won))
        by_triad_signal[triad_id] = obs_signal
        by_triad_noise[triad_id] = obs_noise
    _, triad_pooled_signal = leave_one_triad_out(by_triad_signal)
    _, triad_pooled_noise = leave_one_triad_out(by_triad_noise)
    assert triad_pooled_signal["mean_log_loss"] < triad_pooled_noise["mean_log_loss"], \
        (f"expected the real-signal formula to win leave-one-triad-out, got "
         f"signal={triad_pooled_signal['mean_log_loss']} vs noise={triad_pooled_noise['mean_log_loss']}")
    print(f"  leave_one_triad_out correctly identifies real signal ({triad_pooled_signal['mean_log_loss']}) "
          f"over noise ({triad_pooled_noise['mean_log_loss']}) -- OK")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        if len(sys.argv) < 3:
            return

    args = [a for a in sys.argv[1:] if a != "--selftest"]

    if not os.path.exists(QUEUE_PATH) or not os.path.exists(LINEAGE_PATH):
        print(f"ERROR: need both {QUEUE_PATH} and {LINEAGE_PATH} to exist.")
        sys.exit(1)

    if args:
        votes_path = args[0]
        print(f"Using local votes export: {votes_path}")
        votes = parse_votes(votes_path)
    else:
        raw = fetch_votes_live()
        votes = apply_daily_cap(raw)

    queue_by_triad, queue_version = load_queue()
    lineage = load_lineage()
    print(f"Loaded {len(votes)} raw votes, {len(queue_by_triad)} frozen queue triads (version {queue_version}).")

    by_voter_ratio, by_voter_diff, by_triad_ratio, by_triad_diff, matched, qc = analyze(votes, queue_by_triad, lineage)
    print(f"Matched {matched} votes to the validation queue "
          f"({qc['total_decoy_failures']} had an unexpected decoy pick and were excluded from scoring).")

    n_usable = sum(len(v) for v in by_voter_ratio.values())
    n_voters = len(by_voter_ratio)
    n_triads_represented = len(by_triad_ratio)
    print(f"Usable observations: {n_usable} across {n_voters} voters, "
          f"{n_triads_represented}/{len(queue_by_triad)} triads represented.")

    md_lines = ["# KTC Validation Queue Analysis\n",
                f"Queue version: {queue_version}. Matched {matched} votes "
                f"({qc['total_decoy_failures']} excluded for an unexpected decoy pick). "
                f"{n_usable} usable observations across {n_voters} voters, "
                f"{n_triads_represented}/{len(queue_by_triad)} triads represented.\n"]

    # Sample-size guidance per external review point 10 -- three explicit
    # tiers rather than one magic N, since with only 12 voters, voter and
    # triad COVERAGE matter as much as raw observation count.
    if n_voters < 6 or n_triads_represented < 20 or n_usable < 40:
        tier = "EARLY READ -- not actionable yet"
    elif n_voters < 8 or n_triads_represented < 25 or n_usable < 60:
        tier = "SERIOUS EVIDENCE -- worth evaluating stability, not yet a final call"
    else:
        tier = "POTENTIALLY ACTIONABLE -- check the full pre-registered criteria before acting"
    print(f"\nSample-size tier: {tier}")
    md_lines.append(f"\n**Sample-size tier: {tier}**\n")

    # ---- Raw directional accuracy (scale-independent diagnostic) ----
    all_ratio_obs = [obs for v in by_voter_ratio.values() for obs in v]
    all_diff_obs = [obs for v in by_voter_diff.values() for obs in v]
    raw_acc_ratio = raw_directional_accuracy(all_ratio_obs)
    raw_acc_diff = raw_directional_accuracy(all_diff_obs)
    print(f"\nRaw directional accuracy (scale-independent, no fitting) -- "
          f"ratio: {raw_acc_ratio}, differential: {raw_acc_diff}")
    md_lines.append("\n## Raw directional accuracy (scale-independent diagnostic)\n")
    md_lines.append("Distinguishes \"uninformative\" from \"actively backwards\" -- unlike the "
                     "constrained log-loss scale, this uses each formula's own natural sign with "
                     "no fitting at all.\n")
    md_lines.append(f"- Ratio: **{raw_acc_ratio}**")
    md_lines.append(f"- Differential: **{raw_acc_diff}**")
    for name, acc in (("ratio", raw_acc_ratio), ("differential", raw_acc_diff)):
        if acc is not None and acc < 0.45:
            md_lines.append(f"  - **{name} is actively backwards** ({acc:.0%} correct, worse than a coin flip), "
                             f"not merely uninformative.")

    # ---- Primary: leave-one-voter-out ----
    results_r, pooled_r = leave_one_voter_out(by_voter_ratio)
    results_d, pooled_d = leave_one_voter_out(by_voter_diff)

    print("\n=== RATIO formula (leave-one-voter-out, PRIMARY) ===")
    print(f"  mean log loss: {pooled_r['mean_log_loss']}  mean Brier: {pooled_r['mean_brier']}  "
          f"mean accuracy: {pooled_r['mean_accuracy']}  (n_voters={pooled_r['n_voters']}, n_obs={pooled_r['n_total_observations']})")
    print("\n=== DIFFERENTIAL formula (leave-one-voter-out, PRIMARY) ===")
    print(f"  mean log loss: {pooled_d['mean_log_loss']}  mean Brier: {pooled_d['mean_brier']}  "
          f"mean accuracy: {pooled_d['mean_accuracy']}  (n_voters={pooled_d['n_voters']}, n_obs={pooled_d['n_total_observations']})")

    loov_winner = None
    if pooled_r["mean_log_loss"] is not None and pooled_d["mean_log_loss"] is not None:
        loov_winner = "ratio" if pooled_r["mean_log_loss"] < pooled_d["mean_log_loss"] else "differential"
        print(f"\nLOOV winner by mean log loss: {loov_winner}")

    md_lines.append("\n## Primary: leave-one-voter-out\n")
    md_lines.append("| Formula | Mean log loss | Mean Brier | Mean accuracy | Voters | Observations |")
    md_lines.append("|---|---|---|---|---|---|")
    md_lines.append(f"| ratio | {pooled_r['mean_log_loss']} | {pooled_r['mean_brier']} | "
                     f"{pooled_r['mean_accuracy']} | {pooled_r['n_voters']} | {pooled_r['n_total_observations']} |")
    md_lines.append(f"| differential | {pooled_d['mean_log_loss']} | {pooled_d['mean_brier']} | "
                     f"{pooled_d['mean_accuracy']} | {pooled_d['n_voters']} | {pooled_d['n_total_observations']} |")
    if loov_winner:
        md_lines.append(f"\n**LOOV winner by mean log loss: {loov_winner}**")

    # ---- Robustness: leave-one-triad-out ----
    triad_results_r, triad_pooled_r = leave_one_triad_out(by_triad_ratio)
    triad_results_d, triad_pooled_d = leave_one_triad_out(by_triad_diff)

    print("\n=== RATIO formula (leave-one-TRIAD-out, robustness check) ===")
    print(f"  mean log loss: {triad_pooled_r['mean_log_loss']}  (n_triads={triad_pooled_r['n_triads']})")
    print("\n=== DIFFERENTIAL formula (leave-one-TRIAD-out, robustness check) ===")
    print(f"  mean log loss: {triad_pooled_d['mean_log_loss']}  (n_triads={triad_pooled_d['n_triads']})")

    triad_winner = None
    if triad_pooled_r["mean_log_loss"] is not None and triad_pooled_d["mean_log_loss"] is not None:
        triad_winner = "ratio" if triad_pooled_r["mean_log_loss"] < triad_pooled_d["mean_log_loss"] else "differential"
        print(f"Leave-one-triad-out winner by mean log loss: {triad_winner}")

    agree = (loov_winner is not None and triad_winner is not None and loov_winner == triad_winner)
    print(f"\nLOOV and leave-one-triad-out AGREE on winner: {agree}")
    if not agree and loov_winner is not None and triad_winner is not None:
        print("  WARNING: the two validation schemes disagree -- the result may be voter-specific "
              "or matchup-specific rather than broadly generalizable. Do not treat as settled.")

    md_lines.append("\n## Robustness: leave-one-triad-out\n")
    md_lines.append("Distinguishes \"generalizes to a new person\" (LOOV) from \"generalizes to a new "
                     "matchup\" -- since the same triad answered by several voters lets LOOV see that "
                     "exact matchup during training even when a different voter is held out.\n")
    md_lines.append("| Formula | Mean log loss | Triads |")
    md_lines.append("|---|---|---|")
    md_lines.append(f"| ratio | {triad_pooled_r['mean_log_loss']} | {triad_pooled_r['n_triads']} |")
    md_lines.append(f"| differential | {triad_pooled_d['mean_log_loss']} | {triad_pooled_d['n_triads']} |")
    md_lines.append(f"\n**LOOV and leave-one-triad-out agree on winner: {agree}**")
    if not agree and loov_winner is not None and triad_winner is not None:
        md_lines.append("\n**WARNING: the two schemes disagree -- treat the result as voter-specific or "
                         "matchup-specific, not broadly generalizable, until this resolves.**")

    # ---- Decoy QC (retained, not deleted; excluded from scoring above) ----
    md_lines.append("\n## Decoy failure QC (excluded from formula scoring, retained for validation-design review)\n")
    if matched:
        pct = 100 * qc["total_decoy_failures"] / matched
        md_lines.append(f"Total decoy failures: {qc['total_decoy_failures']} out of {matched} matched votes ({pct:.1f}%).\n")
    else:
        md_lines.append("No matched votes yet.\n")
    if qc["by_player"]:
        md_lines.append("**By decoy player** (a player repeatedly surviving as keep/trade instead of being "
                         "cut may indicate a stale/mispriced value, not just voter idiosyncrasy):")
        for player, count in qc["by_player"].items():
            md_lines.append(f"  - {player}: {count}")
    if qc["by_voter"]:
        md_lines.append("\n**By voter:**")
        for voter, count in qc["by_voter"].items():
            md_lines.append(f"  - voter {voter}: {count}")
    if qc["by_position"]:
        md_lines.append("\n**By decoy position:**")
        for pos, count in qc["by_position"].items():
            md_lines.append(f"  - {pos}: {count}")

    md_lines.append("\n## Per-voter breakdown (ratio formula)\n")
    md_lines.append("| Voter | Log loss | Brier | Accuracy | N |")
    md_lines.append("|---|---|---|---|---|")
    for voter, r in results_r.items():
        md_lines.append(f"| {voter} | {r['log_loss']} | {r['brier']} | {r['accuracy']} | {r['n']} |")

    md_lines.append("\n## Per-voter breakdown (differential formula)\n")
    md_lines.append("| Voter | Log loss | Brier | Accuracy | N |")
    md_lines.append("|---|---|---|---|---|")
    for voter, r in results_d.items():
        md_lines.append(f"| {voter} | {r['log_loss']} | {r['brier']} | {r['accuracy']} | {r['n']} |")

    with open(OUT_PATH, "w") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

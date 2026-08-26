#!/usr/bin/env python3
"""
scripts/ktc_validation_queue_generator.py

Builds a frozen pool of offense-only (QB/RB/WR/TE) KTC vote triads,
deliberately selected because the two candidate scarcity formulas --
ratio (combined/baseline, the live formula) and differential
(combined-baseline, the alternative under consideration) -- disagree on
which of two players is more valuable. This is Bucket C from the
external methodology review: passive random voting was empirically shown
this session to produce ZERO usable disagreements in 39 real all-offense
pairwise observations (0.15-1.55 scale ratio formula and the raw
differential rarely flip ordering on real production data), so waiting
for organic votes to stumble into disagreements isn't viable. Targeted
selection is.

WHY OFFENSE-ONLY: this whole validation exists to resolve ratio-vs-
differential using data untouched by the 2026-08-2X POSITION_WEIGHT
calibration (which used DL/LB/DB votes specifically). Every player in
every generated triad is QB/RB/WR/TE, so every edge in the resulting
vote is clean by construction -- no edge is extracted from a triad that
also touched IDP, unlike the earlier weaker "offense edge from a mixed
triad" tier this project explicitly decided not to trust as primary
evidence.

WHY FROZEN, NOT ADAPTIVE: both formulas are evaluated ONCE against the
current prod_mult_pipeline_output.json snapshot and the resulting queue
is fixed. It must NOT be regenerated based on how people vote -- doing
so would make the test adaptive to its own results, defeating the point
of a held-out validation set. Regenerate this queue only when the
underlying production data itself refreshes (e.g., a new
prod_mult_pipeline.py run), never in response to vote outcomes.

TRIAD CONSTRUCTION: for each selected "disagreement pair" (P1, P2) where
ratio and differential disagree on which is more valuable, a third
"decoy" player is added -- someone both formulas agree is clearly worse
than both P1 and P2. This keeps the vote's real information content
concentrated in the keep-vs-trade choice between P1/P2, rather than
introducing a second, harder-to-interpret three-way disagreement.

DISAGREEMENT STRENGTH: pairs are ranked by how confidently the two
formulas disagree (normalized margin under each formula), not just
whether they disagree at all -- a vote where ratio says "clearly A" and
differential says "clearly B" is far more informative than one where
both formulas are near a coin flip.

REQUIRES NO NETWORK ACCESS -- uses only prod_mult_pipeline_output.json,
already produced by prod_mult_pipeline.py.

USAGE: python3 scripts/ktc_validation_queue_generator.py
Add --selftest to sanity-check the disagreement-detection and decoy-
selection logic against synthetic data before trusting real output.

OUTPUT: scripts/ktc_validation_queue.json -- a list of triads, each
{player_a, player_b, decoy, disagreement_strength}, ready to be pasted
into index.html as the KTC_VALIDATION_QUEUE constant.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LINEAGE_PATH = os.path.join(SCRIPT_DIR, "prod_mult_pipeline_output.json")
OUT_PATH = os.path.join(SCRIPT_DIR, "ktc_validation_queue.json")

OFFENSE_POSITIONS = {"QB", "RB", "WR", "TE"}
QUEUE_SIZE = 60  # deliberately more than needed for a while -- see main() for why
QUEUE_VERSION = "V1"


def compute_values(players):
    """Returns {key: {name, pos, ratio, differential}} for every offense
    player with real combined/baseline data."""
    out = {}
    for key, p in players.items():
        if p["pos"] not in OFFENSE_POSITIONS:
            continue
        combined = p.get("combined")
        baseline = p.get("baseline_used")
        if combined is None or not baseline:
            continue
        out[key] = {
            "name": p["player"],
            "pos": p["pos"],
            "ratio": combined / baseline,
            "differential": combined - baseline,
        }
    return out


def normalize(values, field):
    """
    Percentile-rank normalize one formula's values to [0,1] so margins
    are comparable across formulas that live on completely different raw
    scales (ratio is unitless around 1.0; differential is in raw points).

    2026-08-27 CHANGE (per external review): replaced min-max with
    percentile-rank. Min-max is sensitive to one extreme outlier pair --
    a single enormous gap compresses every other pair's normalized
    margin toward zero, distorting what "confident disagreement" means
    for everyone else. Percentile rank (this player's value's rank among
    all offense players, as a fraction of the population) is far less
    sensitive to a single extreme value and is more directly
    interpretable ("87th percentile confidence") when reviewing the
    generated queue.
    """
    keys = list(values.keys())
    ordered = sorted(keys, key=lambda k: values[k][field])
    n = len(ordered)
    return {k: i / (n - 1) if n > 1 else 0.5 for i, k in enumerate(ordered)}


# Two disagreement strata, per external review point 4 -- a fixed "both
# formulas must be confident" threshold only selects strong-vs-strong
# disagreements and could miss an informative asymmetric class (one
# formula strongly prefers A, the other only mildly prefers B), which is
# itself informative about whether a formula's boundary is misplaced.
STRONG_STRONG_MARGIN = 0.15   # both formulas must clear this percentile-rank margin
ASYMMETRIC_STRONG_MARGIN = 0.20   # the confident formula must clear this
ASYMMETRIC_WEAK_MARGIN = 0.03     # the other formula only needs to clear this (not a tie)
STRONG_STRONG_SHARE = 0.70    # target mix -- see build_queue()


def find_disagreement_pairs(values, tier):
    """
    Returns [(key_a, key_b, strength, tier)] for every pair where ratio
    and differential disagree on ordering, filtered to the requested
    tier ('strong' = both formulas confident, 'asymmetric' = one
    confident and one only mild), sorted by strength descending.
    """
    keys = list(values.keys())
    ratio_norm = normalize(values, "ratio")
    diff_norm = normalize(values, "differential")

    pairs = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            ratio_margin = ratio_norm[a] - ratio_norm[b]
            diff_margin = diff_norm[a] - diff_norm[b]
            if ratio_margin == 0 or diff_margin == 0:
                continue
            ratio_says_a = ratio_margin > 0
            diff_says_a = diff_margin > 0
            if ratio_says_a == diff_says_a:
                continue  # formulas agree -- not a useful validation matchup

            r, d = abs(ratio_margin), abs(diff_margin)
            strength = min(r, d)
            if tier == "strong" and (r >= STRONG_STRONG_MARGIN and d >= STRONG_STRONG_MARGIN):
                pairs.append((a, b, strength, "strong"))
            elif tier == "asymmetric" and (max(r, d) >= ASYMMETRIC_STRONG_MARGIN and min(r, d) >= ASYMMETRIC_WEAK_MARGIN
                                            and min(r, d) < STRONG_STRONG_MARGIN):
                pairs.append((a, b, strength, "asymmetric"))
    pairs.sort(key=lambda t: -t[2])
    return pairs


def find_decoy(values, exclude_keys, ratio_norm, diff_norm, ceiling):
    """
    A decoy must be clearly worse than `ceiling` (the lower of the two
    disagreement-pair values) under BOTH formulas, so both formulas agree
    it's the weakest of the three -- keeps the real informative choice
    concentrated in keep-vs-trade between the disagreement pair, not
    diluted by a second real three-way disagreement.

    2026-08-27 FIX: `exclude_keys` must include every player already used
    ANYWHERE in the queue so far (not just the current pair) -- the first
    version only excluded the current pair, so the single best generic
    "obviously worse than everyone" decoy candidate got reused across
    many different triads (one real run picked the same decoy 7 times).
    Not a correctness bug for any individual triad's validity, but real
    voter-experience repetition, and it interacts badly with the app's
    existing "don't show a voter the same player too soon" exclusion --
    reusing a decoy across many triads effectively shrinks how many of
    those triads a given voter can actually see in a row.
    """
    candidates = [
        k for k in values
        if k not in exclude_keys and ratio_norm[k] < ceiling[0] - 0.05 and diff_norm[k] < ceiling[1] - 0.05
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda k: -(ratio_norm[k] + diff_norm[k]))
    return candidates[0]


def build_queue(values, size=QUEUE_SIZE):
    """
    Blends two disagreement strata -- ~70% strong/strong (both formulas
    confident), ~30% asymmetric (one confident, one only mild) -- per
    external review point 4, so the resulting queue can reveal whether a
    result only shows up for extreme disagreements or holds more broadly.
    """
    ratio_norm = normalize(values, "ratio")
    diff_norm = normalize(values, "differential")
    strong_pairs = find_disagreement_pairs(values, "strong")
    asym_pairs = find_disagreement_pairs(values, "asymmetric")

    target_strong = round(size * STRONG_STRONG_SHARE)
    target_asym = size - target_strong

    queue = []
    used_players = set()

    def fill_from(pairs, target):
        added = 0
        for a, b, strength, tier in pairs:
            if added >= target:
                break
            if a in used_players or b in used_players:
                continue
            ceiling = (min(ratio_norm[a], ratio_norm[b]), min(diff_norm[a], diff_norm[b]))
            decoy = find_decoy(values, used_players | {a, b}, ratio_norm, diff_norm, ceiling)
            if decoy is None:
                continue
            queue.append({
                "queue_id": f"vq1_{len(queue)+1:03d}",
                "player_a": values[a]["name"], "player_a_key": a,
                "player_b": values[b]["name"], "player_b_key": b,
                "decoy": values[decoy]["name"], "decoy_key": decoy,
                "disagreement_strength": round(strength, 4),
                "tier": tier,
            })
            used_players.update({a, b, decoy})
            added += 1

    fill_from(strong_pairs, target_strong)
    fill_from(asym_pairs, target_asym)
    return queue


def run_selftest():
    print("Running self-test on synthetic data...")

    # Construct players where ratio and differential are DESIGNED to
    # disagree: A has a high ratio but low differential; B has a low
    # ratio but high differential. C is clearly worse on both.
    synthetic = {
        "a1": {"player": "Player A", "pos": "WR", "combined": 20, "baseline_used": 10},   # ratio=2.0, diff=10
        "a2": {"player": "Player B", "pos": "RB", "combined": 100, "baseline_used": 60},  # ratio=1.67, diff=40
        "a3": {"player": "Player C", "pos": "TE", "combined": 5, "baseline_used": 8},     # ratio=0.625, diff=-3
    }
    values = compute_values(synthetic)
    assert len(values) == 3
    # ratio order: a1(2.0) > a2(1.67) > a3(0.625)
    # differential order: a2(40) > a1(10) > a3(-3)
    # so a1 vs a2 SHOULD be a disagreement pair (ratio says a1, diff says a2)
    pairs_strong = find_disagreement_pairs(values, "strong")
    pairs_asym = find_disagreement_pairs(values, "asymmetric")
    all_pairs = pairs_strong + pairs_asym
    pair_keys = [(p[0], p[1]) for p in all_pairs]
    assert ("a1", "a2") in pair_keys or ("a2", "a1") in pair_keys, \
        f"expected a1/a2 to be detected as a disagreement pair, got {all_pairs}"
    print("  Disagreement pair (designed conflict between ratio and differential) correctly detected -- OK")

    queue = build_queue(values, size=5)
    assert len(queue) >= 1, "expected at least one triad from the synthetic disagreement"
    triad = queue[0]
    assert triad["decoy_key"] == "a3", f"expected a3 (clearly worst on both formulas) as decoy, got {triad['decoy_key']}"
    print("  Decoy selection correctly picks the player clearly worse on BOTH formulas -- OK")
    assert triad["queue_id"] == "vq1_001", f"expected sequential queue_id, got {triad['queue_id']}"
    print("  queue_id assigned correctly -- OK")

    # Sanity: a case with NO disagreement should produce zero pairs.
    no_conflict = {
        "b1": {"player": "X", "pos": "QB", "combined": 30, "baseline_used": 10},
        "b2": {"player": "Y", "pos": "QB", "combined": 20, "baseline_used": 10},
    }
    values2 = compute_values(no_conflict)
    pairs2 = find_disagreement_pairs(values2, "strong") + find_disagreement_pairs(values2, "asymmetric")
    assert len(pairs2) == 0, f"expected no disagreement pairs when one player dominates on both formulas, got {pairs2}"
    print("  No false-positive disagreement when one player dominates both formulas -- OK")

    print("Self-test passed.\n")


def main():
    if "--selftest" in sys.argv:
        run_selftest()

    if not os.path.exists(LINEAGE_PATH):
        print(f"ERROR: need {LINEAGE_PATH} to exist. Run prod_mult_pipeline.py first.")
        sys.exit(1)

    with open(LINEAGE_PATH) as f:
        lineage = json.load(f)

    values = compute_values(lineage["players"])
    print(f"Offense players with real combined/baseline data: {len(values)}")

    # QUEUE_SIZE deliberately larger than what gets shown soon -- the
    # client-side widget will draw randomly from this pool and skip
    # entries where any player isn't currently eligible for a given
    # voter (on their own roster, or recently shown), so a bigger pool
    # means fewer "nothing eligible, fall through to normal sampling"
    # misses in practice.
    queue = build_queue(values, size=QUEUE_SIZE)
    print(f"Generated {len(queue)} disagreement triads (target was {QUEUE_SIZE}).")
    n_strong = sum(1 for t in queue if t["tier"] == "strong")
    n_asym = sum(1 for t in queue if t["tier"] == "asymmetric")
    print(f"  {n_strong} strong/strong, {n_asym} asymmetric.")
    if queue:
        print(f"Strongest disagreement: {queue[0]['player_a']} vs {queue[0]['player_b']} "
              f"(decoy: {queue[0]['decoy']}), strength={queue[0]['disagreement_strength']}")
        print(f"Weakest included disagreement: {queue[-1]['player_a']} vs {queue[-1]['player_b']} "
              f"(decoy: {queue[-1]['decoy']}), strength={queue[-1]['disagreement_strength']}")

    # Version/expiration metadata, per external review point 6 -- fantasy
    # player values move (injuries, role changes, trades), so a frozen
    # queue needs a documented freeze date and an intended collection
    # window, not an implicit "forever." Close this campaign after the
    # window, analyze it, and generate a fresh V2 from updated player
    # data if more evidence is still needed -- never regenerate V1 itself
    # in response to votes.
    import datetime
    output = {
        "queue_version": QUEUE_VERSION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "formula_versions": {"ratio": "combined/baseline_used", "differential": "combined-baseline_used"},
        "player_values_frozen_from": LINEAGE_PATH,
        "intended_collection_window_weeks": 3,
        "triads": queue,
    }

    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

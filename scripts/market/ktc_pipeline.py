"""
KTC vote aggregation pipeline -- pulls Keep/Trade/Cut votes from the Google
Sheet the Apps Script write endpoint (ktc_vote_collector.gs) feeds, turns
each 3-way vote into 3 pairwise records, enforces the per-voter daily cap,
and fits a Bradley-Terry model to produce real, aggregated player and
position-level ratings.

WHY BRADLEY-TERRY, NOT RAW WIN RATE: raw win-rate treats "beat a scrub" and
"beat an elite player" as identical evidence, and can't produce a coherent
ranking from real human non-transitivity (A beats B, B beats C, C beats A
is a genuine possible outcome of honest small-sample voting). Bradley-Terry
fits a latent strength score per player such that the model's implied
P(i beats j) = s_i / (s_i + s_j) best explains the real observed outcomes --
standard, well-established method for exactly this kind of sparse pairwise
comparison problem, not a novel invention for this project.

WHY THE PER-VOTER CAP IS ENFORCED HERE, NOT JUST CLIENT-SIDE: the widget in
index.html has its own soft daily-limit UX (via localStorage) so people
aren't encouraged to spam pointlessly, but that's just UX -- someone could
clear their browser storage and keep voting. This script is the real
enforcement boundary: it only COUNTS the first N votes per roster_id per
UTC day when building the pairwise dataset, regardless of how many were
actually submitted. That's what keeps one highly engaged voter from
dominating a 12-person dataset the way no single voter can dominate KTC's
real scale.

MINIMUM SAMPLE SIZE: any position-vs-position comparison with fewer than
MIN_PAIRWISE_FOR_SIGNAL real pairwise observations gets explicitly flagged
as "not enough data yet" in the output rather than silently reported
alongside comparisons that do have real support. With only 12 possible
voters, this will take real time to accumulate -- that's an honest
constraint of the problem, not something to paper over.

USAGE: python3 scripts/market/ktc_pipeline.py
Requires: requests (pip install requests --break-system-packages)

HONESTY NOTE, same as every other new script this session: the Bradley-
Terry (Zermelo) iteration below is a standard, well-documented algorithm,
implemented carefully, but has not been run against a real populated
dataset yet since none exists until the Apps Script is deployed and real
votes come in. Sanity-check the first real run's output -- e.g. confirm a
Bradley-Terry rating agrees with your own read on a comparison you already
have a strong opinion about -- before trusting the aggregate numbers.
"""

import csv
import io
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPTS_DIR)

from utilities.generate_player_positions import build_player_position_lookup

# Set this to the published-CSV URL of the "votes" tab after following the
# "Publish to web" step in ktc_vote_collector.gs's setup instructions.
# Format is normally:
# https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTuKORGumlKJmUmBdeNWPstkj8VRjPoVkylbqHv1KqwoyziJYOUlkZUKRsSxzB3qHXmyjjLpGpH6W03/pub?gid=458294959&single=true&output=csv"

# Per Section 4 of the design doc -- caps how many of one voter's votes get
# COUNTED per day, regardless of how many were submitted.
MAX_VOTES_PER_VOTER_PER_DAY = 20

# Per Section 6 of the design doc -- don't report a position-pair
# comparison as a real signal until it has this many real pairwise
# observations behind it.
MIN_PAIRWISE_FOR_SIGNAL = 30

POS_BUCKET = {
    "DE": "DL", "DT": "DL", "DL": "DL", "OLB": "LB", "ILB": "LB", "LB": "LB",
    "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB",
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE",
}


def fetch_votes():
    print("Fetching votes from Sheet...")
    resp = requests.get(SHEET_CSV_URL, timeout=30)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    print(f"  {len(rows)} raw vote rows fetched")
    return rows


def apply_daily_cap(rows):
    """
    Keeps only the first MAX_VOTES_PER_VOTER_PER_DAY rows per
    (voter_roster_id, UTC date) pair, in the order they were submitted.
    This is the real enforcement of the per-voter cap -- see the module
    docstring for why it lives here rather than only client-side.
    """
    counts = defaultdict(int)
    kept = []
    dropped = 0
    for row in rows:
        try:
            day = row["timestamp"][:10]  # ISO date portion
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


def decompose_to_pairwise(rows):
    """
    Each 3-way Keep/Trade/Cut vote becomes 3 (winner, loser) pairs:
    keep beats trade, keep beats cut, trade beats cut.
    """
    pairs = []
    for row in rows:
        keep, trade, cut = row.get("keep"), row.get("trade"), row.get("cut")
        if not (keep and trade and cut):
            continue
        pairs.append((keep, trade))
        pairs.append((keep, cut))
        pairs.append((trade, cut))
    return pairs


def bradley_terry(pairs, iterations=200, tol=1e-6, reg_games=2):
    """
    Zermelo's iterative algorithm for fitting Bradley-Terry strengths from
    a list of (winner, loser) pairs. Returns {player: strength}, normalized
    so the geometric mean of all strengths is 1.0 (an arbitrary but
    standard normalization -- what matters is relative strength between
    players, not the absolute scale).

    REGULARIZATION, added 2026-08-20 after a real failure: with only 36
    votes spread across ~90 distinct players, the comparison graph is
    sparse and mostly disconnected -- most players appear in only 1-2
    pairwise observations, many never compared against each other at all.
    Unregularized Bradley-Terry MLE genuinely diverges in this situation --
    confirmed by reproducing it with synthetic sparse data (max rating hit
    67 million, min rating near zero, dozens of players collapsed to
    identical tied values) -- not a coding typo, a real, well-known
    limitation of the raw method at low/sparse sample sizes.

    Fix: every real player gets `reg_games` virtual wins AND `reg_games`
    virtual losses against a fixed anchor pseudo-player whose strength
    never updates (always 1.0). This is standard regularized/Bayesian
    Bradley-Terry, not a hack -- the anchor gives every player, however
    sparse their real data, something fixed to be measured against, which
    is exactly what prevents the runaway divergence. With reg_games=2 and
    real vote volume eventually reaching 30+ observations per comparison
    (the project's own trust threshold), the anchor's influence becomes
    small relative to real data -- it matters most, and is needed most,
    precisely when real data is thin, which is the correct behavior.
    """
    if not pairs:
        # Real edge case, not just theoretical -- hit this exact case on
        # 2026-08-20 when the Sheet fetch returned zero rows despite real
        # votes existing (a separate real problem, not this function's
        # fault -- see fetch_votes()). Failing gracefully here means a
        # fetch problem shows up as an honest "no data" result instead of
        # crashing the whole job with a ZeroDivisionError.
        return {}

    ANCHOR = '__anchor__'
    real_players = set()
    for w, l in pairs:
        real_players.add(w)
        real_players.add(l)
    real_players = list(real_players)

    win_counts = defaultdict(lambda: defaultdict(int))
    for w, l in pairs:
        win_counts[w][l] += 1
    # Ghost games -- see docstring. Symmetric: every real player "beats"
    # and "loses to" the anchor the same number of times, so this has no
    # directional bias, only a grounding effect.
    for p in real_players:
        win_counts[p][ANCHOR] += reg_games
        win_counts[ANCHOR][p] += reg_games

    all_nodes = real_players + [ANCHOR]
    s = {p: 1.0 for p in all_nodes}

    for _ in range(iterations):
        s_new = {ANCHOR: 1.0}  # anchor's strength is fixed, never updated
        for i in real_players:
            wins_i = sum(win_counts[i].values())
            if wins_i == 0:
                s_new[i] = s[i] * 0.5
                continue
            denom = 0.0
            for j in all_nodes:
                if j == i:
                    continue
                n_ij = win_counts[i][j] + win_counts[j][i]
                if n_ij == 0:
                    continue
                denom += n_ij / (s[i] + s[j])
            s_new[i] = wins_i / denom if denom > 0 else s[i]

        # normalize real players to geometric-mean-1 each iteration to
        # prevent drift -- anchor is excluded from this since its strength
        # is fixed by definition, not something to be renormalized
        import math
        log_mean = sum(math.log(max(s_new[p], 1e-9)) for p in real_players) / len(real_players)
        scale = math.exp(-log_mean)
        for p in real_players:
            s_new[p] *= scale

        max_delta = max(abs(s_new[p] - s[p]) for p in real_players)
        s = s_new
        if max_delta < tol:
            break

    return {p: s[p] for p in real_players}


def is_league_voter(voter_id):
    """
    Real league members submit their numeric Sleeper roster_id. Guest
    voters (people outside the league, added 2026-08-20) submit an
    'ext_xxxxxxxx' identifier instead -- see ktcGuestId() in index.html.
    No schema change needed for this; the existing voter_roster_id column
    already holds whichever shape of string applies.
    """
    return str(voter_id).isdigit()


def build_ratings_summary(rows, pos_lookup, label):
    """
    Runs the full pipeline (decompose -> Bradley-Terry -> position
    aggregation) for one set of vote rows, returning a summary dict.
    Factored out so league-only and all-voters-combined can be computed
    identically rather than duplicating this logic twice with a risk of
    the two versions drifting apart.
    """
    pairs = decompose_to_pairwise(rows)
    strengths = bradley_terry(pairs)

    position_pairwise_count = defaultdict(int)
    # ADDED (2026-08-27): same-position pairwise counts, tracked
    # separately from the cross-position ones below. The original version
    # of this function explicitly skipped same-position pairs (`pw !=
    # pl`) because it was built to answer "is DL worth more than WR,"
    # never "how much real within-position signal exists for QB." That
    # second question turned out to matter for a real follow-up (testing
    # ratio-vs-differential scarcity formulas against real market value
    # WITHIN each offensive position) and there was no way to answer it
    # without this -- the individual player_ratings below are informed by
    # all pairwise data through the full Bradley-Terry graph regardless,
    # but knowing the DIRECT same-position sample size is what tells you
    # whether to trust a within-position comparison specifically.
    same_position_pairwise_count = defaultdict(int)
    for w, l in pairs:
        pw = POS_BUCKET.get(pos_lookup.get(w))
        pl = POS_BUCKET.get(pos_lookup.get(l))
        if pw and pl and pw != pl:
            key = tuple(sorted([pw, pl]))
            position_pairwise_count[key] += 1
        elif pw and pl and pw == pl:
            same_position_pairwise_count[pw] += 1

    position_avg_strength = defaultdict(list)
    unmapped_position_players = []
    for player, strength in strengths.items():
        pos = POS_BUCKET.get(pos_lookup.get(player))
        if pos:
            position_avg_strength[pos].append(strength)
        else:
            unmapped_position_players.append(player)
    position_summary = {pos: round(sum(v)/len(v), 4) for pos, v in position_avg_strength.items()}

    position_pair_signal = {
        f"{pa}_vs_{pb}": {
            "pairwise_observations": count,
            "enough_data": count >= MIN_PAIRWISE_FOR_SIGNAL,
        }
        for (pa, pb), count in position_pairwise_count.items()
    }
    same_position_signal = {
        pos: {"pairwise_observations": count, "enough_data": count >= MIN_PAIRWISE_FOR_SIGNAL}
        for pos, count in same_position_pairwise_count.items()
    }

    print(f"\n=== {label}: {len(rows)} votes, {len(pairs)} pairwise observations ===")
    for pair, info in position_pair_signal.items():
        flag = "OK" if info["enough_data"] else "NOT ENOUGH DATA YET"
        print(f"  {pair}: {info['pairwise_observations']} observations -- {flag}")
    print("  -- same-position (within-position) pairwise counts --")
    for pos, info in sorted(same_position_signal.items(), key=lambda kv: -kv[1]["pairwise_observations"]):
        flag = "OK" if info["enough_data"] else "NOT ENOUGH DATA YET"
        print(f"  {pos} vs {pos}: {info['pairwise_observations']} observations -- {flag}")

    if unmapped_position_players:
        print(
            f"  NOTE: {len(unmapped_position_players)} rated player(s) have no current canonical "
            "position lookup and are omitted from position aggregation: "
            + ", ".join(sorted(unmapped_position_players)[:12])
            + (" ..." if len(unmapped_position_players) > 12 else "")
        )

    return {
        "votes_counted": len(rows),
        "pairwise_observations": len(pairs),
        "player_ratings": {k: round(v, 4) for k, v in sorted(strengths.items(), key=lambda kv: -kv[1])},
        "position_avg_rating": position_summary,
        "position_pair_sample_sizes": position_pair_signal,
        "same_position_pairwise_sample_sizes": same_position_signal,
        "unmapped_position_players": sorted(unmapped_position_players),
    }


def main():
    rows = fetch_votes()
    rows = apply_daily_cap(rows)
    print(f"  {len(rows)} votes counted after daily cap")

    league_rows = [r for r in rows if is_league_voter(r.get("voter_roster_id", ""))]
    guest_rows = [r for r in rows if not is_league_voter(r.get("voter_roster_id", ""))]
    print(f"  {len(league_rows)} from league members, {len(guest_rows)} from guests")

    # Real per-voter share, not a guess -- added 2026-08-20 after a real
    # question about whether one dominant voter (even an honest one)
    # undermines the whole point of aggregating multiple people's
    # judgment. The self-interest guardrail protects against bias; it does
    # nothing about sample diversity, which is a separate, real concern.
    voter_counts = defaultdict(int)
    for r in league_rows:
        voter_counts[r.get("voter_roster_id", "unknown")] += 1
    total_league = len(league_rows)
    voter_share = {
        voter: {"votes": count, "share_pct": round(100 * count / total_league, 1)}
        for voter, count in sorted(voter_counts.items(), key=lambda kv: -kv[1])
    } if total_league else {}

    pos_lookup = {}
    pos_lookup_path = os.path.join(SCRIPTS_DIR, "artifacts", "generated", "player_positions.json")
    if os.path.exists(pos_lookup_path):
        with open(pos_lookup_path) as f:
            pos_lookup = json.load(f)
        expected_positions = build_player_position_lookup()
        if pos_lookup != expected_positions:
            missing = sorted(set(expected_positions) - set(pos_lookup))
            stale = sorted(set(pos_lookup) - set(expected_positions))
            changed = sorted(
                k for k in set(pos_lookup) & set(expected_positions)
                if pos_lookup[k] != expected_positions[k]
            )
            raise RuntimeError(
                "player_positions.json is stale relative to canonical PLAYER_DB/alias data. "
                "Run `python3 scripts/utilities/generate_player_positions.py` first. "
                f"missing={len(missing)}, stale={len(stale)}, changed={len(changed)}"
            )
    else:
        raise RuntimeError(
            "player_positions.json not found. Run "
            "`python3 scripts/utilities/generate_player_positions.py` before KTC aggregation."
        )

    league_only = build_ratings_summary(league_rows, pos_lookup, "League members only")
    all_combined = build_ratings_summary(rows, pos_lookup, "All voters (league + guests)")

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_votes_counted": len(rows),
        "league_votes": len(league_rows),
        "guest_votes": len(guest_rows),
        "voter_share_within_league": voter_share,
        # Two separate results, never silently blended into one number --
        # see keep-trade-cut-design.md for why guest and league opinion
        # shouldn't be assumed equivalent. Compare the two to see whether
        # outside dynasty opinion actually agrees with this league's.
        "league_only": league_only,
        "all_voters_combined": all_combined,
    }

    with open(os.path.join(SCRIPTS_DIR, "ktc_ratings.json"), "w") as f:
        json.dump(output, f, indent=2)

    print("\n=== Voter share within league votes ===")
    for voter, info in voter_share.items():
        print(f"  roster_id {voter}: {info['votes']} votes ({info['share_pct']}% of league total)")

    print("\nWrote ktc_ratings.json")


if __name__ == "__main__":
    main()

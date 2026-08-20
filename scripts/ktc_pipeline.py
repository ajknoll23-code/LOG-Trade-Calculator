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

USAGE: python3 ktc_pipeline.py
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
from collections import defaultdict
from datetime import datetime

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Set this to the published-CSV URL of the "votes" tab after following the
# "Publish to web" step in ktc_vote_collector.gs's setup instructions.
# Format is normally:
# https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}
SHEET_CSV_URL = "PASTE_YOUR_PUBLISHED_SHEET_CSV_URL_HERE"

# Per Section 4 of the design doc -- caps how many of one voter's votes get
# COUNTED per day, regardless of how many were submitted.
MAX_VOTES_PER_VOTER_PER_DAY = 10

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


def bradley_terry(pairs, iterations=200, tol=1e-6):
    """
    Zermelo's iterative algorithm for fitting Bradley-Terry strengths from
    a list of (winner, loser) pairs. Returns {player: strength}, normalized
    so the geometric mean of all strengths is 1.0 (an arbitrary but
    standard normalization -- what matters is relative strength between
    players, not the absolute scale).
    """
    players = set()
    for w, l in pairs:
        players.add(w)
        players.add(l)
    players = list(players)

    win_counts = defaultdict(lambda: defaultdict(int))
    for w, l in pairs:
        win_counts[w][l] += 1

    s = {p: 1.0 for p in players}

    for _ in range(iterations):
        s_new = {}
        max_delta = 0.0
        for i in players:
            wins_i = sum(win_counts[i].values())
            if wins_i == 0:
                s_new[i] = s[i] * 0.5  # decay players who never won a single pairing
                continue
            denom = 0.0
            for j in players:
                if j == i:
                    continue
                n_ij = win_counts[i][j] + win_counts[j][i]
                if n_ij == 0:
                    continue
                denom += n_ij / (s[i] + s[j])
            if denom > 0:
                s_new[i] = wins_i / denom
            else:
                s_new[i] = s[i]
        # normalize to geometric-mean-1 each iteration to prevent drift
        import math
        log_mean = sum(math.log(max(v, 1e-9)) for v in s_new.values()) / len(s_new)
        scale = math.exp(-log_mean)
        s_new = {k: v * scale for k, v in s_new.items()}

        max_delta = max(abs(s_new[p] - s[p]) for p in players)
        s = s_new
        if max_delta < tol:
            break

    return s


def main():
    rows = fetch_votes()
    rows = apply_daily_cap(rows)
    print(f"  {len(rows)} votes counted after daily cap")

    pairs = decompose_to_pairwise(rows)
    print(f"  {len(pairs)} pairwise observations from those votes")

    strengths = bradley_terry(pairs)

    # Position-level aggregation, with the honest minimum-sample gate.
    # Needs an external pos-lookup -- reuses PLAYER_DB's shape by expecting
    # a player_positions.json file (player_key -> pos) to sit alongside
    # this script; that file should just be a plain export of PLAYER_DB
    # from index.html, refreshed whenever PLAYER_DB changes.
    pos_lookup = {}
    pos_lookup_path = os.path.join(SCRIPT_DIR, "player_positions.json")
    if os.path.exists(pos_lookup_path):
        pos_lookup = json.load(open(pos_lookup_path))
    else:
        print("  NOTE: player_positions.json not found -- position-level "
              "aggregation skipped, only per-player ratings will be output.")

    position_pairwise_count = defaultdict(int)
    for w, l in pairs:
        pw = POS_BUCKET.get(pos_lookup.get(w))
        pl = POS_BUCKET.get(pos_lookup.get(l))
        if pw and pl and pw != pl:
            key = tuple(sorted([pw, pl]))
            position_pairwise_count[key] += 1

    position_avg_strength = defaultdict(list)
    for player, strength in strengths.items():
        pos = POS_BUCKET.get(pos_lookup.get(player))
        if pos:
            position_avg_strength[pos].append(strength)

    position_summary = {}
    for pos, vals in position_avg_strength.items():
        position_summary[pos] = round(sum(vals) / len(vals), 4)

    position_pair_signal = {}
    for (pa, pb), count in position_pairwise_count.items():
        position_pair_signal[f"{pa}_vs_{pb}"] = {
            "pairwise_observations": count,
            "enough_data": count >= MIN_PAIRWISE_FOR_SIGNAL,
        }

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_votes_counted": len(rows),
        "total_pairwise_observations": len(pairs),
        "player_ratings": {k: round(v, 4) for k, v in sorted(strengths.items(), key=lambda kv: -kv[1])},
        "position_avg_rating": position_summary,
        "position_pair_sample_sizes": position_pair_signal,
    }

    with open(os.path.join(SCRIPT_DIR, "ktc_ratings.json"), "w") as f:
        json.dump(output, f, indent=2)

    print("\n=== Position-pair sample sizes (real signal requires "
          f"{MIN_PAIRWISE_FOR_SIGNAL}+ observations) ===")
    for pair, info in position_pair_signal.items():
        flag = "OK" if info["enough_data"] else "NOT ENOUGH DATA YET"
        print(f"  {pair}: {info['pairwise_observations']} observations -- {flag}")

    print("\nWrote ktc_ratings.json")


if __name__ == "__main__":
    main()

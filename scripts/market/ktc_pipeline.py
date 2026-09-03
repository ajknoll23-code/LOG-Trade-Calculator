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
actually submitted.

VOTER-BALANCED RESEARCH VIEW (added 2026-09-03): league participation is
structurally uneven, so raw league ratings remain preserved exactly as the
primary historical series while a second, explicitly separate research-only
rating limits any one league member to VOTER_BALANCE_EFFECTIVE_VOTE_CAP
effective lifetime ballots. No ballots are deleted: when a voter exceeds the
cap, every one of that voter's counted ballots receives the same fractional
weight so their total effective contribution equals the cap.

This does NOT change Market Value V1. build_market_value.py continues to read
league_only.player_ratings until a separate review explicitly changes that
consumer.

MINIMUM SAMPLE SIZE: any position-vs-position comparison with fewer than
MIN_PAIRWISE_FOR_SIGNAL real pairwise observations gets explicitly flagged
as "not enough data yet" in the output rather than silently reported
alongside comparisons that do have real support.

USAGE:
  python3 scripts/market/ktc_pipeline.py
  python3 scripts/market/ktc_pipeline.py --selftest

Requires: requests (pip install requests --break-system-packages)
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

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTuKORGumlKJmUmBdeNWPstkj8VRjPoVkylbqHv1KqwoyziJYOUlkZUKRsSxzB3qHXmyjjLpGpH6W03/pub?gid=458294959&single=true&output=csv"

MAX_VOTES_PER_VOTER_PER_DAY = 20
MIN_PAIRWISE_FOR_SIGNAL = 30

# Research-only voter-balance policy.
#
# A voter with <=30 counted league ballots retains weight 1.0 per ballot.
# A voter with >30 counted league ballots keeps ALL ballots, but each receives
# weight 30 / raw_vote_count. Thus 260 ballots still inform ordering/coverage,
# but carry the same total effective mass as 30 ballots rather than 260.
VOTER_BALANCE_EFFECTIVE_VOTE_CAP = 30.0
VOTER_BALANCE_METHOD = "per_voter_total_effective_vote_cap_v1"

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
    """
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
    so the geometric mean of all strengths is 1.0.

    Each real player receives symmetric virtual wins/losses against a fixed
    anchor to stabilize sparse/disconnected comparison graphs.
    """
    if not pairs:
        return {}

    ANCHOR = "__anchor__"
    real_players = set()
    for w, l in pairs:
        real_players.add(w)
        real_players.add(l)
    real_players = list(real_players)

    win_counts = defaultdict(lambda: defaultdict(int))
    for w, l in pairs:
        win_counts[w][l] += 1
    for p in real_players:
        win_counts[p][ANCHOR] += reg_games
        win_counts[ANCHOR][p] += reg_games

    all_nodes = real_players + [ANCHOR]
    s = {p: 1.0 for p in all_nodes}

    for _ in range(iterations):
        s_new = {ANCHOR: 1.0}
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


def weighted_bradley_terry(weighted_pairs, iterations=200, tol=1e-6, reg_games=2.0):
    """
    Weighted counterpart to bradley_terry().

    weighted_pairs contains (winner, loser, weight). The same Zermelo update
    is used, but pairwise wins/games are floating-point masses. Symmetric
    anchor regularization is intentionally unchanged so the voter-balanced
    view differs only because of voter contribution weighting.
    """
    if not weighted_pairs:
        return {}

    ANCHOR = "__anchor__"
    real_players = set()
    for w, l, weight in weighted_pairs:
        if weight <= 0:
            continue
        real_players.add(w)
        real_players.add(l)
    if not real_players:
        return {}
    real_players = list(real_players)

    win_counts = defaultdict(lambda: defaultdict(float))
    for w, l, weight in weighted_pairs:
        weight = float(weight)
        if weight > 0:
            win_counts[w][l] += weight

    for p in real_players:
        win_counts[p][ANCHOR] += float(reg_games)
        win_counts[ANCHOR][p] += float(reg_games)

    all_nodes = real_players + [ANCHOR]
    s = {p: 1.0 for p in all_nodes}

    for _ in range(iterations):
        s_new = {ANCHOR: 1.0}
        for i in real_players:
            wins_i = sum(win_counts[i].values())
            if wins_i <= 0:
                s_new[i] = s[i] * 0.5
                continue
            denom = 0.0
            for j in all_nodes:
                if j == i:
                    continue
                n_ij = win_counts[i][j] + win_counts[j][i]
                if n_ij <= 0:
                    continue
                denom += n_ij / (s[i] + s[j])
            s_new[i] = wins_i / denom if denom > 0 else s[i]

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
    voters use an ext_... identifier.
    """
    return str(voter_id).isdigit()


def build_ratings_summary(rows, pos_lookup, label):
    """
    Existing raw-count summary. This function intentionally preserves the
    pre-V2 behavior used by league_only and all_voters_combined.
    """
    pairs = decompose_to_pairwise(rows)
    strengths = bradley_terry(pairs)

    position_pairwise_count = defaultdict(int)
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
    position_summary = {pos: round(sum(v) / len(v), 4) for pos, v in position_avg_strength.items()}

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
    for pos, info in sorted(
        same_position_signal.items(),
        key=lambda kv: -kv[1]["pairwise_observations"],
    ):
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
        "player_ratings": {
            k: round(v, 4)
            for k, v in sorted(strengths.items(), key=lambda kv: -kv[1])
        },
        "position_avg_rating": position_summary,
        "position_pair_sample_sizes": position_pair_signal,
        "same_position_pairwise_sample_sizes": same_position_signal,
        "unmapped_position_players": sorted(unmapped_position_players),
    }


def build_voter_balance_weights(rows):
    """
    Return per-voter raw counts, common ballot weight, effective vote mass,
    and raw/effective shares.

    All rows remain in the dataset. A voter above the cap is down-weighted
    uniformly across that voter's full counted history.
    """
    counts = defaultdict(int)
    for row in rows:
        voter = str(row.get("voter_roster_id", "unknown"))
        counts[voter] += 1

    effective_by_voter = {}
    total_raw = sum(counts.values())
    for voter, count in counts.items():
        ballot_weight = (
            1.0
            if count <= VOTER_BALANCE_EFFECTIVE_VOTE_CAP
            else VOTER_BALANCE_EFFECTIVE_VOTE_CAP / float(count)
        )
        effective_by_voter[voter] = {
            "raw_votes": count,
            "raw_share_pct": round(100.0 * count / total_raw, 2) if total_raw else 0.0,
            "ballot_weight": ballot_weight,
            "effective_votes": count * ballot_weight,
        }

    total_effective = sum(row["effective_votes"] for row in effective_by_voter.values())
    for row in effective_by_voter.values():
        row["effective_share_pct"] = (
            round(100.0 * row["effective_votes"] / total_effective, 2)
            if total_effective
            else 0.0
        )
        row["ballot_weight"] = round(row["ballot_weight"], 8)
        row["effective_votes"] = round(row["effective_votes"], 6)

    return dict(
        sorted(
            effective_by_voter.items(),
            key=lambda kv: (-kv[1]["effective_votes"], -kv[1]["raw_votes"], kv[0]),
        )
    )


def build_voter_balanced_summary(rows, pos_lookup, label):
    """
    Research-only league summary with capped total effective contribution
    per voter. Raw observations are preserved separately from effective mass.
    """
    voter_weights = build_voter_balance_weights(rows)

    weighted_pairs = []
    raw_pairs = []
    position_pairwise_count = defaultdict(int)
    position_pairwise_mass = defaultdict(float)
    position_pair_voters = defaultdict(set)
    same_position_pairwise_count = defaultdict(int)
    same_position_pairwise_mass = defaultdict(float)
    same_position_voters = defaultdict(set)

    for row in rows:
        voter = str(row.get("voter_roster_id", "unknown"))
        weight_info = voter_weights.get(voter)
        if not weight_info:
            continue
        weight = float(weight_info["ballot_weight"])

        keep, trade, cut = row.get("keep"), row.get("trade"), row.get("cut")
        if not (keep and trade and cut):
            continue

        row_pairs = ((keep, trade), (keep, cut), (trade, cut))
        for w, l in row_pairs:
            raw_pairs.append((w, l))
            weighted_pairs.append((w, l, weight))

            pw = POS_BUCKET.get(pos_lookup.get(w))
            pl = POS_BUCKET.get(pos_lookup.get(l))
            if pw and pl and pw != pl:
                key = tuple(sorted([pw, pl]))
                position_pairwise_count[key] += 1
                position_pairwise_mass[key] += weight
                position_pair_voters[key].add(voter)
            elif pw and pl and pw == pl:
                same_position_pairwise_count[pw] += 1
                same_position_pairwise_mass[pw] += weight
                same_position_voters[pw].add(voter)

    strengths = weighted_bradley_terry(weighted_pairs)

    position_avg_strength = defaultdict(list)
    unmapped_position_players = []
    for player, strength in strengths.items():
        pos = POS_BUCKET.get(pos_lookup.get(player))
        if pos:
            position_avg_strength[pos].append(strength)
        else:
            unmapped_position_players.append(player)
    position_summary = {
        pos: round(sum(values) / len(values), 4)
        for pos, values in position_avg_strength.items()
    }

    position_pair_signal = {
        f"{pa}_vs_{pb}": {
            "raw_pairwise_observations": position_pairwise_count[(pa, pb)],
            "effective_pairwise_mass": round(position_pairwise_mass[(pa, pb)], 4),
            "distinct_voters": len(position_pair_voters[(pa, pb)]),
            "enough_raw_data": position_pairwise_count[(pa, pb)] >= MIN_PAIRWISE_FOR_SIGNAL,
        }
        for pa, pb in position_pairwise_count
    }
    same_position_signal = {
        pos: {
            "raw_pairwise_observations": count,
            "effective_pairwise_mass": round(same_position_pairwise_mass[pos], 4),
            "distinct_voters": len(same_position_voters[pos]),
            "enough_raw_data": count >= MIN_PAIRWISE_FOR_SIGNAL,
        }
        for pos, count in same_position_pairwise_count.items()
    }

    effective_votes = sum(float(v["effective_votes"]) for v in voter_weights.values())
    effective_pairwise_mass = sum(weight for _, _, weight in weighted_pairs)

    print(
        f"\n=== {label}: {len(rows)} raw votes -> "
        f"{effective_votes:.1f} effective votes; "
        f"{len(raw_pairs)} raw pairs -> {effective_pairwise_mass:.1f} effective pair mass ==="
    )
    for voter, info in voter_weights.items():
        print(
            f"  roster_id {voter}: raw={info['raw_votes']} "
            f"weight={info['ballot_weight']:.6f} "
            f"effective={info['effective_votes']:.1f} "
            f"effective_share={info['effective_share_pct']:.1f}%"
        )

    return {
        "status": "research_only_not_consumed_by_market_value_v1",
        "method": VOTER_BALANCE_METHOD,
        "effective_vote_cap_per_voter": VOTER_BALANCE_EFFECTIVE_VOTE_CAP,
        "weight_formula": "min(1.0, effective_vote_cap_per_voter / raw_votes_by_voter)",
        "raw_votes_counted": len(rows),
        "effective_votes": round(effective_votes, 6),
        "raw_pairwise_observations": len(raw_pairs),
        "effective_pairwise_mass": round(effective_pairwise_mass, 6),
        "voter_weights": voter_weights,
        "player_ratings": {
            k: round(v, 4)
            for k, v in sorted(strengths.items(), key=lambda kv: -kv[1])
        },
        "position_avg_rating": position_summary,
        "position_pair_sample_sizes": position_pair_signal,
        "same_position_pairwise_sample_sizes": same_position_signal,
        "unmapped_position_players": sorted(unmapped_position_players),
    }


def run_selftest():
    raw_pairs = [
        ("alpha", "beta"),
        ("alpha", "gamma"),
        ("beta", "gamma"),
        ("gamma", "alpha"),
    ]
    raw = bradley_terry(raw_pairs)
    weighted_unit = weighted_bradley_terry([(w, l, 1.0) for w, l in raw_pairs])
    assert set(raw) == set(weighted_unit)
    for player in raw:
        assert abs(raw[player] - weighted_unit[player]) < 1e-10, (
            player, raw[player], weighted_unit[player]
        )

    rows = []
    for i in range(100):
        rows.append({
            "timestamp": f"2026-09-{1 + (i // 20):02d}T00:00:00Z",
            "voter_roster_id": "4",
            "keep": "alpha",
            "trade": "beta",
            "cut": "gamma",
        })
    for i in range(20):
        rows.append({
            "timestamp": f"2026-09-{1 + (i // 20):02d}T00:00:00Z",
            "voter_roster_id": "8",
            "keep": "gamma",
            "trade": "beta",
            "cut": "alpha",
        })

    weights = build_voter_balance_weights(rows)
    assert abs(weights["4"]["effective_votes"] - 30.0) < 1e-9
    assert abs(weights["8"]["effective_votes"] - 20.0) < 1e-9
    assert abs(weights["4"]["ballot_weight"] - 0.3) < 1e-9
    assert weights["4"]["effective_share_pct"] == 60.0
    assert weights["8"]["effective_share_pct"] == 40.0

    pos_lookup = {"alpha": "QB", "beta": "RB", "gamma": "WR"}
    summary = build_voter_balanced_summary(rows, pos_lookup, "Synthetic voter-balanced self-test")
    assert summary["raw_votes_counted"] == 120
    assert abs(summary["effective_votes"] - 50.0) < 1e-9
    assert summary["raw_pairwise_observations"] == 360
    assert abs(summary["effective_pairwise_mass"] - 150.0) < 1e-8
    assert summary["status"] == "research_only_not_consumed_by_market_value_v1"
    assert set(summary["player_ratings"]) == {"alpha", "beta", "gamma"}

    print(
        "KTC voter-balance self-test passed: unit-weight parity, all-ballot "
        "retention, 30-effective-vote cap, effective-share accounting, and "
        "weighted Bradley-Terry output."
    )


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return

    rows = fetch_votes()
    rows = apply_daily_cap(rows)
    print(f"  {len(rows)} votes counted after daily cap")

    league_rows = [r for r in rows if is_league_voter(r.get("voter_roster_id", ""))]
    guest_rows = [r for r in rows if not is_league_voter(r.get("voter_roster_id", ""))]
    print(f"  {len(league_rows)} from league members, {len(guest_rows)} from guests")

    voter_counts = defaultdict(int)
    for r in league_rows:
        voter_counts[r.get("voter_roster_id", "unknown")] += 1
    total_league = len(league_rows)
    voter_share = {
        voter: {"votes": count, "share_pct": round(100 * count / total_league, 1)}
        for voter, count in sorted(voter_counts.items(), key=lambda kv: -kv[1])
    } if total_league else {}

    pos_lookup = {}
    pos_lookup_path = os.path.join(
        SCRIPTS_DIR, "artifacts", "generated", "player_positions.json"
    )
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

    league_only = build_ratings_summary(
        league_rows, pos_lookup, "League members only"
    )
    league_voter_balanced = build_voter_balanced_summary(
        league_rows, pos_lookup, "League members voter-balanced (research only)"
    )
    all_combined = build_ratings_summary(
        rows, pos_lookup, "All voters (league + guests)"
    )

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_votes_counted": len(rows),
        "league_votes": len(league_rows),
        "guest_votes": len(guest_rows),
        "voter_share_within_league": voter_share,
        "voter_balance_policy": {
            "status": "research_only",
            "method": VOTER_BALANCE_METHOD,
            "effective_vote_cap_per_voter": VOTER_BALANCE_EFFECTIVE_VOTE_CAP,
            "all_ballots_retained": True,
            "market_value_v1_consumer_changed": False,
            "description": (
                "League voters above the cap retain every counted ballot, but "
                "all of that voter's ballots are uniformly down-weighted so "
                "the voter's total effective ballot mass equals the cap."
            ),
        },
        "league_only": league_only,
        "league_voter_balanced": league_voter_balanced,
        "all_voters_combined": all_combined,
    }

    with open(
        os.path.join(SCRIPTS_DIR, "artifacts", "generated", "ktc_ratings.json"),
        "w",
    ) as f:
        json.dump(output, f, indent=2)

    print("\n=== Voter share within league votes ===")
    for voter, info in voter_share.items():
        print(
            f"  roster_id {voter}: {info['votes']} votes "
            f"({info['share_pct']}% of league total)"
        )

    print("\nWrote scripts/artifacts/generated/ktc_ratings.json")


if __name__ == "__main__":
    main()

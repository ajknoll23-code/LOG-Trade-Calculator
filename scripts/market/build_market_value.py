#!/usr/bin/env python3
"""
build_market_value.py

Build a SEPARATE league-market value layer for Trade Desk.

This script does NOT change playerValue(), POSITION_WEIGHT, production
multipliers, age curves, trade totals, verdicts, or Team Utility.

Why a calibration layer is necessary
------------------------------------
scripts/market/ktc_pipeline.py fits regularized Bradley-Terry strengths and
normalizes them to geometric-mean 1.0. That absolute scale is intentionally
arbitrary; only relative ordering/ratios are meaningful. A rating of 4.2 is
therefore not natively comparable with a Trade Desk point value such as 7,500.

Market Value V1 uses rank-preserving quantile calibration:
  1. Resolve league-only KTC player ratings to canonical PLAYER_DB keys.
  2. Rank those players by LEAGUE market rating.
  3. Take the current fundamental Trade Desk values for that exact same
     covered-player universe and sort only the VALUE DISTRIBUTION.
  4. Assign the highest market-ranked player the highest point-scale slot,
     second highest the second slot, etc. Tied market ratings receive the
     average of the corresponding slots.

Result:
- Market ordering is determined by league votes.
- The point scale is familiar/additive Trade Desk units.
- The market distribution cannot inflate/deflate the whole player pool.
- Fundamental values remain unchanged and are preserved alongside market
  values so disagreement is explicit.
- The market signal is NEVER silently blended into the fundamental formula.

This is a MARKET OPINION layer, not fundamental truth. League-only votes are
used; guest votes are deliberately excluded. Current voter concentration and
position-level direct sample sizes are preserved as interpretation guardrails.

Outputs
-------
scripts/artifacts/generated/market_values.json
scripts/artifacts/reports/market_value_report.md

Usage
-----
python3 scripts/market/build_market_value.py
python3 scripts/market/build_market_value.py --write
python3 scripts/market/build_market_value.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = REPO_ROOT / "scripts" / "validation"
if str(VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATION_DIR))

import snapshot_values
from evaluate_market_history import build_alias_index, normalize_name

INDEX_PATH = REPO_ROOT / "index.html"
KTC_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "ktc_ratings.json"
OUTPUT_JSON = REPO_ROOT / "scripts" / "artifacts" / "generated" / "market_values.json"
OUTPUT_MD = REPO_ROOT / "scripts" / "artifacts" / "reports" / "market_value_report.md"

METHOD_VERSION = "league-market-value-v1"
SCALE_SEMANTICS = "league_rank_quantile_mapped_to_trade_desk_points_v1"
MIN_RESOLVED_MARKET_PLAYERS = 100

POLICY = {
    "method_version": METHOD_VERSION,
    "market_source": "ktc_ratings.json::league_only.player_ratings",
    "guest_vote_policy": "excluded from Market Value V1",
    "scale_semantics": SCALE_SEMANTICS,
    "ordering": "league-only regularized Bradley-Terry rating descending",
    "point_scale": (
        "quantile map market ordering onto the current fundamental-value distribution "
        "of the exact same market-covered player universe"
    ),
    "ties": "equal market ratings receive the mean of the corresponding point-scale slots",
    "fundamental_formula_policy": "never modified or blended by this artifact",
    "team_utility_policy": "never modified or blended by this artifact",
    "quality_guardrails": (
        "preserve league vote counts, dominant-voter share, and direct same-position "
        "pairwise sample size; no probability/confidence claim"
    ),
}

POLICY_SHA256 = hashlib.sha256(
    json.dumps(POLICY, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Required market-value input is missing: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON: {path.relative_to(REPO_ROOT)}: {exc}") from exc


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dominant_voter_share_pct(ktc: dict[str, Any]) -> float | None:
    values = []
    for row in (ktc.get("voter_share_within_league") or {}).values():
        try:
            values.append(float((row or {}).get("share_pct")))
        except (TypeError, ValueError):
            continue
    return max(values) if values else None


def resolve_league_ratings(
    model_values: dict[str, dict[str, Any]],
    raw_ratings: dict[str, Any],
) -> tuple[dict[str, float], dict[str, Any]]:
    aliases = build_alias_index(list(model_values))
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unmatched = []
    ambiguous = []

    for raw_name, raw_rating in raw_ratings.items():
        try:
            rating = float(raw_rating)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(rating) or rating <= 0:
            continue

        norm = normalize_name(str(raw_name))
        options = aliases.get(norm, [])
        unique = {}
        for model_key, priority, method in options:
            unique[(model_key, priority, method)] = (model_key, priority, method)
        options = list(unique.values())

        if not options:
            unmatched.append({
                "raw_name": str(raw_name),
                "normalized_name": norm,
                "rating": rating,
            })
            continue

        best_priority = min(item[1] for item in options)
        best = [item for item in options if item[1] == best_priority]
        target_keys = sorted({item[0] for item in best})

        if len(target_keys) != 1:
            ambiguous.append({
                "raw_name": str(raw_name),
                "normalized_name": norm,
                "rating": rating,
                "candidate_model_keys": target_keys,
            })
            continue

        key = target_keys[0]
        method = sorted(item[2] for item in best if item[0] == key)[0]
        candidates[key].append({
            "raw_name": str(raw_name),
            "rating": rating,
            "priority": best_priority,
            "method": method,
        })

    resolved = {}
    methods = defaultdict(int)
    duplicates = []

    for key, rows in candidates.items():
        rows = sorted(rows, key=lambda row: (row["priority"], normalize_name(row["raw_name"])))
        retained = rows[0]
        resolved[key] = float(retained["rating"])
        methods[retained["method"]] += 1
        if len(rows) > 1:
            duplicates.append({
                "model_key": key,
                "retained": retained,
                "discarded": rows[1:],
            })

    return resolved, {
        "raw_rating_count": len(raw_ratings),
        "resolved_model_player_count": len(resolved),
        "coverage_pct_of_model": round(100.0 * len(resolved) / max(1, len(model_values)), 2),
        "match_method_counts": dict(sorted(methods.items())),
        "unmatched_market_names": unmatched,
        "ambiguous_market_names": ambiguous,
        "duplicate_aliases_resolving_to_same_model_player": duplicates,
    }


def quantile_calibrate(
    model_values: dict[str, dict[str, Any]],
    resolved_ratings: dict[str, float],
) -> dict[str, dict[str, Any]]:
    keys = [
        key for key in resolved_ratings
        if key in model_values and isinstance(model_values[key].get("value"), (int, float))
    ]
    if not keys:
        return {}

    slots = sorted(
        [int(model_values[key]["value"]) for key in keys],
        reverse=True,
    )

    market_groups: dict[float, list[str]] = defaultdict(list)
    for key in keys:
        market_groups[float(resolved_ratings[key])].append(key)

    ordered_groups = sorted(market_groups.items(), key=lambda item: -item[0])
    n = len(keys)
    cursor = 0
    out = {}

    for rating, group_keys in ordered_groups:
        group_keys = sorted(group_keys)
        size = len(group_keys)
        group_slots = slots[cursor:cursor + size]
        calibrated = int(math.floor(sum(group_slots) / size + 0.5))
        first_rank = cursor + 1
        last_rank = cursor + size
        avg_rank = (first_rank + last_rank) / 2.0

        percentile = 1.0 if n == 1 else 1.0 - ((avg_rank - 1.0) / (n - 1.0))

        for key in group_keys:
            fundamental = int(model_values[key]["value"])
            delta = calibrated - fundamental
            out[key] = {
                "pos": model_values[key].get("pos"),
                "fundamental_value": fundamental,
                "market_value": calibrated,
                "market_minus_fundamental": delta,
                "market_minus_fundamental_pct": (
                    round(delta / fundamental, 6) if fundamental > 0 else None
                ),
                "market_rating": round(rating, 6),
                "market_rank": round(avg_rank, 3),
                "market_percentile": round(percentile, 6),
            }

        cursor += size

    return out


def attach_evidence(
    players: dict[str, dict[str, Any]],
    ktc: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    same_pos = ((ktc.get("league_only") or {}).get("same_position_pairwise_sample_sizes") or {})
    dominant = dominant_voter_share_pct(ktc)
    concentrated = bool(dominant is not None and dominant > 50.0)

    out = {}
    for key, row in players.items():
        pos = str(row.get("pos") or "")
        pos_signal = same_pos.get(pos) or {}
        out[key] = {
            **row,
            "evidence": {
                "same_position_pairwise_observations": int(
                    pos_signal.get("pairwise_observations") or 0
                ),
                "same_position_enough_data": bool(pos_signal.get("enough_data")),
                "dominant_voter_share_pct": dominant,
                "dominant_voter_majority_flag": concentrated,
            },
        }
    return out


def validate_payload(payload: dict[str, Any], minimum_players: int = MIN_RESOLVED_MARKET_PLAYERS) -> None:
    if payload.get("schema_version") != 1:
        raise RuntimeError("Unexpected market-value schema version")
    if payload.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Unexpected market-value method version")
    if payload.get("scale_semantics") != SCALE_SEMANTICS:
        raise RuntimeError("Market-value scale semantics drifted")

    players = payload.get("players")
    if not isinstance(players, dict) or len(players) < minimum_players:
        raise RuntimeError(
            f"Resolved market-value player coverage unexpectedly small: "
            f"{len(players) if isinstance(players, dict) else 'invalid'}"
        )

    fundamentals = sorted(row["fundamental_value"] for row in players.values())
    market_values = sorted(row["market_value"] for row in players.values())
    total_drift = abs(sum(fundamentals) - sum(market_values))
    if total_drift > len(players):
        raise RuntimeError(
            f"Market quantile calibration unexpectedly changed aggregate scale: drift={total_drift}"
        )

    ordered = sorted(
        players.items(),
        key=lambda kv: (-kv[1]["market_rating"], kv[0]),
    )
    previous_rating = None
    previous_value = None
    for key, row in ordered:
        rating = row["market_rating"]
        value = row["market_value"]
        if previous_rating is not None and rating < previous_rating and value > previous_value:
            raise RuntimeError(f"Market ordering is not monotonic at {key}")
        previous_rating = rating
        previous_value = value


def build_payload() -> dict[str, Any]:
    cfg = snapshot_values.load_from_html(INDEX_PATH)
    model_values = snapshot_values.compute_all_values(cfg)
    ktc = read_json(KTC_PATH)

    league = ktc.get("league_only") or {}
    raw_ratings = league.get("player_ratings") or {}
    if not isinstance(raw_ratings, dict):
        raise RuntimeError("ktc_ratings.json league_only.player_ratings must be a JSON object")

    resolved, identity_audit = resolve_league_ratings(model_values, raw_ratings)
    calibrated = quantile_calibrate(model_values, resolved)
    players = attach_evidence(calibrated, ktc)

    dominant = dominant_voter_share_pct(ktc)
    payload = {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "scale_semantics": SCALE_SEMANTICS,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "policy": POLICY,
        "policy_sha256": POLICY_SHA256,
        "source_file_sha256": {
            "index_html": sha256_file(INDEX_PATH),
            "ktc_ratings": sha256_file(KTC_PATH),
        },
        "market_quality": {
            "league_votes": int(ktc.get("league_votes") or league.get("votes_counted") or 0),
            "league_pairwise_observations": int(league.get("pairwise_observations") or 0),
            "guest_votes_excluded": int(ktc.get("guest_votes") or 0),
            "dominant_voter_share_pct": dominant,
            "dominant_voter_majority_flag": bool(dominant is not None and dominant > 50.0),
            "interpretation": (
                "Market values reflect league opinion. A dominant-voter majority flag means "
                "the aggregate is currently concentrated and should not be treated as broad consensus."
            ),
        },
        "counts": {
            "fundamental_model_players": len(model_values),
            "raw_league_market_ratings": len(raw_ratings),
            "resolved_market_players": len(players),
            "market_coverage_pct_of_model": round(100.0 * len(players) / max(1, len(model_values)), 2),
        },
        "identity_audit": identity_audit,
        "players": players,
    }
    validate_payload(payload)
    return payload


def render_report(payload: dict[str, Any]) -> str:
    players = payload["players"]
    quality = payload["market_quality"]
    counts = payload["counts"]

    disagreement = sorted(
        players.items(),
        key=lambda kv: (-abs(kv[1]["market_minus_fundamental"]), kv[0]),
    )[:30]

    lines = [
        "# Trade Desk Market Value V1",
        "",
        f"Method: `{METHOD_VERSION}`  ",
        f"Scale semantics: `{SCALE_SEMANTICS}`  ",
        f"Policy SHA256: `{payload['policy_sha256']}`",
        "",
        "## Critical interpretation",
        "",
        "**Market Value is a separate league-opinion lens. It is not the fundamental "
        "player-value formula and it is not blended into Team Utility.**",
        "",
        "The Bradley–Terry rating scale is arbitrary, so V1 preserves the league-vote "
        "ranking and maps that ranking onto the point-value distribution of the exact "
        "same covered players. The point number is therefore a comparable market-equivalent "
        "scale, while the ordering itself comes from league votes.",
        "",
        f"- Fundamental model players: **{counts['fundamental_model_players']}**",
        f"- Market-covered players: **{counts['resolved_market_players']}** "
        f"({counts['market_coverage_pct_of_model']:.1f}%)",
        f"- League votes: **{quality['league_votes']}**",
        f"- League pairwise observations: **{quality['league_pairwise_observations']}**",
        f"- Guest votes excluded: **{quality['guest_votes_excluded']}**",
        f"- Dominant voter share: **{quality['dominant_voter_share_pct']}%**",
        f"- Dominant voter majority flag: **{'YES' if quality['dominant_voter_majority_flag'] else 'NO'}**",
        "",
        "## Largest current Fundamental ↔ Market disagreements",
        "",
        "| Player | Pos | Fundamental | Market | Δ | Market rank | Market pct. | Pos direct pairs |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    for key, row in disagreement:
        e = row["evidence"]
        lines.append(
            f"| {key} | {row['pos']} | {row['fundamental_value']:,} | "
            f"{row['market_value']:,} | {row['market_minus_fundamental']:+,} | "
            f"{row['market_rank']} | {100*row['market_percentile']:.1f}% | "
            f"{e['same_position_pairwise_observations']} |"
        )

    lines.extend([
        "",
        "## Guardrails",
        "",
        "- `league_only.player_ratings` is the only market ordering source.",
        "- Guest votes are not blended into Market Value V1.",
        "- A market value never changes the deployed fundamental value.",
        "- Team Utility remains a separate roster-specific calculation.",
        "- Unrated players have no Market Value V1 rather than receiving an invented estimate.",
        "- Voter concentration and direct positional sample size are carried with the output.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(render_report(payload), encoding="utf-8")
    print(
        f"Market Value V1 written: {OUTPUT_JSON.relative_to(REPO_ROOT)} "
        f"({payload['counts']['resolved_market_players']} players; "
        f"{payload['counts']['market_coverage_pct_of_model']:.1f}% model coverage)"
    )


def run_selftest() -> None:
    model_values = {}
    raw_ratings = {}

    for i in range(120):
        key = f"player {i:03d}"
        model_values[key] = {
            "pos": "WR" if i < 60 else "LB",
            "value": 10000 - i * 50,
        }
        raw_ratings[key] = float(i + 1)

    model_values["michael penix jr"] = {"pos": "QB", "value": 7000}
    raw_ratings["michael penix"] = 500.0

    resolved, audit = resolve_league_ratings(model_values, raw_ratings)
    assert resolved["michael penix jr"] == 500.0
    assert audit["ambiguous_market_names"] == []

    calibrated = quantile_calibrate(model_values, resolved)
    assert calibrated["michael penix jr"]["market_value"] == max(
        row["fundamental_value"] for row in calibrated.values()
    )

    ordered = sorted(calibrated.values(), key=lambda row: -row["market_rating"])
    for prev, cur in zip(ordered, ordered[1:]):
        assert prev["market_value"] >= cur["market_value"]

    assert calibrated["player 000"]["fundamental_value"] == model_values["player 000"]["value"]

    synthetic_ktc = {
        "league_votes": 100,
        "guest_votes": 20,
        "voter_share_within_league": {
            "4": {"votes": 60, "share_pct": 60.0},
            "8": {"votes": 40, "share_pct": 40.0},
        },
        "league_only": {
            "votes_counted": 100,
            "pairwise_observations": 300,
            "same_position_pairwise_sample_sizes": {
                "WR": {"pairwise_observations": 40, "enough_data": True},
                "LB": {"pairwise_observations": 10, "enough_data": False},
                "QB": {"pairwise_observations": 5, "enough_data": False},
            },
        },
    }
    with_evidence = attach_evidence(calibrated, synthetic_ktc)
    assert with_evidence["player 000"]["evidence"]["same_position_enough_data"] is True
    assert with_evidence["player 100"]["evidence"]["same_position_enough_data"] is False
    assert with_evidence["michael penix jr"]["evidence"]["dominant_voter_majority_flag"] is True

    payload = {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "scale_semantics": SCALE_SEMANTICS,
        "players": with_evidence,
    }
    validate_payload(payload, minimum_players=100)

    print(
        "build_market_value self-test passed: alias resolution, market-order "
        "quantile calibration, center-value preservation, monotonic mapping, "
        "and voter/sample guardrails."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build separate Trade Desk league Market Value V1.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    payload = build_payload()
    if args.write:
        write_outputs(payload)
    else:
        print(json.dumps({
            "method_version": payload["method_version"],
            "scale_semantics": payload["scale_semantics"],
            "resolved_market_players": payload["counts"]["resolved_market_players"],
            "market_coverage_pct_of_model": payload["counts"]["market_coverage_pct_of_model"],
            "dominant_voter_share_pct": payload["market_quality"]["dominant_voter_share_pct"],
            "dominant_voter_majority_flag": payload["market_quality"]["dominant_voter_majority_flag"],
        }, indent=2))


if __name__ == "__main__":
    main()

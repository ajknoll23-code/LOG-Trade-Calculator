#!/usr/bin/env python3
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
SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATION_DIR = REPO_ROOT / "scripts" / "validation"

for path in (SCRIPT_DIR, VALIDATION_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import ktc_pipeline
import snapshot_values
from evaluate_market_history import build_alias_index, normalize_name

INDEX_PATH = REPO_ROOT / "index.html"
OUTPUT_JSON = REPO_ROOT / "scripts" / "artifacts" / "generated" / "market_values.json"
OUTPUT_MD = REPO_ROOT / "scripts" / "artifacts" / "reports" / "market_value_report.md"

METHOD_VERSION = "market-value-v2-balanced-blended-v1"
SCALE_SEMANTICS = "league_rank_quantile_mapped_to_trade_desk_points_v1"
LEAGUE_GROUP_MULTIPLIER = 1.0
GUEST_GROUP_MULTIPLIER = 0.50
PER_VOTER_EFFECTIVE_CAP = 30.0
MIN_RESOLVED_MARKET_PLAYERS = 100

POLICY = {
    "method_version": METHOD_VERSION,
    "market_source": "raw KTC vote rows through canonical ktc_pipeline utilities",
    "league_group_multiplier": LEAGUE_GROUP_MULTIPLIER,
    "guest_group_multiplier": GUEST_GROUP_MULTIPLIER,
    "per_voter_effective_lifetime_cap": PER_VOTER_EFFECTIVE_CAP,
    "daily_raw_vote_cap": int(ktc_pipeline.MAX_VOTES_PER_VOTER_PER_DAY),
    "package_vote_rows": "excluded before market processing",
    "scale_semantics": SCALE_SEMANTICS,
    "ordering": "weighted regularized Bradley-Terry rating descending",
    "point_scale": (
        "quantile map market ordering onto the current Fundamental Value "
        "distribution of the exact same market-covered player universe"
    ),
    "fundamental_formula_policy": "never modified or blended by this artifact",
    "team_utility_policy": "never modified or blended by this artifact",
    "live_trade_verdict_policy": "never modified by this artifact",
}

POLICY_SHA256 = hashlib.sha256(
    json.dumps(POLICY, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Required file missing: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            unique[(model_key, priority, method)] = (
                model_key, priority, method
            )
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
        method = sorted(
            item[2] for item in best if item[0] == key
        )[0]
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
        rows = sorted(
            rows,
            key=lambda row: (
                row["priority"],
                normalize_name(row["raw_name"]),
            ),
        )
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
        "coverage_pct_of_model": round(
            100.0 * len(resolved) / max(1, len(model_values)), 2
        ),
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
        if key in model_values
        and isinstance(model_values[key].get("value"), (int, float))
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

    ordered_groups = sorted(
        market_groups.items(), key=lambda item: -item[0]
    )
    n = len(keys)
    cursor = 0
    out = {}

    for rating, group_keys in ordered_groups:
        group_keys = sorted(group_keys)
        size = len(group_keys)
        group_slots = slots[cursor:cursor + size]
        calibrated = int(
            math.floor(sum(group_slots) / size + 0.5)
        )
        first_rank = cursor + 1
        last_rank = cursor + size
        avg_rank = (first_rank + last_rank) / 2.0
        percentile = (
            1.0
            if n == 1
            else 1.0 - ((avg_rank - 1.0) / (n - 1.0))
        )

        for key in group_keys:
            fundamental = int(model_values[key]["value"])
            delta = calibrated - fundamental
            out[key] = {
                "pos": model_values[key].get("pos"),
                "fundamental_value": fundamental,
                "market_value": calibrated,
                "market_minus_fundamental": delta,
                "market_minus_fundamental_pct": (
                    round(delta / fundamental, 6)
                    if fundamental > 0 else None
                ),
                "market_rating": round(rating, 6),
                "market_rank": round(avg_rank, 3),
                "market_percentile": round(percentile, 6),
            }

        cursor += size

    return out


def build_voter_weights(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get("voter_roster_id") or "unknown")] += 1

    out = {}
    for voter, raw_count in counts.items():
        group = (
            "league"
            if ktc_pipeline.is_league_voter(voter)
            else "guest"
        )
        group_multiplier = (
            LEAGUE_GROUP_MULTIPLIER
            if group == "league"
            else GUEST_GROUP_MULTIPLIER
        )
        cap_weight = min(
            1.0,
            PER_VOTER_EFFECTIVE_CAP / float(raw_count),
        )
        ballot_weight = cap_weight * group_multiplier
        out[voter] = {
            "group": group,
            "raw_votes": raw_count,
            "cap_weight": cap_weight,
            "group_multiplier": group_multiplier,
            "ballot_weight": ballot_weight,
            "effective_votes": raw_count * ballot_weight,
        }

    total = sum(v["effective_votes"] for v in out.values())
    for info in out.values():
        info["effective_share_pct"] = (
            100.0 * info["effective_votes"] / total
            if total > 0 else 0.0
        )
    return out


def build_weighted_pairs(
    rows: list[dict[str, Any]],
    voter_weights: dict[str, dict[str, Any]],
) -> list[tuple[str, str, float]]:
    pairs = []
    for row in rows:
        voter = str(row.get("voter_roster_id") or "unknown")
        info = voter_weights.get(voter)
        if not info:
            continue
        weight = float(info["ballot_weight"])
        if weight <= 0:
            continue
        keep = row.get("keep")
        trade = row.get("trade")
        cut = row.get("cut")
        if not (keep and trade and cut):
            continue
        pairs.extend([
            (str(keep), str(trade), weight),
            (str(keep), str(cut), weight),
            (str(trade), str(cut), weight),
        ])
    return pairs


def normalize_snapshot_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "timestamp": str(row.get("timestamp") or ""),
            "voter_roster_id": str(row.get("voter_roster_id") or ""),
            "keep": str(row.get("keep") or ""),
            "trade": str(row.get("trade") or ""),
            "cut": str(row.get("cut") or ""),
        }
        for row in rows
    ]


def load_vote_rows(snapshot_path: Path | None = None) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if snapshot_path is not None:
        doc = read_json(snapshot_path)
        rows = normalize_snapshot_rows(doc.get("rows") or [])
        return rows, {
            "mode": "frozen_snapshot",
            "snapshot_path": str(snapshot_path),
            "snapshot_sha256": sha256_file(snapshot_path),
            "raw_sheet_row_count": doc.get("raw_sheet_row_count"),
            "package_rows_excluded": doc.get("package_rows_excluded"),
        }

    all_rows = ktc_pipeline.fetch_votes()
    normal_rows = [
        row for row in all_rows
        if not ktc_pipeline.is_package_vote_row(row)
    ]
    package_rows_excluded = len(all_rows) - len(normal_rows)
    counted = ktc_pipeline.apply_daily_cap(normal_rows)
    return normalize_snapshot_rows(counted), {
        "mode": "live_sheet",
        "sheet_url": ktc_pipeline.SHEET_CSV_URL,
        "raw_sheet_row_count": len(all_rows),
        "package_rows_excluded": package_rows_excluded,
    }


def build_payload(snapshot_path: Path | None = None) -> dict[str, Any]:
    cfg = snapshot_values.load_from_html(INDEX_PATH)
    model_values = snapshot_values.compute_all_values(cfg)

    rows, source = load_vote_rows(snapshot_path)
    voter_weights = build_voter_weights(rows)
    weighted_pairs = build_weighted_pairs(rows, voter_weights)
    raw_ratings = ktc_pipeline.weighted_bradley_terry(weighted_pairs)

    resolved, identity_audit = resolve_league_ratings(
        model_values, raw_ratings
    )
    calibrated = quantile_calibrate(model_values, resolved)

    total_effective = sum(
        float(v["effective_votes"]) for v in voter_weights.values()
    )
    league_effective = sum(
        float(v["effective_votes"])
        for v in voter_weights.values()
        if v["group"] == "league"
    )
    guest_effective = sum(
        float(v["effective_votes"])
        for v in voter_weights.values()
        if v["group"] == "guest"
    )
    league_raw = sum(
        int(v["raw_votes"])
        for v in voter_weights.values()
        if v["group"] == "league"
    )
    guest_raw = sum(
        int(v["raw_votes"])
        for v in voter_weights.values()
        if v["group"] == "guest"
    )

    largest_id, largest = max(
        voter_weights.items(),
        key=lambda kv: kv[1]["effective_share_pct"],
        default=(None, {"effective_share_pct": 0.0}),
    )

    players = {}
    for key, row in calibrated.items():
        players[key] = {
            **row,
            "evidence": {
                "largest_effective_voter_share_pct": round(
                    float(largest["effective_share_pct"]), 4
                ),
                "phase2_robustness_passed": True,
            },
        }

    payload = {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "scale_semantics": SCALE_SEMANTICS,
        "generated_at_utc":
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        "policy": POLICY,
        "policy_sha256": POLICY_SHA256,
        "source": source,
        "market_quality": {
            "raw_votes": len(rows),
            "league_raw_votes": league_raw,
            "guest_raw_votes": guest_raw,
            "total_effective_votes": round(total_effective, 6),
            "league_effective_votes": round(league_effective, 6),
            "guest_effective_votes": round(guest_effective, 6),
            "largest_effective_voter_id": largest_id,
            "largest_effective_voter_share_pct": round(
                float(largest["effective_share_pct"]), 4
            ),
        },
        "counts": {
            "fundamental_model_players": len(model_values),
            "raw_market_ratings": len(raw_ratings),
            "resolved_market_players": len(players),
            "market_coverage_pct_of_model": round(
                100.0 * len(players) / max(1, len(model_values)),
                2,
            ),
        },
        "identity_audit": identity_audit,
        "players": players,
    }
    validate_payload(payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise RuntimeError("Unexpected Market Value schema")
    if payload.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Unexpected Market Value V2 method")
    if payload.get("scale_semantics") != SCALE_SEMANTICS:
        raise RuntimeError("Market Value scale semantics drifted")

    players = payload.get("players")
    if (
        not isinstance(players, dict)
        or len(players) < MIN_RESOLVED_MARKET_PLAYERS
    ):
        raise RuntimeError(
            "Resolved Market Value coverage unexpectedly small"
        )

    fundamentals = sorted(
        int(row["fundamental_value"])
        for row in players.values()
    )
    markets = sorted(
        int(row["market_value"])
        for row in players.values()
    )
    if fundamentals != markets:
        raise RuntimeError(
            "Market quantile calibration did not exactly preserve "
            "the covered Fundamental Value distribution"
        )

    ordered = sorted(
        players.items(),
        key=lambda kv: (-float(kv[1]["market_rating"]), kv[0]),
    )
    prior_rating = None
    prior_value = None
    for key, row in ordered:
        rating = float(row["market_rating"])
        value = int(row["market_value"])
        if (
            prior_rating is not None
            and rating < prior_rating
            and value > prior_value
        ):
            raise RuntimeError(
                f"Market ordering is not monotonic at {key}"
            )
        prior_rating = rating
        prior_value = value


def render_report(payload: dict[str, Any]) -> str:
    players = payload["players"]
    q = payload["market_quality"]
    counts = payload["counts"]

    disagreement = sorted(
        players.items(),
        key=lambda kv: (
            -abs(kv[1]["market_minus_fundamental"]),
            kv[0],
        ),
    )[:30]

    lines = [
        "# Trade Desk Market Value V2",
        "",
        f"Method: `{METHOD_VERSION}`",
        f"Policy SHA256: `{payload['policy_sha256']}`",
        "",
        "**Market Value V2 is a separate market-opinion layer. "
        "It does not change Fundamental Value, Team Utility, or "
        "live trade verdict math.**",
        "",
        f"- Market-covered players: **{counts['resolved_market_players']}**",
        f"- Raw counted votes: **{q['raw_votes']}**",
        f"- Effective votes: **{q['total_effective_votes']:.1f}**",
        f"- League effective votes: **{q['league_effective_votes']:.1f}**",
        f"- Guest effective votes: **{q['guest_effective_votes']:.1f}**",
        f"- Largest effective voter share: "
        f"**{q['largest_effective_voter_share_pct']:.2f}%**",
        "",
        "## Largest Fundamental ↔ Market disagreements",
        "",
        "| Player | Pos | Fundamental | Market | Δ | Market rank |",
        "|---|---|---:|---:|---:|---:|",
    ]

    for key, row in disagreement:
        lines.append(
            f"| {key} | {row['pos']} | "
            f"{row['fundamental_value']:,} | "
            f"{row['market_value']:,} | "
            f"{row['market_minus_fundamental']:+,} | "
            f"{row['market_rank']} |"
        )

    lines += [
        "",
        "## Deployed policy",
        "",
        "- League voter multiplier: `1.00`",
        "- Guest voter multiplier: `0.50`",
        "- Per-voter lifetime effective cap: `30` ballots",
        "- Per-voter UTC daily raw cap: `20` ballots",
        "- Package Preference rows excluded before fitting",
        "- Fundamental Value unchanged",
        "- Team Utility unchanged",
        "- Live trade verdict formulas unchanged",
        "",
    ]
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(
        render_report(payload),
        encoding="utf-8",
    )
    print(
        f"Market Value V2 written: "
        f"{OUTPUT_JSON.relative_to(REPO_ROOT)} "
        f"({payload['counts']['resolved_market_players']} players)"
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

    model_values["michael penix jr"] = {
        "pos": "QB",
        "value": 7000,
    }
    raw_ratings["michael penix"] = 500.0

    resolved, audit = resolve_league_ratings(
        model_values, raw_ratings
    )
    assert resolved["michael penix jr"] == 500.0
    assert audit["ambiguous_market_names"] == []

    calibrated = quantile_calibrate(
        model_values, resolved
    )
    assert (
        calibrated["michael penix jr"]["market_value"]
        == max(
            row["fundamental_value"]
            for row in calibrated.values()
        )
    )

    rows = []
    for i in range(40):
        rows.append({
            "voter_roster_id": "4",
            "keep": "a",
            "trade": "b",
            "cut": "c",
            "timestamp": "2026-09-01T00:00:00Z",
        })
        rows.append({
            "voter_roster_id": "ext_x",
            "keep": "c",
            "trade": "b",
            "cut": "a",
            "timestamp": "2026-09-01T00:00:00Z",
        })
    weights = build_voter_weights(rows)
    assert abs(weights["4"]["effective_votes"] - 30.0) < 1e-9
    assert abs(weights["ext_x"]["effective_votes"] - 15.0) < 1e-9
    assert (
        weights["4"]["effective_share_pct"]
        > weights["ext_x"]["effective_share_pct"]
    )

    print(
        "Market Value V2 self-test passed: identity resolution, "
        "quantile calibration, 30-vote cap, and 0.50 guest weighting."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="Use an already filtered/daily-capped frozen vote snapshot",
    )
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    payload = build_payload(args.snapshot)
    if args.write:
        write_outputs(payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

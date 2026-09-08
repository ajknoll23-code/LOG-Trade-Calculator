#!/usr/bin/env python3
"""
Market Value V2 shadow research.

Builds a voter-balanced market-opinion layer that combines:
- league KTC voters at 1.00 group weight
- guest/external KTC voters at 0.50 group weight (primary shadow setting)
- a 30 effective-vote lifetime cap per voter before group weighting
- the same 20-vote UTC daily cap used by the canonical KTC pipeline
- the same Bradley-Terry fitter and FV quantile calibration used by Market Value V1

This is deliberately SHADOW / RESEARCH ONLY:
- Market Value V1 remains the deployed league-only market artifact.
- Fundamental Value is never modified.
- Team Utility is never modified.
- Trade verdicts are never modified.

The script also evaluates guest-weight sensitivity at 0.00, 0.25, 0.50, 0.75,
and 1.00 so the 0.50 choice can be audited rather than silently treated as truth.

Usage:
  python3 scripts/market/build_market_value_v2_shadow.py --selftest
  python3 scripts/market/build_market_value_v2_shadow.py --write
  python3 scripts/market/build_market_value_v2_shadow.py --check
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
from statistics import median
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
VALIDATION_DIR = REPO_ROOT / "scripts" / "validation"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATION_DIR))

import build_market_value as mv1
import ktc_pipeline

INDEX_PATH = REPO_ROOT / "index.html"
KTC_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "ktc_ratings.json"
MARKET_V1_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "market_values.json"

OUT_DIR = REPO_ROOT / "research" / "market-value-v2"
OUT_JSON = OUT_DIR / "market_value_v2_shadow.json"
OUT_MD = OUT_DIR / "market_value_v2_shadow.md"

SCHEMA_VERSION = 2
METHOD_VERSION = "market-value-v2-blended-shadow-v1"
PRIMARY_GUEST_WEIGHT = 0.50
GUEST_WEIGHT_SENSITIVITY = (0.00, 0.25, 0.50, 0.75, 1.00)
PER_VOTER_EFFECTIVE_CAP = float(ktc_pipeline.VOTER_BALANCE_EFFECTIVE_VOTE_CAP)
MIN_RESOLVED_PLAYERS = 100

POLICY = {
    "status": "research_only_shadow",
    "method_version": METHOD_VERSION,
    "league_group_multiplier": 1.0,
    "primary_guest_group_multiplier": PRIMARY_GUEST_WEIGHT,
    "guest_weight_sensitivity": list(GUEST_WEIGHT_SENSITIVITY),
    "per_voter_effective_lifetime_cap_before_group_multiplier": PER_VOTER_EFFECTIVE_CAP,
    "daily_cap": int(ktc_pipeline.MAX_VOTES_PER_VOTER_PER_DAY),
    "daily_cap_semantics": "same UTC per-voter KTC cap enforced by ktc_pipeline.py",
    "package_vote_rows": "excluded before all KTC market processing",
    "voter_weight_formula": (
        "min(1, cap/raw_count_for_voter) * group_multiplier; "
        "league multiplier=1.0, guest multiplier varies by sensitivity setting"
    ),
    "guest_identity_guardrail": (
        "guest ids are stable browser-local ext_* identifiers, not verified unique people; "
        "guest influence is therefore discounted and capped"
    ),
    "market_scale": (
        "rank-preserving quantile map onto the current Fundamental Value distribution "
        "for the exact resolved market-covered universe"
    ),
    "production_market_value_v1_changed": False,
    "fundamental_value_changed": False,
    "team_utility_changed": False,
    "live_trade_verdict_changed": False,
}

POLICY_SHA256 = hashlib.sha256(
    json.dumps(POLICY, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Required file missing: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def q(values: list[float], quantile: float) -> float | None:
    vals = sorted(float(x) for x in values if math.isfinite(float(x)))
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * quantile
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 1e-15 or vy <= 1e-15:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(vx * vy)


def build_voter_weights(rows: list[dict[str, Any]], guest_weight: float) -> dict[str, dict[str, Any]]:
    if not 0.0 <= guest_weight <= 1.0:
        raise ValueError("guest_weight must be between 0 and 1")

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get("voter_roster_id") or "unknown")] += 1

    result: dict[str, dict[str, Any]] = {}
    for voter, raw_count in counts.items():
        group = "league" if ktc_pipeline.is_league_voter(voter) else "guest"
        group_multiplier = 1.0 if group == "league" else float(guest_weight)
        cap_weight = min(1.0, PER_VOTER_EFFECTIVE_CAP / float(raw_count))
        ballot_weight = cap_weight * group_multiplier
        result[voter] = {
            "group": group,
            "raw_votes": raw_count,
            "cap_weight": cap_weight,
            "group_multiplier": group_multiplier,
            "ballot_weight": ballot_weight,
            "effective_votes": raw_count * ballot_weight,
        }

    total_effective = sum(row["effective_votes"] for row in result.values())
    for row in result.values():
        row["effective_share_pct"] = (
            100.0 * row["effective_votes"] / total_effective if total_effective > 0 else 0.0
        )

    return dict(
        sorted(
            result.items(),
            key=lambda kv: (-kv[1]["effective_votes"], -kv[1]["raw_votes"], kv[0]),
        )
    )


def build_weighted_pairs(
    rows: list[dict[str, Any]],
    voter_weights: dict[str, dict[str, Any]],
) -> list[tuple[str, str, float]]:
    weighted_pairs: list[tuple[str, str, float]] = []
    for row in rows:
        voter = str(row.get("voter_roster_id") or "unknown")
        info = voter_weights.get(voter)
        if not info:
            continue
        weight = float(info["ballot_weight"])
        if weight <= 0:
            continue
        keep, trade, cut = row.get("keep"), row.get("trade"), row.get("cut")
        if not (keep and trade and cut):
            continue
        weighted_pairs.extend(
            [
                (str(keep), str(trade), weight),
                (str(keep), str(cut), weight),
                (str(trade), str(cut), weight),
            ]
        )
    return weighted_pairs


def summarize_weight_mass(voter_weights: dict[str, dict[str, Any]]) -> dict[str, Any]:
    group_raw = {"league": 0, "guest": 0}
    group_effective = {"league": 0.0, "guest": 0.0}
    group_voters = {"league": 0, "guest": 0}

    for row in voter_weights.values():
        group = row["group"]
        group_raw[group] += int(row["raw_votes"])
        group_effective[group] += float(row["effective_votes"])
        group_voters[group] += 1

    total_effective = sum(group_effective.values())
    max_voter = max(
        (
            {
                "voter_id": voter,
                "group": row["group"],
                "raw_votes": row["raw_votes"],
                "effective_votes": row["effective_votes"],
                "effective_share_pct": row["effective_share_pct"],
            }
            for voter, row in voter_weights.items()
        ),
        key=lambda row: row["effective_share_pct"],
        default=None,
    )

    return {
        "unique_voters": group_voters,
        "raw_votes": group_raw,
        "effective_votes": {k: round(v, 6) for k, v in group_effective.items()},
        "effective_share_pct": {
            k: round(100.0 * v / total_effective, 2) if total_effective > 0 else 0.0
            for k, v in group_effective.items()
        },
        "total_effective_votes": round(total_effective, 6),
        "largest_effective_voter": max_voter,
    }


def build_one_setting(
    rows: list[dict[str, Any]],
    model_values: dict[str, dict[str, Any]],
    guest_weight: float,
) -> dict[str, Any]:
    voter_weights = build_voter_weights(rows, guest_weight)
    weighted_pairs = build_weighted_pairs(rows, voter_weights)
    raw_ratings = ktc_pipeline.weighted_bradley_terry(weighted_pairs)
    resolved, identity_audit = mv1.resolve_league_ratings(model_values, raw_ratings)
    calibrated = mv1.quantile_calibrate(model_values, resolved)

    return {
        "guest_weight": guest_weight,
        "voter_weights": voter_weights,
        "weight_mass": summarize_weight_mass(voter_weights),
        "raw_pairwise_observations": len(weighted_pairs),
        "effective_pairwise_mass": round(sum(w for _, _, w in weighted_pairs), 6),
        "raw_rating_count": len(raw_ratings),
        "resolved_rating_count": len(resolved),
        "identity_audit": identity_audit,
        "raw_ratings": raw_ratings,
        "players": calibrated,
    }


def compare_market_sets(
    base_players: dict[str, dict[str, Any]],
    other_players: dict[str, dict[str, Any]],
    *,
    base_value_field: str = "market_value",
    other_value_field: str = "market_value",
    base_rank_field: str = "market_rank",
    other_rank_field: str = "market_rank",
    topn: int = 20,
) -> dict[str, Any]:
    common = sorted(set(base_players) & set(other_players))
    if not common:
        return {
            "common_players": 0,
            "rank_correlation": None,
            "median_abs_value_difference": None,
            "p90_abs_value_difference": None,
            "max_abs_value_difference": None,
            "top_movers": [],
        }

    abs_diffs: list[float] = []
    rank_a: list[float] = []
    rank_b: list[float] = []
    movers = []

    for key in common:
        a = float(base_players[key][base_value_field])
        b = float(other_players[key][other_value_field])
        diff = a - b
        abs_diffs.append(abs(diff))
        rank_a.append(float(base_players[key][base_rank_field]))
        rank_b.append(float(other_players[key][other_rank_field]))
        movers.append(
            {
                "player": key,
                "base_value": int(round(a)),
                "other_value": int(round(b)),
                "difference": int(round(diff)),
                "base_rank": float(base_players[key][base_rank_field]),
                "other_rank": float(other_players[key][other_rank_field]),
                "rank_change": round(
                    float(other_players[key][other_rank_field])
                    - float(base_players[key][base_rank_field]),
                    3,
                ),
            }
        )

    movers.sort(key=lambda row: (-abs(row["difference"]), row["player"]))
    return {
        "common_players": len(common),
        "rank_correlation": round(pearson(rank_a, rank_b), 6)
        if pearson(rank_a, rank_b) is not None
        else None,
        "median_abs_value_difference": round(float(median(abs_diffs)), 3),
        "p90_abs_value_difference": round(float(q(abs_diffs, 0.90)), 3),
        "max_abs_value_difference": round(max(abs_diffs), 3),
        "top_movers": movers[:topn],
    }


def normalize_v1_players(v1_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for key, row in (v1_payload.get("players") or {}).items():
        if not isinstance(row, dict):
            continue
        if row.get("market_value") is None or row.get("market_rank") is None:
            continue
        out[key] = row
    return out


def validate_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("unexpected Market Value V2 shadow schema")
    if payload.get("method_version") != METHOD_VERSION:
        raise RuntimeError("unexpected Market Value V2 shadow method")
    if payload.get("status") != "research_only_shadow":
        raise RuntimeError("Market Value V2 shadow status drifted")
    if payload.get("production_promotion_allowed") is not False:
        raise RuntimeError("shadow artifact must never auto-promote")
    for field in (
        "production_market_value_v1_changed",
        "fundamental_value_changed",
        "team_utility_changed",
        "live_trade_verdict_changed",
    ):
        if payload.get("consumer_contract", {}).get(field) is not False:
            raise RuntimeError(f"consumer contract drifted: {field}")

    players = payload.get("players")
    if not isinstance(players, dict) or len(players) < MIN_RESOLVED_PLAYERS:
        raise RuntimeError(
            f"Market Value V2 shadow resolved coverage too small: "
            f"{len(players) if isinstance(players, dict) else 'invalid'}"
        )

    primary = payload["primary_setting"]
    if abs(float(primary["guest_weight"]) - PRIMARY_GUEST_WEIGHT) > 1e-12:
        raise RuntimeError("primary guest weight drifted")

    sensitivity = payload.get("sensitivity") or {}
    expected = {f"{w:.2f}" for w in GUEST_WEIGHT_SENSITIVITY}
    if set(sensitivity) != expected:
        raise RuntimeError("guest-weight sensitivity grid drifted")

    fundamentals = sorted(int(row["fundamental_value"]) for row in players.values())
    markets = sorted(int(row["blended_market_value"]) for row in players.values())
    if abs(sum(fundamentals) - sum(markets)) > len(players):
        raise RuntimeError("V2 quantile mapping unexpectedly changed aggregate market scale")


def build_payload() -> dict[str, Any]:
    cfg = mv1.snapshot_values.load_from_html(INDEX_PATH)
    model_values = mv1.snapshot_values.compute_all_values(cfg)
    v1_payload = read_json(MARKET_V1_PATH)
    v1_players = normalize_v1_players(v1_payload)

    all_rows = ktc_pipeline.fetch_votes()
    package_rows = [r for r in all_rows if ktc_pipeline.is_package_vote_row(r)]
    ktc_rows = [r for r in all_rows if not ktc_pipeline.is_package_vote_row(r)]
    capped_rows = ktc_pipeline.apply_daily_cap(ktc_rows)

    settings: dict[str, dict[str, Any]] = {}
    for guest_weight in GUEST_WEIGHT_SENSITIVITY:
        settings[f"{guest_weight:.2f}"] = build_one_setting(
            capped_rows, model_values, guest_weight
        )

    primary = settings[f"{PRIMARY_GUEST_WEIGHT:.2f}"]
    league_balanced = settings["0.00"]

    sensitivity_summary: dict[str, Any] = {}
    for key, setting in settings.items():
        cmp = compare_market_sets(primary["players"], setting["players"])
        sensitivity_summary[key] = {
            "guest_weight": setting["guest_weight"],
            "resolved_players": setting["resolved_rating_count"],
            "raw_rating_count": setting["raw_rating_count"],
            "weight_mass": setting["weight_mass"],
            "effective_pairwise_mass": setting["effective_pairwise_mass"],
            "vs_primary_050": {
                k: v for k, v in cmp.items() if k != "top_movers"
            },
        }

    guest_effect = compare_market_sets(primary["players"], league_balanced["players"])
    v1_comparison = compare_market_sets(primary["players"], v1_players)

    players: dict[str, dict[str, Any]] = {}
    for key, row in primary["players"].items():
        fv = int(row["fundamental_value"])
        blended = int(row["market_value"])
        v1_row = v1_players.get(key)
        balanced_row = league_balanced["players"].get(key)

        players[key] = {
            "pos": row.get("pos"),
            "fundamental_value": fv,
            "blended_market_value": blended,
            "blended_minus_fundamental": blended - fv,
            "blended_market_rating": row["market_rating"],
            "blended_market_rank": row["market_rank"],
            "blended_market_percentile": row["market_percentile"],
            "league_market_value_v1": int(v1_row["market_value"]) if v1_row else None,
            "blended_minus_league_v1": (
                blended - int(v1_row["market_value"]) if v1_row else None
            ),
            "balanced_league_shadow_value": (
                int(balanced_row["market_value"]) if balanced_row else None
            ),
            "guest_effect_vs_balanced_league_shadow": (
                blended - int(balanced_row["market_value"]) if balanced_row else None
            ),
            "balanced_league_shadow_rank": (
                balanced_row["market_rank"] if balanced_row else None
            ),
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "status": "research_only_shadow",
        "production_promotion_allowed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "policy": POLICY,
        "policy_sha256": POLICY_SHA256,
        "consumer_contract": {
            "production_market_value_v1_changed": False,
            "fundamental_value_changed": False,
            "team_utility_changed": False,
            "live_trade_verdict_changed": False,
        },
        "source_file_sha256": {
            "index_html": sha256_file(INDEX_PATH),
            "ktc_ratings": sha256_file(KTC_PATH) if KTC_PATH.exists() else None,
            "market_values_v1": sha256_file(MARKET_V1_PATH),
        },
        "raw_input": {
            "sheet_rows_fetched": len(all_rows),
            "package_rows_excluded": len(package_rows),
            "normal_ktc_rows_before_daily_cap": len(ktc_rows),
            "normal_ktc_rows_after_daily_cap": len(capped_rows),
        },
        "primary_setting": {
            "guest_weight": PRIMARY_GUEST_WEIGHT,
            "per_voter_effective_cap": PER_VOTER_EFFECTIVE_CAP,
            "weight_mass": primary["weight_mass"],
            "raw_pairwise_observations": primary["raw_pairwise_observations"],
            "effective_pairwise_mass": primary["effective_pairwise_mass"],
            "raw_rating_count": primary["raw_rating_count"],
            "resolved_rating_count": primary["resolved_rating_count"],
            "identity_audit": primary["identity_audit"],
        },
        "comparisons": {
            "guest_marginal_effect_vs_balanced_league_shadow": guest_effect,
            "vs_deployed_market_value_v1": v1_comparison,
        },
        "sensitivity": sensitivity_summary,
        "players": players,
    }

    validate_payload(payload)
    return payload


def render_report(payload: dict[str, Any]) -> str:
    primary = payload["primary_setting"]
    mass = primary["weight_mass"]
    guest_cmp = payload["comparisons"]["guest_marginal_effect_vs_balanced_league_shadow"]
    v1_cmp = payload["comparisons"]["vs_deployed_market_value_v1"]

    lines = [
        "# Market Value V2 — Blended KTC Shadow",
        "",
        "**Status: RESEARCH ONLY / SHADOW. Market Value V1 remains deployed.**",
        "",
        "## Policy",
        "",
        f"- League voter multiplier: `1.00`",
        f"- Primary guest voter multiplier: `{PRIMARY_GUEST_WEIGHT:.2f}`",
        f"- Per-voter lifetime cap before group weighting: `{PER_VOTER_EFFECTIVE_CAP:.0f}` ballots",
        f"- KTC daily cap: `{ktc_pipeline.MAX_VOTES_PER_VOTER_PER_DAY}` ballots per voter per UTC day",
        "- Package Preference rows are excluded before KTC market processing.",
        "- Guest browser identities are not verified unique people, so guest influence is both capped and discounted.",
        "- Fundamental Value, Team Utility, live verdicts, and deployed Market Value V1 are unchanged.",
        "",
        "## Current evidence mass at primary 0.50 guest weight",
        "",
        f"- League voters: `{mass['unique_voters']['league']}`",
        f"- Guest voters: `{mass['unique_voters']['guest']}`",
        f"- Raw league ballots: `{mass['raw_votes']['league']}`",
        f"- Raw guest ballots: `{mass['raw_votes']['guest']}`",
        f"- Effective league ballots: `{mass['effective_votes']['league']:.1f}` "
        f"(`{mass['effective_share_pct']['league']:.1f}%`)",
        f"- Effective guest ballots: `{mass['effective_votes']['guest']:.1f}` "
        f"(`{mass['effective_share_pct']['guest']:.1f}%`)",
        f"- Resolved V2 market players: `{primary['resolved_rating_count']}`",
        "",
        "## What guests change",
        "",
        "This comparison holds the per-voter league balancing policy constant and changes only guest weight from 0.00 to 0.50.",
        "",
        f"- Common players: `{guest_cmp['common_players']}`",
        f"- Rank correlation: `{guest_cmp['rank_correlation']}`",
        f"- Median absolute value change: `{guest_cmp['median_abs_value_difference']}`",
        f"- 90th-percentile absolute change: `{guest_cmp['p90_abs_value_difference']}`",
        f"- Maximum absolute change: `{guest_cmp['max_abs_value_difference']}`",
        "",
        "| Player | V2 0.50 | Balanced league-only shadow | Guest effect | Rank change |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in guest_cmp["top_movers"]:
        lines.append(
            f"| {row['player']} | {row['base_value']} | {row['other_value']} | "
            f"{row['difference']:+d} | {row['rank_change']:+.1f} |"
        )

    lines += [
        "",
        "## V2 shadow vs deployed Market Value V1",
        "",
        f"- Common players: `{v1_cmp['common_players']}`",
        f"- Rank correlation: `{v1_cmp['rank_correlation']}`",
        f"- Median absolute value change: `{v1_cmp['median_abs_value_difference']}`",
        f"- 90th-percentile absolute change: `{v1_cmp['p90_abs_value_difference']}`",
        f"- Maximum absolute change: `{v1_cmp['max_abs_value_difference']}`",
        "",
        "| Player | V2 shadow | Deployed V1 | Difference | Rank change |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in v1_cmp["top_movers"]:
        lines.append(
            f"| {row['player']} | {row['base_value']} | {row['other_value']} | "
            f"{row['difference']:+d} | {row['rank_change']:+.1f} |"
        )

    lines += [
        "",
        "## Guest-weight sensitivity",
        "",
        "| Guest weight | League effective | Guest effective | Guest share | Resolved | Rank corr vs 0.50 | Median abs Δ | P90 abs Δ | Max abs Δ |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in sorted(payload["sensitivity"], key=float):
        row = payload["sensitivity"][key]
        wm = row["weight_mass"]
        cmp = row["vs_primary_050"]
        lines.append(
            f"| {float(key):.2f} | {wm['effective_votes']['league']:.1f} | "
            f"{wm['effective_votes']['guest']:.1f} | {wm['effective_share_pct']['guest']:.1f}% | "
            f"{row['resolved_players']} | {cmp['rank_correlation']} | "
            f"{cmp['median_abs_value_difference']} | {cmp['p90_abs_value_difference']} | "
            f"{cmp['max_abs_value_difference']} |"
        )

    largest = mass.get("largest_effective_voter")
    lines += [
        "",
        "## Guardrails",
        "",
        "- This artifact cannot promote itself. `production_promotion_allowed` is hard-coded `false`.",
        "- The primary 0.50 guest multiplier is a policy hypothesis, not a fitted truth.",
        "- The sensitivity table is required specifically to show whether that policy choice materially changes rankings.",
        "- Guest `ext_*` ids are browser-local identities; clearing browser storage can create a new identity. The cap and 0.50 discount limit this risk but do not eliminate it.",
        "- V2 uses the same Bradley-Terry implementation and the same rank-to-FV quantile calibration concept as V1 so the experimental change is the voter weighting policy, not a new value scale.",
    ]
    if largest:
        lines.append(
            f"- Largest effective voter at the primary setting: `{largest['voter_id']}` "
            f"({largest['group']}), `{largest['effective_share_pct']:.2f}%` of effective ballot mass."
        )
    lines.append("")
    return "\n".join(lines)


def write_payload(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_report(payload), encoding="utf-8")
    print(f"Wrote {OUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(REPO_ROOT)}")


def run_selftest() -> None:
    rows = []
    for i in range(100):
        rows.append(
            {
                "timestamp": f"2026-09-{1 + i // 20:02d}T00:00:00Z",
                "voter_roster_id": "1",
                "keep": "alpha",
                "trade": "beta",
                "cut": "gamma",
            }
        )
    for i in range(20):
        rows.append(
            {
                "timestamp": "2026-09-01T00:00:00Z",
                "voter_roster_id": "2",
                "keep": "gamma",
                "trade": "beta",
                "cut": "alpha",
            }
        )
    for i in range(20):
        rows.append(
            {
                "timestamp": "2026-09-01T00:00:00Z",
                "voter_roster_id": "ext_a",
                "keep": "gamma",
                "trade": "beta",
                "cut": "alpha",
            }
        )

    weights = build_voter_weights(rows, 0.50)
    assert abs(weights["1"]["effective_votes"] - 30.0) < 1e-9
    assert abs(weights["2"]["effective_votes"] - 20.0) < 1e-9
    assert abs(weights["ext_a"]["effective_votes"] - 10.0) < 1e-9
    assert weights["ext_a"]["group"] == "guest"

    zero = build_voter_weights(rows, 0.0)
    assert zero["ext_a"]["effective_votes"] == 0.0

    pairs = build_weighted_pairs(rows, weights)
    assert len(pairs) == 140 * 3
    strengths = ktc_pipeline.weighted_bradley_terry(pairs)
    assert set(strengths) == {"alpha", "beta", "gamma"}
    assert all(math.isfinite(v) and v > 0 for v in strengths.values())

    mass = summarize_weight_mass(weights)
    assert mass["unique_voters"] == {"league": 2, "guest": 1}
    assert abs(mass["effective_votes"]["league"] - 50.0) < 1e-9
    assert abs(mass["effective_votes"]["guest"] - 10.0) < 1e-9

    a = {
        "x": {"market_value": 100, "market_rank": 1},
        "y": {"market_value": 50, "market_rank": 2},
    }
    b = {
        "x": {"market_value": 90, "market_rank": 1},
        "y": {"market_value": 60, "market_rank": 2},
    }
    cmp = compare_market_sets(a, b)
    assert cmp["common_players"] == 2
    assert cmp["rank_correlation"] == 1.0
    assert cmp["median_abs_value_difference"] == 10.0

    print(
        "Market Value V2 shadow self-test passed: voter cap, guest discount, "
        "zero-guest baseline, weighted BT, mass accounting, and comparison diagnostics."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    if args.check:
        payload = read_json(OUT_JSON)
        validate_payload(payload)
        print("Market Value V2 shadow artifact check passed.")
        return

    payload = build_payload()
    if args.write:
        write_payload(payload)
    else:
        primary = payload["primary_setting"]
        mass = primary["weight_mass"]
        print(
            f"Market Value V2 shadow: {primary['resolved_rating_count']} resolved players; "
            f"league effective={mass['effective_votes']['league']:.1f}, "
            f"guest effective={mass['effective_votes']['guest']:.1f} "
            f"({mass['effective_share_pct']['guest']:.1f}% guest share)."
        )


if __name__ == "__main__":
    main()

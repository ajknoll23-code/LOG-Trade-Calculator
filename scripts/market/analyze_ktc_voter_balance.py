#!/usr/bin/env python3
"""
Research-only comparison of raw league KTC Bradley-Terry ratings versus the
voter-balanced league view.

This script NEVER changes Market Value V1. Its purpose is to make the effect
of voter concentration measurable over time before any production consumer is
considered for a source change.

Inputs:
  scripts/artifacts/generated/ktc_ratings.json

Outputs:
  scripts/artifacts/generated/ktc_voter_balance_analysis.json
  scripts/artifacts/reports/ktc_voter_balance_analysis.md

Usage:
  python3 scripts/market/analyze_ktc_voter_balance.py --selftest
  python3 scripts/market/analyze_ktc_voter_balance.py --write
  python3 scripts/market/analyze_ktc_voter_balance.py --check
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "ktc_ratings.json"
OUTPUT_JSON = REPO_ROOT / "scripts" / "artifacts" / "generated" / "ktc_voter_balance_analysis.json"
OUTPUT_MD = REPO_ROOT / "scripts" / "artifacts" / "reports" / "ktc_voter_balance_analysis.md"

METHOD_VERSION = "ktc-voter-balance-analysis-v1"
TOP_N_VALUES = (10, 20, 50)
MAX_MOVERS = 20


def _finite_positive_ratings(obj: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, raw in (obj or {}).items():
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 0:
            out[str(key)] = value
    return out


def _average_ranks_desc(ratings: dict[str, float]) -> dict[str, float]:
    """Average ranks for exact ties, highest rating = rank 1."""
    ordered = sorted(ratings.items(), key=lambda kv: (-kv[1], kv[0]))
    ranks: dict[str, float] = {}
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][1] == ordered[i][1]:
            j += 1
        avg_rank = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[ordered[k][0]] = avg_rank
        i = j
    return ranks


def _ordered_keys(ratings: dict[str, float]) -> list[str]:
    return [k for k, _ in sorted(ratings.items(), key=lambda kv: (-kv[1], kv[0]))]


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)
    denom = math.sqrt(dx * dy)
    if denom <= 0:
        return None
    return num / denom


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def _round_or_none(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _concentration(voter_weights: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for voter, raw_info in (voter_weights or {}).items():
        info = raw_info or {}
        try:
            raw_votes = float(info.get("raw_votes", 0))
            effective_votes = float(info.get("effective_votes", 0))
            raw_share = float(info.get("raw_share_pct", 0)) / 100.0
            effective_share = float(info.get("effective_share_pct", 0)) / 100.0
            ballot_weight = float(info.get("ballot_weight", 0))
        except (TypeError, ValueError):
            continue
        rows.append({
            "voter": str(voter),
            "raw_votes": raw_votes,
            "effective_votes": effective_votes,
            "raw_share": raw_share,
            "effective_share": effective_share,
            "ballot_weight": ballot_weight,
        })

    raw_hhi = sum(r["raw_share"] ** 2 for r in rows)
    effective_hhi = sum(r["effective_share"] ** 2 for r in rows)
    max_raw = max((r["raw_share"] for r in rows), default=0.0)
    max_eff = max((r["effective_share"] for r in rows), default=0.0)

    return {
        "distinct_league_voters": len(rows),
        "capped_voters": sum(1 for r in rows if r["ballot_weight"] < 0.999999),
        "largest_raw_voter_share_pct": round(max_raw * 100.0, 2),
        "largest_effective_voter_share_pct": round(max_eff * 100.0, 2),
        "raw_hhi": round(raw_hhi, 6),
        "effective_hhi": round(effective_hhi, 6),
        "raw_effective_voter_count": _round_or_none((1.0 / raw_hhi) if raw_hhi > 0 else None, 3),
        "balanced_effective_voter_count": _round_or_none(
            (1.0 / effective_hhi) if effective_hhi > 0 else None, 3
        ),
    }


def build_analysis(ktc: dict[str, Any]) -> dict[str, Any]:
    raw = _finite_positive_ratings((ktc.get("league_only") or {}).get("player_ratings"))
    balanced_section = ktc.get("league_voter_balanced") or {}
    balanced = _finite_positive_ratings(balanced_section.get("player_ratings"))
    if not raw:
        raise RuntimeError("league_only.player_ratings is missing or empty")
    if not balanced:
        raise RuntimeError(
            "league_voter_balanced.player_ratings is missing or empty; "
            "run the voter-balanced KTC pipeline first"
        )

    common = sorted(set(raw) & set(balanced))
    raw_only = sorted(set(raw) - set(balanced))
    balanced_only = sorted(set(balanced) - set(raw))
    if len(common) < 2:
        raise RuntimeError("Need at least two common players to compare KTC ranking views")

    raw_common = {k: raw[k] for k in common}
    bal_common = {k: balanced[k] for k in common}
    raw_ranks = _average_ranks_desc(raw_common)
    bal_ranks = _average_ranks_desc(bal_common)
    raw_order = _ordered_keys(raw_common)
    bal_order = _ordered_keys(bal_common)

    rank_rows = []
    for player in common:
        raw_rank = raw_ranks[player]
        balanced_rank = bal_ranks[player]
        improvement = raw_rank - balanced_rank
        rank_rows.append({
            "player": player,
            "raw_rank": _round_or_none(raw_rank, 3),
            "balanced_rank": _round_or_none(balanced_rank, 3),
            "balanced_rank_improvement": _round_or_none(improvement, 3),
            "absolute_rank_shift": _round_or_none(abs(improvement), 3),
            "raw_rating": round(raw[player], 6),
            "balanced_rating": round(balanced[player], 6),
        })

    abs_shifts = [float(r["absolute_rank_shift"]) for r in rank_rows]
    spearman = _pearson(
        [raw_ranks[p] for p in common],
        [bal_ranks[p] for p in common],
    )

    top_overlap = {}
    for n in TOP_N_VALUES:
        n_eff = min(n, len(common))
        raw_set = set(raw_order[:n_eff])
        bal_set = set(bal_order[:n_eff])
        overlap = len(raw_set & bal_set)
        union = len(raw_set | bal_set)
        top_overlap[str(n)] = {
            "n_effective": n_eff,
            "overlap_count": overlap,
            "overlap_pct": round(100.0 * overlap / n_eff, 2) if n_eff else 0.0,
            "jaccard": round(overlap / union, 4) if union else None,
        }

    gainers = sorted(
        rank_rows,
        key=lambda r: (-float(r["balanced_rank_improvement"]), r["player"]),
    )[:MAX_MOVERS]
    decliners = sorted(
        rank_rows,
        key=lambda r: (float(r["balanced_rank_improvement"]), r["player"]),
    )[:MAX_MOVERS]

    voter_weights = balanced_section.get("voter_weights") or {}
    concentration = _concentration(voter_weights)

    try:
        raw_votes = float(balanced_section.get("raw_votes_counted", ktc.get("league_votes", 0)))
    except (TypeError, ValueError):
        raw_votes = 0.0
    try:
        effective_votes = float(balanced_section.get("effective_votes", 0))
    except (TypeError, ValueError):
        effective_votes = 0.0

    return {
        "method_version": METHOD_VERSION,
        "status": "research_only_no_market_value_change",
        "source_generated_at": ktc.get("generated_at"),
        "market_value_v1_source_changed": False,
        "policy": {
            "raw_view": "ktc_ratings.json::league_only.player_ratings",
            "balanced_view": "ktc_ratings.json::league_voter_balanced.player_ratings",
            "promotion_rule": (
                "Do not switch Market Value V1 from league_only based on a single snapshot. "
                "Use repeated snapshots and prospective predictive/stability evidence."
            ),
        },
        "coverage": {
            "raw_rating_players": len(raw),
            "balanced_rating_players": len(balanced),
            "common_players": len(common),
            "raw_only_players": raw_only,
            "balanced_only_players": balanced_only,
        },
        "voter_concentration": concentration,
        "vote_mass": {
            "raw_league_votes": round(raw_votes, 6),
            "effective_league_votes": round(effective_votes, 6),
            "effective_to_raw_pct": round(100.0 * effective_votes / raw_votes, 2)
            if raw_votes > 0
            else None,
        },
        "rank_agreement": {
            "spearman_rank_correlation": _round_or_none(spearman, 6),
            "median_absolute_rank_shift": _round_or_none(_percentile(abs_shifts, 0.50), 3),
            "p90_absolute_rank_shift": _round_or_none(_percentile(abs_shifts, 0.90), 3),
            "max_absolute_rank_shift": _round_or_none(max(abs_shifts) if abs_shifts else None, 3),
            "top_n_overlap": top_overlap,
        },
        "raw_top_20": raw_order[:20],
        "balanced_top_20": bal_order[:20],
        "largest_balanced_gainers": gainers,
        "largest_balanced_decliners": decliners,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    c = payload["voter_concentration"]
    v = payload["vote_mass"]
    a = payload["rank_agreement"]
    cov = payload["coverage"]

    lines = [
        "# KTC Voter-Balance Research Analysis",
        "",
        f"Method: `{payload['method_version']}`  ",
        f"Source generated at: `{payload.get('source_generated_at')}`  ",
        f"Status: `{payload['status']}`",
        "",
        "## Critical interpretation",
        "",
        "**This report is research-only. Market Value V1 still uses "
        "`league_only.player_ratings`; this analysis does not change production values.**",
        "",
        "The purpose is to quantify how much the raw league ranking changes when every "
        "league voter is limited to the configured effective lifetime contribution cap "
        "while retaining all counted ballots.",
        "",
        "## Voter concentration",
        "",
        f"- Distinct league voters: **{c['distinct_league_voters']}**",
        f"- Voters currently down-weighted by the lifetime cap: **{c['capped_voters']}**",
        f"- Largest raw voter share: **{c['largest_raw_voter_share_pct']:.2f}%**",
        f"- Largest effective voter share: **{c['largest_effective_voter_share_pct']:.2f}%**",
        f"- Raw HHI: **{c['raw_hhi']:.4f}** "
        f"(effective voter count ≈ **{c['raw_effective_voter_count']}**)",
        f"- Balanced HHI: **{c['effective_hhi']:.4f}** "
        f"(effective voter count ≈ **{c['balanced_effective_voter_count']}**)",
        f"- Raw league ballots: **{v['raw_league_votes']:.0f}**",
        f"- Effective league ballots after weighting: **{v['effective_league_votes']:.1f}** "
        f"(**{v['effective_to_raw_pct']:.2f}%** of raw mass)",
        "",
        "## Rank agreement: raw vs voter-balanced",
        "",
        f"- Common rated players: **{cov['common_players']}**",
        f"- Spearman rank correlation: **{a['spearman_rank_correlation']}**",
        f"- Median absolute rank shift: **{a['median_absolute_rank_shift']}** spots",
        f"- 90th-percentile absolute rank shift: **{a['p90_absolute_rank_shift']}** spots",
        f"- Maximum absolute rank shift: **{a['max_absolute_rank_shift']}** spots",
    ]

    for n in TOP_N_VALUES:
        row = a["top_n_overlap"][str(n)]
        lines.append(
            f"- Top-{n} overlap: **{row['overlap_count']}/{row['n_effective']} "
            f"({row['overlap_pct']:.1f}%)**"
        )

    lines.extend([
        "",
        "## Top 20 side-by-side",
        "",
        "| Rank | Raw league | Voter-balanced |",
        "|---:|---|---|",
    ])
    raw_top = payload["raw_top_20"]
    bal_top = payload["balanced_top_20"]
    for i in range(max(len(raw_top), len(bal_top))):
        lines.append(
            f"| {i+1} | {raw_top[i] if i < len(raw_top) else ''} | "
            f"{bal_top[i] if i < len(bal_top) else ''} |"
        )

    def add_movers(title: str, rows: list[dict[str, Any]]) -> None:
        lines.extend([
            "",
            f"## {title}",
            "",
            "| Player | Raw rank | Balanced rank | Improvement | |Δ rank| |",
            "|---|---:|---:|---:|---:|",
        ])
        for row in rows:
            lines.append(
                f"| {row['player']} | {row['raw_rank']} | {row['balanced_rank']} | "
                f"{float(row['balanced_rank_improvement']):+.1f} | "
                f"{row['absolute_rank_shift']} |"
            )

    add_movers("Largest gainers after voter balancing", payload["largest_balanced_gainers"][:15])
    add_movers("Largest decliners after voter balancing", payload["largest_balanced_decliners"][:15])

    lines.extend([
        "",
        "## Decision guardrail",
        "",
        "Do **not** promote the voter-balanced view into Market Value V1 from this report alone. "
        "The current evidence shows that voter concentration materially changes the ordering; "
        "the next question is whether the balanced ordering is more stable and more predictive "
        "of later league opinion across repeated snapshots.",
        "",
    ])
    return "\n".join(lines)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(_canonical_json(payload), encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    print(
        "Wrote "
        f"{OUTPUT_JSON.relative_to(REPO_ROOT)} and {OUTPUT_MD.relative_to(REPO_ROOT)}"
    )


def check_outputs(payload: dict[str, Any]) -> None:
    expected_json = _canonical_json(payload)
    expected_md = render_markdown(payload)
    failures = []
    if not OUTPUT_JSON.exists() or OUTPUT_JSON.read_text(encoding="utf-8") != expected_json:
        failures.append(str(OUTPUT_JSON.relative_to(REPO_ROOT)))
    if not OUTPUT_MD.exists() or OUTPUT_MD.read_text(encoding="utf-8") != expected_md:
        failures.append(str(OUTPUT_MD.relative_to(REPO_ROOT)))
    if failures:
        raise RuntimeError(
            "KTC voter-balance analysis outputs are missing or stale: "
            + ", ".join(failures)
            + ". Run with --write."
        )
    print("KTC voter-balance analysis outputs are current.")


def run_selftest() -> None:
    ktc = {
        "generated_at": "2026-09-03T00:00:00",
        "league_votes": 120,
        "league_only": {
            "player_ratings": {
                "alpha": 4.0,
                "beta": 3.0,
                "gamma": 2.0,
                "delta": 1.0,
            }
        },
        "league_voter_balanced": {
            "raw_votes_counted": 120,
            "effective_votes": 50.0,
            "voter_weights": {
                "1": {
                    "raw_votes": 100,
                    "raw_share_pct": 83.33,
                    "ballot_weight": 0.3,
                    "effective_votes": 30.0,
                    "effective_share_pct": 60.0,
                },
                "2": {
                    "raw_votes": 20,
                    "raw_share_pct": 16.67,
                    "ballot_weight": 1.0,
                    "effective_votes": 20.0,
                    "effective_share_pct": 40.0,
                },
            },
            "player_ratings": {
                "gamma": 4.0,
                "alpha": 3.0,
                "beta": 2.0,
                "delta": 1.0,
            },
        },
    }
    payload = build_analysis(ktc)
    assert payload["status"] == "research_only_no_market_value_change"
    assert payload["market_value_v1_source_changed"] is False
    assert payload["coverage"]["common_players"] == 4
    assert payload["voter_concentration"]["capped_voters"] == 1
    assert payload["vote_mass"]["effective_to_raw_pct"] == 41.67
    assert payload["rank_agreement"]["top_n_overlap"]["10"]["overlap_count"] == 4
    assert payload["largest_balanced_gainers"][0]["player"] == "gamma"
    assert payload["largest_balanced_decliners"][0]["player"] in {"alpha", "beta"}
    md = render_markdown(payload)
    assert "research-only" in md.lower()
    assert "Market Value V1" in md
    print(
        "KTC voter-balance analysis self-test passed: concentration, rank agreement, "
        "top-N overlap, mover direction, deterministic report rendering."
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

    if not INPUT_PATH.exists():
        raise RuntimeError(f"Missing input: {INPUT_PATH.relative_to(REPO_ROOT)}")
    ktc = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    payload = build_analysis(ktc)

    if args.write:
        write_outputs(payload)
    elif args.check:
        check_outputs(payload)
    else:
        print(render_markdown(payload))


if __name__ == "__main__":
    main()

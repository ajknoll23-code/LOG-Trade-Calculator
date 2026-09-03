#!/usr/bin/env python3
"""
Research-only sensitivity analysis for the KTC per-voter effective vote cap.

The voter-balanced KTC view currently uses a 30-effective-ballot lifetime cap.
That is intentionally NOT a production setting yet. This script recomputes the
same weighted Bradley-Terry league ranking at several nearby caps so we can
measure whether the result is robust or highly dependent on choosing 30.

This script does NOT change Market Value V1.

Outputs:
  scripts/artifacts/generated/ktc_cap_sensitivity.json
  scripts/artifacts/reports/ktc_cap_sensitivity.md

Usage:
  python3 scripts/market/analyze_ktc_cap_sensitivity.py --selftest
  python3 scripts/market/analyze_ktc_cap_sensitivity.py --write
  python3 scripts/market/analyze_ktc_cap_sensitivity.py --check
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import ktc_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
KTC_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "ktc_ratings.json"
OUTPUT_JSON = REPO_ROOT / "scripts" / "artifacts" / "generated" / "ktc_cap_sensitivity.json"
OUTPUT_MD = REPO_ROOT / "scripts" / "artifacts" / "reports" / "ktc_cap_sensitivity.md"

METHOD_VERSION = "ktc-voter-cap-sensitivity-v1"
CAPS = (20.0, 30.0, 40.0, 60.0, 90.0, 120.0)
BASELINE_CAP = 30.0
TOP_N = 20


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_league_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    capped = ktc_pipeline.apply_daily_cap(rows)
    return [
        row for row in capped
        if ktc_pipeline.is_league_voter(row.get("voter_roster_id", ""))
    ]


def _weights_for_cap(rows: list[dict[str, Any]], cap: float) -> dict[str, dict[str, float]]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get("voter_roster_id", "unknown"))] += 1

    total_raw = sum(counts.values())
    result: dict[str, dict[str, float]] = {}
    for voter, count in counts.items():
        weight = 1.0 if count <= cap else cap / float(count)
        result[voter] = {
            "raw_votes": float(count),
            "raw_share_pct": 100.0 * count / total_raw if total_raw else 0.0,
            "ballot_weight": weight,
            "effective_votes": count * weight,
        }

    total_effective = sum(v["effective_votes"] for v in result.values())
    for info in result.values():
        info["effective_share_pct"] = (
            100.0 * info["effective_votes"] / total_effective
            if total_effective else 0.0
        )
    return result


def _weighted_ratings(rows: list[dict[str, Any]], cap: float) -> tuple[dict[str, float], dict[str, Any]]:
    weights = _weights_for_cap(rows, cap)
    pairs: list[tuple[str, str, float]] = []
    valid_ballots = 0

    for row in rows:
        keep, trade, cut = row.get("keep"), row.get("trade"), row.get("cut")
        if not (keep and trade and cut):
            continue
        voter = str(row.get("voter_roster_id", "unknown"))
        info = weights.get(voter)
        if not info:
            continue
        weight = float(info["ballot_weight"])
        valid_ballots += 1
        pairs.extend([
            (keep, trade, weight),
            (keep, cut, weight),
            (trade, cut, weight),
        ])

    ratings = ktc_pipeline.weighted_bradley_terry(pairs)

    shares = [float(v["effective_share_pct"]) / 100.0 for v in weights.values()]
    hhi = sum(s * s for s in shares)
    largest_share = max(shares, default=0.0)
    effective_votes = sum(float(v["effective_votes"]) for v in weights.values())

    meta = {
        "cap": cap,
        "valid_ballots": valid_ballots,
        "effective_votes": round(effective_votes, 6),
        "effective_to_raw_pct": round(100.0 * effective_votes / len(rows), 2) if rows else None,
        "capped_voters": sum(1 for v in weights.values() if float(v["ballot_weight"]) < 0.999999),
        "largest_effective_voter_share_pct": round(largest_share * 100.0, 2),
        "effective_hhi": round(hhi, 6),
        "effective_voter_count": round(1.0 / hhi, 3) if hhi > 0 else None,
    }
    return ratings, meta


def _average_ranks_desc(ratings: dict[str, float]) -> dict[str, float]:
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


def _order(ratings: dict[str, float]) -> list[str]:
    return [k for k, _ in sorted(ratings.items(), key=lambda kv: (-kv[1], kv[0]))]


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)
    den = math.sqrt(dx * dy)
    return num / den if den > 0 else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    n = len(vals)
    m = n // 2
    if n % 2:
        return vals[m]
    return (vals[m - 1] + vals[m]) / 2.0


def _compare(
    candidate: dict[str, float],
    baseline: dict[str, float],
    top_n: int = TOP_N,
) -> dict[str, Any]:
    common = sorted(set(candidate) & set(baseline))
    if len(common) < 2:
        return {
            "common_players": len(common),
            "spearman_vs_cap30": None,
            "median_absolute_rank_shift_vs_cap30": None,
            "top20_overlap_count_vs_cap30": None,
            "top20_overlap_pct_vs_cap30": None,
        }

    c = {k: candidate[k] for k in common}
    b = {k: baseline[k] for k in common}
    cr = _average_ranks_desc(c)
    br = _average_ranks_desc(b)
    spearman = _pearson([cr[k] for k in common], [br[k] for k in common])
    shifts = [abs(cr[k] - br[k]) for k in common]

    n = min(top_n, len(common))
    c_top = set(_order(c)[:n])
    b_top = set(_order(b)[:n])
    overlap = len(c_top & b_top)

    return {
        "common_players": len(common),
        "spearman_vs_cap30": round(spearman, 6) if spearman is not None else None,
        "median_absolute_rank_shift_vs_cap30": round(_median(shifts), 3) if shifts else None,
        "top20_overlap_count_vs_cap30": overlap,
        "top20_overlap_pct_vs_cap30": round(100.0 * overlap / n, 2) if n else None,
    }


def build_analysis(rows: list[dict[str, Any]], ktc: dict[str, Any]) -> dict[str, Any]:
    league_rows = _valid_league_rows(rows)

    expected_league_votes = int(ktc.get("league_votes", 0))
    if len(league_rows) != expected_league_votes:
        raise RuntimeError(
            "Published vote sheet changed between the KTC aggregation and cap-sensitivity "
            f"steps: ktc_ratings.json has {expected_league_votes} league votes but the "
            f"current capped sheet has {len(league_rows)}. Re-run the workflow so both "
            "artifacts use the same vote snapshot."
        )

    by_cap: dict[str, Any] = {}
    ratings_by_cap: dict[float, dict[str, float]] = {}

    for cap in CAPS:
        ratings, meta = _weighted_ratings(league_rows, cap)
        ratings_by_cap[cap] = ratings
        by_cap[str(int(cap))] = {
            **meta,
            "top_20": _order(ratings)[:TOP_N],
        }

    baseline = ratings_by_cap[BASELINE_CAP]
    for cap in CAPS:
        by_cap[str(int(cap))]["agreement_vs_cap30"] = _compare(
            ratings_by_cap[cap], baseline
        )

    # Raw uncapped league view from the same exact sheet snapshot.
    raw_pairs = ktc_pipeline.decompose_to_pairwise(league_rows)
    raw_ratings = ktc_pipeline.bradley_terry(raw_pairs)
    raw_vs_30 = _compare(raw_ratings, baseline)

    # Cap-30 should reproduce the existing research view closely because both
    # use the same pipeline functions and same source snapshot.
    artifact_cap30 = (
        (ktc.get("league_voter_balanced") or {}).get("player_ratings") or {}
    )
    artifact_cap30 = {
        str(k): float(v)
        for k, v in artifact_cap30.items()
        if isinstance(v, (int, float)) and float(v) > 0
    }
    cap30_artifact_agreement = _compare(baseline, artifact_cap30)

    neighbor20 = by_cap["20"]["agreement_vs_cap30"]
    neighbor40 = by_cap["40"]["agreement_vs_cap30"]
    neighborhood_spearman_min = min(
        x for x in [
            neighbor20.get("spearman_vs_cap30"),
            neighbor40.get("spearman_vs_cap30"),
        ]
        if x is not None
    )
    neighborhood_top20_min = min(
        x for x in [
            neighbor20.get("top20_overlap_pct_vs_cap30"),
            neighbor40.get("top20_overlap_pct_vs_cap30"),
        ]
        if x is not None
    )

    # Descriptive only. This does not authorize a production source change.
    if neighborhood_spearman_min >= 0.97 and neighborhood_top20_min >= 80.0:
        sensitivity_label = "low_near_cap30"
    elif neighborhood_spearman_min >= 0.90 and neighborhood_top20_min >= 60.0:
        sensitivity_label = "moderate_near_cap30"
    else:
        sensitivity_label = "high_near_cap30"

    return {
        "method_version": METHOD_VERSION,
        "status": "research_only_no_market_value_change",
        "source_ktc_generated_at": ktc.get("generated_at"),
        "league_votes_counted": len(league_rows),
        "baseline_cap": BASELINE_CAP,
        "caps_tested": list(CAPS),
        "sensitivity_label": sensitivity_label,
        "sensitivity_rule": {
            "low_near_cap30": "min Spearman(20,30 / 40,30) >= 0.97 and min top-20 overlap >= 80%",
            "moderate_near_cap30": "min Spearman >= 0.90 and min top-20 overlap >= 60%",
            "high_near_cap30": "otherwise",
            "interpretation": (
                "Descriptive robustness label only; never a promotion rule for Market Value V1."
            ),
        },
        "uncapped_raw_vs_cap30": raw_vs_30,
        "cap30_reproduction_vs_ktc_artifact": cap30_artifact_agreement,
        "by_cap": by_cap,
        "decision_guardrail": (
            "Keep Market Value V1 on league_only until repeated snapshots show that a "
            "voter-balance policy is stable and prospectively more representative/predictive."
        ),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# KTC Voter-Cap Sensitivity Analysis",
        "",
        f"Method: `{payload['method_version']}`  ",
        f"Source KTC generated at: `{payload.get('source_ktc_generated_at')}`  ",
        f"League votes: **{payload['league_votes_counted']}**  ",
        f"Status: `{payload['status']}`",
        "",
        "## Result",
        "",
        f"Near-cap-30 sensitivity: **`{payload['sensitivity_label']}`**",
        "",
        "This asks a narrow question: if the effective lifetime cap were 20, 40, "
        "60, 90, or 120 instead of 30, would the league ordering stay broadly the same?",
        "",
        "## Cap comparison",
        "",
        "| Cap | Capped voters | Effective votes | Largest voter | Eff. voter count | Spearman vs 30 | Median |Δ rank| | Top-20 overlap vs 30 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for cap in payload["caps_tested"]:
        row = payload["by_cap"][str(int(cap))]
        a = row["agreement_vs_cap30"]
        lines.append(
            f"| {int(cap)} | {row['capped_voters']} | {row['effective_votes']:.1f} | "
            f"{row['largest_effective_voter_share_pct']:.2f}% | "
            f"{row['effective_voter_count']} | "
            f"{a['spearman_vs_cap30']} | "
            f"{a['median_absolute_rank_shift_vs_cap30']} | "
            f"{a['top20_overlap_count_vs_cap30']}/{min(TOP_N, a['common_players'])} "
            f"({a['top20_overlap_pct_vs_cap30']:.1f}%) |"
        )

    raw = payload["uncapped_raw_vs_cap30"]
    repro = payload["cap30_reproduction_vs_ktc_artifact"]

    lines.extend([
        "",
        "## Reference checks",
        "",
        f"- Uncapped raw vs cap-30 Spearman: **{raw['spearman_vs_cap30']}**",
        f"- Uncapped raw vs cap-30 top-20 overlap: "
        f"**{raw['top20_overlap_count_vs_cap30']}/{min(TOP_N, raw['common_players'])} "
        f"({raw['top20_overlap_pct_vs_cap30']:.1f}%)**",
        f"- Recomputed cap-30 vs stored KTC cap-30 Spearman: "
        f"**{repro['spearman_vs_cap30']}**",
        "",
        "## Top 20 by cap",
        "",
    ])

    for cap in payload["caps_tested"]:
        lines.append(f"### Cap {int(cap)}")
        lines.append("")
        top = payload["by_cap"][str(int(cap))]["top_20"]
        for i, player in enumerate(top, start=1):
            lines.append(f"{i}. {player}")
        lines.append("")

    lines.extend([
        "## Decision guardrail",
        "",
        payload["decision_guardrail"],
        "",
        "The sensitivity label is **not** permission to switch Market Value. A cap can "
        "be internally stable and still be the wrong market estimator. We need repeated "
        "snapshots and prospective evidence before promotion.",
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


def check_outputs() -> None:
    ktc = _read_json(KTC_PATH)
    payload = _read_json(OUTPUT_JSON)
    if payload.get("method_version") != METHOD_VERSION:
        raise RuntimeError("KTC cap-sensitivity JSON has the wrong method_version")
    if payload.get("status") != "research_only_no_market_value_change":
        raise RuntimeError("KTC cap-sensitivity output lost its research-only guardrail")
    if payload.get("source_ktc_generated_at") != ktc.get("generated_at"):
        raise RuntimeError(
            "KTC cap-sensitivity output is stale relative to ktc_ratings.json; "
            "run analyze_ktc_cap_sensitivity.py --write"
        )
    if "30" not in (payload.get("by_cap") or {}):
        raise RuntimeError("KTC cap-sensitivity output is missing cap 30")
    if not OUTPUT_MD.exists():
        raise RuntimeError("KTC cap-sensitivity markdown report is missing")
    md = OUTPUT_MD.read_text(encoding="utf-8")
    if "Market Value V1" not in md or "Decision guardrail" not in md:
        raise RuntimeError("KTC cap-sensitivity markdown report is missing guardrail text")
    print("KTC cap-sensitivity outputs are current and guarded.")


def run_selftest() -> None:
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
            "timestamp": "2026-09-01T01:00:00Z",
            "voter_roster_id": "8",
            "keep": "gamma",
            "trade": "beta",
            "cut": "alpha",
        })
    for i in range(10):
        rows.append({
            "timestamp": "2026-09-01T02:00:00Z",
            "voter_roster_id": "11",
            "keep": "beta",
            "trade": "gamma",
            "cut": "alpha",
        })

    # apply_daily_cap keeps these because voter 4 is spread across five days.
    ktc = {
        "generated_at": "2026-09-03T00:00:00",
        "league_votes": 130,
        "league_voter_balanced": {
            "player_ratings": {
                "alpha": 1.0,
                "beta": 1.0,
                "gamma": 1.0,
            }
        },
    }
    payload = build_analysis(rows, ktc)
    assert payload["league_votes_counted"] == 130
    assert payload["baseline_cap"] == 30.0
    assert set(payload["by_cap"]) == {"20", "30", "40", "60", "90", "120"}
    assert payload["by_cap"]["20"]["capped_voters"] == 1
    assert payload["by_cap"]["30"]["effective_votes"] == 60.0
    assert payload["status"] == "research_only_no_market_value_change"
    assert payload["sensitivity_label"] in {
        "low_near_cap30", "moderate_near_cap30", "high_near_cap30"
    }
    md = render_markdown(payload)
    assert "Cap comparison" in md
    assert "Market Value" in md
    print(
        "KTC cap-sensitivity self-test passed: cap weighting, effective-vote accounting, "
        "ranking comparisons, robustness label, and production guardrails."
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
        check_outputs()
        return

    ktc = _read_json(KTC_PATH)
    rows = ktc_pipeline.fetch_votes()
    payload = build_analysis(rows, ktc)

    if args.write:
        write_outputs(payload)
    else:
        print(render_markdown(payload))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Prospective evaluation of raw league KTC ratings versus voter-balanced ratings.

Research-only. This script never changes Market Value V1.

Design
------
Each run can append a dedicated KTC research snapshot containing the ratings
that existed at that moment. Later runs fetch the vote sheet and score only
ballots submitted AFTER each snapshot and BEFORE the next distinct snapshot.

Two outcome weightings are reported:
1. raw_future_stream: every eligible future ballot counts equally.
2. equal_voter_future_consensus: within each evaluation interval, every voter
   receives equal total weight regardless of how many eligible ballots they cast.

The equal-voter target is intentionally independent of the 30-vote training cap.
It asks whether a rating view better predicts broad league-member opinion rather
than the raw volume of the most active voter.

Outputs
-------
research/ktc-voter-balance/snapshots/<generated_at>.json
research/ktc-voter-balance/prospective/latest.json
research/ktc-voter-balance/prospective/latest.md

Usage
-----
python3 scripts/market/evaluate_ktc_voter_balance_prospective.py --selftest
python3 scripts/market/evaluate_ktc_voter_balance_prospective.py --snapshot --write
python3 scripts/market/evaluate_ktc_voter_balance_prospective.py --check
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ktc_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
KTC_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "ktc_ratings.json"
SNAPSHOT_DIR = REPO_ROOT / "research" / "ktc-voter-balance" / "snapshots"
OUTPUT_JSON = REPO_ROOT / "research" / "ktc-voter-balance" / "prospective" / "latest.json"
OUTPUT_MD = REPO_ROOT / "research" / "ktc-voter-balance" / "prospective" / "latest.md"

METHOD_VERSION = "ktc-voter-balance-prospective-v1"
MIN_ELIGIBLE_BALLOTS_FOR_EVIDENCE = 30
MIN_DISTINCT_VOTERS_FOR_EVIDENCE = 4
EPS = 1e-12


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def finite_positive_ratings(obj: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    if not isinstance(obj, dict):
        return out
    for key, raw in obj.items():
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 0:
            out[str(key)] = value
    return out


def make_snapshot(ktc: dict[str, Any]) -> dict[str, Any]:
    raw = finite_positive_ratings((ktc.get("league_only") or {}).get("player_ratings"))
    balanced_section = ktc.get("league_voter_balanced") or {}
    balanced = finite_positive_ratings(balanced_section.get("player_ratings"))
    generated = parse_timestamp(ktc.get("generated_at"))

    if generated is None:
        raise RuntimeError("ktc_ratings.json has no parseable generated_at timestamp")
    if len(raw) < 100 or len(balanced) < 100:
        raise RuntimeError("KTC research snapshot has implausibly few raw/balanced ratings")

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "research_only_no_market_value_change",
        "ktc_generated_at": iso_z(generated),
        "captured_at_utc": iso_z(datetime.now(timezone.utc)),
        "league_votes": ktc.get("league_votes"),
        "voter_balance_policy": ktc.get("voter_balance_policy"),
        "raw_player_ratings": raw,
        "balanced_player_ratings": balanced,
        "voter_weights": balanced_section.get("voter_weights") or {},
    }


def snapshot_path(snapshot: dict[str, Any]) -> Path:
    stamp = snapshot["ktc_generated_at"].replace(":", "").replace("-", "")
    return SNAPSHOT_DIR / f"{stamp}.json"


def write_snapshot(snapshot: dict[str, Any]) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(snapshot)
    canonical = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != canonical:
            raise RuntimeError(
                f"Research snapshot collision with different content: {path.relative_to(REPO_ROOT)}"
            )
        print(f"KTC research snapshot already exists: {path.relative_to(REPO_ROOT)}")
    else:
        path.write_text(canonical, encoding="utf-8")
        print(f"Wrote KTC research snapshot: {path.relative_to(REPO_ROOT)}")
    return path


def load_snapshots() -> list[dict[str, Any]]:
    if not SNAPSHOT_DIR.exists():
        return []
    rows = []
    seen_times = set()
    for path in sorted(SNAPSHOT_DIR.glob("*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if obj.get("method_version") != METHOD_VERSION:
            continue
        freeze = parse_timestamp(obj.get("ktc_generated_at"))
        if freeze is None:
            continue
        key = iso_z(freeze)
        if key in seen_times:
            continue
        raw = finite_positive_ratings(obj.get("raw_player_ratings"))
        balanced = finite_positive_ratings(obj.get("balanced_player_ratings"))
        if len(raw) < 100 or len(balanced) < 100:
            continue
        obj["_freeze_dt"] = freeze
        seen_times.add(key)
        rows.append(obj)
    rows.sort(key=lambda x: x["_freeze_dt"])
    return rows


def eligible_league_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    capped = ktc_pipeline.apply_daily_cap(rows)
    out = []
    for row in capped:
        if not ktc_pipeline.is_league_voter(row.get("voter_roster_id", "")):
            continue
        ts = parse_timestamp(row.get("timestamp"))
        keep, trade, cut = row.get("keep"), row.get("trade"), row.get("cut")
        if ts is None or not (keep and trade and cut):
            continue
        copied = dict(row)
        copied["_ts"] = ts
        out.append(copied)
    return out


def pair_probability(ratings: dict[str, float], winner: str, loser: str) -> float | None:
    sw = ratings.get(winner)
    sl = ratings.get(loser)
    if sw is None or sl is None or sw <= 0 or sl <= 0:
        return None
    denom = sw + sl
    if denom <= 0:
        return None
    return min(1.0 - EPS, max(EPS, sw / denom))


def ballot_pairs(row: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    keep, trade, cut = row["keep"], row["trade"], row["cut"]
    return ((keep, trade), (keep, cut), (trade, cut))


def metric_accumulator() -> dict[str, float]:
    return {
        "weight": 0.0,
        "log_loss_sum": 0.0,
        "brier_sum": 0.0,
        "accuracy_sum": 0.0,
    }


def add_metric(acc: dict[str, float], p: float, weight: float) -> None:
    acc["weight"] += weight
    acc["log_loss_sum"] += weight * (-math.log(p))
    acc["brier_sum"] += weight * ((1.0 - p) ** 2)
    if p > 0.5:
        credit = 1.0
    elif p < 0.5:
        credit = 0.0
    else:
        credit = 0.5
    acc["accuracy_sum"] += weight * credit


def finish_metric(acc: dict[str, float]) -> dict[str, Any]:
    w = acc["weight"]
    if w <= 0:
        return {
            "effective_pairwise_weight": 0.0,
            "log_loss": None,
            "brier_score": None,
            "pairwise_accuracy_pct": None,
        }
    return {
        "effective_pairwise_weight": round(w, 6),
        "log_loss": round(acc["log_loss_sum"] / w, 6),
        "brier_score": round(acc["brier_sum"] / w, 6),
        "pairwise_accuracy_pct": round(100.0 * acc["accuracy_sum"] / w, 2),
    }


def evaluate_interval(
    snapshot: dict[str, Any],
    future_rows: list[dict[str, Any]],
    end_dt: datetime | None,
) -> dict[str, Any]:
    start_dt = snapshot["_freeze_dt"]
    raw = finite_positive_ratings(snapshot.get("raw_player_ratings"))
    balanced = finite_positive_ratings(snapshot.get("balanced_player_ratings"))
    common_players = set(raw) & set(balanced)

    candidates = []
    for row in future_rows:
        ts = row["_ts"]
        if ts <= start_dt:
            continue
        if end_dt is not None and ts > end_dt:
            continue
        players = (row["keep"], row["trade"], row["cut"])
        if all(p in common_players for p in players):
            candidates.append(row)

    ballots_by_voter: dict[str, int] = defaultdict(int)
    for row in candidates:
        ballots_by_voter[str(row.get("voter_roster_id", "unknown"))] += 1

    schemes = {
        "raw_future_stream": {
            "raw": metric_accumulator(),
            "balanced": metric_accumulator(),
        },
        "equal_voter_future_consensus": {
            "raw": metric_accumulator(),
            "balanced": metric_accumulator(),
        },
    }

    for row in candidates:
        voter = str(row.get("voter_roster_id", "unknown"))
        equal_voter_ballot_weight = 1.0 / ballots_by_voter[voter]
        for winner, loser in ballot_pairs(row):
            p_raw = pair_probability(raw, winner, loser)
            p_bal = pair_probability(balanced, winner, loser)
            if p_raw is None or p_bal is None:
                continue

            add_metric(schemes["raw_future_stream"]["raw"], p_raw, 1.0)
            add_metric(schemes["raw_future_stream"]["balanced"], p_bal, 1.0)
            add_metric(
                schemes["equal_voter_future_consensus"]["raw"],
                p_raw,
                equal_voter_ballot_weight,
            )
            add_metric(
                schemes["equal_voter_future_consensus"]["balanced"],
                p_bal,
                equal_voter_ballot_weight,
            )

    finished = {}
    for scheme, models in schemes.items():
        raw_m = finish_metric(models["raw"])
        bal_m = finish_metric(models["balanced"])
        delta = {}
        for metric in ("log_loss", "brier_score"):
            rv = raw_m[metric]
            bv = bal_m[metric]
            delta[f"balanced_minus_raw_{metric}"] = (
                round(bv - rv, 6) if rv is not None and bv is not None else None
            )
        ra = raw_m["pairwise_accuracy_pct"]
        ba = bal_m["pairwise_accuracy_pct"]
        delta["balanced_minus_raw_accuracy_pct_points"] = (
            round(ba - ra, 2) if ra is not None and ba is not None else None
        )
        finished[scheme] = {
            "raw_model": raw_m,
            "balanced_model": bal_m,
            "difference_balanced_minus_raw": delta,
        }

    return {
        "snapshot_ktc_generated_at": snapshot["ktc_generated_at"],
        "window_end_utc": iso_z(end_dt) if end_dt is not None else None,
        "eligible_future_ballots": len(candidates),
        "distinct_future_voters": len(ballots_by_voter),
        "future_ballots_by_voter": dict(
            sorted(ballots_by_voter.items(), key=lambda kv: (-kv[1], kv[0]))
        ),
        "metrics": finished,
    }


def combine_intervals(intervals: list[dict[str, Any]], scheme: str, model: str) -> dict[str, Any]:
    # Reconstruct weighted sums from interval averages. Because each interval metric
    # includes its effective pairwise weight, this yields the correct pooled average.
    total_w = 0.0
    ll_sum = 0.0
    brier_sum = 0.0
    acc_sum = 0.0
    for interval in intervals:
        m = interval["metrics"][scheme][f"{model}_model"]
        w = float(m.get("effective_pairwise_weight") or 0.0)
        if w <= 0:
            continue
        total_w += w
        ll_sum += w * float(m["log_loss"])
        brier_sum += w * float(m["brier_score"])
        acc_sum += w * float(m["pairwise_accuracy_pct"]) / 100.0
    if total_w <= 0:
        return {
            "effective_pairwise_weight": 0.0,
            "log_loss": None,
            "brier_score": None,
            "pairwise_accuracy_pct": None,
        }
    return {
        "effective_pairwise_weight": round(total_w, 6),
        "log_loss": round(ll_sum / total_w, 6),
        "brier_score": round(brier_sum / total_w, 6),
        "pairwise_accuracy_pct": round(100.0 * acc_sum / total_w, 2),
    }


def build_evaluation(
    snapshots: list[dict[str, Any]],
    vote_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    future_rows = eligible_league_rows(vote_rows)
    intervals = []

    for i, snapshot in enumerate(snapshots):
        end_dt = snapshots[i + 1]["_freeze_dt"] if i + 1 < len(snapshots) else None
        intervals.append(evaluate_interval(snapshot, future_rows, end_dt))

    aggregate_metrics = {}
    for scheme in ("raw_future_stream", "equal_voter_future_consensus"):
        raw_m = combine_intervals(intervals, scheme, "raw")
        bal_m = combine_intervals(intervals, scheme, "balanced")
        aggregate_metrics[scheme] = {
            "raw_model": raw_m,
            "balanced_model": bal_m,
            "difference_balanced_minus_raw": {
                "balanced_minus_raw_log_loss": (
                    round(bal_m["log_loss"] - raw_m["log_loss"], 6)
                    if raw_m["log_loss"] is not None and bal_m["log_loss"] is not None
                    else None
                ),
                "balanced_minus_raw_brier_score": (
                    round(bal_m["brier_score"] - raw_m["brier_score"], 6)
                    if raw_m["brier_score"] is not None and bal_m["brier_score"] is not None
                    else None
                ),
                "balanced_minus_raw_accuracy_pct_points": (
                    round(
                        bal_m["pairwise_accuracy_pct"] - raw_m["pairwise_accuracy_pct"], 2
                    )
                    if raw_m["pairwise_accuracy_pct"] is not None
                    and bal_m["pairwise_accuracy_pct"] is not None
                    else None
                ),
            },
        }

    total_ballots = sum(i["eligible_future_ballots"] for i in intervals)
    distinct_voters = set()
    for interval in intervals:
        distinct_voters.update(interval["future_ballots_by_voter"])

    if len(snapshots) < 1:
        status = "READY_WAITING_FOR_BASELINE_SNAPSHOT"
    elif total_ballots < MIN_ELIGIBLE_BALLOTS_FOR_EVIDENCE:
        status = "READY_WAITING_FOR_MORE_FUTURE_VOTES"
    elif len(distinct_voters) < MIN_DISTINCT_VOTERS_FOR_EVIDENCE:
        status = "READY_WAITING_FOR_MORE_DISTINCT_FUTURE_VOTERS"
    else:
        status = "EVIDENCE_AVAILABLE_RESEARCH_ONLY"

    consensus = aggregate_metrics["equal_voter_future_consensus"]
    consensus_ll_delta = consensus["difference_balanced_minus_raw"][
        "balanced_minus_raw_log_loss"
    ]
    consensus_brier_delta = consensus["difference_balanced_minus_raw"][
        "balanced_minus_raw_brier_score"
    ]

    if status != "EVIDENCE_AVAILABLE_RESEARCH_ONLY":
        directional_result = "insufficient_future_evidence"
    elif (
        consensus_ll_delta is not None
        and consensus_brier_delta is not None
        and consensus_ll_delta < 0
        and consensus_brier_delta < 0
    ):
        directional_result = "balanced_better_on_equal_voter_future_consensus"
    elif (
        consensus_ll_delta is not None
        and consensus_brier_delta is not None
        and consensus_ll_delta > 0
        and consensus_brier_delta > 0
    ):
        directional_result = "raw_better_on_equal_voter_future_consensus"
    else:
        directional_result = "mixed_metrics_on_equal_voter_future_consensus"

    return {
        "method_version": METHOD_VERSION,
        "status": status,
        "directional_result": directional_result,
        "research_only": True,
        "market_value_v1_source_changed": False,
        "thresholds": {
            "minimum_eligible_future_ballots": MIN_ELIGIBLE_BALLOTS_FOR_EVIDENCE,
            "minimum_distinct_future_voters": MIN_DISTINCT_VOTERS_FOR_EVIDENCE,
        },
        "counts": {
            "distinct_rating_snapshots": len(snapshots),
            "eligible_future_ballots_across_disjoint_windows": total_ballots,
            "distinct_future_voters_across_windows": len(distinct_voters),
        },
        "aggregate_metrics": aggregate_metrics,
        "intervals": intervals,
        "interpretation": {
            "raw_future_stream": (
                "Scores predictions against the naturally observed future vote stream; "
                "high-volume voters therefore contribute more outcomes."
            ),
            "equal_voter_future_consensus": (
                "Within each interval, every voter receives equal total outcome weight. "
                "This target is independent of the 30-vote training cap."
            ),
            "promotion_guardrail": (
                "Do not switch Market Value V1 based on this artifact alone. Require "
                "sustained prospective advantage across multiple intervals and voters."
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    c = payload["counts"]
    lines = [
        "# KTC Voter-Balance Prospective Evaluation",
        "",
        f"Method: `{payload['method_version']}`  ",
        f"Status: **`{payload['status']}`**  ",
        f"Directional result: **`{payload['directional_result']}`**",
        "",
        "## Guardrail",
        "",
        "**Research-only. Market Value V1 remains on `league_only.player_ratings`.**",
        "",
        "This evaluation freezes a KTC rating snapshot, then scores raw and "
        "voter-balanced Bradley-Terry probabilities only against league ballots "
        "submitted afterward. Evaluation windows are disjoint, so the same future "
        "ballot is not repeatedly counted across successive snapshots.",
        "",
        "## Evidence volume",
        "",
        f"- Distinct rating snapshots: **{c['distinct_rating_snapshots']}**",
        f"- Eligible future ballots: **{c['eligible_future_ballots_across_disjoint_windows']}**",
        f"- Distinct future voters: **{c['distinct_future_voters_across_windows']}**",
        f"- Evidence threshold: **{payload['thresholds']['minimum_eligible_future_ballots']} ballots** "
        f"and **{payload['thresholds']['minimum_distinct_future_voters']} voters**",
        "",
        "## Aggregate metrics",
        "",
        "| Target | Model | Log loss ↓ | Brier ↓ | Pairwise accuracy ↑ |",
        "|---|---|---:|---:|---:|",
    ]

    for scheme, label in (
        ("raw_future_stream", "Raw future stream"),
        ("equal_voter_future_consensus", "Equal-voter future consensus"),
    ):
        section = payload["aggregate_metrics"][scheme]
        for model, model_label in (("raw_model", "Raw KTC"), ("balanced_model", "Balanced KTC")):
            m = section[model]
            acc = (
                f"{m['pairwise_accuracy_pct']:.2f}%"
                if m["pairwise_accuracy_pct"] is not None
                else "—"
            )
            lines.append(
                f"| {label} | {model_label} | "
                f"{m['log_loss'] if m['log_loss'] is not None else '—'} | "
                f"{m['brier_score'] if m['brier_score'] is not None else '—'} | {acc} |"
            )

    lines.extend([
        "",
        "Negative `balanced_minus_raw` log-loss/Brier deltas favor the balanced model.",
        "",
        "## Interval detail",
        "",
        "| Snapshot | Window end | Future ballots | Voters | Consensus Δ log loss | Consensus Δ Brier |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for interval in payload["intervals"]:
        d = interval["metrics"]["equal_voter_future_consensus"][
            "difference_balanced_minus_raw"
        ]
        lines.append(
            f"| {interval['snapshot_ktc_generated_at']} | "
            f"{interval['window_end_utc'] or 'current'} | "
            f"{interval['eligible_future_ballots']} | "
            f"{interval['distinct_future_voters']} | "
            f"{d['balanced_minus_raw_log_loss'] if d['balanced_minus_raw_log_loss'] is not None else '—'} | "
            f"{d['balanced_minus_raw_brier_score'] if d['balanced_minus_raw_brier_score'] is not None else '—'} |"
        )

    lines.extend([
        "",
        "## Decision rule",
        "",
        "The primary research target is **equal-voter future consensus**, because it "
        "prevents one future high-volume voter from defining the evaluation target. "
        "The raw future stream is retained as a secondary reality check.",
        "",
        "A single favorable interval is not enough to promote voter-balanced ratings. "
        "Promotion would require a sustained advantage across multiple intervals, "
        "enough future ballots, and multiple distinct voters.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


def check_outputs() -> None:
    payload = read_json(OUTPUT_JSON)
    if payload.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Prospective KTC output has wrong method_version")
    if payload.get("research_only") is not True:
        raise RuntimeError("Prospective KTC output lost research-only guardrail")
    if payload.get("market_value_v1_source_changed") is not False:
        raise RuntimeError("Prospective KTC output incorrectly claims a Market Value change")
    if not OUTPUT_MD.exists():
        raise RuntimeError("Prospective KTC markdown output is missing")
    md = OUTPUT_MD.read_text(encoding="utf-8")
    if "Market Value V1 remains" not in md or "Decision rule" not in md:
        raise RuntimeError("Prospective KTC markdown output is missing guardrail text")
    print("Prospective KTC outputs are current and guarded.")


def run_selftest() -> None:
    base = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    snapshot = {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "status": "research_only_no_market_value_change",
        "ktc_generated_at": iso_z(base),
        "captured_at_utc": iso_z(base),
        "raw_player_ratings": {"a": 4.0, "b": 2.0, "c": 1.0},
        "balanced_player_ratings": {"a": 5.0, "b": 2.0, "c": 1.0},
        "_freeze_dt": base,
    }

    rows = []
    for voter in ("1", "2", "3", "4"):
        rows.append({
            "timestamp": iso_z(base.replace(hour=13)),
            "voter_roster_id": voter,
            "keep": "a",
            "trade": "b",
            "cut": "c",
        })

    interval = evaluate_interval(snapshot, eligible_league_rows(rows), None)
    assert interval["eligible_future_ballots"] == 4
    assert interval["distinct_future_voters"] == 4
    raw_ll = interval["metrics"]["equal_voter_future_consensus"]["raw_model"]["log_loss"]
    bal_ll = interval["metrics"]["equal_voter_future_consensus"]["balanced_model"]["log_loss"]
    assert bal_ll < raw_ll

    payload = build_evaluation([snapshot], rows)
    assert payload["counts"]["eligible_future_ballots_across_disjoint_windows"] == 4
    assert payload["status"] == "READY_WAITING_FOR_MORE_FUTURE_VOTES"
    assert payload["market_value_v1_source_changed"] is False
    assert "equal_voter_future_consensus" in payload["aggregate_metrics"]
    md = render_markdown(payload)
    assert "Research-only" in md
    assert "Equal-voter future consensus" in md
    print(
        "KTC prospective evaluator self-test passed: future-only filtering, "
        "disjoint-window metrics, equal-voter target, directionality, and guardrails."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true")
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

    if args.snapshot:
        ktc = read_json(KTC_PATH)
        write_snapshot(make_snapshot(ktc))

    snapshots = load_snapshots()
    votes = ktc_pipeline.fetch_votes()
    payload = build_evaluation(snapshots, votes)

    if args.write:
        write_outputs(payload)
    else:
        print(render_markdown(payload))


if __name__ == "__main__":
    main()

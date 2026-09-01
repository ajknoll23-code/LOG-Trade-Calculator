#!/usr/bin/env python3
"""
evaluate_market_history.py

Out-of-sample MARKET evaluator for Trade Desk historical snapshots.

This is deliberately separate from evaluate_model_history.py:
- fundamental-v1 asks whether the calculator predicts future fantasy production.
- market-v1 asks whether the calculator anticipates future internal league-market movement.

KTC/internal league ratings are a market target here, NOT fundamental truth.

Frozen MARKET_BACKTEST_V1 protocol
----------------------------------
1. Only refresh_mode == "full" snapshots are market observations because KTC is
   refreshed only on full maintenance passes.
2. Keep at most one market observation per ISO calendar week. If manual full
   reruns happen in the same week, the latest capture wins.
3. Evaluate exact +1, +2, and +4 ISO-week horizons. Missing target weeks remain
   pending; never substitute the next available market snapshot.
4. Primary benchmark universe is the SAME players for both predictors:
      origin Trade Desk value + origin market rating + future market rating.
5. The required naive baseline is today's market rating predicting the future
   market. Trade Desk gets incremental credit only if it beats persistence.
6. A separate disagreement test asks whether:
      model percentile - current market percentile
   predicts:
      future market percentile - current market percentile.
7. Identity matching is conservative. Exact normalized model keys beat aliases;
   same-player duplicate KTC spellings are never double-counted.

Outputs with --write
--------------------
research/model-history/evaluation/market_latest.json
research/model-history/evaluation/market_latest.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Reuse the already-reviewed metric primitives so fundamental and market reports
# do not drift into two subtly different definitions of Spearman/pairwise/top-N.
import evaluate_model_history as metrics


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "research" / "model-history" / "snapshots"
OUTPUT_DIR = REPO_ROOT / "research" / "model-history" / "evaluation"
OUTPUT_JSON = OUTPUT_DIR / "market_latest.json"
OUTPUT_MD = OUTPUT_DIR / "market_latest.md"

MARKET_HORIZONS_WEEKS = (1, 2, 4)
MIN_MARKET_RATINGS = 20
TOP_NS = (12, 24, 50)

# Audited display-name differences between PLAYER_DB keys and market-entered names.
MARKET_NAME_ALIASES = {
    "michael penix": "michael penix jr",
    "harold perkins": "harold perkins jr",
    "zonovan knight": "bam knight",
}

PROTOCOL = {
    "protocol_version": "market-v1",
    "market_source": "snapshot.sources.ktc.league_only.player_ratings",
    "observation_rule": "full refresh snapshots only; latest capture per ISO week retained",
    "horizons_iso_weeks": list(MARKET_HORIZONS_WEEKS),
    "target_semantics": "future internal league market state, not fundamental truth",
    "primary_universe": "origin model value + origin market rating + future market rating",
    "baseline": "origin market rating predicts future market rating",
    "incremental_model_test": "origin Trade Desk value vs future market, minus current-market baseline performance",
    "movement_test": "origin model-market percentile gap predicts future market percentile change",
    "identity_resolution": "exact model key > audited/suffix alias > unique first-initial surname; no duplicate counting",
    "subgroups": ["position", "unit"],
}
PROTOCOL_SHA256 = hashlib.sha256(
    json.dumps(PROTOCOL, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def parse_utc(value: str) -> datetime:
    if not value:
        raise RuntimeError("Missing UTC timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_name(value: str) -> str:
    value = (value or "").lower().strip().replace("’", "'")
    value = re.sub(r"[.'’-]", "", value)
    return " ".join(value.split())


def strip_suffix(value: str) -> str:
    parts = normalize_name(value).split()
    if parts and parts[-1] in {"jr", "ii", "iii", "iv"}:
        parts = parts[:-1]
    return " ".join(parts)


def percentile_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    if len(values) == 1:
        return [0.5]
    ranks = metrics.rankdata(values)
    return [(rank - 1.0) / (len(values) - 1.0) for rank in ranks]


def directional_accuracy(gaps: list[float], changes: list[float]) -> tuple[float | None, int]:
    correct = 0
    comparable = 0
    for gap, change in zip(gaps, changes):
        if gap == 0 or change == 0:
            continue
        comparable += 1
        if (gap > 0) == (change > 0):
            correct += 1
    return ((correct / comparable) if comparable else None, comparable)


def unit_bucket(pos: str) -> str:
    if pos in {"QB", "RB", "WR", "TE"}:
        return "offense"
    if pos in {"DL", "LB", "DB"}:
        return "idp"
    if pos == "K":
        return "kicker"
    return "other"


def iso_week_key(timestamp: str) -> str:
    year, week, _ = parse_utc(timestamp).isocalendar()
    return f"{year}-W{week:02d}"


def target_iso_week_key(timestamp: str, weeks_ahead: int) -> str:
    future = parse_utc(timestamp) + timedelta(days=7 * weeks_ahead)
    year, week, _ = future.isocalendar()
    return f"{year}-W{week:02d}"


def market_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return ((snapshot.get("sources") or {}).get("ktc") or {})


def raw_league_ratings(snapshot: dict[str, Any]) -> dict[str, float]:
    ratings = ((market_payload(snapshot).get("league_only") or {}).get("player_ratings") or {})
    if not isinstance(ratings, dict):
        return {}
    out = {}
    for name, value in ratings.items():
        try:
            out[str(name)] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def league_votes(snapshot: dict[str, Any]) -> int | None:
    ktc = market_payload(snapshot)
    value = ktc.get("league_votes")
    if value is None:
        value = (ktc.get("league_only") or {}).get("votes_counted")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def dominant_voter_share(snapshot: dict[str, Any]) -> float | None:
    shares = market_payload(snapshot).get("voter_share_within_league") or {}
    values = []
    for row in shares.values():
        try:
            values.append(float((row or {}).get("share_pct")))
        except (TypeError, ValueError):
            continue
    return max(values) if values else None


def build_alias_index(model_keys: list[str]) -> dict[str, list[tuple[str, int, str]]]:
    """Alias -> (model_key, priority, method), lower priority is stronger."""
    index: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    normalized = {key: normalize_name(key) for key in model_keys}

    for key, norm in normalized.items():
        if norm:
            index[norm].append((key, 0, "exact_model_key"))

    for alias, target in MARKET_NAME_ALIASES.items():
        target_norm = normalize_name(target)
        matches = [key for key, norm in normalized.items() if norm == target_norm]
        if len(matches) == 1:
            index[normalize_name(alias)].append((matches[0], 1, "audited_alias"))

    suffix_groups: dict[str, list[str]] = defaultdict(list)
    for key, norm in normalized.items():
        stripped = strip_suffix(norm)
        if stripped and stripped != norm:
            suffix_groups[stripped].append(key)
    for alias, keys in suffix_groups.items():
        if len(keys) == 1:
            index[alias].append((keys[0], 1, "unique_suffix_stripped"))

    initial_groups: dict[str, list[str]] = defaultdict(list)
    for key, norm in normalized.items():
        parts = strip_suffix(norm).split()
        if len(parts) >= 2:
            initial_groups[f"{parts[0][0]} {parts[-1]}"].append(key)
    for alias, keys in initial_groups.items():
        if len(keys) == 1:
            index[alias].append((keys[0], 2, "unique_initial_surname"))

    return dict(index)


def resolve_market_ratings(snapshot: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
    model_values = (snapshot.get("model") or {}).get("calculator_values") or {}
    if not isinstance(model_values, dict) or len(model_values) < 100:
        raise RuntimeError("Snapshot calculator_values are missing or unexpectedly small")

    raw = raw_league_ratings(snapshot)
    aliases = build_alias_index(list(model_values))
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unmatched = []
    ambiguous = []

    for raw_name, rating in raw.items():
        norm = normalize_name(raw_name)
        options = list({tuple(x) for x in aliases.get(norm, [])})
        if not options:
            unmatched.append({"raw_name": raw_name, "normalized_name": norm, "rating": rating})
            continue

        best_priority = min(x[1] for x in options)
        best = [x for x in options if x[1] == best_priority]
        target_keys = sorted({x[0] for x in best})
        if len(target_keys) != 1:
            ambiguous.append({
                "raw_name": raw_name,
                "normalized_name": norm,
                "rating": rating,
                "candidate_model_keys": target_keys,
            })
            continue

        model_key = target_keys[0]
        method = sorted(x[2] for x in best if x[0] == model_key)[0]
        candidates[model_key].append({
            "raw_name": raw_name,
            "rating": rating,
            "priority": best_priority,
            "method": method,
        })

    resolved: dict[str, float] = {}
    duplicate_aliases = []
    methods: dict[str, int] = defaultdict(int)

    for model_key, rows in candidates.items():
        rows = sorted(rows, key=lambda row: (row["priority"], normalize_name(row["raw_name"])))
        keep = rows[0]
        resolved[model_key] = float(keep["rating"])
        methods[keep["method"]] += 1
        if len(rows) > 1:
            duplicate_aliases.append({
                "model_key": model_key,
                "retained": keep,
                "discarded": rows[1:],
            })

    return resolved, {
        "raw_rating_count": len(raw),
        "resolved_model_player_count": len(resolved),
        "match_method_counts": dict(sorted(methods.items())),
        "unmatched_market_names": unmatched,
        "ambiguous_market_names": ambiguous,
        "duplicate_aliases_resolving_to_same_model_player": duplicate_aliases,
    }


def load_snapshot(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid historical snapshot {path.name}: {exc}") from exc
    payload["_source_filename"] = path.name
    return payload


def load_full_market_snapshots(snapshot_dir: Path = SNAPSHOT_DIR) -> list[dict[str, Any]]:
    if not snapshot_dir.exists():
        raise RuntimeError(f"Snapshot directory does not exist: {snapshot_dir}")
    out = []
    for path in sorted(snapshot_dir.glob("*.json")):
        snapshot = load_snapshot(path)
        if snapshot.get("refresh_mode") != "full":
            continue
        if len(raw_league_ratings(snapshot)) < MIN_MARKET_RATINGS:
            continue
        out.append(snapshot)
    if not out:
        raise RuntimeError("No usable full historical market snapshots found")
    return out


def dedupe_weekly_market_states(
    snapshots: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for snapshot in snapshots:
        groups[iso_week_key(snapshot["captured_at_utc"])].append(snapshot)

    retained = []
    audit = []
    for week_key, group in sorted(groups.items()):
        group = sorted(group, key=lambda row: parse_utc(row["captured_at_utc"]))
        keep = group[-1]
        keep["_market_week"] = week_key
        retained.append(keep)
        if len(group) > 1:
            audit.append({
                "iso_week": week_key,
                "retained": keep.get("_source_filename"),
                "retained_captured_at_utc": keep["captured_at_utc"],
                "discarded": [
                    {"filename": row.get("_source_filename"), "captured_at_utc": row["captured_at_utc"]}
                    for row in group[:-1]
                ],
            })
    retained.sort(key=lambda row: parse_utc(row["captured_at_utc"]))
    return retained, audit


def predictor_metrics(
    names: list[str], predictor: list[float], future: list[float], include_top_n: bool
) -> dict[str, Any]:
    p = metrics.pearson(predictor, future)
    s = metrics.spearman(predictor, future)
    pair, comparable = metrics.pairwise_ordering_accuracy(predictor, future)
    out = {
        "n": len(names),
        "pearson": round(p, 6) if p is not None else None,
        "spearman": round(s, 6) if s is not None else None,
        "pairwise_ordering_accuracy": round(pair, 6) if pair is not None else None,
        "comparable_pairs": comparable,
    }
    if include_top_n:
        out["top_n"] = {
            str(n): metrics.tie_aware_top_n_hit_rate(names, predictor, future, n)
            for n in TOP_NS
        }
    return out


def build_overlap_records(
    origin: dict[str, Any], future: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    model = (origin.get("model") or {}).get("calculator_values") or {}
    origin_market, origin_audit = resolve_market_ratings(origin)
    future_market, future_audit = resolve_market_ratings(future)
    keys = sorted(set(model) & set(origin_market) & set(future_market))

    records = []
    for key in keys:
        info = model[key]
        pos = str(info.get("pos") or "")
        records.append({
            "model_key": key,
            "pos": pos,
            "unit": unit_bucket(pos),
            "model_value": float(info.get("value") or 0.0),
            "origin_market_rating": float(origin_market[key]),
            "future_market_rating": float(future_market[key]),
        })
    return records, {
        "origin_market_identity": origin_audit,
        "future_market_identity": future_audit,
        "same_player_benchmark_universe_count": len(records),
    }


def score_overlap(records: list[dict[str, Any]], include_top_n: bool) -> dict[str, Any]:
    names = [row["model_key"] for row in records]
    model = [row["model_value"] for row in records]
    current = [row["origin_market_rating"] for row in records]
    future = [row["future_market_rating"] for row in records]

    td = predictor_metrics(names, model, future, include_top_n)
    baseline = predictor_metrics(names, current, future, include_top_n)

    model_pct = percentile_scores(model)
    current_pct = percentile_scores(current)
    future_pct = percentile_scores(future)
    gaps = [m - c for m, c in zip(model_pct, current_pct)]
    changes = [f - c for f, c in zip(future_pct, current_pct)]
    gap_p = metrics.pearson(gaps, changes)
    gap_s = metrics.spearman(gaps, changes)
    direction, direction_n = directional_accuracy(gaps, changes)

    def delta(a: Any, b: Any) -> float | None:
        if a is None or b is None:
            return None
        return round(float(a) - float(b), 6)

    out = {
        "n": len(records),
        "trade_desk_value_predicts_future_market": td,
        "current_market_predicts_future_market_baseline": baseline,
        "incremental_vs_current_market_baseline": {
            "pearson_delta": delta(td["pearson"], baseline["pearson"]),
            "spearman_delta": delta(td["spearman"], baseline["spearman"]),
            "pairwise_accuracy_delta": delta(
                td["pairwise_ordering_accuracy"], baseline["pairwise_ordering_accuracy"]
            ),
        },
        "model_market_gap_predicts_future_market_change": {
            "pearson": round(gap_p, 6) if gap_p is not None else None,
            "spearman": round(gap_s, 6) if gap_s is not None else None,
            "directional_accuracy": round(direction, 6) if direction is not None else None,
            "directional_comparable_players": direction_n,
        },
    }

    if include_top_n:
        out["top_n_baseline_comparison"] = {}
        for n in TOP_NS:
            td_row = (td.get("top_n") or {}).get(str(n))
            base_row = (baseline.get("top_n") or {}).get(str(n))
            td_hit = td_row.get("hit_rate") if td_row else None
            base_hit = base_row.get("hit_rate") if base_row else None
            out["top_n_baseline_comparison"][str(n)] = {
                "trade_desk_hit_rate": td_hit,
                "current_market_baseline_hit_rate": base_hit,
                "hit_rate_delta": delta(td_hit, base_hit),
            }
    return out


def subgroup_scores(records: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        groups[str(row.get(field) or "unknown")].append(row)
    return {key: score_overlap(rows, include_top_n=False) for key, rows in sorted(groups.items())}


def evaluate_pair(origin: dict[str, Any], future: dict[str, Any], weeks_ahead: int) -> dict[str, Any]:
    records, identity_audit = build_overlap_records(origin, future)
    return {
        "status": "evaluated",
        "weeks_ahead": weeks_ahead,
        "origin": {
            "filename": origin.get("_source_filename"),
            "captured_at_utc": origin["captured_at_utc"],
            "iso_week": origin["_market_week"],
            "league_votes": league_votes(origin),
            "dominant_voter_share_pct": dominant_voter_share(origin),
        },
        "future": {
            "filename": future.get("_source_filename"),
            "captured_at_utc": future["captured_at_utc"],
            "iso_week": future["_market_week"],
            "league_votes": league_votes(future),
            "dominant_voter_share_pct": dominant_voter_share(future),
        },
        "identity_audit": identity_audit,
        "overall": score_overlap(records, include_top_n=True),
        "by_position": subgroup_scores(records, "pos"),
        "by_unit": subgroup_scores(records, "unit"),
    }


def build_evaluation(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    states, dedupe_audit = dedupe_weekly_market_states(snapshots)
    by_week = {state["_market_week"]: state for state in states}
    observations = []
    evaluated = 0
    pending = 0

    for origin in states:
        horizons = {}
        for weeks_ahead in MARKET_HORIZONS_WEEKS:
            target_week = target_iso_week_key(origin["captured_at_utc"], weeks_ahead)
            future = by_week.get(target_week)
            if future is None:
                horizons[f"{weeks_ahead}w"] = {
                    "status": "pending",
                    "weeks_ahead": weeks_ahead,
                    "target_iso_week": target_week,
                }
                pending += 1
            else:
                horizons[f"{weeks_ahead}w"] = evaluate_pair(origin, future, weeks_ahead)
                evaluated += 1

        observations.append({
            "origin_snapshot": {
                "filename": origin.get("_source_filename"),
                "captured_at_utc": origin["captured_at_utc"],
                "iso_week": origin["_market_week"],
                "league_votes": league_votes(origin),
                "dominant_voter_share_pct": dominant_voter_share(origin),
            },
            "horizons": horizons,
        })

    return {
        "schema_version": 1,
        "protocol": PROTOCOL,
        "protocol_sha256": PROTOCOL_SHA256,
        "inputs": {
            "full_snapshot_count_seen": len(snapshots),
            "weekly_market_state_count_after_dedup": len(states),
        },
        "summary": {
            "deduplicated_same_week_snapshot_count": len(snapshots) - len(states),
            "evaluated_origin_horizon_pairs": evaluated,
            "pending_origin_horizon_pairs": pending,
        },
        "weekly_market_state_deduplication_audit": dedupe_audit,
        "observations": observations,
    }


def fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Trade Desk Historical Market Backtest",
        "",
        f"Protocol: `{PROTOCOL['protocol_version']}`  ",
        f"Protocol SHA256: `{payload['protocol_sha256']}`",
        "",
        "## Status",
        "",
        f"- Full snapshots seen: **{payload['inputs']['full_snapshot_count_seen']}**",
        f"- Weekly market states after deduplication: **{payload['inputs']['weekly_market_state_count_after_dedup']}**",
        f"- Same-week snapshots deduplicated: **{payload['summary']['deduplicated_same_week_snapshot_count']}**",
        f"- Evaluated origin/horizon pairs: **{payload['summary']['evaluated_origin_horizon_pairs']}**",
        f"- Pending origin/horizon pairs: **{payload['summary']['pending_origin_horizon_pairs']}**",
        "",
        "## What this measures",
        "",
        "This is a **market-target** backtest, not a fundamental player-quality backtest. "
        "The current league market is the required persistence baseline. Trade Desk only "
        "adds market-predictive value when it beats that baseline on the same players.",
        "",
        "## Evaluated horizons",
        "",
    ]

    rows = []
    for observation in payload["observations"]:
        for horizon_name, horizon in observation["horizons"].items():
            if horizon["status"] != "evaluated":
                continue
            overall = horizon["overall"]
            td = overall["trade_desk_value_predicts_future_market"]
            baseline = overall["current_market_predicts_future_market_baseline"]
            incremental = overall["incremental_vs_current_market_baseline"]
            movement = overall["model_market_gap_predicts_future_market_change"]
            rows.append((
                horizon["origin"]["iso_week"],
                horizon["future"]["iso_week"],
                horizon_name,
                overall["n"],
                td["spearman"],
                baseline["spearman"],
                incremental["spearman_delta"],
                movement["spearman"],
                movement["directional_accuracy"],
            ))

    if not rows:
        lines.extend([
            "No future weekly market state is mature yet. This is expected until a later "
            "full-refresh week creates the first true out-of-sample market target.",
            "",
        ])
    else:
        lines.extend([
            "| Origin | Future | Horizon | N | TD→future Spearman | Current market→future | Incremental Δ | Gap→change Spearman | Directional acc. |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|",
        ])
        for row in rows:
            lines.append(
                f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {fmt(row[4])} | "
                f"{fmt(row[5])} | {fmt(row[6])} | {fmt(row[7])} | {fmt(row[8])} |"
            )
        lines.append("")

    lines.extend([
        "## Interpretation guardrails",
        "",
        "- Negative incremental delta means current-market persistence beat Trade Desk for that horizon.",
        "- Positive gap→change relationship means model/market disagreement anticipated later market movement.",
        "- Voter concentration is preserved per evaluated pair; concentrated voting makes apparent movement less independent.",
        "- This report never rewrites player values, position weights, or Team Utility automatically.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    print(
        f"Market evaluator wrote {OUTPUT_JSON.relative_to(REPO_ROOT)} and "
        f"{OUTPUT_MD.relative_to(REPO_ROOT)} | "
        f"weekly_states={payload['inputs']['weekly_market_state_count_after_dedup']} | "
        f"evaluated_pairs={payload['summary']['evaluated_origin_horizon_pairs']}"
    )


def synthetic_snapshot(
    captured_at_utc: str,
    filename: str,
    model_values: dict[str, dict[str, Any]],
    ratings: dict[str, float],
    votes: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "captured_at_utc": captured_at_utc,
        "refresh_mode": "full",
        "model": {"calculator_values": model_values},
        "sources": {"ktc": {
            "league_votes": votes,
            "voter_share_within_league": {
                "1": {"votes": int(votes * 0.6), "share_pct": 60.0},
                "2": {"votes": votes - int(votes * 0.6), "share_pct": 40.0},
            },
            "league_only": {"votes_counted": votes, "player_ratings": ratings},
        }},
        "_source_filename": filename,
    }


def run_selftest() -> None:
    model_values = {
        f"player {i+1:03d}": {"pos": "WR" if i < 60 else "LB", "value": (120 - i) * 100}
        for i in range(120)
    }
    current = {f"player {i+1:03d}": float(120 - i) for i in range(120)}
    current["player 003"], current["player 080"] = current["player 080"], current["player 003"]
    current["player 004"], current["player 090"] = current["player 090"], current["player 004"]
    future = {f"player {i+1:03d}": float((120 - i) * 2) for i in range(120)}

    snapshots = [
        synthetic_snapshot("2026-09-01T15:00:00Z", "w1-early.json", model_values, current, 100),
        synthetic_snapshot("2026-09-02T15:00:00Z", "w1-late.json", model_values, current, 110),
        synthetic_snapshot("2026-09-09T15:00:00Z", "w2.json", model_values, future, 125),
    ]
    payload = build_evaluation(snapshots)
    assert payload["inputs"]["weekly_market_state_count_after_dedup"] == 2
    assert payload["summary"]["deduplicated_same_week_snapshot_count"] == 1
    first = payload["observations"][0]
    assert first["origin_snapshot"]["filename"] == "w1-late.json"
    one_week = first["horizons"]["1w"]
    assert one_week["status"] == "evaluated"
    td_s = one_week["overall"]["trade_desk_value_predicts_future_market"]["spearman"]
    base_s = one_week["overall"]["current_market_predicts_future_market_baseline"]["spearman"]
    assert td_s == 1.0
    assert td_s > base_s
    assert one_week["overall"]["incremental_vs_current_market_baseline"]["spearman_delta"] > 0
    assert first["horizons"]["2w"]["status"] == "pending"

    alias_model = dict(model_values)
    alias_model["michael penix jr"] = {"pos": "QB", "value": 999}
    alias_snapshot = synthetic_snapshot(
        "2026-09-01T15:00:00Z",
        "alias.json",
        alias_model,
        {**current, "michael penix": 4.2},
        100,
    )
    resolved, audit = resolve_market_ratings(alias_snapshot)
    assert resolved["michael penix jr"] == 4.2
    assert audit["ambiguous_market_names"] == []

    print(
        "evaluate_market_history self-test passed: weekly deduplication, exact-horizon "
        "targeting, market-persistence baseline, incremental model test, and conservative identity resolution."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Trade Desk against future internal league market states.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    payload = build_evaluation(load_full_market_snapshots())
    if args.write:
        write_outputs(payload)
    else:
        print(json.dumps({
            "protocol_version": PROTOCOL["protocol_version"],
            "protocol_sha256": PROTOCOL_SHA256,
            "full_snapshot_count_seen": payload["inputs"]["full_snapshot_count_seen"],
            "weekly_market_state_count_after_dedup": payload["inputs"]["weekly_market_state_count_after_dedup"],
            "evaluated_origin_horizon_pairs": payload["summary"]["evaluated_origin_horizon_pairs"],
            "pending_origin_horizon_pairs": payload["summary"]["pending_origin_horizon_pairs"],
        }, indent=2))


if __name__ == "__main__":
    main()

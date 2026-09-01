#!/usr/bin/env python3
"""
capture_model_history.py

Append-only historical evidence capture for Trade Desk model backtesting.
Reuses snapshot_values.py for the deployed fundamental value calculation and
stores the source evidence available at capture time.

Output:
  research/model-history/snapshots/
    <UTC timestamp>_<mode>[_run-<github run id>].json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import snapshot_values

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "index.html"
SLEEPER_PROJECTIONS_PATH = REPO_ROOT / "scripts" / "sleeper_2026_projections.json"
SLEEPER_CATEGORIES_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "sleeper_2026_raw_categories.json"
FANTASYPROS_PATH = REPO_ROOT / "scripts" / "fantasypros_api_normalized_2026.json"
KTC_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "ktc_ratings.json"
IDENTITY_CROSSWALK_PATH = REPO_ROOT / "scripts" / "identity_crosswalk.json"
VALUE_UNCERTAINTY_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "value_uncertainty.json"
MARKET_VALUE_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "market_values.json"

DEFAULT_OUTPUT_DIR = REPO_ROOT / "research" / "model-history" / "snapshots"
RELEVANT_FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "DL", "LB", "DB", "K"}
EMPTY_VALUES = (None, "", 0, 0.0, False)


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Required historical input is missing: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Required historical input is invalid JSON: {path.relative_to(REPO_ROOT)}: {exc}"
        ) from exc


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def compact_nonzero(mapping: Any) -> dict[str, Any]:
    if not isinstance(mapping, dict):
        return {}
    return {str(k): v for k, v in mapping.items() if v not in EMPTY_VALUES}


def git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return os.environ.get("GITHUB_SHA")


def compact_sleeper_projection_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise RuntimeError("Sleeper projection file must contain a JSON list")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({
            "sleeper_id": row.get("sleeper_id"),
            "player": row.get("player"),
            "pos": row.get("pos"),
            "team": row.get("team"),
            "projected_points": row.get("sleeper_2026_proj_total"),
            "weeks_with_projection_data": row.get("weeks_with_projection_data"),
        })
    return out


def compact_sleeper_category_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise RuntimeError("Sleeper raw-category file must contain a JSON list")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        fantasy_positions = row.get("fantasy_positions") or []
        if not isinstance(fantasy_positions, list):
            fantasy_positions = []
        if not RELEVANT_FANTASY_POSITIONS.intersection(map(str, fantasy_positions)):
            continue
        stats = compact_nonzero(row.get("raw_category_season_totals"))
        if not stats:
            continue
        out.append({
            "sleeper_id": row.get("sleeper_id"),
            "player": row.get("player"),
            "pos": row.get("pos"),
            "team": row.get("team"),
            "fantasy_positions": fantasy_positions,
            "weeks_with_projection_data": row.get("weeks_with_projection_data"),
            "projected_categories_nonzero": stats,
        })
    return out


def compact_fantasypros(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("FantasyPros normalized file must contain a JSON object")
    players = payload.get("players")
    if not isinstance(players, list):
        raise RuntimeError("FantasyPros normalized file is missing its players list")

    compact_players = []
    for row in players:
        if not isinstance(row, dict):
            continue
        source_position = row.get("source_position")
        if source_position not in RELEVANT_FANTASY_POSITIONS:
            continue
        compact_players.append({
            "fantasypros_id": row.get("fantasypros_id"),
            "name": row.get("name"),
            "normalized_name": row.get("normalized_name"),
            "source_position": source_position,
            "query_position": row.get("query_position"),
            "team": row.get("team"),
            "fantasypros_stated_points": row.get("fantasypros_stated_points"),
            "trade_desk_normalized_points": row.get("trade_desk_normalized_points"),
            "projected_categories_nonzero": compact_nonzero(row.get("raw_stats_used")),
            "missing_categories": row.get("missing_categories") or [],
        })
    return {
        "generated_at": payload.get("generated_at"),
        "season": payload.get("season"),
        "players": compact_players,
    }


def compact_identity_crosswalk(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise RuntimeError("Identity crosswalk must contain a JSON list")
    keys = (
        "fantasypros_id", "name", "fp_team", "fp_position", "sleeper_id",
        "sleeper_team", "sleeper_pos", "sleeper_fantasy_positions",
        "sleeper_has_signal", "match_method", "match_confidence",
        "had_name_collision", "requires_manual_review", "candidate_sleeper_id",
    )
    return [{k: row.get(k) for k in keys} for row in rows if isinstance(row, dict)]


def compact_value_uncertainty(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("Value uncertainty artifact must contain a JSON object")
    players = payload.get("players")
    if not isinstance(players, dict) or len(players) < 500:
        raise RuntimeError("Value uncertainty artifact has implausibly few players")

    compact_players = {}
    for key, row in players.items():
        if not isinstance(row, dict):
            continue
        signals = row.get("signals") or {}
        compact_players[str(key)] = {
            "center_value": row.get("center_value"),
            "range_low": row.get("range_low"),
            "range_high": row.get("range_high"),
            "relative_half_width": row.get("relative_half_width"),
            "uncertainty_tier": row.get("uncertainty_tier"),
            "projection_provider_count": signals.get("projection_provider_count"),
            "provider_disagreement_component": signals.get("provider_disagreement_component"),
            "history_sampling_component": signals.get("history_sampling_component"),
            "availability_component": signals.get("availability_component"),
            "history_games_2025": signals.get("history_games_2025"),
        }
    return {
        "method_version": payload.get("method_version"),
        "range_semantics": payload.get("range_semantics"),
        "policy_sha256": payload.get("policy_sha256"),
        "counts": payload.get("counts"),
        "position_cohorts": payload.get("position_cohorts"),
        "players": compact_players,
    }


def compact_market_value(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("Market Value artifact must contain a JSON object")
    players = payload.get("players")
    if not isinstance(players, dict) or len(players) < 100:
        raise RuntimeError("Market Value artifact has implausibly few resolved players")

    compact_players = {}
    for key, row in players.items():
        if not isinstance(row, dict):
            continue
        evidence = row.get("evidence") or {}
        compact_players[str(key)] = {
            "pos": row.get("pos"),
            "fundamental_value": row.get("fundamental_value"),
            "market_value": row.get("market_value"),
            "market_minus_fundamental": row.get("market_minus_fundamental"),
            "market_rating": row.get("market_rating"),
            "market_rank": row.get("market_rank"),
            "market_percentile": row.get("market_percentile"),
            "same_position_pairwise_observations": evidence.get("same_position_pairwise_observations"),
            "same_position_enough_data": evidence.get("same_position_enough_data"),
        }
    return {
        "method_version": payload.get("method_version"),
        "scale_semantics": payload.get("scale_semantics"),
        "policy_sha256": payload.get("policy_sha256"),
        "market_quality": payload.get("market_quality"),
        "counts": payload.get("counts"),
        "identity_audit": payload.get("identity_audit"),
        "players": compact_players,
    }


def build_snapshot(mode: str) -> dict[str, Any]:
    required_paths = {
        "index_html": INDEX_PATH,
        "sleeper_projections": SLEEPER_PROJECTIONS_PATH,
        "sleeper_raw_categories": SLEEPER_CATEGORIES_PATH,
        "fantasypros_normalized": FANTASYPROS_PATH,
        "ktc_ratings": KTC_PATH,
        "identity_crosswalk": IDENTITY_CROSSWALK_PATH,
        "value_uncertainty": VALUE_UNCERTAINTY_PATH,
        "market_value": MARKET_VALUE_PATH,
    }
    for path in required_paths.values():
        if not path.exists():
            raise RuntimeError(f"Required historical input is missing: {path.relative_to(REPO_ROOT)}")

    cfg = snapshot_values.load_from_html(INDEX_PATH)
    calculator_values = snapshot_values.compute_all_values(cfg)

    sleeper_projections_raw = read_json(SLEEPER_PROJECTIONS_PATH)
    sleeper_categories_raw = read_json(SLEEPER_CATEGORIES_PATH)
    fantasypros_raw = read_json(FANTASYPROS_PATH)
    ktc_raw = read_json(KTC_PATH)
    identity_raw = read_json(IDENTITY_CROSSWALK_PATH)
    uncertainty_raw = read_json(VALUE_UNCERTAINTY_PATH)
    market_value_raw = read_json(MARKET_VALUE_PATH)

    sleeper_projections = compact_sleeper_projection_rows(sleeper_projections_raw)
    sleeper_categories = compact_sleeper_category_rows(sleeper_categories_raw)
    fantasypros = compact_fantasypros(fantasypros_raw)
    identity_crosswalk = compact_identity_crosswalk(identity_raw)
    value_uncertainty = compact_value_uncertainty(uncertainty_raw)
    market_value = compact_market_value(market_value_raw)

    source_hashes = {name: sha256_file(path) for name, path in required_paths.items()}
    fingerprint_input = {
        "schema_version": 1,
        "source_hashes": source_hashes,
        "position_weight": cfg["position_weight"],
        "age_curve": cfg["age_curve"],
        "role_mult": cfg["role_mult"],
        "qb_post_peak_floor": cfg["qb_post_peak_floor"],
        "lb_post_peak_decay_power": cfg["lb_post_peak_decay_power"],
    }
    state_fingerprint = hashlib.sha256(
        json.dumps(fingerprint_input, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    now = datetime.now(timezone.utc)
    snapshot = {
        "schema_version": 1,
        "captured_at_utc": now.isoformat().replace("+00:00", "Z"),
        "refresh_mode": mode,
        "github": {
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "workflow": os.environ.get("GITHUB_WORKFLOW"),
            "base_git_sha": git_head(),
        },
        "state_fingerprint_sha256": state_fingerprint,
        "source_file_sha256": source_hashes,
        "model": {
            "source_of_truth": "index.html",
            "player_count": len(calculator_values),
            "position_weight": cfg["position_weight"],
            "age_curve": cfg["age_curve"],
            "role_mult": cfg["role_mult"],
            "qb_post_peak_floor": cfg["qb_post_peak_floor"],
            "lb_post_peak_decay_power": cfg["lb_post_peak_decay_power"],
            "production_multipliers": cfg["prod_mult"],
            "no_real_production_history": sorted(cfg["no_real_history"]),
            "calculator_values": calculator_values,
        },
        "sources": {
            "sleeper": {
                "projection_player_count": len(sleeper_projections),
                "category_signal_player_count": len(sleeper_categories),
                "projections": sleeper_projections,
                "category_projections": sleeper_categories,
            },
            "fantasypros": {
                "generated_at": fantasypros.get("generated_at"),
                "season": fantasypros.get("season"),
                "player_count": len(fantasypros["players"]),
                "players": fantasypros["players"],
            },
            "ktc": ktc_raw,
            "identity_crosswalk": {
                "row_count": len(identity_crosswalk),
                "rows": identity_crosswalk,
            },
            "value_uncertainty": value_uncertainty,
            "market_value": market_value,
        },
    }
    validate_snapshot(snapshot)
    return snapshot


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("schema_version") != 1:
        raise RuntimeError("Unexpected model-history schema_version")

    model = snapshot.get("model") or {}
    values = model.get("calculator_values")
    if not isinstance(values, dict) or len(values) < 500:
        raise RuntimeError("Calculator history capture is unexpectedly small")

    position_weight = model.get("position_weight") or {}
    missing_positions = sorted(RELEVANT_FANTASY_POSITIONS.difference(position_weight))
    if missing_positions:
        raise RuntimeError(f"Model history is missing position weights: {missing_positions}")

    sources = snapshot.get("sources") or {}
    sleeper = sources.get("sleeper") or {}
    fp = sources.get("fantasypros") or {}
    ktc = sources.get("ktc") or {}
    crosswalk = sources.get("identity_crosswalk") or {}
    uncertainty = sources.get("value_uncertainty") or {}
    market_value = sources.get("market_value") or {}

    if sleeper.get("projection_player_count", 0) < 100:
        raise RuntimeError("Sleeper history capture has implausibly few projection players")
    if sleeper.get("category_signal_player_count", 0) < 100:
        raise RuntimeError("Sleeper history capture has implausibly few category-signal players")
    if fp.get("player_count", 0) < 500:
        raise RuntimeError("FantasyPros history capture has implausibly few players")
    if not isinstance(ktc, dict) or "total_votes_counted" not in ktc:
        raise RuntimeError("KTC history capture is malformed")
    if crosswalk.get("row_count", 0) < 100:
        raise RuntimeError("Identity history capture has implausibly few rows")

    uncertainty_players = uncertainty.get("players")
    if not isinstance(uncertainty_players, dict) or len(uncertainty_players) < 500:
        raise RuntimeError("Uncertainty history capture has implausibly few players")
    if uncertainty.get("range_semantics") != "sensitivity_envelope_v1_not_probability_interval":
        raise RuntimeError("Uncertainty history capture has unexpected range semantics")

    market_players = market_value.get("players")
    if not isinstance(market_players, dict) or len(market_players) < 100:
        raise RuntimeError("Market Value history capture has implausibly few players")
    if market_value.get("scale_semantics") != "league_rank_quantile_mapped_to_trade_desk_points_v1":
        raise RuntimeError("Market Value history capture has unexpected scale semantics")

    source_hashes = snapshot.get("source_file_sha256") or {}
    if len(source_hashes) != 8 or any(len(str(v)) != 64 for v in source_hashes.values()):
        raise RuntimeError("Model-history source hashes are malformed")


def write_snapshot(snapshot: dict[str, Any], output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    captured = snapshot["captured_at_utc"].replace(":", "").replace("-", "")
    mode = snapshot["refresh_mode"]
    run_id = (snapshot.get("github") or {}).get("run_id")
    suffix = f"_run-{run_id}" if run_id else ""
    out_path = output_dir / f"{captured}_{mode}{suffix}.json"
    out_path.write_text(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return out_path


def run_selftest() -> None:
    snapshot = build_snapshot("manual")
    validate_snapshot(snapshot)
    assert snapshot["model"]["source_of_truth"] == "index.html"
    assert len(snapshot["model"]["calculator_values"]) >= 500
    assert snapshot["sources"]["value_uncertainty"]["range_semantics"] == (
        "sensitivity_envelope_v1_not_probability_interval"
    )
    assert snapshot["sources"]["market_value"]["scale_semantics"] == (
        "league_rank_quantile_mapped_to_trade_desk_points_v1"
    )
    print(
        "capture_model_history self-test passed: production-parity values, "
        "source evidence, uncertainty state, and separate Market Value state."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("full", "light", "manual"), default="manual")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    snapshot = build_snapshot(args.mode)
    out_path = write_snapshot(snapshot)
    print(f"Historical model snapshot written: {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Canonical 2025 production + durability history component for Trade Desk.

This module extracts the *existing* history-side math from
``prod_mult_pipeline.py`` without changing its assumptions. It deliberately
contains no 2026 projection-source logic and no replacement-level/prod_mult
logic.

Current history formula (preserved exactly for V1 integration):

    shrunk_ppg = (n * true_ppg + k[pos] * position_mean_ppg) / (n + k[pos])

    projected_availability_2026 =
        own_weight[pos] * own_availability_2025
        + (1 - own_weight[pos]) * position_median_availability_2025

    history_component = shrunk_ppg * projected_games_2026

For players with no real 2025 PPG row, the existing behavior is preserved:
full shrinkage to the position mean and full reliance on the position-median
availability.

IMPORTANT: This is an engineering extraction, not a durability recalibration.
The existing R^2-as-own-weight interpretation is preserved here on purpose so
the V1 projection work does not silently change a second model component.
That methodology remains a separate backlog item.
"""

from __future__ import annotations

import json
import os
import statistics
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional

# Keep canonical inputs in scripts/; rolling generated output belongs under
# scripts/artifacts/generated/ so it cannot overwrite the frozen IDP V1 release.
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASON_LENGTH_2025 = 17
SEASON_LENGTH_2026 = 17
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")  # tuple for deterministic generated JSON ordering


@dataclass(frozen=True)
class HistoryConstants:
    shrinkage_k_by_position: Dict[str, Optional[float]]
    position_mean_ppg: Dict[str, float]
    position_median_availability_2025: Dict[str, float]
    own_weight_durability_by_position: Dict[str, float]


def compute_shrinkage_k(ppg_rows: Iterable[Mapping]) -> Dict[str, Optional[float]]:
    """Preserve the legacy empirical-Bayes k derivation exactly."""
    by_pos = {}
    for r in ppg_rows:
        by_pos.setdefault(r["pos"], []).append(r)

    k_by_pos = {}
    for pos, rows in by_pos.items():
        means = [r["true_ppg"] for r in rows]
        if len(means) < 2:
            k_by_pos[pos] = None
            continue
        var_between = statistics.variance(means)

        ss_within = 0.0
        df_within = 0
        for r in rows:
            weeks = r.get("weekly_points") or []
            if len(weeks) < 2:
                continue
            player_mean = sum(weeks) / len(weeks)
            ss_within += sum((w - player_mean) ** 2 for w in weeks)
            df_within += len(weeks) - 1

        if df_within == 0 or var_between == 0:
            k_by_pos[pos] = None
            continue
        var_within = ss_within / df_within
        k_by_pos[pos] = var_within / var_between
    return k_by_pos


def compute_position_mean_ppg(ppg_rows: Iterable[Mapping]) -> Dict[str, float]:
    by_pos = {}
    for r in ppg_rows:
        by_pos.setdefault(r["pos"], []).append(r["true_ppg"])
    return {pos: sum(vals) / len(vals) for pos, vals in by_pos.items()}


def compute_position_median_availability(ppg_rows: Iterable[Mapping]) -> Dict[str, float]:
    by_pos = {}
    for r in ppg_rows:
        avail = min(1.0, r["games_played"] / SEASON_LENGTH_2025)
        by_pos.setdefault(r["pos"], []).append(avail)
    return {pos: statistics.median(vals) for pos, vals in by_pos.items()}


def derive_history_constants(ppg_rows, durability_results) -> HistoryConstants:
    own_weight = {}
    for pos in TRACKED_POSITIONS:
        r2 = durability_results.get(pos, {}).get("r_squared")
        own_weight[pos] = max(0.0, min(1.0, r2)) if r2 is not None else 0.0
    return HistoryConstants(
        shrinkage_k_by_position=compute_shrinkage_k(ppg_rows),
        position_mean_ppg=compute_position_mean_ppg(ppg_rows),
        position_median_availability_2025=compute_position_median_availability(ppg_rows),
        own_weight_durability_by_position=own_weight,
    )


def compute_history_for_player(pos: str, ppg_row: Optional[Mapping], constants: HistoryConstants) -> dict:
    """Compute one player's history lineage using the existing formula."""
    if pos not in TRACKED_POSITIONS:
        raise ValueError(f"unsupported history position: {pos}")

    n = int(ppg_row.get("games_played", 0) or 0) if ppg_row else 0
    true_ppg = ppg_row.get("true_ppg") if ppg_row else None
    k = constants.shrinkage_k_by_position.get(pos)
    posmean = constants.position_mean_ppg.get(pos)

    if true_ppg is not None and k is not None and posmean is not None:
        shrunk_ppg = (n * true_ppg + k * posmean) / (n + k)
        shrinkage_note = "real"
    elif posmean is not None:
        shrunk_ppg = posmean
        shrinkage_note = "no_2025_data_full_shrink_to_position_mean"
    else:
        shrunk_ppg = None
        shrinkage_note = "no_position_mean_available"

    has_own_history = true_ppg is not None
    own_weight = constants.own_weight_durability_by_position.get(pos, 0.0) if has_own_history else 0.0
    own_avail = min(1.0, n / SEASON_LENGTH_2025) if has_own_history else None
    med_avail = constants.position_median_availability_2025.get(pos)

    if med_avail is not None:
        if has_own_history and own_avail is not None:
            durability_avail = own_weight * own_avail + (1 - own_weight) * med_avail
        else:
            durability_avail = med_avail
        durability_games = durability_avail * SEASON_LENGTH_2026
    else:
        durability_avail = None
        durability_games = None

    history_component = (
        shrunk_ppg * durability_games
        if shrunk_ppg is not None and durability_games is not None
        else None
    )

    return {
        "games_played_2025": n,
        "true_ppg_2025": true_ppg,
        "shrinkage_k_used": k,
        "position_mean_ppg": posmean,
        "shrunk_ppg": shrunk_ppg,
        "shrinkage_note": shrinkage_note,
        "own_weight_durability": own_weight,
        "own_avail_2025": own_avail,
        "position_median_avail_2025": med_avail,
        "durability_projected_avail_2026": durability_avail,
        "durability_projected_games_2026": durability_games,
        "history_component": history_component,
    }


def build_history_output(all_players, ppg_rows, durability_results) -> dict:
    """Build canonical history records for the tracked Trade Desk universe.

    ``all_players.json`` is intentionally the universe input because it is the
    same tracked-position universe that produced ``ppg_results.json``. This
    keeps history generation independent from any 2026 projection provider.
    """
    constants = derive_history_constants(ppg_rows, durability_results)
    ppg_by_key = {r["player"]: r for r in ppg_rows}

    players = {}
    for p in all_players:
        key = p["key"]
        pos = p["pos"]
        if pos not in TRACKED_POSITIONS:
            continue
        ppg_row = ppg_by_key.get(key)
        rec = {"key": key, "pos": pos}
        if ppg_row and ppg_row.get("sleeper_id"):
            rec["sleeper_id"] = str(ppg_row["sleeper_id"])
        else:
            rec["sleeper_id"] = None
        rec.update(compute_history_for_player(pos, ppg_row, constants))
        players[key] = rec

    return {
        "method": "canonical_history_component_v1_preserve_legacy_math",
        "season_length_2025": SEASON_LENGTH_2025,
        "season_length_2026": SEASON_LENGTH_2026,
        "shrinkage_k_by_position": constants.shrinkage_k_by_position,
        "position_mean_ppg": constants.position_mean_ppg,
        "position_median_availability_2025": constants.position_median_availability_2025,
        "own_weight_durability_by_position": constants.own_weight_durability_by_position,
        "players": players,
    }


def run_selftest():
    rows = [
        {"pos": "LB", "true_ppg": 10.0, "games_played": 2, "weekly_points": [8.0, 12.0]},
        {"pos": "LB", "true_ppg": 20.0, "games_played": 2, "weekly_points": [18.0, 22.0]},
    ]
    durability = {"LB": {"r_squared": 0.25}}
    c = derive_history_constants(rows, durability)
    assert c.position_mean_ppg["LB"] == 15.0
    assert c.position_median_availability_2025["LB"] == 2 / 17
    assert c.own_weight_durability_by_position["LB"] == 0.25

    real = compute_history_for_player("LB", rows[0], c)
    expected_shrunk = (2 * 10.0 + c.shrinkage_k_by_position["LB"] * 15.0) / (2 + c.shrinkage_k_by_position["LB"])
    assert abs(real["shrunk_ppg"] - expected_shrunk) < 1e-12

    rookie = compute_history_for_player("LB", None, c)
    assert rookie["shrunk_ppg"] == 15.0
    assert rookie["own_weight_durability"] == 0.0
    assert abs(rookie["durability_projected_games_2026"] - 2.0) < 1e-12
    print("production_history_component self-test passed.")


def main():
    if "--selftest" in os.sys.argv:
        run_selftest()
        return
    with open(os.path.join(SCRIPT_DIR, "all_players.json"), encoding="utf-8") as f:
        all_players = json.load(f)
    with open(os.path.join(SCRIPT_DIR, "ppg_results.json"), encoding="utf-8") as f:
        ppg_rows = json.load(f)
    with open(os.path.join(SCRIPT_DIR, "durability_results.json"), encoding="utf-8") as f:
        durability = json.load(f)

    out = build_history_output(all_players, ppg_rows, durability)
    path = os.path.join(SCRIPT_DIR, "artifacts", "generated", "production_history_components.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(f"Wrote {path}: {len(out['players'])} tracked history records")


if __name__ == "__main__":
    main()

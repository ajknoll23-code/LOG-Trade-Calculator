#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import requests

DEV_SEASONS = [2019, 2020, 2021, 2022, 2023, 2024]
POSITIONS = ["QB", "RB", "WR", "TE", "K", "DL", "LB", "DB"]

COMMON_FEATURES = [
    "snap_share__latest_active",
    "snap_share__last3_active_mean",
    "snap_share__season_to_date_active_mean",
    "snap_share__last3_minus_prior3",
    "league_points__latest_active",
    "league_points__last3_active_mean",
    "league_points__season_to_date_active_mean",
    "league_points__last3_minus_prior3",
]

OPPORTUNITY_ROOTS = {
    "QB": ["attempts", "carries"],
    "RB": ["carries", "targets", "target_share"],
    "WR": ["targets", "target_share", "air_yards_share", "receiving_air_yards"],
    "TE": ["targets", "target_share", "air_yards_share", "receiving_air_yards"],
    "K": ["fg_att", "pat_att"],
    "DL": [
        "def_tackles_solo",
        "def_tackle_assists",
        "def_tackles_for_loss",
        "def_sacks",
        "def_qb_hits",
    ],
    "LB": [
        "def_tackles_solo",
        "def_tackle_assists",
        "def_tackles_for_loss",
        "def_sacks",
        "def_qb_hits",
    ],
    "DB": [
        "def_tackles_solo",
        "def_tackle_assists",
        "def_interceptions",
        "def_pass_defended",
    ],
}
SUFFIXES = [
    "last3_active_mean",
    "season_to_date_active_mean",
    "last3_minus_prior3",
]

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def get_bytes(session, url, timeout=180, tries=4):
    last = None
    for i in range(tries):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.content
        except Exception as exc:
            last = exc
            if i + 1 < tries:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"download failed after {tries} tries: {url}: {last}")

def get_json(session, url, timeout=90, tries=4):
    return json.loads(get_bytes(session, url, timeout, tries).decode("utf-8"))

def parse_sid(value):
    s = str(value or "").strip()
    if not s or s.lower() in {"nan", "none", "na"}:
        return None
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".", 1)[0]
    if not re.fullmatch(r"\d+", s):
        return None
    return s

def midrank_pct(series: pd.Series) -> pd.Series:
    valid = series.notna()
    out = pd.Series(np.nan, index=series.index, dtype=float)
    n = int(valid.sum())
    if n == 0:
        return out
    if n == 1:
        out.loc[valid] = 0.5
        return out
    ranks = series.loc[valid].rank(method="average")
    out.loc[valid] = (ranks - 1.0) / (n - 1.0)
    return out

def score_history(history_json, sleeper_id, season_stats, scorer, settings):
    games = json.loads(history_json)
    points = []
    missing = 0
    for g in games:
        week = int(g["week"])
        raw = season_stats.get(week, {}).get(sleeper_id)
        if raw is None:
            raw = {}
            missing += 1
        points.append(float(scorer.score_week(raw, settings)))
    return points, missing

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "sources"
    tmp.mkdir(parents=True, exist_ok=True)

    base = repo / "research/player-role-v2"
    b41a = json.loads(
        (base / "player_role_v2_b41a_source_feasibility.json").read_text()
    )
    manifest = json.loads(
        (base / "player_role_v2_b41b_cohort_manifest.json").read_text()
    )
    b41c2 = json.loads(
        (base / "player_role_v2_b41c2_scorer_recovery_preregistration.json").read_text()
    )
    league = json.loads(
        (base / "player_role_v2_b41c_league_scoring_snapshot.json").read_text()
    )

    scorer_path = base / "player_role_v2_b41c2_target_scorer.py"
    scorer_sha = sha256_file(scorer_path)
    assert scorer_sha == b41c2["frozen_b41c2_scorer_sha256"]
    spec = importlib.util.spec_from_file_location("b41d_scorer", scorer_path)
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    settings = league["scoring_settings"]

    session = requests.Session()
    session.headers.update({"User-Agent": "LOG-Trade-Calculator-player-role-v2-b41d"})

    # Reconstruct the exact B41B cohort from B41A-pinned data.
    for season in DEV_SEASONS:
        st = b41a["sources"]["nflverse_weekly_player_stats"]["seasons"][str(season)]
        sn = b41a["sources"]["nflverse_snap_counts"]["seasons"][str(season)]
        for meta, name in [
            (st, f"stats_player_week_{season}.csv"),
            (sn, f"snap_counts_{season}.csv"),
        ]:
            payload = get_bytes(session, meta["url"])
            actual = sha256_bytes(payload)
            if actual != meta["sha256"]:
                raise RuntimeError(
                    f"B41D_SOURCE_DRIFT {name} expected={meta['sha256']} actual={actual}"
                )
            (tmp / name).write_bytes(payload)

    players_url = (
        "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"
    )
    players_bytes = get_bytes(session, players_url)
    players_sha = sha256_bytes(players_bytes)
    expected_players_sha = manifest["source_sha256"]["players.csv"]
    if players_sha != expected_players_sha:
        raise RuntimeError(
            "B41D_B41B_IDENTITY_SOURCE_DRIFT "
            f"expected={expected_players_sha} actual={players_sha}"
        )
    players_path = tmp / "players.csv"
    players_path.write_bytes(players_bytes)

    cohort_path = out / "b41d_reconstructed_cohort.csv.gz"
    cohort_audit = out / "b41d_reconstructed_cohort_audit.json"
    cohort_manifest = out / "b41d_reconstructed_cohort_manifest.json"
    subprocess.run(
        [
            sys.executable,
            str(base / "player_role_v2_b41b_cohort_builder.py"),
            "--source-dir", str(tmp),
            "--players", str(players_path),
            "--out-cohort", str(cohort_path),
            "--out-audit", str(cohort_audit),
            "--out-manifest", str(cohort_manifest),
        ],
        check=True,
    )
    actual_cohort_sha = sha256_file(cohort_path)
    if actual_cohort_sha != manifest["cohort_sha256"]:
        raise RuntimeError(
            "B41D_COHORT_REPRODUCTION_MISMATCH "
            f"expected={manifest['cohort_sha256']} actual={actual_cohort_sha}"
        )

    df = pd.read_csv(cohort_path, compression="gzip")
    assert len(df) == manifest["cohort_row_count"] == 85740
    assert set(df["season"].astype(int).unique()) == set(DEV_SEASONS)
    assert 2025 not in set(df["season"].astype(int))

    # Freeze a versioned stable-ID crosswalk snapshot from DynastyProcess.
    commits_url = (
        "https://api.github.com/repos/dynastyprocess/data/commits"
        "?path=files/db_playerids.csv&per_page=1"
    )
    commit_rows = get_json(session, commits_url)
    if not isinstance(commit_rows, list) or not commit_rows:
        raise RuntimeError("B41D_DYNASTYPROCESS_COMMIT_DISCOVERY_FAILED")
    dp_commit = str(commit_rows[0]["sha"])
    dp_url = (
        "https://raw.githubusercontent.com/dynastyprocess/data/"
        f"{dp_commit}/files/db_playerids.csv"
    )
    cross_bytes = get_bytes(session, dp_url)
    cross_sha = sha256_bytes(cross_bytes)
    cross_df = pd.read_csv(io.BytesIO(cross_bytes), dtype=str)

    required = {"gsis_id", "sleeper_id"}
    if not required.issubset(cross_df.columns):
        raise RuntimeError(
            f"B41D_CROSSWALK_SCHEMA_MISSING {sorted(required - set(cross_df.columns))}"
        )

    gsis_to_sids = defaultdict(set)
    for _, r in cross_df.iterrows():
        gsis = str(r.get("gsis_id") or "").strip()
        sid = parse_sid(r.get("sleeper_id"))
        if gsis and gsis.lower() not in {"nan", "none"} and sid:
            gsis_to_sids[gsis].add(sid)

    ambiguous = {g: sorted(v) for g, v in gsis_to_sids.items() if len(v) > 1}
    if ambiguous:
        raise RuntimeError(
            f"B41D_AMBIGUOUS_STABLE_ID_CROSSWALK count={len(ambiguous)} "
            f"samples={list(ambiguous.items())[:10]}"
        )
    exact_map = {g: next(iter(v)) for g, v in gsis_to_sids.items() if len(v) == 1}

    df["sleeper_id"] = df["gsis_id"].map(exact_map)
    df["identity_mapped"] = df["sleeper_id"].notna()

    overall_coverage = float(df["identity_mapped"].mean())
    cell_cov = (
        df.groupby(["season", "position"], observed=True)["identity_mapped"]
        .mean()
        .reset_index()
    )
    min_cell = float(cell_cov["identity_mapped"].min())
    low_cells = cell_cov[cell_cov["identity_mapped"] < 0.95].to_dict("records")

    identity_audit = {
        "schema_version": 1,
        "study_id": "player-role-v2",
        "phase": "B41D-stable-id-bridge-audit",
        "crosswalk_source": dp_url,
        "crosswalk_commit": dp_commit,
        "crosswalk_sha256": cross_sha,
        "join_keys": ["gsis_id", "sleeper_id"],
        "fuzzy_name_join_used": False,
        "ambiguous_gsis_ids": 0,
        "cohort_rows": int(len(df)),
        "mapped_rows": int(df["identity_mapped"].sum()),
        "overall_mapping_coverage": overall_coverage,
        "minimum_season_position_mapping_coverage": min_cell,
        "required_overall_mapping_coverage": 0.98,
        "required_season_position_mapping_coverage": 0.95,
        "low_cells": low_cells,
        "pass": overall_coverage >= 0.98 and min_cell >= 0.95,
    }
    (out / "player_role_v2_b41d_identity_audit.json").write_text(
        json.dumps(identity_audit, indent=2, sort_keys=True) + "\n"
    )
    if not identity_audit["pass"]:
        raise RuntimeError(
            "B41D_STABLE_ID_COVERAGE_GATE_FAILED "
            f"overall={overall_coverage:.6f} min_cell={min_cell:.6f}"
        )

    # Model only rows with an exact stable-ID bridge.
    model = df[df["identity_mapped"]].copy()
    model["sleeper_id"] = model["sleeper_id"].astype(str)

    # Identify only historical season/week pairs required by the already-frozen
    # active-game windows. No 2025 or 2026 Week 4 data is read.
    required_weeks = defaultdict(set)
    for _, row in model.iterrows():
        season = int(row["season"])
        for col in [
            "history_season_to_date_scoring_components_json",
            "target_next4_active_games_json",
        ]:
            for g in json.loads(row[col]):
                required_weeks[season].add(int(g["week"]))

    sleeper_stats = defaultdict(dict)
    sleeper_source_hashes = {}
    for season in DEV_SEASONS:
        for week in sorted(required_weeks[season]):
            url = f"https://api.sleeper.app/v1/stats/nfl/regular/{season}/{week}"
            payload = get_bytes(session, url, timeout=90)
            data = json.loads(payload.decode("utf-8"))
            if not isinstance(data, dict):
                raise RuntimeError(
                    f"B41D_SLEEPER_HISTORICAL_STATS_NOT_DICT season={season} week={week}"
                )
            sleeper_stats[season][week] = data
            sleeper_source_hashes[f"{season}:{week}"] = sha256_bytes(payload)

    history_missing = 0
    target_missing = 0
    prod_latest = []
    prod_last3 = []
    prod_season = []
    prod_trend = []
    target_ppg = []

    for _, row in model.iterrows():
        season = int(row["season"])
        sid = str(row["sleeper_id"])

        history_games = json.loads(
            row["history_season_to_date_scoring_components_json"]
        )
        hp = []
        for g in history_games:
            week = int(g["week"])
            raw = sleeper_stats[season][week].get(sid)
            if raw is None:
                raw = {}
                history_missing += 1
            hp.append(float(scorer.score_week(raw, settings)))

        target_games = json.loads(row["target_next4_active_games_json"])
        tp = []
        for g in target_games:
            week = int(g["week"])
            raw = sleeper_stats[season][week].get(sid)
            if raw is None:
                raw = {}
                target_missing += 1
            tp.append(float(scorer.score_week(raw, settings)))

        prod_latest.append(hp[-1] if hp else np.nan)
        prod_last3.append(float(np.mean(hp[-3:])) if hp else np.nan)
        prod_season.append(float(np.mean(hp)) if hp else np.nan)
        if len(hp) >= 6:
            prod_trend.append(float(np.mean(hp[-3:]) - np.mean(hp[-6:-3])))
        else:
            prod_trend.append(np.nan)
        target_ppg.append(float(np.mean(tp)) if tp else np.nan)

    model["league_points__latest_active"] = prod_latest
    model["league_points__last3_active_mean"] = prod_last3
    model["league_points__season_to_date_active_mean"] = prod_season
    model["league_points__last3_minus_prior3"] = prod_trend
    model["target_next4_active_ppg"] = target_ppg

    # Position-specific legal features are frozen in the B41D contract.
    contract = json.loads(
        (base / "player_role_v2_b41d_development_contract.json").read_text()
    )
    feature_map = contract["position_feature_columns"]

    normalized_cols = sorted({
        col for cols in feature_map.values() for col in cols
    })
    for col in normalized_cols:
        if col not in model.columns:
            raise RuntimeError(f"B41D_FROZEN_FEATURE_MISSING {col}")
        model[col] = pd.to_numeric(model[col], errors="coerce")

    # Normalize objective predictors within season x origin x position using
    # midranks. This uses no outcome and is available at each historical origin.
    group_cols = ["season", "origin_week", "position"]
    for col in normalized_cols:
        model[col] = (
            model.groupby(group_cols, observed=True, group_keys=False)[col]
            .apply(midrank_pct)
        )

    model["target_percentile"] = (
        model.groupby(group_cols, observed=True, group_keys=False)[
            "target_next4_active_ppg"
        ].apply(midrank_pct)
    )

    if model["target_percentile"].isna().any():
        raise RuntimeError("B41D_TARGET_PERCENTILE_HAS_NAN")

    model.insert(0, "row_id", np.arange(len(model), dtype=np.int64))

    keep = [
        "row_id", "season", "origin_week", "gsis_id", "sleeper_id",
        "player_name", "position", "team_at_origin", "target_next4_active_ppg",
        "target_percentile",
    ] + normalized_cols
    model_out = model[keep].copy()

    modeling_path = out / "player_role_v2_b41d_modeling_data.csv.gz"
    model_out.to_csv(modeling_path, index=False, compression="gzip")

    source_audit = {
        "schema_version": 1,
        "study_id": "player-role-v2",
        "phase": "B41D-development-modeling-data",
        "b41b_expected_cohort_sha256": manifest["cohort_sha256"],
        "b41d_reconstructed_cohort_sha256": actual_cohort_sha,
        "cohort_reproduced_exactly": True,
        "modeling_rows": int(len(model_out)),
        "development_seasons": DEV_SEASONS,
        "holdout_2025_opened": False,
        "week4_2026_opened": False,
        "historical_projection_features_used": False,
        "fuzzy_name_join_used": False,
        "frozen_b41c2_scorer_sha256": scorer_sha,
        "dynastyprocess_crosswalk_commit": dp_commit,
        "dynastyprocess_crosswalk_sha256": cross_sha,
        "historical_sleeper_response_sha256": sleeper_source_hashes,
        "history_active_game_raw_stats_missing_count": history_missing,
        "target_active_game_raw_stats_missing_count": target_missing,
        "modeling_data_sha256": sha256_file(modeling_path),
        "predictor_target_association_computed": False,
        "model_fit_performed": False,
        "production_change_authorized": False,
    }
    (out / "player_role_v2_b41d_modeling_data_audit.json").write_text(
        json.dumps(source_audit, indent=2, sort_keys=True) + "\n"
    )

    print(json.dumps({
        "cohort_rows": len(df),
        "modeling_rows": len(model_out),
        "identity_coverage": overall_coverage,
        "min_cell_identity_coverage": min_cell,
        "history_missing_raw": history_missing,
        "target_missing_raw": target_missing,
        "modeling_data_sha256": source_audit["modeling_data_sha256"],
        "holdout_2025_opened": False,
        "week4_2026_opened": False,
    }, indent=2))

if __name__ == "__main__":
    main()

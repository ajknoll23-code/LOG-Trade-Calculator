#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import sys
import time

import numpy as np
import pandas as pd
import requests
from scipy.stats import spearmanr

POSITIONS = ["QB", "RB", "WR", "TE", "K", "DL", "LB", "DB"]
SNAP_POSITIONS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]
ROLE_ORDER = ["Speculative", "Depth", "Understudy", "Rotational", "Starter", "Every-Down", "Elite"]
HOLDOUT_SEASON = 2025
ORIGIN_WEEKS = list(range(4, 15))


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_bytes(session: requests.Session, url: str, timeout=180, tries=5) -> bytes:
    last = None
    for i in range(tries):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.content
        except Exception as exc:
            last = exc
            if i + 1 < tries:
                time.sleep(2.0 * (i + 1))
    raise RuntimeError(f"transport failure after {tries} tries: {url}: {last}")


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


def safe_spearman(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3 or np.nanstd(x) == 0 or np.nanstd(y) == 0:
        return 0.0
    v = spearmanr(x, y, nan_policy="omit").statistic
    return float(v) if np.isfinite(v) else 0.0


class WeightedRankPlan:
    """Exact average ranks for integer replication weights, with static values."""
    def __init__(self, values):
        values = np.asarray(values, dtype=float)
        self.n = len(values)
        self.order = np.argsort(values, kind="mergesort")
        sv = values[self.order]
        if len(sv) == 0:
            raise ValueError("empty rank plan")
        self.starts = np.r_[0, 1 + np.flatnonzero(sv[1:] != sv[:-1])]
        ends = np.r_[self.starts[1:], len(sv)]
        self.group_id_sorted = np.repeat(np.arange(len(self.starts)), ends - self.starts)

    def ranks(self, weights):
        w = np.asarray(weights, dtype=float)
        ws = w[self.order]
        group_w = np.add.reduceat(ws, self.starts)
        cum = np.cumsum(group_w)
        group_rank = cum - (group_w - 1.0) / 2.0
        sorted_ranks = group_rank[self.group_id_sorted]
        out = np.empty(self.n, dtype=float)
        out[self.order] = sorted_ranks
        return out


def weighted_spearman_from_integer_weights(x_plan, y_plan, weights):
    w = np.asarray(weights, dtype=float)
    total = float(w.sum())
    if total < 3:
        return 0.0
    rx = x_plan.ranks(w)
    ry = y_plan.ranks(w)
    mx = float(np.sum(w * rx) / total)
    my = float(np.sum(w * ry) / total)
    dx = rx - mx
    dy = ry - my
    vx = float(np.sum(w * dx * dx))
    vy = float(np.sum(w * dy * dy))
    if vx <= 0 or vy <= 0:
        return 0.0
    return float(np.sum(w * dx * dy) / math.sqrt(vx * vy))


def self_test_weighted_spearman():
    rng = np.random.default_rng(20261003)
    n = 80
    x = np.round(rng.normal(size=n), 1)  # deliberate ties
    y = np.round(0.5 * x + rng.normal(size=n), 1)
    cluster = rng.integers(0, 11, size=n)
    xp = WeightedRankPlan(x)
    yp = WeightedRankPlan(y)
    for _ in range(100):
        sampled = rng.choice(np.arange(11), size=11, replace=True)
        counts = np.bincount(sampled, minlength=11)
        weights = counts[cluster]
        literal_x = np.repeat(x, weights.astype(int))
        literal_y = np.repeat(y, weights.astype(int))
        a = safe_spearman(literal_x, literal_y)
        b = weighted_spearman_from_integer_weights(xp, yp, weights)
        if not np.isclose(a, b, rtol=0, atol=1e-12):
            raise AssertionError((a, b))
    print("PASS weighted Spearman exact-replication self-test")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def frozen_preflight(base: Path):
    b41g = json.loads((base / "player_role_v2_b41g_holdout_validation_preregistration.json").read_text())
    freeze = json.loads((base / "player_role_v2_b41g_freeze_decision.json").read_text())
    baseline = json.loads((base / "player_role_v2_b41g_baseline_snapshot.json").read_text())
    b41f = json.loads((base / "player_role_v2_b41f_final_model_snapshot.json").read_text())
    c3_path = base / "player_role_v2_b41c3_scientific_decision.json"
    if not c3_path.exists():
        raise RuntimeError("B41H_B41C3_DECISION_MISSING_BEFORE_2025_READ")
    c3 = json.loads(c3_path.read_text())

    assert freeze["result"] == "PASS_2025_HOLDOUT_PROTOCOL_AND_BASELINE_FROZEN"
    assert freeze["2025_holdout_opened"] is False
    assert sha256_file(base / "player_role_v2_b41g_holdout_validation_preregistration.json") == freeze["preregistration_sha256"]
    assert sha256_file(base / "player_role_v2_b41g_baseline_snapshot.json") == freeze["baseline_snapshot_sha256"]
    assert b41g["status"] == "PREREGISTERED_BEFORE_ANY_2025_HOLDOUT_ACCESS"
    assert b41g["sequencing"]["B41C3_must_pass_before_any_2025_read"] is True
    assert c3["result"] == b41g["sequencing"]["required_B41C3_result"]
    assert c3["eligible_for_2025_holdout_evaluation"] is True
    assert c3["2025_holdout_opened"] is False
    assert c3["frozen_scorer_sha256"] == b41g["frozen_inputs"]["frozen_scorer_sha256"]
    assert b41f["2025_holdout_opened"] is False
    assert b41f["production_model_deployed"] is False
    assert b41f["production_change_authorized"] is False
    return b41g, baseline, b41f, c3


def source_integrity_or_stop(session, meta, path: Path, label: str):
    payload = get_bytes(session, meta["url"])
    actual = sha256_bytes(payload)
    if actual != meta["sha256"]:
        raise ValueError(f"SOURCE_SHA_MISMATCH {label} expected={meta['sha256']} actual={actual}")
    path.write_bytes(payload)
    return actual


def build_holdout_cohort(repo: Path, out: Path, prereg: dict, session: requests.Session):
    base = repo / "research/player-role-v2"
    sources = out / "sources"
    sources.mkdir(parents=True, exist_ok=True)

    stats_path = sources / "stats_player_week_2025.csv"
    snaps_path = sources / "snap_counts_2025.csv"
    source_hashes = {}
    source_hashes[stats_path.name] = source_integrity_or_stop(
        session, prereg["frozen_inputs"]["2025_weekly_stats"], stats_path, "2025 weekly stats"
    )
    source_hashes[snaps_path.name] = source_integrity_or_stop(
        session, prereg["frozen_inputs"]["2025_snap_counts"], snaps_path, "2025 snap counts"
    )

    players_url = "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"
    players_payload = get_bytes(session, players_url)
    players_sha = sha256_bytes(players_payload)
    if players_sha != prereg["frozen_inputs"]["players_identity_sha256"]:
        raise ValueError(
            f"SOURCE_SHA_MISMATCH players expected={prereg['frozen_inputs']['players_identity_sha256']} actual={players_sha}"
        )
    players_path = sources / "players.csv"
    players_path.write_bytes(players_payload)
    source_hashes[players_path.name] = players_sha

    builder_path = base / "player_role_v2_b41b_cohort_builder.py"
    if sha256_file(builder_path) != "84dcee287a9884976344acb13b844267105da0396fd4c1f02898b7d70c5d15dc":
        raise ValueError("B41B_BUILDER_CONTENT_SHA_MISMATCH")
    builder = load_module(builder_path, "b41h_frozen_b41b_builder")
    # Exact B41B functions are reused; only the permitted season set is changed.
    builder.DEV_SEASONS = (2025,)
    builder.ORIGIN_WEEKS = tuple(ORIGIN_WEEKS)

    gsis_meta, pfr_to_gsis = builder.load_players(players_path)
    all_rows, source_audit = builder.load_season(stats_path, snaps_path, gsis_meta, pfr_to_gsis)
    if {int(r["season"]) for r in all_rows} != {2025}:
        raise ValueError("B41H_HOLDOUT_SOURCE_SEASON_SCOPE_FAILED")
    cohort_rows, excluded = builder.build_origins(all_rows)
    cohort_rows.sort(key=lambda r: (r["season"], r["origin_week"], r["position"], r["gsis_id"]))
    if not cohort_rows:
        raise ValueError("B41H_EMPTY_HOLDOUT_COHORT")
    df = pd.DataFrame(cohort_rows)
    if set(df["season"].astype(int).unique()) != {2025}:
        raise ValueError("B41H_HOLDOUT_COHORT_SEASON_FAILED")
    return df, source_hashes, source_audit, dict(excluded)


def attach_stable_ids(df: pd.DataFrame, prereg: dict, session: requests.Session):
    commit = prereg["frozen_inputs"]["stable_id_crosswalk_commit"]
    url = f"https://raw.githubusercontent.com/dynastyprocess/data/{commit}/files/db_playerids.csv"
    payload = get_bytes(session, url)
    actual = sha256_bytes(payload)
    expected = prereg["frozen_inputs"]["stable_id_crosswalk_sha256"]
    if actual != expected:
        raise ValueError(f"CROSSWALK_SHA_MISMATCH expected={expected} actual={actual}")
    cross = pd.read_csv(io.BytesIO(payload), dtype=str)
    if not {"gsis_id", "sleeper_id"}.issubset(cross.columns):
        raise ValueError("B41H_CROSSWALK_SCHEMA_MISSING")

    gsis_to_sids = defaultdict(set)
    for _, r in cross.iterrows():
        gsis = str(r.get("gsis_id") or "").strip()
        sid = parse_sid(r.get("sleeper_id"))
        if gsis and gsis.lower() not in {"nan", "none"} and sid:
            gsis_to_sids[gsis].add(sid)
    ambiguous = {g: v for g, v in gsis_to_sids.items() if len(v) > 1}
    if ambiguous:
        raise ValueError(f"B41H_AMBIGUOUS_GSIS_CROSSWALK count={len(ambiguous)}")
    exact = {g: next(iter(v)) for g, v in gsis_to_sids.items() if len(v) == 1}

    out = df.copy()
    out["sleeper_id"] = out["gsis_id"].map(exact)
    out["identity_mapped"] = out["sleeper_id"].notna()
    overall = float(out["identity_mapped"].mean())
    pos_cov = out.groupby("position", observed=True)["identity_mapped"].mean().to_dict()
    return out, actual, overall, {k: float(v) for k, v in pos_cov.items()}


def score_and_normalize(model: pd.DataFrame, repo: Path, out: Path, prereg: dict, b41f: dict, session: requests.Session):
    base = repo / "research/player-role-v2"
    scorer_path = base / "player_role_v2_b41c2_target_scorer.py"
    if sha256_file(scorer_path) != prereg["frozen_inputs"]["frozen_scorer_sha256"]:
        raise ValueError("B41H_FROZEN_SCORER_SHA_MISMATCH")
    scorer = load_module(scorer_path, "b41h_frozen_scorer")
    league = json.loads((base / "player_role_v2_b41c_league_scoring_snapshot.json").read_text())
    settings = league["scoring_settings"]

    required_weeks = set()
    for _, row in model.iterrows():
        for col in ["history_season_to_date_scoring_components_json", "target_next4_active_games_json"]:
            for g in json.loads(row[col]):
                required_weeks.add(int(g["week"]))

    sleeper_stats = {}
    sleeper_hashes = {}
    for week in sorted(required_weeks):
        url = f"https://api.sleeper.app/v1/stats/nfl/regular/2025/{week}"
        payload = get_bytes(session, url, timeout=90)
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"B41H_SLEEPER_STATS_NOT_DICT week={week}")
        sleeper_stats[week] = data
        sleeper_hashes[str(week)] = sha256_bytes(payload)

    history_missing = 0
    target_missing = 0
    latest, last3, season_mean, trend, target_ppg, target_snap = [], [], [], [], [], []
    for _, row in model.iterrows():
        sid = str(row["sleeper_id"])
        history_games = json.loads(row["history_season_to_date_scoring_components_json"])
        hp = []
        for g in history_games:
            raw = sleeper_stats[int(g["week"])].get(sid)
            if raw is None:
                raw = {}
                history_missing += 1
            hp.append(float(scorer.score_week(raw, settings)))
        target_games = json.loads(row["target_next4_active_games_json"])
        tp = []
        snap_vals = []
        for g in target_games:
            raw = sleeper_stats[int(g["week"])].get(sid)
            if raw is None:
                raw = {}
                target_missing += 1
            tp.append(float(scorer.score_week(raw, settings)))
            v = g.get("snap_share")
            if v is not None:
                try:
                    fv = float(v)
                    if np.isfinite(fv):
                        snap_vals.append(fv)
                except Exception:
                    pass
        latest.append(hp[-1] if hp else np.nan)
        last3.append(float(np.mean(hp[-3:])) if hp else np.nan)
        season_mean.append(float(np.mean(hp)) if hp else np.nan)
        trend.append(float(np.mean(hp[-3:]) - np.mean(hp[-6:-3])) if len(hp) >= 6 else np.nan)
        target_ppg.append(float(np.mean(tp)) if tp else np.nan)
        target_snap.append(float(np.mean(snap_vals)) if snap_vals else np.nan)

    model = model.copy()
    model["league_points__latest_active"] = latest
    model["league_points__last3_active_mean"] = last3
    model["league_points__season_to_date_active_mean"] = season_mean
    model["league_points__last3_minus_prior3"] = trend
    model["target_next4_active_ppg"] = target_ppg
    model["future_snap_share_raw"] = target_snap

    frozen_cols = sorted({c for p in POSITIONS for c in b41f["position_models"][p]["feature_columns"]})
    for col in frozen_cols:
        if col not in model.columns:
            raise ValueError(f"B41H_MISSING_FROZEN_FEATURE_COLUMN {col}")
        model[col] = pd.to_numeric(model[col], errors="coerce")

    group_cols = ["season", "origin_week", "position"]
    for col in frozen_cols:
        model[col] = model.groupby(group_cols, observed=True, group_keys=False)[col].apply(midrank_pct)
    model["target_percentile"] = model.groupby(group_cols, observed=True, group_keys=False)["target_next4_active_ppg"].apply(midrank_pct)
    model["future_snap_percentile"] = model.groupby(group_cols, observed=True, group_keys=False)["future_snap_share_raw"].apply(midrank_pct)
    return model, sleeper_hashes, history_missing, target_missing


def apply_frozen_models(model: pd.DataFrame, baseline: dict, b41f: dict):
    frames = []
    imputation = {}
    for pos in POSITIONS:
        sub = model[model["position"] == pos].copy()
        pm = b41f["position_models"][pos]
        score = np.full(len(sub), float(pm["fit"]["intercept"]), dtype=float)
        imp_count = 0
        imp_cells = 0
        for col in pm["feature_columns"]:
            x = pd.to_numeric(sub[col], errors="coerce").to_numpy(dtype=float)
            missing = ~np.isfinite(x)
            imp_count += int(missing.sum())
            imp_cells += len(x)
            x[missing] = float(pm["imputation_medians"][col])
            score += float(pm["fit"]["coefficients"].get(col, 0.0)) * x
        score = np.clip(score, 0.0, 1.0)
        sub["model_score"] = score
        thresholds = np.asarray(pm["frozen_tier_thresholds"], dtype=float)
        tier_index = np.searchsorted(thresholds, score, side="right")
        sub["tier_index"] = tier_index.astype(int)
        sub["role_tier"] = [ROLE_ORDER[int(i)] for i in tier_index]

        bm = baseline["position_baselines"][pos]
        bcol = bm["selected_feature"]
        bx = pd.to_numeric(sub[bcol], errors="coerce").to_numpy(dtype=float)
        bmissing = ~np.isfinite(bx)
        bx[bmissing] = float(bm["full_development_imputation_median"])
        sub["baseline_score"] = np.clip(bx, 0.0, 1.0)
        sub["baseline_feature"] = bcol
        imputation[pos] = {
            "model_missing_cells_imputed": imp_count,
            "model_feature_cells": imp_cells,
            "model_imputation_rate": float(imp_count / imp_cells) if imp_cells else 0.0,
            "baseline_missing_rows_imputed": int(bmissing.sum()),
            "baseline_feature": bcol,
        }
        frames.append(sub)
    return pd.concat(frames, ignore_index=True), imputation


def secondary_descriptives(scored: pd.DataFrame):
    out = {}
    for pos in POSITIONS:
        d = scored[scored["position"] == pos].copy()
        tier_counts = d.groupby("tier_index", observed=True).size().reindex(range(7), fill_value=0)
        target_means = d.groupby("tier_index", observed=True)["target_percentile"].mean().reindex(range(7))
        snap_means = d.groupby("tier_index", observed=True)["future_snap_percentile"].mean().reindex(range(7)) if pos in SNAP_POSITIONS else None
        scores = d["model_score"].to_numpy(dtype=float)
        out[pos] = {
            "n": int(len(d)),
            "tier_counts": {ROLE_ORDER[i]: int(tier_counts.loc[i]) for i in range(7)},
            "tier_target_means": {ROLE_ORDER[i]: (float(target_means.loc[i]) if np.isfinite(target_means.loc[i]) else None) for i in range(7)},
            "tier_future_snap_means": ({ROLE_ORDER[i]: (float(snap_means.loc[i]) if np.isfinite(snap_means.loc[i]) else None) for i in range(7)} if snap_means is not None else None),
            "score_clipped_low_fraction": float(np.mean(scores <= 0.0)),
            "score_clipped_high_fraction": float(np.mean(scores >= 1.0)),
        }
    return out


def data_quality(scored: pd.DataFrame, cohort_with_ids: pd.DataFrame, prereg: dict, overall_cov: float, pos_cov: dict):
    gates = prereg["holdout_data_quality_gates"]
    checks = {}
    checks["all_origin_weeks"] = sorted(int(x) for x in scored["origin_week"].unique()) == gates["all_origin_weeks_required"]
    checks["all_positions"] = sorted(scored["position"].unique()) == sorted(gates["all_positions_required"])
    pos_rows = scored.groupby("position", observed=True).size().to_dict()
    checks["minimum_rows_each_position"] = all(int(pos_rows.get(p, 0)) >= int(gates["minimum_rows_each_position"]) for p in POSITIONS)
    checks["minimum_total_modeling_rows"] = len(scored) >= int(gates["minimum_total_modeling_rows"])
    checks["overall_stable_id_coverage"] = overall_cov >= float(gates["required_overall_stable_id_coverage"])
    checks["each_position_stable_id_coverage"] = all(float(pos_cov.get(p, 0.0)) >= float(gates["required_each_position_stable_id_coverage"]) for p in POSITIONS)
    checks["finite_model_score"] = bool(np.isfinite(scored["model_score"].to_numpy(dtype=float)).all())
    checks["finite_primary_target"] = bool(np.isfinite(scored["target_percentile"].to_numpy(dtype=float)).all())
    return {
        "checks": checks,
        "pass": bool(all(checks.values())),
        "total_modeling_rows": int(len(scored)),
        "position_rows": {p: int(pos_rows.get(p, 0)) for p in POSITIONS},
        "cohort_rows_before_stable_id_filter": int(len(cohort_with_ids)),
        "overall_stable_id_coverage": overall_cov,
        "position_stable_id_coverage": {p: float(pos_cov.get(p, 0.0)) for p in POSITIONS},
    }


def tier_test(scored: pd.DataFrame, value_col: str, positions: list[str], min_rows: int):
    d = scored[scored["position"].isin(positions)].copy()
    d = d[np.isfinite(pd.to_numeric(d[value_col], errors="coerce"))]
    counts = d.groupby("tier_index", observed=True).size().reindex(range(7), fill_value=0)
    means = d.groupby("tier_index", observed=True)[value_col].mean().reindex(range(7))
    all_tiers = bool((counts > 0).all())
    enough = bool((counts >= min_rows).all())
    finite = bool(np.isfinite(means.to_numpy(dtype=float)).all())
    vals = means.to_numpy(dtype=float)
    inversions = []
    if finite:
        for i in range(6):
            if vals[i + 1] < vals[i]:
                inversions.append({"lower_tier": ROLE_ORDER[i], "upper_tier": ROLE_ORDER[i+1], "lower_mean": float(vals[i]), "upper_mean": float(vals[i+1])})
    else:
        inversions.append({"reason": "nonfinite tier mean"})
    return {
        "pass": all_tiers and enough and finite and len(inversions) == 0,
        "counts": {ROLE_ORDER[i]: int(counts.loc[i]) for i in range(7)},
        "means": {ROLE_ORDER[i]: (float(means.loc[i]) if np.isfinite(means.loc[i]) else None) for i in range(7)},
        "adjacent_inversions": inversions,
        "minimum_rows_per_tier": int(min_rows),
    }


def bootstrap_tests(scored: pd.DataFrame, prereg: dict):
    spec1 = prereg["primary_holdout_tests"]["test_1_error_vs_baseline"]
    reps = int(spec1["bootstrap_replicates"])
    seed = int(spec1["random_seed"])
    weeks = np.asarray(ORIGIN_WEEKS, dtype=int)
    rng = np.random.default_rng(seed)
    sampled = rng.choice(weeks, size=(reps, len(weeks)), replace=True)
    counts = np.stack([(sampled == w).sum(axis=1) for w in weeks], axis=1).astype(np.int16)

    # Test 1: exact cluster-replication MAE from pre-aggregated sums/counts.
    model_abs = np.abs(scored["model_score"].to_numpy(dtype=float) - scored["target_percentile"].to_numpy(dtype=float))
    base_abs = np.abs(scored["baseline_score"].to_numpy(dtype=float) - scored["target_percentile"].to_numpy(dtype=float))
    pos_arr = scored["position"].astype(str).to_numpy()
    week_arr = scored["origin_week"].astype(int).to_numpy()
    mae_boot = np.empty(reps, dtype=float)
    per_pos = {}
    agg = {}
    for p in POSITIONS:
        maskp = pos_arr == p
        ma = float(model_abs[maskp].mean())
        ba = float(base_abs[maskp].mean())
        per_pos[p] = {"n": int(maskp.sum()), "model_mae": ma, "baseline_mae": ba, "mae_difference": ma-ba, "spearman": safe_spearman(scored.loc[maskp, "model_score"], scored.loc[maskp, "target_percentile"])}
        msum, bsum, nsum = [], [], []
        for w in weeks:
            m = maskp & (week_arr == w)
            msum.append(float(model_abs[m].sum()))
            bsum.append(float(base_abs[m].sum()))
            nsum.append(int(m.sum()))
        agg[p] = (np.asarray(msum), np.asarray(bsum), np.asarray(nsum, dtype=float))

    for r in range(reps):
        c = counts[r].astype(float)
        diffs = []
        for p in POSITIONS:
            ms, bs, ns = agg[p]
            den = float(np.dot(c, ns))
            if den <= 0:
                raise RuntimeError(f"bootstrap replicate missing position {p}")
            diffs.append(float(np.dot(c, ms)/den - np.dot(c, bs)/den))
        mae_boot[r] = float(np.mean(diffs))

    point_mae_diff = float(np.mean([per_pos[p]["mae_difference"] for p in POSITIONS]))
    mae_ci = np.percentile(mae_boot, [2.5, 97.5], method="linear")
    test1 = {
        "pass": bool(float(mae_ci[1]) < 0.0),
        "point_macro_position_mae_difference": point_mae_diff,
        "ci95": [float(mae_ci[0]), float(mae_ci[1])],
        "pass_rule": "upper 95% CI strictly < 0.0",
    }

    # Test 2: exact weighted-rank correlation for integer cluster replication.
    x = scored["model_score"].to_numpy(dtype=float)
    y = scored["target_percentile"].to_numpy(dtype=float)
    xplan = WeightedRankPlan(x)
    yplan = WeightedRankPlan(y)
    week_index = np.array([ORIGIN_WEEKS.index(int(w)) for w in week_arr], dtype=int)
    spear_boot = np.empty(reps, dtype=float)
    for r in range(reps):
        row_weights = counts[r, week_index]
        spear_boot[r] = weighted_spearman_from_integer_weights(xplan, yplan, row_weights)
    point_spear = safe_spearman(x, y)
    spear_ci = np.percentile(spear_boot, [2.5, 97.5], method="linear")
    test2 = {
        "pass": bool(float(spear_ci[0]) > 0.0),
        "point_pooled_spearman": point_spear,
        "ci95": [float(spear_ci[0]), float(spear_ci[1])],
        "pass_rule": "lower 95% CI strictly > 0.0",
    }

    bootstrap_df = pd.DataFrame({
        "replicate": np.arange(reps, dtype=int),
        "macro_position_mae_difference": mae_boot,
        "pooled_spearman": spear_boot,
    })
    return test1, test2, per_pos, bootstrap_df


def write_csv_deterministic(df: pd.DataFrame, path: Path):
    df.to_csv(path, index=False, lineterminator="\n", float_format="%.17g")


def evaluate(repo: Path, out: Path):
    base = repo / "research/player-role-v2"
    out.mkdir(parents=True, exist_ok=True)
    prereg, baseline, b41f, c3 = frozen_preflight(base)

    existing = [
        base / "player_role_v2_b41h_holdout_evidence.json",
        base / "player_role_v2_b41h_scientific_decision.json",
        base / "player_role_v2_b41h_scored_holdout_rows.csv",
    ]
    if any(p.exists() for p in existing):
        raise RuntimeError("B41H_ONE_SHOT_EVIDENCE_ALREADY_EXISTS_REFUSE_RERUN")

    base_witness = base / "player_role_v2_b41h_holdout_open_witness.json"
    if base_witness.exists():
        # Only a transport-only retry may arrive with an existing open witness.
        if not (base / "player_role_v2_b41h_operational_abort.json").exists():
            raise RuntimeError("B41H_OPEN_WITNESS_EXISTS_WITHOUT_TRANSPORT_ABORT_REFUSE_RERUN")
        witness = json.loads(base_witness.read_text())
        if witness.get("B41C3_result") != c3["result"]:
            raise RuntimeError("B41H_OPEN_WITNESS_B41C3_DRIFT")
    else:
        witness = {
            "schema_version": 1,
            "study_id": "player-role-v2",
            "phase": "B41H-2025-holdout-open-witness",
            "opened_at_utc": utcnow(),
            "B41C3_result": c3["result"],
            "eligible_for_2025_holdout_evaluation": True,
            "frozen_B41G_preregistration_sha256": sha256_file(base / "player_role_v2_b41g_holdout_validation_preregistration.json"),
            "frozen_B41G_baseline_sha256": sha256_file(base / "player_role_v2_b41g_baseline_snapshot.json"),
            "frozen_B41F_snapshot_sha256": sha256_file(base / "player_role_v2_b41f_final_model_snapshot.json"),
            "production_change_authorized": False,
        }
    (out / "player_role_v2_b41h_holdout_open_witness.json").write_text(json.dumps(witness, indent=2, sort_keys=True)+"\n")

    session = requests.Session()
    session.headers.update({"User-Agent": "LOG-Trade-Calculator-player-role-v2-b41h"})

    try:
        cohort, source_hashes, b41b_source_audit, exclusions = build_holdout_cohort(repo, out, prereg, session)
        cohort_ids, cross_sha, overall_cov, pos_cov = attach_stable_ids(cohort, prereg, session)
        model = cohort_ids[cohort_ids["identity_mapped"]].copy()
        model["sleeper_id"] = model["sleeper_id"].astype(str)
        scored_base, sleeper_hashes, history_missing, target_missing = score_and_normalize(model, repo, out, prereg, b41f, session)
        scored, imputation = apply_frozen_models(scored_base, baseline, b41f)
        dq = data_quality(scored, cohort_ids, prereg, overall_cov, pos_cov)

        test1 = test2 = per_pos = bootstrap_df = None
        test3 = test4 = None
        if dq["pass"]:
            test1, test2, per_pos, bootstrap_df = bootstrap_tests(scored, prereg)
            test3 = tier_test(scored, "target_percentile", POSITIONS, int(prereg["primary_holdout_tests"]["test_3_ordered_tier_future_production"]["minimum_rows_per_tier"]))
            test4 = tier_test(scored, "future_snap_percentile", SNAP_POSITIONS, int(prereg["primary_holdout_tests"]["test_4_ordered_tier_future_snap_share"]["minimum_rows_per_tier"]))
            primary_pass = all([test1["pass"], test2["pass"], test3["pass"], test4["pass"]])
        else:
            primary_pass = False

        scored_keep = scored[[
            "season", "origin_week", "gsis_id", "sleeper_id", "player_name", "position", "team_at_origin",
            "target_next4_active_ppg", "target_percentile", "future_snap_share_raw", "future_snap_percentile",
            "model_score", "baseline_score", "baseline_feature", "tier_index", "role_tier"
        ]].copy()
        scored_path = out / "player_role_v2_b41h_scored_holdout_rows.csv"
        write_csv_deterministic(scored_keep, scored_path)
        if bootstrap_df is not None:
            bootstrap_path = out / "player_role_v2_b41h_bootstrap_replicates.csv"
            write_csv_deterministic(bootstrap_df, bootstrap_path)
        else:
            bootstrap_path = None

        evidence = {
            "schema_version": 1,
            "study_id": "player-role-v2",
            "phase": "B41H-untouched-2025-holdout-evidence",
            "holdout_season": 2025,
            "B41C3_result": c3["result"],
            "holdout_was_unopened_before_B41H": True,
            "source_sha256": source_hashes,
            "stable_id_crosswalk_sha256": cross_sha,
            "sleeper_weekly_raw_stats_sha256": sleeper_hashes,
            "b41b_source_audit": b41b_source_audit,
            "cohort_exclusions": exclusions,
            "history_active_game_raw_stats_missing_count": int(history_missing),
            "target_active_game_raw_stats_missing_count": int(target_missing),
            "future_snap_percentile_nonfinite_count": int((~np.isfinite(scored["future_snap_percentile"].to_numpy(dtype=float))).sum()),
            "imputation": imputation,
            "data_quality": dq,
            "primary_tests": {
                "test_1_error_vs_baseline": test1,
                "test_2_spearman_association": test2,
                "test_3_ordered_tier_future_production": test3,
                "test_4_ordered_tier_future_snap_share": test4,
            },
            "secondary_per_position_performance": per_pos,
            "secondary_per_position_tiers_and_clipping": secondary_descriptives(scored),
            "scored_rows_sha256": sha256_file(scored_path),
            "bootstrap_replicates_sha256": sha256_file(bootstrap_path) if bootstrap_path else None,
            "model_or_tier_retuning_performed": False,
            "production_change_authorized": False,
        }
        evidence_path = out / "player_role_v2_b41h_holdout_evidence.json"
        evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True)+"\n")

        if not dq["pass"]:
            result = "SCIENTIFIC_STOP_DATA_INTEGRITY"
        elif primary_pass:
            result = "PASS_UNTOUCHED_2025_HOLDOUT_VALIDATION"
        else:
            result = "SCIENTIFIC_STOP_2025_HOLDOUT_VALIDATION_FAILED"

        decision = {
            "schema_version": 1,
            "study_id": "player-role-v2",
            "phase": "B41H-scientific-decision",
            "result": result,
            "2025_holdout_opened": True,
            "2025_holdout_evaluated_once": True,
            "data_quality_pass": bool(dq["pass"]),
            "all_four_primary_tests_pass": bool(primary_pass) if dq["pass"] else False,
            "model_or_tier_retuning_performed": False,
            "posthoc_exclusions_performed": False,
            "production_model_deployed": False,
            "production_change_authorized": False,
            "B42_owner_blind_role_parity_audit_required_before_production": True,
            "next_stage": (
                "Run B42 owner-blind role parity audit with the frozen Role V2 system; no production deployment yet."
                if result == "PASS_UNTOUCHED_2025_HOLDOUT_VALIDATION"
                else "Scientific STOP for Player Role Engine V2 production path; preserve evidence and do not deploy this version."
            ),
            "evidence_sha256": sha256_file(evidence_path),
        }
        decision_path = out / "player_role_v2_b41h_scientific_decision.json"
        decision_path.write_text(json.dumps(decision, indent=2, sort_keys=True)+"\n")

        report = [
            "# Player Role V2 — B41H Untouched 2025 Holdout Evaluation",
            "",
            f"- Result: **{result}**",
            f"- Holdout rows: **{len(scored):,}**",
            f"- Data-quality gate: **{'PASS' if dq['pass'] else 'FAIL'}**",
            f"- 2025 opened exactly once in this evaluation: **Yes**",
            "- Frozen B41F model retuned: **No**",
            "- Frozen B41E tiers retuned: **No**",
            "- Production deployed: **No**",
            "- Production change authorized: **No**",
            "",
        ]
        if test1 is not None:
            report += [
                "## Primary holdout tests", "",
                f"1. MAE vs baseline: **{'PASS' if test1['pass'] else 'FAIL'}** — macro Δ={test1['point_macro_position_mae_difference']:.6f}, 95% CI [{test1['ci95'][0]:.6f}, {test1['ci95'][1]:.6f}]",
                f"2. Pooled Spearman: **{'PASS' if test2['pass'] else 'FAIL'}** — ρ={test2['point_pooled_spearman']:.6f}, 95% CI [{test2['ci95'][0]:.6f}, {test2['ci95'][1]:.6f}]",
                f"3. Ordered future production tiers: **{'PASS' if test3['pass'] else 'FAIL'}**",
                f"4. Ordered future snap tiers: **{'PASS' if test4['pass'] else 'FAIL'}**",
                "",
            ]
        report += ["## Next stage", "", decision["next_stage"], ""]
        (out / "player_role_v2_b41h_report.md").write_text("\n".join(report), encoding="utf-8")
        print(json.dumps({"result": result, "rows": len(scored), "data_quality_pass": dq["pass"]}, indent=2))
        return result

    except RuntimeError as exc:
        # Transport-only/operational aborts are not a scientific performance look.
        text = str(exc)
        if text.startswith("transport failure"):
            abort = {
                "schema_version": 1,
                "study_id": "player-role-v2",
                "phase": "B41H-operational-abort",
                "result": "OPERATIONAL_ABORT_BEFORE_COMPLETE_METRIC_EVALUATION",
                "reason": text,
                "2025_holdout_access_began": True,
                "performance_decision_computed": False,
                "same_frozen_evaluator_rerun_permitted": True,
                "retuning_permitted": False,
                "production_change_authorized": False,
            }
            (out / "player_role_v2_b41h_operational_abort.json").write_text(json.dumps(abort, indent=2, sort_keys=True)+"\n")
        raise
    except ValueError as exc:
        # Frozen-source/data-integrity failure after the holdout gate opens.
        decision = {
            "schema_version": 1,
            "study_id": "player-role-v2",
            "phase": "B41H-scientific-decision",
            "result": "SCIENTIFIC_STOP_DATA_INTEGRITY",
            "reason": str(exc),
            "2025_holdout_opened": True,
            "2025_holdout_evaluated_once": True,
            "production_model_deployed": False,
            "production_change_authorized": False,
        }
        (out / "player_role_v2_b41h_scientific_decision.json").write_text(json.dumps(decision, indent=2, sort_keys=True)+"\n")
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out-dir")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test_weighted_spearman()
        return
    if not args.out_dir:
        raise SystemExit("--out-dir required unless --self-test")
    self_test_weighted_spearman()
    result = evaluate(Path(args.repo).resolve(), Path(args.out_dir).resolve())
    # Scientific FAIL is handled by workflow after evidence commit.
    print(result)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error

SEASONS = [2019, 2020, 2021, 2022, 2023, 2024]
FAMILY_ORDER = [
    "best_single_signal_baseline",
    "nonnegative_ridge_linear",
    "monotonic_hist_gradient_boosting",
]

def safe_spearman(y, p):
    if len(y) < 3 or np.nanstd(y) == 0 or np.nanstd(p) == 0:
        return 0.0
    value = spearmanr(y, p, nan_policy="omit").statistic
    return float(value) if np.isfinite(value) else 0.0

def usable_columns(train, features):
    cols = []
    for c in features:
        x = pd.to_numeric(train[c], errors="coerce")
        finite = x[np.isfinite(x)]
        if len(finite) >= 2 and finite.nunique() >= 2:
            cols.append(c)
    return cols

def impute(train, test, cols):
    tr = train[cols].apply(pd.to_numeric, errors="coerce").astype(float)
    te = test[cols].apply(pd.to_numeric, errors="coerce").astype(float)
    med = tr.median(axis=0, skipna=True).fillna(0.5)
    return tr.fillna(med).to_numpy(), te.fillna(med).to_numpy(), med

def inner_splits(train):
    seasons = sorted(int(x) for x in train["season"].unique())
    for val_season in seasons:
        yield (
            train[train["season"] != val_season],
            train[train["season"] == val_season],
            val_season,
        )

def choose_baseline(train, features):
    scores = []
    for feature in sorted(features):
        fold_mae = []
        for tr, va, _ in inner_splits(train):
            if feature not in usable_columns(tr, [feature]):
                fold_mae = []
                break
            Xtr, Xva, med = impute(tr, va, [feature])
            pred = np.clip(Xva[:, 0], 0.0, 1.0)
            fold_mae.append(mean_absolute_error(va["target_percentile"], pred))
        if fold_mae:
            scores.append((float(np.mean(fold_mae)), feature))
    if not scores:
        raise RuntimeError("baseline nested CV had no eligible feature")
    scores.sort(key=lambda x: (x[0], x[1]))
    return scores[0][1], scores

def ridge_model(alpha):
    # lbfgs supports positive coefficients and an intercept.
    return Ridge(
        alpha=float(alpha),
        fit_intercept=True,
        positive=True,
        solver="lbfgs",
        max_iter=5000,
        tol=1e-7,
    )

def choose_ridge(train, features, alphas):
    results = []
    for alpha in alphas:
        fold_mae = []
        for tr, va, _ in inner_splits(train):
            cols = usable_columns(tr, features)
            if not cols:
                raise RuntimeError("ridge nested fold has no usable frozen features")
            Xtr, Xva, _ = impute(tr, va, cols)
            model = ridge_model(alpha)
            model.fit(Xtr, tr["target_percentile"].to_numpy())
            pred = np.clip(model.predict(Xva), 0.0, 1.0)
            fold_mae.append(mean_absolute_error(va["target_percentile"], pred))
        results.append((float(np.mean(fold_mae)), float(alpha)))
    # More regularization wins an exact tie.
    results.sort(key=lambda x: (x[0], -x[1]))
    return results[0][1], results

def hgb_model(params, n_features):
    return HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=float(params["learning_rate"]),
        max_iter=int(params["max_iter"]),
        max_leaf_nodes=int(params["max_leaf_nodes"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        l2_regularization=float(params["l2_regularization"]),
        monotonic_cst=[1] * n_features,
        random_state=20261002,
        early_stopping=False,
    )

def hgb_grid(contract):
    c = contract["model_family_preregistration"]["candidate_3"]
    rows = []
    for lr in c["learning_rate_grid"]:
        for leaves in c["max_leaf_nodes_grid"]:
            for min_leaf in c["min_samples_leaf_grid"]:
                for l2 in c["l2_regularization_grid"]:
                    rows.append({
                        "learning_rate": lr,
                        "max_leaf_nodes": leaves,
                        "min_samples_leaf": min_leaf,
                        "l2_regularization": l2,
                        "max_iter": c["max_iter"],
                    })
    return rows

def hgb_simplicity_key(params):
    return (
        int(params["max_leaf_nodes"]),
        -int(params["min_samples_leaf"]),
        -float(params["l2_regularization"]),
        float(params["learning_rate"]),
    )

def choose_hgb(train, features, grid):
    results = []
    for params in grid:
        fold_mae = []
        for tr, va, _ in inner_splits(train):
            cols = usable_columns(tr, features)
            if not cols:
                raise RuntimeError("HGB nested fold has no usable frozen features")
            Xtr, Xva, _ = impute(tr, va, cols)
            model = hgb_model(params, len(cols))
            model.fit(Xtr, tr["target_percentile"].to_numpy())
            pred = np.clip(model.predict(Xva), 0.0, 1.0)
            fold_mae.append(mean_absolute_error(va["target_percentile"], pred))
        results.append((float(np.mean(fold_mae)), params))
    results.sort(key=lambda x: (x[0], hgb_simplicity_key(x[1])))
    return results[0][1], results

def fit_outer_family(family, train, test, features, contract):
    ytr = train["target_percentile"].to_numpy()

    if family == "best_single_signal_baseline":
        feature, tuning = choose_baseline(train, features)
        _, Xte, med = impute(train, test, [feature])
        pred = np.clip(Xte[:, 0], 0.0, 1.0)
        meta = {
            "selected_feature": feature,
            "nested_cv_best_mae": tuning[0][0],
        }
        return pred, meta

    if family == "nonnegative_ridge_linear":
        alphas = contract["model_family_preregistration"]["candidate_2"]["alpha_grid"]
        alpha, tuning = choose_ridge(train, features, alphas)
        cols = usable_columns(train, features)
        if not cols:
            raise RuntimeError("ridge outer fold has no usable frozen features")
        Xtr, Xte, _ = impute(train, test, cols)
        model = ridge_model(alpha)
        model.fit(Xtr, ytr)
        pred = np.clip(model.predict(Xte), 0.0, 1.0)
        meta = {
            "selected_alpha": alpha,
            "feature_columns": cols,
            "intercept": float(model.intercept_),
            "coefficients": {
                c: float(v) for c, v in zip(cols, model.coef_)
            },
            "nested_cv_best_mae": tuning[0][0],
        }
        return pred, meta

    if family == "monotonic_hist_gradient_boosting":
        grid = hgb_grid(contract)
        params, tuning = choose_hgb(train, features, grid)
        cols = usable_columns(train, features)
        if not cols:
            raise RuntimeError("HGB outer fold has no usable frozen features")
        Xtr, Xte, _ = impute(train, test, cols)
        model = hgb_model(params, len(cols))
        model.fit(Xtr, ytr)
        pred = np.clip(model.predict(Xte), 0.0, 1.0)
        meta = {
            "selected_params": params,
            "feature_columns": cols,
            "nested_cv_best_mae": tuning[0][0],
        }
        return pred, meta

    raise ValueError(family)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--contract", required=True)
    ap.add_argument("--position", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    contract = json.loads(Path(args.contract).read_text())
    position = args.position
    features = contract["position_feature_columns"][position]

    df = pd.read_csv(args.data, compression="gzip")
    df = df[df["position"] == position].copy()
    if len(df) < 300:
        raise RuntimeError(f"insufficient rows for {position}: {len(df)}")
    if sorted(int(x) for x in df["season"].unique()) != SEASONS:
        raise RuntimeError(f"{position} missing a development season")

    for c in features:
        if c not in df.columns:
            raise RuntimeError(f"{position} missing frozen feature {c}")

    oof = df[
        ["row_id", "season", "origin_week", "gsis_id", "sleeper_id",
         "player_name", "position", "target_percentile"]
    ].copy()

    fold_results = {family: [] for family in FAMILY_ORDER}
    pred_cols = {family: np.full(len(df), np.nan) for family in FAMILY_ORDER}

    for outer_season in SEASONS:
        train = df[df["season"] != outer_season].copy()
        test = df[df["season"] == outer_season].copy()
        test_idx = np.where(df["season"].to_numpy() == outer_season)[0]

        for family in FAMILY_ORDER:
            pred, meta = fit_outer_family(
                family, train, test, features, contract
            )
            pred_cols[family][test_idx] = pred
            y = test["target_percentile"].to_numpy()
            fold_results[family].append({
                "outer_season": outer_season,
                "n": int(len(test)),
                "mae": float(mean_absolute_error(y, pred)),
                "spearman": safe_spearman(y, pred),
                "fit_metadata": meta,
            })

    family_summary = {}
    for family in FAMILY_ORDER:
        folds = fold_results[family]
        maes = np.array([x["mae"] for x in folds], dtype=float)
        rhos = np.array([x["spearman"] for x in folds], dtype=float)
        family_summary[family] = {
            "mean_outer_mae": float(maes.mean()),
            "se_outer_mae": float(maes.std(ddof=1) / math.sqrt(len(maes))),
            "mean_outer_spearman": float(rhos.mean()),
            "folds": folds,
        }
        oof[f"pred__{family}"] = pred_cols[family]

    best_family = min(
        FAMILY_ORDER,
        key=lambda f: (
            family_summary[f]["mean_outer_mae"],
            FAMILY_ORDER.index(f),
        ),
    )
    one_se_limit = (
        family_summary[best_family]["mean_outer_mae"]
        + family_summary[best_family]["se_outer_mae"]
    )
    selected_family = next(
        f for f in FAMILY_ORDER
        if family_summary[f]["mean_outer_mae"] <= one_se_limit + 1e-12
    )

    selected_pred = oof[f"pred__{selected_family}"].to_numpy()
    if np.isnan(selected_pred).any():
        raise RuntimeError(f"{position} selected OOF predictions contain NaN")

    oof["selected_family"] = selected_family
    oof["selected_oof_prediction"] = selected_pred

    result = {
        "schema_version": 1,
        "study_id": "player-role-v2",
        "phase": "B41D-development-model-selection",
        "position": position,
        "n_rows": int(len(df)),
        "development_seasons": SEASONS,
        "frozen_feature_columns": features,
        "candidate_family_summary": family_summary,
        "lowest_mean_mae_family": best_family,
        "one_standard_error_limit": float(one_se_limit),
        "selected_family_by_one_se_rule": selected_family,
        "selected_family_oof_mae": float(
            mean_absolute_error(df["target_percentile"], selected_pred)
        ),
        "selected_family_oof_spearman": safe_spearman(
            df["target_percentile"].to_numpy(), selected_pred
        ),
        "2025_holdout_opened": False,
        "week4_2026_opened": False,
        "production_change_authorized": False,
    }

    (out / f"player_role_v2_b41d_{position}_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    oof.to_csv(
        out / f"player_role_v2_b41d_{position}_oof.csv.gz",
        index=False,
        compression="gzip",
    )

    print(json.dumps({
        "position": position,
        "n": len(df),
        "lowest_mae_family": best_family,
        "selected_family": selected_family,
        "one_se_limit": one_se_limit,
        "selected_oof_mae": result["selected_family_oof_mae"],
        "selected_oof_spearman": result["selected_family_oof_spearman"],
    }, indent=2))

if __name__ == "__main__":
    main()

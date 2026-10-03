#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error

SEASONS = [2019, 2020, 2021, 2022, 2023, 2024]
POSITIONS = ["QB", "RB", "WR", "TE", "K", "DL", "LB", "DB"]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def usable(df, features):
    out = []
    for c in features:
        x = pd.to_numeric(df[c], errors="coerce")
        finite = x[np.isfinite(x)]
        if len(finite) >= 2 and finite.nunique() >= 2:
            out.append(c)
    return out

def frame(df, cols):
    return df[cols].apply(pd.to_numeric, errors="coerce").astype(float)

def model(alpha):
    return Ridge(alpha=float(alpha), fit_intercept=True, positive=True,
                 solver="lbfgs", max_iter=5000, tol=1e-7)

def choose_alpha(df, features, alphas):
    rows = []
    for alpha in alphas:
        folds = []
        for season in SEASONS:
            tr = df[df["season"] != season].copy()
            va = df[df["season"] == season].copy()
            cols = usable(tr, features)
            if not cols:
                raise RuntimeError(f"B41F_NO_USABLE_FEATURES {season}")
            xtr, xva = frame(tr, cols), frame(va, cols)
            med = xtr.median(axis=0, skipna=True).fillna(0.5)
            Xtr, Xva = xtr.fillna(med).to_numpy(), xva.fillna(med).to_numpy()
            ytr = tr["target_percentile"].to_numpy(float)
            yva = va["target_percentile"].to_numpy(float)
            m = model(alpha)
            m.fit(Xtr, ytr)
            pred = np.clip(m.predict(Xva), 0.0, 1.0)
            folds.append({"validation_season": int(season), "n": int(len(va)),
                          "mae": float(mean_absolute_error(yva, pred)),
                          "feature_count": int(len(cols))})
        rows.append({"alpha": float(alpha),
                     "mean_loso_mae": float(np.mean([r["mae"] for r in folds])),
                     "folds": folds})
    rows.sort(key=lambda r: (r["mean_loso_mae"], -r["alpha"]))
    return float(rows[0]["alpha"]), rows

def fit_position(df, pos, features, alphas, thresholds, roles):
    sub = df[df["position"] == pos].copy()
    if len(sub) < 300 or sorted(sub["season"].astype(int).unique()) != SEASONS:
        raise RuntimeError(f"B41F_POSITION_DATA_GATE {pos}")
    for c in features:
        if c not in sub.columns:
            raise RuntimeError(f"B41F_FEATURE_MISSING {pos} {c}")

    alpha, cv = choose_alpha(sub, features, alphas)
    cols = usable(sub, features)
    x = frame(sub, cols)
    med = x.median(axis=0, skipna=True).fillna(0.5)
    X = x.fillna(med).to_numpy()
    y = sub["target_percentile"].to_numpy(float)
    if not np.isfinite(X).all() or not np.isfinite(y).all():
        raise RuntimeError(f"B41F_NONFINITE {pos}")

    m1, m2 = model(alpha), model(alpha)
    m1.fit(X, y); m2.fit(X, y)
    if not np.allclose(m1.coef_, m2.coef_, rtol=0.0, atol=1e-12):
        raise RuntimeError(f"B41F_NONDETERMINISTIC_COEFFICIENTS {pos}")
    if not np.isclose(float(m1.intercept_), float(m2.intercept_), rtol=0.0, atol=1e-12):
        raise RuntimeError(f"B41F_NONDETERMINISTIC_INTERCEPT {pos}")
    if len(thresholds) != 6 or thresholds != sorted(thresholds) or len(roles) != 7:
        raise RuntimeError(f"B41F_TIER_ARCHITECTURE_DRIFT {pos}")

    raw = m1.predict(X)
    pred = np.clip(raw, 0.0, 1.0)
    idx = np.searchsorted(np.asarray(thresholds), pred, side="right")
    return {
        "position": pos,
        "n_development_rows": int(len(sub)),
        "selected_family": "nonnegative_ridge_linear",
        "alpha_selection": {"method": "six-season LOSO MAE", "selected_alpha": alpha,
                            "candidate_results_sorted": cv,
                            "tie_rule": "larger alpha wins exact MAE tie"},
        "feature_columns": cols,
        "feature_count": int(len(cols)),
        "imputation_medians": {c: float(med[c]) for c in cols},
        "fit": {"estimator": "Ridge", "positive": True, "fit_intercept": True,
                "solver": "lbfgs", "max_iter": 5000, "tol": 1e-7,
                "intercept": float(m1.intercept_),
                "coefficients": {c: float(v) for c, v in zip(cols, m1.coef_)}},
        "score_rule": "clip(intercept + sum(coef_i * imputed_feature_i), 0, 1)",
        "frozen_tier_thresholds": thresholds,
        "role_order": roles,
        "descriptive_full_development_fit_not_validation": {
            "mae": float(mean_absolute_error(y, pred)),
            "fraction_clipped_low": float(np.mean(raw < 0.0)),
            "fraction_clipped_high": float(np.mean(raw > 1.0)),
            "tier_counts": {roles[i]: int((idx == i).sum()) for i in range(7)}},
        "deterministic_refit_check": "PASS"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--development-contract", required=True)
    ap.add_argument("--b41d-decision", required=True)
    ap.add_argument("--b41e-thresholds", required=True)
    ap.add_argument("--b41f-contract", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    dev = json.loads(Path(a.development_contract).read_text())
    d = json.loads(Path(a.b41d_decision).read_text())
    e = json.loads(Path(a.b41e_thresholds).read_text())
    f = json.loads(Path(a.b41f_contract).read_text())
    checks = [(a.data, "modeling_data_sha256"),
              (a.development_contract, "b41d_development_contract_sha256"),
              (a.b41d_decision, "b41d_decision_sha256"),
              (a.b41e_thresholds, "b41e_thresholds_sha256")]
    for p, key in checks:
        if sha(p) != f["frozen_input"][key]:
            raise RuntimeError(f"B41F_SHA_MISMATCH {key}")
    if d["2025_holdout_opened"] or d["week4_2026_opened"] or e["2025_holdout_opened"] or e["week4_2026_opened"]:
        raise RuntimeError("B41F_FIREWALL_BROKEN")

    df = pd.read_csv(a.data, compression="gzip")
    if len(df) != 85648 or sorted(df["season"].astype(int).unique()) != SEASONS or 2025 in set(df["season"].astype(int)):
        raise RuntimeError("B41F_MODELING_DATA_GATE")
    alphas = [float(x) for x in dev["candidate_families"]["candidate_2"]["alpha_grid"]]
    if alphas != [0.0, 0.01, 0.1, 1.0, 10.0]:
        raise RuntimeError("B41F_ALPHA_GRID_DRIFT")
    roles = list(e["role_order"])
    expected_roles = ["Speculative", "Depth", "Understudy", "Rotational", "Starter", "Every-Down", "Elite"]
    if roles != expected_roles:
        raise RuntimeError("B41F_ROLE_ORDER_DRIFT")

    results = {}
    for pos in POSITIONS:
        if d["selected_family_by_position"][pos] != "nonnegative_ridge_linear":
            raise RuntimeError(f"B41F_FAMILY_DRIFT {pos}")
        features = list(dev["position_feature_columns"][pos])
        thresholds = [float(x) for x in e["position_results"][pos]["thresholds_ascending"]]
        results[pos] = fit_position(df, pos, features, alphas, thresholds, roles)

    snapshot = {
        "schema_version": 1, "study_id": "player-role-v2",
        "phase": "B41F-final-development-model-fit",
        "status": "FINAL_2019_2024_MODEL_WEIGHTS_FROZEN_BEFORE_WEEK4_AND_2025_HOLDOUT",
        "development_seasons": SEASONS,
        "modeling_data_sha256": sha(a.data), "modeling_row_count": int(len(df)),
        "selected_family_all_positions": "nonnegative_ridge_linear",
        "position_models": results,
        "tier_threshold_source": "B41E thresholds unchanged",
        "2025_holdout_opened": False, "week4_2026_opened": False,
        "B41C3_completed": False, "production_model_fitted": True,
        "production_model_deployed": False, "production_change_authorized": False,
        "next_stage": "Complete B41C3 untouched 2026 Week 4 scorer validation after all Week 4 games are final and Sleeper scoring settles; only then open untouched 2025."}
    Path(a.out).write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": snapshot["status"],
                      "selected_alpha_by_position": {p: results[p]["alpha_selection"]["selected_alpha"] for p in POSITIONS},
                      "2025_holdout_opened": False, "week4_2026_opened": False,
                      "production_authorized": False}, indent=2))

if __name__ == "__main__":
    main()

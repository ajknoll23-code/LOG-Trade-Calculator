#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

SEASONS = [2019, 2020, 2021, 2022, 2023, 2024]
POSITIONS = ["QB", "RB", "WR", "TE", "K", "DL", "LB", "DB"]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def usable(train, feature):
    x = pd.to_numeric(train[feature], errors='coerce')
    finite = x[np.isfinite(x)]
    return len(finite) >= 2 and finite.nunique() >= 2

def select_baseline(sub, features):
    candidates = []
    for feature in sorted(features):
        folds = []
        eligible = True
        for season in SEASONS:
            tr = sub[sub['season'] != season]
            va = sub[sub['season'] == season]
            if not usable(tr, feature):
                eligible = False
                break
            tr_x = pd.to_numeric(tr[feature], errors='coerce').astype(float)
            va_x = pd.to_numeric(va[feature], errors='coerce').astype(float)
            med = float(tr_x.median(skipna=True)) if tr_x.notna().any() else 0.5
            pred = np.clip(va_x.fillna(med).to_numpy(float), 0.0, 1.0)
            y = va['target_percentile'].to_numpy(float)
            folds.append({
                'validation_season': int(season),
                'n': int(len(va)),
                'mae': float(mean_absolute_error(y, pred)),
                'training_median': med,
            })
        if eligible and folds:
            candidates.append({
                'feature': feature,
                'mean_loso_mae': float(np.mean([r['mae'] for r in folds])),
                'folds': folds,
            })
    if not candidates:
        raise RuntimeError('B41G_NO_ELIGIBLE_BASELINE_FEATURE')
    candidates.sort(key=lambda r: (r['mean_loso_mae'], r['feature']))
    winner = candidates[0]
    x = pd.to_numeric(sub[winner['feature']], errors='coerce').astype(float)
    full_median = float(x.median(skipna=True)) if x.notna().any() else 0.5
    return winner, full_median, candidates

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--development-contract', required=True)
    ap.add_argument('--b41d-decision', required=True)
    ap.add_argument('--b41f-snapshot', required=True)
    ap.add_argument('--prereg', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    contract = json.loads(Path(a.development_contract).read_text())
    decision = json.loads(Path(a.b41d_decision).read_text())
    final = json.loads(Path(a.b41f_snapshot).read_text())
    prereg = json.loads(Path(a.prereg).read_text())

    if sha(a.data) != prereg['frozen_inputs']['development_modeling_data_sha256']:
        raise RuntimeError('B41G_MODELING_DATA_SHA_MISMATCH')
    if final['2025_holdout_opened'] or final['week4_2026_opened']:
        raise RuntimeError('B41G_FIREWALL_BROKEN')
    if final['production_model_deployed'] or final['production_change_authorized']:
        raise RuntimeError('B41G_PRODUCTION_ALREADY_CHANGED')

    df = pd.read_csv(a.data, compression='gzip')
    if len(df) != 85648:
        raise RuntimeError(f'B41G_MODELING_ROW_COUNT {len(df)}')
    if sorted(df['season'].astype(int).unique()) != SEASONS:
        raise RuntimeError('B41G_DEVELOPMENT_SEASONS_DRIFT')
    if 2025 in set(df['season'].astype(int)):
        raise RuntimeError('B41G_2025_LEAK_IN_DEVELOPMENT_ARTIFACT')

    out = {}
    for pos in POSITIONS:
        sub = df[df['position'] == pos].copy()
        features = list(contract['position_feature_columns'][pos])
        if decision['selected_family_by_position'][pos] != 'nonnegative_ridge_linear':
            raise RuntimeError(f'B41G_SELECTED_FAMILY_DRIFT {pos}')
        if final['position_models'][pos]['selected_family'] != 'nonnegative_ridge_linear':
            raise RuntimeError(f'B41G_FINAL_FAMILY_DRIFT {pos}')
        winner, median, candidates = select_baseline(sub, features)
        out[pos] = {
            'selected_feature': winner['feature'],
            'selection_rule': 'lowest six-season LOSO mean MAE; lexicographic feature name wins exact tie',
            'mean_loso_mae': winner['mean_loso_mae'],
            'folds': winner['folds'],
            'full_development_imputation_median': median,
            'holdout_prediction_rule': 'clip(imputed selected normalized feature, 0, 1)',
            'candidate_results_sorted': candidates,
            'n_development_rows': int(len(sub)),
        }

    snapshot = {
        'schema_version': 1,
        'study_id': 'player-role-v2',
        'phase': 'B41G-best-single-signal-baseline-freeze',
        'status': 'BASELINE_FROZEN_BEFORE_2025_HOLDOUT_OPEN',
        'development_seasons': SEASONS,
        'development_modeling_data_sha256': sha(a.data),
        'development_modeling_row_count': int(len(df)),
        'position_baselines': out,
        '2025_holdout_opened': False,
        '2026_week4_opened_by_b41g': False,
        'model_or_tier_retuning_performed': False,
        'production_model_deployed': False,
        'production_change_authorized': False,
    }
    Path(a.out).write_text(json.dumps(snapshot, indent=2, sort_keys=True) + '\n')

if __name__ == '__main__':
    main()

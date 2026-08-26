# Baseline Backtest Report (Revision 2)

**Test 3 is the decision criterion.** Test 1 and Test 2 are diagnostics kept for context, per the methodology review that found Test 1's original correlation-based design could not mathematically distinguish baseline quality within a position (see script docstring).


## QB

### Test 3 (decision criterion) -- MAE against non-circular future relative-production target

| Candidate | Median MAE (4wk) | Folds won (4wk) | MAE @2wk | MAE @4wk | MAE @6wk |
|---|---|---|---|---|---|
| documented | 0.5574 | 15 | 0.4478 | 0.5574 | 0.5854 |
| legacy_empirical | 0.5574 | 0 | 0.4478 | 0.5574 | 0.5854 |
| roster_economics_informed | 0.5574 | 0 | 0.4478 | 0.5574 | 0.5854 |

**Best by Test 3: documented**  |  Stable across forward-window sizes: **True** (per-window winners: {2: 'documented', 4: 'documented', 6: 'documented'})

### Test 1 (diagnostic -- clamp sensitivity, NOT a winner-picker)

| Candidate | Median Pearson | Median Spearman | Median floor% | Median ceiling% |
|---|---|---|---|---|
| documented | 0.5055 | 0.467 | 12.5 | 0.0 |
| legacy_empirical | 0.5055 | 0.467 | 12.5 | 0.0 |
| roster_economics_informed | 0.5055 | 0.467 | 12.5 | 0.0 |

### Test 2 (diagnostic -- future-production tier-break, NOT ground truth)

Median optimal split (independent of named candidates): **rank 20** across 15 folds

### Real-data sanity table (cross-season fold)

| Candidate | Rank | Player at rank | Baseline PPG | Eligible players | Floor% | Ceiling% |
|---|---|---|---|---|---|---|
| documented | 18 | Marcus Mariota | 16.45 | 69 | 31.9 | 0.0 |
| legacy_empirical | 18 | Marcus Mariota | 16.45 | 69 | 31.9 | 0.0 |
| roster_economics_informed | 18 | Marcus Mariota | 16.45 | 69 | 31.9 | 0.0 |

## RB

### Test 3 (decision criterion) -- MAE against non-circular future relative-production target

| Candidate | Median MAE (4wk) | Folds won (4wk) | MAE @2wk | MAE @4wk | MAE @6wk |
|---|---|---|---|---|---|
| documented | 0.2774 | 0 | 0.3062 | 0.2774 | 0.2637 |
| legacy_empirical | 0.3344 | 0 | 0.3523 | 0.3344 | 0.3249 |
| roster_economics_informed | 0.2391 | 15 | 0.2655 | 0.2391 | 0.2223 |

**Best by Test 3: roster_economics_informed**  |  Stable across forward-window sizes: **True** (per-window winners: {2: 'roster_economics_informed', 4: 'roster_economics_informed', 6: 'roster_economics_informed'})

### Test 1 (diagnostic -- clamp sensitivity, NOT a winner-picker)

| Candidate | Median Pearson | Median Spearman | Median floor% | Median ceiling% |
|---|---|---|---|---|
| documented | 0.818 | 0.8215 | 37.8 | 2.0 |
| legacy_empirical | 0.8206 | 0.8258 | 34.9 | 3.0 |
| roster_economics_informed | 0.8103 | 0.8199 | 41.7 | 0.0 |

### Test 2 (diagnostic -- future-production tier-break, NOT ground truth)

Median optimal split (independent of named candidates): **rank 20** across 15 folds

### Real-data sanity table (cross-season fold)

| Candidate | Rank | Player at rank | Baseline PPG | Eligible players | Floor% | Ceiling% |
|---|---|---|---|---|---|---|
| documented | 32 | Jordan Mason | 12.17 | 128 | 43.8 | 0.8 |
| legacy_empirical | 37 | Alexander Mattison | 10.58 | 128 | 41.4 | 2.3 |
| roster_economics_informed | 26 | Brian Robinson | 13.85 | 128 | 49.2 | 0.0 |

## WR

### Test 3 (decision criterion) -- MAE against non-circular future relative-production target

| Candidate | Median MAE (4wk) | Folds won (4wk) | MAE @2wk | MAE @4wk | MAE @6wk |
|---|---|---|---|---|---|
| documented | 0.2485 | 0 | 0.2773 | 0.2485 | 0.2443 |
| legacy_empirical | 0.2826 | 0 | 0.3206 | 0.2826 | 0.2613 |
| roster_economics_informed | 0.2443 | 15 | 0.27 | 0.2443 | 0.2337 |

**Best by Test 3: roster_economics_informed**  |  Stable across forward-window sizes: **True** (per-window winners: {2: 'roster_economics_informed', 4: 'roster_economics_informed', 6: 'roster_economics_informed'})

### Test 1 (diagnostic -- clamp sensitivity, NOT a winner-picker)

| Candidate | Median Pearson | Median Spearman | Median floor% | Median ceiling% |
|---|---|---|---|---|
| documented | 0.7197 | 0.7427 | 46.1 | 0.0 |
| legacy_empirical | 0.725 | 0.7495 | 42.1 | 0.0 |
| roster_economics_informed | 0.7191 | 0.7427 | 46.5 | 0.0 |

### Test 2 (diagnostic -- future-production tier-break, NOT ground truth)

Median optimal split (independent of named candidates): **rank 13** across 15 folds

### Real-data sanity table (cross-season fold)

| Candidate | Rank | Player at rank | Baseline PPG | Eligible players | Floor% | Ceiling% |
|---|---|---|---|---|---|---|
| documented | 36 | Jayden Reed | 10.56 | 223 | 52.0 | 0.0 |
| legacy_empirical | 43 | Khalil Shakir | 9.93 | 223 | 50.7 | 0.0 |
| roster_economics_informed | 34 | Zay Flowers | 10.93 | 223 | 52.9 | 0.0 |

## TE

### Test 3 (decision criterion) -- MAE against non-circular future relative-production target

| Candidate | Median MAE (4wk) | Folds won (4wk) | MAE @2wk | MAE @4wk | MAE @6wk |
|---|---|---|---|---|---|
| documented | 0.2213 | 10 | 0.2342 | 0.2213 | 0.2047 |
| legacy_empirical | 0.2221 | 5 | 0.2397 | 0.2221 | 0.2086 |
| roster_economics_informed | 0.2213 | 0 | 0.2342 | 0.2213 | 0.2047 |

**Best by Test 3: documented**  |  Stable across forward-window sizes: **True** (per-window winners: {2: 'documented', 4: 'documented', 6: 'documented'})

### Test 1 (diagnostic -- clamp sensitivity, NOT a winner-picker)

| Candidate | Median Pearson | Median Spearman | Median floor% | Median ceiling% |
|---|---|---|---|---|
| documented | 0.7407 | 0.7536 | 57.3 | 0.0 |
| legacy_empirical | 0.7441 | 0.7507 | 55.9 | 0.0 |
| roster_economics_informed | 0.7407 | 0.7536 | 57.3 | 0.0 |

### Test 2 (diagnostic -- future-production tier-break, NOT ground truth)

Median optimal split (independent of named candidates): **rank 22** across 15 folds

### Real-data sanity table (cross-season fold)

| Candidate | Rank | Player at rank | Baseline PPG | Eligible players | Floor% | Ceiling% |
|---|---|---|---|---|---|---|
| documented | 15 | Evan Engram | 7.72 | 131 | 64.9 | 0.0 |
| legacy_empirical | 16 | Tyler Higbee | 7.53 | 131 | 64.1 | 0.0 |
| roster_economics_informed | 15 | Evan Engram | 7.72 | 131 | 64.9 | 0.0 |

## DL

### Test 3 (decision criterion) -- MAE against non-circular future relative-production target

| Candidate | Median MAE (4wk) | Folds won (4wk) | MAE @2wk | MAE @4wk | MAE @6wk |
|---|---|---|---|---|---|
| documented | 0.2551 | 0 | 0.2997 | 0.2551 | 0.2378 |
| legacy_empirical | 0.228 | 15 | 0.2826 | 0.228 | 0.2142 |
| roster_economics_informed | 0.2551 | 0 | 0.2997 | 0.2551 | 0.2378 |

**Best by Test 3: legacy_empirical**  |  Stable across forward-window sizes: **True** (per-window winners: {2: 'legacy_empirical', 4: 'legacy_empirical', 6: 'legacy_empirical'})

### Test 1 (diagnostic -- clamp sensitivity, NOT a winner-picker)

| Candidate | Median Pearson | Median Spearman | Median floor% | Median ceiling% |
|---|---|---|---|---|
| documented | 0.6177 | 0.5958 | 36.5 | 0.0 |
| legacy_empirical | 0.614 | 0.5953 | 39.3 | 0.0 |
| roster_economics_informed | 0.6177 | 0.5958 | 36.5 | 0.0 |

### Test 2 (diagnostic -- future-production tier-break, NOT ground truth)

Median optimal split (independent of named candidates): **rank 16** across 15 folds

### Real-data sanity table (cross-season fold)

| Candidate | Rank | Player at rank | Baseline PPG | Eligible players | Floor% | Ceiling% |
|---|---|---|---|---|---|---|
| documented | 32 | Carl Granderson | 8.72 | 317 | 38.5 | 0.3 |
| legacy_empirical | 23 | George Karlaftis | 9.81 | 317 | 43.2 | 0.0 |
| roster_economics_informed | 32 | Carl Granderson | 8.72 | 317 | 38.5 | 0.3 |

## LB

### Test 3 (decision criterion) -- MAE against non-circular future relative-production target

| Candidate | Median MAE (4wk) | Folds won (4wk) | MAE @2wk | MAE @4wk | MAE @6wk |
|---|---|---|---|---|---|
| documented | 0.1936 | 15 | 0.2208 | 0.1936 | 0.1863 |
| legacy_empirical | 0.1936 | 0 | 0.2208 | 0.1936 | 0.1863 |
| roster_economics_informed | 0.1936 | 0 | 0.2208 | 0.1936 | 0.1863 |

**Best by Test 3: documented**  |  Stable across forward-window sizes: **True** (per-window winners: {2: 'documented', 4: 'documented', 6: 'documented'})

### Test 1 (diagnostic -- clamp sensitivity, NOT a winner-picker)

| Candidate | Median Pearson | Median Spearman | Median floor% | Median ceiling% |
|---|---|---|---|---|
| documented | 0.7398 | 0.7611 | 46.3 | 0.0 |
| legacy_empirical | 0.7398 | 0.7611 | 46.3 | 0.0 |
| roster_economics_informed | 0.7398 | 0.7611 | 46.3 | 0.0 |

### Test 2 (diagnostic -- future-production tier-break, NOT ground truth)

Median optimal split (independent of named candidates): **rank 27** across 15 folds

### Real-data sanity table (cross-season fold)

| Candidate | Rank | Player at rank | Baseline PPG | Eligible players | Floor% | Ceiling% |
|---|---|---|---|---|---|---|
| documented | 32 | Azeez Al-Shaair | 13.11 | 267 | 51.3 | 0.0 |
| legacy_empirical | 32 | Azeez Al-Shaair | 13.11 | 267 | 51.3 | 0.0 |
| roster_economics_informed | 32 | Azeez Al-Shaair | 13.11 | 267 | 51.3 | 0.0 |

## DB

### Test 3 (decision criterion) -- MAE against non-circular future relative-production target

| Candidate | Median MAE (4wk) | Folds won (4wk) | MAE @2wk | MAE @4wk | MAE @6wk |
|---|---|---|---|---|---|
| documented | 0.2228 | 0 | 0.254 | 0.2228 | 0.2104 |
| legacy_empirical | 0.2219 | 15 | 0.2536 | 0.2219 | 0.2091 |
| roster_economics_informed | 0.2228 | 0 | 0.254 | 0.2228 | 0.2104 |

**Best by Test 3: legacy_empirical**  |  Stable across forward-window sizes: **True** (per-window winners: {2: 'legacy_empirical', 4: 'legacy_empirical', 6: 'legacy_empirical'})

### Test 1 (diagnostic -- clamp sensitivity, NOT a winner-picker)

| Candidate | Median Pearson | Median Spearman | Median floor% | Median ceiling% |
|---|---|---|---|---|
| documented | 0.6457 | 0.6914 | 40.5 | 0.0 |
| legacy_empirical | 0.6452 | 0.6914 | 40.8 | 0.0 |
| roster_economics_informed | 0.6457 | 0.6914 | 40.5 | 0.0 |

### Test 2 (diagnostic -- future-production tier-break, NOT ground truth)

Median optimal split (independent of named candidates): **rank 23** across 15 folds

### Real-data sanity table (cross-season fold)

| Candidate | Rank | Player at rank | Baseline PPG | Eligible players | Floor% | Ceiling% |
|---|---|---|---|---|---|---|
| documented | 32 | Tyler Nubin | 10.73 | 392 | 43.1 | 0.0 |
| legacy_empirical | 30 | Marcus Epps | 10.75 | 392 | 43.1 | 0.0 |
| roster_economics_informed | 32 | Tyler Nubin | 10.73 | 392 | 43.1 | 0.0 |

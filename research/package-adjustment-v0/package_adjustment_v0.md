# Package Adjustment V0 Research

**Status: RESEARCH ONLY — no production consumer changed.**

## V0 formula

`S = sum(Fundamental Values on the side)`

`H = Σ(vᵢ / S)²`

`F = 1 - H`

`G = max(0, 1 - top_asset_this_side / top_asset_other_side)`

`discount_rate = λ × F × G`

`effective_package_value = S × (1 - discount_rate)`

V0 uses Fundamental Value only. It does not use Market Value, Team Utility, roster slots, a pick-liquidity modifier, or an elite-percentile multiplier.

## Why this is still shadow-only

`λ` is not calibrated. The grid below is sensitivity analysis, not a recommendation. Production promotion requires package-voting or prospective revealed-preference labels.

## Current scenario universe

- Teams: `12`
- Active FV coverage: `95.86%`
- Raw-balanced stud-for-depth scenarios: `3100`
- Deployed Team Utility bench weight: `0.15` (unchanged)
- Active roster limit: `41`

## 1-for-2 package geometry

- Scenarios: `1562`
- Median fragmentation F: `0.438`
- Median best-asset gap G: `0.324`
- Median F×G: `0.142`

| λ | Median discount | P10–P90 discount | Effective package below target |
|---:|---:|---:|---:|
| 0.00 | 0.0% | 0.0%–0.0% | 47.6% |
| 0.10 | 1.4% | 0.6%–2.3% | 98.7% |
| 0.25 | 3.6% | 1.6%–5.8% | 99.3% |
| 0.50 | 7.1% | 3.1%–11.5% | 99.7% |
| 0.75 | 10.7% | 4.7%–17.3% | 100.0% |
| 1.00 | 14.2% | 6.3%–23.1% | 100.0% |

For scenarios where the raw package is worth more than the target, the λ needed merely to erase that raw surplus is:

- P10: `0.0017`
- Median: `0.0079`
- P90: `0.0426`

## 1-for-3 package geometry

- Scenarios: `1538`
- Median fragmentation F: `0.607`
- Median best-asset gap G: `0.492`
- Median F×G: `0.299`

| λ | Median discount | P10–P90 discount | Effective package below target |
|---:|---:|---:|---:|
| 0.00 | 0.0% | 0.0%–0.0% | 37.2% |
| 0.10 | 3.0% | 2.0%–4.0% | 97.5% |
| 0.25 | 7.5% | 4.9%–10.1% | 100.0% |
| 0.50 | 15.0% | 9.8%–20.2% | 100.0% |
| 0.75 | 22.5% | 14.7%–30.2% | 100.0% |
| 1.00 | 29.9% | 19.6%–40.3% | 100.0% |

For scenarios where the raw package is worth more than the target, the λ needed merely to erase that raw surplus is:

- P10: `0.0007`
- Median: `0.0034`
- P90: `0.0473`

## Torture tests

- `one_for_one_null`: **PASS**
- `balanced_two_for_two_null`: **PASS**
- `elite_vs_fragmented_equal_raw_sum`: **PASS**
- `extreme_fragmentation_monotonic`: **PASS**
- `best_asset_gap_monotonic`: **PASS**
- `tiny_asset_padding_resistance`: **PASS**
- `zero_asset_padding_null`: **PASS**
- `scale_invariance`: **PASS**
- `secondary_split_monotonic`: **PASS**
- `package_with_best_asset_not_taxed`: **PASS**
- `side_swap_symmetry`: **PASS**

## Explicitly excluded from V0

- Elite-percentile multiplier `E(p)`
- Pick liquidity or future-pick modifier
- Market Value
- Roster displacement/cuts (Team Utility owns that)
- Position-specific package coefficients
- Production trade verdicts

## Production impact

- Fundamental Value changed: **NO**
- Market Value changed: **NO**
- Team Utility changed: **NO**
- Live trade verdict changed: **NO**
- Package Adjustment consumer enabled: **NO**

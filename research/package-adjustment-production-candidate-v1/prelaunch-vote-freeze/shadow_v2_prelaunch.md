# Package Adjustment Shadow V2

**Status: RESEARCH ONLY — no live calculator consumer changed.**

## Preferred hybrid

- 2-player package: V3 target-sensitive monotonic curve.
- 3-player package: V4 ratio-only constant at `2.051x`.

## Why 3-player changed

- V4 package choice at 2.05x: `50.0%`.
- V4 bootstrap indifference inside tested range: `88.25%`.
- V4 ratio coefficient positive: `100.0%` of voter-cluster bootstraps.
- Ratio-only AIC `399.55` vs ratio+target `401.47`.

## Reference adjustments

| Target ref | Target FV | 2p multiplier | 2p adjustment | 3p multiplier | 3p adjustment |
|---|---:|---:|---:|---:|---:|
| p25 | 4269 | 1.401x | 1711 | 2.051x | 4488 |
| median | 5050 | 1.486x | 2453 | 2.051x | 5308 |
| p75 | 5558 | 1.537x | 2984 | 2.051x | 5843 |
| p90 | 6079 | 1.586x | 3562 | 2.051x | 6390 |

## Guardrails

- 1-for-1: zero adjustment.
- Multi-v-multi: unsupported.
- 4+ meaningful pieces: unsupported.
- Picks: unsupported.
- Tiny throw-ins below 6% of target FV do not increase package size.
- Team Utility remains separate.

## Promotion

Do not promote live yet. Freeze this curve and validate prospectively/out-of-sample.

## Torture tests

- one_for_one_null: `PASS`
- multi_vs_multi_unsupported_null: `PASS`
- equal_or_better_package_asset_unsupported: `PASS`
- four_meaningful_pieces_unsupported: `PASS`
- tiny_throw_in_padding_resistance: `PASS`
- two_player_target_curve_monotonic: `PASS`
- three_player_premium_above_two_player: `PASS`
- three_player_target_neutral: `PASS`
- three_player_no_longer_extrapolated: `PASS`
- side_swap_symmetry: `PASS`

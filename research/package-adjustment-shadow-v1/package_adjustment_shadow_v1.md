# Package Adjustment Shadow V1

**Status: RESEARCH ONLY — no live calculator consumer changed.**

This shadow converts V3 package-vote indifference evidence into candidate KTC-style value adjustments without changing player FV.

## Supported shape

- One concentrated player versus 2 or 3 meaningful lesser players.
- A meaningful package piece must be at least `6%` of target FV, matching V3 construction.
- Tiny throw-ins do not increase package size.
- Picks, 4+ meaningful pieces, and multi-v-multi are not modeled.

## Candidate models

### 1. Simple ratio + package size

- 2-player indifference multiplier: `1.458x`
- 3-player indifference multiplier: `1.990x`

### 2. Target-sensitive monotonic — preferred shadow candidate

Uses V3's monotonic ratio+size+target model and interpolates only inside the empirical p25-p90 target-FV band; values outside are clamped rather than extrapolated.

### 3. Target interaction — diagnostic only

Retains the lowest-AIC V3 interaction model for comparison, but it is not promotion-eligible because its target interaction is not economically monotonic enough.

## Reference adjustments

| Target ref | Target FV | Monotonic 2p multiplier | 2p adjustment | Monotonic 3p multiplier | 3p adjustment |
|---|---:|---:|---:|---:|---:|
| p25 | 4269 | 1.401x | 1711 | 1.907x | 3872 |
| median | 5050 | 1.486x | 2453 | 2.023x | 5164 |
| p75 | 5558 | 1.537x | 2984 | 2.092x | 6070 |
| p90 | 6079 | 1.586x | 3562 | 2.159x | 7045 |

## Frozen V3 challenge-catalog replay

Replayed all `200` frozen V3 trade shapes through all three candidates.

| Candidate | Size | Challenges | Median multiplier | Median adjustment | Offers meeting shadow requirement | Beyond tested ratio range |
|---|---:|---:|---:|---:|---:|---:|
| simple_ratio_plus_size | 2 | 100 | 1.458x | 2311 | 40.0% | 0.0% |
| simple_ratio_plus_size | 3 | 100 | 1.990x | 4999 | 0.0% | 100.0% |
| target_sensitive_monotonic | 2 | 100 | 1.486x | 2454 | 41.0% | 0.0% |
| target_sensitive_monotonic | 3 | 100 | 2.023x | 5165 | 0.0% | 100.0% |
| target_interaction_diagnostic_only | 2 | 100 | 1.496x | 2503 | 40.0% | 0.0% |
| target_interaction_diagnostic_only | 3 | 100 | 1.925x | 4709 | 3.0% | 85.0% |

## Evidence guardrails

- Raw-ratio coefficient positive in voter-cluster bootstrap: `100.0%`
- 3-player coefficient negative in voter-cluster bootstrap: `100.0%`
- 2-player indifference estimates within tested ratio range: `100.0%`
- 3-player indifference estimates within tested ratio range: `4.25%`
- Therefore the 2-player shadow is materially better identified than the 3-player indifference level.

## Torture tests

- one_for_one_null: `PASS`
- balanced_multi_vs_multi_unsupported_null: `PASS`
- package_with_equal_or_better_asset_unsupported: `PASS`
- four_meaningful_pieces_unsupported: `PASS`
- tiny_throw_in_padding_resistance: `PASS`
- three_piece_premium_above_two_piece: `PASS`
- target_sensitive_reference_monotonicity: `PASS`
- target_fv_extrapolation_clamped: `PASS`
- simple_candidate_matches_v3_diagnostic: `PASS`
- nonnegative_adjustment: `PASS`
- side_swap_symmetry: `PASS`
- three_player_extrapolation_is_explicit: `PASS`

## Recommendation

Carry `target_sensitive_monotonic` forward as the shadow candidate. Do not promote live yet. Continue V3/OOS collection and extend the 3-player experiment above 1.85x.

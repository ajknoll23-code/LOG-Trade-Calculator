# Package Adjustment — Production Candidate V1 Validation

**No live calculator consumer changed in this validation run.**

- Controlled launch recommended: `True`
- Synthetic shapes: `20000`
- Supported shapes: `17956` (89.8%)
- Supported verdicts changed: `78.2%`

## Candidate

- 2-player premium: frozen V3 target-sensitive curve.
- Full 3-player premium: frozen V4 `2.051x`.
- Full 3-player premium requires smallest player >= `16%` of package player FV.
- Smaller third players still add full FV but do not escalate the premium tier.

## V4 composition support

- smallest-piece package-share min: `21.2%`
- p05: `21.6%`
- median: `22.0%`

## Frozen replay

- V3 2-player preservation: `100.0%`
- V4 3-player preservation: `100.0%`

## Launch gates

- source_torture_tests: `True`
- production_torture_tests: `True`
- v3_replay_100pct: `True`
- v4_replay_100pct: `True`
- v4_multiplier_exact: `True`
- 20k_synthetic_shapes: `True`
- direction_invariant: `True`
- live_verdict_thresholds: `True`

## Torture tests

- one_for_one_null: `PASS`
- equal_or_better_asset_unsupported: `PASS`
- four_plus_meaningful_unsupported: `PASS`
- tiny_throw_in_does_not_raise_premium: `PASS`
- small_third_guard: `PASS`
- v4_like_shape_gets_full_3p: `PASS`
- size2_curve_monotonic: `PASS`
- size3_above_size2: `PASS`
- exact_requirement_is_fair: `PASS`
- adjustment_never_moves_verdict_toward_package: `PASS`
- live_verdict_thresholds_verified: `PASS`

## Posture

If every launch gate is green, this candidate is eligible for a controlled live launch. Future completed trades are monitoring evidence, not a prelaunch requirement.

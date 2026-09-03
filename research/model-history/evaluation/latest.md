# Trade Desk Historical Fundamental Backtest

Protocol: `fundamental-v1`  
Protocol SHA256: `b6e66793b947e629d8ea238663fc4ab9e94dc7fb6c6b52495ac1207451ba0b29`

## Status

- Snapshots seen: **11**
- Prediction states after deduplication: **3**
- Deduplicated repeated snapshots: **8**
- Outcome identity coverage: **100.0%**
- Completed realized weeks available: **[]**
- Evaluated snapshot/horizon combinations: **0**
- Pending snapshot/horizon combinations: **9**

## Frozen V1 leakage rules

The scoring period containing a snapshot is excluded. Fixed 4-week and 8-week horizons are not graded until every required future week is complete. A week is only treated as complete when the realized-outcome refresh timestamp is on/after its Tuesday completion boundary derived from Sleeper's season start date.

## Evaluated horizons

No horizon is mature enough to grade yet. This is expected before the first four post-snapshot regular-season weeks have completed.

## Interpretation guardrails

- `value_vs_total_points` is the roster-value/availability target.
- `prod_mult_vs_active_ppg` is the cleaner production-rate target.
- KTC is **not** treated as fundamental truth here; future market calibration is a separate target.
- This evaluator reports evidence. It does not automatically rewrite player values or model constants.

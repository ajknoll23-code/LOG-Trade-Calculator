# Trade Desk Historical Fundamental Backtest

Protocol: `fundamental-v1`  
Protocol SHA256: `b6e66793b947e629d8ea238663fc4ab9e94dc7fb6c6b52495ac1207451ba0b29`

## Status

- Snapshots seen: **36**
- Prediction states after deduplication: **21**
- Deduplicated repeated snapshots: **15**
- Outcome identity coverage: **100.0%**
- Completed realized weeks available: **[1, 2, 3, 4]**
- Evaluated snapshot/horizon combinations: **7**
- Pending snapshot/horizon combinations: **56**

## Frozen V1 leakage rules

The scoring period containing a snapshot is excluded. Fixed 4-week and 8-week horizons are not graded until every required future week is complete. A week is only treated as complete when the realized-outcome refresh timestamp is on/after its Tuesday completion boundary derived from Sleeper's season start date.

## Evaluated horizons

| Snapshot | First future week | Horizon | Value↔total Spearman | Pairwise acc. | ProdMult↔active PPG Spearman | Active players |
|---|---:|---|---:|---:|---:|---:|
| 2026-09-01T21:10:40.561467Z | 1 | future_4w | 0.652 | 0.741 | 0.521 | 492 |
| 2026-09-02T19:29:31.487917Z | 1 | future_4w | 0.652 | 0.741 | 0.521 | 492 |
| 2026-09-03T04:38:42.789796Z | 1 | future_4w | 0.652 | 0.741 | 0.521 | 492 |
| 2026-09-04T18:00:29.214394Z | 1 | future_4w | 0.652 | 0.741 | 0.521 | 492 |
| 2026-09-05T19:46:05.101299Z | 1 | future_4w | 0.652 | 0.741 | 0.521 | 492 |
| 2026-09-07T08:13:19.532310Z | 1 | future_4w | 0.652 | 0.741 | 0.521 | 492 |
| 2026-09-08T18:25:19.343501Z | 1 | future_4w | 0.652 | 0.741 | 0.521 | 492 |

## Interpretation guardrails

- `value_vs_total_points` is the roster-value/availability target.
- `prod_mult_vs_active_ppg` is the cleaner production-rate target.
- KTC is **not** treated as fundamental truth here; future market calibration is a separate target.
- This evaluator reports evidence. It does not automatically rewrite player values or model constants.

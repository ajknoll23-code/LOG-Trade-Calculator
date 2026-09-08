# Trade Desk Historical Market Backtest

Protocol: `market-v1`  
Protocol SHA256: `fe6ccf0d5b05bf15038e9239f4c7b18c1d8a40ba93f4f9db8cb01fcec6b0769a`

## Status

- Full snapshots seen: **14**
- Weekly market states after deduplication: **2**
- Same-week snapshots deduplicated: **12**
- Evaluated origin/horizon pairs: **1**
- Pending origin/horizon pairs: **5**

## What this measures

This is a **market-target** backtest, not a fundamental player-quality backtest. The current league market is the required persistence baseline. Trade Desk only adds market-predictive value when it beats that baseline on the same players.

## Evaluated horizons

| Origin | Future | Horizon | N | TD→future Spearman | Current market→future | Incremental Δ | Gap→change Spearman | Directional acc. |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2026-W36 | 2026-W37 | 1w | 453 | 0.378 | 0.962 | -0.584 | 0.148 | 0.560 |

## Interpretation guardrails

- Negative incremental delta means current-market persistence beat Trade Desk for that horizon.
- Positive gap→change relationship means model/market disagreement anticipated later market movement.
- Voter concentration is preserved per evaluated pair; concentrated voting makes apparent movement less independent.
- This report never rewrites player values, position weights, or Team Utility automatically.

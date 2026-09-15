# Trade Desk Historical Market Backtest

Protocol: `market-v1`  
Protocol SHA256: `fe6ccf0d5b05bf15038e9239f4c7b18c1d8a40ba93f4f9db8cb01fcec6b0769a`

## Status

- Full snapshots seen: **21**
- Weekly market states after deduplication: **3**
- Same-week snapshots deduplicated: **18**
- Evaluated origin/horizon pairs: **3**
- Pending origin/horizon pairs: **6**

## What this measures

This is a **market-target** backtest, not a fundamental player-quality backtest. The current league market is the required persistence baseline. Trade Desk only adds market-predictive value when it beats that baseline on the same players.

## Evaluated horizons

| Origin | Future | Horizon | N | TD→future Spearman | Current market→future | Incremental Δ | Gap→change Spearman | Directional acc. |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2026-W36 | 2026-W37 | 1w | 453 | 0.382 | 0.955 | -0.573 | 0.173 | 0.560 |
| 2026-W36 | 2026-W38 | 2w | 453 | 0.383 | 0.944 | -0.561 | 0.171 | 0.570 |
| 2026-W37 | 2026-W38 | 1w | 476 | 0.377 | 0.987 | -0.610 | 0.014 | 0.540 |

## Interpretation guardrails

- Negative incremental delta means current-market persistence beat Trade Desk for that horizon.
- Positive gap→change relationship means model/market disagreement anticipated later market movement.
- Voter concentration is preserved per evaluated pair; concentrated voting makes apparent movement less independent.
- This report never rewrites player values, position weights, or Team Utility automatically.

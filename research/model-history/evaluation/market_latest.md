# Trade Desk Historical Market Backtest

Protocol: `market-v1`  
Protocol SHA256: `fe6ccf0d5b05bf15038e9239f4c7b18c1d8a40ba93f4f9db8cb01fcec6b0769a`

## Status

- Full snapshots seen: **10**
- Weekly market states after deduplication: **1**
- Same-week snapshots deduplicated: **9**
- Evaluated origin/horizon pairs: **0**
- Pending origin/horizon pairs: **3**

## What this measures

This is a **market-target** backtest, not a fundamental player-quality backtest. The current league market is the required persistence baseline. Trade Desk only adds market-predictive value when it beats that baseline on the same players.

## Evaluated horizons

No future weekly market state is mature yet. This is expected until a later full-refresh week creates the first true out-of-sample market target.

## Interpretation guardrails

- Negative incremental delta means current-market persistence beat Trade Desk for that horizon.
- Positive gap→change relationship means model/market disagreement anticipated later market movement.
- Voter concentration is preserved per evaluated pair; concentrated voting makes apparent movement less independent.
- This report never rewrites player values, position weights, or Team Utility automatically.

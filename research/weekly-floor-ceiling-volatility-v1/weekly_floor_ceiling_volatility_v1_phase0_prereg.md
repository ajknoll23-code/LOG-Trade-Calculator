# Weekly Floor/Ceiling Volatility V1 — Phase 0

**Status:** `PREREGISTERED_SOURCE_CONTRACT_ONLY`

This study is display/research only. It may not change Fundamental Value,
Package Adjustment, Team Utility, Trade Value, Market Value, trade verdicts,
or player projections.

## V1 source concept

The primary source candidate is **4for4**, but Phase 1A must prove that the
private source actually contains explicit, week-specific player floor and
ceiling fields. V1 will not manufacture a floor or ceiling from a mean
projection, historical variance, FV, ADP, or market value.

Raw licensed provider rows remain private. Public artifacts may contain only
source hashes and aggregate validation metadata.

## Frozen constructs

- **Floor Strength:** within-position weekly percentile of the explicit provider floor.
- **Ceiling Strength:** within-position weekly percentile of the explicit provider ceiling.
- **Volatility Width:** `ceiling - floor`, normalized within position/week.
- **Overall score:** prohibited in V1.

Higher volatility width means only that the provider's displayed band is wider.
It is not automatically "riskier," worse, or better.

## Scope

QB/RB/WR/TE only. Half-PPR only. Weekly only. Bye or missing rows are
unavailable, never neutral.

## Governance

Outcomes remain sealed in Phase 1A and Phase 1B. Phase 1B must freeze the
provider semantics and exact retrospective validation gates before Phase 2 may
read realized fantasy outcomes.

No user-facing production display is authorized by Phase 0.

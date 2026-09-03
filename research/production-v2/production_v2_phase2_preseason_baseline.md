# Production V2 — Phase 2A Preseason Baseline

## Decision

**FROZEN RESEARCH BASELINE — no production change and no optimal-weight claim is authorized.**

Repository has no temporally-valid 2025 FantasyPros/Sleeper preseason projection snapshots. Sensitivity is measurable now; optimal weights require future realized 2026 outcomes.

This snapshot exists so 2026 results can later be scored against information that was genuinely available before the season.

## Reference integrity

- Phase-1 exact reproduction: **Yes**
- Maximum final-value reproduction delta: **0**
- Reference provider blend: **50% FantasyPros / 50% Sleeper when both exist**
- Reference history/forward: **45% / 55%**

## Current provider disagreement — offense

| Pos | Both-provider N | Median abs disagreement | P90 | P95 | Max |
|---|---:|---:|---:|---:|---:|
| QB | 33 | 5.3% | 10.7% | 42.3% | 69.0% |
| RB | 74 | 14.1% | 75.0% | 86.5% | 160.0% |
| WR | 96 | 14.1% | 56.5% | 75.9% | 199.4% |
| TE | 37 | 11.3% | 53.3% | 64.5% | 96.1% |

## Sensitivity grid

Each row changes only the displayed provider/history weights relative to the Phase-1 reference. These are **not calibrated recommendations**.

| FP weight | History weight | Median abs FV move | P95 abs FV move |
|---:|---:|---:|---:|
| 0% | 25% | 3.7% | 31.1% |
| 0% | 45% | 0.0% | 13.5% |
| 0% | 65% | 4.0% | 41.8% |
| 25% | 25% | 3.5% | 28.0% |
| 25% | 45% | 0.0% | 6.8% |
| 25% | 65% | 4.0% | 42.2% |
| 50% | 25% | 3.7% | 23.2% |
| 50% | 45% | 0.0% | 0.0% |
| 50% | 65% | 4.1% | 43.4% |
| 75% | 25% | 3.6% | 23.0% |
| 75% | 45% | 0.0% | 7.2% |
| 75% | 65% | 3.7% | 42.4% |
| 100% | 25% | 3.5% | 26.1% |
| 100% | 45% | 0.2% | 15.5% |
| 100% | 65% | 4.0% | 41.8% |

## What this does NOT prove

- It does not identify the best FantasyPros/Sleeper blend.
- It does not identify the best history/forward weight.
- It does not authorize changing `PROD_MULT`.
- It does not use future information or market value to train Fundamental Value.

## Prospective Phase 2B

After real 2026 games exist, score the frozen preseason provider projections and later pre-week snapshots against realized league-scored production. Only then may provider/history weights be estimated from out-of-sample evidence.

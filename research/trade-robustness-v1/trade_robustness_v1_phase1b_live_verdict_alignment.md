# Trade Robustness V1 Phase 1B — Live Verdict Alignment

**Decision:** `PASS_TRADE_ROBUSTNESS_V1_PHASE1B_LIVE_VERDICT_ALIGNMENT`

**RESEARCH ONLY. No calculator behavior changed.**

## Why Phase 1B exists

Phase 1 correctly exercised the live package-adjustment math, but it called every nonzero delta a winner. The production calculator instead calls differences below 7% `Fair Trade`. Phase 1B uses the existing production thresholds without refitting them.

## Universe

- Total synthetic real-roster cases: **28776**
- Center verdict already Fair Trade: **4101**
- Directional center verdicts evaluated: **24675**

## Directional verdict survival

- **Sensitivity Robust:** 4791 (19.4%)
- **Fragile → Fair Trade:** 2847 (11.5%)
- **Fragile → Opposite side favored:** 17037 (69.0%)
- Exact Slight/Strong label unchanged: 3287 (13.3%)

## By trade structure

| Structure | Cases | Center fair | Directional | Robust | → Fair | Flipped |
|---|---:|---:|---:|---:|---:|---:|
| 1v1 | 6600 | 1479 | 5121 | 336 | 635 | 4150 |
| 1v2 | 11088 | 1552 | 9536 | 2031 | 950 | 6555 |
| 2v1 | 11088 | 1070 | 10018 | 2424 | 1262 | 6332 |

## By center verdict margin

| Margin | Directional | Robust | → Fair | Flipped |
|---|---:|---:|---:|---:|
| 10_to_20pct | 4805 | 107 | 54 | 4644 |
| 20_to_30pct | 2875 | 67 | 218 | 2590 |
| 30_to_50pct | 5649 | 894 | 764 | 3991 |
| 50pct_plus | 9648 | 3688 | 1775 | 4185 |
| 7_to_10pct | 1698 | 35 | 36 | 1627 |

## UI rule if promoted

- Fair Trade center verdict: no directional robustness badge.
- Directional verdict survives adverse corner at ≥7%: `Sensitivity Robust`.
- Directional verdict falls into Fair Trade or flips: `Sensitivity Fragile`.
- No probability/confidence percentage.

## Guardrails

- Fundamental Value unchanged.
- Value Uncertainty unchanged.
- Package Adjustment unchanged.
- Trade Verdict unchanged.
- Market Value V2 unchanged.
- Team Utility unchanged.

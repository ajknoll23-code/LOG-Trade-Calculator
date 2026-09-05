# Replacement Level / Positional Scale V2 — Phase 3 Current-Board Shadow Audit

**Research only. No deployment or frozen prospective experiment is changed.**

Method: `replacement-level-v2-phase3-current-board-shadow-v2`

## Isolation

- Legacy-rank reconstruction reproduces Production V2 Phase 1 exactly: **Yes**
- Maximum fundamental-value reproduction delta: **0**
- RB fractional-age reference date frozen to Phase 1: **2026-09-03**
- `index.html` SHA matches the Phase 1 recorded input: **Yes**
- Every scenario changes **one position's replacement rank only**.

## Summary

| Pos | Legacy | Phase-2 leader | Phase-3 shortlist | Board-safe recommendation | Leader safety | Median FV Δ | P90 abs FV Δ | Global ρ | Top100 overlap | Top100 share Δ |
|---|---:|---:|---|---:|---|---:|---:|---:|---:|---:|
| QB | 18 | 29 | 18, 29, 34 | 29 | PASS | +29.2% | +33.6% | 0.9947 | +96.0% | +4.0% |
| RB | 32 | 25 | 25, 26, 32 | 25 | PASS | -20.1% | +25.2% | 0.9890 | +93.0% | -7.0% |
| WR | 36 | 28 | 28, 34, 36 | 28 | PASS | -7.9% | +9.2% | 0.9979 | +95.0% | -5.0% |
| TE | 15 | 11 | 10, 11, 15, 16 | 11 | PASS | -14.5% | +17.5% | 0.9972 | +99.0% | -1.0% |
| DL | 32 | 16 | 16, 23, 32 | 16 | PASS | -12.6% | +14.8% | 0.9942 | +95.0% | -5.0% |
| LB | 32 | 28 | 28, 32 | 28 | PASS | -3.9% | +4.9% | 0.9995 | +98.0% | -2.0% |
| DB | 32 | 22 | 22, 30, 32 | 22 | PASS | -3.2% | +3.6% | 0.9996 | +99.0% | -1.0% |

## Scenario detail

### QB

- Legacy control: **18**
- Phase-2 historical leader: **29**
- Board-safe recommendation for Phase 4: **29**

| Rank | Hist MAE | Hist Δ vs legacy | Baseline pts Δ | Median FV Δ | P90 abs FV Δ | P95 abs FV Δ | Global ρ | Top50 overlap | Top100 overlap | Top100 pos-share Δ | Safety |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 18 | 0.5574 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | 1.0000 | +100.0% | +100.0% | +0.0% | PASS |
| 29 | 0.4887 | -12.3% | -20.5% | +29.2% | +33.6% | +35.8% | 0.9947 | +76.0% | +96.0% | +4.0% | PASS |
| 34 | 0.5026 | -9.8% | -67.7% | +150.2% | +264.4% | +304.4% | 0.9244 | +60.0% | +89.0% | +11.0% | FAIL |

### RB

- Legacy control: **32**
- Phase-2 historical leader: **25**
- Board-safe recommendation for Phase 4: **25**

| Rank | Hist MAE | Hist Δ vs legacy | Baseline pts Δ | Median FV Δ | P90 abs FV Δ | P95 abs FV Δ | Global ρ | Top50 overlap | Top100 overlap | Top100 pos-share Δ | Safety |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 25 | 0.2295 | -17.3% | +21.7% | -20.1% | +25.2% | +25.6% | 0.9890 | +88.0% | +93.0% | -7.0% | PASS |
| 26 | 0.2391 | -13.8% | +21.1% | -19.7% | +24.7% | +25.1% | 0.9896 | +90.0% | +93.0% | -7.0% | PASS |
| 32 | 0.2774 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | 1.0000 | +100.0% | +100.0% | +0.0% | PASS |

### WR

- Legacy control: **36**
- Phase-2 historical leader: **28**
- Board-safe recommendation for Phase 4: **28**

| Rank | Hist MAE | Hist Δ vs legacy | Baseline pts Δ | Median FV Δ | P90 abs FV Δ | P95 abs FV Δ | Global ρ | Top50 overlap | Top100 overlap | Top100 pos-share Δ | Safety |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 28 | 0.2304 | -7.3% | +6.9% | -7.9% | +9.2% | +9.4% | 0.9979 | +98.0% | +95.0% | -5.0% | PASS |
| 34 | 0.2443 | -1.7% | +0.9% | -1.1% | +1.3% | +1.3% | 0.9999 | +100.0% | +99.0% | -1.0% | PASS |
| 36 | 0.2485 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | 1.0000 | +100.0% | +100.0% | +0.0% | PASS |

### TE

- Legacy control: **15**
- Phase-2 historical leader: **11**
- Board-safe recommendation for Phase 4: **11**

| Rank | Hist MAE | Hist Δ vs legacy | Baseline pts Δ | Median FV Δ | P90 abs FV Δ | P95 abs FV Δ | Global ρ | Top50 overlap | Top100 overlap | Top100 pos-share Δ | Safety |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 10 | 0.2149 | -2.9% | +14.0% | -15.0% | +18.2% | +18.8% | 0.9969 | +98.0% | +99.0% | -1.0% | PASS |
| 11 | 0.2148 | -2.9% | +13.4% | -14.5% | +17.5% | +18.2% | 0.9972 | +98.0% | +99.0% | -1.0% | PASS |
| 15 | 0.2213 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | 1.0000 | +100.0% | +100.0% | +0.0% | PASS |
| 16 | 0.2221 | +0.4% | -2.7% | +3.5% | +4.3% | +4.4% | 0.9998 | +100.0% | +99.0% | +1.0% | PASS |

### DL

- Legacy control: **32**
- Phase-2 historical leader: **16**
- Board-safe recommendation for Phase 4: **16**

| Rank | Hist MAE | Hist Δ vs legacy | Baseline pts Δ | Median FV Δ | P90 abs FV Δ | P95 abs FV Δ | Global ρ | Top50 overlap | Top100 overlap | Top100 pos-share Δ | Safety |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 16 | 0.1937 | -24.1% | +12.0% | -12.6% | +14.8% | +15.5% | 0.9942 | +98.0% | +95.0% | -5.0% | PASS |
| 23 | 0.2280 | -10.6% | +3.6% | -4.1% | +4.9% | +5.2% | 0.9994 | +100.0% | +99.0% | -1.0% | PASS |
| 32 | 0.2551 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | 1.0000 | +100.0% | +100.0% | +0.0% | PASS |

### LB

- Legacy control: **32**
- Phase-2 historical leader: **28**
- Board-safe recommendation for Phase 4: **28**

| Rank | Hist MAE | Hist Δ vs legacy | Baseline pts Δ | Median FV Δ | P90 abs FV Δ | P95 abs FV Δ | Global ρ | Top50 overlap | Top100 overlap | Top100 pos-share Δ | Safety |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 28 | 0.1883 | -2.7% | +3.4% | -3.9% | +4.9% | +4.9% | 0.9995 | +98.0% | +98.0% | -2.0% | PASS |
| 32 | 0.1936 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | 1.0000 | +100.0% | +100.0% | +0.0% | PASS |

### DB

- Legacy control: **32**
- Phase-2 historical leader: **22**
- Board-safe recommendation for Phase 4: **22**

| Rank | Hist MAE | Hist Δ vs legacy | Baseline pts Δ | Median FV Δ | P90 abs FV Δ | P95 abs FV Δ | Global ρ | Top50 overlap | Top100 overlap | Top100 pos-share Δ | Safety |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 22 | 0.2080 | -6.6% | +2.9% | -3.2% | +3.6% | +3.6% | 0.9996 | +100.0% | +99.0% | -1.0% | PASS |
| 30 | 0.2219 | -0.4% | +0.3% | -0.4% | +0.4% | +0.4% | 1.0000 | +100.0% | +100.0% | +0.0% | PASS |
| 32 | 0.2228 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | 1.0000 | +100.0% | +100.0% | +0.0% | PASS |

## Safety gates

- median absolute target-position FV change ≤ **30%**
- P90 absolute target-position FV change ≤ **40%**
- global Spearman rank correlation ≥ **0.97**
- global top-100 overlap ≥ **90%**
- absolute target-position top-100 share change ≤ **10 percentage points**

These are broad damage-control gates, not evidence that a candidate is calibrated.

## Guardrails

- deployment_authorized: **false**
- production_v2_change_authorized: **false**
- replacement_rank_change_authorized: **false**
- position_weight_change_authorized: **false**
- transform_change_authorized: **false**
- scale_change_authorized: **false**
- frozen prospective experiments touched: **false**

## Next step

Phase 4 will carry only historically supported, board-safe replacement ranks into a separate PM-transform/global-scale audit. POSITION_WEIGHT remains fixed so replacement normalization and positional economics stay identifiable.

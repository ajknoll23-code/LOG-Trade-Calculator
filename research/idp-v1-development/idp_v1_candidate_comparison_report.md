# IDP V1 Candidate Comparison Through Final Trade Desk Values

## Purpose

All candidates are passed through the **actual current `snapshot_values.py` port of `index.html`** for valuation logic, while the OLD side is anchored to the immutable pre-V1 `PROD_MULT_DATA` snapshot. This keeps the comparison reproducible even after V1 is deployed.

## Final value movement by position

### full_canonical

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 79 | -1.4% | +16.5% | +34.9% | -25.2% | +67.2% |
| DL | 86 | +6.4% | +25.6% | +67.9% | -35.3% | +141.5% |
| DB | 65 | -0.9% | +14.0% | +18.2% | -8.7% | +138.2% |

### isolated_normalized

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 79 | -8.6% | -0.8% | +0.0% | -31.8% | +14.1% |
| DL | 86 | +1.0% | +9.6% | +10.8% | -11.9% | +19.4% |
| DB | 65 | -0.8% | +2.1% | +3.9% | -8.3% | +45.5% |

### strict_projection_only

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 79 | +2.5% | +6.1% | +6.6% | -31.1% | +31.1% |
| DL | 86 | +7.8% | +13.5% | +14.9% | -7.9% | +23.9% |
| DB | 65 | +4.3% | +7.3% | +9.2% | -3.4% | +54.5% |

### model_delta_transport

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 79 | -0.5% | +1.7% | +2.5% | -6.5% | +23.9% |
| DL | 86 | +3.3% | +7.3% | +8.2% | -12.6% | +13.4% |
| DB | 65 | +0.2% | +3.1% | +5.2% | -7.1% | +44.5% |

## Top-rank stability

| Candidate | Pos | Top-24 movers >=5 ranks | Top-36 movers >=5 ranks | Max abs move among top-36 |
|---|---|---:|---:|---:|
| full_canonical | LB | 2 | 2 | 12 |
| full_canonical | DL | 23 | 31 | 57 |
| full_canonical | DB | 1 | 7 | 21 |
| isolated_normalized | LB | 1 | 3 | 6 |
| isolated_normalized | DL | 10 | 15 | 12 |
| isolated_normalized | DB | 0 | 1 | 5 |
| strict_projection_only | LB | 1 | 2 | 5 |
| strict_projection_only | DL | 5 | 8 | 8 |
| strict_projection_only | DB | 0 | 1 | 5 |
| model_delta_transport | LB | 1 | 1 | 5 |
| model_delta_transport | DL | 4 | 7 | 8 |
| model_delta_transport | DB | 1 | 2 | 5 |

## Known anchors — final Trade Desk value

| Candidate | Player | Pos | Old | New | Change | Old rank | New rank |
|---|---|---|---:|---:|---:|---:|---:|
| full_canonical | aidan hutchinson | DL | 5084 | 5684 | +11.8% | 4 | 3 |
| full_canonical | myles garrett | DL | 5345 | 5974 | +11.8% | 2 | 1 |
| full_canonical | fred warner | LB | 4762 | 4698 | -1.3% | 8 | 10 |
| full_canonical | roquan smith | LB | 4780 | 4698 | -1.7% | 6 | 11 |
| isolated_normalized | aidan hutchinson | DL | 5084 | 5488 | +7.9% | 4 | 3 |
| isolated_normalized | myles garrett | DL | 5345 | 5747 | +7.5% | 2 | 1 |
| isolated_normalized | fred warner | LB | 4762 | 4388 | -7.9% | 8 | 8 |
| isolated_normalized | roquan smith | LB | 4780 | 4366 | -8.7% | 6 | 11 |
| strict_projection_only | aidan hutchinson | DL | 5084 | 5672 | +11.6% | 4 | 4 |
| strict_projection_only | myles garrett | DL | 5345 | 5938 | +11.1% | 2 | 1 |
| strict_projection_only | fred warner | LB | 4762 | 4924 | +3.4% | 8 | 8 |
| strict_projection_only | roquan smith | LB | 4780 | 4899 | +2.5% | 6 | 11 |
| model_delta_transport | aidan hutchinson | DL | 5084 | 5401 | +6.2% | 4 | 4 |
| model_delta_transport | myles garrett | DL | 5345 | 5655 | +5.8% | 2 | 1 |
| model_delta_transport | fred warner | LB | 4762 | 4743 | -0.4% | 8 | 8 |
| model_delta_transport | roquan smith | LB | 4780 | 4718 | -1.3% | 6 | 11 |

## Largest final-value movers by candidate

### full_canonical

| Player | Pos | Old value | New value | Change | Rank move | Cohort/status |
|---|---|---:|---:|---:|---:|---|
| kayvon thibodeaux | DL | 1115 | 2693 | +141.5% | -35 | both/computed |
| aj haulcy | DB | 796 | 1896 | +138.2% | -3 | both/computed |
| jonathan greenard | DL | 1770 | 3767 | +112.8% | -57 | both/computed |
| peter woods | DL | 866 | 1576 | +82.0% | -6 | both/computed |
| dangelo ponds | DB | 688 | 1218 | +77.0% | -1 | both/computed |
| kayden mcdonald | DL | 643 | 1131 | +75.9% | -2 | sleeper_only/computed |
| keldric faulk | DL | 915 | 1559 | +70.4% | -4 | both/computed |
| jacob rodriguez | LB | 1358 | 2271 | +67.2% | -10 | both/computed |
| r mason thomas | DL | 1113 | 1787 | +60.6% | -5 | both/computed |
| zion young | DL | 1162 | 1768 | +52.2% | -2 | fp_only/computed |
| cashius howell | DL | 965 | 1424 | +47.6% | +1 | sleeper_only/computed |
| josiah trotter | LB | 943 | 1362 | +44.4% | -8 | both/computed |
| anthony hill | LB | 951 | 1320 | +38.8% | -5 | sleeper_only/computed |
| jake golday | LB | 1162 | 1587 | +36.6% | -6 | both/computed |
| jermaine johnson | DL | 2220 | 1436 | -35.3% | +20 | sleeper_only/computed |

### isolated_normalized

| Player | Pos | Old value | New value | Change | Rank move | Cohort/status |
|---|---|---:|---:|---:|---:|---|
| aj haulcy | DB | 796 | 1158 | +45.5% | -1 | both/projection_delta_applied |
| jaishawn barham | LB | 968 | 660 | -31.8% | +5 | both/projection_delta_applied |
| jake golday | LB | 1162 | 886 | -23.8% | +2 | both/projection_delta_applied |
| jonathan greenard | DL | 1770 | 2113 | +19.4% | -13 | both/projection_delta_applied |
| anthony hill | LB | 951 | 809 | -14.9% | +0 | sleeper_only/projection_delta_applied |
| jacob rodriguez | LB | 1358 | 1549 | +14.1% | -3 | both/projection_delta_applied |
| kayvon thibodeaux | DL | 1115 | 1268 | +13.7% | -1 | both/projection_delta_applied |
| james pearce | LB | 1892 | 1642 | -13.2% | +0 | sleeper_only/projection_delta_applied |
| micah mcfadden | LB | 1749 | 1530 | -12.5% | +1 | fp_only/projection_delta_applied |
| danny stutsman | LB | 1638 | 1437 | -12.3% | +1 | fp_only/projection_delta_applied |
| zach allen | DL | 3708 | 4163 | +12.3% | -8 | both/projection_delta_applied |
| jermaine johnson | DL | 2220 | 1955 | -11.9% | +10 | sleeper_only/projection_delta_applied |
| tyrel dodson | LB | 4509 | 3971 | -11.9% | +2 | both/projection_delta_applied |
| nolan smith | DL | 2230 | 1965 | -11.9% | +11 | sleeper_only/projection_delta_applied |
| haason reddick | DL | 1969 | 1737 | -11.8% | +6 | no_new_data/no_new_data_projection_hold |

### strict_projection_only

| Player | Pos | Old value | New value | Change | Rank move | Cohort/status |
|---|---|---:|---:|---:|---:|---|
| aj haulcy | DB | 796 | 1230 | +54.5% | -1 | both/projection_delta_applied |
| jacob rodriguez | LB | 1358 | 1780 | +31.1% | -3 | both/projection_delta_applied |
| bryce boettcher | LB | 1355 | 934 | -31.1% | +5 | fp_only/projection_delta_applied |
| kaleb elarmsorr | LB | 968 | 709 | -26.8% | +4 | both/projection_delta_applied |
| jonathan greenard | DL | 1770 | 2193 | +23.9% | -10 | both/projection_delta_applied |
| kyle louis | LB | 968 | 745 | -23.0% | +2 | fp_only/projection_delta_applied |
| jaishawn barham | LB | 968 | 783 | -19.1% | +2 | both/projection_delta_applied |
| kayvon thibodeaux | DL | 1115 | 1322 | +18.6% | -1 | both/projection_delta_applied |
| will johnson | DB | 2259 | 2636 | +16.7% | -10 | both/projection_delta_applied |
| zach allen | DL | 3708 | 4306 | +16.1% | -6 | both/projection_delta_applied |
| chris jones | DL | 2357 | 2714 | +15.1% | -6 | both/projection_delta_applied |
| r mason thomas | DL | 1113 | 1280 | +15.0% | -1 | both/projection_delta_applied |
| trey hendrickson | DL | 2776 | 3185 | +14.7% | -1 | both/projection_delta_applied |
| donovan ezeiruaku | DL | 2208 | 2531 | +14.6% | -7 | both/projection_delta_applied |
| greg rousseau | DL | 3335 | 3798 | +13.9% | -5 | both/projection_delta_applied |

### model_delta_transport

| Player | Pos | Old value | New value | Change | Rank move | Cohort/status |
|---|---|---:|---:|---:|---:|---|
| aj haulcy | DB | 796 | 1150 | +44.5% | -1 | both/model_delta_transported |
| jacob rodriguez | LB | 1358 | 1682 | +23.9% | -2 | both/model_delta_transported |
| jonathan greenard | DL | 1770 | 2007 | +13.4% | -7 | both/model_delta_transported |
| jadeveon clowney | DL | 2293 | 2003 | -12.6% | +10 | fp_only/model_delta_transported |
| will johnson | DB | 2259 | 2535 | +12.2% | -10 | both/model_delta_transported |
| zach allen | DL | 3708 | 4096 | +10.5% | -6 | both/model_delta_transported |
| zion young | DL | 1162 | 1044 | -10.2% | +3 | fp_only/model_delta_transported |
| chris jones | DL | 2357 | 2579 | +9.4% | -5 | both/model_delta_transported |
| trey hendrickson | DL | 2776 | 3029 | +9.1% | -1 | both/model_delta_transported |
| greg rousseau | DL | 3335 | 3610 | +8.2% | -5 | both/model_delta_transported |
| donovan ezeiruaku | DL | 2208 | 2386 | +8.1% | -6 | both/model_delta_transported |
| derick hall | DL | 2215 | 2037 | -8.0% | +2 | fp_only/model_delta_transported |
| josh hinesallen | DL | 3678 | 3968 | +7.9% | -2 | both/model_delta_transported |
| boye mafe | DL | 2588 | 2789 | +7.8% | -3 | both/model_delta_transported |
| abdul carter | DL | 2749 | 2956 | +7.5% | -1 | both/model_delta_transported |

## Engineering conclusion

- **Full canonical** answers: “What would the model say if we regenerated the entire current history + projection lineage today?” It is the clean long-term architecture but mixes historical lineage cleanup into V1.
- **Isolated normalized** answers: “What if we anchor to live values, apply V1 projection deltas, then immediately force the table back through rank-32 normalization?” This still moves no-change players because the old baked table is not internally rank-32 normalized.
- **Strict projection-only** answers: “What does the direct projection-point delta do if baseline movement is deferred entirely?”
- **Model-delta transport** computes old and V1 models on one reproducible comparable cohort, includes the V1 model’s legitimate rank-32 baseline movement there, and transports only that model delta onto the actual live table. This is the cleanest bridge between reproducibility and release attribution.

**Recommendation:** use `model_delta_transport` as the production-oriented V1 candidate. It nearly reproduces the shape of the earlier validated sensitivity study without importing the stale old model’s absolute level or silently re-normalizing the historical live table.

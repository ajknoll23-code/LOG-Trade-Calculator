# Free Agent Utility V1 — Phase 4 Exact Production-Candidate Shadow

Status: **PASS_PHASE4_EXACT_PRODUCTION_CANDIDATE_SHADOW**

No production file or live board behavior changed.

## Frozen candidate

- 4for4 cohort-relative transport: **15%**
- Absolute score-shift cap: **±0.040**
- ALL section: **existing LOG value order unchanged**
- Position sections: **derived priority rank**
- Candidate artifact rows: **408**
- Candidate artifact row fields: `player_id`, `pos`, `priority_rank` only

## Exact reproduction

- Matched free agents: **304**
- Capped matches: **118**
- 3+ spot moves: **72**
- 5+ spot moves: **11**
- Median absolute matched move: **1.0**
- P95 absolute matched move: **4.0**

## Position-section behavior

| Pos | Cohort | Match | Spearman | >=3 | >=5 | Top-5 | Top-10 | P95 move | Max move |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QB | 15 | 11 | 0.8571 | 3 | 1 | 80% | 90% | 5.0 | 6.0 |
| RB | 40 | 21 | 0.9931 | 1 | 1 | 100% | 90% | 2.0 | 7.0 |
| WR | 93 | 55 | 0.9958 | 19 | 4 | 80% | 90% | 5.0 | 10.0 |
| TE | 75 | 53 | 0.9975 | 9 | 0 | 80% | 100% | 3.0 | 3.0 |
| DL | 60 | 55 | 0.9961 | 4 | 0 | 100% | 90% | 3.0 | 4.0 |
| LB | 25 | 21 | 0.9977 | 0 | 0 | 100% | 100% | 1.0 | 1.0 |
| DB | 100 | 88 | 0.9964 | 36 | 5 | 80% | 90% | 4.6 | 5.0 |

## Privacy / architecture

- The simulated production artifact contains no raw 4for4 rows.
- It contains no 4for4 projections, ranks, percentiles, or player-level deltas.
- It contains no player-level utility score; only the final bounded within-position priority rank.
- Fundamental Value and Free-Agent Production V2 remain untouched.
- No cross-position ordering is derived from the utility percentile.
- This phase does not authorize production deployment.

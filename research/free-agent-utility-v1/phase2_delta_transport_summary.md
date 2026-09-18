# Free Agent Utility V1 — Phase 2 Cohort-Relative Delta Transport

Status: **PASS_PHASE2_COHORT_RELATIVE_DELTA_TRANSPORT**

Research-only. No production file or live ranking changed.

## Why Phase 2 exists

Phase 1 mixed a free-agent-relative LOG percentile with a full-player-pool 4for4 percentile. Phase 2 removes that level mismatch and transports only the relative ordering disagreement among the exact same matched free agents.

## Frozen primary transport

- 4for4 disagreement transport strength: **25%**
- Data-backed FA cohort: **408**
- Exact 4for4 matches: **304** (74.5%)
- 3+ spot matched moves: **184**
- 5+ spot matched moves: **117**
- Clipped scores: **0**

## Position diagnostics

| Pos | Cohort | Match | Coverage | Delta mean | Spearman | >=3 | >=5 | Top-5 | Top-10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QB | 15 | 11 | 73.3% | -0.000000 | 0.8464 | 3 | 1 | 80% | 90% |
| RB | 40 | 21 | 52.5% | -0.000000 | 0.9848 | 8 | 1 | 80% | 80% |
| WR | 93 | 55 | 59.1% | -0.000000 | 0.9787 | 37 | 29 | 60% | 70% |
| TE | 75 | 53 | 70.7% | -0.000000 | 0.9754 | 36 | 21 | 80% | 100% |
| DL | 60 | 55 | 91.7% | -0.000000 | 0.9715 | 31 | 17 | 60% | 90% |
| LB | 25 | 21 | 84.0% | 0.000000 | 0.9715 | 3 | 0 | 100% | 100% |
| DB | 100 | 88 | 88.0% | 0.000000 | 0.9735 | 66 | 48 | 40% | 70% |

## Guards

- Unmatched player scores are unchanged.
- No raw 4for4 row is persisted.
- No player-level 4for4 projection, percentile, rank, delta, or utility score is persisted.
- Fundamental Value is untouched.
- Free-Agent Production V2 is untouched.
- free-agent-board.html is untouched.
- This phase does not authorize production deployment.

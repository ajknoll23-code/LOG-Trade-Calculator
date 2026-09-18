# Free Agent Utility V1 — Phase 1 Private 4for4 Shadow

Status: **PASS_PHASE1_PRIVATE_SHADOW_COMPLETE**

Research-only. No production file or ranking was changed.

## Frozen primary shadow

- 4for4 weight: **25%**
- Current LOG weight: **75%**
- Data-backed free-agent cohort: **408**
- Matched to private 4for4 source: **304** (74.5%)
- Unmatched fallback: exact existing LOG signal

## Position diagnostics

| Pos | Cohort | Matched | Coverage | Spearman | >=3 moves | >=5 moves |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QB | 15 | 11 | 73.3% | 0.8821 | 3 | 0 |
| RB | 40 | 21 | 52.5% | 0.9745 | 6 | 3 |
| WR | 93 | 55 | 59.1% | 0.9829 | 32 | 23 |
| TE | 75 | 53 | 70.7% | 0.9863 | 29 | 11 |
| DL | 60 | 55 | 91.7% | 0.9810 | 22 | 14 |
| LB | 25 | 21 | 84.0% | 0.9877 | 1 | 0 |
| DB | 100 | 88 | 88.0% | 0.9864 | 56 | 32 |

## Privacy / production guards

- No raw 4for4 row is written to the repository.
- No player-level 4for4 projection, percentile, rank, or utility score is persisted.
- Fundamental Value is untouched.
- Free-Agent Production V2 is untouched.
- The live Free Agent Board is untouched.
- This phase does not authorize production deployment.

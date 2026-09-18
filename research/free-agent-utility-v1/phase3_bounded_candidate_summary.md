# Free Agent Utility V1 — Phase 3 Bounded Candidate Selection

Status: **PASS_PHASE3_BOUNDED_CANDIDATE_SELECTED**

Research-only. No production file or live ranking changed.

Phase 3 fixes transport strength at 15% and selects the largest absolute score-shift cap that passes every preregistered safety gate.

## Selected candidate

- Transport strength: **15%**
- Absolute score-shift cap: **±0.040**
- Matched free agents: **304**
- Capped matches: **118**
- 3+ spot moves: **72**
- 5+ spot moves: **11**

## Candidate comparison

| Cap | Pass | Capped | >=3 moves | >=5 moves | Median abs move | P95 abs move |
| ---: | :---: | ---: | ---: | ---: | ---: | ---: |
| ±0.040 | YES | 118 | 72 | 11 | 1.0 | 4.0 |
| ±0.060 | NO | 69 | 116 | 34 | 2.0 | 6.0 |
| ±0.080 | NO | 24 | 123 | 45 | 2.0 | 6.8 |

## Selected candidate by position

| Pos | Match | Spearman | >=3 | >=5 | Top-5 | Top-10 | P95 move | Max move |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QB | 11 | 0.8571 | 3 | 1 | 80% | 90% | 5.0 | 6.0 |
| RB | 21 | 0.9931 | 1 | 1 | 100% | 90% | 2.0 | 7.0 |
| WR | 55 | 0.9958 | 19 | 4 | 80% | 90% | 5.0 | 10.0 |
| TE | 53 | 0.9975 | 9 | 0 | 80% | 100% | 3.0 | 3.0 |
| DL | 55 | 0.9961 | 4 | 0 | 100% | 90% | 3.0 | 4.0 |
| LB | 21 | 0.9977 | 0 | 0 | 100% | 100% | 1.0 | 1.0 |
| DB | 88 | 0.9964 | 36 | 5 | 80% | 90% | 4.6 | 5.0 |

## Guards

- Unmatched player scores remain exact LOG scores.
- No raw 4for4 rows are persisted.
- No player-level projection/rank/delta/utility score is persisted.
- Fundamental Value and Free-Agent Production V2 remain frozen.
- free-agent-board.html remains unchanged.
- Phase 3 does not authorize production deployment.

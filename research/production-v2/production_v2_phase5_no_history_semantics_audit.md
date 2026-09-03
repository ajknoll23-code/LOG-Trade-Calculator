# Production V2 — Phase 5 No-History Semantics Audit

## Decision

**CARRY_DATA_FIRST_NO_HISTORY_SEMANTICS_FORWARD_FOR_V2_CANDIDATE_COHORT**

- Production files mutated: **0**
- Complete V2 candidate cohort: **518**
- Players without a complete V2 candidate: **31** — fallback policy intentionally not changed here

## Invariant result

- Current rule raw-PM↓ / effective-PM↑ violations: **2**
- Data-first candidate semantics violations: **0**
- Data-first monotonicity: **PASS**

### Semantics

**Current:** a no-history non-Elite player can switch into `ROLE_MULT` when raw PM reaches 0.15.

**V2 candidate tested:** once a valid V2 production estimate exists, use that production estimate directly for non-Elite players. `ROLE_MULT` is not triggered by the numeric floor. The existing Elite 0.65 safeguard is held fixed.

## Impact by position

| Pos | Candidates | Current rescues doc→hybrid | Data-first rescues | Semantic FV change @ doc rank (median / P95 abs) | Hybrid-vs-doc FV under data-first (median / P95 abs) |
|---|---:|---|---:|---|---|
| QB | 54 | 7→7 | 0 | +0.0% / 33.0% | +0.0% / 0.0% |
| RB | 93 | 0→2 | 0 | +0.0% / 0.0% | -19.7% / 25.1% |
| WR | 108 | 0→0 | 0 | +0.0% / 0.0% | -1.1% / 1.3% |
| TE | 43 | 0→0 | 0 | +0.0% / 0.0% | +0.0% / 0.0% |
| DL | 83 | 0→0 | 0 | +0.0% / 0.0% | -4.1% / 5.2% |
| LB | 74 | 0→0 | 0 | +0.0% / 0.0% | +0.0% / 0.0% |
| DB | 63 | 0→0 | 0 | +0.0% / 0.0% | -0.4% / 0.4% |

## Players changed by removing threshold rescue at documented ranks

| Player | Pos | Role | Raw PM | Current effective | Data-first effective | Current FV | Data-first FV | FV change |
|---|---|---|---:|---:|---:|---:|---:|---:|
| cade klubnik | QB | Speculative | 0.150 | 0.220 | 0.150 | 1034 | 686 | -33.7% |
| drew allar | QB | Speculative | 0.150 | 0.220 | 0.150 | 1034 | 686 | -33.7% |
| cole payton | QB | Speculative | 0.150 | 0.220 | 0.150 | 1169 | 783 | -33.0% |
| ty simpson | QB | Speculative | 0.150 | 0.220 | 0.150 | 1169 | 783 | -33.0% |
| carson beck | QB | Speculative | 0.150 | 0.220 | 0.150 | 1303 | 879 | -32.5% |
| will howard | QB | Speculative | 0.150 | 0.220 | 0.150 | 1303 | 879 | -32.5% |
| tommy devito | QB | Speculative | 0.150 | 0.220 | 0.150 | 1573 | 1073 | -31.8% |

## Interpretation

For players with a complete V2 production candidate, ROLE_MULT should not be activated by an arbitrary numeric PM threshold. Separating 'production estimate exists' from 'production estimate missing' removes the direction-reversing discontinuity while leaving the Elite safeguard and every other valuation layer untouched.

This is an architecture decision for the V2 **candidate-present** state, not a claim that the underlying raw production estimate is calibrated yet.

The 31 incomplete-candidate players are deliberately left for a separate missing-data fallback audit rather than being silently pushed into a new role-based rule.

## Next step

Rerun/interpret the replacement-baseline comparison under the data-first candidate semantics. If the hybrid ranks remain defensible, audit the remaining affine transform floor/ceiling shape next. Missing-candidate fallback policy remains a separate task.

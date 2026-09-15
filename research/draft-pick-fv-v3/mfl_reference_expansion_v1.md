# Draft Pick FV V3 — MFL Reference Expansion Audit

**Recommendation:** `ACCEPT_ROOKIE_POOL_AS_HISTORICAL_DYNASTY_PROXY`

This audit reads MFL league metadata only. It does **not** read draft results, player outcomes, KTC/market data, package votes, or candidate model scores.

## Frozen expansion design

- Reference years: **2020–2023**
- Original deterministic sample: **150 candidates/year**
- Expansion: **up to 300 additional candidates/year** from the live discovery snapshot after the current first 150, with persisted prior 12T-SF IDs excluded
- Search terms, per-term cap, proxy definition, and scientific gates are unchanged.
- Live MFL search-index drift is recorded diagnostically rather than treated as a fatal error.
- No dynasty-targeted enrichment is used.

## Combined proxy evidence

- Prior labeled reference rows: **9**
- New labeled reference rows: **17**
- Combined labeled reference rows: **26** (gate >= 20)
- Explicit dynasty among combined rows: **26** (gate >= 15)
- Point precision: **1.000** (gate >= 0.90)
- Wilson 95% lower bound: **0.871** (gate >= 0.80)

## Expansion by year

| Year | Expansion probed | 12T SF Rookie | Labeled reference | Dynasty | Non-dynasty |
|---:|---:|---:|---:|---:|---:|
| 2020 | 300 | 22 | 0 | 0 | 0 |
| 2021 | 300 | 22 | 4 | 4 | 0 |
| 2022 | 300 | 26 | 4 | 4 | 0 |
| 2023 | 300 | 37 | 9 | 9 | 0 |

## Interpretation guard

A green workflow means the expansion audit executed correctly. The scientific source decision is the recommendation above.

**Next step:** If ACCEPT: rerun MFL draft-source feasibility using the now-validated fallback qualifier explicit keeperType=dynasty OR keeperType missing + Rookie-only draft. If REJECT: do not weaken the dynasty qualifier; add a second draft source. If still INCONCLUSIVE: expand metadata-only evidence again or add an independent metadata source before any draft-result or player-outcome modeling.

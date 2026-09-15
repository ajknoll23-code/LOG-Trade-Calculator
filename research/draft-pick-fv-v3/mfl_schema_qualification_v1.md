# Draft Pick FV V3 — MFL Historical Schema Qualification Audit

**Recommendation:** `INCONCLUSIVE_REFERENCE_SAMPLE`

This audit reads MFL league metadata only. It does **not** read draft results, player outcomes, KTC/market data, package votes, or candidate model scores.

## Frozen proxy test

Primary question: when `keeperType` is missing, can a 12-team superflex league with a Rookie-only draft be treated as a defensible dynasty-source proxy?

- Reference Rookie-only rows: **9**
- Explicit dynasty among them: **9**
- Point precision: **1.000** (gate >= 0.90)
- Wilson 95% lower bound: **0.701** (gate >= 0.80)

## Historical coverage

| Year | Missing keeperType + 12T SF Rookie-only | Name-signal subset |
|---:|---:|---:|
| 2018 | 12 | 6 |
| 2019 | 11 | 8 |

## Per-season metadata

| Year | Probed | 12T SF | Rookie-only | Rookie + keeper missing | Rookie + keeper observed |
|---:|---:|---:|---:|---:|---:|
| 2018 | 150 | 37 | 12 | 12 | 0 |
| 2019 | 150 | 35 | 11 | 11 | 0 |
| 2020 | 150 | 47 | 19 | 18 | 1 |
| 2021 | 150 | 49 | 13 | 9 | 4 |
| 2022 | 150 | 42 | 13 | 10 | 3 |
| 2023 | 150 | 43 | 12 | 11 | 1 |

## Interpretation guard

A green workflow means the schema audit executed correctly. The scientific source decision is the recommendation above.

**Next step:** If ACCEPT: build a separate rerun of MFL feasibility using the frozen fallback qualifier explicit keeperType=dynasty OR keeperType missing + Rookie-only draft, without reading outcomes. If REJECT: add a second draft source rather than weakening the dynasty qualifier. If INCONCLUSIVE or thin: expand metadata discovery only, still without reading player outcomes.

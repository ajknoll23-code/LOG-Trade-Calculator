# Draft Pick FV V2 — Broad Cohort Catalog

**Status:** `INSUFFICIENT_BROAD_COHORT_EVIDENCE`
**Scientific scope:** `STOP_NO_OUTCOME_INGESTION`

The frozen broad source was sanitized before any historical fantasy outcome ingestion. No candidate has been fit or scored.

## Frozen source verification

- Git blob: `94cd1c40cd3b3c266bfc322117bf4756fc2e665d`
- Raw rows: **945**
- Raw columns: **80**
- Raw ECR/performance fields were detected only to prove they were excluded; they are not present in the sanitized cohort.

## Primary feasibility gates

| Gate | Required | Observed | Pass |
|---|---:|---:|:---:|
| distinct_primary_draft_classes | 6 | 3 | FAIL |
| total_primary_players | 216 | 131 | FAIL |
| minimum_players_per_round_tier_cell | 12 | 0 | FAIL |
| identity_resolution_coverage | 0.950 | 1.000 | PASS |
| dob_coverage_for_absolute_bridge | 0.850 | 1.000 | PASS |
| 2qb_adp_coverage_among_candidate_rows | 0.800 | 0.544 | FAIL |

## IDP authorization gates

| Gate | Required | Observed | Pass |
|---|---:|---:|:---:|
| idp_share | 0.100 | 0.000 | FAIL |
| idp_player_count | 36 | 0 | FAIL |

## Coverage

- Candidate rows with any rookie ADP: **241**
- Candidate rows with valid 2QB ADP: **131**
- 2QB ADP coverage: **54.36%**
- Eligible primary rows: **131**
- Identity resolution coverage: **100.00%**
- DOB coverage: **100.00%**
- IDP share: **0.00%** (0 players)

## Draft classes

- Primary years: **2016, 2017, 2018**
- Provisional development: **2016**
- Provisional locked validation: **2017, 2018**

## Round × tier counts

| Cell | N |
|---|---:|
| R1_early | 12 |
| R1_late | 12 |
| R1_mid | 12 |
| R2_early | 12 |
| R2_late | 10 |
| R2_mid | 12 |
| R3_early | 10 |
| R3_late | 11 |
| R3_mid | 11 |
| R4_early | 10 |
| R4_late | 10 |
| R4_mid | 8 |
| R5_early | 1 |
| R5_late | 0 |
| R5_mid | 0 |
| R6_early | 0 |
| R6_late | 0 |
| R6_mid | 0 |

## Guardrail

No historical weekly outcomes, 2026 outcomes, KTC/current market values, package votes, or candidate scores were read or produced.

**Next step:** Do not ingest outcomes; primary feasibility gates failed.

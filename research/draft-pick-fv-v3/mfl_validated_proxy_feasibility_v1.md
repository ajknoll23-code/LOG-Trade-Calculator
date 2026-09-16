# Draft Pick FV V3 — MFL Validated-Proxy Feasibility Audit

**Recommendation:** `DISCOVERY_INCONCLUSIVE_OR_INSUFFICIENT`

This remains pre-preregistration source research. Draft results are read only to measure source depth/completeness. No player outcomes, market/KTC values, package votes, or candidate model scores are read.

## Execution architecture

- Each season was probed in an independent GitHub Actions matrix job and saved as an artifact.
- The six season artifacts were aggregated only after all six completed.
- This execution-only change was made after the monolithic job hit GitHub's 100-minute timeout; scientific rules are unchanged.

## Frozen proxy evidence

- Reference leagues: **26**
- Explicit dynasty: **26**
- Non-dynasty: **0**
- Precision: **1.000**
- Wilson 95% lower bound: **0.871**

## Per-season feasibility

| Year | Probed | Qualified | Explicit | Proxy | Full 4 | Full 6 | Full 6 IDP | League fetch fail | Draft fetch fail |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018 | 590 | 33 | 0 | 33 | 22 | 5 | 2 | 24 | 1 |
| 2019 | 552 | 33 | 0 | 33 | 27 | 7 | 4 | 19 | 0 |
| 2020 | 563 | 49 | 2 | 47 | 36 | 13 | 3 | 0 | 0 |
| 2021 | 564 | 45 | 9 | 36 | 39 | 12 | 4 | 15 | 0 |
| 2022 | 564 | 52 | 10 | 42 | 46 | 17 | 6 | 7 | 1 |
| 2023 | 566 | 56 | 9 | 47 | 47 | 15 | 6 | 7 | 1 |

## Inherited feasibility heuristics

- Full six-round primary: >= 20 complete qualifying drafts in every season.
- Four-round partial: >= 25 complete qualifying drafts in every season.
- Full six-round IDP: >= 5 complete qualifying IDP drafts in every season.

Full-6 years: **[]**
Full-4 years: **[2019, 2020, 2021, 2022, 2023]**
Full-6 IDP years: **[2022, 2023]**

A green workflow means the audit executed correctly. The scientific source decision is the recommendation above.

**Next step:** If recommendation begins GO_MFL, freeze a separate V3 ADP/outcome preregistration before constructing draft-slot estimates or reading player outcomes. If inconclusive, add a second historical draft source rather than weakening the validated MFL qualifier or inherited heuristics.

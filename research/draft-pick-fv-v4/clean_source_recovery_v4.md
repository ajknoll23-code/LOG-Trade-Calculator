# Draft Pick FV V4 — Clean Source Recovery

**Decision:** `STOP_V4_CLEAN_SOURCE_RECOVERY_INSUFFICIENT`

This stage remains completely pre-outcome. Passing source recovery only authorizes a separate V4 catalog/full-preregistration freeze.

## Clean source counts

| Year | R1–R4 | R5 non-IDP | R6 non-IDP | IDP R6 sensitivity |
|---:|---:|---:|---:|---:|
| 2018 | 31 | 17 | 2 | 2 |
| 2019 | 50 | 19 | 4 | 7 |
| 2020 | 59 | 18 | 6 | 5 |
| 2021 | 64 | 9 | 2 | 5 |
| 2022 | 90 | 16 | 6 | 9 |
| 2023 | 84 | 13 | 5 | 5 |
| **Total** | **378** | **92** | **25** | **33** |

## Primary frozen gates

- `r1_r4_nonmock_total`: **378** ≥ **180** — **PASS**
- `r5_nonidp_nonmock_total`: **92** ≥ **60** — **PASS**
- `r6_nonidp_nonmock_total`: **25** ≥ **36** — **FAIL**
- `r6_nonidp_min_per_year`: **2** ≥ **3** — **FAIL**
- `r6_nonidp_hhi_effective_years`: **5.165289256198347** ≥ **4.5** — **PASS**
- `r6_nonidp_max_year_share`: **0.24** ≤ **0.3** — **PASS**

## IDP sensitivity-only gates

- `idp_r6_nonmock_total`: **33** ≥ **20** — **PASS**
- `idp_r6_years_represented`: **6** ≥ **5** — **PASS**

The IDP gates are explicitly nonblocking in the frozen V4 recovery decision rule.

## Recovery diagnostics

- New audited full-R4 candidates: **217**
- New clean full-R4 leagues: **206**
- New positively contaminated leagues: **11**

## Firewall

- Historical player outcomes read: **No**
- Candidate fit performed: **No**
- Locked validation scored: **No**
- Production change authorized: **No**

## Next step

Stop the MFL historical-draft recovery path. Do not ingest outcomes.

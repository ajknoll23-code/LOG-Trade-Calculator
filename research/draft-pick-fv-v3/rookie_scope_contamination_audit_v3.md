# Draft Pick FV V3 — Rookie Scope Contamination Audit

**Decision:** `ROOKIE_SCOPE_CONTAMINATION_CONFIRMED_CLEAN_SUBSET_FAILS_FROZEN_POOLED_GATES`

This is a pre-outcome diagnostic audit. It does not amend the frozen source catalog and cannot authorize historical outcome ingestion.

## Positive contamination evidence

- Frozen catalog leagues: **213**
- Leagues with positive out-of-class evidence: **41**
- Clean-by-evidence leagues: **172**
- Positive contaminated pick occurrences: **1227**

## Clean-subset scope counts

- primary_r1_r4: frozen **213**, contaminated **41**, clean **172**
- primary_r5: frozen **81**, contaminated **29**, clean **52**
- primary_r6: frozen **44**, contaminated **23**, clean **21**
- idp_sensitivity_r5: frozen **37**, contaminated **9**, clean **28**
- idp_sensitivity_r6: frozen **25**, contaminated **9**, clean **16**

## Frozen pooled gate recheck

- r1_r4_nonmock_total: **172** vs threshold **180.0** — **FAIL**
- r5_nonidp_nonmock_total: **52** vs threshold **60.0** — **FAIL**
- r6_nonidp_nonmock_total: **21** vs threshold **36.0** — **FAIL**
- r6_nonidp_min_per_year: **2** vs threshold **3.0** — **FAIL**
- r6_nonidp_hhi_effective_years: **5.313253012048193** vs threshold **4.5** — **PASS**
- r6_nonidp_max_year_share: **0.23809523809523808** vs threshold **0.3** — **PASS**
- idp_r6_nonmock_total: **16** vs threshold **20.0** — **FAIL**
- idp_r6_years_represented: **6** vs threshold **5.0** — **PASS**

Overall clean-subset pooled gate: **FAIL**

## Outcome firewall

- Historical NFL outcomes read: **No**
- Candidate fit performed: **No**
- Locked validation scored: **No**
- Production change authorized: **No**

## Next step

If clean subset passes all frozen pooled gates, freeze a separate pre-outcome protocol clarification that excludes only leagues with positive out-of-class evidence and defines league-scoped custom identity keys; then rerun the unchanged 95% identity gate. If any frozen pooled gate fails, do not ingest outcomes.

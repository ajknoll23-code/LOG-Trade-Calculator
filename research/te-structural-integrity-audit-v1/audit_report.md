# TE Structural Integrity Audit V1

**Decision:** `PASS_TE_STRUCTURAL_AUDIT_FREEZE_REVIEW_REQUIRED_BEFORE_ANY_MODEL_CHANGE`

## Scope

- Live TE count: **44**
- Production V2 Phase 1 TE benchmark coverage: **43/44 (97.7%)**
- Live TE position weight: **0.820000**
- TE age curve: **{'peakStart': 25, 'peakEnd': 29, 'floor': 34}**
- Fractional-age interpolation: **No (RB-only mechanism)**
- Production changes: **None**
- Fitting: **None**

## Hard integrity gates

- minimum_live_te_count: **PASS**
- all_live_te_values_positive: **PASS**
- unique_live_te_keys: **PASS**
- minimum_phase1_te_candidate_coverage_share: **PASS**
- minimum_phase1_current_vs_candidate_spearman: **PASS**
- minimum_phase1_top_n_overlap_share: **PASS**
- age_v2_must_not_authorize_deployment: **PASS**
- position_weight_v2_must_not_authorize_deployment: **PASS**

## Mechanical interpretation

Within TE, position weight is constant. TE-vs-TE spacing therefore comes from production and integer-age mechanics.

- Current TE1: **trey mcbride — 5058 FV**
- TE1 / TE2 FV ratio: **1.231** (TE2: brock bowers — 4109)
- TE1 / TE3 FV ratio: **1.349** (TE3: tucker kraft — 3749)
- TE1 / TE6 FV ratio: **1.488** (TE6: sam laporta — 3400)
- TE1 / TE12 FV ratio: **1.814** (TE12: dallas goedert — 2789)
- TE1 / TE18 FV ratio: **2.061** (TE18: aj barner — 2454)
- TE1 / TE24 FV ratio: **2.341** (TE24: pat freiermuth — 2161)
- TE1 / TE30 FV ratio: **3.809** (TE30: kenyon sadiq — 1328)
- TE1 / TE36 FV ratio: **6.283** (TE36: zach ertz — 805)
- TE1 / TE40 FV ratio: **7.516** (TE40: eli raridon — 673)

## Upper-TE decomposition

- Top-12 FV coefficient of variation: **0.1817**
- Top-12 production-multiplier coefficient of variation: **0.1651**
- Top-12 age-multiplier coefficient of variation: **0.0782**
- Top-24 FV vs production-multiplier Spearman: **0.8261**
- Top-24 FV vs age-multiplier Spearman: **0.0711**

## Live fallback / floor semantics

- Elite production floor applied: **0 TEs**
- No-history role rescue applied: **5 TEs**
- Raw production at floor: **5 TEs**
- Raw production at ceiling: **0 TEs**
- Age multiplier at 0.62 floor: **2 TEs**

## Production lineage

- Phase 1 current-vs-transparent-candidate Spearman: **0.983309**
- Phase 1 top-15 overlap: **15/15 (100.0%)**
- Legacy TE live-vs-generated median absolute PM drift: **0.0210**
- Legacy overall median absolute PM drift: **0.0339**
- TE / overall median drift ratio: **0.619x**

## Existing prospective evidence

- Completed outcome weeks available: **[1, 2, 3]**
- TE FV vs active PPG Spearman: **0.5765**
- TE FV vs total points Spearman: **0.5655**
- These Weeks 1-3 results are descriptive only under frozen upstream protocols.

## Top 40 live TEs

| Rank | TE | Age | Role | FV | Prod mult | Age mult | Elite floor | No-history rescue |
|---:|---|---:|---|---:|---:|---:|:---:|:---:|
| 1 | trey mcbride | 26 | Elite | 5058 | 1.1216 | 1.0000 | N | N |
| 2 | brock bowers | 23 | Elite | 4109 | 1.0053 | 0.9063 | N | N |
| 3 | tucker kraft | 25 | Elite | 3749 | 0.8312 | 1.0000 | N | N |
| 4 | kyle pitts | 25 | Elite | 3659 | 0.8114 | 1.0000 | N | N |
| 5 | tyler warren | 24 | Elite | 3476 | 0.8208 | 0.9390 | N | N |
| 6 | sam laporta | 25 | Elite | 3400 | 0.7539 | 1.0000 | N | N |
| 7 | colston loveland | 22 | Elite | 3201 | 0.8593 | 0.8259 | N | N |
| 8 | jake ferguson | 27 | Elite | 3066 | 0.6799 | 1.0000 | N | N |
| 9 | dalton kincaid | 26 | Starter | 2982 | 0.6613 | 1.0000 | N | N |
| 10 | juwan johnson | 29 | Starter | 2932 | 0.6500 | 1.0000 | N | N |
| 11 | harold fannin | 22 | Elite | 2823 | 0.7760 | 0.8067 | N | N |
| 12 | dallas goedert | 31 | Elite | 2789 | 0.7292 | 0.8480 | N | N |
| 13 | george kittle | 32 | Elite | 2774 | 0.7967 | 0.7720 | N | N |
| 14 | brenton strange | 25 | Rotational | 2658 | 0.5894 | 1.0000 | N | N |
| 15 | mark andrews | 30 | Rotational | 2609 | 0.6260 | 0.9240 | N | N |
| 16 | dalton schultz | 30 | Rotational | 2569 | 0.6166 | 0.9240 | N | N |
| 17 | hunter henry | 31 | Starter | 2505 | 0.6549 | 0.8480 | N | N |
| 18 | aj barner | 24 | Rotational | 2454 | 0.5906 | 0.9213 | N | N |
| 19 | chig okonkwo | 26 | Rotational | 2309 | 0.5120 | 1.0000 | N | N |
| 20 | tj hockenson | 29 | Rotational | 2296 | 0.5091 | 1.0000 | N | N |
| 21 | isaiah likely | 26 | Rotational | 2266 | 0.5024 | 1.0000 | N | N |
| 22 | cade otton | 27 | Understudy | 2207 | 0.4894 | 1.0000 | N | N |
| 23 | travis kelce | 36 | Elite | 2173 | 0.7770 | 0.6200 | N | N |
| 24 | pat freiermuth | 27 | Understudy | 2161 | 0.4792 | 1.0000 | N | N |
| 25 | oronde gadsden | 23 | Rotational | 2054 | 0.5449 | 0.8356 | N | N |
| 26 | greg dulcich | 26 | Understudy | 2047 | 0.4538 | 1.0000 | N | N |
| 27 | theo johnson | 25 | Understudy | 1667 | 0.3696 | 1.0000 | N | N |
| 28 | gunnar helm | 23 | Understudy | 1578 | 0.4280 | 0.8177 | N | N |
| 29 | david njoku | 30 | Depth | 1436 | 0.3447 | 0.9240 | N | N |
| 30 | kenyon sadiq | 21 | Understudy | 1328 | 0.4571 | 0.6443 | N | N |
| 31 | terrance ferguson | 23 | Depth | 1188 | 0.3284 | 0.8024 | N | N |
| 32 | jake tonges | 27 | Depth | 1108 | 0.2458 | 1.0000 | N | N |
| 33 | mason taylor | 22 | Depth | 1092 | 0.3426 | 0.7069 | N | N |
| 34 | matt hibner | 24 | Speculative | 886 | 0.2200 | 0.8929 | N | Y |
| 35 | michael trigg | 24 | Speculative | 886 | 0.2200 | 0.8929 | N | N |
| 36 | zach ertz | 35 | Depth | 805 | 0.2880 | 0.6200 | N | N |
| 37 | max klare | 23 | Speculative | 780 | 0.2200 | 0.7857 | N | Y |
| 38 | oscar delp | 23 | Speculative | 780 | 0.2200 | 0.7857 | N | Y |
| 39 | elijah arroyo | 23 | Speculative | 683 | 0.1936 | 0.7817 | N | N |
| 40 | eli raridon | 22 | Speculative | 673 | 0.2200 | 0.6786 | N | Y |

## Scientific limit / next step

This audit does not decide that the TE scale or age curve is correct merely because the deployed mechanics are internally consistent. Any material calibration concern must be preregistered at the broad-cohort level before fitting or validation.

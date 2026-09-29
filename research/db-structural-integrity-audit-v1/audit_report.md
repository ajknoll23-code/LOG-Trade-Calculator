# DB Structural Integrity Audit V1

**Decision:** `PASS_DB_STRUCTURAL_AUDIT_FREEZE_REVIEW_REQUIRED_BEFORE_ANY_MODEL_CHANGE`

## Scope

- Live DB count: **65**
- Production V2 Phase 1 DB benchmark coverage: **63/65 (96.9%)**
- Live DB position weight: **0.870000**
- DB age curve: **{'peakStart': 23, 'peakEnd': 27, 'floor': 32}**
- Production changes: **None**
- Fitting: **None**
- Named-player adjustments: **None**
- Kickers: **Excluded from this audit series**

## Hard integrity gates

- minimum_live_db_count: **PASS**
- all_live_db_values_positive: **PASS**
- unique_live_db_keys: **PASS**
- minimum_phase1_db_candidate_coverage_share: **PASS**
- minimum_phase1_current_vs_candidate_spearman: **PASS**
- minimum_phase1_top_n_overlap_share: **PASS**
- age_v2_must_not_authorize_deployment: **PASS**
- position_weight_v2_must_not_authorize_deployment: **PASS**
- db_must_be_outside_idp_position_lineage_deployment: **PASS**
- prior_dl_lb_audit_must_not_have_changed_production: **PASS**
- kicker_excluded_from_scope: **PASS**

## Mechanical interpretation

Within DB, position weight is constant. DB-vs-DB spacing therefore comes from production and age mechanics.

- Current DB1: **tykee smith — 4044 FV**
- DB1 / DB2 FV ratio: **1.051** (DB2: kyle hamilton — 3847)
- DB1 / DB3 FV ratio: **1.051** (DB3: nick cross — 3846)
- DB1 / DB6 FV ratio: **1.097** (DB6: trevon moehrig — 3685)
- DB1 / DB12 FV ratio: **1.176** (DB12: alontae taylor — 3440)
- DB1 / DB24 FV ratio: **1.295** (DB24: daron bland — 3122)
- DB1 / DB32 FV ratio: **1.403** (DB32: nahshon wright — 2883)
- DB1 / DB48 FV ratio: **1.655** (DB48: tyrique stevenson — 2444)
- DB1 / DB60 FV ratio: **2.128** (DB60: jaylon carlies — 1900)

## Upper-DB decomposition

- Top-12 FV coefficient of variation: **0.0426**
- Top-12 production-multiplier coefficient of variation: **0.0426**
- Top-12 age-multiplier coefficient of variation: **0.0336**
- Top-24 FV vs production-multiplier Spearman: **0.9609**
- Top-24 FV vs age-multiplier Spearman: **-0.0452**

## Outlier diagnostics

- Largest top-32 adjacent FV ratio: **1.051x** between DB1 tykee smith and DB2 kyle hamilton
- FV robust-z flags (|z| >= 3.5): **0**
- Production-multiplier robust-z flags (|z| >= 3.5): **2**
- FV Tukey upper-fence flags: **0**
- Production-multiplier Tukey upper-fence flags: **0**
- Statistical flags are review signals only, not correction authority.

## Live fallback / floor semantics

- Elite production floor applied: **0 DBs**
- No-history role rescue applied: **0 DBs**
- Raw production at floor: **0 DBs**
- Raw production at ceiling: **0 DBs**
- Age multiplier at 0.62 floor: **1 DBs**

## Production lineage and benchmark stability

- Phase 1 current-vs-transparent-candidate Spearman: **0.952584**
- Phase 1 top-32 overlap: **30/32 (93.8%)**
- Legacy DB live-vs-generated median absolute PM drift: **0.0211**
- Legacy overall median absolute PM drift: **0.0339**
- DB / overall median drift ratio: **0.622x**

## IDP lineage isolation

- Frozen IDP position-lineage deployed cohort positions observed: **['DL', 'LB']**
- DB present in that cohort: **NO**
- Prior DL/LB structural audit changed production: **False**
- The DL/LB transport-residual finding is not presumed to apply to DB.

## Existing prospective evidence

- Completed Age V2 outcome weeks: **[1, 2, 3]**
- DB FV vs active PPG Spearman: **0.3260**
- DB FV vs total points Spearman: **0.2568**
- These Weeks 1-3 results are descriptive only under frozen upstream protocols.

## Top 60 live DBs

| Rank | DB | Age | Role | FV | Prod mult | Age mult | Elite floor | No-history rescue |
|---:|---|---:|---|---:|---:|---:|:---:|:---:|
| 1 | tykee smith | 25 | Elite | 4044 | 0.8451 | 1.0000 | N | N |
| 2 | kyle hamilton | 25 | Elite | 3847 | 0.8039 | 1.0000 | N | N |
| 3 | nick cross | 24 | Elite | 3846 | 0.8037 | 1.0000 | N | N |
| 4 | kamari lassiter | 23 | Elite | 3813 | 0.7968 | 1.0000 | N | N |
| 5 | koolaid mckinstry | 23 | Elite | 3744 | 0.7825 | 1.0000 | N | N |
| 6 | trevon moehrig | 27 | Elite | 3685 | 0.7702 | 1.0000 | N | N |
| 7 | kam curl | 27 | Elite | 3671 | 0.7671 | 1.0000 | N | N |
| 8 | chamarri conner | 26 | Elite | 3640 | 0.7608 | 1.0000 | N | N |
| 9 | talanoa hufanga | 26 | Elite | 3635 | 0.7597 | 1.0000 | N | N |
| 10 | cooper dejean | 23 | Every-Down | 3624 | 0.7574 | 1.0000 | N | N |
| 11 | nick emmanwori | 22 | Elite | 3496 | 0.8306 | 0.8795 | N | N |
| 12 | alontae taylor | 27 | Every-Down | 3440 | 0.7190 | 1.0000 | N | N |
| 13 | xavier mckinney | 27 | Every-Down | 3430 | 0.7169 | 1.0000 | N | N |
| 14 | xavier watts | 24 | Every-Down | 3430 | 0.7169 | 1.0000 | N | N |
| 15 | quentin lake | 27 | Every-Down | 3368 | 0.7039 | 1.0000 | N | N |
| 16 | jaquan brisker | 27 | Every-Down | 3314 | 0.6925 | 1.0000 | N | N |
| 17 | jordan battle | 25 | Every-Down | 3302 | 0.6901 | 1.0000 | N | N |
| 18 | cole bishop | 23 | Every-Down | 3269 | 0.6831 | 1.0000 | N | N |
| 19 | tyson campbell | 26 | Starter | 3215 | 0.6718 | 1.0000 | N | N |
| 20 | jalen pitre | 27 | Starter | 3202 | 0.6691 | 1.0000 | N | N |
| 21 | malik mustapha | 24 | Starter | 3163 | 0.6610 | 1.0000 | N | N |
| 22 | trent mcduffie | 25 | Rotational | 3161 | 0.6607 | 1.0000 | N | N |
| 23 | marcus jones | 27 | Rotational | 3127 | 0.6534 | 1.0000 | N | N |
| 24 | daron bland | 27 | Starter | 3122 | 0.6524 | 1.0000 | N | N |
| 25 | paulson adebo | 27 | Starter | 3095 | 0.6468 | 1.0000 | N | N |
| 26 | brian branch | 24 | Rotational | 3079 | 0.6434 | 1.0000 | N | N |
| 27 | grant delpit | 27 | Rotational | 3045 | 0.6364 | 1.0000 | N | N |
| 28 | mike sainristil | 25 | Rotational | 2962 | 0.6190 | 1.0000 | N | N |
| 29 | julian love | 28 | Starter | 2949 | 0.6669 | 0.9240 | N | N |
| 30 | jalen thompson | 28 | Every-Down | 2921 | 0.6606 | 0.9240 | N | N |
| 31 | deshon elliott | 29 | Every-Down | 2909 | 0.7168 | 0.8480 | N | N |
| 32 | nahshon wright | 27 | Rotational | 2883 | 0.6025 | 1.0000 | N | N |
| 33 | antoine winfield | 28 | Starter | 2854 | 0.6455 | 0.9240 | N | N |
| 34 | dee alford | 28 | Rotational | 2819 | 0.6377 | 0.9240 | N | N |
| 35 | cam bynum | 28 | Rotational | 2800 | 0.6332 | 0.9240 | N | N |
| 36 | kerby joseph | 25 | Rotational | 2797 | 0.5846 | 1.0000 | N | N |
| 37 | derwin james | 30 | Elite | 2785 | 0.7540 | 0.7720 | N | N |
| 38 | devon witherspoon | 25 | Rotational | 2783 | 0.5817 | 1.0000 | N | N |
| 39 | reed blankenship | 27 | Rotational | 2771 | 0.5791 | 1.0000 | N | N |
| 40 | budda baker | 30 | Elite | 2766 | 0.7489 | 0.7720 | N | N |
| 41 | mike jackson | 29 | Every-Down | 2698 | 0.6649 | 0.8480 | N | N |
| 42 | christian gonzalez | 24 | Rotational | 2694 | 0.5631 | 1.0000 | N | N |
| 43 | sauce gardner | 24 | Rotational | 2540 | 0.5309 | 1.0000 | N | N |
| 44 | jessie bates | 29 | Rotational | 2528 | 0.6231 | 0.8480 | N | N |
| 45 | will johnson | 23 | Understudy | 2524 | 0.5275 | 1.0000 | N | N |
| 46 | marlon humphrey | 30 | Starter | 2522 | 0.6826 | 0.7720 | N | N |
| 47 | minkah fitzpatrick | 29 | Rotational | 2480 | 0.6113 | 0.8480 | N | N |
| 48 | tyrique stevenson | 26 | Understudy | 2444 | 0.5108 | 1.0000 | N | N |
| 49 | cj gardnerjohnson | 28 | Rotational | 2441 | 0.5522 | 0.9240 | N | N |
| 50 | malaki starks | 22 | Rotational | 2405 | 0.5958 | 0.8435 | N | N |
| 51 | dillon thieneman | 22 | Rotational | 2382 | 0.5908 | 0.8427 | N | N |
| 52 | coby bryant | 27 | Rotational | 2333 | 0.4875 | 1.0000 | N | N |
| 53 | jacob parrish | 22 | Rotational | 2329 | 0.5788 | 0.8409 | N | N |
| 54 | derek stingley | 25 | Understudy | 2208 | 0.4615 | 1.0000 | N | N |
| 55 | riq woolen | 27 | Understudy | 2203 | 0.4603 | 1.0000 | N | N |
| 56 | treydan stukes | 24 | Understudy | 2146 | 0.4485 | 1.0000 | N | N |
| 57 | kevin winston | 22 | Rotational | 2135 | 0.5350 | 0.8341 | N | N |
| 58 | mansoor delane | 22 | Rotational | 2051 | 0.5158 | 0.8312 | N | N |
| 59 | kevin byard | 33 | Every-Down | 2012 | 0.6783 | 0.6200 | N | N |
| 60 | jaylon carlies | 24 | Understudy | 1900 | 0.3970 | 1.0000 | N | N |

## Scientific limit / next step

This audit does not decide that the DB scale or age curve is correct merely because the deployed mechanics are internally consistent. Any material calibration concern must be preregistered at the broad-cohort level before fitting or validation.

If B1 is green and review finds no material DB concern, the positional structural-audit series closes here. Kickers are intentionally excluded.

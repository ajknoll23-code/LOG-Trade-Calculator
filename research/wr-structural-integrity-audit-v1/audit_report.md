# WR Structural Integrity Audit V1

**Decision:** `PASS_WR_STRUCTURAL_AUDIT_FREEZE_REVIEW_REQUIRED_BEFORE_ANY_MODEL_CHANGE`

## Scope

- Live WR count: **114**
- Production V2 Phase 1 WR benchmark coverage: **108/114 (94.7%)**
- Live WR position weight: **1.000000**
- WR age curve: **{'peakStart': 24, 'peakEnd': 28, 'floor': 33}**
- Fractional-age interpolation: **No (RB-only mechanism)**
- Production changes: **None**
- Fitting: **None**

## Hard integrity gates

- minimum_live_wr_count: **PASS**
- all_live_wr_values_positive: **PASS**
- unique_live_wr_keys: **PASS**
- minimum_phase1_wr_candidate_coverage_share: **PASS**
- minimum_phase1_current_vs_candidate_spearman: **PASS**
- minimum_phase1_top_n_overlap_share: **PASS**
- age_v2_must_not_authorize_deployment: **PASS**
- position_weight_v2_must_not_authorize_deployment: **PASS**

## Mechanical interpretation

Within WR, position weight is constant. WR-vs-WR spacing therefore comes from production and integer-age mechanics.

- Current WR1: **puka nacua — 7986 FV**
- WR1 / WR2 FV ratio: **1.058** (WR2: jaxon smithnjigba — 7550)
- WR1 / WR3 FV ratio: **1.136** (WR3: jamarr chase — 7030)
- WR1 / WR6 FV ratio: **1.366** (WR6: drake london — 5847)
- WR1 / WR12 FV ratio: **1.568** (WR12: tee higgins — 5094)
- WR1 / WR18 FV ratio: **1.796** (WR18: garrett wilson — 4446)
- WR1 / WR24 FV ratio: **1.956** (WR24: malik nabers — 4083)
- WR1 / WR36 FV ratio: **2.272** (WR36: courtland sutton — 3515)
- WR1 / WR48 FV ratio: **2.600** (WR48: davante adams — 3071)
- WR1 / WR72 FV ratio: **4.333** (WR72: denzel boston — 1843)
- WR1 / WR96 FV ratio: **7.374** (WR96: chris bell — 1083)

## Upper-WR decomposition

- Top-12 FV coefficient of variation: **0.1558**
- Top-12 production-multiplier coefficient of variation: **0.1558**
- Top-12 age-multiplier coefficient of variation: **0.0000**
- Top-24 FV vs production-multiplier Spearman: **0.9722**
- Top-24 FV vs age-multiplier Spearman: **0.3525**

## Live fallback / floor semantics

- Elite production floor applied: **0 WRs**
- No-history role rescue applied: **8 WRs**
- Raw production at floor: **11 WRs**
- Raw production at ceiling: **0 WRs**
- Age multiplier at 0.62 floor: **2 WRs**

## Production lineage

- Phase 1 current-vs-transparent-candidate Spearman: **0.960396**
- Phase 1 top-36 overlap: **35/36 (97.2%)**
- Legacy WR live-vs-generated median absolute PM drift: **0.0513**
- Legacy overall median absolute PM drift: **0.0339**
- WR / overall median drift ratio: **1.513x**

## Existing prospective evidence

- Completed outcome weeks available: **[1, 2, 3]**
- WR FV vs active PPG Spearman: **0.5838**
- WR FV vs total points Spearman: **0.5319**
- These Weeks 1-3 results are descriptive only under frozen upstream protocols.

## Top 40 live WRs

| Rank | WR | Age | Role | FV | Prod mult | Age mult | Elite floor | No-history rescue |
|---:|---|---:|---|---:|---:|---:|:---:|:---:|
| 1 | puka nacua | 25 | Elite | 7986 | 1.4521 | 1.0000 | N | N |
| 2 | jaxon smithnjigba | 24 | Elite | 7550 | 1.3727 | 1.0000 | N | N |
| 3 | jamarr chase | 26 | Elite | 7030 | 1.2781 | 1.0000 | N | N |
| 4 | amonra st brown | 26 | Elite | 6871 | 1.2492 | 1.0000 | N | N |
| 5 | george pickens | 25 | Elite | 5864 | 1.0662 | 1.0000 | N | N |
| 6 | drake london | 25 | Elite | 5847 | 1.0632 | 1.0000 | N | N |
| 7 | nico collins | 27 | Elite | 5490 | 0.9982 | 1.0000 | N | N |
| 8 | rashee rice | 26 | Elite | 5483 | 0.9969 | 1.0000 | N | N |
| 9 | ceedee lamb | 27 | Elite | 5476 | 0.9956 | 1.0000 | N | N |
| 10 | chris olave | 26 | Elite | 5406 | 0.9828 | 1.0000 | N | N |
| 11 | zay flowers | 25 | Elite | 5118 | 0.9305 | 1.0000 | N | N |
| 12 | tee higgins | 27 | Every-Down | 5094 | 0.9262 | 1.0000 | N | N |
| 13 | aj brown | 29 | Elite | 5015 | 0.9869 | 0.9240 | N | N |
| 14 | jameson williams | 25 | Every-Down | 4801 | 0.8728 | 1.0000 | N | N |
| 15 | devonta smith | 27 | Every-Down | 4587 | 0.8340 | 1.0000 | N | N |
| 16 | jaylen waddle | 27 | Every-Down | 4575 | 0.8319 | 1.0000 | N | N |
| 17 | christian watson | 27 | Every-Down | 4480 | 0.8146 | 1.0000 | N | N |
| 18 | garrett wilson | 26 | Every-Down | 4446 | 0.8083 | 1.0000 | N | N |
| 19 | tetairoa mcmillan | 23 | Every-Down | 4410 | 0.8683 | 0.9235 | N | N |
| 20 | alec pierce | 26 | Every-Down | 4405 | 0.8010 | 1.0000 | N | N |
| 21 | ladd mcconkey | 24 | Starter | 4239 | 0.7707 | 1.0000 | N | N |
| 22 | dk metcalf | 28 | Starter | 4236 | 0.7702 | 1.0000 | N | N |
| 23 | rome odunze | 24 | Starter | 4175 | 0.7591 | 1.0000 | N | N |
| 24 | malik nabers | 23 | Every-Down | 4083 | 0.8091 | 0.9175 | N | N |
| 25 | michael wilson | 26 | Starter | 4061 | 0.7383 | 1.0000 | N | N |
| 26 | emeka egbuka | 23 | Every-Down | 3933 | 0.7819 | 0.9147 | N | N |
| 27 | quentin johnston | 24 | Starter | 3909 | 0.7107 | 1.0000 | N | N |
| 28 | wandale robinson | 25 | Starter | 3902 | 0.7094 | 1.0000 | N | N |
| 29 | michael pittman | 28 | Rotational | 3708 | 0.6743 | 1.0000 | N | N |
| 30 | justin jefferson | 27 | Rotational | 3663 | 0.6660 | 1.0000 | N | N |
| 31 | dj moore | 29 | Starter | 3646 | 0.7173 | 0.9240 | N | N |
| 32 | marvin harrison | 24 | Rotational | 3599 | 0.6545 | 1.0000 | N | N |
| 33 | jordan addison | 24 | Rotational | 3562 | 0.6476 | 1.0000 | N | N |
| 34 | luther burden | 22 | Every-Down | 3562 | 0.7810 | 0.8292 | N | N |
| 35 | terry mclaurin | 30 | Starter | 3547 | 0.7605 | 0.8480 | N | N |
| 36 | courtland sutton | 30 | Starter | 3515 | 0.7537 | 0.8480 | N | N |
| 37 | romeo doubs | 26 | Rotational | 3385 | 0.6155 | 1.0000 | N | N |
| 38 | khalil shakir | 26 | Rotational | 3369 | 0.6126 | 1.0000 | N | N |
| 39 | josh downs | 25 | Rotational | 3354 | 0.6098 | 1.0000 | N | N |
| 40 | jayden reed | 26 | Rotational | 3326 | 0.6046 | 1.0000 | N | N |

## Scientific limit / next step

This audit does not decide that the WR scale or age curve is correct merely because the deployed mechanics are internally consistent. Any material calibration concern must be preregistered at the broad-cohort level before fitting or validation.

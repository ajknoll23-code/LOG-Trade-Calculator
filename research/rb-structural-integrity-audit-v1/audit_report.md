# RB Structural Integrity Audit V1

**Decision:** `PASS_RB_STRUCTURAL_AUDIT_FREEZE_REVIEW_REQUIRED_BEFORE_ANY_MODEL_CHANGE`

## Scope

- Live RB count: **97**
- Production V2 Phase 1 RB benchmark coverage: **93/97 (95.9%)**
- Live RB position weight: **0.890000**
- RB age curve: **{'peakStart': 23, 'peakEnd': 25, 'floor': 30}**
- Birth-date coverage: **92/97 (94.8%)**
- Production changes: **None**
- Fitting: **None**

## Hard integrity gates

- minimum_live_rb_count: **PASS**
- all_live_rb_values_positive: **PASS**
- unique_live_rb_keys: **PASS**
- minimum_phase1_rb_candidate_coverage_share: **PASS**
- minimum_phase1_current_vs_candidate_spearman: **PASS**
- minimum_phase1_top_n_overlap_share: **PASS**
- age_v2_must_not_authorize_deployment: **PASS**
- position_weight_v2_must_not_authorize_deployment: **PASS**

## Mechanical interpretation

Within RB, position weight is constant. RB-vs-RB spacing therefore comes from production and age mechanics, including the RB-specific youth rule and fractional-age interpolation.

- Current RB1: **jahmyr gibbs — 8652 FV**
- RB1 / RB2 FV ratio: **1.034** (RB2: bijan robinson — 8369)
- RB1 / RB3 FV ratio: **1.219** (RB3: ashton jeanty — 7095)
- RB1 / RB6 FV ratio: **1.476** (RB6: jonathan taylor — 5863)
- RB1 / RB12 FV ratio: **1.811** (RB12: kenneth walker — 4778)
- RB1 / RB18 FV ratio: **2.127** (RB18: travis etienne — 4067)
- RB1 / RB24 FV ratio: **2.458** (RB24: saquon barkley — 3520)
- RB1 / RB32 FV ratio: **3.093** (RB32: blake corum — 2797)
- RB1 / RB36 FV ratio: **3.275** (RB36: jacory croskeymerritt — 2642)
- RB1 / RB48 FV ratio: **4.692** (RB48: tyler allgeier — 1844)

## Upper-RB decomposition

- Top-12 FV coefficient of variation: **0.2208**
- Top-12 production-multiplier coefficient of variation: **0.1692**
- Top-12 age-multiplier coefficient of variation: **0.1421**
- Top-24 FV vs production-multiplier Spearman: **0.5406**
- Top-24 FV vs age-multiplier Spearman: **0.5323**

## RB-specific age mechanics

- Elite-youth qualifiers: **5**
- Elite-youth qualifiers in top 12: **5**
- Median FV uplift vs no-youth-bonus counterfactual: **828.0**
- Max FV uplift vs no-youth-bonus counterfactual: **1866.0**
- Median absolute fractional-age FV effect where birth date exists: **84.0**
- Max absolute fractional-age FV effect: **2387.0**

## Live fallback / floor semantics

- Elite production floor applied: **0 RBs**
- No-history role rescue applied: **13 RBs**
- Raw production at floor: **17 RBs**
- Raw production at ceiling: **0 RBs**
- Age multiplier at 0.62 floor: **5 RBs**

## Production lineage

- Phase 1 current-vs-transparent-candidate Spearman: **0.967834**
- Phase 1 top-32 overlap: **30/32 (93.8%)**
- Legacy RB live-vs-generated median absolute PM drift: **0.0577**
- Legacy overall median absolute PM drift: **0.0339**
- RB / overall median drift ratio: **1.702x**

## Existing prospective evidence

- Completed outcome weeks available: **[1, 2, 3]**
- RB FV vs active PPG Spearman: **0.7912**
- RB FV vs total points Spearman: **0.7558**
- These Weeks 1-3 results are descriptive only under frozen upstream protocols.

## Top 40 live RBs

| Rank | RB | Age | Frac age | Role | FV | Prod mult | Age mult | Youth qual | Youth uplift |
|---:|---|---:|---:|---|---:|---:|---:|:---:|---:|
| 1 | jahmyr gibbs | 24 | 24.53 | Elite | 8652 | 1.5322 | 1.1536 | Y | 1152 |
| 2 | bijan robinson | 24 | 24.66 | Elite | 8369 | 1.5405 | 1.1099 | Y | 828 |
| 3 | ashton jeanty | 22 | 22.82 | Elite | 7095 | 1.0838 | 1.3373 | Y | 1866 |
| 4 | devon achane | 24 | 24.96 | Elite | 6505 | 1.3125 | 1.0125 | Y | 80 |
| 5 | james cook | 26 | 27.01 | Elite | 5923 | 1.4282 | 0.8472 | N | 0 |
| 6 | jonathan taylor | 27 | 27.69 | Elite | 5863 | 1.5060 | 0.7953 | N | 0 |
| 7 | omarion hampton | 23 | 23.54 | Every-Down | 5066 | 1.0350 | 1.0000 | N | 0 |
| 8 | chase brown | 26 | 26.53 | Elite | 5058 | 1.1688 | 0.8840 | N | 0 |
| 9 | breece hall | 25 | 25.33 | Every-Down | 4914 | 1.0299 | 0.9748 | N | 0 |
| 10 | kyren williams | 25 | 26.09 | Elite | 4914 | 1.0949 | 0.9169 | Y | 0 |
| 11 | cam skattebo | 24 | 24.65 | Every-Down | 4849 | 0.9905 | 1.0000 | N | 0 |
| 12 | kenneth walker | 25 | 25.94 | Every-Down | 4778 | 1.0514 | 0.9284 | N | 0 |
| 13 | javonte williams | 26 | 26.43 | Every-Down | 4724 | 1.0829 | 0.8913 | N | 0 |
| 14 | christian mccaffrey | 30 | 30.31 | Elite | 4679 | 1.5419 | 0.6200 | N | 0 |
| 15 | bucky irving | 23 | 24.11 | Every-Down | 4544 | 0.9283 | 1.0000 | N | 0 |
| 16 | jeremiyah love | 21 | 21.33 | Every-Down | 4429 | 1.0561 | 0.8568 | N | 0 |
| 17 | quinshon judkins | 22 | 22.92 | Every-Down | 4340 | 0.8948 | 0.9909 | N | 0 |
| 18 | travis etienne | 27 | 27.67 | Every-Down | 4067 | 1.0426 | 0.7968 | N | 0 |
| 19 | josh jacobs | 28 | 28.63 | Elite | 3932 | 1.1093 | 0.7241 | N | 0 |
| 20 | derrick henry | 32 | 32.73 | Elite | 3897 | 1.2842 | 0.6200 | N | 0 |
| 21 | dandre swift | 27 | 27.71 | Every-Down | 3823 | 0.9833 | 0.7943 | N | 0 |
| 22 | treveyon henderson | 23 | 23.94 | Starter | 3769 | 0.7700 | 1.0000 | N | 0 |
| 23 | jadarian price | 22 | 22.97 | Starter | 3642 | 0.7469 | 0.9963 | N | 0 |
| 24 | saquon barkley | 29 | 29.64 | Elite | 3520 | 1.1103 | 0.6477 | N | 0 |
| 25 | jaylen warren | 27 | 27.91 | Every-Down | 3503 | 0.9187 | 0.7789 | N | 0 |
| 26 | rj harvey | 25 | 25.65 | Starter | 3439 | 0.7390 | 0.9507 | N | 0 |
| 27 | rico dowdle | 28 | 28.29 | Every-Down | 3203 | 0.8727 | 0.7497 | N | 0 |
| 28 | bhayshul tuten | 24 | 23.62 | Rotational | 3165 | 0.6466 | 1.0000 | N | 0 |
| 29 | kyle monangai | 24 | 24.32 | Rotational | 3043 | 0.6217 | 1.0000 | N | 0 |
| 30 | jk dobbins | 27 | 27.78 | Starter | 2870 | 0.7437 | 0.7884 | N | 0 |
| 31 | chuba hubbard | 27 | 27.30 | Starter | 2802 | 0.6939 | 0.8251 | N | 0 |
| 32 | blake corum | 25 | 25.84 | Rotational | 2797 | 0.6105 | 0.9359 | N | 0 |
| 33 | kenny gainwell | 27 | 27.55 | Starter | 2772 | 0.7020 | 0.8066 | N | 0 |
| 34 | david montgomery | 29 | 29.31 | Starter | 2677 | 0.8133 | 0.6723 | N | 0 |
| 35 | woody marks | 25 | 25.75 | Rotational | 2643 | 0.5726 | 0.9429 | N | 0 |
| 36 | jacory croskeymerritt | 25 | 25.47 | Rotational | 2642 | 0.5596 | 0.9646 | N | 0 |
| 37 | tony pollard | 29 | 29.42 | Starter | 2601 | 0.7999 | 0.6644 | N | 0 |
| 38 | tyrone tracy | 26 | 26.85 | Rotational | 2596 | 0.6170 | 0.8595 | N | 0 |
| 39 | jonathon brooks | 23 | 23.19 | Rotational | 2589 | 0.5288 | 1.0000 | N | 0 |
| 40 | zach charbonnet | 25 | 25.72 | Rotational | 2534 | 0.5478 | 0.9450 | N | 0 |

## Scientific limit / next step

This audit does not decide that the RB scale, age curve, or youth premium is correct merely because the deployed mechanics are internally consistent. Any material calibration concern must be preregistered at the broad-cohort level before fitting or validation.

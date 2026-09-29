# QB Structural Integrity Audit V1

**Decision:** `PASS_QB_STRUCTURAL_AUDIT_FREEZE_REVIEW_REQUIRED_BEFORE_ANY_MODEL_CHANGE`

## Scope

- Live QB count: **64**
- Production V2 Phase 1 QB benchmark coverage: **54/64 (84.4%)**
- Live QB position weight: **1.300000**
- QB age curve: **{'peakStart': 26, 'peakEnd': 33, 'floor': 35}**
- QB post-peak floor: **0.546000**
- Production changes: **None**
- Fitting: **None**

## Hard integrity gates

- minimum_live_qb_count: **PASS**
- all_live_qb_values_positive: **PASS**
- unique_live_qb_keys: **PASS**
- minimum_phase1_qb_candidate_coverage_share: **PASS**
- minimum_phase1_current_vs_candidate_spearman: **PASS**
- phase1_top18_overlap_required: **PASS**
- age_v2_must_not_authorize_deployment: **PASS**
- position_weight_v2_must_not_authorize_deployment: **PASS**

## Mechanical interpretation

Within the QB position, position weight is a common multiplicative constant. It can change QB versus other positions, but it cannot by itself change QB1 versus QB12 spacing.

- Current QB1: **josh allen — 6578 FV**
- QB1 / QB2 FV ratio: **1.167** (QB2: jalen hurts — 5637)
- QB1 / QB3 FV ratio: **1.182** (QB3: trevor lawrence — 5563)
- QB1 / QB6 FV ratio: **1.242** (QB6: justin herbert — 5296)
- QB1 / QB12 FV ratio: **1.342** (QB12: brock purdy — 4902)
- QB1 / QB18 FV ratio: **1.484** (QB18: sam darnold — 4434)
- QB1 / QB24 FV ratio: **1.739** (QB24: cj stroud — 3782)
- QB1 / QB36 FV ratio: **4.182** (QB36: will levis — 1573)

## Upper-QB decomposition

- Top-12 FV coefficient of variation: **0.0833**
- Top-12 production-multiplier coefficient of variation: **0.0787**
- Top-12 age-multiplier coefficient of variation: **0.0487**
- Top-18 FV vs production-multiplier Spearman: **0.8431**
- Top-18 FV vs age-multiplier Spearman: **0.2240**

## Live fallback / floor semantics

- Elite floor applied: **0 QBs**
- No-history role rescue applied: **12 QBs**
- Raw production at floor: **19 QBs**
- Raw production at ceiling: **0 QBs**
- Top-18 elite floor count: **0**
- Top-18 no-history rescue count: **0**

## Production lineage

- Phase 1 current-vs-transparent-candidate Spearman: **0.995931**
- Phase 1 top-18 overlap: **18/18**
- Legacy QB live-vs-generated median absolute PM drift: **0.0032**
- Legacy QB live-vs-generated p95 absolute PM drift: **0.0426**

## Existing prospective evidence

- Completed outcome weeks available: **[1, 2, 3]**
- QB FV vs active PPG Spearman: **0.5496**
- QB FV vs total points Spearman: **0.6980**
- These Weeks 1-3 results are descriptive only under the frozen upstream protocols.

## Top 30 live QBs

| Rank | QB | Age | Role | FV | Prod mult | Age mult | Elite floor | No-history rescue |
|---:|---|---:|---|---:|---:|---:|:---:|:---:|
| 1 | josh allen | 30 | Elite | 6578 | 0.9200 | 1.0000 | N | N |
| 2 | jalen hurts | 28 | Elite | 5637 | 0.7884 | 1.0000 | N | N |
| 3 | trevor lawrence | 26 | Elite | 5563 | 0.7781 | 1.0000 | N | N |
| 4 | dak prescott | 33 | Elite | 5489 | 0.7677 | 1.0000 | N | N |
| 5 | bo nix | 26 | Elite | 5341 | 0.7470 | 1.0000 | N | N |
| 6 | justin herbert | 28 | Elite | 5296 | 0.7407 | 1.0000 | N | N |
| 7 | lamar jackson | 29 | Elite | 5240 | 0.7329 | 1.0000 | N | N |
| 8 | jared goff | 31 | Elite | 5071 | 0.7092 | 1.0000 | N | N |
| 9 | caleb williams | 24 | Elite | 5021 | 0.7823 | 0.8977 | N | N |
| 10 | patrick mahomes | 30 | Starter | 4972 | 0.6954 | 1.0000 | N | N |
| 11 | drake maye | 23 | Elite | 4933 | 0.8101 | 0.8516 | N | N |
| 12 | brock purdy | 26 | Starter | 4902 | 0.6856 | 1.0000 | N | N |
| 13 | baker mayfield | 31 | Starter | 4853 | 0.6787 | 1.0000 | N | N |
| 14 | daniel jones | 29 | Starter | 4672 | 0.6535 | 1.0000 | N | N |
| 15 | joe burrow | 29 | Starter | 4648 | 0.6500 | 1.0000 | N | N |
| 16 | jordan love | 27 | Rotational | 4644 | 0.6495 | 1.0000 | N | N |
| 17 | jayden daniels | 25 | Starter | 4610 | 0.6838 | 0.9428 | N | N |
| 18 | sam darnold | 29 | Rotational | 4434 | 0.6202 | 1.0000 | N | N |
| 19 | jaxson dart | 23 | Elite | 4351 | 0.7275 | 0.8364 | N | N |
| 20 | tyler shough | 26 | Rotational | 4278 | 0.5983 | 1.0000 | N | N |
| 21 | bryce young | 25 | Rotational | 3973 | 0.5929 | 0.9372 | N | N |
| 22 | kyler murray | 29 | Rotational | 3966 | 0.5546 | 1.0000 | N | N |
| 23 | jacoby brissett | 33 | Rotational | 3903 | 0.5458 | 1.0000 | N | N |
| 24 | cj stroud | 24 | Rotational | 3782 | 0.6040 | 0.8758 | N | N |
| 25 | malik willis | 27 | Rotational | 3697 | 0.5171 | 1.0000 | N | N |
| 26 | cam ward | 24 | Rotational | 3134 | 0.5073 | 0.8639 | N | N |
| 27 | matthew stafford | 38 | Elite | 2954 | 0.7568 | 0.5460 | N | N |
| 28 | tua tagovailoa | 28 | Understudy | 2682 | 0.3752 | 1.0000 | N | N |
| 29 | michael penix jr | 26 | Depth | 2503 | 0.3500 | 1.0000 | N | N |
| 30 | fernando mendoza | 22 | Understudy | 2182 | 0.4304 | 0.7089 | N | N |

## Scientific limit / next step

This audit does not decide that the QB curve is correct merely because the mechanics are internally consistent. If review shows a material calibration question, the next study must freeze a broad-cohort hypothesis before fitting or validation and must not be designed around named-player outcomes.

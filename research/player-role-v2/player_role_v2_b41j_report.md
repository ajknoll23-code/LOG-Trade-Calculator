# Player Role V2 — B41J 2025 Holdout Continuation Evaluation

- Continuation class: **OUTCOME_BLIND_IDENTITY_SOURCE_AMENDMENT**
- B41I identity-source amendment used: **Yes**
- Frozen B41I identity SHA256: `d531dcff2d3ff681f02210d314f6e9f16c671c0beefa85fd311a55363675d4cc`
- Holdout rows: **14,282**
- Data-quality gate: **PASS**
- B41F model retuned: **No**
- B41E tiers retuned: **No**
- Post-hoc exclusions: **No**
- Production deployed: **No**
- Production change authorized: **No**

## Outcome-blind structural report

- Pre-performance structural artifact SHA256: `55b7d59f75df2c1390b89776f5e451a87fc9b76226611af076fce1c3d1f68d51`
- Cohort rows before stable-ID filter: **14,486**
- Modeling rows after stable-ID filter: **14,282**
- Overall stable-ID coverage: **0.985917**
- Missing optional identity columns: **full_name**

## Frozen primary holdout tests

1. MAE vs baseline: **PASS** — macro Δ=-0.015102, 95% CI [-0.017557, -0.012346]
2. Pooled Spearman: **PASS** — ρ=0.759368, 95% CI [0.752181, 0.765443]
3. Ordered future production tiers: **PASS**
4. Ordered future snap tiers: **PASS**

## Scientific decision

**PASS_2025_HOLDOUT_VALIDATION_OUTCOME_BLIND_IDENTITY_SOURCE_AMENDMENT**

## Next stage

Run B42 owner-blind role parity audit with the frozen Role V2 system and disclosed B41I identity-source amendment; no production deployment yet.

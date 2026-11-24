# Durability / Availability V2 — Phase 5 Prospective Evaluator

Method: `durability-v2-phase5-prospective-v1`  
Status: **`COLLECTION_ONLY_INTERIM_BYE_UNADJUSTED`**

## Guardrail

**Research only. Production deployment is not authorized.**

- Frozen candidate SHA256: `444d935e7ea108285b0aa6627e1de1404d4c9aaea5f62834e73db76c5452c502`
- Frozen at: **2026-09-05T10:44:59.483609Z**
- First eligible future week: **1**
- Completed consecutive weeks used: **[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]**
- Eligible durability cohort: **425**

## Primary prospective target

**Full-season realized games played / 17 scheduled games.**

This becomes authoritative only after all 18 regular-season weeks are safely complete.
Interim participation diagnostics are bye-unadjusted and cannot authorize promotion.

## Current state

Authoritative full-season durability metrics are **not available yet**.

### Interim bye-unadjusted diagnostic — non-authoritative

| Variant | MAE | RMSE | Spearman | Δ MAE vs control | Δ Spearman | Pos lower MAE |
|---|---:|---:|---:|---:|---:|---:|
| `deployed_control` | 0.1964 | 0.2886 | 0.2055 | — | — | — |
| `bridge_w100` | 0.1941 | 0.2772 | 0.2191 | -0.0024 | +0.0136 | 3/7 |
| `bridge_w50` | 0.1918 | 0.2792 | 0.2159 | -0.0047 | +0.0104 | 4/7 |

## Interpretation

Do not promote or reject a Durability V2 candidate from interim bye-unadjusted metrics. The authoritative prospective target is full-season games played / 17 after all 18 regular-season weeks are safely complete.

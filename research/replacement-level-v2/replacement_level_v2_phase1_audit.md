# Replacement Level / Positional Scale V2 — Phase 1 Baseline Audit

**Research only. No deployment or frozen prospective experiment is changed.**

Method: `replacement-level-v2-phase1-baseline-audit-v1`

## Important architecture note

The live calculator consumes precomputed `PROD_MULT_DATA`; it does not dynamically look up these replacement ranks on every valuation. The ranks below are the legacy Production V2 research/transport anchors being audited for future calibration.

## Current transport constants

- PM transform: `clamp(-0.10 + 0.75 × production_ratio, 0.15, 1.55)`
- Global value scale carried by the Production V2 transport: **55.0**

## Replacement-level evidence inventory

| Pos | Legacy rank | Live pos wt | Eff demand | 80% starts | 90% | 95% | Boot 50% median | Boot p10-p90 | Empirical baseline | Phase-2 candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| QB | 18 | 1.30 | 27.65 | 24 | 29 | 34 | 22 | 22-34 | 18 | 14, 16, 18, 20, 22, 24, 28, 29, 34 |
| RB | 32 | 0.89 | 27.03 | 26 | 33 | 39 | 25 | 25-28 | 37 | 25, 26, 27, 28, 30, 32, 33, 34, 36, 37, 39 |
| WR | 36 | 1.00 | 33.13 | 36 | 43 | 49 | 34 | 28-37 | 43 | 28, 32, 33, 34, 36, 37, 38, 40, 43, 49 |
| TE | 15 | 0.82 | 19.83 | 21 | 27 | 33 | 13 | 10-13 | 16 | 10, 11, 13, 15, 16, 17, 19, 20, 21, 27, 33 |
| DL | 32 | 0.93 | 34.37 | 29 | 39 | 47 | 34 | 16-37 | 23 | 16, 23, 28, 29, 30, 32, 34, 36, 37, 39, 47 |
| LB | 32 | 1.12 | 40.52 | 41 | 50 | 55 | 43 | 40-52 | 32 | 28, 30, 32, 34, 36, 40, 41, 43, 50, 52, 55 |
| DB | 32 | 0.87 | 36.43 | 38 | 47 | 53 | 28 | 22-40 | 30 | 22, 28, 30, 32, 34, 36, 38, 40, 47, 53 |

## Phase 1 decision

- The legacy ranks remain the **control**, not presumed truth.
- Candidate grids are evidence-grounded from actual historical lineup demand plus a narrow local neighborhood around each legacy rank.
- Phase 2 should test **one position at a time** while holding every other position, Production V2 transport input, age curve, opportunity, durability, no-history logic, and position weight fixed.
- Do **not** jointly optimize replacement rank and position weight yet; that would make attribution impossible.
- Do **not** change the PM transform or global scale in Phase 2. Those become a later scale-calibration phase only after replacement ranks are narrowed.

## Guardrails

- deployment_authorized: **false**
- replacement_rank_change_authorized: **false**
- position_weight_change_authorized: **false**
- scale_change_authorized: **false**
- frozen prospective experiments: **untouched**

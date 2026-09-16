# Free-Agent Production V2 — Phase 1 Lineage Audit & Freeze

**Decision:** `PASS_FA_PROD_V2_PHASE1_LINEAGE_AND_FREEZE`

This phase is research-only. It does not change `FA_PROD_MULT_DATA`, `PROD_MULT_DATA`, `index.html`, or any production valuation logic.

## Frozen design

- Cohort: current free agents that actively resolve to deployed `FA_PROD_MULT_DATA`; kickers excluded.
- Identity: stable Sleeper ID + position; team is only a duplicate-name disambiguator.
- History: canonical 2025 shrinkage + durability component, unchanged.
- Offense projection: 50/50 FantasyPros + Sleeper when both are available; one-source fallback otherwise.
- IDP projection: canonical IDP V1 category ensemble.
- History/forward blend: 45% / 55%.
- Replacement ranks: QB18, RB32, WR36, TE15, DL32, LB32, DB32.
- Transform: `clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)`.

## Primary gates

| Gate | Result | Requirement |
|---|---:|---:|
| Runtime FA-specific identity | PASS (364/364) | exact |
| Reproducible active-cohort candidate coverage | 91.5% (333/364) | ≥ 90% |
| Offense FantasyPros coverage among Sleeper-covered active entries | 87.1% (128/147) | ≥ 50% |
| Replacement baselines present | PASS | all 7 positions |

## Cohort

- `FA_PROD_MULT_DATA` entries including kickers: **407**
- Current free agents in committed Sleeper snapshot: **1580**
- Runtime FA-specific non-K cohort: **364**
- Mapped active entries: **364**
- Reproducible candidates: **333**
- Production files mutated: **0**

## Replacement anchors

| Pos | Rank | Anchor | Combined points | Cohort |
|---|---:|---|---:|---:|
| QB | 18 | joe burrow | 245.27 | 54 |
| RB | 32 | rj harvey | 175.88 | 88 |
| WR | 36 | luther burden | 149.98 | 108 |
| TE | 15 | juwan johnson | 128.35 | 42 |
| DL | 32 | jonathan greenard | 149.41 | 83 |
| LB | 32 | tj edwards | 182.16 | 73 |
| DB | 32 | paulson adebo | 158.74 | 62 |

## Largest raw production-multiplier differences

These are diagnostics only, not deployment recommendations.

| Player | Pos | Deployed | Phase-1 candidate | Delta | Source |
|---|---|---:|---:|---:|---|
| benjamin morrison | DB | 0.150 | 0.491 | +0.341 | idp_v1_both |
| marcus epps | DB | 0.160 | 0.463 | +0.303 | idp_v1_both |
| dadrion taylordemerson | DB | 0.293 | 0.567 | +0.274 | idp_v1_both |
| myles harden | DB | 0.161 | 0.418 | +0.257 | idp_v1_both |
| taron johnson | DB | 0.269 | 0.522 | +0.253 | idp_v1_both |
| quinyon mitchell | DB | 0.369 | 0.619 | +0.250 | idp_v1_fp_only |
| denzel ward | DB | 0.266 | 0.514 | +0.248 | idp_v1_both |
| cordale flott | DB | 0.265 | 0.512 | +0.247 | idp_v1_both |
| cam taylorbritt | DB | 0.150 | 0.397 | +0.247 | idp_v1_both |
| jourdan lewis | DB | 0.290 | 0.530 | +0.240 | idp_v1_both |
| renardo green | DB | 0.302 | 0.534 | +0.232 | idp_v1_both |
| eric murray | DB | 0.347 | 0.579 | +0.232 | idp_v1_both |
| darien porter | DB | 0.150 | 0.377 | +0.227 | idp_v1_both |
| tj sanders | DL | 0.151 | 0.378 | +0.227 | idp_v1_both |
| tarheeb still | DB | 0.324 | 0.549 | +0.225 | idp_v1_both |

## Decision semantics

A PASS freezes only the lineage/candidate construction and permits a separate shadow-validation preregistration. It does **not** authorize a production change.

A STOP means source/identity coverage must be repaired before any model selection or production consideration.


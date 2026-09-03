# Production V2 — Phase 8 Consolidated Shadow Model

## Decision

**SHADOW MODEL COMPLETE — research only; no production deployment authorized.**

- Full tracked-player coverage: **549 / 549**
- Normal V2 candidates: **518**
- Continuity fallbacks: **31**
- Shadow variants emitted: **8**
- Production files mutated: **0**
- Deployment authorized: **No**

## What is now locked architecturally

1. Candidate-present players use the **Phase-5 data-first semantics**: a valid production estimate does not switch into `ROLE_MULT` at the numeric floor.
2. The existing **Elite 0.65 safeguard** remains held fixed.
3. Candidate-missing players use the **Phase-7 continuity fallback**: preserve current deployed value until normal V2 evidence exists.
4. Current position weights, age architecture, RB continuous age, QB/LB decline rules, and global scale remain unchanged.

## What is still waiting on real 2026 evidence

- FantasyPros vs Sleeper provider weight
- history vs forward weight
- documented vs evidence-hybrid replacement ranks
- affine transform floor

## Shadow variants

Every variant contains all 549 tracked players. The only varying structural inputs are replacement-rank family and affine floor.

| Variant | Rank family | Floor |
|---|---|---:|
| `documented__floor_0.05` | documented | 0.05 |
| `documented__floor_0.10` | documented | 0.10 |
| `documented__floor_0.15` | documented | 0.15 |
| `documented__floor_0.20` | documented | 0.20 |
| `evidence_hybrid__floor_0.05` | evidence_hybrid | 0.05 |
| `evidence_hybrid__floor_0.10` | evidence_hybrid | 0.10 |
| `evidence_hybrid__floor_0.15` | evidence_hybrid | 0.15 |
| `evidence_hybrid__floor_0.20` | evidence_hybrid | 0.20 |

## Monitoring reference

**`evidence_hybrid__floor_0.15`**

Evidence-hybrid ranks carry the existing denominator backtest signal; 0.15 retains the current floor because Phase 6 found compression but did not authorize a replacement.

This is a monitoring reference, **not a deployment candidate**.

| Pos | N | Continuity | Floor | Median FV Δ | P95 abs FV Δ | Spearman | Top-N overlap | Max rank move |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| QB | 64 | 10 | 21 (32.8%) | +0.0% | 33.0% | 0.9753 | 100.0% | 15 |
| RB | 97 | 4 | 22 (22.7%) | -21.7% | 34.4% | 0.9554 | 92.3% | 31 |
| WR | 114 | 6 | 4 (3.5%) | -8.0% | 39.4% | 0.9625 | 97.1% | 38 |
| TE | 44 | 1 | 0 (0.0%) | -1.1% | 24.7% | 0.9808 | 100.0% | 10 |
| DL | 86 | 3 | 0 (0.0%) | -8.9% | 44.7% | 0.9700 | 100.0% | 43 |
| LB | 79 | 5 | 0 (0.0%) | +2.7% | 44.3% | 0.9751 | 96.9% | 21 |
| DB | 65 | 2 | 0 (0.0%) | -0.7% | 32.4% | 0.9566 | 93.3% | 20 |

## Largest monitoring-reference movers

| Player | Pos | Current | Shadow | Change | Source | Floor |
|---|---|---:|---:|---:|---|---|
| caleb douglas | WR | 687 | 1579 | +129.8% | normal_v2_candidate | no |
| marshawn lloyd | RB | 907 | 1783 | +96.6% | normal_v2_candidate | no |
| aaron donald | DL | 698 | 1366 | +95.7% | normal_v2_candidate | no |
| kayvon thibodeaux | DL | 1182 | 2309 | +95.3% | normal_v2_candidate | no |
| emmanuel mcneilwarren | DB | 827 | 1593 | +92.6% | normal_v2_candidate | no |
| justin joly | TE | 486 | 916 | +88.5% | normal_v2_candidate | no |
| malachi fields | WR | 864 | 1599 | +85.1% | normal_v2_candidate | no |
| zavion thomas | WR | 626 | 1119 | +78.8% | normal_v2_candidate | no |
| jacob rodriguez | LB | 1682 | 2964 | +76.2% | normal_v2_candidate | no |
| kyle louis | LB | 968 | 1683 | +73.9% | normal_v2_candidate | no |
| eli stowers | TE | 578 | 986 | +70.6% | normal_v2_candidate | no |
| aj haulcy | DB | 1150 | 1911 | +66.2% | normal_v2_candidate | no |
| dangelo ponds | DB | 670 | 1093 | +63.1% | normal_v2_candidate | no |
| jonathan greenard | DL | 2007 | 3254 | +62.1% | normal_v2_candidate | no |
| anthony hill | LB | 889 | 1389 | +56.2% | normal_v2_candidate | no |
| josiah trotter | LB | 924 | 1434 | +55.2% | normal_v2_candidate | no |
| deshaun watson | QB | 1838 | 2717 | +47.8% | normal_v2_candidate | no |
| deion burks | WR | 1676 | 875 | -47.8% | normal_v2_candidate | no |
| peter woods | DL | 884 | 1303 | +47.4% | normal_v2_candidate | no |
| jakobi lane | WR | 1055 | 1551 | +47.0% | normal_v2_candidate | no |
| jeremiyah love | RB | 4436 | 2377 | -46.4% | normal_v2_candidate | no |
| kayden mcdonald | DL | 643 | 931 | +44.8% | normal_v2_candidate | no |
| keldric faulk | DL | 892 | 1289 | +44.5% | normal_v2_candidate | no |
| jake golday | LB | 1162 | 1663 | +43.1% | normal_v2_candidate | no |
| phil mafah | RB | 1282 | 734 | -42.7% | normal_v2_candidate | yes |

## Integrity gates

- Full 549-player value coverage in every variant: **PASS**
- Continuity fallback is value-neutral in every variant: **PASS**
- Floor monotonicity violations: **0**

## Phase 9 handoff

Score the frozen/pre-week shadow variants against realized 2026 league-scored outcomes. Do not optimize against current Fundamental Value or market value.

No coefficient should be selected because it looks better against today's values. Phase 9 must score these frozen/pre-week candidates against realized 2026 league-scored outcomes and require stable, material out-of-sample improvement before deployment.

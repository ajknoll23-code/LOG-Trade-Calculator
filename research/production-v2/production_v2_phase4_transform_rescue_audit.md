# Production V2 — Phase 4 Transform + No-History Rescue Audit

## Decision

**BLOCK_BASELINE_OR_TRANSFORM_DEPLOYMENT_UNTIL_NO_HISTORY_RESCUE_IS_REDESIGNED**

- Deployment blocked: **Yes**
- Production files mutated: **0**
- Documented scenario reproduced Phase-1 effective production multipliers exactly: **Yes**

## Why Phase 4 was required

Phase 3 found that changing only the replacement denominator can push a no-history player across the raw-PM floor. The current production function then substitutes the player's role estimate, which can make effective PM rise even though raw PM fell.

Current order of operations:

1. Compute `raw PM = clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)`.
2. Elite players below 0.65 are floored to 0.65.
3. For other no-history players, if raw PM is `<= 0.15` and the role estimate is higher, effective PM becomes the role estimate.

## Floor / rescue behavior by position

| Pos | Doc floor | Hybrid floor | Doc rescues | Hybrid rescues | New rescue crossings | Raw↓ Effective↑ |
|---|---:|---:|---:|---:|---:|---:|
| QB | 21 (38.9%) | 21 (38.9%) | 7 | 7 | 0 | 0 |
| RB | 14 (15.1%) | 22 (23.7%) | 0 | 2 | 2 | 2 |
| WR | 4 (3.7%) | 4 (3.7%) | 0 | 0 | 0 | 0 |
| TE | 0 (0.0%) | 0 (0.0%) | 0 | 0 | 0 | 0 |
| DL | 0 (0.0%) | 0 (0.0%) | 0 | 0 | 0 | 0 |
| LB | 0 (0.0%) | 0 (0.0%) | 0 | 0 | 0 | 0 |
| DB | 0 (0.0%) | 0 (0.0%) | 0 | 0 | 0 | 0 |

## Role threshold discontinuity

| Role | Role estimate | Jump when no-history raw PM hits 0.15 |
|---|---:|---:|
| Depth | 0.35 | +0.20 |
| Elite | 1.40 | +0.00 |
| Every-Down | 1.15 | +1.00 |
| Rotational | 0.65 | +0.50 |
| Speculative | 0.22 | +0.07 |
| Starter | 1.00 | +0.85 |
| Understudy | 0.57 | +0.42 |

For non-Elite no-history players, the floor is therefore not merely a floor. It is a switch into a different model (`ROLE_MULT`). That is the discontinuity.

## Paradoxical movers

| Player | Pos | Role | Raw PM doc→hybrid | Effective PM doc→hybrid | Rescue doc→hybrid |
|---|---|---|---|---|---|
| jmari taylor | RB | Speculative | 0.180→0.150 | 0.180→0.220 | no→yes |
| jam miller | RB | Speculative | 0.186→0.150 | 0.186→0.220 | no→yes |

## Interpretation

A denominator or transform change is not isolated in the current architecture whenever it moves a no-history non-Elite player across raw PM 0.15. The effective production multiplier can jump to ROLE_MULT, creating discontinuous and potentially direction-reversing value movement. Any Production V2 redesign must resolve this before baseline or transform changes can be trusted.

This means the Phase-3 evidence-hybrid rank set is **not rejected**, but it is **not yet a trustworthy deployable candidate** either. We first need continuous fallback semantics so changing a denominator cannot accidentally flip a player into a different valuation model.

## Next step

Design and audit continuous no-history fallback semantics, then rerun the Phase-3 baseline comparison under those semantics before considering deployment.

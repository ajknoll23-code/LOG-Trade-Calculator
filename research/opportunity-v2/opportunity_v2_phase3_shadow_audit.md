# Continuous Opportunity / Role Signal V2 — Phase 3 Shadow Audit

Method: `opportunity-v2-phase3-shadow-audit-v1`  
Status: **`RESEARCH_ONLY_CURRENT_PLAYER_OPPORTUNITY_SHADOW_AUDIT`**

## Guardrail

**Research only. No deployed ROLE_MULT or player value is changed.**

## Why residualize opportunity?

Phase 2 already controls for current production. This shadow therefore
uses only the leader/control prediction ratio, so the opportunity layer
cannot simply re-add production that the deployed model already knows.

- Current shadow cohort: **426**
- No-history players: **isolated / unchanged**
- Production V2: **frozen / unchanged**
- Residual bounds: **historical position-specific OOF P05/P95**

## Current-board movement

| Variant | Changed | Median abs | P90 abs | Max abs | Clipped ratios | Min pos rank ρ | Min top-N overlap | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `opportunity_residual_w25` | 423 | 1.4% | 4.6% | 17.2% | 3 | 0.9875 | 94.4% | PASS |
| `opportunity_residual_w50` | 424 | 2.9% | 9.1% | 34.4% | 3 | 0.9506 | 88.9% | PASS |
| `opportunity_residual_w100` | 425 | 5.8% | 18.3% | 68.8% | 3 | 0.9094 | 83.3% | FAIL |

## Historical residual-ratio bounds

| Pos | N | P05 | Median | P95 |
|---|---:|---:|---:|---:|
| QB | 772 | 0.2834 | 1.0434 | 1.6571 |
| RB | 1728 | 0.4307 | 1.0339 | 1.4210 |
| WR | 2378 | 0.4351 | 1.0356 | 1.4645 |
| TE | 1382 | 0.6204 | 1.0214 | 1.3511 |
| DL | 3085 | 0.5618 | 0.9932 | 1.3904 |
| LB | 3057 | 0.7181 | 1.0151 | 1.2497 |
| DB | 4087 | 0.6875 | 1.0159 | 1.2191 |

## Largest 25% bridge movers

| Player | Pos | Role | Deployed | Shadow | Δ | 2025 opp | 2024 opp | Opp Δ | Ratio |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| tyson bagent | QB | Speculative | 1073 | 888 | -17.2% | 1.2% | 1.2% | -0.1% | 0.3120 |
| anthony richardson | QB | Speculative | 879 | 1023 | +16.4% | 1.4% | 59.9% | -58.5% | 1.6571 |
| kyler murray | QB | Rotational | 3990 | 4594 | +15.1% | 29.1% | 97.1% | -68.1% | 1.6052 |
| joe milton | QB | Speculative | 1073 | 942 | -12.2% | 4.9% | 5.6% | -0.6% | 0.5116 |
| tanner mckee | QB | Speculative | 1073 | 945 | -11.9% | 8.1% | 7.8% | +0.4% | 0.5230 |
| tyrod taylor | QB | Speculative | 586 | 523 | -10.8% | 23.6% | 3.6% | +20.0% | 0.5707 |
| tyreek hill | WR | Rotational | 2473 | 2731 | +10.4% | 16.1% | 79.9% | -63.8% | 1.4171 |
| jalen milroe | QB | Speculative | 783 | 863 | +10.2% | 0.4% | — | +0.0% | 1.4074 |
| carson wentz | QB | Speculative | 1073 | 968 | -9.8% | 27.4% | 5.7% | +21.7% | 0.6083 |
| nnamdi madubuike | DL | Rotational | 2696 | 2959 | +9.8% | 7.5% | 71.4% | -63.9% | 1.3904 |
| davis mills | QB | Speculative | 1073 | 974 | -9.2% | 24.9% | 7.0% | +17.9% | 0.6324 |
| george holani | RB | Speculative | 639 | 581 | -9.1% | 3.6% | 0.5% | +3.1% | 0.6364 |
| marcus mariota | QB | Speculative | 1073 | 978 | -8.9% | 48.2% | 9.1% | +39.2% | 0.6450 |
| joe burrow | QB | Starter | 4648 | 5058 | +8.8% | 41.3% | 99.5% | -58.2% | 1.3528 |
| malik nabers | WR | Every-Down | 4088 | 4445 | +8.7% | 18.7% | 79.9% | -61.2% | 1.3490 |
| jayden daniels | QB | Starter | 4597 | 4995 | +8.7% | 37.2% | 90.9% | -53.7% | 1.3460 |
| jalen mcmillan | WR | Understudy | 2475 | 2688 | +8.6% | 12.1% | 54.1% | -42.0% | 1.3440 |
| nick bosa | DL | Every-Down | 3980 | 4296 | +7.9% | 11.3% | 64.6% | -53.4% | 1.3172 |
| jordan james | RB | Speculative | 767 | 826 | +7.7% | 0.3% | — | +0.0% | 1.3097 |
| jayden reed | WR | Rotational | 3350 | 3601 | +7.5% | 16.9% | 63.2% | -46.2% | 1.2995 |
| trey hendrickson | DL | Rotational | 3029 | 3252 | +7.4% | 24.2% | 72.8% | -48.6% | 1.2941 |
| jameis winston | QB | Speculative | 1073 | 1151 | +7.3% | 11.9% | 41.3% | -29.4% | 1.2922 |
| jerome ford | RB | Speculative | 624 | 665 | +6.6% | 23.3% | 44.5% | -21.2% | 1.2632 |
| garrett wilson | WR | Every-Down | 4455 | 4735 | +6.3% | 35.8% | 96.3% | -60.5% | 1.2516 |
| micah mcfadden | LB | Depth | 1694 | 1800 | +6.3% | 0.9% | 61.6% | -60.7% | 1.2497 |

## Screening result

Conservative current-board survivors: `opportunity_residual_w25`, `opportunity_residual_w50`

**Passing this screen is not deployment authorization.**

## Phase 4

If one or more conservative bridges survive the current-board stability screen, Phase 4 should historically calibrate the bridge weight itself rather than choosing 25% or 50% from current-board appearance. Re-run the Phase-2 historical protocol with the residual bridge layered on the production-only control and select a weight using out-of-sample accuracy plus current-board stability. Do not deploy from Phase 3.

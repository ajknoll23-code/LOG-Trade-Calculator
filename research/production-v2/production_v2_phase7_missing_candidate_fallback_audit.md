# Production V2 — Phase 7 Missing-Candidate Fallback Audit

## Decision

**CARRY_CURRENT_VALUE_CONTINUITY_FALLBACK_FOR_MISSING_V2_CANDIDATES**

- Production files mutated: **0**
- Normal V2 candidates: **518**
- Missing V2 candidates: **31**
- Continuity fallback changes those players' current values: **No**

The fallback is intentionally temporary and player-specific: the moment a normal V2 candidate becomes available, that player exits the continuity fallback automatically.

## Why these 31 are missing

### Forward-source state

- `idp_no_forward_projection`: **8**
- `missing_stable_sleeper_id`: **4**
- `offense_no_forward_projection`: **19**

### Evidence state

- `real_2025_history`: **14**
- `zero_game_synthetic_history`: **17**

- Missing stable Sleeper ID: **4**

Zero-game canonical history is explicitly treated as a **synthetic position-mean fallback**, not as real 2025 production.

## Why continuity is the control

`ROLE_MULT` is a coarse prior. History-only is real evidence for some players, but it is not calibrated as a substitute for the missing forward component. Replacing a player's deployed value with either one solely because a provider projection is absent would make missingness itself change player value.

Continuity avoids that. It says: **if V2 cannot build its normal estimate, do not manufacture a new one. Preserve the deployed value until coverage returns.**

## Diagnostic alternatives vs current value

| Diagnostic | Median change | P95 abs change | Max abs change |
|---|---:|---:|---:|
| Role-only | +0.6% | 52.2% | 63.5% |
| History-only | +95.9% | 158.1% | 287.9% |

These are diagnostics only. Neither alternative is authorized as a fallback by this audit.

## Missing candidates by position

| Pos | Missing | Real 2025 history | Zero-game synthetic history | Role-only P95 abs Δ | History-only P95 abs Δ |
|---|---:|---:|---:|---:|---:|
| QB | 10 | 4 | 6 | 56.6% | 131.3% |
| RB | 4 | 0 | 4 | 0.0% | 123.6% |
| WR | 6 | 4 | 2 | 48.1% | 250.5% |
| TE | 1 | 1 | 0 | 21.6% | 106.5% |
| DL | 3 | 3 | 0 | 24.8% | 11.4% |
| LB | 5 | 1 | 4 | 43.9% | 159.0% |
| DB | 2 | 1 | 1 | 32.2% | 38.2% |

## Largest role-only diagnostic movers

| Player | Pos | Role | Current | Role-only | Change | Evidence state |
|---|---|---|---:|---:|---:|---|
| dillon gabriel | QB | Depth | 1412 | 2308 | +63.5% | real_2025_history |
| bobby wagner | LB | Elite | 3453 | 5347 | +54.9% | real_2025_history |
| chris brazzell | WR | Speculative | 578 | 864 | +49.5% | zero_game_synthetic_history |
| anthony richardson | QB | Speculative | 879 | 1303 | +48.2% | real_2025_history |
| carson wentz | QB | Speculative | 1073 | 1573 | +46.6% | real_2025_history |
| joe milton | QB | Speculative | 1073 | 1573 | +46.6% | real_2025_history |
| cedric tillman | WR | Speculative | 841 | 1210 | +43.9% | real_2025_history |
| chris johnson | DB | Understudy | 1384 | 1852 | +33.8% | zero_game_synthetic_history |
| haason reddick | DL | Understudy | 1969 | 2472 | +25.5% | real_2025_history |
| jayden higgins | WR | Rotational | 2643 | 3222 | +21.9% | real_2025_history |
| zach ertz | TE | Depth | 805 | 979 | +21.6% | real_2025_history |
| tyree wilson | DL | Understudy | 2460 | 2916 | +18.5% | real_2025_history |
| ricky pearsall | WR | Rotational | 3080 | 3575 | +16.1% | real_2025_history |
| joey bosa | DL | Rotational | 2685 | 2819 | +5.0% | real_2025_history |
| jaylon jones | DB | Depth | 1636 | 1675 | +2.4% | real_2025_history |

## Interpretation

The 31 missing V2 candidates are a migration-coverage problem, not permission to invent a new fallback model. ROLE_MULT is a coarse prior and history-only is not calibrated to substitute for the missing forward component. Preserving the currently deployed value is the only fallback that is neutral to missingness and automatically disappears as V2 coverage improves.

## Next step

Production V2 now has a defined candidate-present semantic and a migration-safe candidate-missing semantic. Carry documented and evidence-hybrid baselines plus transform-floor sensitivity into the prospective 2026 evaluator. Before any production deployment, build a consolidated V2 shadow-value generator with these architectural decisions frozen and compare its full 549-player output to current production without mutating index.html.

# Replacement Level / Positional Scale V2 — Phase 4 Combined Board + Identifiability Audit

**Research only. No production or frozen prospective experiment is changed.**

Method: `replacement-level-v2-phase4-combined-identifiability-v1`

## Decision

- Replacement ranks: **empirically testable and ready for prospective freeze**
- Global value scale 55: **not identified by the available historical target — hold fixed**
- Affine PM slope/intercept: **not identified by the available historical target — hold fixed**
- PM floor/ceiling: **already frozen for separate prospective testing in Production V2 Phase 9 — do not duplicate it here**

Phase 4 therefore freezes the conversion layer conceptually: Replacement V2 Phase 5 will vary **replacement ranks only**.

## Combined rank families

| Family | QB | RB | WR | TE | DL | LB | DB | Safety | Global ρ | Top100 overlap | P90 abs FV Δ |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| `legacy_control` | 18 | 32 | 36 | 15 | 32 | 32 | 32 | PASS | 1.0000 | +100.0% | +0.0% |
| `prior_limited_evidence` | 18 | 26 | 34 | 15 | 23 | 32 | 30 | PASS | 0.9901 | +94.0% | +19.4% |
| `stable_positions_only` | 18 | 25 | 28 | 15 | 16 | 28 | 22 | PASS | 0.9898 | +92.0% | +19.9% |
| `full_phase2_leaders` | 29 | 25 | 28 | 11 | 16 | 28 | 22 | PASS | 0.9833 | +91.0% | +24.2% |

## Combined-board positional movement

| Family | QB med | RB med | WR med | TE med | DL med | LB med | DB med | Max abs Top100 share Δ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `prior_limited_evidence` | +0.0% | -19.7% | -1.1% | +0.0% | -4.1% | +0.0% | -0.4% | +5.0% |
| `stable_positions_only` | +0.0% | -20.1% | -7.9% | +0.0% | -12.6% | -3.9% | -3.2% | +4.0% |
| `full_phase2_leaders` | +29.2% | -20.1% | -7.9% | -14.5% | -12.6% | -3.9% | -3.2% | +5.0% |

## Floor / rescue diagnostics

Current deployed semantics can still turn a no-history raw-PM floor hit into `ROLE_MULT`. That is reported here but **excluded from the Phase-5 primary cohort** so Replacement V2 does not duplicate the separate No-History/Rookie V2 experiment.

### `legacy_control`

- role rescues: **7**
- new rescue crossings vs control: **0**
- removed rescue crossings vs control: **0**

### `prior_limited_evidence`

- role rescues: **9**
- new rescue crossings vs control: **2**
- removed rescue crossings vs control: **0**

### `stable_positions_only`

- role rescues: **9**
- new rescue crossings vs control: **2**
- removed rescue crossings vs control: **0**

### `full_phase2_leaders`

- role rescues: **3**
- new rescue crossings vs control: **2**
- removed rescue crossings vs control: **6**

## Transform identifiability

- Current: `clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)`
- Replacement ratio 1.0 maps to PM **0.65**
- Floor activates at ratio **0.333× replacement**
- Ceiling activates at ratio **2.200× replacement**
- Historical Phase-2 target identifies affine spacing: **No**

Reason: future relative production identifies the denominator. It does not provide an observed absolute dynasty PM/FV corresponding to each production ratio. Choosing a steeper or flatter monotone affine map from the same target would be an arbitrary value-spacing choice.

## Global scale identifiability

- Current global scale: **55**
- Identified by Phase-2 future relative-production target: **No**
- Positive pre-round scale preserves ordering mathematically: **Yes**

| Scale | Expected value multiplier vs 55 | Median integer multiplier | Integer-board ρ | Top100 overlap |
|---:|---:|---:|---:|---:|
| 45 | 0.818× | 0.818× | 1.0000 | +100.0% |
| 55 | 1.000× | 1.000× | 1.0000 | +100.0% |
| 65 | 1.182× | 1.182× | 1.0000 | +100.0% |

## Phase 5 handoff

- Phase-1 candidate cohort: **518**
- Primary real-history cohort: **426**
- No-history players excluded from primary: **92**

Freeze these prospective arms:

1. `legacy_control`
2. `prior_limited_evidence`
3. `stable_positions_only` — changes only positions whose Phase-2 leader was stable across 2/4/6-week windows
4. `full_phase2_leaders` — also includes QB29 and TE11

Transform stays **{'intercept': -0.1, 'ratio_slope': 0.75, 'floor': 0.15, 'ceiling': 1.55}**.
Global scale stays **55.0**.
POSITION_WEIGHT stays fixed.

Primary scoring will compare each preseason rank family's predicted within-position production ratio with realized future within-position relative production. That directly tests the replacement denominator without pretending the transform or global scale were calibrated.

## Guardrails

- deployment_authorized: **false**
- production_v2_change_authorized: **false**
- replacement_rank_change_authorized: **false**
- position_weight_change_authorized: **false**
- transform_change_authorized: **false**
- scale_change_authorized: **false**
- frozen prospective experiments touched: **false**

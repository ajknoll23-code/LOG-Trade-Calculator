# Package Adjustment V6 — Development Preregistration

**Status: FROZEN DEVELOPMENT PLAN — research only. Production remains V1.6.**

## Scope

V6 targets one unresolved production gap only: **one player vs exactly three lesser players** outside the narrow V4 45/33/22 composition envelope. Size2 V1.6 remains frozen and untouched. Multi-v-multi and 1-vs-4 are out of scope.

## Why new development voting is necessary

V4 established the three-player indifference level near 45/33/22, but it never varied three-player composition. Therefore a continuous composition/fragmentation slope cannot be identified from the existing V4 evidence. V5 varied composition only for 1-vs-2. NextGen V2 contained no 1-vs-3 challenges.

## Frozen development design

- Composition profiles: 45/33/22, 50/30/20, 50/25/25, 55/30/15, 60/25/15, 60/20/20
- Fragmentation measure: `phi = 1 - H`, `H = sum(s_i^2)`; V4 reference `phi_ref = 0.6402`.
- Apex-piece/target levels: 0.70, 0.80, 0.90, 0.97.
- Research cells: `24`.
- First maturity checkpoint: 600 effective votes; coverage-only retries at +100; hard cap 800.
- Minimum 30 distinct voters, 15 effective votes/cell, 10 voters/cell.

## Candidate set

- **C0:** raw additive FV control.
- **C1:** exact frozen production V1.6 baseline.
- **C2:** constant power norm, scoped only to 1-vs-3; retained as a diagnostic because NextGen M2a already collapsed to q=1 on multi-v-multi.
- **C4:** one-parameter rank-decayed order-statistic utility.
- **C5:** two-parameter HHI-fragmentation threshold, the direct continuous V4-extension candidate.

### Corrected C5

`S = sum(v_i)`, `s_i = v_i/S`, `H = sum(s_i^2)`, `phi = 1-H`.

`eta = a0 + a_phi*(phi - 0.6402)`

`m(phi) = 1 + exp(eta)`

`ScorePackage = S`

`ScoreTarget = target_FV * m(phi)`

`a0 in [-0.287682072452, 0.139761942375]` (reference multiplier 1.75–2.15).

`a_phi in [0, 0.5]`.

The `a_phi <= 0.5` bound is mathematical, not cosmetic: it is a sufficient condition that increasing the FV of any already-present package player cannot make the offer less sufficient.

## Shared choice-probability layer

`P(package) = logistic(beta*(ScorePackage-ScoreTarget)/5401 + delta_left*I(package_displayed_left))`.

Every model uses the same link. `beta` and `delta_left` are refit only on each training fold.

## Selection and governance

Five-fold deterministic challenge-grouped CV is preregistered. Development evidence can select at most one candidate but can never confirm production. A selected candidate must be frozen, followed by a separately generated fresh prospective catalog and new votes. If no development candidate qualifies, V6 stops and V1.6 stays unchanged. No post-hoc 50/30/20 rescue patch is allowed.


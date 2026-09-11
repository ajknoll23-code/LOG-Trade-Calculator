# Package Adjustment NextGen V2 — Research Specification and Preregistered Experiment

**Status: DRAFT FOR HUMAN REVIEW — RESEARCH ONLY. NO PRODUCTION FORMULA CHANGE IS AUTHORIZED BY THIS DOCUMENT.**

**Proposed repository directory:** `research/package-adjustment-nextgen-v2/`

**Proposed repository filename:** `package_adjustment_nextgen_v2_research_spec.md`

---

## 0. Why this uses a new repository directory

The repository already contains a historical directory named:

`research/package-adjustment-v2/`

That directory contains the earlier V2 challenge generator, challenge catalog, fit diagnostics, and results. It must remain historical evidence and **must not be overwritten or repurposed** for this project.

All work described in this specification therefore belongs under:

`research/package-adjustment-nextgen-v2/`

The phrase **NextGen V2** in this document refers to the new generalized Package Adjustment architecture discussed in September 2026, not the historical `research/package-adjustment-v2/` experiment.

---

# 1. Current production baseline

The current controlled-live Package Adjustment revision is:

`v1.6-v5-size2-composition-overlay`

The current exact-live Package Adjustment formula SHA-256 is:

`9a1a52f3393a701fe8463fcf2179d1342debb925da1109ce73276b8b2b8cbbc7`

The controlled-live V1.6 promotion artifact records:

- frozen evidence: **600 votes / 30 voters**
- V5-backed two-player composition support through **60/40**
- **65/35 and more imbalanced two-player packages fail closed**
- frozen V4 three-player behavior remains unchanged
- Fundamental Value / Fair Value remains unchanged
- Market Value remains unchanged
- draft-pick values remain unchanged
- Team Utility remains unchanged
- Package Adjustment continues to affect the **Trade Verdict only**
- future formula recalibration remains human-reviewed only

Production V1.6 stays frozen while NextGen V2 is researched.

Nothing in this specification authorizes a live formula change.

---

# 2. Existing research infrastructure that must be preserved

The existing Package Adjustment research system already has several protections that NextGen V2 should inherit rather than reinvent.

Current V5 research uses:

- `scripts/artifacts/generated/value_uncertainty.json` as the player FV input
- `data/league_rosters.json` to identify rostered players
- eligible positions:
  - QB
  - RB
  - WR
  - TE
  - DL
  - LB
  - DB
- K is excluded
- FV values are hidden from voters
- left/right display side is randomized
- challenge-family / cell sampling is controlled
- frozen challenge catalogs are not modified after activation
- frozen evidence snapshots are fingerprinted
- voter-cluster bootstrap is used
- target-cluster bootstrap is used in evidence hardening
- leave-one-voter-out sensitivity is available
- no extrapolation outside tested evidence is allowed
- research scripts cannot promote a production formula
- a separate reviewed production-candidate and human promotion step is required

The current permanent vote aggregation workflow is:

`.github/workflows/package-vote-aggregation-v3.yml`

Despite the legacy filename, its current workflow name is **Package Vote Aggregation V5**.

It currently validates the controlled-live formula, runs V5 aggregation/diagnostics, protects frozen research files, and recognizes the existing reserved package-vote prefixes:

- `__pkgv1__|`
- `__pkgv2__|`
- `__pkgv3__|`
- `__pkgv4__|`
- `__pkgv5__|`

NextGen V2 must **not reuse any of those transport markers**.

The proposed reserved NextGen transport namespace is:

- vote: `__pkgnv2__|`
- metadata: `__pkgnv2_meta__|`
- schema marker: `__pkgnv2_schema__|1`

These markers must be rechecked for uniqueness immediately before implementation.

The active V5 voting/aggregation path must not be replaced until the new catalog and activation change are separately reviewed.

---

# 3. Draft-pick data warning

`data/draft_picks.json` exists in the repository, but it is an ownership / traded-pick inventory file. It is **not sufficient by itself as the production draft-pick FV source**.

Do not build the NextGen pick challenger against `data/draft_picks.json` as though its rows contain the production pick values.

Before any pick-containing NextGen challenge is generated, the implementation must:

1. locate the exact production draft-pick FV source/logic currently consumed by the Trade Desk;
2. record the exact source path(s);
3. record the exact source SHA-256 fingerprint(s);
4. prove that the generated pick FV exactly matches the production Trade Desk value for the same pick;
5. freeze that mapping before voting activation.

If this cannot be verified, pick-specific challenge families remain inactive.

---

# 4. Problem statement

Production V1.6 was intentionally conservative.

It was designed around the question:

> Is one concentrated player being exchanged for a package of multiple lesser players?

That framing successfully supports evidence-backed 1-v-package regions, but it does not generalize to equal-piece-count or multi-piece-on-both-sides trades.

Observed KeepTradeCut behavior provides useful external behavioral evidence:

- 1-for-1 trades do not receive a visible Value Adjustment.
- 1-for-package trades can receive an adjustment.
- 2-for-2 trades can also receive a substantial adjustment.
- equal roster-slot count therefore does not eliminate the effect.
- absolute quality of the best assets appears to matter in addition to piece count.
- KTC describes its adjustment as considering value differences, "stud" factor, number of lesser pieces, roster spots, and nonlinear math.

KTC is **not** the target formula and is not treated as ground truth.

The research question is:

> Can a general, standalone side-utility model learn how dynasty managers value concentrated high-end assets versus dispersed packages, while preserving player FV and avoiding shape-specific rules?

---

# 5. Non-negotiable invariants

Any NextGen V2 candidate must satisfy all of the following.

1. **Individual player FV never changes.**
2. **Individual draft-pick FV never changes.**
3. Package Adjustment remains a separate trade-level layer.
4. Market Value remains separate.
5. Team Utility remains separate.
6. Position value already encoded in FV is not automatically re-added in Package Adjustment.
7. A true 1-for-1 trade must have zero Package Adjustment.
8. Adding a positive-value supported asset must never reduce the side's effective trade score.
9. Removing a positive-value supported asset must never increase the side's effective trade score.
10. Asset ordering inside a side must not matter.
11. Swapping Side A and Side B must reverse the signed trade differential exactly.
12. Identical sides must produce zero Package Adjustment.
13. Unsupported regions must fail closed.
14. No research script may change production automatically.
15. Any production promotion requires explicit human approval.

---

# 6. Leading hypothesis: standalone normalized utility

The primary hypothesis is that each side can be evaluated independently.

Let an asset have production Fair Value:

`v`

Define a deterministic reference value:

`V_REF`

and normalized asset value:

`x = v / V_REF`

Define a smooth strictly increasing function:

`g(x)`

with identification anchors:

`g(0) = 0`

`g(1) = 1`

For a side `S` containing assets `v_1 ... v_n`:

`U(S) = sum_i g(v_i / V_REF)`

`U(S)` is an internal utility score.

No individual asset FV is changed.

The model is permutation-invariant because it depends only on the multiset of asset values.

---

# 7. V_REF normalization rule

Scale drift is a known risk.

The baseline NextGen normalization rule is:

> `V_REF` is the nearest-rank 95th percentile of positive FV among eligible rostered non-kicker players in the frozen input snapshot.

Eligible positions remain:

`QB, RB, WR, TE, DL, LB, DB`

If the eligible rostered values sorted ascending are:

`v_(1) <= ... <= v_(N)`

then:

`V_REF = v_(ceil(0.95 * N))`

using 1-based indexing.

This rule is deterministic.

Why normalize:

- a global rescaling of the FV system should not silently change the meaning of "elite";
- the highest single player should not be the only scale anchor;
- a high-percentile reference is less sensitive to one player moving sharply;
- the same rule can be replayed after future FV rebuilds.

Every frozen challenge catalog must store:

- `V_REF`
- eligible-player count
- input path
- input SHA-256
- roster path
- roster SHA-256
- generation timestamp
- exact generator commit SHA

---

# 8. Equivalent-value mapping

A useful FV-scale interpretation of a side is:

`E(S) = V_REF * g^-1(U(S))`

or equivalently:

`E(S) = V_REF * g^-1(sum_i g(v_i / V_REF))`

`E(S)` is the **single-asset-equivalent value** of the side under the fitted utility model.

This produces an important singleton identity:

`E({v}) = v`

Therefore, for a true 1-for-1 trade:

`E(A) - E(B) = RawFV(A) - RawFV(B)`

and Package Adjustment is zero automatically.

## Critical interpretation correction

Do **not** define the displayed Package Adjustment as:

`E(S) - RawFV(S)`

and assume it should be positive.

For a concentration-rewarding convex utility region, a multi-asset package can have:

`E(S) < RawFV(S)`

That is not a model failure.

Example with the simple power utility `g(x)=x^1.2`:

- `[9000,1000]` raw = 10000
- equivalent value is approximately 9534
- `[5000,5000]` raw = 10000
- equivalent value is approximately 8909

Both equivalents are below the raw sum, yet the more concentrated side is worth about **625 FV more** in equivalent terms.

That relative difference is the effect we care about.

---

# 9. Trade-level Package Adjustment differential

For Side A and Side B define:

`RawGap = RawFV(A) - RawFV(B)`

`EquivalentGap = E(A) - E(B)`

Then define:

`PackageDifferential = EquivalentGap - RawGap`

This answers:

> How much did nonlinear package utility change the trade gap relative to simple FV addition?

For research UI reconciliation only:

`AdjustmentA = max(PackageDifferential, 0)`

`AdjustmentB = max(-PackageDifferential, 0)`

Then:

`(RawFV(A) + AdjustmentA) - (RawFV(B) + AdjustmentB) = EquivalentGap`

This allows the interface to continue showing unchanged raw FV totals plus a separate positive Package Adjustment on only the side favored by the nonlinear package effect.

This is a **display reconciliation rule**, not a claim that the favored side's individual assets changed FV.

For 1-for-1:

`PackageDifferential = 0`

by construction.

No production UI change is authorized during research.

---

# 10. Inverse-domain guard

`E(S)` requires evaluating `g^-1` at `U(S)`.

A multi-asset side may produce a utility sum above the maximum utility represented by the calibrated single-asset domain.

The research implementation must therefore store and enforce an explicit inverse-support domain.

Rules:

1. No silent spline extrapolation.
2. No arbitrary extension above the calibrated equivalent-value domain.
3. If `U(S)` is outside inverse support:
   - mark `equivalent_value_supported = false`;
   - retain the raw utility score for research diagnostics;
   - do not emit an FV-scale Package Differential;
   - fail closed for any production-like verdict simulation.
4. A later research phase may preregister a safe equivalent-domain extension, but it cannot be invented after viewing favorable results.

This prevents the equivalent-value interpretation from becoming an unnoticed extrapolation engine.

---

# 11. Model candidates

The experiment is designed to compare simple models before adding complexity.

## M0 — Raw FV control

`Score(S) = sum FV_i`

No Package Adjustment.

Purpose:

- minimum baseline
- proves whether any nonlinear model adds predictive information

## M1 — Frozen production V1.6 benchmark

Use the exact controlled-live V1.6 logic unchanged.

Purpose:

- benchmark current supported behavior
- fallback reference
- regression comparison

Outside V1.6 support, M1 behaves exactly as production currently behaves; do not invent support.

## M2a — Homogeneous power equivalent

Use:

`E_p(S) = (sum_i FV_i^p)^(1/p)`

with:

`p >= 1`

Properties:

- `p = 1` reduces exactly to raw FV
- `p > 1` rewards concentration
- singleton identity holds
- scale invariance is exact
- no inverse extrapolation is required
- only one shape parameter

Purpose:

- low-complexity nonlinear benchmark
- test whether a single global concentration strength is already sufficient

## M2b — Normalized monotonic-spline equivalent

Primary flexible candidate:

`U(S) = sum_i g(FV_i / V_REF)`

`E(S) = V_REF * g^-1(U(S))`

Required properties:

- continuous
- strictly increasing
- `g(0)=0`
- `g(1)=1`
- low degrees of freedom
- smoothness penalty
- no hard "stud" threshold
- no hard filler threshold
- no unconstrained upper-tail explosion

The exact spline knot rule, degree-of-freedom limit, regularization rule, and optimizer must be committed in a model-fit preregistration **before the first NextGen vote is opened for fitting**.

Knot locations may depend deterministically on the frozen FV snapshot, but not on vote outcomes.

## M3 — Separate pick curve challenger

Only activated if the production draft-pick FV source is verified.

Baseline null:

`g_pick(x) = g_player(x)`

Challenger:

`g_pick(x) != g_player(x)`

Both curves must be monotonic and independently normalized.

A pick-specific curve is retained only if it produces stable out-of-sample improvement.

## M4 — Explicit roster-friction challenger

Baseline M2 has:

`RosterFriction = 0`

M4 may add a smooth roster/player-count term only if it can preserve monotonicity.

It is specifically intended to test whether a pure piece-count effect remains after nonlinear asset utility is already modeled.

Because Team Utility already exists, M4 carries a high double-counting risk.

It is not part of the primary model unless the data clearly demand it.

## M5 — Sorted marginal-utility / elite-premium challenger

A more expressive model using:

- ordered asset values
- top-asset quality
- relative value of later pieces
- diminishing marginal contribution by piece rank

Purpose:

- test whether one global utility curve misses meaningful order-statistic interactions

This is a challenger, not the default architecture.

## M6 — Explicit concentration-index challenger

A comparative or side-level concentration model using features such as:

- top-asset share
- top-two share
- HHI
- soft top-k share

Purpose:

- test whether explicit concentration adds information beyond M2

It must not win merely because it is more complex.

---

# 12. Model-selection principle

Use the simplest candidate that explains the evidence.

Complexity is added only when it produces stable out-of-sample improvement and passes all hard invariants.

The primary comparison order is:

1. M0
2. M1
3. M2a
4. M2b
5. challengers M3-M6 only where their identifying experiment is mature

If two models are effectively tied out of sample, prefer the simpler model.

A challenger should not be promoted because of in-sample fit.

---

# 13. Choice-model framework

Votes are pairwise preferences.

For an FV-scale model score `Score(S)`, model voter preference as:

`P(A chosen) = logistic(beta * (Score(A) - Score(B)) / V_REF + delta_left * I(A displayed left))`

where:

- `beta > 0` is choice sensitivity
- `delta_left` is a diagnostic display-side effect
- left/right placement is randomized

For raw-utility-only diagnostics, the equivalent formulation may use `U(A)-U(B)`, but production candidate comparison should prefer a common interpretable scale whenever possible.

Primary model-comparison metric:

- held-out log loss

Secondary diagnostics:

- Brier score
- directional accuracy
- calibration
- preference-share residuals by experiment family
- left/right bias
- voter-cluster uncertainty

Voter identity must be retained for clustered inference.

---

# 14. First-wave experiment: Core 2v2 concentration ladder

The highest-information first family keeps raw side totals approximately equal and varies only value concentration.

Canonical design proportions:

- `80/20 vs 50/50`
- `70/30 vs 50/50`
- `60/40 vs 50/50`
- `55/45 vs 50/50`
- `50/50 vs 50/50` control

Illustrative values only:

- `[9000,1000] vs [5000,5000]`
- `[8000,2000] vs [5000,5000]`
- `[7000,3000] vs [5000,5000]`
- `[6000,4000] vs [5000,5000]`
- `[5500,4500] vs [5000,5000]`

The generator must use actual eligible assets from the frozen FV snapshot rather than fake displayed FV numbers.

FV remains hidden from voters.

---

# 15. Absolute-scale test

The same concentration proportions must be repeated at multiple absolute value levels.

This distinguishes:

> concentration ratio alone

from:

> concentration plus absolute elite/stud level

The absolute levels must not be hardcoded as 3000 / 6000 / 9000.

Instead, after freezing the FV snapshot:

1. enumerate feasible real-player 80/20 two-player packages;
2. compute their total-FV distribution;
3. use deterministic nearest-rank quartile locations from that feasible distribution to define:
   - low scale
   - middle scale
   - high scale
4. freeze the realized total targets in the challenge catalog before voting.

Using feasible-package quantiles makes the scale bands data-derived and reproducible rather than arbitrary.

If a cell cannot be constructed within tolerance, it is recorded as skipped. Tolerances are never loosened after seeing votes.

---

# 16. Construction tolerances

The new generator must preregister and validate construction accuracy.

Initial design targets:

- maximum absolute side-total mismatch: **2.5% of target total**
- maximum intended component-share error: **2.5 percentage points**
- no duplicated asset within a challenge
- no same player on both sides
- all asset FV must be positive
- all player FV must come from the frozen production FV snapshot
- K remains excluded

If the catalog cannot achieve adequate coverage at these tolerances, stop and review the design.

Do not silently widen tolerances.

---

# 17. Fragmentation / filler family

This family tests whether the nonlinear utility curve alone explains fragmentation or whether a separate roster/piece-count term is needed.

At the same raw total and same top-asset share, compare:

- `80/20`
- `80/10/10`
- `80/5/5/5/5`

Example proportions:

`[8000,2000]`

`[8000,1000,1000]`

`[8000,500,500,500,500]`

These values are illustrative; actual challenges use frozen production FVs.

Why this family matters:

M2 already predicts a fragmentation effect whenever:

`g(0.20) != 2*g(0.10)`

and:

`g(0.20) != 4*g(0.05)`

Therefore, a preference against extra pieces does **not automatically prove roster friction**.

M4 earns an explicit roster term only if observed preferences show a stable residual piece-count effect beyond M2's prediction.

## 17.1 Pre-freeze frozen-snapshot support decision

No NextGen V2 voting had been activated and no NextGen V2 votes had been collected when this decision was made. The generated catalog was still unreleased and `frozen: false`.

Three read-only audits were run against the same frozen player-FV and league-roster snapshot. The preregistered construction tolerances were not changed.

1. **Scale-integrity audit.** For `80/20 vs 80/5/5/5/5`, the original non-overlapping low and middle bands produced zero complete valid ballots even when the side-candidate search limit was increased from 24 to 48 to 96. The high band produced five ballots at the normal limit of 24. The `80/20 vs 80/10/10` comparison produced five ballots in all three bands at the normal limit.
2. **Joint-feasibility audit.** Of 335 component-window-feasible candidate totals for `80/20 vs 80/5/5/5/5`, only 73 were fully joint-trade constructible. All 73 were between 10,231 and 11,109 FV. Nearest-rank 25th/50th/75th percentile anchors on that true support were 10,757 / 10,891 / 11,000, a low-to-high span of only 243 FV (about 2.26%). A full 15-ballot simulation across those narrow strata used Jahmyr Gibbs in 15/15 ballots and Bijan Robinson in 15/15 ballots.
3. **Diversity-capacity audit.** At a side-candidate limit of 96, the valid candidate universe contained 463 unique full-trade signatures. Bijan Robinson appeared in 463/463. Exact mixed-integer optimization selecting five ballots proved that the minimum possible maximum player appearance was 5/5 even when exact side-package reuse was forbidden.

This is a frozen-input support limitation, not evidence about voter preference.

Therefore, for this frozen first-wave catalog:

- `80/20 vs 80/10/10` remains active at low / middle / high scale.
- `80/20 vs 80/5/5/5/5` is **deferred and inactive**. It is excluded from the voting catalog and from model fitting.
- the deferred comparison may be reconsidered only under a newly frozen asset universe (including verified production pick FV if later available) and a new preregistered support/diversity audit;
- the 2.5% side-total, component-share, and pair-total tolerances remain unchanged;
- no vote outcomes were consulted, so this is a pre-freeze design correction rather than outcome-contingent experiment editing.

---

# 18. Low-value filler stress family

A separate stress family progressively adds very low-value pieces.

Goals:

- identify whether the lower tail of `g` is sufficiently flat
- detect "death by many tiny assets" behavior
- establish the realistic production support boundary
- test solver and equivalent-value stability

The stress grid must remain within realistic roster/trade sizes.

The model is not required to make an infinite number of positive-FV assets worthless.

Instead:

> within the declared supported trade-size and FV region, filler must not create an implausible advantage that contradicts voter evidence.

Extreme synthetic cases outside real trade support are used as diagnostics, not as automatic production targets.

---

# 19. Pick-control family

This family is inactive until the production pick FV source is verified.

Required matched tests include:

1. player component vs draft pick of approximately equal FV;
2. player package vs mixed player/pick package at matched raw total and composition;
3. all-player vs all-pick package where feasible;
4. low/mid/high pick value regions if enough production picks exist.

M3 should be rejected if the separate pick curve does not produce stable held-out improvement over neutral pick treatment.

No assumed pick premium or discount is allowed.

---

# 20. Legacy-compatibility family

NextGen V2 must be tested against the already-supported production regions.

The frozen V3/V4/V5 evidence remains untouched.

Use it as:

- historical benchmark
- external validation
- fallback evidence

Do not rewrite old ballots or regenerate old challenge IDs.

A new small set of structurally equivalent current-FV 1v2 and 1v3 challenges may be generated as compatibility cells, but those rows receive new NextGen IDs and remain separate from historical evidence.

V1.6 is a benchmark, not ground truth.

A disagreement with V1.6 is not automatically wrong, but every material disagreement requires evidence and human review.

---

# 21. Structural holdout

Do not rely only on random row splitting.

The first-wave catalog must reserve entire **challenge cells/families** that are never used to fit M2.

At minimum:

### Holdout A — unseen absolute scale

Reserve one complete absolute-scale slice of the 2v2 concentration ladder.

Purpose:

- test whether the learned curve generalizes across value scale

### Holdout B — unseen topology

Reserve a 3v3 equal-total concentration family that is never used during fitting.

Candidate design proportions include:

- `60/25/15 vs 34/33/33`
- `70/20/10 vs 40/35/25`

Exact realized cells are frozen before voting.

Purpose:

- test whether standalone utility generalizes beyond the 2v2 topology used for primary fitting

### Holdout C — prospective time window

After a candidate is frozen, collect a later ballot window not used for any model selection.

Purpose:

- test genuine prospective stability

---

# 22. Sampling and voter protections

Inherit the existing research protections.

Required:

- FV hidden from voter
- display side randomized
- challenge family sampled before challenge ID
- cell sampled uniformly within family where feasible
- challenge sampled uniformly within selected cell
- voter identity retained
- timestamp retained
- current daily package-vote limit preserved unless separately reviewed
- no adaptive challenge generation based on interim results
- no changing challenge values after release
- major injury/news events must be flaggable in the evidence record
- votes after a frozen evidence timestamp are excluded from that snapshot

The release manifest must explicitly state whether any of these rules differ from V5.

---

# 23. Power / maturity plan

Do not invent a round-number vote threshold in this specification.

Before activation:

1. build the exact frozen catalog;
2. use historical package-voting participation and the realized cell count;
3. run a power / precision simulation;
4. define the evidence maturity gates;
5. commit the maturity plan and its SHA-256;
6. only then activate NextGen voting.

The maturity plan must specify:

- minimum cell coverage
- minimum distinct-voter coverage
- effective voter cap
- primary uncertainty statistic
- stopping rule
- holdout protection
- what constitutes an unresolved cell/family

The maturity gate cannot be changed after seeing NextGen vote outcomes without creating a new preregistered revision.

---

# 24. Evidence freezing

Every analysis run intended for review must freeze its input evidence.

Required artifact fields:

- `generated_at_utc`
- frozen vote cutoff timestamp
- raw ballot count
- valid ballot count
- unique voter count
- distinct challenge count
- distinct family/cell count
- canonical ballot-set SHA-256
- challenge catalog SHA-256
- model-spec SHA-256
- input FV SHA-256
- roster input SHA-256
- pick-value source SHA-256 if picks are active
- code commit SHA

Rows arriving after the cutoff are excluded.

Do not store private raw voter identifiers in public review artifacts if the existing pipeline hashes/pseudonymizes them.

---

# 25. Primary fitting and uncertainty

Primary fitting must be conducted only on the preregistered training cells.

Use voter-cluster-aware uncertainty.

At minimum report:

- point estimate
- voter-cluster bootstrap distribution
- leave-one-voter-out sensitivity
- challenge-family residuals
- display-left choice percentage
- calibration diagnostics

Where target-player dependence is meaningful, retain the V5 target-cluster bootstrap concept.

The existing V5 convention of requiring strong bootstrap stability should be preserved unless a different rule is preregistered **before activation**.

---

# 26. Challenger activation rules

Challengers do not earn complexity from in-sample fit.

## M3 pick curve

Eligible only when matched pick-control cells show a stable residual under M2 and M3 improves structural/prospective holdout performance.

## M4 roster friction

Eligible only when fragmentation/roster-count cells show stable residual preference after M2 prediction and M4 improves holdout performance without monotonicity violations.

## M5 sorted marginal utility

Eligible only when residuals under M2 are systematically associated with ordered-asset structure after FV level and concentration are controlled.

## M6 explicit concentration

Eligible only when M2 shows systematic concentration residuals on held-out equal-total cells and M6 produces stable out-of-sample improvement.

If a challenger and M2 are effectively tied, M2 wins on parsimony.

---

# 27. Hard mathematical rejection tests

A candidate is rejected regardless of predictive accuracy if any of the following occur inside its claimed support.

1. **Singleton identity failure**
   - `E({v}) != v` beyond numerical tolerance.

2. **1v1 adjustment failure**
   - a true 1-for-1 produces nonzero Package Differential.

3. **Permutation failure**
   - reordering assets changes the side score.

4. **Monotonic asset-value failure**
   - increasing an asset FV lowers the side score.

5. **Positive-addition failure**
   - adding a supported positive-FV asset lowers the side score.

6. **Piece-removal paradox**
   - removing a supported positive-FV asset raises the side score.

7. **Side-swap failure**
   - signed Package Differential does not reverse exactly when sides are swapped.

8. **Identical-side failure**
   - identical sides produce a nonzero differential.

9. **Display reconciliation failure**
   - research-only adjustment display does not reconcile exactly to EquivalentGap.

10. **Scale-normalization failure**
    - globally scaling FVs and recomputing `V_REF` under the frozen rule materially changes normalized trade ordering without explanation.

11. **Discontinuity**
    - tiny FV perturbations create large unexplainable score jumps.

12. **Runaway elite behavior**
    - fitted upper-tail behavior makes ordinary supported elite trades numerically or economically impossible to balance.

13. **Solver instability**
    - ordinary supported balancing searches fail to converge.

14. **Unsupported inverse use**
    - an out-of-domain inverse is silently extrapolated.

15. **Production leakage**
    - research execution changes FV, Market Value, Team Utility, draft-pick value, current production Package Adjustment, or Trade Verdict consumers.

---

# 28. Filler and top-end stress tests

Before any production-candidate review, run deterministic synthetic grids across the entire claimed support.

Required stress directions:

- top asset fixed, filler count increased
- top asset fixed, filler FV increased
- total FV fixed, concentration increased
- total FV fixed, concentration decreased
- same composition at low/mid/high absolute scales
- top asset moved by small FV increments
- each secondary asset moved by small FV increments
- side piece count increased
- side piece count decreased
- identical vectors with positions permuted
- player/pick type swapped when M3 is active

These tests are model-validity tests, not substitutes for human voting evidence.

---

# 29. Position handling

Baseline NextGen V2 is position-agnostic **after FV is supplied**.

Position remains part of challenge display because voters need to know the asset.

But the Package Adjustment function does not receive a position bonus/penalty in M2.

Reason:

- positional scarcity is already part of player FV/modeling
- adding it again risks double counting

Position-specific Package Adjustment behavior can be considered only if a preregistered residual test shows stable independent evidence.

K remains excluded from the initial research universe to match existing Package Adjustment research scope.

---

# 30. Balancing-player solver

The production-facing question is eventually:

> What additional asset would make the weaker side approximately even?

For a candidate side B:

`find X such that Score(B + X) = Score(A)`

For simple additive utility, an analytical inversion may sometimes exist.

However the default implementation should use **bounded binary search** because it is:

- deterministic
- easy to audit
- robust for monotonic functions
- compatible with later challenger interactions
- easy to fail closed

Requirements:

1. prove monotonicity over the search interval before solving;
2. use a bounded supported FV interval;
3. recompute the full side score at every probe;
4. stop at a preregistered FV tolerance;
5. return no solution if the supported interval cannot bracket equality;
6. never extrapolate beyond the supported asset domain;
7. map the resulting FV target to real candidate assets separately.

For a result outside the real player/pick range:

> "No single supported asset can balance this trade."

Do not fabricate a theoretical player.

---

# 31. Important 1v1 solver distinction

The **Package Adjustment itself** must remain zero for 1-for-1 because the equivalent side score has the singleton identity.

A balancing recommendation is a different question.

Adding a balancing asset changes the topology from 1v1 to 1v2, so the balancing asset needed under nonlinear utility does not have to equal the raw FV difference.

Do not use the balancing-player result to redefine the initial 1v1 Package Adjustment.

This distinction must be tested explicitly.

---

# 32. Production support philosophy

Do not define production support solely as:

- 1v2
- 1v3
- 2v2
- 2v3
- etc.

NextGen support should ultimately depend on the evidence-covered **feature region**.

Potential support coordinates include:

- piece count
- total normalized FV
- maximum normalized FV
- minimum normalized FV
- top-asset share
- second-asset share
- concentration profile
- player/pick composition
- inverse-equivalent support

A trade may be mathematically computable but still empirically unsupported.

Unsupported means:

- no NextGen production adjustment
- fall back to frozen V1.6 where V1.6 itself is supported
- otherwise raw FV / current production behavior remains

---

# 33. Production-promotion comparison

A NextGen candidate is not promoted because it is more sophisticated.

It must:

1. beat raw FV on preregistered structural holdouts;
2. remain stable on a prospective holdout;
3. show no unexplained material regression in frozen V1.6-supported regions;
4. pass every hard mathematical test;
5. pass filler and elite stress tests;
6. be reproducible from frozen inputs;
7. preserve all production consumers outside Package Adjustment;
8. have an explicit supported region;
9. have a documented fallback;
10. receive human approval.

No automatic formula promotion is permitted.

---

# 34. Model comparison reporting

Every model review artifact must show the same comparison table.

Required columns:

- model ID
- model description
- training log loss
- structural-holdout log loss
- prospective-holdout log loss when available
- Brier score
- directional accuracy
- calibration diagnostic
- voter-bootstrap stability
- V1.6-region comparison
- monotonicity pass/fail
- filler stress pass/fail
- scale test pass/fail
- inverse-support failure count
- parameter count / complexity
- support coverage
- promotion eligible: yes/no
- reason

Do not report only the winning metric.

---

# 35. First implementation phases

## Phase 0 — Freeze this specification

Deliverable:

`research/package-adjustment-nextgen-v2/package_adjustment_nextgen_v2_research_spec.md`

No code changes.

No UI changes.

No workflow changes.

## Phase 1 — Build challenge generator

One new generator file only.

Responsibilities:

- freeze input paths/hashes
- compute `V_REF`
- build core concentration cells
- build fragmentation/filler cells
- reserve structural holdout cells
- optionally build pick cells only after pick FV verification
- validate tolerances
- emit a deterministic catalog
- emit catalog diagnostics
- make no production changes

The generated catalog is reviewed before activation.

## Phase 2 — Freeze model-fit preregistration

Define exact:

- M2a parameter fit
- M2b spline parameterization
- knot rule
- regularization
- optimizer
- choice likelihood
- bootstrap procedure
- model-selection rule
- maturity/power gates
- solver tolerance

This must happen before fit-eligible votes are examined.

## Phase 3 — Activate NextGen voting

Separate reviewed activation.

Do not overwrite frozen V3/V4/V5 evidence.

Do not reuse old transport prefixes.

Do not change production formula.

## Phase 4 — Aggregate frozen evidence

Create new NextGen result artifacts only.

No production changes.

## Phase 5 — Fit M0/M1/M2

Fit baseline models first.

Run structural holdout.

Run mathematical test suite.

## Phase 6 — Challenger review

Only activate/finalize M3-M6 if their preregistered identifying evidence supports doing so.

## Phase 7 — Evidence hardening

Run:

- voter-cluster bootstrap
- target/challenge-family robustness
- leave-one-voter-out
- scale replay
- filler/elite stress grid
- V1.6 regression review

## Phase 8 — Prospective shadow candidate

If research gates pass, freeze a candidate and compute it alongside V1.6 without user-visible effect.

## Phase 9 — Human production review

Only after shadow/prospective success may a separate production-candidate specification be created.

---

# 36. File-isolation rules for implementation

When implementation begins:

- create files only under the new NextGen directory unless a separately reviewed activation step requires another path;
- do not edit historical `research/package-adjustment-v2/`;
- do not edit frozen V3/V4/V5 catalogs;
- do not edit current production formula during challenge generation;
- do not edit Market Value;
- do not edit Team Utility;
- do not edit draft-pick values;
- do not edit Trade Verdict consumers;
- do not edit `.github/workflows/` as part of a research script;
- workflow files, if later needed, are separate reviewed/manual uploads;
- every workflow must prove its changed-file scope before commit/push.

---

# 37. Required generator self-tests

Before the future challenge generator is handed off, it must pass at least:

1. Python compile.
2. Deterministic regeneration.
3. JSON parse.
4. Unique challenge IDs.
5. No duplicated player within challenge.
6. No same player on both sides.
7. Eligible-position check.
8. K exclusion.
9. Positive FV check.
10. Exact frozen FV lookup check.
11. `V_REF` recomputation check.
12. Side-total tolerance check.
13. Component-share tolerance check.
14. Family/cell coverage check.
15. Holdout leakage check.
16. Transport-marker collision check.
17. Historical-directory write-protection check.
18. Frozen V3/V4/V5 hash-protection check.
19. Production formula hash unchanged.
20. Repo regression checks.

Do not hand the file to the user until these checks pass locally against the current repository source.

---

# 38. Research decision log

The following choices are intentionally frozen as the current research direction:

### Accepted

- standalone side utility as the primary architecture
- normalized FV input
- smooth monotonic utility
- raw FV remains untouched
- 1v1 zero Package Adjustment
- 2v2 support is an empirical research target
- absolute elite level must be tested separately from concentration ratio
- M2 baseline has no explicit roster penalty
- M2 baseline treats players and picks identically until evidence says otherwise
- bounded binary search is the default balancing solver
- structural and prospective holdouts
- feature-space support / fail-closed behavior
- V1.6 remains frozen benchmark/fallback
- no automatic production promotion

### Explicitly not accepted yet

- hard "stud" thresholds
- hard filler thresholds
- negative utility for positive-FV players
- explicit roster penalty in the baseline
- automatic separate pick premium/discount
- HHI/Gini as the primary production formula
- KTC's formula as ground truth
- arbitrary 5,000-vote requirement
- arbitrary 85% accuracy requirement
- arbitrary 95% agreement requirement
- shape-by-shape production rules
- silent inverse extrapolation

---

# 39. Open research questions

The experiment must answer these, not assume them.

1. Is M2a already sufficient, or does M2b materially improve holdout prediction?
2. Does concentration premium depend only on ratios, or also on absolute FV level?
3. Can one smooth utility curve explain both elite premium and realistic filler dilution?
4. Is there residual piece-count / roster friction after M2?
5. Do draft picks combine differently from players at equal FV?
6. Are ordered-asset interactions necessary?
7. Does an explicit concentration index add anything after nonlinear utility?
8. How far can NextGen generalize to unseen topology?
9. Where should the empirical production support boundary lie?
10. Can the FV-scale equivalent mapping remain supported throughout the desired live region?

---

# 40. Definition of success for this research program

NextGen V2 succeeds if it produces a simpler and more general trade-level model that:

- predicts blinded dynasty-manager package preferences better than raw FV;
- performs at least competitively with V1.6 where V1.6 is supported;
- extends evidence-backed behavior into equal-piece-count and multi-piece trade shapes;
- preserves all individual asset values;
- remains mathematically monotonic and stable;
- resists realistic filler exploitation;
- is scale-aware;
- has explicit evidence support;
- is interpretable enough to explain in the Trade Desk;
- can fail closed safely;
- survives prospective evidence;
- can be promoted only through a separate human-reviewed production process.

Until those conditions are met:

> **V1.6 remains production. NextGen V2 remains research only.**

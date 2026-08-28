# TRADE DESK IDP PROJECTION CHECKPOINT
_Last updated: 2026-08-28 -- restructured by decision importance, not chronology, per external review_

## A. CLOSED FACTS (settled, don't re-litigate)
- FantasyPros `def_tackle` = solo tackles. `def_assist` = assisted tackles. Confirmed via full-population internal checksum (529/529 real players match FantasyPros' own stated total within 0.5 pts).
- FantasyPros TFL (`def_tlost`) is unpopulated/unusable -- literally constant 0.00 across the entire real IDP population.
- Sleeper supplies real, usable TFL and QB-hit projections that FantasyPros does not.
- Name-only FantasyPros↔Sleeper identity matching is unsafe -- confirmed via real collision cases (Myles Murphy stale-duplicate, Byron Murphy two-different-real-players).
- Identity resolution is hardened and closed: team-agreement tie-breaking, position-compatibility via Sleeper's `fantasy_positions`, global one-to-one invariant, name-normalization invariant, confirmed real JAC/JAX team alias. Real result: 469 high-confidence, 6 genuinely unresolvable (individually inspected -- real cross-provider position-classification disagreements and one roster-status ambiguity, not resolver bugs), 54 no-candidate. Reconciles exactly.
- Strict, high-confidence, both-sources-active cohort: **355 players** (LB=89, DL=128, DB=138).
- The tackle disagreement (both total volume and solo-share allocation) is real and source-wide, not archetype-specific -- confirmed in every subgroup tested, including a sack-rate-based pass-rush/off-ball split (that specific proxy has a known endogeneity limitation, doesn't undermine the broader conclusion).
- No current evidence justifies archetype-specific tackle or sack weights (DL sack agreement is strong post-cleanup: Spearman ≈0.866).

## B. CURRENT MODEL ARCHITECTURE
Two-stage tackle model, implemented in `scripts/idp_ensemble_experiment.py` (parameterized, 13 self-tests, output-only, not wired to production):
- **Stage 1**: consensus total tackles = `stage1_fp_weight × FP_total + (1-stage1_fp_weight) × Sleeper_total`
- **Stage 2**: consensus solo share = `stage2_fp_weight × FP_share + (1-stage2_fp_weight) × Sleeper_share`
- Derived solo/assist from Stage 1 × Stage 2, scored under Trade Desk's real formula (solo=1.5, assist=0.75).
- This structure (not independent solo/assist averaging) is justified because solo tackles = total opportunity × allocation share; independent averaging would produce splits neither source actually forecasts.
- Missing-source handling built in: a single-source player uses that source's real value directly, never averaged with a fake zero. Confidence field distinguishes `ensemble` / `single_source_fantasypros` / `single_source_sleeper` / `no_data`.

## C. P0 -- DOMINANT OPEN RISK: STAGE-1 TOTAL TACKLE CALIBRATION
**Real, measured magnitude** (Stage-1 weight sweep, Stage 2 held at 60/40 Sleeper-leaning, run against the real 355-player cohort):

| Stage-1 FP weight | LB median | DL median | DB median |
|---|---|---|---|
| 0% (all Sleeper) | -22.67 | -13.80 | -19.63 |
| 50% (neutral) | -0.73 | -0.48 | -0.44 |
| 100% (all FP) | +21.51 | +13.17 | +18.60 |

Full-range median swing: **LB ≈44 pts, DB ≈38 pts, DL ≈27 pts.** Individual players move far more -- Jordyn Brooks ≈76 pts, Benjamin Morrison ≈43 pts, Malcolm Roach ≈33 pts, purely from Stage-1 weight choice. This is roughly 10-40x Stage 2's own leverage.

**What this proved**: the sweep validated the model correctly interpolates and that Stage-1 choice has massive downstream consequences. **What it did NOT prove**: which weight (or which source) is actually more accurate. Leverage ≠ accuracy.

**Recommended calibration approach** (raises the evidence bar given the real stakes -- do not set from one median or one season):
1. Build real 2024 AND 2025 actual positional tackle distributions (LB/DL/DB), preferably tackles-per-game or with a minimum-participation filter so injury-shortened players don't distort the scale.
2. Compute median, 25th/75th percentile, top-12/24/36 median for each real season, and for both sources' 2026 projected distributions.
3. Require agreement across (a) both real seasons, (b) multiple quantiles not just the median, and (c) before concluding one global calibration -- check whether LB/DL/DB actually behave differently (the sweep proved different *leverage* by position, not different *accuracy*; don't assume Case E -- distribution-shape-dependent error -- without evidence).
4. **Key open architectural question, possibly bigger than the weight itself**: total-tackle rank agreement between sources is already fairly strong (LB Spearman ≈0.81, DL ≈0.69, DB ≈0.78) while absolute scale disagrees sharply. That pattern suggests the real fix might not be a blend weight at all -- it might be **source-specific positional rescaling** (calibrate each source's absolute scale to match real historical distributions first, then blend the rescaled values) rather than trying to make one blend weight solve both a scale problem and a trust-weighting problem simultaneously. Test this explicitly before assuming a simple weight is sufficient.
5. If historical evidence does support different LB/DL/DB weights, prefer shrinking toward neutral 0.5 over shipping an aggressively-fit position-specific number from a thin sample -- e.g. if a thin calibration implies 0.28 for LB, a more conservative production candidate is likely closer to 0.40, not 0.28, unless the evidence is deep and stable.

## D. P1 -- MISSING-SOURCE POLICY (depends on Stage-1 calibration, don't solve independently first)
A single-source player effectively sits at one Stage-1 extreme (Sleeper-only ≈ 0% FP weight, FantasyPros-only ≈ 100%) on the model's most economically sensitive component -- this makes getting it right more urgent, not less, once Stage 1's real leverage was measured.
- **Current placeholder** (in `idp_ensemble_experiment.py` already): use the one available source's real value directly. Confirmed via self-test this is not silently halved.
- **This should NOT become the final production rule as-is.** Correct sequence: (1) calibrate each source's positional scale via Stage-1 historical work above, (2) apply that same calibration transform to single-source players before using their raw value, (3) only then consider whether additional shrinkage toward a positional prior is warranted for single-source cases specifically.

## E. SETTLED ENOUGH / LOW LEVERAGE -- DO NOT SPEND FURTHER EFFORT HERE YET
- **Stage 2 (solo/assist allocation)**: architecture closed. Neutral baseline 50/50. Preferred experimental scenario 60% Sleeper / 40% FantasyPros, based on real N=8 historical calibration (5 LB, 2 DL, 1 DB; Sleeper closer on 7/8; median absolute error 5.55 vs 14.75 pts, ~2.7x; binomial check on 7+/8 under a fair-coin null is ~3.5% one-sided -- suggestive, not proof, given N and position imbalance). One real counter-example (Kyle Hamilton, DB) reported honestly, not excluded -- DB solo-share evidence is thin (n=1), keep 50/50 visible as the DB comparison point.
- **Real measured economic leverage of Stage 2**: median -0.50 pts at the 60/40 experimental weight, capped around -2.51 pts median even at the full 100%-Sleeper extreme. Do not spend the next block of effort tuning 60/40 toward some more precise decimal (e.g. 57/43) while Stage 1 can move individual players by dozens of points -- that would be optimizing the wrong uncertainty.

## F. NEXT EXPERIMENT (concrete, when work resumes)
Real 2024-2025 positional tackle-scale calibration for LB/DL/DB -- see Section C for the full method. This is the actual next block of work, not a vague "gather more data" placeholder.

## G. PRODUCTION HOLD -- DO NOT
- Bake new `prod_mult` values yet.
- Choose a Stage-1 weight from intuition -- use the historical calibration method above.
- Treat a missing/zero-signal source as a real zero forecast.
- Reopen the FantasyPros tackle-semantics question (closed, checksum-verified).
- Build archetype-specific tackle or sack formulas without materially stronger evidence than currently exists.
- Spend further effort fine-tuning Stage 2 before Stage-1 calibration is done -- Stage 1 is where the real risk lives.

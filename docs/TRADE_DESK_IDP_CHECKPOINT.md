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

**Historical calibration attempt #1 (leaderboard-based) -- REJECTED, real methodological flaw caught before acting on it.** Built a real 2025 league-wide tackle leaderboard (n=49 LB, n=45 DB) and found FP ratio ≈0.95-0.99, Sleeper ratio ≈0.59-0.63 vs. that sample -- looked like Sleeper was ~40% too low. External review caught a real, valid problem before this got acted on: the leaderboard sample is truncated to top tackle-producers (selection bias), compared against a much broader projection cohort (apples-to-oranges).

**Historical calibration attempt #2 (matched-player) -- REVERSES attempt #1.** Used the same 7 players (excluding Fred Warner's real but injury-shortened 6-game sample as a legitimate confound) already in the real projection cohort, with their own real 2025 season totals directly matched against their own real 2026 projections:

| | Median ratio vs. real 2025 (n=7 matched players) |
|---|---|
| FantasyPros | **1.23** (runs ~23% above real recent history) |
| Sleeper | **0.94** (close to real recent history) |

**This is the opposite conclusion from attempt #1** -- once the comparison is properly aligned (same players, not a differently-selected population), Sleeper looks well-calibrated and FantasyPros looks inflated. This directly confirms the population-mismatch critique was real, not a formality. **Current status: promising but still only n=7 -- a real, matched, but small sample.** Per external review's own standard, a properly-aligned large sample (via a real "all qualifying defenders" population, not hand-collected matched players) is the next needed step before this becomes production-actionable. Do NOT average, split the difference, or treat attempts #1 and #2 as partially-each-correct -- #1 has a real, identified flaw and should be discarded, not blended with #2.

**Recommended calibration approach** (raises the evidence bar given the real stakes -- do not set from one median or one season):
1. Build real 2024 AND 2025 actual positional tackle distributions (LB/DL/DB), preferably tackles-per-game or with a minimum-participation filter so injury-shortened players don't distort the scale.
2. Compute median, 25th/75th percentile, top-12/24/36 median for each real season, and for both sources' 2026 projected distributions.
3. Require agreement across (a) both real seasons, (b) multiple quantiles not just the median, and (c) before concluding one global calibration -- check whether LB/DL/DB actually behave differently (the sweep proved different *leverage* by position, not different *accuracy*; don't assume Case E -- distribution-shape-dependent error -- without evidence).
4. **Key open architectural question, possibly bigger than the weight itself**: total-tackle rank agreement between sources is already fairly strong (LB Spearman ≈0.81, DL ≈0.69, DB ≈0.78) while absolute scale disagrees sharply. That pattern suggests the real fix might not be a blend weight at all -- it might be **source-specific positional rescaling** (calibrate each source's absolute scale to match real historical distributions first, then blend the rescaled values) rather than trying to make one blend weight solve both a scale problem and a trust-weighting problem simultaneously. Test this explicitly before assuming a simple weight is sufficient.

**STATUS CHANGE: Stage-1 optimal-weight research moved to BACKLOG, not blocking.** Per external review: continued hand-calibration risked becoming an open-ended research project instead of actually testing whether the new architecture helps. V1 uses the defensible neutral assumption (Stage 1 = 50/50) and moves directly to the real product question below. The matched-player reversal (n=7, Section immediately above) is preserved as a real, promising lead for future validation -- not discarded, just not blocking.

## C.1. REAL PROD_MULT SENSITIVITY TEST -- RUN END-TO-END, RESULT IS CLEAN AND SENSIBLE
Using the neutral V1 assumptions (Stage 1 = 50/50, Stage 2 = 60/40 Sleeper, TFL/QB-hits = Sleeper-only, other shared categories = 50/50 consensus, single-source players use their one real source directly), computed a new `proj_2026` for all 477 real LB/DL/DB players with 2025 game history (15 players excluded -- no history_component, matching the real formula's own existing null-handling, not a new gap). Fed through the REAL `combined`/`baseline`/`ratio`/`prod_mult` formula from `prod_mult_pipeline.py`, holding `shrunk_ppg` and `durability_projected_games_2026` identical to the real existing values -- a faithful "swap just the IDP input" test, not an approximation.

**Real baselines shift modestly** (LB +3.7%, DL +4.8%, DB +3.8% -- the new formula captures real value, like TFL/QB-hits, that was previously undercounted for many players, raising the whole distribution before the ratio-based system partially renormalizes it back out).

**Real prod_mult % change by position:**
| Position | N | Median | P90 | P95 | Max | Min |
|---|---|---|---|---|---|---|
| LB | 124 | -0.9% | +9.3% | +14.6% | +36.5% | -21.3% |
| DL | 169 | +1.3% | +8.3% | +10.4% | +17.8% | -12.4% |
| DB | 184 | +0.4% | +12.9% | +16.9% | +32.9% | -22.1% |

**Median impact is small and reassuring -- the new ensemble does not produce chaos under neutral assumptions.** A real, meaningful tail exists (up to +36.5%), showing the ensemble is doing something real, not just noise.

**Real, football-sensible spot checks:**
- Bradley Chubb (LB, real known EDGE defender): **+36.5%, the single biggest riser** -- exactly the profile expected to benefit most from the new TFL/QB-hit coverage FantasyPros structurally lacks.
- Aidan Hutchinson (+5.5%), Myles Garrett (+5.1%) -- elite real pass-rushers, modest sensible gains.
- Fred Warner (-0.7%), Roquan Smith (-1.6%) -- elite real off-ball tacklers, value already well-captured by both old and new systems, appropriately near-flat.
- Fallers (Christian Izien -22.1%, Isaiah McDuffie -21.3%, etc.) are concentrated in deep/depth players, not star dynasty assets -- no disruption of elite-tier valuations.

**Conclusion: the new category-level ensemble passes the real sensitivity check.** Values move sensibly, in football-plausible directions, concentrated where the architecture predicts they should (pass-rushers gain from TFL/QB-hit coverage, off-ball tacklers stay flat), without wild instability at the median.

## C.2. FOUR FINAL VALIDATION CHECKS -- ALL CLEAN
- **Clamp/ceiling occupancy**: 0 players at the 0.15 floor or 1.55 ceiling, old or new, across all three positions. No hidden compression at either extreme.
- **Top-24 rank stability**: a handful of real top-24 players move ≥5 ranks (e.g. Rueben Bain -18 ranks in DL), but verified directly this is a real, expected, *mechanical* consequence of the DL baseline itself moving up (+4.8%) -- these specific players' own `proj_2026` is unchanged; their relative rank appropriately declined because the bar for the whole position rose from other players' improved data, not because anything about them individually changed. Confirmed by checking their raw old/new proj values directly, not assumed.
- **Single-source cohort audit**: `both`-source median +2.2%, `fp_only` -3.7%, `sleeper_only` -4.7%, `no_new_data` -4.7% (the latter two matching, both driven by the same baseline-shift mechanism). 12 of the top-50 riser/faller extremes are single-source, but all on the modest end (-5.7% to -12.4%) -- none of the truly extreme movers (Bradley Chubb +36.5%, Christian Izien -22.1%) are single-source. No evidence single-source handling is driving erratic behavior. **Real green light for the current V1 missing-source rule** (use the one available source directly, never fake-zero-average).
- **Final player value (age multiplier × POSITION_WEIGHT)**: NOT computed -- real limitation, no per-player age data cached in this sandbox. Honest reasoning for why `prod_mult` % change is likely still a faithful proxy for this specific comparison: `POSITION_WEIGHT` is fixed per position (unaffected either way), and age multiplier is a function of player age/position, not of the projection itself -- it does not change between the old and new scenarios for a given player, since only the IDP projection input was swapped. Under that reasoning, `prod_mult` % change should equal final value % change exactly for this comparison. Worth an explicit confirmation against the real age-multiplier logic before treating this as fully proven, not just assumed.

## D. MISSING-SOURCE POLICY -- VALIDATED CLEAN, V1 RULE CONFIRMED GOOD ENOUGH
Per the real single-source cohort audit in C.2: single-source players show modest, non-extreme, mechanically-explained movement, not erratic behavior. **The current V1 rule (use the one available source directly, never fake-zero-average) is confirmed good enough for V1** -- more sophisticated shrinkage (calibrating single-source values against a positional prior) moves to backlog, not required before considering a bake.

## E. SETTLED ENOUGH / LOW LEVERAGE -- DO NOT SPEND FURTHER EFFORT HERE YET
- **Stage 2 (solo/assist allocation)**: architecture closed. Neutral baseline 50/50. Preferred experimental scenario 60% Sleeper / 40% FantasyPros, based on real N=8 historical calibration (5 LB, 2 DL, 1 DB; Sleeper closer on 7/8; median absolute error 5.55 vs 14.75 pts, ~2.7x; binomial check on 7+/8 under a fair-coin null is ~3.5% one-sided -- suggestive, not proof, given N and position imbalance). One real counter-example (Kyle Hamilton, DB) reported honestly, not excluded -- DB solo-share evidence is thin (n=1), keep 50/50 visible as the DB comparison point.
- **Real measured economic leverage of Stage 2**: median -0.50 pts at the 60/40 experimental weight, capped around -2.51 pts median even at the full 100%-Sleeper extreme. Do not spend further effort tuning 60/40 toward a more precise decimal.

## F. OVERALL STATUS: V1 ARCHITECTURE CLOSED, PRODUCTION BAKE PENDING ONE ITEM
**IDP PROJECTION NORMALIZATION: CLOSED / V1 ARCHITECTURE VALIDATED.**
- Stage 1: 50/50 FP/Sleeper total tackles (neutral, optimal weight remains open -- see backlog).
- Stage 2: 60% Sleeper / 40% FantasyPros solo share.
- TFL, QB hits: Sleeper-only (FantasyPros doesn't have them).
- Sacks/INT/PD/FF/FR/def TD: 50/50 category consensus.
- Single-source players: use the one available real source directly.
- Validated end-to-end against the real `prod_mult` formula (Section C.1/C.2) -- clean, football-sensible, no clamp/compression issues, single-source behavior confirmed ordinary.

**PRODUCTION BAKE: PENDING ONE ITEM** -- explicit confirmation that `prod_mult` % change equals final value % change (the age-multiplier-is-projection-independent reasoning in C.2 is sound but not yet directly confirmed against the real age-multiplier logic). Once confirmed, ready for a production bake decision.

## G. BACKLOG -- NOT A V1 BLOCKER
- Optimal Stage-1 source weight (real, promising n=7 matched-player lead exists -- Section C -- but needs a properly large, aligned sample, e.g. via nflverse, before being production-actionable).
- Source-scale positional normalization (rescale each source to match real historical distributions, then blend -- the architecturally cleaner alternative to a single blend weight).
- More Stage-2 calibration precision.
- Advanced single-source shrinkage toward a positional prior.
- A third projection source.

## H. PRODUCTION HOLD -- DO NOT
- Bake new `prod_mult` values yet -- pending the age-multiplier confirmation in Section F.
- Reopen Stage-1 historical-calibration research as a blocker -- it's real, promising, backlogged, not gating.
- Treat a missing/zero-signal source as a real zero forecast.
- Reopen the FantasyPros tackle-semantics question (closed, checksum-verified).
- Build archetype-specific tackle or sack formulas without materially stronger evidence than currently exists.

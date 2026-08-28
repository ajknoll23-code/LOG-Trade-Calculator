# TRADE DESK IDP PROJECTION CHECKPOINT
_Last updated: 2026-08-28_

## CLOSED (settled, don't re-litigate)
- FantasyPros `def_tackle` = solo tackles. `def_assist` = assisted tackles. Confirmed via full-population internal checksum (529/529 real players match FantasyPros' own stated total within 0.5 pts).
- FantasyPros TFL (`def_tlost`) is unpopulated/unusable -- literally constant 0.00 across the entire real IDP population.
- Sleeper supplies real, usable TFL and QB-hit projections that FantasyPros does not.
- Name-only FantasyPros↔Sleeper identity matching is unsafe -- confirmed via real collision cases (Myles Murphy stale-duplicate, Byron Murphy two-different-real-players).
- Hardened identity resolver is required and built: team-agreement tie-breaking, position-compatibility corroboration via Sleeper's `fantasy_positions`, global one-to-one invariant, name-normalization invariant, confirmed real JAC/JAX team alias.
- Real hardened result: 469 high-confidence matches, 6 genuinely unresolvable (inspected individually -- 4 are a real cross-provider LB/DE position-classification disagreement pattern, 1 is the reverse, 1 is a free-agency roster-status ambiguity), 54 no-candidate. Reconciles exactly (469+6+54=529).
- Strict, high-confidence, both-sources-active cohort: **355 players** (LB=89, DL=128, DB=138).
- The main tackle disagreement is real and source-wide, not archetype-specific. FantasyPros projects both (1) more total tackle volume and (2) a higher solo share than Sleeper, across LB/DL/DB, confirmed in every subgroup tested (including a sack-rate-based pass-rush vs. off-ball split -- though that specific proxy has a known endogeneity limitation, see OPEN below).
- No current evidence justifies archetype-specific tackle weights.
- No current evidence justifies archetype-specific sack weights (DL sack agreement is strong post-cleanup: Spearman ≈0.866).

## CURRENT MODEL PLAN
**Stage 1 (total tackle opportunity):** consensus = 50% FantasyPros + 50% Sleeper total tackles (solo+assist summed).
**Stage 2 (solo/assist allocation):** consensus = 50% FantasyPros + 50% Sleeper solo share.
Derive solo/assist from Stage 1 × Stage 2, then score under Trade Desk's real formula (solo=1.5, assist=0.75).
This two-stage structure (not independent solo/assist averaging) is justified because solo tackles = total opportunity × allocation share, and independent averaging would produce splits neither source actually forecasts.

## HISTORICAL CALIBRATION (real, external, verified -- N=8, decisive)
| Player | Pos | 2025 real solo_share | Sleeper 2026 proj | FP 2026 proj | Sleeper error | FP error | Closer |
|---|---|---|---|---|---|---|---|
| Fred Warner | LB | 54.9% | 55.7% | 66.6% | 0.8 | 11.7 | Sleeper |
| Roquan Smith | LB | 58.5% | 55.4% | 64.4% | 3.1 | 5.9 | Sleeper |
| Carson Schwesinger | LB | 42.9% | 48.2% | 62.0% | 5.3 | 19.1 | Sleeper |
| Akeem Davis-Gaither | LB | 43.6% | 50.9% | 61.4% | 7.3 | 17.8 | Sleeper |
| Troy Dye | LB | 48.3% | 54.1% | 69.3% | 5.8 | 21.0 | Sleeper |
| Jeffery Simmons | DL | 58.2% | 57.7% | 62.3% | 0.5 | 4.1 | Sleeper |
| Travis Jones | DL | 42.6% | 51.0% | 65.9% | 8.4 | 23.3 | Sleeper |
| Kyle Hamilton | DB | 56.2% | 72.1% | 67.5% | 15.9 | 11.3 | **FantasyPros** |

**Sleeper closer on 7/8. Median absolute error: Sleeper 5.55 pts, FantasyPros 14.75 pts (~2.7x).** This clears the review's own stated threshold for testing an experimental Stage-2 lean (their example: "7 of 10 with materially lower median error" → test something like 55/45). One real counter-example (Kyle Hamilton, a DB) reported honestly, not excluded -- worth noting DB may behave differently than LB/DL, sample too small (n=1) to say more.

## TACKLE ENSEMBLE PROTOTYPE -- BUILT, OUTPUT-ONLY, NOT LIVE
Built and run against the real 355-player cohort (354 with both totals >0):
- **Scenario A (neutral baseline)**: Stage 1 = 50/50 FP/Sleeper total tackles, Stage 2 = 50/50 FP/Sleeper solo share.
- **Scenario B (experimental)**: Stage 1 unchanged (50/50 -- no real volume-calibration evidence yet, and the review specifically cautioned 2025 actuals are a weaker anchor for 2026 volume than for solo-share allocation, since roles/rookies/injuries shift volume more than allocation tendency). Stage 2 = 60/40 Sleeper-leaning, per the real N=8 evidence.
- **Real point impact of the Stage-2 lean**: median -0.50 pts, max range roughly -1.8 to +0.9 pts per player at the tested 60/40 weight.
- **Full-swing upper bound** (Stage 2 = 100% Sleeper): median -2.51 pts, max range -9.03 to +4.43. Even at the extreme, this is a secondary lever.
- **Honest conclusion**: Stage 2 (solo/assist allocation) has real but modest direct point leverage. Stage 1 (total tackle volume, ~1.5-1.8x real gap between sources, established earlier but NOT historically calibrated) is likely the much bigger driver of final trade-value impact and hasn't been touched by this prototype yet.

Files: `ensemble_baseline_5050.json`, `ensemble_experimental_sleeper_lean.json` (in the working sandbox, not yet delivered as a repo pipeline).

## KNOWN OPEN LIMITATIONS
- The sack-rate-based archetype proxy has a real endogeneity problem (Sleeper's own tackle count appears in both the grouping variable and the measured outcome ratio) -- the "tackle disagreement is broad, not archetype-specific" finding is directionally supported but not airtight. An independent role classifier would be needed to fully settle it, and isn't necessary for V1.
- `weeks_with_projection_data` in the Sleeper pipeline output is known-bad metadata (shows 18 for every single row, including totally stale players) -- not blocking, but should eventually be replaced with `weeks_with_nonzero_projection_signal`.
- Missing-source policy for the ensemble is not yet designed: a source with zero/no signal must NOT be treated as a real zero forecast and averaged in directly. Needs explicit abstention handling (use available source + stronger shrinkage), not `(value + 0) / 2`.

## NEXT ANALYTICAL STEP (when work resumes)
1. Stage 1 (total tackle volume) sensitivity/calibration -- likely the bigger real lever, not yet tested with historical anchoring (and the review cautioned 2025 actuals are a weaker anchor here than for Stage 2, given real season-over-season volume drivers like role/injury/rookie churn).
2. Design the missing-source/abstention policy before running any sensitivity test.
3. Run a `prod_mult` sensitivity test comparing the new raw-category ensemble (both Scenario A and B) against the current projection blend -- median change, large movers, position-level effects.
4. Only after reviewing sensitivity results: decide whether anything gets baked into live values.
5. Formalize the tackle ensemble prototype as a real, self-tested, committed pipeline script (currently exists only as sandbox analysis, not delivered to the repo).

## DO NOT
- Bake new `prod_mult` values yet.
- Treat a missing/zero-signal source as a real zero forecast.
- Reopen the FantasyPros tackle-semantics question (closed, checksum-verified).
- Build archetype-specific tackle or sack formulas without materially stronger evidence than currently exists.

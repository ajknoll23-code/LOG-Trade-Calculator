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

## HISTORICAL CALIBRATION (real, external, verified -- but small sample)
| Player | 2025 real solo_share | Sleeper 2026 projected | FantasyPros 2026 projected |
|---|---|---|---|
| Fred Warner (6 games, injury-shortened) | 54.9% | 55.7% | 66.6% |
| Roquan Smith (15 games, ~full season) | 58.5% | 55.4% | 64.4% |

**Interpretation:** N=2 directional evidence favors Sleeper's solo-share calibration (both players: Sleeper close to real, FantasyPros consistently 6-11pts higher than real). **Not enough to change the 50/50 production baseline.** Treat as a tiebreaker/design constraint, not a weight-setting rule, until a larger sample (~8-10 players) is checked.

## KNOWN OPEN LIMITATIONS
- The sack-rate-based archetype proxy has a real endogeneity problem (Sleeper's own tackle count appears in both the grouping variable and the measured outcome ratio) -- the "tackle disagreement is broad, not archetype-specific" finding is directionally supported but not airtight. An independent role classifier would be needed to fully settle it, and isn't necessary for V1.
- `weeks_with_projection_data` in the Sleeper pipeline output is known-bad metadata (shows 18 for every single row, including totally stale players) -- not blocking, but should eventually be replaced with `weeks_with_nonzero_projection_signal`.
- Missing-source policy for the ensemble is not yet designed: a source with zero/no signal must NOT be treated as a real zero forecast and averaged in directly. Needs explicit abstention handling (use available source + stronger shrinkage), not `(value + 0) / 2`.

## NEXT ANALYTICAL STEP (when work resumes)
1. If a small block of time is available: check 5-8 more real players (systematically selected: ~3 LB, ~2-3 DL, ~2-3 DB, mixed tackle volume, not cherry-picked) the same lightweight way (real external stats vs. 2026 projections). If Sleeper is closer on ~7+/10 with a materially lower median error, test an experimental Stage-2 lean (e.g. 55/45 toward Sleeper) as a scenario, not production truth. If it comes back closer to 5/5, keep 50/50.
2. Build the tackle ensemble prototype, output-only, with neutral 50/50 weights on both stages -- don't wait indefinitely for more calibration evidence. Preserve all source components in the output so adjusting the weights later is trivial.
3. Design the missing-source/abstention policy before running any sensitivity test.
4. Run a `prod_mult` sensitivity test comparing the new raw-category ensemble against the current projection blend -- median change, large movers, position-level and (with appropriate caveats) archetype-level effects.
5. Only after reviewing sensitivity results: decide whether anything gets baked into live values.

## DO NOT
- Bake new `prod_mult` values yet.
- Treat a missing/zero-signal source as a real zero forecast.
- Reopen the FantasyPros tackle-semantics question (closed, checksum-verified).
- Build archetype-specific tackle or sack formulas without materially stronger evidence than currently exists.

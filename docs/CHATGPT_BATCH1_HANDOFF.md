# ChatGPT Batch 1 Handoff — Repo Hygiene / Correctness Fixes

**Date:** 2026-08-28
**Basis:** Full repo snapshot `LOG_Calculator_FIles.zip`
**Scope:** Only the six isolated cleanup/correctness tasks agreed before Claude resumes core production integration.

## Important boundary

This batch **does not**:
- change the approved IDP V1 model assumptions;
- implement the canonical full IDP V1 production pipeline;
- restore the missing durability pipeline;
- rewire `prod_mult_pipeline.py`;
- bake new `PROD_MULT_DATA` values;
- change Stage-1/Stage-2 weights.

Those remain for the later core integration phase.

---

## 1. `snapshot_values.py` parity repair

### Changed
`scripts/snapshot_values.py`

The snapshot tool now parses the current valuation configuration/data directly from `index.html`:
- `POSITION_WEIGHT`
- `AGE_CURVE`
- `ROLE_MULT`
- `PROD_MULT_DATA`
- `NO_REAL_PRODUCTION_HISTORY`
- `PLAYER_DB`
- `QB_POST_PEAK_FLOOR`
- `LB_POST_PEAK_DECAY_POWER`

Its Python port now matches the current live behavior for:
- lineage-gated production-floor rescue;
- continuous pre-peak production-scaled floor;
- RB youth-premium logic;
- QB post-peak floor;
- LB sqrt post-peak decay;
- current position weights;
- JavaScript `Math.round()` semantics (important: Python `round()` differs on .5 ties).

### Validation
`repo_regression_checks.py` executes the **actual live JS valuation functions extracted from `index.html` in Node** and compares them with the Python snapshot implementation.

Result:
```text
565 PLAYER_DB players
0 final-value differences
0 prod_mult differences
0 age_mult differences
```

---

## 2. `sync_sleeper.py` dual-position repair

### Changed
`scripts/sync_sleeper.py`

Removed the retired rule that selected the eligible position with the highest `POSITION_WEIGHT`.

Current rule now matches the live frontend convention:
```text
collapse Sleeper fantasy_positions in original order
→ first unique Trade Desk bucket is primary
```

Added to each generated free-agent row:
- `fantasy_positions`
- `eligible_buckets`

Added `--selftest`.

### Regenerated
`data/free_agents.json`

Count stayed exactly:
```text
2021 free agents
```

46 dual-eligible free agents changed position bucket under the corrected rule, e.g.:
```text
Trevis Gipson        LB -> DL
John Franklin-Myers  LB -> DL
Tavius Robinson      LB -> DL
Azeez Ojulari        LB -> DL
DJ Wonnum            LB -> DL
```

These are expected corrections from the retired economic-position rule.

---

## 3. Dual-eligibility audit cleanup

### Changed
`scripts/dual_eligibility_pipeline.py`

The script no longer emits a highest-weight `recommended_bucket`.

It is now an eligibility/integrity audit and reports:
- ordered `eligible_buckets`;
- `sleeper_primary_bucket`;
- current Trade Desk position when identity is safe;
- whether the current Trade Desk position is still Sleeper-eligible;
- name-collision flag;
- manual-review flag.

Normalized-name collisions are explicitly guarded: the script will not compare a Trade Desk position to a Sleeper row when multiple Sleeper people share the same normalized name.

It also surfaces single-position players whose current Trade Desk position is no longer Sleeper-eligible.

### Regenerated
`scripts/dual_eligibility_results.json`

Current local Sleeper cache produces:
```text
283 review rows
2 unique-name current-position mismatches
```

Those two are:
```text
James Pearce  Trade Desk LB -> Sleeper eligible [DL]
Travis Hunter Trade Desk WR -> Sleeper eligible [DB]
```

**No automatic PLAYER_DB change was made.** Travis Hunter is an obvious special two-way/manual-review case, so this batch intentionally surfaces the mismatch rather than guessing.

---

## 4. Team identity/mapping fixes

### Changed
`scripts/team_field_refresh_pipeline.py`

The refresh output is now stable-ID-first:
- `teams_by_sleeper_id` = canonical mapping;
- `teams` = normalized-name fallback only when collision-safe;
- `name_collisions` = ambiguous normalized names that must not be guessed.

The old behavior silently overwrote normalized-name collisions.

Synthetic collision self-test includes two active Byron Murphy rows on different teams.

### Regenerated
`scripts/player_team_refresh.json`

Current cache:
```text
3249 active Sleeper-ID team mappings
3215 collision-safe normalized-name fallbacks
13 ambiguous active normalized names
```

### Changed
`index.html`

Added `resolveSyncedTeam(p, key, existing)` and changed both live roster merge paths to use:
```text
1. live ID-resolved p.team from sync_sleeper output
2. existing curated PLAYER_DB team
3. legacy PLAYER_TEAM normalized-name fallback
```

This prevents a name collision in the legacy baked table from overriding a fresh ID-resolved team.

---

## 5. Stale PROD_MULT aliases + KTC position mapping cleanup

### PROD_MULT
Removed 24 stale abbreviated `PROD_MULT_DATA` entries when both the abbreviation and canonical key existed.

Examples:
```text
j greenard       -> jonathan greenard
k thibodeaux     -> kayvon thibodeaux
a st brown       -> amonra st brown
jsmithnjigba     -> jaxon smithnjigba
```

`check_no_duplicate_prod_mult_keys.py` now passes:
```text
823 PROD_MULT_DATA entries
30 known aliases checked
0 stale duplicate pairs
```

None of the 24 removed abbreviation keys are current `PLAYER_DB` keys, so this cleanup does not remove a current canonical player valuation.

### KTC
Added:
`scripts/generate_player_positions.py`

`player_positions.json` is no longer manually maintained. It now contains, in precedence order:
1. all 565 canonical current `PLAYER_DB` positions;
2. safe historical aliases mapped to the canonical player's position;
3. collision-safe active Sleeper fallback positions for historical KTC-rated players no longer in `PLAYER_DB`.

Canonical rows can never be overwritten by aliases/fallbacks.

Current output:
```text
565 canonical PLAYER_DB positions
2056 safe compatibility/fallback lookups
0 currently rated KTC players without a position lookup
```

Changed `ktc_pipeline.py` to hard-fail if `player_positions.json` is stale relative to the deterministic generator, and to report any truly unmapped position names explicitly.

Changed `github-workflows/ktc-vote-aggregation.yml` to regenerate `player_positions.json` before aggregation and commit it with ratings.

---

## 6. Regression tests / invariants

### Added
`scripts/repo_regression_checks.py`

Current six check groups:
1. snapshot Python vs actual live JS valuation parity for all 565 players;
2. first-listed position rule + free-agent/roster invariants;
3. eligibility audit and known current manual-review cases;
4. stable-ID team mapping + collision exclusion + live team precedence;
5. stale PROD_MULT alias guard + canonical/compatibility KTC positions;
6. `index.html` JavaScript syntax.

### Added
`github-workflows/repo-regression-checks.yml`

Read-only workflow; manual or PR trigger. Runs focused self-tests and the regression suite. Does not commit generated output.

---

# Test results

All of the following passed on the patched repo:

```text
snapshot_values.py --selftest
sync_sleeper.py --selftest
dual_eligibility_pipeline.py --selftest
team_field_refresh_pipeline.py --selftest
generate_player_positions.py --selftest
resolve_fantasypros_sleeper_identity.py --selftest
idp_ensemble_experiment.py --selftest
repo_regression_checks.py
```

Repository-wide static checks:
```text
31 Python files compile
28 JSON files parse
18 workflow YAML files parse
index.html inline JavaScript syntax passes
free-agent-board.html inline JavaScript syntax passes
```

Focused regression result:
```text
ALL REPO REGRESSION CHECKS PASSED (6 groups)
```

---

# Intentionally unresolved / do not silently auto-fix

## Position manual-review cases
Current cache exposes:
```text
James Pearce  LB -> Sleeper DL only
Travis Hunter WR -> Sleeper DB only
```

This batch does not auto-change either. Review explicitly before touching `PLAYER_DB`.

## Core P0 production plumbing remains open
From the full repo audit, still not handled in this batch:
- missing `durability_pipeline.py` / `durability_results.json` reproducibility;
- complete committed category-level V1 IDP projection output;
- `prod_mult_pipeline.py` still using the old final-points blend instead of canonical V1 ensemble;
- production pipeline still needs hardened cross-source identity integration;
- actual production bake remains on hold.

## Free Agent Board drift remains open
`free-agent-board.html` still duplicates/stales the valuation engine. Not touched in this batch to keep scope controlled.

---

# Recommended Claude next step

Review this batch as an isolated correctness patch first. Do **not** reopen the statistical model research.

Suggested review order:
```text
1. git/apply the supplied patch on the exact original repo snapshot
2. run scripts/repo_regression_checks.py
3. inspect the two manual-review position cases
4. accept/adjust Batch 1
5. only then move to the P0 production-plumbing work from the full repo audit
```

The Batch 1 code was intentionally kept away from Stage-1/Stage-2 model assumptions and from the actual production bake.

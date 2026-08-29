# Trade Desk — ChatGPT Solo Development Checkpoint

**Started:** 2026-08-28  
**Reason:** Claude usage temporarily/weekly exhausted. ChatGPT is the active code implementer until the user explicitly brings Claude back into the coding loop.

## Working Baseline

This working tree was constructed from:

1. The original uploaded repository ZIP: `LOG_Calculator_FIles.zip`.
2. ChatGPT Batch 1 cleanup patch, previously reviewed by Claude and approved in substance.
3. Claude's latest corrected `bake_idp_ensemble_v1.py` with the E.J. Speed source-presence/source-activity fix.
4. Claude's `bake-idp-ensemble-v1.yml` workflow.
5. The two durability files the user later supplied from the real GitHub repo:
   - `scripts/durability_pipeline.py`
   - `scripts/durability_results.json`

The previously generated candidate V1-baked `index.html` is **not** treated as final production truth. The immutable pre-V1 production comparison baseline remains the original repo's live canonical `PROD_MULT_DATA` values (with Batch 1's redundant alias removals treated as cleanup, not a model change).

## Current Technical State

### Closed / confirmed

- Batch 1 regression suite passes.
- Snapshot valuation parity with live `index.html`: 565/565 exact.
- Dual-position sync highest-economic-weight bug fixed.
- Team identity/name-collision hardening applied.
- 24 stale `PROD_MULT_DATA` aliases removed.
- KTC canonical position coverage repaired.
- E.J. Speed source-presence-vs-source-activity bug confirmed and fixed.
- Durability files were not actually missing from the real GitHub repo; they were omitted from the first ZIP upload. The missing-durability audit finding is closed.
- With the durability files restored, `prod_mult_pipeline.py` runs end-to-end.

### Still open

- The legacy `prod_mult_pipeline.py` still does **not** reproduce the actual pre-V1 live `PROD_MULT_DATA` table and remains diagnostic only.
- The preferred first-release V1 migration, **model-delta transport**, has now been applied to the controlled production `index.html` working tree and passed the final true-live deployment audit. It is ready for GitHub upload.
- A separate historical position-lineage migration remains backlog: 46 live IDP keys have legacy production-position grouping that differs from current canonical valuation position. This is intentionally isolated from V1 rather than silently corrected in the same release.
- Durability weighting methodology remains backlog and is deliberately unchanged for V1.

## Current Validation Snapshot

Batch 1 regression suite:

```text
PASS snapshot/live valuation parity: 565 players, 0 differences
PASS position/free-agent invariants: 2021 free agents, 0 roster overlap
PASS eligibility audit: 2 current-position mismatches surfaced for manual review
PASS team identity: normalized-name collisions safely excluded
PASS alias/KTC position integrity
PASS index.html inline JavaScript syntax
```

Fresh legacy `prod_mult_pipeline.py` run after restoring durability:

```text
Runs successfully end-to-end.
Generated prod_mult players: 1001

Current replacement baselines:
QB18  242.85
RB32  176.23
WR36  154.31
TE15  129.61
DL32  132.00
LB32  184.15
DB32  156.16
```

But versus the actual canonical pre-V1 live table:

```text
695 overlapping generated/live keys
58 exact matches
median absolute prod_mult difference ~0.034
P95 absolute difference ~0.183
max absolute difference ~0.340
```

This proves the lineage drift is real and is not caused merely by the previously omitted durability files.

## Development Rule While Claude Is Out

Until the user explicitly changes this:

- ChatGPT may write/modify code.
- Changes should be small, testable batches.
- No production value bake should be treated as final without an explicit true-live old -> candidate validation.
- Do not reopen Stage-1 statistical calibration as a V1 blocker.
- Preserve the validated V1 assumptions unless new evidence reveals an implementation error.
- Every created/changed file must be recorded below for later Claude Project Knowledge handoff.

# File Change Manifest

This is the cumulative list of files created or modified relative to the user's original ZIP. Keep this section updated after every ChatGPT development batch.

## ChatGPT Batch 1 — already completed / Claude reviewed

### Modified

- `data/free_agents.json`
- `github-workflows/ktc-vote-aggregation.yml`
- `index.html`
- `scripts/dual_eligibility_pipeline.py`
- `scripts/dual_eligibility_results.json`
- `scripts/ktc_pipeline.py`
- `scripts/player_positions.json`
- `scripts/player_team_refresh.json`
- `scripts/snapshot_values.py`
- `scripts/sync_sleeper.py`
- `scripts/team_field_refresh_pipeline.py`

### Created

- `docs/CHATGPT_BATCH1_HANDOFF.md`
- `github-workflows/repo-regression-checks.yml`
- `scripts/generate_player_positions.py`
- `scripts/repo_regression_checks.py`

## Files supplied by user after initial ZIP and restored into working repo

### Created/restored

- `scripts/durability_pipeline.py`
- `scripts/durability_results.json`

## Claude files incorporated before ChatGPT solo development

### Created/restored

- `scripts/bake_idp_ensemble_v1.py`
- `github-workflows/bake-idp-ensemble-v1.yml`

## ChatGPT Solo Development

### Created

- `docs/CHATGPT_SOLO_CHECKPOINT_2026-08-28.md`
- `scripts/idp_v1_projection.py` — canonical pure V1 IDP projection math + source-signal helpers + self-tests.
- `scripts/extract_prod_mult_snapshot.py` — extracts the actually baked `PROD_MULT_DATA` table from `index.html`.
- `scripts/prod_mult_pre_v1_baseline.json` — immutable canonical pre-V1 baked baseline (823 post-alias-cleanup canonical entries).
- `scripts/audit_prod_mult_lineage.py` — compares current legacy generator output with the immutable baked baseline.
- `scripts/prod_mult_lineage_audit.md` — human-readable lineage drift report.
- `scripts/prod_mult_lineage_audit.json` — machine-readable lineage drift report.
- `scripts/idp_v1_live_anchored_candidate.py` — diagnostic candidate generator that anchors to real live values and applies V1 projection deltas without editing production.
- `scripts/idp_v1_live_anchored_candidate.json` — diagnostic candidate output.
- `scripts/idp_v1_live_anchored_report.md` — diagnostic true-live old -> candidate report.

### Modified

- `scripts/bake_idp_ensemble_v1.py` — V1 math moved to the canonical `idp_v1_projection.py` module so bake/analysis implementations cannot drift; existing external wrapper preserved.
- `scripts/repo_regression_checks.py` — added canonical V1 projection self-tests and immutable baseline-snapshot integrity as a seventh regression group.

### Generated during analysis but intentionally NOT retained as a knowledge/source file

- `scripts/prod_mult_pipeline_output.json` — regenerated temporarily to audit lineage, then removed from the working tree because it is a generated artifact and remains non-canonical.
- `scripts/idp_bake_report.md` — temporary bake diagnostic, then removed.

## ChatGPT Solo Batch 2 Results

### Canonical V1 projection logic hardened

The V1 projection formula now distinguishes three concepts that the prior bake script conflated:

```text
source row exists
!= source has meaningful V1 projection signal
!= source has positive tackle projection
```

Current real data is unchanged by the refactor: all 469 high-confidence matched defenders produce identical V1 projections to Claude's corrected script. Source cohorts remain:

```text
354 both active
108 FantasyPros-only
  1 Sleeper-only (E.J. Speed)
  6 no new data
```

New future-proof regression cases cover:

```text
FP row present but inactive / Sleeper active (E.J. Speed = 95.43)
no source signal -> preserve old projection
zero tackles + nonzero FP sacks
zero tackles + nonzero Sleeper PD
```

### Immutable true-live baseline captured

`prod_mult_pre_v1_baseline.json` contains 823 canonical baked `PROD_MULT_DATA` values after removal of 24 redundant alias entries. It records the source `index.html` SHA256 and is deliberately separate from generated lineage JSON.

### Legacy lineage drift formally quantified

Fresh legacy generator vs true baked baseline:

```text
823 live canonical entries
1125 generated player records
813 overlapping keys
695 overlap with generated prod_mult
58 exact matches
median absolute drift 0.0339
P90 absolute drift 0.1328
P95 absolute drift 0.1806
max absolute drift 0.3399
```

This confirms that restoring durability solves clean execution, but not historical parity.

### Live-anchored V1 candidate explored — DIAGNOSTIC ONLY

A conservative candidate method was implemented to test whether V1 projection deltas can be applied while preserving the actual historical live table. It does **not** edit `index.html`.

The first diagnostic shows plausible major-player behavior (e.g. Bradley Chubb lands essentially on Claude's candidate) but also reveals that replacement-baseline normalization is itself part of the historical lineage mismatch. Therefore this candidate is **not approved for production yet**. It exists to make the remaining problem measurable rather than speculative.

### Regression suite now

```text
PASS snapshot/live valuation parity
PASS position/free-agent invariants
PASS dual-eligibility audit
PASS team identity
PASS alias/KTC position integrity
PASS canonical IDP V1 projection + immutable baseline invariants
PASS index.html JavaScript syntax

ALL REPO REGRESSION CHECKS PASSED (7 groups)
```

## ChatGPT Solo Batch 3 — Canonical History + V1 Lineage Bridge

### Closed / accomplished

- Extracted the existing history-side math into `scripts/production_history_component.py` without recalibration.
- Generated `scripts/production_history_components.json` as the canonical history-side artifact.
- Refactored legacy `prod_mult_pipeline.py` to call the canonical history module.
- Proved exact legacy-refactor parity: **1125/1125 player records**, full JSON structural equality, identical baselines and prod_mult outputs.
- Built four explicit V1 migration candidates and compared them through the actual Trade Desk value engine.
- Rejected full canonical absolute recomputation for the first V1 release because it bundles historical lineage drift and creates excessive rank/value movement.
- Selected **model-delta transport** as the preferred first-release bridge.
- Built a safe preview-only production patch generator; production `index.html` remains byte-identical to Batch 2.
- Blocked the old direct bake script from normal execution and converted legacy write workflows to read-only diagnostics.
- Added a read-only V1 candidate validation workflow.
- Expanded repository regression coverage from 7 to **9 groups**.

### Preferred model-delta transport

The bridge computes an internally consistent old and V1 model on the same reproducible cohort, including each model's rank-32 replacement baseline, then transports only the resulting prod_mult delta onto the **actual pre-V1 live** value.

```text
Comparable old/new model cohort: 330 / 404 live IDP keys
Exact holds with no defensible old comparison: 74

Internal replacement-baseline movement:
LB +3.4%
DL +4.4%
DB +3.4%
```

Known raw PROD_MULT anchors:

```text
Bradley Chubb      +35.8%
Aidan Hutchinson    +6.2%
Myles Garrett       +5.8%
Fred Warner         -0.4%
Roquan Smith        -1.3%
E.J. Speed          -5.7%
Isaiah McDuffie    -25.8%
```

These closely reproduce the shape of the earlier validated V1 sensitivity test while anchoring to the true live pre-V1 table instead of stale generated lineage.

### Final-value validation through the real value engine

```text
Median final Trade Desk value movement:
LB -0.9%
DL +3.3%
DB +0.2%

P95 final-value movement:
LB +2.5%
DL +8.2%
DB +5.2%

Top-24 movers >=5 positional ranks:
LB 1
DL 4
DB 1

Top-36 movers >=5 positional ranks:
LB 1
DL 7
DB 2
```

### Preferred bake preview

`scripts/prepare_idp_v1_bake.py` is preview-only by default and refuses to proceed unless current `index.html` still matches the immutable pre-V1 baseline.

Original Batch 3 preview (before final deployment-only threshold review):

```text
404 live IDP candidate keys
324 projected PROD_MULT changes
80 exact holds
```

Batch 4 final-value validation found a no-history role-floor discontinuity affecting four speculative LBs. Those four are now protected by a migration-specific exact-hold guard, producing the final approved deployment of **320 raw PROD_MULT changes / 84 exact holds**. See the Batch 4 section below.

### Historical position-lineage separation

Final review surfaced **46** live IDP keys where legacy production position differs from current canonical valuation position; 42 are primarily legacy LB -> current DL EDGE classifications.

For V1 release attribution, the old-vs-new model bridge deliberately preserves the legacy production-position grouping while final player value/rank validation continues to use current `PLAYER_DB` valuation positions. The regression suite now hard-guards this 46-player mismatch cohort so it cannot change silently.

This is a **separate backlog migration**, not a V1 blocker.

### Final Batch 3 validation

```text
Repo regression suite: 9/9 groups PASS
Python AST: 44 files, 0 errors
JSON parse: 40 files, 0 errors
YAML parse: 20 workflows, 0 errors
index.html JavaScript: PASS
free-agent-board.html JavaScript: PASS
legacy history refactor parity: EXACT
production index.html unchanged vs Batch 2: EXACT / byte-identical
prod_mult_pipeline_output.json retained: NO
idp_bake_report.md retained: NO
```

## ChatGPT Solo Batch 3 File Manifest

### Modified

- `docs/CHATGPT_SOLO_CHECKPOINT_2026-08-28.md`
- `github-workflows/bake-idp-ensemble-v1.yml`
- `github-workflows/prod-mult-pipeline.yml`
- `scripts/bake_idp_ensemble_v1.py`
- `scripts/idp_v1_live_anchored_candidate.py`
- `scripts/idp_v1_live_anchored_report.md`
- `scripts/prod_mult_pipeline.py`
- `scripts/repo_regression_checks.py`

### Created

- `docs/CHATGPT_SOLO_BATCH3_V1_LINEAGE_BRIDGE.md`
- `github-workflows/idp-v1-candidate-validation.yml`
- `scripts/production_history_component.py`
- `scripts/production_history_components.json`
- `scripts/idp_v1_production_candidate.py`
- `scripts/idp_v1_production_candidate.json`
- `scripts/idp_v1_production_candidate_report.md`
- `scripts/idp_v1_isolated_projection_candidate.py`
- `scripts/idp_v1_isolated_projection_candidate.json`
- `scripts/idp_v1_isolated_projection_candidate_report.md`
- `scripts/idp_v1_projection_only_candidate.py`
- `scripts/idp_v1_projection_only_candidate.json`
- `scripts/idp_v1_projection_only_candidate_report.md`
- `scripts/idp_v1_model_delta_transport_candidate.py`
- `scripts/idp_v1_model_delta_transport_candidate.json`
- `scripts/idp_v1_model_delta_transport_candidate_report.md`
- `scripts/validate_idp_v1_candidates.py`
- `scripts/idp_v1_candidate_comparison.json`
- `scripts/idp_v1_candidate_comparison_report.md`
- `scripts/prepare_idp_v1_bake.py`
- `scripts/idp_v1_prod_mult_patch.json`
- `scripts/idp_v1_prod_mult_patch_report.md`
- `scripts/idp_v1_index_preview.patch`

## ChatGPT Solo Batch 4 — IDP V1 Production Bake

### Critical final-release interaction caught

The first controlled apply exposed a live-value discontinuity that was invisible in raw-prod_mult-only reporting.

Four current speculative LBs had zero real 2025 games and a pre-V1 raw multiplier of exactly 0.15. The live value engine rescues that exact-floor/no-history state to the role estimate (0.22). Tiny positive V1 raw changes just above 0.15 would have disabled that rescue and caused large final-value drops.

Guarded players:

```text
Jaishawn Barham
Jake Golday
Kaleb Elarms-Orr
Kyle Louis
```

A migration-specific guard now holds those four raw values at 0.15 unless V1's transported multiplier actually clears their role estimate. This does not change `productionMultiplier()` globally and avoids bundling an unvalidated threshold behavior into V1.

### Final approved deployment

```text
404 candidate IDP keys
320 raw PROD_MULT changes
84 exact holds
4 floor-rescue discontinuity guards
0 non-IDP final-value changes
```

Internal V1 baseline movement remains:

```text
LB +3.4%
DL +4.4%
DB +3.4%
```

True pre-V1 live -> final deployed Trade Desk values:

```text
LB median -0.5%   P95 +2.5%   min -6.5%   max +23.9%
DL median +3.3%   P95 +8.2%   min -12.6%  max +13.4%
DB median +0.2%   P95 +5.2%   min -7.1%   max +44.5%
```

Top-rank stability:

```text
Top-24 movers >=5 ranks: LB 1 / DL 4 / DB 1
Top-36 movers >=5 ranks: LB 1 / DL 7 / DB 2
```

The DB +44.5% maximum is A.J. Haulcy, a low-value depth/rookie asset (796 -> 1150) whose positional rank moves only one spot. No top-tier compression or ceiling-clamp issue was introduced.

### Final deployment tooling

Created:

- `docs/CHATGPT_SOLO_BATCH4_IDP_V1_PRODUCTION_BAKE.md`
- `scripts/validate_idp_v1_final_deployment.py`
- `scripts/idp_v1_final_deployment_validation.json`
- `scripts/idp_v1_final_deployment_validation.md`

Updated post-deployment validation so the immutable pre-V1 baseline remains the OLD side even though `index.html` is now V1.

Repository regression suite expanded to **10 groups** and now hard-validates the deployed V1 table.

### Batch 4 final checks

```text
Canonical history/V1 self-tests: PASS
E.J. Speed 95.43 regression: PASS
Floor-rescue guard self-test: PASS
Final deployment validator: PASS
Repo regression suite: 10/10 PASS
Python: 45 files, 0 errors
JSON: 41 files, 0 errors
YAML: 20 workflows, 0 errors
index.html JS: PASS
free-agent-board JS: PASS
```

Relative to Batch 3, `index.html` changed only inside the production-methodology comment + `PROD_MULT_DATA` region; content before and after that region is byte-identical.

## Current Production Status

```text
IDP V1 methodology: CLOSED / VALIDATED
Model-delta migration: APPLIED / VALIDATED
Production index.html: READY FOR GITHUB UPLOAD
Legacy absolute prod_mult lineage: diagnostic only
46-player position-lineage migration: BACKLOG
Durability weighting recalibration: BACKLOG
```

## Next Step

Upload the Batch 4 changed files to GitHub. Once the repository reflects this exact state, run the read-only deployed-V1 validation workflow once. If it passes, close the IDP V1 deployment workstream and move to the next independent repository improvement.

## ChatGPT Solo Batch 4 File Manifest

### Modified (21)

- `docs/CHATGPT_SOLO_CHECKPOINT_2026-08-28.md`
- `github-workflows/bake-idp-ensemble-v1.yml`
- `github-workflows/idp-v1-candidate-validation.yml`
- `index.html`
- `scripts/idp_v1_candidate_comparison.json`
- `scripts/idp_v1_candidate_comparison_report.md`
- `scripts/idp_v1_index_preview.patch`
- `scripts/idp_v1_isolated_projection_candidate.json`
- `scripts/idp_v1_model_delta_transport_candidate.json`
- `scripts/idp_v1_model_delta_transport_candidate.py`
- `scripts/idp_v1_model_delta_transport_candidate_report.md`
- `scripts/idp_v1_prod_mult_patch.json`
- `scripts/idp_v1_prod_mult_patch_report.md`
- `scripts/idp_v1_production_candidate.json`
- `scripts/idp_v1_production_candidate.py`
- `scripts/idp_v1_projection_only_candidate.json`
- `scripts/prepare_idp_v1_bake.py`
- `scripts/production_history_component.py`
- `scripts/production_history_components.json`
- `scripts/repo_regression_checks.py`
- `scripts/validate_idp_v1_candidates.py`

### Created (4)

- `docs/CHATGPT_SOLO_BATCH4_IDP_V1_PRODUCTION_BAKE.md`
- `scripts/idp_v1_final_deployment_validation.json`
- `scripts/idp_v1_final_deployment_validation.md`
- `scripts/validate_idp_v1_final_deployment.py`

### Deleted

- None.

**Total Batch 4 files to add/update in GitHub: 25.**

---

## Post-Batch-4 GitHub Validation — CI Hotfixes

### CI failure 1 — missing `requests` dependency

The first GitHub run proved the deployed model itself was correct:

```text
PASS final IDP V1 deployment validation: 320 approved PROD_MULT changes deployed
```

The workflow then failed before the regression suite could execute because
`scripts/dual_eligibility_pipeline.py` imports `requests`, while the clean GitHub
runner did not have that package installed.

Fix applied to both IDP validation workflows:

- `github-workflows/bake-idp-ensemble-v1.yml`
- `github-workflows/idp-v1-candidate-validation.yml`

Both now install `requests` before Python regression execution.

Status: **CLOSED — dependency installation verified in the next GitHub run.**

### CI failure 2 — generated `player_positions.json` drift after Sleeper data refresh

The next GitHub run again passed the deployed V1 validator:

```text
PASS final IDP V1 deployment validation: 320 approved PROD_MULT changes deployed
```

It then reached the repository regression suite and failed on:

```text
AssertionError: player_positions.json is stale relative to canonical PLAYER_DB/alias data
```

Root cause was traced to the repository's daily Sleeper sync lifecycle, not the
IDP V1 bake. `scripts/generate_player_positions.py` intentionally derives its
compatibility/fallback rows from `data/players_cache.json`, but
`github-workflows/sync.yml` refreshed/committed `data/` without regenerating or
committing `scripts/player_positions.json`. Therefore a legitimate Sleeper cache
refresh could leave the generated compatibility map stale immediately afterward.

The GitHub log also showed live synchronized free-agent state differing from the
local Batch-4 snapshot, which is consistent with this source/generated-artifact
split.

Fix:

- `github-workflows/sync.yml`
  - now runs `python scripts/generate_player_positions.py` immediately after
    Sleeper roster/player sync;
  - now stages both `data/` and `scripts/player_positions.json` in the same sync
    commit.

The strict regression invariant is intentionally retained. The correct fix is to
keep the generated artifact atomic with its source data rather than weakening the
check.

Local failure-mode reproduction:

1. Modify `data/players_cache.json` while leaving `player_positions.json` stale.
2. Exact regression fails with the same assertion seen in GitHub.
3. Run `python scripts/generate_player_positions.py`.
4. Full 10-group repository regression suite passes.

Status: **FIXED IN WORKFLOW — requires one manual Sleeper sync run in GitHub to
regenerate the currently stale committed `player_positions.json`, followed by a
rerun of `Validate Deployed IDP V1`.**

### Files changed in CI hotfix 2

- `github-workflows/sync.yml`
- `docs/CHATGPT_SOLO_CHECKPOINT_2026-08-28.md`

No calculator values, `PROD_MULT` entries, projection weights, position weights,
age curves, or V1 model outputs were changed by either CI hotfix.


## Batch 4 CI Hotfix 3 — self-healing derived artifact preparation

### Trigger

A third `Validate Deployed IDP V1` run still failed after the `requests` dependency fix. The V1 deployment validator itself again passed all 320 approved PROD_MULT changes, but the general repository regression suite failed because committed `scripts/player_positions.json` was stale relative to the current checked-out `index.html` / `data/players_cache.json` state.

### Root cause

`player_positions.json` is a derived compatibility artifact. Requiring a manually sequenced Sleeper sync before every read-only validation made CI order-dependent: the validator could check out a perfectly valid production commit whose live Sleeper-derived cache had moved while the derived compatibility file had not yet been regenerated/committed.

The prior Hotfix 2 remains correct: `Sync Sleeper League Data` now regenerates and commits `scripts/player_positions.json`. Hotfix 3 additionally makes validation deterministic and self-contained by regenerating this derived artifact in the runner workspace before invoking the repository regression suite.

### Changes

- `github-workflows/bake-idp-ensemble-v1.yml`
  - retains `pip install requests`;
  - now runs `python3 scripts/generate_player_positions.py` before repository regressions.
- `github-workflows/idp-v1-candidate-validation.yml`
  - retains `pip install requests`;
  - now runs the same derived-artifact preparation before repository regressions.
- `github-workflows/repo-regression-checks.yml`
  - now regenerates `player_positions.json` before the full suite (self-test remains separate).
- `github-workflows/sync.yml`
  - retains Hotfix 2 behavior: regenerate and commit `scripts/player_positions.json` alongside Sleeper data.

### Validation performed locally

A stale `player_positions.json` was deliberately created by deleting one generated key. The old sequence failed with the exact GitHub assertion:

```text
AssertionError: player_positions.json is stale relative to canonical PLAYER_DB/alias data
```

Then the new workflow preparation step was run. Results:

```text
Wrote player_positions.json: 565 canonical PLAYER_DB positions + 2056 safe alias/Sleeper fallback lookups
PASS final IDP V1 deployment validation: 320 approved PROD_MULT changes deployed
ALL REPO REGRESSION CHECKS PASSED (10 groups)
Python parse: 45 PASS
JSON parse: 41 PASS
YAML parse: 20 PASS
index.html unchanged: PASS
```

### Model impact

None. Hotfix 3 changes CI/workflow preparation only.

```text
PROD_MULT changes: 0
IDP V1 weights: unchanged
PLAYER_DB: unchanged
index.html: unchanged
final player values: unchanged
```

### Operational change

After this hotfix, `Validate Deployed IDP V1` no longer requires the user to manually run `Sync Sleeper League Data` first merely to refresh `player_positions.json`. The sync workflow still keeps the committed compatibility artifact current for normal repository use, but validation prepares its own deterministic derived copy before regression testing.

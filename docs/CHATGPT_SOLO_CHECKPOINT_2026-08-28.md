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
- The preferred first-release V1 migration is now the validated **model-delta transport** bridge; production `index.html` has not yet been changed.
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

Current preview:

```text
404 live IDP candidate keys
324 actual PROD_MULT entries would change
80 entries remain exact holds
LB changes 117
DL changes 91
DB changes 116
565 PLAYER_DB rows parse/evaluate successfully
```

No production values were applied.

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

## Next Decision

The next step is no longer additional model research or lineage reconstruction. Batch 3 has reduced the decision to one controlled production action:

> **Approve or reject model-delta transport as the first V1 production migration method.**

If approved, run `prepare_idp_v1_bake.py --apply` in the controlled working tree, update the stale methodology comment above `PROD_MULT_DATA` in the same change, rerun the entire regression/final-value suite, generate the exact old-live -> final-new production report, and only then commit the resulting `index.html`.

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

- A fresh run of the legacy `prod_mult_pipeline.py` does **not** reproduce the actual pre-V1 live `PROD_MULT_DATA` table.
- Therefore the old generated JSON lineage cannot be assumed to equal the historical live production model.
- The validated V1 projection architecture remains sound, but the production bake must not accidentally mix a V1 projection change with unrelated legacy-lineage recalibration.
- The current `bake_idp_ensemble_v1.py` still depends on `prod_mult_pipeline_output.json`; the original repo snapshot did not contain that generated file, so the bake path is not yet clean-checkout self-contained.

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

# Next Workstream

**Immediate goal:** make the V1 production path deterministic and auditable without relying on stale generated lineage.

Planned sequence:

1. ~~Capture an immutable canonical pre-V1 `PROD_MULT_DATA` baseline.~~ **DONE**
2. ~~Harden projection-source activity detection beyond tackle-total-only logic.~~ **DONE**
3. ~~Add a dedicated lineage audit explaining legacy generated-vs-live drift.~~ **DONE**
4. **NEXT:** separate reusable history/durability computation from obsolete legacy projection blending and determine the safest baseline-normalization bridge from the historical live table.
5. Build a clean-checkout V1 IDP candidate pipeline that does not require a pre-existing stale `prod_mult_pipeline_output.json`.
6. Validate final candidate against the true old live baseline before touching production values.


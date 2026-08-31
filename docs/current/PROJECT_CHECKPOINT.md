# Trade Desk — Current Project Checkpoint

**Updated:** 2026-08-31  
**Repository:** `ajknoll23-code/LOG-Trade-Calculator`  
**Status:** Repository reorganization complete; production/regression state is green.

## Current Production State

The repository cleanup/reorganization workstream is complete.

Confirmed current state:

- Production `index.html` remains the canonical Trade Desk valuation implementation.
- IDP V1 is deployed, frozen, and validated.
- Free-agent valuation uses the canonical Trade Desk engine and parity validation.
- Sleeper, FantasyPros, KTC, projection, maintenance, model, utility, and validation code is organized into purpose-specific folders.
- Legacy root implementation copies have been removed.
- The temporary root `scripts/idp_v1_projection.py` compatibility wrapper has been removed after regression proved it was no longer required.
- The IDP V1 release has been consolidated into one canonical release package under `model/releases/idp-v1/`.
- Duplicate IDP V1 release copies under `scripts/artifacts/releases/idp_v1/` were removed.
- Repository Regression Checks are green after the consolidation and cleanup.
- No valuation/model recalibration was performed as part of the repository reorganization.

## Canonical Script Layout

### `scripts/sync/`

Live synchronization and generated-source sync jobs:

- `sync_sleeper.py`
- `sync_trade_history.py`
- `sync_free_agent_valuation.py`

### `scripts/projections/`

Projection ingestion and identity-resolution pipelines:

- `fantasypros_api_pipeline.py`
- `resolve_fantasypros_sleeper_identity.py`
- `sleeper_projections_pipeline.py`
- `filter_sleeper_idp_only.py`

### `scripts/model/`

Reusable model/math implementations:

- `ppg_pipeline.py`
- `production_history_component.py`
- `idp_v1_projection.py`

### `scripts/market/`

Market-data and draft-slot pipelines:

- `ktc_pipeline.py`
- `draft_slot_projection_pipeline.py`

### `scripts/maintenance/`

Repository/state maintenance helpers:

- `refresh_repo_derived_state.py`
- `team_field_refresh_pipeline.py`

### `scripts/utilities/`

General reusable utilities:

- `generate_player_positions.py`

### `scripts/validation/`

Validation/regression tools:

- `repo_regression_checks.py`
- `snapshot_values.py`
- `diff_snapshots.py`
- `dual_eligibility_pipeline.py`
- `check_no_duplicate_prod_mult_keys.py`
- `validate_free_agent_valuation_parity.py`
- `validate_idp_v1_final_deployment.py`

## Active GitHub Actions Workflows

There are seven active workflows under `.github/workflows/`:

1. `fantasypros-api-pipeline.yml`
2. `filter-sleeper-idp-only.yml`
3. `ktc-vote-aggregation.yml`
4. `repo-regression-checks.yml`
5. `resolve-fantasypros-sleeper-identity.yml`
6. `sleeper-2026-projections.yml`
7. `sync-sleeper.yml`

The temporary one-time `consolidate-idp-v1-release.yml` workflow was removed after the consolidation completed successfully.

These seven active workflows are intentionally separate. Do not merge or delete them merely to reduce workflow count.

### Sleeper workflow constraint

`sync-sleeper.yml` intentionally does **not** contain the former `all` manual option.

The supported manual choices remain:

```text
sync
dual-eligibility
team-refresh
```

Do not reintroduce `all`; the earlier combined behavior created parallel push/race risk.

## Current Regression/Validation State

Latest repository-reorganization validation:

```text
Repo Regression Checks: GREEN
Free-agent canonical valuation sync: GREEN
Free-agent runtime/source parity: GREEN
IDP V1 canonical model import: GREEN
Production-history canonical model import: GREEN
Frozen IDP V1 release integrity: GREEN
Derived-artifact parity checks: GREEN
Inline JavaScript validation: GREEN
```

The active regression workflow runs canonical nested paths, including:

```text
scripts/sync/sync_sleeper.py
scripts/sync/sync_free_agent_valuation.py
scripts/maintenance/refresh_repo_derived_state.py
scripts/utilities/generate_player_positions.py
scripts/projections/filter_sleeper_idp_only.py
scripts/projections/sleeper_projections_pipeline.py
scripts/market/draft_slot_projection_pipeline.py
scripts/validation/repo_regression_checks.py
scripts/validation/validate_free_agent_valuation_parity.py
scripts/validation/validate_idp_v1_final_deployment.py
```

## Free-Agent Board State

`free-agent-board.html` is a generated/canonical-parity consumer of `index.html` valuation logic.

Canonical generator:

```text
scripts/sync/sync_free_agent_valuation.py
```

Canonical validation:

```text
scripts/validation/validate_free_agent_valuation_parity.py
```

All known stale references to the former root command:

```text
scripts/sync_free_agent_valuation.py
```

have been removed from the active generator, generated board note, validator hint, and workflow paths.

The separate off-roster `FA_PROD_MULT_DATA` lineage remains an independent modeling/data-lineage backlog item; repository cleanup did not recalibrate it.

## IDP V1 State

IDP V1 production deployment remains closed and validated.

Canonical reusable projection implementation:

```text
scripts/model/idp_v1_projection.py
```

Canonical production-history implementation:

```text
scripts/model/production_history_component.py
```

Canonical frozen release package:

```text
model/releases/idp-v1/
```

The package contains:

```text
README.md
idp_v1_final_deployment_validation.json
idp_v1_final_deployment_validation.md
idp_v1_model_delta_transport_candidate.json
idp_v1_prod_mult_patch.json
idp_v1_release_manifest.json
prod_mult_pre_v1_baseline.json
production_history_components.json
```

The release manifest hash-protects the canonical artifacts in this directory.

The former duplicate release copies under:

```text
scripts/artifacts/releases/idp_v1/
```

have been removed.

The former root historical baseline:

```text
scripts/prod_mult_pre_v1_baseline.json
```

has also been removed because the canonical immutable copy now lives inside the frozen release package.

A future model refresh must create a new release rather than silently rewriting IDP V1.

## PPG Pipeline State

Canonical implementation:

```text
scripts/model/ppg_pipeline.py
```

Canonical inputs/outputs remain in the `scripts/` root, including:

```text
scripts/all_players.json
scripts/ppg_results.json
scripts/durability_results.json
```

These files are active pipeline inputs/outputs and/or recorded release-lineage source snapshots. They should not be moved solely for cosmetic organization.

## Projection and Identity Data State

The following root JSON files remain intentionally in `scripts/` because active pipelines and/or release-lineage provenance reference their current locations:

```text
scripts/fantasypros_api_normalized_2026.json
scripts/fantasypros_2026_projections.json
scripts/identity_crosswalk.json
scripts/sleeper_2026_idp_only.json
scripts/sleeper_2026_projections.json
```

Moving these files requires a coordinated path migration and release-lineage decision, not a simple cleanup rename.

## Artifact Layout

Generated and report artifacts are organized under:

```text
scripts/artifacts/generated/
scripts/artifacts/reports/
```

Frozen production releases belong under:

```text
model/releases/<release-id>/
```

New implementation code should not be placed directly under `scripts/` when an existing purpose-specific folder applies.

## Repository Root Policy

The `scripts/` root is reserved primarily for active data files whose current paths have live pipeline or provenance significance.

Implementation code belongs in:

```text
scripts/sync/
scripts/projections/
scripts/model/
scripts/market/
scripts/maintenance/
scripts/utilities/
scripts/validation/
```

Do not move root data files merely to make the directory look cleaner. Preserve functional and provenance semantics first.

## Open Modeling / Data-Lineage Backlog

The following are intentionally **not** part of the completed repository-reorganization workstream:

1. **Legacy PROD_MULT lineage**
   - The legacy production pipeline does not reproduce the historical live `PROD_MULT_DATA` table exactly.
   - Treat it as diagnostic unless/until that lineage is deliberately rebuilt.

2. **Historical IDP position-lineage migration**
   - A known cohort has legacy production-position grouping that differs from current valuation position.
   - This remains separate from the deployed IDP V1 projection release.

3. **Durability weighting methodology**
   - Recalibration remains backlog.
   - No durability weighting changes were made during repository reorganization.

4. **Free-agent off-roster production lineage**
   - `FA_PROD_MULT_DATA` remains a separate lineage/rebuild question.
   - Core engine parity is closed; production-source lineage is not silently considered solved.

These items require their own scoped analysis and validation. Do not mix them into routine repository cleanup.

## Reorganization Closeout

Repository organization is now structurally complete enough that further cleanup should be conservative.

Before moving or deleting any remaining root data file:

1. Search all live code/workflow references.
2. Check release-lineage/provenance references.
3. Make coordinated path changes when required.
4. Run Repo Regression Checks.
5. Keep modeling changes separate from repository organization.

Current validated state: **GREEN**.

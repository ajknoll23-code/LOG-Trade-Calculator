# League of Ordinary Gentlemen — Dynasty Trade Calculator

Production dynasty fantasy-football trade calculator and league-data pipeline for the League of Ordinary Gentlemen.

The repository contains the live Trade Desk UI, Sleeper league synchronization, FantasyPros and Sleeper projection pipelines, KTC market inputs, free-agent valuation, reusable model code, frozen model releases, and repository-wide regression checks.

## Production Entry Points

- `index.html` — canonical Trade Desk valuation implementation and main calculator UI.
- `free-agent-board.html` — generated free-agent board using the same canonical valuation engine.
- `config.json` — league/repository configuration.
- `data/` — synchronized league, roster, player-cache, draft-pick, and free-agent data.

## Repository Layout

### `.github/workflows/`

Active production and validation workflows:

- `fantasypros-api-pipeline.yml`
- `filter-sleeper-idp-only.yml`
- `ktc-vote-aggregation.yml`
- `repo-regression-checks.yml`
- `resolve-fantasypros-sleeper-identity.yml`
- `sleeper-2026-projections.yml`
- `sync-sleeper.yml`

### `scripts/sync/`

Live synchronization and generated-state jobs:

- `sync_sleeper.py`
- `sync_trade_history.py`
- `sync_free_agent_valuation.py`

### `scripts/projections/`

Projection ingestion and identity-resolution pipelines:

- `fantasypros_api_pipeline.py`
- `filter_sleeper_idp_only.py`
- `resolve_fantasypros_sleeper_identity.py`
- `sleeper_projections_pipeline.py`

### `scripts/model/`

Reusable production/model math:

- `idp_v1_projection.py`
- `ppg_pipeline.py`
- `production_history_component.py`

### `scripts/market/`

Market and draft-value pipelines:

- `draft_slot_projection_pipeline.py`
- `ktc_pipeline.py`

### `scripts/maintenance/`

Repository and derived-state maintenance:

- `refresh_repo_derived_state.py`
- `team_field_refresh_pipeline.py`

### `scripts/utilities/`

General utilities:

- `generate_player_positions.py`

### `scripts/validation/`

Regression and parity checks:

- `check_no_duplicate_prod_mult_keys.py`
- `diff_snapshots.py`
- `dual_eligibility_pipeline.py`
- `repo_regression_checks.py`
- `snapshot_values.py`
- `validate_free_agent_valuation_parity.py`
- `validate_idp_v1_final_deployment.py`

### `scripts/artifacts/`

Generated and human-readable pipeline outputs are separated from implementation code:

- `generated/` — deterministic/generated machine-readable outputs.
- `reports/` — human-readable pipeline and identity reports.

### `model/releases/idp-v1/`

Canonical frozen IDP V1 production release package.

This directory contains the immutable release artifacts, validation outputs, release manifest, historical pre-V1 baseline, and release documentation for the deployed IDP V1 model.

A future model release should create a new release directory rather than overwrite the frozen V1 package.

### `research/`

Archived and active research work is grouped by topic rather than mixed into production code.

### `docs/`

- `docs/current/` — current operational/project documentation.
- `docs/archive/` — historical handoffs, closing summaries, and superseded checkpoints.

## Intentional Root Data Files Under `scripts/`

Several JSON files remain directly under `scripts/` because they are active pipeline inputs/outputs and/or recorded release-lineage source snapshots.

Examples include:

- `all_players.json`
- `ppg_results.json`
- `durability_results.json`
- `fantasypros_api_normalized_2026.json`
- `fantasypros_2026_projections.json`
- `identity_crosswalk.json`
- `sleeper_2026_idp_only.json`
- `sleeper_2026_projections.json`

Do not move these solely for cosmetic organization. Path changes should be made only together with all live consumers and release-lineage considerations.

## Repository Regression Checks

Run the active GitHub Actions workflow:

`Repo Regression Checks`

The regression suite verifies, among other things:

- live valuation parity between Python and `index.html`;
- Sleeper/free-agent data integrity;
- player-position and alias integrity;
- deterministic generated artifacts;
- canonical model imports;
- frozen IDP V1 release integrity;
- deployed IDP V1 invariants;
- free-agent valuation parity;
- inline JavaScript syntax.

Repository reorganization should not be considered complete until this workflow is green.

## Sleeper Sync

`sync-sleeper.yml` is the active Sleeper workflow.

Supported manual operations are intentionally separated to avoid parallel write/push races:

- `sync`
- `dual-eligibility`
- `team-refresh`

## Modeling Safety

Repository cleanup and model recalibration are separate workstreams.

Routine organization should not silently change:

- `PROD_MULT_DATA`;
- player values;
- age curves;
- position weights;
- role multipliers;
- durability methodology;
- IDP V1 release artifacts;
- free-agent production lineage.

Any modeling change should be scoped, audited, and validated independently.

## Current Project Documentation

For the detailed current project state and known backlog, see:

`docs/current/PROJECT_CHECKPOINT.md`

# Trade Desk — Current Project Checkpoint

**Updated:** 2026-08-30  
**Repository:** `ajknoll23-code/LOG-Trade-Calculator`  
**Status:** Repository reorganization complete; current production/regression state is green.

## Current Production State

The repository cleanup/reorganization workstream is complete.

Confirmed current state:

- Production `index.html` remains the canonical Trade Desk valuation implementation.
- IDP V1 is deployed and validated.
- Free-agent valuation uses the canonical Trade Desk engine and parity validation.
- Sleeper, FantasyPros, KTC, projection, maintenance, model, utility, and validation code is organized into purpose-specific folders.
- Legacy root script copies were removed unless an explicit compatibility reason remains.
- Repository Regression Checks are green after the final path cleanup.
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

## Intentional Compatibility Wrapper

One Python file intentionally remains directly under `scripts/`:

- `scripts/idp_v1_projection.py`

This is a compatibility wrapper for historical/archived IDP V1 research tooling that still imports or executes the former root path.

The canonical implementation is:

```text
scripts/model/idp_v1_projection.py
```

New production/validation code should use the canonical `scripts/model/` implementation.

Do not delete the root wrapper unless all historical consumers are intentionally migrated first.

## Active GitHub Actions Workflows

There are seven active workflows under `.github/workflows/`:

1. `fantasypros-api-pipeline.yml`
2. `filter-sleeper-idp-only.yml`
3. `ktc-vote-aggregation.yml`
4. `repo-regression-checks.yml`
5. `resolve-fantasypros-sleeper-identity.yml`
6. `sleeper-2026-projections.yml`
7. `sync-sleeper.yml`

These workflows are intentionally separate. Do not merge or delete them merely to reduce workflow count.

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

Frozen release artifacts remain under `scripts/`, including:

```text
scripts/prod_mult_pre_v1_baseline.json
scripts/production_history_components.json
scripts/idp_v1_model_delta_transport_candidate.json
scripts/idp_v1_prod_mult_patch.json
scripts/idp_v1_release_manifest.json
```

These are release/data artifacts, not loose implementation scripts, and are intentionally left at the `scripts/` root.

## PPG Pipeline State

Canonical implementation:

```text
scripts/model/ppg_pipeline.py
```

Canonical inputs/outputs remain in the `scripts/` root, including:

```text
scripts/all_players.json
scripts/ppg_results.json
```

Callers now reference the canonical model path.

The repository-reorganization regression is green. Historical comment/diagnostic wording differences from the former root copy are not treated as a functional open item.

## Repository Root Policy

The `scripts/` root is now reserved primarily for:

- generated JSON/data artifacts,
- frozen release artifacts,
- reports/artifacts that intentionally live beside those datasets,
- the single intentional IDP compatibility wrapper.

New implementation code should normally be placed into the appropriate category folder rather than directly under `scripts/`.

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

## Development Rules Going Forward

- Keep changes small and testable.
- Run Repo Regression Checks after structural/path changes.
- Preserve `index.html` production behavior unless a task explicitly targets valuation/model behavior.
- Do not regenerate or rewrite frozen IDP V1 release artifacts during ordinary maintenance.
- Prefer canonical category-folder imports/paths in new code.
- Keep compatibility wrappers only when there is a known consumer requiring them.
- Do not weaken regression checks merely to make a stale generated artifact pass; fix the source/generated lifecycle instead.
- Treat modeling/calibration work as a separate workstream from repository organization.

## Historical Records

The previous long-form checkpoint accumulated Batch 1–5 development history and many paths that were correct at the time but are no longer current after the repository reorganization.

Historical material should be treated as historical context, not current path guidance.

Detailed historical documents are retained under:

```text
docs/archive/
```

and in Git history.

For current operational paths and repository state, this file and the other documents under:

```text
docs/current/
```

take precedence.

## Reorganization Completion Record — 2026-08-30

Completed during the final repository cleanup:

- moved Sleeper sync implementation to `scripts/sync/`;
- moved trade-history sync to `scripts/sync/`;
- moved free-agent canonical sync to `scripts/sync/`;
- moved FantasyPros and Sleeper projection pipelines to `scripts/projections/`;
- moved FantasyPros/Sleeper identity resolver to `scripts/projections/`;
- moved KTC and draft-slot market pipelines to `scripts/market/`;
- moved maintenance helpers to `scripts/maintenance/`;
- moved `generate_player_positions.py` to `scripts/utilities/`;
- moved regression/validation utilities to `scripts/validation/`;
- moved PPG, production-history, and IDP V1 implementations to `scripts/model/`;
- deleted obsolete root wrappers after caller migration where safe;
- retained `scripts/idp_v1_projection.py` intentionally for historical compatibility;
- removed obsolete workflow/script duplicates;
- standardized active workflow callers on canonical nested paths;
- cleaned stale free-agent valuation path text from generator, board, and validator;
- confirmed exactly seven active workflows;
- confirmed Repo Regression Checks green after final cleanup.

**Repository reorganization status: COMPLETE.**

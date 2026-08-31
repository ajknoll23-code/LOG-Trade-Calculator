# Trade Desk — CI / Regression Runbook

**Updated:** 2026-08-31  
**Repository:** `ajknoll23-code/LOG-Trade-Calculator`

## Purpose

This runbook describes the current repository validation model after the 2026-08-31 reorganization and IDP V1 release consolidation.

The primary safety rule is:

> Repository maintenance may refresh rolling deterministic state, but it must never silently rewrite a frozen production model release.

## Active Regression Workflow

Canonical workflow:

```text
.github/workflows/repo-regression-checks.yml
```

Run it manually from GitHub Actions after repository organization, path changes, generated-state updates, or other maintenance work.

The workflow is read-only with respect to production valuation logic.

## What the Workflow Validates

The regression workflow currently verifies:

- canonical valuation parity between Python and `index.html`;
- Sleeper position/free-agent integrity;
- dual-eligibility audit invariants;
- team identity mappings;
- alias and KTC position integrity;
- IDP V1 projection invariants;
- frozen IDP V1 release integrity;
- production-history/release bridge invariants;
- preferred IDP V1 bake invariants;
- deployed IDP V1 production invariants;
- free-agent board valuation parity;
- deterministic derived-state parity;
- inline JavaScript syntax.

## Rolling Deterministic Derived State

These files may legitimately be regenerated from current committed inputs:

```text
free-agent-board.html
data/free_agents.json
scripts/artifacts/generated/player_positions.json
```

The manual regression workflow may normalize rolling derived state inside the runner before strict validation.

A manual validation run does not automatically push those runner-only changes back to the repository.

If a rolling generated artifact is stale in the repository, use the appropriate canonical generator to intentionally refresh and commit it.

## Frozen IDP V1 Release

The canonical frozen release package is:

```text
model/releases/idp-v1/
```

Core immutable artifacts include:

```text
model/releases/idp-v1/production_history_components.json
model/releases/idp-v1/prod_mult_pre_v1_baseline.json
model/releases/idp-v1/idp_v1_model_delta_transport_candidate.json
model/releases/idp-v1/idp_v1_prod_mult_patch.json
model/releases/idp-v1/idp_v1_release_manifest.json
```

The release manifest SHA256-protects the frozen production artifacts.

General repository maintenance must not regenerate or overwrite them.

A future model revision should create a new release directory rather than mutate IDP V1 in place.

## Release Lineage Drift

The release manifest also records source/code hashes used for release provenance.

Current source files may legitimately change after deployment.

Examples include:

```text
scripts/all_players.json
scripts/ppg_results.json
scripts/durability_results.json
scripts/fantasypros_api_normalized_2026.json
scripts/fantasypros_2026_projections.json
scripts/identity_crosswalk.json
scripts/sleeper_2026_idp_only.json
scripts/sleeper_2026_projections.json
```

If those current sources differ from the frozen release snapshot, regression may report release-lineage drift as informational.

That does **not** invalidate the deployed frozen release.

By contrast, a byte change to a hash-protected immutable release artifact must fail regression.

## Canonical Validation Commands

Primary full repository regression:

```bash
python3 scripts/validation/repo_regression_checks.py
```

Standalone deployed IDP V1 validation:

```bash
python3 scripts/validation/validate_idp_v1_final_deployment.py
```

Free-agent canonical valuation parity:

```bash
python3 scripts/sync/sync_free_agent_valuation.py --check
python3 scripts/validation/validate_free_agent_valuation_parity.py
```

Deterministic derived-state validation:

```bash
python3 scripts/maintenance/refresh_repo_derived_state.py --check
```

## Canonical Self-Tests

Important self-tests used by the active workflow include:

```bash
python3 scripts/validation/snapshot_values.py --selftest
python3 scripts/sync/sync_sleeper.py --selftest
python3 scripts/validation/dual_eligibility_pipeline.py --selftest
python3 scripts/maintenance/team_field_refresh_pipeline.py --selftest
python3 scripts/utilities/generate_player_positions.py --selftest
python3 scripts/sync/sync_free_agent_valuation.py --selftest
python3 scripts/maintenance/refresh_repo_derived_state.py --selftest
python3 scripts/projections/filter_sleeper_idp_only.py --selftest
python3 scripts/projections/sleeper_projections_pipeline.py --selftest
python3 scripts/market/draft_slot_projection_pipeline.py --selftest
```

## Expected Green State

A healthy repository should satisfy all of the following:

```text
Repo Regression Checks: GREEN
Deployed IDP V1 validation: PASS
Free-agent valuation parity: PASS
Derived-artifact parity: PASS
index.html JavaScript: PASS
free-agent-board.html JavaScript: PASS
```

Production `index.html` must remain unchanged by routine repository normalization.

## If Repo Regression Checks Turns Red

Do not start moving more files.

Use this order:

1. Identify the exact failed workflow step.
2. Read the job log and first real traceback/assertion.
3. Determine whether the failure is:
   - a stale generated artifact;
   - a broken import/path;
   - a frozen-release integrity violation;
   - a current-source lineage drift issue;
   - a valuation/runtime parity failure;
   - a JavaScript syntax failure.
4. Fix only the actual failing dependency.
5. Re-run Repo Regression Checks.
6. Continue cleanup only after the workflow is green again.

## Repository Reorganization Rule

Path cleanup is not valuable if it weakens reproducibility.

Before moving or deleting a file:

1. Search live callers and workflows.
2. Check release-manifest/provenance references.
3. Update all required paths together.
4. Run regression.
5. Preserve the last known-green structure if the change fails.

## Modeling Boundary

CI/repository maintenance must not silently recalibrate:

```text
PROD_MULT_DATA
POSITION_WEIGHT
AGE_CURVE
ROLE_MULT
durability methodology
IDP V1 weights/formula
FA_PROD_MULT_DATA lineage
```

Those belong to separately scoped modeling workstreams with their own audits and release process.

# Trade Desk — Free-Agent Board

**Updated:** 2026-08-31  
**Status:** Canonical valuation parity closed; off-roster production lineage remains a separate modeling backlog item.

## Purpose

`free-agent-board.html` is the repository’s generated free-agent view.

It does **not** maintain an independent valuation model. The board uses the same canonical Trade Desk valuation engine as `index.html`, with a separate free-agent production-data fallback for off-roster players when canonical production data is unavailable.

## Canonical Files

Main valuation source:

```text
index.html
```

Generated free-agent board:

```text
free-agent-board.html
```

Canonical synchronization tool:

```text
scripts/sync/sync_free_agent_valuation.py
```

Canonical parity validator:

```text
scripts/validation/validate_free_agent_valuation_parity.py
```

Canonical Sleeper synchronization:

```text
scripts/sync/sync_sleeper.py
```

Committed free-agent data:

```text
data/free_agents.json
```

## Canonical Valuation Synchronization

The free-agent board synchronizer copies the canonical valuation regions from `index.html` into `free-agent-board.html`.

These include:

- `POSITION_WEIGHT`
- `AGE_CURVE`
- `QB_POST_PEAK_FLOOR`
- `LB_POST_PEAK_DECAY_POWER`
- `ROLE_MULT`
- deployed `PROD_MULT_DATA`
- `NO_REAL_PRODUCTION_HISTORY`
- `productionMultiplier()`
- `ageMultiplier()`
- `playerValue()`
- canonical `PLAYER_DB`
- alias resolution
- `normalizeName()`

The board-specific `FA_PROD_MULT_DATA` table is intentionally preserved.

Supported modes:

```text
--write
--check
--selftest
```

Examples:

```bash
python3 scripts/sync/sync_free_agent_valuation.py --check
python3 scripts/sync/sync_free_agent_valuation.py --write
python3 scripts/sync/sync_free_agent_valuation.py --selftest
```

## Production-Source Precedence

For a free-agent row, production multiplier source precedence is:

```text
1. canonical PROD_MULT_DATA, when available
2. FA_PROD_MULT_DATA, when available
3. curated PLAYER_DB role estimate
4. speculative fallback estimate
```

Canonical `PLAYER_DB` metadata may still supply age, role, and position, but it must not suppress valid free-agent-specific production data.

## Parity Validation

Run:

```bash
python3 scripts/validation/validate_free_agent_valuation_parity.py
```

The validator checks:

- exact canonical source-region parity with `index.html`;
- synchronizer idempotence;
- Python-vs-JavaScript valuation parity;
- valuation boundary cases;
- FA production-source precedence;
- full generated-board execution;
- valid rendered row metadata;
- same-name collision protections;
- roster/free-agent disjointness by stable Sleeper ID;
- production-source label correctness.

This validation is also included in the repository regression suite.

## Sleeper Source Hygiene

`data/free_agents.json` is derived from committed Sleeper player/cache and roster state.

The Sleeper sync contains safeguards for:

- inactive/stale player rows;
- impossible ages;
- missing ages;
- stable-ID age overrides where explicitly required;
- dual-position primary-bucket behavior;
- roster/free-agent overlap.

Canonical Sleeper implementation:

```text
scripts/sync/sync_sleeper.py
```

## Rolling Derived State

The free-agent board and its committed data are rolling deterministic state.

The primary related files are:

```text
free-agent-board.html
data/free_agents.json
scripts/artifacts/generated/player_positions.json
```

Canonical repository derived-state maintenance:

```text
scripts/maintenance/refresh_repo_derived_state.py
```

Check mode:

```bash
python3 scripts/maintenance/refresh_repo_derived_state.py --check
```

Write mode:

```bash
python3 scripts/maintenance/refresh_repo_derived_state.py --write
```

A manual CI validation may normalize rolling artifacts inside the runner without pushing those changes back to the repository.

## Relationship to IDP V1

The deployed IDP V1 model release is frozen under:

```text
model/releases/idp-v1/
```

The free-agent board consumes the live canonical Trade Desk valuation engine, but its separate `FA_PROD_MULT_DATA` table is **not automatically equivalent to the frozen IDP V1 production-history/projection lineage**.

Do not regenerate or overwrite the frozen IDP V1 release package as part of free-agent board maintenance.

## Closed Work

The following are considered closed and regression-covered:

```text
FREE-AGENT CORE VALUATION ENGINE PARITY
FREE-AGENT CANONICAL PLAYER METADATA PARITY
FREE-AGENT SOURCE/BADGE PRECEDENCE BUG
FREE-AGENT SOURCE-DATA HYGIENE GUARDS
ROSTER/FREE-AGENT STABLE-ID DISJOINTNESS
```

## Open Modeling / Data-Lineage Work

The remaining independent question is:

```text
FREE-AGENT PRODUCTION LINEAGE / IDP V1 EXTENSION
```

Reason:

Many off-roster players still use the separate `FA_PROD_MULT_DATA` source.

Current repository parity proves those values are routed through the canonical Trade Desk engine correctly. It does **not** prove that the off-roster production multipliers themselves were generated using the same frozen IDP V1 methodology as rostered production values.

That should be handled as a separately scoped modeling/data-lineage project, not bundled into routine frontend or repository cleanup.

## Operational Checks

Before committing a free-agent board change, run:

```bash
python3 scripts/sync/sync_free_agent_valuation.py --check
python3 scripts/validation/validate_free_agent_valuation_parity.py
python3 scripts/maintenance/refresh_repo_derived_state.py --check
python3 scripts/validation/repo_regression_checks.py
```

Expected healthy state:

```text
Free-agent canonical sync: PASS
Free-agent runtime/source parity: PASS
Derived-artifact parity: PASS
Repo Regression Checks: PASS
```

## Safety Boundary

Routine free-agent maintenance must not silently recalibrate:

```text
PROD_MULT_DATA
POSITION_WEIGHT
AGE_CURVE
ROLE_MULT
IDP V1 projection methodology
FA_PROD_MULT_DATA methodology
```

Any of those changes require a separately scoped audit and validation process.

# ChatGPT Solo Batch 5 — Free-Agent Board Valuation Parity

**Date:** 2026-08-28/29  
**Scope:** Free-agent board valuation-engine parity, waiver-source hygiene, and regression hardening.  
**Main Trade Desk `index.html` model change:** **NONE**.

## Executive result

Batch 5 removes the free-agent board as an independent/stale valuation implementation without introducing a new browser/runtime dependency. `index.html` remains the canonical valuation source. A deterministic sync tool now copies the canonical valuation regions into `free-agent-board.html`, and CI verifies both exact source parity and actual JavaScript runtime parity.

The batch also caught two independent data/runtime defects during the deeper validation pass:

1. Sleeper's committed player pool contained stale/legacy or impossible-age rows that leaked into the waiver list.
2. Five current free agents had valid `FA_PROD_MULT_DATA`, but a matching `PLAYER_DB` metadata row suppressed that production number inside `playerValue()` even though the UI labeled the row as having real data.

Both are fixed and regression-covered.

## 1. Canonical valuation synchronization

New: `scripts/sync_free_agent_valuation.py`

The script copies the following exact source regions from `index.html` into `free-agent-board.html`:

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
- full canonical `PLAYER_DB`
- `ALIASES` / `ALIASES_REVERSE` / `resolveExistingKey()`
- `normalizeName()`

The board-specific `FA_PROD_MULT_DATA` table is deliberately **not** overwritten. The sync self-test asserts it is byte-for-byte preserved.

Supported modes:

```text
--write     intentionally synchronize board from index
--check     read-only CI failure if board is stale
--selftest  parser/idempotence/FA-table-preservation tests
```

Why this architecture was chosen: externalizing the valuation runtime into a new browser JS asset would create caching/deployment risk during an already-sensitive production cleanup. The generated-copy model gives one canonical source and enforceable parity while leaving the current static-page deployment architecture intact.

## 2. Deep runtime parity validation

New: `scripts/validate_free_agent_valuation_parity.py`

The validator is network-free and performs all of the following:

1. exact source-region parity against `index.html`;
2. sync idempotence;
3. JavaScript-vs-canonical-Python valuation parity for all **565** canonical `PLAYER_DB` players;
4. **8** synthetic valuation boundary/branch cases;
5. a separate synthetic free-agent production-source precedence case;
6. full execution of `free-agent-board.html` in Node against committed `data/free_agents.json` with mocked DOM/fetch;
7. valid position/role/age/value checks on every rendered row;
8. same-name collision protections for the known Justin Jefferson / Devonta Smith / Byron Young cases;
9. stable Sleeper-ID roster/free-agent disjointness;
10. source-label parity: `hasRealData` must agree with the production source actually used by `playerValue()`.

Current result:

```text
PASS free-agent valuation parity
565 canonical player values
8 canonical synthetic branch cases
1 FA production-source precedence synthetic case
1998 rendered free agents
0 roster overlap
```

## 3. Sleeper source-data hygiene

Modified: `scripts/sync_sleeper.py`

New safeguards:

- explicitly inactive Sleeper rows are excluded even if stale team/status fields remain populated;
- a non-null but impossible age is treated as source corruption rather than trusted;
- genuinely missing ages remain allowed and use the board's documented fallback;
- stable-ID age overrides are explicit rather than name-based;
- Sleeper ID `13869` (Anquin Barnes) has an explicit age override of **23** because the committed Sleeper data reports an impossible age of 3;
- self-tests cover inactive rows, impossible ages, missing ages, the stable-ID override, and dual-position primary-bucket behavior.

`data/free_agents.json` was regenerated from the **committed** `data/players_cache.json` and committed rosters—no network refresh was mixed into this batch.

Population impact:

```text
Batch 4 source rows: 2021
Batch 5 source rows: 2000
Removed:             21
Added:                0
```

The removed rows are stale/inactive/duplicate legacy records plus one active-flagged ghost row with an impossible age. This is data hygiene, not a valuation-model cut.

## 4. Production-source precedence bug fixed

During the full runtime audit, five displayed players were found with this state:

```text
PLAYER_DB metadata match: yes
canonical PROD_MULT:      no
FA_PROD_MULT_DATA:        yes
UI hasRealData:           true
actual value source:      role estimate   <-- bug
```

Affected current rows:

- CJ Daniels
- Reggie Virgil
- Sam Roush
- Deion Burks
- Kevin Coleman

The board now uses this precedence:

```text
1. matching canonical PROD_MULT, if present
2. otherwise matching FA_PROD_MULT_DATA, if present
3. otherwise curated role estimate, if PLAYER_DB metadata exists
4. otherwise speculative estimate
```

Curated `PLAYER_DB` metadata can still supply age/role/position, but it can no longer suppress verified FA-specific production.

Current displayed production-source coverage is now internally consistent:

```text
1599 speculative estimate only
 385 FA_PROD_MULT_DATA
  13 canonical PROD_MULT_DATA
   1 canonical PLAYER_DB metadata / no real production
--------------------------------
1998 rendered rows
```

Rows marked `hasRealData=true`: **398**, exactly `385 + 13`.

## 5. Batch 4 -> Batch 5 impact audit

New reproducibility artifacts:

- `scripts/free_agent_board_pre_batch5_snapshot.json`
- `scripts/audit_free_agent_board_batch5.py`
- `scripts/free_agent_board_batch5_impact.json`
- `scripts/free_agent_board_batch5_impact_report.md`

True deployed Batch 4 -> Batch 5 runtime comparison:

```text
Batch 4 rendered:      2019
Batch 5 rendered:      1998
Common Sleeper IDs:    1998
Removed:                 21
Added:                     0
Common rows changed:     506
Common rows unchanged:  1492
Value-only changes:      487
Metadata-change rows:     19
```

The common-row percentage-change distribution has a median of approximately **+0.6%**. The largest percentage movements are concentrated in lower-value players and/or rows whose stale board logic had been applying the wrong age/role/floor/production behavior.

Representative movements:

```text
Anquin Barnes      619 -> 965   +55.9%   (source age correction + canonical engine)
Marvin Mims       1315 -> 1744  +32.6%
Joseph Ossai      2179 -> 2657  +21.9%

Kendre Miller     1713 -> 734   -57.2%
Spencer Rattler   2277 -> 976   -57.1%
Tyrod Taylor      1366 -> 586   -57.1%
Tanner McKee      2277 -> 1073  -52.9%
```

These changes are not a new model calibration. They are the board adopting the already-live main calculator valuation engine/metadata plus the source-hygiene and FA-production-source fixes above.

## 6. CI / regression integration

Modified: `scripts/repo_regression_checks.py`

The suite now has **11 groups**. In addition to the existing deployed-IDP and repository invariants, it now:

- proves committed `data/free_agents.json` can be regenerated exactly from committed `players_cache.json` + committed roster state;
- runs the deep free-agent runtime parity validator;
- keeps the current free-agent source and production-source semantics under regression coverage.

Modified: `github-workflows/repo-regression-checks.yml`

Before the full suite, CI now runs:

```text
python3 scripts/sync_free_agent_valuation.py --selftest
python3 scripts/sync_free_agent_valuation.py --check
python3 scripts/validate_free_agent_valuation_parity.py
```

It remains read-only. CI does **not** auto-write `free-agent-board.html`; stale canonical source is a real deployment error and should fail visibly.

## 7. Clean-copy CI simulation

This batch was tested from a fresh copied working tree using the workflow sequence rather than only running individual scripts.

Results:

```text
snapshot_values selftest:                     PASS
sync_sleeper selftest:                        PASS
dual_eligibility selftest:                    PASS
team identity selftest:                       PASS
generate_player_positions selftest:           PASS
free-agent sync selftest:                     PASS
free-agent source --check:                    PASS
free-agent deep runtime validator:            PASS
player_positions regeneration:                PASS
repo regression suite:                        11/11 PASS
IDP V1 final deployment validator:            PASS (320 approved changes)
Batch5 impact audit:                          PASS
Python compile:                               48 files / 0 errors
JSON parse:                                   43 files / 0 errors
YAML parse:                                   20 files / 0 errors
index.html JavaScript:                        PASS
free-agent-board.html JavaScript:             PASS
free-agent sync --write idempotence:          PASS (byte-identical)
second full regression after write:           11/11 PASS
```

The clean simulation regenerated `player_positions.json`, the Batch5 impact artifacts, IDP deployment validation artifacts, and the synchronized board; each compared byte-identical to the retained working-tree version.

`index.html` is byte-for-byte identical to the deployed Batch 4 production file.

## 8. Scope boundary — one production lineage remains open

### CLOSED by Batch 5

```text
FREE-AGENT CORE VALUATION ENGINE PARITY: CLOSED
FREE-AGENT CANONICAL PLAYER METADATA PARITY: CLOSED
FREE-AGENT SOURCE/BADGE PRECEDENCE BUG: CLOSED
FREE-AGENT SOURCE-DATA HYGIENE GUARDS: CLOSED
```

### Still OPEN

```text
FREE-AGENT PRODUCTION LINEAGE / IDP V1 EXTENSION: OPEN
```

Reason: **385 currently displayed free agents still derive their production multiplier from the separate `FA_PROD_MULT_DATA` table.** Batch 5 ensures those values are routed into the canonical valuation engine correctly, but it does not claim that the off-roster production table itself has been regenerated under the newly deployed IDP V1 category methodology.

That should be the next independent modeling/data workstream, not silently bundled into frontend parity.

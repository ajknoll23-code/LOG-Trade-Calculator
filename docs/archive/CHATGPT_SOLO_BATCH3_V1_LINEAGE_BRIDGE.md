# Trade Desk — ChatGPT Solo Batch 3: Canonical History + V1 Lineage Bridge

**Date:** 2026-08-28  
**Status:** Complete for candidate-generation/validation. Production `index.html` remains unchanged.

## Goal

Build the V1 IDP production path without relying on stale `prod_mult_pipeline_output.json`, while separating the approved projection-source change from unrelated historical lineage drift.

## What changed

### 1. Canonical history component extracted

Created:

- `scripts/production_history_component.py`
- `scripts/production_history_components.json`

The module contains the existing 2025 history-side math only:

```text
2025 true PPG
-> empirical-Bayes shrinkage
-> durability projection
-> history_component
```

No V1 weighting, projection source, replacement baseline, position weight, or age-curve change was introduced.

The current durability R²-as-own-weight behavior was deliberately preserved. Its statistical interpretation remains a separate backlog question rather than being silently recalibrated during V1.

### 2. Legacy `prod_mult_pipeline.py` history math refactored with exact parity

Modified `scripts/prod_mult_pipeline.py` to call the new canonical history module instead of maintaining a second copy of shrinkage/durability math.

Before/after validation on the full legacy generator:

```text
1125 player records
full generated JSON structural equality: TRUE
baseline outputs: identical
prod_mult outputs: identical
```

So this was a pure extraction/refactor, not a model change.

The legacy pipeline is now explicitly labeled diagnostic/reference only because its projection side still uses the retired manual FantasyPros + Sleeper final-points blend and its absolute output does not reproduce the historical live table.

### 3. Four V1 candidate strategies were made explicit

Created diagnostic implementations for four distinct migration choices:

1. `idp_v1_production_candidate.py` — full canonical recompute.
2. `idp_v1_isolated_projection_candidate.py` — live anchor + projection delta + immediate rank-32 re-normalization.
3. `idp_v1_projection_only_candidate.py` — strict projection-only bridge with no baseline re-normalization.
4. `idp_v1_model_delta_transport_candidate.py` — internally consistent old-vs-V1 model delta transported onto actual live values.

This was necessary because the old live PROD_MULT table is not internally aligned to the current `rank-32 -> prod_mult 0.65` normalization:

```text
LB live rank-32 prod_mult = 0.691
DL live rank-32 prod_mult = 0.616
DB live rank-32 prod_mult = 0.662
```

Therefore any direct re-normalization automatically changes players even when their projection did not change.

## Candidate comparison result

### Full canonical recompute — rejected for first V1 release

It is the clean long-term architecture but absorbs too much historical lineage drift at once.

Final Trade Desk value P95 movement:

```text
LB +34.9%
DL +67.9%
DB +18.2%
```

Top-36 rank movers of >=5 spots:

```text
LB 2
DL 31
DB 7
```

This is far too much unrelated migration to bundle invisibly into a projection-source update.

### Isolated + re-normalized — not preferred

This still moves no-change players because it forces the historically drifted live table back through current rank-32 normalization.

### Strict projection-only — useful diagnostic, but incomplete

This cleanly preserves every no-delta player exactly, but it omits the legitimate replacement-baseline movement caused by the V1 projection model itself.

### Model-delta transport — preferred engineering candidate

**Preferred method:**

```text
canonical history + legacy projection
        -> internally consistent OLD model

canonical history + V1 projection
        -> internally consistent NEW model

old/new models each recompute rank-32 baseline
        -> delta in model ratio / prod_mult units

transport ONLY that delta onto actual pre-V1 live PROD_MULT
```

This retains the V1 model's legitimate replacement-baseline effect but does not import the old regenerated model's absolute level into production.

It also does not force the historically drifted live table through a separate baseline-normalization migration.

## Preferred candidate results

Comparable internally consistent old/new model cohort:

```text
330 of 404 live IDP keys
```

Players without a defensible old projection comparison:

```text
74 exact holds
```

Internal model baseline movement:

```text
LB +3.4%
DL +4.4%
DB +3.4%
```

This is highly consistent with the earlier V1 sensitivity work, where the baseline shifts were approximately +3.7% / +4.8% / +3.8%.

### Raw PROD_MULT movement from the true pre-V1 live table

```text
LB median   +0.0%   P90 +7.2%   P95 +23.1%
DL median   +2.2%   P90 +8.6%   P95 +12.0%
DB median   +0.5%   P90 +13.2%  P95 +17.0%
```

### Known anchors

```text
Bradley Chubb      +35.8%
Aidan Hutchinson    +6.2%
Myles Garrett       +5.8%
Fred Warner         -0.4%
Roquan Smith        -1.3%
E.J. Speed          -5.7%
Isaiah McDuffie    -25.8%
```

These are very close to the earlier validated sensitivity shape, unlike the other migration strategies.

### Final Trade Desk value movement

The preferred candidate was passed through the real current value engine, including production floor/rescue, age multiplier, and position weight.

Median final-value movement:

```text
LB -0.9%
DL +3.3%
DB +0.2%
```

P95 final-value movement:

```text
LB +2.5%
DL +8.2%
DB +5.2%
```

Top-24 players moving >=5 positional ranks:

```text
LB 1
DL 4
DB 1
```

This is materially more stable than the full canonical migration.

## Preferred bake preview

Created `scripts/prepare_idp_v1_bake.py`.

Default execution is **preview only**. It:

1. regenerates the preferred model-delta candidate;
2. verifies current `index.html` PROD_MULT values still exactly match the immutable pre-V1 baseline;
3. changes only the `PROD_MULT_DATA` object in a temporary candidate;
4. runs Node JavaScript syntax validation;
5. runs the real `snapshot_values.py` parser/value engine against the temporary candidate;
6. writes patch/report artifacts;
7. does not edit `index.html` unless explicit `--apply` is supplied.

Current preview:

```text
404 live IDP candidate keys
324 PROD_MULT entries would change
80 candidate entries remain exactly unchanged
LB changes: 117
DL changes: 91
DB changes: 116
565 PLAYER_DB rows parsed/evaluated successfully
```

Generated preview artifacts:

- `scripts/idp_v1_prod_mult_patch.json`
- `scripts/idp_v1_prod_mult_patch_report.md`
- `scripts/idp_v1_index_preview.patch`

**Production `index.html` was NOT modified.**

## Safety hardening

### Retired direct bake blocked

`scripts/bake_idp_ensemble_v1.py` is retained for historical/self-test reference, but normal execution now exits with a hard block. It can no longer accidentally write the stale-lineage bake.

`github-workflows/bake-idp-ensemble-v1.yml` was converted from a write/push workflow into a read-only candidate preparation/validation workflow.

### Legacy prod-mult workflow made read-only

`github-workflows/prod-mult-pipeline.yml` no longer commits generated legacy output. It is now explicitly a diagnostic workflow and uploads its generated output as a GitHub Actions artifact only.

### Historical live-anchored diagnostic marked superseded

`scripts/idp_v1_live_anchored_candidate.py` now requires explicit `--legacy-diagnostic` to run because it depends on the non-canonical generated legacy output. The preferred path is the model-delta transport candidate.

## Regression / integrity status

Current repo regression suite:

```text
PASS snapshot/live valuation parity: 565 players, 0 differences
PASS position/free-agent invariants
PASS dual-eligibility audit
PASS team identity
PASS alias/KTC position integrity
PASS canonical IDP V1 projection/baseline invariants
PASS canonical history/V1 bridge invariants
PASS preferred V1 bake-preview invariants
PASS index.html JavaScript syntax

ALL REPO REGRESSION CHECKS PASSED (9 groups)
```

Broader validation (final Batch 3 run):

```text
Python files parsed: 44, errors 0
JSON files parsed: 40, errors 0
YAML workflows parsed: 20, errors 0
index.html JS syntax: PASS
free-agent-board.html JS syntax: PASS
legacy prod_mult history-refactor parity: 1125/1125 records, exact structural equality
production index.html unchanged vs Batch 2: PASS (byte-identical SHA256)
non-canonical prod_mult_pipeline_output.json retained: NO
```


## Position-lineage finding surfaced during final review

The Batch 1 canonical position work exposed a separate historical lineage issue that must **not** be silently bundled into the first V1 projection release. Across the 404 live IDP PROD_MULT keys, **46 players** have a different legacy model position in `all_players.json` / historical production lineage than their current canonical valuation position in `player_positions.json`. The cohort is dominated by EDGE players historically grouped as LB that are now valued as DL (42 of the 46), plus a few LB/DB hybrids.

Examples include Bradley Chubb, Brian Burns, Micah Parsons, T.J. Watt, Will Anderson, Nolan Smith, Joshua Metellus, and others.

For Batch 3, this is deliberately handled as follows:

```text
OLD-vs-NEW model-delta calculation:
preserve legacy production-position grouping

Final Trade Desk value/rank validation:
use current PLAYER_DB valuation position
```

That choice is intentional release attribution: V1 is a projection-source change, not a position-classification migration. Switching the 46 players to current valuation positions inside the baseline model materially changes the DL/LB replacement baselines and would require a separate validation cycle. The mismatch cohort is now surfaced in candidate output and hard-guarded by the regression suite so it cannot change silently.

**Backlog:** migrate production baseline grouping to canonical valuation positions in a dedicated workstream after V1 is deployed and stabilized.

## Production status

```text
V1 PROJECTION METHODOLOGY:
CLOSED / VALIDATED

CANONICAL HISTORY EXTRACTION:
CLOSED / EXACT LEGACY PARITY

LEGACY ABSOLUTE PROD_MULT LINEAGE:
KNOWN DRIFT / DO NOT USE AS LIVE BASELINE

PREFERRED V1 MIGRATION METHOD:
MODEL-DELTA TRANSPORT

PREFERRED BAKE PREVIEW:
VALIDATED / 324 CHANGES

PRODUCTION index.html:
NOT YET MODIFIED
```

## Batch 3 files changed/created

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
- `docs/CHATGPT_SOLO_BATCH3_V1_LINEAGE_BRIDGE.md`

## Next recommended step

Do **not** rerun model research or baseline calibration.

The next decision is now narrow:

> approve or reject the **model-delta transport** candidate as the first V1 production migration method.

If approved, use `prepare_idp_v1_bake.py --apply` in a controlled working copy, update the stale `PROD_MULT_DATA` methodology comment in the same reviewed change, rerun all regression/final-value checks, and only then commit production `index.html`.

# Trade Desk — ChatGPT Solo Batch 4: IDP V1 Production Bake

**Date:** 2026-08-28  
**Status:** Production candidate applied in the controlled working tree and fully validated. Ready for GitHub upload.

## Goal

Take the Batch 3-approved **model-delta transport** V1 candidate through the actual production `index.html` value engine, catch any release-only interactions, apply only the validated changes, and produce a permanent old-live -> deployed-new audit.

## Important finding before final deployment

The first controlled apply exposed a real threshold interaction that Batch 3's raw `prod_mult` validation did not fully capture.

Four current speculative LBs had:

```text
2025 games played = 0
pre-V1 raw PROD_MULT = 0.15
```

The live `productionMultiplier()` function rescues those exact-floor/no-history players to their role estimate (`Speculative = 0.22`). The first V1 transport candidate moved their raw multipliers only slightly above 0.15:

```text
Jaishawn Barham   0.1500 -> 0.1675
Jake Golday       0.1500 -> 0.1841
Kaleb Elarms-Orr  0.1500 -> 0.1504
Kyle Louis        0.1500 -> 0.1596
```

Because the live rescue only fires at the literal 0.15 floor, those tiny *positive* raw changes would have disabled the rescue and created large *negative* final-value changes, including roughly -25% to -33% for several players.

That behavior was not part of the earlier validated V1 sensitivity cohort because the sensitivity study excluded no-history players.

### Resolution

A **migration-specific floor-rescue discontinuity guard** was added to `idp_v1_model_delta_transport_candidate.py`:

- If a current `PLAYER_DB` player had zero real 2025 games,
- had a pre-V1 raw multiplier at exactly 0.15,
- and the transported V1 raw value moves above 0.15 but still does not clear the player's role estimate,
- hold the raw multiplier at its pre-V1 0.15 value.

This preserves the existing live role-floor behavior rather than silently turning a small positive V1 model delta into a large final-value loss.

This is **not** a recalibration of `productionMultiplier()` and does not change its behavior for the rest of the player pool.

Guarded current players:

```text
Jaishawn Barham
Jake Golday
Kaleb Elarms-Orr
Kyle Louis
```

The model-delta candidate self-test now hard-asserts this exact four-player guard cohort.

## Final production bake

After the guard was added, all candidates and comparison artifacts were regenerated from the immutable pre-V1 baseline.

Final patch:

```text
404 live IDP candidate keys
320 actual PROD_MULT changes
84 exact holds
  - 74 no defensible comparable old projection
  - 4 floor-rescue discontinuity guards
  - remaining exact holds from zero net transported delta
0 non-IDP final-value changes
```

`index.html` was then updated with the 320 approved raw multiplier changes.

The stale production methodology comment above `PROD_MULT_DATA` was replaced with documentation of:

- the V1 category architecture,
- official FantasyPros + Sleeper inputs,
- hardened identity resolution,
- model-delta transport,
- the floor-rescue migration guard,
- and the separate 46-player position-lineage backlog.

No content outside the methodology-comment + `PROD_MULT_DATA` region changed relative to Batch 3.

## Final true-live validation

Created:

- `scripts/validate_idp_v1_final_deployment.py`
- `scripts/idp_v1_final_deployment_validation.json`
- `scripts/idp_v1_final_deployment_validation.md`

The validator reconstructs the OLD side from the immutable pre-V1 `PROD_MULT_DATA` snapshot and compares it to the actual deployed working-tree `index.html`, while holding every other valuation constant identical.

### Deployment integrity

```text
823 pre-V1 PROD_MULT keys
823 deployed PROD_MULT keys
320 approved changed keys
320 actual changed keys
404 candidate IDP keys match approved candidate exactly
0 unexpected PROD_MULT changes
0 offense final-value changes
46 legacy/current IDP position mismatches still isolated
```

### Internal V1 replacement-baseline movement

```text
LB +3.4%
DL +4.4%
DB +3.4%
```

### True live old -> deployed final Trade Desk value movement

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 79 | -0.5% | +1.7% | +2.5% | -6.5% | +23.9% |
| DL | 86 | +3.3% | +7.3% | +8.2% | -12.6% | +13.4% |
| DB | 65 | +0.2% | +3.1% | +5.2% | -7.1% | +44.5% |

The largest final DB percentage is A.J. Haulcy, a low-value depth/rookie asset moving 796 -> 1150; his positional rank changes only one spot. The largest current top-tier movements remain controlled.

### Rank stability

| Pos | Top-24 movers >=5 ranks | Top-36 movers >=5 ranks | Max abs top-36 move |
|---|---:|---:|---:|
| LB | 1 | 1 | 5 |
| DL | 4 | 7 | 8 |
| DB | 1 | 2 | 5 |

### Source cohorts

```text
both          273 candidates
fp_only        35
sleeper_only   44
no_new_data    52
```

No-new-data candidate median/P95 movement is exactly 0.0%.

### Raw candidate clamp occupancy

```text
Pre-V1 floor 0.15: 25
Deployed floor 0.15: 24
Pre-V1 ceiling 1.55: 0
Deployed ceiling 1.55: 0
```

No ceiling compression was introduced.

## Post-deployment CI/regression changes

### Deterministic generated history artifact

`production_history_component.py` previously iterated a Python `set` when writing position-level metadata, so `production_history_components.json` could be semantically identical but byte-different across processes. That would make the GitHub freshness check fail spuriously. `TRACKED_POSITIONS` is now an ordered tuple, and the full generated-diagnostics chain was run twice with **byte-identical outputs on the second run**.

### `repo_regression_checks.py`

Expanded from 9 to **10 groups**. It now verifies the actual deployed V1 table:

```text
PASS deployed IDP V1 invariants:
320 approved PROD_MULT changes
84 exact holds
4 floor-rescue guards
0 offense value changes
```

### `validate_idp_v1_candidates.py`

Changed so the OLD side always comes from the immutable pre-V1 baseline rather than the currently deployed `index.html`. This keeps historical candidate-comparison artifacts reproducible after V1 deployment.

### Workflows

`github-workflows/bake-idp-ensemble-v1.yml` is now a read-only **Validate Deployed IDP V1** workflow. It no longer calls the pre-deployment bake-preparation path.

`github-workflows/idp-v1-candidate-validation.yml` now runs the final deployment validator and no longer tries to regenerate the one-time pre-deployment patch from an already-deployed index.

`prepare_idp_v1_bake.py` remains retained as the pre-deployment/one-time bake tool. Its documentation now explicitly says that its immutable-baseline guard is expected to refuse another preview/apply after deployment; use the final deployment validator instead.

## Final validation status

```text
Canonical history self-test: PASS
Canonical V1 projection self-test: PASS
All candidate self-tests: PASS
E.J. Speed regression: PASS (95.43)
Model-delta floor-rescue guard self-test: PASS
Final deployment validator: PASS
Repo regression suite: 10 / 10 PASS

Python AST: 45 files, 0 errors
JSON parse: 41 files, 0 errors
YAML parse: 20 workflows, 0 errors
index.html JavaScript: PASS
free-agent-board.html JavaScript: PASS

Batch 3 -> Batch 4 index attribution:
prefix before production-methodology comment: byte-identical
suffix after PROD_MULT_DATA: byte-identical
```

## Production status

```text
IDP V1 PROJECTION METHODOLOGY:
CLOSED / VALIDATED

MODEL-DELTA MIGRATION:
DEPLOYED IN CONTROLLED WORKING TREE / VALIDATED

PRODUCTION index.html:
READY FOR GITHUB UPLOAD

POSITION-LINEAGE MIGRATION (46 players):
BACKLOG / DO NOT MIX INTO V1

DURABILITY WEIGHT RECALIBRATION:
BACKLOG
```

## Recommended next step

Upload the Batch 4 changed files to GitHub. After GitHub reflects this exact working tree, run the read-only V1 validation workflow once. If it passes, close the IDP V1 deployment workstream and move to the next independent repo improvement rather than reopening projection-weight research.

## Batch 4 files to add/update in GitHub

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

**Total Batch 4 files to add/update: 25.**

# Package Adjustment NextGen V2 — Prospective Time-Holdout Preregistration V1

**Status:** frozen before prospective catalog generation and voting activation

## Purpose

This preregistration defines the one-time prospective validation of the
frozen first-wave research candidate **pkgnv2-m2b-v1**. It freezes the
study design before any prospective challenge catalog is generated and
before any prospective votes exist.

This document authorizes **no production change**.

## Frozen candidate and control

M2b remains byte-for-byte parameter frozen:

- Parameter vector:
`[0.0, 0.0, 0.0362911410036889, 0.0074486570102035975, 4.745193657558804, 0.24927858289620897]`
- Beta: **115.030079790689**
- Delta-left: **0.249278582896**
- Candidate lambda at freeze: **1.0**
- Refitting/recalibration: **not allowed**

M0 is also frozen as a fixed prospective control:

- Parameter vector:
`[4.67248211670666, 0.24949028824223837]`
- Beta: **106.962907630852**
- Delta-left: **0.249490288242**
- Refitting/recalibration: **not allowed**

The spent first-wave structural holdouts may never be reopened for tuning.

## Fresh prospective challenge catalog

A separate later workflow must deterministically generate a **fresh**
129-challenge player-only catalog using seed **20260912**:

- 90 core 2v2
- 15 fragmentation
- 24 structural-topology 3v3
- 43 low / 43 mid / 43 high
- 24 evaluation cells
- all challenges evaluation-only
- all sides multi-piece
- no exact trade signature may overlap the first-wave catalog
- no duplicate trade signature may appear within the prospective catalog
- maximum player appearance: **11**
- values remain hidden from voters

Generation may use raw FV, topology, scale anchors, deterministic seed, and
a pass/fail M2b mathematical-support check. It may **not** use vote outcomes,
model probabilities, M2b-vs-M0 gaps, or model agreement to select questions.

## Prospective transport and sampling

Prospective votes use a new isolated transport namespace:

- Vote prefix: `__pkgnv2p1__|`
- Meta prefix: `__pkgnv2p1_meta__|`
- Schema marker: `__pkgnv2p1_schema__|1`

A later activation workflow must freeze a valid-ballot start timestamp.
Only rows strictly after that cutoff are eligible.

Sampling remains outcome-blind and exactly equal-cell:

1. family by frozen probabilities 0.625 / 0.125 / 0.25
2. cell uniformly within selected family
3. challenge uniformly within selected cell
4. displayed side randomized 50/50

Every cell therefore has exact unconditional probability **1/24**.

## Evidence maturity and stopping

Prospective collection is coverage-driven only.

- Daily valid vote cap per voter: **20**
- Prospective effective lifetime cap per voter: **30**
- Minimum distinct voters: **30**
- Minimum effective votes per each of 24 cells: **15**
- Minimum distinct voters per each cell: **10**
- Exact checkpoints: **900 / 1000 effective votes**
- Hard cap: **1000**
- Stop at the first checkpoint where every coverage gate passes

Vote direction, model performance, significance, bootstrap results, and
model agreement are forbidden from influencing stopping.

### Coverage-only simulation

The frozen simulation used **100,000** trials at the first
900-vote checkpoint.

- P(all cells >=15 votes): **0.99980**
- P(all cells >=10 distinct voters): **0.99994**
- P(both gates): **0.99976**
- p10 minimum cell votes: **23**
- median minimum cell votes: **26**
- p10 minimum distinct voters/cell: **15**
- median minimum distinct voters/cell: **17**

No outcomes or model scores were used in that simulation.

## One-time prospective evaluation

Once coverage matures, predictions are evaluated **without fitting**.

Primary metric:
equal-cell macro log loss across all 24 prospective cells.

M2b must satisfy all three frozen gates:

1. Combined log-loss improvement over M0 >= **0.005**
2. No family-level log-loss regression greater than **0.005**
for core, fragmentation, or topology
3. M2b beats M0 in at least **80%** of **5,000** valid fixed-prediction
voter-cluster bootstrap draws

The 90% bootstrap improvement interval is reported, but it is **not**
required to be wholly above zero.

## Governance

Passing the prospective gate makes M2b only
**production-candidate eligible**. It does not change production.

Production remains Package Adjustment V1.6 until a separate,
human-approved production decision workflow is executed.

## Required next sequence

1. Freeze this preregistration
2. Generate and freeze the fresh prospective catalog
3. Validate catalog without outcomes
4. Activate prospective voting with a new transport namespace
5. Collect to the first coverage-qualified checkpoint
6. Freeze that exact evidence checkpoint
7. Evaluate frozen M2b vs frozen M0 exactly once
8. If it passes, make a separate human production decision

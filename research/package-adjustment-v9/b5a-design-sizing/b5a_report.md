# Package Adjustment V9 — B5A Joint-Gate Design Sizing

**Status:** `PASS_PLANNING_ONLY_NO_V9_DESIGN_FROZEN`

This workflow is a read-only planning bridge from the durably closed V8 study to a separately preregistered V9. It does not select or freeze a V9 candidate, final gate, or sample size.

## Corrections relative to superseded B5

- Power is evaluated for the **joint decision rule**, not one gate at a time.
- V8 C1-vs-C0 loss-difference variance is **not** treated as V9-vs-V1.7 variance.
- V8 votes are used only to estimate semantically coded human/challenge nuisance variation and its bootstrap uncertainty.
- The simulation includes refitting nuisance calibration inside deterministic challenge folds.
- Candidate/comparator behavior is generative; production V1.7 predictions are never evaluated on V8 outcomes.
- A real constrained assignment is constructed and classified EXACT / APPROXIMATE / INFEASIBLE.
- Small-topology uncertainty uses a t reference rather than a normal-z shortcut.

## Nuisance planning estimates

- Within-topology challenge-effect SD point estimate: **5.4759**
- Challenge-effect SD bootstrap p90: **5.9117**
- Voter-effect SD point estimate: **0.5857**
- Voter-effect SD bootstrap p90: **0.6543**
- Left-bias logit point estimate: **0.0888**

## Principal planning slice

The table below uses a topology NI margin of 0.010 and an overall minimum mean benefit of 0.005. It is **not** a frozen V9 design decision.

| C/topology | Votes/challenge | Voters | Workload | Ballots | Assignment | Good 0.02 joint PASS | Good 0.05 joint PASS | Null false PASS | Unsafe detection |
|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 20 | 6 | 30 | 24 | 720 | APPROXIMATE | 0.000 | NA | 0.000 | 1.000 |
| 18 | 8 | 36 | 24 | 864 | APPROXIMATE | 0.000 | NA | 0.000 | 1.000 |
| 24 | 6 | 36 | 24 | 864 | APPROXIMATE | 0.000 | NA | 0.000 | 1.000 |
| 20 | 8 | 40 | 24 | 960 | APPROXIMATE | 0.000 | NA | 0.000 | 1.000 |
| 30 | 6 | 45 | 24 | 1080 | APPROXIMATE | 0.000 | NA | 0.000 | 1.000 |
| 24 | 8 | 48 | 24 | 1152 | APPROXIMATE | 0.000 | NA | 0.000 | 1.000 |
| 25 | 8 | 50 | 24 | 1200 | APPROXIMATE | 0.000 | NA | 0.000 | 0.988 |
| 30 | 8 | 60 | 24 | 1440 | APPROXIMATE | 0.000 | NA | 0.000 | 1.000 |

## Scientific interpretation

These probabilities are a **design envelope**, not final V9 power. The exact production V1.7 comparator behavior and exact V9 candidate/evaluator have intentionally not been tested on V8 outcomes. After architecture/comparator/gates are frozen, final design sizing must rerun the full frozen evaluator on synthetic data before any fresh V9 human vote is collected.

**Production change authorized:** no.


# Package Adjustment V4 — Phase 3F One-Time Confirmation Evaluation

**Status:** `CONFIRMATION_FAILED_RESEARCH_ONLY`

- Frozen evidence: **600.00 effective votes / 31 voter clusters / 231 challenges / 24 cells**
- Raw control held-out log loss: **0.674732**
- Selected candidate: **`elite-frag-s75-p210-p330`**
- Best-vs-runner-up gap: **0.019545** (resolved if >= 0.002000)
- Candidate selection: **RESOLVED**

## Frozen candidate comparison

| Candidate | Held-out log loss | Improvement vs raw | All deployment gates |
|---|---:|---:|---|
| elite-frag-s75-p210-p330 | 0.629618 | 0.045114 | FAIL |
| elite-frag-s50-p210-p330 | 0.649164 | 0.025569 | FAIL |

## Deployment gates by frozen candidate

### `elite-frag-s75-p210-p330`

- Improvement >= 0.005: **PASS** (0.045114)
- Challenge-cluster bootstrap favorable >= 0.90: **PASS** (0.9716)
- Max topology×asset-mix regression <= 0.03: **FAIL** (0.086259)
- 24/24 frozen coverage: **PASS**

### `elite-frag-s50-p210-p330`

- Improvement >= 0.005: **PASS** (0.025569)
- Challenge-cluster bootstrap favorable >= 0.90: **PASS** (0.9078)
- Max topology×asset-mix regression <= 0.03: **FAIL** (0.081646)
- 24/24 frozen coverage: **PASS**

## Frozen interpretation

- Candidates independently passing every deployment gate: **none**
- Family confirmation supported: **NO**
- Production-candidate eligible: **NO**

Candidate selection resolved, but the selected candidate failed at least one preregistered deployment gate. Do not substitute the runner-up post hoc. Production remains V1.6.

> No parameter tuning, KTC-example tiebreaker, runner-up substitution, or automatic production promotion was performed.

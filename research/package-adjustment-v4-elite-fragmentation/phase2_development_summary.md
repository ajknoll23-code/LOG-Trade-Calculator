# Package Adjustment V4 — Phase 2 Spent-Evidence Development

**Status:** `V4_DEVELOPMENT_CANDIDATE_FAMILY_FROZEN_FOR_FRESH_CONFIRMATION`

## Evidence eligibility

- V3 spent source ballots: **600**
- V4-eligible development ballots: **428**
- Excluded by frozen V4 asset rules: **172**
- Eligible voter clusters: **30 / 30**
- Eligible distinct challenges: **161**

Joe Mixon and 2029+ draft-pick challenges were excluded before eligible ballot outcomes were used for model development.

## Controls

- Raw additive control: **0.693350**
- V3 g2.15 reference: **0.693350**

## Best V4 structure by held-out log loss

- Candidate: **`elite-frag-s75-p210-p330`**
- Held-out log loss: **0.693350**
- Improvement vs raw: **0.000000**
- Improvement vs V3 reference: **0.000000**
- Positive folds vs raw: **4 / 5**
- Max topology×asset-mix regression: **0.000000**

## Frozen fresh-confirmation family

- `elite-frag-s75-p210-p330` — development log loss **0.693350**
- `elite-frag-s50-p210-p330` — development log loss **0.693350**

No production formula changed. These spent V3 votes cannot count toward V4 confirmation.

Generate a new unreleased V4 fresh-confirmation catalog under the Phase 1 frozen contract. The spent V3 ballots cannot count.

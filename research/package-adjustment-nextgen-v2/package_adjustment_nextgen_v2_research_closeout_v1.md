# Package Adjustment NextGen V2 Research Closeout

**Status:** `research_closed_no_successor_candidate`

The Package Adjustment NextGen V2 research branch is complete.

## Final production decision

**No production change.** Production remains:

`v1.6-v5-size2-composition-overlay`

## M2b prospective result

The frozen M2b candidate failed its one-time prospective validation.

- M0 combined log loss: **0.858674**
- M2b combined log loss: **0.856747**
- Improvement: **0.001926**
- Required improvement: **0.005000**
- Bootstrap favorable fraction: **0.9612**
- Fragmentation regression: **0.026836**

M2b showed some real directional signal, but the preregistered effect-size floor and family-safety gate were not met.

## M3 development result

The preregistered M3 development cycle also stopped cleanly.

| Model | CV loss | Improvement vs M0 | Positive folds | Eligible |
|---|---:|---:|---:|---|
| M0 | 0.691505 | — | — | baseline |
| M2b reference | 0.694285 | -0.002780 | — | reference only |
| M3a | 0.694284 | -0.002779 | 3 / 4 | NO |
| M3b | 0.694284 | -0.002779 | 3 / 4 | NO |
| M3c | 0.694285 | -0.002780 | 3 / 4 | NO |

No M3 model class qualified. No M3 candidate was selected or frozen.

## Governance closeout

The exact 900-vote dataset is spent development evidence. Do not collect fresh votes for this M3 branch because there is no frozen candidate to validate.

Do not create an M4 by continuing to tune against these same results. If package adjustment is revisited later, it must start as a genuinely new research cycle with a new hypothesis, a new preregistration, and fresh confirmation evidence.

The completed research artifacts remain in the repository for provenance.

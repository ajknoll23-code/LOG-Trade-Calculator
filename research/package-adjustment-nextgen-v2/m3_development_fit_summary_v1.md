# NextGen V2 M3 Development Fit

**Status:** `no_m3_candidate_qualified_under_frozen_rules`

Production remains `v1.6-v5-size2-composition-overlay`.

## Cross-validated development results

| Model | CV loss | Improvement vs M0 | Positive folds | Eligible |
|---|---:|---:|---:|---|
| M0 | 0.691505 | — | — | baseline |
| M2b reference | 0.694285 | -0.002780 | — | reference only |
| M3a | 0.694284 | -0.002779 | 3 / 4 | NO |
| M3b | 0.694284 | -0.002779 | 3 / 4 | NO |
| M3c | 0.694285 | -0.002780 | 3 / 4 | NO |

## Family regressions versus M0

- **M3a:** core 0.001517; fragmentation 0.010037; structural 3v3 0.002305
- **M3b:** core 0.001517; fragmentation 0.010038; structural 3v3 0.002305
- **M3c:** core 0.001517; fragmentation 0.010041; structural 3v3 0.002306

## Frozen selection

No M3 candidate qualified under the frozen development rules.

This M3 branch stops here. No candidate was manufactured after seeing the results.

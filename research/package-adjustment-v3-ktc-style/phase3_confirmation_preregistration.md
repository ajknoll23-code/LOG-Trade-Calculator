# Package Adjustment V3 — Phase 3 Fresh Confirmation Preregistration

**Status:** `FROZEN_FRESH_CONFIRMATION_PREREGISTRATION`

**Production remains V1.6. No voting is activated by this workflow.**

## Frozen candidate family

- `power-g2.01`
- `power-g2.15`
- `power-g2.30`

The five KTC screenshots were development anchors only. They cannot select the winner.

## Fresh catalog

- 24 research cells
- 6 topologies: 1v2, 1v3, 2v2, 2v3, 3v3, 3v4
- 2 asset mixes: players-only and includes-picks
- 2 candidate-disagreement bands
- 10 challenges per cell
- 240 total challenges
- Candidate predictions are intentionally used to find discriminating trades, but are never shown to voters.
- Exact prior KTC examples and the eight known completed league trades are excluded.

## Fresh-vote stopping rule

- 20 valid ballots per voter per UTC day
- 30 effective lifetime ballots per voter
- At least 30 distinct voters overall
- At least 15 effective votes per research cell
- At least 10 distinct voters per research cell
- Exact checkpoints: 600, 700, 800 effective votes
- Stop at the first checkpoint that passes every coverage gate
- 800 is the hard cap; if coverage still fails, stop unresolved

No response direction, significance, or candidate performance may affect stopping.

## Evaluation after the exact checkpoint is frozen

The three frozen gamma models are compared against a raw-additive gamma=1 control using voter-grouped 5-fold held-out log loss. Calibration scale and randomized-left bias are refit inside each training fold.

A production successor is eligible only if it improves held-out log loss over the raw-additive control by at least 0.005, clears a 0.90 challenge-cluster bootstrap favorable fraction, and has no topology × asset-mix regression worse than 0.03.

If the top two gamma candidates are within 0.002 held-out log loss, gamma selection is unresolved rather than broken using the five KTC development examples.

The old 900-vote dataset is not part of this study.

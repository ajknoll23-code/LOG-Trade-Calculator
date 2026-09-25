# Package Adjustment V7 Phase 1A — Power + 40-Trade Catalog Freeze

**Decision:** `FREEZE_V7_PHASE1A_AT_40_VOTER_FIRST_CHECKPOINT`

No V7 vote has been collected or read. Production remains unchanged.

## Power

- 30 voters conservative planning power: 0.7993 — below 0.80.
- 40 voters conservative planning power: 0.8894 — passes.
- 50 voters remains the hard cap, not the primary target.
- First maturity checkpoint: 40 distinct voters.
- Coverage gate: at least 32 distinct voters on every one of the 40 challenges.

## Frozen development catalog

- Frozen rostered player universe: 472 players.
- Exactly 40 player-only challenges.
- Topologies: 2v2=6, 2v3=8, 2v4=6, 3v3=6, 3v4=8, 4v4=6.
- Direction balance by top-asset share: {'A': 20, 'B': 20}.
- Contrast bands: {'high': 14, 'low': 14, 'moderate': 12}.
- Unique players used: 236.
- Maximum appearances by one player: 2.
- Position challenge coverage: {'DB': 20, 'DL': 21, 'LB': 22, 'QB': 22, 'RB': 31, 'TE': 14, 'WR': 34}.

Primary concentration direction is defined by top-asset share. HHI is frozen as a secondary descriptor because raw HHI is mechanically affected by 2-vs-3-vs-4 asset count; topology already captures cardinality.

Draft picks remain excluded until the independent pick/player FV bridge is frozen.

## Next

Build a separate voting-activation workflow/UI using this exact catalog. Do not regenerate the catalog after votes begin.


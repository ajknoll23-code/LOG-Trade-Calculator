# Schedule Utility V1 — Phase 1E-B Private 4for4 Source Bridge

**Decision:** `PASS_PRIVATE_SOURCE_BRIDGE`

The preregistered source bridge passed using the exact frozen LOG-SAPA V1 implementation and the previously admitted private 4for4 source bundle.

## Frozen primary gate

- Median Spearman: **0.998900** (required >= 0.60)
- Cells with Spearman >= 0.50: **7/7** (required >= 6/7)
- Minimum cell Spearman: **0.994958** (required >= 0.30)
- Result: **PASS**

## Cell-level aggregate diagnostics

- QB_HALF: Spearman **0.999908**, coverage 32/32, mean |rank diff| 0.03125
- RB_HALF: Spearman **0.998442**, coverage 32/32, mean |rank diff| 0.21875
- WR_HALF: Spearman **0.994958**, coverage 32/32, mean |rank diff| 0.59375
- TE_HALF: Spearman **1.000000**, coverage 32/32, mean |rank diff| 0.00000
- RB_PPR: Spearman **0.998900**, coverage 32/32, mean |rank diff| 0.18750
- WR_PPR: Spearman **0.998625**, coverage 32/32, mean |rank diff| 0.21875
- TE_PPR: Spearman **0.999817**, coverage 32/32, mean |rank diff| 0.06250

## Privacy / licensing

- Private 4for4 source hashes were reverified before computation.
- No provider team-level values are frozen or committed.
- No raw/licensed 4for4 rows are committed.
- The public GitHub Action does not read the private provider CSVs.

## Outcome firewall

- Historical 2015-2025 validation outcomes remain unopened.
- Phase 2 outcome testing is **not yet authorized**.
- Phase 2 preregistration is now authorized.

## Production impact

None.

Next: **Phase 2A — retrospective predictive validation preregistration**.

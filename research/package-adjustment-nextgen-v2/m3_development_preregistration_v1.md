# NextGen V2 M3 Development Preregistration

**Status:** `frozen_m3_development_preregistration`

This freezes the M3 development rules before any M3 fitting. The existing 900-effective-vote prospective dataset is now spent development evidence only. Production remains `v1.6-v5-size2-composition-overlay`.

## Model idea

M3 does not apply M2b universally. It learns a bounded trade-level shrinkage gate:

`M3 side score = M0 side score + alpha(trade) * (M2b side score - M0 side score)`

`alpha` is identical for both sides of the trade and uses only production-computable trade features.

### Candidate classes
- **M3a:** scale gate.
- **M3b:** scale + asset-count topology gate.
- **M3c:** scale + topology + concentration gate.

Research family labels, research scale labels, challenge IDs, and human outcomes are forbidden as scoring inputs.

## Development validation

Use deterministic 4-fold grouped challenge cross-validation. All ballots for one challenge stay together, and challenge assignment is stratified within each of the 24 research cells.

An M3 class is eligible only if:
- combined CV improvement versus refit M0 is at least **0.003**;
- no research family regresses by more than **0.003**;
- at least **3 of 4** folds improve;
- optimization completes without a material boundary solution.

If multiple candidates qualify, prefer the simpler one if it is within **0.001** log loss of the best eligible candidate.

## Governance

If one class qualifies, refit only that selected class on all spent development evidence and freeze its parameters. It remains research-only.

The 900-vote dataset can never be reused as fresh M3 confirmation. A new candidate freeze, new prospective preregistration, fresh catalog, and fresh votes are required before production eligibility can be reconsidered.

No automatic production promotion is allowed.

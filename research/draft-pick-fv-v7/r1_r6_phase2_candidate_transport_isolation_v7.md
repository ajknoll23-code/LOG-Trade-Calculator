# Draft Pick FV V7 — Phase 2 Candidate Transport Isolation Amendment

V3 exhausted the frozen residual router for all 22 residual R25 batches and recovered 0 complete batch checkpoints. The observed failures are legacy MFL transport failures, not identity or outcome errors.

V4 changes only transport-failure handling. A candidate with previously proven V3 transport exhaustion is recorded as `transport_unresolved` and is not requested again. Any newly encountered transport failure must exhaust the same frozen residual router before receiving that status. The workflow then continues to the next frozen candidate in the same batch.

Transport-unresolved candidates remain members of the frozen candidate universe. They are not clean leagues, ineligible leagues, source rejections, replacement candidates, or zero-valued observations. No new league search, replacement candidate, source substitution, candidate reordering, identity change, outcome read, fit, or production change is authorized.

The amendment is explicitly methodological and therefore records `scientific_contract_changed: true`, limited to transport-failure censoring. Assembly is permitted only if every frozen candidate receives exactly one disposition and total transport censoring remains at or below 1% of the 6,203-candidate universe.

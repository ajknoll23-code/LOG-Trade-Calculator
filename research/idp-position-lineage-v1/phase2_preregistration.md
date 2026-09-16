# IDP Position Lineage V1 — Phase 2 Shadow Sanity

**Status:** `FROZEN_PRE_SHADOW_SANITY`

Phase 2 uses the exact frozen Phase 1B candidate. It does not refit or
regenerate the candidate.

Because Phase 1 and Phase 1B already revealed that the position-lineage
correction materially changes DL values and rankings, Phase 2 deliberately
avoids inventing post-hoc movement thresholds.

The key scientific sanity check is transport-offset preservation. IDP V1
was deployed by transporting reproducible model deltas onto the true live
production multiplier. Position Lineage V1 must preserve that same
unexplained live-model offset rather than applying it twice:

    deployed_raw - clean_legacy_model
      ==
    candidate_raw - clean_current_model

except for documented clamp/rounding.

Position, age, role, no-history lineage, age multiplier, and position
weight are held fixed in the shadow. Therefore any candidate FV movement
must arise only from the approved raw production-multiplier change.

Distribution and ranking effects are reported as diagnostics for the
deployment decision, not retrofitted as scientific pass/fail thresholds.

A PASS does not authorize production deployment.

# IDP Position Lineage V1 — Phase 2B Age-Feedback Shadow

**Status:** `FROZEN_PRE_AGE_FEEDBACK_SHADOW`

Phase 2 remains a scientific STOP. This successor exists because the
failed gate required `age_mult` itself to remain unchanged even though
the production age formula intentionally uses production multiplier for
pre-peak players.

Phase 2B does not change the candidate or model. It freezes the correct
invariant: age, role, position, position weight, no-history lineage, and
the age formula remain unchanged, while the age multiplier output must
recompute exactly from that same formula when production changes.

For every candidate, Phase 2B decomposes the final FV movement into:

1. direct production effect with the exact current age multiplier held;
2. endogenous age-feedback effect from recomputing the unchanged age
   formula with the candidate production multiplier.

Phase 2B also preserves the original IDP V1 transported-model offset and
all Phase 1B isolation gates. Movement magnitude remains diagnostic only.

A PASS does not authorize deployment.

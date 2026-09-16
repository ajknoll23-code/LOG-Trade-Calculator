# IDP Position Lineage V1 — Phase 1B Current-Core Rebase

**Status:** `FROZEN_BEFORE_CURRENT_CORE_COHORT_SELECTION`

Phase 1 is permanently retained as a scientific STOP. Its failure came
from a held free-agent-only row whose current position had changed after
the original IDP V1 release.

Phase 1B does not edit that result. It defines the production-relevant
problem directly: among all players in the immutable deployed IDP V1
artifact, select the players who currently render in the core calculator
and whose authoritative current IDP position differs from the legacy
position used by the frozen IDP production model.

Cohort selection uses only identity, current core scope, and current
position. It happens before candidate movement is calculated.

Free-agent-only players are out of scope because Free-Agent Production V2
is now a separate deployed production path.

The model inputs and transport math remain frozen. No movement threshold
is introduced in Phase 1B because Phase 1 has already exposed approximate
movement. Movement and rank effects are diagnostics for the next shadow
review, not post-hoc scientific gates.

Production remains unchanged.

# IDP Position Lineage V1 — Phase 1 Preregistration

**Status:** `FROZEN_PRE_EVALUATION`

This study addresses only the 46 IDP players that the deployed IDP V1
release deliberately left on a legacy model position even though the
production valuation engine assigns them a different current IDP position.

The study does **not** refit projection weights, durability, replacement
depth, position weights, age curves, or the production-multiplier transform.

The immutable IDP V1 release is the evidence source. Later rolling source
refreshes are deliberately excluded.

For each mismatch, Phase 1 recomputes the frozen history component using
the player's frozen current valuation position. All 46 rows remain in
the audit, but only rows currently present in the production-parity core
valuation universe can become candidates. Free-agent-only or otherwise
non-rendered rows are explicit holds. Position authority is checked against
the current generated player-position map for all 46 and the live merged
PLAYER_DB for current-core rows. The audit preserves the frozen V1
forward projection, evaluates against the already-frozen V1 replacement
baseline for that current position, and transports only the resulting clean
position-lineage model delta onto the actual deployed raw production
multiplier.

Rows without comparable frozen V1 projection/model evidence are held.
The existing exact-floor/no-history migration guard is preserved.

Phase 1 is research-only and cannot change production.

# Draft Pick FV V3 — Custom Player Identity Namespace Audit

**Decision:** `IDENTITY_NAMESPACE_COLLISION_CONFIRMED_PROTOCOL_CLARIFICATION_REQUIRED`

This audit is diagnostic only. It does **not** authorize historical outcome ingestion and does not change the frozen 95% identity gate.

## Why this audit exists

The previous identity resolver queried MFL's `players` endpoint without the league ID. MFL tooling documents that league-specific custom players require a league-scoped connection. The unresolved set contained low IDs that resolved to unrelated legacy NFL players when interpreted against the global MFL player table.

## Results

- Unresolved MFL source IDs entering audit: **117**
- League/ID occurrence groups: **493**
- Groups with league-scoped metadata: **493**
- Groups with unique same-class stable match: **1**
- MFL IDs with name/position namespace collisions: **90**
- MFL IDs with stable-identity collisions: **0**
- Any namespace-collision MFL IDs: **90**
- Globally consistent resolvable MFL IDs: **0**

## Match-status counts

- `metadata_present_no_external_identity`: **167**
- `name_position_only_future_draft_class`: **303**
- `name_position_only_past_draft_class`: **1**
- `name_position_other_class_or_mixed`: **21**
- `unique_same_class_stable_match`: **1**

## Outcome firewall

- Historical NFL outcomes read: **No**
- Candidate fit performed: **No**
- Locked validation scored: **No**
- Production change authorized: **No**

## Next step

Freeze an explicit pre-outcome identity-namespace clarification before any historical outcome ingestion. Do not change the 95% threshold. The clarification must define how league-local custom MFL IDs map to stable drafted-player identities.

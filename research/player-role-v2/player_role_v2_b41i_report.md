# Player Role Engine V2 — B41I-R4 Outcome-Blind Recovery Eligibility Audit

## Decision

**PASS_B41I_OUTCOME_BLIND_RECOVERY_ELIGIBLE_FOR_B41J**

- Recovery mode: `CURRENT_UPSTREAM_IDENTITY_SNAPSHOT_FROZEN`
- Continuation class: `OUTCOME_BLIND_IDENTITY_SOURCE_AMENDMENT`
- Identity-source amendment required: `True`
- Human holdout performance read by B41I: **NO**
- Holdout metric computed by B41I: **NO**
- Model/tier retuning: **NO**
- Production change authorized: **NO**

## Why continuation is scientifically eligible

B41H's durable stop was the frozen players.csv SHA mismatch. Static
control-flow verification shows that this occurred before the frozen
builder parsed players rows, before the 2025 cohort was built, before
model scores were applied, and before any bootstrap/performance test.

Repository-history verification also found no B41H scored-row,
bootstrap, performance-evidence, or report artifact committed at any
point after the B41H evaluator freeze.

## Identity source frozen for B41J

`{"kind": "committed_file", "path": "research/player-role-v2/frozen_inputs/players_b41i_snapshot.csv", "sha256": "d531dcff2d3ff681f02210d314f6e9f16c671c0beefa85fd311a55363675d4cc"}`

B41J must consume those exact bytes. It may not re-download players.csv.

## Identity-column inventory

Frozen `load_players` requires:

`gsis_id, pfr_id, position`

Frozen `load_players` also consumes optional fallback fields when present:

`display_name, football_name, full_name`

Optional fields missing from the frozen current snapshot:

`full_name`

Time-varying field(s) consumed:

`position`

Disclosure: Frozen load_players consumes current players.csv position. Position can be revised over time. This issue existed in the original post-2025 frozen identity source as well and is disclosed; no status, team, or experience column is consumed by load_players.

## Governance

If continuation class is `OUTCOME_BLIND_IDENTITY_SOURCE_AMENDMENT`,
every later holdout and production claim must retain that label. It is
a disclosed protocol deviation, not strict preregistered-source parity.

B41J must hash-pin the frozen B41F model, unchanged B41E tier
thresholds, feature/imputation implementation, and all four frozen
B41G tests. No retuning is permitted.

B42 remains mandatory even if B41J later passes the 2025 holdout.

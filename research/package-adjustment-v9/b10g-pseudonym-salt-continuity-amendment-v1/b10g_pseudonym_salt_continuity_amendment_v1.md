# Package Adjustment V9 — B10G Pseudonym Salt Continuity Amendment V1

## Decision

**PASS_B10G_PROSPECTIVE_PSEUDONYM_SALT_CONTINUITY_AMENDMENT**

## Why this exists

Slot 1 was issued with a valid unique 64-character pseudonym, but the
private salt implicitly used to create that pseudonym was not
recoverably preserved. This was discovered before issuing Slot 2 and
without inspecting any human vote choices.

## Prospective rule

Slot 1 is grandfathered exactly as logged. It is not rehashed and the
voter is not asked to repeat the study.

Slots 2 through 40 must all use one new private salt. The salt itself
stays off GitHub. GitHub stores only this commitment:

`801c2cf3b3d993d836f4b5e9993917fa78cace734c6b5fb3804da1973355c344`

Commitment definition:

`SHA256(UTF-8(private_salt_string))`

Recipient pseudonym formula for Slots 2–40:

`SHA256(UTF-8(lowercase(trim(stable recipient handle)) + newline + private_salt_string))`

## Scientific effect

This changes only operator-side pseudonymization. It does not change
any ballot, challenge assignment, left/right randomization, vote
transport, model prediction, threshold, or analysis. Pseudonyms are
identifiers for issuance/uniqueness and are not predictors or outcome
variables.

No human choices were read.

## Next

After this workflow is Green, resume the unchanged B10E V2 issuance
workflow beginning with Slot 2. Every Slot 2–40 recipient pseudonym
must use the committed new salt.

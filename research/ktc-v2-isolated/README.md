# QF11 KTC V2 — Dedicated pilot collector source (V31)

**State:** source implementation only. **NOT deployed, NOT activated, no votes collected.**  The owner elected to present KTC V2 *inside* the LOG calculator's Market Research tab under mock-trade voting. V29/V30 deployed only the V2 section and fictional practice ballot. This backend is intentionally **not wired to that page**.

## Scope and isolation

This repository folder holds source and local synthetic tests for a **separate Google Apps Script + dedicated Google Spreadsheet**, rather than any existing `KTC_SUBMIT_URL`, existing KTC voting sheet, or `ktc-vote-aggregation.yml`. The source accepts only `QF11_KTC_V2_PILOT_RESPONSE_V1` records. Never write pilot data to the V1 sheet or the Package Adjustment vote collector. A 12-person comprehension pilot is **not Market Value calibration evidence** and does not modify frozen FV, Market Value, Package Adjustment or production coefficients.

The module is disabled unless an administrator deliberately creates a **new** Apps Script project, a **new** spreadsheet with the exact `Responses` header, configures unique private one-use high-entropy participant tokens and a secret, installs a daily deletion trigger, completes independent human instrument/privacy review, and receives **separate explicit owner approval for real participant contact/collection**. None of those operational actions is performed by V31 or by its GitHub workflow.

## Data contract

Request JSON supports exactly: `schema`, `participant_token`, `display_order`, `consent`, `adult`, `sf_idp_experience`, `keep`, `trade`, `cut`, `mc`. The `participant_token` is an **opaque 32–128 character private token**, never an email, handle, real name, roster ID, or IDP player ID. The `mc` three choices are numerical *proposed* Q1–Q3 answer indices `[1,1,0]`; question wording and human review are **NOT approved yet**. Q4 is open-ended and must be separately assessed by a trained moderator; sending Q4 text to the collector is forbidden. Exact player keys and invite assignments are read from private script properties, not from the publicly committed JavaScript. The three ranking keys must match the private configured pilot trio.

`slot` 1–12 has fixed `display_order = (slot - 1) % 6`, providing two respondents per display order. The assigned participant token is HMAC-SHA256 checked against the server-side allowlist. Server `LockService` serializes dedup, capacity and critical stop. Consent/adult/expertise are **self-attestations only**, not a replacement for moderated eligibility and consent review.

`QF11_V2_SHEET_ID` and `QF11_V1_SHEET_ID` must both be set, must be different, and `QF11_V2_SEPARATE_SHEET_VERIFIED=YES` must be asserted after manual inspection. Any mismatch halts. The collector never calls or imports the live V1 endpoint; its response rows contain only pseudonymous slots, token digests, ranking keys, three MC choices and retention status. It stores **no freeform answers** or raw invitation tokens.

A wrong answer on any of Q1–Q3 is marked `CRITICAL_STOP_QUARANTINED` and sets `QF11_V2_HALTED=true` *before allowing further submissions*. Correct answers are marked `PENDING_HUMAN_Q4_REVIEW`; they are never interpreted as fully certified by software. At most 12 submissions are accepted. The module does not emit an affirmative collection success when disabled, halted, or misconfigured. The server's default is disabled.

## Operational configuration — NOT TO PERFORM BEFORE APPROVAL

Script Properties names (never store values in this public repository):

| Key | Requirement |
| --- | --- |
| `QF11_V2_ENABLED` | Absent / `false` until post-QC activation explicitly authorized; only literal `true` enables |
| `QF11_V2_HALTED` | Initially `false`; any critical incident/storage exception sets `true` |
| `QF11_V2_CLOSED` | Initially `false`; flips when capacity reached |
| `QF11_V2_SHEET_ID` | Newly created V2-only spreadsheet ID |
| `QF11_V1_SHEET_ID` | Existing V1 spreadsheet ID **for equality guard only**; no access to V1 from the module |
| `QF11_V2_SEPARATE_SHEET_VERIFIED` | `YES` only after verifying distinct spreadsheets and access |
| `QF11_V2_HMAC_SECRET` | Private independent 32+ character random value |
| `QF11_V2_INVITES_JSON` | JSON object of HMAC-digest keys to `{slot,display_order}`, 12 unique invites |
| `QF11_V2_PLAYER_KEYS_JSON` | JSON array of three approved *player keys*, never a link to V1 value output |

The `Responses` spreadsheet must contain a first row of exactly:

```
received_utc,delete_due_utc,schema,slot,display_order,token_hmac,keep,trade,cut,q1,q2,q3,review_status
```

**Deletion is NOT operational until** a time-driven trigger for `purgeExpiredQF11V2Rows()` has been installed, exercised against a nonparticipant fixture and independently verified. The purge deletes complete expired rows, then halts intake for owner review. Deleting this sheet alone does not remove the private script properties/invite allowlist; final cleanup must destroy invite mapping/secret, exported files, script logs and any moderator records under an approved retention SOP. The code does not attest to that external cleanup. Daily triggers are approximate; prove 30-day maximum in the actual environment before launch.

## Remaining launch blockers

1. Independent human review and owner approval of exact ballot wording, Q1–Q4 comprehension questions and trained manual Q4 scoring; do not pre-reveal the pilot trio to respondents.
2. Consent and privacy disclosures, verified age/expertise screening, restricted moderator access, retention/deletion and incident handling SOP.
3. Dedicated Google Apps Script and Google Sheet deployment in separate resources; real endpoint and cross-origin delivery/acknowledgment testing. Google Apps Script ContentService redirects and browser CORS may prevent reliable acknowledgment. Never imply HTTP dispatch alone means acceptance; client must fail closed on uncertain outcome and never auto-retry blindly.
4. Deployment smoke test using dummy invites **only**, backend separation audit, daily retention trigger and independent participant-data privacy audit.
5. Separate explicit owner authorization before real recruitment or V2 voting activation; separate scientific review before any potential Market Value evidence promotion.

## Development commands

`node research/ktc-v2-isolated/collector.test.js` (24 synthetic tests, no network, no real people). Google Apps Script syntax is standard JS; run `node --check` on an `.js` copy during CI. The source is an implementation foundation, **not evidence of a configured or operational service**.

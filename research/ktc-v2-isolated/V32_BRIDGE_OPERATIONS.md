# QF11 V32 — KTC V2 browser-to-collector bridge (disabled development source)

**Deployment state:** Source files only, in `research/ktc-v2-isolated/`. Nothing from this package is loaded by `index.html`, no Google Apps Script is deployed, and no real participant has been invited. The KTC V2 section in Market Research remains a fictional interactive demo. This work neither changes KTC V1 nor the Market Value aggregation workflow.

## Purpose

V31 committed the server-side Apps Script collector (`collector.gs`) with strict schema and participant eligibility. V32 adds `client-bridge.js`, a narrowly scoped browser submission transport adapter, and `client-bridge.test.js` with 29 network-free cases. This closes a source-code gap but is **not** proof that Google Apps Script can reliably return a browser-readable CORS acknowledgment.

The adapter starts completely disabled. It cannot send anything until **all six flags** are explicitly true: independent wording/instrument QC, separate owner real-pilot authorization, verified dedicated collector deployment, verified privacy/deletion, moderator/critical-stop procedures, and independent endpoint isolation. It also requires valid distinct Google Apps Script URLs for the V1 legacy endpoint and V2 dedicated endpoint. No URL, secret, invitation, real player trio or private token is committed to this repository.

## Safety and response semantics

- Exact request contract is QF11 V31 schema `QF11_KTC_V2_PILOT_RESPONSE_V1` with `schema`, opaque `participant_token`, display order, consent/adult/SF-IDP attestations, KEEP/TRADE/CUT keys and 3 comprehension selections. No Q4 free text, name, email or roster ID is allowed.
- A browser may make **one attempt per bridge instance**. While the first is in flight or after it settles, repeats return `LOCKED_NO_RETRY`. This avoids unintentionally double-posting when network status is unknown. Server-side V31 dedup remains authoritative.
- Only a verified JSON response with matching schema and exact recognized status can confirm outcome. The only positive output is `AWAITING_MODERATOR_Q4_REVIEW`, **not** scientific approval. Critical misunderstanding is a STOP. Other server statuses mean STOP/NOT ACCEPTED.
- Network exception, CORS failure, opaque/no-cors response, non-JSON response or unknown status returns `UNCERTAIN_DO_NOT_RETRY`. An HTTP 200 / resolved `fetch()` without readable JSON is **not** acceptance.
- `fetch()` uses `mode: 'cors'`, `credentials: 'omit'`, `referrerPolicy: 'no-referrer'`, `cache: 'no-store'`; the adapter does not use localStorage, sessionStorage, console logs, analytics, automatic retries or actual pilot identities.

## Deployment blockers after V32

1. **Independent human QC and owner authorization** of exact V2 wording, Q1–Q4 moderation scoring, real participant procedure and research ethics. Existing technical tests alone are not human QC.
2. Deploy a **dedicated new** Google Apps Script project and separate spreadsheet. V31 uses two distinct sheet IDs and a private invite HMAC allowlist; no production KTC V1 sheet/URL may be reused. Running GitHub Actions does not provision them.
3. Establish secure invitation/identity dedup/consent/retention SOP, train moderator, and prove deletion in the deployed account including exports and backups. The V31 daily purge function is not a verified 30-day lifecycle by itself.
4. **Empirically prove readable acknowledgments** from the Google Apps Script ContentService redirect in actual browsers across the calculator hosting origin. A browser CORS failure or opaque response is not a successful vote; do not silently change the bridge to `no-cors` to bypass it. If browser-readable acknowledgment is infeasible, choose a new validated isolated transport architecture before any real use.
5. Conduct dummy-token end-to-end cross-browser tests and approve a controlled integration of this adapter into the calculator's V2 section. No participant invitation or V2 vote collection until those gates and an **additional explicit owner launch authorization**.
6. Pilot scope remains **12-person comprehension/usability only**. Do not promote pilot responses into Market Value, FV or Package Adjustment without new preregistration, sufficient data and scientific review.

V32 scope is intentionally narrow: three new source/doc files, zero production changes, 24 unchanged V31 server tests plus 29 new client-bridge tests, all existing 14 repository regression groups. The review of CORS/ack integrity is a genuine unresolved blocker, not a claim of operational readiness.

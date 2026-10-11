# LOG Trade Calculator — QF5 V2R1 A7-F02: exact-YAML re-review after E1/E2

**Decision requested from Claude:** Examine the actual attached `QF5-v2r1.yml` and return **APPROVE**, **APPROVE WITH CHANGES**, or **STOP**. This is a pre-run review; **nothing here authorizes GitHub upload, Actions dispatch, a branch push, a promotion, or private-source replay**. Preserve the frozen science, B57, package V9, Draft Pick V10 and independently governed programs.

## 1. Exact review target and provenance

- Workflow file: `QF5-v2r1.yml`; SHA-256 **`2cf258e23dd84656ab1b9e153f9b9b73dcbb0f0671c95aff3cff32c876da0f82`**; 35,942 bytes.
- Workflow title: **QF5 V2R1 - Free Agent Identity R1b Three File Review Candidate**.
- Intended path **after approval and explicit owner decision**: `.github/workflows/QF5-v2r1.yml` on `main`.
- Isolated review-branch name (created only after all gates pass): `qf5-a7f02-v2r1-r1b-review-2026-10-11`.
- Current examined main commit: `4a09e546620fb62fdb6a9d70eebdef3a2745f87a`. QF4 deployed `index.html` git blob `2666f7f8b167e48b7d1571ab527450b521d32c75`.
- Prior review: `LOG_QF5_V2_R1b_Claude_PreRun_Review.md` returned **APPROVE WITH CHANGES**, specifically E1 artifact-budget realism and E2 snapshot pin expiry. **V2 has not been run**. This is the first submission of the revised executable V2R1.

## 2. Decisions already made; review this exact implementation

**Adopt E1 as preregistered, BEFORE any builder execution.** The Utility rank gate now:

1. Verifies the entire `source` block and scalar contract are unchanged.
2. Requires SID population **exactly** old population minus `8702`; no additions or duplicate SIDs.
3. Requires all **non-DB rows byte-equivalent at JSON field level**, and unchanged positions/record schema.
4. Requires every position to have a contiguous `1..n` rank sequence.
5. For DB, compares each surviving SID to its prior rank, shifted by one after the **actual** removed SID's former rank (not hard-coded rank 88). Prints deviations. **STOP if over 14 DB rows deviate or any absolute deviation is over 2 positions.** No post-run widening of this cap.

This is deliberately a bounded scientific gate: it permits mathematically expected small rerankings from recalculating cohort percentiles, but rejects a materially different artifact or any non-DB drift.

**Adopt E2 option (b): preserve pinned code and relative data checks.** The immutable production, validator, builder, phase-1 source, crosswalk and release blobs remain pinned. Do not pin `data/free_agents.json` and `data/free_agent_utility_v1.json` to yesterday's bytes; a legitimate Sleeper sync / Free Agent Utility refresh may update them. Remove the assertion that only workflow files may have changed since QF4; instead require exact protected-code hashes and QF4 commit ancestry.

At runtime, capture the current baseline from the *same* checkout. Require **both** Jaylon Jones DB SIDs `11052` and `8702` to exist, have the canonical `jaylon jones` key and FV 1,636, and be flagged data-backed. Require baseline Utility artifact SID membership to equal the data-backed board SID set, failing if a refresh is stale. Derive rendered and data-backed row counts, the minus-one cohort change and browser expectations from that baseline. For SID `8702`, require real Sleeper age and `Speculative` role, `hasRealData=false`, a positive FV below its inherited canonical FV, and no unexpected player deltas. Do not hard-code post-hold FV 973 or rank 88. Current observed 973 remains descriptive, **not an immutable future data contract**.

## 3. Three-file atomic candidate unchanged from reviewed V2

Exactly these files are staged on the review branch, never on `main`:

1. `free-agent-board.html` — the R1b identity hold: preserve repo-linked SID 11052; hold other Jaylon DB SIDs and all members of future unresolved same-name+position collision groups; group raw and alias-resolved names. Held row uses SID-specific speculative fallback, never another player's `.342` or unlabeled `.15` production.
2. `scripts/validation/validate_free_agent_valuation_parity.py` — independent expected identity-source classification; negative mutation must reject reverting the board fix.
3. `data/free_agent_utility_v1.json` — **re-generated** by the pinned existing builder using existing 4for4 secrets, with no hand-editing. Private files are stored only in `700`-permission `/tmp`, decoded CSVs `600`, and removed under `if: always()`.

Do **not** change `index.html`, shared formula source, `PROD_MULT_DATA`, `FA_PROD_MULT_DATA`, `PLAYER_DB`, aliases, exclusions, the frozen builder, utility validator or model releases.

## 4. Checks performed before this request (not an Actions green)

- YAML parsed; all 12 job-step shells passed `bash -n`; every Python heredoc and generated Python script compiled with `ast.parse`.
- The extracted **actual** E1 artifact acceptance block was executed in a temporary synthetic Git repository against four cases: pure removal/shift **PASS**, adjacent DB swap **PASS**, distant DB reorder **rejected**, unrelated WR rank swap **rejected**. This does not substitute for private-builder results.
- Verified current GitHub `main` still has the expected code and current public-data blobs at the time of review preparation.
- **NOT run:** 4for4 secret-backed builder, all updated end-to-end source fixtures against the live repo, Selenium/Chrome on the Ubuntu runner, complete candidate regressions in Actions, branch publication. Do not claim they passed.

## 5. Specific audit questions

1. Does V2R1 actually implement E1 exactly as proposed, including strong non-DB identity, complete schema, contiguous ranks and `<=14`/`<=2` DB deviations? Could a different set of winners bypass it?
2. Does E2 make ordinary daily data refreshes safe **without** allowing frozen science/code drift? Are current baseline Utility membership checks appropriate and fail-closed on stale refreshes? Is a hardcoded `1636` baseline premise intentional and grounded?
3. Does `acceptance.py` still assert only SID 8702's displayed metadata/value/data status changes, and 11052 remains unchanged? Do dynamic `after` value assertions leave an unacceptable bypass?
4. Does the independent parity classifier continue to catch wrong allowlist, inherited FA production, reverted board hold and aliases? Please inspect its line-by-line Python f-string escaping.
5. Are the 4for4 input decode, CLI builder call, `--check`, full 14 regression groups, IDP release validation, mutation, and final diff allowlist still safe and in the right order? Any known Selenium/Chrome issue on `ubuntu-latest`?
6. Inspect GitHub Actions expression availability and current source-anchor counts. Will uploading `QF5-v2r1.yml` inadvertently fail GitHub workflow registration or the drift guard as V1 did? Verify that secret names are correct; do not disclose secret values.
7. If all tests pass, is creating **only a three-file review branch** safe? Promotion **must** remain a later read-only preflight then separate owner-confirmed three-file atomic production push.

**Return exact failing line(s) with specific corrections rather than generic warnings.** If you approve, state whether review branch upload/dispatch is ready for separate owner authorization. Do not dispatch or modify files yourself.

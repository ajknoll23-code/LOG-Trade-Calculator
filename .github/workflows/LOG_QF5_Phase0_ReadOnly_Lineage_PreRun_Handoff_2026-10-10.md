# LOG Trade Calculator — QF5 Phase 0 pre-run handoff

**Project:** `ajknoll23-code/LOG-Trade-Calculator`  
**Date:** October 10, 2026 Arizona / October 11, 2026 UTC  
**State:** QF1–QF4 deployed; QF5 A7-F02 is OPEN. No QF5 implementation or production repricing authorized.

## Verified current source baseline

- `main`: `0621d68292fe088f5b948849eea2027c537534e2` (QF4 production).
- `index.html` blob: `2666f7f8b167e48b7d1571ab527450b521d32c75`.
- `free-agent-board.html` blob: `700c52db74c05b1122b4f0a48cf082243d98b0a7`.
- `data/free_agents.json`: 1,614 distinct SIDs, exactly **one** same-normalized-name + same-position collision group: Jaylon Jones / DB (SIDs `11052`, `8702`).
- Jaylon `11052`: TEN, age 24, DOB 2002-04-03; Jaylon `8702`: JAX, age 28, DOB 1997-10-14.
- `scripts/identity_crosswalk.json`: 984 authoritative high-confidence stable IDs out of 1,083; neither Jaylon SID is mapped.
- Free Agent Production V2 release: 333 frozen SID-specific overrides; neither Jaylon SID present.
- Free Agent Utility V1: 406 SID+position ranks, with these two Jaylon rows independently ranked 87 and 88 in DB.
- Deployed FA Board holds canonical `jaylon jones` IND/DB/Depth/age24 with 0.342 production *and* an old name-keyed FA data row for Jaylon Jones CHI/DB/0.15. The actual board's name-and-position lookup incorrectly inherits the canonical IND row for either current Jaylon SID, plus any new same-name/DB SID.

## Deliverable

**Upload:** `.github/workflows/QF5-v1.yml`  
**Display name:** `QF5 Phase 0 - Free Agent Stable ID Collision Lineage Audit (Read Only)`  
**Dispatch:** `main`, no inputs. Owner manually runs and replies **Green** or **Red**.

The workflow pins baseline hashes, asserts that the only new repo file since QF4 is the uploaded workflow, and **does not push to main, create a review branch, or write source**. It traces all raw FA SID+pos collision groups; runs the actual Free Agent Board mapping fragment inside a deterministic Node fixture for the two Jaylons and adversarial negative controls; preserves the known exclusions (Byron Young DL, Devonta Smith DB), name+different-position guard (Justin Jefferson LB), array name+position fallback (Devin Neal), and unknown-SID behavior; checks 984/333/406 data contracts and all 14 repository/FA/IDP/Package Adjustment regressions. It attaches a small JSON + Markdown report from Actions with 7-day retention.

**Green means the audit successfully reproduced/documented the problem, NOT that the problem is fixed.** The status is deliberately `PASS_READ_ONLY_AUDIT_STOP_BEFORE_REPAIR`.

## Next governed gates

After owner reports Green, verify actual run logs and download/read attached JSON/MD report if available. Then propose a bounded source change with explicit, evidence-backed stable ID matching/hold policy and downstream Free Agent Utility coverage implications. Do **not** invent which Jaylon deserves IND 0.342 or CHI 0.15. Do not edit frozen multiplier datasets, IDP 320/84 holds, 2024 holdout, PA V1.7, Draft Pick V10, or market model. Follow the established **review branch → independent read-only preflight → separate explicit promotion** only after substantive approval.

A full model V13 handoff is not required yet; update after Phase0 evidence and any approved QF5 implementation plan.

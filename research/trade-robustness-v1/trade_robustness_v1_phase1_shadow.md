# Trade Robustness V1 Phase 1 — Shadow

**Decision:** `PASS_TRADE_ROBUSTNESS_V1_PHASE1_SHADOW`

**RESEARCH ONLY. No calculator behavior changed.**

## What this tests

The shadow reruns the actual production trade-verdict and package-adjustment functions under the existing player sensitivity envelopes.

- `robust`: the center-value winner still wins in the deterministic adverse corner.
- `fragile`: the center-value winner ties or loses in the adverse corner.
- These are **not probability/confidence labels**.

## Universe

- Real league rosters: **12**
- Matched rostered players: **489**
- Synthetic realistic cross-team trade cases: **28776**

## Results

- Robust non-ties: **6118** (21.3%)
- Fragile non-ties: **22656** (78.7%)
- Center-value ties: **2**
- Median base margin: **42.9%**
- Median maximum player envelope half-width: **28.5%**

## By trade structure

| Structure | Cases | Robust | Fragile | Ties |
|---|---:|---:|---:|---:|
| 1v1 | 6600 | 587 | 6011 | 2 |
| 1v2 | 11088 | 2525 | 8563 | 0 |
| 2v1 | 11088 | 3006 | 8082 | 0 |

## Example fragile trades

| Structure | Side A | Side B | Base margin | Package status |
|---|---|---|---:|---|
| 2v1 | alec pierce + travis etienne | rashee rice | 0.0% | applied |
| 1v2 | jonathan taylor | justin herbert + jaylen waddle | 0.0% | applied |
| 1v2 | bo nix | devonta smith + alex highsmith | 0.0% | applied |
| 2v1 | alec pierce + zach allen | trevor lawrence | 0.0% | applied |
| 2v1 | lamar jackson + josh jacobs | rashee rice | 0.0% | applied |
| 1v2 | lamar jackson | tremaine edmunds + alex highsmith | 0.0% | applied |
| 1v2 | aidan hutchinson | quinshon judkins + emeka egbuka | 0.0% | applied |
| 1v2 | jonathan taylor | jameson williams + jeremiyah love | 0.0% | applied |
| 1v2 | jalen hurts | tetairoa mcmillan + tyler shough | 0.0% | applied |
| 1v2 | bo nix | tremaine edmunds + patrick queen | 0.0% | applied |
| 1v1 | trey mcbride | omarion hampton | 0.0% | not_applicable |
| 1v2 | aidan hutchinson | dk metcalf + josh hinesallen | 0.0% | applied |
| 1v1 | ladd mcconkey | quincy williams | 0.0% | not_applicable |
| 1v2 | james cook | carson schwesinger + bucky irving | 0.0% | applied |
| 1v1 | terrel bernard | cj stroud | 0.0% | not_applicable |
| 1v1 | terrel bernard | koolaid mckinstry | 0.0% | not_applicable |
| 2v1 | aidan hutchinson + caleb williams | josh allen | 0.0% | applied |
| 1v2 | chris olave | quinshon judkins + chase young | 0.0% | applied |
| 1v2 | brian burns | jeremiyah love + ladd mcconkey | 0.0% | applied |
| 1v1 | brian burns | maxx crosby | 0.0% | not_applicable |
| 1v2 | jared goff | dk metcalf + michael pittman | 0.0% | applied |
| 1v1 | dak prescott | jack campbell | 0.0% | not_applicable |
| 1v1 | breece hall | aj brown | 0.0% | not_applicable |
| 1v1 | cedric gray | tetairoa mcmillan | 0.0% | not_applicable |
| 2v1 | jaxson dart + kyle pitts | patrick mahomes | 0.0% | applied |

## Guardrails

- Fundamental Value centers are unchanged.
- Sensitivity envelopes are unchanged.
- Market Value V2 is unchanged.
- Team Utility is unchanged.
- Package Adjustment is unchanged.
- Trade Verdict is unchanged.
- No probability label is permitted from this phase.

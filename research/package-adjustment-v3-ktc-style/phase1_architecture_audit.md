# Package Adjustment V3 — Phase 1 KTC-Style Architecture Audit

**Decision:** `PASS_V3_PHASE1_ARCHITECTURE_REPLACEMENT_JUSTIFIED`

**Research only. Production is unchanged.**

## Core finding

- Current V1.6 supports only **1/5** supplied KTC reference shapes.
- Current V1.6 supports **0/8** supplied real completed league trades.
- Every real completed trade anchor contains at least one draft pick, and V1.6 is player-only.
- The real trade set spans 1v2, 2v2, 3v3, 3v4, 4v6, and 5v6 package shapes.
- A topology-agnostic nonlinear all-asset architecture is therefore required if the model is expected to behave like a general trade calculator.

## KTC behavioral anchors

- Development-only best power gamma: **2.009**.
- Correct adjusted side: **5/5**.
- Mean absolute displayed-adjustment error: **550.7 KTC points**.

The power curve is a feasibility baseline only. It is **not** the selected V3 production formula.

| KTC fixture | Shape | V1.6 supported? | Reason |
|---|---:|---:|---|
| `gibbs_vs_achane_higgins` | 1v2 | YES | `supported_size2` |
| `lamb_laporta_vs_odunze_barkley` | 2v2 | NO | `multi_vs_multi` |
| `pickens_lloyd_vs_likely_flournoy_dowdle` | 2v3 | NO | `multi_vs_multi` |
| `allen_vs_caleb_barkley` | 1v2 | NO | `size2_composition_outside_evidence_supported_envelope` |
| `pickens_black_vs_reed_washington_brooks` | 2v3 | NO | `multi_vs_multi` |

## Completed league-trade topology anchors

| Trade | Date | Shape | Players | Picks | V1.6 |
|---:|---|---:|---:|---:|---|
| 1 | 2025-12-03 | 3v4 | 4 | 3 | UNSUPPORTED |
| 2 | 2025-10-21 | 5v6 | 6 | 5 | UNSUPPORTED |
| 3 | 2025-08-28 | 3v3 | 3 | 3 | UNSUPPORTED |
| 4 | 2025-05-21 | 2v2 | 3 | 1 | UNSUPPORTED |
| 5 | 2025-10-02 | 3v3 | 4 | 2 | UNSUPPORTED |
| 6 | 2025-11-06 | 4v6 | 4 | 6 | UNSUPPORTED |
| 7 | 2025-04-05 | 3v3 | 4 | 2 | UNSUPPORTED |
| 8 | 2025-09-26 | 1v2 | 1 | 2 | UNSUPPORTED |

These completed trades validate real-world scope/topology only. They are not treated as mathematically fair or used as zero-adjustment targets.

## Governance

- Prior exact 900-vote dataset: **not used**.
- Five KTC screenshots: development-only behavior anchors.
- Eight completed league trades: topology/scope anchors only.
- No production change is authorized.
- A future V3 candidate requires fresh preregistered confirmation evidence.

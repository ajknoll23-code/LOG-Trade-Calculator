# Free-Agent Production V2 — Phase 2 Shadow Validation

**Decision:** `PASS_FA_PROD_V2_PHASE2_SHADOW_VALIDATION`

This phase is shadow-only. No production change is authorized.

## Frozen population

- Active FA-specific cohort: **364**
- Reproducible candidates: **333**
- Unresolved rows held at deployed values: **31**

## Hard gates

| Gate | Result |
|---|---|
| `phase1_decision_pass` | PASS |
| `phase1_output_hashes_intact` | PASS |
| `phase1_input_snapshot_unchanged` | PASS |
| `frozen_candidate_count_exact` | PASS |
| `frozen_active_count_exact` | PASS |
| `current_runtime_active_identity_exact` | PASS |
| `shadow_source_classification_unchanged` | PASS |
| `unresolved_rows_held_exact` | PASS |
| `all_non_candidate_rows_unchanged` | PASS |
| `candidate_metadata_unchanged` | PASS |
| `candidate_values_valid` | PASS |
| `candidate_fv_monotonic_with_prod` | PASS |
| `free_agent_parity_and_roster_safety` | PASS |

## Shadow movement diagnostics

- Candidate rows with changed FV: **298**
- Increased FV: **275**
- Decreased FV: **23**
- Active-cohort rank Spearman: **0.8633**
- Top-25 overlap: **68.0%**
- Top-50 overlap: **66.0%**
- Top-100 overlap: **76.0%**

### Position summary

| Pos | Active | Candidate | Held | Median ΔFV | P90 | Max |
|---|---:|---:|---:|---:|---:|---:|
| QB | 10 | 10 | 0 | +0.0 | +0.0 | +0.0 |
| RB | 31 | 21 | 10 | +0.0 | +176.0 | +326.0 |
| WR | 83 | 72 | 11 | +257.5 | +594.9 | +1107.0 |
| TE | 70 | 65 | 5 | +190.0 | +431.6 | +713.0 |
| DL | 52 | 50 | 2 | +420.5 | +872.3 | +1084.0 |
| LB | 21 | 21 | 0 | +264.0 | +792.0 | +950.0 |
| DB | 97 | 94 | 3 | +591.0 | +1064.8 | +1388.0 |

### Largest FV movers

| Player | Pos | Old FV | Shadow FV | ΔFV | Old Prod | New Prod |
|---|---|---:|---:|---:|---:|---:|
| Benjamin Morrison | DB | 556 | 1944 | +1388 | 0.150 | 0.491 |
| Dadrion Taylor-Demerson | DB | 1402 | 2711 | +1309 | 0.293 | 0.567 |
| Myles Harden | DB | 770 | 2002 | +1232 | 0.161 | 0.418 |
| Quinyon Mitchell | DB | 1766 | 2961 | +1195 | 0.369 | 0.619 |
| Cor'Dale Flott | DB | 1268 | 2449 | +1181 | 0.265 | 0.512 |
| Cam Taylor-Britt | DB | 718 | 1898 | +1180 | 0.150 | 0.397 |
| Marcus Epps | DB | 591 | 1709 | +1118 | 0.160 | 0.463 |
| Renardo Green | DB | 1445 | 2556 | +1111 | 0.302 | 0.534 |
| Nick Westbrook-Ikhine | WR | 762 | 1869 | +1107 | 0.150 | 0.368 |
| Darien Porter | DB | 718 | 1806 | +1088 | 0.150 | 0.377 |
| Milton Williams | DL | 1923 | 3007 | +1084 | 0.376 | 0.588 |
| Tarheeb Still | DB | 1550 | 2625 | +1075 | 0.324 | 0.549 |
| Eyioma Uwazurike | DL | 1054 | 2099 | +1045 | 0.206 | 0.410 |
| Jaylon Johnson | DB | 1426 | 2467 | +1041 | 0.298 | 0.516 |
| T.J. Sanders | DL | 657 | 1690 | +1033 | 0.151 | 0.378 |
| Cam Hart | DB | 1546 | 2578 | +1032 | 0.323 | 0.539 |
| Eric Stokes | DB | 1340 | 2371 | +1031 | 0.280 | 0.495 |
| Micheal Clemons | DL | 870 | 1901 | +1031 | 0.170 | 0.372 |
| Jaden Hicks | DB | 957 | 1985 | +1028 | 0.200 | 0.415 |
| Andrew Mukuba | DB | 1550 | 2575 | +1025 | 0.324 | 0.538 |

## Decision semantics

A PASS proves the frozen candidate can be isolated inside the real board runtime without spillover or safety violations. It does **not** authorize deployment. Magnitude and rank movement remain diagnostics for the separate production-confirmation step.


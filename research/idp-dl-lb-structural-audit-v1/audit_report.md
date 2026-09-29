# IDP DL/LB Structural Integrity Audit V1

**Decision:** `STOP_TRUSTING_ABSOLUTE_FV_CALIBRATION_FOR_MIGRATED_DL_COHORT_AUTHORIZE_RECONCILIATION_RESEARCH`

## Executive finding

- Audited **86 DL** and **79 LB** using the exact deployed FV port.
- Frozen position-lineage candidates: **24**; current-live comparable: **22** (**21 DL**, **1 LB**).
- Frozen candidates no longer in current PLAYER_DB/valuation universe: **2** (bradley chubb, derrick barnes).
- Median migrated-DL current FV excess versus current-position-clean + same successor overlay: **26.5%**.
- Migrated DL at or above +15% excess: **20/21 (95.2%)**.
- Current top-10 DL containing migrated candidates: **7/10**.
- Systemic transport-residual trigger: **YES**.

The counterfactual above is a diagnostic isolation of inherited transport residual. It is **not** asserted to be true market value.

## Brian Burns decomposition

- Current live FV: **7441**
- Current live raw production multiplier: **1.4547**
- Pre-lineage deployed raw multiplier: **1.0993**
- Legacy-position clean multiplier: **0.8190**
- Current-position clean multiplier: **1.1646**
- Preserved legacy residual: **+0.2803**
- Position-lineage candidate raw multiplier: **1.4449**
- Later successor overlay delta: **+0.0098**
- Clean-current-position + same successor overlay FV: **6007**
- FV attributable to preserved residual under this isolation: **+1434 points (23.9% above the counterfactual)**
- Current DL #1 / DL #2 gap: **1.212×**

## Migrated DL cohort

| Player | Current FV | Clean+successor FV | Excess | Legacy residual | Later overlay |
|---|---:|---:|---:|---:|---:|
| brian burns | 7441 | 6007 | +23.9% | +0.2803 | +0.0098 |
| byron young | 6137 | 4919 | +24.8% | +0.2382 | +0.0029 |
| will anderson | 6028 | 4746 | +27.0% | +0.2506 | +0.0131 |
| nik bonitto | 5883 | 4716 | +24.7% | +0.2281 | +0.0037 |
| tj watt | 5373 | 4349 | +23.5% | +0.2362 | +0.0067 |
| alex highsmith | 5304 | 4283 | +23.8% | +0.1996 | +0.0166 |
| dallas turner | 5106 | 3963 | +28.8% | +0.2172 | +0.0070 |
| micah parsons | 4916 | 3933 | +25.0% | +0.1922 | -0.0052 |
| nick herbig | 4734 | 3794 | +24.8% | +0.1840 | +0.0059 |
| jaelan phillips | 4544 | 3533 | +28.6% | +0.1977 | +0.0008 |
| harold landry | 4501 | 3506 | +28.4% | +0.2105 | -0.0013 |
| rashan gary | 4340 | 3434 | +26.4% | +0.1772 | +0.0091 |
| odafe oweh | 4307 | 3395 | +26.9% | +0.1784 | +0.0097 |
| travon walker | 4257 | 3366 | +26.5% | +0.1741 | +0.0097 |
| abdul carter | 4231 | 3192 | +32.6% | +0.1991 | +0.0049 |
| uchenna nwosu | 3844 | 3004 | +28.0% | +0.1642 | -0.0038 |
| joseph ossai | 3599 | 2821 | +27.6% | +0.1522 | +0.0035 |
| david bailey | 3313 | 2711 | +22.2% | +0.1220 | -0.0011 |
| akheem mesidor | 3161 | 2921 | +8.2% | +0.0470 | +0.0003 |
| nolan smith | 2991 | 2277 | +31.4% | +0.1396 | +0.0104 |
| jermaine johnson | 2966 | 2249 | +31.9% | +0.1403 | +0.0056 |

## Current top DL values

| Rank | Player | FV | Prod mult | Migrated lineage candidate? |
|---:|---|---:|---:|---|
| 1 | brian burns | 7441 | 1.4547 | yes |
| 2 | byron young | 6137 | 1.1999 | yes |
| 3 | will anderson | 6028 | 1.1784 | yes |
| 4 | nik bonitto | 5883 | 1.1502 | yes |
| 5 | myles garrett | 5770 | 1.2209 | no |
| 6 | maxx crosby | 5662 | 1.1069 | no |
| 7 | aidan hutchinson | 5452 | 1.0658 | no |
| 8 | tj watt | 5373 | 1.2388 | yes |
| 9 | alex highsmith | 5304 | 1.0369 | yes |
| 10 | dallas turner | 5106 | 1.0586 | yes |
| 11 | micah parsons | 4916 | 0.9610 | yes |
| 12 | jeffery simmons | 4849 | 0.9479 | no |
| 13 | nick herbig | 4734 | 0.9256 | yes |
| 14 | jaelan phillips | 4544 | 0.8884 | yes |
| 15 | harold landry | 4501 | 0.9523 | yes |
| 16 | tuli tuipulotu | 4389 | 0.9235 | no |
| 17 | jared verse | 4369 | 0.8541 | no |
| 18 | rashan gary | 4340 | 0.8485 | yes |
| 19 | odafe oweh | 4307 | 0.8421 | yes |
| 20 | travon walker | 4257 | 0.8323 | yes |

## DL/LB distribution diagnostics

- DL top1/top2 FV ratio: **1.212×**
- DL top1/p95 FV ratio: **1.296×**
- LB top1/top2 FV ratio: **1.041×**
- LB top1/p95 FV ratio: **1.149×**

## Prospective evidence guardrail

- Production V2 status: **COLLECTING_NO_CALIBRATION**, completed weeks: **[1, 2]**, deployment authorized: **False**.
- Deployed production control rank after Weeks 1-2: **121/121**. This is smoke-test evidence only under the frozen protocol.
- DL deployed-control Spearman vs active PPG: **0.426**.
- LB deployed-control Spearman vs active PPG: **0.371**.
- Replacement Level V2 status: **COLLECTION_ONLY**; replacement-rank change authorized: **False**.
- Position Weight V2 status: **COLLECTION_ONLY**; position-weight change authorized: **False**.

## Scientific conclusion boundaries

This audit may identify a structural lineage-transport problem. It does **not** authorize a manual Brian Burns correction, a global DL haircut, a POSITION_WEIGHT change, or a replacement-rank change. If the systemic transport-residual trigger fires, the next scientifically valid step is a separately preregistered reconciliation study comparing the inherited live residual against clean current-position production evidence and prospective outcomes.


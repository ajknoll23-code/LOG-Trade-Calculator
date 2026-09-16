# Draft Pick FV V3 — Catalog & Outcome Preregistration

**Status:** `FROZEN_PRE_OUTCOME`

This freeze authorizes the next stage to harvest exact MFL draft picks and resolve player identities only.
It does **not** authorize historical NFL outcome ingestion, model fitting, validation scoring, or production changes.

## Frozen source catalog

- R1-R4 primary source drafts: **213**
- R5 primary non-IDP drafts: **81**
- R6 primary non-IDP drafts: **44**
- R5 IDP sensitivity drafts: **37**
- R6 IDP sensitivity drafts: **25**
- Development classes: **2018-2021**
- Locked validation classes: **2022-2023**

## Outcome target

V3 inherits V2's frozen three-season football-outcome contract and player-equivalent FV scale bridge.
The source population changes to validated real 12-team SF/2QB MFL rookie drafts and actual draft slots.

## Candidate families

`C0` deployed baseline, `C1` global rescale, `C2` low-parameter round/tier curve,
and `C3` a development-tuned shrunk monotone exact-slot curve.
`C4` raw isotonic is diagnostic only.

## Leakage firewall

No KTC/current market values, package votes, 2026 outcomes, named-rookie tuning, validation-driven
rule changes, or production modifications are allowed.

# Draft Pick FV V2 — Broad Historical Rookie Cohort Preregistration

**Status:** preregistered before broad-cohort or historical-outcome ingestion

## Why V2 exists

V1 stopped correctly because the user's Sleeper history contains no
three-season-mature rookie class. V1's rules are not being weakened.
V2 is a new broad-cohort study.

## Research question

In a broad historical 2QB/Superflex rookie-ADP cohort, do realized football outcomes support the absolute scale and round/tier shape of the deployed draft-pick Fundamental Values?

## Frozen cohort source

`dynastyprocess/data@ddbf693ee8e59fdfd100ab4f7fd144b70a13f70d:files/archives/database.csv`

Primary ordering is `draft_2QBrookieadp`. 1QB rookie ADP is robustness
only and can never fill missing 2QB ADP. The archive also contains ECR
and later performance columns; those are forbidden and must not enter
the sanitized V2 catalog.

ADP is not rounded before mapping to a 12-team board:
slots 1-4 = early, 5-8 = mid, 9-12 = late, rounds 1-6.

## Feasibility

V2 requires at least 6 mature classes, 216 players total, 12 players in
every round×tier cell, >=95% identity resolution, >=85% DOB coverage,
and >=80% 2QB ADP coverage among candidate source rows.

A full IDP-inclusive claim additionally requires >=10% IDP share and at
least 36 DL/LB/DB players. Otherwise the study may continue only as
`OFFENSE_CONDITIONAL_ONLY`.

## Outcomes and candidates

O1 is three-year replacement-adjusted football utility.
O2 is three-year player-equivalent FV on the frozen 5500 player scale.

Candidates:
- C0 exact deployed table.
- C1 one-parameter global rescale.
- C2 five-parameter monotone round/tier curve.
- C3 flexible monotone diagnostic; cannot win.

The latest two mature classes are locked validation. A replacement must
improve validation O2 macro MAE by >=5%, improve both validation classes,
survive O1/H2/H4 robustness, remain monotone, and avoid parameter-boundary
saturation. No qualifier means production remains unchanged.

## Still out of scope

Future-year discounts and multi-pick consolidation remain separate studies.

## Next step

Build a sanitized broad-cohort catalog from the frozen archive source,
verify the source hash and all feasibility/IDP gates, and freeze the
development/validation class split before any outcome download.

# Schedule Utility V1 — Phase 1A Private Source Ingestion Feasibility

**Decision:** `PASS_PRIVATE_SOURCE_INGESTION_FEASIBILITY`

Phase 1A validated the user-supplied private 4for4 aFPA / Hot Spots source bundle without reading fantasy outcomes and without persisting proprietary row-level provider data.

## Source coverage

- One Half-PPR aFPA master table: 32 NFL teams.
- Seven Hot Spots tables: QB Half-PPR, RB Half-PPR, WR Half-PPR, TE Half-PPR, RB PPR, WR PPR, TE PPR.
- Each Hot Spots table: 32 teams, 18 weekly columns, exactly one bye per team.
- 544 non-bye weekly matchup cells per Hot Spots table.
- 3,808 total non-bye weekly matchup cells across the seven Hot Spots tables.

## Structural validation

- All four Half-PPR position tables reproduce the opponent aFPA master value exactly across 2,176 checks.
- All seven Hot Spots tables encode the same NFL schedule.
- Schedule reciprocity is exact.
- PPR and Half-PPR schedules match exactly for RB, WR, and TE.
- `PO2` is consistent with Weeks 16–17 and `PO3` with Weeks 15–17 within display-rounding tolerance.

## V1 window policy

Provider `ROS`, `PO2`, and `PO3` summary columns are retained only as audit evidence. Schedule Utility V1 will derive its own:
- next-3-games window,
- rest-of-fantasy-regular-season window,
- configured league-playoff window

from the weekly matchup cells.

## Required metadata guard

The CSV exports do not embed capture timestamp or as-of week. Future ingestion must receive both externally and fail closed if either is missing.

## Production

No Fundamental Value, draft-pick value, Package Adjustment, Team Utility, Market Value, Trade Verdict, or UI production code is changed or authorized by Phase 1A.

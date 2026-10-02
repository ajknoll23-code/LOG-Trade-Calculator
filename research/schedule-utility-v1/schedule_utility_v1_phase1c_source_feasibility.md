# Schedule Utility V1 — Phase 1C Historical Source and Reconstruction Feasibility

**Decision:** `PASS_PUBLIC_RECONSTRUCTION_FEASIBILITY_EXACT_PROVIDER_ARCHIVE_UNPROVEN`

Phase 1C is source-only and outcome-blind. It queried public GitHub release metadata only; it did not download or inspect historical stat, schedule, play-by-play, fantasy-point, or outcome rows.

## Public reconstruction feasibility

- Public source repository: `nflverse/nflverse-data`
- Pre-2026 weekly-stat seasons visible in release metadata: **26**
- Historical years cataloged: `[2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]`
- Schedule-like release assets detected: **5**
- Public reconstruction path feasible: **True**
- Data assets downloaded: **NO**
- Historical rows read: **NO**

## Frozen naming firewall

- Proposed public metric: **LOG Schedule-Adjusted Points Allowed V1** (`LOG-SAPA-V1`)
- LOG-SAPA V1 is **not** 4for4 aFPA.
- It may not be labeled, represented, or implied to be a 4for4 metric.
- Provider equivalence is not claimed.

## 4for4 historical archive status

Status: `UNPROVEN_NOT_LOCATED`.

This is not a claim that an exact historical 4for4 archive does not exist. Any future provider archive must satisfy timestamp/as-of-week, look-ahead, coverage, and licensing requirements before admission.

## Outcome firewall

- Phase 2 outcome testing remains unauthorized.
- Historical stat rows remain unopened.
- Historical outcomes remain unopened.
- The exact LOG-SAPA V1 algorithm is not yet frozen.

## Next phase

**Phase 1D — Public Reconstruction Method Preregistration.** Freeze the exact LOG-SAPA V1 algorithm before historical stat rows are read.

## Production impact

None. No player FV, pick FV, Package Adjustment, Team Utility, Market Value, Trade Verdict, or production UI change is authorized.

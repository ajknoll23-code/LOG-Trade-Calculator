# Schedule Utility V1 — Phase 1B Coverage, Freshness, and Dependence Audit

**Decision:** `PASS_COVERAGE_DEPENDENCE_AUDIT_FRESHNESS_GUARD`

Phase 1B remained fully outcome-blind. It audited the exact private 4for4 source bundle admitted by Phase 1A.

## Main scientific finding

aFPA and Hot Spots are **not independent predictors** in this source package. Across QB/RB/WR/TE Half-PPR, all 2,176 non-bye Hot Spots matchup values exactly reproduce the corresponding opponent aFPA master value.

**Frozen guard:** Schedule Utility V1 may not blend, average, or weight aFPA and Hot Spots as two separate signals. Hot Spots is treated as the schedule/window presentation layer for the underlying aFPA matchup signal.

## Coverage

- 32/32 NFL teams.
- QB, RB, WR, TE Half-PPR coverage.
- Separate PPR exports for RB, WR, TE.
- 7 Hot Spots tables.
- 3,808 non-bye weekly matchup cells.
- Zero team/position gaps.
- Zero schedule-identity mismatches.

## Scoring-format audit

PPR and Half-PPR defensive rankings are highly correlated but not identical:

| Position | Spearman rank correlation | Mean absolute rank shift | Max rank shift |
| --- | ---: | ---: | ---: |
| RB | 0.990923298 | 0.84375 | 4.0 |
| WR | 0.994040529 | 0.71875 | 2.0 |
| TE | 0.992574942 | 0.62500 | 3.5 |

**Frozen guard:** scoring format must be explicit. PPR and Half-PPR may not be silently substituted.

## Provider summary semantics

Across all 224 team/table rows, the displayed `ROS` summary is most consistent with the average of displayed Weeks 4–17, within provider rounding. `PO2` is consistent with Weeks 16–17 and `PO3` with Weeks 15–17.

These provider summary columns remain audit evidence only. V1 derives its own configured Next-3, ROS, and fantasy-playoff windows from weekly matchup cells.

## Freshness finding

The exports do not embed a capture timestamp or authoritative as-of week. Their `ROS` structure strongly indicates Week 4, but that is an inference rather than metadata.

Future refreshes must supply capture UTC and as-of week explicitly and fail closed if either is absent.

## Phase 2 gate

Phase 2 outcome testing is **not yet authorized**. A single current source snapshot cannot support a look-ahead-safe retrospective predictive test.

The next source-only step is **Phase 1C — historical snapshot and freshness feasibility**. It must establish whether time-valid historical 4for4/aFPA predictor snapshots (or an equivalent non-look-ahead archive) can be obtained before any realized fantasy outcomes are opened.

## Production impact

None. No player FV, draft-pick FV, Package Adjustment, Team Utility, Market Value, Trade Verdict, or production UI change is authorized.

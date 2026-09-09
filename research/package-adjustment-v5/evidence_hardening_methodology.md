# Package Adjustment V5 — Evidence Hardening Methodology

**Status: RESEARCH ONLY. Production V1.5 is unchanged.**

## Purpose

The preregistered V5 maturity gates and first fit answer whether enough two-player composition evidence exists to analyze. This hardening pass asks the next question: whether the mature V5 signal remains usable when anchored to the exact controlled-live V1.5 two-player curve and stressed across both voters and target selection.

## Frozen evidence snapshot

The hardening run reads the committed V5 aggregation result and freezes the external vote sheet at that result's `generated_at_utc`. Rows that arrive later are excluded. The valid capped ballots must exactly match the committed aggregation count. A SHA-256 fingerprint of the canonical frozen ballot set is written to the hardening artifact so the reviewed evidence snapshot is identifiable without storing raw voter ballots in the repository.

## Controlled-live normalization

For every V5 ballot, the challenge's actual package-to-target FV ratio is divided by the exact controlled-live V1.5 size-2 multiplier for that challenge target FV. The V1.5 multiplier is the frozen log-interpolated curve through:

- 4269.25 FV → 1.4007986955507035x
- 5049.5 FV → 1.485881276187134x
- 5558.25 FV → 1.5368431747111482x
- 6078.700000000002 FV → 1.5859349498155657x

A normalized factor of 1.00 means the challenge package exactly matches the current V1.5 trade-equivalent threshold for that target FV. This removes the main target-FV slope already encoded by production before asking whether composition needs additional treatment.

## Estimation

Within each composition band, ballots are aggregated at their normalized challenge ratio and fit with weighted non-decreasing isotonic regression (PAVA). The 50% package-choice crossing is interpolated only inside observed normalized ratios. No extrapolation is allowed.

Voter weights use the existing V5 lifetime effective cap. The original voter weights are frozen before any resampling.

## Robustness views

Two independent cluster-bootstrap views use 500 draws each:

1. **Voter-cluster bootstrap** — resamples voters with replacement while preserving each voter's original capped ballot weight.
2. **Target-cluster bootstrap** — resamples target players with replacement while retaining the original voter weights. This tests whether conclusions depend excessively on which target players happened to receive votes.

A composition's normalized fit is called stable only when its point estimate is bracketed inside tested evidence and at least 80% of bootstrap draws are bracketed. The 80% threshold matches the preregistered V5 diagnostic stability threshold.

A leave-one-voter-out range is also reported as a sensitivity diagnostic. It is descriptive and does not invent a new post-hoc promotion threshold.

## Expansion-review rule

The 50/50 band remains the frozen V3 production anchor; V5 50/50 is treated as validation rather than an automatic replacement.

For an expansion band (55/45 or more imbalanced) to be labeled evidence-supported **for review**, all three must be true:

- the original mature raw-ratio V5 diagnostic is stable within its tested range;
- the live-V1.5-normalized voter-cluster bootstrap is stable;
- the live-V1.5-normalized target-cluster bootstrap is stable.

Expansion support must be contiguous outward from 55/45. The analysis will not skip a failed band to promote a more imbalanced one.

## Production isolation

This hardening pass does not modify the Package Adjustment formula, Fundamental Value, Market Value, draft-pick values, Team Utility, or any trade-verdict consumer. It does not select or implement a production multiplier. Any live change requires a separate production-candidate design, regression hardening, and human-reviewed promotion step.

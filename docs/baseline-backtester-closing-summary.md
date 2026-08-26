# Baseline Backtester Workstream — Closing Summary

**Status: CLOSED.** No live baseline was changed. `documented` remains the live default at every position.

---

## What this workstream set out to do

After the roster-economics workstream closed with real lineup behavior contradicting the legacy-reconstructed
DL23 baseline (but not proving documented DL32 correct either — see `roster-economics-closing-summary.md`),
the agreed next step was: "which baseline choice would have produced better predictions of subsequent fantasy
production?" — a question neither table reproduction nor lineup behavior could answer.

## What was built

- `baseline_backtester.py` — walk-forward validation (15 folds: rolling within-season + one full cross-season
  2024→2025) testing three candidate baseline sets through the exact live formula
  (`ratio = combined/baseline`, `clamp(-0.10 + 0.75·ratio, 0.15, 1.55)`, verified against the actual audit
  doc, not guessed).
- **Revision 1** built a correlation-based Test 1 as the primary decision criterion. An external methodology
  review caught a real, disqualifying mathematical flaw before it was trusted: within one position, changing
  only the baseline is a positive affine transform of trailing production pre-clamp. Pearson is invariant to
  that; Spearman to any monotonic transform. Confirmed empirically — three baselines run against identical
  data produced different correlations purely from clamp-induced tie compression, not real signal.
- **Revision 2** rebuilt around a non-circular Test 3: derive a future-only replacement rank via SSE-reduction
  applied entirely within actual subsequent production (never referencing any candidate), build a real
  `future_ratio` from it, and score each candidate's `predicted_ratio` (built only from pre-fold data) against
  it via MAE. Validated on synthetic data with a known-correct baseline before trusting real output — a check
  the original revision never had, which turned out to be exactly the right kind of check to add, and exactly
  the kind the final result still needed one level deeper.
- A tie-reporting bug was found and fixed: QB and LB, where all three candidates specify the identical baseline
  rank, were reporting a fabricated "documented: 15/15 folds won" — an artifact of Python's `min()` tie-break,
  not a real result. Now reports "NOT TESTED" explicitly for both.
- `dl_future_split_stability_check.py` — a bounded follow-up verifying whether DL23's Test 3 win (10.6% lower
  MAE than documented, stable across all three forward-window sizes, won all 15 folds) reflected a stable
  future-production boundary or a noisy one.

## The result: Test 3's target itself is invalid as a replacement-level proxy

The DL stability check found the future-derived split **is** stable — a tight bootstrap median around rank 15,
not rank 23. DL23 didn't win because it approximates real replacement level; it won because it happened to be
the less-wrong of the two tested candidates against a target that was itself centered on the wrong concept.

Checking the same SSE-derived split across every position confirmed this wasn't DL-specific:

| Position | SSE-derived split | Documented baseline |
|---|---|---|
| RB | 20 | 32 |
| WR | 13 | 36 |
| TE | 22 | 15 |
| DL | 15-16 | 32 |
| DB | 23 | 32 |

Every position's SSE split lands in the 13-23 range — well below every tested candidate except TE. DL's
independently-measured real effective weekly demand (~34-36, from the roster-economics workstream) makes a
rank-15 "replacement level" for that position roster-mechanically incoherent — this league needs far more than
15 startable DL per week from dedicated slots and IDP_FLEX competition alone.

**Root cause, not just a symptom**: SSE-reduction's gain is proportional to
`(n_left·n_right/n)·(mean_left−mean_right)²` — it rewards whatever split maximizes between-group mean
separation, which in a distribution with a small elite tier and a long merely-average tail is the elite-tier
cutoff (star vs. everyone else), not the replacement-level cutoff (last startable player vs. everyone else).
No discontinuity is even required for this to happen; it's a structural property of the criterion itself.

## What this invalidates

**Every Test 3 candidate "win" — not just DL's.** Once the target is known to represent the wrong construct,
candidate ordering against it is not guaranteed to survive against the right one. A shallow future denominator
mechanically favors whichever candidate has the shallower current denominator, regardless of which one is
actually closer to true replacement level. RB26, DL23, WR34, and the marginal DB/TE comparisons are all invalid
as *backtest* evidence. Preserved in the audit trail as the result of a rejected target definition, not as
support for any live baseline choice.

## What survives, and why

- **RB ~25-28 under the old ruleset** still has real support — but from the roster-economics workstream's
  independent lineup-behavior data, not from this backtester. That's a genuinely separate method and mechanism,
  unaffected by Test 3's target-definition flaw. Still not actionable given the 2026 RB2 ruleset change.
- **WR ~34-36** remains a plausible range from the earlier lineup analysis; Test 3 adds no independent
  confirmation on top of it. No reason to change the live value.
- **The DL23-vs-DL32 question is exactly where it was at the close of the roster-economics workstream**: DL23
  explains the old baked table; real lineup behavior favors the DL32 neighborhood; this backtester's attempt to
  adjudicate between them with future-production data failed on its own methodology, not in DL's favor either
  way.

## What was explicitly NOT done, and why that's correct here

No attempt was made to rescue Test 3 by constraining the SSE search range (e.g., forcing it to search only
ranks 20-50) or tuning it until it returns familiar-looking numbers. Constraining the search embeds a prior
belief about where replacement level sits into the "objective" measurement — which defeats the entire point of
building an independent test. A precisely-estimated wrong construct is still the wrong construct; tightening its
estimate further doesn't fix what it's estimating.

## Recommended future direction (separate project, not resumed here)

An externally-anchored replacement definition — independent of the production distribution itself — measured
against continuous VORP-style production-above-replacement, rather than a rank cliff discovered by a split
search. Candidate anchors, strongest to weakest:
1. Real available waiver-pool alternatives at each historical week (median of the top 2-3 options, not one
   lucky player).
2. The observed real substitution pool — players who actually entered lineups when normal starters were
   unavailable (the league's real "next man up" level).
3. Roster-demand-derived rank from the already-completed roster-economics work, used explicitly as the economic
   definition rather than rediscovered as if independent.

This is a real scarcity-model redesign, not a bounded follow-up — appropriately scoped as its own future
project, especially with 2026's RB2/LB2 ruleset change still reshaping the environment this would need to model.

## Final position-by-position status

| Position | Live value | Status |
|---|---|---|
| QB | 18 | Keep. No valid challenger was ever tested (candidates tied). |
| RB | 32 | Keep for now. Old-rules 25-28 signal preserved from roster-economics; re-evaluate once 2026 RB2 data accumulates. |
| WR | 36 | Keep. 34-36 remains a plausible range; no reason to change. |
| TE | 15 | Keep. No material evidence for change. |
| DL | 32 | Keep. DL23 is legacy-forensic only — explains the old table, not supported by lineup behavior or by a valid backtest. |
| LB | 32 | Keep pending 2026 LB2 data and any future scarcity redesign. |
| DB | 32 | Keep. Deep real demand confirmed, but no validated replacement target supports a specific change. |

## Evidence stack, going forward

- **Documented baselines** — still the live default, because no superior replacement model has been validated
  by any method tried so far.
- **Legacy-empirical baselines** — forensic value only: they explain how the old baked table behaved, not proof
  of anything about correctness.
- **Roster-economics results** — independent, real evidence about positional demand; useful input to a future
  scarcity redesign, not identical to a replacement-normalization baseline.
- **This backtester** — useful for identifying future production tier structure (a real, distinct concept), not
  for selecting replacement ranks. Kept as a diagnostic tool, not a decision engine.

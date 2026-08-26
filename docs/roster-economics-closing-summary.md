# Roster-Economics Workstream — Closing Summary

**Status: CLOSED.** No live baseline was changed. Next step is the backtester.

---

## What this workstream set out to test

The `prod_mult` reconstruction audit found that the legacy baked production table
*behaves as though* three positions used a different replacement-level rank than
documented — most notably DL, which behaved like rank ~22-24 instead of the
documented rank 32. One hypothesis: real competition for shared FLEX/SUPER_FLEX/
IDP_FLEX roster slots explains the gap. This workstream tested that hypothesis
directly against real 2024-2025 lineup data.

## What was built

- `historical_lineup_reconstruction.py` — every real weekly starting lineup for
  2024-2025, reconstructed from Sleeper matchup data, including bench (rostered-
  but-not-started) players.
- `historical_weekly_points_pipeline.py` — real weekly fantasy points under this
  league's exact scoring rules, for the full NFL positional universe (not just
  this league's rostered players), keyed directly by Sleeper player_id.
- `start_rate_curve_analysis.py` — start-rate curves by real, point-in-time
  positional rank (trailing PPG primary, trailing cumulative as a robustness
  check), ranked within position against the full NFL universe, weeks 1-3
  excluded, built per-season then pooled.
- `roster_economics_robustness_checks.py` — effective demand, coverage ranks,
  rosterability-vs-startability separation, bin-width sensitivity, block
  bootstrap, and a real (not assumed) dual-eligibility consistency check.
- `db_bootstrap_sanity_check.py` — targeted verification that a bootstrap/point-
  estimate discrepancy for DB was small-sample behavior, not a bug.

Two real bugs were found and fixed during this process, before the results were
trustworthy:
1. Dedicated-slot demand must be counted by the **slot filled**, not the
   player's own primary position (dual DL/LB-eligible EDGE defenders were
   contaminating the DL/LB dedicated counts).
2. A "benched" observation only counts if the player **actually had a real
   recorded game that week** — an injured/bye-week player retains an elite
   trailing rank for the rest of the season while being correctly benched every
   remaining week, which is not a lineup-competition signal.

## The result: the specific hypothesis did not survive contact with real data

| Position | Roster-economics conclusion | Documented | Legacy-reconstructed | Real behavior |
|---|---|---|---|---|
| QB | Behavioral cliff unstable (width-3 vs width-5 disagree by 14 ranks); legacy formula already independently validated at 93.9% | 18 | 18 | Unresolved — no action |
| RB | 2024-25 demand ~25-28, materially shallower than either baseline — but the league just changed 1→2 dedicated RB slots for 2026 | 32 | 37 | ~25-28 (old rules only) |
| WR | Real demand supports documented (~36) over legacy (~43) on 3 independent metrics | 36 | 43 | ~31-36 |
| TE | Broadly compatible with documented | 15 | 16 | ~13 |
| **DL** | Real demand rejects the roster-economics explanation for legacy ~23; supports the ~32 neighborhood instead | 32 | 23 | ~29-36 |
| LB | Very deep real demand, no clean cliff found; 1→2 dedicated slot change for 2026 | 32 | 32 | Never crashes below 50% by rank 58 |
| DB | Deep real demand; single-cliff concept doesn't fit well; bootstrap-verified stable (see sanity check) | 32 | 30 | ~38-40, but statistically noisy |

**The headline finding is a reversal, not a confirmation.** DL's real lineup
behavior is much closer to the *documented* baseline (32) than the legacy-
reconstructed one (23) that motivated this whole workstream. The specific
theory — "real flex competition explains why the legacy table behaves like
DL23" — is not supported. DL23 still accurately *reproduces* the old baked
table; it just isn't independently supported by how real managers actually
use DL depth.

## The most important conceptual finding

**Start-rate cliff and production replacement level are different concepts.**
A start-rate curve is behavioral — it reflects roster construction, injuries,
byes, manager preferences, and bench depth. A production baseline is a
modeling/economic normalization anchor. There's no requirement that they be
the same number. This lineup-behavior data should be treated as **independent
roster-demand evidence**, not as the mechanism for deriving `PROD_MULT_DATA`'s
replacement baseline directly.

## What did NOT get resolved, and why that's fine

- **LB and DB may not have a clean single-rank "cliff" at all** in this roster
  format — both show real demand extending far deeper than any candidate
  baseline. This doesn't mean the baseline should simply move to 40+; it means
  a single replacement rank may be an imperfect model for these two positions.
  Logged as a technical-backlog item (continuous positional scarcity curves),
  not something to fix now.
- **Check A (rosterability vs. startability)** was built but not analyzed in
  depth. Per the final review, this is deferred to a future continuous-
  scarcity redesign, not required to close this workstream.
- **2026 Ruleset B (RB2/LB2) data** hasn't accumulated enough yet. RB and LB's
  results here are explicitly scoped to the old ruleset and need re-checking
  once more of the 2026 season has played out.

## Explicitly NOT concluded

- DL32 is NOT proven correct — only that DL23's proposed roster-economics
  explanation is falsified.
- RB25-28 is NOT actionable yet — real, but under a ruleset the league no
  longer plays under.
- No live baseline in `index.html` or `PROD_MULT_DATA` was touched.

## Next step

Build the backtester: compare the documented-baseline model against the
legacy-reconstruction-baseline model, judged by how well each predicts
**subsequent** fantasy production — not by which one better reproduces the
old baked table. That's the only way to resolve documentation vs.
reconstruction vs. real roster behavior as three separate, sometimes-
disagreeing kinds of evidence without the analysis becoming circular.

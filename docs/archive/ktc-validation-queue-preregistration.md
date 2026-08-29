# KTC Validation Queue V1 — Pre-Registered Decision Rule

Written 2026-08-27, before any real votes have been collected through the
targeted validation queue (`selectKTCTrio()`'s new 15% sampling branch).
The purpose of writing this now, before seeing results, is to prevent
unconscious goalpost-moving later — the criteria below are fixed in
advance, not adjusted after the fact to match whatever the data happens
to show.

## What's being decided

Whether `ratio` (`combined/baseline`, the live formula) or `differential`
(`combined-baseline`, the alternative under consideration) is the better
scarcity formula for offense positions (QB/RB/WR/TE) — determined by
which one better predicts real KTC vote outcomes on matchups specifically
selected because the two formulas disagree.

## Queue details

- **Version**: V1
- **Generated**: 2026-08-26 (see `ktc_validation_queue.json`'s `generated_at`)
- **Player values frozen from**: `prod_mult_pipeline_output.json` as of generation time
- **Composition**: 37 triads, all offense-only (QB/RB/WR/TE), no player
  repeated across the queue. 23 strong/strong disagreements (both
  formulas confident), 14 asymmetric (one formula confident, one only
  mild) — roughly the intended 70/30 split.
- **Intended collection window**: 3 weeks from launch. After the window
  closes, analyze V1 as a closed campaign. If more evidence is still
  needed, generate a fresh V2 from updated player data — never reopen or
  extend V1, and never regenerate V1 in response to how people voted.

## Decision rule

**Ratio or differential will be considered the preferred offensive
scarcity formulation only if ALL of the following hold:**

1. It wins primary leave-one-voter-out mean log loss.
2. It also wins leave-one-voter-out mean Brier score (not just log loss alone).
3. It remains the winner under leave-one-triad-out (the robustness check
   against "generalizes to a new person" vs. "generalizes to a new
   matchup" being conflated). If leave-one-voter-out and leave-one-triad-out
   disagree on the winner, the result is NOT actionable regardless of
   either score individually.
4. The result is not driven by one voter — no single voter should account
   for a disproportionate share of the winning margin. Reviewed via the
   per-voter breakdown table in the analysis report.
5. The result is not driven by one position-pair class — reviewed by
   checking whether the winner holds up separately within strong/strong
   and asymmetric disagreement tiers, not just pooled.
6. Raw directional accuracy is not contradicting the probabilistic
   result — if the log-loss winner has raw directional accuracy at or
   below 50%, something is wrong with the analysis, not just the formula.
7. The advantage is meaningful, not a rounding-level difference (e.g. log
   loss 0.641 vs. 0.640 does not count as a real result, regardless of
   which side of the comparison it falls on).
8. The decoy failure rate is low enough that the queue's design is
   trustworthy (a double-digit-percentage decoy failure rate on any
   single decoy player, triad, or voter should be investigated before
   trusting the formula comparison at all — see the QC section of the
   analysis report).

**If any of these fail, the result is directional evidence at most, not
a basis for changing the live formula.**

## Sample-size tiers

Per the analysis script's own reporting (`ktc_validation_queue_analysis.py`),
three explicit tiers rather than one magic N, since with only 12 real
league voters, voter and triad *coverage* matter as much as raw
observation count:

| Tier | Voters | Triads represented | Observations | Status |
|---|---|---|---|---|
| Early read | < 6 | < 20 | < 40 | Not actionable — inspect for anything obviously broken, nothing more |
| Serious evidence | 6-7 | 20-24 | 40-59 | Worth evaluating stability, not yet a final call |
| Potentially actionable | 8-10+ | 25-30+ | 60-80+ | Check the full 8-point decision rule above before acting |

Even at the "potentially actionable" tier, all 8 criteria above must hold
— hitting a sample-size threshold alone is necessary, not sufficient.

## What happens after a result

- If the decision rule is satisfied: propose the winning formula as a
  candidate for the live `prod_mult` calculation, but do not deploy
  without a separate review of the change itself (this pre-registration
  covers the validation methodology, not the deployment decision).
- If the decision rule is not satisfied by the end of the 3-week window:
  document the inconclusive result, close V1, and decide separately
  whether a V2 campaign (fresh player data, possibly a larger queue) is
  worth running or whether this question stays open pending other
  evidence (e.g., the eventual backtester work once more 2026 data
  accumulates).
- Either way: this pre-registration document itself does not get edited
  after results are in. A new decision (V2, or a different validation
  approach) gets a new document, not a retroactive edit to this one.

# KTC Voting System — Bug Fixes, Pool Filtering, and V1 Validation Queue Freeze

**Status: Three real bugs fixed and deployed. Vote pool filtering redesigned.
V1 validation queue frozen (not deleted) after a real feasibility audit
answered the question it existed to help resolve.**

---

## Three confirmed bugs found via external review, fixed and verified

All three were flagged as findings of varying confidence by three
independent AI reviews of a fresh technical breakdown of the project. Each
was traced through the actual live code (not accepted on inference alone)
before being fixed.

### 1. KTC vote-card endogeneity

The vote card displayed this tool's own live trade value, real 2025
points, and 2026 projection directly on every card — meaning a voter saw
the calculator's own opinion of each player before choosing keep/trade/
cut. Since KTC votes are used as independent evidence (they already
calibrated `POSITION_WEIGHT`, and now feed the ratio-vs-differential
validation queue), a vote isn't independent of the model if the voter can
see the model's answer while casting it. This affected every vote, not
just the validation queue's.

**Fix:** the card now shows only name, team, position, and age (age added
separately — see below) — real, neutral facts a voter needs to identify
who they're voting on, never anything derived from the model's own
opinion.

### 2. Dual-position valuation always picked whichever position paid more

`pickBestPosition()` unconditionally resolved a dual-eligible player (e.g.
DL/LB) to whichever position had the higher `POSITION_WEIGHT` — always LB
over DL, regardless of which position the player actually primarily
played. Worse: because the calling code used `pos || existing.pos` (a
freshly-resolved position always won when truthy), this silently
**overwrote an already-correct, hand-curated position on every live
sync** — not just for new players.

**Fix:** `pickBestPosition()` now uses Sleeper's own first-listed
("primary") position instead of whichever pays more, with a console
warning for visibility. More importantly, an existing curated position now
always wins over a freshly-resolved one — fixed at both call sites
(`mergeLiveRoster()` and `mergeLeagueRosters()`).

### 3. Floor-fallback discontinuity

The rule that rescues a player's value using his role-tier estimate when
real production data hits the absolute floor was triggering off the
already-clamped value (`real <= 0.15`), not a genuine data-quality signal.
Two players with nearly identical real evidence (say, clamped `prod_mult`
0.151 vs. 0.150) could receive wildly different treatment — one keeps his
real, weak number; the other gets fully replaced by a role estimate up to
~2x higher.

**Fix:** now requires both hitting the floor and zero real 2025 games
played (`NO_REAL_PRODUCTION_HISTORY`, baked from `prod_mult_pipeline.py`'s
own real lineage — 610 real players). Verified directly against real data
before shipping: Justin Fields (real, if weak, 9-game season) is correctly
excluded from the rescue; Malachi Fields and Eli Raridon (the genuine
zero-data rookies named in the original bug-fix comment this rule came
from) are correctly included. Of 56 real players sitting at/near the
floor, 22 have zero real games (the intended rescue population) and 34 —
mostly real backup-tier QBs (Fields, Winston, Wentz, etc.) — have genuine,
if weak, playing history that shouldn't be overridden by a generic role
guess.

---

## Vote pool filtering redesign

Separate from the three bugs above — a real design question about which
players should be eligible to appear in a KTC vote at all.

**Root cause investigated:** the vote pool pulled from the entire player
database with no rostered-status check. Since merge functions only ever
add/update entries, never delete them, a player dropped by whoever had
him just sat in the database forever, still fully vote-eligible.

**Fix, following external review:**
- `currentlyRostered` is now tracked on every player entry, set by both
  merge functions. A fresh, complete 12-team roster sync marks anyone it
  doesn't see as `false` — marked, not deleted, since the player database
  has other legitimate uses beyond KTC eligibility.
- Normal voting now requires `currentlyRostered === true`.
- Explicitly rejected requiring real production data as an additional
  filter — that would systematically exclude rookies, injured players,
  and other legitimate future-value dynasty assets, defeating the actual
  purpose of using human market judgment.
- The validation queue got its own, separate, deliberately looser
  eligibility check (`ktcValidationEligible()`), decoupled from the
  stricter normal-voting pool — so tightening ordinary sampling couldn't
  silently shrink or invalidate the pre-registered validation experiment
  already collecting votes.
- Added `KTC_VALIDATION_INVALIDATED`, an empty, manually-maintained list
  for a genuinely material real-world event (season-ending injury,
  retirement, roster cut) affecting a queue player during collection —
  deliberately based only on external events, never on vote results, to
  preserve non-adaptivity.

## Vote card now shows age

Mirrors real KeepTradeCut.com's own vote-card convention (screenshot
comparison) — position, team, and age, nothing value-derived. Uses real
integer age (our actual data precision), not a fabricated decimal to
visually match KTC.com's display.

---

## The feasibility audit, and why V1 is now frozen

Before trusting the newly-separated validation-queue eligibility path, ran
the real audit external review recommended: classify all 37 frozen queue
triads by real current roster status.

**Result: 33 of 37 triads (89%) have a primary disagreement player nobody
in the league currently rosters.** Only 1 triad is fully rostered on all
three players.

This led to a deeper, decisive follow-up: compute the real ratio-vs-
differential disagreement rate among only currently-rostered offense
players, and compare it to the full-universe rate.

| | Full offense universe (547 players) | Rostered-only (295 players) |
|---|---|---|
| Disagreement rate | 1.205% | 0.005% |
| Disagreement pairs found | 1,800 | 2 |
| "Strong" tier disagreements | 337 | 0 |

Among players that actually get traded in this league, ratio and
differential agree on almost every single comparison. The two formulas'
mathematical disagreement is real, but concentrated almost entirely in the
deep/fringe player tier — exactly where V1's 89% unrostered-player problem
came from in the first place. A V2 queue built on a rostered-only
constraint would have only 2 real pairs to work with — not enough to build
a meaningful experiment.

**Decision, following external review's explicit reasoning:** this is a
real, outcome-independent construct-validity finding, discovered before
looking at any vote results — not the kind of thing pre-registration
exists to prevent changing course on. Continuing to collect V1 votes for
the sake of finishing a pre-registered window, once the design has been
shown unable to answer a meaningful question, would just waste real votes.

**Action taken:** `KTC_VALIDATION_QUEUE_ACTIVE` set to `false` — an
explicit, named flag, not a disguised probability change, so intent is
unambiguous to a future reader. Nothing deleted: the 37-triad queue, the
pre-registration document, the invalidation-list mechanism, and any votes
already collected all remain exactly as they are, preserved as documented
history and exploratory evidence.

## What this means for the ratio-vs-differential question overall

Substantially de-prioritized, not fully closed. The original concern was
specifically about a ~7% swing on DL/DB values — a different population
from what got tested here (offense-only, by necessity, since that was the
only data proven clean of the earlier `POSITION_WEIGHT` vote-contamination
issue). This doesn't directly resolve the IDP-specific question. But it
does mean the broader "should the whole formula switch" question is now
much less urgent — if disagreement all but disappears among tradeable
assets in the one population that could be cleanly tested, there's little
reason to expect the IDP side behaves radically differently in kind, even
though it hasn't been directly measured.

## If a future V2 or different validation approach is ever built

Per external review: select for relevance/representativeness as well as
formula disagreement, not disagreement alone. A matchup can be
mathematically perfect (a real, strong disagreement between two formulas)
and experimentally worthless (if nobody in the league has ever heard of
either player). Disagreement should be a necessary condition for a good
validation matchup, not the only one.

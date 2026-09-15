# Draft Pick FV V1 — Historical Outcome Preregistration

**Status:** preregistered before historical rookie-draft or outcome ingestion

## Research question

Does a market-independent outcome model of this league's actual historical rookie draft picks support the deployed draft-pick Fundamental Value scale and round/tier shape?

## Why this study exists

The deployed pick table is internally monotone, but much of its shape is
market-benchmarked and its absolute early-first anchor was chosen to fit
the calculator's existing scale. That is not independent Fundamental Value
validation. This study uses realized football outcomes from this league's
actual historical rookie drafts and explicitly forbids KTC/market data as
an outcome target.

## Scope

- 12-team league.
- Rounds 1-6.
- Early = slots 1-4; Mid = 5-8; Late = 9-12.
- QB/RB/WR/TE/DL/LB/DB.
- Primary horizon = first 3 completed NFL seasons.
- Future-year discount is **out of scope**.
- Multi-pick package consolidation is **out of scope**.
- Salary/contracts, Team Utility, and Market Value are **out of scope**.

## Primary endpoints

**O1 — three-year replacement-adjusted football utility**

For each drafted rookie, annual surplus is:

`max(0, season total points - replacement PPG × scheduled games)`

summed over the first three NFL seasons. O1 tests relative curve **shape**;
its raw units are not called FV.

**O2 — three-year player-equivalent FV**

For each of years 1-3:

`5500 × current position weight × deployed age multiplier × realized production multiplier`

where realized production multiplier is:

`clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)`

with `ratio = season total / (replacement PPG × scheduled games)`.
A player with zero games gets realized production multiplier `0.0`.

The age bridge uses the repository's canonical
`snapshot_values.age_multiplier()` with a fixed role of **Starter**,
age measured on September 1 of the evaluated NFL season, and the realized
production multiplier supplied as both production arguments. This is
intentionally role-neutral: historical role labels are not allowed to
become an outcome-dependent hidden input, and the RB Elite-youth bonus is
therefore off in the primary bridge.

Replacement PPG is full-NFL season PPG at the frozen positional rank among
players with at least 3 games. Scheduled games are 16 through 2020 and 17
from 2021 onward.

O2 is the arithmetic **mean** of the three annual equivalents so the result
remains in player-FV units instead of career-sum units.

## Frozen replacement ranks

- QB 29
- RB 25
- WR 28
- TE 11
- DL 16
- LB 28
- DB 22

## Candidates

- **C0:** exact deployed PICK_BASE; baseline, no fitting.
- **C1:** one-parameter global rescale of C0.
- **C2:** five-parameter monotone round/tier outcome curve with one R1→R2
  cliff parameter, one later-round decay parameter, and shared mid/late
  penalties.
- **C3:** monotone 18-cell diagnostic only; cannot win.

## Data split

Primary-mature classes require three fully completed NFL seasons. At least
**6 complete rookie-draft classes** are required. The **latest two** mature
classes are locked historical validation and cannot be read for fitting.
All earlier mature classes are development.

If the league history does not meet the preregistered maturity/coverage
gates, the study stops as `INSUFFICIENT_HISTORICAL_EVIDENCE`; it does not
weaken the rules after seeing results.

## Selection gates

A replacement candidate must:

- improve locked-validation equal-cell O2 macro MAE by at least **5%** vs C0;
- improve both locked validation draft classes individually;
- avoid >2% regression on O1 normalized shape;
- avoid >2% regression on H2 and mature H4 O2 robustness;
- remain positive and monotone by round and tier;
- avoid non-null parameter-boundary saturation;
- maintain DOB bridge coverage >=85% and position coverage >=95%.

If C1 and C2 are within 1% relative validation MAE, the lower-parameter
candidate wins. If none qualifies, production stays unchanged.

## Uncertainty

10,000-resample bootstrap clustered by **draft class**, never by individual
pick, because picks from one rookie class share class-strength shocks.

## Forbidden

No KTC/market fitting, no 2026 outcomes, no package votes, no named-player
tuning, no future-year discount change, no package-consolidation inference,
and no production bake from this workflow.

## Next step after this preregistration

Build a separate data-catalog workflow that walks the Sleeper predecessor
league chain, identifies unambiguous completed rookie drafts, resolves
players/positions/DOBs, and checks whether the preregistered maturity gates
are actually satisfiable. **No candidate fitting occurs until that catalog
is frozen.**

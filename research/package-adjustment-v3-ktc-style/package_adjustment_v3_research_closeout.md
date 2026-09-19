# Package Adjustment V3 Research Closeout

**Status:** `research_closed_no_successor_candidate`

Package Adjustment V3 is complete.

## Final production decision

**No production change.** Production remains:

`v1.6-v5-size2-composition-overlay`

## Exact fresh-confirmation result

- Frozen effective votes: **600**
- Distinct voter clusters: **30**
- Distinct challenges: **218**
- Coverage: **24 / 24 cells passed**
- Raw additive control held-out log loss: **0.690887**
- `power-g2.01`: **0.690857**
- `power-g2.15`: **0.690627**
- `power-g2.30`: **0.691671**
- Best candidate: **`power-g2.15`**
- Best vs runner-up gap: **0.000230** (required >= 0.002000)
- Improvement vs raw: **0.000260** (required >= 0.005000)
- Bootstrap favorable fraction: **0.9664** (PASS)
- Maximum topology × asset-mix regression: **0.000394** (PASS)

The global power-scarcity family therefore did not earn production eligibility.

## Governance closeout

The exact 600-vote confirmation dataset is now **spent development evidence**.
It may be used to understand why V3 failed and to develop a genuinely new future
architecture, but it may **not** be reused as fresh confirmation evidence.

Do not rescue V3 by trying nearby gamma values on the same results. Do not use the
five KTC development screenshots as a post-hoc tiebreaker.

V3C1 package voting is closed in the calculator. The frozen sampler remains in the
source only as provenance.

All V3-specific GitHub Actions workflows are removed from the active workflow folder
by this closeout, including this closeout workflow itself after execution. Their prior
contents remain recoverable from Git history. The live V1.6 exact-OOS audit and
prospective real-trade evidence capture remain active because they are useful beyond V3.

## Next research cycle

Package Adjustment V4 must begin with a new preregistered structural hypothesis.
The initial direction is explicit **elite-asset concentration plus fragmentation /
piece-count effects**, rather than another global power exponent.

Any V4 candidate selected using the spent V3 evidence will still require a new,
fresh confirmation dataset before production eligibility can be considered.

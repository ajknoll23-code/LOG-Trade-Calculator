# Package Adjustment V4 — Research Closeout

**Status:** `research_closed_no_production_successor`

V4 selected `elite-frag-s75-p210-p330` decisively, with a **0.019545** held-out log-loss
gap over `elite-frag-s50-p210-p330`.

The selected candidate improved held-out log loss over raw addition by
**0.045114** and passed the **0.9716** challenge-cluster bootstrap gate.
It did not earn production eligibility because the frozen safety cap was
violated in **3v3 trades containing picks**:

- allowed maximum subgroup regression: **0.030000**
- observed s75 regression: **0.086259**
- observed s50 regression: **0.081646**

The V4 exact-600 confirmation evidence is now spent. It may be used for
development of a genuinely new preregistered architecture, but it may never
serve as fresh confirmation again.

Production remains `v1.6-v5-size2-composition-overlay`.

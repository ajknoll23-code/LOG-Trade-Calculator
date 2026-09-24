# Draft Pick FV V6.1 — Phase 4 Numerical Solver Erratum

**Decision:** `{decision}`

The first Phase 4 execution failed numerically during the lexicographic LAD tie-break after a feasible primary LAD solution.
No Phase 4 candidate-selection artifact was committed.

This erratum changes only floating-point parameter fixation between sequential HiGHS lexicographic solves.
Candidate families, bounds, objectives, LOYO folds, metrics, bootstrap, eligibility gates, winner rule, and holdout firewall are unchanged.

# Package Adjustment V9 — B5E Post-STOP Burden, Endpoint and Scope Feasibility Audit

**Decision:** `STOP_NO_TESTED_POST_STOP_FORK_RESTORES_FEASIBILITY`

B5E is planning-only after B5D scientifically stopped every screened six-topology design within the preferred 60-voter / 1,440-ballot burden. It does not weaken B5D thresholds and cannot authorize V9 voting or production.

## Fixed operating-characteristic targets

- >=80% joint PASS power for a true full-process 0.020 macro log-loss benefit.
- <=5% false PASS under the null.
- >=95% detection with one unsafe topology.
- >=95% detection with two unsafe topologies.

## Fork A — all six topologies, expanded burden

| Voters | R | C/topology | Ballots | Power | Null | Unsafe-1 detect | Unsafe-2 detect | Qualifies |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 60 | 2 | 120 | 1440 | 0.400 | 0.050 | 0.642 | 0.883 | no |
| 60 | 4 | 60 | 1440 | 0.292 | 0.000 | 0.592 | 0.792 | no |
| 90 | 2 | 180 | 2160 | 0.417 | 0.000 | 0.667 | 0.833 | no |
| 90 | 4 | 90 | 2160 | 0.442 | 0.000 | 0.658 | 0.850 | no |
| 120 | 2 | 240 | 2880 | 0.533 | 0.008 | 0.592 | 0.925 | no |
| 120 | 4 | 120 | 2880 | 0.542 | 0.000 | 0.575 | 0.850 | no |
| 150 | 2 | 300 | 3600 | 0.633 | 0.008 | 0.650 | 0.900 | no |
| 150 | 4 | 150 | 3600 | 0.592 | 0.017 | 0.625 | 0.825 | no |
| 180 | 2 | 360 | 4320 | 0.675 | 0.000 | 0.675 | 0.950 | no |
| 180 | 4 | 180 | 4320 | 0.692 | 0.017 | 0.625 | 0.942 | no |
| 240 | 2 | 480 | 5760 | 0.867 | 0.000 | 0.742 | 0.975 | no |
| 240 | 4 | 240 | 5760 | 0.767 | 0.000 | 0.700 | 0.933 | no |

## Fork B — bounded endpoint efficiency diagnostic

Brier score is compared with log loss on identical generated predictions. No Brier validation threshold or pass gate is selected in B5E.

| R | Brier/log-loss benefit SNR | Brier/log-loss unsafe SNR | Brier null coverage | Promising diagnostic |
|---:|---:|---:|---:|---|
| 2 | 0.974 | 0.931 | 0.925 | no |
| 4 | 0.885 | 0.901 | 0.975 | no |

## Fork C — asymmetric-count scope only (2v3 / 2v4 / 3v4)

This fork changes the product claim. A qualifying result would not validate 2v2, 3v3 or 4v4.

| Voters | R | C/topology | Ballots | Power | Null | Unsafe-1 detect | Unsafe-2 detect | Qualifies |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 36 | 2 | 144 | 864 | 0.300 | 0.025 | 0.833 | 1.000 | no |
| 36 | 4 | 72 | 864 | 0.275 | 0.017 | 0.783 | 0.983 | no |
| 48 | 2 | 192 | 1152 | 0.458 | 0.008 | 0.825 | 0.992 | no |
| 48 | 4 | 96 | 1152 | 0.275 | 0.017 | 0.817 | 0.975 | no |
| 60 | 2 | 240 | 1440 | 0.508 | 0.008 | 0.833 | 0.983 | no |
| 60 | 4 | 120 | 1440 | 0.375 | 0.025 | 0.800 | 0.992 | no |

## Firewall

- No V9 human outcomes exist or were read.
- No production V1.7 predictions were evaluated on V8 votes.
- No actual V9 candidate/comparator predictions were used.
- No endpoint, scope, rule, design, sample size, architecture, or catalog is frozen.
- No production change is authorized.

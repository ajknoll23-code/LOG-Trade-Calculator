# Package Adjustment V9 — B5B Strict Joint-Gate Feasibility Boundary Audit

**Decision:** `STOP_STRICT_GATE_NOT_FEASIBLE_WITHIN_SEARCH_ENVELOPE`

B5B keeps the strict overall + six unpooled topology UCB rule intact. It does not select a V9 candidate, change a gate, or authorize voting/production.

## Why B5B exists

- B5A was operationally/scientifically green as a planning workflow, but its principal 0.020-benefit scenario had 0% joint PASS across every tested design.
- B5A's 0.050 scenario was not usable because random topology perturbations repeatedly fell outside the generic calibration support.
- B5B fixes only that synthetic calibration defect and extends the sample-burden search.

## Primary boundary criterion

- True macro mean log-loss benefit: **0.020**
- Joint PASS power target: **80%**
- Null false-PASS ceiling: **5%**
- Unsafe-topology detection floor: **95%**
- Principal topology NI margin: **0.010**
- Preferred burden ceiling: **60 voters / 1440 ballots / 24 ballots per voter**

## Principal strict-rule results

| C/topology | Votes/challenge | Voters | Ballots | P(.02 PASS) | P(.03 PASS) | P(.04 PASS) | Null false PASS | Unsafe detection | Preferred burden |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 24 | 6 | 36 | 864 | 0.000 | 0.000 | 0.013 | 0.000 | 1.000 | yes |
| 30 | 6 | 45 | 1080 | 0.000 | 0.006 | 0.006 | 0.000 | 0.994 | yes |
| 24 | 8 | 48 | 1152 | 0.000 | 0.006 | 0.013 | 0.000 | 1.000 | yes |
| 36 | 6 | 54 | 1296 | 0.000 | 0.006 | 0.031 | 0.000 | 1.000 | yes |
| 30 | 8 | 60 | 1440 | 0.000 | 0.013 | 0.056 | 0.000 | 1.000 | yes |
| 42 | 6 | 63 | 1512 | 0.000 | 0.013 | 0.106 | 0.000 | 1.000 | no |
| 36 | 8 | 72 | 1728 | 0.000 | 0.025 | 0.094 | 0.000 | 1.000 | no |
| 48 | 6 | 72 | 1728 | 0.000 | 0.006 | 0.125 | 0.000 | 1.000 | no |
| 42 | 8 | 84 | 2016 | 0.000 | 0.037 | 0.169 | 0.000 | 1.000 | no |
| 60 | 6 | 90 | 2160 | 0.000 | 0.025 | 0.156 | 0.000 | 1.000 | no |
| 48 | 8 | 96 | 2304 | 0.000 | 0.025 | 0.237 | 0.000 | 1.000 | no |
| 72 | 6 | 108 | 2592 | 0.006 | 0.113 | 0.319 | 0.000 | 1.000 | no |
| 60 | 8 | 120 | 2880 | 0.000 | 0.094 | 0.356 | 0.000 | 0.994 | no |
| 90 | 6 | 135 | 3240 | 0.013 | 0.156 | 0.481 | 0.000 | 0.988 | no |
| 72 | 8 | 144 | 3456 | 0.000 | 0.138 | 0.475 | 0.000 | 0.994 | no |
| 90 | 8 | 180 | 4320 | 0.025 | 0.250 | 0.725 | 0.000 | 0.994 | no |

## Scientific firewall

- No production V1.7 predictions were evaluated on V8 votes.
- No V8 C1/C0 topology performance is used to select V9 architecture.
- No V9 candidate, comparator implementation, gate, or human-vote design is frozen here.
- A scientific STOP on strict-gate feasibility is a valid green workflow outcome; it is not permission to weaken the gate.

**Production change authorized:** no.


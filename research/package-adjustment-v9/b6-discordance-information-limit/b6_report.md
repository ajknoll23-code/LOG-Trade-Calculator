# Package Adjustment V9 — B6 Topology-Specific Discordance Information-Limit Audit

**Decision:** `PASS_PREFERRED_BURDEN_FEASIBLE`

B6 is synthetic/planning only. No V9 human outcomes exist, no fresh human catalog is generated, and production V1.7 remains unchanged.

## Frozen before feasibility
- Candidate: `V9_SCALE_COHERENT_NORMALIZED_LQ_V6_Q`
- q: `2.9897594788655337` from frozen pre-V8 V6
- theta_min: `0.6`
- familywise harmful-activation alpha: `0.05` via Holm
- live fair band: `7%`
- one vote per unique discordant challenge; 24 ballots/voter; four per topology

## Primary design screen
| Voters | Ballots | Challenges/topology | P(any good activates) | Max harmful-activation UCB95 | Qualifies |
|---:|---:|---:|---:|---:|---|
| 18 | 432 | 72 | 0.758 | 0.081 | no |
| 24 | 576 | 96 | 0.884 | 0.074 | no |
| 30 | 720 | 120 | 0.944 | 0.046 | yes |
| 36 | 864 | 144 | 0.974 | 0.048 | yes |
| 42 | 1008 | 168 | 0.984 | 0.046 | yes |
| 48 | 1152 | 192 | 0.978 | 0.026 | yes |
| 54 | 1296 | 216 | 0.986 | 0.015 | yes |
| 60 | 1440 | 240 | 0.988 | 0.018 | yes |
| 72 | 1728 | 288 | 0.984 | 0.013 | yes |
| 90 | 2160 | 360 | 0.988 | 0.006 | yes |
| 120 | 2880 | 480 | 0.990 | 0.009 | yes |

## Source-only discordance audit
| Topology | Realism accept | Discordance within realistic | Discordant draws |
|---|---:|---:|---:|
| 2v2 | 0.650 | 0.000 | 31 |
| 2v3 | 0.283 | 0.001 | 27 |
| 2v4 | 0.035 | 0.000 | 0 |
| 3v3 | 0.788 | 0.001 | 111 |
| 3v4 | 0.486 | 0.001 | 53 |
| 4v4 | 0.861 | 0.001 | 137 |

## Firewall
- V8 outcomes beyond nuisance planning were not read.
- V8 candidate performance was not used to select the V9 candidate.
- Production V1.7 predictions were not applied to V8 votes.
- No V9 human challenge catalog was generated.
- No production change is authorized.

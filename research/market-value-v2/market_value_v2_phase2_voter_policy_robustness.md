# Market Value V2 Phase 2 — Voter-Policy Robustness

**Decision:** `ACTIONABLE_FOR_PROMOTION_SHADOW`

**RESEARCH ONLY. Market Value V1 remains deployed.**

## Frozen snapshot

- Counted ballots after daily cap: **900**
- League ballots: **489**
- Guest ballots: **411**
- Distinct voters: **30**

## Primary 0.50 guest-weight candidate

- Resolved players: **526**
- Effective vote mass: **388.0**
- Largest single-voter effective share: **7.73%**

## Leave-one-voter-out robustness

- Runs: **30**
- Median Spearman: **0.995056**
- Worst Spearman: **0.976396**
- Worst Top-50 overlap: **84.0%**

## Guest identity-reset stress

- Guest identities split: **17**
- Spearman vs primary: **0.999037**
- Top-50 overlap vs primary: **96.0%**

## Hard gates

- `minimum_distinct_voters`: **PASS**
- `maximum_single_voter_effective_share_pct`: **PASS**
- `leave_one_voter_out_median_spearman`: **PASS**
- `leave_one_voter_out_worst_spearman`: **PASS**
- `leave_one_voter_out_worst_top50_overlap`: **PASS**
- `guest_identity_split_stress_spearman`: **PASS**
- `guest_identity_split_stress_top50_overlap`: **PASS**

## Guest-weight sensitivity

| Guest weight | Resolved | Spearman vs 0.50 | Top-50 overlap | Effective vote mass |
|---:|---:|---:|---:|---:|
| 0.0 | 498 | 0.830657 | 62.0% | 192.0 |
| 0.25 | 526 | 0.982617 | 84.0% | 290.0 |
| 0.5 | 526 | 1.000000 | 100.0% | 388.0 |
| 0.75 | 526 | 0.993200 | 92.0% | 486.0 |
| 1.0 | 526 | 0.982148 | 82.0% | 584.0 |

## Governance

- The 0.50 guest multiplier was not re-fit in this phase.
- Weight sensitivity is descriptive and cannot rescue a failed primary robustness gate.
- The guest split stress specifically targets browser-local identity reset risk.
- Market Value V1, Fundamental Value, Team Utility, and live trade verdicts are unchanged.
- This phase cannot deploy itself.

## Next-step rule

If ACTIONABLE_FOR_PROMOTION_SHADOW, build a separate Market Value V2 production-candidate shadow that changes only the Market Value consumer and proves exact downstream scope. If any primary gate fails, do not promote 0.50; diagnose the failed robustness dimension without tuning against this frozen snapshot.

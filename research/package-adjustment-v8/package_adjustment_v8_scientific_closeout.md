# Package Adjustment V8 — Durable Scientific Stop Closeout

**Operational status:** Green only if this workflow completes and commits this record.
**Scientific decision:** `STOP_V8_TOPOLOGY_SPLIT_NO_DEVELOPMENT_CONFIRMATION`

## Interpretation

- V8 found a strong developmental signal **relative to a near-null raw-sum baseline** on this deliberately near-balanced catalog.
- V8 did **not** compare C1 against production Package Adjustment V1.7.
- The frozen C1 architecture failed preregistered topology safety gates and cannot advance.
- Production V1.7 remains unchanged and no V8 production change is authorized.

## Overall frozen development result

- C0 CV loss: **0.69423431**
- C1 CV loss: **0.49838820**
- Improvement vs raw-sum C0: **0.19584611**
- Coin-flip log loss ln(2): **0.69314718**
- C0 minus ln(2): **+0.00108713**
- Folds improved: **5 / 5**
- Bootstrap one-sided 95% UCB: **-0.13549986**
- LOPO minimum improvement across 143 players: **0.17518962**

## Topology deltas (candidate minus C0; negative is better)

- 2v2: **+0.11357690**
- 2v3: **-0.49878741**
- 2v4: **-0.62053299**
- 3v3: **-0.06881323**
- 3v4: **-0.27133399**
- 4v4: **+0.17081404**

## 2v2 mechanism

- C0 and C1 2v2 package scores are exactly identical on all 10 frozen 2v2 challenges.
- The frozen evaluator fits one pooled `beta` and `delta_left` per candidate/fold across all training topologies.
- C1 therefore receives different 2v2 probabilities because its pooled nuisance calibration is influenced by its non-2v2 score family.
- Cross-applying the nuisance fits reproduces the opposite model's 2v2 loss exactly.
- Reproduced 2v2 candidate-minus-C0 loss: **+0.113576904518**.
- This is an architecture/scale-coherence failure, not a mismatch in the 2v2 score formula.

## Independent 4v4 stop

- Frozen reported 4v4 candidate-minus-C0 loss: **+0.170814035488**.
- Gate 3 permits at most +0.002 for each topology.
- Gate 4 permits at most +0.010 worst-topology regression.
- Under the frozen reported results, both gates still fail if 2v2 is disregarded.
- This statement does **not** claim what a hypothetical five-topology refit would produce.

## C0 beta boundary

- C0 beta hit its preregistered lower bound of **0.05 in all five folds**.
- Together with C0 loss near ln(2), this indicates negligible usable raw-sum signal **within this deliberately near-balanced catalog**.
- Do not compare the numeric beta magnitudes of C0 and C1; their score scales differ.
- The binding lower bound may slightly handicap C0 and therefore slightly overstate C1 improvement versus C0; it does not alter the STOP.

## Frozen gates

- FAIL — `all_6_topologies_improve_or_within_0_002`
- PASS — `bootstrap_one_sided_95_ucb_lt_0`
- PASS — `combined_cv_improvement_ge_0_005`
- PASS — `delta_left_zero_ranking_unchanged`
- PASS — `folds_improved_ge_4`
- PASS — `leave_one_player_out_positive_every_player`
- PASS — `mathematical_invariants_pass`
- FAIL — `worst_topology_regression_le_0_010`

## Production firewall

- Pinned V1.7 verification: **PASS_PINNED_CONTROLLED_LIVE_V1_7_UNCHANGED**
- V8 comparison against V1.7: **NOT PERFORMED**
- Production behavior changed by V8: **NO**
- Production change authorized: **NO**
- V8 confirmation authorized: **NO**
- Post-hoc rescue authorized: **NO**

## Final status

V8 is scientifically closed. Future Package Adjustment work must be a separate preregistered study.

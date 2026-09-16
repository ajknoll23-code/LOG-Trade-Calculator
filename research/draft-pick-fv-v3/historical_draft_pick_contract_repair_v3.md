# Draft Pick FV V3 — Contract-Correct Harvest & Identity Repair

**Decision:** `STOP_PRE_OUTCOME_CONTRACT_REPAIR_IDENTITY_GATE`

This repair corrects one implementation error in Repair #1: a bad/blank duplicate pick occurrence must be excluded and flagged, but it does not retroactively remove the entire league from a source catalog that the preregistration says to use exactly as frozen.

No historical NFL outcomes, KTC/market values, package votes, candidate fits, validation scores, or production changes were read or produced.

## Source contract

- Frozen primary R1-R4 leagues: **213**
- Frozen primary R5 non-IDP leagues: **81**
- Frozen primary R6 non-IDP leagues: **44**
- Frozen R6 IDP sensitivity leagues: **25**
- Whole-league post-hoc requalification: **No**

## Valid-pick retention

- primary_r1_r4: **9988 / 10224 = 97.69%** valid; pooled exact-slot support min/median/max **200 / 209.0 / 212**
- primary_r5: **4715 / 4860 = 97.02%** valid; pooled exact-slot support min/median/max **71 / 80.0 / 81**
- primary_r6: **2977 / 3168 = 93.97%** valid; pooled exact-slot support min/median/max **35 / 41.5 / 44**
- idp_sensitivity_r6: **1611 / 1800 = 89.50%** valid; pooled exact-slot support min/median/max **19 / 22.5 / 24**

## Identity gate

- Eligible unique drafted MFL identities: **1313**
- Resolved: **1196**
- Coverage: **91.09%**
- Required: **95%**
- Gate: **FAIL**

Resolution remains deterministic: exact DynastyProcess IDs first, then the frozen name+position+draft-class fallback. A pinned nflverse player-identity asset that existed before either harvest result is used only for that same fallback rule.

## Outcome firewall

- Historical outcomes read: **No**
- Locked validation scored: **No**
- Candidate fit performed: **No**
- Production change authorized: **No**

## Next step

Stop before historical outcomes. The remaining failure is the frozen 95% identity gate; do not lower it or manually resolve identities after observing outcomes.

# Draft Pick FV V3 — Harvest & Identity Repair

**Decision:** `STOP_PRE_OUTCOME_REPAIR_GATE`

This is a pre-outcome implementation repair. The original STOP record is preserved. No historical NFL outcomes, market/KTC values, package votes, candidate fits, validation scores, or production changes were read or produced.

## Why the original gate stopped

- Original exact-complete leagues: **135 / 213**
- Original structural failures: **78**
- Original identity coverage: **932 / 1,029 = 90.57%**

## Repair

- MFL `pick` is treated as within-round; picks 1-12 map to the frozen 12-team grid.
- Pick 13+ is reported as an out-of-grid source extra rather than causing the entire draft to be reinterpreted as overall numbering.
- `----` / `0000` are blank identities, not players.
- Duplicate player occurrences are excluded under the frozen rule.
- The name+position+draft-class fallback now indexes crosswalk rows even when they have no MFL ID.
- All pooled-source sufficiency thresholds are unchanged and rechecked before the 95% identity gate.

## Repaired source sufficiency

- R1-R4 usable total: **175** (required 180)
- R5 non-IDP usable total: **60** (required 60)
- R6 non-IDP usable total: **26** (required 36)
- R6 minimum per year: **2** (required 3)
- R6 effective years: **4.899** (required 4.5)
- R6 max year share: **0.308** (max 0.3)
- R6 IDP sensitivity total: **16** (required 20)
- Source sufficiency: **FAIL**

## Identity gate

- Eligible unique MFL identities: **1154**
- Resolved: **1051**
- Coverage: **91.07%**
- Required: **95%**
- Identity gate: **FAIL**

## Outcome firewall

- Historical outcomes read: **No**
- Locked validation scored: **No**
- Candidate fit performed: **No**
- Production change authorized: **No**

## Next step

Stop before historical outcomes. Repair only the documented remaining transport/source-sufficiency/identity failure; do not change frozen thresholds, source rules, split, outcomes, or model families.

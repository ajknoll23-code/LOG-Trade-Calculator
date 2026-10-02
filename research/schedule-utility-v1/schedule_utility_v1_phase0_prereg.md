# Schedule Utility V1 — Phase 0 Preregistration

**Status:** `PREREGISTERED_SOURCE_CONTRACT_ONLY`

This phase freezes the Schedule Utility architecture before any predictor-target association is computed.

## V1 purpose

Schedule Utility is a display-only decision-support lens for:

- next 3 games
- rest of fantasy regular season
- explicitly configured fantasy playoff weeks

It does not change Fundamental Value, draft-pick value, Package Adjustment, Team Utility, Market Value, or the Trade Verdict.

## Primary source contract

- Provider: **4for4**
- Signals: **aFPA + Hot Spots**
- Raw/licensed provider rows remain private.
- Public repository artifacts may contain only aggregate or safely derived output.
- V1 offensive position buckets: **QB / RB / WR / TE**
- IDP schedule utility is **out of scope for V1**.
- Missing or ambiguous joins fail closed.

## Frozen architecture

- Unit: player-team-position-week.
- Join schedule context through current team + opponent + week + position.
- Near-term, ROS, and playoff scores remain separate.
- No single blended overall schedule score in V1.
- Positive means easier/more favorable; negative means harder/less favorable.
- Normalize only within position and source snapshot.
- Never impute missing schedule data as neutral.
- Multi-position players cannot be assigned whichever bucket creates the easiest matchup.

## Scientific sequence

1. **1A:** private-source ingestion feasibility — outcomes sealed.
2. **1B:** coverage/disagreement audit — outcomes sealed.
3. **2:** retrospective predictive validation.
4. **3:** prospective weekly shadow.
5. **4:** display-only production consideration.

No FV blending is authorized by this preregistration.

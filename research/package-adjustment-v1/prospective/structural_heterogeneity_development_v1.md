# Package Trade Evidence — B34C Structural Audit

**Status:** Development-only audit + future taxonomy frozen.

## Existing six eligible trades

- Eligible numeric trades: `6`
- Clean 1-for-2/1-for-3 consolidation trades: `1`
- Existing six are permanently development-only.

### Structural classification

- `MANY_FOR_MANY_TRACK_ONLY`: 4
- `ONE_FOR_ONE_NONPACKAGE`: 1
- `ONE_FOR_TWO_WITH_PICK`: 1

### Only clean consolidation observation

- Transaction `1411042150325456896`: Jameson Williams vs 2-asset package
- Raw package/single ratio: `1.1825`
- Raw premium: `18.25%`
- Package FG: `0.150637`
- Implied lambda to equalize under the V0 functional form: `1.0244`

## Future taxonomy

Primary future evidence is restricted to:

- one player on one side;
- exactly two or three resolved assets on the other side;
- frozen pre-trade FVs only;
- transactions strictly after the B34C freeze-anchor commit.

Primary categories:
- `ONE_FOR_THREE_PLAYER_ONLY`
- `ONE_FOR_THREE_WITH_PICK`
- `ONE_FOR_TWO_PLAYER_ONLY`
- `ONE_FOR_TWO_WITH_PICK`

## Maturity review gate

- Future clean trades: `12`
- 1-for-2: at least `3`
- 1-for-3: at least `3`
- Player-only packages: at least `3`
- Pick-containing packages: at least `3`
- Distinct singleton target players: at least `6`

Crossing this gate authorizes only a new modeling preregistration.
It does not authorize fitting or production.

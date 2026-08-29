# FantasyPros API Pipeline Report

Generated from a real, full-population fetch (declared_count == actual_players_returned enforced as a hard failure at fetch time -- a mismatch stops the run rather than committing partial data).


## Player counts by source position

(Uses each player's own real position_id from the API, not the query label used to fetch them -- the IDP query returns a mix of LB/DL/DB players together.)

| Position | Players normalized |
|---|---|
| DB | 202 |
| DL | 175 |
| LB | 152 |
| QB | 83 |
| RB | 130 |
| TE | 122 |
| WR | 190 |

## Milestone-bonus field population check (across the REAL full population, not a 4-player sample)

- Offense players checked: 525
- Offense players with at least one nonzero milestone field: 0
  - Confirmed across the full population, not just the earlier 4-player sample: these fields are **unpopulated in this specific 2026 preseason API response.** Worded deliberately as a snapshot finding, not a permanent platform limitation -- FantasyPros could populate these in a future season, a weekly feed, or a different endpoint version.

## Known, documented gaps (not silently hidden)

- IDP QB hits: no equivalent API field exists. Every IDP player's normalized total is missing this category's real contribution.
- Per-game milestone bonuses: structurally unreconstructable from season-total projections.

## Real source_position labels actually seen from the combined IDP query

['DB', 'DL', 'LB']

(A verified fact from the real response, not an assumption -- if this list contains anything unexpected, the field-coverage numbers below should be checked per-label.)


## IDP field coverage across the real full population (n=529)

Per external review: a field existing in the schema doesn't mean it's actually populated -- checked directly rather than assumed, same as the milestone check above.

| Field | Nonzero players | % nonzero |
|---|---|---|
| def_tackle | 521 | 98.5% |
| def_assist | 521 | 98.5% |
| def_sack | 521 | 98.5% |
| def_tlost | 0 | 0.0%  **UNPOPULATED** |
| def_int | 501 | 94.7% |
| def_pd | 521 | 98.5% |
| def_ff | 521 | 98.5% |
| def_fr | 521 | 98.5% |
| def_td | 519 | 98.1% |
| def_safety | 0 | 0.0%  **UNPOPULATED** |

**def_tlost (TFL) is unpopulated across the entire real IDP population.** This directly affects the archetype investigation this pipeline exists to support -- if TFL isn't real, usable data, that specific piece of the EDGE-vs-tackle-volume question stays unresolved by this source.

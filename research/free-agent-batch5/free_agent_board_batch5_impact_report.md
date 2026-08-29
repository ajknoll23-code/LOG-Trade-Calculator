# Batch 5 — Free-Agent Board Impact Audit

This report compares the immutable deployed Batch 4 free-agent-board runtime snapshot with the current Batch 5 candidate. No network data is used.

## Population

- Batch 4 rendered: **2019**
- Batch 5 rendered: **1998**
- Common stable Sleeper IDs: **1998**
- Removed stale/corrupt rows: **21**
- Added rows: **0**
- Common rows with any value/metadata change: **506**
- Common rows unchanged: **1492**

The 21 removals come from the Batch 5 Sleeper-data hygiene rules (explicitly inactive legacy/duplicate records plus an impossible-age ghost record). They are not model-driven cuts.

## Current production-source coverage

- Speculative role estimate only: **1599**
- Board-specific `FA_PROD_MULT_DATA`: **385**
- Canonical main-calculator `PROD_MULT_DATA`: **13**
- Canonical PLAYER_DB metadata with no real production source: **1**

Batch 5 also fixes a real source-precedence bug: a PLAYER_DB metadata match can no longer suppress a verified FA-specific production number when that player has no canonical PROD_MULT entry.

## Top value risers

| Player | Pos | Team | Old | New | Change |
|---|---:|---:|---:|---:|---:|
| Anquin Barnes | DL | NYG | 619 | 965 | +55.9% |
| Marvin Mims | WR | DEN | 1315 | 1744 | +32.6% |
| Jaydn Ott | RB | KC | 592 | 734 | +24.0% |
| Troy Franklin | WR | DEN | 1729 | 2119 | +22.6% |
| Joseph Ossai | DL | NYJ | 2179 | 2657 | +21.9% |
| Jack Endries | TE | CIN | 556 | 673 | +21.0% |
| Nate Wiggins | DB | BAL | 2077 | 2245 | +8.1% |
| Jermod McCoy | DB | LV | 768 | 829 | +7.9% |
| Deone Walker | DL | BUF | 1185 | 1248 | +5.3% |
| Kenneth Grant | DL | MIA | 1171 | 1231 | +5.1% |
| Keith Abney | DB | DET | 579 | 602 | +4.0% |
| Genesis Smith | DB | LAC | 579 | 602 | +4.0% |
| Malik Muhammad | DB | CHI | 579 | 602 | +4.0% |
| Jalon Kilgore | DB | BUF | 579 | 602 | +4.0% |
| Larry Worth | DB | SF | 579 | 602 | +4.0% |
| Ricardo Hallman | DB | DEN | 579 | 602 | +4.0% |
| Taurean York | LB | DEN | 745 | 774 | +3.9% |
| Anthony Lucas | DL | DET | 619 | 643 | +3.9% |
| TJ Parker | DL | BUF | 619 | 643 | +3.9% |
| LT Overton | DL | DAL | 619 | 643 | +3.9% |

## Top value fallers

| Player | Pos | Team | Old | New | Change |
|---|---:|---:|---:|---:|---:|
| Kendre Miller | RB | NO | 1713 | 734 | -57.2% |
| Spencer Rattler | QB | NO | 2277 | 976 | -57.1% |
| Tyrod Taylor | QB | GB | 1366 | 586 | -57.1% |
| Tanner McKee | QB | PHI | 2277 | 1073 | -52.9% |
| Deion Burks | WR | IND | 1348 | 701 | -48.0% |
| Kevin Coleman | WR | MIA | 1059 | 578 | -45.4% |
| Sam Roush | TE | CHI | 769 | 448 | -41.7% |
| Oren Burks | LB | CIN | 1012 | 637 | -37.1% |
| Ben Sinnott | TE | WAS | 881 | 600 | -31.9% |
| Tip Reiman | TE | ARI | 881 | 600 | -31.9% |
| Ben Yurosek | TE | MIN | 881 | 600 | -31.9% |
| Nate Boerkircher | TE | JAX | 881 | 600 | -31.9% |
| Seydou Traore | TE | MIA | 881 | 600 | -31.9% |
| Riley Nowakowski | TE | PIT | 881 | 600 | -31.9% |
| Joe Royer | TE | CLE | 881 | 600 | -31.9% |
| Jack Velling | TE | ATL | 881 | 600 | -31.9% |
| Kyle Juszczyk | RB | SF | 668 | 455 | -31.9% |
| Ameer Abdullah | RB | JAX | 668 | 455 | -31.9% |
| James Conner | RB | ARI | 668 | 455 | -31.9% |
| Jeremy McNichols | RB | WAS | 668 | 455 | -31.9% |

## Removed rows

| Player | Pos | Team | Old value | Old age |
|---|---:|---:|---:|---:|
| Chad Cota | DB | HOU | 653 | 52 |
| Myles White | WR | NYJ | 1210 | 27 |
| Brandon Williams | DB | NYG | 973 | 28 |
| Andy Jones | WR | NYG | 1210 | 27 |
| Daniel Henry | DB | BAL | 816 | 22 |
| Isaac Whitney | WR | ARI | 1210 | 27 |
| Josh Banderas | LB | DEN | 949 | 22 |
| Glen Coffee | RB | SF | 668 | 30 |
| Heath Harding | DB | ATL | 1053 | 24 |
| Duplicate Player | WR | CHI | 1210 | 24 |
| Donnie Ernsberger | TE | TEN | 992 | 25 |
| Duplicate Player | DL | LAR | 788 | 22 |
| Kendall Donnerson | LB | CAR | 1355 | 25 |
| Adonis Alexander | DB | NO | 1053 | 25 |
| Duplicate Player | LB | DEN | 1355 | 27 |
| Dwayne Haskins | QB | PIT | 1290 | 24 |
| Keith Butler | LB | SEA | 840 | 62 |
| Duplicate Player | LB | DEN | 1152 | 23 |
| Joe Forson | WR | KC | 1210 | 24 |
| Duplicate Player | DB | PHI | 1053 | 24 |
| Duplicate Player | DB | DAL | 1053 | 26 |

## Scope boundary / open workstream

**Free-agent valuation-engine parity is closed by Batch 5.** The board's position weights, age curves, role multipliers, canonical PROD_MULT table, PLAYER_DB, aliases, and valuation functions are now generated from `index.html` and CI-enforced.

**Free-agent production lineage remains OPEN.** The 385 displayed rows sourced from `FA_PROD_MULT_DATA` use a separate off-roster production table. Batch 5 ensures those numbers are applied correctly; it does not claim that table has been rebuilt under the newly deployed IDP V1 methodology. That should be audited as its own workstream rather than silently bundled into a frontend parity fix.

# Trade Desk Market Value V1

Method: `league-market-value-v1`  
Scale semantics: `league_rank_quantile_mapped_to_trade_desk_points_v1`  
Policy SHA256: `7d3b6723effd6e3bb7a055e9173cfd5426c7a4457ea924b9e52f3b4de39080cf`

## Critical interpretation

**Market Value is a separate league-opinion lens. It is not the fundamental player-value formula and it is not blended into Team Utility.**

The Bradley–Terry rating scale is arbitrary, so V1 preserves the league-vote ranking and maps that ranking onto the point-value distribution of the exact same covered players. The point number is therefore a comparable market-equivalent scale, while the ordering itself comes from league votes.

- Fundamental model players: **565**
- Market-covered players: **469** (83.0%)
- League votes: **449**
- League pairwise observations: **1347**
- Guest votes excluded: **204**
- Dominant voter share: **62.6%**
- Dominant voter majority flag: **YES**

## Largest current Fundamental ↔ Market disagreements

| Player | Pos | Fundamental | Market | Δ | Market rank | Market pct. | Pos direct pairs |
|---|---|---:|---:|---:|---:|---:|---:|
| tucker kraft | TE | 3,739 | 8,895 | +5,156 | 1.0 | 100.0% | 6 |
| drake london | WR | 5,852 | 1,502 | -4,350 | 354.0 | 24.6% | 33 |
| jahmyr gibbs | RB | 8,895 | 4,576 | -4,319 | 46.0 | 90.4% | 26 |
| ty simpson | QB | 1,169 | 5,227 | +4,058 | 15.0 | 97.0% | 11 |
| nick bolton | LB | 5,351 | 1,382 | -3,969 | 368.0 | 21.6% | 39 |
| bhayshul tuten | RB | 3,157 | 6,679 | +3,522 | 2.0 | 99.8% | 26 |
| david bailey | DL | 2,374 | 5,852 | +3,478 | 5.0 | 99.1% | 55 |
| brian burns | DL | 5,623 | 2,305 | -3,318 | 287.0 | 38.9% | 55 |
| dorian williams | LB | 2,297 | 5,493 | +3,196 | 10.0 | 98.1% | 39 |
| malik davis | RB | 807 | 3,984 | +3,177 | 75.0 | 84.2% | 26 |
| devon achane | RB | 6,679 | 3,625 | -3,054 | 108.0 | 77.1% | 26 |
| nicholas singleton | RB | 1,001 | 3,968 | +2,967 | 79.0 | 83.3% | 26 |
| jaylen waddle | WR | 4,576 | 1,636 | -2,940 | 347.0 | 26.1% | 33 |
| devin lloyd | LB | 4,363 | 1,425 | -2,938 | 362.0 | 22.9% | 39 |
| kyle louis | LB | 968 | 3,894 | +2,926 | 84.0 | 82.3% | 39 |
| max klare | TE | 780 | 3,636 | +2,856 | 106.0 | 77.6% | 6 |
| trevon moehrig | DB | 3,636 | 783 | -2,853 | 448.0 | 4.5% | 48 |
| jonah coleman | RB | 1,126 | 3,974 | +2,848 | 77.0 | 83.8% | 26 |
| zach ertz | TE | 805 | 3,625 | +2,820 | 109.0 | 76.9% | 6 |
| jake golday | LB | 1,162 | 3,974 | +2,812 | 78.0 | 83.5% | 39 |
| dj giddens | RB | 734 | 3,539 | +2,805 | 120.0 | 74.6% | 26 |
| jameson williams | WR | 4,829 | 2,026 | -2,803 | 315.0 | 32.9% | 33 |
| fernando mendoza | QB | 2,150 | 4,952 | +2,802 | 23.0 | 95.3% | 11 |
| cj allen | LB | 2,021 | 4,810 | +2,789 | 30.0 | 93.8% | 39 |
| austin booker | DL | 3,431 | 670 | -2,761 | 462.0 | 1.5% | 55 |
| cyrus allen | WR | 1,037 | 3,791 | +2,754 | 91.0 | 80.8% | 33 |
| devin singletary | RB | 687 | 3,374 | +2,687 | 141.5 | 70.0% | 26 |
| tj hockenson | TE | 2,305 | 4,975 | +2,670 | 21.0 | 95.7% | 6 |
| xavier watts | DB | 3,416 | 780 | -2,636 | 451.0 | 3.8% | 48 |
| montez sweat | DL | 3,948 | 1,315 | -2,633 | 371.0 | 20.9% | 55 |

## Guardrails

- `league_only.player_ratings` is the only market ordering source.
- Guest votes are not blended into Market Value V1.
- A market value never changes the deployed fundamental value.
- Team Utility remains a separate roster-specific calculation.
- Unrated players have no Market Value V1 rather than receiving an invented estimate.
- Voter concentration and direct positional sample size are carried with the output.

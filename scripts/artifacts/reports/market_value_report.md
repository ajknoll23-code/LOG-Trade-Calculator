# Trade Desk Market Value V1

Method: `league-market-value-v1`  
Scale semantics: `league_rank_quantile_mapped_to_trade_desk_points_v1`  
Policy SHA256: `7d3b6723effd6e3bb7a055e9173cfd5426c7a4457ea924b9e52f3b4de39080cf`

## Critical interpretation

**Market Value is a separate league-opinion lens. It is not the fundamental player-value formula and it is not blended into Team Utility.**

The Bradley–Terry rating scale is arbitrary, so V1 preserves the league-vote ranking and maps that ranking onto the point-value distribution of the exact same covered players. The point number is therefore a comparable market-equivalent scale, while the ordering itself comes from league votes.

- Fundamental model players: **565**
- Market-covered players: **470** (83.2%)
- League votes: **451**
- League pairwise observations: **1353**
- Guest votes excluded: **364**
- Dominant voter share: **62.3%**
- Dominant voter majority flag: **YES**

## Largest current Fundamental ↔ Market disagreements

| Player | Pos | Fundamental | Market | Δ | Market rank | Market pct. | Pos direct pairs |
|---|---|---:|---:|---:|---:|---:|---:|
| tucker kraft | TE | 3,739 | 8,888 | +5,149 | 1.0 | 100.0% | 6 |
| drake london | WR | 5,852 | 1,502 | -4,350 | 355.0 | 24.5% | 33 |
| jahmyr gibbs | RB | 8,888 | 4,581 | -4,307 | 45.0 | 90.6% | 26 |
| ty simpson | QB | 1,169 | 5,227 | +4,058 | 15.0 | 97.0% | 11 |
| nick bolton | LB | 5,351 | 1,384 | -3,967 | 368.0 | 21.7% | 39 |
| bhayshul tuten | RB | 3,157 | 6,673 | +3,516 | 2.0 | 99.8% | 26 |
| makai lemon | WR | 2,569 | 5,984 | +3,415 | 4.0 | 99.4% | 33 |
| brian burns | DL | 5,623 | 2,309 | -3,314 | 287.0 | 39.0% | 56 |
| david bailey | DL | 2,374 | 5,655 | +3,281 | 6.0 | 98.9% | 56 |
| malik davis | RB | 806 | 3,990 | +3,184 | 75.0 | 84.2% | 26 |
| devon achane | RB | 6,673 | 3,625 | -3,048 | 109.0 | 77.0% | 26 |
| jaylen waddle | WR | 4,576 | 1,585 | -2,991 | 349.0 | 25.8% | 33 |
| nicholas singleton | RB | 1,002 | 3,974 | +2,972 | 79.0 | 83.4% | 26 |
| devin lloyd | LB | 4,363 | 1,426 | -2,937 | 362.0 | 23.0% | 39 |
| kyle louis | LB | 968 | 3,894 | +2,926 | 85.0 | 82.1% | 39 |
| max klare | TE | 780 | 3,644 | +2,864 | 106.0 | 77.6% | 6 |
| jonah coleman | RB | 1,126 | 3,980 | +2,854 | 77.0 | 83.8% | 26 |
| trevon moehrig | DB | 3,636 | 783 | -2,853 | 449.0 | 4.5% | 48 |
| zach ertz | TE | 805 | 3,625 | +2,820 | 110.0 | 76.8% | 6 |
| dj giddens | RB | 734 | 3,549 | +2,815 | 120.0 | 74.6% | 26 |
| jake golday | LB | 1,162 | 3,974 | +2,812 | 78.0 | 83.6% | 39 |
| jameson williams | WR | 4,829 | 2,037 | -2,792 | 313.0 | 33.5% | 33 |
| cj allen | LB | 2,021 | 4,796 | +2,775 | 31.0 | 93.6% | 39 |
| fernando mendoza | QB | 2,150 | 4,925 | +2,775 | 24.0 | 95.1% | 11 |
| austin booker | DL | 3,431 | 670 | -2,761 | 463.0 | 1.5% | 56 |
| cyrus allen | WR | 1,037 | 3,794 | +2,757 | 91.0 | 80.8% | 33 |
| devin singletary | RB | 687 | 3,379 | +2,692 | 141.0 | 70.1% | 26 |
| tj hockenson | TE | 2,305 | 4,962 | +2,657 | 22.0 | 95.5% | 6 |
| xavier watts | DB | 3,416 | 780 | -2,636 | 452.0 | 3.8% | 48 |
| kaelon black | RB | 896 | 3,526 | +2,630 | 122.0 | 74.2% | 26 |

## Guardrails

- `league_only.player_ratings` is the only market ordering source.
- Guest votes are not blended into Market Value V1.
- A market value never changes the deployed fundamental value.
- Team Utility remains a separate roster-specific calculation.
- Unrated players have no Market Value V1 rather than receiving an invented estimate.
- Voter concentration and direct positional sample size are carried with the output.

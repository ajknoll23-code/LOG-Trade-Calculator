# Trade Desk Market Value V1

Method: `league-market-value-v1`  
Scale semantics: `league_rank_quantile_mapped_to_trade_desk_points_v1`  
Policy SHA256: `7d3b6723effd6e3bb7a055e9173cfd5426c7a4457ea924b9e52f3b4de39080cf`

## Critical interpretation

**Market Value is a separate league-opinion lens. It is not the fundamental player-value formula and it is not blended into Team Utility.**

The Bradley–Terry rating scale is arbitrary, so V1 preserves the league-vote ranking and maps that ranking onto the point-value distribution of the exact same covered players. The point number is therefore a comparable market-equivalent scale, while the ordering itself comes from league votes.

- Fundamental model players: **565**
- Market-covered players: **478** (84.6%)
- League votes: **489**
- League pairwise observations: **1467**
- Guest votes excluded: **411**
- Dominant voter share: **57.5%**
- Dominant voter majority flag: **YES**

## Largest current Fundamental ↔ Market disagreements

| Player | Pos | Fundamental | Market | Δ | Market rank | Market pct. | Pos direct pairs |
|---|---|---:|---:|---:|---:|---:|---:|
| jeremiyah love | RB | 4,450 | 8,848 | +4,398 | 1.0 | 100.0% | 26 |
| jahmyr gibbs | RB | 8,848 | 4,623 | -4,225 | 44.0 | 91.0% | 26 |
| drake london | WR | 5,852 | 1,998 | -3,854 | 331.0 | 30.8% | 37 |
| nick bolton | LB | 5,351 | 1,563 | -3,788 | 359.5 | 24.8% | 43 |
| ty simpson | QB | 1,169 | 4,912 | +3,743 | 27.0 | 94.5% | 11 |
| sonny styles | LB | 3,273 | 6,638 | +3,365 | 2.0 | 99.8% | 43 |
| malik davis | RB | 805 | 3,984 | +3,179 | 80.0 | 83.4% | 26 |
| devon achane | RB | 6,638 | 3,539 | -3,099 | 126.0 | 73.8% | 26 |
| makai lemon | WR | 2,569 | 5,621 | +3,052 | 8.0 | 98.5% | 37 |
| jaylen waddle | WR | 4,576 | 1,563 | -3,013 | 359.5 | 24.8% | 37 |
| david bailey | DL | 2,374 | 5,351 | +2,977 | 14.0 | 97.3% | 60 |
| nicholas singleton | RB | 1,005 | 3,948 | +2,943 | 86.0 | 82.2% | 26 |
| devin lloyd | LB | 4,363 | 1,425 | -2,938 | 371.0 | 22.4% | 43 |
| max klare | TE | 780 | 3,713 | +2,933 | 105.0 | 78.2% | 6 |
| kyle louis | LB | 968 | 3,889 | +2,921 | 90.0 | 81.3% | 43 |
| zach ertz | TE | 805 | 3,695 | +2,890 | 108.0 | 77.6% | 6 |
| trevon moehrig | DB | 3,636 | 774 | -2,862 | 461.0 | 3.6% | 50 |
| jonah coleman | RB | 1,126 | 3,980 | +2,854 | 81.0 | 83.2% | 26 |
| dj giddens | RB | 734 | 3,562 | +2,828 | 122.0 | 74.6% | 26 |
| jake golday | LB | 1,162 | 3,974 | +2,812 | 82.0 | 83.0% | 43 |
| montez sweat | DL | 3,948 | 1,169 | -2,779 | 397.0 | 17.0% | 60 |
| austin booker | DL | 3,431 | 673 | -2,758 | 470.0 | 1.7% | 60 |
| cj allen | LB | 2,021 | 4,762 | +2,741 | 36.0 | 92.7% | 43 |
| cyrus allen | WR | 1,037 | 3,777 | +2,740 | 98.0 | 79.7% | 37 |
| devin singletary | RB | 686 | 3,405 | +2,719 | 143.0 | 70.2% | 26 |
| jameson williams | WR | 4,829 | 2,150 | -2,679 | 313.0 | 34.6% | 37 |
| fernando mendoza | QB | 2,150 | 4,814 | +2,664 | 31.0 | 93.7% | 11 |
| kaelon black | RB | 896 | 3,549 | +2,653 | 125.0 | 74.0% | 26 |
| xavier watts | DB | 3,416 | 780 | -2,636 | 459.0 | 4.0% | 50 |
| divine deablo | LB | 3,501 | 896 | -2,605 | 439.0 | 8.2% | 43 |

## Guardrails

- `league_only.player_ratings` is the only market ordering source.
- Guest votes are not blended into Market Value V1.
- A market value never changes the deployed fundamental value.
- Team Utility remains a separate roster-specific calculation.
- Unrated players have no Market Value V1 rather than receiving an invented estimate.
- Voter concentration and direct positional sample size are carried with the output.

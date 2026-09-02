# Trade Desk Market Value V1

Method: `league-market-value-v1`  
Scale semantics: `league_rank_quantile_mapped_to_trade_desk_points_v1`  
Policy SHA256: `7d3b6723effd6e3bb7a055e9173cfd5426c7a4457ea924b9e52f3b4de39080cf`

## Critical interpretation

**Market Value is a separate league-opinion lens. It is not the fundamental player-value formula and it is not blended into Team Utility.**

The Bradley–Terry rating scale is arbitrary, so V1 preserves the league-vote ranking and maps that ranking onto the point-value distribution of the exact same covered players. The point number is therefore a comparable market-equivalent scale, while the ordering itself comes from league votes.

- Fundamental model players: **565**
- Market-covered players: **449** (79.5%)
- League votes: **359**
- League pairwise observations: **1077**
- Guest votes excluded: **20**
- Dominant voter share: **66.9%**
- Dominant voter majority flag: **YES**

## Largest current Fundamental ↔ Market disagreements

| Player | Pos | Fundamental | Market | Δ | Market rank | Market pct. | Pos direct pairs |
|---|---|---:|---:|---:|---:|---:|---:|
| ty simpson | QB | 1,169 | 5,621 | +4,452 | 8.0 | 98.4% | 8 |
| jahmyr gibbs | RB | 8,936 | 4,604 | -4,332 | 40.0 | 91.3% | 23 |
| drake london | WR | 5,852 | 1,636 | -4,216 | 333.0 | 25.9% | 27 |
| trey mcbride | TE | 5,087 | 8,936 | +3,849 | 1.0 | 100.0% | 4 |
| malik davis | RB | 808 | 4,096 | +3,288 | 63.0 | 86.2% | 23 |
| nick bolton | LB | 5,351 | 2,101 | -3,250 | 297.0 | 33.9% | 30 |
| devon achane | RB | 6,713 | 3,520 | -3,193 | 118.0 | 73.9% | 23 |
| jaylen waddle | WR | 4,576 | 1,454 | -3,122 | 340.0 | 24.3% | 27 |
| nick emmanwori | DB | 3,465 | 6,564 | +3,099 | 3.0 | 99.6% | 37 |
| kyle louis | LB | 968 | 3,991 | +3,023 | 69.0 | 84.8% | 30 |
| chris olave | WR | 5,445 | 2,445 | -3,000 | 265.0 | 41.1% | 27 |
| devin lloyd | LB | 4,363 | 1,375 | -2,988 | 351.0 | 21.9% | 30 |
| nicholas singleton | RB | 997 | 3,984 | +2,987 | 71.0 | 84.4% | 23 |
| david bailey | DL | 2,374 | 5,351 | +2,977 | 13.0 | 97.3% | 42 |
| jake golday | LB | 1,162 | 4,122 | +2,960 | 62.0 | 86.4% | 30 |
| jonah coleman | RB | 1,126 | 4,079 | +2,953 | 65.0 | 85.7% | 23 |
| zach ertz | TE | 805 | 3,739 | +2,934 | 94.0 | 79.2% | 4 |
| max klare | TE | 780 | 3,713 | +2,933 | 95.0 | 79.0% | 4 |
| cyrus allen | WR | 1,037 | 3,936 | +2,899 | 78.0 | 82.8% | 27 |
| montez sweat | DL | 3,948 | 1,055 | -2,893 | 391.0 | 12.9% | 42 |
| dj giddens | RB | 734 | 3,611 | +2,877 | 106.0 | 76.6% | 23 |
| harold fannin | TE | 2,832 | 5,655 | +2,823 | 6.0 | 98.9% | 4 |
| brian burns | DL | 5,623 | 2,810 | -2,813 | 206.0 | 54.2% | 42 |
| jameson williams | WR | 4,829 | 2,021 | -2,808 | 304.0 | 32.4% | 27 |
| chris bell | WR | 1,106 | 3,852 | +2,746 | 84.0 | 81.5% | 27 |
| divine deablo | LB | 3,501 | 783 | -2,718 | 428.0 | 4.7% | 30 |
| kyle hamilton | DB | 3,791 | 1,074 | -2,717 | 384.0 | 14.5% | 37 |
| devin singletary | RB | 688 | 3,377 | +2,689 | 135.0 | 70.1% | 23 |
| kaelon black | RB | 896 | 3,575 | +2,679 | 111.0 | 75.4% | 23 |
| austin booker | DL | 3,431 | 783 | -2,648 | 429.0 | 4.5% | 42 |

## Guardrails

- `league_only.player_ratings` is the only market ordering source.
- Guest votes are not blended into Market Value V1.
- A market value never changes the deployed fundamental value.
- Team Utility remains a separate roster-specific calculation.
- Unrated players have no Market Value V1 rather than receiving an invented estimate.
- Voter concentration and direct positional sample size are carried with the output.

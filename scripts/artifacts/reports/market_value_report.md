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
| jahmyr gibbs | RB | 10,501 | 4,604 | -5,897 | 40.0 | 91.3% | 23 |
| devon achane | RB | 8,963 | 3,520 | -5,443 | 118.0 | 73.9% | 23 |
| trey mcbride | TE | 5,087 | 10,501 | +5,414 | 1.0 | 100.0% | 4 |
| rome odunze | WR | 4,169 | 8,963 | +4,794 | 2.0 | 99.8% | 27 |
| ty simpson | QB | 1,169 | 5,621 | +4,452 | 8.0 | 98.4% | 8 |
| drake london | WR | 5,852 | 1,636 | -4,216 | 333.0 | 25.9% | 27 |
| malik davis | RB | 868 | 4,132 | +3,264 | 63.0 | 86.2% | 23 |
| nick bolton | LB | 5,351 | 2,101 | -3,250 | 297.0 | 33.9% | 30 |
| jonah coleman | RB | 886 | 4,096 | +3,210 | 65.0 | 85.7% | 23 |
| nicholas singleton | RB | 846 | 3,991 | +3,145 | 71.0 | 84.4% | 23 |
| jaylen waddle | WR | 4,576 | 1,454 | -3,122 | 340.0 | 24.3% | 27 |
| kyle louis | LB | 968 | 4,075 | +3,107 | 69.0 | 84.8% | 30 |
| nick emmanwori | DB | 3,465 | 6,564 | +3,099 | 3.0 | 99.6% | 37 |
| dj giddens | RB | 569 | 3,618 | +3,049 | 106.0 | 76.6% | 23 |
| devin lloyd | LB | 4,363 | 1,355 | -3,008 | 351.0 | 21.9% | 30 |
| david bailey | DL | 2,374 | 5,375 | +3,001 | 13.0 | 97.3% | 42 |
| chris olave | WR | 5,445 | 2,447 | -2,998 | 265.0 | 41.1% | 27 |
| jake golday | LB | 1,162 | 4,156 | +2,994 | 62.0 | 86.4% | 30 |
| max klare | TE | 780 | 3,739 | +2,959 | 95.0 | 79.0% | 4 |
| zach ertz | TE | 805 | 3,742 | +2,937 | 94.0 | 79.2% | 4 |
| cyrus allen | WR | 1,037 | 3,948 | +2,911 | 78.0 | 82.8% | 27 |
| montez sweat | DL | 3,948 | 1,044 | -2,904 | 391.0 | 12.9% | 42 |
| harold fannin | TE | 2,832 | 5,655 | +2,823 | 6.0 | 98.9% | 4 |
| jameson williams | WR | 4,829 | 2,021 | -2,808 | 304.0 | 32.4% | 27 |
| brian burns | DL | 5,623 | 2,818 | -2,805 | 206.0 | 54.2% | 42 |
| chris bell | WR | 1,106 | 3,852 | +2,746 | 84.0 | 81.5% | 27 |
| divine deablo | LB | 3,501 | 780 | -2,721 | 428.0 | 4.7% | 30 |
| kyle hamilton | DB | 3,791 | 1,073 | -2,718 | 384.0 | 14.5% | 37 |
| kaelon black | RB | 896 | 3,585 | +2,689 | 111.0 | 75.4% | 23 |
| anthony hill | LB | 889 | 3,549 | +2,660 | 115.0 | 74.6% | 30 |

## Guardrails

- `league_only.player_ratings` is the only market ordering source.
- Guest votes are not blended into Market Value V1.
- A market value never changes the deployed fundamental value.
- Team Utility remains a separate roster-specific calculation.
- Unrated players have no Market Value V1 rather than receiving an invented estimate.
- Voter concentration and direct positional sample size are carried with the output.

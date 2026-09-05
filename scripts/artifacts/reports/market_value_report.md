# Trade Desk Market Value V1

Method: `league-market-value-v1`  
Scale semantics: `league_rank_quantile_mapped_to_trade_desk_points_v1`  
Policy SHA256: `7d3b6723effd6e3bb7a055e9173cfd5426c7a4457ea924b9e52f3b4de39080cf`

## Critical interpretation

**Market Value is a separate league-opinion lens. It is not the fundamental player-value formula and it is not blended into Team Utility.**

The Bradley–Terry rating scale is arbitrary, so V1 preserves the league-vote ranking and maps that ranking onto the point-value distribution of the exact same covered players. The point number is therefore a comparable market-equivalent scale, while the ordering itself comes from league votes.

- Fundamental model players: **565**
- Market-covered players: **453** (80.2%)
- League votes: **379**
- League pairwise observations: **1137**
- Guest votes excluded: **20**
- Dominant voter share: **68.6%**
- Dominant voter majority flag: **YES**

## Largest current Fundamental ↔ Market disagreements

| Player | Pos | Fundamental | Market | Δ | Market rank | Market pct. | Pos direct pairs |
|---|---|---:|---:|---:|---:|---:|---:|
| ty simpson | QB | 1,169 | 5,623 | +4,454 | 7.0 | 98.7% | 8 |
| jahmyr gibbs | RB | 8,916 | 4,522 | -4,394 | 44.0 | 90.5% | 25 |
| drake london | WR | 5,852 | 1,556 | -4,296 | 338.0 | 25.4% | 29 |
| trey mcbride | TE | 5,087 | 8,916 | +3,829 | 1.0 | 100.0% | 4 |
| malik davis | RB | 807 | 4,075 | +3,268 | 67.0 | 85.4% | 25 |
| devon achane | RB | 6,696 | 3,463 | -3,233 | 124.0 | 72.8% | 25 |
| nick bolton | LB | 5,351 | 2,160 | -3,191 | 295.0 | 35.0% | 32 |
| jaylen waddle | WR | 4,576 | 1,438 | -3,138 | 345.0 | 23.9% | 29 |
| nick emmanwori | DB | 3,465 | 6,564 | +3,099 | 3.0 | 99.6% | 38 |
| jake golday | LB | 1,162 | 4,229 | +3,067 | 59.0 | 87.2% | 32 |
| kyle louis | LB | 968 | 3,974 | +3,006 | 74.0 | 83.8% | 32 |
| chris olave | WR | 5,445 | 2,445 | -3,000 | 267.0 | 41.2% | 29 |
| devin lloyd | LB | 4,363 | 1,382 | -2,981 | 353.0 | 22.1% | 32 |
| nicholas singleton | RB | 999 | 3,934 | +2,935 | 80.0 | 82.5% | 25 |
| zach ertz | TE | 805 | 3,739 | +2,934 | 95.0 | 79.2% | 4 |
| max klare | TE | 780 | 3,713 | +2,933 | 96.0 | 79.0% | 4 |
| rueben bain | DL | 2,026 | 4,925 | +2,899 | 22.0 | 95.4% | 47 |
| montez sweat | DL | 3,948 | 1,073 | -2,875 | 390.0 | 13.9% | 47 |
| jonah coleman | RB | 1,126 | 3,991 | +2,865 | 70.0 | 84.7% | 25 |
| dj giddens | RB | 734 | 3,587 | +2,853 | 110.0 | 75.9% | 25 |
| cyrus allen | WR | 1,037 | 3,889 | +2,852 | 82.0 | 82.1% | 29 |
| brian burns | DL | 5,623 | 2,794 | -2,829 | 212.0 | 53.3% | 47 |
| harold fannin | TE | 2,832 | 5,655 | +2,823 | 6.0 | 98.9% | 4 |
| jameson williams | WR | 4,829 | 2,048 | -2,781 | 302.0 | 33.4% | 29 |
| chris bell | WR | 1,106 | 3,852 | +2,746 | 85.0 | 81.4% | 29 |
| david bailey | DL | 2,374 | 5,087 | +2,713 | 17.0 | 96.5% | 47 |
| kyle hamilton | DB | 3,791 | 1,079 | -2,712 | 383.0 | 15.5% | 38 |
| austin booker | DL | 3,431 | 734 | -2,697 | 439.0 | 3.1% | 47 |
| devin singletary | RB | 688 | 3,370 | +2,682 | 138.0 | 69.7% | 25 |
| xavier watts | DB | 3,416 | 734 | -2,682 | 438.0 | 3.3% | 38 |

## Guardrails

- `league_only.player_ratings` is the only market ordering source.
- Guest votes are not blended into Market Value V1.
- A market value never changes the deployed fundamental value.
- Team Utility remains a separate roster-specific calculation.
- Unrated players have no Market Value V1 rather than receiving an invented estimate.
- Voter concentration and direct positional sample size are carried with the output.

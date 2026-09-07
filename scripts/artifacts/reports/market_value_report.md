# Trade Desk Market Value V1

Method: `league-market-value-v1`  
Scale semantics: `league_rank_quantile_mapped_to_trade_desk_points_v1`  
Policy SHA256: `7d3b6723effd6e3bb7a055e9173cfd5426c7a4457ea924b9e52f3b4de39080cf`

## Critical interpretation

**Market Value is a separate league-opinion lens. It is not the fundamental player-value formula and it is not blended into Team Utility.**

The Bradley–Terry rating scale is arbitrary, so V1 preserves the league-vote ranking and maps that ranking onto the point-value distribution of the exact same covered players. The point number is therefore a comparable market-equivalent scale, while the ordering itself comes from league votes.

- Fundamental model players: **565**
- Market-covered players: **453** (80.2%)
- League votes: **380**
- League pairwise observations: **1140**
- Guest votes excluded: **20**
- Dominant voter share: **68.7%**
- Dominant voter majority flag: **YES**

## Largest current Fundamental ↔ Market disagreements

| Player | Pos | Fundamental | Market | Δ | Market rank | Market pct. | Pos direct pairs |
|---|---|---:|---:|---:|---:|---:|---:|
| jahmyr gibbs | RB | 8,902 | 4,522 | -4,380 | 44.0 | 90.5% | 25 |
| ty simpson | QB | 1,169 | 5,493 | +4,324 | 10.0 | 98.0% | 8 |
| drake london | WR | 5,852 | 1,573 | -4,279 | 337.0 | 25.7% | 29 |
| trey mcbride | TE | 5,087 | 8,902 | +3,815 | 1.0 | 100.0% | 4 |
| bhayshul tuten | RB | 3,157 | 6,564 | +3,407 | 3.0 | 99.6% | 25 |
| malik davis | RB | 807 | 4,079 | +3,272 | 66.0 | 85.6% | 25 |
| devon achane | RB | 6,684 | 3,465 | -3,219 | 123.0 | 73.0% | 25 |
| nick bolton | LB | 5,351 | 2,160 | -3,191 | 295.0 | 35.0% | 32 |
| jaylen waddle | WR | 4,576 | 1,446 | -3,130 | 344.5 | 24.0% | 29 |
| jake golday | LB | 1,162 | 4,230 | +3,068 | 58.0 | 87.4% | 32 |
| kyle louis | LB | 968 | 3,980 | +3,012 | 73.0 | 84.1% | 32 |
| chris olave | WR | 5,445 | 2,439 | -3,006 | 268.0 | 40.9% | 29 |
| devin lloyd | LB | 4,363 | 1,382 | -2,981 | 353.0 | 22.1% | 32 |
| max klare | TE | 780 | 3,739 | +2,959 | 95.0 | 79.2% | 4 |
| zach ertz | TE | 805 | 3,742 | +2,937 | 94.0 | 79.4% | 4 |
| nicholas singleton | RB | 1,000 | 3,936 | +2,936 | 79.0 | 82.7% | 25 |
| jonah coleman | RB | 1,126 | 4,050 | +2,924 | 69.0 | 85.0% | 25 |
| montez sweat | DL | 3,948 | 1,073 | -2,875 | 390.0 | 13.9% | 47 |
| dj giddens | RB | 734 | 3,589 | +2,855 | 110.0 | 75.9% | 25 |
| cyrus allen | WR | 1,037 | 3,889 | +2,852 | 82.0 | 82.1% | 29 |
| rueben bain | DL | 2,026 | 4,855 | +2,829 | 23.0 | 95.1% | 47 |
| brian burns | DL | 5,623 | 2,797 | -2,826 | 211.5 | 53.4% | 47 |
| harold fannin | TE | 2,832 | 5,623 | +2,791 | 7.0 | 98.7% | 4 |
| jameson williams | WR | 4,829 | 2,048 | -2,781 | 302.0 | 33.4% | 29 |
| chris bell | WR | 1,106 | 3,852 | +2,746 | 85.0 | 81.4% | 29 |
| kyle hamilton | DB | 3,791 | 1,077 | -2,714 | 385.0 | 15.0% | 38 |
| david bailey | DL | 2,374 | 5,086 | +2,712 | 18.0 | 96.2% | 47 |
| austin booker | DL | 3,431 | 734 | -2,697 | 439.0 | 3.1% | 47 |
| kaelon black | RB | 896 | 3,585 | +2,689 | 111.0 | 75.7% | 25 |
| devin singletary | RB | 687 | 3,370 | +2,683 | 138.0 | 69.7% | 25 |

## Guardrails

- `league_only.player_ratings` is the only market ordering source.
- Guest votes are not blended into Market Value V1.
- A market value never changes the deployed fundamental value.
- Team Utility remains a separate roster-specific calculation.
- Unrated players have no Market Value V1 rather than receiving an invented estimate.
- Voter concentration and direct positional sample size are carried with the output.
